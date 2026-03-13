"""
Cognitive Metabolism System — Bio-Inspired Energy Management
════════════════════════════════════════════════════════════
Every computation has a metabolic cost (ATP equivalent). The system
maintains homeostasis — prevents burnout during peak load, and uses
idle periods for "digestion" (background consolidation).

Architecture:
  Operation → ATP Cost → Energy Pool → Metabolic State Machine
                              ↓                  ↓
                    Homeostasis Controller   State Transitions
                              ↓           (Rest→Active→Overdrive→Exhausted)
                    Adrenaline Mode (emergency burst)
"""

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MetabolicState(Enum):
    """Biological metabolic states."""
    RESTING = "resting"            # Low activity, regenerating
    ACTIVE = "active"              # Normal processing
    OVERDRIVE = "overdrive"        # Peak performance (temporary)
    EXHAUSTED = "exhausted"        # Burned out, forced cooldown
    RECOVERING = "recovering"      # Post-exhaustion recovery
    DIGESTING = "digesting"        # Background consolidation


@dataclass
class ATPBudget:
    """Energy currency for cognitive operations."""
    current_atp: float = 100.0
    max_atp: float = 100.0
    regen_rate: float = 2.0        # ATP per second during rest
    overdrive_cost: float = 5.0    # Extra ATP cost in overdrive
    adrenaline_boost: float = 30.0 # Emergency ATP injection

    @property
    def level(self) -> float:
        """ATP level as percentage (0.0→1.0)."""
        return self.current_atp / max(self.max_atp, 1.0)

    def consume(self, amount: float) -> bool:
        """Consume ATP. Returns False if insufficient."""
        if self.current_atp >= amount:
            self.current_atp -= amount
            return True
        return False

    def regenerate(self, duration_s: float) -> float:
        """Regenerate ATP over time. Returns amount gained."""
        gain = self.regen_rate * duration_s
        old = self.current_atp
        self.current_atp = min(self.max_atp, self.current_atp + gain)
        return self.current_atp - old

    def inject_adrenaline(self) -> float:
        """Emergency energy boost. Returns amount gained."""
        old = self.current_atp
        self.current_atp = min(
            self.max_atp * 1.2,  # Can exceed normal max briefly
            self.current_atp + self.adrenaline_boost,
        )
        return self.current_atp - old


# Operation cost table (ATP per operation)
OPERATION_COSTS: Dict[str, float] = {
    "think": 5.0,
    "reason": 8.0,
    "verify": 4.0,
    "remember": 2.0,
    "learn": 6.0,
    "tool_call": 3.0,
    "generate": 10.0,
    "search": 3.0,
    "compile": 7.0,
    "mutate": 12.0,
    "speculate": 9.0,
    "crystallize": 6.0,
    "default": 3.0,
}


@dataclass
class MetabolicEvent:
    """Record of a metabolic event."""
    operation: str = ""
    atp_cost: float = 0.0
    atp_remaining: float = 0.0
    state: MetabolicState = MetabolicState.ACTIVE
    timestamp: float = field(default_factory=time.time)


@dataclass
class DigestiveTask:
    """A background consolidation task to run during idle periods."""
    task_id: str = ""
    description: str = ""
    task_fn: Optional[Callable] = None
    priority: float = 0.5
    completed: bool = False


@dataclass
class MetabolismReport:
    """Health report for the cognitive metabolism."""
    state: MetabolicState = MetabolicState.ACTIVE
    atp_level: float = 1.0
    atp_current: float = 100.0
    atp_max: float = 100.0
    total_consumed: float = 0.0
    total_regenerated: float = 0.0
    overdrive_count: int = 0
    exhaustion_count: int = 0
    adrenaline_triggers: int = 0
    digestive_tasks_completed: int = 0

    def summary(self) -> str:
        return (
            f"Metabolism: {self.state.value} | "
            f"ATP={self.atp_current:.0f}/{self.atp_max:.0f} "
            f"({self.atp_level:.0%}) | "
            f"Consumed={self.total_consumed:.0f}"
        )


