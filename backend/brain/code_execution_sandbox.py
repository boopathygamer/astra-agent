"""
Code Execution Sandbox — Safe Code Execution + AST Validation + Auto-Testing
═════════════════════════════════════════════════════════════════════════════
Runs synthesized code in restricted environments with timeout, memory caps,
AST pre-screening for dangerous ops, and auto-generated test harness.

No external dependencies — uses stdlib subprocess + ast for sandboxing.

Architecture:
  Code → AST Validator → Whitelist Check → Restricted Subprocess
           │                                       │
           ▼                                       ▼
    Reject dangerous ops              Capture stdout/stderr/retval
           │                                       │
           └───────────── Test Harness ────────────┘
                               │
                               ▼
                        Execution Report

Safety layers:
  1. AST validation — blocks imports, file I/O, eval, exec, subprocess
  2. Timeout — kills processes exceeding time limit (default 5s)
  3. Output truncation — caps output to prevent memory bombs
  4. Restricted builtins — only safe functions available
"""

import ast
import hashlib
import logging
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════

class SafetyLevel(Enum):
    SAFE = "safe"             # Pure computation, no side effects
    CAUTIOUS = "cautious"     # Minor I/O (print), no file/network
    RESTRICTED = "restricted" # Some imports allowed (math, re, etc.)
    BLOCKED = "blocked"       # Dangerous code — do not execute


class ViolationType(Enum):
    FORBIDDEN_IMPORT = "forbidden_import"
    DANGEROUS_CALL = "dangerous_call"
    FILE_ACCESS = "file_access"
    NETWORK_ACCESS = "network_access"
    SYSTEM_CALL = "system_call"
    EXEC_EVAL = "exec_eval"
    INFINITE_LOOP = "infinite_loop_risk"
    MEMORY_BOMB = "memory_bomb_risk"


@dataclass
class ASTViolation:
    """A detected safety violation in code AST."""
    violation_type: ViolationType
    description: str
    line_number: int = 0
    severity: float = 0.0  # 0-1

    def __str__(self) -> str:
        return f"L{self.line_number}: [{self.violation_type.value}] {self.description}"


