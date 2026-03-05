"""
Solution Evolver — Iterative Solution Refinement.
──────────────────────────────────────────────────
Evolves code solutions through multiple generations using
a genetic-algorithm-inspired approach:

  1. Generate N variant solutions
  2. Score each for fitness (correctness, efficiency, readability)
  3. Select the best (tournament selection)
  4. Repeat for G generations
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class Variant:
    """A solution variant in the evolution pool."""
    code: str = ""
    fitness: float = 0.0
    generation: int = 0
    mutation_type: str = ""  # optimize, refactor, simplify, generalize
    improvements: List[str] = field(default_factory=list)


@dataclass
class EvolutionResult:
    """Result of solution evolution."""
    original_code: str = ""
    best_code: str = ""
    improved: bool = False
    initial_fitness: float = 0.0
    best_fitness: float = 0.0
    generations: int = 0
    variants_evaluated: int = 0
    evolution_trace: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────

MUTATE_PROMPT = """\
You are a code optimizer. Improve this Python solution.

PROBLEM: {problem}

CURRENT CODE:
```python
{code}
```

MUTATION TYPE: {mutation_type}

{mutation_instruction}

Write ONLY the improved code:
```python
"""

MUTATION_TYPES = {
    "optimize": (
        "Optimize for performance:\n"
        "- Reduce time complexity if possible\n"
        "- Use more efficient data structures\n"
        "- Minimize redundant operations\n"
        "- Consider caching or memoization"
    ),
    "refactor": (
        "Refactor for better code quality:\n"
        "- Improve readability and naming\n"
        "- Extract helper functions\n"
        "- Reduce code duplication\n"
        "- Add proper error handling"
    ),
    "simplify": (
        "Simplify the code:\n"
        "- Remove unnecessary complexity\n"
        "- Use Python idioms and builtins\n"
        "- Reduce line count while keeping clarity\n"
        "- Use list comprehensions where appropriate"
    ),
    "generalize": (
        "Generalize the solution:\n"
        "- Handle more edge cases\n"
        "- Make it work for broader inputs\n"
        "- Add input validation\n"
        "- Consider boundary conditions"
    ),
}


# ──────────────────────────────────────────────
# Solution Evolver Engine
# ──────────────────────────────────────────────

class SolutionEvolver:
    """
    Evolves code solutions through iterative refinement.

    Each generation:
      1. Apply multiple mutation types to current best
      2. Score all variants for fitness
      3. Select the best (tournament selection)

    Fitness is computed from:
      - Syntax validity (is it valid Python?)
      - Code quality (complexity, naming, structure)
      - Efficiency indicators (loop depth, builtin usage)
      - Readability (line length, comments, docstrings)
    """

    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        self._evolution_count = 0
        logger.info("SolutionEvolver initialized")

    def evolve(
        self,
        code: str,
        problem: str,
        generations: int = 3,
        variants_per_gen: int = 3,
    ) -> EvolutionResult:
        """
        Evolve a solution through multiple generations.

        Args:
            code: Starting solution code
            problem: Problem description for context
            generations: Number of evolution generations
            variants_per_gen: Variants to generate per generation

        Returns:
            EvolutionResult with best evolved code
        """
        result = EvolutionResult(original_code=code)
        initial_fitness = self._compute_fitness(code)
        result.initial_fitness = initial_fitness
        result.best_code = code
        result.best_fitness = initial_fitness

        current_best = code
        current_fitness = initial_fitness
        result.evolution_trace.append(
            f"🧬 Gen 0: Fitness = {initial_fitness:.2f}"
        )

        mutations = list(MUTATION_TYPES.keys())

        for gen in range(1, generations + 1):
            variants: List[Variant] = []

            # Generate variants with different mutation types
            for i in range(min(variants_per_gen, len(mutations))):
                mut_type = mutations[i % len(mutations)]
                variant = self._mutate(current_best, problem, mut_type, gen)
                variants.append(variant)
                result.variants_evaluated += 1

            # Tournament selection — pick the best
            if variants:
                best_variant = max(variants, key=lambda v: v.fitness)

                if best_variant.fitness > current_fitness:
                    current_best = best_variant.code
                    current_fitness = best_variant.fitness
                    result.best_code = best_variant.code
                    result.best_fitness = best_variant.fitness
                    result.improved = True
                    result.evolution_trace.append(
                        f"🧬 Gen {gen}: Fitness {current_fitness:.2f} "
                        f"(+{current_fitness - initial_fitness:.2f}) "
                        f"via {best_variant.mutation_type}"
                    )
                else:
                    result.evolution_trace.append(
                        f"🧬 Gen {gen}: No improvement "
                        f"(best={max(v.fitness for v in variants):.2f})"
                    )

            result.generations = gen

        self._evolution_count += 1
        return result

    def _mutate(
        self, code: str, problem: str, mutation_type: str, generation: int
    ) -> Variant:
        """Apply a mutation to generate a code variant."""
        instruction = MUTATION_TYPES.get(mutation_type, MUTATION_TYPES["optimize"])
        prompt = MUTATE_PROMPT.format(
            problem=problem,
            code=code,
            mutation_type=mutation_type,
            mutation_instruction=instruction,
        )

        try:
            response = self.generate_fn(prompt)
            mutated_code = self._extract_code(response)

            if not mutated_code:
                return Variant(code=code, fitness=0.0, generation=generation)

            fitness = self._compute_fitness(mutated_code)
            return Variant(
                code=mutated_code,
                fitness=fitness,
                generation=generation,
                mutation_type=mutation_type,
            )
        except Exception as e:
            logger.warning(f"Mutation failed ({mutation_type}): {e}")
            return Variant(code=code, fitness=0.0, generation=generation)

    def _compute_fitness(self, code: str) -> float:
        """
        Compute fitness score for a code solution (0.0 to 1.0).

        Scoring breakdown:
          - Syntax validity:  0.0 - 0.25
          - Code quality:     0.0 - 0.25
          - Efficiency:       0.0 - 0.25
          - Readability:      0.0 - 0.25
        """
        if not code.strip():
            return 0.0

        score = 0.0

        # 1. Syntax validity (0.25)
        try:
            tree = ast.parse(code)
            score += 0.25
        except SyntaxError:
            return 0.05  # Can't score further without valid syntax

        # 2. Code quality (0.25)
        quality = self._quality_score(code, tree)
        score += quality * 0.25

        # 3. Efficiency (0.25)
        efficiency = self._efficiency_score(code, tree)
        score += efficiency * 0.25

        # 4. Readability (0.25)
        readability = self._readability_score(code)
        score += readability * 0.25

        return round(score, 3)

    def _quality_score(self, code: str, tree: ast.AST) -> float:
        """Score code quality (0-1)."""
        score = 0.5  # Base

        # Has functions?
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        if funcs:
            score += 0.15

        # Has type hints?
        for func in funcs:
            if func.returns or any(a.annotation for a in func.args.args):
                score += 0.1
                break

        # Has error handling?
        if any(isinstance(n, ast.Try) for n in ast.walk(tree)):
            score += 0.1

        # No dangerous patterns
        dangerous = ["eval(", "exec(", "__import__"]
        if not any(d in code for d in dangerous):
            score += 0.15

        return min(score, 1.0)

    def _efficiency_score(self, code: str, tree: ast.AST) -> float:
        """Score efficiency (0-1)."""
        score = 0.6  # Base

        # Count nested loops (deeper = less efficient)
        max_depth = self._max_loop_depth(tree)
        if max_depth <= 1:
            score += 0.2
        elif max_depth == 2:
            score += 0.1
        elif max_depth >= 3:
            score -= 0.2

        # Uses builtin efficient constructs
        if any(kw in code for kw in ["set(", "dict(", "defaultdict", "Counter"]):
            score += 0.1

        # Uses comprehensions (pythonic & often faster)
        if any(isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp))
               for n in ast.walk(tree)):
            score += 0.1

        return max(0.0, min(score, 1.0))

    def _readability_score(self, code: str) -> float:
        """Score readability (0-1)."""
        lines = code.split("\n")
        score = 0.5

        # Line count (reasonable is better)
        if 5 <= len(lines) <= 100:
            score += 0.1
        elif len(lines) > 200:
            score -= 0.1

        # Average line length
        avg_len = sum(len(l) for l in lines) / max(len(lines), 1)
        if avg_len < 80:
            score += 0.1
        elif avg_len > 120:
            score -= 0.1

        # Has comments or docstrings
        if '"""' in code or "'''" in code or "# " in code:
            score += 0.15

        # Good naming (multi-character variables)
        single_vars = len(re.findall(r"\b[a-z]\b", code))
        if single_vars < 5:
            score += 0.15

        return max(0.0, min(score, 1.0))

    def _max_loop_depth(self, tree: ast.AST, depth: int = 0) -> int:
        """Find maximum nesting depth of loops."""
        max_d = depth
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.For, ast.While)):
                max_d = max(max_d, self._max_loop_depth(node, depth + 1))
            else:
                max_d = max(max_d, self._max_loop_depth(node, depth))
        return max_d

    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response."""
        if "```python" in response:
            parts = response.split("```python")
            if len(parts) > 1:
                return parts[1].split("```")[0].strip()
        if "```" in response:
            parts = response.split("```")
            if len(parts) > 1:
                code = parts[1].strip()
                if code.startswith("python\n"):
                    code = code[7:]
                return code
        return response.strip()
