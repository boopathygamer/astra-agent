"""
Metacognition — The Brain That Watches Itself Think.
─────────────────────────────────────────────────────
Self-monitoring system that tracks the brain's own reasoning:
  - Stuck detection: confidence not improving across iterations
  - Strategy switching: auto-switch reasoning mode when approach plateaus
  - Cognitive load monitoring: problem complexity vs allocated iterations
  - Confidence calibration: tracks historical accuracy
  - Reflection: after solving, generates lessons learned
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

NL = "\n"


@dataclass
class CognitiveState:
    """Snapshot of the brain's current cognitive state."""
    iteration: int = 0
    confidence: float = 0.0
    confidence_history: List[float] = field(default_factory=list)
    current_strategy: str = ""
    strategies_tried: List[str] = field(default_factory=list)
    is_stuck: bool = False
    stuck_iterations: int = 0
    cognitive_load: float = 0.0   # 0-1, how hard the problem is
    time_elapsed_ms: float = 0.0

    def trend(self):
        """Is confidence improving, flat, or declining?"""
        if len(self.confidence_history) < 2:
            return "unknown"
        recent = self.confidence_history[-3:]
        if len(recent) < 2:
            return "unknown"
        delta = recent[-1] - recent[0]
        if delta > 0.05:
            return "improving"
        elif delta < -0.05:
            return "declining"
        return "flat"


@dataclass
class CalibrationRecord:
    """Record of predicted vs actual confidence."""
    predicted_confidence: float = 0.0
    actual_success: bool = False
    problem_domain: str = ""
    strategy_used: str = ""


@dataclass
class Reflection:
    """Post-solve reflection — what the brain learned."""
    problem_summary: str = ""
    strategy_that_worked: str = ""
    strategies_that_failed: List[str] = field(default_factory=list)
    key_insight: str = ""
    confidence_accuracy: float = 0.0
    time_spent_ms: float = 0.0
    difficulty_assessment: str = ""

    def to_memory(self):
        return (
            f"Reflection: {self.problem_summary}" + NL
            + f"  Strategy: {self.strategy_that_worked}" + NL
            + f"  Insight: {self.key_insight}" + NL
            + f"  Difficulty: {self.difficulty_assessment}"
        )


