"""
Business Channel Adapters — 6 Adapters
═══════════════════════════════════════
Salesforce · HubSpot · Zendesk · Intercom · Freshdesk · ServiceNow
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


class SalesforceAdapter(ChannelAdapter):
    """Salesforce adapter — Cases, Chatter, Platform Events."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.SALESFORCE
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.THREADS,
        }
        self._instance_url = config.host or ""
        self._api_version = config.extra.get("api_version", "v59.0")
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[SALESFORCE] Missing OAuth access token")
            return False
        logger.info(f"[SALESFORCE] Connected — {self._instance_url}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[SALESFORCE] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            sobject = event.get("sobject", {})
            yield ChannelMessage(
                channel_type=ChannelType.SALESFORCE,
                channel_id=sobject.get("Id", ""),
                sender_id=event.get("userId", ""),
                content=sobject.get("Description", sobject.get("Body", "")),
                thread_id=sobject.get("ParentId", ""),
                raw_event=event,
            )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[SALESFORCE] → {response.channel_id}")
        return True


class HubSpotAdapter(ChannelAdapter):
    """HubSpot adapter — Conversations API + webhooks."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.HUBSPOT
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.THREADS,
        }
        self._portal_id = config.extra.get("portal_id", "")
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.api_key:
            logger.error("[HUBSPOT] Missing API key or private app token")
            return False
        logger.info(f"[HUBSPOT] Connected — portal={self._portal_id}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[HUBSPOT] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            for item in event if isinstance(event, list) else [event]:
                obj_id = item.get("objectId", "")
                yield ChannelMessage(
                    channel_type=ChannelType.HUBSPOT,
                    channel_id=str(obj_id),
                    sender_id=str(item.get("portalId", "")),
                    content=item.get("propertyValue", str(item.get("subscriptionType", ""))),
                    raw_event=item,
                )

    def handle_webhook(self, payload: Any) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[HUBSPOT] → {response.channel_id}")
        return True


class ZendeskAdapter(ChannelAdapter):
    """Zendesk Support adapter — Tickets, triggers, webhooks."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.ZENDESK
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.THREADS,
        }
        self._subdomain = config.extra.get("subdomain", "")
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.api_key:
            logger.error("[ZENDESK] Missing API token")
            return False
        logger.info(f"[ZENDESK] Connected — {self._subdomain}.zendesk.com")
        return True

    async def _disconnect(self) -> None:
        logger.info("[ZENDESK] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            ticket = event.get("ticket", event)
            comment = event.get("comment", {})
            yield ChannelMessage(
                channel_type=ChannelType.ZENDESK,
                channel_id=str(ticket.get("id", "")),
                sender_id=str(comment.get("author_id", ticket.get("requester_id", ""))),
                sender_name=event.get("current_user", {}).get("name", ""),
                content=comment.get("body", ticket.get("description", "")),
                thread_id=str(ticket.get("id", "")),
                raw_event=event,
            )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[ZENDESK] → ticket={response.channel_id}")
        return True


class IntercomAdapter(ChannelAdapter):
    """Intercom adapter — Conversations, contacts, webhooks."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.INTERCOM
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.IMAGES,
            ChannelCapability.BUTTONS, ChannelCapability.CARDS,
        }
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[INTERCOM] Missing access token")
            return False
        logger.info("[INTERCOM] Connected to Intercom API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[INTERCOM] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            topic = event.get("topic", "")
            data = event.get("data", {}).get("item", {})
            conv_parts = data.get("conversation_parts", {}).get("conversation_parts", [])
            latest = conv_parts[-1] if conv_parts else {}
            yield ChannelMessage(
                channel_type=ChannelType.INTERCOM,
                channel_id=data.get("id", ""),
                sender_id=latest.get("author", {}).get("id", ""),
                sender_name=latest.get("author", {}).get("name", ""),
                content=latest.get("body", data.get("body", "")),
                thread_id=data.get("id", ""),
                raw_event=event,
                metadata={"topic": topic},
            )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[INTERCOM] → conversation={response.channel_id}")
        return True


class FreshdeskAdapter(ChannelAdapter):
    """Freshdesk adapter — Tickets via webhooks + REST API."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.FRESHDESK
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.THREADS,
        }
        self._domain = config.extra.get("domain", "")
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.api_key:
            logger.error("[FRESHDESK] Missing API key")
            return False
        logger.info(f"[FRESHDESK] Connected — {self._domain}.freshdesk.com")
        return True

    async def _disconnect(self) -> None:
        logger.info("[FRESHDESK] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            ticket = event.get("freshdesk_webhook", event)
            yield ChannelMessage(
                channel_type=ChannelType.FRESHDESK,
                channel_id=str(ticket.get("ticket_id", "")),
                sender_id=str(ticket.get("requester_id", "")),
                sender_name=ticket.get("requester_name", ""),
                content=ticket.get("ticket_description", ""),
                thread_id=str(ticket.get("ticket_id", "")),
                raw_event=event,
            )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[FRESHDESK] → ticket={response.channel_id}")
        return True


class ServiceNowAdapter(ChannelAdapter):
    """ServiceNow adapter — Incidents, catalog items, via REST + webhooks."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.SERVICENOW
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.THREADS,
        }
        self._instance = config.host or ""
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.api_key:
            logger.error("[SERVICENOW] Missing credentials")
            return False
        logger.info(f"[SERVICENOW] Connected — {self._instance}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[SERVICENOW] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            record = event.get("result", event)
            yield ChannelMessage(
                channel_type=ChannelType.SERVICENOW,
                channel_id=record.get("sys_id", record.get("number", "")),
                sender_id=record.get("opened_by", {}).get("value", ""),
                content=record.get("description", record.get("short_description", "")),
                thread_id=record.get("number", ""),
                raw_event=event,
            )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[SERVICENOW] → {response.channel_id}")
        return True
