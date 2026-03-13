"""
Self-Evolving Intelligence — Failure Autopsy Engine
────────────────────────────────────────────────────
When a strategy fails, this engine performs a deep analysis to understand
WHY it failed, extracts actionable lessons, and generates strategy mutations
to prevent repeating the same mistakes.

This is the AI's ability to LEARN FROM FAILURE.
"""

import time
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class AutopsyReport:
    """Complete analysis of why a strategy failed."""
    failure_id: str
    pillar: str
    root_cause: str
    failure_category: str  # technical, market, resource, timing, competition
    severity: float  # 0.0 (minor) to 1.0 (critical)
    actionable_lessons: List[str]
    suggested_mutations: List[Dict[str, Any]]
    prevention_rules: List[str]
    created_at: float = field(default_factory=time.time)


class FailureAutopsyEngine:
    """
    The AI's error-correction mechanism.
    
    1. Categorizes failures (technical, market, resource, timing, competition)
    2. Performs root cause analysis using AI reasoning
    3. Extracts actionable lessons
    4. Generates strategy mutations to avoid repetition
    5. Builds a failure knowledge base over time
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self._autopsy_history: List[AutopsyReport] = []
        self._failure_patterns: Dict[str, int] = defaultdict(int)
        self._prevention_rules: List[str] = []

    async def analyze_failure(
        self,
        opportunity_data: Dict[str, Any],
        error: str,
        pillar: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AutopsyReport:
        """
        Perform a deep autopsy on a failed earning attempt.
        """
        logger.info(f"[AUTOPSY] 🔬 Analyzing failure in {pillar}: {error[:100]}...")
        
        # Step 1: Categorize the failure
        category = self._categorize_failure(error, opportunity_data)
        self._failure_patterns[f"{pillar}:{category}"] += 1
        
        # Step 2: AI-powered root cause analysis
        root_cause = await self._deduce_root_cause(opportunity_data, error, pillar, context)
        
        # Step 3: Extract lessons
        lessons = await self._extract_lessons(root_cause, category, pillar)
        
        # Step 4: Generate mutations
        mutations = self._generate_mutations(category, root_cause, pillar)
        
        # Step 5: Create prevention rules
        rules = self._generate_prevention_rules(category, root_cause)
        self._prevention_rules.extend(rules)
        
        report = AutopsyReport(
            failure_id=f"autopsy_{int(time.time())}_{len(self._autopsy_history)}",
            pillar=pillar,
            root_cause=root_cause,
            failure_category=category,
            severity=self._calculate_severity(category, error),
            actionable_lessons=lessons,
            suggested_mutations=mutations,
            prevention_rules=rules,
        )
        
        self._autopsy_history.append(report)
        
        logger.info(
            f"[AUTOPSY] Report complete: category={category}, "
            f"severity={report.severity:.2f}, lessons={len(lessons)}"
        )
        return report

    def _categorize_failure(self, error: str, opportunity_data: Dict[str, Any]) -> str:
        """Classify the failure into categories."""
        error_lower = error.lower()
        
        if any(kw in error_lower for kw in ["timeout", "connection", "api", "rate limit", "500", "403"]):
            return "technical"
        elif any(kw in error_lower for kw in ["no demand", "saturated", "already exists", "competitor"]):
            return "market"
        elif any(kw in error_lower for kw in ["token", "memory", "disk", "quota", "budget"]):
            return "resource"
        elif any(kw in error_lower for kw in ["expired", "deadline", "too late", "closed"]):
            return "timing"
        elif any(kw in error_lower for kw in ["rejected", "outbid", "lost", "competition"]):
            return "competition"
        else:
            return "unknown"

    async def _deduce_root_cause(
        self, opportunity_data: Dict, error: str, pillar: str, context: Optional[Dict]
    ) -> str:
        """Use AI to perform root cause analysis."""
        if not self.generate_fn:
            return f"Failure in {pillar}: {error}"
        
        # Check for recurring patterns
        pattern_key = f"{pillar}:{self._categorize_failure(error, opportunity_data)}"
        recurrence = self._failure_patterns.get(pattern_key, 0)
        
        prompt = (
            f"You are a failure analysis expert. Perform root cause analysis:\n\n"
            f"Pillar: {pillar}\n"
            f"Error: {error}\n"
            f"Opportunity: {str(opportunity_data)[:300]}\n"
            f"Recurrence count: {recurrence} (times this type of failure has occurred)\n\n"
            f"Provide a concise root cause analysis (2-3 sentences) that identifies:\n"
            f"1. The immediate cause\n"
            f"2. The underlying systemic issue\n"
            f"3. Why this specific strategy configuration led to failure"
        )
        
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            return result.answer if hasattr(result, 'answer') else str(result)
        except Exception:
            return f"Root cause: {error}"

    async def _extract_lessons(self, root_cause: str, category: str, pillar: str) -> List[str]:
        """Extract actionable lessons from the failure."""
        if not self.generate_fn:
            return [f"Avoid {category} failures in {pillar}"]
        
        prompt = (
            f"Based on this failure analysis, extract 3 concise, actionable lessons:\n\n"
            f"Root Cause: {root_cause}\n"
            f"Category: {category}\n"
            f"Pillar: {pillar}\n\n"
            f"Each lesson should be a single sentence starting with an action verb. "
            f"Return as a JSON array of strings."
        )
        
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            answer = result.answer if hasattr(result, 'answer') else str(result)
            import json
            try:
                lessons = json.loads(self._extract_json_arr(answer))
                if isinstance(lessons, list):
                    return [str(l) for l in lessons[:5]]
            except (json.JSONDecodeError, TypeError):
                pass
        except Exception:
            pass
        
        # Fallback lessons based on category
        fallback_lessons = {
            "technical": [f"Add retry logic for {pillar}", "Implement better error handling"],
            "market": [f"Re-evaluate market demand for {pillar}", "Diversify target markets"],
            "resource": [f"Optimize resource usage in {pillar}", "Set tighter resource limits"],
            "timing": [f"Improve timing in {pillar}", "Scan more frequently for time-sensitive opportunities"],
            "competition": [f"Differentiate approach in {pillar}", "Target less competitive niches"],
        }
        return fallback_lessons.get(category, [f"Review {pillar} strategy thoroughly"])

    def _generate_mutations(self, category: str, root_cause: str, pillar: str) -> List[Dict[str, Any]]:
        """Generate strategy mutations to avoid repeating this failure."""
        mutations = []
        
        if category == "technical":
            mutations.append({
                "parameter": "max_retries",
                "action": "increase",
                "suggested_value": 3,
                "reason": "Technical failures may be transient",
            })
        elif category == "market":
            mutations.append({
                "parameter": "min_roi_score",
                "action": "increase",
                "suggested_value": 0.7,
                "reason": "Be more selective about market opportunities",
            })
            mutations.append({
                "parameter": "preferred_niches",
                "action": "diversify",
                "reason": "Current niche may be saturated",
            })
        elif category == "resource":
            mutations.append({
                "parameter": "max_executions_per_cycle",
                "action": "decrease",
                "suggested_value": 2,
                "reason": "Reduce resource consumption per cycle",
            })
        elif category == "timing":
            mutations.append({
                "parameter": "scan_interval",
                "action": "decrease",
                "reason": "Scan more frequently to catch time-sensitive opportunities",
            })
        elif category == "competition":
            mutations.append({
                "parameter": "max_difficulty",
                "action": "decrease",
                "suggested_value": 0.5,
                "reason": "Target easier opportunities with less competition",
            })
            mutations.append({
                "parameter": "proposal_style",
                "action": "change",
                "suggested_value": "unique_approach",
                "reason": "Differentiate from competitors",
            })
        
        return mutations

    def _generate_prevention_rules(self, category: str, root_cause: str) -> List[str]:
        """Generate rules to prevent similar failures."""
        rules = {
            "technical": ["Verify API availability before executing", "Implement exponential backoff"],
            "market": ["Validate market demand before committing resources"],
            "resource": ["Check resource availability before execution", "Set hard resource limits"],
            "timing": ["Verify opportunity freshness before execution"],
            "competition": ["Analyze competitor density before bidding"],
        }
        return rules.get(category, ["Monitor and log all failures for pattern analysis"])

    def _calculate_severity(self, category: str, error: str) -> float:
        """Calculate failure severity."""
        base_severity = {
            "technical": 0.3,
            "market": 0.5,
            "resource": 0.6,
            "timing": 0.4,
            "competition": 0.3,
            "unknown": 0.5,
        }
        severity = base_severity.get(category, 0.5)
        
        # Recurring failures are more severe
        pattern_count = sum(1 for key, count in self._failure_patterns.items() if count > 2)
        severity += min(pattern_count * 0.1, 0.3)
        
        return min(severity, 1.0)

    def get_recurring_patterns(self, min_count: int = 3) -> List[Dict[str, Any]]:
        """Get failure patterns that keep recurring."""
        return [
            {"pattern": key, "count": count}
            for key, count in self._failure_patterns.items()
            if count >= min_count
        ]

    def get_all_prevention_rules(self) -> List[str]:
        """Get all accumulated prevention rules."""
        return list(set(self._prevention_rules))

    def get_autopsy_stats(self) -> Dict[str, Any]:
        return {
            "total_autopsies": len(self._autopsy_history),
            "failure_patterns": dict(self._failure_patterns),
            "prevention_rules_count": len(self._prevention_rules),
            "categories": defaultdict(int, {
                r.failure_category: 1 for r in self._autopsy_history
            }),
        }

    def _extract_json_arr(self, text: str) -> str:
        text = text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return text[start:end]
        return "[]"
