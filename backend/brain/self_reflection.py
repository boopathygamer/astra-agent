"""
Self-Reflection Engine — Post-Task Learning & Adaptation.
==========================================================
After every task, analyzes what worked/failed, updates the cognitive
genome fitness, triggers prompt evolution, and feeds insights back
into the autonomous loop.

Classes:
  ReflectionInsight  — A learned insight from reflection
  SelfReflectionEngine — The main reflection system
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ReflectionInsight:
    """A learned insight from task reflection."""
    id: str = ""
    category: str = ""  # success_pattern, failure_pattern, optimization, warning
    insight: str = ""
    confidence: float = 0.5
    evidence: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    applied: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass
class TaskOutcome:
    """Record of a completed task and its outcome."""
    task_description: str = ""
    tool_used: str = ""
    success: bool = False
    duration: float = 0.0
    error: str = ""
    quality_score: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class SelfReflectionEngine:
    """
    Post-task analysis and continuous improvement system.

    Processes:
      1. ANALYZE  — Examine task outcome (success/failure/quality)
      2. PATTERN  — Identify recurring patterns across outcomes
      3. INSIGHT  — Generate actionable insights
      4. ADAPT    — Update cognitive parameters based on insights
      5. STORE    — Persist learnings for cross-session use

    Usage:
        engine = SelfReflectionEngine(memory_store=store, genome=genome)
        insight = engine.reflect_on_task(outcome)
        engine.periodic_deep_reflection()
    """

    def __init__(
        self,
        memory_store=None,
        genome_system=None,
        prompt_evolver=None,
    ):
        self.memory = memory_store
        self.genome = genome_system
        self.prompt_evolver = prompt_evolver
        self._outcomes: deque = deque(maxlen=500)
        self._insights: List[ReflectionInsight] = []
        self._adaptation_count: int = 0
        self._streak_tracker: Dict[str, int] = {}  # tool -> consecutive success/fail count

    def reflect_on_task(self, outcome: TaskOutcome) -> Optional[ReflectionInsight]:
        """Reflect on a single task outcome."""
        self._outcomes.append(outcome)
        self._update_streaks(outcome)

        insight = None

        if outcome.success:
            insight = self._reflect_success(outcome)
        else:
            insight = self._reflect_failure(outcome)

        if insight:
            self._insights.append(insight)
            self._apply_insight(insight)

            # Persist to memory store
            if self.memory:
                self.memory.remember(
                    f"insight_{int(time.time())}_{insight.category}",
                    {"insight": insight.insight, "confidence": insight.confidence,
                     "actions": insight.action_items},
                    category="reflections",
                    importance=insight.confidence,
                )

        return insight

    def _reflect_success(self, outcome: TaskOutcome) -> Optional[ReflectionInsight]:
        """Analyze a successful task."""
        tool = outcome.tool_used
        streak = self._streak_tracker.get(f"{tool}_success", 0)

        # Fast execution insight
        if outcome.duration < 0.5 and outcome.quality_score > 0.8:
            return ReflectionInsight(
                category="success_pattern",
                insight=f"Tool '{tool}' is highly efficient for this type of task ({outcome.duration:.2f}s).",
                confidence=0.7,
                evidence=[f"Duration: {outcome.duration:.2f}s, Quality: {outcome.quality_score:.1f}"],
                action_items=["Prioritize this tool for similar tasks"],
            )

        # Winning streak insight
        if streak >= 3:
            return ReflectionInsight(
                category="success_pattern",
                insight=f"Tool '{tool}' has {streak} consecutive successes. Highly reliable.",
                confidence=min(1.0, 0.5 + streak * 0.1),
                evidence=[f"Streak: {streak}"],
                action_items=["Increase confidence for this tool", "Use as default for similar tasks"],
            )

        return None

    def _reflect_failure(self, outcome: TaskOutcome) -> ReflectionInsight:
        """Analyze a failed task."""
        tool = outcome.tool_used
        fail_streak = self._streak_tracker.get(f"{tool}_fail", 0)

        # Recurring failure
        if fail_streak >= 2:
            return ReflectionInsight(
                category="failure_pattern",
                insight=f"Tool '{tool}' has failed {fail_streak} times consecutively. "
                         f"Last error: {outcome.error[:100]}",
                confidence=0.8,
                evidence=[f"Failures: {fail_streak}", f"Error: {outcome.error}"],
                action_items=[
                    f"Avoid tool '{tool}' for current task type",
                    "Try alternative approach",
                    "Log for diagnostic review",
                ],
            )

        # Single failure analysis
        error_lower = outcome.error.lower()
        action_items = ["Retry with different parameters"]

        if "timeout" in error_lower:
            action_items.append("Increase timeout or simplify input")
        elif "not found" in error_lower:
            action_items.append("Verify file/resource exists before retrying")
        elif "permission" in error_lower:
            action_items.append("Check permissions and access rights")
        elif "syntax" in error_lower:
            action_items.append("Validate input syntax before execution")

        return ReflectionInsight(
            category="failure_pattern",
            insight=f"Task '{outcome.task_description}' failed with '{tool}': {outcome.error[:100]}",
            confidence=0.6,
            evidence=[f"Error: {outcome.error}"],
            action_items=action_items,
        )

    def _update_streaks(self, outcome: TaskOutcome):
        """Track consecutive success/failure streaks."""
        tool = outcome.tool_used
        if outcome.success:
            self._streak_tracker[f"{tool}_success"] = \
                self._streak_tracker.get(f"{tool}_success", 0) + 1
            self._streak_tracker[f"{tool}_fail"] = 0
        else:
            self._streak_tracker[f"{tool}_fail"] = \
                self._streak_tracker.get(f"{tool}_fail", 0) + 1
            self._streak_tracker[f"{tool}_success"] = 0

    def _apply_insight(self, insight: ReflectionInsight):
        """Apply insight to update system behavior."""
        self._adaptation_count += 1

        # Update genome if available
        if self.genome and hasattr(self.genome, 'get_champion'):
            champion = self.genome.get_champion()
            if champion:
                if insight.category == "success_pattern":
                    # Reinforce current gene values
                    champion.fitness = min(1.0, champion.fitness + 0.05)
                elif insight.category == "failure_pattern":
                    # Reduce fitness to trigger evolution
                    champion.fitness = max(0.0, champion.fitness - 0.1)

        insight.applied = True

    def periodic_deep_reflection(self) -> Dict[str, Any]:
        """
        Comprehensive reflection over recent history.
        Call this periodically (every N tasks or time interval).
        """
        if len(self._outcomes) < 5:
            return {"skipped": True, "reason": "Not enough data"}

        outcomes = list(self._outcomes)
        total = len(outcomes)
        successes = sum(1 for o in outcomes if o.success)
        failures = total - successes

        # Compute averages
        avg_duration = sum(o.duration for o in outcomes) / total
        avg_quality = sum(o.quality_score for o in outcomes if o.success) / max(successes, 1)

        # Tool performance analysis
        tool_stats: Dict[str, Dict] = {}
        for o in outcomes:
            t = o.tool_used or "unknown"
            if t not in tool_stats:
                tool_stats[t] = {"total": 0, "success": 0, "total_duration": 0.0}
            tool_stats[t]["total"] += 1
            if o.success:
                tool_stats[t]["success"] += 1
            tool_stats[t]["total_duration"] += o.duration

        # Find weakest tool
        worst_tool = None
        worst_rate = 1.0
        for tool, stats in tool_stats.items():
            rate = stats["success"] / stats["total"] if stats["total"] > 0 else 1.0
            if rate < worst_rate:
                worst_rate = rate
                worst_tool = tool

        # Find strongest tool
        best_tool = None
        best_rate = 0.0
        for tool, stats in tool_stats.items():
            rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0.0
            if rate > best_rate:
                best_rate = rate
                best_tool = tool

        # Error pattern analysis
        error_types: Dict[str, int] = {}
        for o in outcomes:
            if not o.success and o.error:
                key = o.error.split(":")[0][:50] if ":" in o.error else o.error[:50]
                error_types[key] = error_types.get(key, 0) + 1

        # Generate meta-insights
        meta_insights = []
        if failures / total > 0.3:
            meta_insights.append(
                f"High failure rate ({failures/total:.0%}) — consider simplifying task decomposition"
            )
        if avg_duration > 5.0:
            meta_insights.append(
                f"Slow execution (avg {avg_duration:.1f}s) — optimize tool selection"
            )
        if worst_tool and worst_rate < 0.5:
            meta_insights.append(
                f"Tool '{worst_tool}' unreliable ({worst_rate:.0%}) — find alternative"
            )
        if best_tool:
            meta_insights.append(
                f"Tool '{best_tool}' is most reliable ({best_rate:.0%}) — leverage more"
            )

        report = {
            "period_tasks": total,
            "success_rate": successes / total,
            "failure_rate": failures / total,
            "avg_duration": round(avg_duration, 3),
            "avg_quality": round(avg_quality, 3),
            "tool_performance": {
                t: {"success_rate": s["success"] / s["total"],
                    "avg_duration": s["total_duration"] / s["total"]}
                for t, s in tool_stats.items()
            },
            "error_patterns": error_types,
            "best_tool": best_tool,
            "worst_tool": worst_tool,
            "meta_insights": meta_insights,
            "total_adaptations": self._adaptation_count,
            "total_insights": len(self._insights),
        }

        # Persist deep reflection
        if self.memory:
            self.memory.remember(
                f"deep_reflection_{int(time.time())}",
                report,
                category="reflections",
                importance=0.9,
            )

        return report

    def get_insights(self, category: str = "", limit: int = 20) -> List[Dict]:
        """Get recent insights, optionally filtered by category."""
        filtered = self._insights
        if category:
            filtered = [i for i in filtered if i.category == category]
        return [
            {"category": i.category, "insight": i.insight,
             "confidence": i.confidence, "actions": i.action_items,
             "applied": i.applied}
            for i in filtered[-limit:]
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_outcomes": len(self._outcomes),
            "total_insights": len(self._insights),
            "adaptations_made": self._adaptation_count,
            "active_streaks": {k: v for k, v in self._streak_tracker.items() if v > 0},
        }
