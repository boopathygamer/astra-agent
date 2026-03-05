"""
Mistake Lesson Engine — Learn From The System's Own Failures
────────────────────────────────────────────────────────────
Bridges the Bug Diary (memory.py) and Expert Reflection (expert_reflection.py)
into structured, teachable anti-pattern lessons.

Pipeline:
  Bug Diary FailureTuples → Cluster by category → Generate Anti-Pattern Lessons
  ExpertPrinciples → Attach universal axioms to lessons
  Recurring category weights → Rank by danger score

Each lesson teaches: "DON'T do this → HERE's why → DO this instead"
with visual red/green comparisons and flowchart diagrams.
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class AntiPatternLesson:
    """A single 'Don't Do This' lesson derived from real failures."""
    id: str = field(default_factory=lambda: f"apl-{uuid.uuid4().hex[:8]}")
    title: str = ""                    # e.g. "Never Trust Raw User Input"
    category: str = ""                 # e.g. "input_validation"
    bad_approach: str = ""             # ❌ The wrong way (with code/example)
    why_it_fails: str = ""             # 🔍 Root cause explanation
    correct_approach: str = ""         # ✅ The right way
    expert_principle: str = ""         # 🧠 Universal axiom
    danger_score: float = 0.0          # From recurring category weights (higher = more dangerous)
    visual_comparison: str = ""        # Side-by-side ❌ vs ✅ formatted text
    recovery_steps: List[str] = field(default_factory=list)  # Steps to fix if already done wrong
    source_failure_ids: List[str] = field(default_factory=list)  # IDs of FailureTuples used
    flowchart: str = ""                # Mermaid diagram showing the pitfall
    quiz_question: str = ""            # Test question for gamification
    quiz_answer: str = ""              # Correct answer


@dataclass
class MistakeCurriculum:
    """An ordered collection of anti-pattern lessons for a topic."""
    topic: str = ""
    lessons: List[AntiPatternLesson] = field(default_factory=list)
    total_danger_score: float = 0.0
    generated_at: float = field(default_factory=time.time)
    category_breakdown: Dict[str, int] = field(default_factory=dict)

    def get_most_dangerous(self, n: int = 3) -> List[AntiPatternLesson]:
        """Get the N most dangerous anti-patterns."""
        return sorted(self.lessons, key=lambda l: l.danger_score, reverse=True)[:n]

    def get_by_category(self, category: str) -> List[AntiPatternLesson]:
        """Get all lessons in a specific category."""
        return [l for l in self.lessons if l.category == category]


# ──────────────────────────────────────────────
# Lesson Templates
# ──────────────────────────────────────────────

_ANTI_PATTERN_VISUAL_TEMPLATE = """\
╔══════════════════════════════════════════════════════════════╗
║  ⚠️  ANTI-PATTERN: {title}
║  Danger Level: {danger_bar} ({danger_score:.1f}/10)
╠══════════════════════════════════════════════════════════════╣
║
║  ❌ THE WRONG WAY:
║  ─────────────────
║  {bad_approach}
║
║  🔍 WHY IT FAILS:
║  ─────────────────
║  {why_it_fails}
║
║  ✅ THE RIGHT WAY:
║  ─────────────────
║  {correct_approach}
║
║  🧠 EXPERT PRINCIPLE:
║  ─────────────────
║  {expert_principle}
║
╚══════════════════════════════════════════════════════════════╝"""

_DANGER_BARS = {
    1: "█░░░░░░░░░",
    2: "██░░░░░░░░",
    3: "███░░░░░░░",
    4: "████░░░░░░",
    5: "█████░░░░░",
    6: "██████░░░░",
    7: "███████░░░",
    8: "████████░░",
    9: "█████████░",
    10: "██████████",
}


def _danger_bar(score: float) -> str:
    """Convert a danger score (0-10) to a visual bar."""
    level = max(1, min(10, int(score)))
    return _DANGER_BARS.get(level, "█░░░░░░░░░")


# ──────────────────────────────────────────────
# Mistake Lesson Engine
# ──────────────────────────────────────────────

