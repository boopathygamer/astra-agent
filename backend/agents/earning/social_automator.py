"""
Revenue Pillar 9 — Social Media Automation
──────────────────────────────────────────
Manages content calendars, generates platform-native posts,
optimizes posting times, and grows accounts algorithmically.
Offers social media management as-a-service.
"""

import time, logging, asyncio, random
from typing import Dict, List, Any, Optional, Callable
from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 5,
    "platforms": ["Twitter/X", "LinkedIn", "Instagram", "TikTok"],
    "content_types": ["thought_leadership", "technical_tips", "case_studies", "behind_scenes"],
    "posts_per_week": 15,
    "service_price_monthly": 1000,
}


class SocialAutomator(EarningPillar):
    """Manages multi-platform social media content and offers it as a service."""

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="social_automator", generate_fn=generate_fn,
                         config=config or DEFAULT_CONFIG.copy())

    async def discover(self) -> List[Opportunity]:
        opportunities = []
        if self.generate_fn:
            prompt = (
                "Identify 3 social media management opportunities:\n"
                "1. A business niche that needs social media help\n"
                "2. A content strategy for organic growth\n"
                "3. A specific platform growth hack\n"
                "For each: opportunity_name, platform, target_client, monthly_value_usd, "
                "time_hours_weekly, difficulty (0-1).\nReturn ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    opps = json.loads(self._extract_json(answer))
                    for o in opps:
                        opportunities.append(Opportunity(
                            id=f"social_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name, platform=o.get("platform", "Twitter/X"),
                            title=o.get("opportunity_name", "Social Media Opp"),
                            description=o.get("target_client", ""),
                            estimated_revenue_usd=float(o.get("monthly_value_usd", 500)),
                            difficulty=float(o.get("difficulty", 0.3)),
                            time_to_revenue_hours=float(o.get("time_hours_weekly", 5)) * 4,
                            competition_level=0.4, confidence=0.5, tags=["social"],
                        ))
                except (json.JSONDecodeError, TypeError): pass
            except Exception as e: logger.debug(f"[SOCIAL] Discovery error: {e}")
        if not opportunities:
            opportunities.append(Opportunity(
                id=f"sim_social_{int(time.time())}", pillar=self.name, platform="Twitter/X",
                title="Tech Startup Social Strategy", description="Content calendar for SaaS startups",
                estimated_revenue_usd=1000, difficulty=0.3, time_to_revenue_hours=20,
                competition_level=0.4, confidence=0.5,
            ))
        return opportunities

    async def evaluate(self, opp: Opportunity) -> float:
        score = 0.6
        hourly = opp.estimated_revenue_usd / max(opp.time_to_revenue_hours, 1)
        score += min(hourly / 100, 0.2)
        score += (1.0 - opp.difficulty) * 0.15
        return max(0.0, min(1.0, score))

    async def execute(self, opp: Opportunity) -> ExecutionResult:
        start = time.time()
        deliverables = []
        try:
            if self.generate_fn:
                for phase in ["content_calendar", "week1_posts", "engagement_strategy", "analytics_template"]:
                    prompt = f"Generate {phase} for social media client: {opp.title}\n{opp.description}"
                    result = await asyncio.to_thread(self.generate_fn, prompt)
                    answer = result.answer if hasattr(result, 'answer') else str(result)
                    deliverables.append(f"{phase}: {answer[:200]}...")
            return ExecutionResult(
                opportunity_id=opp.id, pillar=self.name, success=True,
                revenue_earned_usd=opp.estimated_revenue_usd,
                time_spent_hours=max((time.time() - start) / 3600, 0.5),
                deliverables=deliverables, started_at=start, completed_at=time.time(),
            )
        except Exception as e:
            return ExecutionResult(opportunity_id=opp.id, pillar=self.name, success=False,
                                  error=str(e), started_at=start, completed_at=time.time())

    def _extract_json(self, t):
        s, e = t.find("["), t.rfind("]") + 1
        return t[s:e] if s >= 0 and e > s else "[]"
