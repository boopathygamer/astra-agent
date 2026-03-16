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


@dataclass
class MisconceptionPreempt:
    """
    A preemptive misconception alert shown BEFORE teaching a concept.

    Instead of waiting for the student to make a mistake, this proactively
    says: "90% of people think X, but actually Y. Let me show you why."
    """
    id: str = field(default_factory=lambda: f"mp-{uuid.uuid4().hex[:8]}")
    topic: str = ""
    wrong_belief: str = ""          # What most people wrongly think
    truth: str = ""                 # What is actually correct
    why_people_believe_it: str = "" # Why this misconception is so common
    reveal_question: str = ""       # Socratic question to help student discover the truth
    prevalence: str = "common"      # common, very_common, universal
    source: str = "knowledge_base"  # knowledge_base, llm_generated, failure_history

    def to_teaching_block(self) -> str:
        """Format as a teaching-ready preemption block."""
        prevalence_map = {
            "common": "Many people",
            "very_common": "Most people",
            "universal": "Almost everyone",
        }
        people = prevalence_map.get(self.prevalence, "Many people")
        return (
            f"\n🧠 **BEFORE WE START — Common Trap:**\n"
            f"{people} believe: \"{self.wrong_belief}\"\n"
            f"But actually: \"{self.truth}\"\n"
            f"{'💡 Why this trap exists: ' + self.why_people_believe_it if self.why_people_believe_it else ''}\n"
            f"{'🦉 Think about it: ' + self.reveal_question if self.reveal_question else ''}\n"
        )


