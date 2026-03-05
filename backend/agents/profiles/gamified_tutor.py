"""
Gamified Tutor Engine — Learn Like a Game
──────────────────────────────────────────
Wraps the ExpertTutorEngine with a full game-like learning experience:

  🎮 XP & Level System     — Earn XP for correct answers, discoveries, completions
  🏆 Achievement System    — Unlock achievements for learning milestones
  🔥 Streak Tracking       — Maintain answer streaks for bonus XP
  ⚔️ Challenge Modes       — Quiz, Boss Battle, Puzzle, Sniper challenge types
  📊 Progress Dashboard    — Rich ASCII dashboard showing all stats

Level Progression:
  Novice (0) → Apprentice (100) → Journeyman (300) → Expert (600)
  → Master (1000) → Grandmaster (1500) → Legend (2500)
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Enums & Constants
# ──────────────────────────────────────────────

class PlayerLevel(Enum):
    """Player skill levels with XP thresholds."""
    NOVICE = "Novice"
    APPRENTICE = "Apprentice"
    JOURNEYMAN = "Journeyman"
    EXPERT = "Expert"
    MASTER = "Master"
    GRANDMASTER = "Grandmaster"
    LEGEND = "Legend"


class ChallengeMode(Enum):
    """Types of gamified challenges."""
    QUIZ = "quiz"                 # Rapid-fire questions with timer
    BOSS_BATTLE = "boss_battle"   # Multi-step complex problem
    PUZZLE = "puzzle"             # Find all anti-patterns in code
    SNIPER = "sniper"             # Identify the ONE critical mistake


# XP thresholds for each level
LEVEL_THRESHOLDS = {
    PlayerLevel.NOVICE: 0,
    PlayerLevel.APPRENTICE: 100,
    PlayerLevel.JOURNEYMAN: 300,
    PlayerLevel.EXPERT: 600,
    PlayerLevel.MASTER: 1000,
    PlayerLevel.GRANDMASTER: 1500,
    PlayerLevel.LEGEND: 2500,
}

# Level star display
LEVEL_STARS = {
    PlayerLevel.NOVICE: "⭐",
    PlayerLevel.APPRENTICE: "⭐⭐",
    PlayerLevel.JOURNEYMAN: "⭐⭐⭐",
    PlayerLevel.EXPERT: "⭐⭐⭐⭐",
    PlayerLevel.MASTER: "🌟🌟🌟🌟🌟",
    PlayerLevel.GRANDMASTER: "💎💎💎💎💎💎",
    PlayerLevel.LEGEND: "👑👑👑👑👑👑👑",
}

# XP rewards for different actions
XP_REWARDS = {
    "correct_answer": 15,
    "detailed_answer": 30,      # Long, thoughtful response
    "insight_discovery": 50,    # Student discovers something on their own
    "lesson_complete": 100,
    "challenge_complete": 200,
    "boss_battle_win": 500,
    "streak_bonus_5": 50,       # 5 correct in a row
    "streak_bonus_10": 150,     # 10 correct in a row
    "anti_pattern_learned": 25,
    "flowchart_requested": 10,
    "first_question": 5,
    "quiz_perfect": 100,        # All quiz answers correct
}


# ──────────────────────────────────────────────
# Achievement System
# ──────────────────────────────────────────────

@dataclass
class Achievement:
    """A single unlockable achievement."""
    id: str
    name: str
    description: str
    emoji: str
    unlocked: bool = False
    unlocked_at: float = 0.0

    def display(self) -> str:
        if self.unlocked:
            return f"  {self.emoji} {self.name} — {self.description} ✅"
        else:
            return f"  🔒 {self.name} — {self.description}"


ACHIEVEMENT_DEFINITIONS = {
    "first_blood": {
        "name": "First Blood",
        "description": "Complete your first lesson",
        "emoji": "🗡️",
    },
    "mistake_hunter": {
        "name": "Mistake Hunter",
        "description": "Learn from 5 anti-pattern lessons",
        "emoji": "🔍",
    },
    "flowchart_master": {
        "name": "Flowchart Master",
        "description": "Request 3 visual flowcharts",
        "emoji": "📊",
    },
    "streak_warrior": {
        "name": "Streak Warrior",
        "description": "Get 5 correct answers in a row",
        "emoji": "🔥",
    },
    "streak_inferno": {
        "name": "Streak Inferno",
        "description": "Get 10 correct answers in a row",
        "emoji": "🌋",
    },
    "deep_thinker": {
        "name": "Deep Thinker",
        "description": "Discover 3 root causes independently",
        "emoji": "🧠",
    },
    "speed_demon": {
        "name": "Speed Demon",
        "description": "Complete a lesson in under 2 minutes",
        "emoji": "⚡",
    },
    "perfectionist": {
        "name": "Perfectionist",
        "description": "Score 100% on a challenge quiz",
        "emoji": "💯",
    },
    "explorer": {
        "name": "Explorer",
        "description": "Study 3 different topics",
        "emoji": "🗺️",
    },
    "resilient": {
        "name": "Resilient",
        "description": "Recover from 3 wrong answers without giving up",
        "emoji": "💪",
    },
    "principle_seeker": {
        "name": "Principle Seeker",
        "description": "Identify 3 expert principles",
        "emoji": "🔮",
    },
    "level_up_first": {
        "name": "Rising Star",
        "description": "Reach Apprentice level",
        "emoji": "🌅",
    },
    "master_class": {
        "name": "Master Class",
        "description": "Reach Master level",
        "emoji": "🏅",
    },
    "boss_slayer": {
        "name": "Boss Slayer",
        "description": "Win a Boss Battle challenge",
        "emoji": "⚔️",
    },
    "sniper_elite": {
        "name": "Sniper Elite",
        "description": "Win 3 Sniper Mode challenges",
        "emoji": "🎯",
    },
}


# ──────────────────────────────────────────────
# Player State
# ──────────────────────────────────────────────

@dataclass
class PlayerState:
    """Complete gamification state for a student."""
    player_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    xp: int = 0
    level: PlayerLevel = PlayerLevel.NOVICE
    streak: int = 0
    max_streak: int = 0
    correct_answers: int = 0
    wrong_answers: int = 0
    lessons_completed: int = 0
    challenges_won: int = 0
    boss_battles_won: int = 0
    sniper_wins: int = 0
    anti_patterns_learned: int = 0
    flowcharts_requested: int = 0
    insights_discovered: int = 0
    principles_found: int = 0
    topics_studied: List[str] = field(default_factory=list)
    achievements: Dict[str, Achievement] = field(default_factory=dict)
    xp_history: List[Tuple[int, str]] = field(default_factory=list)  # (xp, reason)
    session_start: float = field(default_factory=time.time)
    total_time_seconds: float = 0.0
    wrong_answer_recovery: int = 0  # Wrong answers recovered from

    def __post_init__(self):
        """Initialize achievements."""
        if not self.achievements:
            for aid, adef in ACHIEVEMENT_DEFINITIONS.items():
                self.achievements[aid] = Achievement(
                    id=aid, **adef
                )


# ──────────────────────────────────────────────
# Challenge Data
# ──────────────────────────────────────────────

@dataclass
class ChallengeQuestion:
    """A single question in a challenge."""
    question: str = ""
    options: List[str] = field(default_factory=list)  # For multiple choice
    correct_answer: str = ""
    explanation: str = ""
    xp_value: int = 20
    time_limit_seconds: int = 60

@dataclass
class Challenge:
    """A gamified challenge session."""
    id: str = field(default_factory=lambda: f"ch-{uuid.uuid4().hex[:6]}")
    mode: ChallengeMode = ChallengeMode.QUIZ
    topic: str = ""
    questions: List[ChallengeQuestion] = field(default_factory=list)
    current_question: int = 0
    score: int = 0
    max_score: int = 0
    started_at: float = field(default_factory=time.time)
    completed: bool = False
    perfect: bool = False


# ──────────────────────────────────────────────
# Dashboard Rendering
# ──────────────────────────────────────────────

def render_dashboard(state: PlayerState) -> str:
    """Render a rich ASCII progress dashboard."""
    # XP bar
    next_level = _get_next_level(state.level)
    if next_level:
        current_threshold = LEVEL_THRESHOLDS[state.level]
        next_threshold = LEVEL_THRESHOLDS[next_level]
        progress = state.xp - current_threshold
        needed = next_threshold - current_threshold
        bar_filled = int((progress / max(needed, 1)) * 20)
        bar_empty = 20 - bar_filled
        xp_bar = f"{'█' * bar_filled}{'░' * bar_empty}"
        xp_text = f"{progress}/{needed}"
    else:
        xp_bar = "██████████████████████"
        xp_text = "MAX LEVEL"

    # Streak display
    streak_fire = "🔥" * min(state.streak, 10)
    if not streak_fire:
        streak_fire = "💤 none"

    # Achievements count
    unlocked = sum(1 for a in state.achievements.values() if a.unlocked)
    total = len(state.achievements)

    # Calculate session time
    session_minutes = int((time.time() - state.session_start) / 60)

    stars = LEVEL_STARS.get(state.level, "⭐")

    return f"""\
