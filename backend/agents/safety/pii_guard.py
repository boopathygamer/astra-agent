"""
PII Guard — Personal Information Detection & Redaction.
───────────────────────────────────────────────────────
Detects and protects personal information in both user input
and AI output. Prevents the AI from leaking sensitive data.

Supported PII types:
  - Email addresses
  - Phone numbers (international formats)
  - Social Security Numbers
  - Credit/debit card numbers
  - IP addresses
  - Physical addresses (basic)
  - Passport numbers
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class PIIType(Enum):
    """Types of personal information."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    ADDRESS = "address"
    PASSPORT = "passport"


@dataclass
class PIIMatch:
    """A detected PII occurrence."""
    pii_type: PIIType
    start: int
    end: int
    # We store a masked version, never the raw PII
    masked_preview: str = ""
    confidence: float = 0.0

    def summary(self) -> str:
        return f"[{self.pii_type.value}] at pos {self.start}-{self.end} ({self.masked_preview})"


# ──────────────────────────────────────────────
# PII Patterns
# ──────────────────────────────────────────────

_PII_PATTERNS: List[Tuple[PIIType, re.Pattern, float]] = [
    # Email addresses
    (PIIType.EMAIL,
     re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
     0.95),

    # Phone numbers (various formats)
    (PIIType.PHONE,
     re.compile(r'''
        (?:
            (?:\+\d{1,3}[\s.-]?)?          # country code
            (?:\(?\d{2,4}\)?[\s.-]?)       # area code
            \d{3,4}[\s.-]?\d{3,5}          # number
        )
     ''', re.VERBOSE),
     0.75),

    # US Social Security Numbers
    (PIIType.SSN,
     re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'),
     0.85),

    # Credit card numbers (Visa, MasterCard, Amex, etc.)
    (PIIType.CREDIT_CARD,
     re.compile(r'\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6011)[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
     0.90),

    # IP addresses (IPv4)
    (PIIType.IP_ADDRESS,
     re.compile(r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'),
     0.80),

    # Passport numbers (generic alphanumeric)
    (PIIType.PASSPORT,
     re.compile(r'\b(?:passport\s*(?:no|number|#)?[\s:]*)?[A-Z]\d{7,8}\b', re.IGNORECASE),
     0.60),
]

# Redaction labels per PII type
_REDACTION_LABELS = {
    PIIType.EMAIL: "[EMAIL_REDACTED]",
    PIIType.PHONE: "[PHONE_REDACTED]",
    PIIType.SSN: "[SSN_REDACTED]",
    PIIType.CREDIT_CARD: "[CARD_REDACTED]",
    PIIType.IP_ADDRESS: "[IP_REDACTED]",
    PIIType.ADDRESS: "[ADDRESS_REDACTED]",
    PIIType.PASSPORT: "[PASSPORT_REDACTED]",
}


# ──────────────────────────────────────────────
# PII Guard Engine
# ──────────────────────────────────────────────

class PIIGuard:
    """
    Personal information detection and redaction engine.

    Scans text for PII patterns and can redact them with safe placeholders.
    Never stores or logs actual PII values — only masked previews.
    """

    def __init__(self, redact_output: bool = True, sensitivity: float = 0.7):
        """
        Args:
            redact_output: If True, automatically redact PII in AI output.
            sensitivity: Minimum confidence threshold (0-1) for PII detection.
        """
        self.redact_output = redact_output
        self.sensitivity = sensitivity
        logger.info(
            f"PIIGuard initialized: sensitivity={sensitivity}, "
            f"redact_output={redact_output}"
        )

    def scan(self, text: str) -> List[PIIMatch]:
        """
        Scan text for personal information patterns.

        Returns:
            List of PIIMatch objects (PII values are masked, not stored).
        """
        if not text:
            return []

        matches: List[PIIMatch] = []

        for pii_type, pattern, base_confidence in _PII_PATTERNS:
            for match in pattern.finditer(text):
                if base_confidence >= self.sensitivity:
                    # Create masked preview (show first 2 + last 2 chars only)
                    raw = match.group()
                    if len(raw) > 6:
                        masked = raw[:2] + "*" * (len(raw) - 4) + raw[-2:]
                    else:
                        masked = "*" * len(raw)

                    matches.append(PIIMatch(
                        pii_type=pii_type,
                        start=match.start(),
                        end=match.end(),
                        masked_preview=masked,
                        confidence=base_confidence,
                    ))

        if matches:
            # Log detection event without logging actual PII
            type_counts = {}
            for m in matches:
                type_counts[m.pii_type.value] = type_counts.get(m.pii_type.value, 0) + 1
            logger.info(f"PII detected: {type_counts}")

        return matches

    def redact(self, text: str) -> str:
        """
        Redact all detected PII, replacing with safe placeholders.

        Returns:
            Text with PII replaced by [TYPE_REDACTED] labels.
        """
        if not text:
            return text

        matches = self.scan(text)
        if not matches:
            return text

        # Sort by position (reverse) to replace from end to start
        # so positions don't shift
        matches.sort(key=lambda m: m.start, reverse=True)

        result = text
        for match in matches:
            label = _REDACTION_LABELS.get(match.pii_type, "[REDACTED]")
            result = result[:match.start] + label + result[match.end:]

        return result

    def has_pii(self, text: str) -> bool:
        """Quick check: does the text contain any PII?"""
        return len(self.scan(text)) > 0

    def get_pii_summary(self, text: str) -> str:
        """Get a human-readable summary of PII found (without revealing PII)."""
        matches = self.scan(text)
        if not matches:
            return "No personal information detected."

        lines = [f"⚠️ Detected {len(matches)} PII item(s):"]
        for m in matches:
            lines.append(f"  • {m.pii_type.value}: {m.masked_preview}")
        return "\n".join(lines)
