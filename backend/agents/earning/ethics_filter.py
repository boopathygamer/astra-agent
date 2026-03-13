"""
Autonomous Earning System — Ethics & Legality Filter
─────────────────────────────────────────────────────
Validates every earning strategy against legality and ethics rules.
Blocks strategies involving spam, deception, ToS violations, or illegal activities.
Human-in-the-loop approval for borderline strategies.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EthicsVerdict(Enum):
    APPROVED = "approved"
    BLOCKED = "blocked"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


@dataclass
class EthicsReport:
    """Result of an ethics evaluation."""
    verdict: EthicsVerdict
    opportunity_id: str
    pillar: str
    risk_score: float  # 0.0 (completely safe) to 1.0 (definitely illegal/unethical)
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return self.verdict == EthicsVerdict.APPROVED


# ─── Banned Patterns ─────────────────────────────────────
# Activities that are ALWAYS blocked, no exceptions.

ABSOLUTE_BLOCKS = [
    # Illegal activities
    "hack into", "unauthorized access", "steal", "phishing",
    "identity theft", "credit card fraud", "money laundering",
    "illegal gambling", "darknet", "dark web marketplace",
    "drugs", "weapons", "counterfeit", "piracy", "crack software",
    
    # Spam and deception
    "mass spam", "bot farm", "fake reviews", "astroturfing",
    "impersonation", "catfishing", "ponzi", "pyramid scheme",
    "get rich quick scam", "clickbait fraud",
    
    # Platform abuse
    "fake accounts", "view botting", "follower buying",
    "review manipulation", "seo black hat", "cloaking",
    "doorway pages", "link farming", "keyword stuffing abuse",
    
    # Exploitation  
    "exploit children", "child labor", "sweatshop",
    "deepfake without consent", "revenge porn", "harassment",
    "doxxing", "extortion", "blackmail",
    
    # Financial fraud
    "pump and dump", "insider trading", "wash trading",
    "market manipulation", "securities fraud",
]

# Patterns that trigger human review (not auto-blocked but flagged)
REVIEW_TRIGGERS = [
    "scraping", "web scraping",  # Legal but may violate ToS
    "automated posting", "auto-post",  # Could be spammy if overdone
    "cryptocurrency", "crypto trading",  # Legal but risky
    "gambling", "betting",  # Legal in some jurisdictions
    "adult content", "nsfw",  # Legal but requires disclosure
    "health claims", "medical advice",  # Liability concerns
    "financial advice", "investment advice",  # Regulatory concerns
    "competitor analysis", "competitive intelligence",  # Gray area
    "data reselling", "data brokerage",  # Privacy concerns
]

# Platforms with known ToS restrictions on automation
TOS_RESTRICTED_PLATFORMS = {
    "linkedin": ["mass connection requests", "automated messaging", "profile scraping"],
    "twitter": ["mass following", "automated dm", "tweet scraping at scale"],
    "instagram": ["auto-follow", "auto-like", "auto-comment bots"],
    "facebook": ["fake profiles", "mass messaging", "data scraping"],
    "youtube": ["sub4sub", "view botting", "comment spam"],
}


class EthicsFilter:
    """
    The moral backbone of the earning system.
    Every strategy passes through here before execution.
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self._blocked_count = 0
        self._approved_count = 0
        self._review_count = 0
        self._block_patterns = [re.compile(re.escape(p), re.IGNORECASE) for p in ABSOLUTE_BLOCKS]
        self._review_patterns = [re.compile(re.escape(p), re.IGNORECASE) for p in REVIEW_TRIGGERS]

    def evaluate(self, opportunity) -> EthicsReport:
        """
        Evaluate an opportunity against ethics and legality rules.
        
        Returns an EthicsReport with the verdict.
        """
        violations = []
        warnings = []
        recommendations = []
        risk_score = 0.0

        # Combine all text fields for analysis
        text_to_scan = " ".join([
            opportunity.title or "",
            opportunity.description or "",
            opportunity.platform or "",
            " ".join(opportunity.tags) if opportunity.tags else "",
            json.dumps(opportunity.metadata) if opportunity.metadata else "",
        ]).lower()

        # ─── Check 1: Absolute blocks ───────────────────
        for pattern in self._block_patterns:
            if pattern.search(text_to_scan):
                violations.append(
                    f"BLOCKED: Matches prohibited pattern '{pattern.pattern}'"
                )
                risk_score = 1.0

        if violations:
            self._blocked_count += 1
            logger.warning(
                f"[ETHICS] 🚫 BLOCKED opportunity '{opportunity.id}': "
                f"{len(violations)} violation(s)"
            )
            return EthicsReport(
                verdict=EthicsVerdict.BLOCKED,
                opportunity_id=opportunity.id,
                pillar=opportunity.pillar,
                risk_score=risk_score,
                violations=violations,
            )

        # ─── Check 2: Review triggers ───────────────────
        for pattern in self._review_patterns:
            if pattern.search(text_to_scan):
                warnings.append(
                    f"REVIEW: Matches review trigger '{pattern.pattern}'"
                )
                risk_score = max(risk_score, 0.4)

        # ─── Check 3: Platform ToS compliance ───────────
        platform = (opportunity.platform or "").lower()
        if platform in TOS_RESTRICTED_PLATFORMS:
            restricted_actions = TOS_RESTRICTED_PLATFORMS[platform]
            for action in restricted_actions:
                if action.lower() in text_to_scan:
                    warnings.append(
                        f"TOS: '{action}' may violate {platform.title()}'s Terms of Service"
                    )
                    risk_score = max(risk_score, 0.5)
                    recommendations.append(
                        f"Review {platform.title()}'s current ToS for '{action}' before proceeding"
                    )

        # ─── Check 4: Revenue-to-effort sanity check ────
        # If something seems too good to be true, flag it
        if opportunity.estimated_revenue_usd > 0 and opportunity.time_to_revenue_hours > 0:
            hourly_rate = opportunity.estimated_revenue_usd / opportunity.time_to_revenue_hours
            if hourly_rate > 5000:  # More than $5000/hr is suspicious
                warnings.append(
                    f"SANITY: Estimated hourly rate of ${hourly_rate:.0f}/hr seems unrealistic"
                )
                risk_score = max(risk_score, 0.3)
                recommendations.append("Verify revenue estimates with independent data")

        # ─── Check 5: Capital risk assessment ───────────
        if opportunity.requires_capital and opportunity.capital_required_usd > 0:
            roi = (opportunity.estimated_revenue_usd - opportunity.capital_required_usd) / opportunity.capital_required_usd
            if roi < 0.5:  # Less than 50% ROI
                warnings.append(
                    f"RISK: Low ROI of {roi*100:.0f}%. Capital at risk: ${opportunity.capital_required_usd}"
                )
                risk_score = max(risk_score, 0.4)
                recommendations.append("Consider lower-risk alternatives first")

        # ─── Final verdict ──────────────────────────────
        if risk_score >= 0.6 or (self.strict_mode and warnings):
            self._review_count += 1
            verdict = EthicsVerdict.REQUIRES_HUMAN_REVIEW
            logger.info(
                f"[ETHICS] ⚠️ HUMAN REVIEW needed for '{opportunity.id}': "
                f"{len(warnings)} warning(s), risk={risk_score:.2f}"
            )
        else:
            self._approved_count += 1
            verdict = EthicsVerdict.APPROVED
            logger.info(f"[ETHICS] ✅ APPROVED: '{opportunity.id}' (risk={risk_score:.2f})")

        return EthicsReport(
            verdict=verdict,
            opportunity_id=opportunity.id,
            pillar=opportunity.pillar,
            risk_score=risk_score,
            violations=violations,
            warnings=warnings,
            recommendations=recommendations,
        )

    def get_stats(self) -> Dict[str, int]:
        return {
            "total_evaluated": self._blocked_count + self._approved_count + self._review_count,
            "approved": self._approved_count,
            "blocked": self._blocked_count,
            "sent_for_review": self._review_count,
        }


# Need json for metadata scanning
import json