╔════════════════════════════════════════════════╗
║  🎮 LEARNING DASHBOARD                        ║
╠════════════════════════════════════════════════╣
║  Level: {stars} {state.level.value:<14}              ║
║  XP:    {xp_bar} {xp_text:<10}       ║
║  Total XP: {state.xp:<6}                           ║
╠════════════════════════════════════════════════╣
║  🔥 Streak: {streak_fire:<25}      ║
║  ✅ Correct: {state.correct_answers:<5}  ❌ Wrong: {state.wrong_answers:<5}     ║
║  📚 Lessons: {state.lessons_completed:<5}  ⚔️ Challenges: {state.challenges_won:<4}║
║  ⚠️ Anti-Patterns: {state.anti_patterns_learned:<4}  📊 Flowcharts: {state.flowcharts_requested:<3}║
║  🏆 Achievements: {unlocked}/{total} unlocked             ║
║  ⏱️ Session: {session_minutes} min                        ║
╚════════════════════════════════════════════════╝"""


def render_achievement_unlocked(achievement: Achievement) -> str:
    """Render an achievement unlock notification."""
    return f"""\
╔════════════════════════════════════════════╗
║          🏆 ACHIEVEMENT UNLOCKED! 🏆      ║
║                                            ║
║    {achievement.emoji} {achievement.name:<30}   ║
║    {achievement.description:<38}   ║
║                                            ║
╚════════════════════════════════════════════╝"""


def render_level_up(old_level: PlayerLevel, new_level: PlayerLevel, xp: int) -> str:
    """Render a level-up celebration."""
    stars = LEVEL_STARS.get(new_level, "⭐")
    return f"""\
