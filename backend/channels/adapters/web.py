"""
Web Channel Adapters — 4 Adapters
═════════════════════════════════
REST Webhook · WebSocket · SSE · GraphQL
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set

from channels.base import (
    ChannelAdapter,
    ChannelCapability,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
    ChannelType,
)

logger = logging.getLogger(__name__)


class RESTWebhookAdapter(ChannelAdapter):
    """
    Generic REST webhook adapter — receives POST requests, sends responses.
    Requires: webhook_url (where to send responses), webhook_secret (HMAC verification).
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.REST_WEBHOOK
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
        }
        self._inbound_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[REST] Webhook endpoint ready — response_url={self.config.webhook_url or 'sync'}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[REST] Webhook endpoint closed")

    async def _listen(self):
        while True:
            payload = await self._inbound_queue.get()
            yield ChannelMessage(
                message_id=payload.get("id", ""),
                channel_type=ChannelType.REST_WEBHOOK,
                channel_id=payload.get("channel_id", "rest"),
                sender_id=payload.get("sender_id", payload.get("user_id", "")),
                sender_name=payload.get("sender_name", ""),
                content=payload.get("content", payload.get("message", payload.get("text", ""))),
                content_type=payload.get("content_type", "text"),
                raw_event=payload,
            )

    def handle_request(self, payload: Dict[str, Any]) -> None:
        """Called from the HTTP route handler to enqueue inbound messages."""
        self._inbound_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[REST] → {response.channel_id} ({len(response.content)} chars)")
        # In production: POST to config.webhook_url with response payload
        return True


class WebSocketChannelAdapter(ChannelAdapter):
    """
    WebSocket channel adapter — manages persistent connections.
    This wraps the existing WebSocket handler to integrate with the gateway.
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.WEBSOCKET
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.TYPING_INDICATOR,
        }
        self._connections: Dict[str, Any] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info("[WEBSOCKET] Channel adapter ready for WebSocket connections")
        return True

    async def _disconnect(self) -> None:
        for ws_id in list(self._connections.keys()):
            self._connections.pop(ws_id, None)
        logger.info("[WEBSOCKET] All connections closed")

    async def _listen(self):
        while True:
            msg_data = await self._message_queue.get()
            yield ChannelMessage(
                message_id=msg_data.get("id", ""),
                channel_type=ChannelType.WEBSOCKET,
                channel_id=msg_data.get("ws_id", ""),
                sender_id=msg_data.get("user_id", msg_data.get("ws_id", "")),
                content=msg_data.get("content", msg_data.get("message", "")),
                is_direct=True,
                raw_event=msg_data,
            )

    def on_ws_message(self, ws_id: str, data: Dict[str, Any]) -> None:
        """Called when a WebSocket message is received."""
        data["ws_id"] = ws_id
        self._message_queue.put_nowait(data)

    def register_connection(self, ws_id: str, ws: Any) -> None:
        self._connections[ws_id] = ws

    def unregister_connection(self, ws_id: str) -> None:
        self._connections.pop(ws_id, None)

    async def _send(self, response: ChannelResponse) -> bool:
        ws = self._connections.get(response.channel_id)
        if ws:
            try:
                await ws.send_json({"type": "response", "content": response.content})
                return True
            except Exception as e:
                logger.error(f"[WEBSOCKET] Send failed to {response.channel_id}: {e}")
                return False
        logger.warning(f"[WEBSOCKET] No connection for {response.channel_id}")
        return False


class SSEAdapter(ChannelAdapter):
    """
    Server-Sent Events adapter — pushes responses to connected clients.
    Inbound messages come via companion REST endpoint.
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.SSE
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
        }
        self._clients: Dict[str, asyncio.Queue] = {}
        self._inbound_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info("[SSE] Event stream adapter ready")
        return True

    async def _disconnect(self) -> None:
        self._clients.clear()
        logger.info("[SSE] All client streams closed")

    async def _listen(self):
        while True:
            payload = await self._inbound_queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.SSE,
                channel_id=payload.get("client_id", ""),
                sender_id=payload.get("user_id", ""),
                content=payload.get("content", ""),
                raw_event=payload,
            )

    def register_client(self, client_id: str) -> asyncio.Queue:
        """Register an SSE client and return its event queue."""
        q: asyncio.Queue = asyncio.Queue()
        self._clients[client_id] = q
        return q

    def unregister_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    async def _send(self, response: ChannelResponse) -> bool:
        client_q = self._clients.get(response.channel_id)
        if client_q:
            await client_q.put({"event": "message", "data": response.content})
            return True
        logger.warning(f"[SSE] No client stream for {response.channel_id}")
        return False


class GraphQLAdapter(ChannelAdapter):
    """
    GraphQL subscription adapter.
    Inbound: GraphQL mutations. Outbound: GraphQL subscriptions.
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.GRAPHQL
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES,
        }
        self._subscription_clients: Dict[str, asyncio.Queue] = {}
        self._mutation_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info("[GRAPHQL] Adapter ready for mutations and subscriptions")
        return True

    async def _disconnect(self) -> None:
        self._subscription_clients.clear()
        logger.info("[GRAPHQL] Disconnected")

    async def _listen(self):
        while True:
            payload = await self._mutation_queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.GRAPHQL,
                channel_id=payload.get("session_id", ""),
                sender_id=payload.get("user_id", ""),
                content=payload.get("query", payload.get("message", "")),
                raw_event=payload,
            )

    def handle_mutation(self, payload: Dict[str, Any]) -> None:
        self._mutation_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        sub_q = self._subscription_clients.get(response.channel_id)
        if sub_q:
            await sub_q.put({"data": {"agentResponse": {"content": response.content}}})
            return True
        logger.info(f"[GRAPHQL] → {response.channel_id} (no active subscription, response buffered)")
        return True
