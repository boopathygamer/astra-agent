"""
Tests for the MCP Server Integration — Expert Level.
─────────────────────────────────────────────────────
Validates all 24 tools, 9 resources, and 8 prompts.

Run with: pytest tests/test_mcp_server.py -v --tb=short
"""

import json
import pytest
from mcp.server.fastmcp import FastMCP

from mcp_server.server import (
    create_mcp_server,
    CircuitBreaker,
    MetricsCollector,
    MCPError,
    ErrorCode,
    _validate_string,
    _validate_range,
    _sanitize_path,
    _make_response,
    _new_trace,
)


# ─────────────────────────────────────
# Fixtures
# ─────────────────────────────────────

@pytest.fixture
def mcp_server() -> FastMCP:
    """Fixture providing a fresh MCP server instance."""
    return create_mcp_server()


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """Fixture providing a fresh circuit breaker."""
    return CircuitBreaker(threshold=3, cooldown_sec=1.0)


@pytest.fixture
def metrics() -> MetricsCollector:
    """Fixture providing a fresh metrics collector."""
    return MetricsCollector()


# ─────────────────────────────────────
# Server Initialization
# ─────────────────────────────────────

@pytest.mark.mcp
def test_mcp_server_initialization(mcp_server: FastMCP):
    """Test that the server initializes correctly with the right name."""
    assert mcp_server.name == "SuperChain AI Agent"


# ─────────────────────────────────────
# Tool Registration (24 tools)
# ─────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_tools_registration(mcp_server: FastMCP):
    """Test that all 24 required tools are registered."""
    expected_tools = {
        # Original 18
        "chat", "agent_task", "think", "quick_think",
        "analyze_code", "execute_code", "search_web",
        "scan_threats", "analyze_file", "memory_recall",
        "memory_store", "tutor_start", "tutor_respond",
        "swarm_execute", "forge_tool", "transpile_code",
        "evolve_code", "calculate",
        # New 6
        "project_scaffold", "deep_research", "refactor_code",
        "generate_tests", "workspace_summary", "git_operations",
    }

    tools = await mcp_server.list_tools()
    registered_tools = {t.name for t in tools}

    missing = expected_tools - registered_tools
    assert not missing, f"Missing MCP tools: {missing}"
    assert len(registered_tools) >= 24, f"Expected >= 24 tools, got {len(registered_tools)}"


# ─────────────────────────────────────
# Resource Registration (9 resources)
# ─────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_resources_registration(mcp_server: FastMCP):
    """Test that all 9 required resources are registered."""
    expected_resources = {
        # Original 6
        "system://health", "system://config",
        "memory://stats", "memory://failures",
        "agents://profiles", "agents://tools",
        # New 3
        "system://capabilities", "system://metrics",
        "workspace://structure",
    }

    resources = await mcp_server.list_resources()
    registered_resources = {str(r.uri) for r in resources}

    missing = expected_resources - registered_resources
    assert not missing, f"Missing MCP resources: {missing}"
    assert len(registered_resources) >= 9, f"Expected >= 9 resources, got {len(registered_resources)}"


# ─────────────────────────────────────
# Prompt Registration (8 prompts)
# ─────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_prompts_registration(mcp_server: FastMCP):
    """Test that all 8 required prompts are registered."""
    expected_prompts = {
        # Original 5
        "code_review", "debug_error", "research_topic",
        "explain_concept", "system_audit",
        # New 3
        "architect_system", "optimize_performance", "write_documentation",
    }

    prompts = await mcp_server.list_prompts()
    registered_prompts = {p.name for p in prompts}

    missing = expected_prompts - registered_prompts
    assert not missing, f"Missing MCP prompts: {missing}"
    assert len(registered_prompts) >= 8, f"Expected >= 8 prompts, got {len(registered_prompts)}"


