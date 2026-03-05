"""
Temporal Memory Decay with Resurrection — Tiered Memory System
───────────────────────────────────────────────────────────────
Memories decay over time but can be resurrected when relevant.
HOT → WARM → COLD → FROZEN, with importance-weighted half-life.
"""

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class MemoryTier(Enum):
    HOT = 4       # Recent, always in context
    WARM = 3      # Days old, loaded on demand
    COLD = 2      # Weeks old, compressed
    FROZEN = 1    # Months old, archived
    EVICTED = 0   # Removed


@dataclass
class TemporalMemoryItem:
    """A memory item with temporal metadata."""
    memory_id: str = ""
    content: str = ""
    compressed_content: str = ""
    tier: MemoryTier = MemoryTier.HOT
    importance: float = 0.5
    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    decay_rate: float = 1.0
    resurrection_count: int = 0
    domain: str = "general"
    tags: Set[str] = field(default_factory=set)

    def __post_init__(self):
        if not self.memory_id:
            self.memory_id = hashlib.sha256(
                f"{self.content[:50]}{time.time()}".encode()
            ).hexdigest()[:12]
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.last_accessed:
            self.last_accessed = now

    @property
    def age_hours(self) -> float:
        return (time.time() - self.created_at) / 3600

    @property
    def staleness_hours(self) -> float:
        return (time.time() - self.last_accessed) / 3600

    @property
    def effective_strength(self) -> float:
        """Current memory strength after decay."""
        half_life_hours = 24.0 / self.decay_rate * (1 + self.importance * 3)
        staleness = self.staleness_hours
        import math
        return self.importance * math.exp(-0.693 * staleness / max(half_life_hours, 1))


# ──────────────────────────────────────────────
# Decay Function
# ──────────────────────────────────────────────

class DecayFunction:
    """Exponential decay with importance-weighted half-life."""

    # Tier thresholds (effective_strength)
    TIER_THRESHOLDS = {
        MemoryTier.HOT: 0.6,
        MemoryTier.WARM: 0.3,
        MemoryTier.COLD: 0.1,
        MemoryTier.FROZEN: 0.02,
    }

    @staticmethod
    def compute_tier(item: TemporalMemoryItem) -> MemoryTier:
        """Compute which tier this memory should be in."""
        strength = item.effective_strength

        if strength >= DecayFunction.TIER_THRESHOLDS[MemoryTier.HOT]:
            return MemoryTier.HOT
        elif strength >= DecayFunction.TIER_THRESHOLDS[MemoryTier.WARM]:
            return MemoryTier.WARM
        elif strength >= DecayFunction.TIER_THRESHOLDS[MemoryTier.COLD]:
            return MemoryTier.COLD
        elif strength >= DecayFunction.TIER_THRESHOLDS[MemoryTier.FROZEN]:
            return MemoryTier.FROZEN
        else:
            return MemoryTier.EVICTED


# ──────────────────────────────────────────────
# Resurrection Trigger
# ──────────────────────────────────────────────

class ResurrectionTrigger:
    """Detects when a cold/frozen memory is relevant and resurrects it."""

    def __init__(self, similarity_threshold: float = 0.3):
        self._threshold = similarity_threshold

    def check_relevance(self, memory: TemporalMemoryItem,
                        context: str) -> float:
        """Check how relevant a memory is to the current context."""
        context_words = set(context.lower().split())
        content = memory.content if memory.tier.value >= MemoryTier.WARM.value else memory.compressed_content
        memory_words = set(content.lower().split())

        if not context_words or not memory_words:
            return 0.0

        # Jaccard similarity
        intersection = context_words & memory_words
        union = context_words | memory_words
        jaccard = len(intersection) / max(len(union), 1)

        # Tag matching bonus
        context_tags = context_words & memory.tags
        tag_bonus = len(context_tags) * 0.1

        # Domain match bonus
        domain_bonus = 0.1 if memory.domain and memory.domain in context.lower() else 0.0

        return min(1.0, jaccard + tag_bonus + domain_bonus)

    def should_resurrect(self, memory: TemporalMemoryItem,
                         context: str) -> bool:
        """Check if a memory should be resurrected."""
        if memory.tier.value >= MemoryTier.WARM.value:
            return False  # Already warm or hot
        relevance = self.check_relevance(memory, context)
        return relevance >= self._threshold


# ──────────────────────────────────────────────
# Content Compressor
# ──────────────────────────────────────────────

class MemoryCompressor:
    """Compresses memory content for cold/frozen tiers."""

    @staticmethod
    def compress(content: str, ratio: float = 0.3) -> str:
        """Compress content to a fraction of original size."""
        if not content:
            return content

        lines = content.split('\n')
        if len(lines) <= 3:
            return content

        # Keep first line (usually topic) + key lines
        target_lines = max(2, int(len(lines) * ratio))
        kept = [lines[0]]  # First line always

        # Score remaining lines by information density
        scored = []
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped:
                continue
            # Higher score for lines with: numbers, code, key terms
            score = len(stripped)
            if any(c.isdigit() for c in stripped):
                score *= 1.5
            if ':' in stripped or '=' in stripped:
                score *= 1.3
            scored.append((score, stripped))

        scored.sort(key=lambda x: x[0], reverse=True)
        for _, line in scored[:target_lines - 1]:
            kept.append(line)

        return '\n'.join(kept)


# ──────────────────────────────────────────────
# Temporal Memory Manager (Main Interface)
# ──────────────────────────────────────────────

