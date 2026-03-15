"""Tests for ASI Core: Autonomous Loop, Multi-Agent, Memory, Reflection, Decision, TechScout."""
import asyncio, json, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

_TEST_DB = os.path.join(tempfile.gettempdir(), "astra_test_memory.db")

def _clean_db():
    if os.path.exists(_TEST_DB):
        try: os.unlink(_TEST_DB)
        except OSError: pass

def test_goal_creation():
    from brain.autonomous_loop import AutonomousLoop, Priority
    loop = AutonomousLoop()
    goal = loop.add_goal("Build a REST API", priority=Priority.HIGH)
    assert goal.id.startswith("goal_") and len(goal.sub_tasks) >= 4
    print(f"  OK Goal: {goal.id}, {len(goal.sub_tasks)} sub-tasks")

def test_goal_decomposition_build():
    from brain.autonomous_loop import AutonomousLoop
    goal = AutonomousLoop().add_goal("Build a new auth module")
    assert any("test" in t.description.lower() for t in goal.sub_tasks)
    print(f"  OK Build decomp: {len(goal.sub_tasks)} tasks")

def test_goal_decomposition_security():
    from brain.autonomous_loop import AutonomousLoop
    goal = AutonomousLoop().add_goal("Scan system for viruses")
    assert any("scan" in t.description.lower() for t in goal.sub_tasks)
    print(f"  OK Security decomp: {len(goal.sub_tasks)} tasks")

def test_autonomous_loop_run():
    from brain.autonomous_loop import AutonomousLoop
    loop = AutonomousLoop()
    loop.add_goal("Analyze codebase quality")
    report = asyncio.run(loop.run(max_cycles=10))
    assert report["cycles"] >= 1 and report["decisions_made"] >= 1
    print(f"  OK Loop: {report['cycles']} cycles, {report['decisions_made']} decisions")

def test_subtask_deps():
    from brain.autonomous_loop import AutonomousLoop
    goal = AutonomousLoop().add_goal("Deploy the app")
    for i in range(1, len(goal.sub_tasks)):
        assert len(goal.sub_tasks[i].depends_on) > 0
    print(f"  OK Deps: {len(goal.sub_tasks)} chained")

def test_spawn_team():
    from brain.agent_orchestrator import AgentOrchestrator, RoleType
    orch = AgentOrchestrator()
    team = orch.spawn_team()
    assert len(team) == 6
    roles = {a.role.role_type for a in team}
    assert RoleType.CODER in roles and RoleType.TESTER in roles
    print(f"  OK Team: {len(team)} agents")

def test_find_best_agent():
    from brain.agent_orchestrator import AgentOrchestrator
    orch = AgentOrchestrator(); orch.spawn_team()
    agent = orch.find_best_agent("testing and validation")
    assert agent and agent.role.name in ("Tester", "Reviewer")
    print(f"  OK Best agent for testing: {agent.role.name}")

def test_consensus():
    from brain.agent_orchestrator import AgentOrchestrator
    orch = AgentOrchestrator(); orch.spawn_team()
    r = asyncio.run(orch.request_consensus("Approach?", ["Fast", "Safe", "Balanced"]))
    assert r["winner"] in ("Fast", "Safe", "Balanced") and r["consensus_strength"] > 0
    print(f"  OK Consensus: '{r['winner']}' strength={r['consensus_strength']:.2f}")

def test_pipeline():
    from brain.agent_orchestrator import AgentOrchestrator
    r = asyncio.run(AgentOrchestrator().execute_pipeline("Build user API"))
    assert r["phases_completed"] >= 1 and r["team_size"] == 6
    print(f"  OK Pipeline: {r['phases_completed']}/{r['phases_total']} phases")

def test_broadcast():
    from brain.agent_orchestrator import AgentOrchestrator
    orch = AgentOrchestrator(); orch.spawn_team()
    orch.broadcast("Kickoff")
    for a in orch.agents.values(): assert len(a.inbox) >= 1
    print(f"  OK Broadcast to {len(orch.agents)} agents")

