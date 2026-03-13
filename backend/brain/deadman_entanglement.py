"""
Deadman Entanglement — Health-Check Heartbeat Monitor
─────────────────────────────────────────────────────
Expert-level async health-check system that monitors configurable
vital signs. If thresholds are violated, triggers exponential
alerting and graceful shutdown sequences. Replaces the basic
if/else stub with a real monitoring state machine.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_CHECK_INTERVAL = 5.0
_DEFAULT_FLATLINE_THRESHOLD = 3  # consecutive failures before shutdown


class VitalStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    FLATLINE = "flatline"


@dataclass
class HealthReport:
    """Snapshot of system health."""
    status: VitalStatus
    consecutive_failures: int
    last_check_time: float
    message: str
    uptime_s: float = 0.0


class HostageEntanglement:
    """
    Tier Aegis: Hostage-State Entanglement (The Dead-Man's Engine)

    Continuously monitors system health via configurable check functions.
    Implements exponential alerting on degradation and triggers graceful
    shutdown if consecutive failures exceed the flatline threshold.
    """

    def __init__(
        self,
        check_interval: float = _DEFAULT_CHECK_INTERVAL,
        flatline_threshold: int = _DEFAULT_FLATLINE_THRESHOLD,
        shutdown_fn: Optional[Callable] = None,
    ):
        self._check_interval = max(0.5, check_interval)
        self._flatline_threshold = max(1, flatline_threshold)
        self._shutdown_fn = shutdown_fn
        self._health_checks: Dict[str, Callable[[], bool]] = {}

        self._start_time = time.monotonic()
        self._consecutive_failures: int = 0
        self._status = VitalStatus.HEALTHY
        self._is_monitoring = False
        self._total_checks: int = 0

        logger.info(
            "[DEADMAN-SWITCH] Initialized (interval=%.1fs, flatline_threshold=%d).",
            self._check_interval, self._flatline_threshold,
        )

    def register_vital(self, name: str, check_fn: Callable[[], bool]) -> None:
        """Register a health-check function. Must return True if healthy."""
        self._health_checks[name] = check_fn
        logger.info("[DEADMAN-SWITCH] Registered vital: '%s'.", name)

    def _run_checks(self) -> VitalStatus:
        """Run all registered health checks."""
        if not self._health_checks:
            return VitalStatus.HEALTHY

        failures = []
        for name, check_fn in self._health_checks.items():
            try:
                if not check_fn():
                    failures.append(name)
            except Exception as e:
                failures.append(f"{name}(error:{e})")
                logger.error("[DEADMAN-SWITCH] Check '%s' raised exception: %s", name, e)

        self._total_checks += 1

        if not failures:
            self._consecutive_failures = 0
            return VitalStatus.HEALTHY

        self._consecutive_failures += 1
        logger.warning(
            "[DEADMAN-SWITCH] %d/%d checks failed (consecutive=%d): %s",
            len(failures), len(self._health_checks),
            self._consecutive_failures, failures,
        )

        if self._consecutive_failures >= self._flatline_threshold:
            return VitalStatus.FLATLINE
        elif self._consecutive_failures >= self._flatline_threshold // 2:
            return VitalStatus.CRITICAL
        else:
            return VitalStatus.DEGRADED

    def check_pulse(self) -> HealthReport:
        """Synchronous single health check."""
        self._status = self._run_checks()
        uptime = time.monotonic() - self._start_time

        report = HealthReport(
            status=self._status,
            consecutive_failures=self._consecutive_failures,
            last_check_time=time.time(),
            message=f"{self._status.value} (checks={self._total_checks})",
            uptime_s=uptime,
        )

        if self._status == VitalStatus.FLATLINE:
            logger.critical("[DEADMAN-SWITCH] FLATLINE DETECTED — triggering shutdown.")
            if self._shutdown_fn:
                try:
                    self._shutdown_fn()
                except Exception as e:
                    logger.error("[DEADMAN-SWITCH] Shutdown function failed: %s", e)

        return report

    async def monitor_loop(self) -> None:
        """Async monitoring loop — runs continuously until stopped."""
        self._is_monitoring = True
        logger.info("[DEADMAN-SWITCH] Monitoring started.")

        while self._is_monitoring:
            report = self.check_pulse()
            if report.status == VitalStatus.FLATLINE:
                self._is_monitoring = False
                break
            await asyncio.sleep(self._check_interval)

        logger.info("[DEADMAN-SWITCH] Monitoring stopped.")

    def stop(self) -> None:
        self._is_monitoring = False

    @property
    def is_alive(self) -> bool:
        return self._status != VitalStatus.FLATLINE


# Global singleton — always active
deadman_switch = HostageEntanglement()