class MetacognitionEngine:
    """
    Self-monitoring for the thinking loop.

    Watches confidence trends, detects when the brain is stuck,
    recommends strategy switches, and generates post-solve reflections.
    """

    def __init__(self, config=None):
        self.state = CognitiveState()
        self._calibration_data: List[CalibrationRecord] = []
        self._stuck_threshold = 3  # iterations without improvement
        self._min_improvement = 0.02  # minimum confidence delta
        self._start_time = 0.0

    def start_monitoring(self, strategy: str = ""):
        """Begin monitoring a new problem-solving session."""
        self.state = CognitiveState(current_strategy=strategy)
        self._start_time = time.time()
        if strategy:
            self.state.strategies_tried.append(strategy)

    def update(self, confidence: float, iteration: int = None):
        """Update cognitive state with new confidence reading."""
        if iteration is not None:
            self.state.iteration = iteration
        else:
            self.state.iteration += 1

        self.state.confidence = confidence
        self.state.confidence_history.append(confidence)
        self.state.time_elapsed_ms = (time.time() - self._start_time) * 1000

        # Stuck detection
        self._check_stuck()

        logger.debug(
            f"Metacognition: iter={self.state.iteration} "
            f"conf={confidence:.3f} trend={self.state.trend()} "
            f"stuck={self.state.is_stuck}"
        )

    def _check_stuck(self):
        """Detect if the brain is stuck (no improvement)."""
        hist = self.state.confidence_history
        if len(hist) < self._stuck_threshold:
            self.state.is_stuck = False
            return

        recent = hist[-self._stuck_threshold:]
        improvement = max(recent) - min(recent)

        if improvement < self._min_improvement:
            self.state.stuck_iterations += 1
            self.state.is_stuck = True
            logger.warning(
                f"Metacognition: STUCK detected "
                f"({self.state.stuck_iterations} rounds, "
                f"improvement={improvement:.4f})"
            )
        else:
            self.state.stuck_iterations = 0
            self.state.is_stuck = False

    def should_switch_strategy(self) -> bool:
        """Should the brain try a different approach?"""
        if self.state.is_stuck and self.state.stuck_iterations >= 2:
            return True
        if self.state.trend() == "declining" and self.state.iteration >= 3:
            return True
        return False

    def recommend_strategy(self, available: List[str]) -> Optional[str]:
        """Suggest the next strategy to try."""
        untried = [s for s in available
                   if s not in self.state.strategies_tried]
        if untried:
            return untried[0]
        # If all tried, recommend the one with best historical performance
        return available[0] if available else None

    def switch_strategy(self, new_strategy: str):
        """Record a strategy switch."""
        self.state.current_strategy = new_strategy
        self.state.strategies_tried.append(new_strategy)
        self.state.is_stuck = False
        self.state.stuck_iterations = 0
        logger.info(f"Metacognition: switching to strategy '{new_strategy}'")

    def estimate_cognitive_load(self, problem: str) -> float:
        """Estimate how hard this problem is (0-1 scale)."""
        load = 0.0
        words = len(problem.split())
        load += min(words / 500.0, 0.3)  # Length factor

        # Complexity indicators
        complexity_words = [
            "complex", "difficult", "multiple", "integrate",
            "optimize", "concurrent", "distributed", "recursive",
            "dynamic", "algorithm", "architecture",
        ]
        matches = sum(1 for w in complexity_words if w in problem.lower())
        load += min(matches * 0.1, 0.4)

        # Code indicators
        if any(w in problem.lower() for w in ["debug", "fix", "error", "bug"]):
            load += 0.15
        if any(w in problem.lower() for w in ["security", "vulnerability"]):
            load += 0.15

        self.state.cognitive_load = min(load, 1.0)
        return self.state.cognitive_load

    def suggest_iterations(self, cognitive_load: float = None) -> int:
        """Suggest number of thinking iterations based on difficulty."""
        load = cognitive_load or self.state.cognitive_load
        if load < 0.3:
            return 2
        elif load < 0.6:
            return 4
        elif load < 0.8:
            return 6
        return 8

    def reflect(self, problem: str, success: bool,
                generate_fn: Callable = None) -> Reflection:
        """Generate post-solve reflection."""
        ref = Reflection(
            problem_summary=problem[:200],
            strategy_that_worked=self.state.current_strategy,
            strategies_that_failed=[
                s for s in self.state.strategies_tried
                if s != self.state.current_strategy
            ],
            time_spent_ms=self.state.time_elapsed_ms,
        )

        # Assess difficulty
        if self.state.iteration <= 2:
            ref.difficulty_assessment = "easy"
        elif self.state.iteration <= 4:
            ref.difficulty_assessment = "medium"
        else:
            ref.difficulty_assessment = "hard"

        # Confidence accuracy
        if self.state.confidence_history:
            final_conf = self.state.confidence_history[-1]
            ref.confidence_accuracy = 1.0 - abs(
                final_conf - (1.0 if success else 0.0))

        # Generate insight via LLM if available
        if generate_fn:
            try:
                strategies_str = ", ".join(self.state.strategies_tried)
                prompt = (
                    "Generate a one-sentence key insight from solving:" + NL
                    + "Problem: " + problem[:300] + NL
                    + "Strategies tried: " + strategies_str + NL
                    + "Success: " + str(success) + NL
                    + "KEY_INSIGHT: "
                )
                insight = generate_fn(prompt)
                if "KEY_INSIGHT:" in insight:
                    ref.key_insight = insight.split("KEY_INSIGHT:")[-1].strip()
                else:
                    ref.key_insight = insight.strip()[:200]
            except Exception:
                ref.key_insight = "Solved via " + self.state.current_strategy

        # Record calibration
        self._calibration_data.append(CalibrationRecord(
            predicted_confidence=self.state.confidence,
            actual_success=success,
            strategy_used=self.state.current_strategy,
        ))

        logger.info(ref.to_memory())
        return ref

    def calibration_accuracy(self) -> float:
        """How accurate are our confidence predictions?"""
        if not self._calibration_data:
            return 0.5
        errors = []
        for r in self._calibration_data:
            actual = 1.0 if r.actual_success else 0.0
            errors.append(abs(r.predicted_confidence - actual))
        return 1.0 - (sum(errors) / len(errors))
