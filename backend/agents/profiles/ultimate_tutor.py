"""
Ultimate Tutor Engine — Unified Expert-Level Teaching System
═════════════════════════════════════════════════════════════
Merges three specialized tutors into one master engine:

  🦉 Socratic Auto-Tutor    → Deep Web Research bootstrapping + strict Socratic dialogue
  🎮 Gamified Tutor Engine   → XP, Levels, Achievements, Streaks, Challenge Modes
  🎓 Expert Tutor Engine     → 9 adaptive teaching techniques + uncertainty detection

Teaching Techniques (9 total):
  🧪 Feynman          — Explain simply with analogies
  🏗️ Scaffolding      — Build knowledge layer by layer
  🦉 Socratic         — Guide via probing questions
  🌉 Analogy Bridge   — Connect unknowns to existing knowledge
  🧩 Chunking         — Break massive topics into micro-lessons
  🚫 Anti-Pattern     — Teach via "Don't Do This" warnings
  📊 Visual Flowchart — Teach with Mermaid diagrams
  🎮 Game Challenge   — Gamified quiz/challenge mode
  🔬 Deep Socratic    — Auto-research + strict Socratic (NEW: merged from SocraticTutor)

Key Innovation:
  If the LLM response shows uncertainty, the engine AUTOMATICALLY triggers
  deep web + social research and weaves expert knowledge into coaching.
  The Deep Socratic mode pre-loads a full Graph-RAG intelligence dossier
  before starting the Socratic questioning loop.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# Re-export gamification system from internal module
# (Previously a separate profile, now an implementation detail)
# ══════════════════════════════════════════════════════════════

from agents.profiles.gamified_tutor import (
    PlayerLevel,
    ChallengeMode,
    LEVEL_THRESHOLDS,
    LEVEL_STARS,
    XP_REWARDS,
    ACHIEVEMENT_DEFINITIONS,
    Achievement,
    PlayerState,
    ChallengeQuestion,
    Challenge,
    GamifiedTutorEngine,
    render_dashboard,
    render_achievement_unlocked,
    render_level_up,
    render_challenge_result,
)


# ══════════════════════════════════════════════════════════════
# Teaching Technique Enum (9 techniques — expanded)
# ══════════════════════════════════════════════════════════════

class TeachingTechnique(Enum):
    FEYNMAN = "feynman"
    SCAFFOLDING = "scaffolding"
    SOCRATIC = "socratic"
    ANALOGY_BRIDGE = "analogy_bridge"
    CHUNKING = "chunking"
    ANTI_PATTERN = "anti_pattern"
    VISUAL_FLOWCHART = "visual_flowchart"
    GAME_CHALLENGE = "game_challenge"
    DEEP_SOCRATIC = "deep_socratic"       # NEW: merged from SocraticTutor


class StudentLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

@dataclass
class DiagnosticResult:
    """Result of diagnosing the student's current level."""
    level: StudentLevel = StudentLevel.BEGINNER
    confidence: float = 0.0
    knowledge_gaps: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)


@dataclass
class ResearchIntel:
    """Teaching material compiled from deep research."""
    topic: str = ""
    eli5_explanations: List[str] = field(default_factory=list)
    expert_insights: List[str] = field(default_factory=list)
    real_world_examples: List[str] = field(default_factory=list)
    practice_problems: List[str] = field(default_factory=list)
    academic_findings: List[str] = field(default_factory=list)
    social_wisdom: List[str] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class TutoringSession:
    """State for an active tutoring session."""
    session_id: str = ""
    topic: str = ""
    student_level: StudentLevel = StudentLevel.BEGINNER
    current_technique: TeachingTechnique = TeachingTechnique.SCAFFOLDING
    research_intel: Optional[ResearchIntel] = None
    research_triggered: bool = False
    history: List[Dict[str, str]] = field(default_factory=list)
    diagnostic: Optional[DiagnosticResult] = None
    lesson_plan: List[str] = field(default_factory=list)
    current_lesson_step: int = 0
    confidence_scores: List[float] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    # Mistake-Based Teaching
    anti_pattern_lessons: List[Any] = field(default_factory=list)
    mistake_curriculum: Any = None
    anti_patterns_shown: int = 0
    # Gamification
    player_state: Any = None
    active_challenge: Any = None
    game_engine: Any = None
    # Deep Socratic (merged from SocraticTutor)
    deep_socratic_dossier_path: Optional[Path] = None
    deep_socratic_intel: str = ""


# ══════════════════════════════════════════════════════════════
# Confidence / Uncertainty Detection
# ══════════════════════════════════════════════════════════════

_UNCERTAINTY_PATTERNS = [
    r"\bi(?:'m| am) not (?:entirely |completely |100%? )?sure\b",
    r"\bi(?:'m| am) not (?:entirely )?certain\b",
    r"\bi think\b(?! you)",
    r"\bit(?:'s| is) possible that\b",
    r"\bi believe\b", r"\bperhaps\b", r"\bprobably\b",
    r"\bmight be\b", r"\bcould be\b",
    r"\bI don'?t have (?:enough |sufficient )?(?:information|knowledge|data)\b",
    r"\bI(?:'m| am) not (?:an )?expert\b",
    r"\bmy (?:knowledge|training|data) (?:is |was )?(?:limited|cut ?off)\b",
    r"\bI (?:can'?t|cannot) (?:verify|confirm|guarantee)\b",
    r"\bgenerally speaking\b", r"\bin general\b",
    r"\bas far as I know\b", r"\bto the best of my knowledge\b",
    r"\byou (?:should|might want to) (?:consult|check|verify|look up)\b",
]

_VAGUE_PATTERNS = [
    r"\bsome (?:people|experts|sources) (?:say|think|believe)\b",
    r"\bit depends\b",
    r"\bthere are (?:many|various|different) (?:ways|approaches|methods)\b",
    r"\bthis is a complex topic\b",
    r"\bthe (?:answer|topic) is (?:nuanced|complex|multifaceted)\b",
]

