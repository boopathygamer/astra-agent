"""
Hardware Symbiosis — Adaptive Hardware-Aware Scheduling Engine
══════════════════════════════════════════════════════════════
Makes the agent hardware-aware: it understands its own resource constraints
and dynamically optimizes its behavior to maximize performance within
safe thermal and memory boundaries.

Subsystems:
  ┌──────────────────────────────────────────────────────────────────┐
  │ ThermalGovernor        Multi-zone thermal management            │
  │ AdaptiveScheduler      CPU priority + affinity control          │
  │ MemoryPressureManager  RAM pressure detection + response        │
  │ IOScheduler            Disk I/O priority management             │
  │ HardwareSymbiosis      Unified coordination + context export    │
  └──────────────────────────────────────────────────────────────────┘
"""

import gc
import logging
import os
import platform
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════════════

class ThermalState(Enum):
    """Thermal zone state classification."""
    COOL = "cool"           # < 60°C — full performance
    NORMAL = "normal"       # 60-75°C — normal operation
    WARNING = "warning"     # 75-85°C — begin throttling
    CRITICAL = "critical"   # > 85°C — aggressive throttling
    UNKNOWN = "unknown"     # No sensor data


class MemoryPressure(Enum):
    """Memory pressure level."""
    LOW = "low"             # < 60% RAM usage
    MODERATE = "moderate"   # 60-75%
    HIGH = "high"           # 75-85%
    CRITICAL = "critical"   # > 85%


class SchedulerAction(Enum):
    """Actions taken by the adaptive scheduler."""
    NONE = "none"
    ELEVATE = "elevate_priority"
    NORMALIZE = "normalize_priority"
    LOWER = "lower_priority"
    GC_TRIGGERED = "gc_triggered"
    IO_THROTTLED = "io_throttled"


