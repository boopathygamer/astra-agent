"""
Speculative Parallel Branching — Multi-Strategy Cognitive Racing
════════════════════════════════════════════════════════════════
Instead of sequential hypothesis → verify → retry, SPB speculatively
branches 3-5 parallel reasoning paths using different cognitive strategies
(deductive, inductive, analogical, adversarial, abductive). The Confidence
Oracle picks the winner and discards the rest.

Resolves thinking loops in 1 cycle instead of 5 retries.

Architecture:
  Problem → Fork N Branches → Race (parallel) → Oracle selects winner
               ↓                     ↓
        Strategy assigned       Best confidence wins
"""

import hashlib
import logging
import secrets
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class CognitiveStrategy(Enum):
    """Distinct reasoning strategies for parallel branching."""
    DEDUCTIVE = "deductive"          # General rules → specific conclusion
    INDUCTIVE = "inductive"          # Specific observations → general pattern
    ANALOGICAL = "analogical"        # Similar problem → mapped solution
    ADVERSARIAL = "adversarial"      # Assume wrong → disprove → find truth
    ABDUCTIVE = "abductive"          # Best explanation for observations


@dataclass
class BranchResult:
    """Result from a single speculative reasoning branch."""
    branch_id: str = ""
    strategy: CognitiveStrategy = CognitiveStrategy.DEDUCTIVE
    output: str = ""
    confidence: float = 0.0
    reasoning_trace: str = ""
    duration_ms: float = 0.0
    was_winner: bool = False
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None and len(self.output) > 0


@dataclass
class SpeculativeResult:
    """Aggregated result of speculative parallel branching."""
    problem: str = ""
    winner: Optional[BranchResult] = None
    branches: List[BranchResult] = field(default_factory=list)
    total_branches: int = 0
    total_duration_ms: float = 0.0
    speedup_vs_sequential: float = 1.0
    strategy_scores: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        winner_name = self.winner.strategy.value if self.winner else "none"
        valid = sum(1 for b in self.branches if b.is_valid)
        return (
            f"SPB: {self.total_branches} branches, {valid} valid | "
            f"Winner={winner_name} "
            f"(conf={self.winner.confidence:.3f}) | "
            f"Speedup={self.speedup_vs_sequential:.1f}x | "
            f"{self.total_duration_ms:.0f}ms"
        )


# ──────────────────────────────────────────────
# Strategy Prompt Templates
# ──────────────────────────────────────────────

STRATEGY_PROMPTS: Dict[CognitiveStrategy, str] = {
    CognitiveStrategy.DEDUCTIVE: (
        "Using DEDUCTIVE reasoning: Start from established general principles "
        "and rules, then logically derive the specific answer. "
        "Apply formal logic: if P then Q, P is true, therefore Q.\n\n"
    ),
    CognitiveStrategy.INDUCTIVE: (
        "Using INDUCTIVE reasoning: Examine specific examples, patterns, "
        "and observations in the problem, then generalize to form a "
        "broader conclusion. Build your answer from evidence upward.\n\n"
    ),
    CognitiveStrategy.ANALOGICAL: (
        "Using ANALOGICAL reasoning: Find a similar, well-understood problem "
        "from a different domain. Map the structure of the known solution "
        "onto this problem. Explicitly state the analogy.\n\n"
    ),
    CognitiveStrategy.ADVERSARIAL: (
        "Using ADVERSARIAL reasoning: Assume the most obvious answer is WRONG. "
        "Try to disprove it. If you cannot disprove it, it is likely correct. "
        "If you can disprove it, find what IS correct by elimination.\n\n"
    ),
    CognitiveStrategy.ABDUCTIVE: (
        "Using ABDUCTIVE reasoning: Given the observations in this problem, "
        "what is the BEST possible explanation? Consider multiple hypotheses, "
        "then select the one that explains the most with the fewest assumptions.\n\n"
    ),
}


# ──────────────────────────────────────────────
# Branch Executor
# ──────────────────────────────────────────────

