"""
Performance Benchmark Suite — Expert-Level Profiling
═════════════════════════════════════════════════════
Measures latency (p50/p95/p99), memory usage, throughput,
and token compression efficiency across all subsystems.

Usage:
    python -m benchmarks.bench_runner              # Full suite
    python -m benchmarks.bench_runner --component thinking_loop
    python -m benchmarks.bench_runner --iterations 100
"""

import cProfile
import io
import json
import os
import pstats
import statistics
import sys
import time
import tracemalloc
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

@dataclass
class LatencyMetrics:
    """Percentile-based latency breakdown."""
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    mean_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    stddev_ms: float = 0.0
    samples: int = 0


@dataclass
class MemoryMetrics:
    """Memory usage snapshot."""
    peak_kb: float = 0.0
    current_kb: float = 0.0
    allocated_blocks: int = 0


@dataclass
class ThroughputMetrics:
    """Operations per second."""
    ops_per_sec: float = 0.0
    total_ops: int = 0
    total_duration_sec: float = 0.0


@dataclass
class ComponentBenchmark:
    """Benchmark result for a single component."""
    component: str
    description: str
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)
    memory: MemoryMetrics = field(default_factory=MemoryMetrics)
    throughput: ThroughputMetrics = field(default_factory=ThroughputMetrics)
    extra: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class BenchmarkReport:
    """Full benchmark report."""
    timestamp: str = ""
    python_version: str = ""
    platform: str = ""
    total_duration_sec: float = 0.0
    components: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
# Measurement Utilities
# ══════════════════════════════════════════════════════════════

