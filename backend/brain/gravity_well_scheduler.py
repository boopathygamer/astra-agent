"""
Gravity-Well Task Scheduler — Organic Self-Balancing Priority System
════════════════════════════════════════════════════════════════════
Models the task queue as a gravitational field. Each task has "mass"
(urgency x complexity x user-wait-time). Tasks with higher mass create
stronger "gravity wells" that pull computational resources toward them.
Idle resources naturally "fall" toward the heaviest tasks.

Creates an organic, self-balancing scheduler that adapts without manual tuning.

Architecture:
  Task Submitted → Mass Calculator → Gravity Field → Resource Allocator
                     ↓                    ↓
              Mass = U × C × W²    Gravitational pull ∝ M/d²
"""

import logging
import math
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class TaskState(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GravityTask:
    """A task in the gravitational priority queue."""
    task_id: str = ""
    description: str = ""
    urgency: float = 0.5            # 0.0 (low) → 1.0 (critical)
    complexity: float = 0.5         # 0.0 (trivial) → 1.0 (extreme)
    state: TaskState = TaskState.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    assigned_resources: int = 0
    domain: str = "general"

    def __post_init__(self):
        if not self.task_id:
            self.task_id = secrets.token_hex(6)

    @property
    def wait_time_s(self) -> float:
        """Time this task has been waiting since creation."""
        if self.state == TaskState.ACTIVE:
            return self.started_at - self.created_at
        if self.state == TaskState.COMPLETED:
            return 0.0
        return time.time() - self.created_at

    @property
    def mass(self) -> float:
        """
        Gravitational mass of this task.
        Mass = urgency × complexity × wait_time²

        Wait time is squared so longer-waiting tasks become
        increasingly impossible to ignore — preventing starvation.
        """
        wait_factor = max(1.0, self.wait_time_s / 10.0)  # Normalize to ~10s units
        return self.urgency * self.complexity * (wait_factor ** 2)

    @property
    def gravitational_pull(self) -> float:
        """
        Gravitational pull on resources: F = G × M / d²
        where d is the "distance" (inversely related to priority).
        """
        G = 6.674  # Gravitational constant (arbitrary scaling)
        d = max(0.1, 1.0 - self.urgency)  # Higher urgency = closer distance
        return G * self.mass / (d ** 2)


@dataclass
class ResourceAllocation:
    """Allocation of compute resources to a task."""
    task_id: str = ""
    resources_allocated: int = 0
    pull_strength: float = 0.0
    rank: int = 0


@dataclass
class GravityFieldSnapshot:
    """Snapshot of the current gravitational field state."""
    total_tasks: int = 0
    total_mass: float = 0.0
    strongest_pull: float = 0.0
    strongest_task_id: str = ""
    allocations: List[ResourceAllocation] = field(default_factory=list)
    field_entropy: float = 0.0
    timestamp: float = field(default_factory=time.time)


# ──────────────────────────────────────────────
# Resource Pool
# ──────────────────────────────────────────────

class ResourcePool:
    """Pool of abstract compute resource units."""

    def __init__(self, total_units: int = 10):
        self.total_units = total_units
        self._allocated: Dict[str, int] = {}

    @property
    def available(self) -> int:
        return self.total_units - sum(self._allocated.values())

    def allocate(self, task_id: str, units: int) -> int:
        """Allocate resources to a task. Returns actual allocated count."""
        actual = min(units, self.available)
        if actual > 0:
            self._allocated[task_id] = self._allocated.get(task_id, 0) + actual
        return actual

    def release(self, task_id: str) -> int:
        """Release all resources held by a task."""
        released = self._allocated.pop(task_id, 0)
        return released

    def get_allocation(self, task_id: str) -> int:
        return self._allocated.get(task_id, 0)


# ──────────────────────────────────────────────
# Gravity-Well Scheduler (Main Interface)
# ──────────────────────────────────────────────

class GravityWellScheduler:
    """
    Self-balancing task scheduler using gravitational dynamics.

    Usage:
        scheduler = GravityWellScheduler(total_resources=8)

        # Submit tasks with varying urgency/complexity
        scheduler.submit("compile_project", urgency=0.3, complexity=0.5)
        scheduler.submit("fix_critical_bug", urgency=0.95, complexity=0.8)
        scheduler.submit("update_docs", urgency=0.1, complexity=0.2)

        # Let gravity do its work
        snapshot = scheduler.rebalance()
        # fix_critical_bug gets the most resources automatically!

        # Get next task to process
        next_task = scheduler.pull_next()
    """

    def __init__(self, total_resources: int = 10):
        self._tasks: Dict[str, GravityTask] = {}
        self._pool = ResourcePool(total_resources)
        self._completed_history: List[GravityTask] = []
        self._total_submitted: int = 0
        self._total_rebalances: int = 0

    def submit(
        self,
        description: str,
        urgency: float = 0.5,
        complexity: float = 0.5,
        domain: str = "general",
        task_id: str = "",
    ) -> str:
        """Submit a new task into the gravitational field."""
        task = GravityTask(
            task_id=task_id or secrets.token_hex(6),
            description=description,
            urgency=max(0.01, min(1.0, urgency)),
            complexity=max(0.01, min(1.0, complexity)),
            domain=domain,
        )
        self._tasks[task.task_id] = task
        self._total_submitted += 1

        logger.info(
            f"Gravity: submitted '{description[:50]}' "
            f"(mass={task.mass:.2f}, pull={task.gravitational_pull:.2f})"
        )
        return task.task_id

    def rebalance(self) -> GravityFieldSnapshot:
        """
        Rebalance resource allocations based on current gravitational field.
        Resources naturally flow toward the highest-mass tasks.
        """
        self._total_rebalances += 1
        pending = [
            t for t in self._tasks.values()
            if t.state in (TaskState.PENDING, TaskState.ACTIVE)
        ]

        if not pending:
            return GravityFieldSnapshot()

        # Sort by gravitational pull (descending)
        pending.sort(key=lambda t: t.gravitational_pull, reverse=True)

        # Release all current allocations
        for task in pending:
            self._pool.release(task.task_id)
            task.assigned_resources = 0

        # Allocate proportionally to gravitational pull
        total_pull = sum(t.gravitational_pull for t in pending)
        allocations = []

        for rank, task in enumerate(pending):
            if total_pull > 0:
                share = task.gravitational_pull / total_pull
            else:
                share = 1.0 / len(pending)

            desired = max(1, int(share * self._pool.total_units))
            actual = self._pool.allocate(task.task_id, desired)
            task.assigned_resources = actual

            allocations.append(ResourceAllocation(
                task_id=task.task_id,
                resources_allocated=actual,
                pull_strength=task.gravitational_pull,
                rank=rank + 1,
            ))

        # Calculate field entropy (how spread out the resources are)
        if self._pool.total_units > 0 and pending:
            probs = [
                a.resources_allocated / max(self._pool.total_units, 1)
                for a in allocations if a.resources_allocated > 0
            ]
            entropy = -sum(p * math.log2(max(p, 1e-10)) for p in probs)
        else:
            entropy = 0.0

        total_mass = sum(t.mass for t in pending)
        strongest = pending[0] if pending else None

        snapshot = GravityFieldSnapshot(
            total_tasks=len(pending),
            total_mass=total_mass,
            strongest_pull=strongest.gravitational_pull if strongest else 0.0,
            strongest_task_id=strongest.task_id if strongest else "",
            allocations=allocations,
            field_entropy=entropy,
        )

        logger.debug(
            f"Gravity rebalance: {len(pending)} tasks, "
            f"total_mass={total_mass:.2f}, entropy={entropy:.3f}"
        )

        return snapshot

    def pull_next(self) -> Optional[GravityTask]:
        """
        Pull the next task to process (highest gravitational pull).
        Marks the task as ACTIVE.
        """
        pending = [
            t for t in self._tasks.values()
            if t.state == TaskState.PENDING
        ]

        if not pending:
            return None

        # Highest pull first
        best = max(pending, key=lambda t: t.gravitational_pull)
        best.state = TaskState.ACTIVE
        best.started_at = time.time()

        logger.info(
            f"Gravity: pulled '{best.description[:50]}' "
            f"(mass={best.mass:.2f})"
        )
        return best

    def complete(self, task_id: str) -> None:
        """Mark a task as completed and release its resources."""
        task = self._tasks.pop(task_id, None)
        if task:
            task.state = TaskState.COMPLETED
            task.completed_at = time.time()
            self._pool.release(task_id)
            self._completed_history.append(task)

    def cancel(self, task_id: str) -> None:
        """Cancel a task and release its resources."""
        task = self._tasks.pop(task_id, None)
        if task:
            task.state = TaskState.CANCELLED
            self._pool.release(task_id)

    def get_stats(self) -> Dict[str, Any]:
        pending = sum(1 for t in self._tasks.values() if t.state == TaskState.PENDING)
        active = sum(1 for t in self._tasks.values() if t.state == TaskState.ACTIVE)
        return {
            "total_submitted": self._total_submitted,
            "pending": pending,
            "active": active,
            "completed": len(self._completed_history),
            "total_rebalances": self._total_rebalances,
            "available_resources": self._pool.available,
            "total_resources": self._pool.total_units,
        }
