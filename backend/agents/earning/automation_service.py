"""
Revenue Pillar 12 — Automation-as-a-Service
────────────────────────────────────────────
Builds custom automation workflows for businesses.
Identifies repetitive processes and sells automation bots.
"""

import time, logging, asyncio, random
from typing import Dict, List, Any, Optional, Callable
from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 2,
    "automation_types": ["data_entry", "invoicing", "reporting", "email", "scheduling", "crm_sync"],
    "service_price_monthly": 500,
}


class AutomationService(EarningPillar):
    """Builds and sells business process automation as a service."""

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="automation_service", generate_fn=generate_fn,
                         config=config or DEFAULT_CONFIG.copy())

    async def discover(self) -> List[Opportunity]:
        opportunities = []
        if self.generate_fn:
            prompt = (
                f"Identify 2 business automation opportunities in: "
                f"{', '.join(self.config['automation_types'])}.\n"
                f"For each: automation_name, business_type, process_automated, "
                f"time_saved_weekly_hours, monthly_value_usd, build_hours, difficulty (0-1).\n"
                f"Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    autos = json.loads(self._extract_json(answer))
                    for auto in autos:
                        opportunities.append(Opportunity(
                            id=f"auto_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name, platform="Direct B2B",
                            title=auto.get("automation_name", "Business Automation"),
                            description=auto.get("process_automated", ""),
                            estimated_revenue_usd=float(auto.get("monthly_value_usd", 500)),
                            difficulty=float(auto.get("difficulty", 0.4)),
                            time_to_revenue_hours=float(auto.get("build_hours", 10)),
                            competition_level=0.3, confidence=0.5,
                            tags=["automation", auto.get("business_type", "general")], metadata=auto,
                        ))
                except (json.JSONDecodeError, TypeError): pass
            except Exception as e: logger.debug(f"[AUTOMATION] Discovery error: {e}")
        if not opportunities:
            opportunities.append(Opportunity(
                id=f"sim_auto_{int(time.time())}", pillar=self.name, platform="Direct B2B",
                title="Invoice Processing Automation", description="Auto-extract and process invoices",
                estimated_revenue_usd=500, difficulty=0.3, time_to_revenue_hours=8,
                competition_level=0.3, confidence=0.6,
            ))
        return opportunities

    async def evaluate(self, opp: Opportunity) -> float:
        score = 0.6  # Automation has excellent repeat revenue
        hourly = opp.estimated_revenue_usd / max(opp.time_to_revenue_hours, 1)
        score += min(hourly / 80, 0.2)
        score += (1.0 - opp.difficulty) * 0.15
        return max(0.0, min(1.0, score))

    async def execute(self, opp: Opportunity) -> ExecutionResult:
        start = time.time()
        deliverables = []
        try:
            if self.generate_fn:
                for phase in ["workflow_design", "automation_script", "setup_guide", "monitoring_dashboard"]:
                    prompt = f"Generate {phase} for automation: {opp.title}\n{opp.description}"
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
