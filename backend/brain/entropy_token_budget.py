"""
Entropy-Aware Token Budgeting — Dynamic Cost Optimization
═════════════════════════════════════════════════════════
Dynamically allocates token budgets based on the Shannon entropy
of the conversation. High-entropy conversations (novel topics, creative
tasks) get generous token budgets. Low-entropy conversations (repetitive
queries, simple lookups) get compressed budgets.

Self-optimizes cost-per-query in real-time without sacrificing quality.

Architecture:
  Conversation → Entropy Calculator → Budget Allocator → Token Limit
                      ↓                      ↓
              H(X) = -Σ p log₂(p)    Budget = f(entropy)
"""

import math
import logging
import re
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class EntropyAnalysis:
    """Result of entropy analysis for a text or conversation."""
    character_entropy: float = 0.0       # Shannon entropy of characters
    word_entropy: float = 0.0            # Shannon entropy of words
    vocabulary_richness: float = 0.0     # Unique words / total words
    novelty_score: float = 0.0           # How novel vs. previous messages
    combined_entropy: float = 0.0        # Weighted combination
    token_count: int = 0


@dataclass
class BudgetAllocation:
    """Token budget allocation for a request."""
    base_budget: int = 2000
    adjusted_budget: int = 2000
    entropy_multiplier: float = 1.0
    reason: str = ""
    savings_vs_max: float = 0.0


@dataclass
class BudgetStats:
    """Cumulative statistics for token budget optimization."""
    total_requests: int = 0
    total_tokens_allocated: int = 0
    total_tokens_max_possible: int = 0
    average_entropy: float = 0.0
    average_multiplier: float = 1.0
    total_savings_pct: float = 0.0


# ──────────────────────────────────────────────
# Shannon Entropy Calculator
# ──────────────────────────────────────────────

