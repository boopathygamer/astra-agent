"""
Situational Awareness — Real-Time Context Fusion Engine
═══════════════════════════════════════════════════════
Goes beyond raw system metrics. Understands *what* is happening,
*why* it's happening, and *what's likely next*.

Context Layers:
  1. Physical  — Hardware state (CPU, RAM, GPU, disk, thermals)
  2. Digital   — Processes, files, windows, active projects
  3. Temporal  — Time-of-day patterns, day-of-week habits
  4. Behavioral — User activity patterns and routines

Capabilities:
  • Situation Classifier  — "gaming", "coding sprint", "idle", "meeting"
  • Trend Analyzer        — Detects resource trends (leak, spike, fill-up)
  • Event Correlator      — Links related system events into narratives
  • Alert Generator       — Intelligent, actionable alerts (not raw data)
"""

import hashlib
import json
import logging
import os
import platform
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Enums & Data Models
# ══════════════════════════════════════════════════════════════

class SituationType(Enum):
    """Classified system situations."""
    IDLE = "idle"
    DEVELOPMENT = "development"
    GAMING = "gaming"
    MEDIA_CONSUMPTION = "media_consumption"
    HEAVY_COMPUTE = "heavy_compute"
    SYSTEM_MAINTENANCE = "system_maintenance"
    MEETING = "meeting"
    BROWSING = "browsing"
    FILE_TRANSFER = "file_transfer"
    UNDER_ATTACK = "under_attack"
    BOOT_SEQUENCE = "boot_sequence"
    UNKNOWN = "unknown"


class TrendDirection(Enum):
    """Direction of a resource trend."""
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    SPIKE = "spike"
    OSCILLATING = "oscillating"


