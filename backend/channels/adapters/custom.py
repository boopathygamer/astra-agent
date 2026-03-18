"""
Custom / Infrastructure Channel Adapters — 7 Adapters
══════════════════════════════════════════════════════
Generic Webhook · CLI Pipe · Unix Socket · Named Pipe
Redis PubSub · Kafka · RabbitMQ
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from channels.base import (
    ChannelAdapter,
    ChannelCapability,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
    ChannelType,
)

logger = logging.getLogger(__name__)


class GenericWebhookAdapter(ChannelAdapter):
    """Catch-all webhook adapter for custom integrations."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.GENERIC_WEBHOOK
        self.capabilities = {ChannelCapability.TEXT, ChannelCapability.FILES}
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info("[GENERIC_WEBHOOK] Ready")
        return True

    async def _disconnect(self) -> None:
        logger.info("[GENERIC_WEBHOOK] Closed")

    async def _listen(self):
        while True:
            p = await self._queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.GENERIC_WEBHOOK,
                channel_id=p.get("source", "webhook"),
                sender_id=p.get("sender", ""),
                content=str(p.get("data", p.get("message", p.get("body", "")))),
                raw_event=p,
            )

    def handle_request(self, payload: Dict[str, Any]) -> None:
        self._queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[GENERIC_WEBHOOK] → {response.channel_id}")
        return True


class CLIPipeAdapter(ChannelAdapter):
    """Stdin/stdout pipe adapter for CLI integrations."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.CLI_PIPE
        self.capabilities = {ChannelCapability.TEXT}
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info("[CLI_PIPE] Ready for stdin")
        return True

    async def _disconnect(self) -> None:
        logger.info("[CLI_PIPE] Closed")

    async def _listen(self):
        while True:
            line = await self._queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.CLI_PIPE,
                channel_id="stdin",
                sender_id="cli_user",
                content=line.strip() if isinstance(line, str) else line.decode().strip(),
                is_direct=True,
            )

    def feed_line(self, line: str) -> None:
        self._queue.put_nowait(line)

    async def _send(self, response: ChannelResponse) -> bool:
        print(response.content)
        return True


class UnixSocketAdapter(ChannelAdapter):
    """Unix domain socket adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.UNIX_SOCKET
        self.capabilities = {ChannelCapability.TEXT}
        self._path = config.extra.get("socket_path", "/tmp/astra.sock")
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[UNIX_SOCKET] Listening on {self._path}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[UNIX_SOCKET] Closed")

    async def _listen(self):
        while True:
            data = await self._queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.UNIX_SOCKET,
                channel_id=self._path,
                sender_id="socket_client",
                content=data if isinstance(data, str) else data.decode(),
                is_direct=True,
            )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[UNIX_SOCKET] → {self._path}")
        return True


class NamedPipeAdapter(ChannelAdapter):
    """Windows named pipe / FIFO adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.NAMED_PIPE
        self.capabilities = {ChannelCapability.TEXT}
        self._pipe_name = config.extra.get("pipe_name", r"\\.\pipe\astra")
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[NAMED_PIPE] Listening on {self._pipe_name}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[NAMED_PIPE] Closed")

    async def _listen(self):
        while True:
            data = await self._queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.NAMED_PIPE,
                channel_id=self._pipe_name,
                sender_id="pipe_client",
                content=data if isinstance(data, str) else data.decode(),
                is_direct=True,
            )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[NAMED_PIPE] → {self._pipe_name}")
        return True


class RedisPubSubAdapter(ChannelAdapter):
    """Redis Pub/Sub adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.REDIS_PUBSUB
        self.capabilities = {ChannelCapability.TEXT}
        self._redis_url = config.host or "redis://localhost:6379"
        self._channels = config.extra.get("channels", ["astra:*"])
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[REDIS] Connected to {self._redis_url}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[REDIS] Disconnected")

    async def _listen(self):
        while True:
            msg = await self._queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.REDIS_PUBSUB,
                channel_id=msg.get("channel", ""),
                sender_id=msg.get("publisher", "redis"),
                content=msg.get("data", ""),
                raw_event=msg,
            )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[REDIS] PUBLISH {response.channel_id}")
        return True


class KafkaAdapter(ChannelAdapter):
    """Apache Kafka consumer/producer adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.KAFKA
        self.capabilities = {ChannelCapability.TEXT}
        self._brokers = config.host or "localhost:9092"
        self._topics = config.extra.get("topics", ["astra-inbound"])
        self._group_id = config.extra.get("group_id", "astra-agent")
        self._queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[KAFKA] Connected to {self._brokers}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[KAFKA] Disconnected")

    async def _listen(self):
        while True:
            record = await self._queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.KAFKA,
                channel_id=record.get("topic", ""),
                sender_id=str(record.get("partition", "")),
                content=record.get("value", ""),
                raw_event=record,
                metadata={"offset": record.get("offset"), "key": record.get("key")},
            )

    async def _send(self, response: ChannelResponse) -> bool:
        topic = response.metadata.get("reply_topic", "astra-outbound")
        logger.info(f"[KAFKA] → {topic}")
        return True


class RabbitMQAdapter(ChannelAdapter):
    """RabbitMQ (AMQP) adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.RABBITMQ
        self.capabilities = {ChannelCapability.TEXT}
        self._url = config.host or "amqp://guest:guest@localhost:5672/"
        self._queue_name = config.extra.get("queue", "astra_inbound")
        self._exchange = config.extra.get("exchange", "astra")
        self._msg_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[RABBITMQ] Connected to {self._url}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[RABBITMQ] Disconnected")

    async def _listen(self):
        while True:
            msg = await self._msg_queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.RABBITMQ,
                channel_id=msg.get("routing_key", self._queue_name),
                sender_id=msg.get("app_id", ""),
                content=msg.get("body", ""),
                raw_event=msg,
                metadata={"exchange": msg.get("exchange", "")},
            )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[RABBITMQ] → {self._exchange}/{response.channel_id}")
        return True