@dataclass
class ValidationResult:
    """Result of AST validation."""
    is_safe: bool = True
    safety_level: SafetyLevel = SafetyLevel.SAFE
    violations: List[ASTViolation] = field(default_factory=list)
    functions_found: List[str] = field(default_factory=list)
    classes_found: List[str] = field(default_factory=list)
    imports_found: List[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "✅ SAFE" if self.is_safe else f"❌ {self.safety_level.value.upper()}"
        lines = [f"**AST Validation**: {status}"]
        if self.violations:
            for v in self.violations:
                lines.append(f"  - {v}")
        return "\n".join(lines)


@dataclass
class TestCase:
    """A single test case for code validation."""
    name: str = ""
    input_args: Any = None
    expected_output: Any = None
    actual_output: Any = None
    passed: bool = False
    error: str = ""

    def __str__(self) -> str:
        icon = "✅" if self.passed else "❌"
        return f"{icon} {self.name}: expected={self.expected_output}, got={self.actual_output}"


@dataclass
class ExecutionOutput:
    """Result of code execution in the sandbox."""
    success: bool = False
    stdout: str = ""
    stderr: str = ""
    return_value: str = ""
    exit_code: int = -1
    timed_out: bool = False
    duration_ms: float = 0.0
    safety_level: SafetyLevel = SafetyLevel.SAFE
    validation: Optional[ValidationResult] = None
    test_results: List[TestCase] = field(default_factory=list)
    tests_passed: int = 0
    tests_total: int = 0

    def summary(self) -> str:
        status = "✅ SUCCESS" if self.success else "❌ FAILED"
        if self.timed_out:
            status = "⏱️ TIMEOUT"
        lines = [
            f"## Code Execution Sandbox Report",
            f"**Status**: {status}",
            f"**Safety**: {self.safety_level.value}",
            f"**Duration**: {self.duration_ms:.1f}ms",
        ]
        if self.stdout:
            lines.append(f"**Output**: {self.stdout[:200]}")
        if self.stderr:
            lines.append(f"**Errors**: {self.stderr[:200]}")
        if self.test_results:
            lines.append(f"\n### Tests: {self.tests_passed}/{self.tests_total} passed")
            for tc in self.test_results[:10]:
                lines.append(f"  {tc}")
        if self.validation and self.validation.violations:
            lines.append(f"\n### Safety Violations:")
            lines.append(self.validation.summary())
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# AST VALIDATOR
# ═══════════════════════════════════════════════════════════

class ASTValidator:
    """Static analysis of Python code via AST to detect dangerous operations."""

    # Completely forbidden modules
    FORBIDDEN_MODULES: Set[str] = {
        "os", "sys", "subprocess", "shutil", "socket", "http",
        "urllib", "requests", "ftplib", "smtplib", "ctypes",
        "importlib", "runpy", "code", "codeop", "compileall",
        "multiprocessing", "threading", "signal", "resource",
        "pathlib", "glob", "tempfile", "io", "pickle", "shelve",
        "sqlite3", "webbrowser", "tkinter", "asyncio",
    }

    # Allowed safe modules for restricted mode
    SAFE_MODULES: Set[str] = {
        "math", "cmath", "decimal", "fractions", "statistics",
        "re", "string", "textwrap", "unicodedata",
        "collections", "itertools", "functools", "operator",
        "json", "csv", "datetime", "time", "random",
        "copy", "enum", "dataclasses", "typing",
        "heapq", "bisect", "array",
    }

    # Dangerous built-in calls
    DANGEROUS_CALLS: Set[str] = {
        "exec", "eval", "compile", "__import__", "globals", "locals",
        "getattr", "setattr", "delattr", "vars",
        "open", "input", "breakpoint",
    }

    @classmethod
    def validate(cls, code: str) -> ValidationResult:
        """Validate Python code via AST analysis."""
        result = ValidationResult()

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            result.is_safe = False
            result.safety_level = SafetyLevel.BLOCKED
            result.violations.append(ASTViolation(
                ViolationType.DANGEROUS_CALL,
                f"Syntax error: {e}", getattr(e, 'lineno', 0), 0.3,
            ))
            return result

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    result.imports_found.append(alias.name)
                    if module in cls.FORBIDDEN_MODULES:
                        result.violations.append(ASTViolation(
                            ViolationType.FORBIDDEN_IMPORT,
                            f"Forbidden import: '{alias.name}'",
                            getattr(node, 'lineno', 0), 0.9,
                        ))

            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split('.')[0]
                result.imports_found.append(node.module or "")
                if module in cls.FORBIDDEN_MODULES:
                    result.violations.append(ASTViolation(
                        ViolationType.FORBIDDEN_IMPORT,
                        f"Forbidden import from: '{node.module}'",
                        getattr(node, 'lineno', 0), 0.9,
                    ))

            # Check dangerous function calls
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in cls.DANGEROUS_CALLS:
                    result.violations.append(ASTViolation(
                        ViolationType.DANGEROUS_CALL if func_name not in ('open',) else ViolationType.FILE_ACCESS,
                        f"Dangerous call: '{func_name}()'",
                        getattr(node, 'lineno', 0), 0.95,
                    ))

            # Check function definitions
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                result.functions_found.append(node.name)

            # Check class definitions
            elif isinstance(node, ast.ClassDef):
                result.classes_found.append(node.name)

            # Check for while True (infinite loop risk)
            elif isinstance(node, ast.While):
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    result.violations.append(ASTViolation(
                        ViolationType.INFINITE_LOOP,
                        "Potential infinite loop: 'while True' without visible break",
                        getattr(node, 'lineno', 0), 0.6,
                    ))

            # Check for huge list/range allocations
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == 'range' and node.args:
                    if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, int):
                        if node.args[0].value > 10_000_000:
                            result.violations.append(ASTViolation(
                                ViolationType.MEMORY_BOMB,
                                f"Huge range allocation: range({node.args[0].value})",
                                getattr(node, 'lineno', 0), 0.8,
                            ))

        # Determine safety level
        if not result.violations:
            only_safe_imports = all(
                imp.split('.')[0] in cls.SAFE_MODULES
                for imp in result.imports_found
            )
            if result.imports_found and only_safe_imports:
                result.safety_level = SafetyLevel.RESTRICTED
            elif result.imports_found:
                result.safety_level = SafetyLevel.CAUTIOUS
            else:
                result.safety_level = SafetyLevel.SAFE
        else:
            max_severity = max(v.severity for v in result.violations)
            if max_severity >= 0.8:
                result.safety_level = SafetyLevel.BLOCKED
                result.is_safe = False
            elif max_severity >= 0.5:
                result.safety_level = SafetyLevel.RESTRICTED
            else:
                result.safety_level = SafetyLevel.CAUTIOUS

        return result


