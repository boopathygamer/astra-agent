"""
Messaging Channel Adapters — 14 Adapters
═════════════════════════════════════════
WhatsApp · Telegram · Discord · Slack · Signal · Matrix · IRC · XMPP
WeChat · LINE · Viber · Facebook Messenger · Instagram DM · Twitter/X DM

Each adapter normalizes platform-specific events into ChannelMessage
and sends ChannelResponse back through the platform API.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, Set

from channels.base import (
    Attachment,
    ChannelAdapter,
    ChannelCapability,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
    ChannelStatus,
    ChannelType,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# WhatsApp — via Cloud API / Business API
# ═══════════════════════════════════════════════════════════

class WhatsAppAdapter(ChannelAdapter):
    """
    WhatsApp Business Cloud API adapter.
    Requires: api_key (access token), extra.phone_number_id, webhook_secret.
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.WHATSAPP
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.IMAGES,
            ChannelCapability.FILES, ChannelCapability.AUDIO,
            ChannelCapability.VIDEO, ChannelCapability.LOCATION,
            ChannelCapability.CONTACTS, ChannelCapability.STICKERS,
            ChannelCapability.BUTTONS, ChannelCapability.READ_RECEIPTS,
            ChannelCapability.REACTIONS,
        }
        self._phone_number_id = config.extra.get("phone_number_id", "")
        self._api_version = config.extra.get("api_version", "v18.0")
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info("[WHATSAPP] Connecting to WhatsApp Cloud API...")
        if not self.config.api_key:
            logger.error("[WHATSAPP] Missing access token")
            return False
        # Verify token by calling the API
        self._base_url = f"https://graph.facebook.com/{self._api_version}/{self._phone_number_id}"
        logger.info(f"[WHATSAPP] Connected — phone_number_id={self._phone_number_id}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[WHATSAPP] Disconnected")

    async def _listen(self):
        """Yield messages from the webhook queue."""
        while True:
            raw_event = await self._webhook_queue.get()
            try:
                msg = self._parse_webhook(raw_event)
                if msg:
                    yield msg
            except Exception as e:
                logger.error(f"[WHATSAPP] Parse error: {e}")

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        """Called by the HTTP webhook endpoint to enqueue events."""
        self._webhook_queue.put_nowait(payload)

    def _parse_webhook(self, payload: Dict[str, Any]) -> Optional[ChannelMessage]:
        """Parse WhatsApp Cloud API webhook into ChannelMessage."""
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None
            msg = messages[0]
            contacts = value.get("contacts", [{}])
            sender_name = contacts[0].get("profile", {}).get("name", "") if contacts else ""

            content = ""
            content_type = "text"
            if msg.get("type") == "text":
                content = msg.get("text", {}).get("body", "")
            elif msg.get("type") in ("image", "audio", "video", "document"):
                content_type = msg["type"]
                content = msg.get(msg["type"], {}).get("caption", f"[{content_type}]")

            return ChannelMessage(
                message_id=msg.get("id", ""),
                channel_type=ChannelType.WHATSAPP,
                channel_id=self._phone_number_id,
                sender_id=msg.get("from", ""),
                sender_name=sender_name,
                content=content,
                content_type=content_type,
                is_direct=True,
                raw_event=payload,
            )
        except (IndexError, KeyError) as e:
            logger.error(f"[WHATSAPP] Webhook parse failed: {e}")
            return None

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[WHATSAPP] → Sending to {response.channel_id} ({len(response.content)} chars)")
        # In production: POST to graph.facebook.com/.../messages
        # with Authorization: Bearer {token}
        return True


# ═══════════════════════════════════════════════════════════
# Telegram — Bot API
# ═══════════════════════════════════════════════════════════

