"""Tests for ASI Integration: Cortex + Tool Factory."""
import asyncio, json, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

_TEST_DB = os.path.join(tempfile.gettempdir(), "astra_cortex_test.db")

def _clean_db():
    if os.path.exists(_TEST_DB):
        try: os.unlink(_TEST_DB)
        except OSError: pass

# ═══ Cortex Tests ═══

def test_cortex_boot():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    cortex = ASICortex(config=CortexConfig(db_path=_TEST_DB))
    result = cortex.boot()
    assert result["subsystems"]["memory"] == "active"
    assert result["subsystems"]["loop"] == "active"
    assert "agents" in result["subsystems"]["orchestrator"]
    cortex.shutdown()
    print(f"  OK Boot: all subsystems active")

def test_cortex_status():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    cortex = ASICortex(config=CortexConfig(db_path=_TEST_DB))
    cortex.boot()
    s = cortex.status()
    assert s["booted"] is True
    assert s["subsystems"]["loop"] is not None
    cortex.shutdown()
    print(f"  OK Status: uptime={s['uptime_seconds']}s")

def test_cortex_register_tool():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    cortex = ASICortex(config=CortexConfig(db_path=_TEST_DB))
    cortex.boot()
    cortex.register_tool("add", lambda a, b: {"result": a + b}, "Add two numbers")
    result = cortex._execute_tool("add", {"a": 3, "b": 5})
    assert result["result"] == 8
    cortex.shutdown()
    print(f"  OK Tool registered and executed: 3+5={result['result']}")

def test_cortex_think_simple():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    cortex = ASICortex(config=CortexConfig(db_path=_TEST_DB, max_cycles_per_goal=5))
    cortex.boot()
    result = asyncio.run(cortex.think("Analyze code quality", priority="low"))
    assert result["mode"] == "autonomous_loop"
    assert result["complexity"] == "simple"
    assert result["decisions_made"] >= 1
    cortex.shutdown()
    print(f"  OK Simple think: {result['decisions_made']} decisions")

def test_cortex_think_complex():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    cortex = ASICortex(config=CortexConfig(db_path=_TEST_DB, max_cycles_per_goal=5))
    cortex.boot()
    try:
        result = asyncio.run(cortex.think("Build a distributed full-stack microservice API"))
        assert result["mode"] in ("multi_agent_pipeline", "autonomous_loop")
        assert "goal_id" in result
        print(f"  OK Complex think: mode={result['mode']}, goal={result['goal_id']}")
    finally:
        cortex.shutdown()

def test_cortex_decide():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    cortex = ASICortex(config=CortexConfig(db_path=_TEST_DB))
    cortex.boot()
    result = asyncio.run(cortex.decide("Which DB?", [
        {"name": "PostgreSQL", "probability_success": 0.85},
        {"name": "MongoDB", "probability_success": 0.65},
    ]))
    assert result["recommendation"] in ("PostgreSQL", "MongoDB")
    assert result["confidence"] > 0
    cortex.shutdown()
    print(f"  OK Decide: {result['recommendation']} conf={result['confidence']:.2f}")

def test_cortex_discover():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    cortex = ASICortex(config=CortexConfig(db_path=_TEST_DB))
    cortex.boot()
    result = asyncio.run(cortex.discover("npm", "react"))
    assert "trending" in result and "radar" in result
    cortex.shutdown()
    print(f"  OK Discover: {len(result['trending'])} trending, radar generated")

def test_cortex_reflect():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    cortex = ASICortex(config=CortexConfig(db_path=_TEST_DB, max_cycles_per_goal=5))
    cortex.boot()
    asyncio.run(cortex.think("Test reflection"))
    report = cortex.reflect()
    assert isinstance(report, dict)
    cortex.shutdown()
    print(f"  OK Reflect: report generated")

def test_cortex_persistence():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    # Session 1: boot, work, shutdown
    cortex1 = ASICortex(config=CortexConfig(db_path=_TEST_DB))
    cortex1.boot()
    cortex1.memory.remember("test_persist", "session1_data", category="test")
    cortex1.shutdown()
    # Session 2: boot, check restored data
    cortex2 = ASICortex(config=CortexConfig(db_path=_TEST_DB))
    cortex2.boot()
    val = cortex2.memory.recall("test_persist")
    assert val == "session1_data"
    cortex2.shutdown()
    print(f"  OK Persistence: data survived restart")

def test_cortex_shutdown_report():
    from brain.asi_cortex import ASICortex, CortexConfig
    _clean_db()
    cortex = ASICortex(config=CortexConfig(db_path=_TEST_DB, max_cycles_per_goal=3))
    cortex.boot()
    asyncio.run(cortex.think("Quick task"))
    report = cortex.shutdown()
    assert "session_duration" in report
    assert "loop_report" in report
    assert "memory_stats" in report
    print(f"  OK Shutdown: duration={report['session_duration']}s, tasks={report['tasks_processed']}")

