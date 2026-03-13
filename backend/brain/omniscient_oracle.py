"""
Omniscient Oracle — Background Knowledge Ingestion Daemon
─────────────────────────────────────────────────────────
Expert-level async daemon that continuously ingests knowledge
from configured data sources, vectorizing and storing them
for RAG retrieval. Replaces hardcoded random data with
configurable source feeds.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeItem:
    """A piece of ingested knowledge."""
    source: str
    title: str
    content: str
    ingested_at: float = field(default_factory=time.time)


class KnowledgeFeed:
    """Configurable knowledge feed that can be populated with real data sources."""

    def __init__(self):
        self._static_feeds: List[Dict[str, str]] = []
        self._fetch_fn: Optional[Callable] = None

    def add_static(self, source: str, title: str, content: str) -> None:
        """Add a static knowledge item to the feed."""
        self._static_feeds.append({"source": source, "title": title, "content": content})

    def set_fetch_function(self, fn: Callable) -> None:
        """Set a custom fetch function for dynamic data ingestion."""
        self._fetch_fn = fn

    def fetch(self) -> List[Dict[str, str]]:
        """Fetch knowledge items from all configured sources."""
        if self._fetch_fn:
            try:
                return self._fetch_fn()
            except Exception as e:
                logger.error("[ORACLE-FEED] Fetch function failed: %s", e)
        return list(self._static_feeds)


class OmniscientOracle:
    """
    ASI Omniscient Oracle: Background Knowledge Ingestion

    Async daemon that ingests knowledge from configured feeds,
    storing them in the memory manager for RAG retrieval.
    """

    def __init__(self, memory_manager):
        self.feed = KnowledgeFeed()
        self.memory = memory_manager
        self.is_running = False
        self._items_ingested: int = 0
        self._cycle_count: int = 0
        self._poll_interval: float = 1800  # 30 minutes default

    async def run_oracle_loop(self) -> None:
        """Async execution loop for perpetual knowledge ingestion."""
        logger.info("[ASI ORACLE] Knowledge ingestion daemon starting (poll=%.0fs)...",
                    self._poll_interval)
        self.is_running = True

        await asyncio.sleep(3)  # Startup delay

        while self.is_running:
            try:
                self._cycle_count += 1
                new_knowledge = self.feed.fetch()

                for item in new_knowledge:
                    logger.info("[ASI ORACLE] Ingesting: %s — %s", item.get("source", "?"), item.get("title", "?"))

                    if hasattr(self.memory, "semantic_memory"):
                        try:
                            self.memory.semantic_memory.add_snippet(
                                content=f"TITLE: {item['title']}\nCONTENT: {item['content']}",
                                source=item["source"],
                                metadata={"type": "asi_omniscience", "timestamp": time.time()}
                            )
                            self._items_ingested += 1
                        except Exception as e:
                            logger.warning("[ASI ORACLE] Memory ingestion failed: %s", e)

                logger.debug("[ASI ORACLE] Cycle %d complete. %d total items ingested.",
                             self._cycle_count, self._items_ingested)

                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[ASI ORACLE] Exception in oracle loop: %s", e)
                await asyncio.sleep(60)

        logger.info("[ASI ORACLE] Daemon stopped.")

    def stop(self) -> None:
        """Stop the oracle daemon."""
        self.is_running = False

    @property
    def stats(self) -> dict:
        return {"items_ingested": self._items_ingested, "cycles": self._cycle_count}
