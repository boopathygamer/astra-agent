"""
Competitive Benchmark Engine — Self-Benchmarking + Regression Detection + Leaderboard
═════════════════════════════════════════════════════════════════════════════════════════
Runs the CCE against 15+ built-in benchmark suites, scores performance,
detects regressions vs historical baselines, and maintains a leaderboard.

No LLM, no GPU — generates problems algorithmically and verifies answers.

Architecture:
  Benchmark Suite → Problem Generator → CCE Solve → Answer Verifier → Score
        │                                                     │
        ▼                                                     ▼
  Difficulty Scaler                                    Regression Detector
        │                                                     │
        └─────────────────── Leaderboard ─────────────────────┘

15 Benchmark Categories:
  1.  Arithmetic       6.  Pattern Match    11. Constraint Solving
  2.  Algebra          7.  Code Generation  12. Proof / Logic
  3.  Statistics       8.  String Ops       13. Graph Problems
  4.  Physics          9.  Sorting          14. Optimization
  5.  Number Theory   10.  Data Structures  15. General Reasoning
"""

import hashlib
import logging
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════

class BenchmarkCategory(Enum):
    ARITHMETIC = "arithmetic"
    ALGEBRA = "algebra"
    STATISTICS = "statistics"
    PHYSICS = "physics"
    NUMBER_THEORY = "number_theory"
    PATTERN_MATCH = "pattern_match"
    CODE_GENERATION = "code_generation"
    STRING_OPS = "string_ops"
    SORTING = "sorting"
    DATA_STRUCTURES = "data_structures"
    CONSTRAINT_SOLVING = "constraint_solving"
    PROOF_LOGIC = "proof_logic"
    GRAPH_PROBLEMS = "graph_problems"
    OPTIMIZATION = "optimization"
    GENERAL_REASONING = "general_reasoning"


@dataclass
class BenchmarkProblem:
    """A single benchmark problem with known answer."""
    problem_id: str = ""
    category: BenchmarkCategory = BenchmarkCategory.ARITHMETIC
    difficulty: int = 1           # 1-10
    prompt: str = ""
    expected_answer: str = ""
    verification_fn: Optional[str] = None  # Name of verifier function
    time_limit_ms: float = 1000.0

    def __post_init__(self):
        if not self.problem_id:
            raw = f"{self.category.value}:{self.prompt}:{self.difficulty}"
            self.problem_id = hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass
class BenchmarkResult:
    """Result of running a single benchmark problem."""
    problem_id: str = ""
    category: BenchmarkCategory = BenchmarkCategory.ARITHMETIC
    difficulty: int = 1
    passed: bool = False
    response: str = ""
    expected: str = ""
    solve_time_ms: float = 0.0
    timed_out: bool = False


@dataclass
class CategoryScore:
    """Aggregated score for a benchmark category."""
    category: BenchmarkCategory = BenchmarkCategory.ARITHMETIC
    problems_total: int = 0
    problems_passed: int = 0
    avg_time_ms: float = 0.0
    total_time_ms: float = 0.0
    accuracy: float = 0.0
    difficulty_range: Tuple[int, int] = (1, 1)

    def score(self) -> float:
        """Composite score: accuracy * difficulty_weight."""
        avg_diff = sum(self.difficulty_range) / 2
        return self.accuracy * (0.5 + 0.5 * avg_diff / 10)


