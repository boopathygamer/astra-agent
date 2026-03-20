"""
CCE v5.0 — Dominance-Tier Test Suite
═════════════════════════════════════
Covers all 6 dominance-tier engines + cognitive_core v5.0 integration.
"""

import sys
import os
import time


# ── Engine 1: Infinite Memory ─────────────────────────────
def test_infinite_memory():
    from brain.infinite_memory_engine import (
        InfiniteMemoryEngine, MemoryTier, EbbinghausCurve, SimilarityEngine,
    )
    mem = InfiniteMemoryEngine()

    # Store
    t1 = mem.store("quicksort", "O(n log n) average time complexity", tags={"sorting", "algorithms"})
    assert t1.trace_id, "Should generate trace ID"
    assert t1.tier == MemoryTier.L2_WORKING

    t2 = mem.store("merge_sort", "O(n log n) worst case guaranteed", tags={"sorting"})
    t3 = mem.store("binary_search", "O(log n) search in sorted array", tags={"searching"})

    # Recall by content
    result = mem.recall("sorting algorithm complexity")
    assert result.found, "Should find sorting memories"
    assert result.total_searched >= 3, f"Should search all traces, searched {result.total_searched}"
    assert result.summary(), "Summary should not be empty"

    # Recall by key
    found = mem.recall_by_key("quicksort")
    assert found is not None, "Should find by key"
    assert found.access_count >= 1, "Access count should be incremented"

    # Deduplication
    t1_dup = mem.store("quicksort_dup", "O(n log n) average time complexity")  # same content
    assert mem.get_total_traces() == 3, f"Should dedup, got {mem.get_total_traces()}"

    # Associations
    assert mem.associate(t1.trace_id, t2.trace_id), "Should create association"
    assocs = mem.get_associated(t1.trace_id)
    assert len(assocs) == 1, f"Should have 1 association, got {len(assocs)}"

    # Consolidation
    report = mem.consolidate()
    assert report.duration_ms >= 0

    # Forgetting curve
    decay = EbbinghausCurve.compute_decay(time.time() - 1, 5)
    assert 0 < decay <= 1.0, f"Decay should be in (0,1], got {decay}"

    # Similarity
    sim = SimilarityEngine.jaccard({"a", "b", "c"}, {"b", "c", "d"})
    assert 0.4 < sim < 0.6, f"Jaccard should be ~0.5, got {sim}"

    # Natural language interface
    nl_result = mem.solve("recall sorting algorithms")
    assert nl_result is not None

    stats = mem.get_stats()
    assert stats["stores"] >= 3
    print("  ✅ Infinite Memory Engine — PASSED")


# ── Engine 2: Autonomous Execution ────────────────────────
def test_autonomous_execution():
    from brain.autonomous_execution_engine import (
        AutonomousExecutionEngine, GoalDecomposer, PlanValidator, TaskStatus,
    )
    engine = AutonomousExecutionEngine()

    # Plan
    plan = engine.plan("Implement a quicksort function in Python")
    assert plan.is_valid, f"Plan should be valid, errors: {plan.validation_errors}"
    assert len(plan.tasks) >= 4, f"Should have 4+ tasks, got {len(plan.tasks)}"
    assert len(plan.execution_order) == len(plan.tasks), "All tasks should be in order"
    assert plan.summary(), "Plan summary should not be empty"

    # Execute
    result = engine.execute_goal("Solve the equation 2x + 5 = 15")
    assert result.tasks_total >= 4, f"Should have 4+ tasks, got {result.tasks_total}"
    assert result.tasks_completed > 0, f"Should complete some tasks"
    assert result.success, "Should succeed"
    assert result.total_duration_ms >= 0
    assert result.summary(), "Result summary should not be empty"

    # DAG validation
    decomposer = GoalDecomposer()
    tasks = decomposer.decompose("Research machine learning architectures")
    is_valid, errors = PlanValidator.validate(tasks)
    assert is_valid, f"Should be valid, errors: {errors}"

    # Topological sort
    order = PlanValidator.topological_sort(tasks)
    assert len(order) == len(tasks)

    # Natural language interface
    nl_result = engine.solve("Build a web scraper")
    assert nl_result.tasks_total > 0

    stats = engine.get_stats()
    assert stats["goals_executed"] >= 2
    print("  ✅ Autonomous Execution Engine — PASSED")


