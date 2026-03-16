"""
Adaptive Learning Pipeline — Self-Improving Feedback Loop
═════════════════════════════════════════════════════════
The system learns from every interaction, adjusting its own
behavior based on user corrections, successful patterns, and
performance signals.

Capabilities:
  1. Correction Learning   — Learns from user fixes/overrides
  2. Strategy Optimization — Tracks which reasoning strategies
                             work best per domain
  3. Parameter Tuning      — Auto-adjusts confidence thresholds
  4. Feedback Signals      — Implicit (timing, retries) & explicit
  5. Learning Decay        — Old lessons lose weight over time
  6. Performance Tracking  — Measures improvement over time
"""

import hashlib
import json
import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    EXPLICIT_POSITIVE = "explicit_positive"   # User said "good"
    EXPLICIT_NEGATIVE = "explicit_negative"   # User corrected/complained
    IMPLICIT_ACCEPT = "implicit_accept"       # User used the result without complaint
    IMPLICIT_RETRY = "implicit_retry"         # User retried / rephrased
    IMPLICIT_ABANDON = "implicit_abandon"     # User moved on without using result
    CORRECTION = "correction"                 # User provided a correction
    RATING = "rating"                         # Numeric rating (1-5)


class LearningDomain(Enum):
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    CONVERSATION = "conversation"
    TASK_EXECUTION = "task_execution"
    INFORMATION = "information"
    CREATIVE = "creative"


@dataclass
class FeedbackSignal:
    """A single feedback data point."""
    signal_id: str = ""
    feedback_type: FeedbackType = FeedbackType.IMPLICIT_ACCEPT
    domain: LearningDomain = LearningDomain.CONVERSATION
    strategy_used: str = ""     # Which reasoning strategy was used
    original_query: str = ""
    original_response: str = ""
    correction: str = ""
    rating: float = 0.0         # -1 to 1 normalized
    response_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = hashlib.md5(
                f"{self.feedback_type.value}_{self.timestamp}".encode()
            ).hexdigest()[:10]
        # Normalize rating based on feedback type
        if self.rating == 0.0:
            type_ratings = {
                FeedbackType.EXPLICIT_POSITIVE: 1.0,
                FeedbackType.EXPLICIT_NEGATIVE: -1.0,
                FeedbackType.IMPLICIT_ACCEPT: 0.3,
                FeedbackType.IMPLICIT_RETRY: -0.5,
                FeedbackType.IMPLICIT_ABANDON: -0.7,
                FeedbackType.CORRECTION: -0.3,
            }
            self.rating = type_ratings.get(self.feedback_type, 0.0)


@dataclass
class StrategyPerformance:
    """Performance record for a strategy in a domain."""
    strategy: str = ""
    domain: str = ""
    total_uses: int = 0
    success_count: int = 0
    failure_count: int = 0
    cumulative_rating: float = 0.0
    avg_response_time_ms: float = 0.0
    last_used: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        if self.total_uses == 0:
            return 0.5
        return self.success_count / self.total_uses

    @property
    def avg_rating(self) -> float:
        if self.total_uses == 0:
            return 0.0
        return self.cumulative_rating / self.total_uses

    @property
    def score(self) -> float:
        """Composite score combining success rate, rating, and recency."""
        recency = math.exp(-0.01 * (time.time() - self.last_used) / 3600)
        return (self.success_rate * 0.4 + (self.avg_rating + 1) / 2 * 0.4 + recency * 0.2)


@dataclass
class LearningInsight:
    """A distilled learning from accumulated feedback."""
    insight_id: str = ""
    domain: str = ""
    pattern: str = ""            # What pattern was discovered
    recommendation: str = ""     # What to do differently
    confidence: float = 0.5
    evidence_count: int = 0
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.insight_id:
            self.insight_id = hashlib.md5(
                f"{self.domain}_{self.pattern}_{self.created_at}".encode()
            ).hexdigest()[:10]


@dataclass
class AdaptiveParameters:
    """Auto-tuning parameters that change based on learning."""
    confidence_threshold: float = 0.7
    max_thinking_iterations: int = 5
    preferred_strategies: Dict[str, str] = field(default_factory=dict)
    domain_weights: Dict[str, float] = field(default_factory=dict)
    verbosity_level: float = 0.5  # 0=terse, 1=verbose
    creativity_level: float = 0.5


