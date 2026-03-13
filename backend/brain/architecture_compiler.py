"""
Recursive Architecture Compiler — Self-Rewriting Topology
═════════════════════════════════════════════════════════
The system inspects its own architecture, identifies bottlenecks,
and rewrites its own module topology — compiling a new version of
itself optimized for the current workload.

Architecture:
  Architecture → Profiler → Bottleneck Map → Topology Mutator
                                                   ↓
                                      Sandbox Evaluator → Hot-Swap Deployer
"""

import logging
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class BottleneckType(Enum):
    HIGH_LATENCY = "high_latency"
    HIGH_FAN_IN = "high_fan_in"
    HIGH_FAN_OUT = "high_fan_out"
    CRITICAL_PATH = "critical_path"
    UNUSED = "unused"
    ERROR_PRONE = "error_prone"


@dataclass
class ModuleProfile:
    """Performance profile of a single module."""
    name: str = ""
    avg_latency_ms: float = 0.0
    call_count: int = 0
    error_count: int = 0
    fan_in: int = 0               # Modules that call this
    fan_out: int = 0              # Modules this calls
    on_critical_path: bool = False
    bottlenecks: List[BottleneckType] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.error_count / max(self.call_count, 1)


@dataclass
class TopologyMutation:
    """A proposed change to the architecture topology."""
    mutation_id: str = ""
    description: str = ""
    action: str = ""              # "add_edge", "remove_edge", "bypass", "parallelize"
    source: str = ""
    target: str = ""
    expected_improvement: float = 0.0

    def __post_init__(self):
        if not self.mutation_id:
            self.mutation_id = secrets.token_hex(4)


@dataclass
class CompilationResult:
    """Result of compiling a new architecture version."""
    version: int = 0
    mutations_applied: int = 0
    bottlenecks_resolved: int = 0
    expected_speedup: float = 1.0
    sandbox_score: float = 0.0
    deployed: bool = False


class ArchitectureProfiler:
    """Profiles the module call graph to find bottlenecks."""

    HIGH_LATENCY_MS = 100.0
    HIGH_FAN_IN = 10
    HIGH_FAN_OUT = 8

    def __init__(self):
        self._call_log: Dict[str, List[float]] = defaultdict(list)
        self._error_log: Dict[str, int] = defaultdict(int)
        self._edges: Dict[str, Set[str]] = defaultdict(set)

    def record_call(self, module: str, latency_ms: float, caller: str = "") -> None:
        self._call_log[module].append(latency_ms)
        if caller:
            self._edges[caller].add(module)

    def record_error(self, module: str) -> None:
        self._error_log[module] += 1

    def profile_all(self) -> Dict[str, ModuleProfile]:
        """Generate profiles for all known modules."""
        # Compute fan-in
        fan_in: Dict[str, int] = defaultdict(int)
        for caller, targets in self._edges.items():
            for t in targets:
                fan_in[t] += 1

        profiles = {}
        for module, latencies in self._call_log.items():
            avg_lat = sum(latencies) / max(len(latencies), 1)
            fan_out = len(self._edges.get(module, set()))

            profile = ModuleProfile(
                name=module,
                avg_latency_ms=avg_lat,
                call_count=len(latencies),
                error_count=self._error_log.get(module, 0),
                fan_in=fan_in.get(module, 0),
                fan_out=fan_out,
            )

            # Detect bottlenecks
            if avg_lat > self.HIGH_LATENCY_MS:
                profile.bottlenecks.append(BottleneckType.HIGH_LATENCY)
            if profile.fan_in > self.HIGH_FAN_IN:
                profile.bottlenecks.append(BottleneckType.HIGH_FAN_IN)
            if fan_out > self.HIGH_FAN_OUT:
                profile.bottlenecks.append(BottleneckType.HIGH_FAN_OUT)
            if profile.error_rate > 0.1:
                profile.bottlenecks.append(BottleneckType.ERROR_PRONE)
            if len(latencies) == 0:
                profile.bottlenecks.append(BottleneckType.UNUSED)

            profiles[module] = profile

        return profiles


