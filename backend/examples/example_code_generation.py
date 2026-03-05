"""
Example: Code Generation with Self-Healing Verification.
═════════════════════════════════════════════════════════

Demonstrates:
- Code generation through the thinking loop
- 6-layer verification (including real AST analysis)
- Verifier calibration updates
- Comparison of good vs dangerous code scoring

No API keys needed — uses deterministic MockLLM.

Usage:
    python examples/example_code_generation.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.mock_llm import MockLLM
from brain.verifier import VerifierStack


def main():
    print("\n" + "═" * 70)
    print("  🔍  Super-System Brain — Code Verification Example")
    print("═" * 70)

    verifier = VerifierStack()

    # ── Scenario 1: Good code ──
    print("\n📋 Scenario 1: Well-structured code")
    print("─" * 70)

    good_code = '''
def binary_search(arr: list, target: int) -> int:
    """Find target in sorted array using binary search.

    Args:
        arr: Sorted list of integers
        target: Value to find

    Returns:
        Index of target, or -1 if not found
    """
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
'''

    mock_high = MockLLM(quality="high")
    report_good = verifier.verify(
        candidate=good_code,
        task="Implement binary search",
        generate_fn=mock_high.generate,
    )

    print(f"\n{report_good.summary()}")
    print(f"\nStatic checks:")
    for detail in report_good.static_details:
        print(f"  {detail}")

    # ── Scenario 2: Dangerous code ──
    print("\n\n📋 Scenario 2: Dangerous code with security issues")
    print("─" * 70)

    dangerous_code = '''
def process_user_input(data):
    result = eval(data)
    cmd = f"echo {data}"
    import os
    os.system(cmd)
    return result
'''

    mock_low = MockLLM(quality="low")
    report_bad = verifier.verify(
        candidate=dangerous_code,
        task="Process user input safely",
        generate_fn=mock_low.generate,
    )

    print(f"\n{report_bad.summary()}")
    print(f"\nStatic checks:")
    for detail in report_bad.static_details:
        print(f"  {detail}")

    # ── Scenario 3: Syntactically broken code ──
    print("\n\n📋 Scenario 3: Code with syntax errors")
    print("─" * 70)

    broken_code = '''
def broken_function(x
    if x > 0
        return x
    else
        return -x
'''

    report_broken = verifier.verify(
        candidate=broken_code,
        task="Write an absolute value function",
        generate_fn=mock_low.generate,
    )

    print(f"\n{report_broken.summary()}")
    print(f"\nStatic checks:")
    for detail in report_broken.static_details:
        print(f"  {detail}")

    # ── Comparison ──
    print("\n\n📊 COMPARISON:")
    print("─" * 70)
    print(f"  {'Scenario':<25} {'Confidence':>12} {'Static':>10} {'Passed':>8}")
    print(f"  {'─'*25} {'─'*12} {'─'*10} {'─'*8}")
    print(f"  {'Good code':<25} {report_good.confidence:>12.4f} {report_good.v_static:>10.3f} {'YES' if report_good.passed else 'NO':>8}")
    print(f"  {'Dangerous code':<25} {report_bad.confidence:>12.4f} {report_bad.v_static:>10.3f} {'YES' if report_bad.passed else 'NO':>8}")
    print(f"  {'Broken code':<25} {report_broken.confidence:>12.4f} {report_broken.v_static:>10.3f} {'YES' if report_broken.passed else 'NO':>8}")

    # ── Calibration ──
    print("\n\n📈 VERIFIER CALIBRATION:")
    print("─" * 70)
    verifier.calibrate(report_good, actual_success=True)
    verifier.calibrate(report_bad, actual_success=False)
    verifier.calibrate(report_broken, actual_success=False)

    print(f"  Calibration rounds: {len(verifier._calibration_history)}")
    print(f"  Updated weights (alpha):")
    for key, val in verifier.alpha.items():
        print(f"    {key:<12}: {val:.4f}")

    print("\n" + "═" * 70)
    print("  ✅  Code verification example completed!")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
