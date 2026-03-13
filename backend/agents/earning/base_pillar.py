"""
Autonomous Earning System — Base Pillar Interface
──────────────────────────────────────────────────
Abstract base class that all 12 Revenue Pillars implement.
Provides a unified lifecycle: discover → evaluate → execute → report.
"""

import os
import json
import time
import logging
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class PillarStatus(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    EVALUATING = "evaluating"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class Opportunity:
    """A discovered earning opportunity."""
    id: str
    pillar: str
    platform: str
    title: str
    description: str
    estimated_revenue_usd: float
    difficulty: float  # 0.0 (trivial) to 1.0 (extremely hard)
    time_to_revenue_hours: float
    competition_level: float  # 0.0 (no competition) to 1.0 (saturated)
    confidence: float  # 0.0 to 1.0 — how confident the AI is in this estimate
    requires_capital: bool = False
    capital_required_usd: float = 0.0
    tags: List[str] = field(default_factory=list)
    discovered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def roi_score(self) -> float:
        """Composite ROI score: higher = better opportunity."""
        if self.time_to_revenue_hours <= 0:
            return 0.0
        revenue_per_hour = self.estimated_revenue_usd / self.time_to_revenue_hours
        net_revenue = self.estimated_revenue_usd - self.capital_required_usd
        feasibility = (1.0 - self.difficulty) * (1.0 - self.competition_level)
        return (net_revenue * feasibility * self.confidence) / max(self.time_to_revenue_hours, 0.1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pillar": self.pillar,
            "platform": self.platform,
            "title": self.title,
            "description": self.description,
            "estimated_revenue_usd": self.estimated_revenue_usd,
            "difficulty": self.difficulty,
            "time_to_revenue_hours": self.time_to_revenue_hours,
            "competition_level": self.competition_level,
            "confidence": self.confidence,
            "requires_capital": self.requires_capital,
            "capital_required_usd": self.capital_required_usd,
            "tags": self.tags,
            "discovered_at": self.discovered_at,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionResult:
    """Result of executing an earning strategy."""
    opportunity_id: str
    pillar: str
    success: bool
    revenue_earned_usd: float = 0.0
    time_spent_hours: float = 0.0
    deliverables: List[str] = field(default_factory=list)
    error: Optional[str] = None
    lessons_learned: List[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def effective_hourly_rate(self) -> float:
        if self.time_spent_hours <= 0:
            return 0.0
        return self.revenue_earned_usd / self.time_spent_hours

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "pillar": self.pillar,
            "success": self.success,
            "revenue_earned_usd": self.revenue_earned_usd,
            "time_spent_hours": self.time_spent_hours,
            "deliverables": self.deliverables,
            "error": self.error,
            "lessons_learned": self.lessons_learned,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


@dataclass
class PillarMetrics:
    """Aggregate metrics for a single earning pillar."""
    pillar_name: str
    total_opportunities_found: int = 0
    total_executions: int = 0
    successful_executions: int = 0
    total_revenue_usd: float = 0.0
    total_time_hours: float = 0.0
    win_rate: float = 0.0
    avg_revenue_per_execution: float = 0.0
    avg_hourly_rate: float = 0.0
    last_active: float = 0.0

    def update(self, result: ExecutionResult):
        self.total_executions += 1
        self.total_time_hours += result.time_spent_hours
        self.last_active = time.time()
        if result.success:
            self.successful_executions += 1
            self.total_revenue_usd += result.revenue_earned_usd
        self.win_rate = self.successful_executions / max(self.total_executions, 1)
        self.avg_revenue_per_execution = self.total_revenue_usd / max(self.total_executions, 1)
        self.avg_hourly_rate = self.total_revenue_usd / max(self.total_time_hours, 0.1)


class EarningPillar(ABC):
    """
    Abstract base class for all earning pillars.
    
    Every pillar follows the same lifecycle:
    1. discover()  — Find opportunities on relevant platforms
    2. evaluate()  — Score and filter opportunities  
    3. execute()   — Carry out the earning strategy
    4. report()    — Return execution results for the ledger
    """

    def __init__(self, name: str, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.generate_fn = generate_fn
        self.config = config or {}
        self.status = PillarStatus.IDLE
        self.metrics = PillarMetrics(pillar_name=name)
        # Removed stateful lists (_active_opportunities, _execution_history) to ensure
        # instances are completely stateless for infinite horizontal scaling.
        logger.info(f"[EARNING PILLAR] Initialized (Stateless): {self.name}")

    @abstractmethod
    async def discover(self) -> List[Opportunity]:
        """
        Scan relevant platforms and sources for new earning opportunities.
        Returns a list of discovered Opportunity objects.
        """
        pass

    @abstractmethod
    async def evaluate(self, opportunity: Opportunity) -> float:
        """
        Evaluate an opportunity and return a confidence score (0.0 to 1.0).
        Considers: AI capability match, market conditions, competition, time investment.
        """
        pass

    @abstractmethod
    async def execute(self, opportunity: Opportunity) -> ExecutionResult:
        """
        Execute the earning strategy for a specific opportunity.
        Returns an ExecutionResult with success/failure and revenue data.
        """
        pass

    async def run_cycle(self) -> List[ExecutionResult]:
        """
        Run a complete earning cycle: discover → evaluate → execute → report.
        This is the main entry point called by the EarningOrchestrator.
        """
        results = []
        
        try:
            # 1. Discover
            self.status = PillarStatus.SCANNING
            logger.info(f"[{self.name}] 🔍 Scanning for opportunities...")
            opportunities = await self.discover()
            self.metrics.total_opportunities_found += len(opportunities)
            logger.info(f"[{self.name}] Found {len(opportunities)} opportunities")

            if not opportunities:
                self.status = PillarStatus.IDLE
                return results

            # 2. Evaluate & Rank
            self.status = PillarStatus.EVALUATING
            scored_opps = []
            for opp in opportunities:
                score = await self.evaluate(opp)
                opp.confidence = score
                scored_opps.append(opp)
            
            # Sort by ROI score (descending)
            scored_opps.sort(key=lambda o: o.roi_score, reverse=True)
            
            # Take top opportunities (configurable, default 3)
            max_executions = self.config.get("max_executions_per_cycle", 3)
            top_opps = scored_opps[:max_executions]

            # 3. Execute (Swarm Intelligence Processing)
            self.status = PillarStatus.EXECUTING
            
            async def _swarm_execute(opp: Opportunity) -> ExecutionResult:
                # Skip if requires capital (needs human approval)
                if opp.requires_capital:
                    logger.warning(
                        f"[{self.name}] ⚖️ Opportunity '{opp.title}' requires "
                        f"${opp.capital_required_usd} capital. Returning for central approval..."
                    )
                    return ExecutionResult(opportunity_id=opp.id, pillar=self.name, success=False, error="Requires human capital approval")
                
                try:
                    logger.info(f"[{self.name}] ⚡ Swarm executing: {opp.title}")
                    return await self.execute(opp)
                except Exception as e:
                    logger.error(f"[{self.name}] 💥 Execution error: {e}")
                    return ExecutionResult(
                        opportunity_id=opp.id,
                        pillar=self.name,
                        success=False,
                        error=str(e)
                    )

            # Fire off entire swarm of opportunities simultaneously
            swarm_tasks = [_swarm_execute(opp) for opp in top_opps]
            swarm_results = await asyncio.gather(*swarm_tasks)

            for result in swarm_results:
                if result.error == "Requires human capital approval":
                    self.status = PillarStatus.AWAITING_APPROVAL
                    continue
                    
                results.append(result)
                self.metrics.update(result)
                
                if result.success:
                    logger.info(
                        f"[{self.name}] ✅ SUCCESS: ${result.revenue_earned_usd} earned "
                        f"from '{result.opportunity_id}'"
                    )
                else:
                    logger.warning(
                        f"[{self.name}] ❌ FAILED: '{result.opportunity_id}' — {result.error}"
                    )

            self.status = PillarStatus.COMPLETED

        except Exception as e:
            logger.error(f"[{self.name}] Critical cycle failure: {e}")
            self.status = PillarStatus.FAILED

        return results

    def get_status(self) -> Dict[str, Any]:
        """Return current pillar status and metrics."""
        return {
            "name": self.name,
            "status": self.status.value,
            "metrics": {
                "total_opportunities_found": self.metrics.total_opportunities_found,
                "total_executions": self.metrics.total_executions,
                "successful_executions": self.metrics.successful_executions,
                "total_revenue_usd": self.metrics.total_revenue_usd,
                "win_rate": self.metrics.win_rate,
            },
            "stateless": True,
        }

    def get_strategy_dna(self) -> Dict[str, Any]:
        """
        Return the pillar's current 'strategy DNA' — the configurable
        parameters that define HOW this pillar operates.
        """
        return {
            "pillar": self.name,
            "config": self.config.copy(),
            "metrics_snapshot": {
                "win_rate": self.metrics.win_rate,
                "total_revenue_usd": self.metrics.total_revenue_usd,
            },
        }

    def apply_evolved_config(self, new_config: Dict[str, Any]):
        """Apply a mutated configuration from the Strategy Evolver."""
        logger.info(f"[{self.name}] 🧬 Applying evolved configuration: {list(new_config.keys())}")
        self.config.update(new_config)