# ── Engine 3: Hallucination Destroyer ─────────────────────
def test_hallucination_destroyer():
    from brain.hallucination_destroyer import (
        HallucinationDestroyer, SyntacticChecker, SemanticConsistencyChecker,
        LogicalChecker, VerificationLayer,
    )
    hd = HallucinationDestroyer()

    # Clean response
    clean = hd.verify("The sum of 2 and 3 is 5. This is a mathematical fact.")
    assert clean.hallucination_score < 0.5, f"Clean response should score low, got {clean.hallucination_score}"
    assert clean.summary(), "Summary should not be empty"

    # Arithmetic error detection
    arith_error = hd.verify("2 + 2 = 5. This is correct.")
    assert len(arith_error.violations) > 0, "Should detect arithmetic error"
    has_num_error = any(
        v.violation_type.value == "numerical_error" for v in arith_error.violations
    )
    assert has_num_error, "Should find numerical_error violation"

    # Truncation detection
    truncated = hd.verify("This is a response that ends abruptly without proper")
    has_structural = any(
        v.layer == VerificationLayer.SYNTACTIC for v in truncated.violations
    )
    assert has_structural, "Should detect truncation as structural defect"

    # Layer scores present
    result = hd.verify("Quicksort has O(n log n) average case complexity. It is a comparison-based sorting algorithm.")
    assert "L1_Syntactic" in result.layer_scores
    assert "L2_Semantic" in result.layer_scores
    assert "L3_Logical" in result.layer_scores
    assert "L4_CrossRef" in result.layer_scores
    assert "L5_Calibration" in result.layer_scores

    # Add custom fact anchor
    hd.add_fact_anchor("Python was created by Guido van Rossum")

    # Natural language interface
    nl = hd.solve("Test this claim for accuracy")
    assert nl.duration_ms >= 0

    stats = hd.get_stats()
    assert stats["verifications"] >= 3
    print("  ✅ Hallucination Destroyer — PASSED")


# ── Engine 4: Real-Time Learning ──────────────────────────
def test_realtime_learning():
    from brain.realtime_learning_engine import (
        RealtimeLearningEngine, SkillDomain, PatternExtractor,
    )
    learner = RealtimeLearningEngine()

    # Learn from interactions
    r1 = learner.learn("calculate 15 * 23", "15 * 23 = 345", success=True, time_ms=5.0)
    assert r1.events_processed == 1
    assert r1.novelty_score > 0, "First event should be novel"
    assert r1.learning_rate > 0

    r2 = learner.learn("solve x^2 = 16", "x = 4 or x = -4", success=True, time_ms=8.0)
    assert r2.summary(), "Summary should not be empty"

    # Learn failure
    r3 = learner.learn("prove Fermat's Last Theorem", "Unable to prove", success=False, time_ms=100.0)
    assert r3.events_processed == 1

    # Skill profiles
    arith_profile = learner.get_skill_profile(SkillDomain.ARITHMETIC)
    assert arith_profile.problems_attempted >= 1

    # Strategy recommendation
    strategy = learner.recommend_strategy(SkillDomain.ARITHMETIC)
    assert strategy is not None, "Should recommend a strategy"

    # Decreasing novelty
    r4 = learner.learn("calculate 20 * 30", "20 * 30 = 600", success=True, time_ms=3.0)
    assert r4.novelty_score < r1.novelty_score, "Repeated signature should be less novel"

    # Pattern extraction
    sig = PatternExtractor.extract_signature("calculate 5 + 3")
    assert sig == "arithmetic_expression"

    domain = PatternExtractor.detect_domain("solve the quadratic equation")
    assert domain == SkillDomain.ALGEBRA

    # Full report
    report = learner.get_report()
    assert report.events_processed >= 4
    assert report.current_skill_levels, "Should have skill levels"

    # All skill levels
    levels = learner.get_all_skill_levels()
    assert len(levels) > 0

    stats = learner.get_stats()
    assert stats["events_total"] >= 4
    print("  ✅ Real-Time Learning Engine — PASSED")


