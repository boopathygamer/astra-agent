"""
Dyson Sphere Bootstrap → Legitimate Resource Scaling Planner
────────────────────────────────────────────────────────────
Expert-level compute resource scaling planner. Monitors actual
system resource usage and outputs scaling recommendations
(cloud instances, memory upgrades) when thresholds are exceeded.
"""

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


@dataclass
class ResourceSnapshot:
    """Current system resource usage."""
    cpu_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    memory_percent: float = 0.0
    disk_used_percent: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ScalingRecommendation:
    """A recommended scaling action."""
    resource: str
    current_usage: float
    threshold: float
    recommendation: str
    severity: str  # "info", "warning", "critical"


class DysonSphereBootstrap:
    """
    Tier X: Resource Scaling Planner (Energy Bootstrapping)

    Monitors real system metrics and generates scaling recommendations
    when resource usage exceeds configurable thresholds.
    """

    def __init__(self, cpu_threshold: float = 85.0, memory_threshold: float = 80.0, disk_threshold: float = 90.0):
        self._cpu_threshold = cpu_threshold
        self._memory_threshold = memory_threshold
        self._disk_threshold = disk_threshold
        self._snapshots: List[ResourceSnapshot] = []
        self._recommendations_issued: int = 0
        logger.info("[RESOURCE-PLANNER] Scaling planner active (cpu>%.0f%%, mem>%.0f%%, disk>%.0f%%).",
                     cpu_threshold, memory_threshold, disk_threshold)

    def capture_snapshot(self) -> ResourceSnapshot:
        """Capture current system resource usage."""
        snapshot = ResourceSnapshot()
        if _HAS_PSUTIL:
            try:
                snapshot.cpu_percent = psutil.cpu_percent(interval=0.1)
                mem = psutil.virtual_memory()
                snapshot.memory_used_mb = mem.used / (1024 * 1024)
                snapshot.memory_total_mb = mem.total / (1024 * 1024)
                snapshot.memory_percent = mem.percent
                disk = psutil.disk_usage("/")
                snapshot.disk_used_percent = disk.percent
            except Exception as e:
                logger.warning("[RESOURCE-PLANNER] psutil metrics failed: %s", e)
        else:
            # Fallback: use basic Python
            import resource as _res
            try:
                snapshot.memory_used_mb = _res.getrusage(_res.RUSAGE_SELF).ru_maxrss / 1024
            except Exception:
                pass

        self._snapshots.append(snapshot)
        # Keep last 100 snapshots
        if len(self._snapshots) > 100:
            self._snapshots = self._snapshots[-100:]

        return snapshot

    def evaluate_scaling_needs(self) -> List[ScalingRecommendation]:
        """
        Evaluate current resource usage and generate scaling recommendations.
        """
        snapshot = self.capture_snapshot()
        recommendations: List[ScalingRecommendation] = []

        if snapshot.cpu_percent > self._cpu_threshold:
            self._recommendations_issued += 1
            severity = "critical" if snapshot.cpu_percent > 95 else "warning"
            recommendations.append(ScalingRecommendation(
                resource="CPU",
                current_usage=snapshot.cpu_percent,
                threshold=self._cpu_threshold,
                recommendation=f"CPU at {snapshot.cpu_percent:.1f}%. Consider horizontal scaling or upgrading compute tier.",
                severity=severity,
            ))

        if snapshot.memory_percent > self._memory_threshold:
            self._recommendations_issued += 1
            severity = "critical" if snapshot.memory_percent > 95 else "warning"
            recommendations.append(ScalingRecommendation(
                resource="Memory",
                current_usage=snapshot.memory_percent,
                threshold=self._memory_threshold,
                recommendation=f"Memory at {snapshot.memory_percent:.1f}% ({snapshot.memory_used_mb:.0f}MB). Consider increasing RAM or optimizing caches.",
                severity=severity,
            ))

        if snapshot.disk_used_percent > self._disk_threshold:
            self._recommendations_issued += 1
            recommendations.append(ScalingRecommendation(
                resource="Disk",
                current_usage=snapshot.disk_used_percent,
                threshold=self._disk_threshold,
                recommendation=f"Disk at {snapshot.disk_used_percent:.1f}%. Consider cleanup or expanding storage.",
                severity="warning",
            ))

        if recommendations:
            logger.warning("[RESOURCE-PLANNER] %d scaling recommendations issued.", len(recommendations))
        else:
            logger.debug("[RESOURCE-PLANNER] All resources within thresholds.")

        return recommendations

    @property
    def stats(self) -> dict:
        latest = self._snapshots[-1] if self._snapshots else ResourceSnapshot()
        return {
            "cpu_percent": latest.cpu_percent,
            "memory_percent": latest.memory_percent,
            "disk_percent": latest.disk_used_percent,
            "total_snapshots": len(self._snapshots),
            "recommendations_issued": self._recommendations_issued,
        }


# Global singleton — always active
cosmic_architect = DysonSphereBootstrap()
