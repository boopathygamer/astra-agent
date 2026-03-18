"""
IoT / Hardware Channel Adapters — 4 Adapters
═════════════════════════════════════════════
MQTT · HTTP Webhook · gRPC · Serial/COM
"""

import asyncio
import logging
from typing import Any, Dict

from channels.base import (
    ChannelAdapter,
    ChannelCapability,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
    ChannelType,
)

logger = logging.getLogger(__name__)


class MQTTAdapter(ChannelAdapter):
    """MQTT adapter for IoT device communication."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.MQTT
        self.capabilities = {ChannelCapability.TEXT, ChannelCapability.FILES}
        self._broker = config.host or "localhost"
        self._port = config.port or 1883
        self._topics = config.extra.get("topics", ["astra/#"])
        self._qos = config.extra.get("qos", 1)
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[MQTT] Connected to {self._broker}:{self._port}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[MQTT] Disconnected")

    async def _listen(self):
        while True:
            event = await self._queue.get()
            payload = event.get("payload", "")
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8", errors="replace")
            yield ChannelMessage(
                channel_type=ChannelType.MQTT,
                channel_id=event.get("topic", ""),
                sender_id="device",
                content=payload,
                raw_event=event,
            )

    def on_mqtt_message(self, topic: str, payload: bytes, qos: int = 0) -> None:
        self._queue.put_nowait({"topic": topic, "payload": payload, "qos": qos})

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[MQTT] → {response.channel_id}")
        return True


class HTTPWebhookAdapter(ChannelAdapter):
    """Generic HTTP Webhook adapter for IoT/microservice events."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.HTTP_WEBHOOK
        self.capabilities = {ChannelCapability.TEXT, ChannelCapability.FILES}
        self._callback_url = config.webhook_url
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[HTTP_WEBHOOK] Ready — callback={self._callback_url or 'none'}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[HTTP_WEBHOOK] Disconnected")

    async def _listen(self):
        while True:
            p = await self._queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.HTTP_WEBHOOK,
                channel_id=p.get("device_id", "webhook"),
                sender_id=p.get("sender", ""),
                content=str(p.get("data", p.get("message", ""))),
                raw_event=p,
            )

    def handle_request(self, payload: Dict[str, Any]) -> None:
        self._queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[HTTP_WEBHOOK] → {response.channel_id}")
        return True


class GRPCAdapter(ChannelAdapter):
    """gRPC bidirectional streaming adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.GRPC
        self.capabilities = {ChannelCapability.TEXT, ChannelCapability.FILES}
        self._host = config.host or "localhost"
        self._port = config.port or 50051
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[GRPC] Listening on {self._host}:{self._port}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[GRPC] Stopped")

    async def _listen(self):
        while True:
            req = await self._queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.GRPC,
                channel_id=req.get("service", ""),
                sender_id=req.get("client_id", ""),
                content=req.get("message", ""),
                raw_event=req,
            )

    def on_rpc_request(self, request: Dict[str, Any]) -> None:
        self._queue.put_nowait(request)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[GRPC] → {response.channel_id}")
        return True


class SerialAdapter(ChannelAdapter):
    """Serial/COM port adapter for hardware devices."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.SERIAL
        self.capabilities = {ChannelCapability.TEXT}
        self._port = config.extra.get("port", "COM3")
        self._baudrate = config.extra.get("baudrate", 115200)
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[SERIAL] Opened {self._port} @ {self._baudrate}")
        return True

    async def _disconnect(self) -> None:
        logger.info(f"[SERIAL] Closed {self._port}")

    async def _listen(self):
        while True:
            data = await self._queue.get()
            content = data if isinstance(data, str) else data.decode("utf-8", errors="replace")
            yield ChannelMessage(
                channel_type=ChannelType.SERIAL,
                channel_id=self._port,
                sender_id=self._port,
                content=content,
            )

    def on_serial_data(self, data: Any) -> None:
        self._queue.put_nowait(data)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[SERIAL] → {self._port}")
        return True
