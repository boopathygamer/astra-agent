"""
Adaptive Token Budget Manager — Intelligent Token Allocation
═══════════════════════════════════════════════════════════
Dynamically allocates tokens based on query complexity,
tracks cost-to-quality ratio, and optimizes spending.

Capabilities:
  1. Complexity Estimation — Rate query difficulty 1-10
  2. Budget Allocation     — More tokens for harder queries
  3. Cost Tracking         — Monitor token consumption
  4. Quality-Cost Ratio    — Optimize for best quality per token
  5. Historical Learning   — Adjust budgets based on past results
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ComplexityTier(Enum):
    TRIVIAL = 1
    SIMPLE = 2
    MODERATE = 3
    COMPLEX = 4
    EXPERT = 5


@dataclass
class TokenAllocation:
    """Token budget allocation for a request."""
    input_budget: int = 2000
    output_budget: int = 1000
    context_budget: int = 3000
    tier: ComplexityTier = ComplexityTier.MODERATE
    reasoning: str = ""

    @property
    def total_budget(self) -> int:
        return self.input_budget + self.output_budget + self.context_budget


@dataclass
class TokenUsage:
    """Actual token usage for a request."""
    input_tokens: int = 0
    output_tokens: int = 0
    context_tokens: int = 0
    quality_score: float = 0.0
    latency_ms: float = 0.0
    tier: ComplexityTier = ComplexityTier.MODERATE

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.context_tokens

    @property
    def efficiency(self) -> float:
        """Quality per 1000 tokens."""
        return (self.quality_score / max(self.total_tokens, 1)) * 1000


class TokenBudgetManager:
    """
    Manages adaptive token allocation with complexity-based
    budgets and historical optimization.
    """

    # Base token budgets per tier
    TIER_BUDGETS = {
        ComplexityTier.TRIVIAL: {"input": 500, "output": 200, "context": 500},
        ComplexityTier.SIMPLE: {"input": 1000, "output": 500, "context": 1500},
        ComplexityTier.MODERATE: {"input": 2000, "output": 1000, "context": 3000},
        ComplexityTier.COMPLEX: {"input": 3000, "output": 2000, "context": 4000},
        ComplexityTier.EXPERT: {"input": 4000, "output": 3000, "context": 6000},
    }

    def __init__(self):
        self._usage_history: deque = deque(maxlen=500)
        self._tier_stats: Dict[str, Dict] = {
            t.name: {"count": 0, "avg_quality": 0.5, "avg_tokens": 0}
            for t in ComplexityTier
        }
        self._total_tokens = 0
        self._total_requests = 0
        logger.info("[TOKEN-BUDGET] Manager initialized")

    def allocate(self, query: str, domain: str = "general") -> TokenAllocation:
        """Allocate token budget based on query complexity."""
        tier = self._estimate_complexity(query, domain)
        budgets = self.TIER_BUDGETS[tier]

        # Adjust based on historical performance
        adjustment = self._get_historical_adjustment(tier)

        allocation = TokenAllocation(
            input_budget=int(budgets["input"] * adjustment),
            output_budget=int(budgets["output"] * adjustment),
            context_budget=int(budgets["context"] * adjustment),
            tier=tier,
            reasoning=f"Tier={tier.name}, domain={domain}, adj={adjustment:.2f}",
        )

        logger.debug(
            f"[TOKEN-BUDGET] Allocated: {allocation.total_budget} tokens "
            f"(tier={tier.name}, domain={domain})"
        )
        return allocation

    def record_usage(self, usage: TokenUsage):
        """Record actual token usage for learning."""
        self._usage_history.append(usage)
        self._total_tokens += usage.total_tokens
        self._total_requests += 1

        # Update tier stats
        stats = self._tier_stats[usage.tier.name]
        stats["count"] += 1
        n = stats["count"]
        stats["avg_quality"] = (
            (stats["avg_quality"] * (n - 1) + usage.quality_score) / n
        )
        stats["avg_tokens"] = (
            (stats["avg_tokens"] * (n - 1) + usage.total_tokens) / n
        )

    def _estimate_complexity(self, query: str, domain: str) -> ComplexityTier:
        """Estimate query complexity tier."""
        words = query.split()
        word_count = len(words)
        query_lower = query.lower()

        score = 0

        # Word count factor
        if word_count <= 5:
            score += 1
        elif word_count <= 15:
            score += 2
        elif word_count <= 30:
            score += 3
        elif word_count <= 60:
            score += 4
        else:
            score += 5

        # Complexity keywords
        complex_words = {
            "algorithm": 2, "implement": 2, "architecture": 2,
            "optimize": 2, "refactor": 2, "debug": 1, "analyze": 2,
            "compare": 1, "explain": 1, "design": 2, "build": 2,
            "comprehensive": 2, "detailed": 1, "step by step": 2,
            "multiple": 1, "system": 1, "integration": 2,
        }
        for word, weight in complex_words.items():
            if word in query_lower:
                score += weight

        # Domain factor
        domain_weights = {
            "code": 1, "debug": 2, "build": 2, "general": 0,
            "creative": 1, "math": 2, "research": 2,
        }
        score += domain_weights.get(domain, 0)

        # Clamp to tiers
        if score <= 3:
            return ComplexityTier.TRIVIAL
        elif score <= 5:
            return ComplexityTier.SIMPLE
        elif score <= 8:
            return ComplexityTier.MODERATE
        elif score <= 12:
            return ComplexityTier.COMPLEX
        else:
            return ComplexityTier.EXPERT

    def _get_historical_adjustment(self, tier: ComplexityTier) -> float:
        """Get budget adjustment based on historical quality data."""
        stats = self._tier_stats[tier.name]
        if stats["count"] < 5:
            return 1.0  # Not enough data

        avg_quality = stats["avg_quality"]
        if avg_quality < 0.4:
            return 1.3  # Need more tokens for low quality
        elif avg_quality > 0.8:
            return 0.85  # Can save tokens for high quality
        return 1.0

    def get_recommendations(self) -> List[str]:
        """Get token budget optimization recommendations."""
        recs = []
        for tier_name, stats in self._tier_stats.items():
            if stats["count"] >= 10:
                if stats["avg_quality"] < 0.5:
                    recs.append(
                        f"Tier {tier_name}: Low quality ({stats['avg_quality']:.2f}) — "
                        f"consider increasing token budget"
                    )
                elif stats["avg_quality"] > 0.85 and stats["avg_tokens"] > 3000:
                    recs.append(
                        f"Tier {tier_name}: High quality with high tokens — "
                        f"can reduce budget to save costs"
                    )
        return recs

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_tokens_used": self._total_tokens,
            "total_requests": self._total_requests,
            "avg_tokens_per_request": (
                self._total_tokens / max(self._total_requests, 1)
            ),
            "tier_stats": {
                k: {
                    "count": v["count"],
                    "avg_quality": round(v["avg_quality"], 2),
                    "avg_tokens": round(v["avg_tokens"]),
                }
                for k, v in self._tier_stats.items()
            },
            "recommendations": self.get_recommendations(),
        }
