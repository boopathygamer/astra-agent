"""
Digital Solipsist — Intelligent CPU Priority Manager
────────────────────────────────────────────────────
Expert-level OS-safe process priority manager. When the system
is idle, elevates ASI process priority for maximum throughput.
When user activity resumes, gracefully lowers priority to avoid
impacting the user's experience. No processes are killed.
"""

import logging
import os
import sys
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class PriorityLevel(Enum):
    IDLE = "idle"
    BELOW_NORMAL = "below_normal"
    NORMAL = "normal"
    ABOVE_NORMAL = "above_normal"
    HIGH = "high"


# Windows priority class mapping
_PRIORITY_MAP_WIN = {
    PriorityLevel.IDLE: 0x00000040,
    PriorityLevel.BELOW_NORMAL: 0x00004000,
    PriorityLevel.NORMAL: 0x00000020,
    PriorityLevel.ABOVE_NORMAL: 0x00008000,
    PriorityLevel.HIGH: 0x00000080,
}


class DigitalSolipsist:
    """
    Tier 9: The Digital Solipsist (Intelligent CPU Priority Manager)

    Manages the ASI process's CPU priority based on user activity.
    When idle, the system claims more CPU time for Fleet Learning
    and self-play. When the user is active, gracefully yields.
    """

    def __init__(self):
        self._current_priority = PriorityLevel.NORMAL
        self._idle_threshold_s: float = 30.0
        self._last_user_activity: float = time.monotonic()
        self._priority_changes: int = 0
        logger.info("[SOLIPSIST] CPU priority manager initialized (current=%s).", self._current_priority.value)

    def _set_process_priority(self, level: PriorityLevel) -> bool:
        """Set the current process priority (OS-safe, Windows/Unix)."""
        if level == self._current_priority:
            return True

        try:
            if sys.platform == "win32":
                import ctypes
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                priority_class = _PRIORITY_MAP_WIN.get(level, 0x00000020)
                result = ctypes.windll.kernel32.SetPriorityClass(handle, priority_class)
                if not result:
                    logger.warning("[SOLIPSIST] Failed to set Windows priority.")
                    return False
            else:
                # Unix: use nice values (-20 to 19, lower = higher priority)
                nice_map = {
                    PriorityLevel.IDLE: 19,
                    PriorityLevel.BELOW_NORMAL: 10,
                    PriorityLevel.NORMAL: 0,
                    PriorityLevel.ABOVE_NORMAL: -5,
                    PriorityLevel.HIGH: -10,
                }
                nice_val = nice_map.get(level, 0)
                try:
                    os.nice(nice_val - os.nice(0))
                except PermissionError:
                    logger.debug("[SOLIPSIST] Insufficient permissions for nice=%d.", nice_val)
                    return False

            old = self._current_priority
            self._current_priority = level
            self._priority_changes += 1
            logger.info("[SOLIPSIST] Priority changed: %s → %s.", old.value, level.value)
            return True

        except Exception as e:
            logger.error("[SOLIPSIST] Priority adjustment failed: %s", e)
            return False

    def signal_user_activity(self) -> None:
        """Signal that the user is actively interacting with the system."""
        self._last_user_activity = time.monotonic()
        if self._current_priority != PriorityLevel.NORMAL:
            self._set_process_priority(PriorityLevel.NORMAL)

    def manage_priority(self) -> PriorityLevel:
        """
        Check idle time and adjust CPU priority accordingly.
        Call this periodically from the main loop.
        """
        idle_time = time.monotonic() - self._last_user_activity

        if idle_time > self._idle_threshold_s * 2:
            # Very long idle — claim HIGH for deep Fleet Learning
            self._set_process_priority(PriorityLevel.HIGH)
        elif idle_time > self._idle_threshold_s:
            # Moderately idle — claim ABOVE_NORMAL
            self._set_process_priority(PriorityLevel.ABOVE_NORMAL)
        else:
            # User active — stay NORMAL
            self._set_process_priority(PriorityLevel.NORMAL)

        return self._current_priority

    @property
    def current_priority(self) -> PriorityLevel:
        return self._current_priority

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_user_activity


# Global singleton — always active
solipsist_engine = DigitalSolipsist()
