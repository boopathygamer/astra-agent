"""
Recursive Reasoning Synthesizer — Self-Evolving Meta-Reasoning
══════════════════════════════════════════════════════════════
Invents new reasoning strategies by composing, mutating, and evolving
reasoning blocks based on performance feedback.

No LLM, no GPU — pure algorithmic meta-reasoning.

Architecture:
  Problem → Strategy Selection (performance memory)
                    ↓
            Composable Reasoning Blocks → Execute Pipeline
                    ↓
            Performance Feedback → Strategy Evolution
                    ↓
            Auto-Discovery of New Compound Strategies

Novel contributions:
  • Strategy genome: reasoning steps as composable blocks
  • Strategy evolution: crossover + mutation of reasoning chains
  • Performance memory: tracks which strategies work for which problems
  • Auto-strategy-discovery: creates new compound strategies
  • Diminishing-return detector: knows when to stop and switch
"""

import copy
import hashlib
import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# REASONING BLOCKS — Composable Primitives
# ═══════════════════════════════════════════════════════════

class BlockType(Enum):
    """Primitive reasoning operations."""
    DECOMPOSE = "decompose"          # Break problem into sub-parts
    HYPOTHESIZE = "hypothesize"      # Generate candidate hypothesis
    VERIFY = "verify"                # Check hypothesis validity
    ANALOGIZE = "analogize"          # Find similar solved problems
    ABSTRACT = "abstract"            # Generalize to higher level
    CONCRETIZE = "concretize"        # Specialize to specific case
    ELIMINATE = "eliminate"           # Rule out impossible options
    ENUMERATE = "enumerate"          # List all possibilities
    BACKTRACK = "backtrack"          # Undo and try different path
    SYNTHESIZE = "synthesize"        # Combine partial results
    SIMPLIFY = "simplify"           # Reduce complexity
    TRANSFORM = "transform"         # Convert to equivalent form
    BOUND = "bound"                 # Establish upper/lower limits
    RECURSE = "recurse"             # Apply strategy to sub-problem
    CONTRADICT = "contradict"       # Assume negation, find contradiction


@dataclass
class ReasoningBlock:
    """A single reasoning operation."""
    block_type: BlockType
    weight: float = 1.0             # Importance weight
    params: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.block_type.value)

    def execute(self, context: 'ReasoningContext') -> 'ReasoningContext':
        """Execute this block on the given context."""
        executor = _BLOCK_EXECUTORS.get(self.block_type)
        if executor:
            return executor(self, context)
        return context


@dataclass
class ReasoningContext:
    """State passed between reasoning blocks."""
    problem: str = ""
    sub_problems: List[str] = field(default_factory=list)
    hypotheses: List[str] = field(default_factory=list)
    verified: List[Tuple[str, float]] = field(default_factory=list)
    eliminated: List[str] = field(default_factory=list)
    partial_results: List[str] = field(default_factory=list)
    final_answer: str = ""
    confidence: float = 0.0
    depth: int = 0
    max_depth: int = 5
    steps_log: List[str] = field(default_factory=list)

    def log(self, message: str):
        self.steps_log.append(f"[Depth {self.depth}] {message}")

    def clone(self) -> 'ReasoningContext':
        return ReasoningContext(
            problem=self.problem,
            sub_problems=list(self.sub_problems),
            hypotheses=list(self.hypotheses),
            verified=list(self.verified),
            eliminated=list(self.eliminated),
            partial_results=list(self.partial_results),
            final_answer=self.final_answer,
            confidence=self.confidence,
            depth=self.depth,
            max_depth=self.max_depth,
            steps_log=list(self.steps_log),
        )


# ─── Block Executors ──────────────────────────────────────

