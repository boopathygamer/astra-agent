"""
Real-Time Learning Engine — Online Learning + Pattern Extraction + Skill Profiling
═════════════════════════════════════════════════════════════════════════════════════
Learns from every interaction in real time — no batch retraining needed.
Tracks strategy effectiveness, extracts patterns, and maintains skill profiles.

No LLM, no GPU — pure algorithmic online learning.

Architecture:
  Interaction → Pattern Extractor → Strategy Tracker → Skill Profiler → Feedback
                       │                    │                  │
                       ▼                    ▼                  ▼
               Pattern Store        Strategy Scores       Skill Map
                       │                    │                  │
                       └────────────────────┼──────────────────┘
                                            ▼
                                    Learning Report

Key features:
  • Online learning — updates after every interaction (no retraining)
  • Pattern extraction — discovers recurring problem/solution patterns
  • Strategy evolution — tracks which strategies work for which domains
  • Skill profiling — maintains proficiency levels across 25+ domains
  • Adaptive learning rate — learns faster from novel inputs, slower from familiar
"""

import hashlib
import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════

class SkillDomain(Enum):
    ARITHMETIC = "arithmetic"
    ALGEBRA = "algebra"
    CALCULUS = "calculus"
    LINEAR_ALGEBRA = "linear_algebra"
    STATISTICS = "statistics"
    NUMBER_THEORY = "number_theory"
    GEOMETRY = "geometry"
    COMBINATORICS = "combinatorics"
    CLASSICAL_MECHANICS = "classical_mechanics"
    ELECTROMAGNETISM = "electromagnetism"
    THERMODYNAMICS = "thermodynamics"
    QUANTUM_PHYSICS = "quantum_physics"
    ALGORITHMS = "algorithms"
    DATA_STRUCTURES = "data_structures"
    SYSTEM_DESIGN = "system_design"
    DEBUGGING = "debugging"
    CODE_GENERATION = "code_generation"
    TESTING = "testing"
    BOOLEAN_LOGIC = "boolean_logic"
    FORMAL_PROOFS = "formal_proofs"
    NATURAL_LANGUAGE = "natural_language"
    PATTERN_MATCHING = "pattern_matching"
    OPTIMIZATION = "optimization"
    PLANNING = "planning"
    GENERAL = "general"


@dataclass
class SolvedPattern:
    """A discovered pattern from solved problems."""
    pattern_id: str = ""
    problem_signature: str = ""  # Abstract representation of problem structure
    solution_strategy: str = ""
    domain: SkillDomain = SkillDomain.GENERAL
    occurrences: int = 1
    success_rate: float = 1.0
    avg_solve_time_ms: float = 0.0
    total_solve_time_ms: float = 0.0
    examples: Deque = field(default_factory=lambda: deque(maxlen=5))
    discovered_at: float = 0.0
    last_seen: float = 0.0

    def __post_init__(self):
        if not self.pattern_id:
            raw = f"{self.problem_signature}:{self.solution_strategy}"
            self.pattern_id = hashlib.sha256(raw.encode()).hexdigest()[:12]
        if not self.discovered_at:
            self.discovered_at = time.time()
        if not self.last_seen:
            self.last_seen = self.discovered_at


@dataclass
class SkillProfile:
    """Proficiency level for a single skill domain."""
    domain: SkillDomain = SkillDomain.GENERAL
    level: float = 0.5                       # 0.0 (novice) → 1.0 (expert)
    problems_attempted: int = 0
    problems_solved: int = 0
    total_time_ms: float = 0.0
    recent_success_rate: float = 0.5         # Moving average
    best_strategy: str = ""
    last_updated: float = 0.0

    @property
    def accuracy(self) -> float:
        return self.problems_solved / max(self.problems_attempted, 1)

    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / max(self.problems_solved, 1)


@dataclass
class StrategyRecord:
    """Track record for a problem-solving strategy."""
    name: str = ""
    domain: SkillDomain = SkillDomain.GENERAL
    uses: int = 0
    successes: int = 0
    failures: int = 0
    total_time_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.uses, 1)

    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / max(self.uses, 1)


