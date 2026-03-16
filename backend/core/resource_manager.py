"""
Auto-Scaling Resource Manager — System Resource Management
═══════════════════════════════════════════════════════════
Monitors CPU, RAM, disk usage; auto-adjusts concurrency,
implements backpressure, and prevents OOM crashes.
"""

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResourceLevel(Enum):
    HEALTHY = "healthy"      # <50% usage
    ELEVATED = "elevated"    # 50-70%
    HIGH = "high"            # 70-85%
    CRITICAL = "critical"    # 85-95%
    EMERGENCY = "emergency"  # >95%


class BackpressureAction(Enum):
    NONE = "none"
    REDUCE_CONCURRENCY = "reduce_concurrency"
    QUEUE_REQUESTS = "queue_requests"
    REJECT_NEW = "reject_new"
    EMERGENCY_GC = "emergency_gc"


@dataclass
class ResourceSnapshot:
    """Point-in-time resource usage snapshot."""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_available_mb: float = 0.0
    active_threads: int = 0
    open_connections: int = 0
    request_queue_depth: int = 0
    level: ResourceLevel = ResourceLevel.HEALTHY


@dataclass
class ScalingDecision:
    """A resource scaling decision."""
    action: BackpressureAction = BackpressureAction.NONE
    max_concurrency: int = 10
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


class ResourceManager:
    """
    Auto-scaling resource manager with health monitoring,
    backpressure control, and adaptive concurrency limits.
    """

    CHECK_INTERVAL = 5     # Seconds between checks
    HISTORY_SIZE = 200

    # Thresholds
    THRESHOLDS = {
        ResourceLevel.HEALTHY: 50,
        ResourceLevel.ELEVATED: 70,
        ResourceLevel.HIGH: 85,
        ResourceLevel.CRITICAL: 95,
    }

    # Concurrency limits per level
    CONCURRENCY_LIMITS = {
        ResourceLevel.HEALTHY: 10,
        ResourceLevel.ELEVATED: 8,
        ResourceLevel.HIGH: 4,
        ResourceLevel.CRITICAL: 2,
        ResourceLevel.EMERGENCY: 1,
    }

    def __init__(self, max_concurrency: int = 10):
        self.max_concurrency = max_concurrency
        self._current_concurrency = max_concurrency
        self._snapshots: deque = deque(maxlen=self.HISTORY_SIZE)
        self._decisions: deque = deque(maxlen=50)
        self._active_requests = 0
        self._rejected_requests = 0
        self._total_requests = 0
        self._lock = threading.Lock()
        self._monitor_running = False
        self._monitor_thread: Optional[threading.Thread] = None
        logger.info(f"[RESOURCE] Manager initialized (max_concurrency={max_concurrency})")

    def start_monitoring(self):
        """Start background resource monitoring."""
        if self._monitor_running:
            return
        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="resource-monitor",
        )
        self._monitor_thread.start()
        logger.info("[RESOURCE] Monitoring started")

    def stop_monitoring(self):
        self._monitor_running = False

    def acquire(self) -> bool:
        """Try to acquire a request slot. Returns False if overloaded."""
        with self._lock:
            self._total_requests += 1
            if self._active_requests >= self._current_concurrency:
                self._rejected_requests += 1
                return False
            self._active_requests += 1
            return True

    def release(self):
        """Release a request slot."""
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)

    def take_snapshot(self) -> ResourceSnapshot:
        """Capture current resource state."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            snapshot = ResourceSnapshot(
                cpu_percent=cpu,
                memory_percent=mem.percent,
                memory_used_mb=mem.used / (1024 * 1024),
                memory_available_mb=mem.available / (1024 * 1024),
                active_threads=threading.active_count(),
                request_queue_depth=self._active_requests,
            )
        except ImportError:
            # Fallback without psutil
            snapshot = ResourceSnapshot(
                cpu_percent=0,
                memory_percent=0,
                active_threads=threading.active_count(),
                request_queue_depth=self._active_requests,
            )

        # Determine level
        max_usage = max(snapshot.cpu_percent, snapshot.memory_percent)
        if max_usage >= 95:
            snapshot.level = ResourceLevel.EMERGENCY
        elif max_usage >= 85:
            snapshot.level = ResourceLevel.CRITICAL
        elif max_usage >= 70:
            snapshot.level = ResourceLevel.HIGH
        elif max_usage >= 50:
            snapshot.level = ResourceLevel.ELEVATED
        else:
            snapshot.level = ResourceLevel.HEALTHY

        self._snapshots.append(snapshot)
        return snapshot

    def _monitor_loop(self):
        """Background resource monitoring loop."""
        while self._monitor_running:
            try:
                snapshot = self.take_snapshot()
                self._apply_scaling(snapshot)
            except Exception as e:
                logger.debug(f"[RESOURCE] Monitor error: {e}")
            time.sleep(self.CHECK_INTERVAL)

    def _apply_scaling(self, snapshot: ResourceSnapshot):
        """Apply auto-scaling based on resource levels."""
        new_concurrency = self.CONCURRENCY_LIMITS.get(
            snapshot.level, self.max_concurrency
        )
        action = BackpressureAction.NONE

        if new_concurrency < self._current_concurrency:
            action = BackpressureAction.REDUCE_CONCURRENCY
        elif snapshot.level == ResourceLevel.EMERGENCY:
            action = BackpressureAction.EMERGENCY_GC
            # Trigger garbage collection
            import gc
            gc.collect()
        elif snapshot.level == ResourceLevel.CRITICAL:
            action = BackpressureAction.REJECT_NEW

        if new_concurrency != self._current_concurrency:
            decision = ScalingDecision(
                action=action,
                max_concurrency=new_concurrency,
                reason=f"Resource level: {snapshot.level.value}, CPU={snapshot.cpu_percent:.0f}%, MEM={snapshot.memory_percent:.0f}%",
            )
            self._decisions.append(decision)
            self._current_concurrency = new_concurrency
            logger.info(
                f"[RESOURCE] Scaled concurrency: {self._current_concurrency} "
                f"(level={snapshot.level.value})"
            )

    def get_health(self) -> Dict[str, Any]:
        """Get current system health."""
        snapshot = self.take_snapshot() if not self._snapshots else self._snapshots[-1]
        return {
            "level": snapshot.level.value,
            "cpu_percent": round(snapshot.cpu_percent, 1),
            "memory_percent": round(snapshot.memory_percent, 1),
            "memory_used_mb": round(snapshot.memory_used_mb, 1),
            "active_threads": snapshot.active_threads,
            "current_concurrency": self._current_concurrency,
            "max_concurrency": self.max_concurrency,
            "active_requests": self._active_requests,
            "total_requests": self._total_requests,
            "rejected_requests": self._rejected_requests,
            "rejection_rate": round(
                self._rejected_requests / max(self._total_requests, 1), 3
            ),
        }

    def get_status(self) -> Dict[str, Any]:
        return self.get_health()
