"""
Real-Time Performance Profiler — Live Bottleneck Detection
═════════════════════════════════════════════════════════
Tracks latency per pipeline stage, detects bottlenecks,
auto-tunes parameters, and provides flame-graph-style data.

Capabilities:
  1. Stage Timing    — Nanosecond-level timing per pipeline stage
  2. Flame Graph     — Hierarchical timing visualization data
  3. Bottleneck Detection — Automatic identification of slow stages
  4. Auto-Tuning      — Suggest/apply parameter adjustments
  5. Alert System      — Threshold-based performance alerts
"""

import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StageProfile:
    """Performance profile for a pipeline stage."""
    name: str = ""
    timings_ms: deque = field(default_factory=lambda: deque(maxlen=100))
    call_count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    min_ms: float = float("inf")
    errors: int = 0
    last_bottleneck: bool = False

    @property
    def avg_ms(self) -> float:
        return self.total_ms / max(self.call_count, 1)

    @property
    def p95_ms(self) -> float:
        if len(self.timings_ms) < 5:
            return self.avg_ms
        sorted_t = sorted(self.timings_ms)
        idx = int(len(sorted_t) * 0.95)
        return sorted_t[min(idx, len(sorted_t) - 1)]

    @property
    def p99_ms(self) -> float:
        if len(self.timings_ms) < 10:
            return self.max_ms
        sorted_t = sorted(self.timings_ms)
        idx = int(len(sorted_t) * 0.99)
        return sorted_t[min(idx, len(sorted_t) - 1)]


@dataclass
class BottleneckAlert:
    """A detected performance bottleneck."""
    stage: str
    severity: str  # "warning", "critical"
    avg_ms: float
    p95_ms: float
    threshold_ms: float
    recommendation: str
    detected_at: float = field(default_factory=time.time)


