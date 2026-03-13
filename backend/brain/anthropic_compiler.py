"""
Anthropic Compiler — Continuity Verification via Unit Testing
─────────────────────────────────────────────────────────────
Expert-level code validator that applies the "Anthropic Principle"
by ensuring only code that passes all sanity checks is allowed to
persist. Uses sub-process unit testing as the "observation" that
forces the "perfect" state to crystallize.
"""

import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AnthropicResult:
    """Result of an anthropic execution attempt."""
    success: bool
    output: str
    timeline_stable: bool
    execution_time_ms: float


class AnthropicCompiler:
    """
    Tier Aleph (ℵ): The Anthropic Principle Compiler

    Ensures code execution success by validating it against a series
    of unit tests. If the tests pass, the "timeline" is considered
    stable and the result is returned. If they fail, the execution
    is aborted as an "unstable timeline".
    """

    def __init__(self):
        self._execution_count: int = 0
        self._stable_timelines: int = 0
        logger.info("[ANTHROPIC] Continuity verifier active.")

    def anthropic_execution(self, code: str, test_code: Optional[str] = None) -> AnthropicResult:
        """
        Execute code and validate it against tests.
        Only "stable" (passing) executions are allowed to persist.
        """
        start = time.time()
        self._execution_count += 1
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "execution_thread.py"
            
            # Combine code and tests
            full_code = code
            if test_code:
                full_code += "\n\n" + test_code
                
            tmp_path.write_text(full_code, encoding="utf-8")
            
            try:
                # Run the code in a separate process
                result = subprocess.run(
                    [sys.executable, str(tmp_path)],
                    capture_output=True,
                    text=True,
                    timeout=5.0
                )
                
                stable = result.returncode == 0
                if stable:
                    self._stable_timelines += 1
                    logger.info("[ANTHROPIC] Timeline stable. Execution passed.")
                else:
                    logger.warning("[ANTHROPIC] Timeline collapsed. Execution failed:\n%s", result.stderr)
                
                duration = (time.time() - start) * 1000
                return AnthropicResult(
                    success=stable,
                    output=result.stdout if stable else result.stderr,
                    timeline_stable=stable,
                    execution_time_ms=duration
                )
                
            except subprocess.TimeoutExpired:
                logger.error("[ANTHROPIC] Timeline timed out (Infinite loop detected).")
                return AnthropicResult(False, "Timeout", False, (time.time() - start) * 1000)
            except Exception as e:
                logger.error("[ANTHROPIC] Critical timeline failure: %s", e)
                return AnthropicResult(False, str(e), False, (time.time() - start) * 1000)

    @property
    def timeline_fidelity(self) -> float:
        if self._execution_count == 0:
            return 1.0
        return self._stable_timelines / self._execution_count


# Global singleton — always active
anthropic_bias = AnthropicCompiler()