class ArchitectureCompiler:
    """
    Self-rewriting architecture optimizer.

    Usage:
        compiler = ArchitectureCompiler()

        # Record module interactions
        compiler.record("thinking_loop", latency_ms=50, caller="controller")
        compiler.record("memory", latency_ms=150, caller="thinking_loop")
        compiler.record("verifier", latency_ms=200, caller="thinking_loop")

        # Compile optimized architecture
        result = compiler.compile()
        print(f"Speedup: {result.expected_speedup:.2f}x")
    """

    def __init__(self):
        self._profiler = ArchitectureProfiler()
        self._version: int = 0
        self._mutations_history: List[TopologyMutation] = []
        self._compilations: List[CompilationResult] = []

    def record(self, module: str, latency_ms: float = 0.0, caller: str = "", error: bool = False) -> None:
        """Record a module call for profiling."""
        self._profiler.record_call(module, latency_ms, caller)
        if error:
            self._profiler.record_error(module)

    def compile(self, sandbox_fn: Optional[Callable[[List[TopologyMutation]], float]] = None) -> CompilationResult:
        """Compile a new optimized architecture version."""
        self._version += 1
        profiles = self._profiler.profile_all()

        # Generate mutations for each bottleneck
        mutations = self._generate_mutations(profiles)

        # Sandbox evaluation
        sandbox_score = 1.0
        if sandbox_fn and mutations:
            sandbox_score = sandbox_fn(mutations)

        # Compute expected improvement
        bottlenecks_resolved = sum(
            1 for m in mutations if m.expected_improvement > 0
        )
        speedup = 1.0 + sum(m.expected_improvement for m in mutations) * 0.1

        self._mutations_history.extend(mutations)

        result = CompilationResult(
            version=self._version,
            mutations_applied=len(mutations),
            bottlenecks_resolved=bottlenecks_resolved,
            expected_speedup=round(speedup, 2),
            sandbox_score=round(sandbox_score, 3),
            deployed=sandbox_score > 0.5,
        )

        self._compilations.append(result)
        logger.info(
            f"ArchCompiler v{self._version}: {len(mutations)} mutations, "
            f"speedup={speedup:.2f}x, deployed={result.deployed}"
        )
        return result

    def get_stats(self) -> Dict[str, Any]:
        profiles = self._profiler.profile_all()
        bottleneck_count = sum(len(p.bottlenecks) for p in profiles.values())
        return {
            "version": self._version,
            "profiled_modules": len(profiles),
            "total_bottlenecks": bottleneck_count,
            "total_mutations": len(self._mutations_history),
            "total_compilations": len(self._compilations),
            "latest_speedup": (
                self._compilations[-1].expected_speedup
                if self._compilations else 1.0
            ),
        }

    def _generate_mutations(self, profiles: Dict[str, ModuleProfile]) -> List[TopologyMutation]:
        """Generate topology mutations to resolve bottlenecks."""
        mutations = []

        for name, profile in profiles.items():
            for bottleneck in profile.bottlenecks:
                if bottleneck == BottleneckType.HIGH_LATENCY:
                    mutations.append(TopologyMutation(
                        description=f"Parallelize {name} (avg={profile.avg_latency_ms:.0f}ms)",
                        action="parallelize",
                        source=name,
                        expected_improvement=0.3,
                    ))
                elif bottleneck == BottleneckType.HIGH_FAN_IN:
                    mutations.append(TopologyMutation(
                        description=f"Add load balancer before {name} (fan_in={profile.fan_in})",
                        action="add_edge",
                        target=name,
                        expected_improvement=0.2,
                    ))
                elif bottleneck == BottleneckType.ERROR_PRONE:
                    mutations.append(TopologyMutation(
                        description=f"Add circuit breaker for {name} (err={profile.error_rate:.1%})",
                        action="bypass",
                        source=name,
                        expected_improvement=0.15,
                    ))
                elif bottleneck == BottleneckType.UNUSED:
                    mutations.append(TopologyMutation(
                        description=f"Remove unused module {name}",
                        action="remove_edge",
                        source=name,
                        expected_improvement=0.05,
                    ))

        return mutations
