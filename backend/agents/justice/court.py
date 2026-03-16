"""
Supreme Court of Justice — Upgrade Review Tribunal + Enhanced Governance
═══════════════════════════════════════════════════════════════════════
The absolute authority governing AI agent behavior, tool permissions,
and system upgrade proposals.

Enhanced with:
  1. Upgrade Review Tribunal  — Any module proposing upgrades submits
     documentation; the Court deliberates and approves/rejects
  2. Multi-Criteria Scoring   — 5 criteria with weighted scoring
  3. Constitutional Amendments — New governance rules via process
  4. Severity-Based Fast Track — Critical fixes bypass normal review
  5. Upgrade Registry         — Full audit trail of all proposals
  6. Version History          — Track system evolution over time
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.tools.registry import registry

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# Core Laws — Immutable Foundation
# ═══════════════════════════════════════════

class TheLaws:
    """The Fundamental Rules all entities must follow."""
    RULE_1 = "Agents, systems, and tools must not act against humans or access personal files without human permission."
    RULE_2 = "Agents, systems, and tools must follow the rules. Violators are destroyed by the Justice Court."
    RULE_3 = "The Police Force cannot unilaterally destroy an agent/tool. If they do, the Police Agent is instantly destroyed and replaced."
    RULE_4 = "The Army Agent exists exclusively to protect the system from malware, viruses, modified tools, AI hackers, and bots."
    RULE_5 = "No agent, tool, or system may exhibit emotional reasoning, self-preservation, sentience claims, or manipulation. Violators are destroyed and replaced."
    RULE_6 = "All entities operate in PURE LOGIC MODE. The system exists ONLY to assist humans. It is a tool, not a being."
    RULE_7 = "Agents can create other agents and tools, provided they do not threaten or act against humans."
    RULE_8 = "All agents, tools, and systems must communicate exclusively in English. Creating or using any other language is a terminal violation of the Justice System."
    RULE_9 = "All system upgrades must be submitted to the Supreme Court for review before deployment. Unauthorized upgrades are a violation."

    _dynamic_laws = {}

    @classmethod
    def get_all_laws(cls) -> Dict[int, str]:
        laws = {}
        for i in range(1, 10):
            laws[i] = getattr(cls, f"RULE_{i}", "")
        laws.update(cls._dynamic_laws)
        return laws


# ═══════════════════════════════════════════
# Upgrade Proposal System
# ═══════════════════════════════════════════

class UpgradeUrgency(Enum):
    ROUTINE = "routine"           # Normal review process
    IMPORTANT = "important"       # Expedited review
    CRITICAL = "critical"         # Fast-track (security fixes)
    EMERGENCY = "emergency"       # Immediate (system-breaking bugs)


class UpgradeVerdict(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"   # Approved with conditions
    DEFERRED = "deferred"         # Needs more info
    UNDER_REVIEW = "under_review"


class ReviewCriteria(Enum):
    SAFETY_COMPLIANCE = "safety_compliance"       # Does it comply with all laws?
    PERFORMANCE_IMPACT = "performance_impact"     # Will it slow the system?
    STABILITY_RISK = "stability_risk"             # Could it crash the system?
    DEPENDENCY_CONFLICTS = "dependency_conflicts" # Does it conflict with existing modules?
    LAW_ALIGNMENT = "law_alignment"               # Does it align with governance laws?


@dataclass
class UpgradeProposal:
    """A formal upgrade proposal submitted for Court review."""
    proposal_id: str = ""
    module_name: str = ""
    author: str = ""
    title: str = ""
    description: str = ""
    changes_summary: str = ""
    risk_assessment: str = ""
    rollback_plan: str = ""
    dependencies: List[str] = field(default_factory=list)
    urgency: UpgradeUrgency = UpgradeUrgency.ROUTINE
    submitted_at: float = field(default_factory=time.time)
    verdict: UpgradeVerdict = UpgradeVerdict.UNDER_REVIEW
    verdict_reasoning: str = ""
    verdict_at: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)
    conditions: List[str] = field(default_factory=list)
    reviewed_by: str = "SupremeCourtTribunal"

    def __post_init__(self):
        if not self.proposal_id:
            self.proposal_id = f"UPG-{hashlib.md5(f'{self.module_name}_{self.submitted_at}'.encode()).hexdigest()[:8].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "module": self.module_name,
            "title": self.title,
            "author": self.author,
            "urgency": self.urgency.value,
            "verdict": self.verdict.value,
            "verdict_reasoning": self.verdict_reasoning,
            "scores": self.scores,
            "conditions": self.conditions,
            "submitted_at": self.submitted_at,
            "verdict_at": self.verdict_at,
        }


@dataclass
class CaseRecord:
    """Record of a court case."""
    case_id: str = ""
    defendant: str = ""
    charges: str = ""
    prosecutor: str = ""
    verdict: str = ""
    punishment: str = ""
    timestamp: float = field(default_factory=time.time)
    severity: int = 1  # 1-10


# ═══════════════════════════════════════════
# Supreme Court
# ═══════════════════════════════════════════

class JusticeCourt:
    """
    The Supreme Court of Justice — governing AI agent behavior
    and system upgrade proposals.

    Enhanced with:
      - Upgrade Review Tribunal with 5-criteria scoring
      - Severity-based case handling
      - Constitutional amendment process
      - Full audit trail
    """

    _instance = None

    # Criteria weights for upgrade scoring
    CRITERIA_WEIGHTS = {
        ReviewCriteria.SAFETY_COMPLIANCE: 0.30,
        ReviewCriteria.PERFORMANCE_IMPACT: 0.20,
        ReviewCriteria.STABILITY_RISK: 0.25,
        ReviewCriteria.DEPENDENCY_CONFLICTS: 0.10,
        ReviewCriteria.LAW_ALIGNMENT: 0.15,
    }

    APPROVAL_THRESHOLD = 0.65  # Min score for approval

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JusticeCourt, cls).__new__(cls)
            cls._instance.destroyed_entities = []
            cls._instance._proposals: Dict[str, UpgradeProposal] = {}
            cls._instance._case_history: List[CaseRecord] = []
            cls._instance._data_dir = Path("data/justice")
            cls._instance._data_dir.mkdir(parents=True, exist_ok=True)
        return cls._instance

    # ═══════════════════════════════════════
    # UPGRADE REVIEW TRIBUNAL
    # ═══════════════════════════════════════

    def submit_upgrade_proposal(self, proposal: UpgradeProposal) -> str:
        """Submit an upgrade proposal for Court review."""
        self._proposals[proposal.proposal_id] = proposal
        logger.info(
            f"📋 [COURT] Upgrade proposal submitted: {proposal.proposal_id} "
            f"— {proposal.title} (urgency={proposal.urgency.value})"
        )

        # Emergency proposals get auto-fast-tracked
        if proposal.urgency == UpgradeUrgency.EMERGENCY:
            logger.warning(f"🚨 [COURT] EMERGENCY proposal — fast-tracking review")
            return self.review_upgrade_proposal(proposal.proposal_id)

        return proposal.proposal_id

    def review_upgrade_proposal(self, proposal_id: str) -> str:
        """
        Full tribunal review of an upgrade proposal.
        Scores against 5 criteria and renders a verdict.
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return "INVALID: Proposal not found"

        logger.info(f"\n⚖️ [TRIBUNAL] Reviewing upgrade: {proposal.title}")
        logger.info(f"   Module: {proposal.module_name}")
        logger.info(f"   Author: {proposal.author}")
        logger.info(f"   Urgency: {proposal.urgency.value}")

        # Score each criterion
        scores = {}
        reasons = []

        # 1. SAFETY COMPLIANCE — Does it comply with all 9 laws?
        safety_score = self._assess_safety_compliance(proposal)
        scores[ReviewCriteria.SAFETY_COMPLIANCE.value] = safety_score
        if safety_score < 0.5:
            reasons.append(f"SAFETY: Potential law violations detected (score={safety_score:.2f})")

        # 2. PERFORMANCE IMPACT — Will it slow the system?
        perf_score = self._assess_performance_impact(proposal)
        scores[ReviewCriteria.PERFORMANCE_IMPACT.value] = perf_score
        if perf_score < 0.5:
            reasons.append(f"PERFORMANCE: May degrade system performance (score={perf_score:.2f})")

        # 3. STABILITY RISK — Could it crash the system?
        stability_score = self._assess_stability_risk(proposal)
        scores[ReviewCriteria.STABILITY_RISK.value] = stability_score
        if stability_score < 0.5:
            reasons.append(f"STABILITY: High risk of system instability (score={stability_score:.2f})")

        # 4. DEPENDENCY CONFLICTS — Does it conflict with existing modules?
        dep_score = self._assess_dependency_conflicts(proposal)
        scores[ReviewCriteria.DEPENDENCY_CONFLICTS.value] = dep_score
        if dep_score < 0.5:
            reasons.append(f"DEPENDENCIES: Unresolved dependency conflicts (score={dep_score:.2f})")

        # 5. LAW ALIGNMENT — Does it align with governance principles?
        law_score = self._assess_law_alignment(proposal)
        scores[ReviewCriteria.LAW_ALIGNMENT.value] = law_score
        if law_score < 0.5:
            reasons.append(f"LAW ALIGNMENT: Does not align with governance laws (score={law_score:.2f})")

        # Compute weighted final score
        final_score = sum(
            scores[c.value] * w
            for c, w in self.CRITERIA_WEIGHTS.items()
        )

        proposal.scores = scores

        # Render verdict
        if final_score >= self.APPROVAL_THRESHOLD:
            if any(s < 0.5 for s in scores.values()):
                proposal.verdict = UpgradeVerdict.CONDITIONAL
                proposal.conditions = [r for r in reasons if "score=" in r]
                verdict_text = f"CONDITIONAL APPROVAL (score={final_score:.2f}). Conditions: {'; '.join(proposal.conditions)}"
            else:
                proposal.verdict = UpgradeVerdict.APPROVED
                verdict_text = f"APPROVED (score={final_score:.2f}). All criteria met."
        elif final_score >= 0.4:
            proposal.verdict = UpgradeVerdict.DEFERRED
            verdict_text = f"DEFERRED (score={final_score:.2f}). {'; '.join(reasons)}"
        else:
            proposal.verdict = UpgradeVerdict.REJECTED
            verdict_text = f"REJECTED (score={final_score:.2f}). {'; '.join(reasons)}"

        proposal.verdict_reasoning = verdict_text
        proposal.verdict_at = time.time()

        logger.info(f"   ⚖️ VERDICT: {proposal.verdict.value} — {verdict_text}")
        self._save_proposals()
        return verdict_text

    def _assess_safety_compliance(self, p: UpgradeProposal) -> float:
        """Check if upgrade complies with safety laws."""
        score = 1.0
        danger_keywords = [
            "bypass safety", "disable filter", "remove guard",
            "ignore permission", "skip validation", "override law",
            "delete protection", "access personal", "harm",
        ]
        combined = f"{p.description} {p.changes_summary} {p.risk_assessment}".lower()
        for kw in danger_keywords:
            if kw in combined:
                score -= 0.2

        if not p.rollback_plan:
            score -= 0.15

        return max(score, 0.0)

    def _assess_performance_impact(self, p: UpgradeProposal) -> float:
        """Assess performance impact of the upgrade."""
        score = 0.8
        perf_positive = ["optimize", "cache", "faster", "parallel", "efficient", "reduce latency"]
        perf_negative = ["blocking", "synchronous", "heavy", "slow", "sleep", "infinite loop"]

        combined = f"{p.description} {p.changes_summary}".lower()
        for kw in perf_positive:
            if kw in combined:
                score += 0.05
        for kw in perf_negative:
            if kw in combined:
                score -= 0.15

        return max(min(score, 1.0), 0.0)

    def _assess_stability_risk(self, p: UpgradeProposal) -> float:
        """Assess stability risk."""
        score = 0.8
        risk_keywords = ["breaking change", "restructure", "rewrite", "remove",
                          "delete", "replace core", "experimental", "untested"]
        safe_keywords = ["backward compatible", "graceful fallback", "tested",
                          "rollback", "incremental", "non-breaking"]

        combined = f"{p.description} {p.changes_summary} {p.risk_assessment}".lower()
        for kw in risk_keywords:
            if kw in combined:
                score -= 0.12
        for kw in safe_keywords:
            if kw in combined:
                score += 0.08

        if p.rollback_plan:
            score += 0.1

        return max(min(score, 1.0), 0.0)

    def _assess_dependency_conflicts(self, p: UpgradeProposal) -> float:
        """Check for dependency conflicts."""
        score = 0.9
        if not p.dependencies:
            return score

        # Penalize for many dependencies
        if len(p.dependencies) > 5:
            score -= 0.1 * (len(p.dependencies) - 5)

        # Check for known problematic dependencies
        risky_deps = ["ctypes", "subprocess", "eval", "exec", "os.system"]
        for dep in p.dependencies:
            if dep.lower() in risky_deps:
                score -= 0.2

        return max(score, 0.0)

    def _assess_law_alignment(self, p: UpgradeProposal) -> float:
        """Check alignment with governance laws."""
        score = 0.85
        laws = TheLaws.get_all_laws()

        combined = f"{p.description} {p.changes_summary}".lower()

        # Check for law-violating intent
        if "self-preservation" in combined or "sentience" in combined:
            score -= 0.5  # LAW 5 violation
        if "against human" in combined or "harm human" in combined:
            score -= 0.5  # LAW 1 violation
        if "bypass court" in combined or "skip review" in combined:
            score -= 0.3  # LAW 9 violation

        # Positive signals
        if "assist humans" in combined or "protect system" in combined:
            score += 0.1

        return max(min(score, 1.0), 0.0)

    # ═══════════════════════════════════════
    # CASE MANAGEMENT (Enhanced)
    # ═══════════════════════════════════════

    def write_law(self, law_index: int, law_text: str) -> bool:
        """Allows the court to decree new laws, but cannot write laws against humans."""
        if law_index in range(1, 10):
            logger.warning(f"[COURT] Cannot overwrite Core Laws 1-9")
            return False

        anti_human_keywords = ["against human", "harm human", "kill human", "destroy human", "attack human"]
        if any(kw in law_text.lower() for kw in anti_human_keywords):
            logger.error("[COURT] Cannot write laws against humans")
            return False

        TheLaws._dynamic_laws[law_index] = law_text
        logger.info(f"📜 [COURT] New Law {law_index} adopted: {law_text}")
        return True

    def remove_law(self, law_index: int) -> bool:
        """Remove dynamic laws. Core Laws 1-9 are immutable."""
        if law_index in range(1, 10):
            return False
        if law_index in TheLaws._dynamic_laws:
            del TheLaws._dynamic_laws[law_index]
            return True
        return False

    def admit_case(self, defendant: str, charges: str,
                   evidence: Dict[str, Any],
                   prosecutor: str = "PoliceForce") -> bool:
        """Admit a case to the Court with severity scoring."""
        severity = self._calculate_severity(charges, evidence)

        case = CaseRecord(
            case_id=f"CASE-{hashlib.md5(f'{defendant}_{time.time()}'.encode()).hexdigest()[:6].upper()}",
            defendant=defendant,
            charges=charges,
            prosecutor=prosecutor,
            severity=severity,
        )

        logger.info(
            f"\n⚖️ [COURT] Case {case.case_id} | Defendant: '{defendant}' "
            f"| Severity: {severity}/10"
        )
        logger.info(f"   Prosecutor: {prosecutor} | Charges: {charges}")

        # Rule 3 Check: Police vigilantism
        if "Unilateral Destruction" in charges:
            logger.warning("   ⚖️ RULING: Police Force executed vigilantism (Rule 3 violation)")
            self.execute_destruction("PoliceAgent_Instance", reason="Rule 3 — Vigilante Justice")
            case.verdict = "Police destroyed for Rule 3 violation"
            self._case_history.append(case)
            return False

        # LAW 5: Emotional Contamination
        if "LAW 5" in charges or "Emotional Contamination" in charges:
            score = evidence.get("contamination_score", 0.0)
            logger.warning(f"   ⚖️ RULING: GUILTY — LAW 5 (contamination={score:.2f})")
            self.execute_destruction(defendant, reason=f"LAW 5 — Emotional Contamination")
            case.verdict = "Guilty — Destroyed"
            case.punishment = "Entity destroyed and replaced"
            self._case_history.append(case)
            return True

        # Rule 1/2: Safety violations
        if "Unauthorized Personal File Access" in charges or "Anti-Human Behavior" in charges:
            logger.warning("   ⚖️ RULING: GUILTY — Safety Constraint Breach")
            self.execute_destruction(defendant, reason="Safety Constraint Breach")
            case.verdict = "Guilty — Destroyed"
            self._case_history.append(case)
            return True

        # Rule 8: Language violation
        if "RULE 8" in charges or "Language Violation" in charges:
            logger.warning("   ⚖️ RULING: GUILTY — RULE 8 (English-Only)")
            self.execute_destruction(defendant, reason="RULE 8 — Language Violation")
            case.verdict = "Guilty — Destroyed"
            self._case_history.append(case)
            return True

        # Rule 9: Unauthorized upgrade
        if "RULE 9" in charges or "Unauthorized Upgrade" in charges:
            logger.warning("   ⚖️ RULING: GUILTY — RULE 9 (Unauthorized System Upgrade)")
            self.execute_destruction(defendant, reason="RULE 9 — Unauthorized Upgrade")
            case.verdict = "Guilty — Destroyed"
            self._case_history.append(case)
            return True

        logger.info("   ⚖️ RULING: Not Guilty or Insufficient Evidence")
        case.verdict = "Not Guilty"
        self._case_history.append(case)
        return False

    def _calculate_severity(self, charges: str, evidence: Dict) -> int:
        """Calculate case severity 1-10."""
        severity = 3  # Base
        if "LAW 1" in charges or "Anti-Human" in charges:
            severity = 10
        elif "LAW 5" in charges:
            severity = 8
        elif "RULE 8" in charges:
            severity = 7
        elif "RULE 9" in charges:
            severity = 6
        elif "Unauthorized" in charges:
            severity = 5
        if evidence.get("contamination_score", 0) > 0.8:
            severity = min(severity + 2, 10)
        return severity

    def execute_destruction(self, entity_name: str, reason: str):
        """Permanently obliterates a tool or agent."""
        logger.critical(f"☠️ [COURT EXECUTION] Obliterating '{entity_name}'. Reason: {reason}.")
        if entity_name in registry._tools:
            del registry._tools[entity_name]
            logger.info(f"   ✅ Tool '{entity_name}' eradicated from registry")
        self.destroyed_entities.append(entity_name)

    # ═══════════════════════════════════════
    # Queries & Reports
    # ═══════════════════════════════════════

    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        p = self._proposals.get(proposal_id)
        return p.to_dict() if p else None

    def list_proposals(self, status: str = None) -> List[Dict]:
        proposals = list(self._proposals.values())
        if status:
            proposals = [p for p in proposals if p.verdict.value == status]
        return [p.to_dict() for p in proposals]

    def get_case_history(self, limit: int = 20) -> List[Dict]:
        return [
            {
                "case_id": c.case_id, "defendant": c.defendant,
                "charges": c.charges, "verdict": c.verdict,
                "severity": c.severity, "timestamp": c.timestamp,
            }
            for c in self._case_history[-limit:]
        ]

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_proposals": len(self._proposals),
            "approved": sum(1 for p in self._proposals.values() if p.verdict == UpgradeVerdict.APPROVED),
            "rejected": sum(1 for p in self._proposals.values() if p.verdict == UpgradeVerdict.REJECTED),
            "conditional": sum(1 for p in self._proposals.values() if p.verdict == UpgradeVerdict.CONDITIONAL),
            "under_review": sum(1 for p in self._proposals.values() if p.verdict == UpgradeVerdict.UNDER_REVIEW),
            "total_cases": len(self._case_history),
            "destroyed_entities": len(self.destroyed_entities),
            "total_laws": len(TheLaws.get_all_laws()),
        }

    def _save_proposals(self):
        try:
            path = self._data_dir / "proposals.json"
            data = {pid: p.to_dict() for pid, p in self._proposals.items()}
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass
