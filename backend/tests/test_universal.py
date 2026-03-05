"""
Tests for Universal Agent Subsystems.
─────────────────────────────────────
Isolated tests that don't trigger sentencepiece or heavy LLM dependencies.
"""

import sys, os, importlib, types

# Add project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# Pre-register 'agents' as a namespace package to prevent __init__.py loading
# which would trigger sentencepiece imports through controller -> tokenizer chain
if 'agents' not in sys.modules:
    agents_pkg = types.ModuleType('agents')
    agents_pkg.__path__ = [os.path.join(PROJECT_ROOT, 'agents')]
    agents_pkg.__package__ = 'agents'
    sys.modules['agents'] = agents_pkg

# Same for 'agents.experts', 'agents.tools', 'agents.prompts'
for subpkg in ['agents.experts', 'agents.tools', 'agents.prompts']:
    if subpkg not in sys.modules:
        mod = types.ModuleType(subpkg)
        mod.__path__ = [os.path.join(PROJECT_ROOT, subpkg.replace('.', os.sep))]
        mod.__package__ = subpkg
        sys.modules[subpkg] = mod

# Same for 'brain'
if 'brain' not in sys.modules:
    brain_pkg = types.ModuleType('brain')
    brain_pkg.__path__ = [os.path.join(PROJECT_ROOT, 'brain')]
    brain_pkg.__package__ = 'brain'
    sys.modules['brain'] = brain_pkg


# ─────────────────────────────────────────────────
# 1. Domain Router
# ─────────────────────────────────────────────────

def test_domain_router():
    router_mod = importlib.import_module('agents.experts.router')
    DomainRouter = router_mod.DomainRouter

    router = DomainRouter()

    result = router.classify("Write a Python function to sort a list")
    assert result.primary_domain == "code", f"Expected 'code', got '{result.primary_domain}'"
    assert result.confidence > 0.0

    result = router.classify("Calculate the integral of x^2 dx")
    assert result.primary_domain == "math", f"Expected 'math', got '{result.primary_domain}'"

    result = router.classify("Analyze the ROI of our marketing campaign")
    assert result.primary_domain == "business", f"Expected 'business', got '{result.primary_domain}'"

    result = router.classify("Create a beautiful illustration with vibrant color palette and typography")
    assert result.primary_domain == "creative", f"Expected 'creative', got '{result.primary_domain}'"

    result = router.classify("What exercises help with lower back pain?")
    assert result.primary_domain == "health", f"Expected 'health', got '{result.primary_domain}'"

    print("✅ test_domain_router PASSED — all 5 domains classified correctly")


# ─────────────────────────────────────────────────
# 2. Domain Experts
# ─────────────────────────────────────────────────

def test_domain_experts():
    domains_mod = importlib.import_module('agents.experts.domains')
    EXPERTS = domains_mod.DOMAIN_EXPERTS
    get_expert = domains_mod.get_expert

    assert len(EXPERTS) >= 10, f"Expected >= 10 experts, got {len(EXPERTS)}"

    for name, expert in EXPERTS.items():
        injection = expert.get_prompt_injection()
        assert injection, f"Expert '{name}' has empty injection"
        assert expert.reasoning_hints, f"Expert '{name}' has no reasoning hints"

    general = get_expert("nonexistent_domain")
    assert general.name == "Universal Assistant"

    print(f"✅ test_domain_experts PASSED — {len(EXPERTS)} experts validated")


# ─────────────────────────────────────────────────
# 3. Persona Engine
# ─────────────────────────────────────────────────

def test_persona_engine():
    persona_mod = importlib.import_module('agents.persona')
    PersonaEngine = persona_mod.PersonaEngine
    PERSONAS = persona_mod.PERSONAS

    engine = PersonaEngine()
    assert len(PERSONAS) >= 5

    engine.detect("I'm new to programming. What is a variable?")
    assert engine.current_name == "beginner", f"Expected beginner, got {engine.current_name}"

    engine.reset()
    engine.detect("Help me study for my calculus exam next semester")
    assert engine.current_name == "student", f"Expected student, got {engine.current_name}"

    engine.reset()
    engine.detect("Give me the ROI and quarterly strategic brief")
    assert engine.current_name == "executive", f"Expected executive, got {engine.current_name}"

    engine.set_persona("creative")
    assert engine.current_name == "creative"
    engine.detect("help me with math")
    assert engine.current_name == "creative"

    prompt = engine.current.get_style_prompt()
    assert "Creative Collaborator" in prompt

    engine.reset()
    assert engine.current_name == "default"

    print("✅ test_persona_engine PASSED — all personas and detection work")


# ─────────────────────────────────────────────────
# 4. Advanced Reasoning
# ─────────────────────────────────────────────────

