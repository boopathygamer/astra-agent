"""
Astra Agent — Multi-Channel Gateway
════════════════════════════════════
52+ channel adapters for universal message delivery.
Normalizes all inbound messages and routes through the central MessageBus.

Usage:
    from channels import ChannelGateway, ChannelType
    gateway = ChannelGateway(agent_controller=controller)
    gateway.enable(ChannelType.TELEGRAM, token="BOT_TOKEN")
    await gateway.start()
"""

from channels.base import (
    ChannelAdapter,
    ChannelMessage,
    ChannelType,
    ChannelStatus,
    ChannelCapability,
    ChannelConfig,
)
from channels.gateway import ChannelGateway

__all__ = [
    "ChannelAdapter",
    "ChannelMessage",
    "ChannelType",
    "ChannelStatus",
    "ChannelCapability",
    "ChannelConfig",
    "ChannelGateway",
]
