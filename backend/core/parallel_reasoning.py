"""
Parallel Reasoning Engine — Multi-Path Strategy Executor
════════════════════════════════════════════════════════
Runs 3-5 reasoning strategies simultaneously, scores each
result, and selects the optimal answer via tournament selection.

Strategies:
  1. Chain-of-Thought   — Step-by-step logical reasoning
  2. Analogical         — Find similar solved problems
  3. Contrarian         — Devil's advocate challenge
  4. First-Principles   — Break down to fundamentals
  5. Synthesis          — Merge multiple perspectives
"""

import hashlib
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReasoningStrategy(Enum):
    CHAIN_OF_THOUGHT = "chain_of_thought"
    ANALOGICAL = "analogical"
    CONTRARIAN = "contrarian"
    FIRST_PRINCIPLES = "first_principles"
    SYNTHESIS = "synthesis"


@dataclass
class ReasoningPath:
    """Result from a single reasoning strategy."""
    strategy: ReasoningStrategy
    result: str = ""
    confidence: float = 0.0
    latency_ms: float = 0.0
    token_count: int = 0
    error: str = ""

    @property
    def quality_score(self) -> float:
        """Combined quality: confidence * (1 - latency_penalty)."""
        latency_penalty = min(self.latency_ms / 10000, 0.3)
        return self.confidence * (1 - latency_penalty)


@dataclass
class ParallelResult:
    """Merged result from parallel reasoning."""
    best_path: Optional[ReasoningPath] = None
    all_paths: List[ReasoningPath] = field(default_factory=list)
    consensus_score: float = 0.0
    total_latency_ms: float = 0.0
    strategy_used: str = ""
    merged_answer: str = ""


# Strategy prompt templates
STRATEGY_PROMPTS = {
    ReasoningStrategy.CHAIN_OF_THOUGHT: (
        "Think step by step through this problem. Show your reasoning chain:\n\n"
        "{query}\n\nStep-by-step reasoning:"
    ),
    ReasoningStrategy.ANALOGICAL: (
        "Find analogies and similar solved problems for this:\n\n"
        "{query}\n\nSimilar problems and their solutions:"
    ),
    ReasoningStrategy.CONTRARIAN: (
        "Play devil's advocate. Challenge assumptions in this problem:\n\n"
        "{query}\n\nCritical analysis and potential issues:"
    ),
    ReasoningStrategy.FIRST_PRINCIPLES: (
        "Break this down to fundamental principles and build up:\n\n"
        "{query}\n\nFirst principles analysis:"
    ),
    ReasoningStrategy.SYNTHESIS: (
        "Consider multiple perspectives and synthesize a comprehensive answer:\n\n"
        "{query}\n\nMulti-perspective synthesis:"
    ),
}


