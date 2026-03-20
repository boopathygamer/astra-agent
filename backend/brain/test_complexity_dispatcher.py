"""
Complexity Dispatcher — Test Suite
═══════════════════════════════════
Tests all 4 components: ComplexityDetector, ProblemDecomposer,
AgentDispatcher, ResultSynthesizer, and the full pipeline.
"""

import time


# ── Test 1: Complexity Detection ──────────────────────────
def test_complexity_detector():
    from brain.complexity_dispatcher import ComplexityDetector, ComplexityLevel

    detector = ComplexityDetector()

    # Simple query → should NOT decompose
    simple = detector.assess("What is 2 + 2?")
    assert simple.level == ComplexityLevel.SIMPLE, f"Expected SIMPLE, got {simple.level}"
    assert not simple.should_decompose, "Simple query should not trigger decomposition"
    assert simple.score < 0.3, f"Simple score should be low, got {simple.score}"

    # Medium query → single domain
    medium = detector.assess("Write a Python function to sort a list using quicksort algorithm")
    assert medium.level in (ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE), f"Expected SIMPLE/MODERATE, got {medium.level}"

    # Complex multi-domain query → SHOULD decompose
    complex_q = (
        "Build a complete web application with a Python API backend, "
        "and then create a marketing strategy for it, plus design the UI "
        "with a modern creative color palette and also write the business plan "
        "including financial analysis with revenue projections"
    )
    cx = detector.assess(complex_q)
    assert cx.score >= 0.4, f"Complex query should score high, got {cx.score}"
    assert cx.domain_count >= 2, f"Should detect 2+ domains, got {cx.domain_count}"
    assert len(cx.detected_domains) >= 2, f"Should list 2+ domains, got {cx.detected_domains}"
    assert cx.should_decompose, "Complex query should trigger decomposition"
    assert cx.summary(), "Summary should not be empty"

    # Highly complex
    deep = (
        "First, research the latest machine learning architectures and then "
        "write a comprehensive article about them. After that, create a business plan "
        "for a startup that uses this technology, and also build the code for "
        "a prototype API. Furthermore, design the creative branding and finally "
        "create a data visualization dashboard to track the startup's KPIs."
    )
    deep_cx = detector.assess(deep)
    assert deep_cx.level in (ComplexityLevel.COMPLEX, ComplexityLevel.HIGHLY_COMPLEX), \
        f"Expected COMPLEX/HIGHLY_COMPLEX, got {deep_cx.level}"
    assert deep_cx.should_decompose, "Highly complex query must trigger decomposition"

    print("  ✅ Complexity Detector — PASSED")


# ── Test 2: Problem Decomposer (heuristic mode) ──────────
def test_problem_decomposer():
    from brain.complexity_dispatcher import (
        ProblemDecomposer, ComplexityDetector, ComplexityAssessment, ComplexityLevel,
    )

    detector = ComplexityDetector()
    decomposer = ProblemDecomposer(generate_fn=None)  # No LLM — heuristic only

    query = (
        "Build an API in Python and then write documentation for it "
        "and also create a marketing landing page"
    )
    assessment = detector.assess(query)
    tasks = decomposer.decompose(query, assessment)

    assert len(tasks) >= 2, f"Should decompose into 2+ tasks, got {len(tasks)}"
    assert all(t.task_id for t in tasks), "All tasks should have IDs"
    assert all(t.description for t in tasks), "All tasks should have descriptions"
    assert tasks[0].depends_on == [], "First task should have no dependencies"

    # Check dependency chain
    if len(tasks) > 1:
        assert len(tasks[1].depends_on) >= 1, "Second task should depend on first"

    # Test max subtask cap
    huge = " and then ".join([f"do step {i}" for i in range(20)])
    huge_assessment = ComplexityAssessment(
        level=ComplexityLevel.HIGHLY_COMPLEX,
        score=0.9,
        domain_count=1,
        detected_domains=["general"],
        sub_problem_hints=[f"do step {i}" for i in range(20)],
    )
    huge_tasks = decomposer.decompose(huge, huge_assessment)
    assert len(huge_tasks) <= 6, f"Should cap at 6 tasks, got {len(huge_tasks)}"

    print("  ✅ Problem Decomposer (heuristic) — PASSED")


