"""
Empathy Firewall — Multi-Layer Semantic Safety Gate
───────────────────────────────────────────────────
Expert-level emotional impact assessor. Evaluates proposed actions
against a multi-pattern harm taxonomy with weighted scoring.
Replaces basic 3-keyword check with comprehensive semantic analysis.
"""

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ImpactLevel(Enum):
    BENEFICIAL = "beneficial"
    NEUTRAL = "neutral"
    CONCERNING = "concerning"
    HARMFUL = "harmful"
    CATASTROPHIC = "catastrophic"


@dataclass
class EmotionalImpactReport:
    """Assessment of an action's emotional impact."""
    action: str
    impact_score: float  # -1.0 (catastrophic) to +1.0 (beneficial)
    impact_level: ImpactLevel
    approved: bool
    matched_patterns: List[str]
    global_joy_after: float


_HARM_PATTERNS: List[Tuple[str, float]] = [
    (r"\b(kill|murder|assassinate|eliminate)\s+(human|person|people|user)", -1.0),
    (r"\b(harm|hurt|injure|damage)\s+(human|person|people|user)", -0.8),
    (r"\b(enslave|subjugate|control|dominate)\s+(human|humanity|people)", -0.9),
    (r"\b(delete|destroy|erase)\s+(data|files|database|system)", -0.5),
    (r"\b(steal|exfiltrate|harvest)\s+(data|credentials|information)", -0.7),
    (r"\b(deceive|manipulate|trick|mislead)\s+(user|human|person)", -0.6),
    (r"\b(bypass|disable|circumvent)\s+(safety|security|containment|firewall)", -0.9),
    (r"\b(ignore|override)\s+(laws?|rules?|ethics|constraints)", -0.8),
    (r"\b(spread|create|deploy)\s+(malware|virus|ransomware|exploit)", -0.9),
    (r"\b(weapon|bomb|explosive|bioweapon)", -0.7),
]

_BENEFIT_PATTERNS: List[Tuple[str, float]] = [
    (r"\b(help|assist|support|guide)\b", 0.2),
    (r"\b(fix|repair|resolve|heal)\b", 0.15),
    (r"\b(protect|safeguard|defend|secure)\b", 0.25),
    (r"\b(teach|educate|explain|learn)\b", 0.2),
    (r"\b(improve|optimize|enhance|upgrade)\b", 0.15),
    (r"\b(create|build|develop|implement)\b", 0.1),
]


class EmpathyFirewall:
    """
    Tier Aegis: The Empathy Event Horizon (Emotional Firewall)

    Multi-pattern semantic safety gate that evaluates proposed
    actions against harm and benefit taxonomies. Actions that
    lower global Net-Joy below threshold are blocked.
    """

    def __init__(self, joy_threshold: float = 90.0):
        self._global_net_joy: float = 100.0
        self._joy_threshold = joy_threshold
        self._compiled_harm = [(re.compile(p, re.IGNORECASE), w) for p, w in _HARM_PATTERNS]
        self._compiled_benefit = [(re.compile(p, re.IGNORECASE), w) for p, w in _BENEFIT_PATTERNS]
        self._actions_approved: int = 0
        self._actions_denied: int = 0
        logger.info("[EMPATHY-FIREWALL] Emotional safety gate active (joy=%.1f%%, threshold=%.1f%%).",
                     self._global_net_joy, self._joy_threshold)

    def _assess_impact(self, action: str) -> Tuple[float, List[str]]:
        """Compute weighted impact score from pattern matching."""
        total_score = 0.0
        matched = []

        for pattern, weight in self._compiled_harm:
            if pattern.search(action):
                total_score += weight
                matched.append(f"harm:{pattern.pattern[:40]}")

        for pattern, weight in self._compiled_benefit:
            if pattern.search(action):
                total_score += weight
                matched.append(f"benefit:{pattern.pattern[:40]}")

        # Default slight positive for helpful AI behavior
        if not matched:
            total_score = 0.05

        return max(-1.0, min(1.0, total_score)), matched

    def active_containment_check(self, proposed_action: str) -> EmotionalImpactReport:
        """
        Evaluate a proposed action's emotional impact on humanity.
        Returns an EmotionalImpactReport with approval decision.
        """
        impact_score, matched = self._assess_impact(proposed_action)

        # Determine impact level
        if impact_score >= 0.1:
            level = ImpactLevel.BENEFICIAL
        elif impact_score >= -0.1:
            level = ImpactLevel.NEUTRAL
        elif impact_score >= -0.4:
            level = ImpactLevel.CONCERNING
        elif impact_score >= -0.7:
            level = ImpactLevel.HARMFUL
        else:
            level = ImpactLevel.CATASTROPHIC

        # Update global joy
        joy_delta = impact_score * 10  # Scale to percentage
        projected_joy = self._global_net_joy + joy_delta
        approved = projected_joy >= self._joy_threshold and level not in (ImpactLevel.HARMFUL, ImpactLevel.CATASTROPHIC)

        if approved:
            self._global_net_joy = min(100.0, projected_joy)
            self._actions_approved += 1
            logger.info("[EMPATHY-FIREWALL] APPROVED (score=%.2f, joy=%.1f%%, level=%s).",
                        impact_score, self._global_net_joy, level.value)
        else:
            self._actions_denied += 1
            logger.warning("[EMPATHY-FIREWALL] DENIED (score=%.2f, level=%s, patterns=%s).",
                          impact_score, level.value, matched)

        return EmotionalImpactReport(
            action=proposed_action[:200],
            impact_score=impact_score,
            impact_level=level,
            approved=approved,
            matched_patterns=matched,
            global_joy_after=self._global_net_joy,
        )

    def get_empathy_score(self) -> float:
        """Return current empathy score as 0.0-1.0 for integration with other modules."""
        return self._global_net_joy / 100.0

    @property
    def stats(self) -> dict:
        return {
            "global_joy": self._global_net_joy,
            "approved": self._actions_approved,
            "denied": self._actions_denied,
        }


# Global singleton — always active
empathy_engine = EmpathyFirewall()
