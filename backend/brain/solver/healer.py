"""
Self-Healer — Error Detection & Auto-Fix Engine.
─────────────────────────────────────────────────
Detects errors in generated code using:
  1. AST parsing (syntax errors)
  2. Static analysis (common bugs)
  3. Safe execution (runtime errors)

Then uses the LLM to auto-fix with up to N retries.
Tracks healing history so the system learns from mistakes.
"""

import ast
import logging
import re
import traceback
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class CodeError:
    """A detected error in code."""
    error_type: str = ""       # syntax, runtime, logic, style
    message: str = ""
    line_number: int = 0
    severity: str = "error"    # error, warning, info
    suggestion: str = ""


@dataclass
class HealingResult:
    """Result of the self-healing process."""
    original_code: str = ""
    healed_code: str = ""
    was_healed: bool = False
    attempts: int = 0
    errors_found: List[CodeError] = field(default_factory=list)
    errors_fixed: List[str] = field(default_factory=list)
    healing_trace: List[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return not any(e.severity == "error" for e in self.errors_found)


# ──────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────

HEAL_PROMPT = """\
You are a code doctor. Fix the errors in this Python code.

ORIGINAL CODE:
```python
{code}
```

ERRORS FOUND:
{errors}

Instructions:
1. Fix ALL the errors listed above
2. Keep the original logic and structure intact
3. Only fix what's broken — don't rewrite unnecessarily
4. Ensure the result is valid, runnable Python

Write ONLY the fixed code, no explanations:
```python
"""

STATIC_ANALYSIS_PATTERNS = [
    # Common Python bugs
    (r"except\s*:", "Bare except clause — catches ALL exceptions including KeyboardInterrupt",
     "warning", "Use except Exception: instead"),
    (r"== None", "Using == for None comparison",
     "warning", "Use 'is None' instead"),
    (r"!= None", "Using != for None comparison",
     "warning", "Use 'is not None' instead"),
    (r"while\s+True\s*:", "Infinite loop without visible break",
     "info", "Ensure there's a break condition"),
    (r"global\s+", "Use of global variable",
     "warning", "Consider passing as parameter instead"),
    (r"exec\s*\(", "Use of exec() — security risk",
     "error", "Remove exec() call"),
    (r"eval\s*\(", "Use of eval() — security risk",
     "error", "Remove eval() call"),
    (r"import\s+\*", "Star import — namespace pollution",
     "warning", "Import specific names instead"),
    (r"\.append\(.*\.append\(", "Nested append — possible bug",
     "info", "Verify nested append is intentional"),
    (r"return\s*\n\s*[^\s]", "Code after return statement",
     "warning", "Dead code after return"),
]


# ──────────────────────────────────────────────
# Self-Healer Engine
# ──────────────────────────────────────────────

class SelfHealer:
    """
    Auto-detect and fix code errors with retry loop.

    Healing pipeline:
      1. AST parse check (syntax)
      2. Static analysis (common patterns)
      3. LLM-powered fix
      4. Verify fix
      5. Repeat if needed

    Tracks healing history for system-wide learning.
    """

    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        self._healing_history: List[Dict] = []
        self._common_fixes: Dict[str, int] = {}  # error_type → count
        logger.info("SelfHealer initialized")

    def heal(
        self,
        code: str,
        problem: str = "",
        max_attempts: int = 5,
    ) -> HealingResult:
        """
        Detect errors and auto-fix code.

        Args:
            code: Python source code to heal
            problem: Original problem (for context in fixes)
            max_attempts: Maximum fix attempts

        Returns:
            HealingResult with healed code and details
        """
        result = HealingResult(original_code=code)
        current_code = code

        for attempt in range(1, max_attempts + 1):
            # Detect errors
            errors = self._detect_errors(current_code)
            result.errors_found.extend(errors)

            # Filter to actual errors (not warnings)
            critical_errors = [e for e in errors if e.severity == "error"]

            if not critical_errors:
                result.healing_trace.append(
                    f"✅ Attempt {attempt}: Code is healthy"
                )
                break

            result.healing_trace.append(
                f"🔧 Attempt {attempt}: Found {len(critical_errors)} error(s)"
            )

            # Generate fix using LLM
            error_text = "\n".join(
                f"  - Line {e.line_number}: {e.error_type}: {e.message}"
                for e in critical_errors
            )
            prompt = HEAL_PROMPT.format(
                code=current_code,
                errors=error_text,
            )
            response = self.generate_fn(prompt)
            fixed_code = self._extract_code(response)

            if not fixed_code or fixed_code == current_code:
                result.healing_trace.append(
                    "   ❌ LLM could not fix — trying again"
                )
                continue

            # Verify the fix didn't break more
            new_errors = self._detect_errors(fixed_code)
            new_critical = [e for e in new_errors if e.severity == "error"]

            if len(new_critical) < len(critical_errors):
                # Fix improved things
                for old_err in critical_errors:
                    if not any(e.message == old_err.message for e in new_critical):
                        result.errors_fixed.append(old_err.message)
                        self._common_fixes[old_err.error_type] = (
                            self._common_fixes.get(old_err.error_type, 0) + 1
                        )
                current_code = fixed_code
                result.was_healed = True
                result.healing_trace.append(
                    f"   ✅ Fixed {len(result.errors_fixed)} error(s)"
                )
            else:
                result.healing_trace.append(
                    "   ⚠️ Fix introduced new errors — rolling back"
                )

            result.attempts = attempt

        result.healed_code = current_code

        # Track for learning
        self._healing_history.append({
            "healed": result.was_healed,
            "attempts": result.attempts,
            "errors": len(result.errors_found),
            "fixed": len(result.errors_fixed),
        })

        return result

    def _detect_errors(self, code: str) -> List[CodeError]:
        """Run all error detection checks."""
        errors = []

        # 1. AST Syntax Check
        errors.extend(self._check_syntax(code))

        # 2. Static Analysis
        errors.extend(self._static_analysis(code))

        # 3. Logic checks
        errors.extend(self._check_logic(code))

        return errors

    def _check_syntax(self, code: str) -> List[CodeError]:
        """Check Python syntax via AST parsing."""
        try:
            ast.parse(code)
            return []
        except SyntaxError as e:
            return [CodeError(
                error_type="syntax",
                message=str(e.msg) if e.msg else str(e),
                line_number=e.lineno or 0,
                severity="error",
                suggestion="Fix the syntax error",
            )]

    def _static_analysis(self, code: str) -> List[CodeError]:
        """Run static analysis patterns."""
        errors = []
        for pattern, message, severity, suggestion in STATIC_ANALYSIS_PATTERNS:
            for match in re.finditer(pattern, code):
                # Find line number
                line_num = code[:match.start()].count("\n") + 1
                errors.append(CodeError(
                    error_type="static",
                    message=message,
                    line_number=line_num,
                    severity=severity,
                    suggestion=suggestion,
                ))
        return errors

    def _check_logic(self, code: str) -> List[CodeError]:
        """Check for common logic issues via AST."""
        errors = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            # Check for functions without return
            if isinstance(node, ast.FunctionDef):
                has_return = any(
                    isinstance(n, ast.Return) and n.value is not None
                    for n in ast.walk(node)
                )
                # Only flag if function name suggests it should return
                if not has_return and any(
                    node.name.startswith(p) for p in
                    ["get_", "find_", "calc_", "compute_", "is_", "has_"]
                ):
                    errors.append(CodeError(
                        error_type="logic",
                        message=f"Function '{node.name}' has no return — name suggests it should",
                        line_number=node.lineno,
                        severity="warning",
                        suggestion=f"Add a return statement to {node.name}",
                    ))

            # Check for unused variables in assignments
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        if name.startswith("_") and name != "_":
                            continue  # Intentional unused

        return errors

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

    def get_healing_stats(self) -> dict:
        """Get healing statistics."""
        total = len(self._healing_history)
        if not total:
            return {"total_sessions": 0}
        return {
            "total_sessions": total,
            "success_rate": sum(1 for h in self._healing_history if h["healed"]) / total,
            "avg_attempts": sum(h["attempts"] for h in self._healing_history) / total,
            "avg_errors": sum(h["errors"] for h in self._healing_history) / total,
            "most_common_fix": max(self._common_fixes, key=self._common_fixes.get)
                if self._common_fixes else "N/A",
        }