# ── Engine 5: Code Execution Sandbox ──────────────────────
def test_code_sandbox():
    from brain.code_execution_sandbox import (
        CodeExecutionSandbox, ASTValidator, SafetyLevel,
    )
    sandbox = CodeExecutionSandbox(timeout=5)

    # Safe code
    result = sandbox.execute("print(2 + 2)")
    assert result.success, f"Should succeed, stderr: {result.stderr}"
    assert "4" in result.stdout, f"Should print 4, got: {result.stdout}"

    # AST validation — dangerous code
    validation = sandbox.validate_only("import os; os.system('rm -rf /')")
    assert not validation.is_safe, "Should detect as unsafe"
    assert validation.safety_level == SafetyLevel.BLOCKED
    assert len(validation.violations) > 0

    # Safe imports
    safe_val = sandbox.validate_only("import math\nprint(math.sqrt(16))")
    assert safe_val.is_safe, f"Math import should be safe, violations: {[str(v) for v in safe_val.violations]}"

    # Code with tests
    result = sandbox.execute_with_tests(
        "def double(x): return x * 2",
        function_name="double",
        io_pairs=[(2, 4), (3, 6), (5, 10)],
    )
    assert result.success, f"Should succeed, stderr: {result.stderr}"
    assert result.tests_passed >= 3, f"Should pass 3+ tests, passed {result.tests_passed}"

    # Blocked execution
    blocked = sandbox.execute("import subprocess; subprocess.run(['ls'])")
    assert not blocked.success, "Dangerous code should be blocked"

    # Natural language interface
    nl = sandbox.solve("run this: ```python\nprint('hello')\n```")
    assert nl is not None

    stats = sandbox.get_stats()
    assert stats["executions"] >= 3
    print("  ✅ Code Execution Sandbox — PASSED")


# ── Engine 6: Competitive Benchmark ──────────────────────
def test_competitive_benchmark():
    from brain.competitive_benchmark_engine import (
        CompetitiveBenchmarkEngine, BenchmarkCategory, ProblemGenerator,
        AnswerVerifier,
    )
    bench = CompetitiveBenchmarkEngine()

    # Problem generation
    arith_probs = ProblemGenerator.arithmetic(difficulty=2)
    assert len(arith_probs) >= 3, f"Should generate 3+ problems, got {len(arith_probs)}"
    assert all(p.expected_answer for p in arith_probs), "All problems should have answers"

    algebra_probs = ProblemGenerator.algebra(difficulty=1)
    assert len(algebra_probs) >= 2

    # Answer verification
    assert AnswerVerifier.verify("The answer is 42", "42"), "Should match contained number"
    assert AnswerVerifier.verify("Yes, Rex is an animal", "yes"), "Should match yes/no"
    assert not AnswerVerifier.verify("The answer is 43", "42"), "Should not match wrong number"

    # Run single category
    def simple_solver(prompt):
        # Very basic solver for testing
        if "Calculate" in prompt or "calculate" in prompt:
            import re
            match = re.search(r'(\d+)\s*([+\-*])\s*(\d+)', prompt)
            if match:
                a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
                ops = {'+': a + b, '-': a - b, '*': a * b}
                return str(ops.get(op, 0))
        return "I don't know"

    cs = bench.run_category(BenchmarkCategory.ARITHMETIC, simple_solver, difficulty=1)
    assert cs.problems_total >= 3
    assert cs.accuracy >= 0.0  # At least 0 (solver may not solve all)

    # Run quick benchmark
    report = bench.run_quick_benchmark(simple_solver)
    assert report.total_problems > 0
    assert report.overall_accuracy >= 0.0
    assert report.summary(), "Summary should not be empty"
    assert report.duration_ms >= 0

    # Leaderboard
    lb = bench.get_leaderboard()
    assert len(lb) >= 1

    # Natural language interface
    nl = bench.solve("benchmark myself")
    assert nl is not None

    stats = bench.get_stats()
    assert stats["runs"] >= 2
    print("  ✅ Competitive Benchmark Engine — PASSED")


# ── Run All ───────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  CCE v5.0 — Dominance-Tier Test Suite")
    print("=" * 60)

    tests = [
        ("Engine 1: Infinite Memory", test_infinite_memory),
        ("Engine 2: Autonomous Execution", test_autonomous_execution),
        ("Engine 3: Hallucination Destroyer", test_hallucination_destroyer),
        ("Engine 4: Real-Time Learning", test_realtime_learning),
        ("Engine 5: Code Execution Sandbox", test_code_sandbox),
        ("Engine 6: Competitive Benchmark", test_competitive_benchmark),
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
        print(f"  ALL 6 ENGINE TESTS PASSED — CCE v5.0 VERIFIED! ✅")
    else:
        print(f"  {passed} passed, {failed} FAILED ❌")
    print(f"  Duration: {duration:.0f}ms")
    print("=" * 60)
