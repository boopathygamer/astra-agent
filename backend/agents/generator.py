"""
Candidate Generator — Module 2 of the 5-module blueprint.
───────────────────────────────────────────────────────────
Generator: propose {h_i} and candidate s.

Combines hypothesis generation with candidate synthesis.
Wraps the brain's HypothesisEngine for the agent layer.
"""

import logging
from typing import Callable, Optional

from brain.hypothesis import HypothesisEngine
from agents.compiler import TaskSpec

logger = logging.getLogger(__name__)


class CandidateGenerator:
    """
    Module 2 — Generator: Propose hypotheses and synthesize candidates.

    Uses the brain's Multi-Hypothesis Engine to:
    1. Generate multiple solution approaches
    2. Weight them based on evidence
    3. Synthesize the best candidate from the mixture
    """

    def __init__(
        self,
        generate_fn: Callable,
        hypothesis_engine: Optional[HypothesisEngine] = None,
    ):
        self.generate_fn = generate_fn
        self.hypothesis_engine = hypothesis_engine or HypothesisEngine()

    def generate(
        self,
        task_spec: TaskSpec,
        memory_context: str = "",
        n_approaches: int = 3,
    ) -> str:
        """
        Generate the best candidate solution.

        Args:
            task_spec: Compiled task specification
            memory_context: Context from memory (past failures/successes)
            n_approaches: Number of hypotheses to generate

        Returns:
            Synthesized candidate solution
        """
        # Build problem description from task spec
        problem = task_spec.to_prompt()
        if memory_context:
            problem += f"\n\nPAST EXPERIENCE:\n{memory_context}"

        # Generate hypotheses
        self.hypothesis_engine.generate_hypotheses(
            problem=problem,
            generate_fn=self.generate_fn,
            n_hypotheses=n_approaches,
            context=memory_context,
        )

        # Synthesize best candidate
        candidate = self.hypothesis_engine.synthesize_candidate(
            synthesize_fn=self.generate_fn,
            problem=task_spec.raw_task,
        )

        return candidate

    def refine(
        self,
        evidence: dict,
        task_spec: TaskSpec,
    ) -> str:
        """
        Refine the candidate based on new evidence.

        Args:
            evidence: Dict mapping hypothesis_id → loss
            task_spec: Original task specification

        Returns:
            Improved candidate
        """
        # Update weights
        self.hypothesis_engine.update_weights(evidence)
        self.hypothesis_engine.prune_weak()

        # Re-synthesize
        candidate = self.hypothesis_engine.synthesize_candidate(
            synthesize_fn=self.generate_fn,
            problem=task_spec.raw_task,
        )

        return candidate