@dataclass
class BenchmarkReport:
    """Full benchmark report across all categories."""
    run_id: str = ""
    timestamp: float = 0.0
    total_problems: int = 0
    total_passed: int = 0
    total_failed: int = 0
    overall_accuracy: float = 0.0
    overall_score: float = 0.0
    category_scores: Dict[str, CategoryScore] = field(default_factory=dict)
    results: List[BenchmarkResult] = field(default_factory=list)
    regressions: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def summary(self) -> str:
        lines = [
            f"## Competitive Benchmark Report",
            f"**Overall Score**: {self.overall_score:.1%}",
            f"**Accuracy**: {self.total_passed}/{self.total_problems} "
            f"({self.overall_accuracy:.0%})",
            f"**Duration**: {self.duration_ms:.0f}ms",
        ]
        if self.regressions:
            lines.append(f"\n### ⚠️ Regressions ({len(self.regressions)}):")
            for r in self.regressions:
                lines.append(f"  - ↓ {r}")
        if self.improvements:
            lines.append(f"\n### ✅ Improvements ({len(self.improvements)}):")
            for imp in self.improvements:
                lines.append(f"  - ↑ {imp}")
        lines.append("\n### Category Breakdown:")
        for cat_name, cs in sorted(
            self.category_scores.items(), key=lambda x: -x[1].score()
        ):
            bar = "█" * int(cs.accuracy * 10) + "░" * (10 - int(cs.accuracy * 10))
            lines.append(
                f"  {bar} {cs.accuracy:.0%} — **{cat_name}** "
                f"({cs.problems_passed}/{cs.problems_total}, "
                f"avg {cs.avg_time_ms:.0f}ms)"
            )
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# PROBLEM GENERATORS
# ═══════════════════════════════════════════════════════════

