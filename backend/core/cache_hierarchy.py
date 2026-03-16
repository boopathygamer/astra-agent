"""
Intelligent Cache Hierarchy — L1/L2/L3 Multi-Tier Caching
═════════════════════════════════════════════════════════
Three-level cache for responses, embeddings, and computations:

  L1 (Memory)  — Exact hash match, <1ms, 1000 entries max
  L2 (Semantic) — Similarity match via token overlap, <10ms, 5000 entries
  L3 (Disk)     — Persistent JSON cache, <50ms, unlimited

Features:
  - TTL-based expiration per tier
  - LRU eviction policies
  - Hit/miss rate tracking
  - Automatic tier promotion on repeated access
  - Warm-up from disk on startup
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cache entry with metadata."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    ttl_seconds: float = 3600  # 1 hour default
    tier: str = "L1"
    hash_key: str = ""

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    def touch(self):
        self.accessed_at = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache performance statistics."""
    l1_hits: int = 0
    l1_misses: int = 0
    l2_hits: int = 0
    l2_misses: int = 0
    l3_hits: int = 0
    l3_misses: int = 0
    total_lookups: int = 0
    total_writes: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total_hits = self.l1_hits + self.l2_hits + self.l3_hits
        return total_hits / max(self.total_lookups, 1)

    @property
    def l1_hit_rate(self) -> float:
        return self.l1_hits / max(self.l1_hits + self.l1_misses, 1)


