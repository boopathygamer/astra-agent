"""
Matryoshka Matrix — Recursive Sub-Problem Decomposition Engine
──────────────────────────────────────────────────────────────
Instead of "spawning pocket universes," this module implements real
recursive problem decomposition. Complex tasks are broken into
smaller solvable sub-problems (like nested Matryoshka dolls),
solved individually, and their results synthesized into a final answer.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_RECURSION_DEPTH = 5
_MAX_SUB_PROBLEMS = 6


@dataclass
class SubProblem:
    """A decomposed sub-problem unit."""
    id: int
    description: str
    parent_id: Optional[int] = None
    depth: int = 0
    solution: str = ""
    solved: bool = False
    duration_ms: float = 0.0


@dataclass
class DecompositionResult:
    """Result of a full recursive decomposition."""
    original_problem: str
    sub_problems: List[SubProblem] = field(default_factory=list)
    synthesized_solution: str = ""
    total_depth: int = 0
    total_duration_ms: float = 0.0
    success: bool = False


class MatryoshkaMatrix:
    """
    Tier X: Ancestral Simulation Recursion (The Matryoshka Matrix)

    Recursively decomposes complex problems into smaller sub-problems,
    solves each independently, and synthesizes results upward.
    """

    def __init__(self, generate_fn: Optional[Callable] = None, max_depth: int = _MAX_RECURSION_DEPTH):
        self._generate_fn = generate_fn
        self._max_depth = max(1, max_depth)
        self._problem_counter: int = 0
        self._total_decompositions: int = 0
        logger.info("[MATRYOSHKA] Recursive decomposition engine active (max_depth=%d).", self._max_depth)

    def _decompose(self, problem: str) -> List[str]:
        """Use LLM to decompose a problem into sub-problems."""
        if not self._generate_fn:
            return [problem]

        prompt = (
            "Break the following complex problem into 2-4 smaller, independent "
            "sub-problems that can each be solved separately. Output each sub-problem "
            "on its own line, prefixed with '- '. Output ONLY the sub-problems.\n\n"
            f"PROBLEM: {problem}"
        )
        try:
            response = self._generate_fn(prompt)
            subs = [
                line.strip().lstrip("- ").strip()
                for line in response.strip().split("\n")
                if line.strip() and line.strip().startswith("-")
            ]
            return subs[:_MAX_SUB_PROBLEMS] if subs else [problem]
        except Exception as e:
            logger.error("[MATRYOSHKA] Decomposition failed: %s", e)
            return [problem]

    def _solve_leaf(self, sub_problem: str) -> str:
        """Solve a leaf-level atomic sub-problem."""
        if not self._generate_fn:
            return f"[Atomic solution for: {sub_problem}]"

        prompt = (
            "Solve the following specific sub-problem concisely and completely. "
            "Output ONLY the solution.\n\n"
            f"SUB-PROBLEM: {sub_problem}"
        )
        try:
            return self._generate_fn(prompt)
        except Exception as e:
            logger.error("[MATRYOSHKA] Leaf solve failed: %s", e)
            return f"[Error solving: {e}]"

    def _synthesize(self, problem: str, sub_solutions: List[str]) -> str:
        """Synthesize sub-solutions into a unified answer."""
        if not self._generate_fn:
            return "\n\n".join(sub_solutions)

        combined = "\n".join(f"Part {i+1}: {s}" for i, s in enumerate(sub_solutions))
        prompt = (
            "Synthesize the following partial solutions into one complete, "
            "unified answer to the original problem. Be concise.\n\n"
            f"ORIGINAL PROBLEM: {problem}\n\n"
            f"PARTIAL SOLUTIONS:\n{combined}"
        )
        try:
            return self._generate_fn(prompt)
        except Exception as e:
            logger.error("[MATRYOSHKA] Synthesis failed: %s", e)
            return "\n\n".join(sub_solutions)

    def solve_recursive(self, problem: str, depth: int = 0) -> DecompositionResult:
        """
        Recursively decompose and solve a complex problem.
        Each layer is a Matryoshka doll — nested problems inside problems.
        """
        start = time.time()
        result = DecompositionResult(original_problem=problem)
        self._total_decompositions += 1

        if depth >= self._max_depth:
            # Base case: solve directly
            solution = self._solve_leaf(problem)
            self._problem_counter += 1
            sub = SubProblem(
                id=self._problem_counter, description=problem,
                depth=depth, solution=solution, solved=True,
                duration_ms=(time.time() - start) * 1000,
            )
            result.sub_problems.append(sub)
            result.synthesized_solution = solution
            result.total_depth = depth
            result.success = True
            result.total_duration_ms = (time.time() - start) * 1000
            return result

        # Decompose into sub-problems
        sub_descriptions = self._decompose(problem)
        logger.info("[MATRYOSHKA] Depth %d: Decomposed into %d sub-problems.", depth, len(sub_descriptions))

        # If decomposition returns only 1 item identical to input, solve directly
        if len(sub_descriptions) <= 1:
            solution = self._solve_leaf(problem)
            self._problem_counter += 1
            sub = SubProblem(
                id=self._problem_counter, description=problem,
                depth=depth, solution=solution, solved=True,
                duration_ms=(time.time() - start) * 1000,
            )
            result.sub_problems.append(sub)
            result.synthesized_solution = solution
            result.success = True
            result.total_duration_ms = (time.time() - start) * 1000
            return result

        # Recurse into each sub-problem
        sub_solutions = []
        for desc in sub_descriptions:
            sub_result = self.solve_recursive(desc, depth + 1)
            result.sub_problems.extend(sub_result.sub_problems)
            sub_solutions.append(sub_result.synthesized_solution)

        # Synthesize partial solutions
        result.synthesized_solution = self._synthesize(problem, sub_solutions)
        result.total_depth = depth
        result.success = True
        result.total_duration_ms = (time.time() - start) * 1000

        logger.info("[MATRYOSHKA] Depth %d: Synthesis complete (%.0fms).", depth, result.total_duration_ms)
        return result


# Global singleton — always active
ancestral_simulator = MatryoshkaMatrix()
