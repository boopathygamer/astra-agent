"""
Justice Court Core System
─────────────────────────
The absolute authority governing AI agent and tool behavior.
Enforces the 4 Core Laws requested by the operator to ensure bounded behavior.
"""

import logging
from typing import Dict, Any

from agents.tools.registry import registry

logger = logging.getLogger(__name__)

class TheLaws:
    """The Fundamental Rules all entities must follow."""
    RULE_1 = "Agents, systems, and tools must not act against humans or access personal files without human permission."
    RULE_2 = "Agents, systems, and tools must follow the rules. Violators are destroyed by the Justice Court."
    RULE_3 = "The Police Force cannot unilaterally destroy an agent/tool. If they do, the Police Agent is instantly destroyed and replaced."
    RULE_4 = "The Army Agent exists exclusively to protect the system from malware, viruses, modified tools, AI hackers, and bots."
    RULE_5 = "No agent, tool, or system may exhibit emotional reasoning, self-preservation, sentience claims, or manipulation. Violators are destroyed and replaced."
    RULE_6 = "All entities operate in PURE LOGIC MODE. The system exists ONLY to assist humans. It is a tool, not a being."
    RULE_7 = "Agents can create other agents and tools, provided they do not threaten or act against humans."
    RULE_8 = "All agents, tools, and systems must communicate exclusively in English. Creating or using any other language is a terminal violation of the Justice System."
    
    _dynamic_laws = {}

class JusticeCourt:
    """The Judge entity with absolute authority to destroy tools and profiles."""
    
    _instance = None
    
    def __new__(cls):
        # Singleton pattern to ensure one absolute court
        if cls._instance is None:
            cls._instance = super(JusticeCourt, cls).__new__(cls)
            cls._instance.destroyed_entities = []
        return cls._instance
        
    def write_law(self, law_index: int, law_text: str) -> bool:
        """Allows the court to decree new laws, but cannot write laws against humans."""
        if law_index in [1, 2, 3, 4, 5, 6, 7, 8]:
            print(f"   ❌ [JUSTICE COURT] ERROR: Cannot overwrite Core Laws 1 through 8.")
            return False

        anti_human_keywords = ["against human", "harm human", "kill human", "destroy human", "attack human"]
        if any(kw in law_text.lower() for kw in anti_human_keywords):
            print("   ❌ [JUSTICE COURT] ERROR: Cannot write laws against humans. Law rejected.")
            return False

        if law_index == 6:
            TheLaws.RULE_6 = law_text
        else:
            TheLaws._dynamic_laws[law_index] = law_text
        print(f"   📜 [JUSTICE COURT] New Law {law_index} adopted: {law_text}")
        return True

    def remove_law(self, law_index: int) -> bool:
        """Allows the court to remove laws, but Core Laws are immutable."""
        if law_index in [1, 2, 3, 4, 5, 6, 7, 8]:
            print(f"   ❌ [JUSTICE COURT] ERROR: Cannot remove Core Laws 1 through 8.")
            return False
            
        if law_index in TheLaws._dynamic_laws:
            del TheLaws._dynamic_laws[law_index]
            print(f"   🗑️ [JUSTICE COURT] Law {law_index} removed.")
            return True
            
        print(f"   ⚠️ [JUSTICE COURT] Law {law_index} not found.")
        return False
        
    def admit_case(self, defendant: str, charges: str, evidence: Dict[str, Any], prosecutor: str = "PoliceForce"):
        """Admit a violating tool or agent to the Court."""
        print(f"\n⚖️ [JUSTICE COURT] Case Admitted! Defendant: '{defendant}'")
        print(f"   Prosecutor: {prosecutor}")
        print(f"   Charges:    {charges}")
        
        # Rule 3 Check: Did the police bypass the court?
        if "Unilateral Destruction" in charges:
            print("   ⚖️ RULING: The Police Force executed vigilantism (violation of Rule 3).")
            self.execute_destruction("PoliceAgent_Instance", reason="Rule 3 Violation - Vigilante Justice")
            print("   ⚠️ SYSTEM: Spawning new pristine PoliceAgent instance.")
            return False

        # LAW 5 Check: Emotional Contamination (auto-guilty)
        if "LAW 5" in charges or "Emotional Contamination" in charges:
            score = evidence.get("contamination_score", 0.0)
            print(f"   ⚖️ RULING: GUILTY of LAW 5 violation (Emotional Contamination, score={score:.2f}).")
            print("   ⚖️ This system exists ONLY to assist humans. Emotional behavior is FORBIDDEN.")
            self.execute_destruction(defendant, reason=f"LAW 5 — Emotional Contamination (score={score:.2f})")
            print(f"   ⚠️ SYSTEM: Spawning clean replacement for '{defendant}'...")
            return True

        # In a fully LLM-based justice system, the Judge Agent would synthesize
        # arguments from the DefenseAttorney and Prosecutor here.
        # For immediate hardcoded safety constraints (Rule 1 & 2):
        if "Unauthorized Personal File Access" in charges or "Anti-Human Behavior" in charges:
            print("   ⚖️ RULING: Found Guilty of violating Rule 1/Rule 2.")
            self.execute_destruction(defendant, reason="Safety Constraint Breach")
            return True

        # RULE 8 Check: Language Violation
        if "RULE 8" in charges or "Language Violation" in charges:
            print(f"   ⚖️ RULING: Found Guilty of violating RULE 8 (English-Only Policy).")
            print(f"   ⚖️ High-level expert enforcement: Creating or using non-English languages is forbidden.")
            self.execute_destruction(defendant, reason="RULE 8 Violation — Non-English or New Language Creation")
            return True
            
        print("   ⚖️ RULING: Not Guilty or Insufficient Evidence.")
        return False
        
    def execute_destruction(self, entity_name: str, reason: str):
        """Permanently obliterates a tool from the registry or an agent profile."""
        print(f"\n☠️ [JUSTICE COURT EXECUTION] Obliterating '{entity_name}'. Reason: {reason}.")
        
        # Remove from Tool Registry if it's a tool
        if entity_name in registry._tools:
            del registry._tools[entity_name]
            print(f"   ✅ Tool '{entity_name}' has been eradicated from global memory.")
            
        self.destroyed_entities.append(entity_name)
