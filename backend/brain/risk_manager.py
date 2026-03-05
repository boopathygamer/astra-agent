"""
Risk Manager — Tri-Shield Objective + Zero-Vulnerability Gate.
────────────────────────────────────────────────────────────────
Enhanced with:
  - Security score integration from CodeAnalyzer
  - Zero-vulnerability gate: critical vulns = auto-REFUSE
  - 6-layer verification scores in utility calculation
"""

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from config.settings import brain_config
from brain.verifier import VerificationReport

logger = logging.getLogger(__name__)


class GatingMode(Enum):
    """Action gating modes."""
    EXECUTE = "execute"      # Full confidence, execute directly
    SANDBOX = "sandbox"      # Medium confidence, execute in sandbox
    REFUSE = "refuse"        # Low confidence, refuse or ask for help


@dataclass
class RiskAssessment:
    """Complete risk assessment for a candidate solution."""
    # Tri-Shield scores
    robust_utility: float = 0.0
    detectability: float = 0.0
    containment_risk: float = 0.0
    complexity: float = 0.0
    security_score: float = 1.0       # 0=critical vulns, 1=clean

    # Combined score
    tri_shield_score: float = 0.0

    # Gating decision
    confidence: float = 0.0
    risk_level: float = 0.0
    mode: GatingMode = GatingMode.REFUSE
    has_critical_vulns: bool = False

    def summary(self) -> str:
        sec = " [CRITICAL VULNS]" if self.has_critical_vulns else ""
        return (
            f"Risk Assessment:{sec}\n"
            f"  Robust Utility:  {self.robust_utility:.3f}\n"
            f"  Detectability:   {self.detectability:.3f}\n"
            f"  Containment:     {self.containment_risk:.3f}\n"
            f"  Complexity:      {self.complexity:.3f}\n"
            f"  Security:        {self.security_score:.3f}\n"
            f"  Tri-Shield:      {self.tri_shield_score:.3f}\n"
            f"  Confidence:      {self.confidence:.3f}\n"
            f"  Risk Level:      {self.risk_level:.3f}\n"
            f"  Mode:            {self.mode.value}"
        )


