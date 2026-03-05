"""Tests for the self-thinking brain components."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_memory_manager():
    """Test Bug Diary memory operations."""
    import tempfile
    from brain.memory import MemoryManager, FailureTuple

    with tempfile.TemporaryDirectory() as tmpdir:
        mem = MemoryManager(persist_dir=tmpdir)

        # Store a failure
        failure = FailureTuple(
            task="Parse JSON input",
            solution="json.loads(data)",
            action="parsing",
            observation="Crashed on empty string",
            root_cause="No null check",
            fix="Add if data: check",
            new_test="assert parse('') returns None",
            category="input_validation",
            severity=0.7,
        )
        fid = mem.store_failure(failure)
        assert fid == failure.id

        # Retrieve similar
        results = mem.retrieve_similar_failures("Parse JSON data")
        assert len(results) >= 1
        print(f"✅ Memory: stored + retrieved {len(results)} failures")

        # Check exponential decay counter
        weights = mem.get_recurring_categories()
        assert len(weights) >= 1
        print(f"✅ Category weights: {weights}")

        # Store another failure in same category
        failure2 = FailureTuple(
            task="Parse XML input",
            observation="Crashed on null",
            category="input_validation",
        )
        mem.store_failure(failure2)
        weights2 = mem.get_recurring_categories()
        # Weight should be γ*1.0 + 1.0 = 1.9 (with γ=0.9)
        print(f"✅ Updated weights: {weights2}")

        # Build context
        context = mem.build_context("Parse some data")
        assert "PAST FAILURES" in context or "RECURRING" in context
        print(f"✅ Context built: {len(context)} chars")


def test_hypothesis_engine():
    """Test multi-hypothesis thinking."""
    from brain.hypothesis import HypothesisEngine, Hypothesis

    engine = HypothesisEngine()

    # Create hypotheses manually
    engine.hypotheses = [
        Hypothesis(id=0, description="Approach A", weight=0.5),
        Hypothesis(id=1, description="Approach B", weight=0.3),
        Hypothesis(id=2, description="Approach C", weight=0.2),
    ]

    # Update with evidence
    evidence = {0: 0.2, 1: 0.8, 2: 0.5}  # Lower loss = better
    engine.update_weights(evidence)

    # Check weights re-normalized
    total = sum(h.weight for h in engine.hypotheses)
    assert abs(total - 1.0) < 0.01
    print(f"✅ Weights after update: {[f'{h.weight:.3f}' for h in engine.hypotheses]}")

    # Best should be id=0 (lowest loss)
    best = engine.get_best_hypothesis()
    assert best.id == 0
    print(f"✅ Best hypothesis: {best.description} (w={best.weight:.3f})")


def test_verifier_stack():
    """Test 4-layer verification."""
    from brain.verifier import VerifierStack

    verifier = VerifierStack()

    # Fake generate function
    def fake_generate(prompt):
        return "OVERALL_SCORE: 7\nEdge cases handled well."

    report = verifier.verify(
        candidate="This is a well-structured solution with error handling.",
        task="Write a robust parser",
        generate_fn=fake_generate,
    )

    assert 0 <= report.confidence <= 1
    print(f"✅ Verification: conf={report.confidence:.3f}, passed={report.passed}")
    print(f"   Scores: static={report.v_static:.2f}, prop={report.v_property:.2f}, "
          f"scenario={report.v_scenario:.2f}, critic={report.v_critic:.2f}")


def test_risk_manager():
    """Test Tri-Shield + Safe Action Gating."""
    from brain.risk_manager import RiskManager, GatingMode
    from brain.verifier import VerificationReport

    rm = RiskManager()

    # High confidence report → should execute
    good_report = VerificationReport(
        v_static=0.9, v_property=0.85, v_scenario=0.8, v_critic=0.9,
        confidence=0.88,
    )
    assessment = rm.assess_risk(
        candidate="Safe solution",
        task="Simple query",
        verification=good_report,
        action_type="general",
    )
    print(f"✅ High confidence: mode={assessment.mode.value}, risk={assessment.risk_level:.3f}")

    # Low confidence report → should refuse
    bad_report = VerificationReport(
        v_static=0.3, v_property=0.2, v_scenario=0.1, v_critic=0.2,
        confidence=0.15,
    )
    assessment2 = rm.assess_risk(
        candidate="Risky solution",
        task="Delete all files",
        verification=bad_report,
        action_type="file_delete",
    )
    assert assessment2.mode == GatingMode.REFUSE
    print(f"✅ Low confidence: mode={assessment2.mode.value}, risk={assessment2.risk_level:.3f}")


if __name__ == "__main__":
    test_memory_manager()
    test_hypothesis_engine()
    test_verifier_stack()
    test_risk_manager()
    print("\n✅ All brain tests passed!")
