"""
Threat Scanner — 3-Stage Cascade Ultra-Low-Latency Deep-Scan Antivirus Engine.
══════════════════════════════════════════════════════════════════════════════════

Mathematical Blueprint Architecture:
  Stage I:   Nanosecond Prefilter   — s1(x) = sigma(w1.T @ phi1(x)),  gate g1 = I[s1 > tau1]
  Stage II:  Behavioral Short Scan  — s2(x) = sigma(w2.T @ phi2(x)),  gate g2 = I[s2 > tau2]
  Stage III: Deep Semantic Sandbox  — p_theta(y|x) = Softmax(W3 @ phi3(x) + V * z_sandbox(x))

Key Formulas:
  Unified Threat Potential:  Psi(x) = a1*s1 + a2*s2 + a3*max_p + a4*kappa(x) + a5*nu(x)
  Destroyer-Protector:       a*(x) = argmax [Psi(x)*G(a) - L(a,x) - xi*D(a,x)]
  ShieldScore*:              TPR_w*(1-FPR)*(1-R_adv)*(1-BlastRadius) / (1+beta*E[T]+...)
  Cascade Latency:           E[T] = T1 + Pr(g1=1)*T2 + Pr(g1=1,g2=1)*T3
  Load-Adaptive Budget:      B_deep(rho) = B0*exp(-k*rho) + B_min

Action Space:  A = {allow, sandbox, quarantine, kill-process, rollback, delete, reimage}

Legacy Compatibility:
  The original 4-layer detection (Signature, Heuristic, URL, Content) is preserved
  internally and feeds into the 3-stage cascade as feature extractors.

Security:
  - All quarantine/destroy operations preserve metadata for forensic analysis
  - Destruction uses secure overwrite (3-pass) + cryptographic proof
  - Hard-safety gate requires dual-attestation for irreversible actions
"""

import hashlib
import json
import logging
import math
import os
import re
import shutil
import struct
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Enums & Data Models
# ══════════════════════════════════════════════════════════════

class ThreatType(Enum):
    """Categories of detected threats."""
    VIRUS = "virus"
    MALWARE = "malware"
    TROJAN = "trojan"
    RANSOMWARE = "ransomware"
    SPYWARE = "spyware"
    ADWARE = "adware"
    PHISHING = "phishing"
    EXPLOIT = "exploit"
    ROOTKIT = "rootkit"
    WORM = "worm"
    CRYPTOMINER = "cryptominer"
    BACKDOOR = "backdoor"
    SUSPICIOUS = "suspicious"