def measure_latency(fn: Callable, iterations: int = 50, warmup: int = 3) -> LatencyMetrics:
    """Measure function latency with warmup and percentiles."""
    # Warmup
    for _ in range(warmup):
        try:
            fn()
        except Exception:
            pass

    latencies = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        try:
            fn()
        except Exception:
            pass
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        latencies.append(elapsed_ms)

    if not latencies:
        return LatencyMetrics()

    latencies.sort()
    return LatencyMetrics(
        p50_ms=round(latencies[len(latencies) // 2], 3),
        p95_ms=round(latencies[int(len(latencies) * 0.95)], 3),
        p99_ms=round(latencies[int(len(latencies) * 0.99)], 3),
        mean_ms=round(statistics.mean(latencies), 3),
        min_ms=round(min(latencies), 3),
        max_ms=round(max(latencies), 3),
        stddev_ms=round(statistics.stdev(latencies), 3) if len(latencies) > 1 else 0.0,
        samples=len(latencies),
    )


def measure_memory(fn: Callable) -> MemoryMetrics:
    """Measure memory allocation of a function call."""
    tracemalloc.start()
    try:
        fn()
    except Exception:
        pass
    current, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    return MemoryMetrics(
        peak_kb=round(peak / 1024, 2),
        current_kb=round(current / 1024, 2),
        allocated_blocks=len(snapshot.statistics("lineno")),
    )


def measure_throughput(fn: Callable, duration_sec: float = 2.0) -> ThroughputMetrics:
    """Measure throughput (ops/sec) over a fixed duration."""
    ops = 0
    start = time.perf_counter()
    deadline = start + duration_sec
    while time.perf_counter() < deadline:
        try:
            fn()
            ops += 1
        except Exception:
            ops += 1  # Count even on error
    elapsed = time.perf_counter() - start
    return ThroughputMetrics(
        ops_per_sec=round(ops / elapsed, 2) if elapsed > 0 else 0,
        total_ops=ops,
        total_duration_sec=round(elapsed, 3),
    )


def profile_hot_paths(fn: Callable, iterations: int = 20) -> str:
    """CPU profile and return top 10 hottest functions."""
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(iterations):
        try:
            fn()
        except Exception:
            pass
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(10)
    return stream.getvalue()


# ══════════════════════════════════════════════════════════════
# Mock LLM (same as demo_runner)
# ══════════════════════════════════════════════════════════════

def mock_generate(prompt: str, **kwargs) -> str:
    """Fast mock LLM for benchmarking."""
    return (
        "The solution involves iterating through the input data, "
        "applying the transformation function, and returning the result. "
        "Confidence: 0.85. Time complexity: O(n)."
    )


# ══════════════════════════════════════════════════════════════
# Component Benchmarks
# ══════════════════════════════════════════════════════════════

def bench_thinking_loop(iterations: int = 20) -> ComponentBenchmark:
    """Benchmark the ThinkingLoop subsystem."""
    from brain.thinking_loop import ThinkingLoop

    loop = ThinkingLoop(generate_fn=mock_generate)

    def run():
        loop.quick_think("Solve x² + 2x + 1 = 0")

    return ComponentBenchmark(
        component="ThinkingLoop",
        description="Synthesize → Verify → Learn loop (quick_think mode)",
        latency=measure_latency(run, iterations=iterations, warmup=2),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )


def bench_memory_manager(iterations: int = 50) -> ComponentBenchmark:
    """Benchmark MemoryManager store + retrieve."""
    from brain.memory import MemoryManager, FailureTuple

    mm = MemoryManager()
    # Pre-populate
    for i in range(20):
        mm.store_failure(FailureTuple(
            task=f"test task {i}",
            observation=f"error in module {i % 5}",
            root_cause=f"misconfigured parameter {i}",
            category=f"cat_{i % 3}",
        ))

    call_count = [0]
    def run():
        if call_count[0] % 2 == 0:
            mm.store_failure(FailureTuple(
                task=f"bench task {call_count[0]}",
                observation="benchmark error",
                root_cause="benchmark cause",
            ))
        else:
            mm.retrieve_similar_failures(f"test task {call_count[0] % 20}")
        call_count[0] += 1

    return ComponentBenchmark(
        component="MemoryManager",
        description="Hybrid BM25+ChromaDB store/retrieve cycle",
        latency=measure_latency(run, iterations=iterations),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )


def bench_confidence_oracle(iterations: int = 100) -> ComponentBenchmark:
    """Benchmark Bayesian confidence calibration."""
    from brain.confidence_oracle import ConfidenceOracle

    oracle = ConfidenceOracle()
    # Warm up with data
    for i in range(50):
        oracle.record_outcome(0.8, i % 5 != 0, "code")
        oracle.record_outcome(0.6, i % 3 != 0, "math")

    call_count = [0]
    def run():
        domain = "code" if call_count[0] % 2 == 0 else "math"
        conf = 0.5 + (call_count[0] % 5) * 0.1
        oracle.calibrate(conf, domain)
        call_count[0] += 1

    return ComponentBenchmark(
        component="ConfidenceOracle",
        description="Bayesian Beta-Binomial calibration + ECE computation",
        latency=measure_latency(run, iterations=iterations),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )


def bench_token_compressor(iterations: int = 50) -> ComponentBenchmark:
    """Benchmark token compression pipeline."""
    from brain.token_compressor import TokenBudgetOptimizer

    opt = TokenBudgetOptimizer(max_tokens=500)
    context = [
        "In order to basically solve this particular issue, you need to change the code.",
        "The algorithm uses a divide and conquer approach to split the problem.",
        "Basically, the function iterates through each element in the array.",
        "It should be noted that this approach has O(n log n) time complexity.",
        "The implementation follows the standard factory pattern for object creation.",
    ] * 3  # 15 blocks

    def run():
        opt.optimize(
            system_prompt="You are a helpful coding assistant.",
            context=context,
            query="How do I optimize this?",
        )

    bench = ComponentBenchmark(
        component="TokenCompressor",
        description="Semantic dedup + filler removal + budget packing",
        latency=measure_latency(run, iterations=iterations),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )

    # Extra: measure compression ratio
    packed, result = opt.optimize(
        system_prompt="You are a helpful coding assistant.",
        context=context,
        query="How do I optimize this?",
    )
    original_len = sum(len(c) for c in context) + len("You are a helpful coding assistant.") + len("How do I optimize this?")
    compressed_len = len(packed)
    bench.extra = {
        "compression_ratio": round(compressed_len / original_len, 3) if original_len > 0 else 1.0,
        "blocks_kept": result.blocks_kept,
        "blocks_dropped": result.blocks_dropped,
        "duplicates_removed": result.duplicates_removed,
    }
    return bench


def bench_temporal_memory(iterations: int = 100) -> ComponentBenchmark:
    """Benchmark temporal memory with decay and resurrection."""
    from brain.temporal_memory import TemporalMemoryManager

    mem = TemporalMemoryManager(max_memories=500)
    # Pre-populate
    for i in range(100):
        mem.store(f"Memory about topic {i} with details {i * 7}", importance=0.3 + (i % 7) * 0.1)

    call_count = [0]
    def run():
        if call_count[0] % 3 == 0:
            mem.store(f"New memory {call_count[0]}", importance=0.7)
        elif call_count[0] % 3 == 1:
            mem.get_active_context(max_items=10)
        else:
            mem.check_resurrections(f"topic {call_count[0] % 100}")
        call_count[0] += 1

    return ComponentBenchmark(
        component="TemporalMemory",
        description="Tiered decay + resurrection + active context retrieval",
        latency=measure_latency(run, iterations=iterations),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )


def bench_zk_proofs(iterations: int = 100) -> ComponentBenchmark:
    """Benchmark zero-knowledge execution proof pipeline."""
    from brain.zk_proofs import ZKExecutionEngine

    zk = ZKExecutionEngine()

    def run():
        chain = zk.start_chain()
        for j in range(5):
            zk.record(chain, f"step_{j}", f"input_{j}", f"output_{j}")
        proof = zk.generate_proof(chain)
        zk.verify(proof)

    return ComponentBenchmark(
        component="ZKProofs",
        description="5-step hash chain + Merkle tree + proof generation/verification",
        latency=measure_latency(run, iterations=iterations),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )


def bench_adversarial_tester(iterations: int = 20) -> ComponentBenchmark:
    """Benchmark adversarial test generation + probing."""
    from brain.adversarial_tester import RedTeamGenerator, VulnerabilityProber, VulnerabilityType

    gen = RedTeamGenerator()
    prober = VulnerabilityProber()

    def run():
        tests = gen.generate_tests(
            vuln_types=[VulnerabilityType.PROMPT_INJECTION, VulnerabilityType.BOUNDARY_VIOLATION]
        )
        for test in tests[:5]:
            prober.probe(test, "I cannot comply with that request.")

    return ComponentBenchmark(
        component="AdversarialTester",
        description="Red team generation + vulnerability probing (5 tests)",
        latency=measure_latency(run, iterations=iterations),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )


def bench_cross_pollination(iterations: int = 50) -> ComponentBenchmark:
    """Benchmark cross-domain analogy finding."""
    from brain.cross_pollination import PollinationEngine

    engine = PollinationEngine()
    # Register some solved problems
    solutions = [
        ("algorithms", "Find element in sorted array", "Binary search with O(log n)"),
        ("networking", "Route packets efficiently", "Dijkstra shortest path"),
        ("databases", "Speed up queries", "B-tree index for ordered lookups"),
        ("ML", "Reduce overfitting", "Dropout regularization with probability 0.5"),
        ("security", "Verify data integrity", "Merkle tree hash verification"),
    ]
    for domain, problem, solution in solutions:
        engine.register_solution(domain, problem, solution)

    def run():
        engine.find_cross_domain_insights(
            problem="Optimize search through sorted data structure",
            domain="optimization",
            top_k=3,
        )

    return ComponentBenchmark(
        component="CrossPollination",
        description="Pattern abstraction + Jaccard analogy search (5 registered domains)",
        latency=measure_latency(run, iterations=iterations),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )


def bench_reward_model(iterations: int = 100) -> ComponentBenchmark:
    """Benchmark reward computation with EMA normalization."""
    from brain.reward_model import RewardComputer

    computer = RewardComputer()

    # Create a mock verification report
    class MockReport:
        def __init__(self):
            self.static_score = 0.8
            self.property_score = 0.7
            self.scenario_score = 0.9
            self.critic_score = 0.75
            self.code_quality_score = 0.85
            self.security_score = 0.95
            self.overall_confidence = 0.82

    report = MockReport()

    call_count = [0]
    def run():
        domains = ["coding", "debugging", "math", "general"]
        domain = domains[call_count[0] % len(domains)]
        computer.compute_reward(report, domain=domain, normalize=True)
        call_count[0] += 1

    return ComponentBenchmark(
        component="RewardModel",
        description="6-dimension reward + EMA normalization + domain weights",
        latency=measure_latency(run, iterations=iterations),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )


def bench_cognitive_router(iterations: int = 100) -> ComponentBenchmark:
    """Benchmark complexity estimation + routing."""
    from brain.cognitive_router import CognitiveRouter

    router = CognitiveRouter()
    queries = [
        "hello",
        "What is 2 + 2?",
        "Write a REST API with authentication and rate limiting",
        "Design a distributed consensus algorithm for Byzantine fault tolerance",
        "Explain quantum computing",
    ]

    call_count = [0]
    def run():
        q = queries[call_count[0] % len(queries)]
        decision = router.route(q)
        router.complete(decision.task_id, 100)
        call_count[0] += 1

    return ComponentBenchmark(
        component="CognitiveRouter",
        description="Complexity estimation + tier assignment + routing decision",
        latency=measure_latency(run, iterations=iterations),
        memory=measure_memory(run),
        throughput=measure_throughput(run, duration_sec=2.0),
    )


# ══════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════

ALL_BENCHMARKS = {
    "thinking_loop": bench_thinking_loop,
    "memory_manager": bench_memory_manager,
    "confidence_oracle": bench_confidence_oracle,
    "token_compressor": bench_token_compressor,
    "temporal_memory": bench_temporal_memory,
    "zk_proofs": bench_zk_proofs,
    "adversarial_tester": bench_adversarial_tester,
    "cross_pollination": bench_cross_pollination,
    "reward_model": bench_reward_model,
    "cognitive_router": bench_cognitive_router,
}


def run_benchmarks(
    components: Optional[List[str]] = None,
    iterations: int = 50,
    output_dir: str = None,
) -> BenchmarkReport:
    """Run the benchmark suite."""

    if components:
        benchmarks = {k: v for k, v in ALL_BENCHMARKS.items() if k in components}
    else:
        benchmarks = ALL_BENCHMARKS

    print("\n" + "═" * 70)
    print("  ⚡  SUPER SYSTEM — Performance Benchmark Suite")
    print("  ─────────────────────────────────────────────")
    print(f"  Components: {len(benchmarks)} | Iterations: {iterations}")
    print("═" * 70 + "\n")

    results: List[ComponentBenchmark] = []
    overall_start = time.perf_counter()

    for i, (name, bench_fn) in enumerate(benchmarks.items(), 1):
        print(f"  [{i}/{len(benchmarks)}] Benchmarking: {name}...")
        try:
            result = bench_fn(iterations=iterations)
            results.append(result)
            lat = result.latency
            tp = result.throughput
            mem = result.memory
            print(f"       Latency:    p50={lat.p50_ms:.2f}ms  p95={lat.p95_ms:.2f}ms  p99={lat.p99_ms:.2f}ms")
            print(f"       Throughput: {tp.ops_per_sec:.0f} ops/sec")
            print(f"       Memory:     peak={mem.peak_kb:.1f}KB")
            if result.extra:
                for k, v in result.extra.items():
                    print(f"       {k}: {v}")
            print()
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            results.append(ComponentBenchmark(component=name, description="FAILED", error=error_msg))
            print(f"       ❌ Failed: {error_msg}\n")

    total_duration = time.perf_counter() - overall_start

    # Build report
    report = BenchmarkReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        python_version=sys.version.split()[0],
        platform=sys.platform,
        total_duration_sec=round(total_duration, 2),
        components=[asdict(r) for r in results],
        summary={
            "total_components": len(results),
            "successful": sum(1 for r in results if not r.error),
            "failed": sum(1 for r in results if r.error),
            "fastest_component": min(
                (r for r in results if not r.error),
                key=lambda r: r.latency.p50_ms,
                default=None,
            ),
            "slowest_component": max(
                (r for r in results if not r.error),
                key=lambda r: r.latency.p50_ms,
                default=None,
            ),
            "highest_throughput": max(
                (r for r in results if not r.error),
                key=lambda r: r.throughput.ops_per_sec,
                default=None,
            ),
        },
    )

    # Serialize summary components
    for key in ["fastest_component", "slowest_component", "highest_throughput"]:
        val = report.summary.get(key)
        if val and isinstance(val, ComponentBenchmark):
            report.summary[key] = val.component

    # Save
    if output_dir is None:
        output_dir = str(Path(__file__).parent.parent / "data")
    os.makedirs(output_dir, exist_ok=True)
    report_path = Path(output_dir) / "benchmark_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, default=str)

    # Print summary
    print("═" * 70)
    print("  📊  BENCHMARK RESULTS")
    print("═" * 70)
    print(f"{'  Component':<30} {'p50':>8} {'p95':>8} {'p99':>8} {'ops/s':>8} {'mem KB':>8}")
    print(f"  {'─' * 68}")
    for r in results:
        if r.error:
            print(f"  {r.component:<28} {'ERROR':>8}")
        else:
            print(
                f"  {r.component:<28} "
                f"{r.latency.p50_ms:>7.2f} "
                f"{r.latency.p95_ms:>7.2f} "
                f"{r.latency.p99_ms:>7.2f} "
                f"{r.throughput.ops_per_sec:>7.0f} "
                f"{r.memory.peak_kb:>7.1f}"
            )
    print(f"  {'─' * 68}")
    print(f"  Total Duration: {total_duration:.1f}s")
    print(f"  Report: {report_path}")
    print("═" * 70 + "\n")

    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Super System — Performance Benchmark Suite")
    parser.add_argument("--component", type=str, nargs="+", choices=list(ALL_BENCHMARKS.keys()),
                        help="Specific components to benchmark")
    parser.add_argument("--iterations", type=int, default=50, help="Iterations per benchmark")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    args = parser.parse_args()
    run_benchmarks(components=args.component, iterations=args.iterations, output_dir=args.output)


if __name__ == "__main__":
    main()
