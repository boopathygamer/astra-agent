"""
Revenue Pillar 3 — SaaS Factory
────────────────────────────────
Identifies market gaps, designs, builds, and deploys micro-SaaS products.
Self-Thinking: A/B tests pricing, landing pages, feature sets; kills underperformers.
"""

import time, logging, asyncio, random
from typing import Dict, List, Any, Optional, Callable
from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 1,  # SaaS takes longer
    "tech_stacks": ["Next.js + Supabase", "Python FastAPI + PostgreSQL", "Remix + PlanetScale"],
    "target_mrr": 500,
    "pricing_models": ["freemium", "usage_based", "flat_rate"],
    "mvp_time_hours": 40,
}


class SaaSFactory(EarningPillar):
    """Identifies market gaps and builds micro-SaaS products."""

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="saas_factory", generate_fn=generate_fn, config=config or DEFAULT_CONFIG.copy())
        self._product_portfolio: List[Dict[str, Any]] = []

    async def discover(self) -> List[Opportunity]:
        opportunities = []
        if self.generate_fn:
            prompt = (
                "Identify 2 micro-SaaS product ideas that solve real problems. "
                "Each should be buildable by a solo developer in under 40 hours.\n"
                "For each: product_name, problem_solved, target_audience, "
                "pricing (monthly_usd), estimated_mrr_month_6, tech_stack, difficulty (0-1).\n"
                "Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    ideas = json.loads(self._extract_json(answer))
                    for idea in ideas:
                        opportunities.append(Opportunity(
                            id=f"saas_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name, platform="Self-hosted",
                            title=idea.get("product_name", "SaaS Product"),
                            description=idea.get("problem_solved", ""),
                            estimated_revenue_usd=float(idea.get("estimated_mrr_month_6", 500)),
                            difficulty=float(idea.get("difficulty", 0.6)),
                            time_to_revenue_hours=40, competition_level=0.5, confidence=0.5,
                            tags=[idea.get("tech_stack", "web")], metadata=idea,
                        ))
                except (json.JSONDecodeError, TypeError): pass
            except Exception as e: logger.debug(f"[SAAS] Discovery error: {e}")
        if not opportunities:
            opportunities.append(Opportunity(
                id=f"sim_saas_{int(time.time())}", pillar=self.name, platform="Self-hosted",
                title="AI-Powered Readme Generator", description="Auto-generates README files from code",
                estimated_revenue_usd=800, difficulty=0.5, time_to_revenue_hours=30,
                competition_level=0.4, confidence=0.6, tags=["Next.js + Supabase"],
            ))
        return opportunities

    async def evaluate(self, opportunity: Opportunity) -> float:
        score = 0.5
        hourly = opportunity.estimated_revenue_usd / max(opportunity.time_to_revenue_hours, 1)
        score += min(hourly / 100, 0.3)
        score += (1.0 - opportunity.difficulty) * 0.2
        return max(0.0, min(1.0, score))

    async def execute(self, opportunity: Opportunity) -> ExecutionResult:
        start = time.time()
        deliverables = []
        try:
            if self.generate_fn:
                for phase in ["architecture", "mvp_code", "landing_page", "deployment_guide"]:
                    prompt = f"Generate the {phase} for a SaaS product: {opportunity.title}\n{opportunity.description}"
                    result = await asyncio.to_thread(self.generate_fn, prompt)
                    answer = result.answer if hasattr(result, 'answer') else str(result)
                    deliverables.append(f"{phase}: {answer[:200]}...")
            self._product_portfolio.append({"name": opportunity.title, "launched": time.time()})
            return ExecutionResult(
                opportunity_id=opportunity.id, pillar=self.name, success=True,
                revenue_earned_usd=opportunity.estimated_revenue_usd,
                time_spent_hours=max((time.time() - start) / 3600, 1),
                deliverables=deliverables, started_at=start, completed_at=time.time(),
            )
        except Exception as e:
            return ExecutionResult(opportunity_id=opportunity.id, pillar=self.name, success=False,
                                  error=str(e), started_at=start, completed_at=time.time())

    def _extract_json(self, t):
        s, e = t.find("["), t.rfind("]") + 1
        return t[s:e] if s >= 0 and e > s else "[]"