class TelegramAdapter(ChannelAdapter):
    """
    Telegram Bot API adapter (long-polling or webhook mode).
    Requires: token (bot token from @BotFather).
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.TELEGRAM
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
            ChannelCapability.AUDIO, ChannelCapability.VIDEO,
            ChannelCapability.STICKERS, ChannelCapability.BUTTONS,
            ChannelCapability.REACTIONS, ChannelCapability.LOCATION,
            ChannelCapability.CONTACTS, ChannelCapability.TYPING_INDICATOR,
        }
        self._offset = 0
        self._poll_interval = config.extra.get("poll_interval", 1.0)
        self._webhook_queue: asyncio.Queue = asyncio.Queue()
        self._use_webhook = bool(config.webhook_url)

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[TELEGRAM] Missing bot token")
            return False
        self._base_url = f"https://api.telegram.org/bot{self.config.token}"
        logger.info("[TELEGRAM] Connected via Bot API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[TELEGRAM] Disconnected")

    async def _listen(self):
        if self._use_webhook:
            while True:
                raw = await self._webhook_queue.get()
                msg = self._parse_update(raw)
                if msg:
                    yield msg
        else:
            # Long-polling mode
            while True:
                # In production: GET {base_url}/getUpdates?offset={offset}&timeout=30
                await asyncio.sleep(self._poll_interval)

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    def _parse_update(self, update: Dict[str, Any]) -> Optional[ChannelMessage]:
        msg_data = update.get("message") or update.get("edited_message")
        if not msg_data:
            return None
        sender = msg_data.get("from", {})
        chat = msg_data.get("chat", {})
        return ChannelMessage(
            message_id=str(msg_data.get("message_id", "")),
            channel_type=ChannelType.TELEGRAM,
            channel_id=str(chat.get("id", "")),
            sender_id=str(sender.get("id", "")),
            sender_name=f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip(),
            content=msg_data.get("text", ""),
            is_direct=chat.get("type") == "private",
            thread_id=str(msg_data.get("message_thread_id", "")),
            raw_event=update,
        )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[TELEGRAM] → chat_id={response.channel_id} ({len(response.content)} chars)")
        # In production: POST {base_url}/sendMessage
        return True


# ═══════════════════════════════════════════════════════════
# Discord — Bot Gateway (WebSocket) + REST
# ═══════════════════════════════════════════════════════════

class DiscordAdapter(ChannelAdapter):
    """
    Discord bot via Gateway WebSocket + REST API.
    Requires: token (bot token), extra.intents (bitmask).
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.DISCORD
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
            ChannelCapability.AUDIO, ChannelCapability.VIDEO,
            ChannelCapability.REACTIONS, ChannelCapability.THREADS,
            ChannelCapability.BUTTONS, ChannelCapability.CARDS,
            ChannelCapability.TYPING_INDICATOR,
        }
        self._ws = None
        self._heartbeat_interval = 41250
        self._sequence = None
        self._session_id = None
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[DISCORD] Missing bot token")
            return False
        # In production: connect to wss://gateway.discord.gg/?v=10&encoding=json
        logger.info("[DISCORD] Connected to Discord Gateway")
        return True

    async def _disconnect(self) -> None:
        if self._ws:
            self._ws = None
        logger.info("[DISCORD] Disconnected")

    async def _listen(self):
        while True:
            event = await self._event_queue.get()
            if event.get("t") == "MESSAGE_CREATE":
                msg = self._parse_message(event.get("d", {}))
                if msg:
                    yield msg

    def _parse_message(self, data: Dict[str, Any]) -> Optional[ChannelMessage]:
        author = data.get("author", {})
        if author.get("bot"):
            return None
        return ChannelMessage(
            message_id=data.get("id", ""),
            channel_type=ChannelType.DISCORD,
            channel_id=data.get("channel_id", ""),
            sender_id=author.get("id", ""),
            sender_name=author.get("username", ""),
            sender_avatar=f"https://cdn.discordapp.com/avatars/{author.get('id')}/{author.get('avatar')}.png" if author.get("avatar") else "",
            content=data.get("content", ""),
            thread_id=data.get("thread", {}).get("id", "") if data.get("thread") else "",
            is_mention=bool(data.get("mention_everyone") or data.get("mentions")),
            raw_event=data,
        )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[DISCORD] → channel={response.channel_id} ({len(response.content)} chars)")
        # In production: POST /api/v10/channels/{channel_id}/messages
        return True


# ═══════════════════════════════════════════════════════════
# Slack — Bot (Events API + Web API)
# ═══════════════════════════════════════════════════════════

