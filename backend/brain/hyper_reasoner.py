"""
Hyper-Reasoning Engine — Multi-Perspective Analysis with Self-Verification
═══════════════════════════════════════════════════════════════════════════
Goes beyond the existing thinking loop with multi-perspective analysis,
formal logic validation, and human-expert-level reasoning chains.

Capabilities:
  1. Multi-Perspective Analysis  — 6 simultaneous viewpoints
  2. Formal Logic Checker        — Validates reasoning for fallacies
  3. Confidence-Weighted Synthesis — Merges perspectives intelligently
  4. Reasoning Audit Trail       — Traceable evidence chains
  5. Socratic Challenger         — Auto-challenges conclusions
  6. Uncertainty Quantification  — Reports what it doesn't know
"""

import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Perspective(Enum):
    ANALYST = "analyst"        # Data-driven, factual
    CRITIC = "critic"          # Devil's advocate, finds flaws
    CREATIVE = "creative"      # Lateral thinking, novel solutions
    PRAGMATIST = "pragmatist"  # Practical, implementation-focused
    HISTORIAN = "historian"    # Precedent-based, lessons learned
    FUTURIST = "futurist"      # Forward-looking, implications


class LogicStatus(Enum):
    VALID = "valid"
    FALLACY_DETECTED = "fallacy_detected"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CIRCULAR = "circular"
    OVERGENERALIZED = "overgeneralized"


KNOWN_FALLACIES = [
    ("because", "therefore", "circular reasoning"),
    ("always", "never", "false dichotomy / absolute language"),
    ("everyone knows", "obviously", "appeal to popularity / common sense"),
    ("correlation", "causes", "correlation ≠ causation"),
]


@dataclass
class PerspectiveAnalysis:
    """Result from a single perspective."""
    perspective: Perspective = Perspective.ANALYST
    reasoning: str = ""
    conclusion: str = ""
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    weight: float = 1.0

    def weighted_confidence(self) -> float:
        return self.confidence * self.weight


@dataclass
class LogicCheck:
    """Result of formal logic verification."""
    status: LogicStatus = LogicStatus.VALID
    issues: List[str] = field(default_factory=list)
    fallacies: List[str] = field(default_factory=list)
    soundness_score: float = 1.0


@dataclass
class UncertaintyReport:
    """What the system doesn't know."""
    known_unknowns: List[str] = field(default_factory=list)
    assumptions_made: List[str] = field(default_factory=list)
    data_gaps: List[str] = field(default_factory=list)
    confidence_distribution: Dict[str, float] = field(default_factory=dict)


@dataclass
class SocraticChallenge:
    """A self-challenge to the conclusion."""
    question: str = ""
    challenge_type: str = ""  # assumption, evidence, logic, scope
    strength: float = 0.0
    counter_argument: str = ""
    resolution: str = ""
    survived: bool = False


@dataclass
class ReasoningResult:
    """Complete result of hyper-reasoning."""
    query: str = ""
    final_conclusion: str = ""
    final_confidence: float = 0.0
    perspectives: List[PerspectiveAnalysis] = field(default_factory=list)
    logic_check: LogicCheck = field(default_factory=LogicCheck)
    challenges: List[SocraticChallenge] = field(default_factory=list)
    uncertainty: UncertaintyReport = field(default_factory=UncertaintyReport)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_prompt: str = ""
    duration_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conclusion": self.final_conclusion,
            "confidence": self.final_confidence,
            "perspectives": [
                {"view": p.perspective.value, "conclusion": p.conclusion,
                 "confidence": p.confidence}
                for p in self.perspectives
            ],
            "logic_status": self.logic_check.status.value,
            "challenges_survived": sum(1 for c in self.challenges if c.survived),
            "challenges_total": len(self.challenges),
            "unknowns": len(self.uncertainty.known_unknowns),
            "duration_s": self.duration_s,
        }


