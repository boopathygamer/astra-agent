"""
Collaboration Channel Adapters — 5 Adapters
════════════════════════════════════════════
Microsoft Teams · Google Chat · Zoom Chat · Mattermost · Rocket.Chat
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


class MicrosoftTeamsAdapter(ChannelAdapter):
    """Microsoft Teams via Bot Framework + Graph API."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.MICROSOFT_TEAMS
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
            ChannelCapability.CARDS, ChannelCapability.BUTTONS,
            ChannelCapability.REACTIONS, ChannelCapability.THREADS,
            ChannelCapability.TYPING_INDICATOR,
        }
        self._app_id = config.extra.get("app_id", "")
        self._app_password = config.api_secret
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self._app_id or not self._app_password:
            logger.error("[TEAMS] Missing app_id or app_password")
            return False
        logger.info(f"[TEAMS] Connected — app_id={self._app_id}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[TEAMS] Disconnected")

    async def _listen(self):
        while True:
            activity = await self._webhook_queue.get()
            if activity.get("type") == "message":
                sender = activity.get("from", {})
                conv = activity.get("conversation", {})
                yield ChannelMessage(
                    message_id=activity.get("id", ""),
                    channel_type=ChannelType.MICROSOFT_TEAMS,
                    channel_id=conv.get("id", ""),
                    sender_id=sender.get("id", ""),
                    sender_name=sender.get("name", ""),
                    content=activity.get("text", ""),
                    is_direct=conv.get("conversationType") == "personal",
                    is_mention=bool(activity.get("entities")),
                    thread_id=conv.get("id", ""),
                    raw_event=activity,
                )

    def handle_activity(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[TEAMS] → {response.channel_id} ({len(response.content)} chars)")
        return True


class GoogleChatAdapter(ChannelAdapter):
    """Google Chat via Chat API + webhook events."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.GOOGLE_CHAT
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.CARDS, ChannelCapability.BUTTONS,
            ChannelCapability.THREADS, ChannelCapability.REACTIONS,
        }
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[GOOGLE_CHAT] Missing service account credentials")
            return False
        logger.info("[GOOGLE_CHAT] Connected to Google Chat API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[GOOGLE_CHAT] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            msg = event.get("message", {})
            sender = msg.get("sender", {})
            space = event.get("space", {})
            yield ChannelMessage(
                message_id=msg.get("name", ""),
                channel_type=ChannelType.GOOGLE_CHAT,
                channel_id=space.get("name", ""),
                sender_id=sender.get("name", ""),
                sender_name=sender.get("displayName", ""),
                sender_avatar=sender.get("avatarUrl", ""),
                content=msg.get("argumentText", msg.get("text", "")),
                is_direct=space.get("type") == "DM",
                thread_id=msg.get("thread", {}).get("name", ""),
                raw_event=event,
            )

    def handle_event(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[GOOGLE_CHAT] → {response.channel_id}")
        return True


class ZoomChatAdapter(ChannelAdapter):
    """Zoom Chat via Zoom API + event subscriptions."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.ZOOM_CHAT
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
            ChannelCapability.REACTIONS,
        }
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[ZOOM] Missing OAuth token")
            return False
        logger.info("[ZOOM] Connected to Zoom Chat API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[ZOOM] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            payload = event.get("payload", {}).get("object", {})
            yield ChannelMessage(
                message_id=payload.get("message_id", ""),
                channel_type=ChannelType.ZOOM_CHAT,
                channel_id=payload.get("channel_id", payload.get("to_jid", "")),
                sender_id=payload.get("sender", ""),
                content=payload.get("message", ""),
                is_direct=payload.get("type") == "to_contact",
                raw_event=event,
            )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[ZOOM] → {response.channel_id}")
        return True


class MattermostAdapter(ChannelAdapter):
    """Mattermost via REST API + WebSocket."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.MATTERMOST
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
            ChannelCapability.REACTIONS, ChannelCapability.THREADS,
            ChannelCapability.TYPING_INDICATOR,
        }
        self._server_url = config.host or "https://your-mattermost.com"
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[MATTERMOST] Missing bot token")
            return False
        logger.info(f"[MATTERMOST] Connected to {self._server_url}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[MATTERMOST] Disconnected")

    async def _listen(self):
        while True:
            event = await self._event_queue.get()
            if event.get("event") == "posted":
                import json as _json
                post = _json.loads(event.get("data", {}).get("post", "{}"))
                yield ChannelMessage(
                    message_id=post.get("id", ""),
                    channel_type=ChannelType.MATTERMOST,
                    channel_id=post.get("channel_id", ""),
                    sender_id=post.get("user_id", ""),
                    content=post.get("message", ""),
                    thread_id=post.get("root_id", ""),
                    raw_event=event,
                )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[MATTERMOST] → {response.channel_id}")
        return True


class RocketChatAdapter(ChannelAdapter):
    """Rocket.Chat via REST API + Realtime WebSocket."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.ROCKETCHAT
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
            ChannelCapability.REACTIONS, ChannelCapability.THREADS,
            ChannelCapability.TYPING_INDICATOR,
        }
        self._server_url = config.host or "https://your-rocketchat.com"
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[ROCKETCHAT] Missing auth token")
            return False
        logger.info(f"[ROCKETCHAT] Connected to {self._server_url}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[ROCKETCHAT] Disconnected")

    async def _listen(self):
        while True:
            event = await self._event_queue.get()
            msg = event.get("fields", {}).get("args", [{}])[0] if event.get("fields") else event
            user = msg.get("u", {})
            yield ChannelMessage(
                message_id=msg.get("_id", ""),
                channel_type=ChannelType.ROCKETCHAT,
                channel_id=msg.get("rid", ""),
                sender_id=user.get("_id", ""),
                sender_name=user.get("username", ""),
                content=msg.get("msg", ""),
                thread_id=msg.get("tmid", ""),
                raw_event=event,
            )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[ROCKETCHAT] → {response.channel_id}")
        return True
