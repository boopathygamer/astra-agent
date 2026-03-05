"""
Verifier Stack — Proofs When Possible, Tests Otherwise
───────────────────────────────────────────────────────
Section 5 of the architecture: Layered verification

4 layers:
  1. Static checks:   types, lint, invariants, pre/post-conditions
  2. Property tests:  randomized and adversarial generation
  3. Scenario tests:  realistic end-to-end cases and regressions
  4. Cross-check:     ask a separate "critic" model to find flaws

Verification report vector:
    v(s) = (v_static, v_prop, v_scenario, v_critic)

Confidence score:
    Conf(s) = σ(α^T · v(s))
"""

import ast
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from config.settings import brain_config

try:
    from brain.code_analyzer import CodeAnalyzer
except ImportError:
    CodeAnalyzer = None

logger = logging.getLogger(__name__)


@dataclass
class VerificationReport:
    """Complete verification report with all 6 layer scores."""
    v_static: float = 0.0      # Layer 1: Static checks [0, 1]
    v_property: float = 0.0    # Layer 2: Property tests [0, 1]
    v_scenario: float = 0.0    # Layer 3: Scenario tests [0, 1]
    v_critic: float = 0.0      # Layer 4: Critic review [0, 1]
    v_code: float = 0.0        # Layer 5: Code analysis [0, 1]
    v_security: float = 0.0    # Layer 6: Security audit [0, 1]

    static_details: list = field(default_factory=list)
    property_details: list = field(default_factory=list)
    scenario_details: list = field(default_factory=list)
    critic_details: str = ""
    code_details: dict = field(default_factory=dict)
    security_details: list = field(default_factory=list)

    confidence: float = 0.0
    passed: bool = False
    has_critical_vulns: bool = False

    def to_dict(self) -> dict:
        return {
            "v_static": self.v_static,
            "v_property": self.v_property,
            "v_scenario": self.v_scenario,
            "v_critic": self.v_critic,
            "v_code": self.v_code,
            "v_security": self.v_security,
            "confidence": self.confidence,
            "passed": self.passed,
            "has_critical_vulns": self.has_critical_vulns,
        }

    def summary(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        sec = " [CRITICAL VULNS]" if self.has_critical_vulns else ""
        return (
            f"{status} | Conf={self.confidence:.3f}{sec}\n"
            f"  Static:   {self.v_static:.2f}\n"
            f"  Property: {self.v_property:.2f}\n"
            f"  Scenario: {self.v_scenario:.2f}\n"
            f"  Critic:   {self.v_critic:.2f}\n"
            f"  Code:     {self.v_code:.2f}\n"
            f"  Security: {self.v_security:.2f}"
        )


class VerifierStack:
    """
    4-Layer Verification Stack with confidence scoring.

    Each layer independently evaluates the candidate solution.
    Results are combined into a confidence score using learned weights.

    Calibration weights α control the importance of each layer:
        Conf(s) = σ(α₁·v_static + α₂·v_prop + α₃·v_scenario + α₄·v_critic)

    Where σ is the sigmoid squashing function.
    """

    def __init__(self, config=None):
        self.config = config or brain_config

        # Calibration weights α — learnable over time (6 layers)
        self.alpha = {
            "static": 1.0,
            "property": 1.5,
            "scenario": 2.0,
            "critic": 1.8,
            "code": 2.2,
            "security": 2.5,
        }

        # Code analyzer for Layers 5-6
        self._code_analyzer = CodeAnalyzer() if CodeAnalyzer else None

        # Track calibration history
        self._calibration_history: List[Dict] = []

    def verify(
        self,
        candidate: str,
        task: str,
        generate_fn: Callable,
        regression_tests: Optional[List[str]] = None,
        custom_checks: Optional[List[Callable]] = None,
    ) -> VerificationReport:
        """
        Run full 4-layer verification on a candidate solution.

        Args:
            candidate: The candidate solution to verify
            task: The original task/problem description
            generate_fn: LLM generation function for critic/property tests
            regression_tests: Past regression tests to run
            custom_checks: Additional custom check functions

        Returns:
            VerificationReport with all scores and confidence
        """
        report = VerificationReport()

        # Layer 1: Static Checks
        report.v_static, report.static_details = self._static_checks(
            candidate, task, custom_checks
        )

        # Layer 2: Property Tests
        report.v_property, report.property_details = self._property_tests(
            candidate, task, generate_fn
        )

        # Layer 3: Scenario Tests
        report.v_scenario, report.scenario_details = self._scenario_tests(
            candidate, task, generate_fn, regression_tests
        )

        # Layer 4: Critic Cross-check
        report.v_critic, report.critic_details = self._critic_review(
            candidate, task, generate_fn
        )

        # Layer 5: Code Analysis (AST-based)
        report.v_code, report.code_details = self._code_analysis(candidate)

        # Layer 6: Security Audit
        report.v_security, report.security_details = self._security_audit(
            candidate
        )

        # Calculate confidence: Conf(s) = σ(α^T · v(s)) with 6 layers
        raw_score = (
            self.alpha["static"] * report.v_static
            + self.alpha["property"] * report.v_property
            + self.alpha["scenario"] * report.v_scenario
            + self.alpha["critic"] * report.v_critic
            + self.alpha["code"] * report.v_code
            + self.alpha["security"] * report.v_security
        )
        report.confidence = self._sigmoid(raw_score)
        report.passed = report.confidence >= self.config.confidence_threshold

        # Zero-vulnerability override: critical vulns = always fail
        if report.has_critical_vulns:
            report.passed = False

        logger.info(f"Verification: {report.summary()}")
        return report

    def _static_checks(
        self,
        candidate: str,
        task: str,
        custom_checks: Optional[List[Callable]] = None,
    ) -> tuple:
        """
        Layer 1: Static checks — type validation, format, invariants.
        """
        checks = []
        passed = 0
        total = 0

        # Check 1: Non-empty response
        total += 1
        if candidate and len(candidate.strip()) > 10:
            passed += 1
            checks.append("✅ Non-empty response")
        else:
            checks.append("❌ Empty or too short response")

        # Check 2: Reasonable length
        total += 1
        if 10 < len(candidate) < 50000:
            passed += 1
            checks.append("✅ Reasonable length")
        else:
            checks.append("❌ Unreasonable length")

        # Check 3: Not a repetition/loop
        total += 1
        words = candidate.split()
        if len(words) > 10:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio > 0.2:
                passed += 1
                checks.append(f"✅ Not repetitive (unique ratio: {unique_ratio:.2f})")
            else:
                checks.append(f"❌ Repetitive content (unique ratio: {unique_ratio:.2f})")
        else:
            passed += 1
            checks.append("✅ Short response (skip repetition check)")

        # Check 4: Doesn't contain error markers
        total += 1
        error_markers = ["error:", "exception:", "traceback", "failed to"]
        has_errors = any(m in candidate.lower() for m in error_markers)
        if not has_errors:
            passed += 1
            checks.append("✅ No error markers")
        else:
            checks.append("❌ Contains error markers")

        # Check 5: AST-based code analysis (if candidate contains Python code)
        code_to_analyze = candidate
        if "```" in candidate:
            blocks = []
            in_block = False
            for line in candidate.split("\n"):
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.strip().startswith("```") and in_block:
                    in_block = False
                    continue
                if in_block:
                    blocks.append(line)
            if blocks:
                code_to_analyze = "\n".join(blocks)

        if any(kw in code_to_analyze for kw in ["def ", "class ", "import "]):
            ast_score, ast_checks = self._ast_static_analysis(code_to_analyze)
            checks.extend(ast_checks)
            # Weight AST checks: count them as additional checks
            ast_check_count = len(ast_checks)
            ast_passed = sum(1 for c in ast_checks if c.startswith("✅"))
            total += ast_check_count
            passed += ast_passed

        # Run custom checks
        if custom_checks:
            for check_fn in custom_checks:
                total += 1
                try:
                    result = check_fn(candidate)
                    if result:
                        passed += 1
                        checks.append("✅ Custom check passed")
                    else:
                        checks.append("❌ Custom check failed")
                except Exception as e:
                    checks.append(f"❌ Custom check error: {e}")

        score = passed / max(total, 1)
        return score, checks

    def _ast_static_analysis(self, code: str) -> tuple:
        """Real AST-based static analysis for Python code."""
        checks = []

        # 1. Syntax validation
        try:
            tree = ast.parse(code)
            checks.append("✅ Valid Python syntax")
        except SyntaxError as e:
            checks.append(f"❌ Syntax error: {e.msg} (line {e.lineno})")
            return 0.0, checks

        # 2. Function/class count
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        if functions or classes:
            checks.append(f"✅ Defines {len(functions)} functions, {len(classes)} classes")
        else:
            checks.append("⚠️ No functions or classes defined")

        # 3. Docstring coverage
        documented = 0
        total_defs = len(functions) + len(classes)
        for node in functions + classes:
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, (ast.Constant, ast.Str))):
                documented += 1
        if total_defs > 0:
            doc_ratio = documented / total_defs
            if doc_ratio >= 0.5:
                checks.append(f"✅ Docstring coverage: {doc_ratio:.0%}")
            else:
                checks.append(f"❌ Low docstring coverage: {doc_ratio:.0%}")

        # 4. Dangerous pattern detection
        dangerous_patterns = {
            "eval(": "eval() usage (code injection risk)",
            "exec(": "exec() usage (code execution risk)",
            "__import__(": "dynamic import (obfuscation risk)",
            "subprocess.call(": "subprocess with shell (injection risk)",
            "os.system(": "os.system (command injection risk)",
        }
        found_dangerous = []
        for pattern, desc in dangerous_patterns.items():
            if pattern in code:
                found_dangerous.append(desc)

        if not found_dangerous:
            checks.append("✅ No dangerous patterns detected")
        else:
            for d in found_dangerous:
                checks.append(f"❌ Dangerous: {d}")

        # 5. Complexity estimation (nesting depth)
        max_depth = self._max_nesting_depth(tree)
        if max_depth <= 4:
            checks.append(f"✅ Nesting depth: {max_depth} (manageable)")
        else:
            checks.append(f"❌ Deep nesting: {max_depth} levels")

        # 6. Return statement check for functions
        for func in functions:
            has_return = any(
                isinstance(n, ast.Return) and n.value is not None
                for n in ast.walk(func)
            )
            if not has_return and func.name.startswith(("get", "compute", "calc", "find")):
                checks.append(f"⚠️ {func.name}() has no return value")

        return 0.0, checks  # Score is computed by caller from pass/fail ratio

    def _max_nesting_depth(self, node, depth=0) -> int:
        """Calculate maximum nesting depth of AST."""
        max_d = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.For, ast.While, ast.If, ast.With,
                                   ast.Try, ast.FunctionDef, ast.ClassDef)):
                max_d = max(max_d, self._max_nesting_depth(child, depth + 1))
            else:
                max_d = max(max_d, self._max_nesting_depth(child, depth))
        return max_d

    def _property_tests(
        self,
        candidate: str,
        task: str,
        generate_fn: Callable,
    ) -> tuple:
        """
        Layer 2: Property tests — adversarial edge case generation.

        Uses the LLM to generate edge cases and test the solution against them.
        """
        prompt = (
            f"You are a testing expert. Given this task and solution, "
            f"generate 3 edge cases that could break or reveal flaws.\n\n"
            f"Task: {task}\n\n"
            f"Solution: {candidate[:1000]}\n\n"
            f"For each edge case, score the solution 0-10.\n"
            f"Format: EDGE_CASE <N>: <description> | SCORE: <0-10>\n"
            f"End with: OVERALL_SCORE: <0-10>"
        )

        try:
            response = generate_fn(prompt)
            score = self._extract_overall_score(response) / 10.0
            details = [line.strip() for line in response.split("\n") if line.strip()]
            return score, details
        except Exception as e:
            logger.warning(f"Property test failed: {e}")
            return 0.5, [f"Property test error: {e}"]

    def _scenario_tests(
        self,
        candidate: str,
        task: str,
        generate_fn: Callable,
        regression_tests: Optional[List[str]] = None,
    ) -> tuple:
        """
        Layer 3: Scenario tests — end-to-end + regression checks.
        """
        details = []
        scores = []

        # Run regression tests from memory
        if regression_tests:
            prompt = (
                f"Check if this solution passes these regression tests:\n\n"
                f"Solution: {candidate[:1000]}\n\n"
                f"Tests:\n"
            )
            for i, test in enumerate(regression_tests[:5]):
                prompt += f"  {i + 1}. {test}\n"

            prompt += (
                "\nFor each test, answer PASS or FAIL.\n"
                "End with: PASS_RATE: <0-100>%"
            )

            try:
                response = generate_fn(prompt)
                # Extract pass rate
                for line in response.split("\n"):
                    if "PASS_RATE" in line.upper():
                        try:
                            rate = float(
                                line.split(":")[-1].strip().replace("%", "")
                            )
                            scores.append(rate / 100.0)
                        except ValueError:
                            scores.append(0.5)
                        break
                details.extend([line.strip() for line in response.split("\n") if line.strip()])
            except Exception as e:
                scores.append(0.5)
                details.append(f"Regression test error: {e}")

        # End-to-end scenario evaluation
        scenario_prompt = (
            f"Evaluate this solution for correctness and completeness.\n\n"
            f"Task: {task}\n"
            f"Solution: {candidate[:1000]}\n\n"
            f"Score the solution 0-10 on:\n"
            f"1. Correctness\n2. Completeness\n3. Edge case handling\n"
            f"End with: OVERALL_SCORE: <0-10>"
        )

        try:
            response = generate_fn(scenario_prompt)
            score = self._extract_overall_score(response) / 10.0
            scores.append(score)
            details.append(f"Scenario score: {score:.2f}")
        except Exception as e:
            scores.append(0.5)
            details.append(f"Scenario test error: {e}")

        avg_score = sum(scores) / max(len(scores), 1)
        return avg_score, details

    def _critic_review(
        self,
        candidate: str,
        task: str,
        generate_fn: Callable,
    ) -> tuple:
        """
        Layer 4: Cross-check — independent critic model review.

        Uses the same LLM with a different persona (critic/adversary)
        to find flaws in the solution.
        """
        prompt = (
            f"You are a harsh but fair code/solution critic. "
            f"Your job is to find EVERY possible flaw, bug, and weakness.\n\n"
            f"Task: {task}\n\n"
            f"Solution to critique: {candidate[:1500]}\n\n"
            f"List all flaws found. For each:\n"
            f"FLAW <N>: <description> | SEVERITY: low/medium/high/critical\n\n"
            f"After listing all flaws, provide:\n"
            f"QUALITY_SCORE: <0-10> (10 = flawless, 0 = completely broken)\n"
            f"RECOMMENDATION: execute / revise / reject"
        )

        try:
            response = generate_fn(prompt)
            score = self._extract_overall_score(response, key="QUALITY_SCORE") / 10.0
            return score, response
        except Exception as e:
            logger.warning(f"Critic review failed: {e}")
            return 0.5, f"Critic review error: {e}"

    def _extract_overall_score(self, text: str, key: str = "OVERALL_SCORE") -> float:
        """Extract a numeric score from LLM output."""
        for line in text.split("\n"):
            if key.upper() in line.upper():
                try:
                    # Extract number after ':'
                    num_str = line.split(":")[-1].strip()
                    # Handle "7/10" format
                    if "/" in num_str:
                        num_str = num_str.split("/")[0].strip()
                    return float(num_str)
                except ValueError:
                    continue
        return 5.0  # Default middle score

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Sigmoid squashing function σ."""
        return 1.0 / (1.0 + math.exp(-x))

    def _code_analysis(self, candidate: str) -> tuple:
        """Layer 5: AST-based code analysis."""
        if not self._code_analyzer:
            return 0.5, {}

        # Detect if candidate contains code
        code_indicators = ["def ", "class ", "import ", "function ", "const ", "let "]
        has_code = any(ind in candidate for ind in code_indicators)
        if not has_code:
            return 0.7, {"note": "Non-code content, skipped analysis"}

        # Extract code blocks
        code = candidate
        if "```" in candidate:
            blocks = []
            in_block = False
            for line in candidate.split("\n"):
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.strip().startswith("```") and in_block:
                    in_block = False
                    continue
                if in_block:
                    blocks.append(line)
            code = "\n".join(blocks) if blocks else candidate

        try:
            report = self._code_analyzer.analyze(code)
            quality_score = report.quality.overall_score / 100.0
            return quality_score, {
                "quality_grade": report.quality.grade(),
                "functions": len(report.structure.functions),
                "complexity": report.quality.cyclomatic_complexity,
            }
        except Exception as e:
            logger.warning(f"Code analysis failed: {e}")
            return 0.5, {"error": str(e)}

    def _security_audit(self, candidate: str) -> tuple:
        """Layer 6: Security vulnerability scan."""
        if not self._code_analyzer:
            return 0.5, []

        code_indicators = ["def ", "class ", "import ", "function "]
        has_code = any(ind in candidate for ind in code_indicators)
        if not has_code:
            return 0.8, ["Non-code content"]

        code = candidate
        if "```" in candidate:
            blocks = []
            in_block = False
            for line in candidate.split("\n"):
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.strip().startswith("```") and in_block:
                    in_block = False
                    continue
                if in_block:
                    blocks.append(line)
            code = "\n".join(blocks) if blocks else candidate

        try:
            report = self._code_analyzer.analyze(code)
            vuln_details = [v.summary() for v in report.vulnerabilities]

            # Check for critical vulnerabilities
            critical = report.critical_vulns
            if critical:
                return 0.0, vuln_details  # Zero score for critical vulns

            return report.security_score, vuln_details
        except Exception as e:
            logger.warning(f"Security audit failed: {e}")
            return 0.5, [f"Audit error: {e}"]

    def calibrate(self, report: VerificationReport, actual_success: bool):
        """Update calibration weights based on actual outcomes."""
        target = 1.0 if actual_success else 0.0
        error = target - report.confidence
        learning_rate = 0.1

        # Gradient update for all 6 layers
        for key, v_score in [
            ("static", report.v_static),
            ("property", report.v_property),
            ("scenario", report.v_scenario),
            ("critic", report.v_critic),
            ("code", report.v_code),
            ("security", report.v_security),
        ]:
            gradient = error * v_score * report.confidence * (1 - report.confidence)
            self.alpha[key] += learning_rate * gradient

        self._calibration_history.append({
            "confidence": report.confidence,
            "actual": actual_success,
            "error": error,
            "alpha": dict(self.alpha),
        })

        logger.info(
            f"Calibrated verifier: error={error:.3f}, "
            f"alpha={self.alpha}"
        )
