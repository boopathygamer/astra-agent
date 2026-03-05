"""
Cognitive Load Balancer — Dynamic Model Routing
─────────────────────────────────────────────────
Routes tasks to the appropriate processing depth based on real-time
complexity analysis. Simple questions get fast answers; hard problems
get the full pipeline.

Tiers:
  INSTANT  → Cache hit, no compute
  LIGHT    → Single LLM call, no verification
  MEDIUM   → Think loop (synthesize → verify)
  HEAVY    → Full pipeline + multi-hypothesis
  EXTREME  → Multi-agent collaboration
"""

import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class ProcessingTier(Enum):
    INSTANT = 0     # Cache hit — 0ms
    LIGHT = 1       # Single LLM call — ~500ms
    MEDIUM = 2      # Think loop — ~2-5s
    HEAVY = 3       # Full pipeline — ~10-30s
    EXTREME = 4     # Multi-agent — ~30-120s


@dataclass
class ComplexityEstimate:
    """Result of complexity analysis for a task."""
    tier: ProcessingTier = ProcessingTier.MEDIUM
    confidence: float = 0.5
    reasoning: str = ""
    estimated_tokens: int = 0
    estimated_latency_ms: float = 1000.0
    complexity_factors: Dict[str, float] = field(default_factory=dict)
    requires_tools: bool = False
    requires_verification: bool = False
    requires_research: bool = False
    domain: str = "general"


@dataclass
class LoadSnapshot:
    """Snapshot of current system load."""
    active_tasks: int = 0
    avg_latency_ms: float = 0.0
    queue_depth: int = 0
    memory_pressure: float = 0.0   # 0-1
    tier_distribution: Dict[ProcessingTier, int] = field(default_factory=dict)
    timestamp: float = 0.0

    @property
    def is_overloaded(self) -> bool:
        return self.active_tasks > 5 or self.avg_latency_ms > 10000


@dataclass
class RoutingDecision:
    """The routing decision for a task."""
    task_id: str = ""
    assigned_tier: ProcessingTier = ProcessingTier.MEDIUM
    estimated_tier: ProcessingTier = ProcessingTier.MEDIUM
    was_escalated: bool = False
    was_downgraded: bool = False
    reason: str = ""
    timestamp: float = 0.0


# ──────────────────────────────────────────────
# Complexity Estimator
# ──────────────────────────────────────────────