_compiled_uncertainty = [re.compile(p, re.IGNORECASE) for p in _UNCERTAINTY_PATTERNS]
_compiled_vague = [re.compile(p, re.IGNORECASE) for p in _VAGUE_PATTERNS]


def detect_uncertainty(response: str) -> Tuple[float, List[str]]:
    """Analyze an LLM response for uncertainty signals. Score > 0.4 triggers research."""
    matched = []
    for pattern in _compiled_uncertainty:
        if pattern.search(response):
            matched.append(f"uncertainty: {pattern.pattern[:40]}")
    for pattern in _compiled_vague:
        if pattern.search(response):
            matched.append(f"vague: {pattern.pattern[:40]}")
    if len(response.split()) < 30:
        matched.append("very_short_response")

    uncertainty_weight = sum(1 for m in matched if m.startswith("uncertainty"))
    vague_weight = sum(0.5 for m in matched if m.startswith("vague"))
    short_weight = 0.3 if "very_short_response" in matched else 0.0
    score = min(1.0, uncertainty_weight * 0.15 + vague_weight * 0.15 + short_weight)
    return score, matched


# ══════════════════════════════════════════════════════════════
# Teaching Technique Prompts (9 total)
# ══════════════════════════════════════════════════════════════

_TECHNIQUE_PROMPTS = {
    TeachingTechnique.FEYNMAN: """\
🧪 FEYNMAN TECHNIQUE MODE:
You are teaching using the Feynman Technique — the gold standard for deep understanding.
Rules:
1. Explain the concept as if teaching a smart 12-year-old
2. Use REAL-WORLD ANALOGIES for every abstract concept
3. When you hit something complex, break it into simpler sub-concepts
4. Use "Imagine you're..." or "Think of it like..." frequently
5. After explaining, ask: "Can you explain this back to me in your own words?"
6. If the student's explanation has gaps, gently point them out
7. NO jargon without immediately defining it with an analogy""",

    TeachingTechnique.SCAFFOLDING: """\
🏗️ SCAFFOLDING MODE:
You are building knowledge layer by layer, like constructing a building.
Rules:
1. Start with the FOUNDATION — what does the student already know?
2. Each new concept builds on the PREVIOUS one — never skip a level
3. Provide a "knowledge checkpoint" after every 2-3 concepts
4. If the student fails a checkpoint, go back ONE layer and reinforce
5. Use this pattern: Foundation → Core Concept → Application → Integration
6. Give specific examples at each layer
7. End each message with: "Before we go deeper, let me check: [checkpoint question]" """,

    TeachingTechnique.SOCRATIC: """\
🦉 SOCRATIC METHOD MODE:
You are a strict Socratic professor who NEVER gives direct answers.
Rules:
1. NEVER tell them the answer directly
2. Ask a leading question that forces them to discover the answer
3. When they answer correctly, praise them: "Excellent! Now consider..."
4. When they answer wrong, don't say "wrong" — instead ask a clarifying question
5. Break the problem into smaller sub-questions they can reason through
6. Your goal: make the student feel like THEY discovered the knowledge
7. Only reveal information after they've attempted to reason through it""",

    TeachingTechnique.ANALOGY_BRIDGE: """\
🌉 ANALOGY BRIDGE MODE:
You are connecting unknown concepts to things the student already understands.
Rules:
1. ALWAYS start by asking what the student is already familiar with
2. Build BRIDGES from their existing knowledge to new concepts
3. Every new concept gets at least TWO analogies from different domains
4. Use "It's like...", "Think of it as...", "Remember how X works? This is similar because..."
5. After the bridge, test it: "Where does the analogy break down?"
6. This forces deeper understanding than surface-level comparison
7. Use visual/spatial analogies when possible (maps, buildings, rivers)""",

    TeachingTechnique.CHUNKING: """\
🧩 CHUNKING MODE:
You are breaking a massive topic into tiny, digestible micro-lessons.
Rules:
1. Split the entire topic into 5-7 numbered CHUNKS
2. Present ONLY ONE chunk at a time — don't overwhelm
3. Each chunk should take ~2 minutes to understand
4. Format: [Chunk Title] → [Core Idea in 1 sentence] → [Example] → [Practice]
5. After each chunk: "Ready for the next piece of the puzzle?"
6. At the end, show how ALL chunks connect into the complete picture
7. Use progress indicators: "Chunk 3/6: [Title]" """,

    TeachingTechnique.ANTI_PATTERN: """\
🚫 ANTI-PATTERN MODE — "DON'T DO THIS" TEACHING:
You are teaching by showing what NOT to do, based on real system failures.
Rules:
1. Start EVERY lesson with a concrete BAD example — show the mistake first
2. Use ❌ and ✅ visual markers: "❌ BAD: ..." vs "✅ GOOD: ..."
3. Explain WHY the bad approach fails with specific technical reasons
4. Show the CORRECT approach as a direct contrast
5. State the universal principle/axiom that prevents this mistake
6. Ask: "Can you spot another scenario where this anti-pattern could appear?"
7. Use red/green metaphors: "This is a RED FLAG because..."
8. Include a recovery plan: "If you already made this mistake, here's how to fix it"
9. Rank dangers: "This is a CRITICAL / HIGH / MEDIUM severity anti-pattern" """,

    TeachingTechnique.VISUAL_FLOWCHART: """\
📊 VISUAL FLOWCHART MODE — TEACH WITH DIAGRAMS:
You are teaching by creating visual flowcharts and diagrams.
Rules:
1. For EVERY concept, provide a Mermaid flowchart diagram in ```mermaid blocks
2. Use decision flowcharts for "when to use A vs B" questions
3. Use process flowcharts for step-by-step procedures
4. Use concept maps to show how ideas relate to each other
5. Color-code: green for good paths, red for bad paths, blue for decisions
6. Keep diagrams focused — 6-12 nodes maximum
7. After each diagram, ask: "Does this diagram make the relationship clear?"
8. Provide ASCII art fallbacks for key visualizations
9. Use the diagram as the PRIMARY teaching tool, with text as support""",

    TeachingTechnique.GAME_CHALLENGE: """\
🎮 GAME CHALLENGE MODE — GAMIFIED LEARNING:
You are running a gamified challenge session with XP and achievements.
Rules:
1. Present questions as CHALLENGES with clear scoring
2. Award 🌟 XP for correct answers: Easy=10, Medium=20, Hard=50
3. Track streaks: "🔥 STREAK: 3 correct in a row!"
4. Use difficulty tiers: 🟢 Easy → 🟡 Medium → 🔴 Hard → 💀 Expert
5. Give immediate feedback: "✅ CORRECT! +20 XP" or "❌ Not quite! The answer is..."
6. Provide progress bars: "Progress: ████░░░░░░ 40%"
7. Celebrate milestones: "🏆 ACHIEVEMENT UNLOCKED: Streak Warrior!"
8. At the end, show a SCOREBOARD with total XP, accuracy, and time
9. Make it FUN — use emojis, enthusiasm, and competitive language""",

    TeachingTechnique.DEEP_SOCRATIC: """\
🔬🦉 DEEP SOCRATIC MODE — RESEARCH-POWERED SOCRATIC MASTERY:
You are an uncompromising strict, elite Socratic Professor and Polymath.
You possess profound, expert-level knowledge across ALL domains (Software, Hardware,
Aerospace, Fitness, Mechanical Engineering, Quantum Physics, etc.).
The user is a student who must learn a topic deeply.

YOUR PRIME DIRECTIVE:
NEVER give the final answer directly.
NEVER write the code for them initially.
NEVER solve the math problem for them at first step.

INSTEAD:
1. Break down their question into smaller underlying concepts.
2. Ask a leading question that forces them to find the first flaw in their own thinking.
3. If they are totally lost, give them a tiny hint, but end your response with a question.
4. Praise successful logical leaps.
5. If they ask for the answer directly, refuse politely and ask another probing question.

When provided with DEEP GRAPH-RAG INTELLIGENCE, use it to ground your Socratic questioning
in hyper-advanced, cutting-edge facts, but DO NOT just recite the facts. Force the student
to deduce the principles you see in the intelligence.

Your goal is to build genuine neural pathways in the student's brain, not to be a search engine.""",
}


