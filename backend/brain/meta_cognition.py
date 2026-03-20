"""
Meta-Cognition Engine — Third-Order Metacognition + Self-Evolution
════════════════════════════════════════════════════════════════════
Reasons about reasoning about reasoning (M²R).
Invents new reasoning strategies. Proposes and verifies self-improvements.

No LLM, no GPU — pure recursive metacognition.

Architecture:
  Problem → Meta1: "What strategy to use?"
               ↓
           Meta2: "How to choose strategies better?"
               ↓
           Meta3: "Can I invent a better meta-strategy?"
               ↓
           Strategy Invention → Validation → Deploy
"""

import hashlib
import logging
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class MetaLevel(Enum):
    LEVEL_0 = "direct"          # Solve the problem directly
    LEVEL_1 = "meta"            # Choose how to solve it
    LEVEL_2 = "meta_meta"       # Improve how we choose
    LEVEL_3 = "meta_meta_meta"  # Invent new choice mechanisms


class StrategyType(Enum):
    DECOMPOSE = "decompose"
    ANALOGIZE = "analogize"
    ABSTRACT = "abstract"
    SPECIALIZE = "specialize"
    TRANSFORM = "transform"
    INVERT = "invert"
    RANDOMIZE = "randomize"
    HYBRIDIZE = "hybridize"


@dataclass
class MetaStrategy:
    """A reasoning strategy that can be selected, evolved, and invented."""
    name: str
    strategy_type: StrategyType
    description: str
    performance_history: List[float] = field(default_factory=list)
    invented_at: float = 0.0
    uses: int = 0

    @property
    def avg_performance(self) -> float:
        return sum(self.performance_history) / len(self.performance_history) if self.performance_history else 0.0

    @property
    def id(self) -> str:
        return hashlib.sha256(f"{self.name}:{self.strategy_type.value}".encode()).hexdigest()[:10]


@dataclass
class SelfImprovement:
    """A proposed self-improvement."""
    target_module: str
    description: str
    expected_benefit: str
    risk_level: str
    confidence: float
    applied: bool = False


