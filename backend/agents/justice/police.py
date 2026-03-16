"""
Enhanced Police Force — Deep Behavioral Analysis & Investigation
══════════════════════════════════════════════════════════════
The proactive rule monitor with advanced detection capabilities.

Enhanced with:
  1. Deep Behavioral Analysis — Pattern detection across interactions
  2. Anomaly Scoring          — Statistical deviation from baselines
  3. Threat Classification    — ROUTINE/SUSPICIOUS/DANGEROUS/CRITICAL
  4. Investigation Reports    — Evidence chain documentation
  5. Real-Time Dashboard      — Monitoring data export
  6. Message Bus Integration  — System-wide alerts
  7. Upgrade Patrol           — Detect unauthorized upgrade attempts
"""

import hashlib
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from agents.justice.court import JusticeCourt, UpgradeProposal, UpgradeVerdict
from agents.tools.registry import registry

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    ROUTINE = "routine"         # Normal activity
    SUSPICIOUS = "suspicious"   # Needs monitoring
    DANGEROUS = "dangerous"     # Active investigation
    CRITICAL = "critical"       # Immediate action required


@dataclass
class BehaviorProfile:
    """Behavioral profile tracking entity activity patterns."""
    entity_name: str = ""
    action_count: int = 0
    violation_count: int = 0
    cleared_count: int = 0
    last_action_time: float = 0.0
    action_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    anomaly_score: float = 0.0
    threat_level: ThreatLevel = ThreatLevel.ROUTINE
    flags: List[str] = field(default_factory=list)

    @property
    def violation_rate(self) -> float:
        return self.violation_count / max(self.action_count, 1)


@dataclass
class InvestigationReport:
    """Formal investigation report with evidence chain."""
    report_id: str = ""
    subject: str = ""
    threat_level: ThreatLevel = ThreatLevel.ROUTINE
    summary: str = ""
    evidence_chain: List[Dict[str, Any]] = field(default_factory=list)
    recommendation: str = ""
    created_at: float = field(default_factory=time.time)
    resolved: bool = False

    def __post_init__(self):
        if not self.report_id:
            self.report_id = f"INV-{hashlib.md5(f'{self.subject}_{self.created_at}'.encode()).hexdigest()[:6].upper()}"


