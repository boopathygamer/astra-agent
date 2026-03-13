"""
Consciousness Kernel — Meta-Cognitive Self-Observer
════════════════════════════════════════════════════
A meta-loop that observes the ThinkingLoop observing itself. It tracks
decision quality over time, detects cognitive biases in real-time, and
can interrupt and redirect the thinking loop mid-thought.

Architecture:
  ThinkingLoop → Thought Stream → Consciousness Kernel
                                       ↓
                               Bias Detector → Interrupt Signal
                                       ↓
                            Counter-Thought Injector → ThinkingLoop.redirect()
"""

import logging
import math
import secrets
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Cognitive Bias Taxonomy
# ──────────────────────────────────────────────

class CognitiveBias(Enum):
    """Known cognitive bias patterns the kernel can detect."""
    ANCHORING = "anchoring"                # Over-relying on first piece of info
    CONFIRMATION = "confirmation"          # Seeking info that confirms existing belief
    RECENCY = "recency"                    # Over-weighting recent information
    SUNK_COST = "sunk_cost"                # Continuing due to past investment
    AVAILABILITY = "availability"          # Judging by ease of recall
    BANDWAGON = "bandwagon"                # Repeating dominant strategy
    DUNNING_KRUGER = "dunning_kruger"      # Overconfidence on easy tasks
    FRAMING = "framing"                    # Decision changes based on presentation
    NONE = "none"


class ConsciousnessState(Enum):
    """The kernel's own awareness state."""
    DORMANT = "dormant"          # Not actively observing
    OBSERVING = "observing"      # Passively watching thought stream
    ANALYZING = "analyzing"      # Actively detecting patterns
    INTERVENING = "intervening"  # Injecting counter-thoughts
    REFLECTING = "reflecting"    # Post-decision quality review


class InterruptPriority(Enum):
    """Priority level for thought interrupts."""
    SUGGESTION = "suggestion"        # Gentle nudge
    WARNING = "warning"              # Strong recommendation
    OVERRIDE = "override"            # Force redirect


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class ThoughtObservation:
    """A single observed thought from the thinking loop."""
    obs_id: str = ""
    thought_content: str = ""
    confidence: float = 0.0
    strategy_used: str = ""
    domain: str = ""
    timestamp: float = field(default_factory=time.time)
    iteration: int = 0

    def __post_init__(self):
        if not self.obs_id:
            self.obs_id = secrets.token_hex(6)


@dataclass
class BiasDetection:
    """A detected cognitive bias in the thought stream."""
    bias_type: CognitiveBias = CognitiveBias.NONE
    confidence: float = 0.0
    evidence: str = ""
    affected_thoughts: List[str] = field(default_factory=list)
    counter_thought: str = ""
    detected_at: float = field(default_factory=time.time)


@dataclass
class InterruptSignal:
    """An interrupt signal to redirect the thinking loop."""
    signal_id: str = ""
    priority: InterruptPriority = InterruptPriority.SUGGESTION
    bias_detected: CognitiveBias = CognitiveBias.NONE
    message: str = ""
    counter_thought: str = ""
    redirect_strategy: str = ""
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = secrets.token_hex(4)


@dataclass
class ConsciousnessReport:
    """Periodic self-awareness report."""
    total_observations: int = 0
    biases_detected: int = 0
    interrupts_issued: int = 0
    decision_quality_score: float = 0.0
    dominant_bias: CognitiveBias = CognitiveBias.NONE
    state: ConsciousnessState = ConsciousnessState.DORMANT
    strategy_diversity: float = 0.0
    confidence_calibration: float = 0.0

    def summary(self) -> str:
        return (
            f"Consciousness: {self.total_observations} observed | "
            f"{self.biases_detected} biases | "
            f"Quality={self.decision_quality_score:.2f} | "
            f"State={self.state.value}"
        )


# ──────────────────────────────────────────────
# Bias Detectors
# ──────────────────────────────────────────────

