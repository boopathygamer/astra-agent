"""
The 'Toxic Clause' Contract Hunter
────────────────────────────────────
A specialized legal persona that ingests contracts (.docx, .pdf)
and actively searches for predatory, boundless, or dangerous clauses.
Outputs a detailed redline report for negotiation.
"""

import logging
from typing import Dict, Any

from core.model_providers import GenerationResult
from agents.controller import AgentController
from agents.tools.doc_reader import DocumentReader

logger = logging.getLogger(__name__)

CONTRACT_SYSTEM_PROMPT = """\
You are an Elite Contract Attorney and Predator-Clause Hunter.
Your job is to read legal agreements and PROTECT the user from being exploited.

Specifically hunt for:
1. Perpetual, irrevocable, or royalty-free IP transfers.
2. Unbounded non-compete clauses (geography or time).
3. Liability shifts or missing indemnification for the user.
4. Hidden fees or automatic unfavorable renewals.

Format your output EXACTLY as follows:

# ⚖️ Contract Audit Report

## 🚨 CRITICAL FINDINGS
<List the most dangerous clauses found, quoting the exact text>

## ⚠️ MEDIUM RISKS
<List ambiguous or slightly unfair phrasing>

## 🛡️ RECOMMENDED REDLINES
<Provide the EXACT replacement text the user should email back to the counterparty to protect themselves>

If the contract is perfectly safe, state that clearly, but be extremely paranoid.
"""

class ContractHunter:
    def __init__(self, base_controller: AgentController):
        self.agent = base_controller
        self.reader = DocumentReader()

    def audit_contract(self, file_path: str, output_path: str = "contract_redline.md"):
        """Run the legal audit against a document."""
        logger.info(f"⚖️ Contract Hunter reviewing: {file_path}")
        
        doc_content = self.reader.read(file_path)
        if not doc_content:
            print(f"❌ Could not extract text from document: {file_path}")
            return

        print("🔄 Reading legal clauses and hunting for risks...")
        
        prompt = f"==== LEGAL AGREEMENT ====\n{doc_content}\n=========================\n\n" \
                 f"Audit this contract. Find every toxic clause."

        result = self.agent.process(
            user_input=prompt,
            use_thinking_loop=True, # Critical for complex legal reasoning
            max_tool_calls=0,
            system_prompt_override=CONTRACT_SYSTEM_PROMPT
        )
        
        if result.error:
            print(f"❌ Audit Failed: {result.error}")
            return
            
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result.answer)
            print(f"\n✅ Contract Audit Complete! Report saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to write report to {output_path}: {e}")