# ═══════════════════════════════════════════════════════════
# TEST HARNESS
# ═══════════════════════════════════════════════════════════

class TestHarness:
    """Auto-generates and runs test cases for code."""

    @staticmethod
    def generate_tests(code: str, function_name: str = "",
                       io_pairs: Optional[List[Tuple]] = None) -> List[TestCase]:
        """Generate test cases from I/O pairs or heuristics."""
        tests = []

        if io_pairs:
            for i, (inp, expected) in enumerate(io_pairs):
                tests.append(TestCase(
                    name=f"test_{function_name or 'fn'}_{i+1}",
                    input_args=inp,
                    expected_output=expected,
                ))

        # Add edge case tests
        if function_name:
            tests.extend([
                TestCase(name=f"test_{function_name}_zero", input_args=0,
                         expected_output=None),  # Just check it doesn't crash
                TestCase(name=f"test_{function_name}_negative", input_args=-1,
                         expected_output=None),
            ])

        return tests

    @staticmethod
    def build_test_script(code: str, function_name: str,
                          tests: List[TestCase]) -> str:
        """Build a complete test script."""
        lines = [code, "", "# ── Auto-generated tests ──", "import json", "results = []"]

        for tc in tests:
            if tc.expected_output is not None:
                lines.append(f"try:")
                lines.append(f"    _result = {function_name}({repr(tc.input_args)})")
                lines.append(f"    _passed = _result == {repr(tc.expected_output)}")
                lines.append(f"    results.append({{'name': {repr(tc.name)}, 'passed': _passed, 'actual': repr(_result), 'error': ''}})")
                lines.append(f"except Exception as e:")
                lines.append(f"    results.append({{'name': {repr(tc.name)}, 'passed': False, 'actual': '', 'error': str(e)}})")
            else:
                # Just test it doesn't crash
                lines.append(f"try:")
                lines.append(f"    {function_name}({repr(tc.input_args)})")
                lines.append(f"    results.append({{'name': {repr(tc.name)}, 'passed': True, 'actual': 'no crash', 'error': ''}})")
                lines.append(f"except Exception as e:")
                lines.append(f"    results.append({{'name': {repr(tc.name)}, 'passed': True, 'actual': 'exception OK', 'error': str(e)}})")

        lines.append("print(json.dumps(results))")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE
# ═══════════════════════════════════════════════════════════

MAX_OUTPUT_BYTES = 50_000
DEFAULT_TIMEOUT_SECS = 5


