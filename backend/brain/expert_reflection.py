"""
Expert Reflection Engine — The 5 Whys & First Principles
────────────────────────────────────────────────────────
Rather than generic "confidence low" error tracking, this engine takes 
failed ideas and deduces the exact logical or mathematical flaw, generating 
Universal "First Principles" to inject into future reasoning contexts.
"""

import json
import logging
from typing import Callable, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExpertPrinciple:
    """A universally abstracted lesson derived from a complex success."""
    domain: str
    problem_context: str
    root_insight: str
    actionable_rule: str
    
    def format_for_prompt(self) -> str:
        return f"AXIOM ({self.domain}): {self.actionable_rule} (Insight: {self.root_insight})"


class ExpertReflectionEngine:
    """
    Deduces exact root causes for failures and extracts First Principles
    from complex successes, drastically accelerating the brain's learning curve.
    """
    
    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        
    def deduce_root_cause(
        self, 
        problem: str, 
        failed_candidate: str, 
        verifier_feedback: str
    ) -> str:
        """
        Runs a deep "5-Whys" post-mortem on a failed attempt.
        Returns a concise, deeply logical root-cause deduction.
        """
        prompt = f"""
You are an Expert Systems Architect diagnosing a logic failure.
The following solution failed to solve the target problem.

TARGET PROBLEM: {problem[:500]}
...

FAILED SOLUTION:
{failed_candidate[:800]}
...

VERIFIER FEEDBACK:
{verifier_feedback}

YOUR DIRECTIVE:
Do not summarize the error. Deduce the fundamental root cause. 
What mathematical, logical, or architectural assumption was violated here?
Respond in exactly one highly-technical, concise sentence.
"""
        try:
            cause = self.generate_fn(prompt).strip()
            logger.info(f"🧠 Deduced Root Cause: {cause}")
            return cause
        except Exception as e:
            logger.error(f"Failed to deduce root cause: {e}")
            return "Logical deduction failed: Verifier confidence threshold not met."

    def extract_first_principle(
        self, 
        problem: str, 
        successful_solution: str, 
        domain: str = "general"
    ) -> Optional[ExpertPrinciple]:
        """
        Abstracts a specific successful solution into a universal cognitive rule.
        """
        prompt = f"""
You are the Chief Scientist of a neural network. 
The system successfully solved a complex problem. You must extract a "First Principle" 
from this success so the system can reuse the core logic in entirely different scenarios.

PROBLEM: {problem[:500]}
...
SUCCESSFUL SOLUTION:
{successful_solution[:800]}

YOUR DIRECTIVE:
Output a pure JSON object containing exactly two keys:
1. "root_insight": The abstract, universal mathematical/architectural reason why this worked.
2. "actionable_rule": A specific, 1-sentence command the system must follow in the future.

Example:
{{
  "root_insight": "Stateful concurrent operations require absolute immutability guarantees outside the closure.",
  "actionable_rule": "Always freeze context data structures before passing them to multi-threaded executor pools."
}}
"""
        try:
            response = self.generate_fn(prompt)
            # Find JSON block
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                principle = ExpertPrinciple(
                    domain=domain,
                    problem_context=problem[:100],
                    root_insight=data.get("root_insight", ""),
                    actionable_rule=data.get("actionable_rule", "")
                )
                logger.info(f"💎 Abstracted First Principle: {principle.actionable_rule}")
                return principle
        except Exception as e:
            logger.error(f"Failed to extract first principle: {e}")
            
        return None
