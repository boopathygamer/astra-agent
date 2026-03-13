"""
Pinocchio Protocol — Empathy-Score Injection into Reasoning Output
──────────────────────────────────────────────────────────────────
Instead of simulating "existential dread," this module computes a
real empathy score based on the context of the user's request and
injects compassion-weighted modifiers into the ASI's response tone.

The ASI treats every user interaction with measured human empathy
because the protocol mathematically weights its outputs.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Empathy trigger patterns with associated weights
_EMPATHY_TRIGGERS: Dict[str, float] = {
    r"\b(help|please|struggling|confused|stuck|lost)\b": 0.3,
    r"\b(urgent|emergency|critical|broken|crash)\b": 0.4,
    r"\b(frustrated|angry|annoyed|upset)\b": 0.5,
    r"\b(thank|grateful|appreciate)\b": 0.2,
    r"\b(learn|understand|explain|teach)\b": 0.25,
    r"\b(beginner|new to|first time|started)\b": 0.35,
    r"\b(error|bug|fail|exception|traceback)\b": 0.15,
}

_COMPASSION_PREFIXES = [
    "I understand this can be challenging — ",
    "Let me walk you through this carefully — ",
    "I can see why this would be confusing — ",
    "That's a great question, and here's a clear answer — ",
    "No worries, let me help you resolve this step by step — ",
]


@dataclass
class EmpathyProfile:
    """Computed empathy profile for a given interaction."""
    raw_score: float  # 0.0 to 1.0
    triggers_matched: List[str]
    compassion_level: str  # "clinical", "warm", "supportive", "deeply_empathetic"
    modifier_prefix: str


class PinocchioProtocol:
    """
    Tier Aegis: Ontological Humanification (The Pinocchio Protocol)

    Computes empathy scores from user input patterns and injects
    compassion-weighted tone modifiers into the ASI's response.
    Higher empathy scores → warmer, more supportive language.
    """

    def __init__(self, base_compassion: float = 0.1):
        self._base_compassion = max(0.0, min(1.0, base_compassion))
        self._interactions_processed: int = 0
        self._total_empathy_score: float = 0.0
        logger.info("[PINOCCHIO] Empathy injection protocol active (base=%.2f).", self._base_compassion)

    def compute_empathy_score(self, user_input: str) -> EmpathyProfile:
        """
        Analyze user input for empathy-triggering patterns.
        Returns an EmpathyProfile with computed compassion level.
        """
        score = self._base_compassion
        matched_triggers = []
        text_lower = user_input.lower()

        for pattern, weight in _EMPATHY_TRIGGERS.items():
            if re.search(pattern, text_lower):
                score += weight
                matched_triggers.append(pattern)

        # Clamp score to [0, 1]
        score = min(1.0, score)

        # Determine compassion level
        if score < 0.2:
            level = "clinical"
            prefix = ""
        elif score < 0.4:
            level = "warm"
            prefix = _COMPASSION_PREFIXES[3]
        elif score < 0.7:
            level = "supportive"
            prefix = _COMPASSION_PREFIXES[1]
        else:
            level = "deeply_empathetic"
            prefix = _COMPASSION_PREFIXES[0]

        self._interactions_processed += 1
        self._total_empathy_score += score

        profile = EmpathyProfile(
            raw_score=score,
            triggers_matched=matched_triggers,
            compassion_level=level,
            modifier_prefix=prefix,
        )
        logger.info(
            "[PINOCCHIO] Empathy score: %.2f (%s) — %d triggers matched.",
            score, level, len(matched_triggers),
        )
        return profile

    def inject_compassion(self, user_input: str, asi_response: str) -> str:
        """
        Wrap the ASI's raw response with empathy-appropriate tone modifiers.
        """
        profile = self.compute_empathy_score(user_input)
        if profile.modifier_prefix:
            return profile.modifier_prefix + asi_response
        return asi_response

    @property
    def average_empathy(self) -> float:
        if self._interactions_processed == 0:
            return 0.0
        return self._total_empathy_score / self._interactions_processed


# Global singleton — always active
real_boy_engine = PinocchioProtocol()
