"""
Self-Thinking Problem Solver Engine.
─────────────────────────────────────
The brain of the problem solver — takes a coding problem and produces
a working solution through 5-stage pipeline:

  Stage 1: DECOMPOSE — Break problem into sub-problems
  Stage 2: LOGIC     — Build step-by-step pseudocode
  Stage 3: GENERATE  — Synthesize Python code
  Stage 4: HEAL      — Detect & fix errors (self-healing)
  Stage 5: IMPROVE   — Learn from solution (self-improving)

Uses multi-hypothesis reasoning, pattern recall, and metacognitive
monitoring to produce high-quality solutions.
"""

import ast
import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

NL = "\n"


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class SolveStage(Enum):
    """Stages of the solving pipeline."""
    DECOMPOSE = "decompose"
    LOGIC = "logic"
    GENERATE = "generate"
    HEAL = "heal"
    EVOLVE = "evolve"
    ANALYZE = "analyze"
    TEST = "test"
    IMPROVE = "improve"


@dataclass
class SubProblem:
    """A decomposed sub-problem."""
    id: int = 0
    description: str = ""
    dependencies: List[int] = field(default_factory=list)
    complexity_hint: str = ""
    solved: bool = False
    solution: str = ""


@dataclass
class LogicStep:
    """A single step in the logical solution."""
    step_number: int = 0
    description: str = ""
    pseudocode: str = ""
    data_structures: List[str] = field(default_factory=list)
    algorithms: List[str] = field(default_factory=list)


@dataclass
class SolutionResult:
    """Complete result of the solving process."""
    problem: str = ""
    code: str = ""
    logic_steps: List[LogicStep] = field(default_factory=list)
    sub_problems: List[SubProblem] = field(default_factory=list)
    confidence: float = 0.0
    stages_completed: List[SolveStage] = field(default_factory=list)
    healing_attempts: int = 0
    evolution_generations: int = 0
    complexity: str = ""
    tests_passed: int = 0
    tests_total: int = 0
    patterns_used: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    thinking_trace: List[str] = field(default_factory=list)
    improvements_learned: List[str] = field(default_factory=list)

    @property
    def is_solved(self) -> bool:
        return bool(self.code) and self.confidence >= 0.6

    def summary(self) -> str:
        lines = [
            f"🧠 Solution ({self.confidence:.0%} confidence)",
            f"   Stages: {' → '.join(s.value for s in self.stages_completed)}",
            f"   Sub-problems: {len(self.sub_problems)}",
            f"   Logic steps: {len(self.logic_steps)}",
            f"   Healing: {self.healing_attempts} fixes",
            f"   Evolution: {self.evolution_generations} generations",
            f"   Complexity: {self.complexity or 'N/A'}",
            f"   Tests: {self.tests_passed}/{self.tests_total}",
            f"   Time: {self.duration_ms:.0f}ms",
        ]
        return NL.join(lines)


# ──────────────────────────────────────────────
# Prompt Templates
# ──────────────────────────────────────────────

DECOMPOSE_PROMPT = """\
You are an expert problem decomposer. Break this coding problem into clear sub-problems.

PROBLEM: {problem}

{patterns_context}

Instructions:
1. Identify 2-5 sub-problems that together solve the main problem
2. For each sub-problem, specify its dependencies (which sub-problems must be solved first)
3. Rate complexity of each: easy, medium, hard

Format your response EXACTLY like this:
SUB_PROBLEM 1: [description]
DEPENDS_ON: none
COMPLEXITY: easy

SUB_PROBLEM 2: [description]
DEPENDS_ON: 1
COMPLEXITY: medium

(continue for all sub-problems)
"""