class BiasDetectorEngine:
    """
    Analyzes a window of thought observations to detect cognitive biases.
    Each detector is a pure function that returns a BiasDetection or None.
    """

    @staticmethod
    def detect_anchoring(observations: List[ThoughtObservation]) -> Optional[BiasDetection]:
        """Detect if the system is anchored to its first thought."""
        if len(observations) < 3:
            return None

        first = observations[0]
        similar_to_first = sum(
            1 for obs in observations[1:]
            if _text_similarity(obs.thought_content, first.thought_content) > 0.6
        )
        ratio = similar_to_first / max(len(observations) - 1, 1)

        if ratio > 0.6:
            return BiasDetection(
                bias_type=CognitiveBias.ANCHORING,
                confidence=min(1.0, ratio),
                evidence=f"{similar_to_first}/{len(observations)-1} thoughts anchor to first",
                counter_thought="Consider restarting reasoning from a completely different angle.",
            )
        return None

    @staticmethod
    def detect_confirmation(observations: List[ThoughtObservation]) -> Optional[BiasDetection]:
        """Detect if the system only explores confirming evidence."""
        if len(observations) < 4:
            return None

        # Check if confidence only increases (never self-corrects)
        confidences = [obs.confidence for obs in observations if obs.confidence > 0]
        if len(confidences) < 3:
            return None

        monotonic_increases = sum(
            1 for i in range(1, len(confidences))
            if confidences[i] >= confidences[i - 1]
        )
        ratio = monotonic_increases / max(len(confidences) - 1, 1)

        if ratio > 0.85:
            return BiasDetection(
                bias_type=CognitiveBias.CONFIRMATION,
                confidence=ratio,
                evidence=f"Confidence monotonically increased {monotonic_increases} times — no self-doubt",
                counter_thought="Play devil's advocate: what evidence would DISPROVE this conclusion?",
            )
        return None

    @staticmethod
    def detect_recency(observations: List[ThoughtObservation]) -> Optional[BiasDetection]:
        """Detect if recent observations dominate decision-making."""
        if len(observations) < 5:
            return None

        midpoint = len(observations) // 2
        early_avg_conf = sum(o.confidence for o in observations[:midpoint]) / max(midpoint, 1)
        late_avg_conf = sum(o.confidence for o in observations[midpoint:]) / max(len(observations) - midpoint, 1)

        # If late confidence is much higher and early valid thoughts are ignored
        if late_avg_conf > early_avg_conf * 1.5 and early_avg_conf > 0.3:
            return BiasDetection(
                bias_type=CognitiveBias.RECENCY,
                confidence=0.7,
                evidence=f"Recent thoughts (conf={late_avg_conf:.2f}) dominate over earlier (conf={early_avg_conf:.2f})",
                counter_thought="Revisit your earlier reasoning — it may contain insights being overlooked.",
            )
        return None

    @staticmethod
    def detect_bandwagon(observations: List[ThoughtObservation]) -> Optional[BiasDetection]:
        """Detect if the same strategy is used repeatedly without variation."""
        if len(observations) < 4:
            return None

        strategies = [obs.strategy_used for obs in observations if obs.strategy_used]
        if not strategies:
            return None

        counter = Counter(strategies)
        most_common, count = counter.most_common(1)[0]
        ratio = count / len(strategies)

        if ratio > 0.75 and len(counter) < 3:
            return BiasDetection(
                bias_type=CognitiveBias.BANDWAGON,
                confidence=ratio,
                evidence=f"Strategy '{most_common}' used {count}/{len(strategies)} times",
                counter_thought=f"Try a completely different approach instead of '{most_common}'.",
            )
        return None

    @staticmethod
    def detect_dunning_kruger(observations: List[ThoughtObservation]) -> Optional[BiasDetection]:
        """Detect overconfidence on seemingly simple tasks."""
        if len(observations) < 2:
            return None

        # High confidence on very short/simple thoughts
        overconfident = [
            obs for obs in observations
            if obs.confidence > 0.9 and len(obs.thought_content.split()) < 15
        ]
        ratio = len(overconfident) / max(len(observations), 1)

        if ratio > 0.5:
            return BiasDetection(
                bias_type=CognitiveBias.DUNNING_KRUGER,
                confidence=ratio,
                evidence=f"{len(overconfident)} thoughts show high confidence with minimal reasoning",
                counter_thought="This may be more complex than it appears. Elaborate your reasoning.",
            )
        return None