class BranchExecutor:
    """
    Executes a single reasoning branch using a specific cognitive strategy.
    Wraps the generate_fn with strategy-specific prompt augmentation.
    """

    def execute(
        self,
        branch_id: str,
        problem: str,
        strategy: CognitiveStrategy,
        generate_fn: Callable[[str], str],
        context: str = "",
    ) -> BranchResult:
        """Execute a single speculative branch."""
        start = time.perf_counter()
        result = BranchResult(branch_id=branch_id, strategy=strategy)

        try:
            prompt = STRATEGY_PROMPTS[strategy]
            full_prompt = f"{prompt}Context:\n{context}\n\nProblem:\n{problem}"
            output = generate_fn(full_prompt)
            result.output = output if isinstance(output, str) else str(output)
            result.reasoning_trace = f"[{strategy.value}] → {result.output[:200]}"

            # Heuristic confidence from output quality
            result.confidence = self._estimate_confidence(result.output, strategy)

        except Exception as e:
            result.error = str(e)
            logger.warning(f"Branch {branch_id} ({strategy.value}) failed: {e}")

        result.duration_ms = (time.perf_counter() - start) * 1000
        return result

    def _estimate_confidence(self, output: str, strategy: CognitiveStrategy) -> float:
        """Heuristic confidence estimation based on output characteristics."""
        if not output or len(output) < 10:
            return 0.1

        score = 0.5

        # Length-based quality signal (longer, more substantive answers)
        if len(output) > 100:
            score += 0.1
        if len(output) > 500:
            score += 0.05

        # Structure signals (bullet points, numbered lists, code blocks)
        structure_markers = ["- ", "1.", "2.", "```", "def ", "class "]
        structure_count = sum(1 for m in structure_markers if m in output)
        score += min(0.15, structure_count * 0.03)

        # Reasoning signal words
        reasoning_words = [
            "because", "therefore", "thus", "consequently",
            "evidence", "implies", "conclude", "analysis",
        ]
        reasoning_count = sum(
            1 for w in reasoning_words if w in output.lower()
        )
        score += min(0.15, reasoning_count * 0.03)

        # Penalize uncertainty signals
        uncertainty_words = ["maybe", "perhaps", "not sure", "might be", "unclear"]
        uncertainty_count = sum(
            1 for w in uncertainty_words if w in output.lower()
        )
        score -= min(0.2, uncertainty_count * 0.05)

        return max(0.05, min(0.99, score))


# ──────────────────────────────────────────────
# Strategy Weight Tracker
# ──────────────────────────────────────────────

class StrategyWeightTracker:
    """
    Tracks historical win rates and adjusts strategy selection weights
    using exponential moving averages.
    """

    def __init__(self, ema_alpha: float = 0.1):
        self._ema_alpha = ema_alpha
        self._win_counts: Dict[str, int] = {s.value: 0 for s in CognitiveStrategy}
        self._total_counts: Dict[str, int] = {s.value: 0 for s in CognitiveStrategy}
        self._ema_scores: Dict[str, float] = {s.value: 0.5 for s in CognitiveStrategy}

    def record_outcome(
        self,
        strategy: CognitiveStrategy,
        confidence: float,
        was_winner: bool,
    ) -> None:
        """Record the outcome of a strategy branch."""
        name = strategy.value
        self._total_counts[name] += 1
        if was_winner:
            self._win_counts[name] += 1

        # Update EMA score
        self._ema_scores[name] = (
            self._ema_alpha * confidence
            + (1 - self._ema_alpha) * self._ema_scores[name]
        )

    def get_ranked_strategies(self, top_k: int = 5) -> List[CognitiveStrategy]:
        """Get strategies ranked by EMA score, highest first."""
        ranked = sorted(
            CognitiveStrategy,
            key=lambda s: self._ema_scores[s.value],
            reverse=True,
        )
        return ranked[:top_k]

    def get_weights(self) -> Dict[str, float]:
        return dict(self._ema_scores)


# ──────────────────────────────────────────────
# Speculative Parallel Branching Engine
# ──────────────────────────────────────────────