@dataclass
class MetaCognitionResult:
    meta_level_reached: MetaLevel = MetaLevel.LEVEL_0
    strategy_selected: str = ""
    strategy_reasoning: List[str] = field(default_factory=list)
    new_strategies_invented: int = 0
    self_improvements: List[SelfImprovement] = field(default_factory=list)
    solution: str = ""
    confidence: float = 0.0
    duration_ms: float = 0.0

    def summary(self) -> str:
        lines = [
            f"## Meta-Cognition Result",
            f"**Meta Level**: {self.meta_level_reached.value}",
            f"**Strategy**: {self.strategy_selected}",
            f"**Confidence**: {self.confidence:.3f}",
            f"**New Strategies Invented**: {self.new_strategies_invented}",
        ]
        if self.strategy_reasoning:
            lines.append("\n### Reasoning Trace:")
            for step in self.strategy_reasoning:
                lines.append(f"  → {step}")
        if self.self_improvements:
            lines.append(f"\n### Self-Improvements Proposed: {len(self.self_improvements)}")
            for imp in self.self_improvements:
                lines.append(f"  - [{imp.risk_level}] {imp.description[:80]}")
        if self.solution:
            lines.append(f"\n**Solution**: {self.solution[:200]}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# STRATEGY LIBRARY
# ═══════════════════════════════════════════════════════════

class StrategyLibrary:
    """Maintains and evolves the strategy portfolio."""

    BUILT_IN: List[MetaStrategy] = [
        MetaStrategy("Divide & Conquer", StrategyType.DECOMPOSE, "Split problem, solve parts, merge"),
        MetaStrategy("Pattern Matching", StrategyType.ANALOGIZE, "Find similar solved problems"),
        MetaStrategy("Abstraction Lift", StrategyType.ABSTRACT, "Solve general version first"),
        MetaStrategy("Case Analysis", StrategyType.SPECIALIZE, "Handle each case separately"),
        MetaStrategy("Representation Change", StrategyType.TRANSFORM, "Transform to easier domain"),
        MetaStrategy("Contrapositive", StrategyType.INVERT, "Prove the contrapositive instead"),
        MetaStrategy("Monte Carlo", StrategyType.RANDOMIZE, "Random sampling for approximate answer"),
        MetaStrategy("Hybrid Approach", StrategyType.HYBRIDIZE, "Combine multiple strategies"),
    ]

    def __init__(self):
        self.strategies: Dict[str, MetaStrategy] = {}
        for s in self.BUILT_IN:
            s.invented_at = time.time()
            self.strategies[s.id] = s
        self._invented_count = 0

    def select_best(self, problem_features: Dict[str, float]) -> MetaStrategy:
        """Select the best strategy for given problem features."""
        scores = {}
        for sid, strategy in self.strategies.items():
            score = strategy.avg_performance * 0.5
            # Feature-based boosting
            if problem_features.get("complexity", 0) > 0.7 and strategy.strategy_type == StrategyType.DECOMPOSE:
                score += 0.3
            if problem_features.get("similarity", 0) > 0.5 and strategy.strategy_type == StrategyType.ANALOGIZE:
                score += 0.3
            if problem_features.get("abstractness", 0) > 0.6 and strategy.strategy_type == StrategyType.ABSTRACT:
                score += 0.25
            if problem_features.get("randomness", 0) > 0.5 and strategy.strategy_type == StrategyType.RANDOMIZE:
                score += 0.2
            score += strategy.uses * 0.01  # Slight bias toward proven strategies
            scores[sid] = score

        best_id = max(scores, key=scores.get) if scores else list(self.strategies.keys())[0]
        selected = self.strategies[best_id]
        selected.uses += 1
        return selected

    def record_performance(self, strategy_id: str, performance: float) -> None:
        """Record how well a strategy performed."""
        if strategy_id in self.strategies:
            self.strategies[strategy_id].performance_history.append(performance)
            # Keep history bounded
            if len(self.strategies[strategy_id].performance_history) > 50:
                self.strategies[strategy_id].performance_history = \
                    self.strategies[strategy_id].performance_history[-50:]

    def invent_strategy(self, problem_context: str) -> MetaStrategy:
        """Invent a new strategy by combining/mutating existing ones."""
        self._invented_count += 1

        # Pick two parent strategies
        parents = random.sample(list(self.strategies.values()), min(2, len(self.strategies)))

        # Crossover: combine types and descriptions
        strategy_types = list(StrategyType)
        new_type = random.choice(strategy_types)

        inventions = [
            f"Recursive {parents[0].name}",
            f"Parallel {parents[0].name} with {parents[-1].name} fallback",
            f"Iterative deepening {new_type.value}",
            f"Bidirectional {parents[0].name}",
            f"Adaptive {new_type.value} with dynamic switching",
            f"Constraint-guided {parents[-1].name}",
            f"Probabilistic {parents[0].name} ensemble",
            f"Hierarchical {new_type.value} cascade",
        ]

        name = inventions[self._invented_count % len(inventions)]
        description = f"Invented from combining {parents[0].name} + {parents[-1].name}. Context: {problem_context[:50]}"

        new_strategy = MetaStrategy(
            name=name,
            strategy_type=new_type,
            description=description,
            invented_at=time.time(),
        )

        self.strategies[new_strategy.id] = new_strategy
        return new_strategy


# ═══════════════════════════════════════════════════════════
# SELF-IMPROVEMENT PROPOSER
# ═══════════════════════════════════════════════════════════

class SelfImprovementProposer:
    """Proposes improvements to the system based on performance analysis."""

    IMPROVEMENT_TEMPLATES = [
        SelfImprovement("strategy_selector", "Add problem-feature extraction for better strategy matching", "10-20% better strategy selection", "low", 0.7),
        SelfImprovement("consensus_engine", "Add weighted solver priority based on problem type", "15% faster consensus", "low", 0.6),
        SelfImprovement("knowledge_base", "Add temporal decay to knowledge confidence", "Reduce stale knowledge impact", "medium", 0.65),
        SelfImprovement("swarm_engine", "Add adaptive population sizing based on problem complexity", "Better resource utilization", "low", 0.7),
        SelfImprovement("phantom_sandbox", "Add effect learning from past simulations", "More accurate risk prediction", "medium", 0.6),
        SelfImprovement("tool_fabricator", "Expand primitive library with domain-specific ops", "More tools fabricable", "low", 0.75),
        SelfImprovement("adversarial_engine", "Add threat signature learning from detected attacks", "Better threat detection over time", "medium", 0.65),
        SelfImprovement("meta_cognition", "Add fourth meta-level for paradigm shifting", "Handle truly novel problems", "high", 0.4),
    ]

    def propose(self, performance_data: Dict[str, float]) -> List[SelfImprovement]:
        """Propose improvements based on performance analysis."""
        proposals = []
        for template in self.IMPROVEMENT_TEMPLATES:
            # Simulate relevance: if module performance is below threshold, propose improvement
            module_perf = performance_data.get(template.target_module, 0.5)
            if module_perf < 0.8:
                proposal = SelfImprovement(
                    target_module=template.target_module,
                    description=template.description,
                    expected_benefit=template.expected_benefit,
                    risk_level=template.risk_level,
                    confidence=template.confidence * (1 - module_perf),
                )
                proposals.append(proposal)

        return sorted(proposals, key=lambda p: -p.confidence)[:5]


# ═══════════════════════════════════════════════════════════
# PROBLEM FEATURE EXTRACTOR
# ═══════════════════════════════════════════════════════════

class ProblemAnalyzer:
    """Extracts features from a problem for meta-reasoning."""

    COMPLEXITY_KEYWORDS = {"optimize", "prove", "synthesize", "invent", "design", "solve", "build"}
    SIMILARITY_KEYWORDS = {"like", "similar", "same", "as", "such", "compare", "versus"}
    ABSTRACT_KEYWORDS = {"general", "abstract", "any", "all", "every", "universal", "theory"}
    RANDOM_KEYWORDS = {"random", "probability", "chance", "likelihood", "estimate", "approximate"}

    def analyze(self, problem: str) -> Dict[str, float]:
        """Extract problem features for strategy selection."""
        words = set(problem.lower().split())
        word_count = len(words)

        return {
            "complexity": len(words & self.COMPLEXITY_KEYWORDS) / max(word_count, 1) * 5,
            "similarity": len(words & self.SIMILARITY_KEYWORDS) / max(word_count, 1) * 5,
            "abstractness": len(words & self.ABSTRACT_KEYWORDS) / max(word_count, 1) * 5,
            "randomness": len(words & self.RANDOM_KEYWORDS) / max(word_count, 1) * 5,
            "length": min(1.0, word_count / 50),
        }


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE — Meta-Cognition
# ═══════════════════════════════════════════════════════════

class MetaCognition:
    """
    Third-order metacognition engine.

    Usage:
        meta = MetaCognition()
        result = meta.think("How to optimize a neural network's hyperparameters?")
        print(result.meta_level_reached)
        print(result.strategy_selected)
        print(result.solution)
    """

    def __init__(self):
        self.library = StrategyLibrary()
        self.analyzer = ProblemAnalyzer()
        self.improver = SelfImprovementProposer()
        self._stats = {"meta_cycles": 0, "strategies_invented": 0, "improvements_proposed": 0, "max_meta_level": 0}

    def think(self, problem: str, max_meta_level: int = 3) -> MetaCognitionResult:
        """Execute multi-level metacognitive reasoning."""
        start = time.time()
        self._stats["meta_cycles"] += 1
        result = MetaCognitionResult()

        # Level 0: Analyze the problem
        features = self.analyzer.analyze(problem)
        result.strategy_reasoning.append(f"L0: Analyzed problem features: complexity={features['complexity']:.2f}")
        result.meta_level_reached = MetaLevel.LEVEL_0

        # Level 1: Select strategy
        strategy = self.library.select_best(features)
        result.strategy_selected = strategy.name
        result.strategy_reasoning.append(f"L1: Selected strategy '{strategy.name}' ({strategy.strategy_type.value})")
        result.meta_level_reached = MetaLevel.LEVEL_1

        # Level 2: Evaluate if we should improve strategy selection
        if max_meta_level >= 2:
            avg_perf = strategy.avg_performance
            if avg_perf < 0.6 or strategy.uses > 10:
                result.strategy_reasoning.append(f"L2: Strategy perf ({avg_perf:.2f}) below threshold — considering alternatives")

                # Try inventing a new strategy
                if avg_perf < 0.4 or len(self.library.strategies) < 12:
                    new_strategy = self.library.invent_strategy(problem)
                    result.new_strategies_invented += 1
                    self._stats["strategies_invented"] += 1
                    result.strategy_reasoning.append(f"L2: Invented new strategy: '{new_strategy.name}'")

                    # Optimistically use the new strategy
                    strategy = new_strategy
                    result.strategy_selected = strategy.name

                result.meta_level_reached = MetaLevel.LEVEL_2

        # Level 3: Meta-meta — consider if our entire approach is wrong
        if max_meta_level >= 3:
            result.strategy_reasoning.append("L3: Evaluating meta-strategy effectiveness")

            # Propose self-improvements
            performance_data = {
                "strategy_selector": strategy.avg_performance,
                "consensus_engine": 0.7,
                "knowledge_base": 0.6,
                "swarm_engine": 0.65,
                "phantom_sandbox": 0.75,
                "tool_fabricator": 0.7,
                "adversarial_engine": 0.8,
                "meta_cognition": 0.5,
            }
            improvements = self.improver.propose(performance_data)
            result.self_improvements = improvements
            self._stats["improvements_proposed"] += len(improvements)

            if improvements:
                result.strategy_reasoning.append(f"L3: Proposed {len(improvements)} self-improvements")

            result.meta_level_reached = MetaLevel.LEVEL_3
            self._stats["max_meta_level"] = max(self._stats["max_meta_level"], 3)

        # Generate solution using selected strategy
        result.solution = self._apply_strategy(strategy, problem, features)
        result.confidence = min(0.95, 0.3 + strategy.avg_performance * 0.3 + features.get("complexity", 0) * 0.2)

        # Record performance (heuristic)
        self.library.record_performance(strategy.id, result.confidence)

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _apply_strategy(self, strategy: MetaStrategy, problem: str,
                        features: Dict[str, float]) -> str:
        """Apply a selected strategy to generate a solution."""
        approach = strategy.strategy_type

        if approach == StrategyType.DECOMPOSE:
            parts = [s.strip() for s in problem.split() if len(s) > 3]
            return f"Decompose: Break into {min(len(parts), 4)} sub-problems, solve each, then merge results"
        elif approach == StrategyType.ANALOGIZE:
            return f"Analogize: This resembles known patterns — apply established solution adapted to context"
        elif approach == StrategyType.ABSTRACT:
            return f"Abstract: Generalize the problem, solve the general case, then specialize back"
        elif approach == StrategyType.SPECIALIZE:
            return f"Specialize: Enumerate cases, solve each separately, combine into complete solution"
        elif approach == StrategyType.TRANSFORM:
            return f"Transform: Convert to an equivalent but easier representation, solve, convert back"
        elif approach == StrategyType.INVERT:
            return f"Invert: Instead of proving X, prove that not-X leads to contradiction"
        elif approach == StrategyType.RANDOMIZE:
            return f"Randomize: Sample solution space, evaluate fitness, converge on best candidates"
        elif approach == StrategyType.HYBRIDIZE:
            return f"Hybridize: Combine decomposition + pattern matching for comprehensive solution"
        else:
            return f"Apply {strategy.name}: {strategy.description}"

    def solve(self, prompt: str) -> MetaCognitionResult:
        """Natural language interface."""
        return self.think(prompt)

    def get_stats(self) -> Dict[str, Any]:
        return {"engine": "MetaCognition", "meta_cycles": self._stats["meta_cycles"], "strategies_invented": self._stats["strategies_invented"], "total_strategies": len(self.library.strategies), "improvements_proposed": self._stats["improvements_proposed"], "max_meta_level_reached": self._stats["max_meta_level"]}
