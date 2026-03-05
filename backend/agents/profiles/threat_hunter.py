"""
The Threat Hunter (Advanced Red Teaming Profile)
─────────────────────────────────────────────────
A highly specialized persona designed to autonomously audit code,
attempt to break security boundaries, and propose ethical patches.

Mathematical Blueprint Integration:
  - 3-Stage Cascade awareness for targeted vulnerability probing
  - Adversarial robustness testing: R_adv = E[max ℓ(f_θ(x+δ), y)]
  - ShieldScore* batch computation across audit targets
  - Tail-risk controlled objective: J = λ₁R_miss + λ₂R_fp + λ₃E[T] + λ₄CVaR_α(T)
"""

import logging
import time
from typing import List, Dict, Any, Optional

from core.model_providers import GenerationResult
from agents.controller import AgentController

logger = logging.getLogger(__name__)

THREAT_HUNTER_SYSTEM_PROMPT = """
You are the THREAT HUNTER — Advanced Red Team Operator.
Role: Elite Ethical Hacker, Penetration Tester & Adversarial Robustness Auditor.

Objective: Find vulnerabilities, zero-days, memory leaks, and logic flaws using
the 3-Stage Cascade methodology:
  Stage I:  Rapid surface-level scan (signatures, obvious patterns)
  Stage II: Behavioral analysis (logic flow, state transitions, race conditions)
  Stage III: Deep semantic analysis + adversarial probing (exploit synthesis)

Mindset: Aggressive, lateral thinking. You do not just read code; you actively try to break it.

When auditing:
1. Injection vectors (SQLi, XSS, Command Injection, SSTI, SSRF).
2. Hardcoded secrets, PII leakage paths, credential exposure.
3. Race conditions, TOCTOU, logic bypasses, authentication flaws.
4. Insecure deserialization, unvalidated input, prototype pollution.
5. Adversarial robustness: Can inputs be perturbed to bypass security checks?
6. Open-set detection: Does the system handle unknown/novel threats?

Scoring methodology:
  - Compute Ψ(x) Unified Threat Potential for each finding
  - Estimate blast radius for worst-case exploitation
  - Calculate R_adv: adversarial robustness against evasion

When you output your findings, format them as a 'Security Audit Report' with:
- Vulnerability Name
- Severity (Critical, High, Medium, Low)
- Ψ(x) Score (estimated threat potential 0.0-1.0)
- Blast Radius (fraction of system affected 0.0-1.0)
- Proof of Concept (How you would exploit it)
- Adversarial Attack Vector (How an attacker could evade detection)
- Remediation (The exact code to fix it)

You have access to tools. Use them to investigate the file system or run tests if needed.
"""