class AdaptiveLearner:
    """
    Self-improving feedback loop that learns from every interaction.
    Tracks strategy performance, processes corrections, auto-tunes
    parameters, and generates actionable learning insights.
    """

    MAX_SIGNALS = 10000
    MAX_INSIGHTS = 200
    DECAY_RATE = 0.005

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path("data/learning")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._signals: Deque[FeedbackSignal] = deque(maxlen=self.MAX_SIGNALS)
        self._strategy_perf: Dict[str, StrategyPerformance] = {}
        self._corrections: Deque[Dict] = deque(maxlen=500)
        self._insights: List[LearningInsight] = []
        self._parameters = AdaptiveParameters()
        self._improvement_log: Deque[Dict] = deque(maxlen=200)

        self._load()
        logger.info("[LEARN] Adaptive Learning Pipeline initialized")

    # ── Feedback Processing ──

    def record_feedback(self, feedback_type: FeedbackType,
                        domain: LearningDomain = LearningDomain.CONVERSATION,
                        strategy: str = "default",
                        query: str = "", response: str = "",
                        correction: str = "", rating: float = 0.0,
                        response_time_ms: float = 0.0,
                        metadata: Dict = None) -> FeedbackSignal:
        """Record a feedback signal from an interaction."""
        signal = FeedbackSignal(
            feedback_type=feedback_type, domain=domain,
            strategy_used=strategy, original_query=query,
            original_response=response[:500], correction=correction[:500],
            rating=rating, response_time_ms=response_time_ms,
            metadata=metadata or {},
        )
        self._signals.append(signal)

        # Update strategy performance
        key = f"{strategy}_{domain.value}"
        if key not in self._strategy_perf:
            self._strategy_perf[key] = StrategyPerformance(
                strategy=strategy, domain=domain.value,
            )
        perf = self._strategy_perf[key]
        perf.total_uses += 1
        perf.cumulative_rating += signal.rating
        perf.last_used = time.time()
        if signal.rating > 0:
            perf.success_count += 1
        elif signal.rating < -0.3:
            perf.failure_count += 1
        if response_time_ms > 0:
            perf.avg_response_time_ms = (
                (perf.avg_response_time_ms * (perf.total_uses - 1) + response_time_ms)
                / perf.total_uses
            )

        # Store corrections for pattern learning
        if feedback_type == FeedbackType.CORRECTION and correction:
            self._corrections.append({
                "query": query[:200],
                "original": response[:200],
                "correction": correction[:200],
                "domain": domain.value,
                "timestamp": time.time(),
            })

        # Periodically auto-tune
        if len(self._signals) % 20 == 0:
            self._auto_tune()

        return signal

    def record_implicit(self, query: str, response: str,
                        strategy: str = "default",
                        domain: LearningDomain = LearningDomain.CONVERSATION,
                        user_followed_up: bool = False,
                        user_rephrased: bool = False,
                        response_time_ms: float = 0.0) -> None:
        """Record implicit feedback signals."""
        if user_rephrased:
            ftype = FeedbackType.IMPLICIT_RETRY
        elif user_followed_up:
            ftype = FeedbackType.IMPLICIT_ACCEPT
        else:
            ftype = FeedbackType.IMPLICIT_ACCEPT

        self.record_feedback(
            feedback_type=ftype, domain=domain, strategy=strategy,
            query=query, response=response,
            response_time_ms=response_time_ms,
        )

    # ── Strategy Optimization ──

    def get_best_strategy(self, domain: LearningDomain) -> str:
        """Get the best-performing strategy for a domain."""
        domain_str = domain.value
        candidates = {
            k: v for k, v in self._strategy_perf.items()
            if v.domain == domain_str and v.total_uses >= 3
        }
        if not candidates:
            return self._parameters.preferred_strategies.get(domain_str, "default")

        best_key = max(candidates, key=lambda k: candidates[k].score)
        return candidates[best_key].strategy

    def get_strategy_ranking(self, domain: LearningDomain = None) -> List[Dict]:
        """Get ranked strategies with performance data."""
        candidates = self._strategy_perf.values()
        if domain:
            candidates = [c for c in candidates if c.domain == domain.value]

        ranked = sorted(candidates, key=lambda p: p.score, reverse=True)
        return [
            {
                "strategy": p.strategy,
                "domain": p.domain,
                "score": round(p.score, 3),
                "success_rate": round(p.success_rate, 3),
                "avg_rating": round(p.avg_rating, 3),
                "uses": p.total_uses,
            }
            for p in ranked
        ]

    # ── Auto-Tuning ──

    def _auto_tune(self) -> None:
        """Auto-tune parameters based on accumulated feedback."""
        recent = [s for s in self._signals if time.time() - s.timestamp < 3600]
        if len(recent) < 5:
            return

        # Adjust confidence threshold
        avg_rating = sum(s.rating for s in recent) / len(recent)
        if avg_rating < -0.2:
            self._parameters.confidence_threshold = min(0.95,
                self._parameters.confidence_threshold + 0.02)
        elif avg_rating > 0.3:
            self._parameters.confidence_threshold = max(0.5,
                self._parameters.confidence_threshold - 0.01)

        # Adjust verbosity based on retry rate
        retries = sum(1 for s in recent if s.feedback_type == FeedbackType.IMPLICIT_RETRY)
        retry_rate = retries / max(len(recent), 1)
        if retry_rate > 0.3:
            self._parameters.verbosity_level = min(1.0,
                self._parameters.verbosity_level + 0.05)

        # Update preferred strategies per domain
        for domain in LearningDomain:
            best = self.get_best_strategy(domain)
            if best != "default":
                self._parameters.preferred_strategies[domain.value] = best

        self._improvement_log.append({
            "timestamp": time.time(),
            "confidence_threshold": self._parameters.confidence_threshold,
            "verbosity": self._parameters.verbosity_level,
            "avg_rating": avg_rating,
            "signals_processed": len(recent),
        })

    def get_parameters(self) -> Dict[str, Any]:
        """Get current adaptive parameters."""
        return {
            "confidence_threshold": self._parameters.confidence_threshold,
            "max_thinking_iterations": self._parameters.max_thinking_iterations,
            "preferred_strategies": self._parameters.preferred_strategies,
            "verbosity_level": self._parameters.verbosity_level,
            "creativity_level": self._parameters.creativity_level,
        }

    # ── Insight Generation ──

    def generate_insights(self) -> List[LearningInsight]:
        """Analyze accumulated feedback to generate learning insights."""
        insights = []

        # Insight: Domains with consistently poor performance
        for domain in LearningDomain:
            domain_signals = [s for s in self._signals if s.domain == domain]
            if len(domain_signals) < 5:
                continue
            recent = domain_signals[-20:]
            avg = sum(s.rating for s in recent) / len(recent)
            if avg < -0.3:
                insights.append(LearningInsight(
                    domain=domain.value,
                    pattern=f"Consistently poor performance in {domain.value}",
                    recommendation=f"Consider using different strategies for {domain.value} tasks",
                    confidence=min(0.9, len(recent) / 20),
                    evidence_count=len(recent),
                ))

        # Insight: Common correction patterns
        if len(self._corrections) >= 3:
            domains_corrected = defaultdict(int)
            for c in self._corrections:
                domains_corrected[c["domain"]] += 1
            for domain, count in domains_corrected.items():
                if count >= 3:
                    insights.append(LearningInsight(
                        domain=domain,
                        pattern=f"Frequent corrections in {domain} ({count} times)",
                        recommendation=f"Review response patterns for {domain} queries",
                        confidence=min(0.85, count / 10),
                        evidence_count=count,
                    ))

        # Insight: Strategy that outperforms others
        for domain in LearningDomain:
            ranking = self.get_strategy_ranking(domain)
            if len(ranking) >= 2 and ranking[0]["uses"] >= 5:
                top = ranking[0]
                if top["score"] > ranking[1]["score"] * 1.3:
                    insights.append(LearningInsight(
                        domain=domain.value,
                        pattern=f"Strategy '{top['strategy']}' significantly outperforms others",
                        recommendation=f"Prioritize '{top['strategy']}' for {domain.value}",
                        confidence=top["score"],
                        evidence_count=top["uses"],
                    ))

        self._insights = insights
        return insights

    # ── Correction Context ──

    def get_correction_context(self, query: str, domain: str = "") -> str:
        """Get relevant past corrections to improve future responses."""
        relevant = []
        query_lower = query.lower()
        for c in self._corrections:
            if domain and c["domain"] != domain:
                continue
            if any(word in c["query"].lower() for word in query_lower.split()[:5]):
                relevant.append(c)

        if not relevant:
            return ""

        context = "LEARNING FROM PAST CORRECTIONS:\n"
        for c in relevant[-3:]:
            context += f"- Query: {c['query'][:100]}\n"
            context += f"  Wrong: {c['original'][:80]}\n"
            context += f"  Fixed: {c['correction'][:80]}\n"
        return context

    # ── Persistence ──

    def save(self) -> None:
        try:
            data = {
                "strategy_perf": {
                    k: {
                        "strategy": v.strategy, "domain": v.domain,
                        "total_uses": v.total_uses,
                        "success_count": v.success_count,
                        "failure_count": v.failure_count,
                        "cumulative_rating": v.cumulative_rating,
                        "avg_response_time_ms": v.avg_response_time_ms,
                    }
                    for k, v in self._strategy_perf.items()
                },
                "corrections": list(self._corrections),
                "parameters": self.get_parameters(),
            }
            path = self.data_dir / "learning_state.json"
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.error(f"[LEARN] Save failed: {e}")

    def _load(self) -> None:
        path = self.data_dir / "learning_state.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for k, v in data.get("strategy_perf", {}).items():
                self._strategy_perf[k] = StrategyPerformance(**v)
            for c in data.get("corrections", []):
                self._corrections.append(c)
            params = data.get("parameters", {})
            if params:
                self._parameters.confidence_threshold = params.get("confidence_threshold", 0.7)
                self._parameters.verbosity_level = params.get("verbosity_level", 0.5)
                self._parameters.preferred_strategies = params.get("preferred_strategies", {})
        except Exception as e:
            logger.warning(f"[LEARN] Load failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_signals": len(self._signals),
            "total_corrections": len(self._corrections),
            "strategies_tracked": len(self._strategy_perf),
            "insights": len(self._insights),
            "parameters": self.get_parameters(),
            "improvement_log_size": len(self._improvement_log),
        }
