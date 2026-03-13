"""
Akashic Node — O(1) Semantic Knowledge Singularity
───────────────────────────────────────────────────
Expert-level content-addressed knowledge cache. Instead of re-generating
answers to previously solved problems, the Akashic Node stores solutions
indexed by SHA3-256 semantic fingerprints for instant O(1) retrieval.

Integrates with the ThinkingLoop as a first-pass oracle: if the answer
already exists in the singularity, bypass all 106 cognitive modules.
"""

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_MAX_SINGULARITY_SIZE = 10_000  # Maximum cached entries before LRU eviction


@dataclass(frozen=True)
class AkashicEntry:
    """Immutable record of a pre-solved concept."""
    fingerprint: str
    answer: str
    confidence: float
    domain: str
    created_at: float = field(default_factory=time.time)


class AkashicNode:
    """
    Tier 9: The Akashic Root-Node (Omniscient Code Manifestation)

    Content-addressed O(1) knowledge singularity. Solutions are SHA3-256
    fingerprinted and stored in an LRU-evicting ordered dictionary.
    Retrieval is instantaneous — no LLM call, no reasoning loop.
    """

    def __init__(self, max_size: int = _MAX_SINGULARITY_SIZE):
        self._singularity: OrderedDict[str, AkashicEntry] = OrderedDict()
        self._max_size = max(1, max_size)
        self._hits: int = 0
        self._misses: int = 0
        logger.info("[AKASHIC-NODE] Singularity initialized (capacity=%d).", self._max_size)

    @staticmethod
    def _fingerprint(concept: str) -> str:
        """SHA3-256 content-addressed fingerprint for deterministic lookup."""
        return hashlib.sha3_256(concept.strip().lower().encode("utf-8")).hexdigest()

    def absorb(self, concept: str, answer: str, confidence: float = 1.0, domain: str = "general") -> AkashicEntry:
        """
        Absorb a solved concept into the singularity for future O(1) retrieval.
        Evicts LRU entries if capacity is exceeded.
        """
        fp = self._fingerprint(concept)
        entry = AkashicEntry(
            fingerprint=fp,
            answer=answer,
            confidence=max(0.0, min(1.0, confidence)),
            domain=domain,
        )

        # Move to end (most recently used) if already exists
        if fp in self._singularity:
            self._singularity.move_to_end(fp)
            self._singularity[fp] = entry
            logger.debug("[AKASHIC-NODE] Updated existing entry: %s", fp[:16])
            return entry

        # Evict LRU if at capacity
        while len(self._singularity) >= self._max_size:
            evicted_key, _ = self._singularity.popitem(last=False)
            logger.debug("[AKASHIC-NODE] LRU eviction: %s", evicted_key[:16])

        self._singularity[fp] = entry
        logger.info("[AKASHIC-NODE] Absorbed concept into singularity (size=%d).", len(self._singularity))
        return entry

    def perceive(self, query: str, min_confidence: float = 0.5) -> Optional[str]:
        """
        O(1) retrieval. Returns the pre-solved answer if it exists in the
        singularity and meets the minimum confidence threshold.
        """
        fp = self._fingerprint(query)
        entry = self._singularity.get(fp)

        if entry is None:
            self._misses += 1
            logger.debug("[AKASHIC-NODE] Cache MISS (misses=%d).", self._misses)
            return None

        if entry.confidence < min_confidence:
            self._misses += 1
            logger.debug("[AKASHIC-NODE] Entry found but below confidence threshold (%.2f < %.2f).",
                         entry.confidence, min_confidence)
            return None

        # Move to end (most recently used)
        self._singularity.move_to_end(fp)
        self._hits += 1
        logger.info("[AKASHIC-NODE] Singularity HIT — 0 computation cycles (hits=%d, ratio=%.2f%%).",
                     self._hits, self.hit_ratio * 100)
        return entry.answer

    @property
    def hit_ratio(self) -> float:
        """Cache hit ratio as a float between 0.0 and 1.0."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._singularity)

    def purge(self) -> int:
        """Wipe the entire singularity. Returns number of entries purged."""
        count = len(self._singularity)
        self._singularity.clear()
        self._hits = 0
        self._misses = 0
        logger.warning("[AKASHIC-NODE] Singularity purged (%d entries destroyed).", count)
        return count


# Global singleton — always active when the system starts
akashic_root = AkashicNode()