# ═══ Tool Factory Tests ═══

def test_factory_create_tool():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    tool = factory.create_tool(
        name="doubler",
        description="Double a number",
        code="def run(n: int) -> dict:\n    return {'result': n * 2}",
    )
    assert tool.enabled and tool.safety_checked
    result = factory._compiled_tools["doubler"](n=5)
    assert result["result"] == 10
    print(f"  OK Create tool: doubler(5) = {result['result']}")

def test_factory_safety_check():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    tool = factory.create_tool(
        name="unsafe",
        code="import subprocess\ndef run(): subprocess.call(['rm', '-rf', '/'])",
    )
    assert not tool.safety_checked and not tool.enabled
    print(f"  OK Safety: blocked unsafe tool (subprocess)")

def test_factory_template_tool():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    tool = factory.create_tool_from_template("text_processor")
    assert tool and tool.enabled
    result = factory._compiled_tools["text_processor"](text="hello world hello")
    assert result["count"] == 3
    print(f"  OK Template: text_processor wordcount={result['count']}")

def test_factory_math_template():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    factory.create_tool_from_template("math_solver")
    result = factory._compiled_tools["math_solver"](expression="sqrt(144) + 10")
    assert result["result"] == 22.0
    print(f"  OK Math: sqrt(144)+10 = {result['result']}")

def test_factory_create_agent():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    agent = factory.create_agent(
        name="MyBot", role="analyzer",
        expertise=["analysis", "reporting"],
        tools=["code_analyzer", "file_read"],
    )
    assert agent.name == "MyBot"
    assert len(agent.expertise) == 2
    print(f"  OK Agent: {agent.name} (role={agent.role})")

def test_factory_agent_template():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    agent = factory.create_agent_from_template("incident_responder")
    assert agent and agent.name == "IncidentResponder"
    assert "debugging" in agent.expertise
    print(f"  OK Template agent: {agent.name}")

def test_factory_pipeline():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    factory.create_tool_from_template("text_processor", "step1")
    pipe = factory.create_pipeline(
        name="text_analysis",
        steps=[{"tool": "step1", "args": {"text": "hello world", "operation": "wordcount"}}],
    )
    result = factory.execute_pipeline("text_analysis")
    assert result["success"] and result["steps_completed"] == 1
    print(f"  OK Pipeline: {result['steps_completed']}/{result['steps_total']} steps")

def test_factory_auto_solve():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    r1 = factory.auto_solve("Calculate a complex formula")
    assert r1["type"] == "tool" and r1["template"] == "math_solver"
    r2 = factory.auto_solve("Debug a server crash")
    assert r2["type"] == "agent" and r2["template"] == "incident_responder"
    print(f"  OK Auto-solve: math→{r1['type']}, crash→{r2['type']}")

def test_factory_list_templates():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    t = factory.list_templates()
    assert len(t["tools"]) >= 5
    assert len(t["agents"]) >= 4
    print(f"  OK Templates: {len(t['tools'])} tools, {len(t['agents'])} agents")

def test_factory_stats():
    from brain.tool_factory import ToolFactory
    factory = ToolFactory()
    factory.create_tool_from_template("text_processor")
    factory.create_agent_from_template("data_engineer")
    s = factory.get_stats()
    assert s["tools_created"] >= 1 and s["agents_created"] >= 1
    print(f"  OK Stats: {s['tools_created']} tools, {s['agents_created']} agents")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ASI Integration - Cortex + Factory Tests")
    print("=" * 60)
    tests = [
        ("Cortex: Boot", test_cortex_boot),
        ("Cortex: Status", test_cortex_status),
        ("Cortex: Register tool", test_cortex_register_tool),
        ("Cortex: Think simple", test_cortex_think_simple),
        ("Cortex: Think complex", test_cortex_think_complex),
        ("Cortex: Decide", test_cortex_decide),
        ("Cortex: Discover", test_cortex_discover),
        ("Cortex: Reflect", test_cortex_reflect),
        ("Cortex: Persistence", test_cortex_persistence),
        ("Cortex: Shutdown", test_cortex_shutdown_report),
        ("Factory: Create tool", test_factory_create_tool),
        ("Factory: Safety check", test_factory_safety_check),
        ("Factory: Template tool", test_factory_template_tool),
        ("Factory: Math template", test_factory_math_template),
        ("Factory: Create agent", test_factory_create_agent),
        ("Factory: Agent template", test_factory_agent_template),
        ("Factory: Pipeline", test_factory_pipeline),
        ("Factory: Auto-solve", test_factory_auto_solve),
        ("Factory: Templates list", test_factory_list_templates),
        ("Factory: Stats", test_factory_stats),
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
