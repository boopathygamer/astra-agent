"""
Domain Router — Intelligent Request Classification & Routing.
──────────────────────────────────────────────────────────────
Classifies user intent and routes to the right domain expert.

Features:
  - Multi-keyword pattern matching across 10 domains
  - Confidence scoring with weighted keywords
  - Multi-domain detection (e.g., "build a website for my shop")
  - Context-aware routing (remembers user's domain)
  - Fallback to general assistant for unclassifiable requests
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class DomainMatch:
    """Result of domain classification."""
    primary_domain: str = "general"
    confidence: float = 0.0
    secondary_domains: List[str] = field(default_factory=list)
    all_scores: Dict[str, float] = field(default_factory=dict)
    reasoning: str = ""

    @property
    def is_multi_domain(self) -> bool:
        return len(self.secondary_domains) > 0

    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.3


# ──────────────────────────────────────────────
# Domain Keywords (weighted)
# ──────────────────────────────────────────────

# Each domain has (keyword, weight) pairs — higher weight = stronger signal
DOMAIN_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    "code": [
        ("code", 1.0), ("program", 1.0), ("function", 0.8), ("debug", 1.0),
        ("python", 1.0), ("javascript", 1.0), ("api", 0.9), ("database", 0.8),
        ("algorithm", 0.9), ("compile", 1.0), ("syntax", 1.0), ("bug", 0.9),
        ("git", 1.0), ("deploy", 0.8), ("server", 0.7), ("html", 1.0),
        ("css", 1.0), ("react", 1.0), ("backend", 1.0), ("frontend", 1.0),
        ("class", 0.5), ("variable", 0.8), ("loop", 0.6), ("array", 0.7),
        ("sql", 1.0), ("docker", 1.0), ("linux", 0.8), ("terminal", 0.7),
        ("framework", 0.7), ("library", 0.5), ("import", 0.6), ("script", 0.8),
    ],
    "writing": [
        ("write", 0.6), ("essay", 1.0), ("article", 0.9), ("blog", 0.8),
        ("story", 0.9), ("poem", 1.0), ("letter", 0.7), ("email", 0.7),
        ("grammar", 1.0), ("proofread", 1.0), ("edit", 0.5), ("draft", 0.8),
        ("paragraph", 0.9), ("thesis", 0.9), ("report", 0.6), ("resume", 0.9),
        ("cover letter", 1.0), ("content", 0.5), ("copywriting", 1.0),
        ("tone", 0.6), ("headline", 0.8), ("creative writing", 1.0),
        ("narrative", 0.9), ("dialogue", 0.8), ("novel", 1.0),
    ],
    "math": [
        ("math", 1.0), ("calculate", 0.9), ("equation", 1.0), ("formula", 0.9),
        ("algebra", 1.0), ("calculus", 1.0), ("geometry", 1.0), ("statistics", 0.9),
        ("probability", 1.0), ("integral", 1.0), ("derivative", 1.0),
        ("matrix", 0.7), ("vector", 0.6), ("linear", 0.5), ("quadratic", 1.0),
        ("trigonometry", 1.0), ("logarithm", 1.0), ("fraction", 0.8),
        ("percentage", 0.7), ("average", 0.6), ("median", 0.8), ("solve", 0.5),
        ("physics", 0.8), ("chemistry", 0.7), ("science", 0.5), ("molecule", 0.9),
        ("atom", 0.9), ("force", 0.5), ("energy", 0.5), ("theorem", 1.0),
    ],
    "business": [
        ("business", 1.0), ("startup", 1.0), ("marketing", 1.0), ("revenue", 1.0),
        ("profit", 0.9), ("strategy", 0.7), ("customer", 0.7), ("market", 0.6),
        ("brand", 0.8), ("sales", 0.9), ("roi", 1.0), ("invest", 0.8),
        ("budget", 0.7), ("kpi", 1.0), ("analytics", 0.6), ("growth", 0.5),
        ("pitch", 0.8), ("competitor", 0.9), ("swot", 1.0), ("funnel", 0.9),
        ("b2b", 1.0), ("b2c", 1.0), ("stakeholder", 0.9), ("ceo", 0.8),
        ("entrepreneur", 1.0), ("product launch", 1.0), ("pricing", 0.8),
    ],
    "creative": [
        ("design", 0.7), ("creative", 0.8), ("art", 0.7), ("color", 0.5),
        ("logo", 1.0), ("illustration", 1.0), ("sketch", 0.9), ("palette", 1.0),
        ("aesthetic", 0.9), ("typography", 1.0), ("layout", 0.6), ("ux", 1.0),
        ("ui", 0.8), ("wireframe", 1.0), ("prototype", 0.7), ("animation", 0.8),
        ("photoshop", 1.0), ("figma", 1.0), ("canva", 1.0), ("mood board", 1.0),
        ("composition", 0.7), ("visual", 0.5), ("branding", 0.8),
        ("brainstorm", 0.7), ("inspiration", 0.6), ("idea", 0.4),
    ],
    "education": [
        ("learn", 0.6), ("teach", 0.8), ("study", 0.7), ("explain", 0.5),
        ("tutor", 1.0), ("homework", 1.0), ("exam", 1.0), ("quiz", 0.9),
        ("lesson", 0.9), ("course", 0.7), ("curriculum", 1.0), ("student", 0.7),
        ("teacher", 0.8), ("classroom", 1.0), ("grade", 0.6), ("semester", 0.9),
        ("lecture", 0.9), ("assignment", 0.9), ("flashcard", 1.0), ("test prep", 1.0),
        ("scholarship", 1.0), ("gpa", 1.0), ("university", 0.8), ("school", 0.6),
        ("textbook", 0.9), ("syllabus", 1.0), ("understand", 0.3),
    ],
    "health": [
        ("health", 0.9), ("nutrition", 1.0), ("exercise", 0.9), ("fitness", 1.0),
        ("diet", 0.9), ("calories", 1.0), ("protein", 0.9), ("vitamin", 1.0),
        ("sleep", 0.7), ("stress", 0.6), ("meditation", 0.9), ("yoga", 1.0),
        ("workout", 1.0), ("muscle", 0.8), ("weight loss", 1.0), ("bmi", 1.0),
        ("wellness", 0.9), ("mental health", 1.0), ("therapy", 0.7),
        ("hydration", 0.9), ("stretching", 0.8), ("cardio", 1.0),
        ("recipe", 0.5), ("meal plan", 1.0), ("supplement", 0.9),
    ],
    "legal": [
        ("legal", 1.0), ("law", 0.9), ("contract", 1.0), ("court", 1.0),
        ("rights", 0.7), ("regulation", 0.9), ("compliance", 1.0), ("sue", 1.0),
        ("lawyer", 1.0), ("attorney", 1.0), ("patent", 1.0), ("trademark", 1.0),
        ("copyright", 1.0), ("nda", 1.0), ("liability", 1.0), ("lawsuit", 1.0),
        ("terms of service", 1.0), ("privacy policy", 1.0), ("gdpr", 1.0),
        ("intellectual property", 1.0), ("clause", 0.9), ("agreement", 0.6),
        ("statute", 1.0), ("jurisdiction", 1.0), ("tort", 1.0),
    ],
    "data": [
        ("data", 0.5), ("dataset", 1.0), ("csv", 1.0), ("excel", 0.9),
        ("spreadsheet", 0.9), ("chart", 0.8), ("graph", 0.5), ("visualization", 0.9),
        ("dashboard", 0.8), ("report", 0.5), ("analysis", 0.6), ("trend", 0.7),
        ("correlation", 1.0), ("regression", 1.0), ("forecast", 0.9),
        ("histogram", 1.0), ("pie chart", 1.0), ("bar chart", 1.0),
        ("pivot table", 1.0), ("aggregate", 0.8), ("metric", 0.7),
        ("insight", 0.5), ("tableau", 1.0), ("power bi", 1.0),
    ],
    "lifestyle": [
        ("travel", 1.0), ("trip", 0.8), ("vacation", 1.0), ("hotel", 0.9),
        ("flight", 0.9), ("itinerary", 1.0), ("cooking", 1.0), ("recipe", 0.8),
        ("ingredient", 0.8), ("restaurant", 0.7), ("productivity", 0.8),
        ("habit", 0.7), ("morning routine", 1.0), ("time management", 1.0),
        ("organization", 0.6), ("declutter", 1.0), ("minimalism", 0.9),
        ("relationship", 0.7), ("gift", 0.6), ("party", 0.5), ("event", 0.5),
        ("home", 0.4), ("garden", 0.8), ("diy", 0.9), ("craft", 0.8),
        ("fashion", 0.8), ("style", 0.4), ("skincare", 0.9), ("self-care", 1.0),
    ],
}


# ──────────────────────────────────────────────
# Domain Router Engine
# ──────────────────────────────────────────────

class DomainRouter:
    """
    Classifies user requests into domains and routes to experts.

    Features:
      - Weighted keyword matching across 10 domains
      - Multi-domain detection with primary + secondary
      - Context persistence (remembers recent domain)
      - Confidence thresholding
      - Fallback to general assistant
    """

    def __init__(self):
        self._context_domain: Optional[str] = None
        self._context_weight = 0.15  # Boost for continuing in same domain
        self._history: List[str] = []
        logger.info("DomainRouter initialized with 10 domains")

    def classify(self, user_input: str) -> DomainMatch:
        """
        Classify a user request into one or more domains.

        Args:
            user_input: The user's message

        Returns:
            DomainMatch with primary domain, confidence, and secondaries
        """
        input_lower = user_input.lower()
        scores: Dict[str, float] = {}

        # Score each domain
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = 0.0
            matches = 0
            for keyword, weight in keywords:
                # Use word boundary matching for short keywords
                if len(keyword) <= 3:
                    pattern = rf"\b{re.escape(keyword)}\b"
                    if re.search(pattern, input_lower):
                        score += weight
                        matches += 1
                elif keyword in input_lower:
                    score += weight
                    matches += 1

            # Normalize: more matches = higher confidence
            if matches > 0:
                # Diminishing returns for many matches
                score = score * min(matches, 5) / 5
                scores[domain] = round(score, 3)

        # Apply context boost (continuing in same domain)
        if self._context_domain and self._context_domain in scores:
            scores[self._context_domain] += self._context_weight

        if not scores:
            return DomainMatch(
                primary_domain="general",
                confidence=0.0,
                all_scores={},
                reasoning="No domain keywords matched — using general assistant",
            )

        # Sort by score
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_domains[0]
        total_score = sum(s for _, s in sorted_domains)

        # Secondary domains (scored above threshold relative to primary)
        secondaries = [
            d for d, s in sorted_domains[1:]
            if s >= primary[1] * 0.5 and s >= 0.3
        ]

        # Confidence is relative strength of primary
        confidence = primary[1] / max(total_score, 0.01)
        confidence = min(confidence, 1.0)

        result = DomainMatch(
            primary_domain=primary[0],
            confidence=round(confidence, 3),
            secondary_domains=secondaries[:2],  # Max 2 secondaries
            all_scores=scores,
            reasoning=(
                f"Matched '{primary[0]}' (score={primary[1]:.2f}, "
                f"confidence={confidence:.0%})"
                + (f" + secondaries: {secondaries}" if secondaries else "")
            ),
        )

        # Update context
        self._context_domain = primary[0]
        self._history.append(primary[0])

        logger.debug(f"Domain: {result.reasoning}")
        return result

    def reset_context(self):
        """Reset domain context."""
        self._context_domain = None
        self._history.clear()

    def get_recent_domains(self, n: int = 5) -> List[str]:
        """Get the last N domains used."""
        return self._history[-n:]
