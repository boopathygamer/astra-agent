"""
Circuit Breaker — Fault Tolerance for External API Calls
════════════════════════════════════════════════════════
Prevents cascading failures by wrapping external calls in a state machine:

  CLOSED → (failures exceed threshold) → OPEN
  OPEN   → (timeout expires)           → HALF_OPEN
  HALF_OPEN → (test call succeeds)     → CLOSED
  HALF_OPEN → (test call fails)        → OPEN

Usage:
    cb = CircuitBreaker("openai_api", failure_threshold=5, recovery_timeout=60)

    # Manual usage
    if cb.allow_request():
        try:
            result = call_api()
            cb.record_success()
        except Exception as e:
            cb.record_failure()

    # Decorator usage
    @circuit_protected("openai_api")
    async def call_openai(prompt):
        ...
"""

import asyncio
import functools
import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"         # Normal operation
    OPEN = "open"             # Blocking all calls
    HALF_OPEN = "half_open"   # Testing with single call


@dataclass
class CircuitMetrics:
    """Metrics for a single circuit breaker."""
    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0
    total_rejected: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    last_state_change: float = field(default_factory=time.time)
    time_in_open: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "total_rejected": self.total_rejected,
            "consecutive_failures": self.consecutive_failures,
            "success_rate": round(
                self.total_successes / max(self.total_calls, 1), 4
            ),
        }


class CircuitBreaker:
    """
    Circuit breaker for protecting external API calls.

    States:
      CLOSED    — Normal. Requests pass through. Failures are counted.
      OPEN      — All requests are rejected immediately. Timer runs.
      HALF_OPEN — One test request is allowed. Success → CLOSED, Failure → OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._metrics = CircuitMetrics()
        self._open_since: float = 0.0
        self._half_open_calls: int = 0
        self._lock = threading.Lock()

        logger.info(
            f"[CIRCUIT] {name} — threshold={failure_threshold}, "
            f"recovery={recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """Get current state, auto-transitioning OPEN → HALF_OPEN if timeout expired."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._open_since >= self.recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        with self._lock:
            current = self.state
            if current == CircuitState.CLOSED:
                return True
            elif current == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            else:  # OPEN
                self._metrics.total_rejected += 1
                return False

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._metrics.total_calls += 1
            self._metrics.total_successes += 1
            self._metrics.consecutive_failures = 0
            self._metrics.consecutive_successes += 1
            self._metrics.last_success_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                if self._metrics.consecutive_successes >= self.success_threshold:
                    self._transition(CircuitState.CLOSED)
            elif self._state == CircuitState.OPEN:
                pass  # Shouldn't happen

    def record_failure(self, error: str = "") -> None:
        """Record a failed call."""
        with self._lock:
            self._metrics.total_calls += 1
            self._metrics.total_failures += 1
            self._metrics.consecutive_failures += 1
            self._metrics.consecutive_successes = 0
            self._metrics.last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN)
                logger.warning(f"[CIRCUIT] {self.name} — half-open test FAILED, reopening")
            elif self._state == CircuitState.CLOSED:
                if self._metrics.consecutive_failures >= self.failure_threshold:
                    self._transition(CircuitState.OPEN)
                    logger.warning(
                        f"[CIRCUIT] {self.name} — TRIPPED after "
                        f"{self._metrics.consecutive_failures} failures"
                    )

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        self._metrics.last_state_change = time.time()

        if new_state == CircuitState.OPEN:
            self._open_since = time.time()
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._metrics.consecutive_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._metrics.consecutive_failures = 0
            elapsed = time.time() - self._open_since if self._open_since else 0
            self._metrics.time_in_open += elapsed

        logger.info(f"[CIRCUIT] {self.name}: {old.value} → {new_state.value}")

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._transition(CircuitState.CLOSED)
            self._metrics = CircuitMetrics()

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "metrics": self._metrics.to_dict(),
            "config": {
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            },
        }


# ── Global Registry ──

_breakers: Dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    with _breakers_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(
                name, failure_threshold, recovery_timeout
            )
        return _breakers[name]


def get_all_breakers() -> Dict[str, Dict[str, Any]]:
    """Get status of all circuit breakers."""
    return {name: cb.get_status() for name, cb in _breakers.items()}


# ── Decorator ──

def circuit_protected(
    circuit_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    fallback: Optional[Callable] = None,
):
    """
    Decorator to protect a function with a circuit breaker.

    @circuit_protected("openai_api", failure_threshold=3)
    async def call_openai(prompt):
        ...
    """
    def decorator(func):
        cb = get_circuit_breaker(circuit_name, failure_threshold, recovery_timeout)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not cb.allow_request():
                if fallback:
                    return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
                raise CircuitOpenError(f"Circuit '{circuit_name}' is OPEN")
            try:
                result = await func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure(str(e))
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not cb.allow_request():
                if fallback:
                    return fallback(*args, **kwargs)
                raise CircuitOpenError(f"Circuit '{circuit_name}' is OPEN")
            try:
                result = func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure(str(e))
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and rejects a request."""
    pass