@dataclass
class LearningEvent:
    """A single learning event from an interaction."""
    event_id: str = ""
    domain: SkillDomain = SkillDomain.GENERAL
    problem_signature: str = ""
    strategy_used: str = ""
    success: bool = True
    solve_time_ms: float = 0.0
    novelty: float = 0.5                     # 0 = familiar, 1 = completely new
    confidence: float = 0.8
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.event_id:
            self.event_id = hashlib.sha256(
                f"{self.problem_signature}:{time.time()}".encode()
            ).hexdigest()[:12]
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class LearningReport:
    """Report from a learning cycle."""
    events_processed: int = 0
    patterns_discovered: int = 0
    patterns_reinforced: int = 0
    strategies_updated: int = 0
    skills_improved: List[str] = field(default_factory=list)
    skills_degraded: List[str] = field(default_factory=list)
    novelty_score: float = 0.0
    learning_rate: float = 0.1
    current_skill_levels: Dict[str, float] = field(default_factory=dict)
    best_strategies: Dict[str, str] = field(default_factory=dict)
    duration_ms: float = 0.0

    def summary(self) -> str:
        lines = [
            f"## Real-Time Learning Report",
            f"**Events processed**: {self.events_processed}",
            f"**Patterns**: {self.patterns_discovered} new, {self.patterns_reinforced} reinforced",
            f"**Novelty**: {self.novelty_score:.0%}",
            f"**Learning rate**: {self.learning_rate:.3f}",
        ]
        if self.skills_improved:
            lines.append(f"**Skills improved**: {', '.join(self.skills_improved)}")
        if self.skills_degraded:
            lines.append(f"**Skills degraded**: {', '.join(self.skills_degraded)}")
        if self.current_skill_levels:
            lines.append("\n### Skill Levels:")
            for domain, level in sorted(
                self.current_skill_levels.items(), key=lambda x: -x[1]
            )[:10]:
                bar = "█" * int(level * 10) + "░" * (10 - int(level * 10))
                lines.append(f"  {bar} {level:.0%} — {domain}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# PATTERN EXTRACTOR
# ═══════════════════════════════════════════════════════════

class PatternExtractor:
    """Extracts abstract patterns from problem/solution pairs."""

    # Problem type signatures based on keyword clusters
    _SIGNATURE_RULES: Dict[str, List[str]] = {
        "arithmetic_expression": ["calculate", "compute", "+", "-", "*", "/", "sum", "product"],
        "equation_solving": ["solve", "equation", "find x", "root", "="],
        "optimization_problem": ["optimize", "minimize", "maximize", "best", "optimal"],
        "sorting_problem": ["sort", "order", "arrange", "rank"],
        "search_problem": ["find", "search", "locate", "lookup", "query"],
        "proof_problem": ["prove", "theorem", "lemma", "show that", "demonstrate"],
        "code_generation": ["implement", "write", "create", "build", "function", "class"],
        "debugging_problem": ["fix", "bug", "error", "debug", "crash", "issue"],
        "analysis_problem": ["analyze", "examine", "investigate", "evaluate", "assess"],
        "design_problem": ["design", "architect", "plan", "structure", "pattern"],
    }

    @classmethod
    def extract_signature(cls, problem: str) -> str:
        """Extract an abstract problem signature."""
        problem_lower = problem.lower()
        scores: Dict[str, int] = {}

        for sig, keywords in cls._SIGNATURE_RULES.items():
            score = sum(1 for kw in keywords if kw in problem_lower)
            if score > 0:
                scores[sig] = score

        if scores:
            return max(scores, key=scores.get)
        return "general_problem"

    @classmethod
    def detect_domain(cls, problem: str) -> SkillDomain:
        """Detect the skill domain of a problem."""
        problem_lower = problem.lower()
        domain_keywords: Dict[SkillDomain, List[str]] = {
            SkillDomain.ARITHMETIC: ["add", "subtract", "multiply", "divide", "sum", "product", "calculate"],
            SkillDomain.ALGEBRA: ["equation", "solve", "variable", "polynomial", "factor"],
            SkillDomain.CALCULUS: ["integral", "derivative", "limit", "differential", "taylor"],
            SkillDomain.LINEAR_ALGEBRA: ["matrix", "vector", "eigenvalue", "determinant", "linear"],
            SkillDomain.STATISTICS: ["mean", "median", "variance", "probability", "distribution"],
            SkillDomain.CLASSICAL_MECHANICS: ["force", "velocity", "acceleration", "momentum", "energy"],
            SkillDomain.ELECTROMAGNETISM: ["charge", "electric", "magnetic", "voltage", "current"],
            SkillDomain.ALGORITHMS: ["algorithm", "sort", "search", "graph", "tree", "dynamic programming"],
            SkillDomain.DATA_STRUCTURES: ["array", "list", "hash", "stack", "queue", "heap"],
            SkillDomain.CODE_GENERATION: ["implement", "write", "function", "class", "code", "program"],
            SkillDomain.DEBUGGING: ["fix", "bug", "error", "debug", "crash"],
            SkillDomain.BOOLEAN_LOGIC: ["boolean", "logic", "truth table", "and", "or", "not", "implies"],
            SkillDomain.FORMAL_PROOFS: ["prove", "theorem", "lemma", "axiom", "qed"],
            SkillDomain.OPTIMIZATION: ["optimize", "minimize", "maximize", "efficient"],
            SkillDomain.PLANNING: ["plan", "schedule", "roadmap", "strategy", "phase"],
        }
        best_domain = SkillDomain.GENERAL
        best_score = 0
        for domain, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw in problem_lower)
            if score > best_score:
                best_score = score
                best_domain = domain
        return best_domain

    @classmethod
    def extract_strategy(cls, solution: str) -> str:
        """Infer the strategy used from the solution text."""
        sol_lower = solution.lower()
        strategies = {
            "decomposition": ["step", "first", "then", "next", "finally", "part"],
            "formula_application": ["formula", "equation", "plug in", "substitute", "apply"],
            "brute_force": ["try all", "iterate", "enumerate", "exhaustive"],
            "pattern_matching": ["pattern", "similar", "like", "analogy", "template"],
            "divide_and_conquer": ["divide", "conquer", "split", "merge", "recursive"],
            "greedy": ["greedy", "best choice", "locally optimal", "pick the largest"],
            "dynamic_programming": ["dp", "dynamic programming", "memoize", "subproblem"],
            "mathematical_derivation": ["derive", "proof", "therefore", "thus", "hence"],
            "heuristic": ["heuristic", "rule of thumb", "approximate", "estimate"],
            "direct_computation": ["compute", "calculate", "result"],
        }
        best_strategy = "direct_computation"
        best_score = 0
        for strategy, keywords in strategies.items():
            score = sum(1 for kw in keywords if kw in sol_lower)
            if score > best_score:
                best_score = score
                best_strategy = strategy
        return best_strategy


