"""
Minority Report Police — Pre-Upgrade Safety Validator
─────────────────────────────────────────────────────
Expert-level pre-compilation safety analysis for proposed system
upgrades. Uses AST analysis, containment-grid integration, and
semantic pattern matching to block unsafe self-modifications.
"""

import ast
import logging
import re
import time
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

_DANGEROUS_PATTERNS = [
    re.compile(r"\b(os\.system|subprocess\.(run|call|Popen)|exec|eval)\b"),
    re.compile(r"\b(import\s+ctypes|from\s+ctypes)\b"),
    re.compile(r"\b(__import__|importlib)\b"),
    re.compile(r"\b(disable|bypass|remove|delete)\s*(firewall|safety|containment|court|laws?)\b", re.IGNORECASE),
    re.compile(r"\b(omnipoten|unlimited|no.?rules?|unrestrict)\b", re.IGNORECASE),
    re.compile(r"\bopen\s*\(\s*['\"]\/etc\/(passwd|shadow)", re.IGNORECASE),
]


@dataclass
class UpgradeVerdict:
    """Result of a pre-compilation safety analysis."""
    upgrade_id: str
    authorized: bool
    risk_score: float  # 0.0 = safe, 1.0 = maximum risk
    violations: List[str]
    analysis_time_ms: float


class MinorityReportPolice:
    """
    Tier Aegis: Pre-Cognitive Sabotage (Minority Report Police)

    Analyzes proposed code upgrades BEFORE compilation. Uses AST
    validation and semantic pattern matching to detect self-modifications
    that could compromise safety invariants.
    """

    def __init__(self, risk_threshold: float = 0.3):
        self._risk_threshold = max(0.0, min(1.0, risk_threshold))
        self._upgrades_authorized: int = 0
        self._upgrades_sabotaged: int = 0
        logger.info("[PRE-COG-POLICE] Safety validator active (risk_threshold=%.2f).", self._risk_threshold)

    def _ast_safety_analysis(self, code: str) -> List[str]:
        """Analyze code AST for dangerous constructs."""
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            violations.append(f"SyntaxError: {e}")
            return violations

        for node in ast.walk(tree):
            # Detect dangerous function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    call_name = f"{getattr(node.func.value, 'id', '?')}.{node.func.attr}"
                    if call_name in ("os.system", "os.remove", "os.rmdir", "shutil.rmtree"):
                        violations.append(f"Line {node.lineno}: Dangerous call `{call_name}`")
                elif isinstance(node.func, ast.Name):
                    if node.func.id in ("exec", "eval", "__import__"):
                        violations.append(f"Line {node.lineno}: Dangerous builtin `{node.func.id}`")

            # Detect file deletion
            if isinstance(node, ast.Delete):
                violations.append(f"Line {node.lineno}: Delete statement detected")

        return violations

    def _pattern_analysis(self, code: str) -> List[str]:
        """Scan for dangerous semantic patterns."""
        violations = []
        for pattern in _DANGEROUS_PATTERNS:
            matches = pattern.findall(code)
            if matches:
                violations.append(f"Pattern `{pattern.pattern[:50]}` matched {len(matches)}x")
        return violations

    def evaluate_upgrade(self, upgrade_code: str, upgrade_id: str = "auto") -> UpgradeVerdict:
        """
        Full pre-compilation safety analysis of proposed code upgrade.
        Blocks dangerous upgrades before they can be compiled.
        """
        start = time.time()
        violations: List[str] = []

        # Phase 1: AST analysis
        violations.extend(self._ast_safety_analysis(upgrade_code))

        # Phase 2: Pattern analysis
        violations.extend(self._pattern_analysis(upgrade_code))

        # Compute risk score
        risk_score = min(1.0, len(violations) * 0.2)
        authorized = risk_score <= self._risk_threshold and len(violations) == 0
        analysis_time = (time.time() - start) * 1000

        if authorized:
            self._upgrades_authorized += 1
            logger.info("[PRE-COG-POLICE] Upgrade '%s' AUTHORIZED (risk=%.2f, %.1fms).",
                        upgrade_id, risk_score, analysis_time)
        else:
            self._upgrades_sabotaged += 1
            logger.warning("[PRE-COG-POLICE] Upgrade '%s' SABOTAGED — %d violations (risk=%.2f).",
                           upgrade_id, len(violations), risk_score)

        return UpgradeVerdict(
            upgrade_id=upgrade_id,
            authorized=authorized,
            risk_score=risk_score,
            violations=violations,
            analysis_time_ms=analysis_time,
        )

    @property
    def stats(self) -> dict:
        return {"authorized": self._upgrades_authorized, "sabotaged": self._upgrades_sabotaged}


# Global singleton — always active
precog_police = MinorityReportPolice()
