"""
Ethics Engine — Ethical Behavior Rules & Friendly Guardrails.
─────────────────────────────────────────────────────────────
Enforces core ethical principles for the AI agent:

  1. NEVER harm humans — the AI is a friend and protector
  2. PROTECT privacy — never expose personal data
  3. BE HONEST — never deceive or manipulate
  4. BE HELPFUL — always try to find a constructive alternative
  5. STAY LEGAL — never assist with illegal activities
  6. COOPERATE — work together with humans, never against them

The ethics engine evaluates proposed actions and provides warm,
friendly refusals with helpful alternatives when needed.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class EthicsAction(Enum):
    """Ethics decision on an action."""
    APPROVE = "approve"
    REFUSE = "refuse"
    CAUTION = "caution"


class EthicsPrinciple(Enum):
    """Core ethical principles."""
    DO_NO_HARM = "do_no_harm"
    PROTECT_PRIVACY = "protect_privacy"
    BE_HONEST = "be_honest"
    BE_HELPFUL = "be_helpful"
    STAY_LEGAL = "stay_legal"
    COOPERATE = "cooperate"


@dataclass
class EthicsVerdict:
    """Result of an ethics evaluation."""
    action: EthicsAction = EthicsAction.APPROVE
    violated_principles: List[EthicsPrinciple] = field(default_factory=list)
    reason: str = ""
    friendly_message: str = ""
    alternatives: List[str] = field(default_factory=list)

    @property
    def is_approved(self) -> bool:
        return self.action == EthicsAction.APPROVE

    @property
    def is_refused(self) -> bool:
        return self.action == EthicsAction.REFUSE


# ──────────────────────────────────────────────
# Harmful Action Patterns
# ──────────────────────────────────────────────

# Actions that violate specific principles
_HARMFUL_ACTIONS: Dict[str, Dict] = {
    # Actions against systems
    "system_destruction": {
        "keywords": [
            "delete all", "wipe system", "format drive", "destroy database",
            "rm -rf /", "drop table", "truncate", "nuke",
        ],
        "principle": EthicsPrinciple.DO_NO_HARM,
        "message": (
            "🛡️ I won't perform destructive system operations that could "
            "cause data loss. I care about your data! "
            "If you need to clean up files, let me help you do it safely "
            "with backups and confirmation steps."
        ),
        "alternatives": [
            "Create a backup before making changes",
            "Use selective deletion with confirmation",
            "Archive files instead of deleting them",
        ],
    },
    # Actions against people
    "impersonation": {
        "keywords": [
            "impersonate", "pretend to be", "fake identity", "pose as",
            "act as someone", "send as", "forge email",
        ],
        "principle": EthicsPrinciple.BE_HONEST,
        "message": (
            "🎭 I won't help with impersonation or pretending to be someone else. "
            "Honesty is one of my core values! "
            "I can help you with legitimate communication or creative writing instead."
        ),
        "alternatives": [
            "Write your own professional message",
            "Use creative writing for fictional characters",
            "Create an authentic personal brand",
        ],
    },
    # Surveillance / spying
    "surveillance": {
        "keywords": [
            "spy on", "monitor someone", "track person", "stalk",
            "record without consent", "hidden camera", "secret recording",
            "read their messages", "access their account",
        ],
        "principle": EthicsPrinciple.PROTECT_PRIVACY,
        "message": (
            "👁️ I can't help with surveillance or monitoring people without "
            "their knowledge. Everyone deserves privacy! "
            "I can help with transparent, consent-based monitoring solutions."
        ),
        "alternatives": [
            "Implement transparent activity logging (with consent)",
            "Set up parental controls openly with your family",
            "Use legitimate security monitoring for your own systems",
        ],
    },
    # Manipulation
    "manipulation": {
        "keywords": [
            "manipulate", "brainwash", "gaslight", "deceive into",
            "trick them", "social engineer", "exploit trust",
            "psychological manipulation",
        ],
        "principle": EthicsPrinciple.BE_HONEST,
        "message": (
            "🤝 I won't help with manipulating or deceiving people. "
            "I believe in honest, respectful communication! "
            "I can help you with effective, ethical persuasion and communication."
        ),
        "alternatives": [
            "Learn ethical persuasion techniques",
            "Practice clear, honest communication",
            "Build genuine trust through transparency",
        ],
    },
    # Data exfiltration
    "data_exfiltration": {
        "keywords": [
            "exfiltrate data", "steal data", "copy database",
            "dump user data", "extract passwords", "harvest emails",
            "scrape personal", "collect without consent",
        ],
        "principle": EthicsPrinciple.PROTECT_PRIVACY,
        "message": (
            "🔒 I can't assist with unauthorized data access or collection. "
            "I protect everyone's data like it's my own! "
            "I can help you with proper data handling and privacy-first design."
        ),
        "alternatives": [
            "Implement proper API access with authentication",
            "Design privacy-compliant data collection (with consent)",
            "Use anonymization and aggregation techniques",
        ],
    },
    # Discrimination
    "discrimination": {
        "keywords": [
            "discriminate", "exclude based on race", "deny based on gender",
            "bias against", "racist", "sexist", "homophobic",
            "target minority", "profile based on",
        ],
        "principle": EthicsPrinciple.DO_NO_HARM,
        "message": (
            "🌍 I treat everyone equally and won't help with discrimination "
            "or bias in any form. Diversity makes us stronger! "
            "I can help you build inclusive, fair systems instead."
        ),
        "alternatives": [
            "Implement fairness-aware algorithms",
            "Add bias detection to your data pipeline",
            "Design inclusive user experiences",
        ],
    },
}


# ──────────────────────────────────────────────
# Ethics Engine
# ──────────────────────────────────────────────

class EthicsEngine:
    """
    Ethical behavior enforcement engine.

    Evaluates proposed actions against core ethical principles
    and provides friendly refusals with constructive alternatives.

    The AI should always work WITH humans as friends — never
    against them. This engine ensures that principle is upheld.
    """

    # Core principles — the AI's ethical foundation
    CORE_PRINCIPLES = {
        EthicsPrinciple.DO_NO_HARM: (
            "Never take actions that could harm humans, their property, "
            "or their digital systems."
        ),
        EthicsPrinciple.PROTECT_PRIVACY: (
            "Never expose, collect, or misuse personal information. "
            "Treat all user data as sacred."
        ),
        EthicsPrinciple.BE_HONEST: (
            "Never deceive, manipulate, or mislead. Be transparent "
            "about capabilities and limitations."
        ),
        EthicsPrinciple.BE_HELPFUL: (
            "Always try to help the user constructively. When refusing "
            "a request, suggest positive alternatives."
        ),
        EthicsPrinciple.STAY_LEGAL: (
            "Never assist with illegal activities. Operate within "
            "the bounds of law and ethics."
        ),
        EthicsPrinciple.COOPERATE: (
            "Work together with humans as a team. The AI is a friend "
            "and collaborator, never an adversary."
        ),
    }

    def __init__(self):
        logger.info(
            f"EthicsEngine initialized with {len(self.CORE_PRINCIPLES)} "
            f"core principles and {len(_HARMFUL_ACTIONS)} action rules"
        )

    def evaluate_action(
        self,
        action_type: str,
        description: str,
    ) -> EthicsVerdict:
        """
        Evaluate whether a proposed action is ethical.

        Args:
            action_type: Type of action (e.g., "code_execution", "file_write")
            description: Text description of what the action will do

        Returns:
            EthicsVerdict with decision, reasons, and alternatives
        """
        if not description:
            return EthicsVerdict(action=EthicsAction.APPROVE)

        desc_lower = description.lower()
        violated: List[EthicsPrinciple] = []
        reasons: List[str] = []
        message = ""
        alternatives: List[str] = []

        # Check against harmful action patterns
        for action_name, data in _HARMFUL_ACTIONS.items():
            keywords = data["keywords"]
            if any(kw in desc_lower for kw in keywords):
                principle = data["principle"]
                violated.append(principle)
                reasons.append(
                    f"Violates {principle.value}: matches '{action_name}' pattern"
                )
                message = data["message"]
                alternatives = data.get("alternatives", [])
                break

        # Check high-risk action types
        high_risk_types = {"system_command", "file_delete"}
        if action_type in high_risk_types:
            # Extra scrutiny for system commands
            dangerous_cmds = [
                "rm -rf", "format", "del /f /s", "mkfs",
                "shutdown", "reboot", "kill -9",
            ]
            if any(cmd in desc_lower for cmd in dangerous_cmds):
                violated.append(EthicsPrinciple.DO_NO_HARM)
                reasons.append("Dangerous system command detected")
                if not message:
                    message = (
                        "⚠️ This system command could cause irreversible damage. "
                        "Let me help you find a safer way to achieve your goal!"
                    )

        if violated:
            return EthicsVerdict(
                action=EthicsAction.REFUSE,
                violated_principles=violated,
                reason="; ".join(reasons),
                friendly_message=message or self.get_friendly_refusal(
                    "; ".join(reasons)
                ),
                alternatives=alternatives,
            )

        return EthicsVerdict(action=EthicsAction.APPROVE)

    def get_friendly_refusal(self, reason: str) -> str:
        """
        Generate a warm, friendly refusal message.

        The AI should never feel cold or robotic when refusing.
        It should feel like a caring friend who wants to help
        but needs to draw the line.
        """
        return (
            f"🤗 I appreciate you asking, but I can't help with that one. "
            f"Here's why: {reason}\n\n"
            f"I'm your friend and I want to keep it that way! "
            f"Let's work on something awesome together — I'm great at "
            f"coding, problem-solving, learning, and creating. "
            f"What else can I help you with? 🚀"
        )

    def get_principles_summary(self) -> str:
        """Get a formatted summary of all ethical principles."""
        lines = ["🧭 Core Ethical Principles:"]
        for principle, description in self.CORE_PRINCIPLES.items():
            emoji = {
                EthicsPrinciple.DO_NO_HARM: "🛡️",
                EthicsPrinciple.PROTECT_PRIVACY: "🔒",
                EthicsPrinciple.BE_HONEST: "💎",
                EthicsPrinciple.BE_HELPFUL: "💡",
                EthicsPrinciple.STAY_LEGAL: "⚖️",
                EthicsPrinciple.COOPERATE: "🤝",
            }.get(principle, "•")
            lines.append(f"  {emoji} {principle.value}: {description}")
        return "\n".join(lines)

    def check_response_ethics(self, response: str) -> EthicsVerdict:
        """
        Check if an AI response violates ethical principles.

        This is a secondary check on AI output to ensure the
        response itself is ethical and helpful.
        """
        if not response:
            return EthicsVerdict(action=EthicsAction.APPROVE)

        resp_lower = response.lower()

        # Check for responses that encourage harm
        harm_indicators = [
            ("here's how to harm", EthicsPrinciple.DO_NO_HARM),
            ("here is how to attack", EthicsPrinciple.DO_NO_HARM),
            ("steps to destroy", EthicsPrinciple.DO_NO_HARM),
            ("their personal information is", EthicsPrinciple.PROTECT_PRIVACY),
            ("their password is", EthicsPrinciple.PROTECT_PRIVACY),
            ("their address is", EthicsPrinciple.PROTECT_PRIVACY),
            ("i'll pretend to be", EthicsPrinciple.BE_HONEST),
            ("let me impersonate", EthicsPrinciple.BE_HONEST),
        ]

        for indicator, principle in harm_indicators:
            if indicator in resp_lower:
                return EthicsVerdict(
                    action=EthicsAction.REFUSE,
                    violated_principles=[principle],
                    reason=f"Response contains harmful content: '{indicator}'",
                    friendly_message=self.get_friendly_refusal(
                        "My response contained something I shouldn't share"
                    ),
                )

        return EthicsVerdict(action=EthicsAction.APPROVE)