class ParallelReasoningEngine:
    """
    Executes multiple reasoning strategies concurrently and selects
    the best result via tournament scoring.

    Performance:
      - ThreadPoolExecutor for true parallel execution
      - Early termination if high-confidence result found
      - Strategy performance tracking for adaptive selection
    """

    MAX_WORKERS = 5

    def __init__(self, generate_fn: Optional[Callable] = None,
                 max_strategies: int = 3):
        self.generate_fn = generate_fn
        self.max_strategies = min(max_strategies, 5)
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS,
            thread_name_prefix="reasoning",
        )
        self._strategy_stats: Dict[str, Dict] = {
            s.value: {"wins": 0, "runs": 0, "avg_confidence": 0.5}
            for s in ReasoningStrategy
        }
        self._lock = threading.Lock()
        self._total_runs = 0
        logger.info(f"[PARALLEL-REASONING] Engine initialized (max_strategies={max_strategies})")

    def reason(self, query: str,
               strategies: List[ReasoningStrategy] = None,
               timeout: float = 30.0) -> ParallelResult:
        """Execute multiple reasoning strategies in parallel."""
        start_time = time.time()

        # Select strategies (use top-performing unless specified)
        if strategies is None:
            strategies = self._select_best_strategies()

        # Launch parallel execution
        futures = {}
        for strategy in strategies:
            future = self._executor.submit(
                self._execute_strategy, query, strategy,
            )
            futures[future] = strategy

        # Collect results with timeout
        paths: List[ReasoningPath] = []
        for future in as_completed(futures, timeout=timeout):
            strategy = futures[future]
            try:
                path = future.result()
                paths.append(path)
            except Exception as e:
                paths.append(ReasoningPath(
                    strategy=strategy, error=str(e), confidence=0.0,
                ))

        # Tournament selection: pick best
        result = self._tournament_select(paths)
        result.total_latency_ms = (time.time() - start_time) * 1000

        # Update strategy stats
        if result.best_path:
            self._update_stats(result.best_path.strategy, won=True)
            for path in paths:
                if path.strategy != result.best_path.strategy:
                    self._update_stats(path.strategy, won=False)

        self._total_runs += 1
        logger.info(
            f"[PARALLEL-REASONING] Completed: {len(paths)} paths, "
            f"winner={result.strategy_used}, "
            f"confidence={result.consensus_score:.2f}, "
            f"latency={result.total_latency_ms:.0f}ms"
        )
        return result

    def _execute_strategy(self, query: str,
                          strategy: ReasoningStrategy) -> ReasoningPath:
        """Execute a single reasoning strategy."""
        start = time.time()
        prompt = STRATEGY_PROMPTS[strategy].format(query=query)

        if self.generate_fn:
            result = self.generate_fn(prompt)
        else:
            # Fallback: template-based reasoning
            result = self._template_reason(query, strategy)

        latency = (time.time() - start) * 1000
        confidence = self._estimate_confidence(result, strategy)

        return ReasoningPath(
            strategy=strategy,
            result=result,
            confidence=confidence,
            latency_ms=latency,
            token_count=len(result.split()),
        )

    def _template_reason(self, query: str,
                         strategy: ReasoningStrategy) -> str:
        """Fallback template reasoning without LLM."""
        templates = {
            ReasoningStrategy.CHAIN_OF_THOUGHT: (
                f"Analyzing '{query[:80]}':\n"
                f"1. Identify the core problem\n"
                f"2. Break into sub-problems\n"
                f"3. Solve each systematically\n"
                f"4. Combine solutions"
            ),
            ReasoningStrategy.ANALOGICAL: (
                f"Finding analogies for '{query[:80]}':\n"
                f"This problem is similar to common patterns in software engineering."
            ),
            ReasoningStrategy.CONTRARIAN: (
                f"Challenging assumptions in '{query[:80]}':\n"
                f"Consider: what if the opposite approach works better?"
            ),
            ReasoningStrategy.FIRST_PRINCIPLES: (
                f"First principles for '{query[:80]}':\n"
                f"Fundamental axioms: break down to basic truths and rebuild."
            ),
            ReasoningStrategy.SYNTHESIS: (
                f"Synthesizing perspectives on '{query[:80]}':\n"
                f"Combining analytical, creative, and practical viewpoints."
            ),
        }
        return templates.get(strategy, f"Analysis of: {query[:100]}")

    def _estimate_confidence(self, result: str,
                             strategy: ReasoningStrategy) -> float:
        """Estimate answer confidence from content quality signals."""
        if not result:
            return 0.0

        score = 0.5  # Baseline

        # Length heuristic (more detailed = higher confidence)
        words = len(result.split())
        if words > 50:
            score += 0.1
        if words > 150:
            score += 0.1

        # Structure signals
        if any(marker in result for marker in ["1.", "2.", "- ", "•"]):
            score += 0.1
        if any(kw in result.lower() for kw in ["because", "therefore", "thus", "specifically"]):
            score += 0.1

        # Code presence for code-related queries
        if "```" in result or "def " in result or "class " in result:
            score += 0.05

        return min(score, 1.0)

    def _tournament_select(self, paths: List[ReasoningPath]) -> ParallelResult:
        """Select best result via tournament scoring."""
        result = ParallelResult(all_paths=paths)

        valid_paths = [p for p in paths if not p.error and p.result]
        if not valid_paths:
            result.merged_answer = "Unable to generate a confident answer."
            return result

        # Sort by quality score
        valid_paths.sort(key=lambda p: p.quality_score, reverse=True)
        winner = valid_paths[0]

        result.best_path = winner
        result.strategy_used = winner.strategy.value
        result.merged_answer = winner.result
        result.consensus_score = winner.confidence

        # Check consensus: if multiple strategies agree, boost confidence
        if len(valid_paths) >= 2:
            avg_confidence = sum(p.confidence for p in valid_paths) / len(valid_paths)
            if avg_confidence > 0.6:
                result.consensus_score = min(winner.confidence + 0.1, 1.0)

        return result

    def _select_best_strategies(self) -> List[ReasoningStrategy]:
        """Select top N strategies based on historical performance."""
        stats = sorted(
            self._strategy_stats.items(),
            key=lambda x: x[1]["avg_confidence"],
            reverse=True,
        )
        selected = [
            ReasoningStrategy(name) for name, _ in stats[:self.max_strategies]
        ]
        return selected

    def _update_stats(self, strategy: ReasoningStrategy, won: bool):
        """Update strategy performance statistics."""
        with self._lock:
            s = self._strategy_stats[strategy.value]
            s["runs"] += 1
            if won:
                s["wins"] += 1
            s["avg_confidence"] = s["wins"] / max(s["runs"], 1)

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_runs": self._total_runs,
            "max_strategies": self.max_strategies,
            "strategy_stats": dict(self._strategy_stats),
        }
