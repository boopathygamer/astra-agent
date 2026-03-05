"""
Example: Math/Logic Reasoning with Full Trace Output.
═══════════════════════════════════════════════════════

Demonstrates the full thinking loop solving a math problem with:
- Problem classification
- 5-mode reasoning
- Multi-hypothesis generation + Bayesian updates
- 6-layer verification
- Risk assessment
- Post-solve learning

No API keys needed — uses deterministic MockLLM.

Usage:
    python examples/example_math_reasoning.py
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
from brain.problem_classifier import ProblemClassifier
from brain.trace_store import LearningStore
from brain.reward_model import RewardComputer
from brain.credit_assignment import CreditAssignmentEngine
from brain.prompt_evolver import PromptEvolver
from brain.expert_reflection import ExpertReflectionEngine


def main():
    print("\n" + "═" * 70)
    print("  🧠  Super-System Brain — Math Reasoning Example")
    print("═" * 70)

    # Initialize with deterministic mock
    mock = MockLLM(quality="high", seed=42)

    with tempfile.TemporaryDirectory() as tmpdir:
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

        problem = (
            "Calculate the sum of all prime numbers less than 100. "
            "Show the approach step by step."
        )

        print(f"\n📋 Problem: {problem}")
        print("─" * 70)
        print("⏳ Running thinking loop...\n")

        result = loop.think(
            problem=problem,
            action_type="math",
            max_iterations=3,
        )

        # Display results
        print("─" * 70)
        print("📊 THINKING TRACE:")
        print("─" * 70)
        print(result.summary())

        print("\n─" * 70)
        print("📝 FINAL ANSWER:")
        print("─" * 70)
        # Trim the mermaid diagram for display
        answer = result.final_answer
        if "### Universal Goal Tree" in answer:
            answer = answer[:answer.index("### Universal Goal Tree")]
        print(answer[:800])

        print("\n─" * 70)
        print("📈 METRICS:")
        print("─" * 70)
        print(f"  Domain:        {result.domain}")
        print(f"  Iterations:    {result.iterations}")
        print(f"  Confidence:    {result.final_confidence:.4f}")
        print(f"  Mode:          {result.mode.value}")
        print(f"  Strategies:    {result.strategies_used}")
        print(f"  Duration:      {result.total_duration_ms:.0f}ms")
        print(f"  LLM calls:     {mock.call_count}")
        print()

        # Show learning store stats
        stats = loop.learning_store.get_stats()
        print("📚 LEARNING STORE:")
        print(f"  Total traces:  {stats.get('total_traces', 0)}")
        print(f"  Success rate:  {stats.get('success_rate', 0):.0%}")
        print(f"  Avg reward:    {stats.get('avg_reward', 0):.3f}")

    print("\n" + "═" * 70)
    print("  ✅  Example completed successfully!")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    main()