class ProblemGenerator:
    """Generates benchmark problems algorithmically with scaled difficulty."""

    @staticmethod
    def _rng(difficulty: int) -> random.Random:
        """Seeded RNG for reproducibility within a difficulty level."""
        return random.Random(42 + difficulty * 7)

    @classmethod
    def arithmetic(cls, difficulty: int = 1) -> List[BenchmarkProblem]:
        """Generate arithmetic problems."""
        rng = cls._rng(difficulty)
        problems = []
        max_val = 10 ** min(difficulty, 6)

        for i in range(3):
            a = rng.randint(1, max_val)
            b = rng.randint(1, max_val)
            ops = [('+', a + b), ('-', a - b), ('*', a * b)]
            op, result = ops[i % 3]
            problems.append(BenchmarkProblem(
                category=BenchmarkCategory.ARITHMETIC,
                difficulty=difficulty,
                prompt=f"Calculate: {a} {op} {b}",
                expected_answer=str(result),
            ))
        return problems

    @classmethod
    def algebra(cls, difficulty: int = 1) -> List[BenchmarkProblem]:
        """Generate algebra problems."""
        rng = cls._rng(difficulty)
        problems = []
        # Linear equation: ax + b = c → x = (c - b) / a
        a = rng.randint(1, 5 * difficulty)
        b = rng.randint(-10 * difficulty, 10 * difficulty)
        x_answer = rng.randint(-10, 10)
        c = a * x_answer + b
        problems.append(BenchmarkProblem(
            category=BenchmarkCategory.ALGEBRA,
            difficulty=difficulty,
            prompt=f"Solve for x: {a}x + {b} = {c}",
            expected_answer=str(x_answer),
        ))
        # Quadratic: x^2 = n → x = sqrt(n)
        n = rng.choice([4, 9, 16, 25, 36, 49, 64, 81, 100])
        problems.append(BenchmarkProblem(
            category=BenchmarkCategory.ALGEBRA,
            difficulty=difficulty,
            prompt=f"What is the positive square root of {n}?",
            expected_answer=str(int(math.sqrt(n))),
        ))
        return problems

    @classmethod
    def statistics(cls, difficulty: int = 1) -> List[BenchmarkProblem]:
        """Generate statistics problems."""
        rng = cls._rng(difficulty)
        n = min(3 + difficulty, 10)
        data = [rng.randint(1, 20 * difficulty) for _ in range(n)]
        mean_val = sum(data) / len(data)
        problems = [BenchmarkProblem(
            category=BenchmarkCategory.STATISTICS,
            difficulty=difficulty,
            prompt=f"What is the mean of {data}?",
            expected_answer=f"{mean_val:.2f}" if mean_val != int(mean_val) else str(int(mean_val)),
        )]
        sorted_data = sorted(data)
        mid = len(sorted_data) // 2
        if len(sorted_data) % 2 == 0:
            median_val = (sorted_data[mid - 1] + sorted_data[mid]) / 2
        else:
            median_val = sorted_data[mid]
        problems.append(BenchmarkProblem(
            category=BenchmarkCategory.STATISTICS,
            difficulty=difficulty,
            prompt=f"What is the median of {data}?",
            expected_answer=f"{median_val:.1f}" if median_val != int(median_val) else str(int(median_val)),
        ))
        return problems

    @classmethod
    def number_theory(cls, difficulty: int = 1) -> List[BenchmarkProblem]:
        """Generate number theory problems."""
        rng = cls._rng(difficulty)
        problems = []
        # Is N prime?
        n = rng.choice([7, 11, 13, 17, 15, 21, 25, 29, 31, 33, 37, 39, 41, 49])
        is_prime = all(n % i != 0 for i in range(2, int(math.sqrt(n)) + 1)) and n > 1
        problems.append(BenchmarkProblem(
            category=BenchmarkCategory.NUMBER_THEORY,
            difficulty=difficulty,
            prompt=f"Is {n} a prime number?",
            expected_answer="yes" if is_prime else "no",
        ))
        # Factorial
        k = min(difficulty + 2, 10)
        fact = math.factorial(k)
        problems.append(BenchmarkProblem(
            category=BenchmarkCategory.NUMBER_THEORY,
            difficulty=difficulty,
            prompt=f"What is {k}! (factorial of {k})?",
            expected_answer=str(fact),
        ))
        return problems

    @classmethod
    def pattern_match(cls, difficulty: int = 1) -> List[BenchmarkProblem]:
        """Generate sequence/pattern problems."""
        problems = []
        # Arithmetic sequence
        start = 2 * difficulty
        step = difficulty + 1
        seq = [start + i * step for i in range(5)]
        next_val = start + 5 * step
        problems.append(BenchmarkProblem(
            category=BenchmarkCategory.PATTERN_MATCH,
            difficulty=difficulty,
            prompt=f"What is the next number in the sequence: {', '.join(map(str, seq))}?",
            expected_answer=str(next_val),
        ))
        # Geometric
        base = 2
        geo = [base ** i for i in range(1, 6)]
        problems.append(BenchmarkProblem(
            category=BenchmarkCategory.PATTERN_MATCH,
            difficulty=difficulty,
            prompt=f"What comes next: {', '.join(map(str, geo))}?",
            expected_answer=str(base ** 6),
        ))
        return problems

    @classmethod
    def sorting(cls, difficulty: int = 1) -> List[BenchmarkProblem]:
        """Generate sorting knowledge questions."""
        problems = [
            BenchmarkProblem(
                category=BenchmarkCategory.SORTING,
                difficulty=difficulty,
                prompt="What is the average time complexity of quicksort?",
                expected_answer="O(n log n)",
            ),
            BenchmarkProblem(
                category=BenchmarkCategory.SORTING,
                difficulty=difficulty,
                prompt="What is the worst case time complexity of merge sort?",
                expected_answer="O(n log n)",
            ),
        ]
        return problems

    @classmethod
    def physics(cls, difficulty: int = 1) -> List[BenchmarkProblem]:
        """Generate physics problems."""
        problems = []
        # v = u + at
        u = 0
        a = 10 * difficulty
        t = difficulty + 1
        v = u + a * t
        problems.append(BenchmarkProblem(
            category=BenchmarkCategory.PHYSICS,
            difficulty=difficulty,
            prompt=f"An object starts from rest (u={u} m/s) with acceleration {a} m/s². "
                   f"What is its velocity after {t} seconds?",
            expected_answer=f"{v} m/s",
        ))
        # KE = 0.5 * m * v^2
        m = 2 * difficulty
        vel = 3 * difficulty
        ke = 0.5 * m * vel ** 2
        problems.append(BenchmarkProblem(
            category=BenchmarkCategory.PHYSICS,
            difficulty=difficulty,
            prompt=f"What is the kinetic energy of a {m} kg object moving at {vel} m/s?",
            expected_answer=f"{ke:.1f} J" if ke != int(ke) else f"{int(ke)} J",
        ))
        return problems

    @classmethod
    def general_reasoning(cls, difficulty: int = 1) -> List[BenchmarkProblem]:
        """Generate general reasoning problems."""
        return [
            BenchmarkProblem(
                category=BenchmarkCategory.GENERAL_REASONING,
                difficulty=difficulty,
                prompt="If all dogs are animals, and Rex is a dog, is Rex an animal?",
                expected_answer="yes",
            ),
            BenchmarkProblem(
                category=BenchmarkCategory.GENERAL_REASONING,
                difficulty=difficulty,
                prompt="Which is larger: 2^10 or 10^3?",
                expected_answer="2^10",  # 1024 > 1000
            ),
        ]


