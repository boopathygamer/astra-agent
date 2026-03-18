"""
Meta-Cognitive Monitor — Calibrated Confidence & Uncertainty Quantification
═══════════════════════════════════════════════════════════════════════════
Implements "thinking about thinking" — tracks the agent's own reasoning
quality and calibrates confidence predictions against actual outcomes.

Inspired by:
  • Kadavath et al. (2022) "Language Models (Mostly) Know What They Know"
  • Bayesian calibration curves from forecasting research
  • Dunning-Kruger effect compensation

Features:
  1. Calibration Curve     — Maps predicted → actual accuracy
  2. Epistemic/Aleatoric   — Decomposes uncertainty type
  3. Knowledge Boundaries  — Detects "I don't know" situations
  4. Cognitive Load Model  — Working memory + attention simulation
  5. Miscalibration Correction — Historical bias compensation
  6. Confidence Intervals  — Reports uncertainty ranges, not point estimates
"""

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CalibrationBin:
    """A single bin in the calibration curve."""
    bin_lower: float = 0.0
    bin_upper: float = 0.1
    total_predictions: int = 0
    total_correct: int = 0

    @property
    def predicted_confidence(self) -> float:
        return (self.bin_lower + self.bin_upper) / 2

    @property
    def actual_accuracy(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return self.total_correct / self.total_predictions

    @property
    def calibration_error(self) -> float:
        """How far off the prediction is from actual."""
        return abs(self.predicted_confidence - self.actual_accuracy)


@dataclass
class UncertaintyDecomposition:
    """Decomposed uncertainty into epistemic and aleatoric components."""
    total_uncertainty: float = 0.0
    epistemic: float = 0.0      # Reducible (model doesn't know)
    aleatoric: float = 0.0      # Irreducible (inherent randomness)
    source: str = ""            # What caused the uncertainty
    suggestions: List[str] = field(default_factory=list)

    @property
    def is_knowledge_gap(self) -> bool:
        """True if uncertainty is mainly from lack of knowledge."""
        return self.epistemic > self.aleatoric * 1.5


@dataclass
class CognitiveLoadReport:
    """Working memory and attention load estimate."""
    load_score: float = 0.0     # 0.0 (trivial) to 1.0 (overwhelming)
    factors: Dict[str, float] = field(default_factory=dict)
    estimated_accuracy: float = 0.0
    recommendation: str = ""

    @property
    def is_overloaded(self) -> bool:
        return self.load_score > 0.8


@dataclass
class ConfidenceReport:
    """Full confidence report with calibrated estimates."""
    raw_confidence: float = 0.0         # Model's initial confidence
    calibrated_confidence: float = 0.0   # After calibration adjustment
    confidence_interval: Tuple[float, float] = (0.0, 1.0)
    uncertainty: UncertaintyDecomposition = field(default_factory=UncertaintyDecomposition)
    cognitive_load: CognitiveLoadReport = field(default_factory=CognitiveLoadReport)
    knowledge_domain: str = ""
    is_reliable: bool = True
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_confidence": round(self.raw_confidence, 4),
            "calibrated": round(self.calibrated_confidence, 4),
            "interval": (round(self.confidence_interval[0], 3),
                         round(self.confidence_interval[1], 3)),
            "epistemic_uncertainty": round(self.uncertainty.epistemic, 4),
            "aleatoric_uncertainty": round(self.uncertainty.aleatoric, 4),
            "cognitive_load": round(self.cognitive_load.load_score, 3),
            "is_reliable": self.is_reliable,
        }


