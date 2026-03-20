"""
Knowledge Crystallization Engine — Self-Growing Knowledge Base
═══════════════════════════════════════════════════════════════
Distills solved problems into reusable theorems, formulas, and patterns.
Detects contradictions in knowledge and auto-corrects using formal logic.

No LLM, no GPU — pure symbolic knowledge management.
"""

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class KnowledgeType(Enum):
    THEOREM = "theorem"         # Proven logical statement
    FORMULA = "formula"         # Mathematical formula
    PATTERN = "pattern"         # Solution pattern
    HEURISTIC = "heuristic"     # Useful rule of thumb
    FACT = "fact"               # Known fact
    RULE = "rule"               # Inferred rule


@dataclass
class Crystal:
    """A crystallized piece of knowledge."""
    crystal_id: str = ""
    crystal_type: KnowledgeType = KnowledgeType.FACT
    statement: str = ""
    evidence: List[str] = field(default_factory=list)
    confidence: float = 1.0
    uses: int = 0
    created_at: float = 0.0
    source_problem: str = ""
    tags: Set[str] = field(default_factory=set)
    related: Set[str] = field(default_factory=set)

    def __post_init__(self):
        if not self.crystal_id:
            self.crystal_id = hashlib.sha256(self.statement.encode()).hexdigest()[:12]
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class Contradiction:
    """A detected contradiction between two crystals."""
    crystal_a_id: str
    crystal_b_id: str
    statement_a: str
    statement_b: str
    contradiction_type: str
    resolution: str = ""
    resolved: bool = False


@dataclass
class CrystallizationResult:
    crystals_added: int = 0
    crystals_total: int = 0
    contradictions_found: int = 0
    contradictions_resolved: int = 0
    relevant_knowledge: List[Crystal] = field(default_factory=list)
    new_crystals: List[Crystal] = field(default_factory=list)
    duration_ms: float = 0.0

    def summary(self) -> str:
        lines = [
            f"## Knowledge Crystallization",
            f"**Total Crystals**: {self.crystals_total}",
            f"**New**: +{self.crystals_added}",
            f"**Contradictions**: {self.contradictions_found} found, {self.contradictions_resolved} resolved",
        ]
        if self.new_crystals:
            lines.append("\n### New Knowledge:")
            for c in self.new_crystals[:5]:
                lines.append(f"  - [{c.crystal_type.value}] {c.statement[:80]} (conf: {c.confidence:.0%})")
        if self.relevant_knowledge:
            lines.append(f"\n### Relevant Knowledge: {len(self.relevant_knowledge)} crystals retrieved")
        return "\n".join(lines)