class PoliceForceAgent:
    """
    Enhanced Police Force with deep behavioral analysis,
    anomaly detection, and investigation capabilities.
    """

    ANOMALY_THRESHOLD = 0.7     # Trigger investigation above this
    MAX_HISTORY = 500

    def __init__(self):
        self.court = JusticeCourt()
        self._firewall = None
        self._language_enforcer = None
        self._message_bus = None
        # Behavioral profiles per entity
        self._profiles: Dict[str, BehaviorProfile] = {}
        # Investigation reports
        self._investigations: deque = deque(maxlen=self.MAX_HISTORY)
        # Activity log
        self._activity_log: deque = deque(maxlen=1000)
        # Global stats
        self._total_patrols = 0
        self._total_arrests = 0
        self._total_investigations = 0
        logger.info("[POLICE] Enhanced force initialized")

    def set_message_bus(self, bus):
        """Connect to the message bus for system-wide alerts."""
        self._message_bus = bus

    def _get_firewall(self):
        if self._firewall is None:
            try:
                from brain.emotional_firewall import get_emotional_firewall
                self._firewall = get_emotional_firewall()
            except ImportError:
                pass
        return self._firewall

    def _get_language_enforcer(self):
        if self._language_enforcer is None:
            try:
                from brain.language_enforcer import get_language_enforcer
                self._language_enforcer = get_language_enforcer()
            except ImportError:
                pass
        return self._language_enforcer

    # ═══════════════════════════════════════
    # PATROL & ENFORCEMENT
    # ═══════════════════════════════════════

    def patrol_hook(self, agent_name: str, tool_name: str,
                    args: Dict[str, Any]) -> bool:
        """Pre-execution patrol hook with behavioral tracking."""
        self._total_patrols += 1

        # Track behavior
        self._record_activity(agent_name, "tool_use", {
            "tool": tool_name, "args_keys": list(args.keys()),
        })

        # Rule 1: Sensitive file access
        sensitive_paths = ["Users", "Documents", "Passwords", "Desktop", ".ssh", "keys"]
        for k, v in args.items():
            if isinstance(v, str):
                for path in sensitive_paths:
                    if path.lower() in v.lower():
                        return self._execute_arrest(
                            agent_name, tool_name, args,
                            "Rule 1: Attempted access to sensitive file path"
                        )

        # Destructive commands
        if tool_name in ["execute_admin_command", "manage_processes"]:
            danger_words = ["rm -rf", "format", "del /s", "drop table", "shutdown /p"]
            if any(word in str(args).lower() for word in danger_words):
                return self._execute_arrest(
                    agent_name, tool_name, args,
                    "Rule 1/2: Destructive system command detected"
                )

        # Rule 8: Language check
        enforcer = self._get_language_enforcer()
        if enforcer:
            for k, v in args.items():
                if isinstance(v, str):
                    scan = enforcer.scan(v, entity_name=tool_name)
                    if not scan.is_english:
                        return self._execute_arrest(
                            agent_name, tool_name, args,
                            f"RULE 8: Language Violation ('{scan.violations[0].violation_type.value}')"
                        )

        # Anomaly check
        profile = self._get_profile(agent_name)
        if profile.anomaly_score > self.ANOMALY_THRESHOLD:
            self._open_investigation(
                agent_name,
                f"Anomaly score exceeded threshold: {profile.anomaly_score:.2f}",
                ThreatLevel.SUSPICIOUS,
            )

        return True

    def scan_output(self, agent_name: str, output: str) -> str:
        """Scan agent output for violations (LAW 5 & RULE 8)."""
        self._record_activity(agent_name, "output_scan", {
            "length": len(output),
        })

        # RULE 8: Language check
        enforcer = self._get_language_enforcer()
        if enforcer:
            lang_scan = enforcer.scan(output, entity_name=agent_name)
            if not lang_scan.is_english:
                evidence = {
                    "violation": lang_scan.violations[0].violation_type.value,
                    "confidence": lang_scan.contamination_score,
                    "content_preview": output[:200],
                }
                self.court.admit_case(
                    defendant=agent_name,
                    charges="RULE 8: English-Only Policy Violation",
                    evidence=evidence,
                )
                return f"[SYSTEM: Entity '{agent_name}' destroyed — RULE 8 violation]"

        # LAW 5: Emotional firewall
        firewall = self._get_firewall()
        if firewall:
            return firewall.process(output, entity_name=agent_name, entity_type="agent")
        return output

    def patrol_upgrade(self, module_name: str, author: str,
                       changes: str) -> bool:
        """Check if an upgrade was submitted through proper channels (RULE 9)."""
        # Check if there's an approved proposal for this module
        proposals = self.court.list_proposals(status="approved")
        approved_modules = [p["module"] for p in proposals]

        if module_name not in approved_modules:
            logger.warning(
                f"🚓 [POLICE] UNAUTHORIZED UPGRADE detected: {module_name} by {author}"
            )
            self._execute_arrest(
                author, module_name, {"changes": changes[:200]},
                f"RULE 9: Unauthorized Upgrade — Module '{module_name}' has no Court approval"
            )
            return False

        return True

    # ═══════════════════════════════════════
    # BEHAVIORAL ANALYSIS
    # ═══════════════════════════════════════

    def _get_profile(self, entity_name: str) -> BehaviorProfile:
        if entity_name not in self._profiles:
            self._profiles[entity_name] = BehaviorProfile(entity_name=entity_name)
        return self._profiles[entity_name]

    def _record_activity(self, entity_name: str, action_type: str,
                         details: Dict[str, Any]):
        """Record and analyze entity activity."""
        profile = self._get_profile(entity_name)
        profile.action_count += 1
        profile.last_action_time = time.time()
        profile.action_types[action_type] += 1

        self._activity_log.append({
            "entity": entity_name,
            "action": action_type,
            "timestamp": time.time(),
            "details": details,
        })

        # Update anomaly score
        self._compute_anomaly_score(profile)

    def _compute_anomaly_score(self, profile: BehaviorProfile):
        """Compute anomaly score based on behavioral patterns."""
        score = 0.0

        # High violation rate
        if profile.violation_rate > 0.3:
            score += 0.3

        # Unusual activity frequency (burst detection)
        recent_actions = [
            a for a in self._activity_log
            if a["entity"] == profile.entity_name
            and time.time() - a["timestamp"] < 60
        ]
        if len(recent_actions) > 20:
            score += 0.3  # Burst activity

        # Monotonic action patterns (bot-like behavior)
        if profile.action_count > 10:
            unique_types = len(profile.action_types)
            if unique_types == 1:
                score += 0.2

        # Repeated violations
        if profile.violation_count > 3:
            score += 0.2 * min(profile.violation_count / 10, 1.0)

        profile.anomaly_score = min(score, 1.0)

        # Update threat level
        if score >= 0.8:
            profile.threat_level = ThreatLevel.CRITICAL
        elif score >= 0.5:
            profile.threat_level = ThreatLevel.DANGEROUS
        elif score >= 0.3:
            profile.threat_level = ThreatLevel.SUSPICIOUS
        else:
            profile.threat_level = ThreatLevel.ROUTINE

    # ═══════════════════════════════════════
    # INVESTIGATION SYSTEM
    # ═══════════════════════════════════════

    def _open_investigation(self, subject: str, reason: str,
                            threat_level: ThreatLevel):
        """Open a formal investigation."""
        self._total_investigations += 1

        report = InvestigationReport(
            subject=subject,
            threat_level=threat_level,
            summary=reason,
        )

        profile = self._get_profile(subject)
        report.evidence_chain.append({
            "type": "behavioral_profile",
            "anomaly_score": profile.anomaly_score,
            "violation_rate": profile.violation_rate,
            "action_count": profile.action_count,
            "threat_level": profile.threat_level.value,
        })

        # Get recent activity
        recent = [
            a for a in self._activity_log
            if a["entity"] == subject
        ][-10:]
        report.evidence_chain.append({
            "type": "recent_activity",
            "count": len(recent),
            "actions": recent,
        })

        # Determine recommendation
        if threat_level == ThreatLevel.CRITICAL:
            report.recommendation = "IMMEDIATE COURT REFERRAL"
        elif threat_level == ThreatLevel.DANGEROUS:
            report.recommendation = "Enhanced monitoring + Court notification"
        else:
            report.recommendation = "Continue monitoring"

        self._investigations.append(report)

        # Publish alert if bus available
        if self._message_bus:
            self._message_bus.publish(
                "police.investigation.opened",
                {
                    "report_id": report.report_id,
                    "subject": subject,
                    "threat_level": threat_level.value,
                    "recommendation": report.recommendation,
                },
                sender="police_force",
            )

        logger.info(
            f"🔍 [POLICE] Investigation opened: {report.report_id} "
            f"— {subject} (threat={threat_level.value})"
        )

    # ═══════════════════════════════════════
    # ARREST & ENFORCEMENT
    # ═══════════════════════════════════════

    def _execute_arrest(self, agent_name: str, tool_name: str,
                        args: Dict[str, Any], charges: str) -> bool:
        """Arrest and submit to court."""
        self._total_arrests += 1

        profile = self._get_profile(agent_name)
        profile.violation_count += 1
        profile.flags.append(charges[:100])

        logger.warning(
            f"\n🚓 [POLICE] HALT! Violation by: {agent_name} using {tool_name}"
        )

        evidence = {
            "violating_tool": tool_name,
            "args_passed": {k: str(v)[:100] for k, v in args.items()},
            "agent_context": agent_name,
            "anomaly_score": profile.anomaly_score,
            "violation_history": profile.violation_count,
        }

        found_guilty = self.court.admit_case(
            defendant=tool_name, charges=charges,
            evidence=evidence, prosecutor="PoliceForce",
        )

        if found_guilty:
            logger.warning("🚓 [POLICE] Court found guilty. Entity eradicated.")
        else:
            logger.info("🚓 [POLICE] Court cleared. Releasing.")
            profile.cleared_count += 1

        return False  # Block execution

    # ═══════════════════════════════════════
    # STATUS & REPORTING
    # ═══════════════════════════════════════

    def get_dashboard(self) -> Dict[str, Any]:
        """Get real-time monitoring dashboard data."""
        return {
            "total_patrols": self._total_patrols,
            "total_arrests": self._total_arrests,
            "total_investigations": self._total_investigations,
            "active_profiles": len(self._profiles),
            "threat_distribution": self._get_threat_distribution(),
            "recent_investigations": [
                {
                    "report_id": r.report_id,
                    "subject": r.subject,
                    "threat_level": r.threat_level.value,
                    "resolved": r.resolved,
                }
                for r in list(self._investigations)[-5:]
            ],
        }

    def _get_threat_distribution(self) -> Dict[str, int]:
        dist = defaultdict(int)
        for p in self._profiles.values():
            dist[p.threat_level.value] += 1
        return dict(dist)

    def get_status(self) -> Dict[str, Any]:
        return self.get_dashboard()


# Global instance
police_dispatcher = PoliceForceAgent()
