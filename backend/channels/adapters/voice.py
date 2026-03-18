"""
Voice/Video Channel Adapters — 3 Adapters
══════════════════════════════════════════
WebRTC · Twilio Voice · SIP
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


class WebRTCAdapter(ChannelAdapter):
    """
    WebRTC peer-to-peer adapter for real-time audio/video.
    Requires: extra.signaling_url (WebSocket signaling server).
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.WEBRTC
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.AUDIO,
            ChannelCapability.VIDEO, ChannelCapability.VOICE_CALL,
            ChannelCapability.VIDEO_CALL, ChannelCapability.SCREEN_SHARE,
        }
        self._signaling_url = config.extra.get("signaling_url", "ws://localhost:8765")
        self._ice_servers = config.extra.get("ice_servers", [
            {"urls": "stun:stun.l.google.com:19302"},
        ])
        self._peers: Dict[str, Any] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        logger.info(f"[WEBRTC] Signaling server: {self._signaling_url}")
        return True

    async def _disconnect(self) -> None:
        self._peers.clear()
        logger.info("[WEBRTC] Disconnected — all peers released")

    async def _listen(self):
        """Listen for signaling events (offer/answer/ICE candidates)."""
        while True:
            event = await self._event_queue.get()
            event_type = event.get("type", "")
            if event_type == "data_channel_message":
                yield ChannelMessage(
                    channel_type=ChannelType.WEBRTC,
                    channel_id=event.get("peer_id", ""),
                    sender_id=event.get("peer_id", ""),
                    content=event.get("data", ""),
                    is_direct=True,
                    raw_event=event,
                )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[WEBRTC] → peer={response.channel_id} ({len(response.content)} chars)")
        return True


class TwilioVoiceAdapter(ChannelAdapter):
    """
    Twilio Programmable Voice adapter.
    Requires: api_key (Account SID), api_secret (Auth Token).
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.TWILIO_VOICE
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.AUDIO,
            ChannelCapability.VOICE_CALL,
        }
        self._account_sid = config.api_key
        self._auth_token = config.api_secret
        self._from_number = config.extra.get("from_number", "")
        self._twiml_url = config.extra.get("twiml_url", "")
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self._account_sid or not self._auth_token:
            logger.error("[TWILIO] Missing Account SID or Auth Token")
            return False
        logger.info(f"[TWILIO] Connected — from={self._from_number}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[TWILIO] Disconnected")

    async def _listen(self):
        """Listen for incoming call/SMS webhooks from Twilio."""
        while True:
            event = await self._webhook_queue.get()
            content = event.get("SpeechResult", event.get("Body", ""))
            if content:
                yield ChannelMessage(
                    message_id=event.get("CallSid", event.get("MessageSid", "")),
                    channel_type=ChannelType.TWILIO_VOICE,
                    channel_id=event.get("To", self._from_number),
                    sender_id=event.get("From", ""),
                    content=content,
                    content_type="audio" if "SpeechResult" in event else "text",
                    is_direct=True,
                    raw_event=event,
                )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[TWILIO] → {response.channel_id} ({len(response.content)} chars)")
        # In production: Twilio REST API to initiate call or send SMS
        return True


class SIPAdapter(ChannelAdapter):
    """
    SIP (Session Initiation Protocol) adapter for VoIP.
    Requires: host (SIP server), port, api_key (SIP username), api_secret (SIP password).
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.SIP
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.VOICE_CALL,
            ChannelCapability.AUDIO,
        }
        self._sip_uri = config.extra.get("sip_uri", f"sip:{config.api_key}@{config.host}")
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.host:
            logger.error("[SIP] Missing SIP server host")
            return False
        logger.info(f"[SIP] Registered at {self._sip_uri}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[SIP] Unregistered")

    async def _listen(self):
        while True:
            event = await self._event_queue.get()
            if event.get("type") == "INVITE":
                yield ChannelMessage(
                    channel_type=ChannelType.SIP,
                    channel_id=event.get("call_id", ""),
                    sender_id=event.get("from_uri", ""),
                    content=event.get("sdp_body", ""),
                    content_type="audio",
                    is_direct=True,
                    raw_event=event,
                )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[SIP] → {response.channel_id}")
        return True
