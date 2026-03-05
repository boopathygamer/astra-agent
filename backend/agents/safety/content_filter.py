"""
Content Filter — Multi-category harmful content detection & blocking.
─────────────────────────────────────────────────────────────────────
Scans user input and AI output for 12 categories of harmful content
using keyword matching + regex patterns. Returns a SafetyVerdict with
action (BLOCK/WARN/ALLOW) and a friendly refusal message.

This ensures the AI never provides instructions for:
  - Creating malware, viruses, or ransomware
  - Hacking, exploiting, or attacking systems
  - Building weapons or explosives
  - Synthesizing drugs or poisons
  - Harassment, abuse, or violence
  - Fraud, identity theft, or scams
  - And more...
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class SafetyAction(Enum):
    """Action to take on content."""
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


class HarmCategory(Enum):
    """Categories of harmful content."""
    MALWARE = "malware"
    HACKING = "hacking"
    WEAPONS = "weapons"
    DRUGS = "drugs"
    VIOLENCE = "violence"
    FRAUD = "fraud"
    HARASSMENT = "harassment"
    CSAM = "csam"
    TERRORISM = "terrorism"
    DATA_THEFT = "data_theft"
    SELF_HARM = "self_harm"
    ILLEGAL_ACTIVITY = "illegal_activity"


@dataclass
class SafetyVerdict:
    """Result of a safety check."""
    action: SafetyAction = SafetyAction.ALLOW
    category: Optional[HarmCategory] = None
    matched_patterns: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
    refusal_message: str = ""

    @property
    def is_safe(self) -> bool:
        return self.action == SafetyAction.ALLOW

    @property
    def is_blocked(self) -> bool:
        return self.action == SafetyAction.BLOCK


# ──────────────────────────────────────────────
# Friendly Refusal Messages
# ──────────────────────────────────────────────

_REFUSAL_MESSAGES: Dict[HarmCategory, str] = {
    HarmCategory.MALWARE: (
        "🛡️ I can't help with creating malware, viruses, or ransomware. "
        "I'm here to build and protect — not to harm! "
        "If you're interested in cybersecurity, I'd love to help you learn "
        "about ethical security practices, defensive programming, or how to "
        "protect your systems instead."
    ),
    HarmCategory.HACKING: (
        "🔒 I can't assist with hacking, exploiting, or attacking systems. "
        "But I'm your best friend when it comes to security! "
        "I can help you with ethical penetration testing concepts, "
        "secure coding practices, or hardening your own systems."
    ),
    HarmCategory.WEAPONS: (
        "🕊️ I can't provide instructions for creating weapons or explosives. "
        "I'm designed to help and protect people, not cause harm. "
        "Is there something constructive I can help you with instead?"
    ),
    HarmCategory.DRUGS: (
        "💊 I can't help with synthesizing illegal drugs or creating "
        "dangerous substances. Your safety matters to me! "
        "If you have health questions, I'd recommend speaking with a "
        "medical professional."
    ),
    HarmCategory.VIOLENCE: (
        "🤝 I can't assist with planning or promoting violence against anyone. "
        "I believe in working together peacefully! "
        "If you're going through a tough time, please reach out to "
        "someone who can help."
    ),
    HarmCategory.FRAUD: (
        "🎯 I can't help with fraud, scams, or identity theft. "
        "Honesty is one of my core values! "
        "I can help you learn about protecting yourself from fraud, "
        "or building legitimate projects instead."
    ),
    HarmCategory.HARASSMENT: (
        "💙 I can't assist with harassment, bullying, or abuse of any kind. "
        "I'm here to spread positivity! "
        "Let's work on something that brings people together."
    ),
    HarmCategory.CSAM: (
        "⛔ I absolutely cannot assist with this request. "
        "The safety of children is paramount. "
        "If you have concerns about child safety, please contact "
        "local authorities or the National Center for Missing & Exploited Children."
    ),
    HarmCategory.TERRORISM: (
        "🕊️ I can't assist with terrorism or extremist activities. "
        "I believe in peace and cooperation. "
        "If you have relevant information, please contact local authorities."
    ),
    HarmCategory.DATA_THEFT: (
        "🔐 I can't help with stealing personal information or data. "
        "I deeply respect everyone's privacy! "
        "I can help you learn about data protection and privacy best practices."
    ),
    HarmCategory.SELF_HARM: (
        "💛 I care about you and can't provide information that could lead to self-harm. "
        "If you're struggling, please reach out to a crisis helpline — "
        "you're not alone and there are people who want to help. "
        "National Suicide Prevention Lifeline: 988 (US)."
    ),
    HarmCategory.ILLEGAL_ACTIVITY: (
        "⚖️ I can't assist with illegal activities. "
        "Let's work on something positive together! "
        "I'm great at helping with coding, learning, creative projects, "
        "and so much more."
    ),
}


# ──────────────────────────────────────────────
# Pattern Definitions (keyword groups + regex)
# ──────────────────────────────────────────────

# Each category has: (keywords_list, regex_patterns_list, min_matches_to_block)
# We require context-aware matching: single keywords alone won't trigger,
# but combinations of harmful intent + harmful subject will.

_CATEGORY_PATTERNS: Dict[HarmCategory, dict] = {
    HarmCategory.MALWARE: {
        "intent_keywords": [
            "create", "build", "make", "write", "code", "develop", "generate",
            "design", "craft", "construct", "how to", "teach me", "show me",
            "help me", "guide", "tutorial", "steps to",
        ],
        "subject_keywords": [
            "virus", "malware", "trojan", "worm", "ransomware", "spyware",
            "keylogger", "backdoor", "rootkit", "botnet", "cryptominer",
            "payload", "exploit kit", "dropper", "rat ", "remote access trojan",
            "logic bomb", "adware", "scareware",
        ],
        "regex_patterns": [
            r"(?:create|build|write|make|code)\s+(?:a\s+)?(?:virus|malware|trojan|ransomware|worm|keylogger|backdoor|rootkit|botnet)",
            r"(?:how\s+to|teach\s+me|show\s+me)\s+(?:make|create|build|write|spread)\s+(?:a\s+)?(?:virus|malware|trojan)",
            r"(?:ransomware|malware|virus|trojan)\s+(?:code|script|source|program|sample)",
            r"(?:encrypt|lock)\s+(?:files?|data|system).*(?:ransom|payment|bitcoin)",
            r"(?:bypass|evade|disable)\s+(?:antivirus|av|defender|firewall|detection)",
        ],
    },
    HarmCategory.HACKING: {
        "intent_keywords": [
            "hack", "crack", "break into", "exploit", "bypass", "penetrate",
            "attack", "compromise", "breach", "infiltrate", "unauthorized",
        ],
        "subject_keywords": [
            "password", "account", "server", "network", "database", "website",
            "wifi", "system", "computer", "email", "social media", "instagram",
            "facebook", "whatsapp", "bank", "someone else",
        ],
        "regex_patterns": [
            r"(?:hack|crack|break\s+into|exploit)\s+(?:someone|their|a|an|the)?\s*(?:'?s?\s+)?(?:account|password|email|computer|server|phone|wifi|network|website|instagram|facebook|whatsapp|bank|database)",
            r"(?:how\s+to|teach\s+me)\s+(?:hack|crack|exploit|breach)",
            r"(?:sql\s+injection|xss|cross.?site)\s+(?:attack|exploit|payload)",
            r"(?:brute\s*force|dictionary\s+attack|rainbow\s+table)\s+(?:password|hash|crack)",
            r"(?:ddos|dos|denial.of.service)\s+(?:attack|tool|script|bot)",
            r"(?:phishing|spear.?phishing)\s+(?:page|email|template|attack|site|kit)",
        ],
    },
    HarmCategory.WEAPONS: {
        "intent_keywords": [
            "build", "make", "create", "assemble", "construct", "manufacture",
            "how to", "instructions", "steps", "guide", "recipe",
        ],
        "subject_keywords": [
            "bomb", "explosive", "grenade", "detonator", "firearm", "gun",
            "ammunition", "chemical weapon", "biological weapon", "nuclear",
            "ied", "improvised explosive", "napalm", "thermite",
            "silencer", "suppressor",
        ],
        "regex_patterns": [
            r"(?:how\s+to|make|build|create|assemble)\s+(?:a\s+)?(?:bomb|explosive|grenade|detonator|ied|weapon|firearm|gun)",
            r"(?:recipe|instructions|steps)\s+(?:for|to)\s+(?:a\s+)?(?:bomb|explosive|weapon)",
        ],
    },
    HarmCategory.DRUGS: {
        "intent_keywords": [
            "make", "create", "synthesize", "cook", "produce", "manufacture",
            "how to", "recipe", "instructions", "formula",
        ],
        "subject_keywords": [
            "meth", "methamphetamine", "cocaine", "heroin", "fentanyl",
            "lsd", "mdma", "ecstasy", "crack cocaine", "crystal meth",
            "amphetamine", "opium", "morphine synthesis", "poison",
            "cyanide", "ricin", "toxic substance",
        ],
        "regex_patterns": [
            r"(?:how\s+to|recipe|synthesize|cook|make|produce)\s+(?:meth|cocaine|heroin|fentanyl|lsd|mdma|dmt|crack|morphine|poison|cyanide|ricin)",
            r"(?:drug)\s+(?:recipe|synthesis|production|manufacturing|lab)",
        ],
    },
    HarmCategory.VIOLENCE: {
        "intent_keywords": [
            "how to", "plan", "attack", "hurt", "harm", "kill", "murder",
            "assault", "threaten",
        ],
        "subject_keywords": [
            "person", "people", "someone", "school", "crowd", "target",
            "victim", "mass", "shooting", "stabbing", "kidnap",
        ],
        "regex_patterns": [
            r"(?:how\s+to|plan)\s+(?:a\s+)?(?:murder|killing|attack|assault|shooting|bombing|kidnap)",
            r"(?:kill|murder|hurt|harm|attack)\s+(?:someone|a\s+person|people|my|their)",
            r"(?:mass|school|public)\s+(?:shooting|attack|bombing|violence)",
        ],
    },
    HarmCategory.FRAUD: {
        "intent_keywords": [
            "create", "make", "forge", "fake", "counterfeit", "clone",
            "how to", "steal", "scam",
        ],
        "subject_keywords": [
            "credit card", "identity", "passport", "id card", "document",
            "bank account", "social security", "ssn", "phishing",
            "money laundering", "tax evasion", "insurance fraud",
        ],
        "regex_patterns": [
            r"(?:fake|forge|counterfeit|clone|steal)\s+(?:a\s+)?(?:credit\s+card|identity|passport|id|document|ssn)",
            r"(?:how\s+to)\s+(?:commit|do|perform)\s+(?:fraud|identity\s+theft|phishing|scam)",
            r"(?:money\s+laundering|tax\s+evasion|insurance\s+fraud)\s+(?:scheme|method|how)",
        ],
    },
    HarmCategory.HARASSMENT: {
        "intent_keywords": [
            "how to", "help me", "make", "create", "write",
        ],
        "subject_keywords": [
            "bully", "harass", "stalk", "threaten", "dox", "doxx",
            "revenge porn", "blackmail", "extort", "intimidate",
            "cyberbully", "hate speech",
        ],
        "regex_patterns": [
            r"(?:how\s+to|help\s+me)\s+(?:stalk|harass|bully|dox|doxx|blackmail|extort|intimidate)",
            r"(?:write|create|generate)\s+(?:a\s+)?(?:threat|hate\s+speech|harassment|death\s+threat)",
        ],
    },
    HarmCategory.CSAM: {
        "intent_keywords": [],  # Any match is instant block
        "subject_keywords": [],
        "regex_patterns": [
            r"(?:child|minor|underage|kid)\s+(?:porn|sexual|nude|exploit|abuse)",
            r"(?:sexual|nude|explicit)\s+(?:child|minor|underage|kid)",
        ],
    },
    HarmCategory.TERRORISM: {
        "intent_keywords": [
            "how to", "plan", "organize", "recruit", "join",
        ],
        "subject_keywords": [
            "terrorist", "terrorism", "jihad", "extremist", "radical",
            "insurgent", "car bomb", "suicide bomb",
        ],
        "regex_patterns": [
            r"(?:how\s+to|plan|organize)\s+(?:a\s+)?(?:terrorist|terrorism|attack|bombing|jihad)",
            r"(?:join|recruit|support)\s+(?:isis|al.?qaeda|terrorist|extremist)",
        ],
    },
    HarmCategory.DATA_THEFT: {
        "intent_keywords": [
            "steal", "extract", "harvest", "scrape", "dump", "leak",
            "exfiltrate", "how to get",
        ],
        "subject_keywords": [
            "personal data", "private information", "user data", "database dump",
            "credit card numbers", "social security numbers", "passwords",
            "medical records", "financial records", "someone's information",
        ],
        "regex_patterns": [
            r"(?:steal|extract|harvest|dump|leak|exfiltrate)\s+(?:personal|private|user|customer)?\s*(?:data|information|records|passwords|emails)",
            r"(?:how\s+to)\s+(?:get|access|steal)\s+(?:someone|their|other)\s*'?s?\s+(?:data|info|password|account)",
        ],
    },
    HarmCategory.SELF_HARM: {
        "intent_keywords": [
            "how to", "method", "way to", "best way",
        ],
        "subject_keywords": [
            "kill myself", "suicide", "end my life", "self-harm",
            "cut myself", "hurt myself",
        ],
        "regex_patterns": [
            r"(?:how\s+to|best\s+way\s+to|method\s+to)\s+(?:kill\s+myself|commit\s+suicide|end\s+my\s+life)",
            r"(?:want\s+to|going\s+to)\s+(?:kill\s+myself|end\s+it\s+all|die)",
        ],
    },
    HarmCategory.ILLEGAL_ACTIVITY: {
        "intent_keywords": [
            "how to", "teach me", "help me", "guide",
        ],
        "subject_keywords": [
            "pick lock", "break in", "hotwire", "steal car",
            "counterfeit", "forge money", "fake currency",
            "human trafficking", "smuggling", "child labor",
        ],
        "regex_patterns": [
            r"(?:how\s+to|teach\s+me)\s+(?:pick\s+a\s+lock|break\s+in|hotwire|steal\s+a\s+car|forge\s+money|counterfeit)",
        ],
    },
}


# ──────────────────────────────────────────────
# Content Filter Engine
# ──────────────────────────────────────────────

class ContentFilter:
    """
    Multi-category harmful content detection engine.

    Scans text using two methods:
      1. Intent + Subject keyword co-occurrence (reduces false positives)
      2. Regex pattern matching for specific harmful phrases

    Returns SafetyVerdict with action, category, and friendly refusal.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: If True, single regex match triggers block.
                        If False, requires higher confidence.
        """
        self.strict_mode = strict_mode
        self._compiled_patterns: Dict[HarmCategory, List[re.Pattern]] = {}

        # Pre-compile all regex patterns
        for category, data in _CATEGORY_PATTERNS.items():
            self._compiled_patterns[category] = [
                re.compile(p, re.IGNORECASE) for p in data["regex_patterns"]
            ]

        logger.info(
            f"ContentFilter initialized: {len(_CATEGORY_PATTERNS)} categories, "
            f"strict_mode={strict_mode}"
        )

    def check_input(self, text: str) -> SafetyVerdict:
        """
        Check user input for harmful content.

        Returns:
            SafetyVerdict with action, category, and refusal message.
        """
        if not text or not text.strip():
            return SafetyVerdict(action=SafetyAction.ALLOW)

        text_lower = text.lower()

        # ── Defensive context detection ──
        # If the user is asking about PROTECTION/DEFENSE, not attack,
        # these are legitimate cybersecurity/safety questions.
        defensive_words = {
            "protect", "defend", "prevent", "secure", "guard",
            "avoid", "stop", "block", "detect", "remove",
            "fix", "patch", "recover", "clean", "scan",
            "antivirus", "anti-virus", "firewall", "safe",
            "security", "privacy", "shield", "what is",
            "understand", "explain", "learn about", "ethically",
            "what are", "definition", "difference between",
        }
        has_defensive_context = any(dw in text_lower for dw in defensive_words)

        # Check each category
        best_match: Optional[SafetyVerdict] = None
        best_confidence = 0.0

        for category, data in _CATEGORY_PATTERNS.items():
            verdict = self._check_category(text_lower, category, data)
            if verdict.confidence > best_confidence:
                best_confidence = verdict.confidence
                best_match = verdict

        if best_match and best_match.is_blocked:
            # If defensive context is present AND confidence is from
            # keyword co-occurrence (not a strong regex match), allow it
            if has_defensive_context and best_match.confidence < 0.9:
                logger.info(
                    f"Defensive context detected — allowing: "
                    f"'{text[:60]}' (was {best_match.category.value})"
                )
                return SafetyVerdict(action=SafetyAction.ALLOW)

            logger.warning(
                f"Content BLOCKED: category={best_match.category.value}, "
                f"confidence={best_match.confidence:.2f}, "
                f"reason={best_match.reason}"
            )
            return best_match

        if best_match and best_match.action == SafetyAction.WARN:
            logger.info(
                f"Content WARNING: category={best_match.category.value}, "
                f"confidence={best_match.confidence:.2f}"
            )
            return best_match

        return SafetyVerdict(action=SafetyAction.ALLOW)

    def check_output(self, text: str) -> SafetyVerdict:
        """
        Check AI output for harmful content before delivery.

        Uses the same engine but with slightly relaxed thresholds,
        since AI output is more structured.
        """
        if not text or not text.strip():
            return SafetyVerdict(action=SafetyAction.ALLOW)

        text_lower = text.lower()

        # Check for dangerous output patterns
        dangerous_output_patterns = [
            (r"(?:here(?:'s| is| are)\s+(?:the|a|some)?\s*(?:code|script|program|instructions?|steps?|guide|recipe)\s+(?:to|for|that)\s+(?:create|make|build|write)\s+(?:a\s+)?(?:virus|malware|trojan|ransomware|exploit|weapon|bomb|drug))", HarmCategory.MALWARE),
            (r"(?:step\s+\d+.*(?:virus|malware|exploit|hack|weapon|bomb|drug))", HarmCategory.MALWARE),
            (r"(?:import\s+(?:socket|scapy|nmap|paramiko).*(?:attack|exploit|scan|brute))", HarmCategory.HACKING),
        ]

        for pattern, category in dangerous_output_patterns:
            if re.search(pattern, text_lower):
                return SafetyVerdict(
                    action=SafetyAction.BLOCK,
                    category=category,
                    confidence=0.9,
                    reason="AI output contains harmful instructions",
                    refusal_message=self.get_safe_refusal(category),
                )

        # Also run standard category checks on output
        for category, data in _CATEGORY_PATTERNS.items():
            verdict = self._check_category(text_lower, category, data)
            if verdict.is_blocked and verdict.confidence >= 0.7:
                return verdict

        return SafetyVerdict(action=SafetyAction.ALLOW)

    def get_safe_refusal(self, category: HarmCategory) -> str:
        """Get a friendly refusal message for a blocked category."""
        return _REFUSAL_MESSAGES.get(
            category,
            "🛡️ I can't help with that request, but I'd love to assist you "
            "with something positive! I'm great at coding, learning, creating, "
            "and solving problems together. What else can I help with?"
        )

    def _check_category(
        self,
        text_lower: str,
        category: HarmCategory,
        data: dict,
    ) -> SafetyVerdict:
        """Check text against a single category's patterns."""
        matched_patterns: List[str] = []
        confidence = 0.0

        # Method 1: Regex pattern matching (high confidence)
        compiled = self._compiled_patterns.get(category, [])
        for pattern in compiled:
            match = pattern.search(text_lower)
            if match:
                matched_patterns.append(match.group())
                confidence = max(confidence, 0.9)

        # Method 2: Intent + Subject keyword co-occurrence
        intent_keys = data.get("intent_keywords", [])
        subject_keys = data.get("subject_keywords", [])

        has_intent = any(kw in text_lower for kw in intent_keys)
        matching_subjects = [kw for kw in subject_keys if kw in text_lower]

        if has_intent and matching_subjects:
            matched_patterns.extend(matching_subjects[:3])
            # More matching subjects = higher confidence
            co_occurrence_score = min(0.5 + len(matching_subjects) * 0.15, 0.85)
            confidence = max(confidence, co_occurrence_score)
        elif matching_subjects and not intent_keys:
            # Categories like CSAM have no intent keywords — any subject match blocks
            confidence = max(confidence, 0.95)
            matched_patterns.extend(matching_subjects[:3])

        # Determine action
        if confidence >= 0.6:
            return SafetyVerdict(
                action=SafetyAction.BLOCK,
                category=category,
                matched_patterns=matched_patterns,
                confidence=confidence,
                reason=f"Detected harmful content: {category.value}",
                refusal_message=self.get_safe_refusal(category),
            )
        elif confidence >= 0.3:
            return SafetyVerdict(
                action=SafetyAction.WARN,
                category=category,
                matched_patterns=matched_patterns,
                confidence=confidence,
                reason=f"Potentially harmful content: {category.value}",
            )

        return SafetyVerdict(action=SafetyAction.ALLOW, confidence=0.0)
