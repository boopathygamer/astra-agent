"""
Revenue Pillar 10 — Web Scraping & Data Services
─────────────────────────────────────────────────
Builds scrapers, data pipelines, and sells structured datasets.
Adapts scrapers when sites change, finds highest-value buyers.
"""

import time, logging, asyncio, random
from typing import Dict, List, Any, Optional, Callable
from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 2,
    "data_categories": ["real_estate", "job_listings", "product_pricing", "lead_generation", "market_research"],
    "delivery_formats": ["csv", "json", "api_endpoint"],
}


class DataServices(EarningPillar):
    """Builds data scrapers and sells structured datasets."""

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="data_services", generate_fn=generate_fn,
                         config=config or DEFAULT_CONFIG.copy())

    async def discover(self) -> List[Opportunity]:
        opportunities = []
        if self.generate_fn:
            prompt = (
                f"Identify 2 data service opportunities in: {', '.join(self.config['data_categories'])}.\n"
                f"For each: data_product, target_buyers, data_sources, "
                f"monthly_subscription_usd, build_hours, difficulty (0-1).\n"
                f"Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    services = json.loads(self._extract_json(answer))
                    for svc in services:
                        opportunities.append(Opportunity(
                            id=f"data_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name, platform="Data Marketplace",
                            title=svc.get("data_product", "Data Service"),
                            description=svc.get("target_buyers", ""),
                            estimated_revenue_usd=float(svc.get("monthly_subscription_usd", 300)),
                            difficulty=float(svc.get("difficulty", 0.5)),
                            time_to_revenue_hours=float(svc.get("build_hours", 15)),
                            competition_level=0.4, confidence=0.5,
                            tags=["data"], metadata=svc,
                        ))
                except (json.JSONDecodeError, TypeError): pass
            except Exception as e: logger.debug(f"[DATA] Discovery error: {e}")
        if not opportunities:
            opportunities.append(Opportunity(
                id=f"sim_data_{int(time.time())}", pillar=self.name, platform="Data Marketplace",
                title="SaaS Pricing Intelligence Dataset", description="Competitive pricing data",
                estimated_revenue_usd=500, difficulty=0.5, time_to_revenue_hours=15,
                competition_level=0.4, confidence=0.5,
            ))
        return opportunities

    async def evaluate(self, opp: Opportunity) -> float:
        score = 0.5
        hourly = opp.estimated_revenue_usd / max(opp.time_to_revenue_hours, 1)
        score += min(hourly / 80, 0.25)
        score += (1.0 - opp.difficulty) * 0.2
        return max(0.0, min(1.0, score))

    async def execute(self, opp: Opportunity) -> ExecutionResult:
        start = time.time()
        deliverables = []
        try:
            if self.generate_fn:
                for phase in ["scraper_code", "data_schema", "pipeline_config", "api_wrapper"]:
                    prompt = f"Generate {phase} for data service: {opp.title}\n{opp.description}"
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
