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

    # Module 5: New Expert Modules (v2 upgrade)
    print("\n── Expert Tutor v2 Modules ──")
    test_tutor_tool_bridge()
    test_truth_verifier()
    test_misconception_preempt()
    test_root_cause_chain()
    test_tool_demo_result_formatting()
    test_truth_report_api_dict()
    test_misconception_first_technique()
    test_enhanced_session_fields()
    test_llm_retry_logic()

    print("\n" + "=" * 60)
    print("  ✅ ALL TUTOR IMPROVEMENT TESTS PASSED!")
    print("=" * 60 + "\n")


# ══════════════════════════════════════════════════════════════
# Module 5: Expert Tutor v2 Tests
# ══════════════════════════════════════════════════════════════

def test_tutor_tool_bridge():
    """Test TutorToolBridge initialization and basic operations."""
    from brain.tutor_tool_bridge import TutorToolBridge, ToolDemoResult, ToolCategory

    bridge = TutorToolBridge(agent_controller=None, generate_fn=None)
    assert isinstance(bridge.available_tools, list)
    assert bridge.demo_count == 0

    # Test calculate fallback (uses Python eval for basic math)
    result = bridge.calculate("2 + 2")
    assert result.success
    assert "4" in result.formatted_output
    assert result.tool == ToolCategory.CALCULATOR
    assert result.execution_ms >= 0

    # Test session summary
    summary = bridge.get_session_summary()
    assert summary["total_demos"] == 1
    assert summary["successful"] == 1

    print("✅ TutorToolBridge basic operations work")


def test_truth_verifier():
    """Test TruthVerifier hallucination detection and misconception checking."""
    from brain.truth_verifier import TruthVerifier, TruthReport

    verifier = TruthVerifier(generate_fn=None, tool_bridge=None)

    # Test hallucination detection on suspicious text
    report = verifier.verify_response(
        "Python was invented in 1991. Exactly 95.7% of developers prefer it. "
        "The best and only correct way to learn is through practice.",
        topic="python",
    )
    assert isinstance(report, TruthReport)
    assert len(report.hallucination_signals) > 0
    assert "absolutist_claim" in report.hallucination_signals or "specific_statistic" in report.hallucination_signals

    # Test trust badge
    badge = report.trust_badge
    assert any(emoji in badge for emoji in ["✅", "⚠️", "❓"])

    # Test API dict output
    api = report.to_api_dict()
    assert "truth_score" in api
    assert "hallucination_signals" in api
    assert "verification_time_ms" in api

    print("✅ TruthVerifier hallucination detection works")


def test_misconception_preempt():
    """Test MisconceptionPreempt dataclass and formatting."""
    from brain.mistake_lesson_engine import MisconceptionPreempt

    mp = MisconceptionPreempt(
        topic="python",
        wrong_belief="Python is interpreted, not compiled",
        truth="Python IS compiled to bytecode first",
        why_people_believe_it="Because there's no explicit compile step",
        reveal_question="What do you think happens when you run 'python script.py'?",
        prevalence="very_common",
    )

    block = mp.to_teaching_block()
    assert "BEFORE WE START" in block
    assert "Most people" in block  # very_common → Most people
    assert mp.wrong_belief in block
    assert mp.truth in block
    assert mp.id.startswith("mp-")

    print("✅ MisconceptionPreempt formatting works")


def test_root_cause_chain():
    """Test RootCauseChain dataclass and Mermaid generation."""
    from brain.mistake_lesson_engine import RootCauseChain

    chain = RootCauseChain(
        topic="error_handling",
        assumption="Exceptions don't need to be caught",
        mistake="Using bare except clauses",
        symptom="Silent failures, hard-to-debug issues",
        root_cause="Catching too broadly hides the real error",
        fix="Catch specific exception types",
        principle="Always catch the narrowest exception possible",
    )

    block = chain.to_teaching_block()
    assert "ROOT-CAUSE CHAIN" in block
    assert "Assumption" in block
    assert "Principle" in block
    assert chain.id.startswith("rcc-")

    # Test Mermaid diagram generation
    mermaid = chain.to_mermaid()
    assert "graph TD" in mermaid
    assert "Assumption" in mermaid
    assert "Principle" in mermaid
    assert "style A" in mermaid  # Has styling

    print("✅ RootCauseChain with Mermaid generation works")


