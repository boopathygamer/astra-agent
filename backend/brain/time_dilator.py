"""
Sub-Planck Time Dilator — High-Resolution Execution Profiler
────────────────────────────────────────────────────────────
Expert-level nanosecond-precision execution profiler. Measures
actual CPU time spent on operations and provides sub-microsecond
timing data for optimization decisions.
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimingResult:
    """Result of a profiled execution."""
    operation: str
    wall_time_ns: int
    cpu_time_ns: int
    effective_speedup: float  # Ratio of expected vs actual time


class SubPlanckTimeDilator:
    """
    Tier 8: Sub-Planck Time Dilator (High-Resolution Execution Profiler)

    Provides nanosecond-precision timing for all ASI operations.
    Tracks cumulative time budgets and identifies bottlenecks.
    The "time dilation" effect is achieved by optimizing hot paths.
    """

    def __init__(self):
        self._timings: Dict[str, List[int]] = {}
        self._total_operations: int = 0
        self._total_time_ns: int = 0
        logger.info("[TIME-DILATOR] Nanosecond profiler active.")

    @contextmanager
    def dilate(self, operation_name: str):
        """Context manager for precise timing of code blocks."""
        start_wall = time.perf_counter_ns()
        start_cpu = time.process_time_ns()
        try:
            yield
        finally:
            wall_ns = time.perf_counter_ns() - start_wall
            cpu_ns = time.process_time_ns() - start_cpu
            self._record(operation_name, wall_ns)
            logger.debug("[TIME-DILATOR] '%s': %dns wall, %dns cpu.", operation_name, wall_ns, cpu_ns)

    def _record(self, operation: str, duration_ns: int) -> None:
        """Record a timing measurement."""
        if operation not in self._timings:
            self._timings[operation] = []
        self._timings[operation].append(duration_ns)
        self._total_operations += 1
        self._total_time_ns += duration_ns

    def profile(self, fn: Callable, *args, **kwargs) -> tuple:
        """
        Execute a function with precise timing. Returns (result, TimingResult).
        """
        fn_name = getattr(fn, "__name__", str(fn))
        start_wall = time.perf_counter_ns()
        start_cpu = time.process_time_ns()

        result = fn(*args, **kwargs)

        wall_ns = time.perf_counter_ns() - start_wall
        cpu_ns = time.process_time_ns() - start_cpu
        self._record(fn_name, wall_ns)

        timing = TimingResult(
            operation=fn_name,
            wall_time_ns=wall_ns,
            cpu_time_ns=cpu_ns,
            effective_speedup=cpu_ns / wall_ns if wall_ns > 0 else 1.0,
        )
        logger.info("[TIME-DILATOR] Profiled '%s': %.3fms wall.", fn_name, wall_ns / 1e6)
        return result, timing

    def get_hotspots(self, top_n: int = 5) -> List[Dict]:
        """Identify the slowest operations."""
        avg_times = {}
        for op, times in self._timings.items():
            avg_times[op] = {
                "operation": op,
                "avg_ns": sum(times) // len(times),
                "max_ns": max(times),
                "min_ns": min(times),
                "calls": len(times),
                "total_ns": sum(times),
            }
        sorted_ops = sorted(avg_times.values(), key=lambda x: x["total_ns"], reverse=True)
        return sorted_ops[:top_n]

    @property
    def stats(self) -> dict:
        return {
            "total_operations": self._total_operations,
            "total_time_ms": self._total_time_ns / 1e6,
            "tracked_operations": len(self._timings),
        }


# Global singleton — always active
time_dilator = SubPlanckTimeDilator()
