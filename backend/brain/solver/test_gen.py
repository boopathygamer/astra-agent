"""
Test Generator — Automatic Test Case Generation & Validation.
─────────────────────────────────────────────────────────────
Generates test cases for solutions and validates them by execution.

Features:
  - Generates normal, edge, boundary, and stress test cases
  - Safe sandboxed execution
  - Tracks pass/fail with detailed results
  - LLM-powered test generation for complex problems
"""

import ast
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class TestCase:
    """A single test case."""
    name: str = ""
    input_data: str = ""            # Python expression for input
    expected_output: str = ""       # Expected result (or "no_error")
    test_type: str = "normal"       # normal, edge, boundary, stress
    passed: Optional[bool] = None
    actual_output: str = ""
    error: str = ""

    @property
    def status_icon(self) -> str:
        if self.passed is None:
            return "⏳"
        return "✅" if self.passed else "❌"


@dataclass
class TestSuite:
    """Collection of test cases with results."""
    tests: List[TestCase] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.passed is True)

    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if t.passed is False)

    @property
    def total(self) -> int:
        return len(self.tests)

    def summary(self) -> str:
        lines = [f"🧪 Test Suite: {self.passed}/{self.total} passed"]
        for t in self.tests:
            lines.append(
                f"  {t.status_icon} {t.name} ({t.test_type})"
                + (f" — {t.error[:60]}" if t.error else "")
            )
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────

TEST_GEN_PROMPT = """\
Generate test cases for this Python code.

PROBLEM: {problem}

CODE:
```python
{code}
```

Generate 5-8 test cases covering:
1. Normal cases (typical inputs)
2. Edge cases (empty input, single element, etc.)
3. Boundary cases (minimum/maximum values)
4. Error cases (invalid input)

For each test, specify the function to call, input, and expected output.
Format EXACTLY like this:

TEST: [name]
TYPE: normal
CALL: function_name(arg1, arg2)
EXPECTED: expected_result

TEST: [name]
TYPE: edge
CALL: function_name([])
EXPECTED: []
"""


# ──────────────────────────────────────────────
# Test Generator Engine
# ──────────────────────────────────────────────