class TemporalMemoryManager:
    """
    Manages tiered memory with decay and resurrection.

    Usage:
        mem = TemporalMemoryManager()

        # Store a memory
        mem.store("Python uses indentation for blocks", importance=0.7,
                  domain="python", tags={"syntax", "python"})

        # Retrieve HOT memories for context
        hot = mem.get_active_context()

        # Check for resurrections given current context
        resurrected = mem.check_resurrections("How does Python indentation work?")

        # Run periodic maintenance
        mem.run_maintenance()
    """

    def __init__(self, max_memories: int = 2000, gc_interval_seconds: float = 300):
        self._memories: Dict[str, TemporalMemoryItem] = {}
        self._tiers: Dict[MemoryTier, Set[str]] = defaultdict(set)
        self._max_memories = max_memories
        self._gc_interval = gc_interval_seconds
        self._last_gc = time.time()
        self._resurrection_trigger = ResurrectionTrigger()
        self._compressor = MemoryCompressor()
        self._total_resurrections = 0
        self._total_evictions = 0

    def store(self, content: str, importance: float = 0.5,
              domain: str = "general", tags: Set[str] = None,
              decay_rate: float = 1.0) -> str:
        """Store a new memory."""
        item = TemporalMemoryItem(
            content=content,
            compressed_content=self._compressor.compress(content),
            importance=max(0.0, min(1.0, importance)),
            domain=domain,
            tags=tags or set(),
            decay_rate=decay_rate,
        )

        self._memories[item.memory_id] = item
        self._tiers[MemoryTier.HOT].add(item.memory_id)

        # Auto-maintenance if needed
        if len(self._memories) > self._max_memories:
            self._evict_weakest()

        return item.memory_id

    def access(self, memory_id: str) -> Optional[TemporalMemoryItem]:
        """Access a memory, boosting its strength."""
        item = self._memories.get(memory_id)
        if item:
            item.last_accessed = time.time()
            item.access_count += 1
            # Accessing resets decay — move to HOT
            old_tier = item.tier
            item.tier = MemoryTier.HOT
            if old_tier != MemoryTier.HOT:
                self._tiers[old_tier].discard(memory_id)
                self._tiers[MemoryTier.HOT].add(memory_id)
        return item

    def get_active_context(self, max_items: int = 10) -> List[TemporalMemoryItem]:
        """Get HOT memories for inclusion in context."""
        hot_ids = self._tiers.get(MemoryTier.HOT, set())
        hot_items = [self._memories[mid] for mid in hot_ids if mid in self._memories]
        hot_items.sort(key=lambda m: m.effective_strength, reverse=True)
        return hot_items[:max_items]

    def check_resurrections(self, context: str) -> List[TemporalMemoryItem]:
        """Check if any cold/frozen memories should be resurrected."""
        resurrected = []

        for tier in [MemoryTier.COLD, MemoryTier.FROZEN]:
            for mid in list(self._tiers.get(tier, set())):
                item = self._memories.get(mid)
                if not item:
                    continue

                if self._resurrection_trigger.should_resurrect(item, context):
                    # Resurrect!
                    old_tier = item.tier
                    item.tier = MemoryTier.HOT
                    item.last_accessed = time.time()
                    item.resurrection_count += 1
                    self._tiers[old_tier].discard(mid)
                    self._tiers[MemoryTier.HOT].add(mid)
                    resurrected.append(item)
                    self._total_resurrections += 1

                    logger.info(
                        f"⏱️ Resurrected memory '{mid}' from {old_tier.name} "
                        f"(resurrection #{item.resurrection_count})"
                    )

        return resurrected

    def run_maintenance(self):
        """Run periodic tier transitions and garbage collection."""
        now = time.time()
        if now - self._last_gc < self._gc_interval:
            return
        self._last_gc = now

        transitions = 0
        for mid, item in list(self._memories.items()):
            new_tier = DecayFunction.compute_tier(item)

            if new_tier == MemoryTier.EVICTED:
                self._tiers[item.tier].discard(mid)
                del self._memories[mid]
                self._total_evictions += 1
                transitions += 1
            elif new_tier != item.tier:
                self._tiers[item.tier].discard(mid)
                item.tier = new_tier
                self._tiers[new_tier].add(mid)
                transitions += 1

                # Compress when moving to COLD
                if new_tier == MemoryTier.COLD and not item.compressed_content:
                    item.compressed_content = self._compressor.compress(item.content, 0.3)

        if transitions > 0:
            logger.debug(f"⏱️ Memory maintenance: {transitions} tier transitions")

    def _evict_weakest(self, count: int = 50):
        """Evict the weakest memories to stay within limits."""
        all_items = sorted(self._memories.values(), key=lambda m: m.effective_strength)
        for item in all_items[:count]:
            self._tiers[item.tier].discard(item.memory_id)
            del self._memories[item.memory_id]
            self._total_evictions += 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_memories": len(self._memories),
            "tier_distribution": {
                tier.name: len(ids) for tier, ids in self._tiers.items()
            },
            "total_resurrections": self._total_resurrections,
            "total_evictions": self._total_evictions,
            "hot_count": len(self._tiers.get(MemoryTier.HOT, set())),
            "warm_count": len(self._tiers.get(MemoryTier.WARM, set())),
            "cold_count": len(self._tiers.get(MemoryTier.COLD, set())),
            "frozen_count": len(self._tiers.get(MemoryTier.FROZEN, set())),
        }