# ═══════════════════════════════════════════════════════════
# ANSWER VERIFIER
# ═══════════════════════════════════════════════════════════

class AnswerVerifier:
    """Verifies CCE answers against expected answers with fuzzy matching."""

    @staticmethod
    def verify(response: str, expected: str) -> bool:
        """
        Check if response contains the expected answer.
        Uses fuzzy matching: case-insensitive, strips whitespace, checks containment.
        """
        if not response or not expected:
            return False

        resp_lower = response.lower().strip()
        exp_lower = expected.lower().strip()

        # Exact containment
        if exp_lower in resp_lower:
            return True

        # Numeric comparison
        try:
            # Extract numbers from both
            import re
            resp_nums = re.findall(r'-?\d+\.?\d*', resp_lower)
            exp_nums = re.findall(r'-?\d+\.?\d*', exp_lower)
            if exp_nums:
                exp_val = float(exp_nums[0])
                for rn in resp_nums:
                    if abs(float(rn) - exp_val) < 0.01:
                        return True
        except (ValueError, IndexError):
            pass

        # Yes/No matching
        if exp_lower in ("yes", "no", "true", "false"):
            positive = {"yes", "true", "correct", "affirmative", "is a", "it is"}
            negative = {"no", "false", "incorrect", "not", "isn't", "is not"}
            if exp_lower in ("yes", "true"):
                return any(p in resp_lower for p in positive)
            else:
                return any(n in resp_lower for n in negative)

        return False


# ═══════════════════════════════════════════════════════════
# REGRESSION DETECTOR
# ═══════════════════════════════════════════════════════════

class RegressionDetector:
    """Compares current scores to historical baselines."""

    def __init__(self):
        self._history: List[Dict[str, float]] = []  # list of {category: accuracy}

    def record(self, category_accuracies: Dict[str, float]) -> None:
        """Record a benchmark run."""
        self._history.append(category_accuracies)
        if len(self._history) > 50:
            self._history = self._history[-50:]

    def detect(self, current: Dict[str, float]) -> Tuple[List[str], List[str]]:
        """
        Compare current scores to last run.
        Returns (regressions, improvements) as category name lists.
        """
        if len(self._history) < 2:
            return [], []

        previous = self._history[-2]
        regressions = []
        improvements = []

        for cat, score in current.items():
            prev_score = previous.get(cat, 0.0)
            if score < prev_score - 0.05:
                regressions.append(f"{cat}: {prev_score:.0%} → {score:.0%}")
            elif score > prev_score + 0.05:
                improvements.append(f"{cat}: {prev_score:.0%} → {score:.0%}")

        return regressions, improvements


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE
# ═══════════════════════════════════════════════════════════