class MistakeLessonEngine:
    """
    Converts the system's stored failures and expert principles into
    structured anti-pattern lessons that teach users what NOT to do.

    Reads from:
      - MemoryManager.failures (FailureTuples from Bug Diary)
      - MemoryManager.principles (ExpertPrinciples from reflection)
      - MemoryManager.get_recurring_categories() (danger scoring)

    Produces:
      - AntiPatternLesson objects with visual comparisons
      - MistakeCurriculum ordered by danger score
    """

    def __init__(self, memory_manager=None, generate_fn: Optional[Callable] = None):
        """
        Args:
            memory_manager: MemoryManager instance with stored failures
            generate_fn: LLM generation function for enriching lessons
        """
        self.memory = memory_manager
        self.generate_fn = generate_fn
        self._lesson_cache: Dict[str, MistakeCurriculum] = {}
        logger.info("🎓 MistakeLessonEngine initialized")

    # ──────────────────────────────────────
    # Core Lesson Generation
    # ──────────────────────────────────────

    def generate_curriculum(self, topic: str = "") -> MistakeCurriculum:
        """
        Generate a complete anti-pattern curriculum from stored failures.

        Args:
            topic: Optional topic filter. If empty, uses ALL failures.

        Returns:
            MistakeCurriculum with ordered lessons
        """
        curriculum = MistakeCurriculum(topic=topic or "all")

        if not self.memory:
            logger.warning("No memory manager available — generating from LLM only")
            if self.generate_fn:
                curriculum.lessons = self._generate_lessons_from_llm(topic)
            return curriculum

        # Step 1: Get relevant failures
        if topic:
            failures = self.memory.retrieve_similar_failures(topic, n_results=20)
        else:
            failures = self.memory.failures[-50:]  # Latest 50

        if not failures:
            logger.info(f"No failures found for topic '{topic}' — generating from LLM")
            if self.generate_fn:
                curriculum.lessons = self._generate_lessons_from_llm(topic)
            return curriculum

        # Step 2: Cluster failures by category
        clusters = self._cluster_failures(failures)

        # Step 3: Get danger scores from recurring categories
        recurring = dict(self.memory.get_recurring_categories(top_n=20))

        # Step 4: Get expert principles
        principles_by_domain = {}
        for p in self.memory.principles:
            principles_by_domain.setdefault(p.domain, []).append(p)

        # Step 5: Generate a lesson for each cluster
        for category, category_failures in clusters.items():
            lesson = self._generate_lesson_from_failures(
                category=category,
                failures=category_failures,
                danger_score=recurring.get(category, 1.0),
                principles=principles_by_domain.get(category, [])
                           + principles_by_domain.get("general", []),
            )
            if lesson:
                curriculum.lessons.append(lesson)
                curriculum.category_breakdown[category] = len(category_failures)

        # Step 6: Sort by danger score (most dangerous first)
        curriculum.lessons.sort(key=lambda l: l.danger_score, reverse=True)
        curriculum.total_danger_score = sum(l.danger_score for l in curriculum.lessons)

        # Cache
        self._lesson_cache[topic] = curriculum

        logger.info(
            f"🎓 Generated curriculum: {len(curriculum.lessons)} anti-pattern lessons, "
            f"total danger={curriculum.total_danger_score:.1f}"
        )
        return curriculum

    def get_lessons_for_topic(self, topic: str, max_lessons: int = 5) -> List[AntiPatternLesson]:
        """
        Get the most relevant anti-pattern lessons for a tutoring session topic.

        Returns lessons sorted by danger score, limited to max_lessons.
        """
        # Check cache first
        if topic in self._lesson_cache:
            curriculum = self._lesson_cache[topic]
        else:
            curriculum = self.generate_curriculum(topic)

        return curriculum.get_most_dangerous(max_lessons)

    def format_lesson_visual(self, lesson: AntiPatternLesson) -> str:
        """Format a lesson into a rich visual display."""
        # Indent multi-line content
        def indent(text: str, prefix: str = "║  ") -> str:
            lines = text.split("\n")
            return ("\n" + prefix).join(lines)

        return _ANTI_PATTERN_VISUAL_TEMPLATE.format(
            title=lesson.title,
            danger_bar=_danger_bar(lesson.danger_score),
            danger_score=lesson.danger_score,
            bad_approach=indent(lesson.bad_approach),
            why_it_fails=indent(lesson.why_it_fails),
            correct_approach=indent(lesson.correct_approach),
            expert_principle=indent(lesson.expert_principle or "Apply defensive programming."),
        )

    def format_lesson_for_prompt(self, lesson: AntiPatternLesson) -> str:
        """Format lesson as context for LLM teaching prompts."""
        return (
            f"⚠️ ANTI-PATTERN LESSON: {lesson.title}\n"
            f"Category: {lesson.category} | Danger: {lesson.danger_score:.1f}/10\n"
            f"❌ BAD: {lesson.bad_approach}\n"
            f"🔍 WHY: {lesson.why_it_fails}\n"
            f"✅ GOOD: {lesson.correct_approach}\n"
            f"🧠 PRINCIPLE: {lesson.expert_principle}\n"
        )

    # ──────────────────────────────────────
    # Internal — Clustering & Generation
    # ──────────────────────────────────────

    def _cluster_failures(self, failures) -> Dict[str, list]:
        """Group failures by their category."""
        clusters = defaultdict(list)
        for f in failures:
            cat = f.category or "uncategorized"
            clusters[cat].append(f)
        return dict(clusters)

    def _generate_lesson_from_failures(
        self,
        category: str,
        failures: list,
        danger_score: float,
        principles: list,
    ) -> Optional[AntiPatternLesson]:
        """
        Synthesize a single anti-pattern lesson from a cluster of related failures.
        """
        lesson = AntiPatternLesson(
            category=category,
            danger_score=min(10.0, danger_score),
            source_failure_ids=[f.id for f in failures],
        )

        # Use the most severe failure as the primary example
        primary = max(failures, key=lambda f: f.severity)

        # Basic fields from the failure data
        lesson.bad_approach = primary.solution or primary.action or "Unknown approach"
        lesson.why_it_fails = primary.root_cause or primary.observation or "Unknown cause"
        lesson.correct_approach = primary.fix or "Apply the correct pattern"

        # Attach expert principle if available
        if principles:
            best_principle = principles[0]
            lesson.expert_principle = best_principle.actionable_rule

        # Generate rich content via LLM if available
        if self.generate_fn:
            lesson = self._enrich_lesson_with_llm(lesson, failures, principles)
        else:
            # Fallback: generate title from category
            lesson.title = self._generate_title_from_category(category)
            lesson.visual_comparison = self.format_lesson_visual(lesson)
            lesson.recovery_steps = [
                f"Check your code for {category} issues",
                f"Apply fix: {lesson.correct_approach}",
                "Add regression test to prevent recurrence",
            ]
            # Generate quiz question
            lesson.quiz_question = (
                f"What is wrong with this approach: {lesson.bad_approach[:100]}?"
            )
            lesson.quiz_answer = lesson.why_it_fails[:200]

        # Generate anti-pattern flowchart
        lesson.flowchart = self._generate_anti_pattern_flowchart(lesson)

        return lesson

    def _enrich_lesson_with_llm(
        self,
        lesson: AntiPatternLesson,
        failures: list,
        principles: list,
    ) -> AntiPatternLesson:
        """Use LLM to generate rich lesson content."""
        # Compile failure evidence
        evidence = "\n".join(
            f"- Task: {f.task}, Error: {f.observation}, Root Cause: {f.root_cause}, Fix: {f.fix}"
            for f in failures[:5]
        )

        principle_text = ""
        if principles:
            principle_text = "\n".join(
                f"- {p.actionable_rule}" for p in principles[:3]
            )

        prompt = f"""\
You are an expert teacher creating an anti-pattern lesson from real system failures.

CATEGORY: {lesson.category}
DANGER SCORE: {lesson.danger_score:.1f}/10

FAILURE EVIDENCE:
{evidence}

EXPERT PRINCIPLES:
{principle_text or "None available"}

Generate a JSON object with these exact keys:
{{
  "title": "A memorable, punchy title (e.g. 'Never Trust Raw User Input')",
  "bad_approach": "The wrong approach explained clearly with a code/pseudocode example (2-3 lines)",
  "why_it_fails": "One clear paragraph explaining the root cause",
  "correct_approach": "The correct pattern with a code/pseudocode example (2-3 lines)",
  "expert_principle": "One universal rule to always follow",
  "recovery_steps": ["Step 1 to fix if already done wrong", "Step 2", "Step 3"],
  "quiz_question": "A test question about this anti-pattern",
  "quiz_answer": "The correct answer"
}}
"""
        try:
            result = self._call_llm(prompt)
            import json
            import re
            match = re.search(r'\{.*\}', result, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                lesson.title = data.get("title", lesson.title)
                lesson.bad_approach = data.get("bad_approach", lesson.bad_approach)
                lesson.why_it_fails = data.get("why_it_fails", lesson.why_it_fails)
                lesson.correct_approach = data.get("correct_approach", lesson.correct_approach)
                lesson.expert_principle = data.get("expert_principle", lesson.expert_principle)
                lesson.recovery_steps = data.get("recovery_steps", lesson.recovery_steps)
                lesson.quiz_question = data.get("quiz_question", "")
                lesson.quiz_answer = data.get("quiz_answer", "")
        except Exception as e:
            logger.warning(f"LLM enrichment failed: {e}")
            lesson.title = self._generate_title_from_category(lesson.category)

        # Always update visual comparison
        lesson.visual_comparison = self.format_lesson_visual(lesson)
        return lesson

    def _generate_lessons_from_llm(self, topic: str) -> List[AntiPatternLesson]:
        """Generate anti-pattern lessons purely from LLM when no failures exist."""
        if not self.generate_fn:
            return []

        prompt = f"""\
You are an expert teacher. Generate 3 common anti-pattern lessons for the topic: "{topic}".

For each, output a JSON array of objects with keys:
[
  {{
    "title": "Punchy anti-pattern title",
    "category": "error_category",
    "bad_approach": "The wrong way with example",
    "why_it_fails": "Clear explanation of why",
    "correct_approach": "The right way with example",
    "expert_principle": "Universal rule",
    "danger_score": 7.5,
    "quiz_question": "Test question",
    "quiz_answer": "Correct answer"
  }}
]
"""
        try:
            result = self._call_llm(prompt)
            import json
            import re
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                items = json.loads(match.group(0))
                lessons = []
                for item in items[:5]:
                    lesson = AntiPatternLesson(
                        title=item.get("title", ""),
                        category=item.get("category", "general"),
                        bad_approach=item.get("bad_approach", ""),
                        why_it_fails=item.get("why_it_fails", ""),
                        correct_approach=item.get("correct_approach", ""),
                        expert_principle=item.get("expert_principle", ""),
                        danger_score=float(item.get("danger_score", 5.0)),
                        quiz_question=item.get("quiz_question", ""),
                        quiz_answer=item.get("quiz_answer", ""),
                    )
                    lesson.visual_comparison = self.format_lesson_visual(lesson)
                    lesson.flowchart = self._generate_anti_pattern_flowchart(lesson)
                    lessons.append(lesson)
                return lessons
        except Exception as e:
            logger.warning(f"LLM lesson generation failed: {e}")

        return []

    def _generate_anti_pattern_flowchart(self, lesson: AntiPatternLesson) -> str:
        """Generate a Mermaid flowchart showing the anti-pattern decision tree."""
        safe_title = lesson.title.replace('"', "'")
        safe_bad = (lesson.bad_approach[:60]).replace('"', "'").replace("\n", " ")
        safe_good = (lesson.correct_approach[:60]).replace('"', "'").replace("\n", " ")
        safe_why = (lesson.why_it_fails[:50]).replace('"', "'").replace("\n", " ")

        return f"""\
graph TD
    START["🎯 Task: {lesson.category}"] --> DECISION{{{"Choose Approach"}}}
    DECISION -->|"❌ Bad Path"| BAD["{safe_bad}"]
    DECISION -->|"✅ Good Path"| GOOD["{safe_good}"]
    BAD --> FAIL["💥 FAILURE: {safe_why}"]
    GOOD --> SUCCESS["🎉 SUCCESS"]
    FAIL -->|"🔧 Recovery"| FIX["Apply fix + add tests"]
    FIX --> SUCCESS

    style BAD fill:#ff4444,color:#fff
    style FAIL fill:#cc0000,color:#fff
    style GOOD fill:#44bb44,color:#fff
    style SUCCESS fill:#00aa00,color:#fff
    style DECISION fill:#4488ff,color:#fff"""

    def _generate_title_from_category(self, category: str) -> str:
        """Generate a readable title from a failure category."""
        titles = {
            "input_validation": "Never Trust Raw User Input",
            "null_check": "Always Guard Against Null Values",
            "type_error": "Type Mismatches Are Silent Killers",
            "logic": "Subtle Logic Bugs Hide In Plain Sight",
            "syntax": "Syntax Errors Break Everything",
            "reasoning": "Flawed Reasoning Leads To Wrong Solutions",
            "concurrency": "Shared State Without Locks Is A Trap",
            "security": "Security Shortcuts Are Never Worth It",
            "performance": "Premature Optimization vs Real Bottlenecks",
            "uncategorized": "Common Mistakes To Avoid",
        }
        return titles.get(category, f"Anti-Pattern: {category.replace('_', ' ').title()}")

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM safely."""
        if not self.generate_fn:
            return ""
        try:
            result = self.generate_fn(prompt)
            if hasattr(result, 'answer'):
                return result.answer
            return str(result)
        except Exception as e:
            logger.error(f"LLM call failed in MistakeLessonEngine: {e}")
            return ""
