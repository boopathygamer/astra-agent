"""
Self-Thinking Problem Solver — Brain Module.
─────────────────────────────────────────────
7-feature coding problem solver:
  1. SolverEngine     — self-thinking decomposition + code generation
  2. SelfHealer       — error detection + auto-fix
  3. SolutionEvolver  — iterative solution refinement
  4. PatternLibrary   — reusable coding pattern storage
  5. ComplexityAnalyzer — time/space Big-O analysis
  6. TestGenerator    — automatic test case generation
"""

from brain.solver.engine import SolverEngine, SolutionResult
from brain.solver.healer import SelfHealer, HealingResult
from brain.solver.evolver import SolutionEvolver, EvolutionResult
from brain.solver.patterns import PatternLibrary, CodingPattern
from brain.solver.complexity import ComplexityAnalyzer, ComplexityResult
from brain.solver.test_gen import TestGenerator, TestSuite

__all__ = [
    "SolverEngine", "SolutionResult",
    "SelfHealer", "HealingResult",
    "SolutionEvolver", "EvolutionResult",
    "PatternLibrary", "CodingPattern",
    "ComplexityAnalyzer", "ComplexityResult",
    "TestGenerator", "TestSuite",
]