@dataclass
class HardwareReport:
    """Report from a full hardware optimization pass."""
    timestamp: float = field(default_factory=time.time)
    thermal_state: ThermalState = ThermalState.UNKNOWN
    memory_pressure: MemoryPressure = MemoryPressure.LOW
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    max_temperature_c: float = 0.0
    agent_memory_mb: float = 0.0
    actions_taken: List[SchedulerAction] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"[HW] CPU: {self.cpu_percent:.0f}% | "
            f"RAM: {self.ram_percent:.0f}% | "
            f"Temp: {self.max_temperature_c:.0f}°C | "
            f"Thermal: {self.thermal_state.value} | "
            f"Pressure: {self.memory_pressure.value}",
        ]
        if self.actions_taken:
            actions_str = ", ".join(a.value for a in self.actions_taken)
            lines.append(f"     Actions: {actions_str}")
        if self.recommendations:
            for rec in self.recommendations[:3]:
                lines.append(f"     → {rec}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
# Thermal Governor
# ══════════════════════════════════════════════════════════════════════

class ThermalGovernor:
    """
    Multi-zone thermal management.

    Tracks per-core/per-zone temperatures and determines the overall
    thermal state. Triggers throttling actions when thresholds are
    exceeded.
    """

    def __init__(
        self,
        warning_c: float = 75.0,
        critical_c: float = 85.0,
    ):
        self.warning_c = warning_c
        self.critical_c = critical_c
        self._last_state = ThermalState.UNKNOWN
        self._thermal_events: List[Dict[str, Any]] = []

    def assess(self) -> tuple:
        """
        Read thermal sensors and classify the state.

        Returns:
            (ThermalState, max_temperature, per_zone_data)
        """
        zones: Dict[str, float] = {}
        max_temp = 0.0

        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for chip, entries in temps.items():
                    for entry in entries:
                        label = entry.label or chip
                        zones[label] = entry.current
                        max_temp = max(max_temp, entry.current)
        except (AttributeError, OSError):
            pass

        # Windows fallback: estimate from CPU usage heuristic
        if not zones and platform.system() == "Windows":
            cpu_pct = psutil.cpu_percent(interval=0)
            # Rough thermal estimate based on CPU load
            max_temp = 45.0 + (cpu_pct * 0.35)
            zones["estimated"] = max_temp

        # Classify state
        if max_temp <= 0:
            state = ThermalState.UNKNOWN
        elif max_temp < 60:
            state = ThermalState.COOL
        elif max_temp < self.warning_c:
            state = ThermalState.NORMAL
        elif max_temp < self.critical_c:
            state = ThermalState.WARNING
        else:
            state = ThermalState.CRITICAL

        # Log state transitions
        if state != self._last_state:
            self._thermal_events.append({
                "time": time.time(),
                "from": self._last_state.value,
                "to": state.value,
                "temp": max_temp,
            })
            if state in (ThermalState.WARNING, ThermalState.CRITICAL):
                logger.warning(
                    f"🌡️ Thermal transition: {self._last_state.value} → "
                    f"{state.value} ({max_temp:.1f}°C)"
                )
            self._last_state = state

        return state, max_temp, zones

    @property
    def recent_events(self) -> List[Dict[str, Any]]:
        return self._thermal_events[-10:]


# ══════════════════════════════════════════════════════════════════════
# Adaptive Scheduler
# ══════════════════════════════════════════════════════════════════════

class AdaptiveScheduler:
    """
    CPU priority and affinity control for the agent process.

    Adjusts the process priority based on system load and thermal state.
    On multi-core systems, can pin compute tasks to specific cores.
    """

    def __init__(self, target_cpu: float = 90.0):
        self.target_cpu = target_cpu
        self._process = psutil.Process(os.getpid())
        self._os_type = platform.system()
        self._original_nice = self._get_nice()

    def _get_nice(self) -> int:
        """Get current process priority."""
        try:
            return self._process.nice()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            return 0

    def optimize(
        self, cpu_usage: float, thermal_state: ThermalState
    ) -> SchedulerAction:
        """
        Decide and apply the optimal scheduling action.

        Priority adjustments:
          - COOL/NORMAL + under-utilized: elevate priority
          - WARNING: normalize priority
          - CRITICAL: lower priority to reduce heat
          - CPU over target: lower priority to share resources
        """
        action = SchedulerAction.NONE

        if thermal_state == ThermalState.CRITICAL:
            self._set_priority("low")
            action = SchedulerAction.LOWER
        elif thermal_state == ThermalState.WARNING:
            self._set_priority("normal")
            action = SchedulerAction.NORMALIZE
        elif cpu_usage > self.target_cpu + 5:
            self._set_priority("normal")
            action = SchedulerAction.NORMALIZE
        elif cpu_usage < self.target_cpu - 20 and thermal_state in (
            ThermalState.COOL, ThermalState.NORMAL, ThermalState.UNKNOWN,
        ):
            self._set_priority("high")
            action = SchedulerAction.ELEVATE

        return action

    def _set_priority(self, level: str):
        """Set process priority level."""
        try:
            if self._os_type == "Windows":
                priority_map = {
                    "high": psutil.HIGH_PRIORITY_CLASS,
                    "normal": psutil.NORMAL_PRIORITY_CLASS,
                    "low": psutil.IDLE_PRIORITY_CLASS,
                }
            else:
                priority_map = {"high": -5, "normal": 0, "low": 10}

            nice_val = priority_map.get(level)
            if nice_val is not None:
                self._process.nice(nice_val)
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            pass

    def get_cpu_affinity(self) -> Optional[List[int]]:
        """Get current CPU affinity (which cores we're pinned to)."""
        try:
            return self._process.cpu_affinity()
        except (AttributeError, psutil.AccessDenied, OSError):
            return None

    def set_cpu_affinity(self, cores: List[int]):
        """Pin the agent process to specific CPU cores."""
        try:
            self._process.cpu_affinity(cores)
            logger.info(f"CPU affinity set to cores: {cores}")
        except (AttributeError, psutil.AccessDenied, OSError, ValueError) as e:
            logger.warning(f"Failed to set CPU affinity: {e}")

    def restore_defaults(self):
        """Restore original scheduling parameters."""
        try:
            if self._os_type == "Windows":
                self._process.nice(psutil.NORMAL_PRIORITY_CLASS)
            else:
                self._process.nice(0)
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            pass


# ══════════════════════════════════════════════════════════════════════
# Memory Pressure Manager
# ══════════════════════════════════════════════════════════════════════

class MemoryPressureManager:
    """
    Detects memory pressure and responds with GC + cache cleanup.

    Thresholds:
      < 60% RAM → LOW
      60-75%    → MODERATE (preemptive GC)
      75-85%    → HIGH (aggressive GC + cache cleanup)
      > 85%     → CRITICAL (emergency cleanup)
    """

    def __init__(self, critical_pct: float = 85.0):
        self.critical_pct = critical_pct
        self._last_gc_time: float = 0.0
        self._gc_cooldown: float = 30.0  # seconds between GC cycles
        self._total_gc_runs: int = 0

    def assess(self) -> tuple:
        """
        Assess memory pressure and take action if needed.

        Returns:
            (MemoryPressure, ram_percent, action_taken)
        """
        mem = psutil.virtual_memory()
        ram_pct = mem.percent
        action = SchedulerAction.NONE

        if ram_pct < 60:
            pressure = MemoryPressure.LOW
        elif ram_pct < 75:
            pressure = MemoryPressure.MODERATE
        elif ram_pct < self.critical_pct:
            pressure = MemoryPressure.HIGH
            action = self._trigger_gc()
        else:
            pressure = MemoryPressure.CRITICAL
            action = self._trigger_gc(aggressive=True)

        return pressure, ram_pct, action

    def _trigger_gc(self, aggressive: bool = False) -> SchedulerAction:
        """Trigger garbage collection if cooldown has elapsed."""
        now = time.time()
        if now - self._last_gc_time < self._gc_cooldown:
            return SchedulerAction.NONE

        if aggressive:
            # Full collection across all generations
            gc.collect(generation=2)
        else:
            gc.collect(generation=0)

        self._last_gc_time = now
        self._total_gc_runs += 1
        logger.info(
            f"🧹 GC triggered (aggressive={aggressive}), "
            f"total runs: {self._total_gc_runs}"
        )
        return SchedulerAction.GC_TRIGGERED

    def get_agent_memory(self) -> Dict[str, float]:
        """Get the agent process's own memory usage."""
        try:
            proc = psutil.Process(os.getpid())
            mem_info = proc.memory_info()
            return {
                "rss_mb": round(mem_info.rss / (1024 ** 2), 1),
                "vms_mb": round(mem_info.vms / (1024 ** 2), 1),
                "percent": round(proc.memory_percent(), 2),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"rss_mb": 0, "vms_mb": 0, "percent": 0}


# ══════════════════════════════════════════════════════════════════════
# I/O Scheduler
# ══════════════════════════════════════════════════════════════════════

class IOScheduler:
    """
    Disk I/O priority management.

    Monitors disk I/O rates and adjusts the agent's I/O priority
    when heavy computation is occurring, preventing disk bottlenecks
    from slowing down the thinking loop.
    """

    def __init__(self):
        self._last_io: Optional[tuple] = None
        self._last_io_time: float = 0.0

    def assess(self) -> Dict[str, Any]:
        """
        Measure I/O rates since last assessment.

        Returns dict with read/write rates in MB/s.
        """
        result: Dict[str, Any] = {"io_rate_available": False}

        try:
            counters = psutil.disk_io_counters()
            if not counters:
                return result

            now = time.time()
            current = (counters.read_bytes, counters.write_bytes)

            if self._last_io and self._last_io_time:
                elapsed = now - self._last_io_time
                if elapsed > 0.1:
                    read_rate = (current[0] - self._last_io[0]) / elapsed
                    write_rate = (current[1] - self._last_io[1]) / elapsed
                    result["read_rate_mbs"] = round(
                        read_rate / (1024 ** 2), 2
                    )
                    result["write_rate_mbs"] = round(
                        write_rate / (1024 ** 2), 2
                    )
                    result["io_rate_available"] = True

                    # Classify I/O pressure
                    total_rate = (read_rate + write_rate) / (1024 ** 2)
                    if total_rate > 100:
                        result["io_pressure"] = "heavy"
                    elif total_rate > 20:
                        result["io_pressure"] = "moderate"
                    else:
                        result["io_pressure"] = "light"

            self._last_io = current
            self._last_io_time = now

        except (AttributeError, OSError):
            pass

        return result

    def set_io_priority(self, level: str = "normal"):
        """
        Set the agent process I/O priority (Windows only).

        Levels: 'low', 'normal', 'high'
        """
        if platform.system() != "Windows":
            return

        try:
            proc = psutil.Process(os.getpid())
            priority_map = {
                "low": psutil.IOPRIO_LOW,
                "normal": psutil.IOPRIO_NORMAL,
                "high": psutil.IOPRIO_HIGH,
            }
            prio = priority_map.get(level)
            if prio is not None:
                proc.ionice(prio)
        except (AttributeError, psutil.AccessDenied, OSError):
            pass


# ══════════════════════════════════════════════════════════════════════
# Hardware Symbiosis — Unified Engine  
# ══════════════════════════════════════════════════════════════════════

class HardwareSymbiosis:
    """
    Adaptive hardware-aware scheduling engine.

    Coordinates thermal management, CPU scheduling, memory pressure
    response, and I/O optimization to keep the agent running at
    peak performance within safe hardware boundaries.

    Usage:
        symbiosis = HardwareSymbiosis()
        report = symbiosis.optimize()
        print(report.summary())

        # Get context for the thinking loop
        context = symbiosis.get_hardware_context()
    """

    def __init__(
        self,
        thermal_warning_c: float = 75.0,
        thermal_critical_c: float = 85.0,
        cpu_target: float = 90.0,
        memory_critical_pct: float = 85.0,
    ):
        self.governor = ThermalGovernor(
            warning_c=thermal_warning_c,
            critical_c=thermal_critical_c,
        )
        self.scheduler = AdaptiveScheduler(target_cpu=cpu_target)
        self.memory_mgr = MemoryPressureManager(critical_pct=memory_critical_pct)
        self.io_scheduler = IOScheduler()

        self._total_optimizations: int = 0
        self._last_report: Optional[HardwareReport] = None

        logger.info(
            f"⚡ HardwareSymbiosis initialized — "
            f"thermal_warn={thermal_warning_c}°C, "
            f"thermal_crit={thermal_critical_c}°C, "
            f"cpu_target={cpu_target}%, "
            f"mem_crit={memory_critical_pct}%"
        )

    def optimize(self) -> HardwareReport:
        """
        Run a full optimization pass across all subsystems.

        1. Read thermal sensors → adjust CPU priority if needed
        2. Assess memory pressure → trigger GC if needed
        3. Check I/O rates → adjust I/O priority if needed
        4. Generate recommendations for the agent

        Returns:
            HardwareReport with current state and actions taken.
        """
        report = HardwareReport()
        report.cpu_percent = psutil.cpu_percent(interval=0.2)

        # ── Thermal ──
        thermal_state, max_temp, zones = self.governor.assess()
        report.thermal_state = thermal_state
        report.max_temperature_c = max_temp

        # ── CPU Scheduling ──
        sched_action = self.scheduler.optimize(
            report.cpu_percent, thermal_state
        )
        if sched_action != SchedulerAction.NONE:
            report.actions_taken.append(sched_action)

        # ── Memory Pressure ──
        pressure, ram_pct, mem_action = self.memory_mgr.assess()
        report.memory_pressure = pressure
        report.ram_percent = ram_pct
        if mem_action != SchedulerAction.NONE:
            report.actions_taken.append(mem_action)

        # Agent's own memory
        agent_mem = self.memory_mgr.get_agent_memory()
        report.agent_memory_mb = agent_mem.get("rss_mb", 0)

        # ── I/O ──
        io_data = self.io_scheduler.assess()

        # ── Recommendations ──
        report.recommendations = self._generate_recommendations(
            report, io_data
        )

        self._total_optimizations += 1
        self._last_report = report

        logger.info(f"⚡ Optimization #{self._total_optimizations}: {report.summary()}")

        return report

    def _generate_recommendations(
        self, report: HardwareReport, io_data: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations based on current state."""
        recs = []

        if report.thermal_state == ThermalState.CRITICAL:
            recs.append(
                "CRITICAL: Temperature above safe limit — reduce compute load immediately"
            )
        elif report.thermal_state == ThermalState.WARNING:
            recs.append(
                "Thermal warning — consider reducing parallel operations"
            )

        if report.memory_pressure == MemoryPressure.CRITICAL:
            recs.append(
                "Memory critically high — avoid loading large datasets"
            )
        elif report.memory_pressure == MemoryPressure.HIGH:
            recs.append(
                "Memory pressure high — minimize object creation"
            )

        if report.cpu_percent > 95:
            recs.append(
                "CPU near saturation — defer non-urgent background tasks"
            )

        io_pressure = io_data.get("io_pressure", "light")
        if io_pressure == "heavy":
            recs.append(
                "Heavy disk I/O — batch file operations for efficiency"
            )

        if report.agent_memory_mb > 500:
            recs.append(
                f"Agent using {report.agent_memory_mb:.0f}MB RAM — "
                f"consider releasing cached data"
            )

        return recs

    def get_hardware_context(self, max_length: int = 400) -> str:
        """
        Generate a context string for the thinking loop about
        the current hardware state.

        The agent uses this to make hardware-aware decisions,
        such as reducing batch sizes when memory is high or
        deferring compute when thermal state is critical.
        """
        if not self._last_report:
            report = self.optimize()
        else:
            report = self._last_report

        lines = ["HARDWARE CONTEXT:"]
        lines.append(
            f"  CPU: {report.cpu_percent:.0f}% | "
            f"RAM: {report.ram_percent:.0f}% | "
            f"AgentMem: {report.agent_memory_mb:.0f}MB"
        )

        if report.thermal_state != ThermalState.UNKNOWN:
            lines.append(
                f"  Thermal: {report.thermal_state.value} "
                f"({report.max_temperature_c:.0f}°C)"
            )

        if report.memory_pressure in (
            MemoryPressure.HIGH, MemoryPressure.CRITICAL
        ):
            lines.append(
                f"  ⚠ Memory pressure: {report.memory_pressure.value}"
            )

        if report.recommendations:
            lines.append("  Recommendations:")
            for rec in report.recommendations[:2]:
                lines.append(f"    → {rec}")

        result = "\n".join(lines)
        return result[:max_length]

    def get_stats(self) -> Dict[str, Any]:
        """Get hardware symbiosis statistics."""
        return {
            "total_optimizations": self._total_optimizations,
            "thermal_events": self.governor.recent_events,
            "gc_runs": self.memory_mgr._total_gc_runs,
            "agent_memory": self.memory_mgr.get_agent_memory(),
            "cpu_affinity": self.scheduler.get_cpu_affinity(),
        }

    def restore_defaults(self):
        """Restore all scheduling to system defaults."""
        self.scheduler.restore_defaults()
        logger.info("Hardware scheduling restored to defaults")


# ══════════════════════════════════════════════════════════════════════
# Global Instance
# ══════════════════════════════════════════════════════════════════════

hw_symbiosis = HardwareSymbiosis()