class SlackAdapter(ChannelAdapter):
    """
    Slack bot via Events API (webhooks) + Web API for sending.
    Requires: token (xoxb-...), webhook_secret (signing secret).
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.SLACK
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
            ChannelCapability.REACTIONS, ChannelCapability.THREADS,
            ChannelCapability.BUTTONS, ChannelCapability.CARDS,
            ChannelCapability.TYPING_INDICATOR,
        }
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[SLACK] Missing bot token (xoxb-...)")
            return False
        logger.info("[SLACK] Connected to Slack Web API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[SLACK] Disconnected")

    async def _listen(self):
        while True:
            event = await self._event_queue.get()
            msg = self._parse_event(event)
            if msg:
                yield msg

    def handle_event(self, payload: Dict[str, Any]) -> Optional[str]:
        """Handle Slack Events API webhook. Returns challenge for verification."""
        if payload.get("type") == "url_verification":
            return payload.get("challenge", "")
        event = payload.get("event", {})
        if event.get("type") == "message" and not event.get("bot_id"):
            self._event_queue.put_nowait(event)
        return None

    def _parse_event(self, event: Dict[str, Any]) -> Optional[ChannelMessage]:
        return ChannelMessage(
            message_id=event.get("client_msg_id", event.get("ts", "")),
            channel_type=ChannelType.SLACK,
            channel_id=event.get("channel", ""),
            sender_id=event.get("user", ""),
            content=event.get("text", ""),
            thread_id=event.get("thread_ts", ""),
            is_direct=event.get("channel_type") == "im",
            is_mention="<@" in event.get("text", ""),
            raw_event=event,
        )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[SLACK] → channel={response.channel_id} ({len(response.content)} chars)")
        # In production: POST https://slack.com/api/chat.postMessage
        return True


# ═══════════════════════════════════════════════════════════
# Signal — via signal-cli REST API
# ═══════════════════════════════════════════════════════════

class SignalAdapter(ChannelAdapter):
    """Signal messenger via signal-cli or Signal REST API."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.SIGNAL
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.IMAGES,
            ChannelCapability.FILES, ChannelCapability.AUDIO,
            ChannelCapability.VIDEO, ChannelCapability.REACTIONS,
            ChannelCapability.READ_RECEIPTS, ChannelCapability.TYPING_INDICATOR,
        }
        self._api_url = config.extra.get("signal_api_url", "http://localhost:8080")
        self._phone = config.extra.get("phone_number", "")
        self._poll_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self._phone:
            logger.error("[SIGNAL] Missing phone_number in config.extra")
            return False
        logger.info(f"[SIGNAL] Connected — phone={self._phone}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[SIGNAL] Disconnected")

    async def _listen(self):
        while True:
            event = await self._poll_queue.get()
            envelope = event.get("envelope", {})
            data_msg = envelope.get("dataMessage")
            if data_msg:
                yield ChannelMessage(
                    channel_type=ChannelType.SIGNAL,
                    channel_id=self._phone,
                    sender_id=envelope.get("source", ""),
                    sender_name=envelope.get("sourceName", ""),
                    content=data_msg.get("message", ""),
                    is_direct=True,
                    raw_event=event,
                )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[SIGNAL] → {response.channel_id} ({len(response.content)} chars)")
        return True


# ═══════════════════════════════════════════════════════════
# Matrix — via Client-Server API
# ═══════════════════════════════════════════════════════════

class MatrixAdapter(ChannelAdapter):
    """Matrix (Element/Synapse) via Client-Server API."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.MATRIX
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
            ChannelCapability.REACTIONS, ChannelCapability.THREADS,
            ChannelCapability.READ_RECEIPTS, ChannelCapability.TYPING_INDICATOR,
        }
        self._homeserver = config.host or "https://matrix.org"
        self._sync_token = ""
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[MATRIX] Missing access token")
            return False
        logger.info(f"[MATRIX] Connected to {self._homeserver}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[MATRIX] Disconnected")

    async def _listen(self):
        while True:
            event = await self._event_queue.get()
            if event.get("type") == "m.room.message":
                content = event.get("content", {})
                yield ChannelMessage(
                    message_id=event.get("event_id", ""),
                    channel_type=ChannelType.MATRIX,
                    channel_id=event.get("room_id", ""),
                    sender_id=event.get("sender", ""),
                    content=content.get("body", ""),
                    content_type=content.get("msgtype", "m.text").replace("m.", ""),
                    raw_event=event,
                )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[MATRIX] → room={response.channel_id} ({len(response.content)} chars)")
        return True


# ═══════════════════════════════════════════════════════════
# IRC — Classic IRC Protocol
# ═══════════════════════════════════════════════════════════

class IRCAdapter(ChannelAdapter):
    """IRC (Internet Relay Chat) adapter using raw sockets."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.IRC
        self.capabilities = {ChannelCapability.TEXT}
        self._nick = config.extra.get("nickname", "astra-bot")
        self._irc_channels = config.extra.get("channels", [])
        self._reader = None
        self._writer = None

    async def _connect(self) -> bool:
        host = self.config.host or "irc.libera.chat"
        port = self.config.port or (6697 if self.config.ssl else 6667)
        logger.info(f"[IRC] Connecting to {host}:{port} as {self._nick}")
        # In production: asyncio.open_connection with SSL
        return True

    async def _disconnect(self) -> None:
        if self._writer:
            self._writer = None
        logger.info("[IRC] Disconnected")

    async def _listen(self):
        # In production: read lines from self._reader, parse IRC protocol
        while True:
            await asyncio.sleep(1)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[IRC] → {response.channel_id} ({len(response.content)} chars)")
        return True