# ─────────────────────────────────────
# System Health Resource
# ─────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_system_health_resource(mcp_server: FastMCP):
    """Test reading the system health resource to ensure callback is registered."""
    resources = await mcp_server.list_resources()
    health_res = next((r for r in resources if str(r.uri) == "system://health"), None)
    assert health_res is not None, "system://health resource not found"


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_capabilities_resource(mcp_server: FastMCP):
    """Test that system://capabilities resource exists."""
    resources = await mcp_server.list_resources()
    cap_res = next((r for r in resources if str(r.uri) == "system://capabilities"), None)
    assert cap_res is not None, "system://capabilities resource not found"


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_metrics_resource(mcp_server: FastMCP):
    """Test that system://metrics resource exists."""
    resources = await mcp_server.list_resources()
    met_res = next((r for r in resources if str(r.uri) == "system://metrics"), None)
    assert met_res is not None, "system://metrics resource not found"


# ─────────────────────────────────────
# Expert Infrastructure Unit Tests
# ─────────────────────────────────────

class TestMCPError:
    """Tests for the structured error system."""

    def test_error_to_dict_basic(self):
        err = MCPError(code="E001", message="Not initialized")
        d = err.to_dict()
        assert d["code"] == "E001"
        assert d["message"] == "Not initialized"
        assert "details" not in d
        assert "retry_hint" not in d

    def test_error_to_dict_full(self):
        err = MCPError(code="E002", message="Validation failed", details="Too long", retry_hint="Shorten input")
        d = err.to_dict()
        assert d["details"] == "Too long"
        assert d["retry_hint"] == "Shorten input"


class TestInputValidation:
    """Tests for input validation helpers."""

    def test_validate_string_valid(self):
        assert _validate_string("hello", "test") is None

    def test_validate_string_too_long(self):
        err = _validate_string("x" * 200, "test", max_len=100)
        assert err is not None
        assert "exceeds maximum" in err.message

    def test_validate_range_valid(self):
        assert _validate_range(5, "test", 1, 10) is None

    def test_validate_range_invalid(self):
        err = _validate_range(50, "test", 1, 10)
        assert err is not None
        assert "must be between" in err.message

    def test_sanitize_path_valid(self):
        result = _sanitize_path(".")
        assert result is not None

    def test_sanitize_path_traversal(self):
        result = _sanitize_path("../../etc/passwd")
        assert result is None


class TestCircuitBreaker:
    """Tests for the circuit breaker pattern."""

    def test_initially_closed(self, circuit_breaker):
        assert not circuit_breaker.is_open("llm")

    def test_opens_after_threshold(self, circuit_breaker):
        for _ in range(3):
            circuit_breaker.record_failure("llm")
        assert circuit_breaker.is_open("llm")

    def test_success_resets(self, circuit_breaker):
        circuit_breaker.record_failure("llm")
        circuit_breaker.record_failure("llm")
        circuit_breaker.record_success("llm")
        assert not circuit_breaker.is_open("llm")

    def test_stays_closed_below_threshold(self, circuit_breaker):
        circuit_breaker.record_failure("llm")
        circuit_breaker.record_failure("llm")
        assert not circuit_breaker.is_open("llm")


class TestMetricsCollector:
    """Tests for the performance metrics system."""

    def test_record_and_snapshot(self, metrics):
        metrics.record("chat", 150.0)
        metrics.record("chat", 200.0)
        metrics.record("chat", 100.0, is_error=True)

        snap = metrics.snapshot()
        assert "chat" in snap
        assert snap["chat"]["calls"] == 3
        assert snap["chat"]["errors"] == 1
        assert snap["chat"]["avg_latency_ms"] == 150.0
        assert snap["chat"]["error_rate"] == pytest.approx(0.3333, abs=0.01)

    def test_empty_snapshot(self, metrics):
        snap = metrics.snapshot()
        assert snap == {}


class TestResponseEnvelope:
    """Tests for standardised response format."""

    def test_success_response(self):
        tid, t0 = _new_trace()
        resp = _make_response({"answer": "hello"}, tid, t0)
        assert resp["success"] is True
        assert "trace_id" in resp
        assert "timestamp" in resp
        assert "duration_ms" in resp
        assert resp["data"]["answer"] == "hello"

    def test_error_response(self):
        tid, t0 = _new_trace()
        err = MCPError(code="E001", message="fail")
        resp = _make_response({}, tid, t0, error=err)
        assert resp["success"] is False
        assert resp["error"]["code"] == "E001"
        assert "data" not in resp

    def test_trace_id_is_unique(self):
        tid1, _ = _new_trace()
        tid2, _ = _new_trace()
        assert tid1 != tid2