def test_tool_demo_result_formatting():
    """Test ToolDemoResult to_teaching_block formatting."""
    from brain.tutor_tool_bridge import ToolDemoResult, ToolCategory

    # Success case
    success = ToolDemoResult(
        tool=ToolCategory.CODE_EXECUTOR,
        success=True,
        formatted_output="Hello, World!",
        execution_ms=42.5,
        teaching_annotation="Running a basic print statement",
    )
    block = success.to_teaching_block()
    assert "LIVE DEMONSTRATION" in block
    assert "Hello, World!" in block
    assert "42ms" in block

    # Error case (error as teaching moment)
    error = ToolDemoResult(
        tool=ToolCategory.CALCULATOR,
        success=False,
        error_message="Division by zero",
    )
    block = error.to_teaching_block()
    assert "encountered an issue" in block
    assert "teaching moment" in block

    print("✅ ToolDemoResult formatting works correctly")


def test_truth_report_api_dict():
    """Test TruthReport to_api_dict for proper API serialization."""
    from brain.truth_verifier import TruthReport

    report = TruthReport(
        original_response="Test response",
        overall_confidence=0.85,
        claims_checked=5,
        claims_verified=4,
        claims_flagged=1,
        hallucination_signals=["specific_statistic"],
        sources=[{"title": "Source 1", "url": "http://example.com"}],
        verification_time_ms=123.456,
    )

    api = report.to_api_dict()
    assert api["truth_score"] == 0.85
    assert api["claims_checked"] == 5
    assert api["claims_verified"] == 4
    assert api["claims_flagged"] == 1
    assert len(api["hallucination_signals"]) == 1
    assert api["verification_time_ms"] == 123.5  # rounded
    assert "High Confidence" in report.trust_badge

    print("✅ TruthReport API serialization works")


def test_misconception_first_technique():
    """Test that MISCONCEPTION_FIRST technique exists and has a prompt."""
    from agents.profiles.ultimate_tutor import TeachingTechnique, TECHNIQUE_PROMPTS

    assert hasattr(TeachingTechnique, "MISCONCEPTION_FIRST")
    assert TeachingTechnique.MISCONCEPTION_FIRST.value == "misconception_first"
    assert TeachingTechnique.MISCONCEPTION_FIRST in TECHNIQUE_PROMPTS
    prompt = TECHNIQUE_PROMPTS[TeachingTechnique.MISCONCEPTION_FIRST]
    assert "MISCONCEPTION-FIRST" in prompt
    assert "BUST MYTHS" in prompt
    assert len(TeachingTechnique) == 10  # Verify we now have 10 techniques

    print("✅ MISCONCEPTION_FIRST technique exists with 10 total techniques")


def test_enhanced_session_fields():
    """Test that TutoringSession has the new fields."""
    from agents.profiles.ultimate_tutor import TutoringSession

    session = TutoringSession(session_id="test", topic="python")
    assert hasattr(session, "tool_demos_used")
    assert hasattr(session, "truth_scores")
    assert hasattr(session, "misconceptions_addressed")
    assert hasattr(session, "progressive_stages")
    assert hasattr(session, "progressive_stage_idx")
    assert session.tool_demos_used == []
    assert session.truth_scores == []
    assert session.misconceptions_addressed == []

    print("✅ TutoringSession has all new enhanced fields")


def test_llm_retry_logic():
    """Test that LLM retry with backoff is properly configured."""
    from agents.profiles.ultimate_tutor import UltimateTutorEngine

    assert hasattr(UltimateTutorEngine, "_LLM_MAX_RETRIES")
    assert UltimateTutorEngine._LLM_MAX_RETRIES == 3
    assert hasattr(UltimateTutorEngine, "_LLM_BASE_DELAY")
    assert UltimateTutorEngine._LLM_BASE_DELAY == 0.5

    # Test that retry works (mock with a function that fails then succeeds)
    call_count = 0
    def flaky_generate(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Simulated LLM failure")
        class Result:
            answer = "Success after retry"
        return Result()

    engine = UltimateTutorEngine(generate_fn=flaky_generate)
    # Override delay for faster testing
    engine._LLM_BASE_DELAY = 0.01
    result = engine._call_llm("test prompt")
    assert result == "Success after retry"
    assert call_count == 3

    print("✅ LLM retry with exponential backoff works")

