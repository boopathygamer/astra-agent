"""
Developer Channel Adapters — 6 Adapters
════════════════════════════════════════
GitHub · GitLab · Jira · Linear · Notion · Confluence
"""

import asyncio
import hashlib
import hmac
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


class GitHubAdapter(ChannelAdapter):
    """
    GitHub adapter — Issues, PRs, Discussions, webhooks.
    Requires: token (PAT or GitHub App token), webhook_secret.
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.GITHUB
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.REACTIONS, ChannelCapability.THREADS,
        }
        self._webhook_queue: asyncio.Queue = asyncio.Queue()
        self._watched_events = config.extra.get("events", [
            "issues", "issue_comment", "pull_request",
            "pull_request_review_comment", "discussion", "discussion_comment",
        ])

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[GITHUB] Missing token (PAT or App)")
            return False
        logger.info("[GITHUB] Connected to GitHub API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[GITHUB] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            msg = self._parse_webhook(event)
            if msg:
                yield msg

    def handle_webhook(self, headers: Dict[str, str], payload: Dict[str, Any]) -> bool:
        """Verify and enqueue a GitHub webhook event."""
        if self.config.webhook_secret:
            sig = headers.get("X-Hub-Signature-256", "")
            expected = "sha256=" + hmac.new(
                self.config.webhook_secret.encode(), 
                str(payload).encode(), 
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig, expected):
                logger.warning("[GITHUB] Invalid webhook signature")
                return False
        self._webhook_queue.put_nowait({
            "event_type": headers.get("X-GitHub-Event", ""),
            "payload": payload,
        })
        return True

    def _parse_webhook(self, event: Dict[str, Any]) -> Optional[ChannelMessage]:
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})

        # Extract content based on event type
        content = ""
        sender = {}
        repo = payload.get("repository", {}).get("full_name", "")

        if event_type in ("issues", "issue_comment"):
            issue = payload.get("issue", {})
            comment = payload.get("comment", {})
            sender = comment.get("user", issue.get("user", {}))
            content = comment.get("body", issue.get("body", ""))
            channel_id = f"{repo}/issues/{issue.get('number', '')}"
        elif event_type in ("pull_request", "pull_request_review_comment"):
            pr = payload.get("pull_request", {})
            comment = payload.get("comment", {})
            sender = comment.get("user", pr.get("user", {}))
            content = comment.get("body", pr.get("body", ""))
            channel_id = f"{repo}/pulls/{pr.get('number', '')}"
        elif event_type in ("discussion", "discussion_comment"):
            disc = payload.get("discussion", {})
            comment = payload.get("comment", {})
            sender = comment.get("user", disc.get("user", {}))
            content = comment.get("body", disc.get("body", ""))
            channel_id = f"{repo}/discussions/{disc.get('number', '')}"
        else:
            return None

        if not content:
            return None

        return ChannelMessage(
            channel_type=ChannelType.GITHUB,
            channel_id=channel_id,
            sender_id=sender.get("login", ""),
            sender_name=sender.get("login", ""),
            sender_avatar=sender.get("avatar_url", ""),
            content=content,
            content_type="text",
            thread_id=channel_id,
            raw_event=event,
            metadata={"event_type": event_type, "action": payload.get("action", "")},
        )

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[GITHUB] → {response.channel_id} ({len(response.content)} chars)")
        # In production: POST /repos/{owner}/{repo}/issues/{num}/comments
        return True


class GitLabAdapter(ChannelAdapter):
    """GitLab adapter — Issues, MRs, webhooks."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.GITLAB
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.REACTIONS, ChannelCapability.THREADS,
        }
        self._base_url = config.host or "https://gitlab.com"
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[GITLAB] Missing personal access token")
            return False
        logger.info(f"[GITLAB] Connected to {self._base_url}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[GITLAB] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            obj_attrs = event.get("object_attributes", {})
            user = event.get("user", {})
            project = event.get("project", {})
            content = obj_attrs.get("description", obj_attrs.get("note", ""))
            if content:
                yield ChannelMessage(
                    channel_type=ChannelType.GITLAB,
                    channel_id=f"{project.get('path_with_namespace', '')}/{obj_attrs.get('iid', '')}",
                    sender_id=user.get("username", ""),
                    sender_name=user.get("name", ""),
                    sender_avatar=user.get("avatar_url", ""),
                    content=content,
                    raw_event=event,
                )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[GITLAB] → {response.channel_id}")
        return True


class JiraAdapter(ChannelAdapter):
    """Jira Cloud/Server adapter via webhooks + REST API."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.JIRA
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.THREADS,
        }
        self._base_url = config.host or "https://your-domain.atlassian.net"
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.api_key:
            logger.error("[JIRA] Missing API token")
            return False
        logger.info(f"[JIRA] Connected to {self._base_url}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[JIRA] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            issue = event.get("issue", {})
            comment = event.get("comment", {})
            content = comment.get("body", issue.get("fields", {}).get("description", ""))
            if content:
                fields = issue.get("fields", {})
                reporter = fields.get("reporter", {}) if not comment else comment.get("author", {})
                yield ChannelMessage(
                    channel_type=ChannelType.JIRA,
                    channel_id=issue.get("key", ""),
                    sender_id=reporter.get("accountId", ""),
                    sender_name=reporter.get("displayName", ""),
                    sender_avatar=reporter.get("avatarUrls", {}).get("48x48", ""),
                    content=content,
                    thread_id=issue.get("key", ""),
                    raw_event=event,
                )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[JIRA] → {response.channel_id} ({len(response.content)} chars)")
        # In production: POST /rest/api/3/issue/{key}/comment
        return True


class LinearAdapter(ChannelAdapter):
    """Linear issue tracker adapter via webhooks + GraphQL API."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.LINEAR
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.THREADS,
        }
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.api_key:
            logger.error("[LINEAR] Missing API key")
            return False
        logger.info("[LINEAR] Connected to Linear GraphQL API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[LINEAR] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            data = event.get("data", {})
            yield ChannelMessage(
                channel_type=ChannelType.LINEAR,
                channel_id=data.get("identifier", data.get("id", "")),
                sender_id=data.get("creatorId", ""),
                content=data.get("description", data.get("body", "")),
                thread_id=data.get("issueId", ""),
                raw_event=event,
            )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[LINEAR] → {response.channel_id}")
        return True


class NotionAdapter(ChannelAdapter):
    """Notion API adapter — pages, databases, comments."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.NOTION
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.IMAGES, ChannelCapability.FILES,
        }
        self._poll_interval = config.extra.get("poll_interval", 30)
        self._watched_databases = config.extra.get("database_ids", [])

    async def _connect(self) -> bool:
        if not self.config.token:
            logger.error("[NOTION] Missing integration token")
            return False
        logger.info("[NOTION] Connected to Notion API")
        return True

    async def _disconnect(self) -> None:
        logger.info("[NOTION] Disconnected")

    async def _listen(self):
        """Poll Notion databases for new/updated items."""
        while True:
            # In production: query each watched database for recent changes
            await asyncio.sleep(self._poll_interval)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[NOTION] → page={response.channel_id}")
        # In production: POST /v1/comments or PATCH /v1/pages/{page_id}
        return True


class ConfluenceAdapter(ChannelAdapter):
    """Atlassian Confluence adapter — pages and comments."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.channel_type = ChannelType.CONFLUENCE
        self.capabilities = {
            ChannelCapability.TEXT, ChannelCapability.RICH_TEXT,
            ChannelCapability.FILES, ChannelCapability.IMAGES,
        }
        self._base_url = config.host or "https://your-domain.atlassian.net/wiki"
        self._webhook_queue: asyncio.Queue = asyncio.Queue()

    async def _connect(self) -> bool:
        if not self.config.api_key:
            logger.error("[CONFLUENCE] Missing API token")
            return False
        logger.info(f"[CONFLUENCE] Connected to {self._base_url}")
        return True

    async def _disconnect(self) -> None:
        logger.info("[CONFLUENCE] Disconnected")

    async def _listen(self):
        while True:
            event = await self._webhook_queue.get()
            page = event.get("page", {})
            comment = event.get("comment", {})
            content = comment.get("body", {}).get("storage", {}).get("value", "")
            if not content:
                content = page.get("title", "")
            yield ChannelMessage(
                channel_type=ChannelType.CONFLUENCE,
                channel_id=page.get("id", ""),
                sender_id=event.get("userAccountId", ""),
                content=content,
                thread_id=page.get("id", ""),
                raw_event=event,
            )

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        self._webhook_queue.put_nowait(payload)

    async def _send(self, response: ChannelResponse) -> bool:
        logger.info(f"[CONFLUENCE] → page={response.channel_id}")
        return True
