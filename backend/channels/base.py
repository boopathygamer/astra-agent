"""
Channel Adapter Base — Abstract interface for all 52+ channel integrations.
═══════════════════════════════════════════════════════════════════════════
Every channel (WhatsApp, Telegram, Slack, email, MQTT, etc.) implements
this interface to normalize messages into ChannelMessage objects.

Design Principles:
  1. Normalize Everything — every platform becomes a ChannelMessage
  2. Fail Gracefully — adapters never crash the gateway
  3. Observe Everything — metrics, status, error tracking per channel
  4. Rate Limit — per-channel rate limiting to respect API quotas
"""

import asyncio
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════

class ChannelType(Enum):
    """All 52+ supported channel types."""
    # ── Messaging (14) ──
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    SIGNAL = "signal"
    MATRIX = "matrix"
    IRC = "irc"
    XMPP = "xmpp"
    WECHAT = "wechat"
    LINE = "line"
    VIBER = "viber"
    FACEBOOK_MESSENGER = "facebook_messenger"
    INSTAGRAM_DM = "instagram_dm"
    TWITTER_DM = "twitter_dm"

    # ── Email (3) ──
    EMAIL_SMTP = "email_smtp"
    EMAIL_GMAIL = "email_gmail"
    EMAIL_OUTLOOK = "email_outlook"

    # ── Voice/Video (3) ──
    WEBRTC = "webrtc"
    TWILIO_VOICE = "twilio_voice"
    SIP = "sip"

    # ── Web (4) ──
    REST_WEBHOOK = "rest_webhook"
    WEBSOCKET = "websocket"
    SSE = "sse"
    GRAPHQL = "graphql"

    # ── Developer (6) ──
    GITHUB = "github"
    GITLAB = "gitlab"
    JIRA = "jira"
    LINEAR = "linear"
    NOTION = "notion"
    CONFLUENCE = "confluence"

    # ── Business (6) ──
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    ZENDESK = "zendesk"
    INTERCOM = "intercom"
    FRESHDESK = "freshdesk"
    SERVICENOW = "servicenow"

    # ── Collaboration (5) ──
    MICROSOFT_TEAMS = "microsoft_teams"
    GOOGLE_CHAT = "google_chat"
    ZOOM_CHAT = "zoom_chat"
    MATTERMOST = "mattermost"
    ROCKETCHAT = "rocketchat"

    # ── IoT/Hardware (4) ──
    MQTT = "mqtt"
    HTTP_WEBHOOK = "http_webhook"
    GRPC = "grpc"
    SERIAL = "serial"

    # ── Custom/Infrastructure (7) ──
    GENERIC_WEBHOOK = "generic_webhook"
    CLI_PIPE = "cli_pipe"
    UNIX_SOCKET = "unix_socket"
    NAMED_PIPE = "named_pipe"
    REDIS_PUBSUB = "redis_pubsub"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"


class ChannelStatus(Enum):
    """Adapter connection states."""
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    DISABLED = "disabled"


class ChannelCapability(Enum):
    """What a channel can do beyond plain text."""
    TEXT = auto()
    RICH_TEXT = auto()       # Markdown, HTML
    IMAGES = auto()
    FILES = auto()
    AUDIO = auto()
    VIDEO = auto()
    REACTIONS = auto()
    THREADS = auto()
    TYPING_INDICATOR = auto()
    READ_RECEIPTS = auto()
    BUTTONS = auto()         # Interactive buttons
    CARDS = auto()           # Rich cards / embeds
    LOCATION = auto()
    CONTACTS = auto()
    STICKERS = auto()
    VOICE_CALL = auto()
    VIDEO_CALL = auto()
    SCREEN_SHARE = auto()


# ═══════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════

@dataclass
class Attachment:
    """A file/media attachment on a message."""
    filename: str = ""
    mime_type: str = ""
    url: str = ""
    data: bytes = b""
    size_bytes: int = 0


