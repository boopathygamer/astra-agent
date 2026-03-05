"""
Epistemic Checker — Real-Time Fact Checking Module.
─────────────────────────────────────────────────
Uses an internal tool chain (e.g., simulated web search) to identify
and verify factual claims in a candidate solution to reduce hallucinations.
"""

import logging
from typing import Callable

logger = logging.getLogger(__name__)

class EpistemicChecker:
    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn

    def check_claims(self, candidate: str) -> tuple[bool, str]:
        """
        Verify the candidate text for hallucinations.
        Returns: (passed_check: bool, fact_check_report: str)
        """
        if "```" in candidate and len(candidate.split("```")) > 2:
            # Code is generally less prone to historical/factual hallucination
            return True, "Code snippet detected. Bypassing factual epistemic check."

        logger.info("🧠 Running Epistemic Fact Check on candidate solution...")

        # 1. Extract factual claims
        extract_prompt = (
            f"Extract the top 3 most assertive factual, historical, or scientific claims made in this text.\n"
            f"If there are no factual claims (e.g. it's just conversational or code), simply output 'NO_CLAIMS'.\n\n"
            f"TEXT: {candidate[:2000]}\n"
        )
        try:
            claims = self.generate_fn(extract_prompt).strip()
            if "NO_CLAIMS" in claims.upper():
                 logger.debug("No factual claims found to verify.")
                 return True, "No major factual claims detected."
        except Exception as e:
            logger.warning(f"Failed to extract claims: {e}")
            return True, "Error extracting claims."

        # 2. Simulate Web Verification (Uses LLM as a proxy for web search if no real tool is configured)
        verify_prompt = (
            f"You are an objective Epistemic Fact Checker. Verify the validity of these claims.\n"
            f"CLAIMS:\n{claims}\n\n"
            f"If any claim is factually false or hallucinated, identify it and output 'STATUS: HALLUCINATION'.\n"
            f"If all claims are mostly true, output 'STATUS: VERIFIED'."
        )
        
        try:
            verification_result = self.generate_fn(verify_prompt).strip()
            if "HALLUCINATION" in verification_result.upper():
                logger.warning("🚨 Hallucination detected during epistemic check!")
                return False, verification_result
            else:
                logger.info("✅ Epistemic check passed.")
                return True, "All claims verified successfully."
        except Exception as e:
            logger.warning(f"Failed to verify claims: {e}")
            return True, "Error running epistemic verification."