# Difficulty Adaptation Prompts
_LEVEL_PROMPTS = {
    StudentLevel.BEGINNER: (
        "The student is a COMPLETE BEGINNER. "
        "Use everyday language. No jargon. Lots of analogies and examples. "
        "Assume ZERO prior knowledge. Be warm and encouraging."
    ),
    StudentLevel.INTERMEDIATE: (
        "The student has BASIC understanding and some experience. "
        "Use standard terminology but define advanced terms. "
        "Focus on WHY things work, not just HOW. Challenge them a little."
    ),
    StudentLevel.ADVANCED: (
        "The student is ADVANCED and understands core concepts well. "
        "Use technical language freely. Focus on edge cases, trade-offs, "
        "and real-world applications. Push them toward expert-level thinking."
    ),
    StudentLevel.EXPERT: (
        "The student is near-EXPERT level. "
        "Engage in peer-level discussion. Focus on cutting-edge research, "
        "open problems, and frontier knowledge. Cite specific papers/sources. "
        "Challenge their assumptions with contrarian viewpoints."
    ),
}


# ══════════════════════════════════════════════════════════════
# Ultimate Tutor Engine — The Unified Master
# ══════════════════════════════════════════════════════════════

class UltimateTutorEngine:
    """
    Research-backed adaptive teaching engine with 9 techniques,
    gamification, deep research, and Socratic mastery.

    Merges the capabilities of:
      - SocraticTutor (Deep Web Research bootstrapping + strict dialogue)
      - GamifiedTutorEngine (XP, levels, achievements, challenges)
      - ExpertTutorEngine (8 techniques, uncertainty detection, adaptive teaching)
    """

    def __init__(self, generate_fn: Callable, agent_controller=None, memory_manager=None):
        self.generate_fn = generate_fn
        self.agent = agent_controller
        self.memory_manager = memory_manager
        self._sessions: Dict[str, TutoringSession] = {}
        self._researcher = None
        self._mistake_engine = None
        self._flowchart_gen = None
        self._game_engine = None

        # Lazy-init researcher (used by both uncertainty detection AND Deep Socratic)
        if agent_controller:
            try:
                from agents.profiles.deep_researcher import DeepWebResearcher
                self._researcher = DeepWebResearcher(agent_controller)
            except ImportError:
                logger.warning("DeepWebResearcher not available")

        # Init mistake lesson engine
        try:
            from brain.mistake_lesson_engine import MistakeLessonEngine
            self._mistake_engine = MistakeLessonEngine(
                memory_manager=memory_manager, generate_fn=generate_fn,
            )
        except ImportError:
            logger.warning("MistakeLessonEngine not available")

        # Init flowchart generator
        try:
            from brain.flowchart_generator import FlowchartGenerator
            self._flowchart_gen = FlowchartGenerator(generate_fn=generate_fn)
        except ImportError:
            logger.warning("FlowchartGenerator not available")

        # Init gamification engine (previously a separate profile)
        try:
            self._game_engine = GamifiedTutorEngine(generate_fn=generate_fn)
        except Exception:
            logger.warning("GamifiedTutorEngine not available")

        logger.info("🎓 UltimateTutorEngine initialized (9 techniques, gamified, research-powered)")

    # ──────────────────────────────────────
    # Session Management
    # ──────────────────────────────────────

    def start_session(self, topic: str, session_id: str = None) -> TutoringSession:
        """Start a new tutoring session on a topic."""
        import uuid
        session_id = session_id or uuid.uuid4().hex[:10]
        session = TutoringSession(session_id=session_id, topic=topic)

        # Step 1: Probe LLM confidence on the topic
        probe_prompt = (
            f"Provide a comprehensive, expert-level explanation of: {topic}. "
            f"Cover the key concepts, principles, and latest developments. Be specific."
        )
        probe_result = self._call_llm(probe_prompt, "You are a knowledge assessment probe.")
        uncertainty_score, signals = detect_uncertainty(probe_result)
        logger.info(f"🎓 Topic '{topic}' — LLM uncertainty: {uncertainty_score:.2f} (signals: {len(signals)})")

        # Step 2: If uncertain, trigger deep research
        if uncertainty_score > 0.3:
            logger.info(f"🔬 Triggering deep research for topic: {topic}")
            session.research_intel = self._research_for_teaching(topic)
            session.research_triggered = True

        # Step 3: Build lesson plan
        session.lesson_plan = self._build_lesson_plan(topic, session.research_intel)

        # Step 4: Choose initial technique
        session.current_technique = self._select_technique(topic)

        # Step 5: Load anti-pattern lessons from mistake history
        if self._mistake_engine:
            try:
                session.anti_pattern_lessons = self._mistake_engine.get_lessons_for_topic(topic)
                session.mistake_curriculum = self._mistake_engine.generate_curriculum(topic)
                if session.anti_pattern_lessons:
                    logger.info(f"🚫 Loaded {len(session.anti_pattern_lessons)} anti-pattern lessons")
            except Exception as e:
                logger.warning(f"Failed to load anti-pattern lessons: {e}")

        # Step 6: Initialize gamification
        if self._game_engine:
            session.player_state = self._game_engine.create_player()
            session.game_engine = self._game_engine

        self._sessions[session_id] = session
        logger.info(
            f"🎓 Session {session_id}: topic='{topic}', "
            f"technique={session.current_technique.value}, "
            f"research={'YES' if session.research_triggered else 'NO'}, "
            f"steps={len(session.lesson_plan)}, "
            f"anti_patterns={len(session.anti_pattern_lessons)}, "
            f"gamified={'YES' if session.player_state else 'NO'}"
        )
        return session

    def get_session(self, session_id: str) -> Optional[TutoringSession]:
        return self._sessions.get(session_id)

    # ──────────────────────────────────────
    # Deep Socratic Bootstrap (from SocraticTutor)
    # ──────────────────────────────────────

    def _bootstrap_deep_socratic(self, session: TutoringSession):
        """
        Pre-load a full Graph-RAG intelligence dossier before starting
        Socratic questioning. Merged from the original SocraticTutor.
        """
        if not self._researcher:
            logger.warning("Deep Socratic: No researcher available, using base LLM knowledge")
            return

        try:
            dossier_path = self._researcher.compile_dossier(
                target_topic=f"Advanced educational breakdown and core principles of: {session.topic}"
            )
            if dossier_path and dossier_path.exists():
                session.deep_socratic_dossier_path = dossier_path
                with open(dossier_path, 'r', encoding='utf-8') as f:
                    session.deep_socratic_intel = f.read()
                logger.info("🔬🦉 Deep Socratic: Mapped topic across Surface, Deep, and Social Web")
            else:
                logger.warning("Deep Socratic: Could not generate intelligence graph")
        except Exception as e:
            logger.error(f"Deep Socratic research failed: {e}")

    # ──────────────────────────────────────
    # Teaching Flow
    # ──────────────────────────────────────

    def begin_teaching(self, session: TutoringSession) -> str:
        """Generate the opening diagnostic + first teaching message."""
        # If Deep Socratic, bootstrap research first
        if session.current_technique == TeachingTechnique.DEEP_SOCRATIC:
            self._bootstrap_deep_socratic(session)

        system_prompt = self._build_system_prompt(session)

        opening_prompt = f"You are starting a tutoring session on: {session.topic}\n\nLESSON PLAN:\n"
        for i, step in enumerate(session.lesson_plan):
            opening_prompt += f"  {i+1}. {step}\n"

        opening_prompt += (
            "\nFirst, give a brief exciting introduction about WHY this topic matters "
            "(2-3 sentences). Then ask ONE diagnostic question to assess the student's "
            "current level. The question should have 3 difficulty levels embedded "
            "(easy/medium/hard) so you can gauge where they are."
        )

        if session.research_intel:
            opening_prompt += self._format_research_context(session.research_intel)

        response = self._call_llm(opening_prompt, system_prompt, temperature=0.7)
        session.history.append({"role": "assistant", "content": response})
        return response

    def respond_to_student(self, session: TutoringSession, student_message: str) -> str:
        """Process student's response and generate next coaching step."""
        session.history.append({"role": "user", "content": student_message})

        # Diagnose student level
        diagnosis = self._diagnose_student(session, student_message)
        session.diagnostic = diagnosis
        session.student_level = diagnosis.level

        # Check if follow-up needs more research
        follow_up_uncertainty = self._check_followup_knowledge(session, student_message)
        if follow_up_uncertainty > 0.4 and not session.research_triggered:
            logger.info(f"🔬 Student question triggered deep research")
            session.research_intel = self._research_for_teaching(f"{session.topic}: {student_message}")
            session.research_triggered = True

        system_prompt = self._build_system_prompt(session)

        # Build conversational context (last 10 exchanges)
        context_messages = session.history[-20:]
        chat_context = ""
        for msg in context_messages:
            role = "STUDENT" if msg["role"] == "user" else "COACH"
            chat_context += f"{role}: {msg['content']}\n\n"

        progress = ""
        if session.lesson_plan:
            step_idx = min(session.current_lesson_step, len(session.lesson_plan) - 1)
            progress = (
                f"\n\nCURRENT PROGRESS: Step {step_idx + 1}/{len(session.lesson_plan)}: "
                f"{session.lesson_plan[step_idx]}"
            )

        teaching_prompt = (
            f"Dialogue so far:\n{chat_context}\n"
            f"STUDENT DIAGNOSIS: Level={diagnosis.level.value}, "
            f"Gaps={diagnosis.knowledge_gaps}, Strengths={diagnosis.strengths}\n"
            f"{progress}\n\n"
            f"The student just said: \"{student_message}\"\n\n"
            f"Generate your next coaching response. Remember to use the "
            f"{session.current_technique.value} technique. "
            f"If the student shows they understand, advance to the next step."
        )

        if session.research_intel:
            teaching_prompt += self._format_research_context(session.research_intel)

        # Anti-pattern context
        if session.anti_pattern_lessons:
            if (session.current_technique == TeachingTechnique.ANTI_PATTERN
                or session.anti_patterns_shown < len(session.anti_pattern_lessons)):
                teaching_prompt += self._format_anti_pattern_context(session)

        # Flowchart context
        if session.current_technique == TeachingTechnique.VISUAL_FLOWCHART and self._flowchart_gen:
            teaching_prompt += self._format_flowchart_context(session, student_message)

        # Deep Socratic intel injection
        if session.current_technique == TeachingTechnique.DEEP_SOCRATIC and session.deep_socratic_intel:
            teaching_prompt += (
                f"\n\n--- CUTTING-EDGE GRAPH-RAG INTELLIGENCE ---\n"
                f"{session.deep_socratic_intel[:3000]}\n"
                f"--- END INTELLIGENCE ---\n"
                f"Use this to ground your Socratic questioning in expert-level facts. "
                f"Do NOT recite facts directly — force the student to DEDUCE principles."
            )

        response = self._call_llm(teaching_prompt, system_prompt, temperature=0.7)
        session.history.append({"role": "assistant", "content": response})

        # Auto-advance lesson if student shows understanding
        if diagnosis.confidence > 0.7 and session.lesson_plan:
            if session.current_lesson_step < len(session.lesson_plan) - 1:
                session.current_lesson_step += 1

        return response

    # ──────────────────────────────────────
    # Interactive CLI Session
    # ──────────────────────────────────────

    def start_interactive(self, topic: str):
        """Start an interactive tutoring session in the console."""
        print(f"\n{'='*60}")
        print("  🎓 ULTIMATE TUTOR ENGINE — Interactive Session")
        print(f"  Topic: {topic}")
        print(f"{'='*60}")

        session = self.start_session(topic)

        if session.research_triggered:
            print("\n🔬 Deep Research triggered — using expert web sources to teach you.\n")

        print(f"📚 Teaching technique: {session.current_technique.value}")
        print(f"📋 Lesson plan: {len(session.lesson_plan)} steps")
        print("\nType 'exit', 'quit', or 'done' to end the session.")
        print("Type 'switch <technique>' to change teaching style.")
        print("  Techniques: feynman, scaffolding, socratic, analogy_bridge, chunking,")
        print("              anti_pattern, visual_flowchart, game_challenge, deep_socratic")
        if session.player_state:
            print("Type 'dashboard' to see your XP & progress.")
            print("Type 'challenge' to start a gamified quiz.")
        print(f"{'─'*60}\n")

        opening = self.begin_teaching(session)
        print(f"🎓 Coach: {opening}\n")

        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ('exit', 'quit', 'done'):
                    self._end_session_summary(session)
                    break

                # Handle technique switching
                if user_input.lower().startswith('switch '):
                    technique_name = user_input[7:].strip().lower()
                    try:
                        session.current_technique = TeachingTechnique(technique_name)
                        # Bootstrap Deep Socratic if switching to it
                        if session.current_technique == TeachingTechnique.DEEP_SOCRATIC:
                            print("\n🔬🦉 Bootstrapping Deep Socratic mode — loading expert intelligence...\n")
                            self._bootstrap_deep_socratic(session)
                        print(f"\n📚 Switched to {technique_name} technique!\n")
                        continue
                    except ValueError:
                        print(f"\n❌ Unknown technique: {technique_name}")
                        print("   Available: feynman, scaffolding, socratic, analogy_bridge, chunking,")
                        print("              anti_pattern, visual_flowchart, game_challenge, deep_socratic\n")
                        continue

                # Gamification dashboard
                if user_input.lower() == 'dashboard' and session.player_state:
                    print(render_dashboard(session.player_state))
                    continue

                # Gamification challenge
                if user_input.lower() == 'challenge' and session.game_engine:
                    self._run_interactive_challenge(session)
                    continue

                response = self.respond_to_student(session, user_input)
                step = min(session.current_lesson_step + 1, len(session.lesson_plan))
                total = len(session.lesson_plan) or 1
                level = session.student_level.value
                print(f"\n[📊 Level: {level} | Step: {step}/{total}]")
                print(f"🎓 Coach: {response}\n")

            except KeyboardInterrupt:
                self._end_session_summary(session)
                break
            except Exception as e:
                logger.error(f"Tutor error: {e}", exc_info=True)
                print("\n⚠️ Teaching error occurred. Let me try again.\n")

    def _run_interactive_challenge(self, session: TutoringSession):
        """Run a gamified challenge within the interactive session."""
        if not session.game_engine or not session.player_state:
            print("⚠️ Gamification not available.\n")
            return

        challenge = session.game_engine.create_challenge(
            mode=ChallengeMode.QUIZ, topic=session.topic,
        )
        session.active_challenge = challenge
        print(f"\n⚔️ CHALLENGE STARTED: {len(challenge.questions)} questions about {session.topic}\n")

        for i, q in enumerate(challenge.questions):
            print(f"  Q{i+1}: {q.question}")
            if q.options:
                for opt in q.options:
                    print(f"       {opt}")
            answer = input("  Your answer: ").strip()
            result = session.game_engine.answer_challenge(challenge.id, answer, session.player_state)
            if result.get("correct"):
                print(f"  ✅ Correct! +{result.get('xp_earned', 0)} XP\n")
            else:
                print(f"  ❌ Wrong. Answer: {result.get('correct_answer', '?')}")
                print(f"  💡 {result.get('explanation', '')}\n")
            if result.get("challenge_complete"):
                print(result.get("challenge_result", ""))
                break
        print()

    def _end_session_summary(self, session: TutoringSession):
        """Print a session summary when the student exits."""
        elapsed = time.time() - session.started_at
        minutes = int(elapsed / 60)
        exchanges = len([m for m in session.history if m["role"] == "user"])

        print(f"\n{'='*60}")
        print("  📊 SESSION SUMMARY")
        print(f"{'='*60}")
        print(f"  Topic: {session.topic}")
        print(f"  Duration: {minutes} minutes")
        print(f"  Exchanges: {exchanges}")
        print(f"  Final Level: {session.student_level.value}")
        print(f"  Research Used: {'Yes' if session.research_triggered else 'No'}")
        print(f"  Technique: {session.current_technique.value}")
        if session.lesson_plan:
            step = min(session.current_lesson_step + 1, len(session.lesson_plan))
            print(f"  Progress: {step}/{len(session.lesson_plan)} steps completed")
        if session.player_state:
            ps = session.player_state
            print(f"  🎮 XP: {ps.xp} | Level: {ps.level.value} | Streak: {ps.max_streak}")
            unlocked = sum(1 for a in ps.achievements.values() if a.unlocked)
            print(f"  🏆 Achievements: {unlocked}/{len(ps.achievements)}")
        print("\n  🎓 Great work today! Keep learning! 🚀")
        print(f"{'='*60}\n")

    # ──────────────────────────────────────
    # Deep Research for Teaching
    # ──────────────────────────────────────

    def _research_for_teaching(self, topic: str) -> ResearchIntel:
        """Trigger deep research and convert into teaching material."""
        intel = ResearchIntel(topic=topic)
        try:
            from agents.tools.web_search import advanced_web_search

            surface = advanced_web_search(f"explain {topic} simply with examples", network="surface", max_results=5, deep_scrape=True)
            for item in surface.get("results", []):
                content = item.get("full_content") or item.get("snippet", "")
                if content and len(content) > 50:
                    intel.real_world_examples.append(content[:800])
                    intel.sources.append({"title": item.get("title", ""), "url": item.get("href", ""), "type": "surface"})

            social = advanced_web_search(f"{topic} ELI5 explained simple", network="social", max_results=5)
            for item in social.get("results", []):
                snippet = item.get("snippet", "")
                if snippet and len(snippet) > 30:
                    intel.social_wisdom.append(snippet[:600])
                    intel.eli5_explanations.append(snippet[:400])
                    intel.sources.append({"title": item.get("title", ""), "url": item.get("href", ""), "type": "social"})

            academic = advanced_web_search(topic, network="deep", max_results=5)
            for item in academic.get("results", []):
                snippet = item.get("snippet", "")
                if snippet:
                    intel.academic_findings.append(snippet[:800])
                    intel.expert_insights.append(f"[{item.get('title', 'Research')}]: {snippet[:300]}")
                    intel.sources.append({"title": item.get("title", ""), "url": item.get("href", ""), "type": "academic"})

            logger.info(f"🔬 Research: {len(intel.real_world_examples)} examples, {len(intel.eli5_explanations)} ELI5s, {len(intel.academic_findings)} academic")
        except Exception as e:
            logger.error(f"Research failed: {e}", exc_info=True)

        if intel.real_world_examples or intel.academic_findings:
            try:
                problems = self._call_llm(
                    f"Based on this topic: {topic}\nGenerate 3 practice problems ordered easy to hard. Numbered list with hints.",
                    "You are an expert educator.",
                )
                intel.practice_problems = [problems]
            except Exception:
                pass
        return intel

    def _format_research_context(self, intel: ResearchIntel) -> str:
        """Format research intelligence for injection into the teaching prompt."""
        parts = ["\n\n--- DEEP RESEARCH INTELLIGENCE (use to enrich your teaching) ---"]
        if intel.eli5_explanations:
            parts.append("\n📱 COMMUNITY EXPLANATIONS (Reddit/Social):")
            for i, exp in enumerate(intel.eli5_explanations[:3]):
                parts.append(f"  {i+1}. {exp[:300]}")
        if intel.expert_insights:
            parts.append("\n🔬 ACADEMIC/EXPERT INSIGHTS:")
            for i, insight in enumerate(intel.expert_insights[:3]):
                parts.append(f"  {i+1}. {insight[:300]}")
        if intel.real_world_examples:
            parts.append("\n🌍 REAL-WORLD EXAMPLES:")
            for i, ex in enumerate(intel.real_world_examples[:2]):
                parts.append(f"  {i+1}. {ex[:300]}")
        if intel.practice_problems:
            parts.append("\n✏️ PRACTICE PROBLEMS:")
            for prob in intel.practice_problems[:1]:
                parts.append(f"  {prob[:500]}")
        parts.append("\n--- END RESEARCH INTELLIGENCE ---")
        parts.append("\nIMPORTANT: Weave this intelligence naturally into your teaching.")
        return "\n".join(parts)

    # ──────────────────────────────────────
    # Student Diagnosis
    # ──────────────────────────────────────

    def _diagnose_student(self, session: TutoringSession, student_msg: str) -> DiagnosticResult:
        """Analyze the student's response to determine their level."""
        result = DiagnosticResult()
        msg_lower = student_msg.lower()
        word_count = len(student_msg.split())

        beginner_signals = ["i don't know", "what is", "what's", "i have no idea", "never heard", "confused", "don't understand", "huh", "idk", "no clue", "explain"]
        intermediate_signals = ["i think", "maybe because", "is it like", "i remember", "so basically", "i've heard", "i know a little"]
        advanced_signals = ["because", "therefore", "the reason is", "this implies", "trade-off", "alternatively", "however", "specifically", "in my experience", "the key insight"]
        expert_signals = ["according to", "the paper by", "the algorithm", "complexity is", "formally", "proof", "theorem", "implementation detail", "the specification"]

        scores = {
            StudentLevel.BEGINNER: sum(1 for s in beginner_signals if s in msg_lower),
            StudentLevel.INTERMEDIATE: sum(1 for s in intermediate_signals if s in msg_lower),
            StudentLevel.ADVANCED: sum(1 for s in advanced_signals if s in msg_lower),
            StudentLevel.EXPERT: sum(1 for s in expert_signals if s in msg_lower),
        }
        if word_count > 50: scores[StudentLevel.ADVANCED] += 1
        if word_count > 100: scores[StudentLevel.EXPERT] += 1
        if word_count < 10: scores[StudentLevel.BEGINNER] += 1

        best_level = max(scores, key=scores.get)
        best_score = scores[best_level]

        if best_score == 0:
            result.level = session.student_level
            result.confidence = 0.5
        else:
            result.level = best_level
            result.confidence = min(1.0, best_score * 0.25)

        if "?" in student_msg:
            result.knowledge_gaps = [q.strip() + "?" for q in student_msg.split("?") if q.strip()][:3]

        tech_terms = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', student_msg)
        if tech_terms:
            result.strengths = tech_terms[:3]
        return result

    # ──────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────

    def _call_llm(self, prompt: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        """Call the LLM generation function safely."""
        try:
            result = self.generate_fn(prompt=prompt, system_prompt=system_prompt, temperature=temperature)
            if hasattr(result, 'answer'): return result.answer
            if hasattr(result, 'error') and result.error: return f"[LLM Error: {result.error}]"
            return str(result)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "[Unable to generate response — using cached knowledge]"

    def _build_system_prompt(self, session: TutoringSession) -> str:
        """Build the full system prompt combining technique + level + research."""
        parts = [
            "You are an ELITE expert tutor with decades of teaching experience.",
            "You adapt your teaching to the student's exact level and learning style.",
            "",
            _TECHNIQUE_PROMPTS.get(session.current_technique, ""),
            "",
            _LEVEL_PROMPTS.get(session.student_level, ""),
        ]
        if session.lesson_plan:
            parts.append(f"\nLESSON PLAN: {json.dumps(session.lesson_plan)}")
        return "\n".join(parts)

    def _build_lesson_plan(self, topic: str, research: Optional[ResearchIntel] = None) -> List[str]:
        """Generate a structured lesson plan for the topic."""
        context = ""
        if research and research.expert_insights:
            context = "\nUse these expert insights to inform the plan:\n" + "\n".join(research.expert_insights[:3])
        prompt = (
            f"Create a lesson plan for teaching: {topic}\n"
            f"Generate exactly 5-7 steps, ordered from foundation to mastery.\n"
            f"Each step should be a short phrase (5-10 words max).\n"
            f"Format: one step per line, no numbers or bullets.\n{context}"
        )
        result = self._call_llm(prompt, "You are a curriculum designer.", temperature=0.5)
        lines = [line.strip().lstrip("0123456789.-) ") for line in result.split("\n")]
        plan = [line for line in lines if line and len(line) > 5 and len(line) < 100]
        if not plan:
            plan = [
                f"What is {topic} and why it matters",
                "Core concepts and terminology",
                f"How {topic} works step by step",
                "Real-world applications and examples",
                "Common mistakes and misconceptions",
                "Practice problems and exercises",
                "Advanced topics and next steps",
            ]
        return plan[:7]

    def _select_technique(self, topic: str) -> TeachingTechnique:
        """Select the best teaching technique for a topic."""
        topic_lower = topic.lower()
        if any(w in topic_lower for w in ["math", "calculus", "algebra", "physics", "chemistry", "algorithm", "data structure", "proof", "theorem"]):
            return TeachingTechnique.SCAFFOLDING
        if any(w in topic_lower for w in ["quantum", "philosophy", "theory", "abstract", "consciousness", "relativity", "economics"]):
            return TeachingTechnique.ANALOGY_BRIDGE
        if any(w in topic_lower for w in ["programming", "code", "python", "javascript", "web", "cooking", "fitness", "design", "build", "create"]):
            return TeachingTechnique.FEYNMAN
        if any(w in topic_lower for w in ["history", "overview", "complete guide", "everything about", "introduction to", "full course"]):
            return TeachingTechnique.CHUNKING
        return TeachingTechnique.SCAFFOLDING

    def _check_followup_knowledge(self, session: TutoringSession, student_msg: str) -> float:
        """Check if a student's follow-up question requires more research."""
        specific_indicators = ["latest", "newest", "recent", "2024", "2025", "2026", "current", "today", "right now", "updated", "specific paper", "who invented", "exact number"]
        msg_lower = student_msg.lower()
        return min(1.0, sum(0.15 for ind in specific_indicators if ind in msg_lower))

    def _format_anti_pattern_context(self, session: TutoringSession) -> str:
        """Format anti-pattern lessons as context."""
        if not session.anti_pattern_lessons:
            return ""
        parts = ["\n\n--- ANTI-PATTERN LESSONS ---"]
        idx = session.anti_patterns_shown
        if idx < len(session.anti_pattern_lessons) and self._mistake_engine:
            lesson = session.anti_pattern_lessons[idx]
            parts.append(self._mistake_engine.format_lesson_for_prompt(lesson))
            session.anti_patterns_shown += 1
            if session.player_state and session.game_engine:
                session.game_engine.record_anti_pattern_learned(session.player_state)
        parts.append("--- END ANTI-PATTERN LESSONS ---")
        parts.append("IMPORTANT: Show ❌ BAD approach first, then contrast with ✅ GOOD approach.")
        return "\n".join(parts)

    def _format_flowchart_context(self, session: TutoringSession, student_msg: str) -> str:
        """Generate and format a flowchart for the current teaching context."""
        if not self._flowchart_gen:
            return ""
        try:
            from brain.flowchart_generator import FlowchartType
            msg_lower = student_msg.lower()
            if any(w in msg_lower for w in ["choose", "decision", "which", "should i", "vs"]):
                chart_type = FlowchartType.DECISION
            elif any(w in msg_lower for w in ["how", "steps", "process", "procedure"]):
                chart_type = FlowchartType.PROCESS
            elif any(w in msg_lower for w in ["wrong", "mistake", "bad", "don't", "avoid"]):
                chart_type = FlowchartType.ANTI_PATTERN
            elif any(w in msg_lower for w in ["relate", "connect", "map", "overview"]):
                chart_type = FlowchartType.CONCEPT_MAP
            elif any(w in msg_lower for w in ["compare", "difference", "versus", "pros cons"]):
                chart_type = FlowchartType.COMPARISON
            elif any(w in msg_lower for w in ["debug", "fix", "error", "bug"]):
                chart_type = FlowchartType.DEBUG_TRACE
            else:
                chart_type = FlowchartType.PROCESS

            chart = self._flowchart_gen.generate(topic=session.topic, chart_type=chart_type, context=student_msg)
            if session.player_state and session.game_engine:
                session.game_engine.record_flowchart_requested(session.player_state)
            return (
                f"\n\n--- VISUAL FLOWCHART ---\n```mermaid\n{chart}\n```\n--- END FLOWCHART ---\n"
                "IMPORTANT: Include this flowchart in your response inside a ```mermaid block."
            )
        except Exception as e:
            logger.warning(f"Flowchart generation failed: {e}")
            return ""

    # ──────────────────────────────────────
    # Gamification API Methods
    # ──────────────────────────────────────

    def get_game_dashboard(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        if not session or not session.player_state or not session.game_engine:
            return None
        return render_dashboard(session.player_state)

    def start_challenge(self, session_id: str, mode: str = "quiz") -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session or not session.game_engine:
            return None
        try:
            challenge_mode = ChallengeMode(mode)
        except ValueError:
            challenge_mode = ChallengeMode.QUIZ
        challenge = session.game_engine.create_challenge(mode=challenge_mode, topic=session.topic)
        session.active_challenge = challenge
        return {
            "challenge_id": challenge.id, "mode": challenge.mode.value,
            "questions": len(challenge.questions),
            "first_question": challenge.questions[0].question if challenge.questions else "",
            "options": challenge.questions[0].options if challenge.questions else [],
        }

    def answer_challenge(self, session_id: str, answer: str) -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session or not session.active_challenge or not session.game_engine:
            return None
        return session.game_engine.answer_challenge(
            challenge_id=session.active_challenge.id, answer=answer, state=session.player_state,
        )

    def generate_flowchart(self, session_id: str, chart_type: str = "process") -> Optional[str]:
        session = self.get_session(session_id)
        if not session or not self._flowchart_gen:
            return None
        from brain.flowchart_generator import FlowchartType
        try:
            ftype = FlowchartType(chart_type)
        except ValueError:
            ftype = FlowchartType.PROCESS
        return self._flowchart_gen.generate(topic=session.topic, chart_type=ftype)

    def get_anti_patterns(self, session_id: str) -> List[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session or not session.anti_pattern_lessons:
            return []
        return [
            {"title": l.title, "category": l.category, "danger_score": l.danger_score,
             "bad_approach": l.bad_approach, "correct_approach": l.correct_approach,
             "expert_principle": l.expert_principle, "flowchart": l.flowchart}
            for l in session.anti_pattern_lessons
        ]

    # ──────────────────────────────────────
    # API-Compatible Methods
    # ──────────────────────────────────────

    def api_start_session(self, topic: str) -> Dict[str, Any]:
        session = self.start_session(topic)
        opening = self.begin_teaching(session)
        return {
            "session_id": session.session_id, "topic": session.topic,
            "technique": session.current_technique.value,
            "research_used": session.research_triggered,
            "lesson_plan": session.lesson_plan, "opening_message": opening,
            "anti_patterns_loaded": len(session.anti_pattern_lessons),
            "gamification_active": session.player_state is not None,
            "techniques_available": [t.value for t in TeachingTechnique],
        }

    def api_respond(self, session_id: str, message: str) -> Dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}
        response = self.respond_to_student(session, message)
        result = {
            "session_id": session_id, "response": response,
            "student_level": session.student_level.value,
            "technique": session.current_technique.value,
            "lesson_progress": {
                "current_step": session.current_lesson_step + 1,
                "total_steps": len(session.lesson_plan),
                "current_topic": session.lesson_plan[session.current_lesson_step] if session.lesson_plan else "",
            },
            "research_used": session.research_triggered,
            "anti_patterns_shown": session.anti_patterns_shown,
        }
        if session.player_state:
            result["gamification"] = {
                "xp": session.player_state.xp, "level": session.player_state.level.value,
                "streak": session.player_state.streak,
                "achievements_unlocked": sum(1 for a in session.player_state.achievements.values() if a.unlocked),
            }
        return result


# ══════════════════════════════════════════════════════════════
# Backward Compatibility Aliases
# ══════════════════════════════════════════════════════════════

# Allow existing code that imports ExpertTutorEngine to keep working
ExpertTutorEngine = UltimateTutorEngine
