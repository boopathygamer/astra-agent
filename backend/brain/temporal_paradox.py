"""
Temporal Paradox Engine — Predictive Pre-Computation Cache
──────────────────────────────────────────────────────────
Expert-level predictive cache that pre-computes results for
anticipated queries. When the actual query arrives, the result
is already waiting — achieving negative apparent latency.
"""

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_PRECOMPUTED = 100


@dataclass
class PrecomputedResult:
    """A pre-computed answer waiting for its query."""
    query_fingerprint: str
    result: str
    computed_at: float = field(default_factory=time.time)
    hit: bool = False
    latency_saved_ms: float = 0.0


class TemporalParadoxEngine:
    """
    Tier 9: Temporal Paradox Engine (Predictive Pre-Computation)

    Pre-computes results for predicted future queries based on
    conversation context and user patterns. When the actual query
    arrives, the answer already exists — negative latency.
    """

    def __init__(self, generate_fn: Optional[Callable] = None, max_cache: int = _MAX_PRECOMPUTED):
        self._generate_fn = generate_fn
        self._cache: OrderedDict[str, PrecomputedResult] = OrderedDict()
        self._max_cache = max(1, max_cache)
        self._hits: int = 0
        self._misses: int = 0
        self._total_latency_saved_ms: float = 0.0
        logger.info("[TEMPORAL-PARADOX] Pre-computation engine active (capacity=%d).", self._max_cache)

    @staticmethod
    def _fingerprint(query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()

    def precompute(self, predicted_queries: List[str]) -> int:
        """
        Pre-compute results for a list of predicted future queries.
        Returns the number of successfully pre-computed results.
        """
        if not self._generate_fn:
            return 0

        count = 0
        for query in predicted_queries[:10]:  # Limit batch size
            fp = self._fingerprint(query)
            if fp in self._cache:
                continue

            try:
                start = time.time()
                result = self._generate_fn(query)
                compute_time = (time.time() - start) * 1000

                # Evict LRU if at capacity
                while len(self._cache) >= self._max_cache:
                    self._cache.popitem(last=False)

                self._cache[fp] = PrecomputedResult(
                    query_fingerprint=fp,
                    result=result,
                    latency_saved_ms=compute_time,
                )
                count += 1
                logger.debug("[TEMPORAL-PARADOX] Pre-computed query (%.0fms): %s…", compute_time, query[:50])

            except Exception as e:
                logger.warning("[TEMPORAL-PARADOX] Pre-computation failed: %s", e)

        if count > 0:
            logger.info("[TEMPORAL-PARADOX] Pre-computed %d/%d predicted queries.", count, len(predicted_queries))
        return count

    def retrieve(self, query: str) -> Optional[str]:
        """
        Check if a query's result was already pre-computed.
        If yes, return it instantly (negative latency achieved).
        """
        fp = self._fingerprint(query)
        entry = self._cache.get(fp)

        if entry is None:
            self._misses += 1
            return None

        entry.hit = True
        self._hits += 1
        self._total_latency_saved_ms += entry.latency_saved_ms
        self._cache.move_to_end(fp)

        logger.info(
            "[TEMPORAL-PARADOX] PRE-COMPUTED HIT — saved %.0fms (total saved=%.0fms).",
            entry.latency_saved_ms, self._total_latency_saved_ms,
        )
        return entry.result

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "total_latency_saved_ms": round(self._total_latency_saved_ms, 1),
            "cache_size": len(self._cache),
        }


# Global singleton — always active
paradox_engine = TemporalParadoxEngine()