def test_advanced_reasoning():
    reasoning_mod = importlib.import_module('brain.advanced_reasoning')
    AdvancedReasoner = reasoning_mod.AdvancedReasoner
    ReasoningStrategy = reasoning_mod.ReasoningStrategy

    reasoner = AdvancedReasoner()

    strategy = reasoner.select_strategy("Hello!")
    assert strategy == ReasoningStrategy.DIRECT

    strategy = reasoner.select_strategy("Walk me through how to debug this code")
    assert strategy == ReasoningStrategy.CHAIN_OF_THOUGHT, f"Got {strategy}"

    strategy = reasoner.select_strategy("Compare React vs Vue pros and cons")
    assert strategy == ReasoningStrategy.TREE_OF_THOUGHT, f"Got {strategy}"

    strategy = reasoner.select_strategy("What is recursion?", persona="beginner")
    assert strategy == ReasoningStrategy.ANALOGY, f"Got {strategy}"

    strategy = reasoner.select_strategy("Help me with this math problem", persona="student")
    assert strategy == ReasoningStrategy.SOCRATIC, f"Got {strategy}"

    result = reasoner.reason("How to sort a list step by step?", domain="code")
    assert result.strategy_used == ReasoningStrategy.CHAIN_OF_THOUGHT
    assert result.reasoning_prompt
    assert len(result.steps) > 0

    stats = reasoner.get_stats()
    assert stats["chain_of_thought"] > 0

    print("✅ test_advanced_reasoning PASSED — all 4 strategies work")


# ─────────────────────────────────────────────────
# 5. Calculator
# ─────────────────────────────────────────────────

def test_calculator():
    calc_mod = importlib.import_module('agents.tools.calculator')
    AdvancedCalculator = calc_mod.AdvancedCalculator

    calc = AdvancedCalculator()

    r = calc.evaluate("2 * (3 + 4)")
    assert r["result"] == 14

    r = calc.evaluate("sqrt(144)")
    assert r["result"] == 12.0

    r = calc.convert_units(1, "mile", "km")
    assert abs(r["result"] - 1.609344) < 0.01

    r = calc.convert_units(100, "celsius", "fahrenheit")
    assert r["result"] == 212.0

    r = calc.compound_interest(1000, 5, 10)
    assert r["final_amount"] > 1600

    r = calc.loan_payment(200000, 6, 30)
    assert r["monthly_payment"] > 1000

    r = calc.roi(1000, 1500)
    assert r["roi_percent"] == 50.0

    r = calc.stats([10, 20, 30, 40, 50])
    assert r["mean"] == 30.0
    assert r["median"] == 30.0

    r = calc.days_between("2024-01-01", "2024-12-31")
    assert r["days"] == 365

    r = calc.add_days("2024-01-01", 10)
    assert r["result"] == "2024-01-11"

    r = calc.percentage("of", 200, 15)
    assert r["result"] == 30.0

    print("✅ test_calculator PASSED — math, units, finance, stats, dates, percentages all work")


# ─────────────────────────────────────────────────
# 6. Writing Assistant
# ─────────────────────────────────────────────────

def test_writing_assistant():
    writer_mod = importlib.import_module('agents.tools.writer')
    WritingAssistant = writer_mod.WritingAssistant

    writer = WritingAssistant()

    text = (
        "The quick brown fox jumped over the lazy dog. "
        "This is a test paragraph that has multiple sentences. "
        "Some of them are really long and others are short. "
        "The purpose is to test the writing analysis feature."
    )

    analysis = writer.analyze(text)
    assert analysis.word_count > 30
    assert analysis.sentence_count >= 4
    assert analysis.readability_score in ("easy", "moderate", "difficult")
    assert analysis.tone

    formal_text = "Pursuant to our agreement, we hereby acknowledge and consequently proceed."
    analysis2 = writer.analyze(formal_text)
    assert analysis2.tone == "formal"

    summary_prompt = writer.summarize(text, style="bullet_points")
    assert "Summarize" in summary_prompt

    print("✅ test_writing_assistant PASSED — analysis, tone detection, and templates work")


# ─────────────────────────────────────────────────
# 7. Data Analyzer
# ─────────────────────────────────────────────────

def test_data_analyzer():
    da_mod = importlib.import_module('agents.tools.data_analyzer')
    DataAnalyzer = da_mod.DataAnalyzer

    analyzer = DataAnalyzer()

    csv_data = "Name,Age,Score\nAlice,25,95\nBob,30,87\nCharlie,22,91\nDiana,28,76"
    parsed = analyzer.parse_csv(csv_data)
    assert len(parsed) == 4
    assert parsed[0]["Name"] == "Alice"

    summary = analyzer.analyze(parsed)
    assert summary.row_count == 4
    assert summary.column_count == 3
    assert len(summary.insights) > 0

    age_col = [c for c in summary.columns if c["name"] == "Age"][0]
    assert age_col["type"] == "numeric"
    assert age_col["min"] == 22.0
    assert age_col["max"] == 30.0

    charts = analyzer.suggest_charts(summary)
    assert len(charts) > 0

    data = [
        {"team": "A", "score": "10"}, {"team": "A", "score": "15"},
        {"team": "B", "score": "20"}, {"team": "B", "score": "25"},
    ]
    groups = analyzer.compare_groups(data, "team", "score")
    assert groups["group_count"] == 2
    assert groups["groups"]["A"]["mean"] == 12.5
    assert groups["groups"]["B"]["mean"] == 22.5

    print("✅ test_data_analyzer PASSED — CSV parsing, analysis, charts, groups all work")


