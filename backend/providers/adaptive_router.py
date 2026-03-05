"""
Adaptive Model Router — Smart Query Routing
════════════════════════════════════════════
Instead of always querying all 5 models (expensive), classifies
query complexity and routes to the optimal number of models.

  Easy query   → 1 fast model (Llama/Mistral)     ~$0.001
  Medium query → 2 models (+ GPT-4o)               ~$0.01
  Hard query   → 5 models (full consensus)         ~$0.05

Cuts API costs by ~80% on average workloads.
"""

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from providers.multi_llm_client import BaseProvider, ProviderID

logger = logging.getLogger(__name__)


class QueryComplexity(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class RoutingDecision:
    """Result of the adaptive routing decision."""
    complexity: QueryComplexity
    selected_providers: List[str]
    reason: str
    estimated_cost_usd: float = 0.0


# Complexity heuristics
_HARD_KEYWORDS = [
    "compare", "analyze", "architect", "design", "implement",
    "debug", "optimize", "security", "vulnerability", "proof",
    "algorithm", "distributed", "consensus", "blockchain",
    "machine learning", "neural", "train", "fine-tune",
]
_MEDIUM_KEYWORDS = [
    "explain", "how does", "write code", "function", "class",
    "api", "endpoint", "database", "query", "test",
    "refactor", "review", "best practice",
]


class AdaptiveRouter:
    """
    Classifies query complexity and selects the optimal provider set.
    """
    
    def __init__(
        self,
        providers: List[BaseProvider] = None,
        easy_budget: int = 1,
        medium_budget: int = 2,
        hard_budget: int = 5,
    ):
        self.easy_budget = easy_budget
        self.medium_budget = medium_budget
        self.hard_budget = hard_budget
        
        # Provider tiers (cheapest first)
        self._budget_tier = [ProviderID.LLAMA_3.value, ProviderID.MISTRAL.value]
        self._mid_tier = [ProviderID.GPT4O.value, ProviderID.GEMINI_1_5.value]
        self._premium_tier = [ProviderID.CLAUDE_3_5.value]
        
        # Stats
        self._routing_history: List[RoutingDecision] = []
    
    def classify_complexity(self, query: str) -> QueryComplexity:
        """Classify query complexity based on heuristics."""
        q = query.lower()
        word_count = len(q.split())
        
        # Length-based heuristic
        if word_count > 100:
            return QueryComplexity.HARD
        
        # Keyword-based
        hard_hits = sum(1 for kw in _HARD_KEYWORDS if kw in q)
        medium_hits = sum(1 for kw in _MEDIUM_KEYWORDS if kw in q)
        
        if hard_hits >= 2 or (hard_hits >= 1 and word_count > 50):
            return QueryComplexity.HARD
        elif medium_hits >= 1 or word_count > 30:
            return QueryComplexity.MEDIUM
        
        # Code detection
        if "```" in query or "def " in query or "class " in query:
            return QueryComplexity.MEDIUM
        
        return QueryComplexity.EASY
    
    def route(self, query: str) -> RoutingDecision:
        """Route a query to the optimal provider set."""
        complexity = self.classify_complexity(query)
        
        if complexity == QueryComplexity.EASY:
            providers = self._budget_tier[:self.easy_budget]
            cost = 0.001
            reason = "Simple query → 1 fast model"
        elif complexity == QueryComplexity.MEDIUM:
            providers = (self._budget_tier[:1] + self._mid_tier[:1])[:self.medium_budget]
            cost = 0.01
            reason = "Medium complexity → 2 models"
        else:  # HARD
            providers = self._budget_tier + self._mid_tier + self._premium_tier
            providers = providers[:self.hard_budget]
            cost = 0.05
            reason = "Complex query → full consensus (5 models)"
        
        decision = RoutingDecision(
            complexity=complexity,
            selected_providers=providers,
            reason=reason,
            estimated_cost_usd=cost,
        )
        
        self._routing_history.append(decision)
        return decision
    
    def get_stats(self):
        total = len(self._routing_history)
        if total == 0:
            return {"total_routed": 0}
        
        by_complexity = {}
        total_cost = 0.0
        for d in self._routing_history:
            by_complexity[d.complexity.value] = by_complexity.get(d.complexity.value, 0) + 1
            total_cost += d.estimated_cost_usd
        
        return {
            "total_routed": total,
            "by_complexity": by_complexity,
            "estimated_total_cost_usd": round(total_cost, 4),
            "avg_cost_per_query": round(total_cost / total, 4),
        }
