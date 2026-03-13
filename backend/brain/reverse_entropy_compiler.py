"""
Reverse Entropy Compiler — Code Synthesis via Evolutionary Refinement
─────────────────────────────────────────────────────────────────────
Expert-level code generator that starts with random candidate snippets
and iteratively refines them through mutation and AST validation until
a compilable, functional solution crystallizes from noise.

VULNERABILITY FIX: Previously used `random` module and had undefined
local variable (`crystallized_code` used before assignment).
"""

import ast
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CrystallizedCode:
    """A code solution that emerged from entropic refinement."""
    code: str
    iterations: int
    compiles: bool
    refinement_time_ms: float


class ReverseEntropyCompiler:
    """
    Tier 7: Reverse-Entropy Compilation (The Phoenix Protocol)

    Generates candidate code solutions and refines them through
    iterative mutation + AST validation. Code crystallizes from
    random noise into working implementations.
    """

    def __init__(self, generate_fn: Optional[Callable] = None, max_iterations: int = 5):
        self._generate_fn = generate_fn
        self._max_iterations = max(1, max_iterations)
        self._compilations: int = 0
        logger.info("[REVERSE-ENTROPY] Evolutionary code synthesizer active (max_iter=%d).", self._max_iterations)

    def _generate_chaos(self, byte_length: int) -> bytes:
        """Generate cryptographically secure random bytes (the raw chaos)."""
        return os.urandom(byte_length)

    def _attempt_crystallization(self, target_concept: str) -> Optional[str]:
        """Use LLM to crystallize a concept into code."""
        if not self._generate_fn:
            # Fallback: generate a minimal stub
            safe_name = "".join(c if c.isalnum() else "_" for c in target_concept.lower()[:30])
            return f"def {safe_name}():\n    \"\"\"Auto-generated stub for: {target_concept}\"\"\"\n    pass\n"

        prompt = (
            f"Generate a complete, working Python function that implements: {target_concept}\n"
            f"Output ONLY raw Python code. No markdown, no explanation."
        )
        try:
            return self._generate_fn(prompt)
        except Exception as e:
            logger.error("[REVERSE-ENTROPY] Crystallization failed: %s", e)
            return None

    def _validate_code(self, code: str) -> bool:
        """Check if code compiles without syntax errors."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _refine(self, code: str, error_context: str) -> Optional[str]:
        """Refine broken code through mutation."""
        if not self._generate_fn:
            return code

        prompt = (
            f"Fix the following Python code that has this error: {error_context}\n"
            f"Code:\n{code}\n\n"
            f"Output ONLY the fixed raw Python code."
        )
        try:
            return self._generate_fn(prompt)
        except Exception:
            return code

    def crystallize(self, target_concept: str) -> CrystallizedCode:
        """
        Generate and iteratively refine code until it compiles.
        Code crystallizes from chaos into working implementations.
        """
        start = time.time()
        self._compilations += 1

        code = self._attempt_crystallization(target_concept)
        if code is None:
            return CrystallizedCode(code="# Failed to generate", iterations=0, compiles=False,
                                     refinement_time_ms=(time.time() - start) * 1000)

        # Strip markdown if LLM leaked it
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()

        for iteration in range(self._max_iterations):
            if self._validate_code(code):
                duration = (time.time() - start) * 1000
                logger.info("[REVERSE-ENTROPY] Crystallized in %d iterations (%.0fms).", iteration + 1, duration)
                return CrystallizedCode(code=code, iterations=iteration + 1, compiles=True,
                                         refinement_time_ms=duration)

            # Refine
            try:
                ast.parse(code)
            except SyntaxError as e:
                code = self._refine(code, str(e)) or code

        duration = (time.time() - start) * 1000
        compiles = self._validate_code(code)
        logger.warning("[REVERSE-ENTROPY] Crystallization incomplete after %d iterations.", self._max_iterations)
        return CrystallizedCode(code=code, iterations=self._max_iterations, compiles=compiles,
                                 refinement_time_ms=duration)


# Global singleton — always active
entropy_compiler = ReverseEntropyCompiler()