@dataclass
class ChannelMessage:
    """
    Universal message format — every channel normalizes to this.
    This is the lingua franca of the gateway.
    """
    # ── Identity ──
    message_id: str = ""
    channel_type: ChannelType = ChannelType.REST_WEBHOOK
    channel_id: str = ""          # Unique channel instance (e.g., guild ID, chat ID)

    # ── Sender ──
    sender_id: str = ""
    sender_name: str = ""
    sender_avatar: str = ""

    # ── Content ──
    content: str = ""
    content_type: str = "text"    # text, image, audio, video, file, location, command
    attachments: List[Attachment] = field(default_factory=list)

    # ── Context ──
    thread_id: str = ""           # For threaded conversations
    reply_to_id: str = ""         # Message being replied to
    is_mention: bool = False      # Was the bot @mentioned?
    is_direct: bool = False       # Is this a DM?

    # ── Metadata ──
    timestamp: float = field(default_factory=time.time)
    raw_event: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.message_id:
            self.message_id = hashlib.md5(
                f"{self.channel_type.value}:{self.sender_id}:{self.timestamp}:{self.content[:50]}".encode()
            ).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "channel_type": self.channel_type.value,
            "channel_id": self.channel_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "content": self.content,
            "content_type": self.content_type,
            "is_direct": self.is_direct,
            "is_mention": self.is_mention,
            "thread_id": self.thread_id,
            "timestamp": self.timestamp,
            "attachments": len(self.attachments),
        }


@dataclass
class ChannelResponse:
    """Response to send back through a channel."""
    content: str = ""
    channel_type: ChannelType = ChannelType.REST_WEBHOOK
    channel_id: str = ""
    reply_to_id: str = ""
    thread_id: str = ""
    attachments: List[Attachment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Formatting hints — adapters use what they support
    format_markdown: bool = True
    embed_title: str = ""
    embed_color: str = ""
    buttons: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ChannelConfig:
    """Configuration for a channel adapter."""
    channel_type: ChannelType = ChannelType.REST_WEBHOOK
    enabled: bool = False
    # Auth
    api_key: str = ""
    api_secret: str = ""
    token: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""
    # Connection
    host: str = ""
    port: int = 0
    ssl: bool = True
    # Rate limiting
    max_requests_per_minute: int = 60
    max_messages_per_second: float = 5.0
    # Behavior
    auto_reply: bool = True
    require_mention: bool = False     # Only respond when @mentioned
    allowed_channels: List[str] = field(default_factory=list)  # Filter by channel ID
    blocked_users: List[str] = field(default_factory=list)
    # Custom
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelMetrics:
    """Per-channel runtime metrics."""
    messages_received: int = 0
    messages_sent: int = 0
    errors: int = 0
    last_message_at: float = 0.0
    last_error: str = ""
    last_error_at: float = 0.0
    avg_response_ms: float = 0.0
    _response_times: list = field(default_factory=list)
    uptime_start: float = field(default_factory=time.time)

    def record_response(self, duration_ms: float):
        self._response_times.append(duration_ms)
        if len(self._response_times) > 500:
            self._response_times = self._response_times[-500:]
        self.avg_response_ms = sum(self._response_times) / len(self._response_times)
        self.messages_sent += 1

    def record_error(self, error: str):
        self.errors += 1
        self.last_error = error
        self.last_error_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages_received": self.messages_received,
            "messages_sent": self.messages_sent,
            "errors": self.errors,
            "last_message_at": self.last_message_at,
            "last_error": self.last_error,
            "avg_response_ms": round(self.avg_response_ms, 2),
            "uptime_seconds": round(time.time() - self.uptime_start, 1),
        }


# ═══════════════════════════════════════════════
# Abstract Base Adapter
# ═══════════════════════════════════════════════