def test_memory_recall():
    _clean_db()
    from brain.memory_store import MemoryStore
    s = MemoryStore(_TEST_DB)
    s.remember("k", {"v": 42}, category="test", importance=0.9)
    assert s.recall("k") == {"v": 42}
    print(f"  OK Recall: {s.recall('k')}")

def test_memory_search():
    _clean_db()
    from brain.memory_store import MemoryStore
    s = MemoryStore(_TEST_DB)
    s.remember("py_style", "PEP8", category="pref")
    s.remember("py_ver", "3.13", category="pref")
    assert len(s.search("py", category="pref")) >= 2
    print(f"  OK Search: 2+ results")

def test_memory_decision_log():
    _clean_db()
    from brain.memory_store import MemoryStore
    s = MemoryStore(_TEST_DB)
    s.log_decision("React", ["Vue"], confidence=0.8)
    d = s.get_past_decisions()
    assert len(d) == 1 and d[0]["decision"] == "React"
    print(f"  OK Decision log: {d[0]['decision']}")

def test_memory_expiry():
    _clean_db()
    from brain.memory_store import MemoryStore
    s = MemoryStore(_TEST_DB)
    s.remember("tmp", "val", ttl_seconds=0.01)
    time.sleep(0.02)
    assert s.recall("tmp") is None
    print(f"  OK Expiry works")

def test_memory_stats():
    _clean_db()
    from brain.memory_store import MemoryStore
    s = MemoryStore(_TEST_DB)
    s.remember("a", 1); s.remember("b", 2)
    assert s.get_stats()["total_memories"] == 2
    print(f"  OK Stats: 2 memories")

def test_reflect_success():
    from brain.self_reflection import SelfReflectionEngine, TaskOutcome
    e = SelfReflectionEngine()
    e.reflect_on_task(TaskOutcome(tool_used="exec", success=True, duration=0.3, quality_score=0.9))
    print(f"  OK Reflect success")

def test_reflect_failure_pattern():
    from brain.self_reflection import SelfReflectionEngine, TaskOutcome
    e = SelfReflectionEngine()
    for i in range(3):
        e.reflect_on_task(TaskOutcome(tool_used="broken", success=False, error="Timeout"))
    ins = e.get_insights(category="failure_pattern")
    assert len(ins) >= 1 and "broken" in ins[-1]["insight"]
    print(f"  OK Failure pattern: {ins[-1]['insight'][:60]}")

def test_deep_reflection():
    from brain.self_reflection import SelfReflectionEngine, TaskOutcome
    e = SelfReflectionEngine()
    for i in range(10):
        e.reflect_on_task(TaskOutcome(tool_used="exec", success=i%3!=0, duration=0.5+i*0.1, quality_score=0.7))
    r = e.periodic_deep_reflection()
    assert "success_rate" in r and "meta_insights" in r
    print(f"  OK Deep reflection: rate={r['success_rate']:.0%}, {len(r['meta_insights'])} insights")

def test_decision_basic():
    from brain.decision_engine import DecisionEngine
    r = DecisionEngine().decide("Lang?", [
        {"name": "Python", "probability_success": 0.8, "risk_score": 0.2},
        {"name": "Rust", "probability_success": 0.6, "risk_score": 0.4},
    ])
    assert r["recommendation"] in ("Python", "Rust") and 0 < r["confidence"] <= 1
    print(f"  OK Decision: {r['recommendation']} conf={r['confidence']:.2f}")

def test_decision_bayesian():
    from brain.decision_engine import DecisionEngine
    r = DecisionEngine().decide("DB?", [
        {"name": "PG", "probability_success": 0.7},
        {"name": "MySQL", "probability_success": 0.6},
    ], evidence=[("benchmark", 0.9, 0.5), ("survey", 0.85, 0.6)])
    assert r["simulations_run"] >= 2000
    for s in r["scores"]: assert s["posterior"] != s["prior"]
    print(f"  OK Bayesian: {r['recommendation']}, {r['simulations_run']} sims")

