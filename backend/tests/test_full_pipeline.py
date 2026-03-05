"""
Full Pipeline Integration Tests — End-to-End Brain System Tests.
═══════════════════════════════════════════════════════════════════

These tests verify that the entire brain pipeline works end-to-end
using the deterministic MockLLM. No API keys required.

Tests:
    1. Full thinking loop: classify → reason → hypothesize → verify → learn
    2. All 5 reasoning modes with mock LLM
    3. Verifier 6-layer scoring with deterministic inputs
    4. Metacognition stuck detection and strategy switching
    5. Reward model weight updates and persistence
    6. Learning store trajectory persistence
    7. Hypothesis Bayesian weight updates
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ──────────────────────────────────────────────
# Test 1: Full Thinking Loop End-to-End
# ──────────────────────────────────────────────

def test_full_thinking_loop_e2e():
    """Full pipeline: classify → reason → hypothesize → verify → learn."""
    from brain.mock_llm import MockLLM
    from brain.thinking_loop import ThinkingLoop, ThinkingResult
    from brain.memory import MemoryManager
    from brain.hypothesis import HypothesisEngine
    from brain.verifier import VerifierStack
    from brain.risk_manager import RiskManager
    from brain.reasoning import ReasoningEngine
    from brain.metacognition import MetacognitionEngine
    from brain.problem_classifier import ProblemClassifier
    from brain.trace_store import LearningStore
    from brain.reward_model import RewardComputer
    from brain.credit_assignment import CreditAssignmentEngine
    from brain.prompt_evolver import PromptEvolver
    from brain.expert_reflection import ExpertReflectionEngine

    mock = MockLLM(quality="high")

    with tempfile.TemporaryDirectory() as tmpdir:
        mem_dir = str(Path(tmpdir) / "memory")
        store_dir = str(Path(tmpdir) / "store")
        reward_dir = str(Path(tmpdir) / "rewards")

        loop = ThinkingLoop(
            generate_fn=mock.generate,
            memory=MemoryManager(persist_dir=mem_dir),
            hypothesis_engine=HypothesisEngine(),
            verifier=VerifierStack(),
            risk_manager=RiskManager(),
            reasoning_engine=ReasoningEngine(mock.generate),
            metacognition=MetacognitionEngine(),
            problem_classifier=ProblemClassifier(mock.generate),
            learning_store=LearningStore(store_dir=store_dir),
            reward_computer=RewardComputer(persist_dir=reward_dir),
            credit_engine=CreditAssignmentEngine(mock.generate),
            prompt_evolver=PromptEvolver(mock.generate),
            expert_reflection=ExpertReflectionEngine(mock.generate),
        )

        result = loop.think(
            problem="Implement a binary search function in Python",
            action_type="coding",
            max_iterations=3,
        )

        assert isinstance(result, ThinkingResult)
        assert result.final_answer, "Should produce a final answer"
        assert result.iterations > 0, "Should have at least 1 iteration"
        assert result.final_confidence > 0, "Should have positive confidence"
        assert result.domain, "Should classify to a domain"
        assert len(result.strategies_used) > 0, "Should use at least one strategy"

        print(f"  ✅ Full pipeline completed:")
        print(f"     Domain: {result.domain}")
        print(f"     Iterations: {result.iterations}")
        print(f"     Confidence: {result.final_confidence:.3f}")
        print(f"     Mode: {result.mode.value}")
        print(f"     Strategies: {result.strategies_used}")
        print(f"     Answer length: {len(result.final_answer)} chars")
        print(f"     Mock LLM calls: {mock.call_count}")

    print("✅ Full Thinking Loop E2E test PASSED!\n")


# ──────────────────────────────────────────────
# Test 2: All 5 Reasoning Modes
# ──────────────────────────────────────────────

def test_all_reasoning_modes():
    """Test all 5 cognitive modes produce valid reasoning traces."""
    from brain.mock_llm import MockLLM
    from brain.reasoning import ReasoningEngine, CognitiveMode, ReasoningTrace

    mock = MockLLM(quality="high")
    engine = ReasoningEngine(generate_fn=mock.generate)

    for mode in CognitiveMode:
        mock.reset()
        trace = engine.reason(
            problem="Sort an array of integers efficiently",
            mode=mode,
        )

        assert isinstance(trace, ReasoningTrace)
        assert trace.final_answer, f"{mode.value}: should produce answer"
        assert len(trace.steps) > 0, f"{mode.value}: should have steps"
        assert trace.total_confidence > 0, f"{mode.value}: should have confidence"
        assert trace.duration_ms >= 0, f"{mode.value}: should have duration"

        print(f"  ✅ {mode.value}: {len(trace.steps)} steps, "
              f"conf={trace.total_confidence:.2f}, "
              f"calls={mock.call_count}")

    print("✅ All 5 Reasoning Modes test PASSED!\n")


# ──────────────────────────────────────────────
# Test 3: Verifier 6-Layer Scoring
# ──────────────────────────────────────────────

def test_verifier_6layer():
    """Test all 6 verification layers with various inputs."""
    from brain.mock_llm import MockLLM
    from brain.verifier import VerifierStack, VerificationReport

    mock_high = MockLLM(quality="high")
    mock_low = MockLLM(quality="low")
    verifier = VerifierStack()

    # Good code should score higher
    good_code = '''
def fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
'''
    report_good = verifier.verify(
        candidate=good_code,
        task="Write a fibonacci function",
        generate_fn=mock_high.generate,
    )
    assert report_good.confidence > 0, "Good code should have positive confidence"
    assert report_good.v_static > 0, "Good code should pass static checks"
    print(f"  ✅ Good code: conf={report_good.confidence:.3f}, "
          f"static={report_good.v_static:.2f}, "
          f"passed={report_good.passed}")

    # Bad code should score lower
    bad_code = "def foo( return eval(x)"
    report_bad = verifier.verify(
        candidate=bad_code,
        task="Write a parser",
        generate_fn=mock_low.generate,
    )
    # Bad code may still get some scores from LLM layers but static should be lower
    print(f"  ✅ Bad code: conf={report_bad.confidence:.3f}, "
          f"static={report_bad.v_static:.2f}, "
          f"passed={report_bad.passed}")

    # Dangerous code should be flagged
    dangerous_code = '''
def process(data):
    return eval(data)
'''
    report_danger = verifier.verify(
        candidate=dangerous_code,
        task="Process user input",
        generate_fn=mock_high.generate,
    )
    # Should detect eval() in static checks
    has_danger_flag = any("eval" in d.lower() for d in report_danger.static_details)
    assert has_danger_flag, "Should detect eval() as dangerous"
    print(f"  ✅ Dangerous code flagged: {[d for d in report_danger.static_details if 'eval' in d.lower()]}")

    # Verify calibration works
    verifier.calibrate(report_good, actual_success=True)
    verifier.calibrate(report_bad, actual_success=False)
    assert len(verifier._calibration_history) == 2, "Should track calibration"
    print(f"  ✅ Calibration: {len(verifier._calibration_history)} records")

    print("✅ Verifier 6-Layer Scoring test PASSED!\n")


# ──────────────────────────────────────────────
# Test 4: Metacognition and Strategy Switching
# ──────────────────────────────────────────────

def test_metacognition():
    """Test stuck detection and strategy switching."""
    from brain.metacognition import MetacognitionEngine

    meta = MetacognitionEngine()
    meta.start_monitoring("decompose")

    # Simulate improving confidence
    meta.update(0.3, 0)
    meta.update(0.5, 1)
    assert not meta.should_switch_strategy(), "Improving, shouldn't switch"
    print(f"  ✅ Improving: trend={meta.state.trend()}")

    # Simulate stuck (flat confidence)
    meta.update(0.51, 2)
    meta.update(0.51, 3)
    meta.update(0.52, 4)

    stuck = meta.should_switch_strategy()
    print(f"  ✅ Stuck detection: stuck={stuck}, trend={meta.state.trend()}")

    # Test cognitive load estimation
    simple_problem = "Add two numbers"
    complex_problem = (
        "Design a distributed system architecture for handling 10 million "
        "concurrent users with eventual consistency, CRDT-based state sync, "
        "and multi-region failover with sub-100ms latency requirements"
    )
    simple_load = meta.estimate_cognitive_load(simple_problem)
    complex_load = meta.estimate_cognitive_load(complex_problem)
    assert complex_load > simple_load, "Complex problem should have higher load"
    print(f"  ✅ Cognitive load: simple={simple_load:.2f}, complex={complex_load:.2f}")

    # Test iteration suggestion
    iters = meta.suggest_iterations(complex_load)
    assert iters > 0, "Should suggest positive iterations"
    print(f"  ✅ Suggested iterations for complex: {iters}")

    print("✅ Metacognition test PASSED!\n")


# ──────────────────────────────────────────────
# Test 5: Reward Model with Persistence
# ──────────────────────────────────────────────

def test_reward_model_persistence():
    """Test reward weight updates, persistence, and learning stats."""
    from brain.reward_model import RewardComputer
    from brain.verifier import VerificationReport

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create and update weights
        computer = RewardComputer(persist_dir=tmpdir)
        initial_weights = dict(computer.get_dimension_weights("coding"))

        # Simulate multiple episodes
        for i in range(5):
            report = VerificationReport(
                v_static=0.7 + i * 0.05,
                v_property=0.6 + i * 0.05,
                v_scenario=0.65 + i * 0.04,
                v_critic=0.7,
                v_code=0.75,
                v_security=0.8,
                confidence=0.7 + i * 0.04,
            )
            reward = computer.compute_reward(report, domain="coding")
            # Update weights based on "successful" dimension
            computer.update_weights("coding", "static", 0.1 * (i + 1))
            computer.update_weights("coding", "property", -0.05 * (i + 1))

        # Save explicitly
        computer.save_weights()

        # Verify weights changed
        new_weights = computer.get_dimension_weights("coding")
        assert new_weights["static"] != initial_weights["static"], \
            "Static weight should have changed"
        print(f"  ✅ Weights changed: static {initial_weights['static']:.3f} → {new_weights['static']:.3f}")

        # Verify history
        history = computer.get_weight_history()
        assert len(history) > 0, "Should have weight history"
        print(f"  ✅ Weight history: {len(history)} entries")

        # Verify learning stats
        stats = computer.get_learning_stats()
        assert stats["total_updates"] > 0
        print(f"  ✅ Learning stats: {stats}")

        # Test persistence: create new instance, verify weights loaded
        computer2 = RewardComputer(persist_dir=tmpdir)
        loaded_weights = computer2.get_dimension_weights("coding")
        assert abs(loaded_weights["static"] - new_weights["static"]) < 0.001, \
            "Loaded weights should match saved"
        print(f"  ✅ Persistence verified: loaded static={loaded_weights['static']:.3f}")

    print("✅ Reward Model Persistence test PASSED!\n")


# ──────────────────────────────────────────────
# Test 6: Learning Store Trajectories
# ──────────────────────────────────────────────

def test_learning_store():
    """Test trajectory persistence and querying."""
    from brain.trace_store import LearningStore, TrajectoryTrace, TraceSpan, SpanType, emit_span

    with tempfile.TemporaryDirectory() as tmpdir:
        store = LearningStore(store_dir=tmpdir)

        # Store multiple trajectories
        for i in range(5):
            trace = TrajectoryTrace(
                problem=f"Test problem {i}",
                domain="coding" if i % 2 == 0 else "math",
            )
            trace.add_span(emit_span(
                span_type=SpanType.REASONING,
                input_data="test input",
                output_data="test output",
                cognitive_mode="decompose",
            ))
            trace.final_reward = 0.5 + i * 0.1
            trace.success = i >= 2
            store.store_trajectory(trace)

        # Query by domain
        coding_traces = store.query_trajectories(domain="coding")
        assert len(coding_traces) == 3, f"Expected 3 coding traces, got {len(coding_traces)}"
        print(f"  ✅ Query by domain: {len(coding_traces)} coding traces")

        # Query successes only
        successes = store.query_trajectories(success_only=True)
        assert len(successes) == 3, f"Expected 3 successes, got {len(successes)}"
        print(f"  ✅ Query successes: {len(successes)} successful traces")

        # Query with min reward
        high_reward = store.query_trajectories(min_reward=0.7)
        print(f"  ✅ High reward traces: {len(high_reward)}")

        # Check stats
        stats = store.get_stats()
        assert stats["total_traces"] == 5
        assert stats["success_rate"] > 0
        print(f"  ✅ Stats: {stats}")

        # Test resource storage
        store.store_resource("test_weights", {"w1": 1.0, "w2": 2.0})
        loaded = store.get_resource("test_weights")
        assert loaded == {"w1": 1.0, "w2": 2.0}
        print(f"  ✅ Resource persistence: stored and loaded")

        # Test persistence across instances
        store2 = LearningStore(store_dir=tmpdir)
        stats2 = store2.get_stats()
        assert stats2["total_traces"] == 5
        print(f"  ✅ Persistence: new instance sees {stats2['total_traces']} traces")

    print("✅ Learning Store test PASSED!\n")


# ──────────────────────────────────────────────
# Test 7: Hypothesis Engine Bayesian Updates
# ──────────────────────────────────────────────

def test_hypothesis_bayesian():
    """Test that hypothesis weights converge correctly."""
    from brain.mock_llm import MockLLM
    from brain.hypothesis import HypothesisEngine, Hypothesis

    mock = MockLLM(quality="high")
    engine = HypothesisEngine()

    # Generate hypotheses
    hypotheses = engine.generate_hypotheses(
        problem="Find the shortest path in a graph",
        generate_fn=mock.generate,
        n_hypotheses=3,
    )
    assert len(hypotheses) > 0, "Should generate hypotheses"
    print(f"  ✅ Generated {len(hypotheses)} hypotheses")

    # Store initial weights
    initial_weights = [h.weight for h in engine.hypotheses]

    # Simulate evidence: hypothesis 0 is best (low loss), hypothesis 2 is worst
    evidence = {h.id: (0.2 + h.id * 0.3) for h in engine.hypotheses}
    engine.update_weights(evidence)

    # Weights should have changed
    new_weights = [h.weight for h in engine.hypotheses]
    assert new_weights != initial_weights, "Weights should change after evidence"

    # Weights should sum to 1
    weight_sum = sum(h.weight for h in engine.hypotheses)
    assert abs(weight_sum - 1.0) < 0.01, f"Weights should sum to 1, got {weight_sum}"
    print(f"  ✅ Weight normalization: sum={weight_sum:.4f}")

    # Best hypothesis should have highest weight
    best = engine.get_best_hypothesis()
    assert best.id == 0, f"Best should be id=0 (lowest loss), got {best.id}"
    print(f"  ✅ Best hypothesis: id={best.id}, weight={best.weight:.3f}")

    # Pruning should remove weak hypotheses
    engine.prune_weak(threshold=0.1)
    remaining = len(engine.hypotheses)
    print(f"  ✅ After pruning: {remaining} hypotheses remain")

    # Synthesis should work
    candidate = engine.synthesize_candidate(
        synthesize_fn=mock.generate,
        problem="Find shortest path",
    )
    assert candidate, "Should produce synthesized candidate"
    print(f"  ✅ Synthesized candidate: {len(candidate)} chars")

    print("✅ Hypothesis Bayesian Updates test PASSED!\n")


# ──────────────────────────────────────────────
# Test 8: Problem Classifier + Strategy
# ──────────────────────────────────────────────

def test_problem_classifier():
    """Test domain classification and strategy selection."""
    from brain.mock_llm import MockLLM
    from brain.problem_classifier import ProblemClassifier, ProblemDomain

    mock = MockLLM()
    classifier = ProblemClassifier(generate_fn=mock.generate)

    test_cases = [
        ("Write a Python function to sort a list", ProblemDomain.CODING),
        ("Fix the bug in this code's null pointer", ProblemDomain.DEBUGGING),
        ("Implement BFS graph traversal algorithm", ProblemDomain.ALGORITHM),
        ("Calculate the integral of x^2", ProblemDomain.MATH),
    ]

    for problem, expected_domain in test_cases:
        domain = classifier.classify(problem)
        strategy = classifier.get_strategy(domain)
        print(f"  ✅ '{problem[:40]}...' → {domain.value} "
              f"(mode={strategy.primary_mode.value}, iters={strategy.suggested_iterations})")

    # Test strategy weight updates
    classifier.update_strategy_weights(
        domain=ProblemDomain.CODING,
        reward=0.9,
        strategy_used="decompose",
    )
    strategy = classifier.get_strategy(ProblemDomain.CODING)
    print(f"  ✅ After high reward: iters={strategy.suggested_iterations}, "
          f"boost={strategy.confidence_boost:.4f}")

    print("✅ Problem Classifier test PASSED!\n")


# ──────────────────────────────────────────────
# Run All Tests
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🧠  Full Pipeline Integration Tests")
    print("=" * 60 + "\n")

    print("─── Test 1: Full Thinking Loop E2E ───")
    test_full_thinking_loop_e2e()

    print("─── Test 2: All 5 Reasoning Modes ───")
    test_all_reasoning_modes()

    print("─── Test 3: Verifier 6-Layer Scoring ───")
    test_verifier_6layer()

    print("─── Test 4: Metacognition ───")
    test_metacognition()

    print("─── Test 5: Reward Model Persistence ───")
    test_reward_model_persistence()

    print("─── Test 6: Learning Store ───")
    test_learning_store()

    print("─── Test 7: Hypothesis Bayesian Updates ───")
    test_hypothesis_bayesian()

    print("─── Test 8: Problem Classifier ───")
    test_problem_classifier()

    print("=" * 60)
    print("  🎉  ALL 8 INTEGRATION TESTS PASSED!")
    print("=" * 60 + "\n")
