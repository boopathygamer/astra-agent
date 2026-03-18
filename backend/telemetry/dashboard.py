"""
Telemetry Dashboard — Real-Time System Metrics Aggregator
═════════════════════════════════════════════════════════
Collects and aggregates metrics from all subsystems:
  - Channel Gateway status & per-channel metrics
  - Message Bus throughput & health
  - Circuit Breaker states
  - Brain module activity
  - Agent performance
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SystemSnapshot:
    """Point-in-time snapshot of system health."""
    timestamp: float = field(default_factory=time.time)
    gateway_status: Dict[str, Any] = field(default_factory=dict)
    message_bus_status: Dict[str, Any] = field(default_factory=dict)
    circuit_breakers: Dict[str, Any] = field(default_factory=dict)
    brain_activity: Dict[str, Any] = field(default_factory=dict)
    agent_status: Dict[str, Any] = field(default_factory=dict)
    system_health: str = "unknown"
    health_score: float = 0.0


class TelemetryDashboard:
    """
    Central telemetry aggregator for real-time system monitoring.

    Usage:
        dashboard = TelemetryDashboard()
        dashboard.register_source("gateway", gateway.get_status)
        dashboard.register_source("bus", bus.get_status)
        snapshot = dashboard.get_snapshot()
    """

    MAX_HISTORY = 1000

    def __init__(self):
        self._sources: Dict[str, Any] = {}
        self._history: List[SystemSnapshot] = []
        self._custom_metrics: Dict[str, float] = {}
        self._alerts: List[Dict[str, Any]] = []
        self._start_time = time.time()
        logger.info("[TELEMETRY] Dashboard initialized")

    def register_source(self, name: str, getter: Any) -> None:
        """Register a metrics source (callable that returns dict)."""
        self._sources[name] = getter
        logger.info(f"[TELEMETRY] Registered source: {name}")

    def get_snapshot(self) -> Dict[str, Any]:
        """Collect a real-time snapshot from all registered sources."""
        snapshot = {
            "timestamp": time.time(),
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "sources": {},
            "health": self._compute_health(),
            "custom_metrics": dict(self._custom_metrics),
            "active_alerts": len(self._alerts),
        }

        for name, getter in self._sources.items():
            try:
                if callable(getter):
                    snapshot["sources"][name] = getter()
                else:
                    snapshot["sources"][name] = {"status": "non-callable"}
            except Exception as e:
                snapshot["sources"][name] = {"error": str(e)}

        # Store in history
        if len(self._history) >= self.MAX_HISTORY:
            self._history = self._history[-(self.MAX_HISTORY // 2):]
        self._history.append(SystemSnapshot(
            gateway_status=snapshot["sources"].get("gateway", {}),
            message_bus_status=snapshot["sources"].get("bus", {}),
            circuit_breakers=snapshot["sources"].get("circuit_breakers", {}),
            system_health=snapshot["health"]["status"],
            health_score=snapshot["health"]["score"],
        ))

        return snapshot

    def _compute_health(self) -> Dict[str, Any]:
        """Compute overall system health from all sources."""
        checks = []

        for name, getter in self._sources.items():
            try:
                if callable(getter):
                    data = getter()
                    is_healthy = True
                    # Check for error indicators
                    if isinstance(data, dict):
                        if data.get("errors", 0) > 100:
                            is_healthy = False
                        if data.get("state") == "open":
                            is_healthy = False
                        if data.get("running") is False:
                            is_healthy = False
                    checks.append({"source": name, "healthy": is_healthy})
            except Exception:
                checks.append({"source": name, "healthy": False})

        healthy_count = sum(1 for c in checks if c["healthy"])
        total = max(len(checks), 1)
        score = healthy_count / total

        if score >= 0.9:
            status = "healthy"
        elif score >= 0.6:
            status = "degraded"
        else:
            status = "critical"

        return {"status": status, "score": round(score, 3), "checks": checks}

    def record_metric(self, name: str, value: float) -> None:
        """Record a custom metric value."""
        self._custom_metrics[name] = value

    def add_alert(self, severity: str, message: str, source: str = "") -> None:
        """Add a system alert."""
        alert = {
            "severity": severity,
            "message": message,
            "source": source,
            "timestamp": time.time(),
        }
        self._alerts.append(alert)
        if len(self._alerts) > 200:
            self._alerts = self._alerts[-100:]
        logger.warning(f"[TELEMETRY] Alert [{severity}]: {message}")

    def get_alerts(self, severity: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        alerts = self._alerts
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        return alerts[-limit:]

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [
            {
                "timestamp": s.timestamp,
                "health": s.system_health,
                "score": s.health_score,
            }
            for s in self._history[-limit:]
        ]

    def get_status(self) -> Dict[str, Any]:
        return {
            "registered_sources": list(self._sources.keys()),
            "history_size": len(self._history),
            "active_alerts": len(self._alerts),
            "uptime_seconds": round(time.time() - self._start_time, 1),
        }
