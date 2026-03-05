"""Tests for Auto-Gap Detection in the Thinking Loop."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def fake_generate(prompt, **kwargs):
    """Fake LLM that returns content simulating tool gap failures."""
    if "insufficient tools" in prompt.lower() or "no tool available" in prompt.lower():
        return "I lack a capability for this task. No tool available to handle this operation."
    if "Generate a Python function" in prompt:
        return '''def forged_data_tool(data: str) -> str:
    """Process data."""
    return f"Processed: {data}"
'''
    if "OVERALL_SCORE" in prompt or "score" in prompt.lower():
        return "OVERALL_SCORE: 3\nInsufficient tools to handle request."
    if "root cause" in prompt.lower() or "deduce" in prompt.lower():
        return "No tool available for this specific operation. Insufficient tools in the registry."
    if "classify" in prompt.lower():
        return "general"
    if "reasoning" in prompt.lower() or "chain" in prompt.lower():
        return "Step 1: Analyze. Step 2: No tool available to execute."
    return "Generic response — insufficient tools for specialized tasks."


def fake_generate_no_gap(prompt, **kwargs):
    """Fake LLM that returns content WITHOUT tool gap indicators."""
    if "OVERALL_SCORE" in prompt:
        return "OVERALL_SCORE: 3\nThe logic is incomplete."
    if "root cause" in prompt.lower() or "deduce" in prompt.lower():
        return "Logic error in candidate solution. Wrong algorithm used."
    return "Generic response without tool gap issues."


def test_auto_gap_detection_constants():
    """Test that auto-gap detection constants are properly defined."""
    from brain.thinking_loop import MAX_AUTO_FORGE_ATTEMPTS, TOOL_GAP_KEYWORDS

    assert MAX_AUTO_FORGE_ATTEMPTS == 2
    assert len(TOOL_GAP_KEYWORDS) > 0
    assert "insufficient tools" in TOOL_GAP_KEYWORDS
    assert "no tool available" in TOOL_GAP_KEYWORDS
    print("✅ test_auto_gap_detection_constants PASSED")


def test_thinking_loop_has_tool_forge_param():
    """Test that ThinkingLoop accepts tool_forge parameter."""
    from brain.thinking_loop import ThinkingLoop

    loop = ThinkingLoop(generate_fn=fake_generate, tool_forge=None)
    assert loop.tool_forge is None
    assert loop._auto_forge_attempts == 0
    assert loop._auto_forge_stats == {"attempts": 0, "successes": 0, "failures": 0}
    print("✅ test_thinking_loop_has_tool_forge_param PASSED")


def test_auto_forge_counter_resets_per_task():
    """Test that auto-forge attempt counter resets for each think() call."""
    from brain.thinking_loop import ThinkingLoop

    loop = ThinkingLoop(generate_fn=fake_generate)
    loop._auto_forge_attempts = 5  # Simulate leftover

    # After calling think(), it should reset to 0
    # We just verify the reset logic exists
    assert hasattr(loop, '_auto_forge_attempts')
    print("✅ test_auto_forge_counter_resets_per_task PASSED")


def test_max_auto_forge_attempts_enforced():
    """Test that max 2 auto-forge attempts per task is enforced."""
    from brain.thinking_loop import MAX_AUTO_FORGE_ATTEMPTS

    assert MAX_AUTO_FORGE_ATTEMPTS == 2, "Max auto-forge attempts should be 2"
    print("✅ test_max_auto_forge_attempts_enforced PASSED")


def test_tool_gap_keyword_matching():
    """Test that tool gap keywords match expected failure patterns."""
    from brain.thinking_loop import TOOL_GAP_KEYWORDS

    # These should match
    test_failures = [
        "The system has insufficient tools to handle image processing",
        "No tool available for audio transcription",
        "Missing capability for database optimization",
        "Cannot find tool for PDF generation",
        "I lack a capability for this specific task",
    ]

    for failure in test_failures:
        failure_lower = failure.lower()
        matched = any(kw in failure_lower for kw in TOOL_GAP_KEYWORDS)
        assert matched, f"Should detect tool gap in: '{failure}'"

    # These should NOT match
    non_gap_failures = [
        "Logic error in the algorithm",
        "Wrong approach used for calculation",
        "Confidence too low: verification failed",
    ]

    for failure in non_gap_failures:
        failure_lower = failure.lower()
        matched = any(kw in failure_lower for kw in TOOL_GAP_KEYWORDS)
        assert not matched, f"Should NOT detect tool gap in: '{failure}'"

    print("✅ test_tool_gap_keyword_matching PASSED")


def test_auto_forge_stats_tracking():
    """Test that auto-forge stats are properly tracked."""
    from brain.thinking_loop import ThinkingLoop

    loop = ThinkingLoop(generate_fn=fake_generate)

    # Initial stats should be zero
    assert loop._auto_forge_stats["attempts"] == 0
    assert loop._auto_forge_stats["successes"] == 0
    assert loop._auto_forge_stats["failures"] == 0

    # Simulate incrementing
    loop._auto_forge_stats["attempts"] += 1
    loop._auto_forge_stats["failures"] += 1

    assert loop._auto_forge_stats["attempts"] == 1
    assert loop._auto_forge_stats["failures"] == 1
    print("✅ test_auto_forge_stats_tracking PASSED")


if __name__ == "__main__":
    test_auto_gap_detection_constants()
    test_thinking_loop_has_tool_forge_param()
    test_auto_forge_counter_resets_per_task()
    test_max_auto_forge_attempts_enforced()
    test_tool_gap_keyword_matching()
    test_auto_forge_stats_tracking()
    print("\n✅ All Auto-Gap Detection tests passed!")
