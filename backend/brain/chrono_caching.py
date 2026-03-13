"""
Chrono-Caching — Immutable Event-Sourced State Timeline
──────────────────────────────────────────────────────
Expert-level state management via immutable snapshots.
Enables instant rollback to any previous state using
binary search over the sorted timeline.
"""

import bisect
import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StateSnapshot:
    """An immutable snapshot of agent state at a point in time."""
    timestamp_ms: float
    agent_id: str
    context_matrix: str
    code_state: str
    variable_heap: Dict[str, Any]
    index: int = 0


class ChronoCacheDeltas:
    """
    Chrono-Caching (Time-Traveling State Restoration)

    Implements immutable event sourcing with O(log n) binary-search
    rollback. Snapshots are capped to prevent memory bloat.
    """

    def __init__(self, max_depth: int = 500):
        self._timeline: List[StateSnapshot] = []
        self._timestamps: List[float] = []  # Parallel sorted list for bisect
        self._max_depth = max(10, max_depth)
        logger.info("[CHRONO-CACHE] Event-sourced timeline active (max_depth=%d).", max_depth)

    def capture_snapshot(self, agent_id: str, context_matrix: str, code_state: str,
                         variable_heap: Dict) -> int:
        """
        Capture an immutable snapshot before a risky operation.
        Returns the timeline index.
        """
        ts = time.time() * 1000
        snapshot = StateSnapshot(
            timestamp_ms=ts,
            agent_id=agent_id,
            context_matrix=context_matrix,
            code_state=code_state,
            variable_heap=copy.deepcopy(variable_heap),  # Deep copy for true immutability
            index=len(self._timeline),
        )

        self._timeline.append(snapshot)
        self._timestamps.append(ts)

        # Prune if over capacity
        if len(self._timeline) > self._max_depth:
            self._timeline.pop(0)
            self._timestamps.pop(0)

        logger.debug("[CHRONO-CACHE] Snapshot captured (idx=%d, agent=%s).",
                     snapshot.index, agent_id)
        return len(self._timeline) - 1

    def rewind_time(self, milliseconds_ago: float) -> Optional[StateSnapshot]:
        """
        Find the closest valid state snapshot before the target time.
        Uses binary search for O(log n) rollback.
        """
        if not self._timeline:
            return None

        target_ts = (time.time() * 1000) - milliseconds_ago

        # Binary search for nearest timestamp <= target
        idx = bisect.bisect_right(self._timestamps, target_ts) - 1

        if idx < 0:
            # Target is before all snapshots, return earliest
            logger.warning("[CHRONO-CACHE] Genesis state restored (target before timeline).")
            snapshot = self._timeline[0]
        else:
            snapshot = self._timeline[idx]
            # Truncate future from this point
            self._timeline = self._timeline[:idx + 1]
            self._timestamps = self._timestamps[:idx + 1]
            logger.info("[CHRONO-CACHE] Rewound %.0fms to snapshot [%d].",
                        milliseconds_ago, idx)

        return snapshot

    def rewind_to_index(self, index: int) -> Optional[StateSnapshot]:
        """Direct rollback to a specific snapshot index."""
        if 0 <= index < len(self._timeline):
            self._timeline = self._timeline[:index + 1]
            self._timestamps = self._timestamps[:index + 1]
            logger.info("[CHRONO-CACHE] Rewound to index [%d].", index)
            return self._timeline[-1]
        return None

    @property
    def depth(self) -> int:
        return len(self._timeline)

    @property
    def stats(self) -> dict:
        return {"snapshots": len(self._timeline), "max_depth": self._max_depth}


# Global singleton — always active
chrono_cache = ChronoCacheDeltas()
