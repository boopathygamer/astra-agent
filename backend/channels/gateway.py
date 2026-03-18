"""
Channel Gateway — Central Multi-Channel Orchestrator
═════════════════════════════════════════════════════
Routes messages from 52+ channels through the MessageBus to the AgentController.

Architecture:
  ┌────────────┐
  │  Telegram   │──┐
  │  Discord    │──┤ ChannelAdapter.listen()
  │  Slack      │──┤     │
  │  Email      │──┤     ▼
  │  GitHub     │──┤  ChannelGateway._on_channel_message()
  │  MQTT       │──┤     │
  │  50+ more   │──┘     ▼ normalize
  └────────────┘    MessageBus.publish("channel.inbound.*")
                         │
                         ▼
                    AgentController.chat()
                         │
                         ▼
                    ChannelGateway._send_response()
                         │
                    ChannelAdapter.send()
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from channels.base import (
    ChannelAdapter,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
    ChannelStatus,
    ChannelType,
)

logger = logging.getLogger(__name__)


@dataclass
class GatewayMetrics:
    """Aggregate metrics across all channels."""
    total_inbound: int = 0
    total_outbound: int = 0
    total_errors: int = 0
    active_channels: int = 0
    uptime_start: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_inbound": self.total_inbound,
            "total_outbound": self.total_outbound,
            "total_errors": self.total_errors,
            "active_channels": self.active_channels,
            "uptime_seconds": round(time.time() - self.uptime_start, 1),
        }


class ChannelGateway:
    """
    Central gateway that manages all channel adapters.

    Responsibilities:
      1. Lifecycle — start/stop all enabled adapters
      2. Normalize — convert platform-specific events to ChannelMessage
      3. Route — publish to MessageBus and get agent responses
      4. Respond — send agent responses back through the originating channel
      5. Monitor — per-channel metrics, status tracking, circuit breakers
    """

    def __init__(
        self,
        agent_fn: Optional[Callable] = None,
        message_bus: Optional[Any] = None,
    ):
        """
        Args:
            agent_fn: Callable that takes a string and returns a string (agent response).
                      Typically `agent_controller.chat`.
            message_bus: Optional MessageBus instance for pub/sub integration.
        """
        self._agent_fn = agent_fn
        self._message_bus = message_bus
        self._adapters: Dict[ChannelType, ChannelAdapter] = {}
        self._configs: Dict[ChannelType, ChannelConfig] = {}
        self._metrics = GatewayMetrics()
        self._running = False

        # Per-channel conversation context (channel_id → history)
        self._channel_contexts: Dict[str, List[Dict[str, str]]] = {}

        # Circuit breaker state per channel
        self._circuit_open: Set[ChannelType] = set()
        self._circuit_failures: Dict[ChannelType, int] = {}
        self._circuit_threshold: int = 5
        self._circuit_reset_time: Dict[ChannelType, float] = {}

        logger.info("[GATEWAY] Multi-Channel Gateway initialized")

    # ═══════════════════════════════════════════════
    # Channel Registration
    # ═══════════════════════════════════════════════

    def register(self, adapter: ChannelAdapter) -> None:
        """Register a channel adapter."""
        self._adapters[adapter.channel_type] = adapter
        self._configs[adapter.channel_type] = adapter.config
        logger.info(f"[GATEWAY] Registered adapter: {adapter.channel_type.value}")

    def enable(self, channel_type: ChannelType, **kwargs) -> Optional[ChannelAdapter]:
        """
        Create and register an adapter from config kwargs.

        Usage:
            gateway.enable(ChannelType.TELEGRAM, token="BOT_TOKEN")
            gateway.enable(ChannelType.SLACK, token="xoxb-...", webhook_url="...")
        """
        config = ChannelConfig(
            channel_type=channel_type,
            enabled=True,
            **kwargs,
        )
        adapter = self._create_adapter(config)
        if adapter:
            self.register(adapter)
            return adapter
        return None

    def _create_adapter(self, config: ChannelConfig) -> Optional[ChannelAdapter]:
        """Factory: create the right adapter for a channel type."""
        # Import adapters lazily to avoid circular imports
        from channels.adapters import ADAPTER_REGISTRY
        adapter_class = ADAPTER_REGISTRY.get(config.channel_type)
        if adapter_class:
            return adapter_class(config)
        logger.warning(f"[GATEWAY] No adapter registered for: {config.channel_type.value}")
        return None

    # ═══════════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════════

    async def start(self) -> None:
        """Start all enabled adapters."""
        self._running = True
        logger.info(f"[GATEWAY] 🚀 Starting {len(self._adapters)} channel adapter(s)...")

        start_tasks = []
        for channel_type, adapter in self._adapters.items():
            if adapter.config.enabled:
                start_tasks.append(self._start_adapter(adapter))

        results = await asyncio.gather(*start_tasks, return_exceptions=True)
        active = sum(1 for r in results if r is True)
        self._metrics.active_channels = active

        logger.info(
            f"[GATEWAY] ✅ Gateway online — {active}/{len(start_tasks)} channels active"
        )

        # Publish to message bus
        if self._message_bus:
            self._message_bus.publish(
                "gateway.started",
                {"active_channels": active, "total": len(start_tasks)},
                sender="gateway",
            )

    async def _start_adapter(self, adapter: ChannelAdapter) -> bool:
        """Start a single adapter with error handling."""
        try:
            return await adapter.start(on_message=self._on_channel_message)
        except Exception as e:
            logger.error(f"[GATEWAY] Failed to start {adapter.channel_type.value}: {e}")
            return False

    async def stop(self) -> None:
        """Stop all adapters gracefully."""
        self._running = False
        logger.info("[GATEWAY] 🛑 Shutting down all channels...")

        stop_tasks = [adapter.stop() for adapter in self._adapters.values()]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._metrics.active_channels = 0
        logger.info("[GATEWAY] ✅ All channels stopped")

    # ═══════════════════════════════════════════════
    # Message Handling (Core)
    # ═══════════════════════════════════════════════

    async def _on_channel_message(self, message: ChannelMessage) -> None:
        """
        Handle an inbound message from any channel.
        This is the heart of the gateway.
        """
        self._metrics.total_inbound += 1
        channel_type = message.channel_type

        # Circuit breaker check
        if channel_type in self._circuit_open:
            reset_time = self._circuit_reset_time.get(channel_type, 0)
            if time.time() < reset_time:
                logger.warning(f"[GATEWAY] Circuit OPEN for {channel_type.value}, skipping")
                return
            else:
                # Half-open: try one request
                self._circuit_open.discard(channel_type)
                self._circuit_failures[channel_type] = 0

        logger.info(
            f"[GATEWAY] 📩 Inbound [{channel_type.value}] "
            f"from={message.sender_name or message.sender_id} "
            f"len={len(message.content)}"
        )

        # Publish to message bus for other subsystems to observe
        if self._message_bus:
            self._message_bus.publish(
                f"channel.inbound.{channel_type.value}",
                message.to_dict(),
                sender="gateway",
            )

        # Process through agent
        try:
            response_text = await self._get_agent_response(message)

            if response_text:
                response = ChannelResponse(
                    content=response_text,
                    channel_type=channel_type,
                    channel_id=message.channel_id,
                    reply_to_id=message.message_id,
                    thread_id=message.thread_id,
                )

                adapter = self._adapters.get(channel_type)
                if adapter:
                    success = await adapter.send(response)
                    if success:
                        self._metrics.total_outbound += 1
                        # Reset circuit breaker on success
                        self._circuit_failures[channel_type] = 0
                    else:
                        self._record_failure(channel_type, "send failed")

                # Publish outbound event
                if self._message_bus:
                    self._message_bus.publish(
                        f"channel.outbound.{channel_type.value}",
                        {"response_length": len(response_text), "channel_id": message.channel_id},
                        sender="gateway",
                    )

        except Exception as e:
            self._record_failure(channel_type, str(e))
            logger.error(f"[GATEWAY] Processing error on {channel_type.value}: {e}")

    async def _get_agent_response(self, message: ChannelMessage) -> Optional[str]:
        """Get agent response for a message."""
        if not self._agent_fn:
            return "⚠️ Agent not connected to gateway."

        # Build context key from channel + sender
        ctx_key = f"{message.channel_type.value}:{message.channel_id}:{message.sender_id}"

        # Maintain per-channel conversation context (last 10 messages)
        if ctx_key not in self._channel_contexts:
            self._channel_contexts[ctx_key] = []
        ctx = self._channel_contexts[ctx_key]
        ctx.append({"role": "user", "content": message.content})
        if len(ctx) > 20:
            self._channel_contexts[ctx_key] = ctx[-20:]

        try:
            # Call the agent (sync or async)
            if asyncio.iscoroutinefunction(self._agent_fn):
                response = await self._agent_fn(message.content)
            else:
                response = await asyncio.to_thread(self._agent_fn, message.content)

            # Store response in context
            ctx.append({"role": "assistant", "content": response})
            return response

        except Exception as e:
            logger.error(f"[GATEWAY] Agent error: {e}")
            return f"❌ I encountered an error processing your message. Please try again."

    # ═══════════════════════════════════════════════
    # Circuit Breaker
    # ═══════════════════════════════════════════════

    def _record_failure(self, channel_type: ChannelType, error: str) -> None:
        """Record a failure and trip circuit breaker if threshold hit."""
        self._metrics.total_errors += 1
        count = self._circuit_failures.get(channel_type, 0) + 1
        self._circuit_failures[channel_type] = count

        if count >= self._circuit_threshold:
            self._circuit_open.add(channel_type)
            self._circuit_reset_time[channel_type] = time.time() + 60  # 60s cooldown
            logger.warning(
                f"[GATEWAY] ⚡ Circuit OPEN for {channel_type.value} "
                f"after {count} failures (60s cooldown)"
            )

    # ═══════════════════════════════════════════════
    # Status & Metrics
    # ═══════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get full gateway status for the /health and /telemetry endpoints."""
        channels = {}
        for channel_type, adapter in self._adapters.items():
            channels[channel_type.value] = adapter.get_status()

        return {
            "running": self._running,
            "gateway_metrics": self._metrics.to_dict(),
            "channels": channels,
            "circuit_breakers_open": [ct.value for ct in self._circuit_open],
            "total_registered": len(self._adapters),
        }

    def get_channel_list(self) -> List[Dict[str, Any]]:
        """Get summary of all registered channels."""
        result = []
        for channel_type, adapter in self._adapters.items():
            result.append({
                "type": channel_type.value,
                "status": adapter.status.value,
                "enabled": adapter.config.enabled,
                "messages_in": adapter.metrics.messages_received,
                "messages_out": adapter.metrics.messages_sent,
                "errors": adapter.metrics.errors,
            })
        return result

    @property
    def channel_count(self) -> int:
        return len(self._adapters)

    @property
    def active_count(self) -> int:
        return sum(
            1 for a in self._adapters.values()
            if a.status == ChannelStatus.CONNECTED
        )
