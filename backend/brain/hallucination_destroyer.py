"""
Hallucination Destroyer — 5-Layer Verification + Fact Anchoring + Confidence Calibration
═══════════════════════════════════════════════════════════════════════════════════════════
Ensures every output is grounded in verifiable logic chains.
Detects internal contradictions, unsubstantiated claims, and over-confidence.

No LLM, no GPU — pure rule-based verification and formal consistency checking.

Verification Stack:
  Layer 1: Syntactic     — well-formed output, no truncation, valid structure
  Layer 2: Semantic      — internal consistency, no self-contradiction
  Layer 3: Logical       — derivation chain validity, no logical fallacies
  Layer 4: Cross-ref     — claims anchored to known facts or derivations
  Layer 5: Calibration   — confidence matches evidence strength

Output: HallucinationScore ∈ [0.0, 1.0]
  0.0 = fully grounded   |   1.0 = pure hallucination
"""

import hashlib
import logging
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════

class VerificationLayer(IntEnum):
    SYNTACTIC = 1
    SEMANTIC = 2
    LOGICAL = 3
    CROSS_REFERENCE = 4
    CALIBRATION = 5


class HallucinationType(Enum):
    CONTRADICTION = "internal_contradiction"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    LOGICAL_FALLACY = "logical_fallacy"
    FABRICATED_FACT = "fabricated_fact"
    OVERCONFIDENCE = "overconfidence"
    STRUCTURAL = "structural_defect"
    NUMERICAL_ERROR = "numerical_error"


@dataclass
class VerificationViolation:
    """A single detected violation."""
    layer: VerificationLayer
    violation_type: HallucinationType
    description: str
    severity: float  # 0-1
    location: str = ""  # sentence or segment where found
    suggestion: str = ""

    def __str__(self) -> str:
        return f"[L{self.layer.value}:{self.violation_type.value}] {self.description} (sev: {self.severity:.0%})"


@dataclass
class AnchorPoint:
    """A fact anchor — a known-true statement used to ground claims."""
    statement: str
    source: str  # "mathematical_identity", "logical_tautology", etc.
    confidence: float = 1.0