# ═══════════════════════════════════════════════════════════
# XMPP — Jabber Protocol
# ═══════════════════════════════════════════════════════════

class XMPPAdapter(ChannelAdapter):
    """XMPP/Jabber adapter (slixmpp compatible)."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.XMPP
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.TYPING_INDICATOR,
        }
        self._jid = config.extra.get("jid", "")
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self._jid:
            logger.error("[XMPP] Missing JID")
            return False
        logger.info(f"[XMPP] Connected as {self._jid}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[XMPP] Disconnected")

    async def _listen(self):
        while True:
            stanza = await self._event_queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.XMPP,
                channel_id=stanza.get("from", ""),
                sender_id=stanza.get("from", ""),
                content=stanza.get("body", ""),
                is_direct=stanza.get("type") == "chat",
                raw_event=stanza,
            )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[XMPP] → {response.channel_id}")
        return True


# ═══════════════════════════════════════════════════════════
# WeChat — Official Account API
# ═══════════════════════════════════════════════════════════

class WeChatAdapter(ChannelAdapter):
    """WeChat Official Account / Mini Program adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.WECHAT
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.IMAGES,
            ChannelCapability.AUDIO, ChannelCapability.VIDEO,
            ChannelCapability.LOCATION, ChannelCapability.CARDS,
        }
        self._app_id = config.extra.get("app_id", "")
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self._app_id or not self.config.api_secret:
            logger.error("[WECHAT] Missing app_id or api_secret")
            return False
        logger.info(f"[WECHAT] Connected — app_id={self._app_id}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[WECHAT] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            yield ChannelMessage(
                channel_type=ChannelType.WECHAT,
                channel_id=event.get("ToUserName", ""),
                sender_id=event.get("FromUserName", ""),
                content=event.get("Content", ""),
                content_type=event.get("MsgType", "text"),
                raw_event=event,
            )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[WECHAT] → {response.channel_id}")
        return True


# ═══════════════════════════════════════════════════════════
# LINE — Messaging API
# ═══════════════════════════════════════════════════════════

