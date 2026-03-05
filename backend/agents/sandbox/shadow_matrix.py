"""
The Shadow Matrix — Hardened Isolated Execution
────────────────────────────────────────────────
An isolated hyper-execution environment used exclusively by the
Synthesized Consciousness Engine to benchmark self-mutated brain code
against regression tests before committing them to the master branch.

Uses HardenedExecutor for real process isolation, memory limits,
and import restrictions. Falls back to CodeExecutor if unavailable.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# Try hardened executor first, fall back to basic
try:
    from agents.sandbox.hardened_executor import HardenedExecutor, SandboxConfig
    _HAS_HARDENED = True
except ImportError:
    _HAS_HARDENED = False

try:
    from agents.tools.code_executor import CodeExecutor
    _HAS_BASIC = True
except ImportError:
    _HAS_BASIC = False


@dataclass
class GauntletConfig:
    """Configuration for Shadow Matrix test runs."""
    timeout_per_test: int = 10
    max_memory_mb: int = 128
    require_flawless: bool = True  # Must pass 100% to win
    max_tests: int = 50
    use_hardened: bool = True


@dataclass
class GauntletReport:
    """Detailed report from a Shadow Matrix gauntlet run."""
    target_file: str = ""
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    win_rate: float = 0.0
    overall_passed: bool = False
    total_duration_ms: float = 0.0
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    executor_type: str = ""


class ShadowMatrix:
    def __init__(self, config: GauntletConfig = None):
        self._config = config or GauntletConfig()

        # Initialize executor
        if self._config.use_hardened and _HAS_HARDENED:
            sandbox_cfg = SandboxConfig(
                timeout_seconds=self._config.timeout_per_test,
                max_memory_mb=self._config.max_memory_mb,
            )
            self.executor = HardenedExecutor(default_config=sandbox_cfg)
            self._executor_type = "hardened"
            logger.info("🕶️ Shadow Matrix initialized with HardenedExecutor (process isolation)")
        elif _HAS_BASIC:
            from agents.tools.code_executor import CodeExecutor
            self.executor = CodeExecutor()
            self._executor_type = "basic"
            logger.warning("🕶️ Shadow Matrix using basic CodeExecutor (no process isolation)")
        else:
            self.executor = None
            self._executor_type = "none"
            logger.error("🕶️ Shadow Matrix has no executor available")

    def run_gauntlet(
        self,
        mutated_code: str,
        target_file_name: str,
        regression_tests: List[str],
        config: GauntletConfig = None,
    ) -> tuple[bool, str]:
        """
        Runs the mutated codebase against past failure tests in memory.
        Returns (passed_all, matrix_report_string).
        """
        cfg = config or self._config
        logger.info(f"🕶️ Entering The Shadow Matrix: Benchmarking mutated `{target_file_name}`...")
        logger.info(f"   Executor: {self._executor_type} | Timeout: {cfg.timeout_per_test}s | "
                     f"Memory limit: {cfg.max_memory_mb}MB")

        if self.executor is None:
            return False, "Aborted: No executor available."

        if not regression_tests:
            logger.warning("No regression tests mapped for this mutation. Blind acceptance is too dangerous.")
            return False, "Aborted: Zero regression tests available."

        # Cap tests
        tests = regression_tests[:cfg.max_tests]
        successful_tests = 0
        total_tests = len(tests)
        report_lines = []
        test_results = []
        overall_start = time.perf_counter()

        for i, test in enumerate(tests):
            logger.info(f"   -> Shadow Matrix Test {i+1}/{total_tests}...")
            matrix_simulation = f"{mutated_code}\n\n# --- REGRESSION TEST ---\n{test}\n"

            test_start = time.perf_counter()
            try:
                if self._executor_type == "hardened":
                    result = self.executor.execute(matrix_simulation)
                    has_error = not result.success
                    error_msg = result.error
                    test_duration = result.duration_ms
                    memory_kb = result.memory_peak_kb
                else:
                    result = self.executor.execute(matrix_simulation, timeout=cfg.timeout_per_test)
                    has_error = bool(result.error)
                    error_msg = result.error or ""
                    test_duration = (time.perf_counter() - test_start) * 1000
                    memory_kb = 0

                if has_error:
                    logger.warning(f"   ❌ Matrix Test {i+1} Failed: {error_msg[:200]}")
                    report_lines.append(f"Test {i+1} Failed: {error_msg[:200]}")
                    test_results.append({
                        "test_index": i + 1, "passed": False,
                        "error": error_msg[:200], "duration_ms": round(test_duration, 2),
                        "memory_kb": memory_kb,
                    })
                else:
                    logger.info(f"   ✅ Matrix Test {i+1} Passed.")
                    successful_tests += 1
                    report_lines.append(f"Test {i+1} Passed.")
                    test_results.append({
                        "test_index": i + 1, "passed": True,
                        "duration_ms": round(test_duration, 2),
                        "memory_kb": memory_kb,
                    })

            except Exception as e:
                return False, f"Matrix catastrophic crash: {e}"

        total_duration = (time.perf_counter() - overall_start) * 1000
        win_rate = successful_tests / total_tests if total_tests > 0 else 0
        passed = win_rate == 1.0 if cfg.require_flawless else win_rate >= 0.8

        if passed:
            logger.info(f"🟢 Shadow Matrix Protocol Completed: Flawless Victory. "
                        f"({total_duration:.0f}ms)")
            return True, "All tests passed cleanly in isolated benchmarking."
        else:
            logger.warning(f"🔴 Shadow Matrix Protocol Failed. Win Rate: {win_rate:.0%} "
                           f"({total_duration:.0f}ms)")
            return False, "\n".join(report_lines)
