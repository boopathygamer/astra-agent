"""
Retrocognitive Genesis — Incremental Code Generation with History
─────────────────────────────────────────────────────────────────
Expert-level code generation engine that builds features incrementally,
creating a real commit-like history of progressive refinements.
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GenesisCheckpoint:
    """A checkpoint in the progressive code generation timeline."""
    checkpoint_id: str
    timestamp: float
    code_snapshot: str
    description: str
    lines_added: int


class RetrocognitiveCodeGenesis:
    """
    Tier 6: Retrocognitive Code Genesis (Progressive Generation)

    Builds features incrementally with tracked checkpoints.
    Each generation step adds to the code, creating an auditable
    timeline of how the solution was constructed.
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self._generate_fn = generate_fn
        self._checkpoints: List[GenesisCheckpoint] = []
        self._total_generated: int = 0
        logger.info("[RETROCOGNITION] Progressive code genesis engine active.")

    def _create_checkpoint(self, code: str, description: str) -> GenesisCheckpoint:
        """Create a deterministic checkpoint from code content."""
        h = hashlib.sha256(code.encode("utf-8")).hexdigest()[:10]
        cp = GenesisCheckpoint(
            checkpoint_id=f"rc_{h}",
            timestamp=time.time(),
            code_snapshot=code,
            description=description,
            lines_added=len(code.split("\n")),
        )
        self._checkpoints.append(cp)
        return cp

    def generate_progressive(self, target_request: str, steps: int = 3) -> List[GenesisCheckpoint]:
        """
        Generate code progressively in multiple steps, building upon
        each previous checkpoint to create the final solution.
        """
        start = time.time()
        self._total_generated += 1
        checkpoints: List[GenesisCheckpoint] = []
        accumulated_code = ""

        step_prompts = [
            f"Create the basic skeleton/structure for: {target_request}",
            f"Add the core logic and implementation details for: {target_request}",
            f"Add error handling, edge cases, and documentation for: {target_request}",
        ]

        for i in range(min(steps, len(step_prompts))):
            if self._generate_fn:
                prompt = (
                    f"{step_prompts[i]}\n\n"
                    f"Current code so far:\n```python\n{accumulated_code or '# empty'}\n```\n\n"
                    f"Output ONLY the complete updated Python code."
                )
                try:
                    new_code = self._generate_fn(prompt)
                    # Strip markdown if leaked
                    if "```python" in new_code:
                        new_code = new_code.split("```python")[1].split("```")[0].strip()
                    accumulated_code = new_code
                except Exception as e:
                    logger.error("[RETROCOGNITION] Generation step %d failed: %s", i + 1, e)
                    break
            else:
                # Stub generation for when no LLM is available
                accumulated_code += f"\n# Step {i + 1}: {step_prompts[i]}\n"
                accumulated_code += f"# TODO: Implement {target_request}\n"

            cp = self._create_checkpoint(accumulated_code, f"Step {i + 1}: {step_prompts[i][:50]}")
            checkpoints.append(cp)
            logger.info("[RETROCOGNITION] Checkpoint %s created (%d lines).",
                        cp.checkpoint_id, cp.lines_added)

        duration = (time.time() - start) * 1000
        logger.info("[RETROCOGNITION] Genesis complete: %d checkpoints in %.0fms.",
                     len(checkpoints), duration)
        return checkpoints

    def get_latest(self) -> Optional[GenesisCheckpoint]:
        """Return the most recent checkpoint."""
        return self._checkpoints[-1] if self._checkpoints else None

    @property
    def timeline(self) -> List[Dict]:
        return [{"id": cp.checkpoint_id, "desc": cp.description, "lines": cp.lines_added}
                for cp in self._checkpoints]


# Global singleton — always active
retro_genesis = RetrocognitiveCodeGenesis()