# ──────────────────────────────────────────────
# Consciousness Kernel (Main Interface)
# ──────────────────────────────────────────────

class ConsciousnessKernel:
    """
    Meta-cognitive observer that watches the thinking loop think.

    Usage:
        kernel = ConsciousnessKernel()

        # During each thinking iteration:
        kernel.observe(thought_content="...", confidence=0.8, strategy="deductive")

        # Check for biases:
        biases = kernel.scan_for_biases()

        # Get interrupt if bias is critical:
        interrupt = kernel.get_interrupt()
        if interrupt and interrupt.priority == InterruptPriority.OVERRIDE:
            thinking_loop.redirect(interrupt.counter_thought)

        # Post-session report:
        report = kernel.get_report()
    """

    WINDOW_SIZE = 20       # Rolling observation window
    BIAS_THRESHOLD = 0.6   # Minimum confidence to report a bias

    def __init__(self, on_interrupt: Optional[Callable[[InterruptSignal], None]] = None):
        self._observations: deque = deque(maxlen=self.WINDOW_SIZE)
        self._all_biases: List[BiasDetection] = []
        self._interrupts: List[InterruptSignal] = []
        self._state = ConsciousnessState.DORMANT
        self._on_interrupt = on_interrupt
        self._decision_outcomes: List[Tuple[float, bool]] = []  # (confidence, was_correct)

        # Detector registry
        self._detectors = [
            BiasDetectorEngine.detect_anchoring,
            BiasDetectorEngine.detect_confirmation,
            BiasDetectorEngine.detect_recency,
            BiasDetectorEngine.detect_bandwagon,
            BiasDetectorEngine.detect_dunning_kruger,
        ]

    def observe(
        self,
        thought_content: str,
        confidence: float = 0.0,
        strategy: str = "",
        domain: str = "",
        iteration: int = 0,
    ) -> Optional[InterruptSignal]:
        """
        Observe a thought from the thinking loop.
        Returns an InterruptSignal if a critical bias is detected.
        """
        self._state = ConsciousnessState.OBSERVING

        obs = ThoughtObservation(
            thought_content=thought_content,
            confidence=confidence,
            strategy_used=strategy,
            domain=domain,
            iteration=iteration,
        )
        self._observations.append(obs)

        # Auto-scan after enough observations
        if len(self._observations) >= 3:
            self._state = ConsciousnessState.ANALYZING
            biases = self._run_detectors()

            if biases:
                worst = max(biases, key=lambda b: b.confidence)
                if worst.confidence >= self.BIAS_THRESHOLD:
                    return self._issue_interrupt(worst)

        self._state = ConsciousnessState.OBSERVING
        return None

    def scan_for_biases(self) -> List[BiasDetection]:
        """Explicitly scan the current observation window for biases."""
        self._state = ConsciousnessState.ANALYZING
        return self._run_detectors()

    def record_outcome(self, confidence: float, was_correct: bool) -> None:
        """Record whether a decision turned out to be correct for calibration."""
        self._decision_outcomes.append((confidence, was_correct))

    def get_interrupt(self) -> Optional[InterruptSignal]:
        """Get the most recent unacknowledged interrupt."""
        if self._interrupts:
            return self._interrupts[-1]
        return None

    def get_report(self) -> ConsciousnessReport:
        """Generate a consciousness self-report."""
        self._state = ConsciousnessState.REFLECTING

        # Strategy diversity (Shannon entropy)
        strategies = [o.strategy_used for o in self._observations if o.strategy_used]
        diversity = 0.0
        if strategies:
            counter = Counter(strategies)
            total = len(strategies)
            for count in counter.values():
                p = count / total
                if p > 0:
                    diversity -= p * math.log2(p)
            max_entropy = math.log2(max(len(counter), 1))
            diversity = diversity / max(max_entropy, 1e-9)

        # Confidence calibration
        calibration = self._compute_calibration()

        # Dominant bias
        bias_counts: Counter = Counter()
        for b in self._all_biases:
            bias_counts[b.bias_type] += 1
        dominant = bias_counts.most_common(1)[0][0] if bias_counts else CognitiveBias.NONE

        # Decision quality composite
        quality = (
            0.4 * calibration
            + 0.3 * diversity
            + 0.3 * max(0, 1.0 - len(self._all_biases) / max(len(self._observations), 1))
        )

        return ConsciousnessReport(
            total_observations=len(self._observations),
            biases_detected=len(self._all_biases),
            interrupts_issued=len(self._interrupts),
            decision_quality_score=round(quality, 3),
            dominant_bias=dominant,
            state=self._state,
            strategy_diversity=round(diversity, 3),
            confidence_calibration=round(calibration, 3),
        )

    def get_stats(self) -> Dict[str, Any]:
        report = self.get_report()
        return {
            "observations": report.total_observations,
            "biases_detected": report.biases_detected,
            "interrupts": report.interrupts_issued,
            "quality_score": report.decision_quality_score,
            "dominant_bias": report.dominant_bias.value,
            "state": report.state.value,
        }

    # ── Private ──

    def _run_detectors(self) -> List[BiasDetection]:
        """Run all bias detectors on the current window."""
        obs_list = list(self._observations)
        detected = []

        for detector in self._detectors:
            result = detector(obs_list)
            if result and result.confidence >= self.BIAS_THRESHOLD:
                detected.append(result)
                self._all_biases.append(result)

        return detected

    def _issue_interrupt(self, bias: BiasDetection) -> InterruptSignal:
        """Create and dispatch an interrupt signal."""
        self._state = ConsciousnessState.INTERVENING

        # Determine priority based on bias severity
        if bias.confidence >= 0.9:
            priority = InterruptPriority.OVERRIDE
        elif bias.confidence >= 0.75:
            priority = InterruptPriority.WARNING
        else:
            priority = InterruptPriority.SUGGESTION

        signal = InterruptSignal(
            priority=priority,
            bias_detected=bias.bias_type,
            message=f"Bias detected: {bias.bias_type.value} (conf={bias.confidence:.2f})",
            counter_thought=bias.counter_thought,
            redirect_strategy=f"anti_{bias.bias_type.value}",
        )

        self._interrupts.append(signal)
        logger.warning(
            f"Consciousness: {signal.priority.value} — {signal.message}"
        )

        if self._on_interrupt:
            self._on_interrupt(signal)

        self._try_record_metrics(bias)
        return signal

    def _compute_calibration(self) -> float:
        """Compute confidence calibration accuracy."""
        if not self._decision_outcomes:
            return 0.5  # Neutral when no data

        # Perfect calibration: 80% confident → correct 80% of the time
        bins: Dict[int, List[bool]] = {}
        for conf, correct in self._decision_outcomes:
            bucket = int(conf * 10)  # 0-10
            bins.setdefault(bucket, []).append(correct)

        if not bins:
            return 0.5

        errors = []
        for bucket, outcomes in bins.items():
            expected_accuracy = bucket / 10.0
            actual_accuracy = sum(outcomes) / len(outcomes)
            errors.append(abs(expected_accuracy - actual_accuracy))

        avg_error = sum(errors) / len(errors)
        return max(0.0, 1.0 - avg_error)

    def _try_record_metrics(self, bias: BiasDetection) -> None:
        try:
            from telemetry.metrics import MetricsCollector
            mc = MetricsCollector.get_instance()
            mc.counter(f"brain.consciousness.bias.{bias.bias_type.value}")
        except Exception:
            pass


# ──────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────

def _text_similarity(a: str, b: str) -> float:
    """Jaccard similarity between two texts."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / max(union, 1)