class AlertSeverity(Enum):
    """Alert importance levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ContextLayer:
    """A single layer of situational context."""
    layer_name: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.0

    def age_seconds(self) -> float:
        return time.time() - self.timestamp


@dataclass
class ResourceTrend:
    """Detected trend in a resource metric."""
    resource_name: str = ""
    direction: TrendDirection = TrendDirection.STABLE
    current_value: float = 0.0
    average_value: float = 0.0
    peak_value: float = 0.0
    change_rate: float = 0.0       # units per minute
    samples: int = 0
    prediction_minutes: float = 0.0  # estimated time until threshold
    threshold: float = 0.0

    def is_concerning(self) -> bool:
        return (
            self.direction in (TrendDirection.RISING, TrendDirection.SPIKE)
            and self.current_value > self.threshold * 0.7
        )


@dataclass
class CorrelatedEvent:
    """A group of correlated system events forming a narrative."""
    event_id: str = ""
    narrative: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
    root_cause: str = ""
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class SituationalAlert:
    """An intelligent, actionable alert."""
    alert_id: str = ""
    severity: AlertSeverity = AlertSeverity.INFO
    title: str = ""
    description: str = ""
    suggestion: str = ""
    source: str = ""
    auto_resolvable: bool = False
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False
    resolved: bool = False

    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = hashlib.md5(
                f"{self.title}_{self.timestamp}".encode()
            ).hexdigest()[:12]


@dataclass
class SituationReport:
    """Complete situational awareness snapshot."""
    timestamp: float = field(default_factory=time.time)
    situation: SituationType = SituationType.UNKNOWN
    situation_confidence: float = 0.0
    context_layers: Dict[str, ContextLayer] = field(default_factory=dict)
    active_trends: List[ResourceTrend] = field(default_factory=list)
    correlated_events: List[CorrelatedEvent] = field(default_factory=list)
    active_alerts: List[SituationalAlert] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "situation": self.situation.value,
            "situation_confidence": self.situation_confidence,
            "summary": self.summary,
            "trends": [
                {
                    "resource": t.resource_name,
                    "direction": t.direction.value,
                    "current": t.current_value,
                    "concerning": t.is_concerning(),
                }
                for t in self.active_trends
            ],
            "alerts": [
                {
                    "severity": a.severity.value,
                    "title": a.title,
                    "suggestion": a.suggestion,
                }
                for a in self.active_alerts if not a.resolved
            ],
            "event_count": len(self.correlated_events),
        }


# ══════════════════════════════════════════════════════════════
# Situational Awareness Engine
# ══════════════════════════════════════════════════════════════

class SituationalAwareness:
    """
    Real-Time Context Fusion Engine.

    Combines multiple context layers (physical, digital, temporal,
    behavioral) into a unified situation classification with trend
    analysis, event correlation, and intelligent alerts.
    """

    MAX_HISTORY = 300        # data points per metric
    TREND_WINDOW = 60        # samples for trend analysis
    CORRELATION_WINDOW = 30  # seconds for event correlation
    ALERT_DEDUP_SECONDS = 120

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path("data/awareness")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Context layers
        self._layers: Dict[str, ContextLayer] = {}

        # Metric history for trend analysis
        self._metric_history: Dict[str, Deque[Tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=self.MAX_HISTORY)
        )

        # Event buffer for correlation
        self._event_buffer: Deque[Dict[str, Any]] = deque(maxlen=500)

        # Alert history
        self._alerts: Deque[SituationalAlert] = deque(maxlen=200)
        self._alert_titles_recent: Dict[str, float] = {}

        # Situation history
        self._situation_history: Deque[Tuple[float, SituationType]] = deque(maxlen=100)

        # Thresholds
        self._thresholds = {
            "cpu_percent": 85.0,
            "ram_percent": 90.0,
            "disk_percent": 95.0,
            "gpu_percent": 90.0,
            "temperature_c": 85.0,
            "swap_percent": 80.0,
        }

        # Situation keywords for classification
        self._situation_signatures = {
            SituationType.DEVELOPMENT: {
                "processes": ["python", "node", "npm", "java", "gcc", "cargo",
                              "dotnet", "code", "vim", "nvim", "idea"],
                "weight": 0.9,
            },
            SituationType.GAMING: {
                "processes": ["steam", "epic", "unity", "unreal", "game"],
                "indicators": {"gpu_high": True, "cpu_high": True},
                "weight": 0.85,
            },
            SituationType.HEAVY_COMPUTE: {
                "indicators": {"cpu_high": True, "ram_high": True},
                "weight": 0.7,
            },
            SituationType.MEDIA_CONSUMPTION: {
                "processes": ["vlc", "spotify", "chrome", "firefox", "edge",
                              "youtube", "netflix"],
                "weight": 0.6,
            },
            SituationType.MEETING: {
                "processes": ["zoom", "teams", "slack", "discord", "meet"],
                "weight": 0.85,
            },
            SituationType.FILE_TRANSFER: {
                "indicators": {"disk_io_high": True, "network_high": True},
                "weight": 0.65,
            },
        }

        self._boot_time = time.time()
        logger.info("[AWARENESS] Situational Awareness engine initialized")

    # ── Context Layer Management ──

    def update_layer(self, layer_name: str, data: Dict[str, Any],
                     confidence: float = 1.0) -> None:
        """Update a context layer with fresh data."""
        self._layers[layer_name] = ContextLayer(
            layer_name=layer_name,
            data=data,
            confidence=confidence,
        )

        # Record metrics for trending
        for key, value in data.items():
            if isinstance(value, (int, float)):
                metric_key = f"{layer_name}.{key}"
                self._metric_history[metric_key].append((time.time(), float(value)))

    def update_physical(self, vitals: Dict[str, Any]) -> None:
        """Update the physical/hardware context layer."""
        self.update_layer("physical", vitals)

    def update_digital(self, processes: List[str] = None,
                       active_windows: List[str] = None,
                       open_files: List[str] = None) -> None:
        """Update the digital context layer."""
        data = {
            "processes": processes or [],
            "active_windows": active_windows or [],
            "open_files": open_files or [],
            "process_count": len(processes) if processes else 0,
        }
        self.update_layer("digital", data)

    def update_temporal(self) -> None:
        """Update the temporal context layer based on current time."""
        now = time.localtime()
        hour = now.tm_hour
        day = now.tm_wday  # 0=Monday

        # Classify time period
        if 6 <= hour < 9:
            period = "early_morning"
        elif 9 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 14:
            period = "lunch"
        elif 14 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 21:
            period = "evening"
        elif 21 <= hour < 24:
            period = "night"
        else:
            period = "late_night"

        is_weekend = day >= 5
        is_work_hours = not is_weekend and 9 <= hour < 17

        data = {
            "hour": hour,
            "day_of_week": day,
            "period": period,
            "is_weekend": is_weekend,
            "is_work_hours": is_work_hours,
            "uptime_minutes": (time.time() - self._boot_time) / 60,
        }
        self.update_layer("temporal", data)

    def update_behavioral(self, interaction_type: str = "",
                          query_complexity: str = "simple") -> None:
        """Update the behavioral context layer with user activity patterns."""
        data = {
            "last_interaction_type": interaction_type,
            "query_complexity": query_complexity,
            "timestamp": time.time(),
        }
        self.update_layer("behavioral", data)

    # ── Situation Classification ──

    def classify_situation(self) -> Tuple[SituationType, float]:
        """
        Classify the current system situation from all context layers.

        Returns (SituationType, confidence).
        """
        scores: Dict[SituationType, float] = defaultdict(float)

        physical = self._layers.get("physical", ContextLayer())
        digital = self._layers.get("digital", ContextLayer())
        temporal = self._layers.get("temporal", ContextLayer())

        # Check process-based signatures
        active_procs = [
            p.lower() for p in digital.data.get("processes", [])
        ]

        for sit_type, sig in self._situation_signatures.items():
            keyw = sig.get("processes", [])
            matched = sum(
                1 for k in keyw
                if any(k in proc for proc in active_procs)
            )
            if matched > 0:
                score = (matched / max(len(keyw), 1)) * sig["weight"]
                scores[sit_type] += score

        # Check indicator-based signatures
        cpu = physical.data.get("cpu_percent", 0)
        ram = physical.data.get("ram_percent", 0)
        gpu = physical.data.get("gpu_percent", 0)

        indicators = {
            "cpu_high": cpu > 70,
            "ram_high": ram > 70,
            "gpu_high": gpu > 60,
            "disk_io_high": physical.data.get("disk_io_high", False),
            "network_high": physical.data.get("network_high", False),
        }

        for sit_type, sig in self._situation_signatures.items():
            req_indicators = sig.get("indicators", {})
            if req_indicators:
                match_count = sum(
                    1 for ind, val in req_indicators.items()
                    if indicators.get(ind) == val
                )
                if match_count == len(req_indicators):
                    scores[sit_type] += sig["weight"] * 0.5

        # Check idle
        if cpu < 10 and ram < 40 and not active_procs:
            scores[SituationType.IDLE] = 0.9

        # Boot sequence (first 2 minutes)
        if time.time() - self._boot_time < 120:
            scores[SituationType.BOOT_SEQUENCE] = 0.8

        if not scores:
            return SituationType.UNKNOWN, 0.0

        best = max(scores, key=scores.get)
        confidence = min(scores[best], 1.0)

        self._situation_history.append((time.time(), best))
        return best, confidence

    # ── Trend Analysis ──

    def analyze_trends(self) -> List[ResourceTrend]:
        """Analyze metric history for concerning trends."""
        trends = []

        for metric_key, history in self._metric_history.items():
            if len(history) < 5:
                continue

            recent = list(history)[-self.TREND_WINDOW:]
            values = [v for _, v in recent]
            timestamps = [t for t, _ in recent]

            current = values[-1]
            average = sum(values) / len(values)
            peak = max(values)

            # Calculate rate of change (per minute)
            if len(timestamps) >= 2:
                time_span = timestamps[-1] - timestamps[0]
                if time_span > 0:
                    value_change = values[-1] - values[0]
                    change_rate = (value_change / time_span) * 60
                else:
                    change_rate = 0.0
            else:
                change_rate = 0.0

            # Determine direction
            if len(values) >= 3:
                recent_3 = values[-3:]
                if all(recent_3[i] < recent_3[i+1] for i in range(len(recent_3)-1)):
                    direction = TrendDirection.RISING
                elif all(recent_3[i] > recent_3[i+1] for i in range(len(recent_3)-1)):
                    direction = TrendDirection.FALLING
                elif peak > average * 2:
                    direction = TrendDirection.SPIKE
                elif max(values) - min(values) > average * 0.5:
                    direction = TrendDirection.OSCILLATING
                else:
                    direction = TrendDirection.STABLE
            else:
                direction = TrendDirection.STABLE

            # Estimate time to threshold
            base_metric = metric_key.split(".")[-1]
            threshold = self._thresholds.get(base_metric, 100.0)
            prediction_minutes = 0.0
            if change_rate > 0 and current < threshold:
                remaining = threshold - current
                prediction_minutes = remaining / change_rate

            trend = ResourceTrend(
                resource_name=metric_key,
                direction=direction,
                current_value=current,
                average_value=average,
                peak_value=peak,
                change_rate=change_rate,
                samples=len(values),
                prediction_minutes=prediction_minutes,
                threshold=threshold,
            )
            trends.append(trend)

        return trends

    # ── Event Correlation ──

    def record_event(self, event_type: str, source: str,
                     data: Dict[str, Any] = None) -> None:
        """Record a system event for correlation."""
        self._event_buffer.append({
            "timestamp": time.time(),
            "type": event_type,
            "source": source,
            "data": data or {},
        })

    def correlate_events(self) -> List[CorrelatedEvent]:
        """Find correlated events within the correlation window."""
        if not self._event_buffer:
            return []

        now = time.time()
        recent = [
            e for e in self._event_buffer
            if now - e["timestamp"] < self.CORRELATION_WINDOW
        ]

        if len(recent) < 2:
            return []

        correlations = []

        # Group by time proximity
        groups: List[List[Dict]] = []
        current_group: List[Dict] = [recent[0]]

        for i in range(1, len(recent)):
            if recent[i]["timestamp"] - recent[i-1]["timestamp"] < 5:
                current_group.append(recent[i])
            else:
                if len(current_group) >= 2:
                    groups.append(current_group)
                current_group = [recent[i]]

        if len(current_group) >= 2:
            groups.append(current_group)

        # Build narratives from groups
        for group in groups:
            sources = [e["source"] for e in group]
            types = [e["type"] for e in group]
            narrative = self._build_narrative(types, sources)

            corr = CorrelatedEvent(
                event_id=hashlib.md5(
                    f"{group[0]['timestamp']}_{len(group)}".encode()
                ).hexdigest()[:12],
                narrative=narrative,
                events=group,
                root_cause=types[0] if types else "unknown",
                confidence=min(0.5 + len(group) * 0.1, 0.95),
            )
            correlations.append(corr)

        return correlations

    def _build_narrative(self, types: List[str], sources: List[str]) -> str:
        """Build a human-readable narrative from correlated events."""
        if not types:
            return "Unknown event cluster"

        unique_types = list(dict.fromkeys(types))
        unique_sources = list(dict.fromkeys(sources))

        if len(unique_types) == 1:
            return f"Repeated {unique_types[0]} events from {', '.join(unique_sources)}"

        return (
            f"Correlated events: {' → '.join(unique_types)} "
            f"(sources: {', '.join(unique_sources)})"
        )

    # ── Alert Generation ──

    def generate_alerts(self, trends: List[ResourceTrend] = None) -> List[SituationalAlert]:
        """Generate intelligent alerts based on current state and trends."""
        new_alerts = []
        trends = trends or self.analyze_trends()

        for trend in trends:
            if not trend.is_concerning():
                continue

            # Dedup check
            if self._is_alert_recent(trend.resource_name):
                continue

            if trend.direction == TrendDirection.SPIKE:
                alert = SituationalAlert(
                    severity=AlertSeverity.HIGH,
                    title=f"Spike detected: {trend.resource_name}",
                    description=(
                        f"{trend.resource_name} spiked to {trend.current_value:.1f} "
                        f"(avg: {trend.average_value:.1f})"
                    ),
                    suggestion="Investigate recent process launches or workload changes",
                    source="trend_analyzer",
                )
            elif trend.prediction_minutes > 0 and trend.prediction_minutes < 30:
                alert = SituationalAlert(
                    severity=AlertSeverity.MEDIUM,
                    title=f"{trend.resource_name} approaching threshold",
                    description=(
                        f"At current rate ({trend.change_rate:+.1f}/min), "
                        f"{trend.resource_name} will hit {trend.threshold:.0f} "
                        f"in ~{trend.prediction_minutes:.0f} minutes"
                    ),
                    suggestion="Consider freeing resources or scaling capacity",
                    source="trend_analyzer",
                )
            elif trend.current_value > trend.threshold * 0.9:
                alert = SituationalAlert(
                    severity=AlertSeverity.HIGH,
                    title=f"{trend.resource_name} near critical threshold",
                    description=(
                        f"Currently at {trend.current_value:.1f} "
                        f"(threshold: {trend.threshold:.0f})"
                    ),
                    suggestion="Immediate action recommended to prevent degradation",
                    source="trend_analyzer",
                )
            else:
                continue

            self._alerts.append(alert)
            self._alert_titles_recent[trend.resource_name] = time.time()
            new_alerts.append(alert)

        return new_alerts

    def _is_alert_recent(self, key: str) -> bool:
        """Check if we recently issued an alert for this key."""
        last_time = self._alert_titles_recent.get(key, 0)
        return (time.time() - last_time) < self.ALERT_DEDUP_SECONDS

    def get_active_alerts(self) -> List[SituationalAlert]:
        """Get all unresolved alerts."""
        return [a for a in self._alerts if not a.resolved]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                return True
        return False

    # ── Full Situational Report ──

    def generate_report(self) -> SituationReport:
        """
        Generate a complete situational awareness report.

        This is the main entry point — it runs all analysis layers
        and produces a comprehensive snapshot.
        """
        # Update temporal layer automatically
        self.update_temporal()

        # Classify situation
        situation, sit_confidence = self.classify_situation()

        # Analyze trends
        trends = self.analyze_trends()

        # Correlate events
        correlations = self.correlate_events()

        # Generate alerts from trends
        new_alerts = self.generate_alerts(trends)
        active_alerts = self.get_active_alerts()

        # Build summary
        concerning_trends = [t for t in trends if t.is_concerning()]
        summary_parts = [f"Situation: {situation.value} ({sit_confidence:.0%} confident)"]

        if concerning_trends:
            summary_parts.append(
                f"{len(concerning_trends)} concerning trend(s) detected"
            )
        if active_alerts:
            high_alerts = [a for a in active_alerts if a.severity in
                          (AlertSeverity.HIGH, AlertSeverity.CRITICAL)]
            if high_alerts:
                summary_parts.append(f"⚠️ {len(high_alerts)} high-priority alert(s)")

        if correlations:
            summary_parts.append(f"{len(correlations)} correlated event group(s)")

        report = SituationReport(
            situation=situation,
            situation_confidence=sit_confidence,
            context_layers=dict(self._layers),
            active_trends=trends,
            correlated_events=correlations,
            active_alerts=active_alerts,
            summary=" | ".join(summary_parts),
        )

        return report

    # ── Persistence ──

    def save_snapshot(self) -> None:
        """Save current awareness state to disk."""
        report = self.generate_report()
        path = self.data_dir / "awareness_snapshot.json"
        try:
            path.write_text(
                json.dumps(report.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[AWARENESS] Failed to save snapshot: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get a compact status summary."""
        report = self.generate_report()
        return report.to_dict()
