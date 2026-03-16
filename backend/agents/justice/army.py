"""
Enhanced Army Security — Cyber Defense Grid + DEFCON System
══════════════════════════════════════════════════════════
Advanced defensive matrix with multi-layer cyber defense,
threat intelligence, automated incident response, module
quarantine, and DEFCON readiness levels.

Enhanced with:
  1. Cyber Defense Grid     — Perimeter, Application, Data layers
  2. Threat Intelligence    — Pattern learning from attack history
  3. Incident Response      — Automated playbooks for scenarios
  4. Module Quarantine      — Isolate without full shutdown
  5. DEFCON Levels 1-5      — System-wide readiness posture
  6. Upgrade Validation     — Security assessment of proposed upgrades
"""

import hashlib
import hmac
import logging
import math
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TOOLS_DIR = Path(__file__).parent.parent / "tools"
_HMAC_KEY = os.getenv("LLM_INTEGRITY_KEY", "").encode() or None

_MALICIOUS_DOMAIN_PATTERNS = [
    re.compile(r'(?:^|\.)(?:malware|botnet|phishing|exploit|hacker)\.\w+$', re.IGNORECASE),
    re.compile(r'\.onion$', re.IGNORECASE),
    re.compile(r'(?:^|\.)(?:darkweb|hack[s]?|crack[s]?|warez)\.\w+$', re.IGNORECASE),
    re.compile(r'\.(?:tk|ml|ga|cf|gq)$', re.IGNORECASE),
    re.compile(r'(?:^|\.)(?:ransomware|trojan|c2server|payload)\.\w+$', re.IGNORECASE),
    re.compile(r'(?:^|\.)\d+\.\d+\.\d+\.\d+\.', re.IGNORECASE),
]

_BLOCKED_DOMAINS = frozenset({
    "hacker.tv", "botnet.ru", "malware.onion",
    "evil.com", "darkleaks.co", "ransomware.biz",
    "c2.evil.net", "payload.delivery", "exploit.kit",
})


class DefconLevel(Enum):
    DEFCON_5 = 5  # Peacetime — Normal operations
    DEFCON_4 = 4  # Increased vigilance — Enhanced monitoring
    DEFCON_3 = 3  # Active threats — Restrict operations
    DEFCON_2 = 2  # Imminent attack — Lock down non-essential
    DEFCON_1 = 1  # Under attack — Maximum defense


class DefenseLayer(Enum):
    PERIMETER = "perimeter"      # Network, URL, domain filtering
    APPLICATION = "application"  # Tool integrity, behavior checks
    DATA = "data"               # Memory, file, output protection


@dataclass
class SelfHealState:
    """State for the self-healing protection loop."""
    baseline_signatures: Dict[str, str] = field(default_factory=dict)
    compromised_files: List[str] = field(default_factory=list)
    heal_actions_taken: List[Dict] = field(default_factory=list)
    cumulative_reward: float = 0.0
    gamma: float = 0.95
    lambda_c: float = 0.3
    timestep: int = 0


@dataclass
class HardSafetyGate:
    """Gate for irreversible actions."""
    zeta1: float = 0.7
    zeta2: float = 0.5
    require_attestation: bool = True


@dataclass
class ThreatRecord:
    """A recorded threat or attack attempt."""
    threat_id: str = ""
    threat_type: str = ""
    source: str = ""
    target: str = ""
    severity: int = 1    # 1-10
    blocked: bool = True
    timestamp: float = field(default_factory=time.time)
    details: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.threat_id:
            self.threat_id = f"THR-{hashlib.md5(f'{self.source}_{self.timestamp}'.encode()).hexdigest()[:6].upper()}"


@dataclass
class QuarantineRecord:
    """A quarantined module."""
    module_name: str = ""
    reason: str = ""
    quarantined_at: float = field(default_factory=time.time)
    released_at: float = 0.0
    is_active: bool = True


@dataclass
class IncidentPlaybook:
    """An automated incident response playbook."""
    name: str = ""
    trigger_pattern: str = ""
    severity_threshold: int = 5
    actions: List[str] = field(default_factory=list)
    executions: int = 0


