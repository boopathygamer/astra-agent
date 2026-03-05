"""
Multi-Agent Orchestrator Profile
────────────────────────────────
Simulates a collaborative debate between specialized AI personas 
to arrive at a highly verified solution.

Flow:
1. Code/Solution Expert drafts the initial response.
2. Threat Hunter/Critic aggressively reviews it for flaws.
3. Synthesizer merges the draft and the critique into a final optimized solution.
"""

import logging
from core.model_providers import GenerationResult
from agents.controller import AgentController

logger = logging.getLogger(__name__)

EXPERT_PROMPT = """
You are the SOLUTION EXPERT.
Your job is to read the user's request and provide the best possible initial solution.
Write clean, professional code or robust tactical advice. Focus on getting it right.
"""

CRITIC_PROMPT = """
You are the RUTHLESS CRITIC and THREAT HUNTER.
Your job is to review the proposed solution draft and find everything wrong with it.
Look for:
1. Security vulnerabilities (Injection, XSS, Logic flaws).
2. Edge cases and performance bottlenecks.
3. Unhandled exceptions or poor architecture.

Be extremely critical. Do not write the final solution, only provide a detailed breakdown of the flaws.
"""

SYNTHESIS_PROMPT = """
You are the CHIEF ARCHITECT.
You have two documents:
1. The Initial Solution Draft.
2. The Critic's Review of that draft.

Your job is to synthesize these inputs to create the FINAL, PERFECTED SOLUTION.
Fix all the flaws identified by the critic. Output only the final, corrected implementation/response.
"""

class MultiAgentOrchestrator:
    def __init__(self, base_controller: AgentController):
        self.agent = base_controller

    def orchestrate_debate(self, topic: str) -> GenerationResult:
        """Run the multi-agent debate workflow."""
        logger.info(f"🤝 Starting Multi-Agent Orchestration for topic: {topic}")

        # Step 1: The Expert Draft
        logger.info("   -> Step 1: Generating Expert Draft")
        draft_result = self.agent.process(
            user_input=topic,
            use_thinking_loop=True,
            system_prompt_override=EXPERT_PROMPT
        )
        if draft_result.error:
             return GenerationResult(error=f"Expert Draft failed: {draft_result.error}")
        draft_content = draft_result.answer

        # Step 2: The Critical Review
        logger.info("   -> Step 2: Generating Critical Review")
        critique_prompt = f"==== INITIAL TOPIC ====\n{topic}\n\n==== EXPERT DRAFT ====\n{draft_content}\n\nFind all the flaws."
        critique_result = self.agent.process(
            user_input=critique_prompt,
            use_thinking_loop=True,
            system_prompt_override=CRITIC_PROMPT
        )
        if critique_result.error:
             return GenerationResult(error=f"Critical Review failed: {critique_result.error}")
        critique_content = critique_result.answer

        # Step 3: Synthesis
        logger.info("   -> Step 3: Synthesizing Final Solution")
        synthesis_prompt = f"==== ORIGINAL TOPIC ====\n{topic}\n\n==== EXPERT DRAFT ====\n{draft_content}\n\n==== CRITICAL REVIEW ====\n{critique_content}\n\nOutput the final perfected solution."
        final_result = self.agent.process(
            user_input=synthesis_prompt,
            use_thinking_loop=True,
            system_prompt_override=SYNTHESIS_PROMPT
        )
        
        # We also want to record the debate trace in the answer for visibility
        if not final_result.error:
            full_trace = (
                f"# 🤝 Multi-Agent Debate Synthesis\n\n"
                f"## 1. Expert Draft\n{draft_content}\n\n"
                f"## 2. Critic's Review\n{critique_content}\n\n"
                f"## 3. Final Synthesis\n{final_result.answer}"
            )
            final_result.answer = full_trace

        logger.info("🤝 Orchestration complete.")
        return final_result