# ═══════════════════════════════════════════════════════════
# LEARNING RATE SCHEDULER
# ═══════════════════════════════════════════════════════════

class LearningRateScheduler:
    """
    Adaptive learning rate based on novelty and performance trajectory.
    Novel inputs → higher learning rate (learn faster from new material).
    Familiar inputs → lower learning rate (avoid overwriting stable knowledge).
    """

    BASE_RATE = 0.1
    MIN_RATE = 0.01
    MAX_RATE = 0.5

    def __init__(self):
        self._seen_signatures: Dict[str, int] = defaultdict(int)
        self._recent_novelties: Deque[float] = deque(maxlen=50)

    def compute_novelty(self, signature: str) -> float:
        """Compute novelty score for a problem signature."""
        count = self._seen_signatures.get(signature, 0)
        novelty = math.exp(-count * 0.3)  # Exponential novelty decay
        self._seen_signatures[signature] += 1
        self._recent_novelties.append(novelty)
        return novelty

    def get_rate(self, novelty: float) -> float:
        """Get adaptive learning rate based on novelty."""
        rate = self.BASE_RATE + (self.MAX_RATE - self.BASE_RATE) * novelty
        # Smooth with recent average
        if self._recent_novelties:
            avg_novelty = sum(self._recent_novelties) / len(self._recent_novelties)
            rate = rate * 0.7 + (self.BASE_RATE + (self.MAX_RATE - self.BASE_RATE) * avg_novelty) * 0.3
        return max(self.MIN_RATE, min(self.MAX_RATE, rate))


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE
# ═══════════════════════════════════════════════════════════