class ComplexityEstimator:
    """
    Estimates task cognitive complexity using keyword analysis,
    structural features, and historical patterns.
    """

    # Keyword-based complexity signals
    INSTANT_SIGNALS = {
        "hi", "hello", "hey", "thanks", "thank you", "ok", "yes", "no",
        "bye", "goodbye", "good morning", "good night",
    }

    LIGHT_PATTERNS = [
        r"what (?:is|are|was|were)\b",
        r"define\b", r"explain briefly\b",
        r"translate\b", r"convert\b",
        r"(?:how|what) (?:much|many)\b",
    ]

    HEAVY_PATTERNS = [
        r"(?:write|create|build|implement)\s+(?:a|an|the)\s+(?:full|complete|entire)",
        r"debug.*(?:code|function|system|application)",
        r"(?:design|architect)\s+(?:a|an)\s+system",
        r"(?:analyze|review)\s+(?:this|the)\s+(?:code|codebase|architecture)",
        r"(?:step.by.step|detailed|comprehensive|thorough)",
        r"(?:compare|contrast)\s+(?:multiple|several|different)",
    ]

    EXTREME_PATTERNS = [
        r"(?:refactor|rewrite)\s+(?:the\s+)?entire",
        r"(?:build|create)\s+(?:a\s+)?(?:full|complete)\s+(?:application|system|platform)",
        r"multi.?(?:agent|model|step)\s+(?:pipeline|system)",
        r"research\s+(?:and|then)\s+implement",
    ]

    def estimate(self, task: str, context: str = "") -> ComplexityEstimate:
        """Estimate task complexity from text analysis."""
        task_lower = task.lower().strip()
        factors = {}

        # Check instant (greetings, simple acks)
        words = set(task_lower.split())
        if words.issubset(self.INSTANT_SIGNALS) or len(task_lower) < 10:
            return ComplexityEstimate(
                tier=ProcessingTier.INSTANT,
                confidence=0.95,
                reasoning="Simple greeting or acknowledgment",
                estimated_latency_ms=5,
            )

        # Score complexity factors
        length_factor = min(1.0, len(task_lower) / 500)
        factors["length"] = length_factor

        question_marks = task_lower.count("?")
        factors["questions"] = min(1.0, question_marks / 3)

        code_indicators = sum(1 for kw in ["def ", "class ", "function", "import ", "```"]
                              if kw in task_lower)
        factors["code_complexity"] = min(1.0, code_indicators / 3)

        # Pattern matching
        light_hits = sum(1 for p in self.LIGHT_PATTERNS if re.search(p, task_lower))
        heavy_hits = sum(1 for p in self.HEAVY_PATTERNS if re.search(p, task_lower))
        extreme_hits = sum(1 for p in self.EXTREME_PATTERNS if re.search(p, task_lower))

        factors["light_patterns"] = min(1.0, light_hits / 2)
        factors["heavy_patterns"] = min(1.0, heavy_hits / 2)
        factors["extreme_patterns"] = min(1.0, extreme_hits)

        # Determine tier
        if extreme_hits > 0:
            tier = ProcessingTier.EXTREME
            confidence = 0.7 + 0.1 * extreme_hits
        elif heavy_hits >= 2 or (heavy_hits >= 1 and code_indicators >= 2):
            tier = ProcessingTier.HEAVY
            confidence = 0.6 + 0.1 * heavy_hits
        elif light_hits >= 1 and heavy_hits == 0 and length_factor < 0.3:
            tier = ProcessingTier.LIGHT
            confidence = 0.7 + 0.1 * light_hits
        else:
            tier = ProcessingTier.MEDIUM
            confidence = 0.5

        # Latency estimates per tier
        latency_map = {
            ProcessingTier.INSTANT: 5,
            ProcessingTier.LIGHT: 500,
            ProcessingTier.MEDIUM: 3000,
            ProcessingTier.HEAVY: 15000,
            ProcessingTier.EXTREME: 60000,
        }

        return ComplexityEstimate(
            tier=tier,
            confidence=min(0.99, confidence),
            reasoning=f"Matched {light_hits} light, {heavy_hits} heavy, {extreme_hits} extreme patterns",
            estimated_latency_ms=latency_map.get(tier, 3000),
            complexity_factors=factors,
            requires_tools=code_indicators > 0,
            requires_verification=heavy_hits > 0,
            requires_research="research" in task_lower or "analyze" in task_lower,
        )


# ──────────────────────────────────────────────
# Load Balancer
# ──────────────────────────────────────────────

class LoadBalancer:
    """
    Tracks current computational load and adjusts routing decisions
    to maintain system responsiveness.
    """

    def __init__(self, max_concurrent_heavy: int = 3, max_concurrent_extreme: int = 1):
        self._active: Dict[str, RoutingDecision] = {}
        self._latency_history: deque = deque(maxlen=50)
        self._max_heavy = max_concurrent_heavy
        self._max_extreme = max_concurrent_extreme

    def can_accept(self, tier: ProcessingTier) -> bool:
        """Check if the system can accept another task at this tier."""
        tier_counts = {}
        for decision in self._active.values():
            t = decision.assigned_tier
            tier_counts[t] = tier_counts.get(t, 0) + 1

        if tier == ProcessingTier.HEAVY:
            return tier_counts.get(ProcessingTier.HEAVY, 0) < self._max_heavy
        elif tier == ProcessingTier.EXTREME:
            return tier_counts.get(ProcessingTier.EXTREME, 0) < self._max_extreme
        return True  # No limits on lighter tiers

    def register_task(self, task_id: str, decision: RoutingDecision):
        self._active[task_id] = decision

    def complete_task(self, task_id: str, latency_ms: float = 0):
        self._active.pop(task_id, None)
        if latency_ms > 0:
            self._latency_history.append(latency_ms)

    def get_snapshot(self) -> LoadSnapshot:
        return LoadSnapshot(
            active_tasks=len(self._active),
            avg_latency_ms=(
                sum(self._latency_history) / len(self._latency_history)
                if self._latency_history else 0
            ),
            queue_depth=0,
            timestamp=time.time(),
        )