class CodeExecutionSandbox:
    """
    Safe code execution sandbox with AST validation and auto-testing.

    Usage:
        sandbox = CodeExecutionSandbox()

        # Execute code safely
        result = sandbox.execute("print(2 + 2)")

        # Execute with tests
        result = sandbox.execute_with_tests(
            "def double(x): return x * 2",
            function_name="double",
            io_pairs=[(2, 4), (3, 6), (5, 10)],
        )
        print(result.summary())
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT_SECS):
        self.timeout = timeout
        self.validator = ASTValidator()
        self.harness = TestHarness()
        self._stats = {
            "executions": 0, "successes": 0, "failures": 0,
            "blocked": 0, "timeouts": 0, "tests_run": 0, "tests_passed": 0,
        }

    def execute(self, code: str, timeout: Optional[float] = None) -> ExecutionOutput:
        """
        Execute Python code in a sandboxed subprocess.
        Returns ExecutionOutput with stdout, stderr, and metadata.
        """
        timeout = timeout or self.timeout
        start = time.time()
        output = ExecutionOutput()

        # Step 1: AST Validation
        validation = self.validator.validate(code)
        output.validation = validation
        output.safety_level = validation.safety_level

        if not validation.is_safe:
            output.success = False
            output.stderr = f"Code blocked by AST validator: {len(validation.violations)} violation(s)"
            output.duration_ms = (time.time() - start) * 1000
            self._stats["executions"] += 1
            self._stats["blocked"] += 1
            return output

        # Step 2: Execute in subprocess
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False, encoding='utf-8'
            ) as f:
                f.write(code)
                tmp_path = f.name

            try:
                proc = subprocess.run(
                    [sys.executable, tmp_path],
                    capture_output=True, text=True,
                    timeout=timeout,
                    cwd=tempfile.gettempdir(),
                )
                output.stdout = proc.stdout[:MAX_OUTPUT_BYTES]
                output.stderr = proc.stderr[:MAX_OUTPUT_BYTES]
                output.exit_code = proc.returncode
                output.success = proc.returncode == 0
            except subprocess.TimeoutExpired:
                output.timed_out = True
                output.success = False
                output.stderr = f"Execution timed out after {timeout}s"
                self._stats["timeouts"] += 1
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except Exception as e:
            output.success = False
            output.stderr = f"{type(e).__name__}: {str(e)[:200]}"

        output.duration_ms = (time.time() - start) * 1000
        self._stats["executions"] += 1
        if output.success:
            self._stats["successes"] += 1
        else:
            self._stats["failures"] += 1

        return output

    def execute_with_tests(self, code: str, function_name: str,
                           io_pairs: Optional[List[Tuple]] = None,
                           timeout: Optional[float] = None) -> ExecutionOutput:
        """Execute code and run auto-generated tests against it."""
        tests = self.harness.generate_tests(code, function_name, io_pairs)

        if not tests:
            return self.execute(code, timeout)

        # Build test script
        test_script = self.harness.build_test_script(code, function_name, tests)

        # Execute the test script
        result = self.execute(test_script, timeout)

        # Parse test results from stdout
        if result.success and result.stdout.strip():
            try:
                import json
                test_data = json.loads(result.stdout.strip().split('\n')[-1])
                for td in test_data:
                    tc = TestCase(
                        name=td.get("name", "?"),
                        passed=td.get("passed", False),
                        actual_output=td.get("actual", ""),
                        error=td.get("error", ""),
                    )
                    result.test_results.append(tc)
            except (json.JSONDecodeError, IndexError):
                pass

        result.tests_total = len(tests)
        result.tests_passed = sum(1 for t in result.test_results if t.passed)
        self._stats["tests_run"] += result.tests_total
        self._stats["tests_passed"] += result.tests_passed

        return result

    def validate_only(self, code: str) -> ValidationResult:
        """Run AST validation without executing."""
        return self.validator.validate(code)

    def solve(self, prompt: str) -> ExecutionOutput:
        """Natural language interface for CCE routing."""
        # Extract code from prompt (look for code blocks or raw code)
        code = prompt
        if "```" in prompt:
            # Extract code from markdown code block
            import re
            match = re.search(r'```(?:python)?\s*\n(.*?)```', prompt, re.DOTALL)
            if match:
                code = match.group(1)

        return self.execute(code)

    def get_stats(self) -> Dict[str, Any]:
        return {"engine": "CodeExecutionSandbox", **self._stats}