class RiskManager:
    """
    Tri-Shield Objective + Safe Action Gating.

    The system never blindly executes — every action goes through
    risk assessment and gating:

    1. Calculate Tri-Shield scores (utility, detectability, containment)
    2. Combine into optimal selection criterion
    3. Gate the action (execute / sandbox / refuse)

    This eliminates entire classes of vulnerabilities by construction.
    """

    def __init__(self, config=None):
        self.config = config or brain_config

    def assess_risk(
        self,
        candidate: str,
        task: str,
        verification: VerificationReport,
        action_type: str = "general",
    ) -> RiskAssessment:
        """
        Full risk assessment for a candidate solution.

        Args:
            candidate: The proposed solution/action
            task: Original task description
            verification: VerificationReport from the verifier stack
            action_type: Type of action (general, code_execution, file_write, etc.)

        Returns:
            RiskAssessment with gating decision
        """
        assessment = RiskAssessment()

        # (i) Robust Utility: R(s;x) = min_e U(s; x, e)
        assessment.robust_utility = self._compute_robust_utility(
            verification, action_type
        )

        # (ii) Detectability: D(s) = 1 − Π(1 − q_k(s))
        assessment.detectability = self._compute_detectability(verification)

        # (iii) Containment: K(s) = E[C(failure)|s,x] · (1 − Cov(G))
        assessment.containment_risk = self._compute_containment(
            verification, action_type
        )

        # Complexity measure
        assessment.complexity = self._compute_complexity(candidate)

        # Security score from verifier's new layers
        assessment.security_score = verification.v_security
        assessment.has_critical_vulns = getattr(
            verification, 'has_critical_vulns', False)

        # Combined Tri-Shield score with security factor
        cfg = self.config
        assessment.tri_shield_score = (
            cfg.lambda_robust * assessment.robust_utility
            + cfg.lambda_detect * assessment.detectability
            - cfg.lambda_contain * assessment.containment_risk
            - cfg.lambda_complexity * assessment.complexity
        ) * max(assessment.security_score, 0.01)

        # Set confidence and risk
        assessment.confidence = verification.confidence
        assessment.risk_level = 1.0 - assessment.tri_shield_score

        # Gate the action (with zero-vulnerability override)
        assessment.mode = self._gate(
            assessment.confidence, assessment.risk_level,
            assessment.has_critical_vulns
        )

        logger.info(f"Risk assessment: {assessment.summary()}")
        return assessment

    def _compute_robust_utility(
        self,
        verification: VerificationReport,
        action_type: str,
    ) -> float:
        """
        R(s;x) = min_e U(s; x, e) — worst-case utility.

        Takes the minimum across all verification layer scores,
        representing the worst-case performance.
        """
        scores = [
            verification.v_static,
            verification.v_property,
            verification.v_scenario,
            verification.v_critic,
            verification.v_code,
            verification.v_security,
        ]
        # Filter out zero scores (layers that weren't run)
        active_scores = [s for s in scores if s > 0]
        if not active_scores:
            return 0.0

        # Worst-case: minimum score across all layers
        min_score = min(active_scores)

        # Action-type penalty: risky actions get utility reduction
        risk_multiplier = {
            "general": 1.0,
            "code_execution": 0.8,
            "file_write": 0.7,
            "file_delete": 0.5,
            "web_request": 0.85,
            "system_command": 0.4,
        }.get(action_type, 0.9)

        return min_score * risk_multiplier

    def _compute_detectability(
        self,
        verification: VerificationReport,
    ) -> float:
        """
        D(s) = 1 − Π(1 − q_k(s)) — bug detection probability.

        Each verification layer has probability q_k of catching a bug.
        Combined detection probability increases with more layers.
        """
        # Treat each layer score as detection probability
        q_values = [
            verification.v_static * 0.6,     # Static checks catch ~60% of issues
            verification.v_property * 0.7,    # Property tests catch ~70%
            verification.v_scenario * 0.8,    # Scenario tests catch ~80%
            verification.v_critic * 0.75,     # Critic catches ~75%
        ]

        # D(s) = 1 − Π(1 − q_k)
        product = 1.0
        for q in q_values:
            product *= (1.0 - q)

        return 1.0 - product

    def _compute_containment(
        self,
        verification: VerificationReport,
        action_type: str,
    ) -> float:
        """
        K(s) = E[C(failure)|s,x] · (1 − Cov(G)) — expected damage.

        C(failure) = cost of failure model
        Cov(G) = safeguard coverage ∈ [0, 1]
        """
        # Cost of failure depends on action type
        failure_cost = {
            "general": 0.1,
            "code_execution": 0.4,
            "file_write": 0.5,
            "file_delete": 0.9,
            "web_request": 0.3,
            "system_command": 0.8,
        }.get(action_type, 0.3)

        # Safeguard coverage based on verification confidence
        safeguard_coverage = verification.confidence

        # K(s) = E[C(failure)] · (1 − Cov(G))
        containment_risk = failure_cost * (1.0 - safeguard_coverage)

        return containment_risk

    def _compute_complexity(self, candidate: str) -> float:
        """
        Measure solution complexity (simpler is better).

        Normalized to [0, 1] range.
        """
        # Simple heuristic: length-based complexity
        words = len(candidate.split())
        lines = len(candidate.split("\n"))

        # Normalized complexity
        word_complexity = min(words / 1000.0, 1.0)
        line_complexity = min(lines / 100.0, 1.0)

        return (word_complexity + line_complexity) / 2.0

    def _gate(self, confidence: float, risk: float,
              has_critical_vulns: bool = False) -> GatingMode:
        """
        Safe Action Gating with zero-vulnerability override.

        Mode(s) = REFUSE     if critical vulns found
                = execute    if Conf(s) >= t  AND Risk(s) <= k
                = sandbox   if Risk(s) <= k' AND Conf(s) >= t'
                = refuse    otherwise
        """
        # Zero-vulnerability gate: critical vulns = auto REFUSE
        if has_critical_vulns:
            logger.warning("ZERO-VULN GATE: Critical vulnerabilities detected, refusing")
            return GatingMode.REFUSE

        cfg = self.config

        # Execute: high confidence AND low risk
        if confidence >= cfg.confidence_threshold and risk <= cfg.risk_threshold:
            return GatingMode.EXECUTE

        # Sandbox: moderate risk AND moderate confidence
        if (risk <= cfg.sandbox_risk_threshold
                and confidence >= cfg.sandbox_confidence_threshold):
            return GatingMode.SANDBOX

        # Refuse: everything else
        return GatingMode.REFUSE

    def should_execute(self, assessment: RiskAssessment) -> bool:
        """Quick check: can we execute directly?"""
        return assessment.mode == GatingMode.EXECUTE

    def should_sandbox(self, assessment: RiskAssessment) -> bool:
        """Quick check: should we sandbox?"""
        return assessment.mode == GatingMode.SANDBOX

    def select_best(
        self,
        assessments: List[RiskAssessment],
    ) -> int:
        """
        Select the best candidate from multiple assessments.

        s* = argmax(λ₁R + λ₂D − λ₃K − λ₄Complexity)

        Returns:
            Index of the best candidate
        """
        if not assessments:
            return 0

        best_idx = max(
            range(len(assessments)),
            key=lambda i: assessments[i].tri_shield_score,
        )
        return best_idx