╔════════════════════════════════════════════╗
║          ⬆️  LEVEL UP!  ⬆️               ║
║                                            ║
║    {old_level.value} → {new_level.value:<20}          ║
║    {stars:<36}    ║
║    Total XP: {xp}                          ║
║                                            ║
║    🎉 Keep pushing! You're amazing! 🎉    ║
╚════════════════════════════════════════════╝"""


def render_challenge_result(challenge: Challenge) -> str:
    """Render challenge completion results."""
    pct = (challenge.score / max(challenge.max_score, 1)) * 100
    grade = "🥇" if pct >= 90 else "🥈" if pct >= 70 else "🥉" if pct >= 50 else "📝"
    elapsed = int(time.time() - challenge.started_at)

    return f"""\
╔════════════════════════════════════════════╗
║         ⚔️ CHALLENGE COMPLETE! ⚔️         ║
╠════════════════════════════════════════════╣
║  Mode:  {challenge.mode.value:<20}           ║
║  Score: {challenge.score}/{challenge.max_score} {grade:<10}                    ║
║  Grade: {pct:.0f}%                               ║
║  Time:  {elapsed}s                               ║
║  {"🌟 PERFECT SCORE!" if challenge.perfect else "Good effort! Try again for perfect!":<40} ║
╚════════════════════════════════════════════╝"""


# ──────────────────────────────────────────────
# Gamified Tutor Engine
# ──────────────────────────────────────────────

class GamifiedTutorEngine:
    """
    Game-layer wrapper around the Expert Tutor that adds XP, levels,
    achievements, streaks, and challenge modes for engaging learning.

    Usage:
        game = GamifiedTutorEngine(generate_fn=llm_fn)
        state = game.create_player()
        game.award_xp(state, "correct_answer")
        print(game.get_dashboard(state))
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self._active_challenges: Dict[str, Challenge] = {}
        logger.info("🎮 GamifiedTutorEngine initialized")

    # ──────────────────────────────────────
    # Player Management
    # ──────────────────────────────────────

    def create_player(self) -> PlayerState:
        """Create a new player with fresh stats."""
        state = PlayerState()
        logger.info(f"🎮 New player created: {state.player_id}")
        return state

    def get_dashboard(self, state: PlayerState) -> str:
        """Get the full ASCII progress dashboard."""
        return render_dashboard(state)

    def get_achievements_display(self, state: PlayerState) -> str:
        """Get formatted list of all achievements."""
        lines = [
            "╔════════════════════════════════════════════════╗",
            "║            🏆 ACHIEVEMENTS                    ║",
            "╠════════════════════════════════════════════════╣",
        ]
        for achievement in state.achievements.values():
            lines.append(f"║ {achievement.display():<45}║")
        lines.append("╚════════════════════════════════════════════════╝")
        return "\n".join(lines)

    # ──────────────────────────────────────
    # XP & Level System
    # ──────────────────────────────────────

    def award_xp(self, state: PlayerState, reason: str, bonus: int = 0) -> Tuple[int, Optional[str]]:
        """
        Award XP to the player.

        Args:
            state: Player state to update
            reason: Key from XP_REWARDS dict
            bonus: Additional bonus XP

        Returns:
            (xp_awarded, level_up_message or None)
        """
        base_xp = XP_REWARDS.get(reason, 10)
        total_xp = base_xp + bonus

        # Streak multiplier
        if state.streak >= 10:
            total_xp = int(total_xp * 1.5)  # 1.5x for 10+ streak
        elif state.streak >= 5:
            total_xp = int(total_xp * 1.2)  # 1.2x for 5+ streak

        old_level = state.level
        state.xp += total_xp
        state.xp_history.append((total_xp, reason))

        # Check for level up
        new_level = self._calculate_level(state.xp)
        level_up_msg = None
        if new_level != old_level:
            state.level = new_level
            level_up_msg = render_level_up(old_level, new_level, state.xp)
            self._check_level_achievements(state)

        logger.debug(f"🎮 +{total_xp} XP ({reason}) → total={state.xp} level={state.level.value}")
        return total_xp, level_up_msg

    def record_correct_answer(self, state: PlayerState) -> Dict[str, Any]:
        """Record a correct answer and process streak/achievements."""
        state.correct_answers += 1
        state.streak += 1
        state.max_streak = max(state.max_streak, state.streak)

        result = {"xp": 0, "level_up": None, "achievements": [], "streak": state.streak}

        # Award XP
        reason = "detailed_answer" if state.streak >= 3 else "correct_answer"
        xp, level_msg = self.award_xp(state, reason)
        result["xp"] = xp
        result["level_up"] = level_msg

        # Check streak bonuses
        if state.streak == 5:
            bonus_xp, _ = self.award_xp(state, "streak_bonus_5")
            result["xp"] += bonus_xp
        elif state.streak == 10:
            bonus_xp, _ = self.award_xp(state, "streak_bonus_10")
            result["xp"] += bonus_xp

        # Check achievements
        result["achievements"] = self._check_achievements(state)

        return result

    def record_wrong_answer(self, state: PlayerState) -> Dict[str, Any]:
        """Record a wrong answer and reset streak."""
        state.wrong_answers += 1
        state.streak = 0

        # Track recovery potential
        state.wrong_answer_recovery += 1

        result = {"streak_lost": True, "encouragement": self._get_encouragement(state)}
        result["achievements"] = self._check_achievements(state)
        return result

    def record_lesson_complete(self, state: PlayerState, topic: str = "") -> Dict[str, Any]:
        """Record a completed lesson."""
        state.lessons_completed += 1
        if topic and topic not in state.topics_studied:
            state.topics_studied.append(topic)

        result = {"xp": 0, "level_up": None, "achievements": []}
        xp, level_msg = self.award_xp(state, "lesson_complete")
        result["xp"] = xp
        result["level_up"] = level_msg

        # Check speed achievement
        elapsed = time.time() - state.session_start
        if elapsed < 120 and "speed_demon" in state.achievements and not state.achievements["speed_demon"].unlocked:
            self._unlock_achievement(state, "speed_demon")
            result["achievements"].append(state.achievements["speed_demon"])

        result["achievements"].extend(self._check_achievements(state))
        return result

    def record_anti_pattern_learned(self, state: PlayerState) -> int:
        """Record learning an anti-pattern. Returns XP awarded."""
        state.anti_patterns_learned += 1
        xp, _ = self.award_xp(state, "anti_pattern_learned")
        self._check_achievements(state)
        return xp

    def record_flowchart_requested(self, state: PlayerState) -> int:
        """Record requesting a flowchart. Returns XP awarded."""
        state.flowcharts_requested += 1
        xp, _ = self.award_xp(state, "flowchart_requested")
        self._check_achievements(state)
        return xp

    def record_insight_discovered(self, state: PlayerState) -> int:
        """Record discovering an insight. Returns XP awarded."""
        state.insights_discovered += 1
        xp, _ = self.award_xp(state, "insight_discovery")
        self._check_achievements(state)
        return xp

    def record_principle_found(self, state: PlayerState) -> int:
        """Record finding an expert principle. Returns XP awarded."""
        state.principles_found += 1
        xp, _ = self.award_xp(state, "anti_pattern_learned")
        self._check_achievements(state)
        return xp

    # ──────────────────────────────────────
    # Challenge System
    # ──────────────────────────────────────

    def create_challenge(
        self,
        mode: ChallengeMode,
        topic: str,
        questions: Optional[List[ChallengeQuestion]] = None,
    ) -> Challenge:
        """
        Create a gamified challenge.

        If no questions provided, generates them via LLM.
        """
        challenge = Challenge(mode=mode, topic=topic)

        if questions:
            challenge.questions = questions
        elif self.generate_fn:
            challenge.questions = self._generate_challenge_questions(mode, topic)
        else:
            challenge.questions = self._get_fallback_questions(mode, topic)

        challenge.max_score = sum(q.xp_value for q in challenge.questions)
        self._active_challenges[challenge.id] = challenge

        logger.info(
            f"⚔️ Challenge created: mode={mode.value}, "
            f"topic={topic}, questions={len(challenge.questions)}"
        )
        return challenge

    def answer_challenge(
        self,
        challenge_id: str,
        answer: str,
        state: PlayerState,
    ) -> Dict[str, Any]:
        """
        Submit an answer to the current challenge question.

        Returns result dict with correctness, XP, explanation.
        """
        challenge = self._active_challenges.get(challenge_id)
        if not challenge or challenge.completed:
            return {"error": "Challenge not found or already completed"}

        if challenge.current_question >= len(challenge.questions):
            return {"error": "All questions answered"}

        question = challenge.questions[challenge.current_question]
        is_correct = self._check_answer(answer, question.correct_answer)

        result = {
            "correct": is_correct,
            "explanation": question.explanation,
            "correct_answer": question.correct_answer,
            "xp_earned": 0,
            "question_number": challenge.current_question + 1,
            "total_questions": len(challenge.questions),
        }

        if is_correct:
            challenge.score += question.xp_value
            game_result = self.record_correct_answer(state)
            result["xp_earned"] = question.xp_value
            result["game"] = game_result
        else:
            game_result = self.record_wrong_answer(state)
            result["game"] = game_result

        # Advance to next question
        challenge.current_question += 1

        # Check if challenge is complete
        if challenge.current_question >= len(challenge.questions):
            challenge.completed = True
            challenge.perfect = challenge.score == challenge.max_score
            result["challenge_complete"] = True
            result["challenge_result"] = render_challenge_result(challenge)

            # Award challenge XP
            if challenge.mode == ChallengeMode.BOSS_BATTLE:
                self.award_xp(state, "boss_battle_win")
                state.boss_battles_won += 1
            else:
                self.award_xp(state, "challenge_complete")
                state.challenges_won += 1

            if challenge.mode == ChallengeMode.SNIPER:
                state.sniper_wins += 1

            if challenge.perfect:
                self._unlock_achievement(state, "perfectionist")

            self._check_achievements(state)

        return result

    def get_challenge_status(self, challenge_id: str) -> Optional[str]:
        """Get formatted challenge status."""
        challenge = self._active_challenges.get(challenge_id)
        if not challenge:
            return None

        q = challenge.current_question
        total = len(challenge.questions)
        pct = (challenge.score / max(challenge.max_score, 1)) * 100

        return (
            f"⚔️ Challenge: {challenge.mode.value} | "
            f"Question {min(q+1, total)}/{total} | "
            f"Score: {challenge.score}/{challenge.max_score} ({pct:.0f}%)"
        )

    # ──────────────────────────────────────
    # Internal — Level Calculations
    # ──────────────────────────────────────

    def _calculate_level(self, xp: int) -> PlayerLevel:
        """Determine player level from XP."""
        current = PlayerLevel.NOVICE
        for level, threshold in LEVEL_THRESHOLDS.items():
            if xp >= threshold:
                current = level
        return current

    def _get_next_level(self, level: PlayerLevel) -> Optional[PlayerLevel]:
        """Get the next level after the current one."""
        return _get_next_level(level)

    # ──────────────────────────────────────
    # Internal — Achievement Checks
    # ──────────────────────────────────────

    def _check_achievements(self, state: PlayerState) -> List[Achievement]:
        """Check and unlock any earned achievements. Returns newly unlocked."""
        newly_unlocked = []

        checks = {
            "first_blood": state.lessons_completed >= 1,
            "mistake_hunter": state.anti_patterns_learned >= 5,
            "flowchart_master": state.flowcharts_requested >= 3,
            "streak_warrior": state.max_streak >= 5,
            "streak_inferno": state.max_streak >= 10,
            "deep_thinker": state.insights_discovered >= 3,
            "explorer": len(state.topics_studied) >= 3,
            "resilient": state.wrong_answer_recovery >= 3 and state.correct_answers > state.wrong_answers,
            "principle_seeker": state.principles_found >= 3,
            "boss_slayer": state.boss_battles_won >= 1,
            "sniper_elite": state.sniper_wins >= 3,
        }

        for aid, condition in checks.items():
            if condition and aid in state.achievements and not state.achievements[aid].unlocked:
                self._unlock_achievement(state, aid)
                newly_unlocked.append(state.achievements[aid])

        return newly_unlocked

    def _check_level_achievements(self, state: PlayerState):
        """Check level-based achievements."""
        if state.level == PlayerLevel.APPRENTICE:
            self._unlock_achievement(state, "level_up_first")
        elif state.level == PlayerLevel.MASTER:
            self._unlock_achievement(state, "master_class")

    def _unlock_achievement(self, state: PlayerState, achievement_id: str):
        """Unlock an achievement."""
        if achievement_id in state.achievements:
            ach = state.achievements[achievement_id]
            if not ach.unlocked:
                ach.unlocked = True
                ach.unlocked_at = time.time()
                logger.info(f"🏆 Achievement unlocked: {ach.name}")

    # ──────────────────────────────────────
    # Internal — Challenge Generation
    # ──────────────────────────────────────

    def _generate_challenge_questions(
        self, mode: ChallengeMode, topic: str
    ) -> List[ChallengeQuestion]:
        """Generate challenge questions via LLM."""
        mode_descriptions = {
            ChallengeMode.QUIZ: "rapid-fire knowledge test questions",
            ChallengeMode.BOSS_BATTLE: "a multi-step complex problem that builds on itself",
            ChallengeMode.PUZZLE: "questions where the student finds anti-patterns or bugs",
            ChallengeMode.SNIPER: "questions where the student identifies ONE critical mistake",
        }

        desc = mode_descriptions.get(mode, "test questions")
        n_questions = 3 if mode == ChallengeMode.BOSS_BATTLE else 5

        prompt = f"""\
Generate {n_questions} {desc} about: {topic}

Output a JSON array. Each question object has:
{{
  "question": "The question text",
  "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
  "correct_answer": "The letter of the correct answer (A, B, C, or D)",
  "explanation": "Why this is the correct answer"
}}

Make questions progressively harder. Include tricky but fair distractors.
"""
        try:
            result = self._call_llm(prompt)
            import json
            import re
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                items = json.loads(match.group(0))
                questions = []
                for item in items[:n_questions]:
                    q = ChallengeQuestion(
                        question=item.get("question", ""),
                        options=item.get("options", []),
                        correct_answer=item.get("correct_answer", ""),
                        explanation=item.get("explanation", ""),
                        xp_value=30 if mode == ChallengeMode.BOSS_BATTLE else 20,
                        time_limit_seconds=90 if mode == ChallengeMode.BOSS_BATTLE else 60,
                    )
                    questions.append(q)
                return questions
        except Exception as e:
            logger.warning(f"Challenge generation failed: {e}")

        return self._get_fallback_questions(mode, topic)

    def _get_fallback_questions(
        self, mode: ChallengeMode, topic: str
    ) -> List[ChallengeQuestion]:
        """Generate basic fallback questions when LLM is unavailable."""
        return [
            ChallengeQuestion(
                question=f"What is the most important principle to remember about {topic}?",
                correct_answer="Apply defensive programming and always validate inputs.",
                explanation="This is a foundational principle that prevents many common errors.",
                xp_value=20,
            ),
            ChallengeQuestion(
                question=f"What is the most common mistake when working with {topic}?",
                correct_answer="Not handling edge cases and error conditions properly.",
                explanation="Edge cases are where most bugs hide.",
                xp_value=20,
            ),
            ChallengeQuestion(
                question=f"How would you debug an issue related to {topic}?",
                correct_answer="Isolate the problem, form a hypothesis, test it, then fix.",
                explanation="Systematic debugging is more effective than guessing.",
                xp_value=20,
            ),
        ]

    def _check_answer(self, given: str, correct: str) -> bool:
        """Check if a given answer matches the correct one (fuzzy)."""
        given_clean = given.strip().lower()
        correct_clean = correct.strip().lower()

        # Exact match
        if given_clean == correct_clean:
            return True

        # Letter match (A, B, C, D)
        if len(given_clean) == 1 and given_clean in correct_clean[:1]:
            return True

        # Contains the key answer
        if correct_clean in given_clean or given_clean in correct_clean:
            return True

        # Check if first word matches (for "A)" style answers)
        if given_clean and correct_clean and given_clean[0] == correct_clean[0]:
            if len(given_clean) <= 2:
                return True

        return False

    def _get_encouragement(self, state: PlayerState) -> str:
        """Get an encouraging message after a wrong answer."""
        messages = [
            "💪 Don't give up! Every mistake is a learning opportunity!",
            "🧠 The best learners make mistakes — that's how neurons connect!",
            "🔥 You lost your streak, but you'll build a bigger one!",
            "⚡ Wrong answer, but you're still making progress!",
            "🎯 Close! Think about it from a different angle.",
            "🌟 Remember: even experts started as beginners!",
            "💎 Mistakes are the raw material of expertise!",
        ]
        import random
        return random.choice(messages)

    def _call_llm(self, prompt: str) -> str:
        """Call LLM safely."""
        if not self.generate_fn:
            return ""
        try:
            result = self.generate_fn(prompt)
            if hasattr(result, 'answer'):
                return result.answer
            return str(result)
        except Exception as e:
            logger.error(f"LLM call failed in GamifiedTutorEngine: {e}")
            return ""


# Module-level helper
def _get_next_level(level: PlayerLevel) -> Optional[PlayerLevel]:
    """Get the next level after current."""
    levels = list(PlayerLevel)
    idx = levels.index(level)
    if idx + 1 < len(levels):
        return levels[idx + 1]
    return None
