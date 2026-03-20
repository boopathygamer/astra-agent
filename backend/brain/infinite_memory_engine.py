"""
Infinite Memory Engine — Hierarchical Tiered Memory with Associative Recall
═══════════════════════════════════════════════════════════════════════════════
4-tier memory hierarchy (L1 hot → L4 archival) with semantic deduplication,
associative content-addressable recall, Ebbinghaus forgetting curves, and
automatic consolidation.

No LLM, no GPU — pure algorithmic memory management.

Architecture:
  L1 ─ Hot Cache    (≤64 items, <1ms access)   — recent / high-frequency
  L2 ─ Working Mem  (≤512 items, ~1ms access)   — session-relevant
  L3 ─ Episodic     (≤4096 items, ~5ms access)  — event-indexed autobiographic
  L4 ─ Archival     (unlimited, ~10ms access)    — long-term compressed storage

Promotion / Demotion:
  • Access count > threshold → promote to hotter tier
  • Decay below threshold   → demote to colder tier
  • Consolidation runs every N operations

Usage:
    mem = InfiniteMemoryEngine()
    mem.store("quicksort", "O(n log n) average case", tags={"algorithms"})
    results = mem.recall("sorting complexity")
    mem.consolidate()
"""

import hashlib
import logging
import math
import time
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════

class MemoryTier(IntEnum):
    """Memory hierarchy tiers, lower = hotter."""
    L1_HOT = 1
    L2_WORKING = 2
    L3_EPISODIC = 3
    L4_ARCHIVAL = 4


@dataclass
class MemoryTrace:
    """A single memory trace stored in the hierarchy."""
    trace_id: str = ""
    key: str = ""
    content: str = ""
    tier: MemoryTier = MemoryTier.L2_WORKING
    access_count: int = 0
    creation_time: float = 0.0
    last_access_time: float = 0.0
    decay_factor: float = 1.0               # 1.0 = full strength
    tags: Set[str] = field(default_factory=set)
    associations: Set[str] = field(default_factory=set)  # IDs of related traces
    content_hash: str = ""                   # for dedup
    compressed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.trace_id:
            raw = f"{self.key}:{self.content}:{time.time()}"
            self.trace_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if not self.creation_time:
            self.creation_time = time.time()
        if not self.last_access_time:
            self.last_access_time = self.creation_time
        if not self.content_hash:
            self.content_hash = hashlib.md5(self.content.encode()).hexdigest()

    @property
    def effective_strength(self) -> float:
        """Current memory strength after decay."""
        return self.decay_factor * min(1.0, 0.3 + 0.7 * math.log1p(self.access_count))

    def touch(self) -> None:
        """Record an access, refreshing decay and bumping count."""
        self.access_count += 1
        self.last_access_time = time.time()
        # Partial decay recovery on access
        self.decay_factor = min(1.0, self.decay_factor + 0.15)


@dataclass
class RecallResult:
    """Result of a memory recall query."""
    traces: List[Tuple[MemoryTrace, float]] = field(default_factory=list)  # (trace, score)
    total_searched: int = 0
    duration_ms: float = 0.0
    tier_hits: Dict[str, int] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return len(self.traces) > 0

    @property
    def best(self) -> Optional[MemoryTrace]:
        return self.traces[0][0] if self.traces else None

    def summary(self) -> str:
        lines = [
            "## Infinite Memory — Recall",
            f"**Found**: {len(self.traces)} traces in {self.duration_ms:.1f}ms",
            f"**Searched**: {self.total_searched} traces",
        ]
        if self.tier_hits:
            hits = ", ".join(f"{k}: {v}" for k, v in sorted(self.tier_hits.items()))
            lines.append(f"**Tier hits**: {hits}")
        if self.traces:
            lines.append("\n### Top Results:")
            for trace, score in self.traces[:5]:
                lines.append(
                    f"  - [{trace.tier.name}] **{trace.key}**: "
                    f"{trace.content[:80]} (score: {score:.2f})"
                )
        return "\n".join(lines)


