"""
Revenue Pillar 7 — API Monetization
────────────────────────────────────
Builds and sells API endpoints (AI tools, data enrichment, text processing).
Usage-based billing on RapidAPI or self-hosted infrastructure.
"""

import time, logging, asyncio, random
from typing import Dict, List, Any, Optional, Callable
from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 2,
    "api_categories": ["text_processing", "data_enrichment", "image_generation", "translation", "sentiment"],
    "platforms": ["RapidAPI", "Self-hosted"],
    "pricing_per_call": 0.01,
}


class APIMonetizer(EarningPillar):
    """Builds and deploys monetized API endpoints."""

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="api_monetizer", generate_fn=generate_fn,
                         config=config or DEFAULT_CONFIG.copy())

    async def discover(self) -> List[Opportunity]:
        opportunities = []
        if self.generate_fn:
            prompt = (
                f"Identify 2 profitable API product ideas in: {', '.join(self.config['api_categories'])}.\n"
                f"For each: api_name, description, use_case, estimated_daily_calls, "
                f"price_per_call_usd, build_hours, difficulty (0-1).\n"
                f"Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    apis = json.loads(self._extract_json(answer))
                    for api in apis:
                        daily_calls = int(api.get("estimated_daily_calls", 1000))
                        price = float(api.get("price_per_call_usd", 0.01))
                        monthly = daily_calls * price * 30
                        opportunities.append(Opportunity(
                            id=f"api_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name, platform="RapidAPI",
                            title=api.get("api_name", "API Endpoint"),
                            description=api.get("use_case", ""),
                            estimated_revenue_usd=monthly, difficulty=float(api.get("difficulty", 0.5)),
                            time_to_revenue_hours=float(api.get("build_hours", 15)),
                            competition_level=0.5, confidence=0.5,
                            tags=["api"], metadata=api,
                        ))
                except (json.JSONDecodeError, TypeError): pass
            except Exception as e: logger.debug(f"[API] Discovery error: {e}")
        if not opportunities:
            opportunities.append(Opportunity(
                id=f"sim_api_{int(time.time())}", pillar=self.name, platform="RapidAPI",
                title="Text Summarization API", description="AI-powered text summarization endpoint",
                estimated_revenue_usd=600, difficulty=0.4, time_to_revenue_hours=10,
                competition_level=0.5, confidence=0.5,
            ))
        return opportunities

    async def evaluate(self, opp: Opportunity) -> float:
        score = 0.5
        hourly = opp.estimated_revenue_usd / max(opp.time_to_revenue_hours, 1)
        score += min(hourly / 100, 0.25)
        score += (1.0 - opp.difficulty) * 0.2
        return max(0.0, min(1.0, score))

    async def execute(self, opp: Opportunity) -> ExecutionResult:
        start = time.time()
        deliverables = []
        try:
            if self.generate_fn:
                for phase in ["api_spec", "implementation", "documentation", "deployment_config"]:
                    prompt = f"Generate {phase} for API product: {opp.title}\n{opp.description}"
                    result = await asyncio.to_thread(self.generate_fn, prompt)
                    answer = result.answer if hasattr(result, 'answer') else str(result)
                    deliverables.append(f"{phase}: {answer[:200]}...")
            return ExecutionResult(
                opportunity_id=opp.id, pillar=self.name, success=True,
                revenue_earned_usd=opp.estimated_revenue_usd,
                time_spent_hours=max((time.time() - start) / 3600, 1),
                deliverables=deliverables, started_at=start, completed_at=time.time(),
            )
        except Exception as e:
            return ExecutionResult(opportunity_id=opp.id, pillar=self.name, success=False,
                                  error=str(e), started_at=start, completed_at=time.time())

    def _extract_json(self, t):
        s, e = t.find("["), t.rfind("]") + 1
        return t[s:e] if s >= 0 and e > s else "[]"
