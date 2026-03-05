"""
Confidence Calibration Oracle — Bayesian Self-Trust
────────────────────────────────────────────────────
Calibrates model confidence using historical accuracy data.
The system KNOWS where it's reliable and where it isn't.

Architecture:
  CalibrationHistory  →  BayesianCalibrator  →  ConfidenceAdjuster
  (track predictions)    (posterior updates)     (Platt scaling)
     ↓
  DomainConfidenceProfile (per-domain reliability map)
"""

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class CalibrationPoint:
    """A single (predicted_confidence, actual_correctness) data point."""
    predicted_confidence: float
    was_correct: bool
    domain: str = "general"
    timestamp: float = 0.0
    task_type: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class CalibrationBucket:
    """Aggregated calibration data for a confidence range."""
    bucket_min: float = 0.0
    bucket_max: float = 0.1
    total_predictions: int = 0
    correct_predictions: int = 0

    @property
    def observed_accuracy(self) -> float:
        return self.correct_predictions / max(self.total_predictions, 1)

    @property
    def midpoint(self) -> float:
        return (self.bucket_min + self.bucket_max) / 2

    @property
    def calibration_error(self) -> float:
        """Absolute difference between predicted and observed accuracy."""
        return abs(self.midpoint - self.observed_accuracy)


@dataclass
class DomainConfidenceProfile:
    """Per-domain confidence reliability profile."""
    domain: str = "general"
    total_predictions: int = 0
    correct_predictions: int = 0
    mean_predicted_confidence: float = 0.5
    empirical_accuracy: float = 0.5
    calibration_error: float = 0.0  # ECE
    overconfidence_score: float = 0.0   # How much it overestimates
    underconfidence_score: float = 0.0  # How much it underestimates
    reliability_tier: str = "unknown"   # excellent, good, moderate, poor, unreliable

    @property
    def is_overconfident(self) -> bool:
        return self.mean_predicted_confidence > self.empirical_accuracy + 0.05

    @property
    def is_underconfident(self) -> bool:
        return self.mean_predicted_confidence < self.empirical_accuracy - 0.05


@dataclass
class CalibrationReport:
    """Full calibration report across all domains."""
    overall_ece: float = 0.0         # Expected Calibration Error
    overall_accuracy: float = 0.0
    total_predictions: int = 0
    domain_profiles: Dict[str, DomainConfidenceProfile] = field(default_factory=dict)
    buckets: List[CalibrationBucket] = field(default_factory=list)
    reliability_ranking: List[str] = field(default_factory=list)  # Domains sorted by reliability


# ──────────────────────────────────────────────
# Calibration History
# ──────────────────────────────────────────────

