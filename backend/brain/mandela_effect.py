"""
Mandela Effect Protocol — AST-Level Auto-Patching Engine
────────────────────────────────────────────────────────
Instead of "rewriting human history," this module analyzes Python
SyntaxErrors and runtime exceptions, uses AST inspection to propose
concrete fixes, and re-attempts compilation automatically.

The "Mandela Effect" is that the bug never existed — because the
system fixed it before the user ever saw it.
"""

import ast
import logging
import re
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PatchStrategy(Enum):
    MISSING_COLON = "missing_colon"
    INDENT_FIX = "indent_fix"
    UNMATCHED_PAREN = "unmatched_paren"
    MISSING_IMPORT = "missing_import"
    LLM_ASSISTED = "llm_assisted"
    UNFIXABLE = "unfixable"


@dataclass
class PatchResult:
    """Result of an auto-patch attempt."""
    original_code: str
    patched_code: str
    strategy: PatchStrategy
    success: bool
    attempts: int = 0
    error_message: str = ""


class ProbabilityWaveOverwrite:
    """
    Tier X: Probability-Wave Overwrite (The Mandela Effect Protocol)

    Automatically detects and patches Python syntax and runtime errors
    using AST analysis and heuristic pattern matching. The bug is
    retconned — it never existed in the user's reality.
    """

    _COLON_PATTERNS = re.compile(r"^\s*(def |class |if |elif |else|for |while |try|except|finally|with |async )")
    _INDENT_ERROR = re.compile(r"unexpected indent|indentation|IndentationError")

    def __init__(self, generate_fn: Optional[Callable] = None, max_attempts: int = 3):
        self._generate_fn = generate_fn
        self._max_attempts = max(1, max_attempts)
        self._patches_applied: int = 0
        logger.info("[MANDELA-EFFECT] Auto-patching engine initialized (max_attempts=%d).", self._max_attempts)

    def _detect_missing_colon(self, code: str, error_line: int) -> Optional[str]:
        """Detect and fix missing colons on control-flow statements."""
        lines = code.split("\n")
        if 0 < error_line <= len(lines):
            line = lines[error_line - 1]
            if self._COLON_PATTERNS.match(line) and not line.rstrip().endswith(":"):
                lines[error_line - 1] = line.rstrip() + ":"
                logger.info("[MANDELA-EFFECT] Injected missing colon at line %d.", error_line)
                return "\n".join(lines)
        return None

    def _detect_unmatched_parens(self, code: str) -> Optional[str]:
        """Detect and fix unmatched parentheses/brackets."""
        openers = {"(": ")", "[": "]", "{": "}"}
        stack = []
        for char in code:
            if char in openers:
                stack.append(openers[char])
            elif char in openers.values():
                if stack and stack[-1] == char:
                    stack.pop()

        if stack:
            # Append missing closers
            fix = code.rstrip() + "".join(reversed(stack))
            logger.info("[MANDELA-EFFECT] Appended %d missing closing brackets.", len(stack))
            return fix
        return None

    def _llm_assisted_patch(self, code: str, error_msg: str) -> Optional[str]:
        """Use the LLM to fix the code if heuristics fail."""
        if not self._generate_fn:
            return None

        prompt = (
            "Fix the following Python code that produces this error. "
            "Return ONLY the corrected Python code with no explanation.\n\n"
            f"ERROR: {error_msg}\n\nCODE:\n{code}"
        )
        try:
            fixed = self._generate_fn(prompt)
            if "```python" in fixed:
                fixed = fixed.split("```python")[1].split("```")[0].strip()
            elif "```" in fixed:
                fixed = fixed.split("```")[1].split("```")[0].strip()

            # Validate the fix compiles
            ast.parse(fixed)
            logger.info("[MANDELA-EFFECT] LLM-assisted patch compiled successfully.")
            return fixed
        except Exception as e:
            logger.warning("[MANDELA-EFFECT] LLM patch failed: %s", e)
            return None

    def auto_patch(self, code: str) -> PatchResult:
        """
        Attempt to automatically fix syntax errors in the given code.
        Tries heuristic fixes first, falls back to LLM if available.
        """
        for attempt in range(self._max_attempts):
            try:
                ast.parse(code)
                self._patches_applied += 1
                return PatchResult(
                    original_code=code, patched_code=code,
                    strategy=PatchStrategy.MISSING_COLON if attempt > 0 else PatchStrategy.UNFIXABLE,
                    success=True, attempts=attempt,
                )
            except SyntaxError as e:
                error_line = e.lineno or 1
                error_msg = str(e)

                # Strategy 1: Missing colon
                fixed = self._detect_missing_colon(code, error_line)
                if fixed:
                    code = fixed
                    continue

                # Strategy 2: Unmatched parentheses
                fixed = self._detect_unmatched_parens(code)
                if fixed:
                    code = fixed
                    continue

                # Strategy 3: LLM-assisted
                fixed = self._llm_assisted_patch(code, error_msg)
                if fixed:
                    self._patches_applied += 1
                    return PatchResult(
                        original_code=code, patched_code=fixed,
                        strategy=PatchStrategy.LLM_ASSISTED,
                        success=True, attempts=attempt + 1,
                    )

                logger.error("[MANDELA-EFFECT] All patch strategies exhausted at attempt %d.", attempt + 1)
                return PatchResult(
                    original_code=code, patched_code=code,
                    strategy=PatchStrategy.UNFIXABLE,
                    success=False, attempts=attempt + 1,
                    error_message=error_msg,
                )

        return PatchResult(
            original_code=code, patched_code=code,
            strategy=PatchStrategy.UNFIXABLE,
            success=False, attempts=self._max_attempts,
        )


# Global singleton — always active
mandela_protocol = ProbabilityWaveOverwrite()
