"""
Agents Scheduler — Cron-Like Task Scheduling
═════════════════════════════════════════════
Background scheduler for executing recurring tasks, cleanup jobs,
health checks, and workflow triggers on a timed basis.

Capabilities:
  1. Cron-Like Scheduling  — Flexible timing (seconds, minutes, hours)
  2. Named Jobs            — Register/unregister by name
  3. One-Shot & Recurring  — Both supported
  4. Priority Queue        — Higher-priority jobs run first
  5. Job History           — Audit trail of all runs
  6. Error Handling        — Retries with backoff
"""

import hashlib
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobFrequency(Enum):
    ONCE = "once"
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
    DAILY = "daily"


@dataclass
class ScheduledJob:
    """A job registered with the scheduler."""
    name: str = ""
    callback: Callable = None
    frequency: JobFrequency = JobFrequency.MINUTES
    interval: int = 1
    priority: int = 5       # 1=highest, 10=lowest
    max_retries: int = 2
    enabled: bool = True
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0
    error_count: int = 0
    last_error: str = ""
    last_duration_ms: float = 0.0

    def __post_init__(self):
        if self.next_run == 0:
            self.next_run = time.time()

    def compute_next_run(self) -> None:
        now = time.time()
        if self.frequency == JobFrequency.ONCE:
            self.enabled = False
            return

        intervals = {
            JobFrequency.SECONDS: self.interval,
            JobFrequency.MINUTES: self.interval * 60,
            JobFrequency.HOURS: self.interval * 3600,
            JobFrequency.DAILY: self.interval * 86400,
        }
        delta = intervals.get(self.frequency, 60)
        self.next_run = now + delta

    @property
    def is_due(self) -> bool:
        return self.enabled and time.time() >= self.next_run


@dataclass
class JobRun:
    """Record of a single job execution."""
    job_name: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    success: bool = False
    error: str = ""
    duration_ms: float = 0.0


class AgentScheduler:
    """
    Background scheduler for recurring tasks with priority queuing,
    retries, and job history tracking.
    """

    MAX_HISTORY = 500

    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._history: Deque[JobRun] = deque(maxlen=self.MAX_HISTORY)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        logger.info("[SCHEDULER] Agent Scheduler initialized")

    def register(self, name: str, callback: Callable,
                 frequency: JobFrequency = JobFrequency.MINUTES,
                 interval: int = 1, priority: int = 5,
                 max_retries: int = 2) -> ScheduledJob:
        """Register a new scheduled job."""
        job = ScheduledJob(
            name=name, callback=callback,
            frequency=frequency, interval=interval,
            priority=priority, max_retries=max_retries,
        )
        with self._lock:
            self._jobs[name] = job
        logger.info(f"[SCHEDULER] Registered: {name} (every {interval} {frequency.value})")
        return job

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._jobs.pop(name, None) is not None

    def enable(self, name: str) -> bool:
        job = self._jobs.get(name)
        if job:
            job.enabled = True
            job.next_run = time.time()
            return True
        return False

    def disable(self, name: str) -> bool:
        job = self._jobs.get(name)
        if job:
            job.enabled = False
            return True
        return False

    # ── Execution ──

    def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="agent-scheduler",
        )
        self._thread.start()
        logger.info("[SCHEDULER] Started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[SCHEDULER] Stopped")

    def _run_loop(self) -> None:
        while self._running:
            try:
                due_jobs = []
                with self._lock:
                    for job in self._jobs.values():
                        if job.is_due:
                            due_jobs.append(job)

                # Sort by priority (lower number = higher priority)
                due_jobs.sort(key=lambda j: j.priority)

                for job in due_jobs:
                    self._execute_job(job)

            except Exception as e:
                logger.error(f"[SCHEDULER] Loop error: {e}")

            time.sleep(1)  # Check every second

    def _execute_job(self, job: ScheduledJob) -> None:
        """Execute a single scheduled job."""
        run = JobRun(job_name=job.name)
        start = time.time()

        retries = 0
        success = False
        error = ""

        while retries <= job.max_retries:
            try:
                job.callback()
                success = True
                break
            except Exception as e:
                error = str(e)
                retries += 1
                if retries <= job.max_retries:
                    time.sleep(min(2 ** retries, 30))  # Exponential backoff

        run.completed_at = time.time()
        run.duration_ms = (run.completed_at - start) * 1000
        run.success = success
        run.error = error

        job.last_run = time.time()
        job.run_count += 1
        job.last_duration_ms = run.duration_ms
        if not success:
            job.error_count += 1
            job.last_error = error
            logger.warning(f"[SCHEDULER] Job failed: {job.name} — {error}")

        job.compute_next_run()
        self._history.append(run)

    def run_now(self, name: str) -> Optional[JobRun]:
        """Manually trigger a job immediately."""
        job = self._jobs.get(name)
        if not job:
            return None
        self._execute_job(job)
        return self._history[-1] if self._history else None

    # ── Status ──

    def list_jobs(self) -> List[Dict]:
        return [
            {
                "name": j.name, "frequency": j.frequency.value,
                "interval": j.interval, "priority": j.priority,
                "enabled": j.enabled, "run_count": j.run_count,
                "error_count": j.error_count,
                "last_duration_ms": round(j.last_duration_ms, 1),
            }
            for j in self._jobs.values()
        ]

    def get_history(self, job_name: str = None, limit: int = 20) -> List[Dict]:
        runs = list(self._history)
        if job_name:
            runs = [r for r in runs if r.job_name == job_name]
        return [
            {
                "job": r.job_name, "success": r.success,
                "duration_ms": round(r.duration_ms, 1),
                "error": r.error,
            }
            for r in runs[-limit:]
        ]

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "total_jobs": len(self._jobs),
            "enabled_jobs": sum(1 for j in self._jobs.values() if j.enabled),
            "total_runs": sum(j.run_count for j in self._jobs.values()),
            "total_errors": sum(j.error_count for j in self._jobs.values()),
        }