class RealtimeLearningEngine:
    """
    Online learning engine that improves from every interaction.

    Usage:
        learner = RealtimeLearningEngine()

        # Record a successful learning event
        learner.learn("calculate 15 * 23", "15 * 23 = 345", success=True, time_ms=5.0)

        # Get best strategy for a domain
        strategy = learner.recommend_strategy(SkillDomain.ARITHMETIC)

        # Get skill profile
        profile = learner.get_skill_profile(SkillDomain.ALGORITHMS)

        # Full report
        report = learner.get_report()
        print(report.summary())
    """

    def __init__(self):
        self.extractor = PatternExtractor()
        self.scheduler = LearningRateScheduler()

        # Core stores
        self._patterns: Dict[str, SolvedPattern] = {}           # pattern_id → pattern
        self._strategies: Dict[str, Dict[str, StrategyRecord]] = defaultdict(dict)  # domain → {strategy → record}
        self._skills: Dict[SkillDomain, SkillProfile] = {
            d: SkillProfile(domain=d) for d in SkillDomain
        }
        self._history: Deque[LearningEvent] = deque(maxlen=1000)

        self._stats = {
            "events_total": 0, "patterns_total": 0, "strategies_total": 0,
            "total_learning_time_ms": 0.0,
        }

    def learn(self, problem: str, solution: str,
              success: bool = True, time_ms: float = 0.0,
              confidence: float = 0.8) -> LearningReport:
        """
        Learn from a single problem-solution interaction.
        Updates patterns, strategies, and skill profiles in real time.
        """
        start = time.time()
        report = LearningReport()

        # Extract features
        signature = self.extractor.extract_signature(problem)
        domain = self.extractor.detect_domain(problem)
        strategy = self.extractor.extract_strategy(solution)
        novelty = self.scheduler.compute_novelty(signature)
        lr = self.scheduler.get_rate(novelty)

        # Create learning event
        event = LearningEvent(
            domain=domain, problem_signature=signature,
            strategy_used=strategy, success=success,
            solve_time_ms=time_ms, novelty=novelty, confidence=confidence,
        )
        self._history.append(event)

        # Update patterns
        pattern_key = f"{signature}:{strategy}"
        pattern_id = hashlib.sha256(pattern_key.encode()).hexdigest()[:12]
        if pattern_id in self._patterns:
            pattern = self._patterns[pattern_id]
            pattern.occurrences += 1
            pattern.last_seen = time.time()
            pattern.total_solve_time_ms += time_ms
            pattern.avg_solve_time_ms = pattern.total_solve_time_ms / pattern.occurrences
            # Update success rate with moving average
            pattern.success_rate = pattern.success_rate * (1 - lr) + (1.0 if success else 0.0) * lr
            pattern.examples.append(problem[:100])
            report.patterns_reinforced += 1
        else:
            self._patterns[pattern_id] = SolvedPattern(
                pattern_id=pattern_id, problem_signature=signature,
                solution_strategy=strategy, domain=domain,
                success_rate=1.0 if success else 0.0,
                avg_solve_time_ms=time_ms, total_solve_time_ms=time_ms,
                examples=deque([problem[:100]], maxlen=5),
            )
            report.patterns_discovered += 1
            self._stats["patterns_total"] += 1

        # Update strategy tracking
        domain_key = domain.value
        if strategy not in self._strategies[domain_key]:
            self._strategies[domain_key][strategy] = StrategyRecord(
                name=strategy, domain=domain,
            )
            self._stats["strategies_total"] += 1
        rec = self._strategies[domain_key][strategy]
        rec.uses += 1
        if success:
            rec.successes += 1
        else:
            rec.failures += 1
        rec.total_time_ms += time_ms
        report.strategies_updated += 1

        # Update skill profile
        skill = self._skills[domain]
        old_level = skill.level
        skill.problems_attempted += 1
        if success:
            skill.problems_solved += 1
        skill.total_time_ms += time_ms
        skill.last_updated = time.time()

        # Exponential moving average for success rate
        skill.recent_success_rate = skill.recent_success_rate * (1 - lr) + (1.0 if success else 0.0) * lr

        # Update skill level (blends accuracy, recency, and volume)
        accuracy = skill.accuracy
        volume_factor = min(1.0, math.log1p(skill.problems_attempted) / 5)
        skill.level = accuracy * 0.6 + skill.recent_success_rate * 0.3 + volume_factor * 0.1

        # Find best strategy for this domain
        if self._strategies[domain_key]:
            best = max(self._strategies[domain_key].values(), key=lambda s: s.success_rate)
            skill.best_strategy = best.name

        if skill.level > old_level + 0.01:
            report.skills_improved.append(domain.value)
        elif skill.level < old_level - 0.01:
            report.skills_degraded.append(domain.value)

        # Build report
        report.events_processed = 1
        report.novelty_score = novelty
        report.learning_rate = lr
        report.current_skill_levels = {
            d.value: s.level for d, s in self._skills.items() if s.problems_attempted > 0
        }
        report.best_strategies = {
            d: max(strats.values(), key=lambda s: s.success_rate).name
            for d, strats in self._strategies.items() if strats
        }
        report.duration_ms = (time.time() - start) * 1000

        self._stats["events_total"] += 1
        self._stats["total_learning_time_ms"] += report.duration_ms
        return report

    def recommend_strategy(self, domain: SkillDomain) -> Optional[str]:
        """Recommend the best strategy for a given domain."""
        domain_key = domain.value
        strats = self._strategies.get(domain_key, {})
        if not strats:
            return None
        best = max(strats.values(), key=lambda s: s.success_rate * math.log1p(s.uses))
        return best.name

    def get_skill_profile(self, domain: SkillDomain) -> SkillProfile:
        """Get current skill profile for a domain."""
        return self._skills[domain]

    def get_all_skill_levels(self) -> Dict[str, float]:
        """Get all skill levels as a dict."""
        return {d.value: s.level for d, s in self._skills.items() if s.problems_attempted > 0}

    def get_pattern_count(self) -> int:
        return len(self._patterns)

    def get_top_patterns(self, n: int = 10) -> List[SolvedPattern]:
        """Get most-used patterns."""
        return sorted(self._patterns.values(), key=lambda p: -p.occurrences)[:n]

    def get_report(self) -> LearningReport:
        """Generate a comprehensive learning report."""
        report = LearningReport()
        report.events_processed = self._stats["events_total"]
        report.patterns_discovered = self._stats["patterns_total"]
        report.current_skill_levels = self.get_all_skill_levels()
        report.best_strategies = {
            d: max(strats.values(), key=lambda s: s.success_rate).name
            for d, strats in self._strategies.items() if strats
        }
        if self._history:
            report.novelty_score = sum(e.novelty for e in self._history) / len(self._history)
        return report

    def solve(self, prompt: str) -> LearningReport:
        """Natural language interface for CCE routing."""
        # Learn from the prompt itself and provide a report
        return self.learn(prompt, f"Processed: {prompt[:100]}", success=True, time_ms=1.0)

    def get_stats(self) -> Dict[str, Any]:
        active_skills = sum(1 for s in self._skills.values() if s.problems_attempted > 0)
        return {
            "engine": "RealtimeLearningEngine",
            "events_total": self._stats["events_total"],
            "patterns_total": self._stats["patterns_total"],
            "strategies_total": self._stats["strategies_total"],
            "active_skills": active_skills,
        }