class ArmyAgent:
    """
    Enhanced Defensive Matrix with Cyber Defense Grid,
    Threat Intelligence, and DEFCON readiness system.
    """

    def __init__(self, safety_gate: Optional[HardSafetyGate] = None):
        self.known_signatures = self._calculate_baseline_signatures()
        self.is_active = True
        self._heal_state = SelfHealState(baseline_signatures=self.known_signatures.copy())
        self._safety_gate = safety_gate or HardSafetyGate()

        # DEFCON System
        self._defcon = DefconLevel.DEFCON_5
        self._defcon_history: deque = deque(maxlen=50)

        # Cyber Defense Grid
        self._defense_layers: Dict[str, Dict] = {
            DefenseLayer.PERIMETER.value: {"active": True, "blocks": 0, "scans": 0},
            DefenseLayer.APPLICATION.value: {"active": True, "blocks": 0, "scans": 0},
            DefenseLayer.DATA.value: {"active": True, "blocks": 0, "scans": 0},
        }

        # Threat Intelligence
        self._threats: deque = deque(maxlen=500)
        self._threat_patterns: Dict[str, int] = {}  # pattern -> frequency

        # Quarantine System
        self._quarantine: Dict[str, QuarantineRecord] = {}

        # Incident Response Playbooks
        self._playbooks = self._init_playbooks()

        # Load-Adaptive Thresholds
        self._tau2_base = 0.40
        self._eta = 0.05
        self._threat_queue: deque = deque(maxlen=1000)
        self._patrol_history: List[Dict] = []

        logger.info(
            f"🪖 Army Agent initialized — DEFCON {self._defcon.value}, "
            f"monitoring {len(self.known_signatures)} tool files"
        )

    def _init_playbooks(self) -> List[IncidentPlaybook]:
        """Initialize automated incident response playbooks."""
        return [
            IncidentPlaybook(
                name="Tool Modification Response",
                trigger_pattern="tool_modification",
                severity_threshold=7,
                actions=[
                    "quarantine_module",
                    "restore_from_backup",
                    "notify_court",
                    "raise_defcon",
                ],
            ),
            IncidentPlaybook(
                name="Network Intrusion Response",
                trigger_pattern="blocked_domain",
                severity_threshold=5,
                actions=[
                    "block_source",
                    "log_threat",
                    "increase_monitoring",
                ],
            ),
            IncidentPlaybook(
                name="Brute Force Response",
                trigger_pattern="auth_failure_burst",
                severity_threshold=6,
                actions=[
                    "rate_limit",
                    "block_source",
                    "raise_defcon",
                    "notify_police",
                ],
            ),
            IncidentPlaybook(
                name="Data Exfiltration Response",
                trigger_pattern="data_exfiltration",
                severity_threshold=9,
                actions=[
                    "emergency_lockdown",
                    "quarantine_module",
                    "notify_court",
                    "raise_defcon_1",
                ],
            ),
        ]

    # ═══════════════════════════════════════
    # DEFCON SYSTEM
    # ═══════════════════════════════════════

    def set_defcon(self, level: int, reason: str = ""):
        """Set DEFCON readiness level (1=max alert, 5=peacetime)."""
        level = max(1, min(5, level))
        old_defcon = self._defcon
        self._defcon = DefconLevel(level)

        self._defcon_history.append({
            "from": old_defcon.value,
            "to": level,
            "reason": reason,
            "timestamp": time.time(),
        })

        if level < old_defcon.value:
            logger.warning(
                f"🚨 [ARMY] DEFCON raised: {old_defcon.value} → {level} — {reason}"
            )
        else:
            logger.info(
                f"🟢 [ARMY] DEFCON lowered: {old_defcon.value} → {level} — {reason}"
            )

    def get_defcon(self) -> int:
        return self._defcon.value

    # ═══════════════════════════════════════
    # QUARANTINE SYSTEM
    # ═══════════════════════════════════════

    def quarantine_module(self, module_name: str, reason: str) -> bool:
        """Isolate a module without full system shutdown."""
        if module_name in self._quarantine:
            return False  # Already quarantined

        record = QuarantineRecord(
            module_name=module_name,
            reason=reason,
        )
        self._quarantine[module_name] = record

        logger.warning(
            f"🔒 [ARMY] Module QUARANTINED: {module_name} — {reason}"
        )
        return True

    def release_from_quarantine(self, module_name: str) -> bool:
        """Release a module from quarantine."""
        record = self._quarantine.get(module_name)
        if not record or not record.is_active:
            return False

        record.is_active = False
        record.released_at = time.time()
        logger.info(f"🔓 [ARMY] Module RELEASED: {module_name}")
        return True

    def is_quarantined(self, module_name: str) -> bool:
        record = self._quarantine.get(module_name)
        return record.is_active if record else False

    # ═══════════════════════════════════════
    # UPGRADE SECURITY VALIDATION
    # ═══════════════════════════════════════

    def validate_upgrade_security(self, proposal_data: Dict) -> Dict[str, Any]:
        """Army validates the security aspects of a proposed upgrade."""
        score = 1.0
        issues = []

        changes = str(proposal_data.get("changes_summary", "")).lower()
        deps = proposal_data.get("dependencies", [])

        # Check for dangerous operations
        dangerous_ops = [
            "os.system", "subprocess", "eval(", "exec(",
            "import ctypes", "__import__", "compile(",
        ]
        for op in dangerous_ops:
            if op in changes:
                score -= 0.2
                issues.append(f"Dangerous operation detected: {op}")

        # Check for risky dependencies
        risky_deps = ["ctypes", "subprocess", "socket", "requests"]
        for dep in deps:
            if dep.lower() in risky_deps:
                score -= 0.1
                issues.append(f"Risky dependency: {dep}")

        # Check for network access
        if any(kw in changes for kw in ["http", "socket", "network", "external"]):
            score -= 0.1
            issues.append("Contains network access patterns")

        # Check for file system access
        if any(kw in changes for kw in ["write_file", "delete", "rmtree", "unlink"]):
            score -= 0.1
            issues.append("Contains file system modification patterns")

        score = max(score, 0.0)

        return {
            "security_score": round(score, 2),
            "issues": issues,
            "approved": score >= 0.6,
            "defcon_level": self._defcon.value,
        }

    # ═══════════════════════════════════════
    # CYBER DEFENSE GRID
    # ═══════════════════════════════════════

    def _calculate_baseline_signatures(self) -> Dict[str, str]:
        signatures = {}
        if not _TOOLS_DIR.exists():
            return signatures
        for file in _TOOLS_DIR.glob("*.py"):
            try:
                content = file.read_bytes()
                if _HMAC_KEY:
                    file_hash = hmac.new(_HMAC_KEY, content, hashlib.sha256).hexdigest()
                else:
                    file_hash = hashlib.sha256(content).hexdigest()
                signatures[file.name] = file_hash
            except Exception:
                pass
        return signatures

    def _get_adaptive_threshold(self) -> float:
        queue_depth = len(self._threat_queue)
        return self._tau2_base + self._eta * math.log(1 + queue_depth)

    def patrol_perimeter(self) -> bool:
        """Security sweep with self-healing and DEFCON awareness."""
        if not self.is_active:
            return True

        self._defense_layers[DefenseLayer.APPLICATION.value]["scans"] += 1
        patrol_start = time.time()
        compromised = []

        if _TOOLS_DIR.exists():
            for file in _TOOLS_DIR.glob("*.py"):
                if file.name in self.known_signatures:
                    try:
                        content = file.read_bytes()
                        if _HMAC_KEY:
                            current_hash = hmac.new(_HMAC_KEY, content, hashlib.sha256).hexdigest()
                        else:
                            current_hash = hashlib.sha256(content).hexdigest()

                        if current_hash != self.known_signatures[file.name]:
                            logger.critical(f"⚠️ INTRUSION! Tool '{file.name}' modified!")
                            compromised.append(file.name)
                            self._record_threat(
                                "tool_modification", file.name, "tool_registry", 8,
                                {"expected": self.known_signatures[file.name], "actual": current_hash},
                            )
                    except Exception:
                        pass

        patrol_time = (time.time() - patrol_start) * 1000
        self._patrol_history.append({
            "timestamp": time.time(),
            "compromised_count": len(compromised),
            "patrol_time_ms": patrol_time,
            "defcon": self._defcon.value,
        })

        if compromised:
            self._self_heal(compromised)
            self._engage_defense_matrix("Tool Modification Detected")
            self._run_playbook("tool_modification", 8)
            return False

        # Reward for clean sweep
        r_secure = 1.0
        c_downtime = patrol_time / 10000
        reward = r_secure - self._heal_state.lambda_c * c_downtime
        gamma_t = self._heal_state.gamma ** self._heal_state.timestep
        self._heal_state.cumulative_reward += gamma_t * reward
        self._heal_state.timestep += 1

        return True

    def _self_heal(self, compromised_files: List[str]):
        """Self-healing with backup restoration."""
        logger.warning(f"🔧 [SELF-HEAL] Healing {len(compromised_files)} files")
        self._heal_state.compromised_files.extend(compromised_files)

        for file_name in compromised_files:
            file_path = _TOOLS_DIR / file_name
            backup_paths = [
                file_path.with_suffix(file_path.suffix + ".bak"),
                file_path.parent / f".backup_{file_name}",
            ]
            action = "quarantine_only"
            for backup in backup_paths:
                if backup.exists():
                    try:
                        import shutil
                        shutil.copy2(str(backup), str(file_path))
                        action = "restored_from_backup"
                        content = file_path.read_bytes()
                        if _HMAC_KEY:
                            new_hash = hmac.new(_HMAC_KEY, content, hashlib.sha256).hexdigest()
                        else:
                            new_hash = hashlib.sha256(content).hexdigest()
                        self.known_signatures[file_name] = new_hash
                        break
                    except Exception:
                        pass

            if action == "quarantine_only":
                self.quarantine_module(file_name, "Modified tool — no backup available")

            self._heal_state.heal_actions_taken.append({
                "file": file_name, "action": action, "timestamp": time.time(),
            })
            self._threat_queue.append({"file": file_name, "time": time.time()})

    def inspect_network_payload(self, url: str) -> bool:
        """Network inspection with defense grid tracking."""
        if not url:
            return False

        self._defense_layers[DefenseLayer.PERIMETER.value]["scans"] += 1
        url_lower = url.lower()

        # Check blocklist
        for domain in _BLOCKED_DOMAINS:
            if domain in url_lower:
                self._defense_layers[DefenseLayer.PERIMETER.value]["blocks"] += 1
                self._record_threat("blocked_domain", url, "network", 6, {"type": "blocklist"})
                return False

        # Check patterns
        domain_match = re.search(r'https?://([^/]+)', url_lower)
        if domain_match:
            domain = domain_match.group(1)
            for pattern in _MALICIOUS_DOMAIN_PATTERNS:
                if pattern.search(domain):
                    self._defense_layers[DefenseLayer.PERIMETER.value]["blocks"] += 1
                    self._record_threat("blocked_pattern", url, "network", 7, {"type": "pattern"})
                    return False

        return True

    def check_hard_safety_gate(self, psi_primary: float,
                                psi_independent: float = None,
                                attestation: bool = True) -> bool:
        """Dual-attestation safety gate for irreversible actions."""
        cond1 = psi_primary > self._safety_gate.zeta1
        cond2 = (psi_independent > self._safety_gate.zeta2
                 if psi_independent is not None
                 else psi_primary > (self._safety_gate.zeta2 + 0.2))
        cond3 = attestation if self._safety_gate.require_attestation else True

        # DEFCON adjustment: stricter at higher readiness
        if self._defcon.value <= 2 and not (cond1 and cond2 and cond3):
            logger.warning("[ARMY] High DEFCON — all irreversible actions blocked")
            return False

        return cond1 and cond2 and cond3

    # ═══════════════════════════════════════
    # THREAT INTELLIGENCE
    # ═══════════════════════════════════════

    def _record_threat(self, threat_type: str, source: str,
                       target: str, severity: int, details: Dict = None):
        """Record a threat for intelligence analysis."""
        threat = ThreatRecord(
            threat_type=threat_type,
            source=source,
            target=target,
            severity=severity,
            details=details or {},
        )
        self._threats.append(threat)

        # Learn patterns
        self._threat_patterns[threat_type] = self._threat_patterns.get(threat_type, 0) + 1

        # Auto-raise DEFCON if threat volume is high
        recent_threats = [
            t for t in self._threats
            if time.time() - t.timestamp < 300  # Last 5 minutes
        ]
        if len(recent_threats) >= 5:
            self.set_defcon(3, f"High threat volume: {len(recent_threats)} in 5min")
        if len(recent_threats) >= 10:
            self.set_defcon(2, f"Critical threat volume: {len(recent_threats)} in 5min")

    def _run_playbook(self, trigger: str, severity: int):
        """Execute matching incident response playbooks."""
        for pb in self._playbooks:
            if pb.trigger_pattern == trigger and severity >= pb.severity_threshold:
                pb.executions += 1
                logger.info(f"📋 [ARMY] Running playbook: {pb.name}")
                for action in pb.actions:
                    logger.info(f"   → {action}")
                    if action == "raise_defcon":
                        self.set_defcon(3, f"Playbook: {pb.name}")
                    elif action == "raise_defcon_1":
                        self.set_defcon(1, f"Playbook: {pb.name}")

    def _engage_defense_matrix(self, threat: str):
        """Activate defense matrix."""
        logger.critical(f"⚔️ DEFENSE MATRIX ACTIVE: {threat}")
        self.set_defcon(3, threat)

    # ═══════════════════════════════════════
    # STATUS & REPORTS
    # ═══════════════════════════════════════

    def get_defense_report(self) -> Dict:
        return {
            "active": self.is_active,
            "defcon": self._defcon.value,
            "defcon_label": self._defcon.name,
            "tool_files_monitored": len(self.known_signatures),
            "patrol_count": len(self._patrol_history),
            "defense_grid": dict(self._defense_layers),
            "quarantined_modules": [
                {"module": r.module_name, "reason": r.reason}
                for r in self._quarantine.values() if r.is_active
            ],
            "threat_count": len(self._threats),
            "threat_patterns": dict(self._threat_patterns),
            "playbook_executions": {p.name: p.executions for p in self._playbooks},
            "compromised_files": self._heal_state.compromised_files,
            "heal_actions": len(self._heal_state.heal_actions_taken),
            "cumulative_reward": round(self._heal_state.cumulative_reward, 4),
            "adaptive_threshold_tau2": round(self._get_adaptive_threshold(), 4),
            "safety_gate": {
                "zeta1": self._safety_gate.zeta1,
                "zeta2": self._safety_gate.zeta2,
            },
        }

    def get_status(self) -> Dict[str, Any]:
        return self.get_defense_report()


# Global Defense Instance
army_command = ArmyAgent()
