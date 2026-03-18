"""
Email Channel Adapters — 3 Adapters
════════════════════════════════════
SMTP/IMAP · Gmail API · Outlook (Microsoft Graph)
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from channels.base import (
    Attachment,
    ChannelAdapter,
    ChannelCapability,
    ChannelConfig,
    ChannelMessage,
    ChannelResponse,
    ChannelType,
)

logger = logging.getLogger(__name__)


class SMTPEmailAdapter(ChannelAdapter):
    """
    SMTP (send) + IMAP (receive) email adapter.
    Requires: host, port, api_key (username), api_secret (password).
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.EMAIL_SMTP
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.IMAGES,
        }
        self._imap_host = config.extra.get("imap_host", config.host)
        self._imap_port = config.extra.get("imap_port", 993)
        self._smtp_host = config.host or "smtp.gmail.com"
        self._smtp_port = config.port or 587
        self._poll_interval = config.extra.get("poll_interval", 30)
        self._seen_uids = set()

    async def _connect(self) -> bool:
        if not self.config.api_key or not self.config.api_secret:
            logger.error("[EMAIL_SMTP] Missing username/password")
            return False
        logger.info(f"[EMAIL_SMTP] Connected — IMAP={self._imap_host}, SMTP={self._smtp_host}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[EMAIL_SMTP] Disconnected")

    async def _listen(self):
        """Poll IMAP for new messages."""
        while True:
            # In production: connect to IMAP, search UNSEEN, fetch
            await asyncio.sleep(self._poll_interval)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[EMAIL_SMTP] → {response.channel_id} ({len(response.content)} chars)")
        # In production: smtplib.SMTP with starttls
        return True


class GmailAdapter(ChannelAdapter):
    """
    Gmail API adapter (OAuth2).
    Requires: token (OAuth access token), extra.refresh_token.
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.EMAIL_GMAIL
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.IMAGES,
            ChannelCapability.THREADS,
        }
        self._history_id = None
        self._poll_interval = config.extra.get("poll_interval", 15)
        self._label_filter = config.extra.get("label", "INBOX")

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[GMAIL] Missing OAuth token")
            return False
        logger.info("[GMAIL] Connected to Gmail API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[GMAIL] Disconnected")

    async def _listen(self):
        """Watch Gmail for new messages via polling or push notifications."""
        while True:
            # In production: GET /gmail/v1/users/me/messages?q=is:unread
            await asyncio.sleep(self._poll_interval)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[GMAIL] → thread={response.thread_id or 'new'} ({len(response.content)} chars)")
        # In production: POST /gmail/v1/users/me/messages/send
        return True


class OutlookAdapter(ChannelAdapter):
    """
    Microsoft Outlook/365 via Microsoft Graph API.
    Requires: token (OAuth access token), extra.tenant_id.
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.EMAIL_OUTLOOK
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.IMAGES,
            ChannelCapability.THREADS,
        }
        self._tenant_id = config.extra.get("tenant_id", "")
        self._poll_interval = config.extra.get("poll_interval", 15)
        self._subscription_id = ""

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[OUTLOOK] Missing OAuth token")
            return False
        logger.info(f"[OUTLOOK] Connected to Microsoft Graph — tenant={self._tenant_id}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[OUTLOOK] Disconnected")

    async def _listen(self):
        """Poll Microsoft Graph for new messages or use change notifications."""
        while True:
            # In production: GET /me/mailFolders/Inbox/messages?$filter=isRead eq false
            await asyncio.sleep(self._poll_interval)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[OUTLOOK] → {response.channel_id} ({len(response.content)} chars)")
        # In production: POST /me/sendMail
        return True