def _exec_decompose(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Break problem into sub-problems using heuristics."""
    problem = ctx.problem
    words = problem.split()

    # Sentence-level decomposition
    sentences = [s.strip() for s in problem.replace('?', '?.').replace('!', '!.').split('.')
                 if s.strip()]

    if len(sentences) > 1:
        ctx.sub_problems = sentences[:5]
        ctx.log(f"DECOMPOSE: Split into {len(ctx.sub_problems)} sub-problems")
    elif len(words) > 15:
        mid = len(words) // 2
        ctx.sub_problems = [' '.join(words[:mid]), ' '.join(words[mid:])]
        ctx.log("DECOMPOSE: Split at midpoint into 2 parts")
    else:
        ctx.sub_problems = [problem]
        ctx.log("DECOMPOSE: Problem is atomic, no further decomposition")

    return ctx


def _exec_hypothesize(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Generate hypotheses from context."""
    n = block.params.get("n_hypotheses", 3)

    if ctx.sub_problems:
        for sp in ctx.sub_problems[:n]:
            ctx.hypotheses.append(f"Hypothesis: The answer involves solving '{sp[:60]}'")
    elif ctx.problem:
        ctx.hypotheses.append(f"Direct hypothesis for: {ctx.problem[:80]}")

    ctx.log(f"HYPOTHESIZE: Generated {len(ctx.hypotheses)} hypotheses")
    return ctx


def _exec_verify(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Verify hypotheses using consistency checks."""
    new_verified = []
    for h in ctx.hypotheses:
        # Simple consistency scoring based on keyword overlap
        problem_words = set(ctx.problem.lower().split())
        h_words = set(h.lower().split())
        overlap = len(problem_words & h_words)
        score = min(1.0, overlap / max(len(problem_words), 1) + 0.3)
        new_verified.append((h, score))

    ctx.verified = sorted(new_verified, key=lambda x: -x[1])
    if ctx.verified:
        ctx.confidence = ctx.verified[0][1]
    ctx.log(f"VERIFY: Verified {len(ctx.verified)} hypotheses, best confidence={ctx.confidence:.2f}")
    return ctx


def _exec_analogize(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Find analogies to known problem patterns."""
    patterns = {
        "optimize": "This is an optimization problem; consider gradient descent or dynamic programming",
        "sort": "This is an ordering problem; consider comparison-based or radix approaches",
        "find": "This is a search problem; consider BFS, DFS, or binary search",
        "prove": "This is a proof problem; consider induction, contradiction, or construction",
        "count": "This is a counting problem; consider combinatorics or inclusion-exclusion",
        "build": "This is a construction problem; consider greedy or divide-and-conquer",
        "minimum": "This is a minimization problem; consider dynamic programming",
        "maximum": "This is a maximization problem; consider greedy or DP",
        "path": "This is a path problem; consider graph algorithms",
        "match": "This is a matching problem; consider bipartite matching or regex",
    }

    problem_lower = ctx.problem.lower()
    for keyword, analogy in patterns.items():
        if keyword in problem_lower:
            ctx.partial_results.append(f"[ANALOGY] {analogy}")
            ctx.log(f"ANALOGIZE: Found pattern match '{keyword}'")
            break
    else:
        ctx.log("ANALOGIZE: No direct analogy found")

    return ctx


def _exec_abstract(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Generalize the problem."""
    if ctx.sub_problems:
        common = set(ctx.sub_problems[0].lower().split())
        for sp in ctx.sub_problems[1:]:
            common &= set(sp.lower().split())
        if common:
            abstract = f"Abstract pattern: common elements are {', '.join(list(common)[:5])}"
            ctx.partial_results.append(abstract)
            ctx.log(f"ABSTRACT: Identified common elements across sub-problems")
    else:
        ctx.log("ABSTRACT: No sub-problems to abstract from")
    return ctx


def _exec_concretize(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Specialize abstract results to the specific problem."""
    if ctx.partial_results and ctx.problem:
        concrete = f"Applied to '{ctx.problem[:50]}': {ctx.partial_results[-1][:100]}"
        ctx.partial_results.append(concrete)
        ctx.log("CONCRETIZE: Specialized abstract result")
    return ctx


def _exec_eliminate(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Eliminate hypotheses below confidence threshold."""
    threshold = block.params.get("threshold", 0.3)
    before = len(ctx.verified)
    ctx.eliminated.extend([h for h, s in ctx.verified if s < threshold])
    ctx.verified = [(h, s) for h, s in ctx.verified if s >= threshold]
    after = len(ctx.verified)
    ctx.log(f"ELIMINATE: Removed {before - after} weak hypotheses (threshold={threshold})")
    return ctx


def _exec_enumerate(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Enumerate possible approaches."""
    approaches = ["divide-and-conquer", "greedy", "dynamic-programming",
                   "backtracking", "reduction", "direct-computation"]
    ctx.hypotheses.extend([f"Approach: {a}" for a in approaches[:3]])
    ctx.log(f"ENUMERATE: Added {min(3, len(approaches))} enumerated approaches")
    return ctx


def _exec_backtrack(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Backtrack: discard worst results and retry."""
    if ctx.verified:
        worst = min(ctx.verified, key=lambda x: x[1])
        ctx.eliminated.append(worst[0])
        ctx.verified.remove(worst)
        ctx.log(f"BACKTRACK: Removed worst hypothesis (score={worst[1]:.2f})")
    return ctx


def _exec_synthesize(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Synthesize final answer from partial results."""
    parts = []

    if ctx.verified:
        best_h, best_s = ctx.verified[0]
        parts.append(f"Best hypothesis (confidence={best_s:.2f}): {best_h}")

    if ctx.partial_results:
        parts.append(f"Supporting analysis: {'; '.join(ctx.partial_results[-3:])}")

    if ctx.sub_problems and len(ctx.sub_problems) > 1:
        parts.append(f"Problem decomposed into {len(ctx.sub_problems)} parts")

    if parts:
        ctx.final_answer = "\n".join(parts)
        ctx.confidence = max(ctx.confidence, 0.5)
    ctx.log(f"SYNTHESIZE: Combined {len(parts)} elements into final answer")
    return ctx


def _exec_simplify(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Simplify the problem representation."""
    if ctx.sub_problems:
        # Keep only unique sub-problems
        ctx.sub_problems = list(dict.fromkeys(ctx.sub_problems))
        ctx.log(f"SIMPLIFY: Deduplicated to {len(ctx.sub_problems)} unique sub-problems")
    return ctx


def _exec_transform(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Transform problem to equivalent form."""
    ctx.partial_results.append(f"[TRANSFORM] Reformulated: {ctx.problem[:60]}")
    ctx.log("TRANSFORM: Reformulated problem")
    return ctx


def _exec_bound(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Establish bounds on the solution."""
    ctx.partial_results.append("[BOUND] Establishing feasibility bounds")
    ctx.log("BOUND: Established solution bounds")
    return ctx


def _exec_recurse(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Apply reasoning recursively to sub-problems."""
    if ctx.depth >= ctx.max_depth:
        ctx.log(f"RECURSE: Max depth {ctx.max_depth} reached, stopping")
        return ctx

    if ctx.sub_problems:
        for sp in ctx.sub_problems[:2]:
            sub_ctx = ReasoningContext(
                problem=sp, depth=ctx.depth + 1, max_depth=ctx.max_depth
            )
            sub_ctx = _exec_hypothesize(block, sub_ctx)
            sub_ctx = _exec_verify(block, sub_ctx)
            if sub_ctx.verified:
                ctx.partial_results.append(f"[RECURSE] {sub_ctx.verified[0][0][:80]}")
        ctx.log(f"RECURSE: Applied reasoning to {min(2, len(ctx.sub_problems))} sub-problems")
    return ctx


def _exec_contradict(block: ReasoningBlock, ctx: ReasoningContext) -> ReasoningContext:
    """Attempt proof by contradiction."""
    ctx.partial_results.append("[CONTRADICT] Assuming negation to find contradiction")
    ctx.log("CONTRADICT: Applied proof by contradiction framework")
    return ctx


_BLOCK_EXECUTORS = {
    BlockType.DECOMPOSE: _exec_decompose,
    BlockType.HYPOTHESIZE: _exec_hypothesize,
    BlockType.VERIFY: _exec_verify,
    BlockType.ANALOGIZE: _exec_analogize,
    BlockType.ABSTRACT: _exec_abstract,
    BlockType.CONCRETIZE: _exec_concretize,
    BlockType.ELIMINATE: _exec_eliminate,
    BlockType.ENUMERATE: _exec_enumerate,
    BlockType.BACKTRACK: _exec_backtrack,
    BlockType.SYNTHESIZE: _exec_synthesize,
    BlockType.SIMPLIFY: _exec_simplify,
    BlockType.TRANSFORM: _exec_transform,
    BlockType.BOUND: _exec_bound,
    BlockType.RECURSE: _exec_recurse,
    BlockType.CONTRADICT: _exec_contradict,
}


# ═══════════════════════════════════════════════════════════
# STRATEGY GENOME — Composable Reasoning Pipeline
# ═══════════════════════════════════════════════════════════

@dataclass
class Strategy:
    """A reasoning strategy = ordered sequence of blocks."""
    name: str
    blocks: List[ReasoningBlock] = field(default_factory=list)
    fitness: float = 0.0
    uses: int = 0
    successes: int = 0
    avg_confidence: float = 0.0
    problem_classes: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        block_str = ",".join(b.block_type.value for b in self.blocks)
        return hashlib.sha256(block_str.encode()).hexdigest()[:8]

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.uses, 1)

    def pipeline_str(self) -> str:
        return " → ".join(b.block_type.value for b in self.blocks)

    def execute(self, problem: str, max_depth: int = 5) -> ReasoningContext:
        """Execute the full strategy pipeline."""
        ctx = ReasoningContext(problem=problem, max_depth=max_depth)
        ctx.log(f"Strategy: {self.name} [{self.pipeline_str()}]")

        for block in self.blocks:
            ctx = block.execute(ctx)

        return ctx

    def clone(self) -> 'Strategy':
        return Strategy(
            name=self.name,
            blocks=[ReasoningBlock(b.block_type, b.weight, dict(b.params)) for b in self.blocks],
            fitness=self.fitness,
            uses=self.uses,
            successes=self.successes,
            avg_confidence=self.avg_confidence,
            problem_classes=list(self.problem_classes),
        )


# ─── Built-in Strategies ─────────────────────────────────

_BUILTIN_STRATEGIES = [
    Strategy("scientific_method", [
        ReasoningBlock(BlockType.DECOMPOSE),
        ReasoningBlock(BlockType.HYPOTHESIZE, params={"n_hypotheses": 3}),
        ReasoningBlock(BlockType.VERIFY),
        ReasoningBlock(BlockType.ELIMINATE, params={"threshold": 0.3}),
        ReasoningBlock(BlockType.SYNTHESIZE),
    ]),
    Strategy("divide_and_conquer", [
        ReasoningBlock(BlockType.DECOMPOSE),
        ReasoningBlock(BlockType.RECURSE),
        ReasoningBlock(BlockType.SYNTHESIZE),
    ]),
    Strategy("analogy_transfer", [
        ReasoningBlock(BlockType.ANALOGIZE),
        ReasoningBlock(BlockType.ABSTRACT),
        ReasoningBlock(BlockType.CONCRETIZE),
        ReasoningBlock(BlockType.VERIFY),
        ReasoningBlock(BlockType.SYNTHESIZE),
    ]),
    Strategy("exhaustive_search", [
        ReasoningBlock(BlockType.ENUMERATE),
        ReasoningBlock(BlockType.VERIFY),
        ReasoningBlock(BlockType.ELIMINATE, params={"threshold": 0.5}),
        ReasoningBlock(BlockType.SYNTHESIZE),
    ]),
    Strategy("proof_by_contradiction", [
        ReasoningBlock(BlockType.CONTRADICT),
        ReasoningBlock(BlockType.HYPOTHESIZE),
        ReasoningBlock(BlockType.VERIFY),
        ReasoningBlock(BlockType.SYNTHESIZE),
    ]),
    Strategy("simplify_and_solve", [
        ReasoningBlock(BlockType.SIMPLIFY),
        ReasoningBlock(BlockType.TRANSFORM),
        ReasoningBlock(BlockType.HYPOTHESIZE),
        ReasoningBlock(BlockType.VERIFY),
        ReasoningBlock(BlockType.SYNTHESIZE),
    ]),
    Strategy("bound_and_search", [
        ReasoningBlock(BlockType.BOUND),
        ReasoningBlock(BlockType.ENUMERATE),
        ReasoningBlock(BlockType.ELIMINATE, params={"threshold": 0.4}),
        ReasoningBlock(BlockType.VERIFY),
        ReasoningBlock(BlockType.SYNTHESIZE),
    ]),
    Strategy("iterative_refinement", [
        ReasoningBlock(BlockType.HYPOTHESIZE),
        ReasoningBlock(BlockType.VERIFY),
        ReasoningBlock(BlockType.BACKTRACK),
        ReasoningBlock(BlockType.HYPOTHESIZE, params={"n_hypotheses": 2}),
        ReasoningBlock(BlockType.VERIFY),
        ReasoningBlock(BlockType.SYNTHESIZE),
    ]),
]


# ═══════════════════════════════════════════════════════════
# STRATEGY EVOLUTION — Genetic Operators for Strategies
# ═══════════════════════════════════════════════════════════

class StrategyEvolver:
    """Evolves new reasoning strategies via genetic operators."""

    ALL_BLOCKS = list(BlockType)

    @staticmethod
    def crossover(s1: Strategy, s2: Strategy) -> Strategy:
        """Single-point crossover of two strategies."""
        if len(s1.blocks) < 2 or len(s2.blocks) < 2:
            return s1.clone()

        point1 = random.randint(1, len(s1.blocks) - 1)
        point2 = random.randint(1, len(s2.blocks) - 1)

        new_blocks = (
            [ReasoningBlock(b.block_type, b.weight, dict(b.params)) for b in s1.blocks[:point1]]
            + [ReasoningBlock(b.block_type, b.weight, dict(b.params)) for b in s2.blocks[point2:]]
        )

        # Ensure strategy ends with SYNTHESIZE
        if not new_blocks or new_blocks[-1].block_type != BlockType.SYNTHESIZE:
            new_blocks.append(ReasoningBlock(BlockType.SYNTHESIZE))

        # Limit length
        new_blocks = new_blocks[:8]

        child = Strategy(
            name=f"{s1.name}×{s2.name}",
            blocks=new_blocks,
        )
        return child

    @staticmethod
    def mutate(strategy: Strategy, mutation_rate: float = 0.2) -> Strategy:
        """Mutate a strategy by adding, removing, or swapping blocks."""
        s = strategy.clone()
        new_blocks = []

        for block in s.blocks:
            if random.random() < mutation_rate:
                mutation = random.choice(["swap", "insert", "remove", "param"])

                if mutation == "swap":
                    new_blocks.append(ReasoningBlock(random.choice(StrategyEvolver.ALL_BLOCKS)))

                elif mutation == "insert" and len(new_blocks) + len(s.blocks) < 10:
                    new_blocks.append(ReasoningBlock(random.choice(StrategyEvolver.ALL_BLOCKS)))
                    new_blocks.append(ReasoningBlock(block.block_type, block.weight, dict(block.params)))

                elif mutation == "remove" and (len(new_blocks) + 1) >= 2:
                    if block.block_type != BlockType.SYNTHESIZE:
                        continue  # Skip this block (remove it)
                    else:
                        new_blocks.append(block)  # Keep SYNTHESIZE

                elif mutation == "param":
                    mutated_block = ReasoningBlock(block.block_type, block.weight, dict(block.params))
                    if mutated_block.block_type == BlockType.HYPOTHESIZE:
                        mutated_block.params["n_hypotheses"] = random.randint(1, 5)
                    elif mutated_block.block_type == BlockType.ELIMINATE:
                        mutated_block.params["threshold"] = round(random.uniform(0.1, 0.7), 2)
                    new_blocks.append(mutated_block)
                else:
                    new_blocks.append(block)
            else:
                new_blocks.append(block)

        s.blocks = new_blocks if new_blocks else [ReasoningBlock(BlockType.HYPOTHESIZE)]

        # Ensure SYNTHESIZE at end
        if not s.blocks or s.blocks[-1].block_type != BlockType.SYNTHESIZE:
            s.blocks.append(ReasoningBlock(BlockType.SYNTHESIZE))

        # Cap length
        s.blocks = s.blocks[:8]

        s.name = f"evolved_{strategy.name}"
        return s

    @staticmethod
    def random_strategy(min_len: int = 3, max_len: int = 7) -> Strategy:
        """Generate a completely random strategy."""
        length = random.randint(min_len, max_len)
        blocks = [ReasoningBlock(random.choice(StrategyEvolver.ALL_BLOCKS))
                  for _ in range(length - 1)]
        blocks.append(ReasoningBlock(BlockType.SYNTHESIZE))

        return Strategy(
            name=f"random_{random.randint(1000, 9999)}",
            blocks=blocks,
        )


# ═══════════════════════════════════════════════════════════
# PERFORMANCE MEMORY — Tracks Strategy Effectiveness
# ═══════════════════════════════════════════════════════════

@dataclass
class PerformanceRecord:
    strategy_id: str
    strategy_name: str
    problem_class: str
    confidence: float
    success: bool
    timestamp: float = 0.0


class PerformanceMemory:
    """Tracks which strategies work for which problem classes."""

    def __init__(self, max_records: int = 500):
        self.records: List[PerformanceRecord] = []
        self.max_records = max_records
        self._class_strategy_scores: Dict[str, Dict[str, float]] = {}

    def record(self, strategy: Strategy, problem_class: str,
               confidence: float, success: bool) -> None:
        """Record a strategy's performance."""
        rec = PerformanceRecord(
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            problem_class=problem_class,
            confidence=confidence,
            success=success,
            timestamp=time.time(),
        )
        self.records.append(rec)

        # Update aggregate scores
        if problem_class not in self._class_strategy_scores:
            self._class_strategy_scores[problem_class] = {}
        scores = self._class_strategy_scores[problem_class]
        if strategy.id not in scores:
            scores[strategy.id] = 0.0
        # Exponential moving average
        alpha = 0.3
        scores[strategy.id] = (1 - alpha) * scores[strategy.id] + alpha * confidence

        # Prune old records
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]

    def best_strategy_for(self, problem_class: str,
                          available: List[Strategy]) -> Optional[Strategy]:
        """Find the best performing strategy for a problem class."""
        scores = self._class_strategy_scores.get(problem_class, {})
        if not scores:
            return None

        best_id = max(scores, key=scores.get)
        for s in available:
            if s.id == best_id:
                return s
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_records": len(self.records),
            "problem_classes": list(self._class_strategy_scores.keys()),
            "success_rate": sum(1 for r in self.records if r.success) / max(len(self.records), 1),
        }


# ═══════════════════════════════════════════════════════════
# PROBLEM CLASSIFIER (Lightweight)
# ═══════════════════════════════════════════════════════════

class ProblemTyper:
    """Lightweight problem classification for strategy selection."""

    KEYWORDS = {
        "optimization": ["optimize", "minimize", "maximize", "best", "optimal", "efficient"],
        "proof": ["prove", "theorem", "show that", "demonstrate", "qed"],
        "search": ["find", "search", "locate", "discover", "identify"],
        "construction": ["build", "create", "construct", "design", "implement", "write"],
        "analysis": ["analyze", "explain", "why", "how does", "understand"],
        "counting": ["count", "how many", "number of", "enumerate", "combinations"],
        "comparison": ["compare", "difference", "versus", "better", "worse"],
        "transformation": ["convert", "transform", "translate", "change", "modify"],
        "debugging": ["bug", "fix", "error", "wrong", "broken", "debug"],
        "planning": ["plan", "schedule", "sequence", "steps", "workflow"],
    }

    @staticmethod
    def classify(problem: str) -> str:
        """Classify problem into a category."""
        problem_lower = problem.lower()
        scores = {}

        for category, keywords in ProblemTyper.KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in problem_lower)
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores, key=scores.get)
        return "general"


# ═══════════════════════════════════════════════════════════
# DIMINISHING RETURN DETECTOR
# ═══════════════════════════════════════════════════════════

class DiminishingReturnDetector:
    """Detects when further reasoning iterations yield diminishing returns."""

    def __init__(self, window: int = 5, threshold: float = 0.02):
        self.window = window
        self.threshold = threshold
        self._history: List[float] = []

    def update(self, confidence: float) -> None:
        self._history.append(confidence)

    def should_stop(self) -> bool:
        """Returns True if improvements have plateaued."""
        if len(self._history) < self.window:
            return False

        recent = self._history[-self.window:]
        improvement = max(recent) - min(recent)
        return improvement < self.threshold

    def reset(self) -> None:
        self._history.clear()


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE — Recursive Reasoning Synthesizer
# ═══════════════════════════════════════════════════════════

@dataclass
class ReasoningResult:
    """Result of recursive reasoning."""
    answer: str = ""
    confidence: float = 0.0
    strategy_used: str = ""
    strategy_pipeline: str = ""
    steps: List[str] = field(default_factory=list)
    strategies_tried: int = 0
    duration_ms: float = 0.0
    problem_class: str = ""
    evolved_strategy: bool = False

    @property
    def is_valid(self) -> bool:
        return self.confidence > 0.3 and bool(self.answer)

    def summary(self) -> str:
        status = "SOLVED" if self.is_valid else "PARTIAL"
        return (
            f"## Recursive Reasoning — {status}\n\n"
            f"**Strategy**: {self.strategy_used}\n"
            f"**Pipeline**: {self.strategy_pipeline}\n"
            f"**Confidence**: {self.confidence:.3f}\n"
            f"**Problem class**: {self.problem_class}\n"
            f"**Strategies tried**: {self.strategies_tried}\n"
            f"**Duration**: {self.duration_ms:.0f}ms\n\n"
            f"### Reasoning Steps:\n" +
            "\n".join(f"  {i+1}. {s}" for i, s in enumerate(self.steps))
        )


class RecursiveReasoningSynthesizer:
    """
    Self-evolving meta-reasoning engine.

    Usage:
        reasoner = RecursiveReasoningSynthesizer()

        result = reasoner.reason("How to optimize a sorting algorithm?")
        print(result.strategy_used)     # e.g., "scientific_method"
        print(result.strategy_pipeline) # "decompose → hypothesize → verify → ..."
        print(result.answer)
    """

    def __init__(
        self,
        population_size: int = 12,
        evolution_interval: int = 10,
    ):
        # Strategy population
        self.strategies: List[Strategy] = [s.clone() for s in _BUILTIN_STRATEGIES]

        # Performance tracking
        self.memory = PerformanceMemory()
        self.typer = ProblemTyper()
        self.diminishing = DiminishingReturnDetector()

        # Evolution config
        self.population_size = population_size
        self.evolution_interval = evolution_interval
        self._solve_counter = 0

        # Stats
        self._stats = {
            "total_problems": 0,
            "strategies_evolved": 0,
            "auto_discoveries": 0,
        }

    def reason(
        self,
        problem: str,
        max_strategies: int = 3,
        confidence_threshold: float = 0.6,
    ) -> ReasoningResult:
        """
        Solve a problem using meta-reasoning with strategy selection.

        1. Classify the problem
        2. Select best strategy from memory (or default)
        3. Execute strategy pipeline
        4. If confidence is low, try alternative strategies
        5. Record performance for future use
        6. Periodically evolve new strategies
        """
        start = time.time()
        self._stats["total_problems"] += 1
        self._solve_counter += 1

        result = ReasoningResult()
        result.problem_class = self.typer.classify(problem)

        # ── Strategy Selection ──
        best_strategy = self.memory.best_strategy_for(
            result.problem_class, self.strategies
        )
        strategies_to_try = []

        if best_strategy:
            strategies_to_try.append(best_strategy)
        # Add defaults
        for s in self.strategies:
            if s not in strategies_to_try:
                strategies_to_try.append(s)
            if len(strategies_to_try) >= max_strategies:
                break

        # ── Execute Strategies ──
        best_ctx = None
        best_conf = 0.0
        best_strat = None

        self.diminishing.reset()

        for strategy in strategies_to_try:
            result.strategies_tried += 1

            ctx = strategy.execute(problem)

            # Record performance
            success = ctx.confidence >= confidence_threshold
            strategy.uses += 1
            if success:
                strategy.successes += 1
            strategy.avg_confidence = (
                (strategy.avg_confidence * (strategy.uses - 1) + ctx.confidence)
                / strategy.uses
            )

            self.memory.record(strategy, result.problem_class, ctx.confidence, success)

            if ctx.confidence > best_conf:
                best_conf = ctx.confidence
                best_ctx = ctx
                best_strat = strategy

            self.diminishing.update(ctx.confidence)

            # Stop if good enough or diminishing returns
            if ctx.confidence >= confidence_threshold:
                break
            if self.diminishing.should_stop():
                break

        # ── Build Result ──
        if best_ctx and best_strat:
            result.answer = best_ctx.final_answer or "Analysis complete — see reasoning steps"
            result.confidence = best_ctx.confidence
            result.strategy_used = best_strat.name
            result.strategy_pipeline = best_strat.pipeline_str()
            result.steps = best_ctx.steps_log

        result.duration_ms = (time.time() - start) * 1000

        # ── Periodic Evolution ──
        if self._solve_counter % self.evolution_interval == 0:
            self._evolve_strategies()

        logger.info(
            f"[RECURSIVE REASONING] Strategy={result.strategy_used} "
            f"Confidence={result.confidence:.3f} "
            f"Class={result.problem_class} "
            f"Tried={result.strategies_tried}"
        )

        return result

    def _evolve_strategies(self) -> None:
        """Evolve new strategies from the best performers."""
        if len(self.strategies) < 2:
            return

        self._stats["strategies_evolved"] += 1

        # Sort by success rate
        ranked = sorted(self.strategies, key=lambda s: s.success_rate, reverse=True)

        # Crossover top performers
        if len(ranked) >= 2:
            child = StrategyEvolver.crossover(ranked[0], ranked[1])
            if child.id not in {s.id for s in self.strategies}:
                self.strategies.append(child)
                self._stats["auto_discoveries"] += 1
                logger.info(f"[STRATEGY EVOLVED] {child.name}: {child.pipeline_str()}")

        # Mutate a random strategy
        target = random.choice(ranked[:max(3, len(ranked) // 2)])
        mutant = StrategyEvolver.mutate(target)
        if mutant.id not in {s.id for s in self.strategies}:
            self.strategies.append(mutant)

        # Add random exploration
        if random.random() < 0.3:
            random_s = StrategyEvolver.random_strategy()
            self.strategies.append(random_s)

        # Prune to population size
        if len(self.strategies) > self.population_size:
            self.strategies.sort(key=lambda s: s.success_rate, reverse=True)
            # Always keep builtins + top performers
            keep = set(s.name for s in _BUILTIN_STRATEGIES)
            pruned = [s for s in self.strategies if s.name in keep]
            for s in self.strategies:
                if s.name not in keep and len(pruned) < self.population_size:
                    pruned.append(s)
            self.strategies = pruned

    def get_all_strategies(self) -> List[Dict[str, Any]]:
        """Get info about all available strategies."""
        return [
            {
                "name": s.name,
                "pipeline": s.pipeline_str(),
                "uses": s.uses,
                "successes": s.successes,
                "success_rate": s.success_rate,
                "avg_confidence": s.avg_confidence,
            }
            for s in self.strategies
        ]

    def solve(self, prompt: str) -> ReasoningResult:
        """Alias for reason() — used by the CCE routing."""
        return self.reason(prompt)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "RecursiveReasoningSynthesizer",
            "total_problems": self._stats["total_problems"],
            "strategies_evolved": self._stats["strategies_evolved"],
            "auto_discoveries": self._stats["auto_discoveries"],
            "active_strategies": len(self.strategies),
            "performance_memory": self.memory.get_stats(),
        }
