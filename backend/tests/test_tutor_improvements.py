"""
Tests for the Improved Tutor System
────────────────────────────────────
Tests cover:
  1. MistakeLessonEngine — lesson generation, curriculum building, visual formatting
  2. FlowchartGenerator — Mermaid syntax, validation, ASCII rendering, all chart types
  3. GamifiedTutorEngine — XP, levels, streaks, achievements, challenges
  4. Integration — anti-pattern lessons in ExpertTutorEngine sessions
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ──────────────────────────────────────────────
# 1. Mistake Lesson Engine Tests
# ──────────────────────────────────────────────

def test_anti_pattern_lesson_creation():
    """Test creating AntiPatternLesson dataclass."""
    from brain.mistake_lesson_engine import AntiPatternLesson

    lesson = AntiPatternLesson(
        title="Never Trust Raw User Input",
        category="input_validation",
        bad_approach="json.loads(user_input)  # No validation!",
        why_it_fails="Malformed input causes crashes and injection attacks",
        correct_approach="if user_input: validated = json.loads(sanitize(user_input))",
        expert_principle="Always validate and sanitize ALL external inputs",
        danger_score=8.5,
    )
    assert lesson.title == "Never Trust Raw User Input"
    assert lesson.category == "input_validation"
    assert lesson.danger_score == 8.5
    assert lesson.id.startswith("apl-")
    print("✅ AntiPatternLesson creation works")


def test_mistake_curriculum():
    """Test MistakeCurriculum ordering and filtering."""
    from brain.mistake_lesson_engine import AntiPatternLesson, MistakeCurriculum

    lessons = [
        AntiPatternLesson(title="Low danger", category="logic", danger_score=2.0),
        AntiPatternLesson(title="High danger", category="security", danger_score=9.0),
        AntiPatternLesson(title="Medium danger", category="input_validation", danger_score=5.5),
    ]
    curriculum = MistakeCurriculum(topic="testing", lessons=lessons)

    # Test most dangerous
    top = curriculum.get_most_dangerous(2)
    assert len(top) == 2
    assert top[0].title == "High danger"
    assert top[1].title == "Medium danger"

    # Test by category
    security = curriculum.get_by_category("security")
    assert len(security) == 1
    assert security[0].danger_score == 9.0

    print("✅ MistakeCurriculum ordering and filtering works")


def test_mistake_lesson_engine_without_memory():
    """Test MistakeLessonEngine when no memory manager is available."""
    from brain.mistake_lesson_engine import MistakeLessonEngine

    engine = MistakeLessonEngine(memory_manager=None, generate_fn=None)
    curriculum = engine.generate_curriculum("Python basics")

    # Without memory or LLM, should return empty curriculum
    assert curriculum.topic == "Python basics"
    assert len(curriculum.lessons) == 0
    print("✅ MistakeLessonEngine without memory works (empty curriculum)")


def test_mistake_lesson_engine_with_memory():
    """Test MistakeLessonEngine with real MemoryManager data."""
    from brain.mistake_lesson_engine import MistakeLessonEngine
    from brain.memory import MemoryManager, FailureTuple

    with tempfile.TemporaryDirectory() as tmpdir:
        mem = MemoryManager(persist_dir=tmpdir)

        # Store some failures
        mem.store_failure(FailureTuple(
            task="Parse JSON input",
            solution="json.loads(data)",
            observation="Crashed on empty string",
            root_cause="No null check before parsing",
            fix="Add if data: check before json.loads()",
            category="input_validation",
            severity=0.8,
        ))
        mem.store_failure(FailureTuple(
            task="Parse XML input",
            solution="xml.parse(data)",
            observation="XML injection vulnerability",
            root_cause="No sanitization of user input",
            fix="Use defusedxml library",
            category="input_validation",
            severity=0.9,
        ))
        mem.store_failure(FailureTuple(
            task="Calculate total",
            solution="total = a + b",
            observation="Type error: string + int",
            root_cause="No type checking",
            fix="Convert to int/float first",
            category="type_error",
            severity=0.5,
        ))

        # Create engine with memory
        engine = MistakeLessonEngine(memory_manager=mem, generate_fn=None)
        curriculum = engine.generate_curriculum()

        assert len(curriculum.lessons) >= 2  # At least 2 categories
        assert curriculum.total_danger_score > 0

        # Check that lessons have content from failures
        categories = [l.category for l in curriculum.lessons]
        assert "input_validation" in categories

        # Test visual formatting
        if curriculum.lessons:
            visual = engine.format_lesson_visual(curriculum.lessons[0])
            assert "ANTI-PATTERN" in visual
            assert "WRONG WAY" in visual
            assert "RIGHT WAY" in visual

            prompt = engine.format_lesson_for_prompt(curriculum.lessons[0])
            assert "BAD:" in prompt
            assert "GOOD:" in prompt

        print(f"✅ MistakeLessonEngine with memory: {len(curriculum.lessons)} lessons generated")
        for l in curriculum.lessons:
            print(f"   ⚠️ {l.title} (danger={l.danger_score:.1f}, category={l.category})")


def test_anti_pattern_flowchart_generation():
    """Test that anti-pattern lessons generate valid Mermaid flowcharts."""
    from brain.mistake_lesson_engine import MistakeLessonEngine, AntiPatternLesson

    engine = MistakeLessonEngine(generate_fn=None)

    lesson = AntiPatternLesson(
        title="Test Pattern",
        category="testing",
        bad_approach="Skip tests",
        correct_approach="Write tests first",
        why_it_fails="Bugs go undetected",
    )

    flowchart = engine._generate_anti_pattern_flowchart(lesson)
    assert "graph TD" in flowchart
    assert "BAD" in flowchart
    assert "GOOD" in flowchart
    assert "-->" in flowchart
    assert "style BAD fill:#ff4444" in flowchart
    assert "style GOOD fill:#44bb44" in flowchart
    print("✅ Anti-pattern flowchart generation works")


# ──────────────────────────────────────────────
# 2. Flowchart Generator Tests
# ──────────────────────────────────────────────

def test_flowchart_generator_all_types():
    """Test generating all flowchart types with templates."""
    from brain.flowchart_generator import FlowchartGenerator, FlowchartType

    gen = FlowchartGenerator(generate_fn=None)

    for chart_type in FlowchartType:
        chart = gen.generate("Python Programming", chart_type=chart_type, use_llm=False)
        assert "graph" in chart, f"Missing 'graph' in {chart_type.value}"
        assert "-->" in chart, f"Missing '-->' in {chart_type.value}"
        print(f"  ✅ {chart_type.value} template OK")

    print("✅ All flowchart types generate valid Mermaid")


def test_flowchart_anti_pattern_chart():
    """Test specialized anti-pattern flowchart generation."""
    from brain.flowchart_generator import FlowchartGenerator

    gen = FlowchartGenerator()
    chart = gen.generate_anti_pattern_chart(
        bad_approach="Using eval() on user input",
        good_approach="Using ast.literal_eval() with validation",
        failure_reason="Remote code execution vulnerability",
        topic="Input Handling",
    )
    assert "graph TD" in chart
    assert "BAD" in chart
    assert "GOOD" in chart
    assert "#ff4444" in chart  # Red for bad
    assert "#44bb44" in chart  # Green for good
    print("✅ Anti-pattern chart generation works")


def test_flowchart_learning_path():
    """Test learning path flowchart generation."""
    from brain.flowchart_generator import FlowchartGenerator

    gen = FlowchartGenerator()
    steps = [
        "Variables and Data Types",
        "Control Flow (if/else, loops)",
        "Functions and Modules",
        "Object-Oriented Programming",
        "Error Handling",
        "Advanced Topics",
    ]
    chart = gen.generate_learning_path(steps, topic="Python")
    assert "graph TD" in chart
    assert "S0" in chart
    assert "S5" in chart  # Last step
    assert "📚" in chart  # Start emoji
    assert "🏆" in chart  # End emoji
    print("✅ Learning path flowchart works")


def test_flowchart_concept_map():
    """Test concept map generation."""
    from brain.flowchart_generator import FlowchartGenerator

    gen = FlowchartGenerator()
    chart = gen.generate_concept_map(
        main_concept="Machine Learning",
        sub_concepts={
            "Supervised": ["Classification", "Regression"],
            "Unsupervised": ["Clustering", "Dimensionality Reduction"],
            "Reinforcement": ["Policy Gradient", "Q-Learning"],
        },
    )
    assert "graph LR" in chart
    assert "CORE" in chart
    assert "Machine Learning" in chart
    print("✅ Concept map generation works")


def test_flowchart_ascii_rendering():
    """Test ASCII flowchart rendering."""
    from brain.flowchart_generator import render_ascii_flowchart, render_ascii_comparison

    # Test vertical flowchart
    steps = ["Start", "Process Data", "Validate", "Output"]
    ascii_chart = render_ascii_flowchart(steps, "Test Flow")
    assert "Start" in ascii_chart
    assert "Output" in ascii_chart
    assert "▼" in ascii_chart
    assert "═" in ascii_chart
    print("✅ ASCII vertical flowchart works")

    # Test comparison chart
    comparison = render_ascii_comparison(
        "Bad Approach", ["No validation", "No error handling"],
        "Good Approach", ["Input validation", "Error handling"],
    )
    assert "❌" in comparison
    assert "✅" in comparison
    assert "No validation" in comparison
    assert "Input validation" in comparison
    print("✅ ASCII comparison chart works")


def test_flowchart_mermaid_validation():
    """Test Mermaid syntax validation."""
    from brain.flowchart_generator import FlowchartGenerator

    gen = FlowchartGenerator()

    # Valid mermaid
    assert gen._validate_mermaid("graph TD\n    A[Start] --> B[End]")
    assert gen._validate_mermaid("flowchart LR\n    A --> B\n    B --> C")

    # Invalid mermaid
    assert not gen._validate_mermaid("")
    assert not gen._validate_mermaid("not mermaid at all")
    assert not gen._validate_mermaid("graph TD\n    no edges here")

    print("✅ Mermaid validation works")


def test_flowchart_safe_text():
    """Test text escaping for Mermaid labels."""
    from brain.flowchart_generator import FlowchartGenerator

    gen = FlowchartGenerator()
    safe = gen._safe_mermaid_text

    assert '"' not in safe('He said "hello"')
    assert '[' not in safe('array[0]')
    assert '{' not in safe('dict{key}')
    assert '<' not in safe('<script>alert()</script>')
    print("✅ Mermaid text escaping works")


# ──────────────────────────────────────────────
# 3. Gamified Tutor Engine Tests
# ──────────────────────────────────────────────

def test_gamification_player_creation():
    """Test creating a new player with initial state."""
    from agents.profiles.ultimate_tutor import GamifiedTutorEngine, PlayerLevel

    game = GamifiedTutorEngine()
    player = game.create_player()

    assert player.xp == 0
    assert player.level == PlayerLevel.NOVICE
    assert player.streak == 0
    assert len(player.achievements) > 0
    assert all(not a.unlocked for a in player.achievements.values())
    print("✅ Player creation works")


def test_gamification_xp_and_levels():
    """Test XP awarding and level progression."""
    from agents.profiles.ultimate_tutor import GamifiedTutorEngine, PlayerLevel

    game = GamifiedTutorEngine()
    player = game.create_player()

    # Award XP manually
    xp, level_msg = game.award_xp(player, "correct_answer")
    assert xp > 0
    assert player.xp == xp
    assert level_msg is None  # Not enough for level up yet

    # Force level up by awarding lots of XP
    total_xp = 0
    while player.level == PlayerLevel.NOVICE:
        x, msg = game.award_xp(player, "lesson_complete")
        total_xp += x
        if msg:
            assert "LEVEL UP" in msg
            break

    assert player.level.value != "Novice" or total_xp >= 100
    print(f"✅ XP and leveling works: {player.xp} XP, level={player.level.value}")


def test_gamification_streaks():
    """Test streak tracking and bonuses."""
    from agents.profiles.ultimate_tutor import GamifiedTutorEngine

    game = GamifiedTutorEngine()
    player = game.create_player()

    # Build a streak
    for i in range(6):
        result = game.record_correct_answer(player)
        assert result["streak"] == i + 1

    assert player.streak == 6
    assert player.max_streak == 6
    assert player.correct_answers == 6

    # Break streak
    result = game.record_wrong_answer(player)
    assert result["streak_lost"] is True
    assert player.streak == 0
    assert player.max_streak == 6  # Max preserved

    # Rebuild
    game.record_correct_answer(player)
    assert player.streak == 1

    print("✅ Streak tracking works")


def test_gamification_achievements():
    """Test achievement unlocking."""
    from agents.profiles.ultimate_tutor import GamifiedTutorEngine

    game = GamifiedTutorEngine()
    player = game.create_player()

    # Trigger "streak_warrior" (5 correct in a row)
    for _ in range(5):
        result = game.record_correct_answer(player)

    # Check if streak_warrior was unlocked
    assert player.achievements["streak_warrior"].unlocked
    print("✅ Achievement unlocking works (streak_warrior)")

    # Trigger "first_blood" (complete a lesson)
    game.record_lesson_complete(player, topic="Python")
    assert player.achievements["first_blood"].unlocked
    print("✅ Achievement unlocking works (first_blood)")

    # Trigger "explorer" (3 different topics)
    game.record_lesson_complete(player, topic="JavaScript")
    game.record_lesson_complete(player, topic="Rust")
    assert player.achievements["explorer"].unlocked
    print("✅ Achievement unlocking works (explorer)")


def test_gamification_dashboard():
    """Test dashboard rendering."""
    from agents.profiles.ultimate_tutor import GamifiedTutorEngine, render_dashboard

    game = GamifiedTutorEngine()
    player = game.create_player()

    # Add some stats
    for _ in range(3):
        game.record_correct_answer(player)
    game.record_lesson_complete(player, "Python")
    player.anti_patterns_learned = 5
    player.flowcharts_requested = 2

    dashboard = render_dashboard(player)
    assert "LEARNING DASHBOARD" in dashboard
    assert "Level:" in dashboard
    assert "XP:" in dashboard
    assert "Streak:" in dashboard
    assert "Achievements:" in dashboard
    print("✅ Dashboard rendering works")
    print(dashboard)


def test_gamification_challenges():
    """Test challenge creation and answering."""
    from agents.profiles.ultimate_tutor import GamifiedTutorEngine, ChallengeMode

    game = GamifiedTutorEngine()
    player = game.create_player()

    # Create a challenge (fallback questions without LLM)
    challenge = game.create_challenge(
        mode=ChallengeMode.QUIZ,
        topic="Python Error Handling",
    )
    assert len(challenge.questions) >= 1
    assert challenge.max_score > 0
    assert not challenge.completed

    # Answer correctly
    correct_answer = challenge.questions[0].correct_answer
    result = game.answer_challenge(challenge.id, correct_answer, player)
    assert result["correct"] is True
    assert result["xp_earned"] > 0

    print(f"✅ Challenge system works: {len(challenge.questions)} questions, score={challenge.score}")


def test_gamification_encouragement():
    """Test encouragement messages on wrong answers."""
    from agents.profiles.ultimate_tutor import GamifiedTutorEngine

    game = GamifiedTutorEngine()
    player = game.create_player()

    result = game.record_wrong_answer(player)
    assert "encouragement" in result
    assert len(result["encouragement"]) > 10
    print(f"✅ Encouragement: {result['encouragement']}")


# ──────────────────────────────────────────────
# 4. Integration Tests
# ──────────────────────────────────────────────

def test_expert_tutor_new_techniques():
    """Test that new techniques are available in the enum."""
    from agents.profiles.ultimate_tutor import TeachingTechnique

    # Verify new techniques exist
    assert TeachingTechnique.ANTI_PATTERN.value == "anti_pattern"
    assert TeachingTechnique.VISUAL_FLOWCHART.value == "visual_flowchart"
    assert TeachingTechnique.GAME_CHALLENGE.value == "game_challenge"

    # Verify old techniques still work
    assert TeachingTechnique.FEYNMAN.value == "feynman"
    assert TeachingTechnique.SOCRATIC.value == "socratic"

    # Total should be 9 (added DEEP_SOCRATIC)
    assert len(TeachingTechnique) == 9
    print("✅ All 9 teaching techniques available")


def test_expert_tutor_technique_prompts():
    """Test that all techniques have prompts."""
    from agents.profiles.ultimate_tutor import _TECHNIQUE_PROMPTS, TeachingTechnique

    for technique in TeachingTechnique:
        assert technique in _TECHNIQUE_PROMPTS, f"Missing prompt for {technique.value}"
        prompt = _TECHNIQUE_PROMPTS[technique]
        assert len(prompt) > 50, f"Prompt too short for {technique.value}"

    print("✅ All teaching techniques have prompts")


def test_expert_tutor_session_fields():
    """Test that TutoringSession has the new fields."""
    from agents.profiles.ultimate_tutor import TutoringSession

    session = TutoringSession()
    assert hasattr(session, 'anti_pattern_lessons')
    assert hasattr(session, 'mistake_curriculum')
    assert hasattr(session, 'anti_patterns_shown')
    assert hasattr(session, 'player_state')
    assert hasattr(session, 'active_challenge')
    assert hasattr(session, 'game_engine')

    assert session.anti_pattern_lessons == []
    assert session.anti_patterns_shown == 0
    assert session.player_state is None
    print("✅ TutoringSession has all new fields")


def test_expert_tutor_engine_init():
    """Test ExpertTutorEngine initialization with new modules."""
    from agents.profiles.ultimate_tutor import UltimateTutorEngine

    def mock_generate(prompt, system_prompt="", temperature=0.7):
        return "Mock response for testing."

    engine = UltimateTutorEngine(generate_fn=mock_generate)

    # Check new modules initialized
    assert engine._mistake_engine is not None
    assert engine._flowchart_gen is not None
    assert engine._game_engine is not None
    print("✅ UltimateTutorEngine initializes all new modules")


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🧪 TUTOR IMPROVEMENT TESTS")
    print("=" * 60)

    # Module 1: Mistake Lesson Engine
    print("\n── Mistake Lesson Engine ──")
    test_anti_pattern_lesson_creation()
    test_mistake_curriculum()
    test_mistake_lesson_engine_without_memory()
    test_mistake_lesson_engine_with_memory()
    test_anti_pattern_flowchart_generation()

    # Module 2: Flowchart Generator
    print("\n── Flowchart Generator ──")
    test_flowchart_generator_all_types()
    test_flowchart_anti_pattern_chart()
    test_flowchart_learning_path()
    test_flowchart_concept_map()
    test_flowchart_ascii_rendering()
    test_flowchart_mermaid_validation()
    test_flowchart_safe_text()

    # Module 3: Gamified Tutor Engine
    print("\n── Gamified Tutor Engine ──")
    test_gamification_player_creation()
    test_gamification_xp_and_levels()
    test_gamification_streaks()
    test_gamification_achievements()
    test_gamification_dashboard()
    test_gamification_challenges()
    test_gamification_encouragement()

    # Module 4: Integration
    print("\n── Integration Tests ──")
    test_expert_tutor_new_techniques()
    test_expert_tutor_technique_prompts()
    test_expert_tutor_session_fields()
    test_expert_tutor_engine_init()

    print("\n" + "=" * 60)
    print("  ✅ ALL TUTOR IMPROVEMENT TESTS PASSED!")
    print("=" * 60 + "\n")
