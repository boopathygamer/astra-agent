"""Quick import + functional verification for all new modules."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

errors = []
print("=" * 60)
print("  IMPORT VERIFICATION TEST")
print("=" * 60)

# 1. Schemas
try:
    from schemas.agent_schemas import AgentRequest, AgentResponse, ToolCallRecord, ThinkingTraceSchema
    print("  OK schemas.agent_schemas")
except Exception as e:
    errors.append(f"schemas.agent_schemas: {e}")
    print(f"  FAIL schemas.agent_schemas: {e}")

try:
    from schemas.brain_schemas import ThinkingInput, ThinkingOutput, FailureInput, VerificationResult
    print("  OK schemas.brain_schemas")
except Exception as e:
    errors.append(f"schemas.brain_schemas: {e}")
    print(f"  FAIL schemas.brain_schemas: {e}")

try:
    from schemas.tool_schemas import ToolDefinition, ToolExecutionRequest, ThreatScanResult
    print("  OK schemas.tool_schemas")
except Exception as e:
    errors.append(f"schemas.tool_schemas: {e}")
    print(f"  FAIL schemas.tool_schemas: {e}")

# 2. Telemetry
try:
    from telemetry.metrics import MetricsCollector, HistogramSummary
    print("  OK telemetry.metrics")
except Exception as e:
    errors.append(f"telemetry.metrics: {e}")
    print(f"  FAIL telemetry.metrics: {e}")

try:
    from telemetry.tracer import SpanTracer, Span, Trace
    print("  OK telemetry.tracer")
except Exception as e:
    errors.append(f"telemetry.tracer: {e}")
    print(f"  FAIL telemetry.tracer: {e}")

# 3. Distributed
try:
    from distributed.task_queue import TaskQueue, WorkerPool, TaskPriority
    print("  OK distributed.task_queue")
except Exception as e:
    errors.append(f"distributed.task_queue: {e}")
    print(f"  FAIL distributed.task_queue: {e}")

# 4. Hardened Executor
try:
    from agents.sandbox.hardened_executor import HardenedExecutor, SandboxConfig, CodeAnalyzer
    print("  OK agents.sandbox.hardened_executor")
except Exception as e:
    errors.append(f"agents.sandbox.hardened_executor: {e}")
    print(f"  FAIL agents.sandbox.hardened_executor: {e}")

# 5. Benchmarks
try:
    from benchmarks.bench_runner import run_benchmarks, measure_latency
    print("  OK benchmarks.bench_runner")
except Exception as e:
    errors.append(f"benchmarks.bench_runner: {e}")
    print(f"  FAIL benchmarks.bench_runner: {e}")

# 6. Demo Runner
try:
    from demo_runner import run_demo, mock_generate, SCENARIOS
    print("  OK demo_runner")
except Exception as e:
    errors.append(f"demo_runner: {e}")
    print(f"  FAIL demo_runner: {e}")

# === Functional Tests ===
print()
print("=" * 60)
print("  FUNCTIONAL TESTS")
print("=" * 60)

# Test Pydantic validation
try:
    from schemas.agent_schemas import AgentRequest, AgentResponse
    req = AgentRequest(user_input="Test query")
    assert req.use_thinking_loop == True
    assert req.max_tool_calls == 10
    resp = AgentResponse(answer="Test answer", confidence=0.85, mode="direct")
    assert resp.confidence == 0.85
    print("  OK Pydantic schema validation")
except Exception as e:
    errors.append(f"schema_validation: {e}")
    print(f"  FAIL Schema validation: {e}")

# Test MetricsCollector
try:
    from telemetry.metrics import MetricsCollector
    MetricsCollector.reset()
    m = MetricsCollector.get_instance()
    m.histogram("test.latency", 100.0)
    m.histogram("test.latency", 200.0)
    m.counter("test.count", 5)
    m.gauge("test.gauge", 42.0)
    h = m.get_histogram("test.latency")
    assert h.count == 2, f"Expected 2 samples, got {h.count}"
    assert m.get_counter("test.count") == 5
    assert m.get_gauge("test.gauge") == 42.0
    report = m.get_report()
    assert len(report.histograms) > 0
    print("  OK MetricsCollector (histogram/counter/gauge/report)")
except Exception as e:
    errors.append(f"metrics: {e}")
    print(f"  FAIL MetricsCollector: {e}")

# Test SpanTracer
try:
    from telemetry.tracer import SpanTracer
    tracer = SpanTracer()
    with tracer.span("test_span") as s:
        s.attributes["key"] = "value"
    assert s.duration_ms >= 0
    assert s.status == "OK"
    print("  OK SpanTracer (span creation/duration/status)")
except Exception as e:
    errors.append(f"tracer: {e}")
    print(f"  FAIL SpanTracer: {e}")

# Test HardenedExecutor
try:
    from agents.sandbox.hardened_executor import HardenedExecutor
    executor = HardenedExecutor()
    result = executor.execute("print(2 + 2)")
    assert result.success, f"Expected success but got: {result.error}"
    assert "4" in result.output
    print(f"  OK HardenedExecutor (output: {result.output.strip()}, {result.duration_ms:.0f}ms)")
except Exception as e:
    errors.append(f"executor: {e}")
    print(f"  FAIL HardenedExecutor: {e}")

# Test blocking dangerous code
try:
    from agents.sandbox.hardened_executor import HardenedExecutor
    executor = HardenedExecutor()
    result2 = executor.execute("import os; os.system('whoami')")
    assert not result2.success, "Should have blocked dangerous code"
    print("  OK HardenedExecutor blocks dangerous code")
except Exception as e:
    errors.append(f"executor_block: {e}")
    print(f"  FAIL HardenedExecutor blocking: {e}")

# Test CodeAnalyzer
try:
    from agents.sandbox.hardened_executor import CodeAnalyzer, SandboxConfig
    violations = CodeAnalyzer.analyze("import os\nos.system('rm -rf /')", SandboxConfig())
    assert len(violations) > 0
    safe = CodeAnalyzer.analyze("x = 2 + 2\nprint(x)", SandboxConfig())
    assert len(safe) == 0
    print(f"  OK CodeAnalyzer ({len(violations)} violations caught, 0 false positives)")
except Exception as e:
    errors.append(f"analyzer: {e}")
    print(f"  FAIL CodeAnalyzer: {e}")

# Summary
print()
print("=" * 60)
if errors:
    print(f"  RESULT: {len(errors)} ERRORS")
    for e in errors:
        print(f"     - {e}")
else:
    print("  RESULT: ALL TESTS PASSED")
print("=" * 60)
sys.exit(1 if errors else 0)