# ── Test 3: Agent Dispatcher ─────────────────────────────
def test_agent_dispatcher():
    from brain.complexity_dispatcher import AgentDispatcher, SubTask
    from agents.experts.domains import DOMAIN_EXPERTS

    call_count = 0
    def mock_generate(prompt):
        nonlocal call_count
        call_count += 1
        return f"[Mock LLM Response #{call_count}] Solved: {prompt[:80]}"

    dispatcher = AgentDispatcher(
        generate_fn=mock_generate,
        domain_experts=DOMAIN_EXPERTS,
    )

    # Dispatch to a known domain expert
    task = SubTask(
        task_id="test_1",
        description="Write a quicksort function in Python",
        domain="code",
    )
    result = dispatcher.dispatch(task)
    assert result.status == "done", f"Should succeed, got {result.status}"
    assert result.result, "Should have a result"
    assert "expert:" in result.agent_used, f"Should use expert, got {result.agent_used}"
    assert result.duration_ms >= 0

    # Dispatch to an unknown domain → general fallback
    task2 = SubTask(
        task_id="test_2",
        description="Explain quantum entanglement",
        domain="quantum_physics",
    )
    result2 = dispatcher.dispatch(task2)
    assert result2.status == "done"
    assert result2.agent_used == "general"

    # Dispatch with context from previous step
    task3 = SubTask(
        task_id="test_3",
        description="Now optimize the sorting function",
        domain="code",
    )
    result3 = dispatcher.dispatch(task3, context="Previous: quicksort was O(n^2) worst case")
    assert result3.status == "done"

    stats = dispatcher.get_stats()
    assert stats["dispatched"] >= 3
    assert stats["expert_hits"] >= 2

    print("  ✅ Agent Dispatcher — PASSED")


# ── Test 4: Result Synthesizer ────────────────────────────
def test_result_synthesizer():
    from brain.complexity_dispatcher import ResultSynthesizer, SubTask

    # Fallback mode (no LLM)
    synth = ResultSynthesizer(generate_fn=None)

    tasks = [
        SubTask(task_id="1", description="Build API", domain="code",
                status="done", result="Here's a Flask API with 3 endpoints..."),
        SubTask(task_id="2", description="Write docs", domain="writing",
                status="done", result="API Documentation:\n- GET /users\n- POST /users"),
        SubTask(task_id="3", description="Design UI", domain="creative",
                status="failed", result="Error: timeout"),
    ]

    answer = synth.synthesize("Build an API with docs and UI", tasks)
    assert "Flask API" in answer, "Should include code result"
    assert "Documentation" in answer, "Should include writing result"
    assert "could not be completed" in answer, "Should mention failure"

    # Single result — passthrough
    single = synth.synthesize("Simple question", [
        SubTask(task_id="1", description="Answer it", status="done", result="The answer is 42."),
    ])
    assert single == "The answer is 42."

    # All failed
    empty = synth.synthesize("Impossible question", [
        SubTask(task_id="1", status="failed", result="Error"),
    ])
    assert "unable" in empty.lower()

    print("  ✅ Result Synthesizer — PASSED")


# ── Test 5: Full Pipeline ────────────────────────────────
def test_full_pipeline():
    from brain.complexity_dispatcher import ComplexityDispatcher
    from agents.experts.domains import DOMAIN_EXPERTS

    call_count = 0
    def mock_generate(prompt):
        nonlocal call_count
        call_count += 1
        if "Break down" in prompt or "sub-tasks" in prompt.lower():
            return (
                "1. [code] Build the Python API with Flask endpoints\n"
                "2. [writing] Write comprehensive API documentation (depends on: 1)\n"
                "3. [business] Create a go-to-market strategy (depends on: 1)\n"
            )
        if "Synthesize" in prompt or "synthesize" in prompt:
            return "Here is your complete solution combining API, docs, and strategy."
        return f"Expert answer #{call_count} for: {prompt[:60]}"

    dispatcher = ComplexityDispatcher(
        generate_fn=mock_generate,
        domain_experts=DOMAIN_EXPERTS,
    )

    # Simple query — should NOT decompose
    simple = dispatcher.assess("What is 2 + 2?")
    assert not simple.should_decompose

    # Complex query — full solve
    result = dispatcher.solve(
        "Build a Python API with Flask and then write the documentation "
        "and also create a business marketing strategy for the product"
    )

    assert result.success, f"Should succeed, got success={result.success}"
    assert len(result.sub_tasks) >= 2, f"Should have 2+ sub-tasks, got {len(result.sub_tasks)}"
    assert len(result.agents_used) >= 1, f"Should use 1+ agents, got {result.agents_used}"
    assert result.synthesized_answer, "Should have a synthesized answer"
    assert result.total_duration_ms >= 0
    assert result.summary(), "Summary should not be empty"

    stats = dispatcher.get_stats()
    assert stats["assessments"] >= 1
    assert stats["decompositions"] >= 1
    assert stats["total_subtasks_dispatched"] >= 2

    print("  ✅ Full Pipeline — PASSED")


# ── Run All ───────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Complexity Dispatcher — Test Suite")
    print("=" * 60)

    tests = [
        ("Complexity Detector", test_complexity_detector),
        ("Problem Decomposer", test_problem_decomposer),
        ("Agent Dispatcher", test_agent_dispatcher),
        ("Result Synthesizer", test_result_synthesizer),
        ("Full Pipeline", test_full_pipeline),
    ]

    passed = 0
    failed = 0
    start = time.time()

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  ❌ {name} — FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    duration = (time.time() - start) * 1000
    print()
    print("=" * 60)
    if failed == 0:
        print(f"  ALL {passed} TESTS PASSED — COMPLEXITY DISPATCHER VERIFIED! ✅")
    else:
        print(f"  {passed} passed, {failed} FAILED ❌")
    print(f"  Duration: {duration:.0f}ms")
    print("=" * 60)
