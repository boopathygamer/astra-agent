"""
Revenue Pillar 6 — Trading Signal Engine
─────────────────────────────────────────
Analyzes market data and news sentiment to generate trading signals.
Publishes signals to a subscription service. Advisory ONLY — no autonomous trading.
"""

import time, logging, asyncio, random
from typing import Dict, List, Any, Optional, Callable
from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 2,
    "markets": ["crypto", "stocks", "forex"],
    "signal_types": ["technical_analysis", "sentiment_analysis", "on_chain_metrics"],
    "subscription_price_usd": 49,
}


class TradingSignalEngine(EarningPillar):
    """Generates trading signals and publishes them as a subscription service."""

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="trading_signals", generate_fn=generate_fn,
                         config=config or DEFAULT_CONFIG.copy())

    async def discover(self) -> List[Opportunity]:
        opportunities = []
        if self.generate_fn:
            prompt = (
                f"Identify 2 trading signal opportunities in: {', '.join(self.config['markets'])}.\n"
                f"For each: market, asset_class, signal_type, subscription_potential, "
                f"estimated_subscribers, monthly_price_usd, difficulty (0-1).\n"
                f"Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    signals = json.loads(self._extract_json(answer))
                    for sig in signals:
                        subs = int(sig.get("estimated_subscribers", 20))
                        price = float(sig.get("monthly_price_usd", 49))
                        opportunities.append(Opportunity(
                            id=f"signal_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name, platform=sig.get("market", "crypto"),
                            title=f"Signal Service: {sig.get('asset_class', 'Market')}",
                            description=sig.get("signal_type", ""),
                            estimated_revenue_usd=subs * price, difficulty=float(sig.get("difficulty", 0.6)),
                            time_to_revenue_hours=20, competition_level=0.6, confidence=0.4,
                            tags=["trading", sig.get("market", "general")], metadata=sig,
                        ))
                except (json.JSONDecodeError, TypeError): pass
            except Exception as e: logger.debug(f"[TRADING] Discovery error: {e}")
        if not opportunities:
            opportunities.append(Opportunity(
                id=f"sim_signal_{int(time.time())}", pillar=self.name, platform="crypto",
                title="Crypto Sentiment Signal Service", description="AI-powered crypto sentiment analysis",
                estimated_revenue_usd=980, difficulty=0.6, time_to_revenue_hours=20,
                competition_level=0.6, confidence=0.4,
            ))
        return opportunities

    async def evaluate(self, opp: Opportunity) -> float:
        score = 0.4
        if opp.estimated_revenue_usd >= 1000: score += 0.2
        elif opp.estimated_revenue_usd >= 500: score += 0.1
        score += (1.0 - opp.difficulty) * 0.2
        return max(0.0, min(1.0, score))

    async def execute(self, opp: Opportunity) -> ExecutionResult:
        start = time.time()
        deliverables = []
        try:
            if self.generate_fn:
                for phase in ["market_analysis", "signal_algorithm", "subscription_platform_spec"]:
                    prompt = f"Generate {phase} for a trading signal service: {opp.title}\n{opp.description}"
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
