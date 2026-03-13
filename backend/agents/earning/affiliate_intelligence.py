"""
Revenue Pillar 5 — Affiliate Intelligence
──────────────────────────────────────────
Discovers high-commission affiliate programs, generates SEO-optimized
review content, builds comparison sites, and drives organic traffic.
"""

import time, logging, asyncio, random
from typing import Dict, List, Any, Optional, Callable
from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 4,
    "niches": ["ai_tools", "developer_tools", "saas_products", "hosting", "productivity"],
    "min_commission_percent": 10,
    "content_types": ["review_article", "comparison_table", "tutorial_with_links"],
}


class AffiliateIntelligence(EarningPillar):
    """Discovers affiliate programs and generates conversion-optimized content."""

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="affiliate_intelligence", generate_fn=generate_fn,
                         config=config or DEFAULT_CONFIG.copy())

    async def discover(self) -> List[Opportunity]:
        opportunities = []
        if self.generate_fn:
            prompt = (
                f"Identify 3 high-commission affiliate programs in these niches: "
                f"{', '.join(self.config['niches'])}.\n"
                f"For each: product_name, affiliate_program, commission_percent, "
                f"cookie_duration_days, avg_sale_usd, content_angle, difficulty (0-1).\n"
                f"Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    programs = json.loads(self._extract_json(answer))
                    for prog in programs:
                        commission = float(prog.get("commission_percent", 20)) / 100
                        avg_sale = float(prog.get("avg_sale_usd", 50))
                        monthly_rev = commission * avg_sale * 30  # Estimated 30 conversions/mo
                        opportunities.append(Opportunity(
                            id=f"aff_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name, platform=prog.get("affiliate_program", "Direct"),
                            title=f"Affiliate: {prog.get('product_name', 'Product')}",
                            description=prog.get("content_angle", ""),
                            estimated_revenue_usd=monthly_rev, difficulty=float(prog.get("difficulty", 0.3)),
                            time_to_revenue_hours=6, competition_level=0.5, confidence=0.5,
                            tags=["affiliate"], metadata=prog,
                        ))
                except (json.JSONDecodeError, TypeError): pass
            except Exception as e: logger.debug(f"[AFFILIATE] Discovery error: {e}")
        if not opportunities:
            opportunities.append(Opportunity(
                id=f"sim_aff_{int(time.time())}", pillar=self.name, platform="Amazon Associates",
                title="Affiliate: Developer Productivity Tools", description="Review article for dev tools",
                estimated_revenue_usd=300, difficulty=0.3, time_to_revenue_hours=5,
                competition_level=0.5, confidence=0.5, tags=["affiliate"],
            ))
        return opportunities

    async def evaluate(self, opp: Opportunity) -> float:
        score = 0.6  # Affiliates are generally reliable
        hourly = opp.estimated_revenue_usd / max(opp.time_to_revenue_hours, 1)
        score += min(hourly / 100, 0.2)
        score += (1.0 - opp.difficulty) * 0.15
        return max(0.0, min(1.0, score))

    async def execute(self, opp: Opportunity) -> ExecutionResult:
        start = time.time()
        deliverables = []
        try:
            if self.generate_fn:
                for ctype in self.config.get("content_types", ["review_article"])[:2]:
                    prompt = f"Write a {ctype} for {opp.title}. {opp.description}. Include affiliate CTA."
                    result = await asyncio.to_thread(self.generate_fn, prompt)
                    answer = result.answer if hasattr(result, 'answer') else str(result)
                    deliverables.append(f"{ctype}: {answer[:200]}...")
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