# ──────────────────────────────────────────────
# Tier Router (Main Interface)
# ──────────────────────────────────────────────

class CognitiveRouter:
    """
    Main interface for dynamic model routing.

    Usage:
        router = CognitiveRouter()
        decision = router.route("What is Python?")
        # decision.assigned_tier → ProcessingTier.LIGHT

        decision = router.route("Design a complete microservices architecture for an e-commerce platform")
        # decision.assigned_tier → ProcessingTier.EXTREME
    """

    def __init__(self, max_heavy: int = 3, max_extreme: int = 1):
        self.estimator = ComplexityEstimator()
        self.balancer = LoadBalancer(max_heavy, max_extreme)
        self._routing_history: List[RoutingDecision] = []

    def route(self, task: str, context: str = "", task_id: str = "") -> RoutingDecision:
        """Route a task to the appropriate processing tier."""
        import hashlib
        if not task_id:
            task_id = hashlib.sha256(f"{task}{time.time()}".encode()).hexdigest()[:12]

        # Estimate complexity
        estimate = self.estimator.estimate(task, context)
        assigned_tier = estimate.tier
        was_downgraded = False
        was_escalated = False

        # Check load — downgrade if system is overloaded
        if not self.balancer.can_accept(assigned_tier):
            if assigned_tier == ProcessingTier.EXTREME:
                assigned_tier = ProcessingTier.HEAVY
                was_downgraded = True
            elif assigned_tier == ProcessingTier.HEAVY:
                assigned_tier = ProcessingTier.MEDIUM
                was_downgraded = True

        snapshot = self.balancer.get_snapshot()
        if snapshot.is_overloaded and assigned_tier.value >= ProcessingTier.HEAVY.value:
            assigned_tier = ProcessingTier(max(assigned_tier.value - 1, 1))
            was_downgraded = True

        decision = RoutingDecision(
            task_id=task_id,
            assigned_tier=assigned_tier,
            estimated_tier=estimate.tier,
            was_escalated=was_escalated,
            was_downgraded=was_downgraded,
            reason=estimate.reasoning,
            timestamp=time.time(),
        )

        self.balancer.register_task(task_id, decision)
        self._routing_history.append(decision)

        tier_emoji = {
            ProcessingTier.INSTANT: "⚡",
            ProcessingTier.LIGHT: "💡",
            ProcessingTier.MEDIUM: "🔄",
            ProcessingTier.HEAVY: "🔥",
            ProcessingTier.EXTREME: "🌋",
        }
        logger.info(
            f"📊 Routed to {tier_emoji.get(assigned_tier, '?')} "
            f"{assigned_tier.name} (est: {estimate.tier.name}"
            f"{', downgraded' if was_downgraded else ''})"
        )

        return decision

    def complete(self, task_id: str, latency_ms: float = 0):
        """Mark a task as completed."""
        self.balancer.complete_task(task_id, latency_ms)

    def escalate(self, task_id: str) -> RoutingDecision:
        """Escalate a task to a higher tier (e.g., LIGHT → MEDIUM)."""
        if task_id in self.balancer._active:
            current = self.balancer._active[task_id]
            if current.assigned_tier.value < ProcessingTier.EXTREME.value:
                new_tier = ProcessingTier(current.assigned_tier.value + 1)
                current.assigned_tier = new_tier
                current.was_escalated = True
                logger.info(f"📊 Escalated {task_id} to {new_tier.name}")
            return current
        return RoutingDecision(task_id=task_id)

    def get_stats(self) -> Dict[str, Any]:
        tier_counts = {}
        for d in self._routing_history[-100:]:
            t = d.assigned_tier.name
            tier_counts[t] = tier_counts.get(t, 0) + 1

        return {
            "total_routed": len(self._routing_history),
            "active_tasks": len(self.balancer._active),
            "tier_distribution": tier_counts,
            "downgrade_rate": round(
                sum(1 for d in self._routing_history[-100:] if d.was_downgraded)
                / max(len(self._routing_history[-100:]), 1), 4
            ),
            "load": {
                "avg_latency_ms": round(
                    sum(self.balancer._latency_history) / max(len(self.balancer._latency_history), 1)
                ),
            },
        }