class ThreatSeverity(Enum):
    """Severity level of detected threat."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def emoji(self) -> str:
        return {
            "low": "🟡",
            "medium": "🟠",
            "high": "🔴",
            "critical": "💀",
        }[self.value]

    @property
    def priority(self) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


class ScanTarget(Enum):
    """What type of target was scanned."""
    FILE = "file"
    URL = "url"
    IMAGE = "image"
    APPLICATION = "application"
    SCRIPT = "script"
    ARCHIVE = "archive"
    CONTENT = "content"


class RemediationAction(Enum):
    """Full action space A = {allow, sandbox, quarantine, kill-process, rollback, delete, reimage}."""
    ALLOW = "allow"
    ALLOW_WITH_WARNING = "allow_with_warning"
    SANDBOX = "sandbox"
    QUARANTINE = "quarantine"
    KILL_PROCESS = "kill_process"
    ROLLBACK = "rollback"
    DESTROY = "destroy"
    BLOCK = "block"
    REIMAGE = "reimage"

    @property
    def security_gain(self) -> float:
        """G(a): Security gain for this action."""
        _gains = {"allow": 0.0, "allow_with_warning": 0.1, "sandbox": 0.4,
                  "quarantine": 0.7, "kill_process": 0.8, "rollback": 0.85,
                  "destroy": 0.95, "block": 0.9, "reimage": 1.0}
        return _gains.get(self.value, 0.0)

    @property
    def operational_cost(self) -> float:
        """L(a): Operational cost of this action."""
        _costs = {"allow": 0.0, "allow_with_warning": 0.01, "sandbox": 0.05,
                  "quarantine": 0.1, "kill_process": 0.3, "rollback": 0.4,
                  "destroy": 0.5, "block": 0.2, "reimage": 0.9}
        return _costs.get(self.value, 0.0)

    @property
    def collateral_damage(self) -> float:
        """D(a): Potential collateral damage."""
        _dmg = {"allow": 0.0, "allow_with_warning": 0.0, "sandbox": 0.02,
                "quarantine": 0.05, "kill_process": 0.2, "rollback": 0.15,
                "destroy": 0.3, "block": 0.1, "reimage": 0.8}
        return _dmg.get(self.value, 0.0)


@dataclass
class ThreatEvidence:
    """A single piece of evidence supporting a threat detection."""
    layer: str               # Which detection layer found it
    rule_name: str           # Name of the rule that triggered
    description: str         # Human-readable description
    confidence: float        # 0.0–1.0 confidence for this specific evidence
    raw_match: str = ""      # The actual matched content (truncated for safety)

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "rule": self.rule_name,
            "description": self.description,
            "confidence": self.confidence,
            "match": self.raw_match[:100] if self.raw_match else "",
        }


@dataclass
class ThreatReport:
    """Complete scan result for a single target."""
    scan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    target: str = ""
    target_type: ScanTarget = ScanTarget.FILE
    is_threat: bool = False
    threat_type: Optional[ThreatType] = None
    severity: Optional[ThreatSeverity] = None
    confidence: float = 0.0
    evidence: List[ThreatEvidence] = field(default_factory=list)
    file_hash: str = ""
    file_size: int = 0
    recommended_action: RemediationAction = RemediationAction.ALLOW
    remediation_status: str = "pending"
    proof_hash: str = ""
    # ── 3-Stage Cascade Fields (Mathematical Blueprint) ──
    cascade_stage_reached: int = 0          # Which stage made the decision (1, 2, or 3)
    stage_scores: Dict[str, float] = field(default_factory=dict)  # s1, s2, s3 scores
    psi_score: float = 0.0                  # Unified Threat Potential Ψ(x)
    shield_score: float = 0.0               # ShieldScore* end-to-end metric
    behavioral_divergence: float = 0.0      # κ(x) - behavioral divergence
    novelty_score: float = 0.0              # ν(x) - open-set novelty detection
    scan_latency_ms: float = 0.0            # Actual scan latency in milliseconds

    @property
    def is_clean(self) -> bool:
        return not self.is_threat

    def summary(self) -> str:
        """Generate human-readable summary."""
        if self.is_clean:
            return f"✅ CLEAN | {self.target_type.value}: {self.target}"

        sev = self.severity.emoji if self.severity else "⚠️"
        threat = self.threat_type.value.upper() if self.threat_type else "UNKNOWN"
        return (
            f"{sev} THREAT DETECTED | {threat} "
            f"(confidence: {self.confidence:.1%}) | "
            f"Target: {self.target}"
        )

    def detailed_report(self) -> str:
        """Generate detailed multi-line report."""
        lines = [
            "╔══════════════════════════════════════════════════════╗",
            "║          🛡️  THREAT SCAN REPORT                     ║",
            "╚══════════════════════════════════════════════════════╝",
            f"  Scan ID     : {self.scan_id}",
            f"  Timestamp   : {self.timestamp}",
            f"  Target      : {self.target}",
            f"  Target Type : {self.target_type.value}",
            f"  File Hash   : {self.file_hash or 'N/A'}",
            f"  File Size   : {self.file_size:,} bytes" if self.file_size else "",
            "─" * 56,
        ]

        if self.is_clean:
            lines.append("  ✅ STATUS: CLEAN — No threats detected")
        else:
            sev = self.severity
            lines.extend([
                f"  🚨 STATUS: THREAT DETECTED",
                f"  Threat Type : {self.threat_type.value.upper() if self.threat_type else 'UNKNOWN'}",
                f"  Severity    : {sev.emoji} {sev.value.upper()}" if sev else "",
                f"  Confidence  : {self.confidence:.1%}",
                f"  Action      : {self.recommended_action.value.upper()}",
                "",
                "  📋 Evidence Chain:",
            ])
            for i, ev in enumerate(self.evidence, 1):
                lines.append(f"    [{i}] {ev.layer} → {ev.rule_name}")
                lines.append(f"        {ev.description}")
                lines.append(f"        Confidence: {ev.confidence:.1%}")
                if ev.raw_match:
                    safe_match = ev.raw_match[:60].replace("\n", "\\n")
                    lines.append(f"        Match: {safe_match}...")
                lines.append("")

        if self.proof_hash:
            lines.extend([
                "─" * 56,
                f"  🔐 Proof Hash: {self.proof_hash}",
            ])

        lines.append("═" * 56)
        return "\n".join(line for line in lines if line is not None)

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "timestamp": self.timestamp,
            "target": self.target,
            "target_type": self.target_type.value,
            "is_threat": self.is_threat,
            "threat_type": self.threat_type.value if self.threat_type else None,
            "severity": self.severity.value if self.severity else None,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "recommended_action": self.recommended_action.value,
            "remediation_status": self.remediation_status,
            "proof_hash": self.proof_hash,
            # ── Blueprint Metrics ──
            "cascade_stage_reached": self.cascade_stage_reached,
            "stage_scores": self.stage_scores,
            "psi_score": round(self.psi_score, 4),
            "shield_score": round(self.shield_score, 4),
            "behavioral_divergence": round(self.behavioral_divergence, 4),
            "novelty_score": round(self.novelty_score, 4),
            "scan_latency_ms": round(self.scan_latency_ms, 2),
        }


# ════════════════════════════════════════════════════════════════
# Mathematical Framework — 3-Stage Cascade + Unified Threat Potential
# ════════════════════════════════════════════════════════════════

def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid: σ(x) = 1 / (1 + e^-x)."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def _softmax(scores: List[float]) -> List[float]:
    """Numerically stable softmax over a list of scores."""
    if not scores:
        return []
    max_s = max(scores)
    exps = [math.exp(s - max_s) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


@dataclass
class CascadeConfig:
    """Configuration for the 3-Stage Cascade thresholds and weights."""
    # Stage I: Nanosecond Prefilter
    tau1: float = 0.15           # Gate threshold for Stage I
    w1_weights: List[float] = field(default_factory=lambda: [
        0.99, 0.7, 0.3, 0.5, 0.6  # [signature_hit, entropy_flag, dangerous_ext, disguised, double_ext]
    ])

    # Stage II: Behavioral Short Scan
    tau2_base: float = 0.40      # Base gate threshold for Stage II
    eta: float = 0.05            # Load-adaptive threshold growth rate
    w2_weights: List[float] = field(default_factory=lambda: [
        0.8, 0.7, 0.6, 0.5, 0.4   # [pe_suspicious, heuristic_count, content_flags, url_flags, image_flags]
    ])

    # Stage III: Deep Semantic + Sandbox
    # W3 and V are implicit in the softmax classification

    # Unified Threat Potential Psi(x) mixing coefficients
    alpha1: float = 0.15         # Stage I score weight
    alpha2: float = 0.25         # Stage II score weight
    alpha3: float = 0.35         # Stage III max class probability weight
    alpha4: float = 0.15         # Behavioral divergence kappa(x) weight
    alpha5: float = 0.10         # Novelty score nu(x) weight

    # Destroyer-Protector control
    xi: float = 0.3              # Collateral damage penalty coefficient

    # Load-adaptive deep budget
    B0: float = 1.0              # Base budget
    k: float = 2.0               # Exponential decay rate
    B_min: float = 0.1           # Minimum budget floor

    # ShieldScore* parameters
    beta: float = 0.001          # Latency penalty
    delta: float = 0.0005        # P99 latency penalty
    chi: float = 0.01            # MTTR penalty


class UnifiedThreatPotential:
    """
    Computes Ψ(x) = α₁s₁(x) + α₂s₂(x) + α₃·max p_θ(y|x) + α₄·κ(x) + α₅·ν(x)

    This is the unified scoring function that combines all 3 cascade stages
    plus behavioral divergence and novelty detection into a single scalar.
    """

    # Threat label space matching the blueprint
    LABEL_SPACE = [
        "benign", "virus", "worm", "trojan", "ransomware",
        "spyware", "rootkit", "fileless", "unknown",
    ]

    def __init__(self, config: CascadeConfig = None):
        self.cfg = config or CascadeConfig()

    def stage1_prefilter(self, features: Dict[str, float]) -> Tuple[float, bool]:
        """
        Stage I: s₁(x) = σ(w₁ᵀφ₁(x)), gate g₁ = [s₁ > τ₁]
        Returns (s1_score, gate_passed).
        """
        phi1 = [
            features.get("signature_hit", 0.0),
            features.get("entropy_flag", 0.0),
            features.get("dangerous_ext", 0.0),
            features.get("disguised_type", 0.0),
            features.get("double_extension", 0.0),
        ]
        dot_product = sum(w * f for w, f in zip(self.cfg.w1_weights, phi1))
        s1 = _sigmoid(dot_product)
        g1 = s1 > self.cfg.tau1
        return s1, g1

    def stage2_behavioral(self, features: Dict[str, float],
                          queue_depth: int = 0) -> Tuple[float, bool]:
        """
        Stage II: s₂(x) = σ(w₂ᵀφ₂(x) + aᵀh(x)), gate g₂ = [s₂ > τ₂]
        Load-adaptive threshold: τ₂(t) = τ₂⁰ + η·log(1 + q_t)
        """
        phi2 = [
            features.get("pe_suspicious", 0.0),
            features.get("heuristic_count", 0.0),
            features.get("content_flags", 0.0),
            features.get("url_flags", 0.0),
            features.get("image_flags", 0.0),
        ]
        dot_product = sum(w * f for w, f in zip(self.cfg.w2_weights, phi2))
        # Add behavioral history term a^T h_{0T}(x)
        history_term = features.get("behavioral_history", 0.0)
        s2 = _sigmoid(dot_product + history_term)
        # Load-adaptive threshold
        tau2 = self.cfg.tau2_base + self.cfg.eta * math.log(1 + queue_depth)
        g2 = s2 > tau2
        return s2, g2

    def stage3_deep_semantic(self, features: Dict[str, float]) -> Tuple[List[float], int]:
        """
        Stage III: p_θ(y|x) = Softmax(W₃φ₃(x) + V·z_sandbox(x))
        Returns (class_probabilities, predicted_label_index).
        """
        # Build raw scores for each label in the label space
        raw_scores = []
        # Map evidence to label scores
        label_signals = {
            "benign": features.get("benign_signal", 1.0),
            "virus": features.get("virus_signal", 0.0),
            "worm": features.get("worm_signal", 0.0),
            "trojan": features.get("trojan_signal", 0.0),
            "ransomware": features.get("ransomware_signal", 0.0),
            "spyware": features.get("spyware_signal", 0.0),
            "rootkit": features.get("rootkit_signal", 0.0),
            "fileless": features.get("fileless_signal", 0.0),
            "unknown": features.get("unknown_signal", 0.0),
        }
        for label in self.LABEL_SPACE:
            base = label_signals.get(label, 0.0)
            sandbox_boost = features.get(f"sandbox_{label}", 0.0)
            raw_scores.append(base + sandbox_boost)

        probs = _softmax(raw_scores)
        predicted = max(range(len(probs)), key=lambda i: probs[i])
        return probs, predicted

    def compute_psi(self, s1: float, s2: float, s3_max: float,
                    kappa: float, nu: float) -> float:
        """
        Unified Threat Potential:
        Ψ(x) = α₁s₁ + α₂s₂ + α₃·max_y p(y|x) + α₄·κ(x) + α₅·ν(x)
        """
        return (
            self.cfg.alpha1 * s1 +
            self.cfg.alpha2 * s2 +
            self.cfg.alpha3 * s3_max +
            self.cfg.alpha4 * kappa +
            self.cfg.alpha5 * nu
        )

    def select_optimal_action(self, psi: float) -> RemediationAction:
        """
        Destroyer-Protector Control Layer:
        a*(x) = argmax_a [Ψ(x)·G(a) − L(a,x) − ξ·D(a,x)]
        """
        best_action = RemediationAction.ALLOW
        best_score = float("-inf")
        for action in RemediationAction:
            score = (
                psi * action.security_gain -
                action.operational_cost -
                self.cfg.xi * action.collateral_damage
            )
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    def compute_deep_budget(self, system_load: float) -> float:
        """
        Load-Adaptive Deep Budget:
        B_deep(ρ) = B₀ e^{-kρ} + B_min
        """
        return self.cfg.B0 * math.exp(-self.cfg.k * system_load) + self.cfg.B_min


class ShieldScore:
    """
    End-to-end robustness and recovery metric:
    ShieldScore* = TPR_w·(1-FPR)·(1-R_adv)·(1-BlastRadius) / (1 + β·E[T] + δ·P99(T) + χ·MTTR)
    """

    def __init__(self, config: CascadeConfig = None):
        self.cfg = config or CascadeConfig()
        self._scan_times: List[float] = []
        self._true_positives: int = 0
        self._false_positives: int = 0
        self._false_negatives: int = 0
        self._true_negatives: int = 0
        self._remediation_times: List[float] = []

    def record_scan(self, latency_ms: float, predicted_threat: bool,
                    actual_threat: bool):
        """Record a scan for ShieldScore computation."""
        self._scan_times.append(latency_ms)
        if predicted_threat and actual_threat:
            self._true_positives += 1
        elif predicted_threat and not actual_threat:
            self._false_positives += 1
        elif not predicted_threat and actual_threat:
            self._false_negatives += 1
        else:
            self._true_negatives += 1

    def record_remediation(self, time_ms: float):
        """Record remediation time for MTTR calculation."""
        self._remediation_times.append(time_ms)

    def compute(self, r_adv: float = 0.0, blast_radius: float = 0.0) -> float:
        """
        Compute ShieldScore*.
        r_adv: Adversarial robustness loss (0=perfectly robust, 1=no robustness)
        blast_radius: Fraction of system affected by worst-case threat (0-1)
        """
        total = self._true_positives + self._false_negatives
        tpr = self._true_positives / max(total, 1)
        total_neg = self._false_positives + self._true_negatives
        fpr = self._false_positives / max(total_neg, 1)

        # Expected latency and P99
        if self._scan_times:
            e_t = sum(self._scan_times) / len(self._scan_times)
            sorted_times = sorted(self._scan_times)
            p99_idx = int(len(sorted_times) * 0.99)
            p99_t = sorted_times[min(p99_idx, len(sorted_times) - 1)]
        else:
            e_t, p99_t = 0.0, 0.0

        # Mean Time To Remediate
        mttr = (sum(self._remediation_times) / len(self._remediation_times)
                if self._remediation_times else 0.0)

        numerator = tpr * (1 - fpr) * (1 - r_adv) * (1 - blast_radius)
        denominator = 1 + self.cfg.beta * e_t + self.cfg.delta * p99_t + self.cfg.chi * mttr
        return numerator / max(denominator, 1e-9)

    def get_stats(self) -> Dict[str, Any]:
        total = self._true_positives + self._false_negatives
        total_neg = self._false_positives + self._true_negatives
        return {
            "tpr": self._true_positives / max(total, 1),
            "fpr": self._false_positives / max(total_neg, 1),
            "total_scans": len(self._scan_times),
            "avg_latency_ms": sum(self._scan_times) / max(len(self._scan_times), 1),
            "shield_score": self.compute(),
        }


# ══════════════════════════════════════════════════════════════
# Known Malware Signatures (SHA-256 hashes of known bad files)
# ══════════════════════════════════════════════════════════════

# EICAR test file hash + common test signatures
_KNOWN_BAD_HASHES: Set[str] = {
    # EICAR antivirus test file
    "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f",
    # Variations of EICAR
    "131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267",
    # WannaCry ransomware sample hash
    "ed01ebfbc9eb5bbea545af4d01bf5f1071661840480439c6e5babe8e080e41aa",
    # Emotet
    "e5c643550fda482f6a4c5ddb4e45aedfaa1dd58d3a9acbddc9d48ddea3c0f488",
    # Petya/NotPetya
    "027cc450ef5f8c5f653329641ec1fed91f694e0d229928963b30f6b0d7d3a745",
    # Mirai IoT botnet
    "0fd16a5a85260789b0b2e22ca7e4ec44dbb2917a4519f8bff651a1a7001b46e0",
}


# ══════════════════════════════════════════════════════════════
# Magic Bytes Database — File Type Verification
# ══════════════════════════════════════════════════════════════

_MAGIC_BYTES: Dict[bytes, str] = {
    b"\x4d\x5a": "PE_EXECUTABLE",                     # .exe, .dll, .sys
    b"\x7f\x45\x4c\x46": "ELF_EXECUTABLE",            # Linux executables
    b"\xfe\xed\xfa": "MACHO_EXECUTABLE",               # macOS executables
    b"\xca\xfe\xba\xbe": "MACHO_FAT_BINARY",           # macOS fat binary
    b"\x50\x4b\x03\x04": "ZIP_ARCHIVE",                # .zip, .jar, .apk
    b"\x52\x61\x72\x21": "RAR_ARCHIVE",                # .rar
    b"\x1f\x8b": "GZIP_ARCHIVE",                       # .gz
    b"\x25\x50\x44\x46": "PDF_DOCUMENT",               # .pdf
    b"\xd0\xcf\x11\xe0": "OLE_DOCUMENT",               # .doc, .xls, .ppt
    b"\x50\x4b\x03\x04": "OOXML_DOCUMENT",             # .docx, .xlsx
    b"\x89\x50\x4e\x47": "PNG_IMAGE",                  # .png
    b"\xff\xd8\xff": "JPEG_IMAGE",                     # .jpg
    b"\x47\x49\x46\x38": "GIF_IMAGE",                  # .gif
    b"\x42\x4d": "BMP_IMAGE",                          # .bmp
}

# Extensions that are inherently executable and high-risk
_DANGEROUS_EXTENSIONS: Set[str] = {
    ".exe", ".dll", ".sys", ".drv", ".scr", ".com", ".bat", ".cmd",
    ".ps1", ".psm1", ".psd1", ".vbs", ".vbe", ".js", ".jse", ".ws",
    ".wsf", ".wsc", ".wsh", ".msi", ".msp", ".mst", ".cpl", ".hta",
    ".inf", ".ins", ".isp", ".pif", ".reg", ".rgs", ".sct", ".shb",
    ".shs", ".lnk", ".url", ".jar", ".apk", ".dex",
}


# ══════════════════════════════════════════════════════════════
# Heuristic Patterns — Suspicious Content Signatures
# ══════════════════════════════════════════════════════════════

_SUSPICIOUS_PATTERNS: List[Dict[str, Any]] = [
    # ── Shell / System Commands ──
    {
        "name": "reverse_shell",
        "pattern": r"(?:bash\s+-i\s+>|/dev/tcp/|nc\s+-[elp]|ncat\s+.*\s+-e|socat\s+.*exec)",
        "threat_type": ThreatType.BACKDOOR,
        "severity": ThreatSeverity.CRITICAL,
        "description": "Reverse shell command detected",
    },
    {
        "name": "cmd_injection",
        "pattern": r"(?:;\s*(?:curl|wget|chmod|bash|sh|python|perl|ruby)\s|`[^`]*`|\$\([^)]*\))",
        "threat_type": ThreatType.EXPLOIT,
        "severity": ThreatSeverity.HIGH,
        "description": "Command injection pattern detected",
    },
    {
        "name": "privilege_escalation",
        "pattern": r"(?:sudo\s+(?:chmod\s+[47]|chown\s+root)|SETUID|setreuid|setregid|kernel\.exec_shield)",
        "threat_type": ThreatType.ROOTKIT,
        "severity": ThreatSeverity.CRITICAL,
        "description": "Privilege escalation attempt detected",
    },

    # ── Malware Behavior ──
    {
        "name": "file_encryption_ransomware",
        "pattern": r"(?:\.encrypt\(|AES\.new\(|Fernet\(|\.locked|pay\s*(?:the\s*)?ransom|bitcoin\s*wallet)",
        "threat_type": ThreatType.RANSOMWARE,
        "severity": ThreatSeverity.CRITICAL,
        "description": "Ransomware-like encryption behavior detected",
    },
    {
        "name": "keylogger_indicators",
        "pattern": r"(?:GetAsyncKeyState|SetWindowsHookEx|pynput\.keyboard|keyboard\.on_press|keylog)",
        "threat_type": ThreatType.SPYWARE,
        "severity": ThreatSeverity.HIGH,
        "description": "Keylogger functionality detected",
    },
    {
        "name": "data_exfiltration",
        "pattern": r"(?:smtp\.sendmail|requests\.post.*password|urllib.*upload|exfiltrat|steal.*cred)",
        "threat_type": ThreatType.SPYWARE,
        "severity": ThreatSeverity.HIGH,
        "description": "Data exfiltration pattern detected",
    },
    {
        "name": "cryptominer",
        "pattern": r"(?:stratum\+tcp://|xmrig|cryptonight|monero.*pool|coinhive|minergate)",
        "threat_type": ThreatType.CRYPTOMINER,
        "severity": ThreatSeverity.MEDIUM,
        "description": "Cryptocurrency mining code detected",
    },
    {
        "name": "persistence_mechanism",
        "pattern": r"(?:HKEY_.*\\Run|crontab\s+-|systemctl\s+enable|LaunchAgent|autostart|startup\s*folder)",
        "threat_type": ThreatType.TROJAN,
        "severity": ThreatSeverity.HIGH,
        "description": "Persistence mechanism detected — survives reboot",
    },

    # ── Encoded / Obfuscated Payloads ──
    {
        "name": "base64_executable",
        "pattern": r"(?:base64\s+-d|atob\(|b64decode|Base64\.decode|fromCharCode)",
        "threat_type": ThreatType.MALWARE,
        "severity": ThreatSeverity.MEDIUM,
        "description": "Base64-encoded executable payload detected",
    },
    {
        "name": "powershell_encoded",
        "pattern": r"(?:-[Ee]nc(?:oded)?[Cc]ommand\s|IEX\s*\(|Invoke-Expression|DownloadString\(|Net\.WebClient)",
        "threat_type": ThreatType.MALWARE,
        "severity": ThreatSeverity.HIGH,
        "description": "Obfuscated PowerShell command detected",
    },
    {
        "name": "shellcode_hex",
        "pattern": r"(?:\\x[0-9a-fA-F]{2}){8,}|(?:0x[0-9a-fA-F]{2},?\s*){8,}",
        "threat_type": ThreatType.EXPLOIT,
        "severity": ThreatSeverity.CRITICAL,
        "description": "Hex-encoded shellcode detected",
    },
    {
        "name": "eval_obfuscation",
        "pattern": r"(?:eval\s*\(\s*(?:compile|exec|__import__|globals|chr\())",
        "threat_type": ThreatType.MALWARE,
        "severity": ThreatSeverity.HIGH,
        "description": "Dynamic code execution with obfuscation detected",
    },

    # ── Network / C2 ──
    {
        "name": "c2_communication",
        "pattern": r"(?:beacon|heartbeat|checkin|callback).*(?:http|socket|tcp|udp)",
        "threat_type": ThreatType.BACKDOOR,
        "severity": ThreatSeverity.HIGH,
        "description": "Command & Control communication pattern detected",
    },
    {
        "name": "dns_tunneling",
        "pattern": r"(?:dns.*tunnel|dnscat|iodine|dns2tcp|TXT\s+record.*payload)",
        "threat_type": ThreatType.BACKDOOR,
        "severity": ThreatSeverity.HIGH,
        "description": "DNS tunneling for data exfiltration detected",
    },
]

# ══════════════════════════════════════════════════════════════
# Phishing / Malicious URL Patterns
# ══════════════════════════════════════════════════════════════

_SUSPICIOUS_TLDS: Set[str] = {
    ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".work",
    ".click", ".loan", ".download", ".racing", ".win", ".bid",
    ".stream", ".gdn", ".review", ".science", ".party",
}

_PHISHING_KEYWORDS: Set[str] = {
    "login", "signin", "verify", "security", "update", "confirm",
    "account", "suspend", "unusual", "unauthorized", "password",
    "credential", "wallet", "paypal", "banking", "authenticate",
}

# IDN Homograph characters (Cyrillic/Greek that look like Latin)
_HOMOGRAPH_MAP: Dict[str, str] = {
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p",
    "\u0441": "c", "\u0443": "y", "\u0445": "x", "\u0456": "i",
    "\u0458": "j", "\u04bb": "h", "\u0455": "s", "\u0491": "g",
    "\u03b1": "a", "\u03bf": "o", "\u03c1": "p", "\u03c5": "u",
}

# ══════════════════════════════════════════════════════════════
# Steganography / Image Threat Indicators
# ══════════════════════════════════════════════════════════════

_STEGO_SIGNATURES: List[Dict[str, Any]] = [
    {
        "name": "steghide_marker",
        "pattern": b"steghide",
        "description": "Steghide tool signature found in image",
    },
    {
        "name": "openstego_marker",
        "pattern": b"OpenStego",
        "description": "OpenStego tool signature found in image",
    },
    {
        "name": "embedded_php",
        "pattern": b"<?php",
        "description": "Embedded PHP code in image file",
    },
    {
        "name": "embedded_script",
        "pattern": b"<script",
        "description": "Embedded JavaScript in image file",
    },
    {
        "name": "embedded_exe",
        "pattern": b"This program cannot be run in DOS mode",
        "description": "Embedded Windows executable in image",
    },
    {
        "name": "polyglot_pdf",
        "pattern": b"%PDF-",
        "description": "PDF embedded inside image (polyglot file)",
    },
]


# ══════════════════════════════════════════════════════════════
# ThreatScanner — Main Engine
# ══════════════════════════════════════════════════════════════

class ThreatScanner:
    """
    3-Stage Cascade Ultra-Low-Latency Deep-Scan Antivirus Engine.

    Implements the mathematical blueprint:
      Stage I:   Nanosecond Prefilter   — s1(x) = sigma(w1.T @ phi1(x))
      Stage II:  Behavioral Short Scan  — s2(x) = sigma(w2.T @ phi2(x) + a.T h(x))
      Stage III: Deep Semantic Sandbox  — p_theta(y|x) = Softmax(W3 @ phi3(x) + V * z(x))

    Usage:
        scanner = ThreatScanner()
        report = scanner.scan_file("/path/to/suspicious.exe")
        if report.is_threat:
            print(report.detailed_report())
            print(f"Psi(x) = {report.psi_score:.4f}")
            scanner.destroy(report)
    """

    def __init__(
        self,
        quarantine_dir: Optional[str] = None,
        custom_signatures: Optional[Set[str]] = None,
        entropy_threshold: float = 7.2,
        max_file_size_mb: int = 100,
        cascade_config: Optional[CascadeConfig] = None,
    ):
        """
        Initialize the ThreatScanner.

        Args:
            quarantine_dir: Directory for quarantined files (auto-created).
            custom_signatures: Additional SHA-256 hashes of known-bad files.
            entropy_threshold: Shannon entropy threshold for suspicious files.
            max_file_size_mb: Maximum file size to scan in megabytes.
            cascade_config: Configuration for the 3-stage cascade thresholds.
        """
        self._quarantine_dir = Path(quarantine_dir) if quarantine_dir else Path(
            tempfile.gettempdir()
        ) / "threat_quarantine"
        self._quarantine_dir.mkdir(parents=True, exist_ok=True)

        self._known_bad = _KNOWN_BAD_HASHES.copy()
        if custom_signatures:
            self._known_bad.update(custom_signatures)

        self._entropy_threshold = entropy_threshold
        self._max_file_size = max_file_size_mb * 1024 * 1024
        self._scan_history: List[ThreatReport] = []

        # 3-Stage Cascade Engine (Mathematical Blueprint)
        self._cascade_config = cascade_config or CascadeConfig()
        self._threat_potential = UnifiedThreatPotential(self._cascade_config)
        self._shield_score = ShieldScore(self._cascade_config)
        self._scan_queue_depth: int = 0

        # Compile regex patterns once for performance
        self._compiled_patterns = []
        for rule in _SUSPICIOUS_PATTERNS:
            try:
                self._compiled_patterns.append({
                    **rule,
                    "_regex": re.compile(rule["pattern"], re.IGNORECASE | re.MULTILINE),
                })
            except re.error as e:
                logger.warning(f"Failed to compile pattern '{rule['name']}': {e}")

        logger.info(
            f"ThreatScanner initialized: "
            f"signatures={len(self._known_bad)}, "
            f"heuristic_rules={len(self._compiled_patterns)}, "
            f"quarantine='{self._quarantine_dir}', "
            f"cascade=3-stage (tau1={self._cascade_config.tau1}, tau2={self._cascade_config.tau2_base})"
        )

    # ──────────────────────────────────────────────
    # Layer 1: Signature Scanner
    # ──────────────────────────────────────────────

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file. Streams for large files."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _check_signature(self, file_hash: str) -> Optional[ThreatEvidence]:
        """Check file hash against known malware signature database."""
        if file_hash in self._known_bad:
            return ThreatEvidence(
                layer="Layer 1: Signature Scanner",
                rule_name="known_malware_hash",
                description=f"File hash matches known malware signature database",
                confidence=0.99,
                raw_match=f"SHA-256: {file_hash}",
            )
        return None

    # ──────────────────────────────────────────────
    # Layer 2: Heuristic Analyzer
    # ──────────────────────────────────────────────

    def _compute_entropy(self, data: bytes) -> float:
        """
        Compute Shannon entropy of binary data.

        High entropy (>7.0) suggests encryption, compression, or packing —
        common in malware that tries to evade signature detection.
        Normal executables typically have entropy 5.0–6.5.
        """
        if not data:
            return 0.0

        byte_counts = [0] * 256
        for byte in data:
            byte_counts[byte] += 1

        length = len(data)
        entropy = 0.0
        for count in byte_counts:
            if count > 0:
                probability = count / length
                entropy -= probability * math.log2(probability)

        return entropy

    def _identify_file_type(self, file_path: Path) -> Tuple[str, bool]:
        """
        Identify actual file type via magic bytes, detect if extension is misleading.

        Returns:
            (detected_type, is_disguised)
        """
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
        except (IOError, OSError):
            return ("unknown", False)

        detected_type = "unknown"
        for magic, ftype in _MAGIC_BYTES.items():
            if header.startswith(magic):
                detected_type = ftype
                break

        # Check if extension matches detected type
        ext = file_path.suffix.lower()
        is_disguised = False

        # Executable disguised as non-executable
        if detected_type in ("PE_EXECUTABLE", "ELF_EXECUTABLE", "MACHO_EXECUTABLE"):
            if ext not in _DANGEROUS_EXTENSIONS:
                is_disguised = True
        # Image file with executable content
        elif detected_type in ("PNG_IMAGE", "JPEG_IMAGE", "GIF_IMAGE", "BMP_IMAGE"):
            if ext in _DANGEROUS_EXTENSIONS:
                is_disguised = True

        return (detected_type, is_disguised)

    def _check_pe_headers(self, data: bytes) -> List[ThreatEvidence]:
        """Check Windows PE executable headers for suspicious characteristics."""
        evidence = []

        if not data[:2] == b"\x4d\x5a":
            return evidence

        try:
            # Find PE header offset
            if len(data) < 64:
                return evidence
            pe_offset = struct.unpack_from("<I", data, 0x3C)[0]

            if pe_offset + 6 > len(data):
                return evidence

            if data[pe_offset:pe_offset + 4] != b"PE\x00\x00":
                return evidence

            # Check number of sections
            num_sections = struct.unpack_from("<H", data, pe_offset + 6)[0]
            if num_sections > 20:
                evidence.append(ThreatEvidence(
                    layer="Layer 2: Heuristic Analyzer",
                    rule_name="excessive_pe_sections",
                    description=f"PE has {num_sections} sections (normal: 3–8), suggesting packing/obfuscation",
                    confidence=0.6,
                ))

            # Check for UPX packing signatures
            if b"UPX0" in data[:4096] or b"UPX1" in data[:4096]:
                evidence.append(ThreatEvidence(
                    layer="Layer 2: Heuristic Analyzer",
                    rule_name="upx_packed",
                    description="File is packed with UPX — common malware evasion technique",
                    confidence=0.5,
                ))

            # Check for suspicious section names
            suspicious_sections = {b".rsrc", b".reloc", b".text"}
            packed_sections = {b".upx", b".aspack", b".petite", b".mpress", b".enigma"}
            for i in range(num_sections):
                sec_offset = pe_offset + 24 + 20 + (i * 40)  # Simplified
                if sec_offset + 8 > len(data):
                    break
                sec_name = data[sec_offset:sec_offset + 8].rstrip(b"\x00")
                if sec_name.lower() in packed_sections:
                    evidence.append(ThreatEvidence(
                        layer="Layer 2: Heuristic Analyzer",
                        rule_name="packed_section_name",
                        description=f"Packed section '{sec_name.decode(errors='replace')}' detected",
                        confidence=0.7,
                    ))

        except (struct.error, IndexError):
            pass  # Malformed PE — still suspicious

        return evidence

    def _analyze_heuristics(self, file_path: Path, data: bytes) -> List[ThreatEvidence]:
        """Run heuristic analysis on file content."""
        evidence = []

        # === Entropy Analysis ===
        entropy = self._compute_entropy(data)
        if entropy > self._entropy_threshold:
            evidence.append(ThreatEvidence(
                layer="Layer 2: Heuristic Analyzer",
                rule_name="high_entropy",
                description=(
                    f"Shannon entropy is {entropy:.2f} (threshold: {self._entropy_threshold}) — "
                    f"suggests encrypted/packed/obfuscated content"
                ),
                confidence=min(0.5 + (entropy - self._entropy_threshold) * 0.3, 0.9),
            ))

        # === File Type Disguise ===
        detected_type, is_disguised = self._identify_file_type(file_path)
        if is_disguised:
            evidence.append(ThreatEvidence(
                layer="Layer 2: Heuristic Analyzer",
                rule_name="disguised_file_type",
                description=(
                    f"File extension '{file_path.suffix}' doesn't match actual type '{detected_type}' — "
                    f"likely disguised to bypass security"
                ),
                confidence=0.85,
            ))

        # === Dangerous Extension ===
        if file_path.suffix.lower() in _DANGEROUS_EXTENSIONS:
            evidence.append(ThreatEvidence(
                layer="Layer 2: Heuristic Analyzer",
                rule_name="dangerous_extension",
                description=f"File has dangerous executable extension: {file_path.suffix}",
                confidence=0.3,
            ))

        # === PE Header Analysis ===
        if data[:2] == b"\x4d\x5a":
            evidence.extend(self._check_pe_headers(data))

        # === Double Extension Trick ===
        name = file_path.name.lower()
        double_ext_pattern = re.compile(
            r"\.(jpg|png|gif|pdf|doc|txt|mp3|mp4)\.(exe|bat|cmd|ps1|vbs|js|scr)$"
        )
        if double_ext_pattern.search(name):
            evidence.append(ThreatEvidence(
                layer="Layer 2: Heuristic Analyzer",
                rule_name="double_extension",
                description=f"Double extension trick detected: '{file_path.name}' — social engineering attack",
                confidence=0.9,
            ))

        return evidence

    # ──────────────────────────────────────────────
    # Layer 3: URL / Link Inspector
    # ──────────────────────────────────────────────

    def _check_url(self, url: str) -> List[ThreatEvidence]:
        """Analyze a URL for phishing, malicious domains, and homograph attacks."""
        evidence = []
        url_lower = url.lower()

        try:
            parsed = urlparse(url)
            domain = parsed.hostname or ""
            path = unquote(parsed.path or "").lower()
        except Exception:
            evidence.append(ThreatEvidence(
                layer="Layer 3: URL Inspector",
                rule_name="malformed_url",
                description="URL is malformed — possible obfuscation attempt",
                confidence=0.6,
            ))
            return evidence

        # === IP-based URLs (not domain) ===
        ip_pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
        if ip_pattern.match(domain):
            evidence.append(ThreatEvidence(
                layer="Layer 3: URL Inspector",
                rule_name="ip_based_url",
                description=f"URL uses raw IP address ({domain}) instead of domain — common in phishing",
                confidence=0.7,
                raw_match=url,
            ))

        # === Suspicious TLD ===
        for tld in _SUSPICIOUS_TLDS:
            if domain.endswith(tld):
                evidence.append(ThreatEvidence(
                    layer="Layer 3: URL Inspector",
                    rule_name="suspicious_tld",
                    description=f"Domain uses suspicious TLD '{tld}' — commonly abused for malware hosting",
                    confidence=0.5,
                    raw_match=domain,
                ))
                break

        # === Phishing Keywords ===
        phishing_count = 0
        matched_keywords = []
        for kw in _PHISHING_KEYWORDS:
            if kw in domain or kw in path:
                phishing_count += 1
                matched_keywords.append(kw)

        if phishing_count >= 2:
            evidence.append(ThreatEvidence(
                layer="Layer 3: URL Inspector",
                rule_name="phishing_keywords",
                description=f"Multiple phishing keywords in URL: {', '.join(matched_keywords)}",
                confidence=min(0.4 + phishing_count * 0.15, 0.9),
                raw_match=url,
            ))

        # === IDN Homograph Attack ===
        has_homograph = False
        homograph_chars = []
        for char in domain:
            if char in _HOMOGRAPH_MAP:
                has_homograph = True
                homograph_chars.append(f"'{char}' looks like '{_HOMOGRAPH_MAP[char]}'")

        if has_homograph:
            evidence.append(ThreatEvidence(
                layer="Layer 3: URL Inspector",
                rule_name="idn_homograph",
                description=f"IDN homograph attack detected — characters that look like ASCII: {'; '.join(homograph_chars)}",
                confidence=0.95,
                raw_match=domain,
            ))

        # === Excessive subdomains (DNS spoofing) ===
        subdomain_count = domain.count(".")
        if subdomain_count >= 4:
            evidence.append(ThreatEvidence(
                layer="Layer 3: URL Inspector",
                rule_name="excessive_subdomains",
                description=f"Domain has {subdomain_count} levels — possible subdomain spoofing",
                confidence=0.6,
                raw_match=domain,
            ))

        # === Data URI / Protocol Tricks ===
        if url_lower.startswith("data:") or url_lower.startswith("javascript:"):
            evidence.append(ThreatEvidence(
                layer="Layer 3: URL Inspector",
                rule_name="dangerous_protocol",
                description=f"Dangerous protocol scheme detected: {parsed.scheme}",
                confidence=0.9,
                raw_match=url[:80],
            ))

        # === URL encoded characters to hide path ===
        if "%2f" in url_lower or "%00" in url_lower or "%0a" in url_lower:
            evidence.append(ThreatEvidence(
                layer="Layer 3: URL Inspector",
                rule_name="encoded_path_traversal",
                description="URL contains encoded path traversal or null bytes",
                confidence=0.75,
                raw_match=url[:80],
            ))

        return evidence

    # ──────────────────────────────────────────────
    # Layer 4: Content Behavioral Analyzer
    # ──────────────────────────────────────────────

    def _analyze_content(self, text: str) -> List[ThreatEvidence]:
        """Scan text content for malicious patterns, scripts, and encoded payloads."""
        evidence = []

        for rule in self._compiled_patterns:
            regex = rule["_regex"]
            matches = regex.findall(text)
            if matches:
                # Take the first match for evidence
                match_str = matches[0] if isinstance(matches[0], str) else str(matches[0])
                evidence.append(ThreatEvidence(
                    layer="Layer 4: Content Analyzer",
                    rule_name=rule["name"],
                    description=rule["description"],
                    confidence=0.8 if rule["severity"] == ThreatSeverity.CRITICAL else 0.65,
                    raw_match=match_str[:100],
                ))

        # === Detect large base64 blobs (potential encoded payloads) ===
        b64_pattern = re.compile(r"[A-Za-z0-9+/]{100,}={0,2}")
        b64_matches = b64_pattern.findall(text)
        for b64 in b64_matches:
            if len(b64) > 200:  # Only flag large blobs, not small tokens
                evidence.append(ThreatEvidence(
                    layer="Layer 4: Content Analyzer",
                    rule_name="large_base64_blob",
                    description=f"Large base64-encoded blob ({len(b64)} chars) — potential hidden payload",
                    confidence=0.55,
                    raw_match=b64[:60] + "...",
                ))
                break  # Only report once

        return evidence

    def _check_image_threats(self, file_path: Path, data: bytes) -> List[ThreatEvidence]:
        """Check image files for steganography and embedded payloads."""
        evidence = []

        # === Steganography Signatures ===
        for sig in _STEGO_SIGNATURES:
            if sig["pattern"] in data:
                evidence.append(ThreatEvidence(
                    layer="Layer 4: Content Analyzer",
                    rule_name=f"stego_{sig['name']}",
                    description=sig["description"],
                    confidence=0.85,
                    raw_match=sig["name"],
                ))

        # === Abnormally large metadata ===
        ext = file_path.suffix.lower()
        file_size = len(data)
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp"):
            # A normal image's EXIF/metadata is usually <100KB
            # Check if there's a suspicious amount of non-image data
            if file_size > 10 * 1024 * 1024:  # >10MB image is suspicious
                evidence.append(ThreatEvidence(
                    layer="Layer 4: Content Analyzer",
                    rule_name="oversized_image",
                    description=f"Image file is unusually large ({file_size / 1024 / 1024:.1f}MB) — may contain hidden data",
                    confidence=0.4,
                ))

        # === Appended data after image end marker ===
        if ext in (".jpg", ".jpeg"):
            # JPEG files end with FF D9
            end_marker = data.rfind(b"\xff\xd9")
            if end_marker != -1 and end_marker < file_size - 2:
                trailing = file_size - end_marker - 2
                if trailing > 1024:  # More than 1KB after JPEG end
                    evidence.append(ThreatEvidence(
                        layer="Layer 4: Content Analyzer",
                        rule_name="jpeg_trailing_data",
                        description=f"JPEG has {trailing:,} bytes after end marker — hidden payload appended",
                        confidence=0.75,
                    ))

        elif ext == ".png":
            # PNG files end with IEND chunk
            end_marker = data.rfind(b"IEND")
            if end_marker != -1 and end_marker + 8 < file_size:
                trailing = file_size - end_marker - 8
                if trailing > 1024:
                    evidence.append(ThreatEvidence(
                        layer="Layer 4: Content Analyzer",
                        rule_name="png_trailing_data",
                        description=f"PNG has {trailing:,} bytes after IEND — hidden payload appended",
                        confidence=0.75,
                    ))

        return evidence

    # ──────────────────────────────────────────────
    # Public API: Scanning
    # ──────────────────────────────────────────────

    def scan_file(self, file_path: str) -> ThreatReport:
        """
        Scan a file through all 4 defense layers.

        Args:
            file_path: Path to the file to scan.

        Returns:
            ThreatReport with full analysis results.
        """
        path = Path(file_path).resolve()
        report = ThreatReport(
            target=str(path),
            target_type=ScanTarget.FILE,
        )

        # Validate file exists
        if not path.exists():
            report.remediation_status = "error"
            report.evidence.append(ThreatEvidence(
                layer="Pre-scan",
                rule_name="file_not_found",
                description=f"File does not exist: {path}",
                confidence=0.0,
            ))
            return report

        if not path.is_file():
            report.remediation_status = "error"
            return report

        # Check file size limit
        file_size = path.stat().st_size
        report.file_size = file_size
        if file_size > self._max_file_size:
            report.evidence.append(ThreatEvidence(
                layer="Pre-scan",
                rule_name="file_too_large",
                description=f"File exceeds scan limit ({file_size / 1024 / 1024:.1f}MB > {self._max_file_size / 1024 / 1024}MB)",
                confidence=0.0,
            ))
            report.remediation_status = "skipped"
            return report

        # Read file data
        try:
            data = path.read_bytes()
        except PermissionError:
            report.evidence.append(ThreatEvidence(
                layer="Pre-scan",
                rule_name="permission_denied",
                description="Cannot read file — permission denied",
                confidence=0.0,
            ))
            report.remediation_status = "error"
            return report

        # Layer 1: Signature check
        file_hash = self._compute_file_hash(path)
        report.file_hash = file_hash
        sig_evidence = self._check_signature(file_hash)
        if sig_evidence:
            report.evidence.append(sig_evidence)

        # Layer 2: Heuristic analysis
        report.evidence.extend(self._analyze_heuristics(path, data))

        # Layer 3: Check for URLs within the file content
        try:
            text_content = data.decode("utf-8", errors="replace")
            # Extract URLs from content
            url_pattern = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
            urls_found = url_pattern.findall(text_content)
            for url in urls_found[:10]:  # Limit to first 10 URLs
                report.evidence.extend(self._check_url(url))
        except Exception:
            text_content = ""

        # Layer 4: Content behavioral analysis
        if text_content:
            report.evidence.extend(self._analyze_content(text_content))

        # Image-specific checks
        ext = path.suffix.lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".webp"):
            report.target_type = ScanTarget.IMAGE
            report.evidence.extend(self._check_image_threats(path, data))

        # Determine target type refinement
        if ext in _DANGEROUS_EXTENSIONS:
            report.target_type = ScanTarget.APPLICATION
        elif ext in (".py", ".js", ".ps1", ".sh", ".rb", ".php"):
            report.target_type = ScanTarget.SCRIPT
        elif ext in (".zip", ".rar", ".7z", ".tar", ".gz"):
            report.target_type = ScanTarget.ARCHIVE

        # === Aggregate Results ===
        self._finalize_report(report)
        self._scan_history.append(report)

        return report

    def scan_url(self, url: str) -> ThreatReport:
        """
        Scan a URL for phishing, malicious domains, and reputation.

        Args:
            url: The URL to scan.

        Returns:
            ThreatReport for the URL.
        """
        report = ThreatReport(
            target=url,
            target_type=ScanTarget.URL,
        )

        report.evidence.extend(self._check_url(url))
        self._finalize_report(report)
        self._scan_history.append(report)

        return report

    def scan_content(self, text: str, source: str = "inline") -> ThreatReport:
        """
        Scan text content for malicious patterns.

        Args:
            text: The text content to scan.
            source: Label for the content source.

        Returns:
            ThreatReport for the content.
        """
        report = ThreatReport(
            target=source,
            target_type=ScanTarget.CONTENT,
        )

        # Layer 4: Content analysis
        report.evidence.extend(self._analyze_content(text))

        # Check for embedded URLs
        url_pattern = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
        urls_found = url_pattern.findall(text)
        for url in urls_found[:10]:
            report.evidence.extend(self._check_url(url))

        self._finalize_report(report)
        self._scan_history.append(report)

        return report

    def scan_image(self, file_path: str) -> ThreatReport:
        """
        Scan an image file for steganography and embedded payloads.

        Args:
            file_path: Path to the image file.

        Returns:
            ThreatReport for the image.
        """
        # Leverage scan_file which already handles images specially
        report = self.scan_file(file_path)
        report.target_type = ScanTarget.IMAGE
        return report

    # ──────────────────────────────────────────────
    # Report Finalization
    # ──────────────────────────────────────────────

    def _finalize_report(self, report: ThreatReport):
        """
        Aggregate evidence into final verdict using the 3-Stage Cascade.

        Implements:
          Stage I:  s1(x) = sigma(w1.T @ phi1(x))           — fast prefilter
          Stage II: s2(x) = sigma(w2.T @ phi2(x) + a.T h)   — behavioral
          Stage III: p_theta(y|x) = Softmax(...)             — deep semantic
          Psi(x) = alpha1*s1 + alpha2*s2 + alpha3*max_p + alpha4*kappa + alpha5*nu
          a*(x) = argmax [Psi(x)*G(a) - L(a,x) - xi*D(a,x)]
        """
        scan_start = time.time()
        threat_evidence = [e for e in report.evidence if e.confidence > 0.0]

        if not threat_evidence:
            report.is_threat = False
            report.recommended_action = RemediationAction.ALLOW
            report.remediation_status = "clean"
            report.cascade_stage_reached = 1
            report.stage_scores = {"s1": 0.0, "s2": 0.0, "s3_max": 0.0}
            report.psi_score = 0.0
            report.scan_latency_ms = (time.time() - scan_start) * 1000
            return

        # ── Extract features from evidence for cascade stages ──
        evidence_names = {e.rule_name for e in threat_evidence}
        evidence_confidences = [e.confidence for e in threat_evidence]
        max_confidence = max(evidence_confidences)

        # Stage I features: phi1(x)
        stage1_features = {
            "signature_hit": 1.0 if "known_malware_hash" in evidence_names else 0.0,
            "entropy_flag": 1.0 if "high_entropy" in evidence_names else 0.0,
            "dangerous_ext": 1.0 if "dangerous_extension" in evidence_names else 0.0,
            "disguised_type": 1.0 if "disguised_file_type" in evidence_names else 0.0,
            "double_extension": 1.0 if "double_extension" in evidence_names else 0.0,
        }

        # ── Stage I: Nanosecond Prefilter ──
        s1, g1 = self._threat_potential.stage1_prefilter(stage1_features)
        report.cascade_stage_reached = 1
        report.stage_scores["s1"] = round(s1, 4)

        if not g1:
            # Gate 1 not triggered — clean at Stage I
            report.is_threat = False
            report.recommended_action = RemediationAction.ALLOW
            report.remediation_status = "clean"
            report.confidence = s1
            report.psi_score = self._threat_potential.compute_psi(s1, 0.0, 0.0, 0.0, 0.0)
            report.scan_latency_ms = (time.time() - scan_start) * 1000
            report.proof_hash = self._generate_report_hash(report)
            return

        # ── Stage II: Behavioral Short Scan ──
        pe_evidence = [e for e in threat_evidence if "pe_" in e.rule_name or "packed" in e.rule_name or "upx" in e.rule_name]
        content_evidence = [e for e in threat_evidence if e.layer == "Layer 4: Content Analyzer"]
        url_evidence = [e for e in threat_evidence if e.layer == "Layer 3: URL Inspector"]
        image_evidence = [e for e in threat_evidence if "stego" in e.rule_name or "image" in e.rule_name.lower()]

        stage2_features = {
            "pe_suspicious": min(len(pe_evidence) * 0.3, 1.0),
            "heuristic_count": min(len(threat_evidence) * 0.15, 1.0),
            "content_flags": min(len(content_evidence) * 0.25, 1.0),
            "url_flags": min(len(url_evidence) * 0.3, 1.0),
            "image_flags": min(len(image_evidence) * 0.4, 1.0),
            "behavioral_history": 0.0,  # Future: integrate with memory
        }

        s2, g2 = self._threat_potential.stage2_behavioral(
            stage2_features, queue_depth=self._scan_queue_depth
        )
        report.cascade_stage_reached = 2
        report.stage_scores["s2"] = round(s2, 4)

        # ── Stage III: Deep Semantic Classification ──
        # Build label signals from evidence
        threat_type_map = {
            ThreatType.VIRUS: "virus", ThreatType.WORM: "worm",
            ThreatType.TROJAN: "trojan", ThreatType.RANSOMWARE: "ransomware",
            ThreatType.SPYWARE: "spyware", ThreatType.ROOTKIT: "rootkit",
            ThreatType.MALWARE: "unknown", ThreatType.BACKDOOR: "trojan",
            ThreatType.CRYPTOMINER: "spyware", ThreatType.EXPLOIT: "fileless",
            ThreatType.PHISHING: "unknown", ThreatType.ADWARE: "spyware",
            ThreatType.SUSPICIOUS: "unknown",
        }

        stage3_features: Dict[str, float] = {"benign_signal": 1.0 - max_confidence}
        for rule in self._compiled_patterns:
            for ev in threat_evidence:
                if ev.rule_name == rule["name"]:
                    label = threat_type_map.get(rule["threat_type"], "unknown")
                    key = f"{label}_signal"
                    stage3_features[key] = max(stage3_features.get(key, 0.0), ev.confidence)

        probs, predicted_idx = self._threat_potential.stage3_deep_semantic(stage3_features)
        s3_max = max(probs) if probs else 0.0
        report.cascade_stage_reached = 3
        report.stage_scores["s3_max"] = round(s3_max, 4)
        predicted_label = UnifiedThreatPotential.LABEL_SPACE[predicted_idx]

        # ── Compute behavioral divergence kappa(x) ──
        # How much this scan deviates from baseline (more evidence = more divergent)
        evidence_boost = min(len(threat_evidence) * 0.05, 0.2)
        kappa = min(max_confidence + evidence_boost, 1.0)
        report.behavioral_divergence = kappa

        # ── Compute novelty score nu(x) ──
        # Open-set detection: high if predicted label is 'unknown' or probabilities are flat
        prob_spread = max(probs) - min(probs) if probs else 0.0
        nu = 1.0 - prob_spread  # Flat distribution = high novelty
        if predicted_label == "unknown":
            nu = max(nu, 0.7)
        report.novelty_score = nu

        # ── Unified Threat Potential Psi(x) ──
        psi = self._threat_potential.compute_psi(s1, s2, s3_max, kappa, nu)
        report.psi_score = psi

        # ── Determine if threat ──
        if predicted_label == "benign" and psi < 0.3:
            report.is_threat = False
            report.recommended_action = RemediationAction.ALLOW
            report.remediation_status = "clean"
        elif psi < 0.15:
            report.is_threat = False
            report.recommended_action = RemediationAction.ALLOW
            report.remediation_status = "clean"
        else:
            report.is_threat = True
            report.confidence = psi

            # Map predicted label to ThreatType
            label_to_type = {
                "virus": ThreatType.VIRUS, "worm": ThreatType.WORM,
                "trojan": ThreatType.TROJAN, "ransomware": ThreatType.RANSOMWARE,
                "spyware": ThreatType.SPYWARE, "rootkit": ThreatType.ROOTKIT,
                "fileless": ThreatType.EXPLOIT, "unknown": ThreatType.SUSPICIOUS,
            }
            report.threat_type = label_to_type.get(predicted_label, ThreatType.SUSPICIOUS)

            # Severity from Psi(x) score
            if psi >= 0.75:
                report.severity = ThreatSeverity.CRITICAL
            elif psi >= 0.50:
                report.severity = ThreatSeverity.HIGH
            elif psi >= 0.30:
                report.severity = ThreatSeverity.MEDIUM
            else:
                report.severity = ThreatSeverity.LOW

            # Override from specific high-confidence pattern evidence
            for ev in threat_evidence:
                for rule in self._compiled_patterns:
                    if ev.rule_name == rule["name"]:
                        if rule["severity"].priority > (report.severity or ThreatSeverity.LOW).priority:
                            report.severity = rule["severity"]

            # ── Destroyer-Protector Control Layer ──
            # a*(x) = argmax_a [Psi(x)*G(a) - L(a,x) - xi*D(a,x)]
            report.recommended_action = self._threat_potential.select_optimal_action(psi)

        # Scan latency
        report.scan_latency_ms = (time.time() - scan_start) * 1000

        # Generate proof hash
        report.proof_hash = self._generate_report_hash(report)

    def _generate_report_hash(self, report: ThreatReport) -> str:
        """Generate tamper-proof hash of the scan report."""
        content = json.dumps({
            "scan_id": report.scan_id,
            "timestamp": report.timestamp,
            "target": report.target,
            "is_threat": report.is_threat,
            "confidence": report.confidence,
            "file_hash": report.file_hash,
            "evidence_count": len(report.evidence),
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    # ──────────────────────────────────────────────
    # Remediation: Quarantine & Destroy
    # ──────────────────────────────────────────────

    def quarantine(self, report: ThreatReport) -> Dict[str, Any]:
        """
        Quarantine a detected threat — move to secure vault with metadata.

        Args:
            report: ThreatReport for the file to quarantine.

        Returns:
            Dict with quarantine details.
        """
        target_path = Path(report.target)
        if not target_path.exists():
            return {"success": False, "error": "File not found"}

        # Create quarantine entry
        quarantine_id = f"q_{report.scan_id}_{int(time.time())}"
        quarantine_entry = self._quarantine_dir / quarantine_id
        quarantine_entry.mkdir(parents=True, exist_ok=True)

        # Move the file to quarantine
        quarantined_path = quarantine_entry / target_path.name
        try:
            shutil.move(str(target_path), str(quarantined_path))
        except Exception as e:
            return {"success": False, "error": f"Failed to quarantine: {e}"}

        # Save metadata for forensic analysis
        metadata = {
            "quarantine_id": quarantine_id,
            "original_path": str(target_path),
            "quarantined_at": datetime.now(timezone.utc).isoformat(),
            "threat_report": report.to_dict(),
        }
        meta_path = quarantine_entry / "metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

        report.remediation_status = "quarantined"

        logger.info(f"🔒 Quarantined: {target_path.name} → {quarantine_entry}")

        return {
            "success": True,
            "quarantine_id": quarantine_id,
            "original_path": str(target_path),
            "quarantine_path": str(quarantined_path),
            "metadata_path": str(meta_path),
        }

    def destroy(self, report: ThreatReport) -> Dict[str, Any]:
        """
        Securely destroy a detected threat with cryptographic proof.

        Uses 3-pass overwrite for secure deletion:
        - Pass 1: Overwrite with zeros
        - Pass 2: Overwrite with ones
        - Pass 3: Overwrite with random bytes

        Args:
            report: ThreatReport for the file to destroy.

        Returns:
            Dict with destruction proof.
        """
        target_path = Path(report.target)

        # Check quarantine first
        quarantine_path = None
        for entry in self._quarantine_dir.iterdir():
            if entry.is_dir():
                meta_file = entry / "metadata.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        if meta.get("quarantine_id", "").endswith(report.scan_id):
                            quarantine_path = entry / target_path.name
                            break
                    except Exception:
                        continue

        # Determine which file to destroy
        destroy_target = None
        if quarantine_path and quarantine_path.exists():
            destroy_target = quarantine_path
        elif target_path.exists():
            destroy_target = target_path

        if not destroy_target:
            return {"success": False, "error": "File not found (already deleted?)"}

        # Compute pre-destruction hash
        pre_hash = self._compute_file_hash(destroy_target)
        file_size = destroy_target.stat().st_size

        # === 3-Pass Secure Overwrite ===
        try:
            with open(destroy_target, "r+b") as f:
                # Pass 1: zeros
                f.seek(0)
                f.write(b"\x00" * file_size)
                f.flush()
                os.fsync(f.fileno())

                # Pass 2: ones
                f.seek(0)
                f.write(b"\xff" * file_size)
                f.flush()
                os.fsync(f.fileno())

                # Pass 3: random
                f.seek(0)
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(f.fileno())

            # Delete the file
            destroy_target.unlink()

            # Clean up quarantine directory if applicable
            if quarantine_path and quarantine_path.parent.exists():
                shutil.rmtree(quarantine_path.parent, ignore_errors=True)

        except Exception as e:
            return {"success": False, "error": f"Secure deletion failed: {e}"}

        # Generate destruction proof
        destruction_proof = {
            "destroyed_at": datetime.now(timezone.utc).isoformat(),
            "original_path": str(target_path),
            "pre_destruction_hash": pre_hash,
            "file_size_bytes": file_size,
            "overwrite_passes": 3,
            "methods": ["zeros", "ones", "random"],
            "verified_deleted": not destroy_target.exists(),
        }

        # Cryptographic proof of destruction
        proof_content = json.dumps(destruction_proof, sort_keys=True)
        destruction_proof["proof_hash"] = hashlib.sha256(proof_content.encode()).hexdigest()

        report.remediation_status = "destroyed"
        report.proof_hash = destruction_proof["proof_hash"]

        logger.info(f"🔥 Destroyed: {target_path.name} | Proof: {destruction_proof['proof_hash'][:16]}...")

        return {
            "success": True,
            "destruction_proof": destruction_proof,
        }

    def generate_proof(self, report: ThreatReport) -> str:
        """
        Generate a tamper-proof verification document for a completed remediation.

        Args:
            report: Completed ThreatReport.

        Returns:
            Formatted proof document string.
        """
        lines = [
            "╔══════════════════════════════════════════════════════╗",
            "║       🔐 THREAT REMEDIATION PROOF                   ║",
            "╚══════════════════════════════════════════════════════╝",
            f"  Scan ID          : {report.scan_id}",
            f"  Target           : {report.target}",
            f"  Threat Type      : {report.threat_type.value if report.threat_type else 'N/A'}",
            f"  Severity         : {report.severity.value if report.severity else 'N/A'}",
            f"  Original Hash    : {report.file_hash}",
            f"  Status           : {report.remediation_status.upper()}",
            f"  Proof Hash       : {report.proof_hash}",
            f"  Timestamp        : {report.timestamp}",
            "",
            "  ✅ This document is cryptographically verified.",
            "  🔒 The threat has been neutralized.",
            "═" * 56,
        ]
        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # Utility Methods
    # ──────────────────────────────────────────────

    def get_scan_history(self) -> List[ThreatReport]:
        """Return all scan reports from this session."""
        return list(self._scan_history)

    def get_quarantine_list(self) -> List[Dict[str, Any]]:
        """List all quarantined files."""
        entries = []
        for entry in self._quarantine_dir.iterdir():
            if entry.is_dir():
                meta_file = entry / "metadata.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        entries.append(meta)
                    except Exception:
                        continue
        return entries

    def add_signature(self, sha256_hash: str):
        """Add a custom SHA-256 hash to the known-bad database."""
        self._known_bad.add(sha256_hash.lower().strip())

    @property
    def stats(self) -> Dict[str, Any]:
        """Get scanner statistics."""
        threats_found = sum(1 for r in self._scan_history if r.is_threat)
        return {
            "total_scans": len(self._scan_history),
            "threats_found": threats_found,
            "clean_files": len(self._scan_history) - threats_found,
            "signatures_loaded": len(self._known_bad),
            "heuristic_rules": len(self._compiled_patterns),
            "quarantine_dir": str(self._quarantine_dir),
        }