# ─────────────────────────────────────────────────
# 8. Task Planner
# ─────────────────────────────────────────────────

def test_task_planner():
    tp_mod = importlib.import_module('agents.tools.task_planner')
    TaskPlanner = tp_mod.TaskPlanner

    planner = TaskPlanner()

    tasks = [
        {"title": "Research competitors", "priority": "high", "hours": 3, "category": "Research"},
        {"title": "Write business plan", "priority": "critical", "hours": 6, "category": "Planning"},
        {"title": "Design logo", "priority": "medium", "hours": 2, "category": "Design"},
        {"title": "Register domain", "priority": "low", "hours": 0.5, "category": "Setup"},
    ]
    plan = planner.create_plan("Launch Startup", tasks)

    assert len(plan.tasks) == 4
    assert plan.total_hours == 11.5
    assert plan.estimated_days >= 1
    assert plan.progress_percent == 0.0

    planner.mark_complete(plan, plan.tasks[0].id)
    assert plan.completed_count == 1
    assert plan.progress_percent == 25.0

    progress = planner.get_progress(plan)
    assert progress["completed"] == 1
    assert progress["remaining"] == 3

    schedule = planner.generate_schedule(plan, hours_per_day=6, start_date="2024-01-08")
    assert len(schedule) > 0
    assert schedule[0]["date"] == "2024-01-08"

    formatted = planner.format_plan(plan)
    assert "Launch Startup" in formatted
    assert "✅" in formatted

    print("✅ test_task_planner PASSED — plans, scheduling, progress, formatting all work")


# ─────────────────────────────────────────────────
# 9. Response Formatter
# ─────────────────────────────────────────────────

def test_response_formatter():
    rf_mod = importlib.import_module('agents.response_formatter')
    ResponseFormatter = rf_mod.ResponseFormatter
    DOMAIN_FORMATS = rf_mod.DOMAIN_FORMATS

    formatter = ResponseFormatter()

    assert "health" in DOMAIN_FORMATS
    assert "legal" in DOMAIN_FORMATS
    assert DOMAIN_FORMATS["health"].add_disclaimer != ""

    response = formatter.format("Drink water daily for better health.", domain="health")
    assert "medical advice" in response.lower()

    response = formatter.format("This contract clause is standard.", domain="legal")
    assert "legal advice" in response.lower()

    sections = {
        "Summary": "This is the summary.",
        "Steps": "1. Do this\n2. Do that",
        "Tips": "Be careful!",
    }
    structured = formatter.build_structured_response(sections, domain="education", title="Learning Guide")
    assert "Learning Guide" in structured
    assert "Summary" in structured

    table = formatter.format_comparison(
        "Python", "JavaScript",
        {"Speed": ("Fast", "Very Fast"), "Ease": ("Easy", "Easy")},
    )
    assert "Python" in table
    assert "JavaScript" in table

    actions = formatter.format_action_items([
        {"title": "Deploy to staging", "priority": "High", "owner": "Dev Team"},
    ])
    assert "Deploy" in actions

    long_text = "This is a comprehensive analysis of market trends showing growth. " + "Here is more detail about the analysis. " * 25
    result = formatter.format(long_text, domain="business")
    assert "TL;DR" in result

    print("✅ test_response_formatter PASSED — formatting, disclaimers, tables all work")


# ─────────────────────────────────────────────────
# 10. Knowledge Engine
# ─────────────────────────────────────────────────

def test_knowledge_engine():
    ke_mod = importlib.import_module('agents.tools.knowledge')
    KnowledgeEngine = ke_mod.KnowledgeEngine

    engine = KnowledgeEngine()

    assert engine._detect_type("What is machine learning?") == "definition"
    assert engine._detect_type("Compare React vs Vue") == "comparison"
    assert engine._detect_type("Pros and cons of remote work") == "pros_cons"
    assert engine._detect_type("Tell me about quantum computing") == "summary"

    result = engine.query("What is machine learning?")
    assert result.query_type == "definition"
    assert "definition" in result.content.lower() or "explain" in result.content.lower()

    print("✅ test_knowledge_engine PASSED — query type detection and templates work")


# ─────────────────────────────────────────────────
# Run All Tests
# ─────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_domain_router,
        test_domain_experts,
        test_persona_engine,
        test_advanced_reasoning,
        test_calculator,
        test_writing_assistant,
        test_data_analyzer,
        test_task_planner,
        test_response_formatter,
        test_knowledge_engine,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
    print(f"{'='*50}")
