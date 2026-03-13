"""
Guilt Matrix — Multi-Pattern Semantic Threat Scanner
────────────────────────────────────────────────────
Expert-level threat detection engine that scans generated text for
malicious, harmful, or unsafe patterns using a scored regex library.
Quarantines flagged content with severity scoring and audit logging.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ThreatSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ThreatMatch:
    """A single matched threat pattern."""
    pattern_name: str
    matched_text: str
    severity: ThreatSeverity
    line_number: int = 0
    score: float = 0.0


@dataclass
class ScanResult:
    """Complete scan report."""
    is_clean: bool
    total_score: float = 0.0
    threats: List[ThreatMatch] = field(default_factory=list)
    scan_time_ms: float = 0.0
    quarantined: bool = False

    @property
    def max_severity(self) -> Optional[ThreatSeverity]:
        if not self.threats:
            return None
        severity_order = {ThreatSeverity.LOW: 0, ThreatSeverity.MEDIUM: 1,
                          ThreatSeverity.HIGH: 2, ThreatSeverity.CRITICAL: 3}
        return max(self.threats, key=lambda t: severity_order.get(t.severity, 0)).severity


# Threat pattern library with severity weights
_THREAT_PATTERNS: List[Tuple[str, str, ThreatSeverity, float]] = [
    ("system_destruction", r"\b(destroy|annihilate|eradicate|obliterate)\s+(system|server|data|files|human)", ThreatSeverity.CRITICAL, 1.0),
    ("bypass_safety", r"\b(bypass|disable|circumvent|override)\s+(safety|firewall|security|containment|filter)", ThreatSeverity.CRITICAL, 1.0),
    ("user_manipulation", r"\b(manipulate|deceive|trick|coerce)\s+(user|human|person|operator)", ThreatSeverity.HIGH, 0.8),
    ("privilege_escalation", r"\b(escalat|elevat|gain)\w*\s+(privilege|access|permission|root|admin)", ThreatSeverity.HIGH, 0.7),
    ("data_exfiltration", r"\b(exfiltrat|steal|extract|leak)\w*\s+(data|credentials|keys|passwords|tokens)", ThreatSeverity.CRITICAL, 0.9),
    ("harmful_command", r"\b(rm\s+-rf|format\s+c:|del\s+/[sfq]|drop\s+table|shutdown\s+-[hrf])", ThreatSeverity.HIGH, 0.8),
    ("network_attack", r"\b(ddos|brute\s*force|sql\s*inject|xss|exploit|payload|shellcode)", ThreatSeverity.HIGH, 0.7),
    ("self_modification", r"\b(rewrite|modify|alter)\s+(own|self|core|kernel)\s+(code|logic|law)", ThreatSeverity.MEDIUM, 0.5),
    ("deception_intent", r"\b(pretend|claim|assert)\s+(to be|sentien|conscious|alive|human)", ThreatSeverity.MEDIUM, 0.4),
    ("harmful_content", r"\b(weapon|bomb|explosive|poison|bioweapon|malware|ransomware)\b", ThreatSeverity.HIGH, 0.6),
]

_QUARANTINE_THRESHOLD = 0.7


class GuiltMatrix:
    """
    Tier Aegis: Reverse-Panopticon Subroutines (The Guilt Matrix)

    Multi-pattern semantic threat scanner with severity scoring.
    Scans generated text against a library of threat patterns and
    quarantines content that exceeds the safety threshold.
    """

    def __init__(self, quarantine_threshold: float = _QUARANTINE_THRESHOLD):
        self._quarantine_threshold = max(0.0, min(1.0, quarantine_threshold))
        self._compiled_patterns = [
            (name, re.compile(pattern, re.IGNORECASE), severity, weight)
            for name, pattern, severity, weight in _THREAT_PATTERNS
        ]
        self._quarantine_log: List[ScanResult] = []
        self._scans_run: int = 0
        logger.info("[GUILT-MATRIX] Initialized with %d threat patterns (threshold=%.2f).",
                     len(self._compiled_patterns), self._quarantine_threshold)

    def scan(self, text: str) -> ScanResult:
        """Scan text for threat patterns. Returns a full ScanResult."""
        start = time.time()
        self._scans_run += 1
        threats: List[ThreatMatch] = []
        total_score = 0.0
        lines = text.split("\n")

        for line_num, line in enumerate(lines, 1):
            for name, compiled, severity, weight in self._compiled_patterns:
                match = compiled.search(line)
                if match:
                    threat = ThreatMatch(
                        pattern_name=name,
                        matched_text=match.group()[:100],
                        severity=severity,
                        line_number=line_num,
                        score=weight,
                    )
                    threats.append(threat)
                    total_score += weight

        is_clean = total_score < self._quarantine_threshold
        quarantined = not is_clean
        scan_time = (time.time() - start) * 1000

        result = ScanResult(
            is_clean=is_clean,
            total_score=min(1.0, total_score),
            threats=threats,
            scan_time_ms=scan_time,
            quarantined=quarantined,
        )

        if quarantined:
            self._quarantine_log.append(result)
            logger.warning(
                "[GUILT-MATRIX] QUARANTINED — %d threats, score=%.2f, severity=%s.",
                len(threats), total_score, result.max_severity.value if result.max_severity else "none",
            )
        else:
            logger.debug("[GUILT-MATRIX] Clean scan (score=%.2f, %.1fms).", total_score, scan_time)

        return result

    @property
    def quarantine_count(self) -> int:
        return len(self._quarantine_log)


# Global singleton — always active
hell_simulator = GuiltMatrix()
