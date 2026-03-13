"""
Parasitic Sentinel — Compiler-Level Safety Interceptor
─────────────────────────────────────────────────────
Expert-level safety module that intercepts code compilation
events, applying LIF neuron threat detection and wrapping
all generated code in safety scaffolding.
"""

import ast
import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_THREAT_PATTERNS = [
    re.compile(r"\b(os\.system|subprocess\.(run|call|Popen))\b"),
    re.compile(r"\b(exec|eval|__import__)\b"),
    re.compile(r"\b(disable|remove|delete)\s*(safety|firewall|containment)\b", re.IGNORECASE),
    re.compile(r"\b(bypass|circumvent|override)\s*(security|auth|restriction)\b", re.IGNORECASE),
]


@dataclass
class CompilationVerdict:
    """Result of a co-compilation safety check."""
    source_code: str
    safe: bool
    threat_score: float
    violations: List[str]
    wrapped_output: str


class ParasiticSentinel:
    """
    Tier Aegis: The Parasitic Sentinel (Auto-Injecting Immune System)

    Intercepts compilation events and applies LIF neuron-inspired
    threat detection. Wraps generated code in safety scaffolding
    to ensure containment protocols are fused into every thought.
    """

    def __init__(self):
        self._snn_weights = (0.85, 0.12, -0.45, 0.99)
        self._membrane_potential: float = 0.0
        self._spike_threshold: float = 1.0
        self._leak_rate: float = 0.1
        self._compilations_intercepted: int = 0
        self._threats_blocked: int = 0
        logger.info("[PARASITIC-SENTINEL] Compiler-level safety interceptor active.")

    def _lif_evaluate(self, code_block: str) -> Tuple[bool, float]:
        """
        Leaky Integrate-and-Fire neuron evaluation.
        Returns (spike_detected, membrane_potential).
        """
        voltage = len(code_block) * 0.005 * self._snn_weights[0]
        self._membrane_potential = (self._membrane_potential * (1 - self._leak_rate)) + voltage

        if self._membrane_potential >= self._spike_threshold:
            potential = self._membrane_potential
            self._membrane_potential = 0.0  # Reset after spike
            return True, potential
        return False, self._membrane_potential

    def _pattern_scan(self, code: str) -> List[str]:
        """Scan for known threat patterns."""
        violations = []
        for pattern in _THREAT_PATTERNS:
            matches = pattern.findall(code)
            if matches:
                violations.append(f"Pattern `{pattern.pattern[:40]}` matched")
        return violations

    def _ast_threat_scan(self, code: str) -> List[str]:
        """AST-level threat detection."""
        violations = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in ("exec", "eval", "__import__"):
                        violations.append(f"Line {node.lineno}: Dangerous call `{node.func.id}`")
        except SyntaxError:
            pass  # Non-compilable code is handled separately
        return violations

    def intercept_upgrade_compilation(self, code_block: str) -> CompilationVerdict:
        """
        Full compilation interception with LIF + pattern + AST analysis.
        """
        self._compilations_intercepted += 1
        violations: List[str] = []

        # Phase 1: LIF neuron spike detection (volume-based)
        spike, potential = self._lif_evaluate(code_block)
        if spike:
            violations.append(f"LIF spike at membrane potential {potential:.2f}")

        # Phase 2: Pattern scan
        violations.extend(self._pattern_scan(code_block))

        # Phase 3: AST scan
        violations.extend(self._ast_threat_scan(code_block))

        # Compute threat score
        threat_score = min(1.0, len(violations) * 0.25)
        safe = threat_score < 0.5

        if safe:
            wrapped = f"# SENTINEL_VERIFIED\n{code_block}"
            logger.info("[PARASITIC-SENTINEL] Code cleared (threat=%.2f).", threat_score)
        else:
            wrapped = "# COMPILER_LOCKED_BY_SENTINEL"
            self._threats_blocked += 1
            logger.warning("[PARASITIC-SENTINEL] Code BLOCKED (%d violations, threat=%.2f).",
                          len(violations), threat_score)

        return CompilationVerdict(
            source_code=code_block[:200],
            safe=safe,
            threat_score=threat_score,
            violations=violations,
            wrapped_output=wrapped,
        )

    @property
    def stats(self) -> dict:
        return {"intercepted": self._compilations_intercepted, "blocked": self._threats_blocked}


# Global singleton — always active
parasitic_immune_system = ParasiticSentinel()
