"""
Problem Classifier — Domain Detection + Strategy Selection.
────────────────────────────────────────────────────────────
Classifies problems into 8 domains and selects optimal
reasoning strategies for each:
  coding, debugging, algorithm, architecture,
  logic, math, real_world, general
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from brain.reasoning import CognitiveMode

logger = logging.getLogger(__name__)

NL = "\n"


class ProblemDomain(Enum):
    CODING = "coding"
    DEBUGGING = "debugging"
    ALGORITHM = "algorithm"
    ARCHITECTURE = "architecture"
    LOGIC = "logic"
    MATH = "math"
    REAL_WORLD = "real_world"
    GENERAL = "general"


@dataclass
class DomainStrategy:
    """Optimal strategy configuration for a problem domain."""
    domain: ProblemDomain = ProblemDomain.GENERAL
    primary_mode: CognitiveMode = CognitiveMode.DECOMPOSE
    fallback_modes: List[CognitiveMode] = field(default_factory=list)
    use_code_analysis: bool = False
    use_security_scan: bool = False
    use_simulation: bool = False
    suggested_iterations: int = 4
    confidence_boost: float = 0.0    # Domain expertise boost
    focus_areas: List[str] = field(default_factory=list)

    def summary(self):
        modes = [self.primary_mode.value] + [m.value for m in self.fallback_modes]
        return (
            f"Domain: {self.domain.value} | "
            f"Modes: {modes} | "
            f"Iters: {self.suggested_iterations} | "
            f"Code: {self.use_code_analysis} Security: {self.use_security_scan}"
        )


# Pre-configured strategies for each domain
DOMAIN_STRATEGIES: Dict[ProblemDomain, DomainStrategy] = {
    ProblemDomain.CODING: DomainStrategy(
        domain=ProblemDomain.CODING,
        primary_mode=CognitiveMode.DECOMPOSE,
        fallback_modes=[CognitiveMode.SIMULATE, CognitiveMode.BACKTRACK],
        use_code_analysis=True,
        use_security_scan=True,
        suggested_iterations=5,
        focus_areas=["correctness", "security", "edge_cases", "testing"],
    ),
    ProblemDomain.DEBUGGING: DomainStrategy(
        domain=ProblemDomain.DEBUGGING,
        primary_mode=CognitiveMode.SIMULATE,
        fallback_modes=[CognitiveMode.BACKTRACK, CognitiveMode.DECOMPOSE],
        use_code_analysis=True,
        use_simulation=True,
        suggested_iterations=6,
        focus_areas=["root_cause", "trace", "state_inspection", "reproduction"],
    ),
    ProblemDomain.ALGORITHM: DomainStrategy(
        domain=ProblemDomain.ALGORITHM,
        primary_mode=CognitiveMode.ABSTRACT,
        fallback_modes=[CognitiveMode.DECOMPOSE, CognitiveMode.ANALOGIZE],
        use_simulation=True,
        suggested_iterations=5,
        focus_areas=["time_complexity", "space_complexity", "correctness_proof"],
    ),
    ProblemDomain.ARCHITECTURE: DomainStrategy(
        domain=ProblemDomain.ARCHITECTURE,
        primary_mode=CognitiveMode.ABSTRACT,
        fallback_modes=[CognitiveMode.ANALOGIZE, CognitiveMode.DECOMPOSE],
        use_code_analysis=True,
        suggested_iterations=4,
        focus_areas=["scalability", "maintainability", "separation_of_concerns"],
    ),
    ProblemDomain.LOGIC: DomainStrategy(
        domain=ProblemDomain.LOGIC,
        primary_mode=CognitiveMode.DECOMPOSE,
        fallback_modes=[CognitiveMode.SIMULATE, CognitiveMode.ABSTRACT],
        suggested_iterations=5,
        focus_areas=["soundness", "completeness", "formal_proof"],
    ),
    ProblemDomain.MATH: DomainStrategy(
        domain=ProblemDomain.MATH,
        primary_mode=CognitiveMode.DECOMPOSE,
        fallback_modes=[CognitiveMode.ABSTRACT, CognitiveMode.SIMULATE],
        suggested_iterations=4,
        focus_areas=["precision", "step_verification", "edge_cases"],
    ),
    ProblemDomain.REAL_WORLD: DomainStrategy(
        domain=ProblemDomain.REAL_WORLD,
        primary_mode=CognitiveMode.ANALOGIZE,
        fallback_modes=[CognitiveMode.DECOMPOSE, CognitiveMode.ABSTRACT],
        suggested_iterations=3,
        focus_areas=["practicality", "trade_offs", "stakeholder_impact"],
    ),
    ProblemDomain.GENERAL: DomainStrategy(
        domain=ProblemDomain.GENERAL,
        primary_mode=CognitiveMode.DECOMPOSE,
        fallback_modes=[CognitiveMode.ANALOGIZE, CognitiveMode.BACKTRACK],
        suggested_iterations=4,
        focus_areas=["clarity", "completeness", "correctness"],
    ),
}


# Keyword patterns for each domain
DOMAIN_KEYWORDS: Dict[ProblemDomain, List[str]] = {
    ProblemDomain.CODING: [
        "implement", "write code", "function", "class", "method",
        "api", "endpoint", "module", "library", "package", "program",
        "create a", "build a", "develop", "code", "script",
        "python", "javascript", "typescript", "java", "rust", "go",
    ],
    ProblemDomain.DEBUGGING: [
        "debug", "fix", "error", "bug", "crash", "exception",
        "traceback", "stack trace", "not working", "broken",
        "unexpected", "wrong output", "fails", "issue",
    ],
    ProblemDomain.ALGORITHM: [
        "algorithm", "sort", "search", "graph", "tree", "dynamic programming",
        "dp", "greedy", "backtrack", "bfs", "dfs", "shortest path",
        "time complexity", "space complexity", "big o", "optimize",
        "data structure", "linked list", "hash", "binary",
    ],
    ProblemDomain.ARCHITECTURE: [
        "architecture", "design pattern", "system design", "microservice",
        "monolith", "scalab", "infrastructure", "deploy", "database schema",
        "api design", "distributed", "load balanc", "caching strategy",
    ],
    ProblemDomain.LOGIC: [
        "prove", "proof", "theorem", "logical", "boolean",
        "predicate", "inference", "deduction", "induction",
        "contradict", "valid", "satisf",
    ],
    ProblemDomain.MATH: [
        "calculate", "equation", "formula", "integral", "derivative",
        "matrix", "vector", "probability", "statistic", "linear algebra",
        "calculus", "sum", "product", "series",
    ],
    ProblemDomain.REAL_WORLD: [
        "real world", "practical", "business", "stakeholder",
        "user experience", "trade-off", "cost", "budget",
        "team", "workflow", "process", "migration",
    ],
}


class ProblemClassifier:
    """
    Classifies problems into domains and selects optimal strategies.

    Uses keyword matching + LLM classification for accuracy.
    """

    def __init__(self, generate_fn: Callable = None):
        self.generate_fn = generate_fn

    def set_generate_fn(self, fn: Callable):
        self.generate_fn = fn

    def classify(self, problem: str) -> ProblemDomain:
        """Classify a problem into its primary domain."""
        # Stage 1: Keyword-based scoring
        scores = self._keyword_scores(problem)

        # Stage 2: LLM classification if scores are ambiguous
        top_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if top_scores and top_scores[0][1] > 0:
            # If clear winner, use it
            if len(top_scores) < 2 or top_scores[0][1] > top_scores[1][1] * 1.5:
                return top_scores[0][0]

        # Ambiguous — use LLM
        if self.generate_fn:
            return self._llm_classify(problem)

        # Fallback to best keyword match
        if top_scores and top_scores[0][1] > 0:
            return top_scores[0][0]
        return ProblemDomain.GENERAL

    def get_strategy(self, domain: ProblemDomain = None,
                     problem: str = None) -> DomainStrategy:
        """Get the optimal strategy for a domain or problem."""
        if domain is None and problem:
            domain = self.classify(problem)
        domain = domain or ProblemDomain.GENERAL
        return DOMAIN_STRATEGIES.get(domain, DOMAIN_STRATEGIES[ProblemDomain.GENERAL])

    def get_all_modes(self, domain: ProblemDomain) -> List[CognitiveMode]:
        """Get all reasoning modes to try for a domain (primary + fallbacks)."""
        strategy = DOMAIN_STRATEGIES.get(
            domain, DOMAIN_STRATEGIES[ProblemDomain.GENERAL])
        return [strategy.primary_mode] + strategy.fallback_modes

    def _keyword_scores(self, problem: str) -> Dict[ProblemDomain, float]:
        """Score each domain by keyword matches."""
        lower = problem.lower()
        scores = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = sum(1.0 for kw in keywords if kw in lower)
            scores[domain] = score
        return scores

    def _llm_classify(self, problem: str) -> ProblemDomain:
        """Use LLM for classification when keywords are ambiguous."""
        domains_str = "|".join(d.value for d in ProblemDomain)
        try:
            response = self.generate_fn(
                "Classify this problem into exactly ONE domain:" + NL
                + domains_str + NL
                + "Problem: " + problem[:500] + NL
                + "DOMAIN: "
            )
            upper = response.upper()
            for d in ProblemDomain:
                if d.value.upper() in upper:
                    return d
        except Exception as e:
            import logging
            logging.debug(f"Domain classifier fallback: {e}")
        return ProblemDomain.GENERAL

    # ── Phase 10: Learned Strategy Weights ──

    def update_strategy_weights(
        self,
        domain: "ProblemDomain",
        reward: float,
        strategy_used: str,
        alpha: float = 0.1,
    ) -> None:
        """Update strategy weights based on trajectory reward.

        Uses EMA to shift iteration counts and confidence boosts toward
        strategies that produce higher rewards per domain.

        Args:
            domain: The problem domain
            reward: The trajectory reward (0-1)
            strategy_used: Name of the cognitive mode used
            alpha: Learning rate for EMA update
        """
        if domain not in DOMAIN_STRATEGIES:
            return

        strat = DOMAIN_STRATEGIES[domain]

        # Adjust suggested iterations based on reward:
        # High reward → maybe fewer iterations needed (efficient)
        # Low reward → maybe more iterations needed
        if reward > 0.8:
            target_iters = max(2, strat.suggested_iterations - 1)
        elif reward < 0.3:
            target_iters = min(10, strat.suggested_iterations + 1)
        else:
            target_iters = strat.suggested_iterations

        strat.suggested_iterations = round(
            (1 - alpha) * strat.suggested_iterations + alpha * target_iters
        )

        # Update confidence boost based on recent performance
        strat.confidence_boost = (
            (1 - alpha) * strat.confidence_boost + alpha * (reward - 0.5) * 0.1
        )

        logger.debug(
            f"Updated strategy weights for {domain.value}: "
            f"iters={strat.suggested_iterations}, "
            f"boost={strat.confidence_boost:.4f}, "
            f"strategy={strategy_used}, reward={reward:.3f}"
        )