class CacheHierarchy:
    """
    Three-tier cache with automatic promotion, eviction,
    and semantic matching capabilities.
    """

    L1_MAX = 1000    # Memory cache
    L2_MAX = 5000    # Semantic cache
    L3_TTL = 86400   # 24 hours for disk

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path("data/cache")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # L1: Exact match (OrderedDict for LRU)
        self._l1: OrderedDict[str, CacheEntry] = OrderedDict()
        # L2: Semantic match (token overlap)
        self._l2: OrderedDict[str, CacheEntry] = OrderedDict()
        # L3: Disk persistence
        self._l3_path = self.data_dir / "l3_cache.json"

        self._stats = CacheStats()
        self._lock = threading.Lock()

        self._warm_from_disk()
        logger.info(f"[CACHE] Hierarchy initialized: L1={len(self._l1)}, L2={len(self._l2)}")

    # ── Lookup ──

    def get(self, query: str, similarity_threshold: float = 0.6) -> Optional[Any]:
        """Look up query through L1 → L2 → L3 hierarchy."""
        self._stats.total_lookups += 1
        hash_key = self._hash(query)

        # L1: Exact match
        with self._lock:
            if hash_key in self._l1:
                entry = self._l1[hash_key]
                if not entry.is_expired:
                    entry.touch()
                    self._l1.move_to_end(hash_key)
                    self._stats.l1_hits += 1
                    return entry.value
                else:
                    del self._l1[hash_key]
            self._stats.l1_misses += 1

        # L2: Semantic similarity match
        query_tokens = set(query.lower().split())
        best_match = None
        best_score = 0.0

        with self._lock:
            for key, entry in self._l2.items():
                if entry.is_expired:
                    continue
                entry_tokens = set(entry.key.lower().split())
                if not query_tokens or not entry_tokens:
                    continue
                # Jaccard similarity
                intersection = len(query_tokens & entry_tokens)
                union = len(query_tokens | entry_tokens)
                score = intersection / max(union, 1)
                if score > best_score and score >= similarity_threshold:
                    best_score = score
                    best_match = entry

        if best_match:
            best_match.touch()
            self._stats.l2_hits += 1
            # Promote to L1
            self._promote_to_l1(best_match)
            return best_match.value
        self._stats.l2_misses += 1

        # L3: Disk cache
        disk_result = self._check_l3(hash_key)
        if disk_result is not None:
            self._stats.l3_hits += 1
            # Promote to L1 and L2
            entry = CacheEntry(
                key=query, value=disk_result,
                hash_key=hash_key, tier="L3",
            )
            self._promote_to_l1(entry)
            self._promote_to_l2(entry)
            return disk_result
        self._stats.l3_misses += 1

        return None

    # ── Store ──

    def put(self, query: str, value: Any,
            ttl: float = 3600, persist: bool = True):
        """Store a value in all appropriate tiers."""
        hash_key = self._hash(query)
        entry = CacheEntry(
            key=query, value=value, hash_key=hash_key,
            ttl_seconds=ttl,
        )

        self._stats.total_writes += 1

        # Store in L1
        with self._lock:
            self._l1[hash_key] = entry
            self._l1.move_to_end(hash_key)
            if len(self._l1) > self.L1_MAX:
                self._l1.popitem(last=False)
                self._stats.evictions += 1

        # Store in L2
        with self._lock:
            self._l2[hash_key] = CacheEntry(
                key=query, value=value, hash_key=hash_key,
                ttl_seconds=ttl, tier="L2",
            )
            if len(self._l2) > self.L2_MAX:
                self._l2.popitem(last=False)
                self._stats.evictions += 1

        # Persist to L3
        if persist:
            self._write_l3(hash_key, query, value)

    # ── Eviction ──

    def invalidate(self, query: str):
        """Remove a query from all cache tiers."""
        hash_key = self._hash(query)
        with self._lock:
            self._l1.pop(hash_key, None)
            self._l2.pop(hash_key, None)

    def clear_all(self):
        """Clear all cache tiers."""
        with self._lock:
            self._l1.clear()
            self._l2.clear()
        if self._l3_path.exists():
            self._l3_path.unlink()
        self._stats = CacheStats()

    def evict_expired(self) -> int:
        """Remove expired entries from all tiers."""
        evicted = 0
        with self._lock:
            expired_l1 = [k for k, v in self._l1.items() if v.is_expired]
            for k in expired_l1:
                del self._l1[k]
                evicted += 1
            expired_l2 = [k for k, v in self._l2.items() if v.is_expired]
            for k in expired_l2:
                del self._l2[k]
                evicted += 1
        self._stats.evictions += evicted
        return evicted

    # ── Internal ──

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode()).hexdigest()[:16]

    def _promote_to_l1(self, entry: CacheEntry):
        with self._lock:
            self._l1[entry.hash_key] = entry
            self._l1.move_to_end(entry.hash_key)
            if len(self._l1) > self.L1_MAX:
                self._l1.popitem(last=False)

    def _promote_to_l2(self, entry: CacheEntry):
        with self._lock:
            self._l2[entry.hash_key] = entry
            if len(self._l2) > self.L2_MAX:
                self._l2.popitem(last=False)

    def _check_l3(self, hash_key: str) -> Optional[Any]:
        if not self._l3_path.exists():
            return None
        try:
            data = json.loads(self._l3_path.read_text(encoding="utf-8"))
            entry = data.get(hash_key)
            if entry:
                created = entry.get("created_at", 0)
                if (time.time() - created) < self.L3_TTL:
                    return entry.get("value")
        except Exception:
            pass
        return None

    def _write_l3(self, hash_key: str, query: str, value: Any):
        try:
            data = {}
            if self._l3_path.exists():
                try:
                    data = json.loads(self._l3_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            # Only cache serializable values
            if isinstance(value, str):
                data[hash_key] = {
                    "query": query[:200],
                    "value": value[:2000],
                    "created_at": time.time(),
                }
                self._l3_path.write_text(
                    json.dumps(data, indent=2), encoding="utf-8",
                )
        except Exception as e:
            logger.debug(f"[CACHE] L3 write failed: {e}")

    def _warm_from_disk(self):
        """Pre-load L3 entries into L1/L2 on startup."""
        if not self._l3_path.exists():
            return
        try:
            data = json.loads(self._l3_path.read_text(encoding="utf-8"))
            loaded = 0
            for hash_key, entry_data in list(data.items())[:100]:
                created = entry_data.get("created_at", 0)
                if (time.time() - created) < self.L3_TTL:
                    entry = CacheEntry(
                        key=entry_data.get("query", ""),
                        value=entry_data.get("value", ""),
                        hash_key=hash_key,
                        created_at=created,
                    )
                    self._l2[hash_key] = entry
                    loaded += 1
            if loaded:
                logger.info(f"[CACHE] Warmed {loaded} entries from L3")
        except Exception:
            pass

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        return {
            "l1_size": len(self._l1),
            "l2_size": len(self._l2),
            "l1_max": self.L1_MAX,
            "l2_max": self.L2_MAX,
            "hit_rate": round(self._stats.hit_rate, 3),
            "l1_hit_rate": round(self._stats.l1_hit_rate, 3),
            "total_lookups": self._stats.total_lookups,
            "total_writes": self._stats.total_writes,
            "evictions": self._stats.evictions,
            "l1_hits": self._stats.l1_hits,
            "l2_hits": self._stats.l2_hits,
            "l3_hits": self._stats.l3_hits,
        }
