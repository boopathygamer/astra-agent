"""
Tests for the MCP Server Integration.
─────────────────────────────────────
Run with: pytest -m mcp tests/test_mcp_server.py
"""

import json
import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server.server import create_mcp_server


@pytest.fixture
def mcp_server() -> FastMCP:
    """Fixture providing a fresh MCP server instance."""
    return create_mcp_server()


@pytest.mark.mcp
def test_mcp_server_initialization(mcp_server: FastMCP):
    """Test that the server initializes correctly with the right name."""
    assert mcp_server.name == "SuperChain AI Agent"


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_tools_registration(mcp_server: FastMCP):
    """Test that all required tools are registered."""
    expected_tools = {
        "chat", "agent_task", "think", "quick_think", 
        "analyze_code", "execute_code", "search_web", 
        "scan_threats", "analyze_file", "memory_recall", 
        "memory_store", "tutor_start", "tutor_respond", 
        "swarm_execute", "forge_tool", "transpile_code", 
        "evolve_code", "calculate"
    }

    tools = await mcp_server.list_tools()
    registered_tools = {t.name for t in tools}
    
    missing = expected_tools - registered_tools
    assert not missing, f"Missing MCP tools: {missing}"


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_resources_registration(mcp_server: FastMCP):
    """Test that all required resources are registered."""
    expected_resources = {
        "system://health", "system://config",
        "memory://stats", "memory://failures",
        "agents://profiles", "agents://tools"
    }

    resources = await mcp_server.list_resources()
    registered_resources = {str(r.uri) for r in resources}
    
    missing = expected_resources - registered_resources
    assert not missing, f"Missing MCP resources: {missing}"


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_prompts_registration(mcp_server: FastMCP):
    """Test that all required prompts are registered."""
    expected_prompts = {
        "code_review", "debug_error", "research_topic",
        "explain_concept", "system_audit"
    }

    prompts = await mcp_server.list_prompts()
    registered_prompts = {p.name for p in prompts}
    
    missing = expected_prompts - registered_prompts
    assert not missing, f"Missing MCP prompts: {missing}"


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_system_health_resource(mcp_server: FastMCP):
    """Test reading the system health resource to ensure callback is registered."""
    resources = await mcp_server.list_resources()
    health_res = next((r for r in resources if str(r.uri) == "system://health"), None)
    assert health_res is not None, "system://health resource not found"