class CognitiveMetabolism:
    """
    Bio-inspired energy management for sustained peak performance.

    Usage:
        metabolism = CognitiveMetabolism()

        # Before each operation, check if affordable
        if metabolism.can_afford("reason"):
            metabolism.consume("reason")
            do_reasoning()
        else:
            metabolism.enter_recovery()

        # Emergency burst for critical tasks
        metabolism.adrenaline_burst()

        # During idle, run digestive tasks
        metabolism.digest()

        # Health check
        report = metabolism.get_report()
    """

    OVERDRIVE_THRESHOLD = 0.8     # Enter overdrive above this workload
    EXHAUSTION_THRESHOLD = 0.05   # Forced cooldown below this ATP
    RECOVERY_TARGET = 0.5         # Recover until this ATP level
    IDLE_THRESHOLD_S = 5.0        # Seconds of no activity → digesting

    def __init__(self, max_atp: float = 100.0, regen_rate: float = 2.0):
        self._budget = ATPBudget(
            current_atp=max_atp,
            max_atp=max_atp,
            regen_rate=regen_rate,
        )
        self._state = MetabolicState.RESTING
        self._events: deque = deque(maxlen=500)
        self._digestive_queue: deque = deque(maxlen=50)
        self._last_activity: float = time.time()

        # Counters
        self._total_consumed: float = 0.0
        self._total_regenerated: float = 0.0
        self._overdrive_count: int = 0
        self._exhaustion_count: int = 0
        self._adrenaline_count: int = 0
        self._digestive_completed: int = 0

    def can_afford(self, operation: str) -> bool:
        """Check if an operation is affordable."""
        cost = OPERATION_COSTS.get(operation, OPERATION_COSTS["default"])
        if self._state == MetabolicState.OVERDRIVE:
            cost += self._budget.overdrive_cost
        if self._state in (MetabolicState.EXHAUSTED, MetabolicState.RECOVERING):
            return False
        return self._budget.current_atp >= cost

    def consume(self, operation: str) -> float:
        """Consume ATP for an operation. Returns actual cost."""
        self._last_activity = time.time()
        cost = OPERATION_COSTS.get(operation, OPERATION_COSTS["default"])

        if self._state == MetabolicState.OVERDRIVE:
            cost += self._budget.overdrive_cost

        if not self._budget.consume(cost):
            self._enter_exhaustion()
            return 0.0

        self._total_consumed += cost
        self._state = MetabolicState.ACTIVE

        # Check for overdrive
        if self._budget.level < 0.3:
            self._state = MetabolicState.OVERDRIVE
            self._overdrive_count += 1

        # Check for exhaustion
        if self._budget.level < self.EXHAUSTION_THRESHOLD:
            self._enter_exhaustion()

        self._events.append(MetabolicEvent(
            operation=operation,
            atp_cost=cost,
            atp_remaining=self._budget.current_atp,
            state=self._state,
        ))

        return cost

    def adrenaline_burst(self) -> float:
        """Emergency energy injection for critical tasks."""
        self._adrenaline_count += 1
        gained = self._budget.inject_adrenaline()
        self._state = MetabolicState.OVERDRIVE
        logger.warning(
            f"Metabolism: ADRENALINE! +{gained:.0f} ATP "
            f"(now {self._budget.current_atp:.0f})"
        )
        return gained

    def rest(self, duration_s: float = 1.0) -> float:
        """Actively rest to regenerate ATP."""
        self._state = MetabolicState.RESTING
        gained = self._budget.regenerate(duration_s)
        self._total_regenerated += gained

        if self._state == MetabolicState.RECOVERING and self._budget.level >= self.RECOVERY_TARGET:
            self._state = MetabolicState.RESTING
            logger.info("Metabolism: recovery complete")

        return gained

    def digest(self) -> int:
        """Run background consolidation tasks during idle periods."""
        self._state = MetabolicState.DIGESTING
        completed = 0

        while self._digestive_queue and self._budget.level > 0.3:
            task = self._digestive_queue.popleft()
            if task.task_fn:
                try:
                    task.task_fn()
                    task.completed = True
                    completed += 1
                    self._budget.consume(2.0)  # Digestion has a small cost
                except Exception as e:
                    logger.warning(f"Digestive task failed: {e}")

        self._digestive_completed += completed
        if completed:
            logger.info(f"Metabolism: digested {completed} tasks")

        self._state = MetabolicState.RESTING
        return completed

    def schedule_digestive(
        self,
        description: str,
        task_fn: Callable,
        priority: float = 0.5,
    ) -> None:
        """Schedule a background consolidation task."""
        self._digestive_queue.append(DigestiveTask(
            description=description,
            task_fn=task_fn,
            priority=priority,
        ))

    def tick(self) -> MetabolicState:
        """Called periodically to update metabolic state."""
        idle_s = time.time() - self._last_activity

        # Auto-regenerate during idle
        if idle_s > 1.0:
            self.rest(min(idle_s, 5.0))

        # Auto-digest during extended idle
        if idle_s > self.IDLE_THRESHOLD_S and self._digestive_queue:
            self.digest()

        return self._state

    def get_report(self) -> MetabolismReport:
        return MetabolismReport(
            state=self._state,
            atp_level=self._budget.level,
            atp_current=round(self._budget.current_atp, 1),
            atp_max=self._budget.max_atp,
            total_consumed=round(self._total_consumed, 1),
            total_regenerated=round(self._total_regenerated, 1),
            overdrive_count=self._overdrive_count,
            exhaustion_count=self._exhaustion_count,
            adrenaline_triggers=self._adrenaline_count,
            digestive_tasks_completed=self._digestive_completed,
        )

    def get_stats(self) -> Dict[str, Any]:
        r = self.get_report()
        return {
            "state": r.state.value,
            "atp_level": round(r.atp_level, 3),
            "total_consumed": r.total_consumed,
            "total_regenerated": r.total_regenerated,
            "overdrive_count": r.overdrive_count,
            "exhaustion_count": r.exhaustion_count,
            "adrenaline_triggers": r.adrenaline_triggers,
        }

    # ── Private ──

    def _enter_exhaustion(self) -> None:
        self._state = MetabolicState.EXHAUSTED
        self._exhaustion_count += 1
        logger.warning(
            f"Metabolism: EXHAUSTED! ATP={self._budget.current_atp:.1f}. "
            f"Entering forced recovery."
        )
        self._state = MetabolicState.RECOVERING
