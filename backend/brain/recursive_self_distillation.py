"""
Recursive Self-Distillation — Consensus Pattern Micro-Model Cache
═════════════════════════════════════════════════════════════════
After the Multi-LLM Council repeatedly solves a category of problem,
the system automatically distills the council's consensus patterns into
a lightweight local micro-model (pattern + rule set) stored in a
"skill cache". Future identical task categories bypass the council
entirely and use the distilled model — 100x faster, $0 cost.

Architecture:
  Council Solves → Pattern Extractor → Distillation → Skill Cache
  New Task → Category Match → Cache Hit → Instant Response
"""

import hashlib
import logging
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class SolveRecord:
    """Record of a single council solve for a task category."""
    task: str
    solution: str
    confidence: float = 0.0
    domain: str = "general"
    strategies_used: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class DistilledSkill:
    """A micro-model distilled from repeated council consensus."""
    skill_id: str = ""
    category: str = ""
    domain: str = "general"
    pattern_rules: List[str] = field(default_factory=list)
    template: str = ""
    keywords: Set[str] = field(default_factory=set)
    average_confidence: float = 0.0
    solve_count: int = 0
    hit_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)

    @property
    def hit_rate(self) -> float:
        total = self.solve_count + self.hit_count
        return self.hit_count / max(total, 1)

    def apply(self, task: str) -> str:
        """Apply the distilled skill to generate a response."""
        response = self.template
        # Simple template variable substitution
        response = response.replace("{task}", task)
        response = response.replace("{category}", self.category)
        self.hit_count += 1
        self.last_used = time.time()
        return response


@dataclass
class DistillationResult:
    """Result of a distillation attempt."""
    category: str = ""
    success: bool = False
    skill: Optional[DistilledSkill] = None
    records_analyzed: int = 0
    patterns_found: int = 0
    reason: str = ""


# ──────────────────────────────────────────────
# Pattern Extractor
# ──────────────────────────────────────────────

class PatternExtractor:
    """
    Extracts common structural patterns from multiple solutions
    to the same category of problem.
    """

    def extract_patterns(self, records: List[SolveRecord]) -> List[str]:
        """Extract recurring solution patterns from solve records."""
        if len(records) < 2:
            return []

        patterns = []

        # Extract common structural elements
        structure_patterns = self._extract_structural_patterns(records)
        patterns.extend(structure_patterns)

        # Extract common keywords/phrases
        keyword_patterns = self._extract_keyword_patterns(records)
        patterns.extend(keyword_patterns)

        return patterns

    def extract_template(self, records: List[SolveRecord]) -> str:
        """Create a generalized template from solution patterns."""
        if not records:
            return ""

        # Find the solution with highest confidence
        best = max(records, key=lambda r: r.confidence)
        template = best.solution

        # Generalize specific values into template variables
        # Replace specific numbers with {number}
        template = re.sub(r'\b\d{2,}\b', '{value}', template)

        return template

    def extract_keywords(self, records: List[SolveRecord]) -> Set[str]:
        """Extract the most distinctive keywords from solutions."""
        word_freq = Counter()
        for record in records:
            words = re.findall(r'\b\w{4,}\b', record.solution.lower())
            word_freq.update(words)

        # Keep words that appear in >50% of solutions
        threshold = len(records) * 0.5
        return {
            word for word, count in word_freq.items()
            if count >= threshold
        }

    def _extract_structural_patterns(self, records: List[SolveRecord]) -> List[str]:
        """Find common structural elements across solutions."""
        patterns = []

        # Check for common prefixes/structures
        has_code = sum(1 for r in records if "```" in r.solution)
        has_list = sum(1 for r in records if re.search(r'^\d+\.|\n-\s', r.solution))
        has_steps = sum(1 for r in records if "step" in r.solution.lower())

        threshold = len(records) * 0.6
        if has_code >= threshold:
            patterns.append("INCLUDES_CODE_BLOCK")
        if has_list >= threshold:
            patterns.append("USES_NUMBERED_LIST")
        if has_steps >= threshold:
            patterns.append("STEP_BY_STEP_FORMAT")

        return patterns

    def _extract_keyword_patterns(self, records: List[SolveRecord]) -> List[str]:
        """Extract keyword co-occurrence patterns."""
        patterns = []
        all_words = []
        for rec in records:
            words = set(re.findall(r'\b\w{4,}\b', rec.solution.lower()))
            all_words.append(words)

        # Find words common to all solutions
        if all_words:
            common = set.intersection(*all_words) if all_words else set()
            for word in list(common)[:10]:
                patterns.append(f"KEYWORD:{word}")

        return patterns


# ──────────────────────────────────────────────
# Skill Cache
# ──────────────────────────────────────────────

class SkillCache:
    """LRU cache of distilled skills with category-based lookup."""

    def __init__(self, max_skills: int = 500):
        self._skills: Dict[str, DistilledSkill] = {}
        self._category_index: Dict[str, str] = {}  # category → skill_id
        self._max_skills = max_skills

    def store(self, skill: DistilledSkill) -> None:
        """Store a distilled skill."""
        if len(self._skills) >= self._max_skills:
            self._evict_lru()

        self._skills[skill.skill_id] = skill
        self._category_index[skill.category.lower()] = skill.skill_id

    def lookup(self, category: str) -> Optional[DistilledSkill]:
        """Look up a skill by category."""
        skill_id = self._category_index.get(category.lower())
        if skill_id:
            return self._skills.get(skill_id)
        return None

    def lookup_fuzzy(self, task: str) -> Optional[DistilledSkill]:
        """Fuzzy match a task against stored skill keywords."""
        task_words = set(re.findall(r'\b\w{4,}\b', task.lower()))
        best_match = None
        best_overlap = 0

        for skill in self._skills.values():
            overlap = len(task_words & skill.keywords)
            if overlap > best_overlap and overlap >= 3:
                best_overlap = overlap
                best_match = skill

        return best_match

    @property
    def size(self) -> int:
        return len(self._skills)

    def get_stats(self) -> Dict[str, Any]:
        total_hits = sum(s.hit_count for s in self._skills.values())
        return {
            "cached_skills": self.size,
            "total_hits": total_hits,
            "categories": list(self._category_index.keys()),
        }

    def _evict_lru(self) -> None:
        """Evict the least recently used skill."""
        if not self._skills:
            return
        oldest = min(self._skills.values(), key=lambda s: s.last_used)
        self._category_index.pop(oldest.category.lower(), None)
        del self._skills[oldest.skill_id]


