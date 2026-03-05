"""
Async Task Queue — In-Process Distributed Execution
════════════════════════════════════════════════════
Production-grade async task queue with:
  - Priority-based scheduling (heapq)
  - Configurable worker pool
  - Task lifecycle management (pending → running → done/failed)
  - Cancellation support
  - Retry with exponential backoff
  - Queue statistics and health monitoring

No external dependencies (Redis-compatible interface for future upgrade).
"""

import asyncio
import heapq
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Enums & Data Models
# ══════════════════════════════════════════════════════════════

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"


class TaskPriority(int, Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class TaskResult:
    """Result of a completed task."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: str = ""
    duration_ms: float = 0.0
    retries: int = 0
    worker_id: str = ""


@dataclass
class TaskItem:
    """Internal task representation."""
    task_id: str = ""
    priority: int = TaskPriority.NORMAL
    fn: Optional[Callable] = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    submit_time: float = 0.0
    start_time: float = 0.0
    end_time: float = 0.0
    retries: int = 0
    max_retries: int = 3
    timeout_seconds: float = 60.0
    worker_id: str = ""
    is_async: bool = False

    def __post_init__(self):
        if not self.task_id:
            self.task_id = str(uuid.uuid4())[:12]
        if not self.submit_time:
            self.submit_time = time.time()

    def __lt__(self, other):
        """For heapq ordering: lower priority value = higher priority."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.submit_time < other.submit_time


@dataclass
class QueueStats:
    """Queue statistics."""
    total_submitted: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    avg_wait_ms: float = 0.0
    avg_duration_ms: float = 0.0
    workers_active: int = 0
    workers_total: int = 0
    queue_depth: int = 0


# ══════════════════════════════════════════════════════════════
# Task Queue
# ══════════════════════════════════════════════════════════════

class TaskQueue:
    """
    Async task queue with priority scheduling and worker pool.

    Usage:
        queue = TaskQueue(num_workers=4)
        await queue.start()

        # Submit tasks
        task_id = await queue.submit(my_async_fn, args=(x,), priority=TaskPriority.HIGH)

        # Wait for result
        result = await queue.get_result(task_id, timeout=30.0)

        # Or submit and wait
        result = await queue.submit_and_wait(my_fn, args=(x,))

        # Stats
        stats = queue.get_stats()

        await queue.stop()
    """

    def __init__(self, num_workers: int = 4, max_queue_size: int = 1000):
        self._num_workers = max(1, num_workers)
        self._max_queue_size = max_queue_size
        self._queue: List[TaskItem] = []  # heapq
        self._tasks: Dict[str, TaskItem] = {}
        self._results: Dict[str, TaskResult] = {}
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._queue_event = asyncio.Event()
        self._result_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

        # Stats
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_cancelled = 0
        self._wait_times: List[float] = []
        self._durations: List[float] = []

    async def start(self):
        """Start the worker pool."""
        if self._running:
            return
        self._running = True
        for i in range(self._num_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)
        logger.info(f"TaskQueue started with {self._num_workers} workers")

    async def stop(self, graceful: bool = True):
        """Stop the worker pool."""
        self._running = False
        self._queue_event.set()  # Wake up all workers

        if graceful:
            # Wait for current tasks to finish
            for worker in self._workers:
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass
        else:
            for worker in self._workers:
                worker.cancel()

        self._workers.clear()
        logger.info("TaskQueue stopped")

    async def submit(
        self,
        fn: Callable,
        args: tuple = (),
        kwargs: dict = None,
        priority: int = TaskPriority.NORMAL,
        max_retries: int = 3,
        timeout_seconds: float = 60.0,
    ) -> str:
        """Submit a task to the queue. Returns task_id."""
        if len(self._tasks) >= self._max_queue_size:
            raise RuntimeError(f"Queue full ({self._max_queue_size} tasks)")

        is_async = asyncio.iscoroutinefunction(fn)

        task = TaskItem(
            priority=priority,
            fn=fn,
            args=args,
            kwargs=kwargs or {},
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            is_async=is_async,
        )

        async with self._lock:
            self._tasks[task.task_id] = task
            self._result_events[task.task_id] = asyncio.Event()
            heapq.heappush(self._queue, task)
            self._total_submitted += 1

        self._queue_event.set()
        logger.debug(f"Task {task.task_id} submitted (priority={priority})")
        return task.task_id

    async def submit_and_wait(
        self,
        fn: Callable,
        args: tuple = (),
        kwargs: dict = None,
        priority: int = TaskPriority.NORMAL,
        timeout: float = 60.0,
    ) -> TaskResult:
        """Submit a task and wait for its result."""
        task_id = await self.submit(fn, args, kwargs, priority, timeout_seconds=timeout)
        return await self.get_result(task_id, timeout=timeout)

    async def get_result(self, task_id: str, timeout: float = 30.0) -> Optional[TaskResult]:
        """Wait for and return a task result."""
        event = self._result_events.get(task_id)
        if event is None:
            return None

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error="Timeout waiting for result",
            )

        return self._results.get(task_id)

    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task.status != TaskStatus.PENDING:
                return False
            task.status = TaskStatus.CANCELLED
            self._total_cancelled += 1
            # Signal result
            event = self._result_events.get(task_id)
            if event:
                self._results[task_id] = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.CANCELLED,
                )
                event.set()
        return True

    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        pending = sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)
        running = sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)

        return QueueStats(
            total_submitted=self._total_submitted,
            pending=pending,
            running=running,
            completed=self._total_completed,
            failed=self._total_failed,
            cancelled=self._total_cancelled,
            avg_wait_ms=round(sum(self._wait_times[-100:]) / max(len(self._wait_times[-100:]), 1), 2),
            avg_duration_ms=round(sum(self._durations[-100:]) / max(len(self._durations[-100:]), 1), 2),
            workers_active=running,
            workers_total=self._num_workers,
            queue_depth=len(self._queue),
        )

    # ── Worker Loop ──

    async def _worker_loop(self, worker_id: str):
        """Main worker loop — pulls and executes tasks."""
        logger.debug(f"Worker {worker_id} started")
        while self._running:
            # Wait for work
            self._queue_event.clear()

            task = await self._dequeue()
            if task is None:
                await self._queue_event.wait()
                continue

            if task.status == TaskStatus.CANCELLED:
                continue

            # Execute
            await self._execute_task(task, worker_id)

        logger.debug(f"Worker {worker_id} stopped")

    async def _dequeue(self) -> Optional[TaskItem]:
        """Pop the highest-priority task from the queue."""
        async with self._lock:
            while self._queue:
                task = heapq.heappop(self._queue)
                if task.status == TaskStatus.PENDING:
                    return task
        return None

    async def _execute_task(self, task: TaskItem, worker_id: str):
        """Execute a single task with retry logic."""
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        task.worker_id = worker_id
        wait_ms = (task.start_time - task.submit_time) * 1000
        self._wait_times.append(wait_ms)

        try:
            if task.is_async:
                result = await asyncio.wait_for(
                    task.fn(*task.args, **task.kwargs),
                    timeout=task.timeout_seconds,
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda: task.fn(*task.args, **task.kwargs)
                    ),
                    timeout=task.timeout_seconds,
                )

            task.status = TaskStatus.COMPLETED
            task.result = result
            task.end_time = time.time()
            duration_ms = (task.end_time - task.start_time) * 1000
            self._durations.append(duration_ms)
            self._total_completed += 1

            self._results[task.task_id] = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                duration_ms=duration_ms,
                retries=task.retries,
                worker_id=worker_id,
            )

        except asyncio.TimeoutError:
            await self._handle_failure(task, worker_id, f"Timeout after {task.timeout_seconds}s")

        except Exception as e:
            await self._handle_failure(task, worker_id, f"{type(e).__name__}: {e}")

        finally:
            event = self._result_events.get(task.task_id)
            if event:
                event.set()

    async def _handle_failure(self, task: TaskItem, worker_id: str, error: str):
        """Handle task failure with optional retry."""
        task.retries += 1

        if task.retries <= task.max_retries:
            # Retry with exponential backoff
            backoff = min(2 ** task.retries, 30)
            logger.warning(f"Task {task.task_id} failed (attempt {task.retries}), "
                           f"retrying in {backoff}s: {error}")
            task.status = TaskStatus.PENDING
            await asyncio.sleep(backoff)
            async with self._lock:
                heapq.heappush(self._queue, task)
            self._queue_event.set()
        else:
            task.status = TaskStatus.FAILED
            task.error = error
            task.end_time = time.time()
            duration_ms = (task.end_time - task.start_time) * 1000
            self._total_failed += 1

            self._results[task.task_id] = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=error,
                duration_ms=duration_ms,
                retries=task.retries,
                worker_id=worker_id,
            )
            logger.error(f"Task {task.task_id} permanently failed after {task.retries} retries: {error}")