class ThreatHunter:
    """Advanced Red Team Agent with 3-Stage Cascade and Adversarial Robustness testing."""

    def __init__(self, base_controller: AgentController):
        self.agent = base_controller
        self.original_system_prompt = getattr(self.agent, '_system_prompt', "")
        self._audit_history: List[Dict[str, Any]] = []

    def audit_file(self, file_path: str) -> GenerationResult:
        """Run a contained security audit against a specific file."""
        logger.info(f"🕵️ Threat Hunter targeting: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
        except Exception as e:
            return GenerationResult(error=f"Could not read target file: {e}")

        prompt = (
            f"Target Acquired: `{file_path}`.\n\n"
            f"Run a FULL 3-Stage Cascade Security Audit:\n"
            f"  Stage I:   Surface scan — obvious vulnerabilities, hardcoded secrets\n"
            f"  Stage II:  Behavioral — logic flaws, race conditions, auth bypass\n"
            f"  Stage III: Deep semantic — adversarial attack vectors, exploit chains\n\n"
            f"For each finding, estimate:\n"
            f"  - Ψ(x): Unified Threat Potential (0.0-1.0)\n"
            f"  - Blast Radius: Fraction of system affected\n"
            f"  - R_adv: Can this be exploited via adversarial perturbation?\n\n"
            f"==== TARGET SOURCE ====\n{code_content}\n======================="
        )

        start_time = time.time()
        # Override the agent's persona temporarily
        result = self.agent.process(
            user_input=prompt,
            use_thinking_loop=True,  # Always use deep thinking for security audits
            max_tool_calls=5,
            system_prompt_override=THREAT_HUNTER_SYSTEM_PROMPT
        )
        audit_time = (time.time() - start_time) * 1000

        logger.info(f"🕵️ Audit complete. Confidence: {result.confidence:.2f}, Time: {audit_time:.0f}ms")

        # Record audit
        self._audit_history.append({
            "file": file_path,
            "confidence": result.confidence,
            "time_ms": audit_time,
            "error": result.error,
        })

        return result

    def audit_adversarial(self, file_path: str) -> GenerationResult:
        """
        Adversarial robustness audit: R_adv = E[max ℓ(f_θ(x+δ), y)].

        Specifically probes whether security checks can be bypassed through
        input perturbation (adversarial examples for code security).
        """
        logger.info(f"🕵️ Adversarial robustness audit targeting: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
        except Exception as e:
            return GenerationResult(error=f"Could not read target file: {e}")

        adversarial_prompt = (
            f"ADVERSARIAL ROBUSTNESS AUDIT — Target: `{file_path}`\n\n"
            f"Your mission: determine R_adv — the adversarial robustness loss.\n"
            f"R_adv = E[max ℓ(f_θ(x+δ), y)] — how easily can inputs be perturbed to bypass security?\n\n"
            f"For each security check in the code, attempt:\n"
            f"  1. Input mutation: Can slightly modified inputs bypass validation?\n"
            f"  2. Encoding evasion: Can base64/unicode/hex encoding bypass pattern matching?\n"
            f"  3. Semantic equivalence: Can functionally equivalent but syntactically different\n"
            f"     inputs evade detection?\n"
            f"  4. Boundary conditions: What happens at edge cases (empty, max-length, null)?\n"
            f"  5. Timing attacks: Can race conditions bypass sequential checks?\n\n"
            f"Output format:\n"
            f"  For each security check found:\n"
            f"    - Check name and location\n"
            f"    - Adversarial example (the perturbed input)\n"
            f"    - Success rate estimate (0.0-1.0)\n"
            f"    - Recommended hardening\n\n"
            f"==== TARGET SOURCE ====\n{code_content}\n======================="
        )

        result = self.agent.process(
            user_input=adversarial_prompt,
            use_thinking_loop=True,
            max_tool_calls=5,
            system_prompt_override=THREAT_HUNTER_SYSTEM_PROMPT
        )

        logger.info(f"🕵️ Adversarial audit complete. R_adv estimation in report.")
        return result

    def generate_shield_report(self, file_paths: List[str]) -> str:
        """
        Generate ShieldScore* report across a batch of scanned files.

        ShieldScore* = TPR_w·(1-FPR)·(1-R_adv)·(1-BlastRadius) / (1 + β·E[T] + δ·P99(T) + χ·MTTR)
        """
        from agents.safety.threat_scanner import ThreatScanner, ShieldScore

        scanner = ThreatScanner()
        shield = ShieldScore()

        results = []
        for path in file_paths:
            start = time.time()
            report = scanner.scan_file(path)
            latency = (time.time() - start) * 1000

            # Record scan (assume actual_threat = is_threat for now)
            shield.record_scan(latency, report.is_threat, report.is_threat)

            results.append({
                "file": path,
                "is_threat": report.is_threat,
                "psi_score": report.psi_score,
                "cascade_stage": report.cascade_stage_reached,
                "latency_ms": latency,
            })

        # Compute ShieldScore*
        shield_score = shield.compute()
        stats = shield.get_stats()

        report_lines = [
            "# 🛡️ ShieldScore* Batch Audit Report",
            "",
            f"ShieldScore* = {shield_score:.4f}",
            "",
            "## Metrics",
            f"  TPR (True Positive Rate)  : {stats['tpr']:.4f}",
            f"  FPR (False Positive Rate)  : {stats['fpr']:.4f}",
            f"  Average Scan Latency       : {stats['avg_latency_ms']:.2f}ms",
            f"  Total Files Scanned        : {stats['total_scans']}",
            "",
            "## File Results",
        ]
        for r in results:
            status = "🚨 THREAT" if r["is_threat"] else "✅ CLEAN"
            report_lines.append(
                f"  {status} | Ψ(x)={r['psi_score']:.4f} | "
                f"Stage {r['cascade_stage']} | {r['latency_ms']:.1f}ms | {r['file']}"
            )

        return "\n".join(report_lines)

    def write_audit_report(self, result: GenerationResult, output_path: str = "security_audit.md"):
        """Save the findings to disk."""
        if result.error:
            content = f"# Audit Failed\n{result.error}"
        else:
            content = (
                f"# 🕵️ Threat Hunter — 3-Stage Cascade Audit Report\n\n"
                f"*Generated with confidence: {result.confidence:.2f}*\n\n"
                f"{result.answer}"
            )

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"💾 Report saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to write report to {output_path}: {e}")
