"""
Metrics Collector — OpenTelemetry-Inspired Metrics Engine
═════════════════════════════════════════════════════════
Production-grade metrics aggregation with:
  - Histograms (latency distributions with p50/p95/p99)
  - Counters (monotonic event counts)
  - Gauges (point-in-time values)
  - Labels (dimensional filtering)
  - JSON export for dashboards

Zero external dependencies. Thread-safe.
"""

import json
import logging
import math
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

@dataclass
class HistogramBucket:
    """Aggregated histogram bucket."""
    le: float  # Upper bound
    count: int = 0


@dataclass
class HistogramSummary:
    """Summary statistics of a histogram."""
    name: str
    count: int = 0
    sum: float = 0.0
    mean: float = 0.0
    min: float = 0.0
    max: float = 0.0
    stddev: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class CounterValue:
    """Counter state."""
    value: int = 0
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class GaugeValue:
    """Gauge state."""
    value: float = 0.0
    timestamp: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricsReport:
    """Full metrics export."""
    timestamp: str = ""
    uptime_seconds: float = 0.0
    histograms: List[Dict[str, Any]] = field(default_factory=list)
    counters: List[Dict[str, Any]] = field(default_factory=list)
    gauges: List[Dict[str, Any]] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════
# Metrics Collector (Thread-Safe Singleton)
# ══════════════════════════════════════════════════════════════

class MetricsCollector:
    """
    Production-grade metrics collector.

    Usage:
        metrics = MetricsCollector.get_instance()

        # Histograms (latency, durations)
        metrics.histogram("thinking_loop.latency_ms", 150.3, {"domain": "coding"})
        metrics.histogram("thinking_loop.latency_ms", 200.1, {"domain": "coding"})

        # Counters (events, errors)
        metrics.counter("tool_calls.total", labels={"tool": "web_search"})
        metrics.counter("errors.total", delta=1, labels={"type": "timeout"})

        # Gauges (current state)
        metrics.gauge("memory.active_items", 42.0)
        metrics.gauge("thinking_loop.confidence", 0.85)

        # Export
        report = metrics.get_report()
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._histogram_labels: Dict[str, Dict[str, str]] = {}
        self._counters: Dict[str, int] = defaultdict(int)
        self._counter_labels: Dict[str, Dict[str, str]] = {}
        self._gauges: Dict[str, Tuple[float, float]] = {}  # (value, timestamp)
        self._gauge_labels: Dict[str, Dict[str, str]] = {}
        self._start_time = time.time()
        self._data_lock = threading.Lock()
        self._max_histogram_samples = 10000

    @classmethod
    def get_instance(cls) -> "MetricsCollector":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    # ── Histogram ──

    def histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a value in a histogram (e.g., latency, duration)."""
        key = self._make_key(name, labels)
        with self._data_lock:
            samples = self._histograms[key]
            samples.append(value)
            # Rolling window: keep last N samples
            if len(samples) > self._max_histogram_samples:
                self._histograms[key] = samples[-self._max_histogram_samples:]
            if labels:
                self._histogram_labels[key] = labels

    def get_histogram(self, name: str, labels: Dict[str, str] = None) -> HistogramSummary:
        """Get histogram summary with percentiles."""
        key = self._make_key(name, labels)
        with self._data_lock:
            samples = list(self._histograms.get(key, []))
            stored_labels = self._histogram_labels.get(key, {})

        if not samples:
            return HistogramSummary(name=name, labels=stored_labels)

        samples.sort()
        n = len(samples)
        return HistogramSummary(
            name=name,
            count=n,
            sum=sum(samples),
            mean=round(statistics.mean(samples), 4),
            min=round(min(samples), 4),
            max=round(max(samples), 4),
            stddev=round(statistics.stdev(samples), 4) if n > 1 else 0.0,
            p50=round(samples[n // 2], 4),
            p90=round(samples[int(n * 0.9)], 4),
            p95=round(samples[int(n * 0.95)], 4),
            p99=round(samples[int(n * 0.99)], 4),
            labels=stored_labels,
        )

    # ── Counter ──

    def counter(self, name: str, delta: int = 1, labels: Dict[str, str] = None):
        """Increment a counter."""
        key = self._make_key(name, labels)
        with self._data_lock:
            self._counters[key] += delta
            if labels:
                self._counter_labels[key] = labels

    def get_counter(self, name: str, labels: Dict[str, str] = None) -> int:
        """Get current counter value."""
        key = self._make_key(name, labels)
        with self._data_lock:
            return self._counters.get(key, 0)

    # ── Gauge ──

    def gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge to a specific value."""
        key = self._make_key(name, labels)
        with self._data_lock:
            self._gauges[key] = (value, time.time())
            if labels:
                self._gauge_labels[key] = labels

    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> float:
        """Get current gauge value."""
        key = self._make_key(name, labels)
        with self._data_lock:
            return self._gauges.get(key, (0.0, 0))[0]

    # ── Reporting ──

    def get_report(self) -> MetricsReport:
        """Generate full metrics report."""
        with self._data_lock:
            histograms = []
            for key, samples in self._histograms.items():
                if not samples:
                    continue
                name = key.split("{")[0]
                labels = self._histogram_labels.get(key, {})
                sorted_samples = sorted(samples)
                n = len(sorted_samples)
                histograms.append({
                    "name": name,
                    "count": n,
                    "sum": round(sum(sorted_samples), 4),
                    "mean": round(statistics.mean(sorted_samples), 4),
                    "min": round(min(sorted_samples), 4),
                    "max": round(max(sorted_samples), 4),
                    "p50": round(sorted_samples[n // 2], 4),
                    "p95": round(sorted_samples[int(n * 0.95)], 4),
                    "p99": round(sorted_samples[int(n * 0.99)], 4),
                    "labels": labels,
                })

            counters = []
            for key, value in self._counters.items():
                name = key.split("{")[0]
                labels = self._counter_labels.get(key, {})
                counters.append({"name": name, "value": value, "labels": labels})

            gauges = []
            for key, (value, ts) in self._gauges.items():
                name = key.split("{")[0]
                labels = self._gauge_labels.get(key, {})
                gauges.append({"name": name, "value": round(value, 4), "timestamp": ts, "labels": labels})

        return MetricsReport(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            uptime_seconds=round(time.time() - self._start_time, 2),
            histograms=histograms,
            counters=counters,
            gauges=gauges,
        )

    def export_json(self, filepath: str = None) -> str:
        """Export metrics as JSON."""
        report = self.get_report()
        data = {
            "timestamp": report.timestamp,
            "uptime_seconds": report.uptime_seconds,
            "histograms": report.histograms,
            "counters": report.counters,
            "gauges": report.gauges,
        }
        json_str = json.dumps(data, indent=2, default=str)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str

    # ── Internal ──

    @staticmethod
    def _make_key(name: str, labels: Dict[str, str] = None) -> str:
        """Create a unique key from name + labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