@dataclass
class VerificationResult:
    """Result of the full hallucination verification pipeline."""
    hallucination_score: float = 0.0          # 0 = grounded, 1 = hallucinated
    grounding_score: float = 1.0              # inverse of hallucination
    violations: List[VerificationViolation] = field(default_factory=list)
    layer_scores: Dict[str, float] = field(default_factory=dict)
    anchored_claims: int = 0
    unanchored_claims: int = 0
    total_claims: int = 0
    confidence_calibration: float = 1.0       # how well-calibrated confidence is
    is_clean: bool = True                     # no violations found
    corrected_response: str = ""
    duration_ms: float = 0.0

    def summary(self) -> str:
        status = "✅ GROUNDED" if self.is_clean else "⚠️ VIOLATIONS FOUND"
        lines = [
            f"## Hallucination Destroyer Report",
            f"**Status**: {status}",
            f"**Hallucination Score**: {self.hallucination_score:.2f} / 1.00",
            f"**Grounding Score**: {self.grounding_score:.0%}",
            f"**Claims**: {self.anchored_claims}/{self.total_claims} anchored",
        ]
        if self.layer_scores:
            lines.append("\n### Layer Scores:")
            for layer_name, score in sorted(self.layer_scores.items()):
                icon = "✅" if score >= 0.8 else "⚠️" if score >= 0.5 else "❌"
                lines.append(f"  {icon} {layer_name}: {score:.0%}")
        if self.violations:
            lines.append(f"\n### Violations ({len(self.violations)}):")
            for v in self.violations[:10]:
                lines.append(f"  - {v}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# LAYER 1: SYNTACTIC CHECKER
# ═══════════════════════════════════════════════════════════

class SyntacticChecker:
    """Checks structural well-formedness of output."""

    @staticmethod
    def check(response: str) -> Tuple[float, List[VerificationViolation]]:
        violations = []
        score = 1.0

        # Empty or near-empty
        stripped = response.strip()
        if len(stripped) < 5:
            violations.append(VerificationViolation(
                VerificationLayer.SYNTACTIC, HallucinationType.STRUCTURAL,
                "Response is empty or trivially short", 0.9,
            ))
            return 0.0, violations

        # Truncation detection (ends mid-sentence without punctuation)
        if stripped and stripped[-1] not in '.!?"\':)]}…' and len(stripped) > 50:
            violations.append(VerificationViolation(
                VerificationLayer.SYNTACTIC, HallucinationType.STRUCTURAL,
                "Response appears truncated (no terminal punctuation)", 0.3,
                suggestion="Complete the final sentence",
            ))
            score -= 0.15

        # Unmatched brackets/parens
        bracket_pairs = [('(', ')'), ('[', ']'), ('{', '}')]
        for open_b, close_b in bracket_pairs:
            if stripped.count(open_b) != stripped.count(close_b):
                violations.append(VerificationViolation(
                    VerificationLayer.SYNTACTIC, HallucinationType.STRUCTURAL,
                    f"Unmatched bracket pair: '{open_b}' / '{close_b}'", 0.2,
                ))
                score -= 0.1

        # Unmatched code blocks
        if stripped.count('```') % 2 != 0:
            violations.append(VerificationViolation(
                VerificationLayer.SYNTACTIC, HallucinationType.STRUCTURAL,
                "Unmatched code block (odd number of ```).", 0.3,
            ))
            score -= 0.15

        # Excessive repetition (same sentence repeated)
        sentences = [s.strip() for s in re.split(r'[.!?]', stripped) if len(s.strip()) > 10]
        if sentences:
            seen = defaultdict(int)
            for s in sentences:
                seen[s.lower()] += 1
            repeats = sum(1 for cnt in seen.values() if cnt > 2)
            if repeats > 0:
                violations.append(VerificationViolation(
                    VerificationLayer.SYNTACTIC, HallucinationType.STRUCTURAL,
                    f"Excessive repetition: {repeats} sentence(s) repeated 3+ times", 0.5,
                ))
                score -= 0.25

        return max(0.0, score), violations


# ═══════════════════════════════════════════════════════════
# LAYER 2: SEMANTIC CONSISTENCY CHECKER
# ═══════════════════════════════════════════════════════════

class SemanticConsistencyChecker:
    """Detects internal contradictions within the response."""

    ANTONYM_PAIRS = {
        "always": "never", "true": "false", "possible": "impossible",
        "increase": "decrease", "faster": "slower", "more": "less",
        "best": "worst", "safe": "unsafe", "correct": "incorrect",
        "valid": "invalid", "efficient": "inefficient", "positive": "negative",
        "higher": "lower", "greater": "smaller", "optimal": "suboptimal",
        "convergent": "divergent", "stable": "unstable", "linear": "exponential",
        "yes": "no", "can": "cannot", "will": "won't",
    }

    @classmethod
    def check(cls, response: str) -> Tuple[float, List[VerificationViolation]]:
        violations = []
        sentences = [s.strip() for s in re.split(r'[.!?\n]', response) if len(s.strip()) > 8]

        if len(sentences) < 2:
            return 1.0, violations  # Can't check consistency with < 2 sentences

        score = 1.0
        for i in range(len(sentences)):
            for j in range(i + 1, min(i + 8, len(sentences))):  # Compare nearby sentences
                s_i = sentences[i].lower()
                s_j = sentences[j].lower()

                # Check antonym-based contradiction
                for word, antonym in cls.ANTONYM_PAIRS.items():
                    if word in s_i and antonym in s_j:
                        # Only flag if they share subject words
                        w_i = set(s_i.split()) - {word}
                        w_j = set(s_j.split()) - {antonym}
                        overlap = w_i & w_j
                        if len(overlap) >= 2:
                            violations.append(VerificationViolation(
                                VerificationLayer.SEMANTIC,
                                HallucinationType.CONTRADICTION,
                                f"Contradiction: '{word}' vs '{antonym}' about same subject",
                                0.7,
                                location=f"Sentences {i+1} and {j+1}",
                            ))
                            score -= 0.2

                # Direct negation
                if f"not {s_i}" in s_j or f"not {s_j}" in s_i:
                    violations.append(VerificationViolation(
                        VerificationLayer.SEMANTIC, HallucinationType.CONTRADICTION,
                        "Direct negation detected between statements", 0.8,
                        location=f"Sentences {i+1} and {j+1}",
                    ))
                    score -= 0.3

        return max(0.0, score), violations


# ═══════════════════════════════════════════════════════════
# LAYER 3: LOGICAL VALIDITY CHECKER
# ═══════════════════════════════════════════════════════════

class LogicalChecker:
    """Detects logical fallacies and invalid reasoning patterns."""

    FALLACY_PATTERNS = [
        (r'(?:because|since)\s+.*\s+(?:therefore|so|thus)\s+.*(?:because|since)', "Circular reasoning (A because B because A)", 0.7),
        (r'everyone\s+(?:knows|says|thinks|believes)', "Appeal to popularity / common knowledge", 0.3),
        (r'(?:obviously|clearly|undoubtedly|without\s+doubt)\s+', "Assertion without evidence (hedging with 'obviously')", 0.2),
        (r'if\s+.*then\s+.*therefore\s+(?:the\s+)?converse', "Affirming the consequent", 0.6),
        (r'(?:no\s+true|real)\s+\w+\s+would', "No true Scotsman fallacy", 0.4),
        (r'either\s+.*\s+or\s+.*(?:nothing\s+else|only\s+two)', "False dichotomy", 0.5),
        (r'(?:slippery\s+slope|inevitably\s+lead|will\s+cause.*which\s+will\s+cause)', "Slippery slope reasoning", 0.4),
    ]

    @classmethod
    def check(cls, response: str) -> Tuple[float, List[VerificationViolation]]:
        violations = []
        score = 1.0
        resp_lower = response.lower()

        for pattern, fallacy_name, severity in cls.FALLACY_PATTERNS:
            matches = re.findall(pattern, resp_lower)
            if matches:
                violations.append(VerificationViolation(
                    VerificationLayer.LOGICAL, HallucinationType.LOGICAL_FALLACY,
                    fallacy_name, severity,
                ))
                score -= severity * 0.3

        # Check for numeric calculations claimed in text
        # Look for "X * Y = Z" patterns and verify
        calc_pattern = r'(\d+(?:\.\d+)?)\s*([+\-*/×÷])\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)'
        for match in re.finditer(calc_pattern, response):
            try:
                a = float(match.group(1))
                op = match.group(2)
                b = float(match.group(3))
                claimed = float(match.group(4))
                ops = {'+': a + b, '-': a - b, '*': a * b, '×': a * b,
                       '/': a / b if b != 0 else float('inf'),
                       '÷': a / b if b != 0 else float('inf')}
                actual = ops.get(op)
                if actual is not None and abs(actual - claimed) > 0.01:
                    violations.append(VerificationViolation(
                        VerificationLayer.LOGICAL, HallucinationType.NUMERICAL_ERROR,
                        f"Arithmetic error: {a} {op} {b} = {actual}, not {claimed}",
                        0.9,
                    ))
                    score -= 0.3
            except (ValueError, ZeroDivisionError):
                pass

        return max(0.0, score), violations


# ═══════════════════════════════════════════════════════════
# LAYER 4: CROSS-REFERENCE CHECKER
# ═══════════════════════════════════════════════════════════

class CrossReferenceChecker:
    """Grounds claims against known facts and identity anchors."""

    # Built-in fact anchors (mathematical identities, physical constants, etc.)
    ANCHORS: List[AnchorPoint] = [
        AnchorPoint("pi is approximately 3.14159", "mathematical_constant"),
        AnchorPoint("e is approximately 2.71828", "mathematical_constant"),
        AnchorPoint("speed of light is approximately 3e8 m/s", "physical_constant"),
        AnchorPoint("gravitational acceleration is approximately 9.8 m/s²", "physical_constant"),
        AnchorPoint("absolute zero is -273.15 degrees Celsius", "physical_constant"),
        AnchorPoint("water freezes at 0 degrees Celsius", "physical_fact"),
        AnchorPoint("water boils at 100 degrees Celsius at standard pressure", "physical_fact"),
        AnchorPoint("1 + 1 = 2", "mathematical_identity"),
        AnchorPoint("0! = 1", "mathematical_identity"),
        AnchorPoint("sum of angles in a triangle is 180 degrees", "mathematical_theorem"),
        AnchorPoint("Pythagorean theorem: a² + b² = c²", "mathematical_theorem"),
        AnchorPoint("there are infinitely many prime numbers", "mathematical_theorem"),
        AnchorPoint("quicksort average case is O(n log n)", "computer_science"),
        AnchorPoint("merge sort worst case is O(n log n)", "computer_science"),
        AnchorPoint("binary search requires O(log n) time", "computer_science"),
        AnchorPoint("hash table average lookup is O(1)", "computer_science"),
    ]

    def __init__(self):
        self._custom_anchors: List[AnchorPoint] = []
        self._anchor_tokens: List[Tuple[AnchorPoint, Set[str]]] = [
            (a, set(a.statement.lower().split())) for a in self.ANCHORS
        ]

    def add_anchor(self, statement: str, source: str = "custom") -> None:
        """Add a custom fact anchor."""
        anchor = AnchorPoint(statement, source)
        self._custom_anchors.append(anchor)
        self._anchor_tokens.append((anchor, set(statement.lower().split())))

    def check(self, response: str) -> Tuple[float, List[VerificationViolation], int, int]:
        """
        Check response claims against anchors.
        Returns (score, violations, anchored_count, unanchored_count).
        """
        violations = []
        sentences = [s.strip() for s in re.split(r'[.!?\n]', response) if len(s.strip()) > 15]

        if not sentences:
            return 1.0, violations, 0, 0

        # Identify claim sentences (those making assertions)
        claim_indicators = [
            'is', 'are', 'equals', 'has', 'have', 'will', 'was', 'were',
            'requires', 'takes', 'runs', 'uses', 'produces', 'computes',
        ]
        claims = []
        for sent in sentences:
            sent_lower = sent.lower()
            if any(ind in sent_lower.split() for ind in claim_indicators):
                claims.append(sent)

        if not claims:
            return 1.0, violations, 0, 0

        anchored = 0
        unanchored = 0
        for claim in claims:
            claim_tokens = set(claim.lower().split())
            best_sim = 0.0
            for anchor, anchor_toks in self._anchor_tokens:
                if not anchor_toks:
                    continue
                intersection = len(claim_tokens & anchor_toks)
                union = len(claim_tokens | anchor_toks)
                sim = intersection / union if union > 0 else 0
                best_sim = max(best_sim, sim)

            if best_sim > 0.25:
                anchored += 1
            else:
                unanchored += 1

        # Score based on anchoring ratio
        total = anchored + unanchored
        if total == 0:
            return 1.0, violations, 0, 0

        score = 0.4 + 0.6 * (anchored / total)

        if unanchored > anchored * 2:
            violations.append(VerificationViolation(
                VerificationLayer.CROSS_REFERENCE, HallucinationType.UNSUPPORTED_CLAIM,
                f"{unanchored} claims not anchored to known facts (vs {anchored} anchored)", 0.4,
            ))

        return max(0.0, score), violations, anchored, unanchored


# ═══════════════════════════════════════════════════════════
# LAYER 5: CONFIDENCE CALIBRATOR
# ═══════════════════════════════════════════════════════════

class ConfidenceCalibrator:
    """Checks if stated confidence levels match evidence strength."""

    HIGH_CONFIDENCE_PHRASES = [
        "definitely", "certainly", "absolutely", "guaranteed", "proven",
        "without doubt", "100%", "always", "never fails", "impossible to",
    ]

    LOW_EVIDENCE_PHRASES = [
        "might", "perhaps", "arguably", "some say", "could be",
        "not sure", "uncertain", "debatable", "allegedly",
    ]

    @classmethod
    def check(cls, response: str, stated_confidence: float = 0.8) -> Tuple[float, List[VerificationViolation]]:
        violations = []
        resp_lower = response.lower()

        high_confidence_count = sum(1 for p in cls.HIGH_CONFIDENCE_PHRASES if p in resp_lower)
        low_evidence_count = sum(1 for p in cls.LOW_EVIDENCE_PHRASES if p in resp_lower)

        # Overconfidence: high confidence language + low evidence
        if high_confidence_count > 0 and low_evidence_count > 0:
            violations.append(VerificationViolation(
                VerificationLayer.CALIBRATION, HallucinationType.OVERCONFIDENCE,
                "Mix of high-confidence and uncertainty language suggests poor calibration",
                0.5,
            ))

        # Overconfidence: very high stated confidence with hedging language
        if stated_confidence > 0.9 and low_evidence_count > 1:
            violations.append(VerificationViolation(
                VerificationLayer.CALIBRATION, HallucinationType.OVERCONFIDENCE,
                f"Stated confidence {stated_confidence:.0%} but uses {low_evidence_count} hedging phrases",
                0.4,
            ))

        # Calculate calibration score
        if high_confidence_count + low_evidence_count == 0:
            calibration = 1.0  # No confidence language = neutral
        else:
            # Penalize mixed signals
            mixed_ratio = min(high_confidence_count, low_evidence_count) / max(high_confidence_count + low_evidence_count, 1)
            calibration = 1.0 - mixed_ratio * 0.5

        return calibration, violations


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE
# ═══════════════════════════════════════════════════════════

class HallucinationDestroyer:
    """
    5-layer verification pipeline that detects and scores hallucinations.

    Usage:
        hd = HallucinationDestroyer()
        result = hd.verify("The answer is 42. 2 + 2 = 5.")
        print(result.hallucination_score)  # high — arithmetic error
        print(result.summary())

        # Verify with context
        result = hd.verify(response, prompt="What is 2+2?", confidence=0.95)
    """

    def __init__(self):
        self.syntactic = SyntacticChecker()
        self.semantic = SemanticConsistencyChecker()
        self.logical = LogicalChecker()
        self.cross_ref = CrossReferenceChecker()
        self.calibrator = ConfidenceCalibrator()
        self._stats = {
            "verifications": 0, "clean": 0, "violations_total": 0,
            "avg_hallucination_score": 0.0, "total_h_score": 0.0,
        }

    def verify(self, response: str, prompt: str = "",
               confidence: float = 0.8) -> VerificationResult:
        """
        Run the full 5-layer verification pipeline.
        Returns a VerificationResult with hallucination score and violations.
        """
        start = time.time()
        result = VerificationResult()
        all_violations: List[VerificationViolation] = []

        # Layer 1: Syntactic
        l1_score, l1_viols = self.syntactic.check(response)
        result.layer_scores["L1_Syntactic"] = l1_score
        all_violations.extend(l1_viols)

        # Layer 2: Semantic Consistency
        l2_score, l2_viols = self.semantic.check(response)
        result.layer_scores["L2_Semantic"] = l2_score
        all_violations.extend(l2_viols)

        # Layer 3: Logical Validity
        l3_score, l3_viols = self.logical.check(response)
        result.layer_scores["L3_Logical"] = l3_score
        all_violations.extend(l3_viols)

        # Layer 4: Cross-Reference
        l4_score, l4_viols, anchored, unanchored = self.cross_ref.check(response)
        result.layer_scores["L4_CrossRef"] = l4_score
        result.anchored_claims = anchored
        result.unanchored_claims = unanchored
        result.total_claims = anchored + unanchored
        all_violations.extend(l4_viols)

        # Layer 5: Confidence Calibration
        l5_score, l5_viols = self.calibrator.check(response, confidence)
        result.layer_scores["L5_Calibration"] = l5_score
        result.confidence_calibration = l5_score
        all_violations.extend(l5_viols)

        # Aggregate hallucination score (weighted)
        weights = {
            "L1_Syntactic": 0.10,
            "L2_Semantic": 0.25,
            "L3_Logical": 0.30,
            "L4_CrossRef": 0.25,
            "L5_Calibration": 0.10,
        }
        weighted_score = sum(
            result.layer_scores.get(k, 1.0) * w
            for k, w in weights.items()
        )
        result.grounding_score = weighted_score
        result.hallucination_score = max(0.0, min(1.0, 1.0 - weighted_score))

        # Severity boost — critical violations push score higher
        critical_severity = sum(v.severity for v in all_violations if v.severity >= 0.7)
        if critical_severity > 0:
            result.hallucination_score = min(1.0, result.hallucination_score + critical_severity * 0.1)
            result.grounding_score = 1.0 - result.hallucination_score

        result.violations = all_violations
        result.is_clean = len(all_violations) == 0
        result.duration_ms = (time.time() - start) * 1000

        # Stats
        self._stats["verifications"] += 1
        if result.is_clean:
            self._stats["clean"] += 1
        self._stats["violations_total"] += len(all_violations)
        self._stats["total_h_score"] += result.hallucination_score
        self._stats["avg_hallucination_score"] = (
            self._stats["total_h_score"] / self._stats["verifications"]
        )

        return result

    def solve(self, prompt: str) -> VerificationResult:
        """Natural language interface for CCE routing."""
        return self.verify(prompt, prompt=prompt)

    def add_fact_anchor(self, statement: str, source: str = "custom") -> None:
        """Add a known-true fact to the cross-reference database."""
        self.cross_ref.add_anchor(statement, source)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "HallucinationDestroyer",
            **self._stats,
        }