def test_bias_detection():
    from brain.decision_engine import DecisionEngine
    r = DecisionEngine().decide("FW?", [
        {"name": "A", "probability_success": 0.95},
        {"name": "B", "probability_success": 0.92},
        {"name": "C", "probability_success": 0.93},
    ])
    assert "overconfidence" in [b["type"] for b in r["biases_detected"]]
    print(f"  OK Bias detected: {[b['type'] for b in r['biases_detected']]}")

def test_temporal():
    from brain.decision_engine import DecisionEngine
    r = DecisionEngine().decide("Approach?", [
        {"name": "Fast", "probability_success": 0.8, "time_cost": 0.2},
        {"name": "Thorough", "probability_success": 0.6, "time_cost": 0.8},
    ])
    for t in r["temporal_analysis"].values():
        assert "short_term" in t and "long_term" in t
    print(f"  OK Temporal analysis done")

def test_quick_decide():
    from brain.decision_engine import DecisionEngine
    r = DecisionEngine().quick_decide("Color?", ["Red", "Blue", "Green"])
    assert r["recommendation"] in ("Red", "Blue", "Green")
    print(f"  OK Quick: {r['recommendation']}")

def test_tech_evaluate():
    from brain.tech_scout import TechnologyScout
    r = TechnologyScout().evaluate("react")
    assert r and r["overall_score"] > 0.8 and r["recommendation"] == "adopt"
    print(f"  OK Evaluate React: {r['overall_score']:.3f} -> {r['recommendation']}")

def test_tech_compare():
    from brain.tech_scout import TechnologyScout
    r = TechnologyScout().compare(["react", "vue", "svelte"])
    assert r["success"] and len(r["comparison"]) == 3
    print(f"  OK Compare: winner={r['winner']}")

def test_tech_radar():
    from brain.tech_scout import TechnologyScout
    r = TechnologyScout().generate_tech_radar()
    assert r["success"] and r["total_technologies"] >= 8
    print(f"  OK Radar: {r['total_technologies']} techs, {r['adopt_count']} adopt")

def test_tech_suggest():
    from brain.tech_scout import TechnologyScout
    r = TechnologyScout().suggest_for_project("fullstack", ["performance"])
    assert r["success"] and "recommended" in r
    print(f"  OK Suggest: {r['recommended']}")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ASI Core Modules - Full Test Suite")
    print("=" * 60)
    tests = [
        ("Loop: Goal creation", test_goal_creation),
        ("Loop: Build decomp", test_goal_decomposition_build),
        ("Loop: Security decomp", test_goal_decomposition_security),
        ("Loop: Full run", test_autonomous_loop_run),
        ("Loop: Dependencies", test_subtask_deps),
        ("Orch: Spawn team", test_spawn_team),
        ("Orch: Best agent", test_find_best_agent),
        ("Orch: Consensus", test_consensus),
        ("Orch: Pipeline", test_pipeline),
        ("Orch: Broadcast", test_broadcast),
        ("Mem: Recall", test_memory_recall),
        ("Mem: Search", test_memory_search),
        ("Mem: Decision log", test_memory_decision_log),
        ("Mem: Expiry", test_memory_expiry),
        ("Mem: Stats", test_memory_stats),
        ("Reflect: Success", test_reflect_success),
        ("Reflect: Failure pattern", test_reflect_failure_pattern),
        ("Reflect: Deep", test_deep_reflection),
        ("Decide: Basic", test_decision_basic),
        ("Decide: Bayesian", test_decision_bayesian),
        ("Decide: Bias detect", test_bias_detection),
        ("Decide: Temporal", test_temporal),
        ("Decide: Quick", test_quick_decide),
        ("Scout: Evaluate", test_tech_evaluate),
        ("Scout: Compare", test_tech_compare),
        ("Scout: Radar", test_tech_radar),
        ("Scout: Suggest", test_tech_suggest),
    ]
    passed = 0
    for name, fn in tests:
        print(f"\n--- {name} ---")
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
    _clean_db()
    print(f"\n{'='*60}\n  {passed}/{len(tests)} TESTS PASSED!\n{'='*60}\n")