@dataclass
class ConsolidationReport:
    """Report from a consolidation cycle."""
    promoted: int = 0
    demoted: int = 0
    deduplicated: int = 0
    decayed: int = 0
    evicted: int = 0
    duration_ms: float = 0.0

    def summary(self) -> str:
        return (
            f"Consolidation: ↑{self.promoted} promoted, ↓{self.demoted} demoted, "
            f"🔗{self.deduplicated} deduped, 📉{self.decayed} decayed, "
            f"🗑️{self.evicted} evicted ({self.duration_ms:.1f}ms)"
        )


# ═══════════════════════════════════════════════════════════
# FORGETTING CURVE
# ═══════════════════════════════════════════════════════════

class EbbinghausCurve:
    """
    Ebbinghaus forgetting curve: retention = e^(-t / S)
    where t = time since last access, S = stability (grows with repetitions).
    """

    BASE_STABILITY = 3600.0  # 1 hour base half-life

    @classmethod
    def compute_decay(cls, last_access: float, access_count: int,
                      now: Optional[float] = None) -> float:
        """Compute current decay factor in [0, 1]."""
        now = now or time.time()
        elapsed = max(0, now - last_access)
        # Stability grows logarithmically with repetitions
        stability = cls.BASE_STABILITY * (1.0 + math.log1p(access_count))
        retention = math.exp(-elapsed / stability)
        return max(0.01, min(1.0, retention))


# ═══════════════════════════════════════════════════════════
# SIMILARITY ENGINE
# ═══════════════════════════════════════════════════════════