class TestGenerator:
    """
    Automatic test case generation and validation.

    Pipeline:
      1. Analyze code to find callable functions
      2. Generate test cases using LLM
      3. Add standard edge cases
      4. Execute tests in sandbox
      5. Report results
    """

    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        self._test_count = 0
        logger.info("TestGenerator initialized")

    def generate_tests(self, code: str, problem: str = "") -> TestSuite:
        """
        Generate test cases for code.

        Args:
            code: Python code to test
            problem: Problem description for context

        Returns:
            TestSuite with generated test cases
        """
        suite = TestSuite()

        # Get function names from code
        functions = self._extract_functions(code)
        if not functions:
            logger.warning("No functions found in code to test")
            suite.tests.append(TestCase(
                name="syntax_check",
                test_type="normal",
                input_data="",
                expected_output="no_error",
            ))
            return suite

        # Generate tests using LLM
        prompt = TEST_GEN_PROMPT.format(
            problem=problem or "See code below",
            code=code,
        )
        response = self.generate_fn(prompt)
        llm_tests = self._parse_tests(response)
        suite.tests.extend(llm_tests)

        # Add standard edge cases
        suite.tests.extend(self._standard_edge_cases(functions))

        return suite

    def run_tests(self, code: str, suite: TestSuite) -> TestSuite:
        """
        Execute test cases against the code.

        Args:
            code: Python code to test
            suite: TestSuite with test cases

        Returns:
            Updated TestSuite with results
        """
        # Create safe execution environment
        safe_globals = {
            "__builtins__": {
                "len": len, "range": range, "int": int, "float": float,
                "str": str, "list": list, "dict": dict, "set": set,
                "tuple": tuple, "bool": bool, "sum": sum, "min": min,
                "max": max, "sorted": sorted, "reversed": reversed,
                "enumerate": enumerate, "zip": zip, "map": map,
                "filter": filter, "abs": abs, "round": round,
                "print": print, "isinstance": isinstance, "type": type,
                "None": None, "True": True, "False": False,
                "ValueError": ValueError, "TypeError": TypeError,
                "IndexError": IndexError, "KeyError": KeyError,
                "Exception": Exception,
            }
        }

        # Execute the code to define functions
        try:
            exec(code, safe_globals)  # nosec B102
        except Exception as e:
            for test in suite.tests:
                test.passed = False
                test.error = f"Code failed to load: {str(e)}"
            return suite

        # Run each test
        for test in suite.tests:
            if not test.input_data and test.expected_output == "no_error":
                # Syntax-only test (already passed by loading)
                test.passed = True
                test.actual_output = "Code loaded successfully"
                continue

            try:
                # Execute the test call
                call = test.input_data or test.name
                result = eval(call, safe_globals)  # nosec B307
                test.actual_output = repr(result)

                # Check expected output
                if test.expected_output and test.expected_output != "no_error":
                    try:
                        expected = eval(test.expected_output, safe_globals)  # nosec B307
                        test.passed = (result == expected)
                    except Exception:
                        # Can't evaluate expected — string compare
                        test.passed = str(result) == test.expected_output
                else:
                    # No expected output — just check no error
                    test.passed = True

            except Exception as e:
                test.passed = False
                test.error = f"{type(e).__name__}: {str(e)}"
                test.actual_output = ""

        self._test_count += len(suite.tests)
        return suite

    def generate_and_run(self, code: str, problem: str = "") -> TestSuite:
        """Generate tests and run them in one call."""
        suite = self.generate_tests(code, problem)
        return self.run_tests(code, suite)

    def _extract_functions(self, code: str) -> List[Dict]:
        """Extract function names and signatures from code."""
        functions = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    args = []
                    for arg in node.args.args:
                        if arg.arg != "self":
                            args.append(arg.arg)
                    functions.append({
                        "name": node.name,
                        "args": args,
                        "has_return": any(
                            isinstance(n, ast.Return) and n.value is not None
                            for n in ast.walk(node)
                        ),
                    })
        except SyntaxError:
            pass
        return functions

    def _parse_tests(self, text: str) -> List[TestCase]:
        """Parse LLM output into TestCase objects."""
        tests = []
        current_test = None

        for line in text.split("\n"):
            line = line.strip()
            upper = line.upper()

            if upper.startswith("TEST:"):
                if current_test:
                    tests.append(current_test)
                name = line.split(":", 1)[1].strip()
                current_test = TestCase(name=name)

            elif upper.startswith("TYPE:") and current_test:
                current_test.test_type = line.split(":", 1)[1].strip().lower()

            elif upper.startswith("CALL:") and current_test:
                current_test.input_data = line.split(":", 1)[1].strip()

            elif upper.startswith("EXPECTED:") and current_test:
                current_test.expected_output = line.split(":", 1)[1].strip()

        if current_test:
            tests.append(current_test)

        return tests

    def _standard_edge_cases(self, functions: List[Dict]) -> List[TestCase]:
        """Generate standard edge case tests."""
        tests = []

        for func in functions[:3]:  # Limit to first 3 functions
            name = func["name"]
            args = func["args"]

            if not args or not func["has_return"]:
                continue

            # Empty input test
            if len(args) == 1:
                tests.append(TestCase(
                    name=f"{name}_empty_input",
                    test_type="edge",
                    input_data=f"{name}([])",
                    expected_output="no_error",
                ))

                # Single element test
                tests.append(TestCase(
                    name=f"{name}_single_element",
                    test_type="edge",
                    input_data=f"{name}([1])",
                    expected_output="no_error",
                ))

        return tests

    def get_stats(self) -> dict:
        """Get test generation statistics."""
        return {
            "total_tests_generated": self._test_count,
        }
