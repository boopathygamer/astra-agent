"""
Zeno Engine — Exponential-Backoff Retry with Circuit Breaker
────────────────────────────────────────────────────────────
The Zeno Paradox states that to reach a crash, you must first reach
half-way to the crash, then half of that, infinitely. Practically,
this translates to an exponential-backoff retry engine: each failure
doubles the wait time, mathematically pushing the "crash horizon"
further and further away until the operation succeeds.

Includes a circuit-breaker pattern to prevent cascading failures.
"""

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_DEFAULT_MAX_RETRIES = 8
_DEFAULT_BASE_DELAY_S = 0.1
_DEFAULT_MAX_DELAY_S = 30.0
_CIRCUIT_FAILURE_THRESHOLD = 5
_CIRCUIT_RECOVERY_TIMEOUT_S = 60.0


class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failures exceeded threshold — block calls
    HALF_OPEN = "half_open"  # Testing if recovery is possible


@dataclass
class RetryResult:
    """Result of a retried operation."""
    success: bool
    value: Any = None
    attempts: int = 0
    total_wait_s: float = 0.0
    final_error: Optional[str] = None


class ZenoParadoxEngine:
    """
    Tier Aleph: Zeno's Paradox Engine (Invulnerable Execution)

    Exponential-backoff retry engine with jitter and circuit-breaker
    pattern. The crash horizon is pushed infinitely far away by
    doubling the wait interval on each failure.
    """

    def __init__(
        self,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_delay: float = _DEFAULT_BASE_DELAY_S,
        max_delay: float = _DEFAULT_MAX_DELAY_S,
        failure_threshold: int = _CIRCUIT_FAILURE_THRESHOLD,
        recovery_timeout: float = _CIRCUIT_RECOVERY_TIMEOUT_S,
    ):
        self._max_retries = max(1, max_retries)
        self._base_delay = max(0.001, base_delay)
        self._max_delay = max(base_delay, max_delay)
        self._failure_threshold = max(1, failure_threshold)
        self._recovery_timeout = recovery_timeout

        # Circuit breaker state
        self._circuit_state = CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._last_failure_time: float = 0.0

        self._total_retries: int = 0
        self._total_successes: int = 0
        logger.info(
            "[ZENO-ENGINE] Initialized (max_retries=%d, base_delay=%.3fs, circuit_threshold=%d).",
            self._max_retries, self._base_delay, self._failure_threshold,
        )

    def _compute_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter: delay = min(base * 2^attempt + jitter, max)."""
        exp_delay = self._base_delay * (2 ** attempt)
        jitter = (secrets.randbelow(1000) / 1000.0) * self._base_delay
        return min(exp_delay + jitter, self._max_delay)

    def _check_circuit(self) -> bool:
        """Returns True if the circuit allows the call to proceed."""
        if self._circuit_state == CircuitState.CLOSED:
            return True

        if self._circuit_state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._circuit_state = CircuitState.HALF_OPEN
                logger.info("[ZENO-ENGINE] Circuit HALF_OPEN — allowing probe attempt.")
                return True
            logger.warning("[ZENO-ENGINE] Circuit OPEN — blocking call (%.1fs until recovery).",
                           self._recovery_timeout - elapsed)
            return False

        # HALF_OPEN — allow single probe
        return True

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._total_successes += 1
        if self._circuit_state != CircuitState.CLOSED:
            logger.info("[ZENO-ENGINE] Circuit recovered → CLOSED.")
            self._circuit_state = CircuitState.CLOSED

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        self._last_failure_time = time.monotonic()
        if self._consecutive_failures >= self._failure_threshold:
            self._circuit_state = CircuitState.OPEN
            logger.error("[ZENO-ENGINE] Circuit OPEN — %d consecutive failures.", self._consecutive_failures)

    def run_invulnerable(self, fn: Callable[..., T], *args, **kwargs) -> RetryResult:
        """
        Execute fn with exponential-backoff retries and circuit-breaker protection.
        The crash horizon recedes with each attempt — Zeno's shield.
        """
        if not self._check_circuit():
            return RetryResult(success=False, attempts=0, final_error="Circuit breaker OPEN")

        total_wait = 0.0
        last_error = None

        for attempt in range(self._max_retries):
            try:
                result = fn(*args, **kwargs)
                self._record_success()
                self._total_retries += attempt
                logger.info("[ZENO-ENGINE] Success on attempt %d/%d.", attempt + 1, self._max_retries)
                return RetryResult(success=True, value=result, attempts=attempt + 1, total_wait_s=total_wait)

            except Exception as e:
                last_error = str(e)
                delay = self._compute_delay(attempt)
                total_wait += delay
                logger.warning(
                    "[ZENO-ENGINE] Attempt %d/%d failed: %s. Halving crash distance (wait=%.3fs).",
                    attempt + 1, self._max_retries, last_error, delay,
                )
                time.sleep(delay)

        self._record_failure()
        self._total_retries += self._max_retries
        logger.error("[ZENO-ENGINE] All %d attempts exhausted. Crash horizon reached.", self._max_retries)
        return RetryResult(
            success=False, attempts=self._max_retries,
            total_wait_s=total_wait, final_error=last_error,
        )

    async def run_invulnerable_async(self, fn: Callable, *args, **kwargs) -> RetryResult:
        """Async variant of run_invulnerable for coroutine compatibility."""
        if not self._check_circuit():
            return RetryResult(success=False, attempts=0, final_error="Circuit breaker OPEN")

        total_wait = 0.0
        last_error = None

        for attempt in range(self._max_retries):
            try:
                if asyncio.iscoroutinefunction(fn):
                    result = await fn(*args, **kwargs)
                else:
                    result = await asyncio.to_thread(fn, *args, **kwargs)
                self._record_success()
                return RetryResult(success=True, value=result, attempts=attempt + 1, total_wait_s=total_wait)
            except Exception as e:
                last_error = str(e)
                delay = self._compute_delay(attempt)
                total_wait += delay
                logger.warning("[ZENO-ENGINE] Async attempt %d/%d failed: %s", attempt + 1, self._max_retries, last_error)
                await asyncio.sleep(delay)

        self._record_failure()
        return RetryResult(success=False, attempts=self._max_retries, total_wait_s=total_wait, final_error=last_error)

    @property
    def circuit_state(self) -> CircuitState:
        return self._circuit_state


# Global singleton — always active
zeno_shield = ZenoParadoxEngine()
