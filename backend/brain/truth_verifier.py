"""
Truth Verifier — Fact-Check Before Teaching
════════════════════════════════════════════
Most AI tutors blindly present whatever the LLM generates. This engine
validates teaching content BEFORE it reaches the student.

Pipeline:
  1. Parse response into individual claims/facts
  2. Detect hallucination signals (suspicious specificity, round numbers, etc.)
  3. Cross-reference key claims against web sources
  4. Score overall truth confidence
  5. Annotate response with verification badges
  6. Flag known misconceptions

Confidence Levels:
  🟢 HIGH   (≥0.8) — Multiple sources confirm, safe to teach
  🟡 MEDIUM (≥0.5) — Some support, teach with caveats
  🔴 LOW    (<0.5) — Unverified or contradicted, flag prominently

Usage:
    verifier = TruthVerifier(generate_fn=llm_fn, tool_bridge=bridge)
    result = verifier.verify_response(response_text, topic="quantum computing")
    annotated = result.annotated_response
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Hallucination Detection Patterns
# ══════════════════════════════════════════════════════════════

# Patterns that suggest potentially fabricated specifics
_HALLUCINATION_SIGNALS = [
    # Suspiciously specific statistics without citation
    (re.compile(r'\b\d{2,3}(?:\.\d+)?%\s+of\s+(?:people|users|companies|developers|students)', re.I),
     "specific_statistic", 0.3),
    # Exact year claims for discoveries/inventions (often wrong)
    (re.compile(r'(?:invented|discovered|created|founded|established)\s+in\s+\d{4}', re.I),
     "historical_date", 0.2),
    # Named attribution without hedging
    (re.compile(r'(?:Dr\.|Professor|researcher)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s+(?:proved|showed|demonstrated)', re.I),
     "named_attribution", 0.25),
    # Round numbers that feel estimated
    (re.compile(r'\b(?:exactly|precisely|approximately)\s+\d+(?:,\d{3})+\b', re.I),
     "round_number", 0.15),
    # Definitive claims about contested topics
    (re.compile(r'(?:the\s+(?:best|only|correct|true|proven))\s+(?:way|method|approach|answer)', re.I),
     "absolutist_claim", 0.2),
    # Claims about "most" or "all" without qualification
    (re.compile(r'\b(?:all|every|most|no)\s+(?:experts|scientists|researchers|developers)\s+(?:agree|believe|recommend)', re.I),
     "universal_claim", 0.25),
]

# Known misconception patterns (topic → common wrong beliefs)
_COMMON_MISCONCEPTIONS = {
    "python": [
        ("Python is interpreted, not compiled", "Python IS compiled to bytecode; the bytecode is then interpreted by the CPython VM"),
        ("Python is always slow", "Python can be fast with NumPy/Cython/PyPy; bottleneck is often I/O, not CPU"),
        ("GIL prevents all parallelism", "GIL only affects CPU-bound threads; multiprocessing/async I/O bypass it"),
    ],
    "javascript": [
        ("JavaScript is single-threaded", "The main thread is single-threaded, but Web Workers enable true parallelism"),
        ("== and === are interchangeable", "== does type coercion which leads to unexpected results; prefer ==="),
        ("var and let are the same", "var is function-scoped and hoisted; let is block-scoped"),
    ],
    "machine learning": [
        ("More data always means better models", "Noisy/biased data can hurt; data quality matters more than quantity"),
        ("Deep learning is always better than classical ML", "For tabular data, gradient boosting often outperforms deep learning"),
        ("Accuracy is the best metric", "For imbalanced classes, precision/recall/F1/AUC are far more informative"),
    ],
    "security": [
        ("HTTPS means the site is safe", "HTTPS only encrypts transit; the server itself may be malicious"),
        ("Strong passwords are enough", "Even strong passwords can be phished; 2FA/MFA is essential"),
        ("Encryption is unbreakable", "Encryption strength depends on key length, algorithm, and implementation"),
    ],
    "database": [
        ("NoSQL is always faster than SQL", "For complex queries and joins, SQL databases often outperform NoSQL"),
        ("ORMs remove the need to understand SQL", "ORMs can generate inefficient queries; understanding SQL is critical"),
        ("Indexing everything improves performance", "Too many indexes slow writes and increase storage"),
    ],
}


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

@dataclass
class ClaimVerification:
    """Verification status of a single claim in the response."""
    claim_text: str = ""
    confidence: float = 0.5
    hallucination_signals: List[str] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    is_misconception: bool = False
    correction: str = ""
    verified: bool = False


@dataclass
class TruthReport:
    """Complete truth verification report for a tutoring response."""
    original_response: str = ""
    annotated_response: str = ""
    overall_confidence: float = 0.5
    claims_checked: int = 0
    claims_verified: int = 0
    claims_flagged: int = 0
    hallucination_signals: List[str] = field(default_factory=list)
    misconceptions_found: List[Dict[str, str]] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    verification_time_ms: float = 0.0
    claim_details: List[ClaimVerification] = field(default_factory=list)

    @property
    def trust_badge(self) -> str:
        """Return a trust badge for the response."""
        if self.overall_confidence >= 0.8:
            return f"✅ High Confidence ({self.overall_confidence:.0%})"
        elif self.overall_confidence >= 0.5:
            return f"⚠️ Medium Confidence ({self.overall_confidence:.0%})"
        else:
            return f"❓ Low Confidence ({self.overall_confidence:.0%})"

    def to_api_dict(self) -> Dict[str, Any]:
        """Convert to API-friendly dict."""
        return {
            "truth_score": round(self.overall_confidence, 3),
            "trust_badge": self.trust_badge,
            "claims_checked": self.claims_checked,
            "claims_verified": self.claims_verified,
            "claims_flagged": self.claims_flagged,
            "hallucination_signals": self.hallucination_signals,
            "misconceptions": self.misconceptions_found,
            "sources": self.sources[:5],
            "verification_time_ms": round(self.verification_time_ms, 1),
        }


# ══════════════════════════════════════════════════════════════
# Truth Verifier Engine
# ══════════════════════════════════════════════════════════════

class TruthVerifier:
    """
    Validates teaching content before it reaches the student.

    Unlike typical AI tutors that present LLM output as-is, this engine:
      1. Detects hallucination signals (suspicious specificity)
      2. Flags known misconceptions relevant to the topic
      3. Cross-references key claims against web sources (when tool bridge available)
      4. Annotates the response with verification badges
      5. Provides an overall truth confidence score

    This implements the "truth-first" teaching philosophy:
    it's better to say "I'm not sure" than to teach something wrong.
    """

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        tool_bridge=None,
    ):
        self._generate_fn = generate_fn
        self._tool_bridge = tool_bridge
        self._verification_cache: Dict[str, TruthReport] = {}
        logger.info("🔍 TruthVerifier initialized")

    def verify_response(
        self,
        response: str,
        topic: str = "",
        deep_verify: bool = False,
    ) -> TruthReport:
        """
        Verify a tutoring response for truthfulness.

        Args:
            response: The LLM-generated teaching response
            topic: The topic being taught (for misconception checking)
            deep_verify: If True, cross-references claims against web (slower)

        Returns:
            TruthReport with confidence score and annotations
        """
        start = time.monotonic()
        report = TruthReport(original_response=response)

        # Step 1: Detect hallucination signals
        h_signals = self._detect_hallucinations(response)
        report.hallucination_signals = h_signals

        # Step 2: Check for known misconceptions
        misconceptions = self._check_misconceptions(response, topic)
        report.misconceptions_found = misconceptions

        # Step 3: Extract and verify key claims
        claims = self._extract_claims(response)
        report.claims_checked = len(claims)

        for claim_text in claims:
            claim_v = ClaimVerification(claim_text=claim_text)

            # Check if this claim matches a hallucination pattern
            for pattern, signal_name, weight in _HALLUCINATION_SIGNALS:
                if pattern.search(claim_text):
                    claim_v.hallucination_signals.append(signal_name)
                    claim_v.confidence -= weight

            # Check misconceptions
            for m in misconceptions:
                if m["wrong_belief"].lower() in claim_text.lower():
                    claim_v.is_misconception = True
                    claim_v.correction = m["truth"]
                    claim_v.confidence = 0.1

            # Deep verification via web search
            if deep_verify and self._tool_bridge and len(claim_text) > 20:
                web_verification = self._tool_bridge.verify_claim(
                    claim=claim_text, topic_context=topic,
                )
                claim_v.confidence = max(
                    claim_v.confidence, web_verification.confidence,
                )
                claim_v.sources = web_verification.sources
                claim_v.verified = web_verification.verified
                report.sources.extend(web_verification.sources)

            # Clamp confidence
            claim_v.confidence = max(0.0, min(1.0, claim_v.confidence + 0.5))

            if claim_v.confidence >= 0.7:
                report.claims_verified += 1
            elif claim_v.confidence < 0.4 or claim_v.is_misconception:
                report.claims_flagged += 1

            report.claim_details.append(claim_v)

        # Step 4: Calculate overall confidence
        if report.claim_details:
            avg_conf = sum(c.confidence for c in report.claim_details) / len(report.claim_details)
            # Penalize for hallucination signals
            penalty = len(h_signals) * 0.05
            # Penalize for misconceptions
            penalty += len(misconceptions) * 0.1
            report.overall_confidence = max(0.0, min(1.0, avg_conf - penalty))
        else:
            report.overall_confidence = 0.6  # Neutral if no claims extracted

        # Step 5: Annotate response
        report.annotated_response = self._annotate_response(response, report)

        report.verification_time_ms = (time.monotonic() - start) * 1000
        logger.info(
            "🔍 Truth verification: confidence=%.2f, claims=%d, verified=%d, flagged=%d, time=%.0fms",
            report.overall_confidence, report.claims_checked,
            report.claims_verified, report.claims_flagged,
            report.verification_time_ms,
        )
        return report

    # ──────────────────────────────────────
    # Hallucination Detection
    # ──────────────────────────────────────

    def _detect_hallucinations(self, text: str) -> List[str]:
        """Scan text for hallucination signals."""
        signals = []
        for pattern, signal_name, _weight in _HALLUCINATION_SIGNALS:
            if pattern.search(text):
                signals.append(signal_name)

        # Additional heuristic: very long, very specific paragraphs
        sentences = text.split(". ")
        for sentence in sentences:
            # Suspiciously specific number claims
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', sentence)
            if len(numbers) >= 3 and len(sentence) > 100:
                signals.append("dense_statistics")
                break

        return list(set(signals))

    # ──────────────────────────────────────
    # Misconception Detection
    # ──────────────────────────────────────

    def _check_misconceptions(self, text: str, topic: str) -> List[Dict[str, str]]:
        """Check if the response contains known misconceptions."""
        found = []
        text_lower = text.lower()

        # Check topic-specific misconceptions
        for topic_key, misconceptions in _COMMON_MISCONCEPTIONS.items():
            if topic_key in topic.lower() or topic_key in text_lower:
                for wrong_belief, truth in misconceptions:
                    # Check if response contains the wrong belief
                    # (simplified: check if key phrases match)
                    wrong_keywords = wrong_belief.lower().split()
                    match_count = sum(
                        1 for kw in wrong_keywords
                        if len(kw) > 3 and kw in text_lower
                    )
                    if match_count >= len(wrong_keywords) * 0.6:
                        found.append({
                            "wrong_belief": wrong_belief,
                            "truth": truth,
                            "topic": topic_key,
                        })

        return found

    # ──────────────────────────────────────
    # Claim Extraction
    # ──────────────────────────────────────

    def _extract_claims(self, text: str) -> List[str]:
        """Extract verifiable factual claims from the response text."""
        claims = []

        # Strategy 1: Sentences with factual markers
        factual_markers = [
            r'is\s+(?:a|an|the)\b',
            r'(?:was|were)\s+(?:invented|discovered|created|founded)',
            r'\b(?:always|never|must|requires)\b',
            r'\b\d+(?:\.\d+)?%',
            r'\bin\s+\d{4}\b',
            r'(?:according to|research shows|studies show)',
        ]

        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 15 or len(sentence) > 300:
                continue
            # Skip questions, commands, and meta-text
            if sentence.endswith("?") or sentence.startswith(("Let's", "Try", "Now")):
                continue

            for marker in factual_markers:
                if re.search(marker, sentence, re.I):
                    claims.append(sentence)
                    break

        # Deduplicate while preserving order
        seen = set()
        unique_claims = []
        for claim in claims:
            normalized = claim.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                unique_claims.append(claim)

        return unique_claims[:10]  # Max 10 claims to verify

    # ──────────────────────────────────────
    # Response Annotation
    # ──────────────────────────────────────

    def _annotate_response(self, response: str, report: TruthReport) -> str:
        """Add verification annotations to the response."""
        annotated = response

        # Add misconception warnings
        for m in report.misconceptions_found:
            warning = (
                f"\n\n⚠️ **Common Misconception Alert:**\n"
                f"Many people believe: \"{m['wrong_belief']}\"\n"
                f"But the truth is: \"{m['truth']}\"\n"
            )
            annotated += warning

        # Add overall trust badge at the end
        if report.claims_checked > 0:
            badge = f"\n\n---\n{report.trust_badge}"
            if report.sources:
                badge += f" | 📚 {len(report.sources)} source(s) checked"
            annotated += badge

        return annotated

    # ──────────────────────────────────────
    # Preemptive Misconception Generator
    # ──────────────────────────────────────

    def get_preemptive_misconceptions(self, topic: str) -> List[Dict[str, str]]:
        """
        Get known misconceptions for a topic BEFORE teaching begins.

        This enables the "misconception-first" teaching approach:
        show students what most people get wrong, then teach the truth.
        """
        results = []

        # Check static database
        for topic_key, misconceptions in _COMMON_MISCONCEPTIONS.items():
            if topic_key in topic.lower():
                for wrong_belief, truth in misconceptions:
                    results.append({
                        "wrong_belief": wrong_belief,
                        "truth": truth,
                        "source": "knowledge_base",
                    })

        # Generate dynamic misconceptions via LLM
        if self._generate_fn and len(results) < 3:
            try:
                prompt = (
                    f"What are the top 3 most common misconceptions that beginners "
                    f"have about: {topic}?\n\n"
                    f"Format as JSON array:\n"
                    f'[{{"wrong_belief": "what people wrongly think", '
                    f'"truth": "what is actually correct"}}]\n'
                    f"Be specific and practical. Output ONLY the JSON array."
                )
                result = self._call_llm(prompt)
                import json
                match = re.search(r'\[.*\]', result, re.DOTALL)
                if match:
                    items = json.loads(match.group(0))
                    for item in items[:3]:
                        results.append({
                            "wrong_belief": item.get("wrong_belief", ""),
                            "truth": item.get("truth", ""),
                            "source": "llm_generated",
                        })
            except Exception as exc:
                logger.warning("Misconception generation failed: %s", exc)

        return results[:5]

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM safely."""
        if not self._generate_fn:
            return ""
        try:
            result = self._generate_fn(prompt)
            if hasattr(result, "answer"):
                return result.answer
            return str(result)
        except Exception as exc:
            logger.error("TruthVerifier LLM call failed: %s", exc)
            return ""