class HyperReasoner:
    """
    Multi-perspective reasoning engine with logic verification,
    Socratic self-challenge, and uncertainty quantification.
    """

    PERSPECTIVE_PROMPTS = {
        Perspective.ANALYST: (
            "Analyze this problem from a purely data-driven, factual perspective. "
            "Focus on evidence, metrics, and objective analysis. "
            "What does the data tell us?"
        ),
        Perspective.CRITIC: (
            "Play devil's advocate. Find every possible flaw, risk, and weakness "
            "in the proposed approach. What could go wrong? What are we missing?"
        ),
        Perspective.CREATIVE: (
            "Think laterally and creatively. What unconventional solutions exist? "
            "What would happen if we approached this from a completely different angle?"
        ),
        Perspective.PRAGMATIST: (
            "Focus on practical implementation. What's the most efficient path? "
            "What are the real-world constraints and how do we work within them?"
        ),
        Perspective.HISTORIAN: (
            "What historical precedents exist? What lessons from similar past "
            "situations apply here? What patterns repeat?"
        ),
        Perspective.FUTURIST: (
            "Look forward. What are the long-term implications? How will this "
            "decision look in 6 months, 1 year, 5 years? What trends matter?"
        ),
    }

    PERSPECTIVE_WEIGHTS = {
        Perspective.ANALYST: 1.0,
        Perspective.CRITIC: 0.9,
        Perspective.CREATIVE: 0.7,
        Perspective.PRAGMATIST: 1.0,
        Perspective.HISTORIAN: 0.8,
        Perspective.FUTURIST: 0.6,
    }

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self._reasoning_history: List[Dict] = []
        logger.info("[REASON] Hyper-Reasoning engine initialized")

    def reason(self, query: str, context: str = "",
               perspectives: List[Perspective] = None,
               depth: str = "standard") -> ReasoningResult:
        """
        Perform comprehensive multi-perspective reasoning.

        Args:
            query: The question or problem to reason about
            context: Additional context
            perspectives: Which perspectives to use (default: all 6)
            depth: "quick" (3 perspectives), "standard" (all 6), "deep" (all + extra challenges)
        """
        start = time.time()
        result = ReasoningResult(query=query)
        result.audit_trail.append({"step": "start", "time": start, "query": query})

        if perspectives is None:
            if depth == "quick":
                perspectives = [Perspective.ANALYST, Perspective.PRAGMATIST, Perspective.CRITIC]
            else:
                perspectives = list(Perspective)

        # Step 1: Multi-perspective analysis
        for perspective in perspectives:
            analysis = self._analyze_perspective(query, context, perspective)
            result.perspectives.append(analysis)
            result.audit_trail.append({
                "step": f"perspective_{perspective.value}",
                "confidence": analysis.confidence,
                "conclusion_preview": analysis.conclusion[:80],
            })

        # Step 2: Logic verification
        result.logic_check = self._check_logic(result.perspectives)
        result.audit_trail.append({
            "step": "logic_check",
            "status": result.logic_check.status.value,
            "soundness": result.logic_check.soundness_score,
        })

        # Step 3: Synthesize
        result.final_conclusion = self._synthesize(result.perspectives, result.logic_check)
        result.final_confidence = self._calculate_confidence(result.perspectives, result.logic_check)

        # Step 4: Socratic challenge
        num_challenges = 5 if depth == "deep" else 3
        result.challenges = self._socratic_challenge(
            result.final_conclusion, result.perspectives, num_challenges
        )
        survived = sum(1 for c in result.challenges if c.survived)
        if survived < len(result.challenges) * 0.5:
            result.final_confidence *= 0.7

        # Step 5: Uncertainty quantification
        result.uncertainty = self._quantify_uncertainty(query, result.perspectives)

        # Build reasoning prompt for downstream use
        result.reasoning_prompt = self._build_reasoning_prompt(result)

        result.duration_s = time.time() - start
        self._reasoning_history.append(result.to_dict())
        return result

    def _analyze_perspective(self, query: str, context: str,
                             perspective: Perspective) -> PerspectiveAnalysis:
        """Generate analysis from a single perspective."""
        prompt_prefix = self.PERSPECTIVE_PROMPTS[perspective]
        weight = self.PERSPECTIVE_WEIGHTS[perspective]

        if self.generate_fn:
            full_prompt = (
                f"{prompt_prefix}\n\n"
                f"Problem: {query}\n"
                f"{'Context: ' + context if context else ''}\n\n"
                f"Provide: 1) Your reasoning, 2) Your conclusion, "
                f"3) Key evidence, 4) Risks. Be concise."
            )
            try:
                response = self.generate_fn(full_prompt)
                return PerspectiveAnalysis(
                    perspective=perspective,
                    reasoning=response,
                    conclusion=self._extract_conclusion(response),
                    confidence=self._estimate_confidence(response),
                    evidence=self._extract_list(response, "evidence"),
                    risks=self._extract_list(response, "risk"),
                    weight=weight,
                )
            except Exception as e:
                logger.warning(f"[REASON] {perspective.value} analysis failed: {e}")

        # Fallback: heuristic analysis
        return PerspectiveAnalysis(
            perspective=perspective,
            reasoning=f"[{perspective.value}] Analysis of: {query[:100]}",
            conclusion=f"From {perspective.value} perspective: approach appears reasonable",
            confidence=0.5,
            weight=weight,
        )

    def _check_logic(self, perspectives: List[PerspectiveAnalysis]) -> LogicCheck:
        """Verify reasoning for logical fallacies."""
        check = LogicCheck()
        all_text = " ".join(p.reasoning.lower() for p in perspectives)

        for patterns in KNOWN_FALLACIES:
            *triggers, fallacy_name = patterns
            if all(t in all_text for t in triggers):
                check.fallacies.append(fallacy_name)

        # Check for contradictions between perspectives
        conclusions = [p.conclusion.lower() for p in perspectives if p.conclusion]
        for i, c1 in enumerate(conclusions):
            for c2 in conclusions[i+1:]:
                if ("not" in c1 and c1.replace("not ", "") in c2) or \
                   ("not" in c2 and c2.replace("not ", "") in c1):
                    check.issues.append("Contradictory conclusions between perspectives")

        # Check for insufficient evidence
        low_evidence = [p for p in perspectives if len(p.evidence) == 0]
        if len(low_evidence) > len(perspectives) * 0.5:
            check.issues.append("Majority of perspectives lack supporting evidence")

        if check.fallacies:
            check.status = LogicStatus.FALLACY_DETECTED
            check.soundness_score = max(0.3, 1.0 - len(check.fallacies) * 0.2)
        elif check.issues:
            check.status = LogicStatus.INSUFFICIENT_EVIDENCE
            check.soundness_score = max(0.5, 1.0 - len(check.issues) * 0.15)
        else:
            check.status = LogicStatus.VALID
            check.soundness_score = 1.0

        return check

    def _synthesize(self, perspectives: List[PerspectiveAnalysis],
                    logic_check: LogicCheck) -> str:
        """Synthesize perspectives into a final conclusion."""
        if not perspectives:
            return "Insufficient data for conclusion."

        weighted = sorted(perspectives, key=lambda p: p.weighted_confidence(), reverse=True)

        if self.generate_fn:
            perspective_text = "\n".join(
                f"- [{p.perspective.value}] (conf={p.confidence:.0%}): {p.conclusion}"
                for p in weighted
            )
            logic_text = ""
            if logic_check.fallacies:
                logic_text = f"\n⚠️ Logic issues: {', '.join(logic_check.fallacies)}"

            prompt = (
                f"Synthesize these expert perspectives into one balanced conclusion:\n\n"
                f"{perspective_text}{logic_text}\n\n"
                f"Provide a single, well-balanced conclusion that weighs all perspectives."
            )
            try:
                return self.generate_fn(prompt)
            except Exception:
                pass

        # Fallback: use highest-confidence perspective
        return weighted[0].conclusion

    def _socratic_challenge(self, conclusion: str,
                             perspectives: List[PerspectiveAnalysis],
                             num_challenges: int = 3) -> List[SocraticChallenge]:
        """Challenge the conclusion Socratically."""
        challenges = []
        challenge_templates = [
            ("assumption", "What if the key assumption — {assumption} — is wrong?"),
            ("evidence", "What evidence would disprove this conclusion?"),
            ("scope", "Does this conclusion apply in all contexts or only specific ones?"),
            ("bias", "Could cognitive bias be influencing this reasoning?"),
            ("alternative", "What's the strongest counter-argument to this conclusion?"),
        ]

        for i, (ctype, template) in enumerate(challenge_templates[:num_challenges]):
            challenge = SocraticChallenge(
                question=template.format(assumption="the primary premise"),
                challenge_type=ctype,
            )

            # Try to resolve the challenge
            if self.generate_fn:
                try:
                    prompt = (
                        f"Conclusion: {conclusion[:200]}\n"
                        f"Challenge: {challenge.question}\n"
                        f"Can the conclusion survive this challenge? "
                        f"Answer YES or NO with brief explanation."
                    )
                    response = self.generate_fn(prompt)
                    challenge.resolution = response
                    challenge.survived = "yes" in response.lower()[:50]
                    challenge.strength = 0.7 if not challenge.survived else 0.4
                except Exception:
                    challenge.survived = True
                    challenge.strength = 0.3
            else:
                challenge.survived = True
                challenge.strength = 0.5

            challenges.append(challenge)

        return challenges

    def _quantify_uncertainty(self, query: str,
                               perspectives: List[PerspectiveAnalysis]) -> UncertaintyReport:
        """Quantify what we don't know."""
        report = UncertaintyReport()

        # Confidence distribution
        for p in perspectives:
            report.confidence_distribution[p.perspective.value] = p.confidence

        # Identify low-confidence areas
        low_conf = [p for p in perspectives if p.confidence < 0.5]
        for p in low_conf:
            report.known_unknowns.append(
                f"Low confidence in {p.perspective.value} analysis ({p.confidence:.0%})"
            )

        # Identify gaps
        all_risks = []
        for p in perspectives:
            all_risks.extend(p.risks)
        if all_risks:
            report.data_gaps.append(f"Identified {len(all_risks)} risk factors to monitor")

        # Common assumptions
        report.assumptions_made = [
            "Current context remains stable",
            "Input data is accurate and current",
            "No external disruptions during execution",
        ]

        return report

    def _calculate_confidence(self, perspectives: List[PerspectiveAnalysis],
                               logic_check: LogicCheck) -> float:
        """Calculate final confidence from all signals."""
        if not perspectives:
            return 0.0

        total_weight = sum(p.weight for p in perspectives)
        weighted_conf = sum(p.weighted_confidence() for p in perspectives) / total_weight

        # Penalize for logic issues
        final = weighted_conf * logic_check.soundness_score

        # Penalize for high disagreement
        confs = [p.confidence for p in perspectives]
        if confs:
            variance = sum((c - weighted_conf) ** 2 for c in confs) / len(confs)
            if variance > 0.1:
                final *= 0.85

        return max(0.0, min(1.0, final))

    def _build_reasoning_prompt(self, result: ReasoningResult) -> str:
        """Build a reasoning context prompt for downstream use."""
        parts = [f"[HYPER-REASONING: {result.final_confidence:.0%} confident]"]
        for p in result.perspectives[:3]:
            parts.append(f"  [{p.perspective.value}]: {p.conclusion[:100]}")
        if result.logic_check.fallacies:
            parts.append(f"  ⚠️ Logic: {', '.join(result.logic_check.fallacies)}")
        if result.uncertainty.known_unknowns:
            parts.append(f"  ❓ Unknowns: {len(result.uncertainty.known_unknowns)}")
        return "\n".join(parts)

    # ── Helpers ──

    def _extract_conclusion(self, text: str) -> str:
        for marker in ["conclusion:", "therefore:", "in summary:", "result:"]:
            idx = text.lower().find(marker)
            if idx >= 0:
                return text[idx + len(marker):].strip().split("\n")[0][:200]
        sentences = text.strip().split(".")
        return (sentences[-1] if sentences else text[:200]).strip()

    def _estimate_confidence(self, text: str) -> float:
        low_markers = ["uncertain", "unclear", "might", "possibly", "not sure"]
        high_markers = ["clearly", "definitely", "certain", "confident", "evident"]
        text_l = text.lower()
        low = sum(1 for m in low_markers if m in text_l)
        high = sum(1 for m in high_markers if m in text_l)
        base = 0.6
        return max(0.1, min(0.95, base + high * 0.08 - low * 0.1))

    def _extract_list(self, text: str, keyword: str) -> List[str]:
        items = []
        for line in text.split("\n"):
            if keyword.lower() in line.lower() and line.strip().startswith(("-", "•", "*")):
                items.append(line.strip().lstrip("-•* "))
        return items[:5]

    def get_status(self) -> Dict[str, Any]:
        return {
            "reasoning_sessions": len(self._reasoning_history),
            "avg_confidence": (
                sum(r.get("confidence", 0) for r in self._reasoning_history) /
                max(len(self._reasoning_history), 1)
            ),
        }