# ──────────────────────────────────────────────
# Self-Distillation Engine (Main Interface)
# ──────────────────────────────────────────────

class SelfDistillationEngine:
    """
    Automatically distills repeated council solutions into
    lightweight cached skills.

    Usage:
        engine = SelfDistillationEngine()

        # Record council solves
        for solve in council_results:
            engine.record_solve(solve.task, solve.solution, solve.confidence, "python")

        # Check if a new task can be answered from cache
        cached = engine.try_cached_response("How do I reverse a list in Python?")
        if cached:
            print(f"Instant answer: {cached}")
    """

    MIN_SOLVES_TO_DISTILL = 3   # Minimum solves before distillation triggers
    DISTILL_CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, min_solves: int = 3):
        self.MIN_SOLVES_TO_DISTILL = min_solves
        self._solve_buffer: Dict[str, List[SolveRecord]] = defaultdict(list)
        self._extractor = PatternExtractor()
        self._cache = SkillCache()
        self._total_distillations: int = 0
        self._cache_hits: int = 0

    def record_solve(
        self,
        task: str,
        solution: str,
        confidence: float = 0.0,
        domain: str = "general",
        category: str = "",
    ) -> Optional[DistillationResult]:
        """
        Record a council solve. If enough solves accumulate for a category,
        triggers automatic distillation.
        """
        if not category:
            category = self._categorize_task(task)

        record = SolveRecord(
            task=task,
            solution=solution,
            confidence=confidence,
            domain=domain,
        )
        self._solve_buffer[category].append(record)

        # Check if distillation threshold reached
        records = self._solve_buffer[category]
        if len(records) >= self.MIN_SOLVES_TO_DISTILL:
            high_conf = [r for r in records if r.confidence >= self.DISTILL_CONFIDENCE_THRESHOLD]
            if len(high_conf) >= self.MIN_SOLVES_TO_DISTILL:
                return self._distill(category, high_conf)

        return None

    def try_cached_response(self, task: str) -> Optional[str]:
        """Try to answer from a distilled skill cache."""
        category = self._categorize_task(task)
        skill = self._cache.lookup(category)

        if not skill:
            skill = self._cache.lookup_fuzzy(task)

        if skill:
            self._cache_hits += 1
            response = skill.apply(task)
            logger.info(
                f"Distillation cache HIT: category='{skill.category}' "
                f"(hits={skill.hit_count})"
            )
            self._try_record_metric("brain.distillation.cache_hit")
            return response

        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_distillations": self._total_distillations,
            "cache_hits": self._cache_hits,
            "buffer_categories": len(self._solve_buffer),
            "buffer_total_solves": sum(
                len(v) for v in self._solve_buffer.values()
            ),
            "cache": self._cache.get_stats(),
        }

    # ── Private Methods ──

    def _distill(
        self,
        category: str,
        records: List[SolveRecord],
    ) -> DistillationResult:
        """Perform distillation of accumulated solves into a cached skill."""
        patterns = self._extractor.extract_patterns(records)
        template = self._extractor.extract_template(records)
        keywords = self._extractor.extract_keywords(records)

        avg_conf = sum(r.confidence for r in records) / len(records)

        skill = DistilledSkill(
            skill_id=hashlib.sha256(category.encode()).hexdigest()[:12],
            category=category,
            domain=records[0].domain,
            pattern_rules=patterns,
            template=template,
            keywords=keywords,
            average_confidence=avg_conf,
            solve_count=len(records),
        )

        self._cache.store(skill)
        self._total_distillations += 1

        # Clear buffer for this category
        self._solve_buffer[category] = []

        logger.info(
            f"Distilled skill: '{category}' "
            f"({len(patterns)} patterns, {len(keywords)} keywords, "
            f"conf={avg_conf:.3f})"
        )

        return DistillationResult(
            category=category,
            success=True,
            skill=skill,
            records_analyzed=len(records),
            patterns_found=len(patterns),
        )

    def _categorize_task(self, task: str) -> str:
        """Simple task categorization based on keyword extraction."""
        task_lower = task.lower()

        categories = {
            "code_generation": ["write", "create", "implement", "build", "code"],
            "debugging": ["debug", "fix", "error", "bug", "issue"],
            "explanation": ["explain", "what is", "how does", "describe", "define"],
            "analysis": ["analyze", "review", "assess", "evaluate"],
            "optimization": ["optimize", "improve", "speed", "performance", "faster"],
            "translation": ["translate", "convert", "transform"],
        }

        for cat, keywords in categories.items():
            if any(kw in task_lower for kw in keywords):
                return cat

        return "general"

    def _try_record_metric(self, name: str) -> None:
        try:
            from telemetry.metrics import MetricsCollector
            MetricsCollector.get_instance().counter(name)
        except Exception:
            pass
