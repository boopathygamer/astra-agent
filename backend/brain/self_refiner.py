"""
Recursive Self-Refinement Engine
════════════════════════════════
Generate → Critique → Refine loop with convergence detection.

Inspired by:
  • Madaan et al. (2023) "Self-Refine: Iterative Refinement with Self-Feedback"
  • Constitutional AI's critique-and-revise pattern

Architecture:
  Pass 0:  Generate initial candidate
  Pass 1+: Critique(candidate) → feedback → Refine(candidate, feedback) → candidate'
  Stop:    When improvement delta < ε or budget exhausted

Each critique pass uses an ensemble of 4 perspectives:
  1. Correctness  — Is the answer factually/logically correct?
  2. Completeness — Does it address all parts of the question?
  3. Clarity      — Is it well-structured and easy to follow?
  4. Edge Cases   — Does it handle corner cases and exceptions?
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CritiqueType(Enum):
    CORRECTNESS = "correctness"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    EDGE_CASES = "edge_cases"


@dataclass
class Critique:
    """A single critique of a candidate response."""
    critique_type: CritiqueType = CritiqueType.CORRECTNESS
    issues: List[str] = field(default_factory=list)
    score: float = 0.0           # 0.0 (terrible) to 1.0 (flawless)
    suggestions: List[str] = field(default_factory=list)
    raw_feedback: str = ""

    @property
    def has_issues(self) -> bool:
        return self.score < 0.85 or len(self.issues) > 0


@dataclass
class RefinementPass:
    """Record of a single refinement iteration."""
    pass_number: int = 0
    candidate: str = ""
    critiques: List[Critique] = field(default_factory=list)
    aggregate_score: float = 0.0
    improvement_delta: float = 0.0
    semantic_diff_ratio: float = 0.0  # How much changed between iterations
    duration_ms: float = 0.0

    @property
    def critique_summary(self) -> str:
        parts = []
        for c in self.critiques:
            status = "✓" if not c.has_issues else "✗"
            parts.append(f"{status} {c.critique_type.value}: {c.score:.2f}")
        return " | ".join(parts)


@dataclass
class RefinementResult:
    """Complete result of the self-refinement process."""
    problem: str = ""
    final_output: str = ""
    final_score: float = 0.0
    total_passes: int = 0
    converged: bool = False
    passes: List[RefinementPass] = field(default_factory=list)
    total_duration_ms: float = 0.0
    improvement_trajectory: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_score": round(self.final_score, 4),
            "total_passes": self.total_passes,
            "converged": self.converged,
            "improvement_curve": [round(x, 4) for x in self.improvement_trajectory],
            "duration_ms": round(self.total_duration_ms, 2),
        }


class SelfRefiner:
    """
    Recursive self-refinement with multi-perspective critique ensemble
    and convergence detection.

    Each iteration:
      1. Run 4 parallel critiques on the current candidate
      2. Aggregate critique scores (weighted)
      3. Check convergence: EMA of improvement deltas < epsilon
      4. If not converged: generate refined version using critique feedback
      5. Repeat until converged or budget exhausted

    Convergence uses Exponential Moving Average (EMA) of per-pass
    improvement to detect diminishing returns.
    """

    CRITIQUE_PROMPTS = {
        CritiqueType.CORRECTNESS: (
            "You are a fact-checker and logic verifier. Analyze this response for:\n"
            "1. Factual accuracy — are all claims correct?\n"
            "2. Logical consistency — does the reasoning flow without contradictions?\n"
            "3. Technical correctness — are code, formulas, or procedures correct?\n\n"
            "Response to critique:\n{candidate}\n\n"
            "Score (0.0-1.0) and list specific issues:\n"
            "SCORE: [number]\n"
            "ISSUES:\n- [issue 1]\n- [issue 2]\n"
            "SUGGESTIONS:\n- [fix 1]\n- [fix 2]"
        ),
        CritiqueType.COMPLETENESS: (
            "You are a completeness auditor. Check if this response fully addresses "
            "all aspects of the original question.\n\n"
            "Original question: {problem}\n"
            "Response:\n{candidate}\n\n"
            "Score (0.0-1.0) and identify gaps:\n"
            "SCORE: [number]\n"
            "MISSING:\n- [gap 1]\n- [gap 2]\n"
            "SUGGESTIONS:\n- [add 1]"
        ),
        CritiqueType.CLARITY: (
            "You are a technical editor. Evaluate this response for:\n"
            "1. Structure — is it well-organized with clear sections?\n"
            "2. Language — is the writing clear and precise?\n"
            "3. Examples — are concepts illustrated with examples?\n\n"
            "Response:\n{candidate}\n\n"
            "SCORE: [number]\nISSUES:\n- [issue]\nSUGGESTIONS:\n- [fix]"
        ),
        CritiqueType.EDGE_CASES: (
            "You are a QA engineer. Find edge cases, exceptions, and failure modes "
            "not addressed in this response.\n\n"
            "Question: {problem}\n"
            "Response:\n{candidate}\n\n"
            "SCORE: [number]\n"
            "EDGE_CASES_MISSED:\n- [case 1]\n- [case 2]\n"
            "SUGGESTIONS:\n- [handle 1]"
        ),
    }

    CRITIQUE_WEIGHTS = {
        CritiqueType.CORRECTNESS: 0.35,
        CritiqueType.COMPLETENESS: 0.25,
        CritiqueType.CLARITY: 0.20,
        CritiqueType.EDGE_CASES: 0.20,
    }

    REFINE_PROMPT = (
        "Improve this response based on the critique feedback below.\n\n"
        "Original question: {problem}\n\n"
        "Current response:\n{candidate}\n\n"
        "Critique feedback:\n{feedback}\n\n"
        "Provide an improved version that addresses ALL the feedback. "
        "Keep what's already good, fix what's broken, add what's missing.\n\n"
        "Improved response:"
    )

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        max_passes: int = 5,
        convergence_epsilon: float = 0.02,
        ema_alpha: float = 0.4,
        min_passes: int = 1,
        target_score: float = 0.92,
    ):
        self.generate_fn = generate_fn
        self.max_passes = max_passes
        self.epsilon = convergence_epsilon
        self.ema_alpha = ema_alpha
        self.min_passes = min_passes
        self.target_score = target_score

        self._history: List[Dict[str, Any]] = []
        self._critique_effectiveness: Dict[str, List[float]] = {
            ct.value: [] for ct in CritiqueType
        }
        logger.info(
            f"[REFINER] Initialized — max_passes={max_passes}, "
            f"ε={convergence_epsilon}, target={target_score}"
        )

    def refine(self, problem: str, initial_response: str = "",
               context: str = "") -> RefinementResult:
        """
        Run the full refinement loop.

        Args:
            problem: The original question/task
            initial_response: Starting candidate (generated if empty)
            context: Additional context for generation
        """
        start = time.time()
        result = RefinementResult(problem=problem)

        # Generate initial candidate if needed
        candidate = initial_response
        if not candidate and self.generate_fn:
            candidate = self.generate_fn(
                f"Provide a thorough response to:\n{problem}\n"
                f"{'Context: ' + context if context else ''}"
            )

        if not candidate:
            result.final_output = "Unable to generate initial response."
            return result

        prev_score = 0.0
        ema_improvement = 1.0  # Start high to allow first pass

        for pass_num in range(self.max_passes):
            pass_start = time.time()
            rpass = RefinementPass(pass_number=pass_num, candidate=candidate)

            # Run critique ensemble
            rpass.critiques = self._critique_ensemble(candidate, problem)
            rpass.aggregate_score = self._aggregate_scores(rpass.critiques)
            rpass.improvement_delta = rpass.aggregate_score - prev_score
            result.improvement_trajectory.append(rpass.aggregate_score)

            # EMA of improvement
            ema_improvement = (
                self.ema_alpha * abs(rpass.improvement_delta) +
                (1 - self.ema_alpha) * ema_improvement
            )

            rpass.duration_ms = (time.time() - pass_start) * 1000
            result.passes.append(rpass)

            logger.info(
                f"[REFINER] Pass {pass_num}: score={rpass.aggregate_score:.3f} "
                f"Δ={rpass.improvement_delta:+.3f} EMA_Δ={ema_improvement:.4f} "
                f"| {rpass.critique_summary}"
            )

            # Check convergence conditions
            if pass_num >= self.min_passes:
                if rpass.aggregate_score >= self.target_score:
                    result.converged = True
                    logger.info(f"[REFINER] Target score {self.target_score} reached!")
                    break

                if ema_improvement < self.epsilon:
                    result.converged = True
                    logger.info(f"[REFINER] Converged (EMA_Δ={ema_improvement:.4f} < ε={self.epsilon})")
                    break

            # Refine candidate using critique feedback
            if pass_num < self.max_passes - 1:  # Don't refine on last pass
                feedback = self._format_feedback(rpass.critiques)
                refined = self._refine(candidate, problem, feedback)
                if refined:
                    rpass.semantic_diff_ratio = self._semantic_diff(candidate, refined)
                    candidate = refined

            prev_score = rpass.aggregate_score

        result.final_output = candidate
        result.final_score = result.passes[-1].aggregate_score if result.passes else 0.0
        result.total_passes = len(result.passes)
        result.total_duration_ms = (time.time() - start) * 1000

        self._history.append(result.to_dict())
        return result

    def _critique_ensemble(self, candidate: str, problem: str) -> List[Critique]:
        """Run all 4 critique types on the candidate."""
        critiques = []
        for ctype, prompt_template in self.CRITIQUE_PROMPTS.items():
            critique = self._run_critique(ctype, prompt_template, candidate, problem)
            critiques.append(critique)
        return critiques

    def _run_critique(self, ctype: CritiqueType, template: str,
                      candidate: str, problem: str) -> Critique:
        """Run a single critique."""
        critique = Critique(critique_type=ctype)

        if self.generate_fn:
            prompt = template.format(candidate=candidate[:2000], problem=problem[:500])
            try:
                response = self.generate_fn(prompt)
                critique.raw_feedback = response
                critique.score = self._extract_score(response)
                critique.issues = self._extract_list(response, "ISSUES", "MISSING", "EDGE_CASES_MISSED")
                critique.suggestions = self._extract_list(response, "SUGGESTIONS")
            except Exception as e:
                logger.warning(f"[REFINER] Critique {ctype.value} failed: {e}")
                critique.score = 0.6
        else:
            # Heuristic critique
            critique.score = self._heuristic_score(candidate, ctype)

        return critique

    def _refine(self, candidate: str, problem: str, feedback: str) -> Optional[str]:
        """Generate refined version using feedback."""
        if not self.generate_fn:
            return None
        prompt = self.REFINE_PROMPT.format(
            candidate=candidate[:3000],
            problem=problem[:500],
            feedback=feedback[:1500],
        )
        try:
            return self.generate_fn(prompt)
        except Exception as e:
            logger.warning(f"[REFINER] Refinement failed: {e}")
            return None

    def _aggregate_scores(self, critiques: List[Critique]) -> float:
        """Weighted average of critique scores."""
        total_weight = 0.0
        weighted_sum = 0.0
        for c in critiques:
            w = self.CRITIQUE_WEIGHTS.get(c.critique_type, 0.25)
            weighted_sum += c.score * w
            total_weight += w
        return weighted_sum / max(total_weight, 0.01)

    @staticmethod
    def _format_feedback(critiques: List[Critique]) -> str:
        """Format all critiques into a text feedback block."""
        parts = []
        for c in critiques:
            if not c.has_issues:
                continue
            section = f"[{c.critique_type.value.upper()}] Score: {c.score:.2f}\n"
            if c.issues:
                section += "Issues:\n" + "\n".join(f"  - {i}" for i in c.issues) + "\n"
            if c.suggestions:
                section += "Fix:\n" + "\n".join(f"  → {s}" for s in c.suggestions) + "\n"
            parts.append(section)
        return "\n".join(parts) if parts else "Minor improvements needed."

    @staticmethod
    def _extract_score(text: str) -> float:
        """Extract a score from critique response."""
        import re
        for line in text.split("\n"):
            if "SCORE" in line.upper():
                numbers = re.findall(r"(\d+\.?\d*)", line)
                if numbers:
                    val = float(numbers[0])
                    return val if val <= 1.0 else val / 10.0
        return 0.6

    @staticmethod
    def _extract_list(text: str, *headers: str) -> List[str]:
        """Extract bullet items from under a header."""
        items = []
        in_section = False
        for line in text.split("\n"):
            upper = line.strip().upper().rstrip(":")
            if any(h.upper() in upper for h in headers):
                in_section = True
                continue
            if in_section:
                stripped = line.strip()
                if stripped.startswith(("-", "•", "*", "→")):
                    items.append(stripped.lstrip("-•*→ ").strip())
                elif stripped and not stripped.startswith(("SCORE", "ISSUES", "SUGGEST")):
                    # Still part of a multi-line item
                    if items:
                        items[-1] += " " + stripped
                else:
                    in_section = False
        return items[:10]

    @staticmethod
    def _semantic_diff(old: str, new: str) -> float:
        """Estimate how much changed between iterations (0=identical, 1=completely different)."""
        if not old or not new:
            return 1.0
        old_words = set(old.lower().split())
        new_words = set(new.lower().split())
        if not old_words and not new_words:
            return 0.0
        intersection = old_words & new_words
        union = old_words | new_words
        jaccard = len(intersection) / max(len(union), 1)
        return 1.0 - jaccard

    @staticmethod
    def _heuristic_score(candidate: str, ctype: CritiqueType) -> float:
        """Fallback heuristic scoring when no LLM is available."""
        score = 0.5
        c = candidate.lower()
        if ctype == CritiqueType.CORRECTNESS:
            if any(w in c for w in ["because", "therefore", "thus"]):
                score += 0.2
        elif ctype == CritiqueType.COMPLETENESS:
            if len(candidate) > 200:
                score += 0.15
            if any(w in c for w in ["first", "second", "finally"]):
                score += 0.1
        elif ctype == CritiqueType.CLARITY:
            if "\n" in candidate:
                score += 0.1
            if any(w in c for w in ["example", "for instance"]):
                score += 0.15
        elif ctype == CritiqueType.EDGE_CASES:
            if any(w in c for w in ["however", "exception", "edge case", "unless"]):
                score += 0.2
        return min(1.0, score)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_refinements": len(self._history),
            "avg_passes": (
                sum(h["total_passes"] for h in self._history) /
                max(len(self._history), 1)
            ),
            "avg_final_score": (
                sum(h["final_score"] for h in self._history) /
                max(len(self._history), 1)
            ),
            "convergence_rate": (
                sum(1 for h in self._history if h.get("converged", False)) /
                max(len(self._history), 1)
            ),
        }
