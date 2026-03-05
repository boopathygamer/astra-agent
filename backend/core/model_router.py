"""
Model Router — Provider failover with circuit breakers.
───────────────────────────────────────────────────────
Features (inspired by OpenClaw model failover):
  - Provider failover chain with automatic retry
  - Health checks and circuit breaker per provider
  - Model reference resolution (provider/model format)
  - Configurable timeout and retry limits
  - Provider priority ordering
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit_open"  # Too many failures
    DISABLED = "disabled"


@dataclass
class ProviderConfig:
    """Configuration for a model provider."""
    name: str
    model_id: str  # e.g., "mistral-7b-instruct"
    priority: int = 0  # Lower = higher priority
    enabled: bool = True
    timeout: int = 30  # seconds
    max_retries: int = 2
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_seconds: int = 60


@dataclass
class ProviderState:
    """Runtime state for a provider."""
    status: ProviderStatus = ProviderStatus.HEALTHY
    consecutive_failures: int = 0
    total_calls: int = 0
    total_failures: int = 0
    total_latency: float = 0.0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    circuit_opened_at: float = 0.0


class ModelRouter:
    """
    Routes model calls across providers with failover.

    Features:
      - Priority-based provider selection
      - Automatic failover on provider failure
      - Circuit breaker pattern (opens after N consecutive failures)
      - Auto-reset circuit after cooldown period
      - Per-provider health tracking
    """

    def __init__(self):
        self._providers: Dict[str, ProviderConfig] = {}
        self._states: Dict[str, ProviderState] = {}
        self._handlers: Dict[str, Callable] = {}

    def register_provider(
        self,
        config: ProviderConfig,
        handler: Callable = None,
    ):
        """
        Register a model provider.

        Args:
            config: Provider configuration
            handler: Callable(prompt, **kwargs) -> response
        """
        self._providers[config.name] = config
        self._states[config.name] = ProviderState()
        if handler:
            self._handlers[config.name] = handler

        logger.info(
            f"Registered provider: {config.name} "
            f"(model={config.model_id}, priority={config.priority})"
        )

    def set_handler(self, provider_name: str, handler: Callable):
        """Set the handler function for a provider."""
        self._handlers[provider_name] = handler

    def _get_available_providers(self) -> List[str]:
        """Get providers sorted by priority, filtering disabled/circuit-open ones."""
        now = time.time()
        available = []

        for name, config in self._providers.items():
            if not config.enabled:
                continue

            state = self._states[name]

            # Check circuit breaker
            if state.status == ProviderStatus.CIRCUIT_OPEN:
                elapsed = now - state.circuit_opened_at
                if elapsed >= config.circuit_breaker_reset_seconds:
                    # Reset circuit breaker (half-open)
                    state.status = ProviderStatus.DEGRADED
                    state.consecutive_failures = 0
                    logger.info(f"Circuit breaker reset for provider: {name}")
                else:
                    continue  # Still in cooldown

            available.append(name)

        # Sort by priority (lower = higher priority)
        available.sort(key=lambda n: self._providers[n].priority)
        return available

    def call(
        self,
        prompt: str,
        preferred_provider: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Call a model with automatic failover.

        Args:
            prompt: The prompt to send
            preferred_provider: Specific provider to try first
            **kwargs: Additional arguments passed to the handler

        Returns:
            {"provider": name, "response": ..., "latency": ...}
            or {"error": ..., "tried": [...]}
        """
        providers = self._get_available_providers()

        # Put preferred provider first if specified
        if preferred_provider and preferred_provider in providers:
            providers.remove(preferred_provider)
            providers.insert(0, preferred_provider)

        if not providers:
            return {
                "error": "No available providers",
                "tried": [],
            }

        tried = []
        for provider_name in providers:
            config = self._providers[provider_name]
            state = self._states[provider_name]
            handler = self._handlers.get(provider_name)

            if not handler:
                continue

            # Try the provider with retries
            for attempt in range(config.max_retries + 1):
                try:
                    start = time.time()
                    response = handler(prompt, **kwargs)
                    latency = time.time() - start

                    # Record success
                    state.total_calls += 1
                    state.total_latency += latency
                    state.consecutive_failures = 0
                    state.last_success_time = time.time()
                    if state.status == ProviderStatus.DEGRADED:
                        state.status = ProviderStatus.HEALTHY

                    return {
                        "provider": provider_name,
                        "model": config.model_id,
                        "response": response,
                        "latency": round(latency, 3),
                        "attempt": attempt + 1,
                    }

                except Exception as e:
                    state.total_calls += 1
                    state.total_failures += 1
                    state.consecutive_failures += 1
                    state.last_failure_time = time.time()

                    tried.append({
                        "provider": provider_name,
                        "attempt": attempt + 1,
                        "error": str(e),
                    })

                    logger.warning(
                        f"Provider {provider_name} failed "
                        f"(attempt {attempt + 1}/{config.max_retries + 1}): {e}"
                    )

                    # Check circuit breaker
                    if state.consecutive_failures >= config.circuit_breaker_threshold:
                        state.status = ProviderStatus.CIRCUIT_OPEN
                        state.circuit_opened_at = time.time()
                        logger.error(
                            f"Circuit breaker opened for {provider_name} "
                            f"after {state.consecutive_failures} failures"
                        )
                        break  # Move to next provider

        return {
            "error": "All providers failed",
            "tried": tried,
        }

    def get_health(self) -> Dict[str, Any]:
        """Get health status for all providers."""
        health = {}
        for name, config in self._providers.items():
            state = self._states[name]
            avg_latency = (
                state.total_latency / state.total_calls
                if state.total_calls > 0 else 0
            )
            health[name] = {
                "status": state.status.value,
                "model": config.model_id,
                "priority": config.priority,
                "enabled": config.enabled,
                "total_calls": state.total_calls,
                "total_failures": state.total_failures,
                "consecutive_failures": state.consecutive_failures,
                "avg_latency": round(avg_latency, 3),
                "failure_rate": (
                    round(state.total_failures / state.total_calls, 3)
                    if state.total_calls > 0 else 0
                ),
            }
        return health

    def reset_provider(self, provider_name: str):
        """Reset a provider's state (clear circuit breaker)."""
        if provider_name in self._states:
            self._states[provider_name] = ProviderState()
            logger.info(f"Reset provider state: {provider_name}")
