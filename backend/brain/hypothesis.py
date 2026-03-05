"""
Multi-Hypothesis Thinking Engine
─────────────────────────────────
Section 4 of the architecture:

Maintain hypotheses {h_i} with weights p_i, Σ p_i = 1.
After evidence E (tests, counterexamples, tool outputs), update:
    p'_i ∝ p_i · exp(-β · Loss(h_i; E)),    Σ p'_i = 1

Generate candidate s from the mixture, not from a single guess.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.settings import brain_config

logger = logging.getLogger(__name__)


@dataclass
class Hypothesis:
    """A single hypothesis/approach for solving a task."""
    id: int = 0
    description: str = ""
    approach: str = ""        # Detailed approach description
    assumptions: list = field(default_factory=list)
    weight: float = 1.0       # p_i
    loss_history: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    score: float = 0.0        # Latest evaluation score

    def to_prompt(self) -> str:
        """Convert hypothesis to a prompt-friendly format."""
        parts = [f"Hypothesis {self.id}: {self.description}"]
        parts.append(f"  Approach: {self.approach}")
        if self.assumptions:
            parts.append(f"  Assumptions: {', '.join(self.assumptions)}")
        parts.append(f"  Weight: {self.weight:.3f}")
        if self.loss_history:
            parts.append(f"  Recent losses: {self.loss_history[-3:]}")
        return "\n".join(parts)


class HypothesisEngine:
    """
    Multi-Hypothesis Thinking — avoid getting stuck on one approach.

    Core algorithm:
    1. Generate multiple hypotheses for a problem
    2. Evaluate each against evidence
    3. Update weights using exponential loss: p'_i ∝ p_i · exp(-β·Loss)
    4. Synthesize best candidate from weighed mixture
    5. Repeat as new evidence arrives

    This prevents the system from tunnel-visioning on a single bad approach.
    """

    def __init__(self, config=None):
        self.config = config or brain_config
        self.hypotheses: List[Hypothesis] = []
        self.iteration = 0

    def generate_hypotheses(
        self,
        problem: str,
        generate_fn,
        n_hypotheses: Optional[int] = None,
        context: str = "",
    ) -> List[Hypothesis]:
        """
        Generate multiple hypotheses for a problem.

        Args:
            problem: Problem description
            generate_fn: Function(prompt) → text that calls the LLM
            n_hypotheses: Number of hypotheses to generate
            context: Additional context (from memory)

        Returns:
            List of generated hypotheses
        """
        n = n_hypotheses or self.config.max_hypotheses

        prompt = (
            "You are a multi-hypothesis reasoning engine. "
            f"Generate exactly {n} DIFFERENT approaches to solve this problem. "
            f"Each approach should use a fundamentally different strategy.\n\n"
            f"Problem: {problem}\n"
        )

        if context:
            prompt += f"\nRelevant context from past experience:\n{context}\n"

        prompt += (
            "\nFor each approach, provide:\n"
            "1. A short title\n"
            "2. The detailed approach\n"
            "3. Key assumptions\n"
            "4. Potential risks\n\n"
            "Format each as:\n"
            "HYPOTHESIS <N>:\n"
            "Title: ...\n"
            "Approach: ...\n"
            "Assumptions: ...\n"
            "Risks: ...\n"
        )

        response = generate_fn(prompt)
        self.hypotheses = self._parse_hypotheses(response, n)

        # Initialize uniform weights
        uniform_weight = 1.0 / max(len(self.hypotheses), 1)
        for h in self.hypotheses:
            h.weight = uniform_weight

        self.iteration = 0
        logger.info(f"Generated {len(self.hypotheses)} hypotheses")
        return self.hypotheses

    def update_weights(
        self,
        evidence: Dict[int, float],
        beta: Optional[float] = None,
    ) -> List[Hypothesis]:
        """
        Update hypothesis weights based on new evidence.

        Implements: p'_i ∝ p_i · exp(-β · Loss(h_i; E))

        Args:
            evidence: Dict mapping hypothesis_id → loss value (lower = better)
            beta: Temperature parameter (higher = more aggressive updates)

        Returns:
            Updated hypotheses
        """
        beta = beta or self.config.hypothesis_temperature
        min_weight = self.config.min_hypothesis_weight

        # Update weights
        for h in self.hypotheses:
            if h.id in evidence:
                loss = evidence[h.id]
                h.loss_history.append(loss)
                h.weight *= math.exp(-beta * loss)

        # Normalize weights (Σ p'_i = 1)
        total_weight = sum(h.weight for h in self.hypotheses)
        if total_weight > 0:
            for h in self.hypotheses:
                h.weight = max(h.weight / total_weight, min_weight)

            # Re-normalize after applying minimum
            total_weight = sum(h.weight for h in self.hypotheses)
            for h in self.hypotheses:
                h.weight /= total_weight

        self.iteration += 1

        # Log weight distribution
        weight_dist = {h.id: f"{h.weight:.3f}" for h in self.hypotheses}
        logger.info(f"Iteration {self.iteration}: weights = {weight_dist}")

        return self.hypotheses

    def synthesize_candidate(
        self,
        synthesize_fn,
        problem: str,
    ) -> str:
        """
        Synthesize the best candidate from the weighted hypothesis mixture.

        Instead of picking the single best hypothesis, we present all
        hypotheses with their weights to the LLM and ask it to synthesize
        the optimal approach combining the strongest elements.

        Args:
            synthesize_fn: Function(prompt) → text that calls the LLM
            problem: Original problem description

        Returns:
            Synthesized candidate solution
        """
        # Sort by weight descending
        sorted_h = sorted(self.hypotheses, key=lambda h: h.weight, reverse=True)

        prompt = (
            f"You are synthesizing the best solution from multiple hypotheses.\n\n"
            f"Problem: {problem}\n\n"
            f"Hypotheses (ranked by confidence weight):\n"
        )

        for h in sorted_h:
            prompt += f"\n{h.to_prompt()}\n"

        prompt += (
            "\n\nBased on the weights and evidence, synthesize the BEST approach. "
            "Draw heavily from the highest-weighted hypotheses, but incorporate "
            "useful elements from others. Be specific and actionable.\n\n"
            "SYNTHESIZED SOLUTION:\n"
        )

        candidate = synthesize_fn(prompt)
        return candidate

    def get_best_hypothesis(self) -> Optional[Hypothesis]:
        """Return the highest-weighted hypothesis."""
        if not self.hypotheses:
            return None
        return max(self.hypotheses, key=lambda h: h.weight)

    def prune_weak(self, threshold: Optional[float] = None):
        """Remove hypotheses below the minimum weight threshold."""
        threshold = threshold or self.config.min_hypothesis_weight * 2
        before = len(self.hypotheses)
        self.hypotheses = [h for h in self.hypotheses if h.weight >= threshold]

        # Re-normalize
        total = sum(h.weight for h in self.hypotheses)
        if total > 0:
            for h in self.hypotheses:
                h.weight /= total

        pruned = before - len(self.hypotheses)
        if pruned > 0:
            logger.info(f"Pruned {pruned} weak hypotheses")

    def _parse_hypotheses(self, text: str, expected: int) -> List[Hypothesis]:
        """Parse LLM output into structured hypotheses."""
        hypotheses = []
        current = None

        for line in text.split("\n"):
            line = line.strip()
            upper = line.upper()

            if upper.startswith("HYPOTHESIS") and ":" in line:
                if current is not None:
                    hypotheses.append(current)
                idx = len(hypotheses)
                current = Hypothesis(id=idx)

            elif current is not None:
                if upper.startswith("TITLE:"):
                    current.description = line.split(":", 1)[1].strip()
                elif upper.startswith("APPROACH:"):
                    current.approach = line.split(":", 1)[1].strip()
                elif upper.startswith("ASSUMPTIONS:"):
                    assumptions_text = line.split(":", 1)[1].strip()
                    current.assumptions = [
                        a.strip() for a in assumptions_text.split(",") if a.strip()
                    ]
                elif upper.startswith("RISKS:"):
                    # Store risks as additional evidence
                    pass
                elif current.approach and line:
                    # Continuation of approach
                    current.approach += " " + line

        if current is not None:
            hypotheses.append(current)

        # If parsing failed, create single default hypothesis
        if not hypotheses:
            hypotheses = [Hypothesis(
                id=0,
                description="Direct approach",
                approach=text[:500],
            )]

        return hypotheses[:expected]

    def get_summary(self) -> str:
        """Get a human-readable summary of current hypothesis state."""
        lines = [f"Hypothesis Engine — Iteration {self.iteration}"]
        for h in sorted(self.hypotheses, key=lambda h: h.weight, reverse=True):
            lines.append(
                f"  [{h.id}] w={h.weight:.3f} | {h.description[:60]}"
            )
        return "\n".join(lines)