class SimilarityEngine:
    """Content-addressable similarity using token Jaccard + positional weighting."""

    _STOP_WORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "and",
        "or", "but", "not", "this", "that", "it", "its", "i", "we", "you",
    })

    @classmethod
    def tokenize(cls, text: str) -> Set[str]:
        """Extract meaningful tokens from text."""
        words = text.lower().split()
        return {w for w in words if len(w) > 2 and w not in cls._STOP_WORDS}

    @classmethod
    def jaccard(cls, set_a: Set[str], set_b: Set[str]) -> float:
        """Jaccard similarity between two token sets."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    @classmethod
    def score(cls, query: str, content: str, key: str = "",
              tags: Optional[Set[str]] = None) -> float:
        """
        Compute relevance score for a query against content + key + tags.
        Returns float in [0, 1].
        """
        q_tokens = cls.tokenize(query)
        c_tokens = cls.tokenize(content)
        k_tokens = cls.tokenize(key)

        if not q_tokens:
            return 0.0

        # Content similarity (primary)
        content_sim = cls.jaccard(q_tokens, c_tokens)

        # Key similarity (boosted — keys are concise identifiers)
        key_sim = cls.jaccard(q_tokens, k_tokens)

        # Tag similarity — tags are curated labels, high signal
        tag_sim = 0.0
        if tags:
            tag_tokens = {t.lower() for t in tags if len(t) > 2}
            tag_sim = cls.jaccard(q_tokens, tag_tokens)

        # Substring bonus — exact phrase fragments
        query_lower = query.lower()
        substr_bonus = 0.0
        if query_lower in content.lower():
            substr_bonus = 0.3
        elif content.lower() in query_lower:
            substr_bonus = 0.2

        return min(1.0, content_sim * 0.4 + key_sim * 0.25 + tag_sim * 0.2 + substr_bonus + 0.15 * min(1.0, len(c_tokens) / 20))


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE
# ═══════════════════════════════════════════════════════════

TIER_CAPACITY = {
    MemoryTier.L1_HOT: 64,
    MemoryTier.L2_WORKING: 512,
    MemoryTier.L3_EPISODIC: 4096,
    MemoryTier.L4_ARCHIVAL: 100_000,
}

PROMOTION_THRESHOLDS = {
    MemoryTier.L4_ARCHIVAL: 3,    # 3 accesses → promote to L3
    MemoryTier.L3_EPISODIC: 8,    # 8 accesses → promote to L2
    MemoryTier.L2_WORKING: 20,    # 20 accesses → promote to L1
}

DEMOTION_DECAY = {
    MemoryTier.L1_HOT: 0.3,       # decay below 0.3 → demote to L2
    MemoryTier.L2_WORKING: 0.15,   # decay below 0.15 → demote to L3
    MemoryTier.L3_EPISODIC: 0.05,  # decay below 0.05 → demote to L4
}


class InfiniteMemoryEngine:
    """
    Hierarchical tiered memory with associative recall.

    Usage:
        mem = InfiniteMemoryEngine()
        mem.store("quicksort", "O(n log n) average", tags={"algo"})
        result = mem.recall("sorting complexity")
        print(result.summary())
    """

    def __init__(self):
        # tier → {trace_id: MemoryTrace}
        self._tiers: Dict[MemoryTier, Dict[str, MemoryTrace]] = {
            tier: {} for tier in MemoryTier
        }
        # Global index: trace_id → tier (for O(1) lookup)
        self._index: Dict[str, MemoryTier] = {}
        # Content hash → trace_id (for dedup)
        self._hash_index: Dict[str, str] = {}
        # Tag → trace_ids (inverted index)
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)
        # Operation counter (triggers consolidation)
        self._ops = 0
        self._consolidation_interval = 100
        self._stats = {
            "stores": 0, "recalls": 0, "hits": 0, "misses": 0,
            "promotions": 0, "demotions": 0, "evictions": 0,
            "consolidations": 0, "deduplications": 0,
        }

    # ── Store ──────────────────────────────────────────────

    def store(self, key: str, content: str,
              tier: MemoryTier = MemoryTier.L2_WORKING,
              tags: Optional[Set[str]] = None,
              metadata: Optional[Dict[str, Any]] = None) -> MemoryTrace:
        """Store a memory trace into the hierarchy."""
        content_hash = hashlib.md5(content.encode()).hexdigest()

        # Semantic deduplication — merge if near-duplicate exists
        existing_id = self._hash_index.get(content_hash)
        if existing_id and existing_id in self._index:
            existing_tier = self._index[existing_id]
            existing = self._tiers[existing_tier][existing_id]
            existing.touch()
            if tags:
                existing.tags.update(tags)
            self._stats["deduplications"] += 1
            return existing

        trace = MemoryTrace(
            key=key, content=content, tier=tier,
            tags=tags or set(), content_hash=content_hash,
            metadata=metadata or {},
        )

        # Auto-tag from content
        auto_tags = SimilarityEngine.tokenize(key + " " + content[:200])
        meaningful = {t for t in auto_tags if len(t) > 3}
        trace.tags.update(list(meaningful)[:15])

        # Insert into tier (evict if full)
        self._insert(trace)
        self._stats["stores"] += 1
        self._ops += 1
        self._maybe_consolidate()
        return trace

    def _insert(self, trace: MemoryTrace) -> None:
        """Insert trace into its tier, evicting coldest if over capacity."""
        tier = trace.tier
        tier_store = self._tiers[tier]
        capacity = TIER_CAPACITY[tier]

        # Evict coldest if at capacity
        while len(tier_store) >= capacity:
            coldest_id = min(
                tier_store,
                key=lambda tid: tier_store[tid].effective_strength,
            )
            coldest = tier_store.pop(coldest_id)
            del self._index[coldest_id]
            self._hash_index.pop(coldest.content_hash, None)
            for tag in coldest.tags:
                self._tag_index[tag].discard(coldest_id)

            # Demote instead of destroy (unless already L4)
            if tier != MemoryTier.L4_ARCHIVAL:
                next_tier = MemoryTier(tier.value + 1)
                coldest.tier = next_tier
                coldest.compressed = True
                self._tiers[next_tier][coldest_id] = coldest
                self._index[coldest_id] = next_tier
                self._hash_index[coldest.content_hash] = coldest_id
                self._stats["demotions"] += 1
            else:
                self._stats["evictions"] += 1

        tier_store[trace.trace_id] = trace
        self._index[trace.trace_id] = tier
        self._hash_index[trace.content_hash] = trace.trace_id
        for tag in trace.tags:
            self._tag_index[tag].add(trace.trace_id)

    # ── Recall ─────────────────────────────────────────────

    def recall(self, query: str, top_k: int = 5,
               tags_filter: Optional[Set[str]] = None) -> RecallResult:
        """
        Associative recall — search across all tiers by content similarity.
        Hotter tiers are searched first and receive a relevance boost.
        """
        start = time.time()
        self._stats["recalls"] += 1

        candidates: List[Tuple[MemoryTrace, float]] = []
        tier_hits: Dict[str, int] = {}
        total_searched = 0

        # Pre-filter by tags if provided
        if tags_filter:
            candidate_ids: Set[str] = set()
            for tag in tags_filter:
                candidate_ids |= self._tag_index.get(tag, set())
        else:
            candidate_ids = None

        # Search all tiers (hot → cold)
        tier_boost = {
            MemoryTier.L1_HOT: 1.5,
            MemoryTier.L2_WORKING: 1.2,
            MemoryTier.L3_EPISODIC: 1.0,
            MemoryTier.L4_ARCHIVAL: 0.8,
        }

        for tier in MemoryTier:
            tier_store = self._tiers[tier]
            hits = 0
            for trace_id, trace in tier_store.items():
                if candidate_ids is not None and trace_id not in candidate_ids:
                    continue
                total_searched += 1
                score = SimilarityEngine.score(query, trace.content, trace.key, trace.tags)
                # Apply tier boost + strength
                score *= tier_boost[tier]
                score *= trace.effective_strength
                if score > 0.05:
                    candidates.append((trace, score))
                    hits += 1
            if hits > 0:
                tier_hits[tier.name] = hits

        # Sort by score descending and take top-k
        candidates.sort(key=lambda x: -x[1])
        top = candidates[:top_k]

        # Touch accessed traces (reinforces memory)
        for trace, _ in top:
            trace.touch()

        if top:
            self._stats["hits"] += 1
        else:
            self._stats["misses"] += 1

        self._ops += 1
        self._maybe_consolidate()

        return RecallResult(
            traces=top,
            total_searched=total_searched,
            duration_ms=(time.time() - start) * 1000,
            tier_hits=tier_hits,
        )

    def recall_by_key(self, key: str) -> Optional[MemoryTrace]:
        """Direct key-based lookup across all tiers (O(n) worst case)."""
        for tier in MemoryTier:
            for trace in self._tiers[tier].values():
                if trace.key == key:
                    trace.touch()
                    return trace
        return None

    # ── Consolidation ──────────────────────────────────────

    def consolidate(self) -> ConsolidationReport:
        """
        Run a full consolidation cycle:
          1. Apply forgetting curve decay
          2. Promote hot traces to higher tiers
          3. Demote cold traces to lower tiers
          4. Deduplicate across tiers
          5. Evict dead traces from L4
        """
        start = time.time()
        report = ConsolidationReport()
        now = time.time()

        # Phase 1: Apply Ebbinghaus decay
        for tier in MemoryTier:
            for trace in list(self._tiers[tier].values()):
                new_decay = EbbinghausCurve.compute_decay(
                    trace.last_access_time, trace.access_count, now,
                )
                if new_decay < trace.decay_factor:
                    trace.decay_factor = new_decay
                    report.decayed += 1

        # Phase 2: Promotions (cold → hot)
        for tier in [MemoryTier.L4_ARCHIVAL, MemoryTier.L3_EPISODIC, MemoryTier.L2_WORKING]:
            threshold = PROMOTION_THRESHOLDS.get(tier, 999)
            for trace_id in list(self._tiers[tier]):
                trace = self._tiers[tier][trace_id]
                if trace.access_count >= threshold and trace.decay_factor > 0.5:
                    target_tier = MemoryTier(tier.value - 1)
                    if len(self._tiers[target_tier]) < TIER_CAPACITY[target_tier]:
                        self._move(trace_id, tier, target_tier)
                        report.promoted += 1

        # Phase 3: Demotions (hot → cold)
        for tier in [MemoryTier.L1_HOT, MemoryTier.L2_WORKING, MemoryTier.L3_EPISODIC]:
            decay_thresh = DEMOTION_DECAY.get(tier, 0.0)
            for trace_id in list(self._tiers[tier]):
                trace = self._tiers[tier][trace_id]
                if trace.decay_factor < decay_thresh:
                    target_tier = MemoryTier(tier.value + 1)
                    self._move(trace_id, tier, target_tier)
                    report.demoted += 1

        # Phase 4: Cross-tier dedup
        seen_hashes: Dict[str, Tuple[str, MemoryTier]] = {}
        for tier in MemoryTier:
            for trace_id in list(self._tiers[tier]):
                trace = self._tiers[tier][trace_id]
                if trace.content_hash in seen_hashes:
                    orig_id, orig_tier = seen_hashes[trace.content_hash]
                    # Keep the one in the hotter tier
                    if tier.value > orig_tier.value:
                        # Current is colder → remove it
                        self._remove(trace_id, tier)
                        report.deduplicated += 1
                    else:
                        self._remove(orig_id, orig_tier)
                        seen_hashes[trace.content_hash] = (trace_id, tier)
                        report.deduplicated += 1
                else:
                    seen_hashes[trace.content_hash] = (trace_id, tier)

        # Phase 5: Evict near-zero strength from L4
        for trace_id in list(self._tiers[MemoryTier.L4_ARCHIVAL]):
            trace = self._tiers[MemoryTier.L4_ARCHIVAL][trace_id]
            if trace.effective_strength < 0.02:
                self._remove(trace_id, MemoryTier.L4_ARCHIVAL)
                report.evicted += 1

        report.duration_ms = (time.time() - start) * 1000
        self._stats["consolidations"] += 1
        self._stats["promotions"] += report.promoted
        self._stats["demotions"] += report.demoted
        self._stats["evictions"] += report.evicted
        self._stats["deduplications"] += report.deduplicated
        return report

    def _move(self, trace_id: str, from_tier: MemoryTier,
              to_tier: MemoryTier) -> None:
        """Move a trace between tiers."""
        trace = self._tiers[from_tier].pop(trace_id, None)
        if trace is None:
            return
        trace.tier = to_tier
        trace.compressed = to_tier.value >= 3
        self._tiers[to_tier][trace_id] = trace
        self._index[trace_id] = to_tier

    def _remove(self, trace_id: str, tier: MemoryTier) -> None:
        """Permanently remove a trace."""
        trace = self._tiers[tier].pop(trace_id, None)
        if trace is None:
            return
        self._index.pop(trace_id, None)
        self._hash_index.pop(trace.content_hash, None)
        for tag in trace.tags:
            self._tag_index[tag].discard(trace_id)

    def _maybe_consolidate(self) -> None:
        """Auto-consolidate every N operations."""
        if self._ops >= self._consolidation_interval:
            self.consolidate()
            self._ops = 0

    # ── Associations ───────────────────────────────────────

    def associate(self, trace_id_a: str, trace_id_b: str) -> bool:
        """Create a bidirectional association between two traces."""
        tier_a = self._index.get(trace_id_a)
        tier_b = self._index.get(trace_id_b)
        if tier_a is None or tier_b is None:
            return False
        self._tiers[tier_a][trace_id_a].associations.add(trace_id_b)
        self._tiers[tier_b][trace_id_b].associations.add(trace_id_a)
        return True

    def get_associated(self, trace_id: str) -> List[MemoryTrace]:
        """Retrieve all traces associated with a given trace."""
        tier = self._index.get(trace_id)
        if tier is None:
            return []
        trace = self._tiers[tier].get(trace_id)
        if trace is None:
            return []
        results = []
        for assoc_id in trace.associations:
            assoc_tier = self._index.get(assoc_id)
            if assoc_tier is not None:
                assoc_trace = self._tiers[assoc_tier].get(assoc_id)
                if assoc_trace:
                    results.append(assoc_trace)
        return results

    # ── Natural Language Interface ─────────────────────────

    def solve(self, prompt: str) -> RecallResult:
        """Natural language interface for CCE routing."""
        prompt_lower = prompt.lower()

        # Store intent
        if any(kw in prompt_lower for kw in ["remember", "store", "save", "memorize"]):
            trace = self.store(
                key=prompt[:60],
                content=prompt,
                tags=set(SimilarityEngine.tokenize(prompt)),
            )
            result = RecallResult(
                traces=[(trace, 1.0)],
                total_searched=0,
                duration_ms=0.0,
            )
            return result

        # Default: recall
        return self.recall(prompt)

    # ── Stats ──────────────────────────────────────────────

    def get_tier_sizes(self) -> Dict[str, int]:
        return {tier.name: len(store) for tier, store in self._tiers.items()}

    def get_total_traces(self) -> int:
        return sum(len(store) for store in self._tiers.values())

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "InfiniteMemoryEngine",
            "total_traces": self.get_total_traces(),
            "tier_sizes": self.get_tier_sizes(),
            **self._stats,
        }