# ══════════════════════════════════════════════════════════════
# Worker Pool (High-Level API)
# ══════════════════════════════════════════════════════════════

class WorkerPool:
    """
    High-level worker pool for agent processing.

    Usage:
        pool = WorkerPool(num_workers=4, generate_fn=mock_generate)
        await pool.start()

        # Submit agent requests
        result = await pool.process("Write a fibonacci function")

        # Batch processing
        results = await pool.process_batch([
            "Write fibonacci",
            "Solve x² + 1 = 0",
            "Explain recursion",
        ])

        stats = pool.get_stats()
        await pool.stop()
    """

    def __init__(self, num_workers: int = 4, generate_fn: Callable = None):
        self._queue = TaskQueue(num_workers=num_workers)
        self._generate_fn = generate_fn
        self._num_workers = num_workers

    async def start(self):
        """Start the worker pool."""
        await self._queue.start()

    async def stop(self):
        """Stop the worker pool."""
        await self._queue.stop()

    async def process(
        self,
        user_input: str,
        priority: int = TaskPriority.NORMAL,
        timeout: float = 60.0,
        use_thinking_loop: bool = True,
    ) -> TaskResult:
        """Process a single agent request."""
        return await self._queue.submit_and_wait(
            fn=self._process_request,
            args=(user_input, use_thinking_loop),
            priority=priority,
            timeout=timeout,
        )

    async def process_batch(
        self,
        inputs: List[str],
        priority: int = TaskPriority.NORMAL,
        timeout: float = 120.0,
    ) -> List[TaskResult]:
        """Process multiple requests concurrently."""
        # Submit all
        task_ids = []
        for user_input in inputs:
            task_id = await self._queue.submit(
                fn=self._process_request,
                args=(user_input, True),
                priority=priority,
                timeout_seconds=timeout,
            )
            task_ids.append(task_id)

        # Wait for all
        results = []
        for task_id in task_ids:
            result = await self._queue.get_result(task_id, timeout=timeout)
            results.append(result)

        return results

    def _process_request(self, user_input: str, use_thinking_loop: bool = True) -> Dict[str, Any]:
        """Worker function that processes a single request."""
        from agents.controller import AgentController
        agent = AgentController(generate_fn=self._generate_fn)
        result = agent.process(user_input=user_input, use_thinking_loop=use_thinking_loop)
        return {
            "answer": result.answer,
            "confidence": result.confidence,
            "iterations": result.iterations,
            "duration_ms": result.duration_ms,
            "mode": result.mode,
        }

    def get_stats(self) -> QueueStats:
        """Get pool statistics."""
        return self._queue.get_stats()
