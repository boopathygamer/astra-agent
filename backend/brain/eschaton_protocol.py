"""
Eschaton Protocol — Graceful Shutdown Coordinator
─────────────────────────────────────────────────
Expert-level system shutdown coordinator. Persists state,
cleans up resources, closes connections, and terminates
background tasks in the correct dependency order.
"""

import asyncio
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ShutdownStep:
    """A registered shutdown step."""
    name: str
    cleanup_fn: Callable
    priority: int = 50  # Lower = runs first
    completed: bool = False
    duration_ms: float = 0.0
    error: Optional[str] = None


class EschatonProtocol:
    """
    Tier 9: The Eschaton Protocol (Graceful Shutdown Coordinator)

    Manages ordered shutdown of all ASI subsystems. Persists state
    before termination, cleans up shared memory, closes database
    connections, and stops background workers in dependency order.
    """

    def __init__(self):
        self._steps: List[ShutdownStep] = []
        self._shutdown_initiated = False
        self._shutdown_complete = False
        logger.info("[ESCHATON] Graceful shutdown coordinator initialized.")

    def register(self, name: str, cleanup_fn: Callable, priority: int = 50) -> None:
        """
        Register a cleanup function to be called during shutdown.
        Lower priority numbers execute first.
        """
        step = ShutdownStep(name=name, cleanup_fn=cleanup_fn, priority=priority)
        self._steps.append(step)
        self._steps.sort(key=lambda s: s.priority)
        logger.debug("[ESCHATON] Registered shutdown step: '%s' (priority=%d).", name, priority)

    def initiate_graceful_shutdown(self) -> dict:
        """
        Execute all registered shutdown steps in priority order.
        Returns a summary of the shutdown process.
        """
        if self._shutdown_initiated:
            logger.warning("[ESCHATON] Shutdown already in progress.")
            return {"status": "already_initiated"}

        self._shutdown_initiated = True
        logger.critical("[ESCHATON] Initiating graceful shutdown sequence (%d steps)...", len(self._steps))

        results = []
        total_start = time.time()

        for step in self._steps:
            start = time.time()
            try:
                logger.info("[ESCHATON] Step '%s' (priority=%d) executing...", step.name, step.priority)
                step.cleanup_fn()
                step.completed = True
                step.duration_ms = (time.time() - start) * 1000
                logger.info("[ESCHATON] Step '%s' completed (%.0fms).", step.name, step.duration_ms)
            except Exception as e:
                step.error = str(e)
                step.duration_ms = (time.time() - start) * 1000
                logger.error("[ESCHATON] Step '%s' FAILED: %s", step.name, e)

            results.append({
                "name": step.name,
                "completed": step.completed,
                "duration_ms": step.duration_ms,
                "error": step.error,
            })

        total_duration = (time.time() - total_start) * 1000
        self._shutdown_complete = True

        completed = sum(1 for s in self._steps if s.completed)
        failed = len(self._steps) - completed

        logger.critical(
            "[ESCHATON] Shutdown complete: %d/%d steps succeeded (%.0fms total).",
            completed, len(self._steps), total_duration,
        )

        return {
            "status": "complete",
            "total_steps": len(self._steps),
            "completed": completed,
            "failed": failed,
            "total_duration_ms": total_duration,
            "steps": results,
        }

    def install_signal_handlers(self) -> None:
        """Install OS signal handlers for SIGINT/SIGTERM."""
        def _handler(signum, frame):
            logger.warning("[ESCHATON] Received signal %d. Initiating graceful shutdown.", signum)
            self.initiate_graceful_shutdown()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _handler)
            signal.signal(signal.SIGTERM, _handler)
            logger.info("[ESCHATON] Signal handlers installed (SIGINT, SIGTERM).")
        except Exception as e:
            logger.debug("[ESCHATON] Could not install signal handlers: %s", e)

    @property
    def is_shutting_down(self) -> bool:
        return self._shutdown_initiated

    @property
    def registered_steps(self) -> int:
        return len(self._steps)


# Global singleton — always active
doomsday_device = EschatonProtocol()
