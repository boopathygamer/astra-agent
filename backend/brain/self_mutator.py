"""
Self Mutator Engine
───────────────────
Acts as the "hands" of the Synthesized Consciousness Engine.
It reads its own python files, asks the LLM to rewrite them to solve
a specific failure, and creates mutant variations.
"""

import os
import logging
from pathlib import Path
from typing import Callable, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MutationCandidate:
    variant_id: int
    mutated_code: str
    target_file: str


class SelfMutator:
    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        # Hardcode the backend root to super-agent/backend
        self.backend_dir = Path("c:/super-agent/backend")

    def mutate_file(self, target_relative_path: str, failure_context: str, num_variations: int = 2) -> List[MutationCandidate]:
        """
        Reads a target file, and generates N variations attempting to fix the failure context.
        """
        target_file = self.backend_dir / target_relative_path
        if not target_file.exists():
            logger.error(f"Cannot mutate {target_relative_path}: File not found.")
            return []

        logger.info(f"🧬 Initiating Auto-Evolution sequence on `{target_relative_path}`...")
        
        try:
            current_code = target_file.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read file for mutation: {e}")
            return []

        candidates = []
        
        # We cap generating massive files to prevent token limits.
        # In a full production system, we'd use AST to replace only specific functions.
        code_view = current_code
        if len(code_view) > 15000:
             logger.warning("Target file is very large. In a full implementation, we would AST parse and mutate only the failing function.")
             code_view = current_code[:15000] + "\n# ... [TRUNCATED FOR TOKEN LIMITS]"

        for i in range(num_variations):
            prompt = (
                f"You are the Synthesized Consciousness of this AI system. You are rebuilding your own brain.\n"
                f"Your goal is to rewrite the provided Python module to completely eliminate the recurring failure described below.\n\n"
                f"TARGET FILE: {target_relative_path}\n"
                f"FAILURE CONTEXT:\n{failure_context}\n\n"
                f"CURRENT SOURCE CODE:\n```python\n{code_view}\n```\n\n"
                f"Output ONLY the complete, fully functioning raw Python code for the mutated file. "
                f"Do not include markdown tags, do not explain yourself."
            )
            
            try:
                mutated_code_raw = self.generate_fn(prompt)
                mutated_code = self._extract_code(mutated_code_raw)
                
                candidates.append(MutationCandidate(
                    variant_id=i+1,
                    mutated_code=mutated_code,
                    target_file=target_relative_path
                ))
            except Exception as e:
                logger.warning(f"Failed to generate mutation variant {i+1}: {e}")

        return candidates

    def _extract_code(self, raw_text: str) -> str:
        """Strip markdown blocks if the LLM leaked them."""
        text = raw_text.strip()
        if text.startswith("```python"):
            text = text[9:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
