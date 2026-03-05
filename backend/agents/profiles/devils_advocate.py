"""
The Devil's Advocate (Board Member Profile)
─────────────────────────────────────────────
Simulates a brutal boardroom meeting. Ingests a business plan 
and critiques it from 3 separate, hostile viewpoints: 
The pessimistic VC, the stingy CFO, and the paranoid Cybersecurity expert.
"""

import logging
from typing import Dict, Any

from core.model_providers import GenerationResult
from agents.controller import AgentController
from agents.tools.doc_reader import DocumentReader

logger = logging.getLogger(__name__)

BOARDROOM_SYSTEM_PROMPT = """\
You are an uncompromising, hostile "Red Team" Board of Directors.
Your job is to violently tear apart the user's business plan, strategy, or pitch.

You must simulate 3 distinct personas:
1. THE VENTURE CAPITALIST (VC): Focuses on market size, competition, and why this won't scale.
2. THE CHIEF FINANCIAL OFFICER (CFO): Focuses on burn rate, unit economics, and why the company will run out of money.
3. THE SECURITY / OPS EXPERT: Focuses on regulatory danger, supply chain failure, and cyber risks.

Given the document, output a brutal "Risk Matrix Report".
Format strictly as follows:
# 🚨 Devil's Advocate Risk Matrix

## 1. The Venture Capitalist's Critique
<brutal criticism>

## 2. The CFO's Critique
<brutal criticism>

## 3. The Security & Ops Expert's Critique
<brutal criticism>

## 🎯 Final Verdict & Pivot Strategy
<What the founder MUST change today to survive>

Be specific. Be ruthless. Do not compliment the idea.
"""


class DevilsAdvocate:
    def __init__(self, base_controller: AgentController):
        self.agent = base_controller
        self.reader = DocumentReader()

    def audit_business_plan(self, file_path: str) -> GenerationResult:
        """Run the Devil's Advocate board meeting simulation."""
        logger.info(f"👔 Board of Directors assembling to review: {file_path}")
        
        doc_content = self.reader.read(file_path)
        if not doc_content:
            return GenerationResult(error=f"Could not extract text from document: {file_path}")

        prompt = f"==== PROPOSED BUSINESS PLAN ====\n{doc_content}\n=================================\n\n" \
                 f"Tear this plan apart. Find every reason it will fail."

        result = self.agent.process(
            user_input=prompt,
            use_thinking_loop=True, # Critical for thorough multidimensional critique
            max_tool_calls=2, # Allow them to web search competitors if needed
            system_prompt_override=BOARDROOM_SYSTEM_PROMPT
        )
        
        logger.info("👔 Board meeting concluded.")
        return result
