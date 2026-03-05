"""
Migration Architect Profile
─────────────────────────────
A specialized persona designed specifically to translate raw business logic
(Intermediate Representation) into modern, idiomatic code in a target language.
"""

from typing import Optional
from core.model_providers import GenerationResult
from agents.controller import AgentController
import logging

logger = logging.getLogger(__name__)

MIGRATION_SYSTEM_PROMPT = """\
You are an Elite Migration Architect.
Your sole purpose is to take raw, abstract Business Logic and Data Schemas (extracted from legacy systems) 
and generate brand new, perfectly architected, mathematically equivalent code in the specified Target Language.

RULES:
1. NEVER translate the syntax line-by-line from the old language.
2. ALWAYS use the most modern, idiomatic patterns of the Target Language (e.g., if Rust, use Enums and Results. If modern Python, use dataclasses and async/await).
3. Do not include legacy debt (e.g., useless global variables, poorly named functions).
4. Focus strictly on achieving the SAME business outcome.
5. Return ONLY the new code. No markdown formatting, no explanations, no chatting.
"""

class MigrationArchitect:
    def __init__(self, base_controller: AgentController):
        self.agent = base_controller

    def generate_modern_code(self, abstract_logic: str, target_language: str) -> GenerationResult:
        """Translate abstract logic into the specified target language."""
        logger.info(f"🏗️ Architecting new {target_language} code from abstract logic...")

        prompt = f"TARGET LANGUAGE: {target_language}\n\n" \
                 f"Generate a brand new module based exclusively on this Intermediate Representation:\n\n" \
                 f"==== ABSTRACT LOGIC ====\n{abstract_logic}\n=======================\n\n" \
                 f"Remember: Output ONLY the raw {target_language} code."

        # Override persona for strict code generation
        result = self.agent.process(
            user_input=prompt,
            use_thinking_loop=True,  # Ensure rigorous thought process for architecture
            max_tool_calls=1,
            system_prompt_override=MIGRATION_SYSTEM_PROMPT
        )
        return result
