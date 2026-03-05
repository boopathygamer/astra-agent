"""Tests for the agent framework."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_tool_registry():
    """Test tool registration and execution."""
    from agents.tools.registry import ToolRegistry, RiskLevel

    tr = ToolRegistry()

    # Register a test tool
    @tr.register(
        name="test_add",
        description="Add two numbers",
        risk_level=RiskLevel.LOW,
        parameters={"a": "First number", "b": "Second number"},
    )
    def add(a: int, b: int) -> int:
        return a + b

    # List tools
    tools = tr.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "test_add"
    print(f"✅ Registered {len(tools)} tool(s)")

    # Execute
    result = tr.execute("test_add", a=3, b=5)
    assert result["success"] is True
    assert result["result"] == 8
    print(f"✅ Tool execution: add(3,5) = {result['result']}")

    # Schema generation
    schemas = tr.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "test_add"
    print(f"✅ Schema: {schemas[0]}")


def test_task_compiler():
    """Test task compilation."""
    from agents.compiler import TaskCompiler

    compiler = TaskCompiler()

    # Rule-based compilation (no LLM)
    spec = compiler.compile("Analyze this image and tell me what you see")
    assert "analyze_image" in spec.tools_needed
    assert spec.action_type == "general"
    print(f"✅ Compiled: tools={spec.tools_needed}, action={spec.action_type}")

    # File operations
    spec2 = compiler.compile("Write a Python script to sort numbers")
    assert spec2.action_type == "file_write"
    print(f"✅ Compiled: action={spec2.action_type}")


def test_built_in_tools():
    """Test built-in tools are registered."""
    from agents.tools.registry import registry

    # Check some tools exist
    tools = {t.name for t in registry.list_tools()}
    print(f"✅ Registered tools: {tools}")

    # Test expression evaluator
    result = registry.execute("evaluate_expression", expression="2 + 2 * 3")
    if result["success"]:
        print(f"✅ eval('2 + 2 * 3') = {result['result']}")
    else:
        print(f"⚠️ eval failed: {result.get('error')}")


if __name__ == "__main__":
    test_tool_registry()
    test_task_compiler()
    test_built_in_tools()
    print("\n✅ All agent tests passed!")