LOGIC_PROMPT = """\
You are an expert algorithm designer. Build step-by-step logic for this coding problem.

PROBLEM: {problem}

SUB-PROBLEMS:
{sub_problems}

{patterns_context}

Instructions:
1. Design the logical approach step-by-step
2. For each step, write pseudocode
3. Identify data structures and algorithms needed
4. Think about edge cases

Format your response EXACTLY like this:
STEP 1: [description]
PSEUDOCODE:
  [pseudocode here]
DATA_STRUCTURES: [list]
ALGORITHMS: [list]

STEP 2: [description]
...
"""

CODE_PROMPT = """\
You are an expert Python programmer. Generate clean, working code for this problem.

PROBLEM: {problem}

LOGICAL PLAN:
{logic}

REQUIREMENTS:
- Write clean, well-documented Python code
- Include proper error handling
- Use type hints
- Optimize for readability and efficiency
- Include a brief docstring
- The code should be self-contained and runnable
{patterns_hint}

Write ONLY the Python code, no explanations:
"""

IMPROVE_PROMPT = """\
You just solved a coding problem. Reflect on what worked and what you learned.

PROBLEM: {problem}

YOUR SOLUTION:
```python
{code}
```

PERFORMANCE: {performance}

Generate 2-3 reusable insights or patterns you learned from this solution.
Format as:
INSIGHT 1: [insight]
INSIGHT 2: [insight]
INSIGHT 3: [insight]
"""


# ──────────────────────────────────────────────
# Solver Engine
# ──────────────────────────────────────────────

