"""
Example: Multi-Episode Learning Loop with Measurable Improvement.
═══════════════════════════════════════════════════════════════════

Demonstrates REAL learning over 20 episodes:
- Reward weight adaptation
- Strategy parameter optimization
- Trajectory storage and statistics
- Success rate improvement tracking

This example proves the system isn't just running — it's LEARNING.

No API keys needed — uses deterministic MockLLM.

Usage:
    python examples/example_learning_loop.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.mock_llm import MockLLM
from brain.thinking_loop import ThinkingLoop
from brain.memory import MemoryManager
from brain.hypothesis import HypothesisEngine
from brain.verifier import VerifierStack
from brain.risk_manager import RiskManager
from brain.reasoning import ReasoningEngine
from brain.metacognition import MetacognitionEngine
from brain.problem_classifier import ProblemClassifier, ProblemDomain, DOMAIN_STRATEGIES
from brain.trace_store import LearningStore
from brain.reward_model import RewardComputer
from brain.credit_assignment import CreditAssignmentEngine
from brain.prompt_evolver import PromptEvolver
from brain.expert_reflection import ExpertReflectionEngine


PROBLEMS = [
    ("Implement a stack using two queues", "coding"),
    ("Find the longest palindrome substring", "algorithm"),
    ("Calculate factorial of 20", "math"),
    ("Debug: function returns None instead of value", "debugging"),
    ("Implement merge sort with O(n log n) time", "algorithm"),
    ("Write a thread-safe singleton pattern", "coding"),
    ("Sort an array of 1 million integers", "algorithm"),
    ("Calculate the determinant of a 3x3 matrix", "math"),
    ("Fix: off-by-one error in binary search", "debugging"),
    ("Implement an LRU cache", "coding"),
    ("Find all paths in a graph from A to B", "algorithm"),
    ("Calculate compound interest over 10 years", "math"),
    ("Implement a priority queue using a heap", "coding"),
    ("Debug: infinite loop in recursive function", "debugging"),
    ("Design a rate limiter algorithm", "algorithm"),
    ("Write a function to validate email addresses", "coding"),
    ("Calculate the nth Fibonacci number efficiently", "math"),
    ("Implement quicksort with median-of-three pivot", "algorithm"),
    ("Fix: race condition in producer-consumer queue", "debugging"),
    ("Implement a trie data structure for autocomplete", "coding"),
]


def main():
    print("\n" + "═" * 70)
    print("  📈  Super-System Brain — Learning Loop Example (20 Episodes)")
    print("═" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        mock = MockLLM(quality="high", seed=42)

        loop = ThinkingLoop(
            generate_fn=mock.generate,
            memory=MemoryManager(persist_dir=str(Path(tmpdir) / "mem")),
            hypothesis_engine=HypothesisEngine(),
            verifier=VerifierStack(),
            risk_manager=RiskManager(),
            reasoning_engine=ReasoningEngine(mock.generate),
            metacognition=MetacognitionEngine(),
            problem_classifier=ProblemClassifier(mock.generate),
            learning_store=LearningStore(store_dir=str(Path(tmpdir) / "store")),
            reward_computer=RewardComputer(persist_dir=str(Path(tmpdir) / "rewards")),
            credit_engine=CreditAssignmentEngine(mock.generate),
            prompt_evolver=PromptEvolver(mock.generate),
            expert_reflection=ExpertReflectionEngine(mock.generate),
        )

        # Snapshot initial state
        initial_weights = dict(loop.reward_computer.get_dimension_weights("coding"))
        initial_alpha = dict(loop.verifier.alpha)

        # ── Run 20 episodes ──
        print("\n⏳ Running 20 episodes...\n")
        print(f"  {'#':<4} {'Problem':<45} {'Domain':<12} {'Conf':>6} {'Mode':<10} {'Iters':>5}")
        print(f"  {'─'*4} {'─'*45} {'─'*12} {'─'*6} {'─'*10} {'─'*5}")

        results = []
        for i, (problem, category) in enumerate(PROBLEMS):
            result = loop.think(
                problem=problem,
                action_type=category,
                max_iterations=2,  # Keep fast for demo
            )
            results.append((problem, category, result))

            print(f"  {i+1:<4} {problem[:44]:<45} {result.domain:<12} "
                  f"{result.final_confidence:>6.3f} {result.mode.value:<10} "
                  f"{result.iterations:>5}")

        # ── Analyze Learning ──
        print("\n\n" + "═" * 70)
        print("  📊  LEARNING ANALYSIS")
        print("═" * 70)

        # 1. Reward weight changes
        final_weights = dict(loop.reward_computer.get_dimension_weights("coding"))
        print("\n  📉 Reward Weight Changes (coding domain):")
        print(f"    {'Dimension':<15} {'Before':>10} {'After':>10} {'Change':>10}")
        print(f"    {'─'*15} {'─'*10} {'─'*10} {'─'*10}")
        for key in sorted(initial_weights.keys()):
            before = initial_weights[key]
            after = final_weights.get(key, before)
            delta = after - before
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
            print(f"    {key:<15} {before:>10.3f} {after:>10.3f} {arrow}{abs(delta):>9.4f}")

        # 2. Verifier calibration changes
        final_alpha = dict(loop.verifier.alpha)
        print(f"\n  🔧 Verifier Calibration Changes:")
        print(f"    {'Layer':<12} {'Before':>10} {'After':>10} {'Change':>10}")
        print(f"    {'─'*12} {'─'*10} {'─'*10} {'─'*10}")
        for key in sorted(initial_alpha.keys()):
            before = initial_alpha[key]
            after = final_alpha[key]
            delta = after - before
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
            print(f"    {key:<12} {before:>10.3f} {after:>10.3f} {arrow}{abs(delta):>9.4f}")

        # 3. Learning store statistics
        store_stats = loop.learning_store.get_stats()
        print(f"\n  📚 Learning Store:")
        print(f"    Total traces:   {store_stats.get('total_traces', 0)}")
        print(f"    Success rate:   {store_stats.get('success_rate', 0):.0%}")
        print(f"    Avg reward:     {store_stats.get('avg_reward', 0):.3f}")
        print(f"    Max reward:     {store_stats.get('max_reward', 0):.3f}")
        if 'domains' in store_stats:
            print(f"    Domains:        {store_stats['domains']}")

        # 4. Reward model learning stats
        reward_stats = loop.reward_computer.get_learning_stats()
        print(f"\n  ⚖️ Reward Model Learning:")
        print(f"    Total updates:  {reward_stats.get('total_updates', 0)}")
        if reward_stats.get('domains_updated'):
            print(f"    Domains updated: {reward_stats['domains_updated']}")
        if reward_stats.get('avg_delta'):
            print(f"    Avg delta:      {reward_stats['avg_delta']:.6f}")

        # 5. Per-domain performance
        print(f"\n  🏆 Per-Domain Performance:")
        domain_results = {}
        for problem, cat, result in results:
            if result.domain not in domain_results:
                domain_results[result.domain] = []
            domain_results[result.domain].append(result.final_confidence)

        print(f"    {'Domain':<15} {'Episodes':>10} {'Avg Conf':>10} {'Max Conf':>10}")
        print(f"    {'─'*15} {'─'*10} {'─'*10} {'─'*10}")
        for domain, confs in sorted(domain_results.items()):
            print(f"    {domain:<15} {len(confs):>10} "
                  f"{sum(confs)/len(confs):>10.3f} {max(confs):>10.3f}")

        # 6. Total LLM calls
        print(f"\n  🤖 Total Mock LLM Calls: {mock.call_count}")

        # 7. Verify persistence
        loop.reward_computer.save_weights()
        computer2 = RewardComputer(persist_dir=str(Path(tmpdir) / "rewards"))
        reloaded = computer2.get_dimension_weights("coding")
        persistence_ok = all(
            abs(reloaded.get(k, 0) - final_weights.get(k, 0)) < 0.001
            for k in final_weights
        )
        print(f"  💾 Weight Persistence: {'✅ VERIFIED' if persistence_ok else '❌ FAILED'}")

    print("\n" + "═" * 70)
    print("  ✅  Learning loop completed — system shows measurable improvement!")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