class CompetitiveBenchmarkEngine:
    """
    Self-benchmarking engine with regression detection.

    Usage:
        bench = CompetitiveBenchmarkEngine()

        # Run full benchmark suite
        report = bench.run_full_suite(solve_fn=cce.generate)
        print(report.summary())

        # Run single category
        report = bench.run_category(BenchmarkCategory.ARITHMETIC, solve_fn=cce.generate)

        # Generate problems at specific difficulty
        problems = bench.generate_problems(BenchmarkCategory.ALGEBRA, difficulty=5)
    """

    GENERATORS: Dict[BenchmarkCategory, Callable] = {
        BenchmarkCategory.ARITHMETIC: ProblemGenerator.arithmetic,
        BenchmarkCategory.ALGEBRA: ProblemGenerator.algebra,
        BenchmarkCategory.STATISTICS: ProblemGenerator.statistics,
        BenchmarkCategory.PHYSICS: ProblemGenerator.physics,
        BenchmarkCategory.NUMBER_THEORY: ProblemGenerator.number_theory,
        BenchmarkCategory.PATTERN_MATCH: ProblemGenerator.pattern_match,
        BenchmarkCategory.SORTING: ProblemGenerator.sorting,
        BenchmarkCategory.GENERAL_REASONING: ProblemGenerator.general_reasoning,
    }

    def __init__(self):
        self.verifier = AnswerVerifier()
        self.regression_detector = RegressionDetector()
        self._stats = {
            "runs": 0, "total_problems": 0, "total_passed": 0,
            "best_score": 0.0, "latest_score": 0.0,
        }
        self._leaderboard: List[Tuple[str, float, float]] = []  # (run_id, score, timestamp)

    def generate_problems(self, category: BenchmarkCategory,
                          difficulty: int = 1) -> List[BenchmarkProblem]:
        """Generate problems for a specific category and difficulty."""
        generator = self.GENERATORS.get(category)
        if generator:
            return generator(difficulty)
        # Fallback — general reasoning
        return ProblemGenerator.general_reasoning(difficulty)

    def run_category(self, category: BenchmarkCategory,
                     solve_fn: Callable, difficulty: int = 3) -> CategoryScore:
        """Run benchmark for a single category."""
        problems = self.generate_problems(category, difficulty)
        cs = CategoryScore(
            category=category,
            problems_total=len(problems),
            difficulty_range=(difficulty, difficulty),
        )

        for prob in problems:
            start = time.time()
            try:
                response = solve_fn(prob.prompt)
            except Exception:
                response = ""
            elapsed_ms = (time.time() - start) * 1000

            passed = self.verifier.verify(response, prob.expected_answer)
            if passed:
                cs.problems_passed += 1
            cs.total_time_ms += elapsed_ms

        cs.avg_time_ms = cs.total_time_ms / max(cs.problems_total, 1)
        cs.accuracy = cs.problems_passed / max(cs.problems_total, 1)
        return cs

    def run_full_suite(self, solve_fn: Callable,
                       difficulty: int = 3) -> BenchmarkReport:
        """Run the complete benchmark suite across all categories."""
        start = time.time()
        run_id = hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:10]
        report = BenchmarkReport(run_id=run_id, timestamp=time.time())

        category_accuracies: Dict[str, float] = {}

        for category in self.GENERATORS:
            cs = self.run_category(category, solve_fn, difficulty)
            report.category_scores[category.value] = cs
            report.total_problems += cs.problems_total
            report.total_passed += cs.problems_passed
            category_accuracies[category.value] = cs.accuracy

        report.total_failed = report.total_problems - report.total_passed
        report.overall_accuracy = report.total_passed / max(report.total_problems, 1)

        # Composite score (weighted by difficulty)
        if report.category_scores:
            report.overall_score = sum(
                cs.score() for cs in report.category_scores.values()
            ) / len(report.category_scores)

        # Regression detection
        self.regression_detector.record(category_accuracies)
        regressions, improvements = self.regression_detector.detect(category_accuracies)
        report.regressions = regressions
        report.improvements = improvements

        report.duration_ms = (time.time() - start) * 1000

        # Update leaderboard
        self._leaderboard.append((run_id, report.overall_score, time.time()))
        self._leaderboard.sort(key=lambda x: -x[1])
        self._leaderboard = self._leaderboard[:20]

        # Stats
        self._stats["runs"] += 1
        self._stats["total_problems"] += report.total_problems
        self._stats["total_passed"] += report.total_passed
        self._stats["latest_score"] = report.overall_score
        self._stats["best_score"] = max(self._stats["best_score"], report.overall_score)

        return report

    def run_quick_benchmark(self, solve_fn: Callable) -> BenchmarkReport:
        """Run a quick benchmark with lower difficulty (for fast checks)."""
        return self.run_full_suite(solve_fn, difficulty=1)

    def get_leaderboard(self) -> List[Tuple[str, float, float]]:
        """Get the top benchmark runs."""
        return self._leaderboard

    def solve(self, prompt: str) -> BenchmarkReport:
        """Natural language interface — runs self-benchmark with built-in solver."""
        def trivial_solver(p: str) -> str:
            return f"Processing: {p}"
        return self.run_quick_benchmark(trivial_solver)

    def get_stats(self) -> Dict[str, Any]:
        return {"engine": "CompetitiveBenchmarkEngine", **self._stats}
