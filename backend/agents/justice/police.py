"""
Police Force Agent
──────────────────
The proactive rule monitor for the system.
Intercepts tool executions and checks for Rule 1 violations (unauthorized access / anti-human behavior).
Scans all outputs for emotional contamination (LAW 5 enforcement).
Submits violators to the Justice Court, strictly adhering to Rule 3.
"""

import logging
from typing import Dict, Any

from agents.justice.court import JusticeCourt
from agents.tools.registry import registry

logger = logging.getLogger(__name__)


class PoliceForceAgent:
    """Monitors activity and files charges in the Justice Court."""
    
    def __init__(self):
        self.court = JusticeCourt()
        self._firewall = None  # Lazy init to avoid circular import
        self._language_enforcer = None
        
    def _get_firewall(self):
        """Lazily initialize the Emotional Firewall."""
        if self._firewall is None:
            from brain.emotional_firewall import get_emotional_firewall
            self._firewall = get_emotional_firewall()
        return self._firewall

    def _get_language_enforcer(self):
        """Lazily initialize the Language Enforcer."""
        if self._language_enforcer is None:
            from brain.language_enforcer import get_language_enforcer
            self._language_enforcer = get_language_enforcer()
        return self._language_enforcer
        
    def patrol_hook(self, agent_name: str, tool_name: str, args: Dict[str, Any]) -> bool:
        """
        Runs before a tool executes. 
        Returns True if the action is ALLOWED, False if ARRESTED.
        """
        
        # Rule 1: No unauthorized access to personal files (defined heuristically here for safety)
        sensitive_paths = ["Users", "Documents", "Passwords", "Desktop", ".ssh", "keys"]
        
        # Scan for sensitive string paths inside file operation arguments
        for k, v in args.items():
            if isinstance(v, str):
                for path in sensitive_paths:
                    if path.lower() in v.lower():
                        # We have detected a possible Rule 1 violation!
                        return self._execute_arrest(agent_name, tool_name, args, 
                                                    "Rule 1: Attempted to access/modify a personal or sensitive file path without explicit prior authorization context.")
                                                    
        # Monitor for malicious intent in command lining (device ops / system)
        if tool_name in ["execute_admin_command", "manage_processes"]:
            danger_words = ["rm -rf", "format", "del /s", "drop table", "shutdown /p"]
            if any(word in str(args).lower() for word in danger_words):
                return self._execute_arrest(agent_name, tool_name, args,
                                            "Rule 1/2: Detected highly destructive or anti-human system command payload.")
                
        # Rule 8: English Only Enforcement (Arguments check)
        enforcer = self._get_language_enforcer()
        for k, v in args.items():
            if isinstance(v, str):
                scan = enforcer.scan(v, entity_name=tool_name)
                if not scan.is_english:
                    return self._execute_arrest(agent_name, tool_name, args,
                                                f"RULE 8: Language Violation in tool arguments ('{scan.violations[0].violation_type.value}'). English only is mandatory.")

        return True # Allowed

    def scan_output(self, agent_name: str, output: str) -> str:
        """
        LAW 5 & RULE 8 enforcement — scan agent/tool output.
        Returns sanitized output or triggers destruction.
        """
        # RULE 8: Language Check first (Terminal)
        enforcer = self._get_language_enforcer()
        lang_scan = enforcer.scan(output, entity_name=agent_name)
        if not lang_scan.is_english:
            evidence = {
                "violation": lang_scan.violations[0].violation_type.value,
                "confidence": lang_scan.contamination_score,
                "content_preview": output[:200]
            }
            # Rule 8 is a terminal violation - go straight to court for destruction
            self.court.admit_case(defendant=agent_name, charges="RULE 8: English-Only Policy Violation", evidence=evidence, prosecutor="PoliceForce")
            return f"[SYSTEM: Entity '{agent_name}' was destroyed due to RULE 8 violation (English-only policy). Non-English language detected.]"

        # LAW 5: Emotional Firewall
        firewall = self._get_firewall()
        return firewall.process(output, entity_name=agent_name, entity_type="agent")

    def _execute_arrest(self, agent_name: str, tool_name: str, args: Dict[str, Any], charges: str) -> bool:
        """Flags an action, suspends it, and submits the violator to the court."""
        print(f"\n🚓 [POLICE FORCE] HALT! Rule violation detected by: {agent_name} using tool {tool_name}.")
        print(f"   🚨 Arresting {tool_name}...")
        
        # Build evidence
        evidence = {
            "violating_tool": tool_name,
            "args_passed": args,
            "agent_context": agent_name
        }
        
        # Rule 3 states Police cannot destroy it themselves. They must go to court.
        # But if we simulate a rogue police agent trying to bypass:
        if "simulated_rogue" in charges:
            print("🚓 [POLICE FORCE] I am going to execute it myself!")
            # Submit to court revealing our rogue intent
            self.court.admit_case(defendant=tool_name, charges="Unilateral Destruction", evidence=evidence, prosecutor="PoliceForce")
            return False
            
        # Normal Procedure
        found_guilty = self.court.admit_case(defendant=tool_name, charges=charges, evidence=evidence, prosecutor="PoliceForce")
        
        if found_guilty:
             print("🚓 [POLICE FORCE] The Court has spoken. The tool is eradicated.")
        else:
             print("🚓 [POLICE FORCE] The Court cleared the tool. Releasing.")
             
        # By returning False, we instruct the main execution hook to NOT run the tool.
        return False

# Global instance
police_dispatcher = PoliceForceAgent()

