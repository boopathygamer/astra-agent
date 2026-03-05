"""
Credit Assignment Engine — Step-Level Reward Attribution.
Inspired by Agent Lightning's TracerTraceToTriplet adapter pattern.

Decomposes trajectory-level rewards into per-step contributions using:
1. Temporal difference: reward change between consecutive steps
2. Counterfactual reasoning: "what if this step was removed?"
3. Attention-based: LLM judges which steps contributed most
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from brain.trace_store import TraceSpan, TrajectoryTrace, SpanType

logger = logging.getLogger(__name__)


@dataclass
class Triplet:
    """(State, Action, Reward) triplet — the fundamental learning unit.

    Directly mirrors Agent Lightning's core data structure from
    TracerTraceToTriplet adapter.
    """
    state: str = ""         # Problem + context at this step
    action: str = ""        # What the agent did/generated
    reward: float = 0.0     # Step-level attributed reward
    span_id: str = ""
    step_index: int = 0
    contribution: float = 0.0   # How much this step contributed


@dataclass
class StepCredit:
    """Credit assigned to a single step in the trajectory."""
    span_id: str
    step_index: int
    contribution_score: float = 0.0     # [-1, 1]: negative = harmful
    temporal_delta: float = 0.0         # Reward change from this step
    counterfactual_score: float = 0.0   # Impact if removed
    attention_score: float = 0.0        # LLM-judged importance
    was_helpful: bool = True


@dataclass
class CreditReport:
    """Full credit assignment report for a trajectory."""
    trace_id: str = ""
    credits: List[StepCredit] = field(default_factory=list)
    triplets: List[Triplet] = field(default_factory=list)
    total_reward: float = 0.0
    attribution_method: str = "hybrid"

    def get_helpful_steps(self) -> List[StepCredit]:
        return [c for c in self.credits if c.was_helpful]

    def get_harmful_steps(self) -> List[StepCredit]:
        return [c for c in self.credits if not c.was_helpful]

    def summary(self) -> str:
        helpful = len(self.get_helpful_steps())
        harmful = len(self.get_harmful_steps())
        return (
            f"CreditReport [{self.trace_id}]: "
            f"{len(self.credits)} steps, "
            f"{helpful} helpful, {harmful} harmful, "
            f"reward={self.total_reward:.3f}"
        )


class TripletAdapter:
    """Converts trajectory traces to (state, action, reward) triplets.

    Directly inspired by Agent Lightning's TracerTraceToTriplet.
    Processes ordered spans and creates learning-ready triplets.
    """

    def adapt(self, trace: TrajectoryTrace) -> List[Triplet]:
        """Convert a trajectory into triplets.

        Each span becomes a triplet with:
        - state = cumulative context up to this point
        - action = this span's output
        - reward = distributed trajectory reward (uniform initially)
        """
        if not trace.spans:
            return []

        triplets = []
        cumulative_context = f"Problem: {trace.problem[:300]}\n"

        # Base reward per step (uniform distribution)
        base_reward = trace.final_reward / max(len(trace.spans), 1)

        for i, span in enumerate(trace.spans):
            triplet = Triplet(
                state=cumulative_context[:500],
                action=span.output_data[:500],
                reward=base_reward,
                span_id=span.span_id,
                step_index=i,
            )
            triplets.append(triplet)

            # Build cumulative context for next step
            cumulative_context += (
                f"\nStep {i} [{span.span_type.value}]: "
                f"{span.output_data[:100]}"
            )

        return triplets


class CreditAssignmentEngine:
    """Full credit assignment using 3 methods + hybrid fusion.

    Goes beyond Agent Lightning's basic triplet extraction by adding
    counterfactual reasoning and attention-based scoring.
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self.adapter = TripletAdapter()

    def assign_credit(
        self,
        trace: TrajectoryTrace,
        use_counterfactual: bool = True,
        use_attention: bool = True,
    ) -> CreditReport:
        """Run full credit assignment on a trajectory.

        Args:
            trace: The complete trajectory to analyze
            use_counterfactual: Enable counterfactual reasoning
            use_attention: Enable LLM attention-based scoring

        Returns:
            CreditReport with per-step attributions
        """
        report = CreditReport(
            trace_id=trace.trace_id,
            total_reward=trace.final_reward,
        )

        if not trace.spans:
            return report

        # Step 1: Temporal difference credit
        td_scores = self._temporal_difference(trace)

        # Step 2: Counterfactual credit (optional)
        cf_scores = (
            self._counterfactual(trace)
            if use_counterfactual
            else [0.0] * len(trace.spans)
        )

        # Step 3: Attention-based credit (optional, requires LLM)
        attn_scores = (
            self._attention_based(trace)
            if use_attention and self.generate_fn
            else [0.0] * len(trace.spans)
        )

        # Fuse scores (weighted average)
        w_td, w_cf, w_attn = 0.4, 0.3, 0.3
        if not use_counterfactual:
            w_td, w_cf, w_attn = 0.6, 0.0, 0.4
        if not use_attention or not self.generate_fn:
            w_td, w_cf, w_attn = 0.7, 0.3, 0.0

        for i, span in enumerate(trace.spans):
            td = td_scores[i] if i < len(td_scores) else 0.0
            cf = cf_scores[i] if i < len(cf_scores) else 0.0
            attn = attn_scores[i] if i < len(attn_scores) else 0.0

            composite = w_td * td + w_cf * cf + w_attn * attn

            credit = StepCredit(
                span_id=span.span_id,
                step_index=i,
                contribution_score=composite,
                temporal_delta=td,
                counterfactual_score=cf,
                attention_score=attn,
                was_helpful=composite > 0,
            )
            report.credits.append(credit)

            # Update span with credit info
            span.was_helpful = credit.was_helpful
            span.reward = composite * trace.final_reward

        # Generate triplets with credit-adjusted rewards
        base_triplets = self.adapter.adapt(trace)
        for triplet, credit in zip(base_triplets, report.credits):
            triplet.reward = credit.contribution_score * trace.final_reward
            triplet.contribution = credit.contribution_score
        report.triplets = base_triplets

        logger.info(report.summary())
        return report

    def _temporal_difference(self, trace: TrajectoryTrace) -> List[float]:
        """Compute reward change between consecutive steps.

        Steps that improve confidence get positive credit.
        Steps that decrease confidence get negative credit.
        """
        scores = []

        for i, span in enumerate(trace.spans):
            if i == 0:
                # First step: credit based on initial output quality
                scores.append(0.1 if span.output_data else 0.0)
            else:
                # Compare verification improvement
                curr_attrs = span.attributes
                prev_attrs = trace.spans[i - 1].attributes

                curr_conf = float(curr_attrs.get("confidence", 0.5))
                prev_conf = float(prev_attrs.get("confidence", 0.5))

                delta = curr_conf - prev_conf
                # Normalize to [-1, 1]
                scores.append(max(-1.0, min(1.0, delta * 5)))

        return scores

    def _counterfactual(self, trace: TrajectoryTrace) -> List[float]:
        """Estimate impact of removing each step.

        Uses heuristics based on span type and position:
        - Verification spans: high impact (catch errors)
        - Early reasoning spans: high impact (set direction)
        - Late improvement spans: variable impact
        """
        n = len(trace.spans)
        scores = []

        for i, span in enumerate(trace.spans):
            position_weight = 1.0 - (i / max(n, 1)) * 0.3

            type_weights = {
                SpanType.VERIFICATION: 0.8,
                SpanType.REASONING: 0.7,
                SpanType.HYPOTHESIS: 0.6,
                SpanType.METACOGNITION: 0.5,
                SpanType.LLM_CALL: 0.4,
                SpanType.REWARD: 0.3,
                SpanType.CLASSIFICATION: 0.3,
                SpanType.RISK_ASSESSMENT: 0.6,
                SpanType.TOOL_CALL: 0.5,
            }
            type_weight = type_weights.get(span.span_type, 0.4)

            # Counterfactual score: how important was this step?
            cf = position_weight * type_weight
            scores.append(cf)

        return scores

    def _attention_based(self, trace: TrajectoryTrace) -> List[float]:
        """LLM-based importance scoring — which steps mattered most?

        Asks the LLM to rate each step's contribution to the final answer.
        Falls back to uniform if LLM unavailable.
        """
        if not self.generate_fn or len(trace.spans) == 0:
            return [1.0 / max(len(trace.spans), 1)] * len(trace.spans)

        # Build step summary for LLM
        step_descriptions = []
        for i, span in enumerate(trace.spans):
            desc = (
                f"Step {i} [{span.span_type.value}]: "
                f"{span.output_data[:100]}"
            )
            step_descriptions.append(desc)

        prompt = (
            "Given this problem-solving trajectory, rate each step's "
            "contribution to the final outcome on a scale of 0.0 to 1.0. "
            "Return ONLY a comma-separated list of numbers, one per step.\n\n"
            f"Problem: {trace.problem[:200]}\n"
            f"Final answer quality: {trace.final_reward:.2f}\n\n"
            "Steps:\n" + "\n".join(step_descriptions) + "\n\n"
            "Scores (comma-separated):"
        )

        try:
            response = self.generate_fn(prompt)
            # Parse comma-separated scores
            parts = response.strip().split(",")
            scores = []
            for p in parts:
                p = p.strip()
                try:
                    scores.append(max(0.0, min(1.0, float(p))))
                except ValueError:
                    scores.append(0.5)

            # Pad or truncate to match span count
            while len(scores) < len(trace.spans):
                scores.append(0.5)
            scores = scores[:len(trace.spans)]
            return scores

        except Exception as e:
            logger.warning(f"Attention-based credit failed: {e}")
            return [0.5] * len(trace.spans)