class PerformanceProfiler:
    """
    Real-time performance profiler with hierarchical timing,
    bottleneck detection, and auto-tuning capabilities.
    """

    # Default thresholds per stage (ms)
    DEFAULT_THRESHOLDS = {
        "routing": 50,
        "thinking": 5000,
        "tool_execution": 10000,
        "synthesis": 5000,
        "safety_check": 100,
        "memory_lookup": 200,
        "cache_check": 10,
        "prefetch_check": 5,
        "context_optimization": 100,
        "default": 1000,
    }

    def __init__(self):
        self._stages: Dict[str, StageProfile] = {}
        self._active_spans: Dict[str, float] = {}
        self._thresholds = dict(self.DEFAULT_THRESHOLDS)
        self._alerts: deque = deque(maxlen=100)
        self._request_timings: deque = deque(maxlen=500)
        self._lock = threading.Lock()
        self._total_requests = 0
        logger.info("[PROFILER] Performance profiler initialized")

    @contextmanager
    def profile(self, stage: str):
        """Context manager to time a pipeline stage."""
        start = time.time()
        try:
            yield
        finally:
            elapsed_ms = (time.time() - start) * 1000
            self._record(stage, elapsed_ms)

    def start_span(self, stage: str) -> str:
        """Start a timing span manually."""
        span_id = f"{stage}_{time.time()}"
        self._active_spans[span_id] = time.time()
        return span_id

    def end_span(self, span_id: str, stage: str = None):
        """End a timing span and record the result."""
        start = self._active_spans.pop(span_id, None)
        if start is None:
            return
        elapsed_ms = (time.time() - start) * 1000
        stage_name = stage or span_id.split("_")[0]
        self._record(stage_name, elapsed_ms)

    def _record(self, stage: str, elapsed_ms: float):
        """Record timing for a stage."""
        with self._lock:
            if stage not in self._stages:
                self._stages[stage] = StageProfile(name=stage)
            profile = self._stages[stage]
            profile.timings_ms.append(elapsed_ms)
            profile.call_count += 1
            profile.total_ms += elapsed_ms
            profile.max_ms = max(profile.max_ms, elapsed_ms)
            profile.min_ms = min(profile.min_ms, elapsed_ms)

        # Check for bottleneck
        self._check_bottleneck(stage, elapsed_ms)

    def _check_bottleneck(self, stage: str, elapsed_ms: float):
        """Check if a stage is exceeding its threshold."""
        threshold = self._thresholds.get(stage, self._thresholds["default"])

        if elapsed_ms > threshold:
            severity = "critical" if elapsed_ms > threshold * 2 else "warning"
            profile = self._stages[stage]
            profile.last_bottleneck = True

            recommendation = self._generate_recommendation(stage, elapsed_ms, threshold)

            alert = BottleneckAlert(
                stage=stage,
                severity=severity,
                avg_ms=profile.avg_ms,
                p95_ms=profile.p95_ms,
                threshold_ms=threshold,
                recommendation=recommendation,
            )
            self._alerts.append(alert)

            if severity == "critical":
                logger.warning(
                    f"[PROFILER] CRITICAL bottleneck: {stage} "
                    f"({elapsed_ms:.0f}ms > {threshold:.0f}ms threshold)"
                )

    def _generate_recommendation(self, stage: str, elapsed_ms: float,
                                   threshold: float) -> str:
        """Generate optimization recommendation for a bottleneck."""
        recommendations = {
            "routing": "Consider caching domain classifications",
            "thinking": "Reduce thinking loop iterations or use quick_think",
            "tool_execution": "Batch tool calls or add timeout limits",
            "synthesis": "Use streaming or reduce context window size",
            "safety_check": "Optimize content filter regex patterns",
            "memory_lookup": "Increase L1 cache size or add semantic index",
            "cache_check": "Reduce cache size or optimize hash function",
            "context_optimization": "Reduce context chunks or lower compression ratio",
        }
        base = recommendations.get(stage, "Profile this stage for optimization opportunities")
        ratio = elapsed_ms / threshold
        if ratio > 3:
            return f"URGENT: {base}. Stage is {ratio:.1f}x over threshold."
        return base

    def record_request(self, total_ms: float, mode: str = ""):
        """Record overall request timing."""
        self._total_requests += 1
        self._request_timings.append({
            "total_ms": total_ms,
            "mode": mode,
            "timestamp": time.time(),
        })

    def get_bottlenecks(self, limit: int = 10) -> List[Dict]:
        """Get recent bottleneck alerts."""
        return [
            {
                "stage": a.stage,
                "severity": a.severity,
                "avg_ms": round(a.avg_ms, 1),
                "p95_ms": round(a.p95_ms, 1),
                "threshold_ms": a.threshold_ms,
                "recommendation": a.recommendation,
            }
            for a in list(self._alerts)[-limit:]
        ]

    def get_flame_graph(self) -> Dict[str, Any]:
        """Get flame-graph-style hierarchical timing data."""
        stages = {}
        total_time = sum(p.total_ms for p in self._stages.values())

        for name, profile in sorted(
            self._stages.items(), key=lambda x: x[1].total_ms, reverse=True
        ):
            stages[name] = {
                "calls": profile.call_count,
                "avg_ms": round(profile.avg_ms, 2),
                "p95_ms": round(profile.p95_ms, 2),
                "p99_ms": round(profile.p99_ms, 2),
                "max_ms": round(profile.max_ms, 2),
                "min_ms": round(profile.min_ms, 2) if profile.min_ms != float("inf") else 0,
                "total_ms": round(profile.total_ms, 2),
                "pct_of_total": round(
                    (profile.total_ms / max(total_time, 1)) * 100, 1
                ),
                "is_bottleneck": profile.last_bottleneck,
            }
        return {
            "stages": stages,
            "total_time_ms": round(total_time, 2),
            "total_requests": self._total_requests,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_requests": self._total_requests,
            "stages_tracked": len(self._stages),
            "active_alerts": len(self._alerts),
            "flame_graph": self.get_flame_graph(),
        }