@dataclass
class RootCauseChain:
    """
    A full chain showing how a wrong assumption leads to failure,
    and how to trace back to the root cause and fix.

    Chain: assumption → mistake → symptom → root_cause → fix → principle
    """
    id: str = field(default_factory=lambda: f"rcc-{uuid.uuid4().hex[:8]}")
    topic: str = ""
    assumption: str = ""     # The initial wrong assumption
    mistake: str = ""        # The mistake that follows from the assumption
    symptom: str = ""        # What the student observes (the visible error)
    root_cause: str = ""     # The real underlying cause
    fix: str = ""            # How to fix it
    principle: str = ""      # The universal principle to remember
    mermaid_diagram: str = "" # Visual chain diagram

    def to_teaching_block(self) -> str:
        """Format as a detailed teaching chain."""
        return (
            f"\n🔗 **ROOT-CAUSE CHAIN — Trace the Problem:**\n"
            f"  1️⃣ **Assumption:** {self.assumption}\n"
            f"  2️⃣ **Mistake:** {self.mistake}\n"
            f"  3️⃣ **Symptom:** {self.symptom}\n"
            f"  4️⃣ **Root Cause:** {self.root_cause}\n"
            f"  5️⃣ **Fix:** {self.fix}\n"
            f"  6️⃣ **Principle:** 🧠 {self.principle}\n"
        )

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram of the chain."""
        if self.mermaid_diagram:
            return self.mermaid_diagram

        def safe(text: str) -> str:
            return text[:50].replace('"', "'").replace('\n', ' ')

        return (
            f"graph TD\n"
            f'    A["💭 Assumption: {safe(self.assumption)}"] --> B["❌ Mistake: {safe(self.mistake)}"]\n'
            f'    B --> C["⚠️ Symptom: {safe(self.symptom)}"]\n'
            f'    C --> D["🔍 Root Cause: {safe(self.root_cause)}"]\n'
            f'    D --> E["🔧 Fix: {safe(self.fix)}"]\n'
            f'    E --> F["🧠 Principle: {safe(self.principle)}"]\n'
            f"\n"
            f"    style A fill:#ff9944,color:#fff\n"
            f"    style B fill:#ff4444,color:#fff\n"
            f"    style C fill:#ff6644,color:#fff\n"
            f"    style D fill:#4488ff,color:#fff\n"
            f"    style E fill:#44bb44,color:#fff\n"
            f"    style F fill:#00aa00,color:#fff\n"
        )


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

    # ──────────────────────────────────────
    # Misconception Preemption
    # ──────────────────────────────────────

    def generate_preemptive_misconceptions(
        self, topic: str, max_items: int = 3,
    ) -> List[MisconceptionPreempt]:
        """
        Generate preemptive misconception alerts for a topic.

        These are shown BEFORE teaching to prevent the student from
        falling into common traps that "everyone" falls into.
        """
        results: List[MisconceptionPreempt] = []

        # Source 1: Mine from failure history
        if self.memory:
            try:
                failures = self.memory.retrieve_similar_failures(topic, n_results=10)
                # Group by root cause to find recurring misconceptions
                root_causes: Dict[str, int] = {}
                for f in failures:
                    rc = getattr(f, 'root_cause', '') or ''
                    if rc and len(rc) > 10:
                        root_causes[rc] = root_causes.get(rc, 0) + 1

                for rc, count in sorted(root_causes.items(), key=lambda x: -x[1])[:2]:
                    results.append(MisconceptionPreempt(
                        topic=topic,
                        wrong_belief=rc,
                        truth=getattr(failures[0], 'fix', '') or "Apply the correct pattern",
                        prevalence="very_common" if count >= 3 else "common",
                        source="failure_history",
                    ))
            except Exception as e:
                logger.warning(f"Failed to mine misconceptions from failures: {e}")

        # Source 2: Generate via LLM
        if self.generate_fn and len(results) < max_items:
            try:
                prompt = (
                    f"What are the top {max_items - len(results)} most common misconceptions "
                    f"that beginners have about: {topic}?\n\n"
                    f"For each, explain:\n"
                    f"1. What people wrongly believe\n"
                    f"2. What is actually true\n"
                    f"3. Why people fall for this misconception\n"
                    f"4. A Socratic question to help them discover the truth\n\n"
                    f"Format as JSON array:\n"
                    f'[{{"wrong_belief": "...", "truth": "...", '
                    f'"why_common": "...", "reveal_question": "..."}}]\n'
                    f"Output ONLY the JSON array."
                )
                result = self._call_llm(prompt)
                import json
                import re
                match = re.search(r'\[.*\]', result, re.DOTALL)
                if match:
                    items = json.loads(match.group(0))
                    for item in items[:max_items - len(results)]:
                        results.append(MisconceptionPreempt(
                            topic=topic,
                            wrong_belief=item.get("wrong_belief", ""),
                            truth=item.get("truth", ""),
                            why_people_believe_it=item.get("why_common", ""),
                            reveal_question=item.get("reveal_question", ""),
                            prevalence="common",
                            source="llm_generated",
                        ))
            except Exception as e:
                logger.warning(f"LLM misconception generation failed: {e}")

        logger.info(f"🧠 Generated {len(results)} preemptive misconceptions for '{topic}'")
        return results

    # ──────────────────────────────────────
    # Root-Cause Chain Builder
    # ──────────────────────────────────────

    def build_root_cause_chain(
        self, lesson: AntiPatternLesson,
    ) -> RootCauseChain:
        """
        Build a full root-cause chain from an anti-pattern lesson.

        Chain: assumption → mistake → symptom → root_cause → fix → principle

        This shows students the FULL path from wrong thinking to correct
        understanding, not just "bad → good".
        """
        chain = RootCauseChain(
            topic=lesson.category,
            mistake=lesson.bad_approach,
            root_cause=lesson.why_it_fails,
            fix=lesson.correct_approach,
            principle=lesson.expert_principle or "Apply defensive programming.",
        )

        # Try to enrich via LLM
        if self.generate_fn:
            try:
                prompt = (
                    f"Given this anti-pattern:\n"
                    f"  Bad approach: {lesson.bad_approach}\n"
                    f"  Why it fails: {lesson.why_it_fails}\n"
                    f"  Fix: {lesson.correct_approach}\n\n"
                    f"Fill in the FULL root-cause chain:\n"
                    f'{{"assumption": "what wrong assumption led to this", '
                    f'"symptom": "what the user actually sees/experiences when this goes wrong"}}\n'
                    f"Output ONLY the JSON object."
                )
                result = self._call_llm(prompt)
                import json
                import re
                match = re.search(r'\{.*\}', result, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    chain.assumption = data.get("assumption", "Incorrect assumption")
                    chain.symptom = data.get("symptom", "Unexpected failure")
            except Exception as e:
                logger.warning(f"Root-cause chain enrichment failed: {e}")
                chain.assumption = "Incorrect assumption about how this works"
                chain.symptom = "Unexpected error or failure"
        else:
            chain.assumption = "Incorrect assumption about how this works"
            chain.symptom = "Unexpected error or failure"

        # Generate Mermaid diagram
        chain.mermaid_diagram = chain.to_mermaid()
        return chain

    # ──────────────────────────────────────
    # Progressive Disclosure Formatter
    # ──────────────────────────────────────

    def format_progressive_disclosure(
        self, lesson: AntiPatternLesson,
    ) -> List[Dict[str, str]]:
        """
        Format an anti-pattern lesson as a progressive disclosure sequence.

        Instead of showing everything at once, reveal information in stages:
          Stage 1: Show the wrong code/approach
          Stage 2: Ask student to find the bug
          Stage 3: Reveal the symptom
          Stage 4: Guide to the root cause
          Stage 5: Show the fix
          Stage 6: State the principle

        Returns a list of stage dicts for the tutor to present one at a time.
        """
        stages = [
            {
                "stage": "1_challenge",
                "emoji": "🔍",
                "title": "Spot the Problem",
                "content": (
                    f"Look at this code/approach carefully:\n"
                    f"```\n{lesson.bad_approach}\n```\n"
                    f"Can you spot what's wrong with it? Take a moment to think..."
                ),
                "wait_for_student": True,
            },
            {
                "stage": "2_hint",
                "emoji": "💡",
                "title": "Here's a Hint",
                "content": (
                    f"Think about what happens when: {lesson.why_it_fails[:80]}...\n"
                    f"What would the user experience?"
                ),
                "wait_for_student": True,
            },
            {
                "stage": "3_reveal",
                "emoji": "⚠️",
                "title": "The Problem",
                "content": (
                    f"The issue is:\n{lesson.why_it_fails}\n\n"
                    f"Danger level: {'🔴' * max(1, int(lesson.danger_score / 2))}"
                ),
                "wait_for_student": False,
            },
            {
                "stage": "4_fix",
                "emoji": "✅",
                "title": "The Correct Approach",
                "content": (
                    f"Here's how to do it right:\n"
                    f"```\n{lesson.correct_approach}\n```"
                ),
                "wait_for_student": False,
            },
            {
                "stage": "5_principle",
                "emoji": "🧠",
                "title": "Remember This Principle",
                "content": (
                    f"**Universal Principle:**\n"
                    f"{lesson.expert_principle or 'Always validate, always test, always handle errors.'}\n\n"
                    f"🎯 Can you think of another scenario where this principle applies?"
                ),
                "wait_for_student": True,
            },
        ]

        # Add recovery steps if available
        if lesson.recovery_steps:
            recovery_content = "If you've already made this mistake, here's how to fix it:\n"
            for i, step in enumerate(lesson.recovery_steps, 1):
                recovery_content += f"  {i}. {step}\n"
            stages.append({
                "stage": "6_recovery",
                "emoji": "🔧",
                "title": "Recovery Plan",
                "content": recovery_content,
                "wait_for_student": False,
            })

        return stages