class SpeculativeBranchingEngine:
    """
    Main engine that forks multiple reasoning paths in parallel
    and selects the best result.

    Usage:
        engine = SpeculativeBranchingEngine(generate_fn=my_llm_call)
        result = engine.speculate("How do neural networks learn?", num_branches=3)
        print(result.summary())
    """

    def __init__(
        self,
        generate_fn: Optional[Callable[[str], str]] = None,
        max_workers: int = 5,
        default_branches: int = 3,
    ):
        self.generate_fn = generate_fn or (lambda p: f"[mock] {p[:100]}")
        self._executor_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._branch_executor = BranchExecutor()
        self._weight_tracker = StrategyWeightTracker()
        self._default_branches = default_branches
        self._total_speculations: int = 0

    def speculate(
        self,
        problem: str,
        context: str = "",
        num_branches: Optional[int] = None,
        strategies: Optional[List[CognitiveStrategy]] = None,
        timeout_s: float = 30.0,
    ) -> SpeculativeResult:
        """
        Fork multiple parallel reasoning branches and race them.

        Args:
            problem: The problem to solve
            context: Additional context
            num_branches: Number of branches (default: 3)
            strategies: Specific strategies to use (auto-selected if None)
            timeout_s: Maximum time for all branches

        Returns:
            SpeculativeResult with the winning branch
        """
        start = time.perf_counter()
        n = num_branches or self._default_branches
        self._total_speculations += 1

        # Select strategies
        if strategies:
            selected = strategies[:n]
        else:
            selected = self._weight_tracker.get_ranked_strategies(n)

        # Launch branches in parallel
        futures: Dict[Future, Tuple[str, CognitiveStrategy]] = {}
        for strategy in selected:
            branch_id = secrets.token_hex(6)
            future = self._executor_pool.submit(
                self._branch_executor.execute,
                branch_id=branch_id,
                problem=problem,
                strategy=strategy,
                generate_fn=self.generate_fn,
                context=context,
            )
            futures[future] = (branch_id, strategy)

        # Collect results
        branches: List[BranchResult] = []
        for future in as_completed(futures, timeout=timeout_s):
            try:
                branch_result = future.result(timeout=5.0)
                branches.append(branch_result)
            except Exception as e:
                bid, strat = futures[future]
                branches.append(BranchResult(
                    branch_id=bid,
                    strategy=strat,
                    error=str(e),
                ))

        # Select winner (highest confidence among valid branches)
        valid_branches = [b for b in branches if b.is_valid]
        winner = None
        if valid_branches:
            winner = max(valid_branches, key=lambda b: b.confidence)
            winner.was_winner = True

        # Record outcomes for adaptive weighting
        for branch in branches:
            self._weight_tracker.record_outcome(
                strategy=branch.strategy,
                confidence=branch.confidence if branch.is_valid else 0.0,
                was_winner=branch.was_winner,
            )

        total_ms = (time.perf_counter() - start) * 1000

        # Estimate sequential speedup
        sequential_time = sum(b.duration_ms for b in branches)
        speedup = sequential_time / max(total_ms, 1.0) if branches else 1.0

        result = SpeculativeResult(
            problem=problem,
            winner=winner,
            branches=branches,
            total_branches=len(branches),
            total_duration_ms=total_ms,
            speedup_vs_sequential=speedup,
            strategy_scores=self._weight_tracker.get_weights(),
        )

        self._try_record_metrics(result)
        logger.info(result.summary())
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_speculations": self._total_speculations,
            "strategy_weights": self._weight_tracker.get_weights(),
            "strategy_wins": dict(self._weight_tracker._win_counts),
        }

    def shutdown(self) -> None:
        """Gracefully shut down the thread pool."""
        self._executor_pool.shutdown(wait=False)

    def _try_record_metrics(self, result: SpeculativeResult) -> None:
        try:
            from telemetry.metrics import MetricsCollector
            mc = MetricsCollector.get_instance()
            mc.histogram("brain.spb.branches", result.total_branches)
            mc.histogram("brain.spb.speedup", result.speedup_vs_sequential)
            if result.winner:
                mc.counter(f"brain.spb.wins.{result.winner.strategy.value}")
        except Exception:
            pass