class ShannonEntropyCalculator:
    """
    Calculates Shannon entropy at multiple granularities:
    character-level, word-level, and vocabulary richness.
    """

    @staticmethod
    def character_entropy(text: str) -> float:
        """Calculate character-level Shannon entropy: H = -Σ p(c) log₂ p(c)."""
        if not text:
            return 0.0

        freq = Counter(text)
        total = len(text)
        entropy = 0.0

        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    @staticmethod
    def word_entropy(text: str) -> float:
        """Calculate word-level Shannon entropy."""
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return 0.0

        freq = Counter(words)
        total = len(words)
        entropy = 0.0

        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    @staticmethod
    def vocabulary_richness(text: str) -> float:
        """Ratio of unique words to total words (type-token ratio)."""
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return 0.0
        return len(set(words)) / len(words)

    def analyze(self, text: str, history: Optional[List[str]] = None) -> EntropyAnalysis:
        """Full entropy analysis of text with optional conversation history."""
        char_ent = self.character_entropy(text)
        word_ent = self.word_entropy(text)
        vocab_rich = self.vocabulary_richness(text)

        # Calculate novelty relative to history
        novelty = 1.0
        if history:
            history_text = " ".join(history[-5:])  # Last 5 messages
            history_words = set(re.findall(r'\b\w+\b', history_text.lower()))
            current_words = set(re.findall(r'\b\w+\b', text.lower()))

            if current_words:
                new_words = current_words - history_words
                novelty = len(new_words) / len(current_words)

        # Combined entropy (weighted average)
        combined = (
            0.2 * (char_ent / 5.0)      # Normalize char entropy (~0-5 bits)
            + 0.4 * (word_ent / 10.0)    # Normalize word entropy (~0-10 bits)
            + 0.2 * vocab_rich
            + 0.2 * novelty
        )

        tokens = max(1, len(text) // 4)

        return EntropyAnalysis(
            character_entropy=round(char_ent, 4),
            word_entropy=round(word_ent, 4),
            vocabulary_richness=round(vocab_rich, 4),
            novelty_score=round(novelty, 4),
            combined_entropy=round(min(1.0, combined), 4),
            token_count=tokens,
        )


# ──────────────────────────────────────────────
# Budget Allocator
# ──────────────────────────────────────────────

class BudgetAllocator:
    """
    Allocates token budgets dynamically based on entropy analysis.

    Budget curve:
        Low entropy (< 0.3):  budget = base × 0.4  (compressed)
        Medium (0.3 - 0.7):   budget = base × 0.7  (standard)
        High entropy (> 0.7): budget = base × 1.2  (generous)
        Max entropy (> 0.9):  budget = base × 1.5  (maximum)
    """

    def __init__(
        self,
        base_budget: int = 2000,
        min_budget: int = 256,
        max_budget: int = 8000,
    ):
        self.base_budget = base_budget
        self.min_budget = min_budget
        self.max_budget = max_budget

    def allocate(self, analysis: EntropyAnalysis) -> BudgetAllocation:
        """Allocate token budget based on entropy analysis."""
        entropy = analysis.combined_entropy

        # Smooth piecewise multiplier
        if entropy < 0.15:
            multiplier = 0.3
            reason = "Very low entropy (repetitive/simple)"
        elif entropy < 0.3:
            multiplier = 0.5
            reason = "Low entropy (familiar topic)"
        elif entropy < 0.5:
            multiplier = 0.7
            reason = "Medium entropy (standard)"
        elif entropy < 0.7:
            multiplier = 1.0
            reason = "High entropy (novel topic)"
        elif entropy < 0.9:
            multiplier = 1.3
            reason = "Very high entropy (creative/complex)"
        else:
            multiplier = 1.5
            reason = "Maximum entropy (highly novel/unpredictable)"

        adjusted = int(self.base_budget * multiplier)
        adjusted = max(self.min_budget, min(self.max_budget, adjusted))

        savings = 1.0 - (adjusted / self.max_budget)

        return BudgetAllocation(
            base_budget=self.base_budget,
            adjusted_budget=adjusted,
            entropy_multiplier=round(multiplier, 3),
            reason=reason,
            savings_vs_max=round(savings, 3),
        )


# ──────────────────────────────────────────────
# Entropy Token Budget Engine (Main Interface)
# ──────────────────────────────────────────────

class EntropyTokenBudgetEngine:
    """
    Self-optimizing token budget system.

    Usage:
        engine = EntropyTokenBudgetEngine(base_budget=2000)

        budget = engine.get_budget("What is Python?")
        # Low entropy → budget = ~1000 tokens

        budget = engine.get_budget(
            "Design a novel quantum-resistant encryption scheme using lattice-based"
            " cryptography combined with homomorphic evaluation circuits"
        )
        # High entropy → budget = ~3000 tokens
    """

    def __init__(
        self,
        base_budget: int = 2000,
        min_budget: int = 256,
        max_budget: int = 8000,
    ):
        self._calculator = ShannonEntropyCalculator()
        self._allocator = BudgetAllocator(base_budget, min_budget, max_budget)
        self._conversation_history: List[str] = []
        self._budget_history: deque = deque(maxlen=200)
        self._total_allocated: int = 0
        self._total_max_possible: int = 0

    def get_budget(self, text: str) -> BudgetAllocation:
        """
        Analyze text entropy and return optimized token budget.
        """
        analysis = self._calculator.analyze(
            text,
            history=self._conversation_history,
        )

        allocation = self._allocator.allocate(analysis)

        # Track history
        self._conversation_history.append(text)
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]

        self._budget_history.append(allocation)
        self._total_allocated += allocation.adjusted_budget
        self._total_max_possible += self._allocator.max_budget

        logger.debug(
            f"Entropy budget: H={analysis.combined_entropy:.3f} → "
            f"{allocation.adjusted_budget} tokens ({allocation.reason})"
        )

        self._try_record_metrics(analysis, allocation)
        return allocation

    def analyze_entropy(self, text: str) -> EntropyAnalysis:
        """Analyze entropy without allocating a budget."""
        return self._calculator.analyze(
            text,
            history=self._conversation_history,
        )

    def get_stats(self) -> BudgetStats:
        multipliers = [b.entropy_multiplier for b in self._budget_history]
        entropies = []
        for text in self._conversation_history:
            a = self._calculator.analyze(text)
            entropies.append(a.combined_entropy)

        return BudgetStats(
            total_requests=len(self._budget_history),
            total_tokens_allocated=self._total_allocated,
            total_tokens_max_possible=self._total_max_possible,
            average_entropy=(
                sum(entropies) / len(entropies) if entropies else 0.0
            ),
            average_multiplier=(
                sum(multipliers) / len(multipliers) if multipliers else 1.0
            ),
            total_savings_pct=(
                round(
                    1.0 - self._total_allocated / max(self._total_max_possible, 1),
                    3,
                )
            ),
        )

    def _try_record_metrics(
        self,
        analysis: EntropyAnalysis,
        allocation: BudgetAllocation,
    ) -> None:
        try:
            from telemetry.metrics import MetricsCollector
            mc = MetricsCollector.get_instance()
            mc.histogram("brain.entropy.combined", analysis.combined_entropy)
            mc.histogram("brain.entropy.budget", allocation.adjusted_budget)
            mc.histogram("brain.entropy.multiplier", allocation.entropy_multiplier)
        except Exception:
            pass