class ChannelAdapter(ABC):
    """
    Abstract base class for all channel adapters.

    Subclasses must implement:
      - _connect()      — establish connection to the channel
      - _disconnect()   — clean up connection
      - _listen()       — async generator yielding ChannelMessage
      - _send()         — send a ChannelResponse back

    The base class handles:
      - Lifecycle management (start/stop)
      - Rate limiting
      - Error tracking and metrics
      - Circuit breaker integration
    """

    def __init__(self, config: ChannelConfig):
        self.config = config
        self.channel_type = config.channel_type
        self.status = ChannelStatus.IDLE
        self.metrics = ChannelMetrics()
        self.capabilities: Set[ChannelCapability] = {ChannelCapability.TEXT}

        # Rate limiting
        self._rate_tokens: float = config.max_messages_per_second
        self._rate_max: float = config.max_messages_per_second
        self._rate_last_refill: float = time.time()

        # Callbacks
        self._on_message: Optional[Callable] = None
        self._listen_task: Optional[asyncio.Task] = None

        logger.info(f"[CHANNEL] Adapter created: {self.channel_type.value}")

    # ── Abstract Methods (implementors must override) ──

    @abstractmethod
    async def _connect(self) -> bool:
        """Establish connection. Return True on success."""
        ...

    @abstractmethod
    async def _disconnect(self) -> None:
        """Clean up connection resources."""
        ...

    @abstractmethod
    async def _listen(self):
        """Async generator that yields ChannelMessage objects."""
        yield  # pragma: no cover

    @abstractmethod
    async def _send(self, response: ChannelResponse) -> bool:
        """Send a response. Return True on success."""
        ...

    # ── Lifecycle ──

    async def start(self, on_message: Callable) -> bool:
        """Start the adapter and begin listening for messages."""
        self._on_message = on_message
        self.status = ChannelStatus.CONNECTING
        try:
            connected = await self._connect()
            if connected:
                self.status = ChannelStatus.CONNECTED
                self._listen_task = asyncio.create_task(self._listen_loop())
                logger.info(f"[CHANNEL] ✅ {self.channel_type.value} connected")
                return True
            else:
                self.status = ChannelStatus.ERROR
                self.metrics.record_error("Connection failed")
                return False
        except Exception as e:
            self.status = ChannelStatus.ERROR
            self.metrics.record_error(str(e))
            logger.error(f"[CHANNEL] ❌ {self.channel_type.value} start failed: {e}")
            return False

    async def stop(self) -> None:
        """Stop the adapter and clean up."""
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        await self._disconnect()
        self.status = ChannelStatus.DISCONNECTED
        logger.info(f"[CHANNEL] 🛑 {self.channel_type.value} disconnected")

    async def _listen_loop(self) -> None:
        """Internal listen loop with error recovery."""
        while self.status == ChannelStatus.CONNECTED:
            try:
                async for message in self._listen():
                    if self.status != ChannelStatus.CONNECTED:
                        break

                    # Filter blocked users
                    if message.sender_id in self.config.blocked_users:
                        continue

                    # Filter by allowed channels
                    if self.config.allowed_channels and message.channel_id not in self.config.allowed_channels:
                        continue

                    # Check mention requirement
                    if self.config.require_mention and not message.is_mention and not message.is_direct:
                        continue

                    self.metrics.messages_received += 1
                    self.metrics.last_message_at = time.time()

                    if self._on_message:
                        try:
                            await self._on_message(message)
                        except Exception as e:
                            logger.error(f"[CHANNEL] Message handler error on {self.channel_type.value}: {e}")
                            self.metrics.record_error(f"handler: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.metrics.record_error(str(e))
                logger.error(f"[CHANNEL] Listen error on {self.channel_type.value}: {e}")
                # Backoff before retry
                await asyncio.sleep(5)

    # ── Sending with Rate Limiting ──

    async def send(self, response: ChannelResponse) -> bool:
        """Send with rate limiting and metrics."""
        # Token bucket rate limiting
        now = time.time()
        elapsed = now - self._rate_last_refill
        self._rate_tokens = min(self._rate_max, self._rate_tokens + elapsed * self._rate_max)
        self._rate_last_refill = now

        if self._rate_tokens < 1.0:
            self.status = ChannelStatus.RATE_LIMITED
            logger.warning(f"[CHANNEL] Rate limited: {self.channel_type.value}")
            await asyncio.sleep(1.0 / self._rate_max)
            self.status = ChannelStatus.CONNECTED

        self._rate_tokens -= 1.0
        start = time.time()

        try:
            success = await self._send(response)
            duration_ms = (time.time() - start) * 1000
            if success:
                self.metrics.record_response(duration_ms)
            else:
                self.metrics.record_error("send returned False")
            return success
        except Exception as e:
            self.metrics.record_error(str(e))
            logger.error(f"[CHANNEL] Send error on {self.channel_type.value}: {e}")
            return False

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        return {
            "channel_type": self.channel_type.value,
            "status": self.status.value,
            "enabled": self.config.enabled,
            "capabilities": [c.name for c in self.capabilities],
            "metrics": self.metrics.to_dict(),
        }
