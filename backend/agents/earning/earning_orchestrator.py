"""
Autonomous Earning System — Earning Orchestrator
─────────────────────────────────────────────────
The master controller that manages all 12 earning pillars.
Allocates AI compute time based on Strategy Leaderboard rankings.
Handles the complete lifecycle: Discover → Ethics → Execute → Ledger → Evolve.
"""

import os
import json
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import asdict

from agents.earning.base_pillar import (
    EarningPillar, Opportunity, ExecutionResult, PillarStatus
)
from agents.earning.opportunity_scanner import OpportunityScanner
from agents.earning.ethics_filter import EthicsFilter, EthicsVerdict
from brain.performance_ledger import PerformanceLedger
from brain.strategy_evolver import StrategyEvolver
from brain.failure_autopsy import FailureAutopsyEngine

logger = logging.getLogger(__name__)

# Treasury path — all money flows here
USER_TREASURY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "user_treasury.json"
)


class EarningOrchestrator:
    """
    The neural cortex of the earning system.
    
    Responsibilities:
    1. Manages registration and lifecycle of all earning pillars
    2. Runs the Opportunity Scanner on a schedule
    3. Routes opportunities to the correct pillar
    4. Enforces ethics/legality checks before execution
    5. Records all results in the Performance Ledger
    6. Allocates compute priority based on pillar performance
    7. Interfaces with the User Treasury for fund deposits
    """

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        scan_interval_seconds: float = 3600,  # How often to scan for opportunities
        cycle_interval_seconds: float = 1800,  # How often pillars run execution cycles
    ):
        self.generate_fn = generate_fn
        self.scan_interval = scan_interval_seconds
        self.cycle_interval = cycle_interval_seconds
        
        # Core components
        self.scanner = OpportunityScanner(generate_fn)
        self.ethics = EthicsFilter(strict_mode=True)
        self.ledger = PerformanceLedger()
        self.evolver = StrategyEvolver(generate_fn=generate_fn)
        self.autopsy = FailureAutopsyEngine(generate_fn=generate_fn)
        
        # Registered pillars
        self._pillars: Dict[str, EarningPillar] = {}
        
        # State
        self._is_running = False
        self._pending_opportunities: List[Opportunity] = []
        self._pending_approvals: List[Dict[str, Any]] = []  # Needs human approval
        self._total_cycles = 0
        self._startup_time: float = 0
        
        logger.info("[ORCHESTRATOR] 🏗️ Earning Orchestrator initialized")

    # ─── Pillar Management ──────────────────────────────

    def register_pillar(self, pillar: EarningPillar):
        """Register an earning pillar with the orchestrator."""
        self._pillars[pillar.name] = pillar
        logger.info(f"[ORCHESTRATOR] 📋 Registered pillar: {pillar.name}")

    def unregister_pillar(self, name: str):
        """Remove a pillar from the orchestrator."""
        if name in self._pillars:
            del self._pillars[name]
            logger.info(f"[ORCHESTRATOR] Removed pillar: {name}")

    def get_pillar(self, name: str) -> Optional[EarningPillar]:
        return self._pillars.get(name)

    # ─── Main Loop ──────────────────────────────────────

    async def start(self):
        """Start the earning system main loop."""
        if self._is_running:
            logger.warning("[ORCHESTRATOR] Already running")
            return
        
        self._is_running = True
        self._startup_time = time.time()
        logger.info("=" * 70)
        logger.info("[ORCHESTRATOR] 🚀 AUTONOMOUS EARNING SYSTEM ONLINE")
        logger.info(f"[ORCHESTRATOR] Active pillars: {list(self._pillars.keys())}")
        logger.info("=" * 70)
        
        # Run the scan loop and execution loop concurrently
        await asyncio.gather(
            self._scan_loop(),
            self._execution_loop(),
            return_exceptions=True,
        )

    async def stop(self):
        """Gracefully stop the earning system."""
        logger.info("[ORCHESTRATOR] 🛑 Shutting down earning system...")
        self._is_running = False

    async def _scan_loop(self):
        """Continuously scan for new opportunities."""
        while self._is_running:
            try:
                logger.info("[ORCHESTRATOR] 🔍 Running opportunity scan...")
                opportunities = await self.scanner.scan_all()
                
                # Ethics check each opportunity
                for opp in opportunities:
                    report = self.ethics.evaluate(opp)
                    
                    if report.verdict == EthicsVerdict.APPROVED:
                        self._pending_opportunities.append(opp)
                    elif report.verdict == EthicsVerdict.REQUIRES_HUMAN_REVIEW:
                        self._pending_approvals.append({
                            "opportunity": asdict(opp),
                            "ethics_report": {
                                "risk_score": report.risk_score,
                                "warnings": report.warnings,
                                "recommendations": report.recommendations,
                            },
                            "timestamp": time.time(),
                        })
                    # BLOCKED = silently dropped
                
                logger.info(
                    f"[ORCHESTRATOR] Scan complete: {len(self._pending_opportunities)} "
                    f"approved, {len(self._pending_approvals)} awaiting human review"
                )
                
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] Scan loop error: {e}")
            
            await asyncio.sleep(self.scan_interval)

    async def _execution_loop(self):
        """Execute earning cycles for all active pillars."""
        # Initial delay to let the first scan complete
        await asyncio.sleep(5)
        
        while self._is_running:
            try:
                self._total_cycles += 1
                logger.info(
                    f"[ORCHESTRATOR] ⚡ Execution cycle #{self._total_cycles} "
                    f"({len(self._pillars)} active pillars)"
                )
                
                # Evolve strategies every 5 cycles
                if self._total_cycles % 5 == 0 and self._total_cycles > 0:
                    logger.info("[ORCHESTRATOR] 🧬 Triggering Strategy Evolution cycle...")
                    self.evolver.evolve(self.evolver.calculate_fitness_from_ledger(self.ledger))
                
                # Route pending opportunities to the right pillars
                self._route_opportunities()
                
                # Run execution cycles for all pillars (prioritized by performance)
                prioritized = self._get_prioritized_pillars()
                
                # Swarm execution: Build tasks for all active pillars
                async def _run_pillar_cycle(pillar: Any):
                    if not self._is_running:
                        return
                    try:
                        results = await pillar.run_cycle()
                        
                        for result in results:
                            # Record in ledger
                            self.ledger.record(result)
                            
                            # Deposit successful earnings to treasury
                            if result.success and result.revenue_earned_usd > 0:
                                self._deposit_to_treasury(result)
                            elif not result.success:
                                # Trigger Autopsy on failure result
                                asyncio.create_task(
                                    self.autopsy.analyze_failure(
                                        opportunity_data={"id": result.opportunity_id},
                                        error="Execution returned success=False",
                                        pillar=pillar.name
                                    )
                                )
                        
                    except Exception as e:
                        logger.error(f"[ORCHESTRATOR] Pillar '{pillar.name}' error: {e}")
                        asyncio.create_task(
                            self.autopsy.analyze_failure(
                                opportunity_data={},
                                error=str(e),
                                pillar=pillar.name
                            )
                        )

                # Launch swarm across all prioritized pillars concurrently
                pillar_tasks = [_run_pillar_cycle(pillar) for pillar in prioritized]
                await asyncio.gather(*pillar_tasks)
                
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] Execution loop error: {e}")
            
            await asyncio.sleep(self.cycle_interval)

    def _route_opportunities(self):
        """Route pending opportunities to their target pillars."""
        routed = 0
        remaining = []
        
        for opp in self._pending_opportunities:
            pillar = self._pillars.get(opp.pillar)
            if pillar:
                pillar._active_opportunities.append(opp)
                routed += 1
            else:
                remaining.append(opp)
        
        self._pending_opportunities = remaining
        if routed:
            logger.info(f"[ORCHESTRATOR] 📨 Routed {routed} opportunities to pillars")

    def _get_prioritized_pillars(self) -> List[EarningPillar]:
        """
        Return pillars sorted by priority.
        Priority is based on: historical revenue, win rate, and recency.
        Top performers get more compute cycles.
        """
        pillar_scores = []
        for name, pillar in self._pillars.items():
            stats = self.ledger.get_pillar_stats(name)
            # Score = revenue * win_rate * recency_bonus
            revenue_score = stats.get("total_revenue", 0)
            win_rate = stats.get("win_rate", 0.5)
            # New pillars get a boost to explore them
            attempts = stats.get("total_attempts", 0)
            exploration_bonus: float = max(0, 10 - attempts) * 100  # Bonus for < 10 attempts
            
            score: float = float(revenue_score * win_rate) + float(exploration_bonus)
            pillar_scores.append((pillar, score))
        
        pillar_scores.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in pillar_scores]

    def _deposit_to_treasury(self, result: ExecutionResult):
        """Deposit earnings into the User Treasury."""
        try:
            os.makedirs(os.path.dirname(USER_TREASURY_PATH), exist_ok=True)
            
            vault = {}
            if os.path.exists(USER_TREASURY_PATH):
                with open(USER_TREASURY_PATH, "r") as f:
                    vault = json.load(f)
            
            vault[result.opportunity_id] = {
                "pillar": result.pillar,
                "revenue_usd": result.revenue_earned_usd,
                "timestamp": time.time(),
                "status": "awaiting_human_collection",
                "deliverables": result.deliverables[:5],  # Store first 5
            }
            
            with open(USER_TREASURY_PATH, "w") as f:
                json.dump(vault, f, indent=4)
            
            logger.info(
                f"[TREASURY] 💰 Deposited ${result.revenue_earned_usd:.2f} "
                f"from {result.pillar} into User Treasury"
            )
        except Exception as e:
            logger.error(f"[TREASURY] Deposit error: {e}")

    # ─── Run Single Cycle (for testing / manual trigger) ──

    async def run_single_scan(self) -> List[Opportunity]:
        """Run a single scan cycle without the loop."""
        opportunities = await self.scanner.scan_all()
        approved = []
        for opp in opportunities:
            report = self.ethics.evaluate(opp)
            if report.verdict == EthicsVerdict.APPROVED:
                approved.append(opp)
        return approved

    async def run_single_execution(self, pillar_name: str) -> List[ExecutionResult]:
        """Run a single execution cycle for a specific pillar."""
        pillar = self._pillars.get(pillar_name)
        if not pillar:
            logger.error(f"Pillar '{pillar_name}' not found")
            return []
        
        results = await pillar.run_cycle()
        for result in results:
            self.ledger.record(result)
            if result.success and result.revenue_earned_usd > 0:
                self._deposit_to_treasury(result)
        return results

    # ─── Human Approval Queue ───────────────────────────

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Return opportunities waiting for human approval."""
        return self._pending_approvals

    def approve_opportunity(self, opportunity_id: str) -> bool:
        """Human approves a pending opportunity for execution."""
        for i, pending in enumerate(self._pending_approvals):
            if pending["opportunity"]["id"] == opportunity_id:
                opp_data = pending["opportunity"]
                opp = Opportunity(**{k: v for k, v in opp_data.items() 
                                    if k in Opportunity.__dataclass_fields__})
                self._pending_opportunities.append(opp)
                self._pending_approvals.pop(i)
                logger.info(f"[ORCHESTRATOR] ✅ Human approved: {opportunity_id}")
                return True
        return False

    def reject_opportunity(self, opportunity_id: str) -> bool:
        """Human rejects a pending opportunity."""
        for i, pending in enumerate(self._pending_approvals):
            if pending["opportunity"]["id"] == opportunity_id:
                self._pending_approvals.pop(i)
                logger.info(f"[ORCHESTRATOR] ❌ Human rejected: {opportunity_id}")
                return True
        return False

    # ─── Dashboard Data ─────────────────────────────────

    def get_dashboard(self) -> Dict[str, Any]:
        """Full dashboard data for the earning system."""
        uptime = time.time() - self._startup_time if self._startup_time else 0
        
        return {
            "status": "running" if self._is_running else "stopped",
            "uptime_hours": round(uptime / 3600, 2),
            "total_cycles": self._total_cycles,
            "active_pillars": {
                name: pillar.get_status() for name, pillar in self._pillars.items()
            },
            "pending_opportunities": len(self._pending_opportunities),
            "pending_approvals": len(self._pending_approvals),
            "financial_report": self.ledger.get_full_report(),
            "scanner_stats": self.scanner.get_stats(),
            "ethics_stats": self.ethics.get_stats(),
        }