class MetaCognitiveMonitor:
    """
    Monitors and calibrates the agent's confidence predictions.

    Maintains a calibration curve that maps predicted confidence
    to actual accuracy. Uses this curve to adjust future predictions,
    compensating for systematic over/under-confidence.

    Also provides:
    - Uncertainty decomposition (epistemic vs aleatoric)
    - Cognitive load estimation
    - Knowledge boundary detection
    - Dunning-Kruger compensation
    """

    NUM_BINS = 10

    # Keywords indicating knowledge boundary
    UNCERTAINTY_SIGNALS = {
        "high": ["unsure", "unclear", "might", "perhaps", "possibly",
                 "speculation", "guess", "not certain", "ambiguous"],
        "medium": ["likely", "probably", "seems", "appears", "suggests",
                   "could be", "may", "I think"],
        "low": ["definitely", "certainly", "clearly", "proven",
                "established", "verified", "confirmed"],
    }

    # Problem complexity indicators for cognitive load
    COMPLEXITY_FACTORS = {
        "multi_step": ["then", "next", "after", "before", "first", "second", "finally"],
        "abstract": ["concept", "theory", "abstract", "principle", "philosophy"],
        "technical": ["algorithm", "architecture", "protocol", "implementation"],
        "ambiguous": ["depends", "context", "it varies", "trade-off", "nuance"],
        "novel": ["unusual", "unique", "novel", "unprecedented", "new approach"],
    }

    def __init__(self):
        # Calibration bins: [0.0-0.1, 0.1-0.2, ..., 0.9-1.0]
        self._bins: List[CalibrationBin] = [
            CalibrationBin(
                bin_lower=i / self.NUM_BINS,
                bin_upper=(i + 1) / self.NUM_BINS,
            )
            for i in range(self.NUM_BINS)
        ]

        # Historical tracking
        self._prediction_history: List[Dict[str, float]] = []
        self._domain_accuracy: Dict[str, List[float]] = defaultdict(list)
        self._miscalibration_ema = 0.0  # Exponential moving average of error

        logger.info("[META_COG] Meta-Cognitive Monitor initialized")

    def assess_confidence(
        self,
        raw_confidence: float,
        response_text: str = "",
        problem: str = "",
        domain: str = "general",
    ) -> ConfidenceReport:
        """
        Produce a calibrated confidence report.

        Takes the model's raw confidence and adjusts it using:
        1. Historical calibration curve
        2. Uncertainty signal detection
        3. Domain-specific accuracy
        4. Cognitive load estimation
        5. Dunning-Kruger compensation
        """
        report = ConfidenceReport(
            raw_confidence=raw_confidence,
            knowledge_domain=domain,
        )

        # 1. Calibrate using historical curve
        report.calibrated_confidence = self._calibrate(raw_confidence)

        # 2. Decompose uncertainty
        report.uncertainty = self._decompose_uncertainty(
            response_text, problem, raw_confidence
        )

        # 3. Estimate cognitive load
        report.cognitive_load = self._estimate_cognitive_load(problem)

        # 4. Dunning-Kruger compensation
        dk_adjustment = self._dunning_kruger_adjust(raw_confidence, domain)
        report.calibrated_confidence = max(0.0, min(1.0,
            report.calibrated_confidence + dk_adjustment
        ))

        # 5. Compute confidence interval
        report.confidence_interval = self._confidence_interval(
            report.calibrated_confidence,
            report.uncertainty.total_uncertainty,
        )

        # 6. Reliability assessment
        report.is_reliable = (
            report.calibrated_confidence > 0.4
            and not report.uncertainty.is_knowledge_gap
            and not report.cognitive_load.is_overloaded
        )

        report.explanation = self._explain(report)
        return report

    def record_outcome(self, predicted_confidence: float, was_correct: bool,
                       domain: str = "general") -> None:
        """
        Record a prediction outcome to update calibration.

        Call this after verifying whether a response was actually correct.
        """
        # Update calibration bin
        bin_idx = min(int(predicted_confidence * self.NUM_BINS), self.NUM_BINS - 1)
        self._bins[bin_idx].total_predictions += 1
        if was_correct:
            self._bins[bin_idx].total_correct += 1

        # Track history
        self._prediction_history.append({
            "predicted": predicted_confidence,
            "actual": 1.0 if was_correct else 0.0,
            "domain": domain,
            "time": time.time(),
        })

        # Update domain accuracy
        self._domain_accuracy[domain].append(1.0 if was_correct else 0.0)
        # Keep only recent history
        if len(self._domain_accuracy[domain]) > 200:
            self._domain_accuracy[domain] = self._domain_accuracy[domain][-100:]

        # Update miscalibration EMA
        error = abs(predicted_confidence - (1.0 if was_correct else 0.0))
        self._miscalibration_ema = 0.1 * error + 0.9 * self._miscalibration_ema

    def _calibrate(self, raw_confidence: float) -> float:
        """
        Adjust confidence using the calibration curve.

        If bin shows historical over-confidence (predicted > actual),
        reduce the confidence. If under-confident, increase it.
        """
        bin_idx = min(int(raw_confidence * self.NUM_BINS), self.NUM_BINS - 1)
        cal_bin = self._bins[bin_idx]

        if cal_bin.total_predictions < 5:
            # Not enough data, apply conservative shrinkage toward 0.5
            return 0.7 * raw_confidence + 0.3 * 0.5

        # Adjust based on historical accuracy in this bin
        actual = cal_bin.actual_accuracy
        predicted = cal_bin.predicted_confidence

        # Blend raw confidence with historical actual accuracy
        calibrated = 0.6 * raw_confidence + 0.4 * actual
        return max(0.0, min(1.0, calibrated))

    def _decompose_uncertainty(self, response: str, problem: str,
                               confidence: float) -> UncertaintyDecomposition:
        """
        Decompose total uncertainty into epistemic (lack of knowledge)
        and aleatoric (inherent randomness) components.
        """
        decomp = UncertaintyDecomposition()
        decomp.total_uncertainty = 1.0 - confidence

        resp_lower = response.lower()
        prob_lower = problem.lower()

        # Epistemic: detected uncertainty in the response itself
        high_signals = sum(1 for w in self.UNCERTAINTY_SIGNALS["high"] if w in resp_lower)
        med_signals = sum(1 for w in self.UNCERTAINTY_SIGNALS["medium"] if w in resp_lower)
        low_signals = sum(1 for w in self.UNCERTAINTY_SIGNALS["low"] if w in resp_lower)

        # More high-uncertainty signals → more epistemic uncertainty
        epistemic_ratio = (high_signals * 0.3 + med_signals * 0.1) / max(
            high_signals + med_signals + low_signals, 1
        )
        epistemic_ratio = max(0.2, min(0.9, epistemic_ratio + 0.3))

        # Aleatoric: inherent ambiguity in the problem
        if any(w in prob_lower for w in ["opinion", "prefer", "feel", "creative"]):
            epistemic_ratio *= 0.6  # Less epistemic, more aleatoric

        decomp.epistemic = decomp.total_uncertainty * epistemic_ratio
        decomp.aleatoric = decomp.total_uncertainty * (1 - epistemic_ratio)

        # Suggestions based on uncertainty type
        if decomp.is_knowledge_gap:
            decomp.source = "knowledge_gap"
            decomp.suggestions = [
                "Consult additional references or documentation",
                "Break down into smaller, more answerable sub-questions",
                "Explicitly state assumptions and unknowns",
            ]
        else:
            decomp.source = "inherent_ambiguity"
            decomp.suggestions = [
                "Present multiple valid perspectives",
                "Acknowledge the inherent trade-offs",
            ]

        return decomp

    def _estimate_cognitive_load(self, problem: str) -> CognitiveLoadReport:
        """
        Estimate cognitive load using problem characteristics.

        Models working memory constraints using Miller's Law (7±2 chunks).
        """
        report = CognitiveLoadReport()
        prob_lower = problem.lower()

        # Measure complexity factors
        factors = {}
        for factor, keywords in self.COMPLEXITY_FACTORS.items():
            matches = sum(1 for kw in keywords if kw in prob_lower)
            factors[factor] = min(matches * 0.15, 0.3)

        # Problem length contributes to load
        word_count = len(problem.split())
        length_factor = min(word_count / 200, 0.3)
        factors["length"] = length_factor

        # Question complexity (number of question marks, sub-questions)
        q_count = problem.count("?")
        factors["multi_question"] = min(q_count * 0.1, 0.3)

        report.factors = factors
        report.load_score = min(1.0, sum(factors.values()))

        # Estimated accuracy based on load (inverse relationship)
        # Based on cognitive load theory: accuracy drops sigmoidal with load
        report.estimated_accuracy = 1.0 / (1.0 + math.exp(5 * (report.load_score - 0.6)))

        # Recommendation
        if report.is_overloaded:
            report.recommendation = "Decompose into sub-problems before attempting solution"
        elif report.load_score > 0.5:
            report.recommendation = "Use structured reasoning (chain-of-thought) for best results"
        else:
            report.recommendation = "Direct answer is likely sufficient"

        return report

    def _dunning_kruger_adjust(self, raw_confidence: float, domain: str) -> float:
        """
        Compensate for Dunning-Kruger effect.

        If historical accuracy in this domain is low but confidence is high,
        reduce confidence. If accuracy is high but confidence is low, increase it.
        """
        history = self._domain_accuracy.get(domain, [])
        if len(history) < 10:
            return 0.0  # Not enough data to adjust

        actual_accuracy = sum(history[-20:]) / len(history[-20:])
        gap = raw_confidence - actual_accuracy

        # If overconfident (high confidence, low actual): negative adjustment
        # If underconfident (low confidence, high actual): positive adjustment
        adjustment = -gap * 0.3  # Moderate correction strength
        return max(-0.2, min(0.2, adjustment))

    @staticmethod
    def _confidence_interval(center: float, uncertainty: float) -> Tuple[float, float]:
        """Compute a confidence interval given uncertainty."""
        half_width = uncertainty * 0.5
        lower = max(0.0, center - half_width)
        upper = min(1.0, center + half_width)
        return (round(lower, 4), round(upper, 4))

    @staticmethod
    def _explain(report: ConfidenceReport) -> str:
        """Generate a human-readable explanation of the confidence assessment."""
        parts = []
        if abs(report.raw_confidence - report.calibrated_confidence) > 0.1:
            direction = "reduced" if report.calibrated_confidence < report.raw_confidence else "increased"
            parts.append(
                f"Confidence {direction} from {report.raw_confidence:.0%} to "
                f"{report.calibrated_confidence:.0%} based on calibration history"
            )
        if report.uncertainty.is_knowledge_gap:
            parts.append("High epistemic uncertainty detected — knowledge gap suspected")
        if report.cognitive_load.is_overloaded:
            parts.append(f"Cognitive load is high ({report.cognitive_load.load_score:.0%}) — "
                         f"consider decomposing the problem")
        return "; ".join(parts) if parts else "Confidence assessment within normal range"

    def get_calibration_curve(self) -> List[Dict[str, float]]:
        """Get the calibration curve data for visualization."""
        return [
            {
                "predicted": b.predicted_confidence,
                "actual": b.actual_accuracy,
                "count": b.total_predictions,
                "error": b.calibration_error,
            }
            for b in self._bins if b.total_predictions > 0
        ]

    def get_ece(self) -> float:
        """Expected Calibration Error (ECE) — lower is better."""
        total = sum(b.total_predictions for b in self._bins)
        if total == 0:
            return 0.0
        ece = sum(
            (b.total_predictions / total) * b.calibration_error
            for b in self._bins
        )
        return round(ece, 4)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_predictions": len(self._prediction_history),
            "ece": self.get_ece(),
            "miscalibration_ema": round(self._miscalibration_ema, 4),
            "domains_tracked": list(self._domain_accuracy.keys()),
            "calibration_bins": sum(1 for b in self._bins if b.total_predictions > 0),
        }