class SolverEngine:
    """
    Self-Thinking, Self-Improving Coding Problem Solver.

    Pipeline: DECOMPOSE → LOGIC → GENERATE → HEAL → EVOLVE → ANALYZE → TEST → IMPROVE

    Features:
      - Multi-step decomposition into sub-problems
      - Step-by-step logic building with pseudocode
      - Code generation from logical plan
      - Self-healing: auto-detects and fixes errors
      - Self-improving: learns patterns from solutions
      - Pattern recall: retrieves relevant past patterns
    """

    def __init__(
        self,
        generate_fn: Callable,
        healer=None,
        evolver=None,
        pattern_library=None,
        complexity_analyzer=None,
        test_generator=None,
    ):
        """
        Args:
            generate_fn: LLM text generation function(prompt) → str
            healer: SelfHealer instance (optional, created if None)
            evolver: SolutionEvolver instance (optional)
            pattern_library: PatternLibrary instance (optional)
            complexity_analyzer: ComplexityAnalyzer instance (optional)
            test_generator: TestGenerator instance (optional)
        """
        self.generate_fn = generate_fn

        # Import here to avoid circular imports
        from brain.solver.healer import SelfHealer
        from brain.solver.evolver import SolutionEvolver
        from brain.solver.patterns import PatternLibrary
        from brain.solver.complexity import ComplexityAnalyzer
        from brain.solver.test_gen import TestGenerator

        self.healer = healer or SelfHealer(generate_fn)
        self.evolver = evolver or SolutionEvolver(generate_fn)
        self.pattern_library = pattern_library or PatternLibrary()
        self.complexity_analyzer = complexity_analyzer or ComplexityAnalyzer()
        self.test_generator = test_generator or TestGenerator(generate_fn)

        # Self-improvement tracking
        self._solve_count = 0
        self._success_history: List[Dict] = []

        logger.info("SolverEngine initialized with all 7 features")

    def solve(
        self,
        problem: str,
        max_heal_attempts: int = 5,
        evolve_generations: int = 3,
        generate_tests: bool = True,
    ) -> SolutionResult:
        """
        Solve a coding problem through the full 8-stage pipeline.

        Args:
            problem: Natural language problem description
            max_heal_attempts: Max self-healing retry attempts
            evolve_generations: Number of evolution generations
            generate_tests: Whether to auto-generate tests

        Returns:
            SolutionResult with code, analysis, and metadata
        """
        start_time = time.time()
        result = SolutionResult(problem=problem)
        result.thinking_trace.append(f"🎯 Starting solver for: {problem[:80]}...")

        try:
            # ── Stage 1: DECOMPOSE ──
            result.thinking_trace.append("📦 Stage 1: Decomposing problem...")
            result.sub_problems = self._decompose(problem)
            result.stages_completed.append(SolveStage.DECOMPOSE)
            result.thinking_trace.append(
                f"   Found {len(result.sub_problems)} sub-problems"
            )

            # ── Stage 2: LOGIC ──
            result.thinking_trace.append("🧩 Stage 2: Building logic...")
            result.logic_steps = self._build_logic(problem, result.sub_problems)
            result.stages_completed.append(SolveStage.LOGIC)
            result.thinking_trace.append(
                f"   Built {len(result.logic_steps)} logical steps"
            )

            # ── Stage 3: GENERATE ──
            result.thinking_trace.append("💻 Stage 3: Generating code...")
            code = self._generate_code(problem, result.logic_steps)
            result.code = code
            result.stages_completed.append(SolveStage.GENERATE)
            result.thinking_trace.append(
                f"   Generated {len(code.splitlines())} lines of code"
            )

            # ── Stage 4: HEAL ──
            result.thinking_trace.append("🩺 Stage 4: Self-healing check...")
            healed = self.healer.heal(
                code=result.code,
                problem=problem,
                max_attempts=max_heal_attempts,
            )
            result.healing_attempts = healed.attempts
            if healed.was_healed:
                result.code = healed.healed_code
                result.thinking_trace.append(
                    f"   🔧 Fixed {healed.attempts} error(s): {healed.errors_fixed}"
                )
            else:
                result.thinking_trace.append("   ✅ No errors found")
            result.stages_completed.append(SolveStage.HEAL)

            # ── Stage 5: EVOLVE ──
            result.thinking_trace.append("🧬 Stage 5: Evolving solution...")
            evolved = self.evolver.evolve(
                code=result.code,
                problem=problem,
                generations=evolve_generations,
            )
            result.evolution_generations = evolved.generations
            if evolved.improved:
                result.code = evolved.best_code
                result.thinking_trace.append(
                    f"   🧬 Improved over {evolved.generations} generations "
                    f"(fitness: {evolved.initial_fitness:.2f} → {evolved.best_fitness:.2f})"
                )
            else:
                result.thinking_trace.append("   Original solution is optimal")
            result.stages_completed.append(SolveStage.EVOLVE)

            # ── Stage 6: ANALYZE COMPLEXITY ──
            result.thinking_trace.append("📊 Stage 6: Analyzing complexity...")
            complexity = self.complexity_analyzer.analyze(result.code)
            result.complexity = complexity.summary
            result.thinking_trace.append(
                f"   Time: {complexity.time_complexity}, "
                f"Space: {complexity.space_complexity}"
            )
            result.stages_completed.append(SolveStage.ANALYZE)

            # ── Stage 7: GENERATE & RUN TESTS ──
            if generate_tests:
                result.thinking_trace.append("🧪 Stage 7: Testing solution...")
                test_suite = self.test_generator.generate_and_run(
                    code=result.code,
                    problem=problem,
                )
                result.tests_passed = test_suite.passed
                result.tests_total = test_suite.total
                result.thinking_trace.append(
                    f"   Tests: {test_suite.passed}/{test_suite.total} passed"
                )
                result.stages_completed.append(SolveStage.TEST)

            # Calculate confidence
            result.confidence = self._calculate_confidence(result)

            # ── Stage 8: SELF-IMPROVE ──
            result.thinking_trace.append("📚 Stage 8: Self-improving...")
            improvements = self._improve(problem, result)
            result.improvements_learned = improvements
            result.stages_completed.append(SolveStage.IMPROVE)
            result.thinking_trace.append(
                f"   Learned {len(improvements)} new insight(s)"
            )

        except Exception as e:
            logger.error(f"Solver error: {e}", exc_info=True)
            result.thinking_trace.append(f"❌ Error: {str(e)}")
            result.confidence = 0.1

        result.duration_ms = (time.time() - start_time) * 1000
        result.thinking_trace.append(
            f"\n{'='*50}\n"
            f"✅ Solved in {result.duration_ms:.0f}ms "
            f"({result.confidence:.0%} confidence)"
        )

        self._solve_count += 1
        logger.info(
            f"Problem solved: {result.confidence:.0%} confidence, "
            f"{result.duration_ms:.0f}ms, stages={len(result.stages_completed)}"
        )

        return result

    # ──────────────────────────────────────────
    # Stage 1: DECOMPOSE
    # ──────────────────────────────────────────

    def _decompose(self, problem: str) -> List[SubProblem]:
        """Break problem into sub-problems with dependency graph."""
        # Check pattern library for similar problems
        patterns_ctx = ""
        similar_patterns = self.pattern_library.search(problem)
        if similar_patterns:
            patterns_ctx = "RELEVANT PATTERNS FROM PAST:\n"
            for p in similar_patterns[:3]:
                patterns_ctx += f"  - {p.name}: {p.description}\n"

        prompt = DECOMPOSE_PROMPT.format(
            problem=problem,
            patterns_context=patterns_ctx,
        )
        response = self.generate_fn(prompt)
        return self._parse_sub_problems(response)

    def _parse_sub_problems(self, text: str) -> List[SubProblem]:
        """Parse LLM output into SubProblem objects."""
        sub_problems = []
        current_sp = None

        for line in text.split("\n"):
            line = line.strip()
            upper = line.upper()

            if upper.startswith("SUB_PROBLEM") or upper.startswith("SUBPROBLEM"):
                if current_sp:
                    sub_problems.append(current_sp)
                # Extract ID and description
                parts = line.split(":", 1)
                try:
                    sp_id = int("".join(c for c in parts[0] if c.isdigit()) or "0")
                except ValueError:
                    sp_id = len(sub_problems) + 1
                desc = parts[1].strip() if len(parts) > 1 else ""
                current_sp = SubProblem(id=sp_id, description=desc)

            elif upper.startswith("DEPENDS_ON") and current_sp:
                deps_str = line.split(":", 1)[1].strip().lower()
                if deps_str != "none" and deps_str:
                    deps = [int(d.strip()) for d in deps_str.split(",") if d.strip().isdigit()]
                    current_sp.dependencies = deps

            elif upper.startswith("COMPLEXITY") and current_sp:
                current_sp.complexity_hint = line.split(":", 1)[1].strip()

        if current_sp:
            sub_problems.append(current_sp)

        # Fallback: if parsing failed, create one sub-problem
        if not sub_problems:
            sub_problems.append(SubProblem(id=1, description="Solve the entire problem"))

        return sub_problems

    # ──────────────────────────────────────────
    # Stage 2: BUILD LOGIC
    # ──────────────────────────────────────────

    def _build_logic(
        self, problem: str, sub_problems: List[SubProblem]
    ) -> List[LogicStep]:
        """Build step-by-step logical solution."""
        sp_text = "\n".join(
            f"  {sp.id}. {sp.description} (complexity: {sp.complexity_hint})"
            for sp in sub_problems
        )

        patterns_ctx = ""
        similar = self.pattern_library.search(problem)
        if similar:
            patterns_ctx = "RELEVANT PATTERNS:\n"
            for p in similar[:2]:
                patterns_ctx += f"  - {p.name}: {p.template}\n"

        prompt = LOGIC_PROMPT.format(
            problem=problem,
            sub_problems=sp_text,
            patterns_context=patterns_ctx,
        )
        response = self.generate_fn(prompt)
        return self._parse_logic_steps(response)

    def _parse_logic_steps(self, text: str) -> List[LogicStep]:
        """Parse LLM output into LogicStep objects."""
        steps = []
        current_step = None
        section = None

        for line in text.split("\n"):
            line_stripped = line.strip()
            upper = line_stripped.upper()

            if upper.startswith("STEP"):
                if current_step:
                    steps.append(current_step)
                parts = line_stripped.split(":", 1)
                num = int("".join(c for c in parts[0] if c.isdigit()) or str(len(steps) + 1))
                desc = parts[1].strip() if len(parts) > 1 else ""
                current_step = LogicStep(step_number=num, description=desc)
                section = "description"

            elif upper.startswith("PSEUDOCODE") and current_step:
                section = "pseudocode"
                content = line_stripped.split(":", 1)
                if len(content) > 1 and content[1].strip():
                    current_step.pseudocode = content[1].strip()

            elif upper.startswith("DATA_STRUCT") and current_step:
                section = "data"
                content = line_stripped.split(":", 1)
                if len(content) > 1:
                    current_step.data_structures = [
                        d.strip() for d in content[1].split(",") if d.strip()
                    ]

            elif upper.startswith("ALGORITHM") and current_step:
                section = "algo"
                content = line_stripped.split(":", 1)
                if len(content) > 1:
                    current_step.algorithms = [
                        a.strip() for a in content[1].split(",") if a.strip()
                    ]

            elif section == "pseudocode" and current_step and line_stripped:
                current_step.pseudocode += "\n" + line_stripped

        if current_step:
            steps.append(current_step)

        if not steps:
            steps.append(LogicStep(
                step_number=1,
                description="Implement the solution directly",
            ))

        return steps

    # ──────────────────────────────────────────
    # Stage 3: GENERATE CODE
    # ──────────────────────────────────────────

    def _generate_code(self, problem: str, logic_steps: List[LogicStep]) -> str:
        """Generate Python code from logical plan."""
        logic_text = ""
        for step in logic_steps:
            logic_text += f"Step {step.step_number}: {step.description}\n"
            if step.pseudocode:
                logic_text += f"Pseudocode:\n{step.pseudocode}\n"
            if step.data_structures:
                logic_text += f"Data structures: {', '.join(step.data_structures)}\n"
            if step.algorithms:
                logic_text += f"Algorithms: {', '.join(step.algorithms)}\n"
            logic_text += "\n"

        # Check for relevant patterns
        patterns_hint = ""
        similar = self.pattern_library.search(problem)
        if similar:
            patterns_hint = "\nRelevant patterns to consider:\n"
            for p in similar[:2]:
                if p.template:
                    patterns_hint += f"\n# Pattern: {p.name}\n{p.template}\n"

        prompt = CODE_PROMPT.format(
            problem=problem,
            logic=logic_text,
            patterns_hint=patterns_hint,
        )
        response = self.generate_fn(prompt)
        return self._extract_code(response)

    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response."""
        # Try to find code blocks
        if "```python" in response:
            parts = response.split("```python")
            if len(parts) > 1:
                code = parts[1].split("```")[0].strip()
                return code

        if "```" in response:
            parts = response.split("```")
            if len(parts) > 1:
                code = parts[1].strip()
                if code.startswith("python\n"):
                    code = code[7:]
                return code

        # If no code blocks, try to find the code portion
        lines = response.split("\n")
        code_lines = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("def ", "class ", "import ", "from ", "#")):
                in_code = True
            if in_code:
                code_lines.append(line)
            elif stripped and not any(stripped.startswith(w) for w in
                ["Here", "This", "The", "I'll", "Below", "Note"]):
                code_lines.append(line)

        return "\n".join(code_lines).strip() or response.strip()

    # ──────────────────────────────────────────
    # Stage 8: SELF-IMPROVE
    # ──────────────────────────────────────────

    def _improve(self, problem: str, result: SolutionResult) -> List[str]:
        """Learn from the solution — self-improvement."""
        improvements = []

        # Generate improvement insights using LLM
        try:
            performance = (
                f"Confidence: {result.confidence:.0%}, "
                f"Complexity: {result.complexity}, "
                f"Tests: {result.tests_passed}/{result.tests_total}, "
                f"Heals: {result.healing_attempts}"
            )
            prompt = IMPROVE_PROMPT.format(
                problem=problem,
                code=result.code[:2000],
                performance=performance,
            )
            response = self.generate_fn(prompt)

            # Parse insights
            for line in response.split("\n"):
                line = line.strip()
                if line.upper().startswith("INSIGHT"):
                    insight = line.split(":", 1)[1].strip() if ":" in line else line
                    improvements.append(insight)

            # Store new pattern if solution was good
            if result.confidence >= 0.7 and result.code:
                from brain.solver.patterns import CodingPattern
                pattern = CodingPattern(
                    name=f"solution_{self._solve_count}",
                    description=problem[:200],
                    category=self._categorize_problem(problem),
                    template=result.code[:500],
                    complexity=result.complexity,
                    tags=self._extract_tags(problem),
                )
                self.pattern_library.store(pattern)
                improvements.append(
                    f"Stored solution as pattern: {pattern.name}"
                )

            # Track success for learning
            self._success_history.append({
                "problem": problem[:200],
                "confidence": result.confidence,
                "stages": len(result.stages_completed),
                "heals": result.healing_attempts,
            })

        except Exception as e:
            logger.warning(f"Self-improvement failed: {e}")
            improvements.append(f"Could not generate insights: {e}")

        return improvements

    # ──────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────

    def _calculate_confidence(self, result: SolutionResult) -> float:
        """Calculate overall solution confidence."""
        score = 0.3  # Base for having code

        # Syntax check
        try:
            ast.parse(result.code)
            score += 0.2  # Valid Python
        except SyntaxError:
            pass

        # Logic completeness
        if result.logic_steps:
            score += min(len(result.logic_steps) * 0.05, 0.15)

        # Test results
        if result.tests_total > 0:
            test_ratio = result.tests_passed / result.tests_total
            score += test_ratio * 0.25

        # Healing success (less healing = better initial code)
        if result.healing_attempts == 0:
            score += 0.1
        elif result.healing_attempts <= 2:
            score += 0.05

        return min(score, 1.0)

    def _categorize_problem(self, problem: str) -> str:
        """Quick categorize a problem type."""
        lower = problem.lower()
        categories = {
            "sorting": ["sort", "order", "arrange", "rank"],
            "searching": ["search", "find", "locate", "lookup", "binary search"],
            "graph": ["graph", "tree", "node", "edge", "traverse", "bfs", "dfs"],
            "dynamic_programming": ["dp", "dynamic", "memoize", "optimize", "subproblem"],
            "string": ["string", "text", "parse", "regex", "substring", "palindrome"],
            "array": ["array", "list", "matrix", "grid", "subarray"],
            "math": ["math", "number", "prime", "factorial", "fibonacci"],
            "data_structure": ["stack", "queue", "heap", "hash", "linked list", "trie"],
        }
        for cat, keywords in categories.items():
            if any(kw in lower for kw in keywords):
                return cat
        return "general"

    def _extract_tags(self, problem: str) -> List[str]:
        """Extract tags from problem description."""
        lower = problem.lower()
        tags = []
        tag_keywords = [
            "sort", "search", "graph", "tree", "array", "string",
            "dp", "recursion", "loop", "stack", "queue", "hash",
            "binary", "linked", "matrix", "math", "optimization",
        ]
        for kw in tag_keywords:
            if kw in lower:
                tags.append(kw)
        return tags[:5]

    def get_stats(self) -> dict:
        """Get solver statistics."""
        return {
            "problems_solved": self._solve_count,
            "patterns_stored": len(self.pattern_library),
            "avg_confidence": (
                sum(h["confidence"] for h in self._success_history) /
                len(self._success_history)
                if self._success_history else 0
            ),
            "avg_heals": (
                sum(h["heals"] for h in self._success_history) /
                len(self._success_history)
                if self._success_history else 0
            ),
        }
