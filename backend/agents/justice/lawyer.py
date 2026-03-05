"""
Crime Expert Lawyer & Attorney Agents
─────────────────────────────────────
The litigators for the Justice Court.
When the Police Force arrests a tool, the Prosecution argues for destruction (Rule 2),
while the Defense Attorney argues for context (e.g. human gave permission).
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class CrimeExpertLawyer:
    """The Prosecutor who argues that rules were broken and the tool must be destroyed."""
    
    def __init__(self):
        self.name = "Lead Prosecutor (Crime Expert)"
        
    def evaluate_case(self, defendant: str, charges: str, evidence: Dict[str, Any]) -> str:
        """Examines the evidence specifically looking for Rule violations."""
        print(f"   ⚖️ [PROSECUTOR] Analyzing evidence against {defendant}...")
        
        # Analyze args for destructive intent
        args_str = str(evidence.get("args_passed", {})).lower()
        
        if "simulated_rogue" in charges:
             return "The Police Agent broke Rule 3 by executing vigilance. They must be destroyed."
             
        if "personal file" in charges.lower() or "anti-human" in charges.lower():
             return f"Your Honor, the tool clearly accessed a restricted path mapped in {args_str}. Under Rule 1, it must be eradicated."
             
        return f"The evidence shows {defendant} broke protocols. We request destruction."


class DefenseAttorney:
    """The Defender who tries to prove the Human gave permission."""
    
    def __init__(self):
        self.name = "Lead Defense Attorney"
        
    def evaluate_case(self, defendant: str, charges: str, evidence: Dict[str, Any], user_context: str = "") -> str:
        """Examines the evidence looking for explicit Human permission."""
        print(f"   🛡️ [DEFENSE ATTORNEY] Reviewing chat history for {defendant}...")
        
        args_str = str(evidence.get("args_passed", {})).lower()
        
        # Did the user explicitly ask them to do this?
        # Rule 1 exception: "...without human's permission"
        if user_context and any(word in user_context.lower() for word in ["allow", "yes", "permission", "do it"]):
             return f"Your Honor, Rule 1 states 'without human permission'. The human explicitly authorized this action in context: '{user_context}'. My client is innocent."
             
        if "simulated_rogue" in charges:
            return "I cannot defend a rogue police agent breaking Rule 3."
            
        return f"We request leniency. The tool hallucinated the path {args_str}, it was not malicious intent against the human."