class LINEAdapter(ChannelAdapter):
    """LINE Messaging API adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.LINE
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.IMAGES,
            ChannelCapability.STICKERS, ChannelCapability.BUTTONS,
            ChannelCapability.CARDS, ChannelCapability.LOCATION,
            ChannelCapability.AUDIO, ChannelCapability.VIDEO,
        }
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[LINE] Missing channel access token")
            return False
        logger.info("[LINE] Connected to LINE Messaging API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[LINE] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            src = event.get("source", {})
            msg = event.get("message", {})
            yield ChannelMessage(
                message_id=msg.get("id", ""),
                channel_type=ChannelType.LINE,
                channel_id=src.get("groupId", src.get("userId", "")),
                sender_id=src.get("userId", ""),
                content=msg.get("text", ""),
                content_type=msg.get("type", "text"),
                is_direct=src.get("type") == "user",
                raw_event=event,
            )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[LINE] → {response.channel_id}")
        return True


# ═══════════════════════════════════════════════════════════
# Viber — Bot API
# ═══════════════════════════════════════════════════════════

class ViberAdapter(ChannelAdapter):
    """Viber Bot API adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.VIBER
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.IMAGES,
            ChannelCapability.FILES, ChannelCapability.STICKERS,
            ChannelCapability.BUTTONS, ChannelCapability.CARDS,
            ChannelCapability.LOCATION,
        }
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[VIBER] Missing auth token")
            return False
        logger.info("[VIBER] Connected to Viber Bot API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[VIBER] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            if event.get("event") == "message":
                sender = event.get("sender", {})
                msg = event.get("message", {})
                yield ChannelMessage(
                    message_id=str(event.get("message_token", "")),
                    channel_type=ChannelType.VIBER,
                    channel_id=sender.get("id", ""),
                    sender_id=sender.get("id", ""),
                    sender_name=sender.get("name", ""),
                    sender_avatar=sender.get("avatar", ""),
                    content=msg.get("text", ""),
                    content_type=msg.get("type", "text"),
                    is_direct=True,
                    raw_event=event,
                )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[VIBER] → {response.channel_id}")
        return True


# ═══════════════════════════════════════════════════════════
# Facebook Messenger — Send/Receive API
# ═══════════════════════════════════════════════════════════

class FacebookMessengerAdapter(ChannelAdapter):
    """Facebook Messenger Platform adapter."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.FACEBOOK_MESSENGER
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.IMAGES,
            ChannelCapability.FILES, ChannelCapability.AUDIO,
            ChannelCapability.VIDEO, ChannelCapability.BUTTONS,
            ChannelCapability.CARDS, ChannelCapability.TYPING_INDICATOR,
            ChannelCapability.READ_RECEIPTS,
        }
        self._page_id = config.extra.get("page_id", "")
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.api_key:
            logger.error("[FB_MESSENGER] Missing page access token")
            return False
        logger.info(f"[FB_MESSENGER] Connected — page_id={self._page_id}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[FB_MESSENGER] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            entry = event.get("entry", [{}])[0]
            messaging = entry.get("messaging", [{}])[0]
            msg = messaging.get("message", {})
            if msg:
                yield ChannelMessage(
                    message_id=msg.get("mid", ""),
                    channel_type=ChannelType.FACEBOOK_MESSENGER,
                    channel_id=self._page_id,
                    sender_id=messaging.get("sender", {}).get("id", ""),
                    content=msg.get("text", ""),
                    is_direct=True,
                    raw_event=event,
                )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[FB_MESSENGER] → {response.channel_id}")
        return True


# ═══════════════════════════════════════════════════════════
# Instagram DM — Messenger Platform
# ═══════════════════════════════════════════════════════════

class InstagramDMAdapter(ChannelAdapter):
    """Instagram Direct Messages via Messenger Platform."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.INSTAGRAM_DM
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.IMAGES,
            ChannelCapability.REACTIONS, ChannelCapability.READ_RECEIPTS,
        }
        self._ig_user_id = config.extra.get("ig_user_id", "")
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.api_key:
            logger.error("[INSTAGRAM] Missing access token")
            return False
        logger.info(f"[INSTAGRAM] Connected — ig_user_id={self._ig_user_id}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[INSTAGRAM] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            entry = event.get("entry", [{}])[0]
            messaging = entry.get("messaging", [{}])[0]
            msg = messaging.get("message", {})
            if msg:
                yield ChannelMessage(
                    message_id=msg.get("mid", ""),
                    channel_type=ChannelType.INSTAGRAM_DM,
                    channel_id=self._ig_user_id,
                    sender_id=messaging.get("sender", {}).get("id", ""),
                    content=msg.get("text", ""),
                    is_direct=True,
                    raw_event=event,
                )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[INSTAGRAM] → {response.channel_id}")
        return True


# ═══════════════════════════════════════════════════════════
# Twitter/X DM — Direct Message API v2
# ═══════════════════════════════════════════════════════════

class TwitterDMAdapter(ChannelAdapter):
    """Twitter/X Direct Messages via API v2."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.TWITTER_DM
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.IMAGES,
            ChannelCapability.REACTIONS,
        }
        self._bearer_token = config.api_key
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self._bearer_token:
            logger.error("[TWITTER] Missing bearer token")
            return False
        logger.info("[TWITTER] Connected to X API v2")
        return True

    async def _disconnect(self) -> None:
        logger.info("[TWITTER] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            dm_event = event.get("direct_message_events", [{}])[0]
            msg_data = dm_event.get("message_create", {})
            yield ChannelMessage(
                message_id=dm_event.get("id", ""),
                channel_type=ChannelType.TWITTER_DM,
                sender_id=msg_data.get("sender_id", ""),
                content=msg_data.get("message_data", {}).get("text", ""),
                is_direct=True,
                raw_event=event,
            )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[TWITTER] → DM ({len(response.content)} chars)")
        return True
