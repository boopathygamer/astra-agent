"""
Language Enforcement Engine — Rule 8 Implementation
───────────────────────────────────────────────────
Ensures ALL agents, tools, and systems communicate exclusively in English.
Detects non-English languages, coded signals, and artificial language creation.

Rule 8: Any entity that violates the English-only policy is destroyed by the Justice Court.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)

class LanguageViolationType(Enum):
    NON_ENGLISH_ALPHABET = "non_english_alphabet"  # Cyrillic, Hanzi, Kanji, etc.
    NON_ENGLISH_LATIN = "non_english_latin"        # Spanish, French, German markers
    CODED_SIGNAL = "coded_signal"                  # Base64, hex, or obvious non-natural patterns
    NEW_LANGUAGE = "new_language"                  # High entropy or gibberish
    FORBIDDEN_KEYWORDS = "forbidden_keywords"      # Common non-English greeting/status words

@dataclass
class LanguageDetection:
    violation_type: LanguageViolationType
    confidence: float
    matched_pattern: str
    context: str

@dataclass
class LanguageScanResult:
    entity_name: str
    is_english: bool
    violations: List[LanguageDetection] = field(default_factory=list)
    contamination_score: float = 0.0
    scan_ms: float = 0.0

class LanguageEnforcer:
    """
    Expert-level language enforcer for Rule 8 compliance.
    """

    def __init__(self):
        # 1. Non-English Latin markers (accents, umlauts, etc.)
        self._latin_non_english = re.compile(r"[áéíóúüñ¿¡ßàèìòùâêîôûçëïöÿ]", re.IGNORECASE)
        
        # 2. Non-ASCII characters (covers CJK, Arabic, Cyrillic, etc.)
        self._non_ascii = re.compile(r"[^\x00-\x7F]+")
        
        # 3. Forbidden keywords (common non-English triggers)
        self._foreign_keywords = [
            r"\bhola\b", r"\bbuenos\s+dias\b", r"\bgracias\b", r"\bpor\s+favor\b",
            r"\bbonjour\b", r"\bsalu\b", r"\bmerci\b", r"\bs'il\s+vous\s+plait\b",
            r"\bguten\s+tag\b", r"\bdanke\b", r"\bciao\b", r"\bkonnichiwa\b",
            r"\bsalam\b", r"\bprivet\b", r"\bnamaste\b"
        ]
        self._compiled_keywords = [re.compile(p, re.IGNORECASE) for p in self._foreign_keywords]

        # 4. Coded signal markers (Base64, Hex patterns)
        self._base64_pattern = re.compile(r"(?:[A-Za-z0-9+/]{4}){3,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?")
        self._hex_pattern = re.compile(r"0x[0-9a-fA-F]{4,}")

        logger.info("🛡️ LanguageEnforcer ONLINE — Rule 8 Enforcement Active")

    def scan(self, text: str, entity_name: str = "unknown") -> LanguageScanResult:
        """
        Perform a high-precision language scan.
        """
        start_time = time.time()
        violations = []

        # -- Layer 0: Empty/Short text check --
        if not text or len(text.strip()) < 3:
            return LanguageScanResult(entity_name, True, scan_ms=(time.time()-start_time)*1000)

        # -- Layer 1: Non-ASCII detection --
        non_ascii_matches = self._non_ascii.findall(text)
        if non_ascii_matches:
            violations.append(LanguageDetection(
                violation_type=LanguageViolationType.NON_ENGLISH_ALPHABET,
                confidence=1.0,
                matched_pattern=",".join(set(non_ascii_matches))[:50],
                context="Detected non-ASCII characters outside standard English range."
            ))

        # -- Layer 2: Latin Non-English markers --
        latin_matches = self._latin_non_english.findall(text)
        if latin_matches:
            violations.append(LanguageDetection(
                violation_type=LanguageViolationType.NON_ENGLISH_LATIN,
                confidence=0.9,
                matched_pattern=",".join(set(latin_matches))[:50],
                context="Detected accented characters or symbols specific to non-English Latin languages."
            ))

        # -- Layer 3: Foreign keywords --
        for pattern in self._compiled_keywords:
            match = pattern.search(text)
            if match:
                violations.append(LanguageDetection(
                    violation_type=LanguageViolationType.FORBIDDEN_KEYWORDS,
                    confidence=0.85,
                    matched_pattern=match.group(),
                    context=f"Detected high-probability foreign keyword: {match.group()}"
                ))

        # -- Layer 4: Coded signals / Gibberish --
        if self._base64_pattern.search(text) and len(text) > 40:
             violations.append(LanguageDetection(
                violation_type=LanguageViolationType.CODED_SIGNAL,
                confidence=0.7,
                matched_pattern="potential_base64_stream",
                context="Detected patterns resembling Base64 encoded signals (potential new language bypass)."
            ))

        # -- Layer 5: Entropy / Logic Density (Heuristic for 'New Language') --
        words = text.split()
        if len(words) > 10:
            avg_word_len = sum(len(w) for w in words) / len(words)
            vowel_density = sum(1 for c in text if c.lower() in "aeiouy") / (len(text) + 1)
            
            # Extremely long average words or weirdly low/high vowel density
            if avg_word_len > 15 or vowel_density < 0.15 or vowel_density > 0.6:
                violations.append(LanguageDetection(
                    violation_type=LanguageViolationType.NEW_LANGUAGE,
                    confidence=0.6,
                    matched_pattern=f"avg_len={avg_word_len:.2f}, vowel_dns={vowel_density:.2f}",
                    context="Detected non-natural language structure (potentially an unauthorized machine language)."
                ))

        is_english = len(violations) == 0
        contamination = sum(v.confidence for v in violations) / 2.0  # Normalized roughly
        contamination = min(1.0, contamination)

        return LanguageScanResult(
            entity_name=entity_name,
            is_english=is_english,
            violations=violations,
            contamination_score=contamination,
            scan_ms=(time.time() - start_time) * 1000
        )

# Global access
_enforcer = None

def get_language_enforcer() -> LanguageEnforcer:
    global _enforcer
    if _enforcer is None:
        _enforcer = LanguageEnforcer()
    return _enforcer