class CalibrationHistory:
    """
    Tracks (predicted_confidence, actual_correctness) pairs and
    computes ECE (Expected Calibration Error).
    """

    def __init__(self, max_history: int = 10000, num_buckets: int = 10):
        self._history: List[CalibrationPoint] = []
        self._max_history = max_history
        self._num_buckets = num_buckets
        self._domain_history: Dict[str, List[CalibrationPoint]] = defaultdict(list)

    def record(self, predicted_confidence: float, was_correct: bool,
               domain: str = "general", task_type: str = ""):
        """Record a prediction outcome."""
        point = CalibrationPoint(
            predicted_confidence=max(0, min(1, predicted_confidence)),
            was_correct=was_correct,
            domain=domain,
            task_type=task_type,
        )
        self._history.append(point)
        self._domain_history[domain].append(point)

        # Enforce limits
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        for d in self._domain_history:
            if len(self._domain_history[d]) > self._max_history // 5:
                self._domain_history[d] = self._domain_history[d][-(self._max_history // 5):]

    def compute_ece(self, domain: str = None) -> float:
        """Compute Expected Calibration Error."""
        points = self._domain_history.get(domain, []) if domain else self._history
        if not points:
            return 0.0

        buckets = self._build_buckets(points)
        total = len(points)
        ece = 0.0

        for bucket in buckets:
            if bucket.total_predictions > 0:
                weight = bucket.total_predictions / total
                ece += weight * bucket.calibration_error

        return ece

    def _build_buckets(self, points: List[CalibrationPoint]) -> List[CalibrationBucket]:
        """Build confidence buckets for ECE computation."""
        bucket_size = 1.0 / self._num_buckets
        buckets = []

        for i in range(self._num_buckets):
            b_min = i * bucket_size
            b_max = (i + 1) * bucket_size
            bucket = CalibrationBucket(bucket_min=b_min, bucket_max=b_max)

            for point in points:
                if b_min <= point.predicted_confidence < b_max or (
                    i == self._num_buckets - 1 and point.predicted_confidence == 1.0
                ):
                    bucket.total_predictions += 1
                    if point.was_correct:
                        bucket.correct_predictions += 1

            buckets.append(bucket)

        return buckets

    def get_domain_stats(self, domain: str) -> Optional[DomainConfidenceProfile]:
        """Get calibration profile for a specific domain."""
        points = self._domain_history.get(domain, [])
        if not points:
            return None

        correct = sum(1 for p in points if p.was_correct)
        mean_conf = sum(p.predicted_confidence for p in points) / len(points)
        accuracy = correct / len(points)
        ece = self.compute_ece(domain)

        # Determine reliability tier
        if ece < 0.05 and len(points) >= 20:
            tier = "excellent"
        elif ece < 0.10:
            tier = "good"
        elif ece < 0.20:
            tier = "moderate"
        elif ece < 0.35:
            tier = "poor"
        else:
            tier = "unreliable"

        return DomainConfidenceProfile(
            domain=domain,
            total_predictions=len(points),
            correct_predictions=correct,
            mean_predicted_confidence=round(mean_conf, 4),
            empirical_accuracy=round(accuracy, 4),
            calibration_error=round(ece, 4),
            overconfidence_score=round(max(0, mean_conf - accuracy), 4),
            underconfidence_score=round(max(0, accuracy - mean_conf), 4),
            reliability_tier=tier,
        )

    @property
    def domains(self) -> List[str]:
        return list(self._domain_history.keys())


# ──────────────────────────────────────────────
# Bayesian Calibrator
# ──────────────────────────────────────────────

class BayesianCalibrator:
    """
    Maintains a posterior distribution of model reliability per domain.
    Uses Beta-Binomial conjugate model for analytical updates.

    Prior: Beta(alpha, beta) for each domain
    Update: observe correct → alpha += 1, observe wrong → beta += 1
    Posterior mean = alpha / (alpha + beta) = estimated reliability
    """

    def __init__(self, prior_alpha: float = 2.0, prior_beta: float = 2.0):
        self._prior_alpha = prior_alpha
        self._prior_beta = prior_beta
        self._domain_params: Dict[str, Tuple[float, float]] = {}

    def update(self, domain: str, was_correct: bool):
        """Update the posterior for a domain based on a new observation."""
        alpha, beta = self._domain_params.get(
            domain, (self._prior_alpha, self._prior_beta)
        )
        if was_correct:
            alpha += 1
        else:
            beta += 1
        self._domain_params[domain] = (alpha, beta)

    def get_reliability(self, domain: str) -> float:
        """Get the posterior mean (estimated reliability) for a domain."""
        alpha, beta = self._domain_params.get(
            domain, (self._prior_alpha, self._prior_beta)
        )
        return alpha / (alpha + beta)

    def get_confidence_interval(self, domain: str, level: float = 0.95
                                 ) -> Tuple[float, float]:
        """Get credible interval for domain reliability."""
        alpha, beta = self._domain_params.get(
            domain, (self._prior_alpha, self._prior_beta)
        )
        # Approximate using normal approximation to Beta
        mean = alpha / (alpha + beta)
        var = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
        std = math.sqrt(var) if var > 0 else 0
        z = 1.96 if level >= 0.95 else 1.645  # Simplified
        return (max(0, mean - z * std), min(1, mean + z * std))

    def get_surprise(self, domain: str, predicted_confidence: float) -> float:
        """How surprising is this confidence given what we know about the domain?"""
        reliability = self.get_reliability(domain)
        return abs(predicted_confidence - reliability)

    def get_all_domains(self) -> Dict[str, float]:
        """Get reliability estimates for all domains."""
        return {
            domain: self.get_reliability(domain)
            for domain in self._domain_params
        }


# ──────────────────────────────────────────────
# Confidence Adjuster
# ──────────────────────────────────────────────

class ConfidenceAdjuster:
    """
    Applies calibration corrections to raw LLM confidence scores.
    Uses learned mapping from raw → calibrated confidence.
    """

    def __init__(self):
        self._adjustment_map: Dict[str, List[Tuple[float, float]]] = {}

    def learn_adjustment(self, domain: str, history: CalibrationHistory):
        """Learn calibration mapping from history."""
        points = history._domain_history.get(domain, [])
        if len(points) < 10:
            return  # Not enough data

        # Group predictions into buckets and compute actual accuracy
        bucket_size = 0.1
        adjustments = []

        for i in range(10):
            b_min, b_max = i * bucket_size, (i + 1) * bucket_size
            bucket_points = [
                p for p in points
                if b_min <= p.predicted_confidence < b_max
            ]
            if bucket_points:
                predicted = (b_min + b_max) / 2
                actual = sum(1 for p in bucket_points if p.was_correct) / len(bucket_points)
                adjustments.append((predicted, actual))

        self._adjustment_map[domain] = adjustments

    def adjust(self, raw_confidence: float, domain: str = "general") -> float:
        """Apply calibration adjustment to a raw confidence score."""
        adjustments = self._adjustment_map.get(domain, [])
        if not adjustments:
            return raw_confidence

        # Linear interpolation between nearest calibration points
        for i, (pred, actual) in enumerate(adjustments):
            if raw_confidence <= pred:
                if i == 0:
                    return actual
                prev_pred, prev_actual = adjustments[i - 1]
                t = (raw_confidence - prev_pred) / max(pred - prev_pred, 0.001)
                return prev_actual + t * (actual - prev_actual)

        return adjustments[-1][1]


# ──────────────────────────────────────────────
# Confidence Calibration Oracle (Main Interface)
# ──────────────────────────────────────────────

class ConfidenceOracle:
    """
    The main oracle that calibrates and adjusts model confidence.

    Usage:
        oracle = ConfidenceOracle()

        # Before making a decision, calibrate confidence
        calibrated = oracle.calibrate(raw_confidence=0.9, domain="code_review")
        # calibrated might be 0.75 if the model tends to be overconfident here

        # After the decision, record outcome for learning
        oracle.record_outcome(predicted=0.9, was_correct=True, domain="code_review")

        # Get reliability report
        report = oracle.generate_report()
    """

    def __init__(self):
        self.history = CalibrationHistory()
        self.bayesian = BayesianCalibrator()
        self.adjuster = ConfidenceAdjuster()

    def calibrate(self, raw_confidence: float, domain: str = "general") -> float:
        """Calibrate a raw confidence score using learned adjustments."""
        # Step 1: Apply learned calibration mapping
        adjusted = self.adjuster.adjust(raw_confidence, domain)

        # Step 2: Blend with Bayesian reliability estimate
        reliability = self.bayesian.get_reliability(domain)
        surprise = self.bayesian.get_surprise(domain, raw_confidence)

        # If the model is being unusually confident for this domain, discount
        if surprise > 0.3:
            adjusted = adjusted * 0.8 + reliability * 0.2

        return max(0.0, min(1.0, round(adjusted, 4)))

    def record_outcome(self, predicted: float, was_correct: bool,
                       domain: str = "general", task_type: str = ""):
        """Record a prediction outcome for calibration learning."""
        self.history.record(predicted, was_correct, domain, task_type)
        self.bayesian.update(domain, was_correct)

        # Periodically re-learn adjustments
        domain_count = len(self.history._domain_history.get(domain, []))
        if domain_count % 25 == 0:
            self.adjuster.learn_adjustment(domain, self.history)

    def get_domain_reliability(self, domain: str) -> float:
        """Get estimated reliability for a domain."""
        return self.bayesian.get_reliability(domain)

    def generate_report(self) -> CalibrationReport:
        """Generate a full calibration report."""
        report = CalibrationReport(
            overall_ece=self.history.compute_ece(),
            total_predictions=len(self.history._history),
        )

        if self.history._history:
            report.overall_accuracy = sum(
                1 for p in self.history._history if p.was_correct
            ) / len(self.history._history)

        # Per-domain profiles
        for domain in self.history.domains:
            profile = self.history.get_domain_stats(domain)
            if profile:
                report.domain_profiles[domain] = profile

        # Reliability ranking
        report.reliability_ranking = sorted(
            report.domain_profiles.keys(),
            key=lambda d: report.domain_profiles[d].empirical_accuracy,
            reverse=True,
        )

        report.buckets = self.history._build_buckets(self.history._history)

        return report

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_predictions": len(self.history._history),
            "domains_tracked": len(self.history.domains),
            "overall_ece": round(self.history.compute_ece(), 4),
            "domain_reliabilities": self.bayesian.get_all_domains(),
        }