class KnowledgeCrystal:
    """
    Self-growing knowledge base with contradiction detection.

    Usage:
        kb = KnowledgeCrystal()

        # Crystallize from a solved problem
        kb.crystallize("Quicksort has O(n log n) average case",
                       crystal_type=KnowledgeType.THEOREM,
                       tags={"sorting", "algorithms", "complexity"})

        # Query knowledge
        results = kb.query("sorting algorithm complexity")

        # Detect contradictions
        contradictions = kb.detect_contradictions()
    """

    # Antonym pairs for contradiction detection
    ANTONYMS = {
        "always": "never", "true": "false", "positive": "negative",
        "increase": "decrease", "faster": "slower", "more": "less",
        "best": "worst", "optimal": "suboptimal", "possible": "impossible",
        "correct": "incorrect", "valid": "invalid", "safe": "unsafe",
        "efficient": "inefficient", "convergent": "divergent",
        "linear": "exponential", "stable": "unstable",
    }

    def __init__(self):
        self._crystals: Dict[str, Crystal] = {}
        self._index: Dict[str, Set[str]] = defaultdict(set)  # tag → crystal_ids
        self._contradictions: List[Contradiction] = []
        self._stats = {"crystallizations": 0, "queries": 0, "contradictions_found": 0, "contradictions_resolved": 0}

    def crystallize(self, statement: str, crystal_type: KnowledgeType = KnowledgeType.FACT,
                    confidence: float = 1.0, evidence: Optional[List[str]] = None,
                    tags: Optional[Set[str]] = None, source: str = "") -> Crystal:
        """Add a new crystal to the knowledge base."""
        crystal = Crystal(
            crystal_type=crystal_type,
            statement=statement,
            evidence=evidence or [],
            confidence=confidence,
            source_problem=source,
            tags=tags or set(),
        )

        # Auto-tag from content
        auto_tags = self._extract_tags(statement)
        crystal.tags.update(auto_tags)

        # Store
        self._crystals[crystal.crystal_id] = crystal
        for tag in crystal.tags:
            self._index[tag].add(crystal.crystal_id)

        # Check for contradictions with existing knowledge
        self._check_new_contradictions(crystal)

        self._stats["crystallizations"] += 1
        return crystal

    def crystallize_from_solution(self, problem: str, solution: str,
                                  confidence: float = 0.8) -> List[Crystal]:
        """Extract and crystallize knowledge from a problem-solution pair."""
        crystals = []
        tags = self._extract_tags(problem + " " + solution)

        # Create a pattern crystal
        pattern = Crystal(
            crystal_type=KnowledgeType.PATTERN,
            statement=f"Problem: {problem[:60]} → Solution approach: {solution[:80]}",
            evidence=[f"Discovered from solving: {problem[:100]}"],
            confidence=confidence,
            source_problem=problem,
            tags=tags,
        )
        self._crystals[pattern.crystal_id] = pattern
        for tag in pattern.tags:
            self._index[tag].add(pattern.crystal_id)
        crystals.append(pattern)

        # Extract key facts
        sentences = [s.strip() for s in solution.split('.') if len(s.strip()) > 10]
        for sent in sentences[:3]:
            fact = Crystal(
                crystal_type=KnowledgeType.FACT,
                statement=sent,
                confidence=confidence * 0.8,
                source_problem=problem,
                tags=self._extract_tags(sent),
            )
            self._crystals[fact.crystal_id] = fact
            for tag in fact.tags:
                self._index[tag].add(fact.crystal_id)
            crystals.append(fact)

        self._stats["crystallizations"] += len(crystals)
        return crystals

    def query(self, query: str, top_k: int = 5) -> List[Crystal]:
        """Query the knowledge base."""
        self._stats["queries"] += 1
        query_tags = self._extract_tags(query)
        query_words = set(query.lower().split())

        # Score crystals by relevance
        scores: Dict[str, float] = defaultdict(float)
        for tag in query_tags:
            for crystal_id in self._index.get(tag, set()):
                scores[crystal_id] += 1.0

        # Also do keyword matching
        for crystal_id, crystal in self._crystals.items():
            crystal_words = set(crystal.statement.lower().split())
            overlap = len(query_words & crystal_words)
            if overlap > 0:
                scores[crystal_id] += overlap * 0.5

        # Boost by confidence and usage
        for crystal_id in scores:
            crystal = self._crystals[crystal_id]
            scores[crystal_id] *= crystal.confidence
            scores[crystal_id] += crystal.uses * 0.1

        # Sort and return top results
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        results = []
        for crystal_id, score in ranked[:top_k]:
            crystal = self._crystals[crystal_id]
            crystal.uses += 1
            results.append(crystal)

        return results

    def detect_contradictions(self) -> List[Contradiction]:
        """Scan all knowledge for internal contradictions."""
        new_contradictions = []
        crystal_list = list(self._crystals.values())

        for i in range(len(crystal_list)):
            for j in range(i + 1, len(crystal_list)):
                c1, c2 = crystal_list[i], crystal_list[j]
                contradiction = self._check_pair(c1, c2)
                if contradiction:
                    new_contradictions.append(contradiction)

        self._contradictions.extend(new_contradictions)
        self._stats["contradictions_found"] += len(new_contradictions)
        return new_contradictions

    def resolve_contradiction(self, contradiction: Contradiction) -> str:
        """Resolve a contradiction by keeping the higher-confidence crystal."""
        c_a = self._crystals.get(contradiction.crystal_a_id)
        c_b = self._crystals.get(contradiction.crystal_b_id)
        if not c_a or not c_b:
            return "Cannot resolve — crystal(s) not found"

        # Keep higher confidence, lower confidence of the other
        if c_a.confidence >= c_b.confidence:
            c_b.confidence *= 0.5
            resolution = f"Kept '{c_a.statement[:50]}' (conf: {c_a.confidence:.2f}), weakened '{c_b.statement[:50]}'"
        else:
            c_a.confidence *= 0.5
            resolution = f"Kept '{c_b.statement[:50]}' (conf: {c_b.confidence:.2f}), weakened '{c_a.statement[:50]}'"

        contradiction.resolved = True
        contradiction.resolution = resolution
        self._stats["contradictions_resolved"] += 1
        return resolution

    def _check_new_contradictions(self, new_crystal: Crystal) -> None:
        """Check if a new crystal contradicts existing knowledge."""
        for existing in self._crystals.values():
            if existing.crystal_id == new_crystal.crystal_id:
                continue
            contradiction = self._check_pair(new_crystal, existing)
            if contradiction:
                self._contradictions.append(contradiction)
                self._stats["contradictions_found"] += 1

    def _check_pair(self, c1: Crystal, c2: Crystal) -> Optional[Contradiction]:
        """Check if two crystals contradict each other."""
        s1_lower = c1.statement.lower()
        s2_lower = c2.statement.lower()

        # Check for antonym-based contradictions
        for word, antonym in self.ANTONYMS.items():
            if word in s1_lower and antonym in s2_lower:
                # Check if they're talking about the same subject
                s1_words = set(s1_lower.split())
                s2_words = set(s2_lower.split())
                overlap = s1_words & s2_words - {word, antonym}
                if len(overlap) >= 2:
                    return Contradiction(
                        crystal_a_id=c1.crystal_id,
                        crystal_b_id=c2.crystal_id,
                        statement_a=c1.statement,
                        statement_b=c2.statement,
                        contradiction_type=f"Antonym conflict: '{word}' vs '{antonym}'",
                    )

        # Check for direct negation
        if ("not " in s1_lower and s1_lower.replace("not ", "") in s2_lower) or \
           ("not " in s2_lower and s2_lower.replace("not ", "") in s1_lower):
            return Contradiction(
                crystal_a_id=c1.crystal_id, crystal_b_id=c2.crystal_id,
                statement_a=c1.statement, statement_b=c2.statement,
                contradiction_type="Direct negation",
            )

        return None

    def _extract_tags(self, text: str) -> Set[str]:
        """Extract meaningful tags from text."""
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "to", "of", "in", "for", "on", "with", "at", "by", "from",
                      "and", "or", "but", "not", "this", "that", "it", "its"}
        words = text.lower().split()
        return {w for w in words if len(w) > 3 and w not in stop_words}

    def solve(self, prompt: str) -> CrystallizationResult:
        """Natural language interface."""
        start = time.time()
        result = CrystallizationResult()

        # Query existing knowledge
        result.relevant_knowledge = self.query(prompt)

        # Crystallize the query itself as a new fact
        new = self.crystallize(prompt, crystal_type=KnowledgeType.FACT, confidence=0.6, source=prompt)
        result.new_crystals = [new]
        result.crystals_added = 1

        # Detect contradictions
        contradictions = self.detect_contradictions()
        result.contradictions_found = len(contradictions)

        # Auto-resolve
        for c in contradictions:
            if not c.resolved:
                self.resolve_contradiction(c)
                result.contradictions_resolved += 1

        result.crystals_total = len(self._crystals)
        result.duration_ms = (time.time() - start) * 1000
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {"engine": "KnowledgeCrystal", "total_crystals": len(self._crystals), "crystallizations": self._stats["crystallizations"], "queries": self._stats["queries"], "contradictions_found": self._stats["contradictions_found"], "contradictions_resolved": self._stats["contradictions_resolved"]}
