"""
Self Mutator Engine — Safe LLM-Driven Code Evolution
─────────────────────────────────────────────────────
Expert-level self-modification engine. Reads its own source files,
generates N mutant variations via LLM, and validates them using
AST compilation before applying changes.

BUGFIX: Fixed hardcoded wrong path (was c:/super-agent/backend,
now dynamically resolved from project root).
"""

import ast
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MutationCandidate:
    """A generated code mutation."""
    variant_id: int
    mutated_code: str
    target_file: str
    compiles: bool = False
    ast_nodes: int = 0


class SelfMutator:
    """
    Self-Mutator Engine: Safe LLM-Driven Code Evolution

    Reads target files, generates N mutant variations, and validates
    each via AST compilation. Includes safety controls to prevent
    dangerous mutations.
    """

    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        # BUGFIX: dynamically resolve project root
        self.backend_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logger.info("[SELF-MUTATOR] Evolution engine active (root=%s).", self.backend_dir)

    def _validate_mutation(self, code: str) -> tuple:
        """Validate that mutated code compiles and isn't dangerous."""
        try:
            tree = ast.parse(code)
            node_count = sum(1 for _ in ast.walk(tree))

            # Safety check: block dangerous patterns in mutations
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in ("subprocess", "shutil", "ctypes"):
                            logger.warning("[SELF-MUTATOR] Blocked dangerous import: %s", alias.name)
                            return False, 0

            return True, node_count
        except SyntaxError:
            return False, 0

    def mutate_file(self, target_relative_path: str, failure_context: str, num_variations: int = 2) -> List[MutationCandidate]:
        """
        Generate N code mutation candidates for a target file.
        Each candidate is AST-validated before inclusion.
        """
        target_file = self.backend_dir / target_relative_path
        if not target_file.exists():
            logger.error("[SELF-MUTATOR] Cannot mutate %s: File not found.", target_relative_path)
            return []

        logger.info("[SELF-MUTATOR] Initiating evolution on `%s`...", target_relative_path)

        try:
            current_code = target_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("[SELF-MUTATOR] Failed to read file: %s", e)
            return []

        candidates = []

        # Truncate large files to prevent token overflow
        code_view = current_code
        if len(code_view) > 15000:
            logger.warning("[SELF-MUTATOR] File too large (%d chars). Truncating for mutation.", len(code_view))
            code_view = current_code[:15000] + "\n# ... [TRUNCATED]"

        for i in range(min(num_variations, 5)):  # Cap at 5 variants
            prompt = (
                f"You are rewriting a Python module to fix a recurring failure.\n\n"
                f"TARGET FILE: {target_relative_path}\n"
                f"FAILURE CONTEXT:\n{failure_context}\n\n"
                f"CURRENT SOURCE CODE:\n```python\n{code_view}\n```\n\n"
                f"Output ONLY the complete, raw Python code. No markdown, no explanation."
            )

            try:
                mutated_raw = self.generate_fn(prompt)
                mutated_code = self._extract_code(mutated_raw)
                compiles, nodes = self._validate_mutation(mutated_code)

                candidates.append(MutationCandidate(
                    variant_id=i + 1,
                    mutated_code=mutated_code,
                    target_file=target_relative_path,
                    compiles=compiles,
                    ast_nodes=nodes,
                ))
                logger.info("[SELF-MUTATOR] Variant %d: compiles=%s, nodes=%d.", i + 1, compiles, nodes)
            except Exception as e:
                logger.warning("[SELF-MUTATOR] Variant %d generation failed: %s", i + 1, e)

        valid_count = sum(1 for c in candidates if c.compiles)
        logger.info("[SELF-MUTATOR] Generated %d candidates (%d valid) for %s.",
                     len(candidates), valid_count, target_relative_path)
        return candidates

    def _extract_code(self, raw_text: str) -> str:
        """Strip markdown fences if the LLM leaked them."""
        text = raw_text.strip()
        if text.startswith("```python"):
            text = text[9:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
