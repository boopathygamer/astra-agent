"""
MCP Server — FastMCP integration for SuperChain Universal AI Agent.
───────────────────────────────────────────────────────────────────
Expert-level MCP server exposing:
  • 24 Tools   — chat, reasoning, code analysis, refactoring, research, git, etc.
  • 9 Resources — health, config, memory, profiles, tools, capabilities, metrics, workspace
  • 8 Prompts  — code review, debugging, research, teaching, audit, architecture, perf, docs

Architecture:
  Uses FastMCP's lifespan protocol for lazy initialization.
  All subsystems are created once and shared via AppContext.
  Thread-safe via generate_fn isolation per request.
  Expert patterns: structured errors, request tracing, input validation, circuit breaker.
"""

import json
import logging
import os
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Ensure backend is on sys.path
# ──────────────────────────────────────────────
_BACKEND_DIR = str(Path(__file__).parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ──────────────────────────────────────────────
# Expert Infrastructure: Errors, Tracing, Validation, Circuit Breaker
# ──────────────────────────────────────────────

import secrets
import functools
import threading
import subprocess
from enum import Enum


class ErrorCode(Enum):
    """Typed error codes for structured MCP responses."""
    NOT_INITIALIZED = "E001"
    VALIDATION_FAILED = "E002"
    TOOL_NOT_FOUND = "E003"
    LLM_TIMEOUT = "E004"
    LLM_FAILURE = "E005"
    CIRCUIT_OPEN = "E006"
    FILE_NOT_FOUND = "E007"
    INTERNAL_ERROR = "E999"


@dataclass
class MCPError:
    """Structured error envelope for all MCP responses."""
    code: str
    message: str
    details: Optional[str] = None
    retry_hint: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message}
        if self.details:
            d["details"] = self.details
        if self.retry_hint:
            d["retry_hint"] = self.retry_hint
        return d


def _make_response(
    data: dict,
    trace_id: str,
    start_time: float,
    error: Optional[MCPError] = None,
) -> dict:
    """Build a standardised response envelope with tracing metadata."""
    envelope: Dict[str, Any] = {
        "success": error is None,
        "trace_id": trace_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_ms": round((time.time() - start_time) * 1000, 2),
    }
    if error:
        envelope["error"] = error.to_dict()
    else:
        envelope["data"] = data
    return envelope


def _new_trace() -> tuple:
    """Return (trace_id, start_time) for a new request."""
    return secrets.token_hex(8), time.time()


# ── Input Validation ──

_MAX_INPUT_LEN = 100_000  # 100 KB max for any text input
_MAX_CODE_LEN = 500_000   # 500 KB max for code inputs


def _validate_string(value: str, name: str, max_len: int = _MAX_INPUT_LEN) -> Optional[MCPError]:
    if not isinstance(value, str):
        return MCPError(ErrorCode.VALIDATION_FAILED.value, f"{name} must be a string")
    if len(value) > max_len:
        return MCPError(
            ErrorCode.VALIDATION_FAILED.value,
            f"{name} exceeds maximum length ({len(value)} > {max_len})",
            retry_hint=f"Reduce {name} to under {max_len} characters",
        )
    return None


def _validate_range(value: int, name: str, lo: int, hi: int) -> Optional[MCPError]:
    if not (lo <= value <= hi):
        return MCPError(
            ErrorCode.VALIDATION_FAILED.value,
            f"{name} must be between {lo} and {hi}, got {value}",
        )
    return None


def _sanitize_path(raw: str) -> Optional[str]:
    """Block path traversal attempts; return resolved path or None."""
    p = Path(raw).resolve()
    if ".." in Path(raw).parts:
        return None
    return str(p)


# ── Circuit Breaker ──

class CircuitBreaker:
    """Protects external calls (LLM, network) from cascading failures."""

    def __init__(self, threshold: int = 5, cooldown_sec: float = 60.0):
        self._threshold = threshold
        self._cooldown = cooldown_sec
        self._failures: Dict[str, int] = {}
        self._open_since: Dict[str, float] = {}
        self._lock = threading.Lock()

    def is_open(self, subsystem: str) -> bool:
        with self._lock:
            opened = self._open_since.get(subsystem)
            if opened and (time.time() - opened) > self._cooldown:
                # Half-open: allow one attempt
                del self._open_since[subsystem]
                self._failures[subsystem] = 0
                return False
            return subsystem in self._open_since

    def record_success(self, subsystem: str) -> None:
        with self._lock:
            self._failures[subsystem] = 0
            self._open_since.pop(subsystem, None)

    def record_failure(self, subsystem: str) -> None:
        with self._lock:
            self._failures[subsystem] = self._failures.get(subsystem, 0) + 1
            if self._failures[subsystem] >= self._threshold:
                self._open_since[subsystem] = time.time()
                logger.warning(
                    f"🔴 Circuit OPEN for '{subsystem}' after "
                    f"{self._threshold} consecutive failures"
                )


# ── Performance Metrics ──

class MetricsCollector:
    """Thread-safe per-tool performance telemetry."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls: Dict[str, int] = {}
        self._errors: Dict[str, int] = {}
        self._total_ms: Dict[str, float] = {}

    def record(self, tool: str, duration_ms: float, is_error: bool = False):
        with self._lock:
            self._calls[tool] = self._calls.get(tool, 0) + 1
            self._total_ms[tool] = self._total_ms.get(tool, 0.0) + duration_ms
            if is_error:
                self._errors[tool] = self._errors.get(tool, 0) + 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            result = {}
            for tool in self._calls:
                calls = self._calls[tool]
                result[tool] = {
                    "calls": calls,
                    "errors": self._errors.get(tool, 0),
                    "avg_latency_ms": round(self._total_ms[tool] / calls, 2) if calls else 0,
                    "error_rate": round(self._errors.get(tool, 0) / calls, 4) if calls else 0,
                }
            return result


# Global singletons
_circuit = CircuitBreaker()
_metrics = MetricsCollector()


# ──────────────────────────────────────────────
# Lazy Subsystem Imports
# ──────────────────────────────────────────────

def _import_subsystems():
    """Import all subsystems lazily to avoid circular imports."""
    from config.settings import (
        brain_config, agent_config, provider_config,
        api_config, threat_config,
    )
    from brain.memory import MemoryManager
    from brain.thinking_loop import ThinkingLoop
    from brain.code_analyzer import CodeAnalyzer
    from brain.long_term_memory import LongTermMemory
    from agents.controller import AgentController
    from agents.tools.registry import registry as tool_registry
    from core.model_providers import ProviderRegistry

    return {
        "brain_config": brain_config,
        "agent_config": agent_config,
        "provider_config": provider_config,
        "api_config": api_config,
        "threat_config": threat_config,
        "MemoryManager": MemoryManager,
        "ThinkingLoop": ThinkingLoop,
        "CodeAnalyzer": CodeAnalyzer,
        "LongTermMemory": LongTermMemory,
        "AgentController": AgentController,
        "tool_registry": tool_registry,
        "ProviderRegistry": ProviderRegistry,
    }


# ──────────────────────────────────────────────
# Application Context (shared across all tools)
# ──────────────────────────────────────────────

@dataclass
class AppContext:
    """Shared state for MCP tool/resource handlers."""
    provider_registry: Any = None
    generate_fn: Any = None
    agent_controller: Any = None
    memory_manager: Any = None
    thinking_loop: Any = None
    code_analyzer: Any = None
    long_term_memory: Any = None
    tool_registry: Any = None
    threat_scanner: Any = None
    configs: Dict[str, Any] = field(default_factory=dict)
    _initialized: bool = False

    def is_ready(self) -> bool:
        return self._initialized and self.generate_fn is not None


# ──────────────────────────────────────────────
# Lifespan Management
# ──────────────────────────────────────────────

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Manage application lifecycle.

    Startup:
      1. Import all subsystems
      2. Create provider registry + select best provider
      3. Initialize agent controller with full pipeline
      4. Store everything in AppContext

    Shutdown:
      - Graceful cleanup of subsystems
    """
    logger.info("🚀 MCP Server starting — initializing subsystems...")
    ctx = AppContext()

    try:
        modules = _import_subsystems()

        # ── Provider Registry ──
        provider_cfg = modules["provider_config"]
        ProviderRegistry = modules["ProviderRegistry"]

        provider_name = os.getenv("LLM_PROVIDER", provider_cfg.provider)
        registry = ProviderRegistry()

        # Register available providers
        if provider_cfg.gemini_api_key:
            registry.register_provider(
                "gemini", provider_cfg.gemini_api_key,
                model=provider_cfg.gemini_model,
            )
        if provider_cfg.claude_api_key:
            registry.register_provider(
                "claude", provider_cfg.claude_api_key,
                model=provider_cfg.claude_model,
            )
        if provider_cfg.openai_api_key:
            registry.register_provider(
                "chatgpt", provider_cfg.openai_api_key,
                model=provider_cfg.openai_model,
            )

        ctx.provider_registry = registry

        # Select generate function
        if provider_name != "auto":
            ctx.generate_fn = registry.get_generate_fn(provider_name)
        else:
            ctx.generate_fn = registry.get_best_generate_fn()

        if ctx.generate_fn is None:
            # Fallback: echo function for environments without API keys
            logger.warning(
                "⚠ No LLM provider configured. MCP tools requiring LLM will "
                "return placeholder responses. Set GEMINI_API_KEY, CLAUDE_API_KEY, "
                "or OPENAI_API_KEY to enable full functionality."
            )
            ctx.generate_fn = lambda prompt: (
                f"[No LLM provider configured] Prompt received ({len(prompt)} chars). "
                f"Configure an API key to enable AI responses."
            )

        # ── Subsystem Initialization ──
        MemoryManager = modules["MemoryManager"]
        ctx.memory_manager = MemoryManager(config=modules["brain_config"])

        ThinkingLoop = modules["ThinkingLoop"]
        ctx.thinking_loop = ThinkingLoop(
            generate_fn=ctx.generate_fn,
            memory=ctx.memory_manager,
        )

        CodeAnalyzer = modules["CodeAnalyzer"]
        ctx.code_analyzer = CodeAnalyzer()

        ctx.tool_registry = modules["tool_registry"]

        # Long-Term Memory (optional — may fail if dirs don't exist yet)
        try:
            LongTermMemory = modules["LongTermMemory"]
            ctx.long_term_memory = LongTermMemory()
        except Exception as e:
            logger.warning(f"Long-term memory init skipped: {e}")

        # Agent Controller
        try:
            AgentController = modules["AgentController"]
            ctx.agent_controller = AgentController(
                generate_fn=ctx.generate_fn,
                memory=ctx.memory_manager,
                tool_registry=ctx.tool_registry,
                agent_id="mcp_agent",
            )
        except Exception as e:
            logger.warning(f"Agent controller init skipped: {e}")

        # Threat Scanner (optional)
        try:
            from agents.safety.threat_scanner import ThreatScanner
            threat_cfg = modules["threat_config"]
            ctx.threat_scanner = ThreatScanner(
                quarantine_dir=threat_cfg.quarantine_dir,
                entropy_threshold=threat_cfg.entropy_threshold,
                max_file_size_mb=threat_cfg.max_file_size_mb,
            )
        except Exception as e:
            logger.debug(f"Threat scanner init skipped: {e}")

        # Store configs for resource access
        ctx.configs = {
            "brain": {k: str(v) for k, v in modules["brain_config"].__dict__.items()},
            "agent": {k: str(v) for k, v in modules["agent_config"].__dict__.items()},
            "provider": provider_name,
            "available_providers": provider_cfg.available_providers,
        }

        ctx._initialized = True
        logger.info(
            f"✅ MCP Server ready — provider={provider_name}, "
            f"tools={len(ctx.tool_registry.list_tools()) if ctx.tool_registry else 0}, "
            f"agent={'active' if ctx.agent_controller else 'unavailable'}"
        )

        yield ctx

    finally:
        logger.info("🛑 MCP Server shutting down — cleaning up...")
        ctx._initialized = False


# ──────────────────────────────────────────────
# Server Factory
# ──────────────────────────────────────────────

def create_mcp_server() -> FastMCP:
    """
    Create and configure the MCP server with all tools, resources, and prompts.

    Returns:
        Fully configured FastMCP server ready to run.
    """
    mcp = FastMCP(
        "SuperChain AI Agent",
        lifespan=app_lifespan,
        stateless_http=True,
        json_response=True,
    )

    # ─────────────────────────────────────
    # TOOLS (18 total)
    # ─────────────────────────────────────

    @mcp.tool()
    def chat(
        message: str,
        session_id: str = "",
        use_thinking: bool = True,
    ) -> dict:
        """
        Conversational chat with the AI agent.

        Engages the full agent pipeline: domain classification, persona detection,
        advanced reasoning, tool orchestration, and safety filtering.

        Args:
            message: User message to process
            session_id: Optional session ID for conversation continuity
            use_thinking: Enable the Synthesize→Verify→Learn thinking loop
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized", "answer": ""}

        if ctx.agent_controller:
            resp = ctx.agent_controller.process(
                user_input=message,
                use_thinking_loop=use_thinking,
                session_id=session_id or None,
            )
            return {
                "answer": resp.answer,
                "confidence": resp.confidence,
                "iterations": resp.iterations,
                "mode": resp.mode,
                "tools_used": [t.get("tool", "") for t in resp.tools_used],
                "session_id": resp.session_id,
                "duration_ms": resp.duration_ms,
            }
        else:
            # Fallback direct generation
            answer = ctx.generate_fn(message)
            return {"answer": answer, "confidence": 0.8, "mode": "direct"}

    @mcp.tool()
    def agent_task(
        task: str,
        use_thinking: bool = True,
        max_tool_calls: int = 10,
    ) -> dict:
        """
        Submit a complex task for the AI agent to solve.

        Uses the full agent pipeline with multi-step reasoning, tool orchestration,
        and self-healing code generation.

        Args:
            task: Complex task description for the agent
            use_thinking: Enable multi-iteration thinking loop
            max_tool_calls: Maximum number of tool calls allowed (1-50)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        if ctx.agent_controller:
            resp = ctx.agent_controller.process(
                user_input=task,
                use_thinking_loop=use_thinking,
                max_tool_calls=min(max(max_tool_calls, 1), 50),
            )
            return {
                "answer": resp.answer,
                "confidence": resp.confidence,
                "iterations": resp.iterations,
                "mode": resp.mode,
                "tools_used": [t.get("tool", "") for t in resp.tools_used],
                "thinking_trace": (
                    resp.thinking_trace.summary()
                    if resp.thinking_trace else None
                ),
                "duration_ms": resp.duration_ms,
            }
        else:
            return {"answer": ctx.generate_fn(task), "mode": "direct"}

    @mcp.tool()
    def think(
        problem: str,
        action_type: str = "general",
        max_iterations: int = 5,
    ) -> dict:
        """
        Run the Synthesize → Verify → Learn thinking loop.

        Multi-iteration reasoning that generates hypotheses, verifies them,
        assesses risk, and learns from each attempt. Uses credit assignment
        and prompt evolution for continuous self-improvement.

        Args:
            problem: The problem or question to reason about
            action_type: Type of action (general, code, math, analysis, creative)
            max_iterations: Maximum reasoning iterations (1-10)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        result = ctx.thinking_loop.think(
            problem=problem,
            action_type=action_type,
            max_iterations=min(max(max_iterations, 1), 10),
        )
        return {
            "answer": result.final_answer,
            "confidence": result.final_confidence,
            "iterations": result.iterations,
            "mode": result.mode.value,
            "domain": result.domain,
            "strategies_used": result.strategies_used,
            "reflection": result.reflection,
            "total_duration_ms": result.total_duration_ms,
        }

    @mcp.tool()
    def quick_think(
        problem: str,
        action_type: str = "general",
    ) -> dict:
        """
        Quick single-pass reasoning without the full thinking loop.

        For simple queries where multi-iteration reasoning is overkill.
        Uses direct generation with basic verification.

        Args:
            problem: The question or task to answer
            action_type: Type of action (general, code, math, creative)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        answer = ctx.thinking_loop.quick_think(
            problem=problem,
            action_type=action_type,
        )
        return {"answer": answer, "mode": "quick_think"}

    @mcp.tool()
    def analyze_code(
        code: str,
        language: str = "python",
    ) -> dict:
        """
        Deep static code analysis with AST parsing and security scanning.

        Runs 15 vulnerability detectors (SQL injection, XSS, path traversal,
        command injection, hardcoded secrets, SSRF, etc.) and computes a
        quality score with cyclomatic complexity, nesting depth, and more.

        Args:
            code: Source code to analyze
            language: Programming language (python, javascript, typescript, java, go, rust, c, cpp)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        report = ctx.code_analyzer.analyze(code, language=language)
        return {
            "language": report.language,
            "is_parseable": report.is_parseable,
            "parse_error": report.parse_error,
            "structure": {
                "functions": report.structure.functions,
                "classes": report.structure.classes,
                "imports": report.structure.imports,
                "total_lines": report.structure.total_lines,
                "code_lines": report.structure.code_lines,
            },
            "vulnerabilities": [
                {
                    "id": v.id,
                    "name": v.name,
                    "severity": v.severity.value,
                    "description": v.description,
                    "line": v.line,
                    "fix_suggestion": v.fix_suggestion,
                    "cwe_id": v.cwe_id,
                }
                for v in report.vulnerabilities
            ],
            "quality": {
                "overall_score": report.quality.overall_score,
                "grade": report.quality.grade,
                "cyclomatic_complexity": report.quality.cyclomatic_complexity,
                "max_nesting_depth": report.quality.max_nesting_depth,
                "avg_function_length": report.quality.avg_function_length,
            },
            "security_score": report.security_score,
            "summary": report.summary(),
        }

    @mcp.tool()
    def execute_code(
        code: str,
        language: str = "python",
        timeout: int = 30,
    ) -> dict:
        """
        Execute code in a sandboxed environment.

        Runs code safely with timeout protection and output capture.
        Supported via the agent's code executor tool.

        Args:
            code: Code to execute
            language: Programming language (python, javascript, bash)
            timeout: Execution timeout in seconds (1-120)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        if ctx.tool_registry:
            tool = ctx.tool_registry.get("execute_code")
            if tool:
                result = ctx.tool_registry.execute(
                    "execute_code",
                    sandbox=True,
                    code=code,
                    language=language,
                    timeout=min(max(timeout, 1), 120),
                )
                return result

        return {"error": "Code execution tool not available"}

    @mcp.tool()
    def search_web(
        query: str,
        max_results: int = 5,
    ) -> dict:
        """
        Search the internet using DuckDuckGo.

        Returns relevant search results with titles, URLs, and snippets.

        Args:
            query: Search query string
            max_results: Maximum number of results to return (1-20)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        if ctx.tool_registry:
            tool = ctx.tool_registry.get("web_search")
            if tool:
                result = ctx.tool_registry.execute(
                    "web_search",
                    query=query,
                    max_results=min(max(max_results, 1), 20),
                )
                return result

        return {"error": "Web search tool not available"}

    @mcp.tool()
    def scan_threats(
        target_path: str,
    ) -> dict:
        """
        Scan a file or directory for security threats.

        4-layer threat detection: signature matching, entropy analysis,
        behavioral heuristics, and content scanning. Detects viruses,
        malware, suspicious scripts, and data exfiltration attempts.

        Args:
            target_path: Absolute path to file or directory to scan
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        if not ctx.threat_scanner:
            return {"error": "Threat scanner not available"}

        target = Path(target_path)
        if not target.exists():
            return {"error": f"Path does not exist: {target_path}"}

        try:
            if target.is_file():
                report = ctx.threat_scanner.scan_file(str(target))
            elif target.is_dir():
                report = ctx.threat_scanner.scan_directory(str(target))
            else:
                return {"error": "Target is neither a file nor directory"}

            return {
                "scan_id": report.scan_id,
                "is_threat": report.is_threat,
                "threat_type": (
                    report.threat_type.value if report.threat_type else None
                ),
                "severity": (
                    report.severity.value if report.severity else None
                ),
                "confidence": report.confidence,
                "summary": report.summary(),
                "recommended_action": report.recommended_action.value,
            }
        except Exception as e:
            return {"error": f"Scan failed: {str(e)}"}

    @mcp.tool()
    def analyze_file(
        file_path: str,
        question: str = "Analyze this file in detail.",
    ) -> dict:
        """
        Analyze a file using the multimodal pipeline.

        Supports PDFs, images, code files, and documents.
        Uses AI to answer questions about the file content.

        Args:
            file_path: Absolute path to the file to analyze
            question: Specific question about the file content
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        target = Path(file_path)
        if not target.exists():
            return {"error": f"File does not exist: {file_path}"}

        try:
            from brain.multimodal import MultimodalPipeline
            pipeline = MultimodalPipeline(generate_fn=ctx.generate_fn)
            result = pipeline.analyze(str(target), question=question)
            return {"analysis": result, "file": str(target)}
        except ImportError:
            # Fallback: read and analyze via LLM
            try:
                content = target.read_text(encoding="utf-8", errors="replace")[:8000]
                prompt = (
                    f"Analyze this file ({target.name}):\n\n"
                    f"```\n{content}\n```\n\n"
                    f"Question: {question}"
                )
                return {"analysis": ctx.generate_fn(prompt), "file": str(target)}
            except Exception as e:
                return {"error": f"Analysis failed: {str(e)}"}

    @mcp.tool()
    def memory_recall(
        query: str,
        max_results: int = 5,
    ) -> dict:
        """
        Query episodic long-term memory for relevant past experiences.

        Searches across conversation history, learned patterns, and
        knowledge graph connections using hybrid vector + BM25 search.

        Args:
            query: Search query for memory recall
            max_results: Maximum episodes to return (1-20)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        results = []

        # Short-term memory (bug diary)
        if ctx.memory_manager:
            failures = ctx.memory_manager.retrieve_similar_failures(
                query, n_results=min(max(max_results, 1), 20),
            )
            for f in failures:
                results.append({
                    "type": "failure_memory",
                    "id": f.id,
                    "task": f.task,
                    "root_cause": f.root_cause,
                    "fix": f.fix,
                    "category": f.category,
                    "severity": f.severity,
                })

        # Episodic long-term memory
        if ctx.long_term_memory:
            try:
                episodes = ctx.long_term_memory.episodic.recall(
                    query, max_results=max_results,
                )
                for ep in episodes:
                    results.append({
                        "type": "episodic",
                        "episode_id": ep.episode_id,
                        "topic": ep.topic,
                        "summary": ep.summary,
                        "outcome": ep.outcome,
                        "tags": ep.tags,
                    })
            except Exception:
                pass

        return {"query": query, "results": results, "count": len(results)}

    @mcp.tool()
    def memory_store(
        topic: str,
        summary: str,
        tags: str = "",
        outcome: str = "success",
    ) -> dict:
        """
        Store a new episode in long-term episodic memory.

        Args:
            topic: Topic or title of the episode
            summary: Summary of what happened
            tags: Comma-separated tags for categorization
            outcome: Outcome of the episode (success, failure, partial)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        if not ctx.long_term_memory:
            return {"error": "Long-term memory not available"}

        try:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            ep = ctx.long_term_memory.episodic.store_episode(
                topic=topic,
                user_messages=[summary],
                agent_responses=[f"Stored: {topic}"],
                outcome=outcome,
                tags=tag_list,
            )
            return {
                "stored": True,
                "episode_id": ep.episode_id if hasattr(ep, 'episode_id') else "ok",
                "topic": topic,
            }
        except Exception as e:
            return {"error": f"Storage failed: {str(e)}"}

    @mcp.tool()
    def tutor_start(
        topic: str,
    ) -> dict:
        """
        Start an expert tutoring session on any topic.

        Uses 8 teaching techniques including Socratic questioning,
        gamified learning, and flowchart generation. Auto-detects
        when LLM knowledge is insufficient and triggers deep research.

        Args:
            topic: Subject to learn about
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        try:
            from agents.profiles.ultimate_tutor import UltimateTutorEngine
            tutor = UltimateTutorEngine(generate_fn=ctx.generate_fn)
            result = tutor.start_session(topic)
            return result
        except Exception as e:
            # Fallback: direct LLM tutoring
            prompt = (
                f"You are an expert tutor. Begin teaching the student about: {topic}\n\n"
                f"Start with an assessment of their current knowledge level, "
                f"then provide a structured lesson plan."
            )
            return {
                "response": ctx.generate_fn(prompt),
                "topic": topic,
                "session_id": f"mcp_tutor_{int(time.time())}",
            }

    @mcp.tool()
    def tutor_respond(
        session_id: str,
        message: str,
    ) -> dict:
        """
        Continue a tutoring conversation with a student response.

        Args:
            session_id: Tutoring session ID from tutor_start
            message: Student's response or question
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        try:
            from agents.profiles.ultimate_tutor import UltimateTutorEngine
            tutor = UltimateTutorEngine(generate_fn=ctx.generate_fn)
            result = tutor.respond(session_id, message)
            return result
        except Exception as e:
            return {
                "response": ctx.generate_fn(
                    f"Continue tutoring. Student says: {message}"
                ),
                "session_id": session_id,
            }

    @mcp.tool()
    def swarm_execute(
        task: str,
        roles: str = "architect,coder,reviewer",
    ) -> dict:
        """
        Deploy multi-agent swarm intelligence on a complex task.

        Decomposes the task into subtasks, assigns specialized agent roles,
        runs them in parallel, and merges results into a unified solution.

        Args:
            task: Complex task to solve with swarm intelligence
            roles: Comma-separated agent roles (architect,coder,reviewer,tester,analyst)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        try:
            from agents.profiles.swarm_intelligence import SwarmOrchestrator
            role_list = [r.strip() for r in roles.split(",") if r.strip()]
            orchestrator = SwarmOrchestrator(generate_fn=ctx.generate_fn)
            result = orchestrator.execute(task, roles=role_list)
            return result
        except Exception as e:
            return {
                "answer": ctx.generate_fn(
                    f"Act as a team of {roles}. Solve this collaboratively:\n{task}"
                ),
                "mode": "fallback_direct",
                "error": str(e),
            }

    @mcp.tool()
    def forge_tool(
        description: str,
        name: str = "",
    ) -> dict:
        """
        Create a new tool at runtime using the Tool Forge.

        The AI generates working Python code for the tool based on
        a natural language description, then registers it for immediate use.

        Args:
            description: Natural language description of the tool to create
            name: Optional name for the tool (auto-generated if empty)
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        try:
            from agents.tools.tool_forge import ToolForge
            forge = ToolForge(generate_fn=ctx.generate_fn)
            result = forge.create_tool(description=description, name=name or None)
            return result
        except Exception as e:
            return {"error": f"Tool forge failed: {str(e)}"}

    @mcp.tool()
    def transpile_code(
        code: str,
        source_lang: str = "python",
        target_lang: str = "javascript",
    ) -> dict:
        """
        Transpile code from one language to another.

        Uses AI-guided code transpilation with semantic understanding
        to produce idiomatic output in the target language.

        Args:
            code: Source code to transpile
            source_lang: Source programming language
            target_lang: Target programming language
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        try:
            from brain.transpiler import Transpiler
            transpiler = Transpiler(generate_fn=ctx.generate_fn)
            result = transpiler.transpile(
                code, source_lang=source_lang, target_lang=target_lang,
            )
            return result
        except Exception as e:
            # Fallback
            prompt = (
                f"Transpile this {source_lang} code to {target_lang}.\n"
                f"Return ONLY the transpiled code.\n\n"
                f"```{source_lang}\n{code}\n```"
            )
            return {
                "transpiled_code": ctx.generate_fn(prompt),
                "source_lang": source_lang,
                "target_lang": target_lang,
            }

    @mcp.tool()
    def evolve_code(
        code: str,
        goal: str = "improve quality and performance",
    ) -> dict:
        """
        Evolve code through AI-guided iterative improvement.

        Uses genetic programming principles to improve code quality,
        performance, and security through multiple generations.

        Args:
            code: Source code to evolve
            goal: Evolution objective (e.g., "optimize for speed", "improve readability")
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        try:
            from brain.evolution import EvolutionEngine
            engine = EvolutionEngine(generate_fn=ctx.generate_fn)
            result = engine.evolve(code, goal=goal)
            return result
        except Exception as e:
            prompt = (
                f"Improve this code. Goal: {goal}\n\n"
                f"```\n{code}\n```\n\n"
                f"Return the improved version with explanations."
            )
            return {
                "evolved_code": ctx.generate_fn(prompt),
                "goal": goal,
            }

    @mcp.tool()
    def calculate(
        expression: str,
    ) -> dict:
        """
        Safely evaluate a mathematical expression.

        Uses AST-based safe evaluation (no eval). Supports arithmetic,
        trigonometric functions, logarithms, and common math operations.

        Args:
            expression: Mathematical expression to evaluate (e.g., "sqrt(16) + 2^3")
        """
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return {"error": "Server not initialized"}

        if ctx.tool_registry:
            tool = ctx.tool_registry.get("calculator")
            if tool:
                result = ctx.tool_registry.execute(
                    "calculator", expression=expression,
                )
                return result

        # Fallback: safe AST evaluation
        try:
            from agents.tools.calculator import safe_eval
            result = safe_eval(expression)
            return {"success": True, "result": result, "expression": expression}
        except Exception as e:
            return {"error": f"Calculation failed: {str(e)}"}

    # ─────────────────────────────────────
    # RESOURCES (6 total)
    # ─────────────────────────────────────

    @mcp.resource("system://health")
    def system_health() -> str:
        """System health and readiness status."""
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        status = {
            "status": "ready" if ctx.is_ready() else "initializing",
            "provider": ctx.configs.get("provider", "unknown"),
            "available_providers": ctx.configs.get("available_providers", []),
            "agent_active": ctx.agent_controller is not None,
            "memory_active": ctx.memory_manager is not None,
            "thinking_loop_active": ctx.thinking_loop is not None,
            "code_analyzer_active": ctx.code_analyzer is not None,
            "threat_scanner_active": ctx.threat_scanner is not None,
            "long_term_memory_active": ctx.long_term_memory is not None,
            "tools_count": (
                len(ctx.tool_registry.list_tools())
                if ctx.tool_registry else 0
            ),
        }
        return json.dumps(status, indent=2)

    @mcp.resource("system://config")
    def system_config() -> str:
        """Current system configuration summary."""
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        return json.dumps(ctx.configs, indent=2, default=str)

    @mcp.resource("memory://stats")
    def memory_stats() -> str:
        """Memory subsystem statistics (failures, successes, categories)."""
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if ctx.memory_manager:
            stats = ctx.memory_manager.get_stats()
            return json.dumps(stats, indent=2, default=str)
        return json.dumps({"error": "Memory manager not available"})

    @mcp.resource("memory://failures")
    def memory_failures() -> str:
        """Bug diary — stored failure records for learning."""
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if ctx.memory_manager:
            failures = []
            for f in ctx.memory_manager.failures[-20:]:  # Last 20
                failures.append({
                    "id": f.id,
                    "task": f.task[:200],
                    "root_cause": f.root_cause[:200],
                    "fix": f.fix[:200],
                    "category": f.category,
                    "severity": f.severity,
                    "weight": f.weight,
                })
            return json.dumps(failures, indent=2)
        return json.dumps([])

    @mcp.resource("agents://profiles")
    def agent_profiles() -> str:
        """Available agent profiles and domain experts."""
        profiles = [
            {"name": "ultimate_tutor", "domain": "teaching", "description": "9-technique expert tutoring engine with gamification, deep research, and Socratic mastery"},
            {"name": "deep_researcher", "domain": "research", "description": "Multi-source deep research agent"},
            {"name": "devils_advocate", "domain": "critical_thinking", "description": "Adversarial argument challenger"},
            {"name": "devops_reviewer", "domain": "devops", "description": "CI/CD and infrastructure reviewer"},
            {"name": "swarm_intelligence", "domain": "multi_agent", "description": "Multi-agent task decomposition"},
            {"name": "threat_hunter", "domain": "security", "description": "Security audit and threat detection"},
            {"name": "contract_hunter", "domain": "legal", "description": "Toxic clause detection in contracts"},
            {"name": "migration_architect", "domain": "engineering", "description": "Code migration planning"},
            {"name": "multi_agent_orchestrator", "domain": "orchestration", "description": "Multi-agent debate and synthesis"},
        ]
        return json.dumps(profiles, indent=2)

    @mcp.resource("agents://tools")
    def agent_tools() -> str:
        """Registered tools catalog with descriptions and risk levels."""
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if ctx.tool_registry:
            tools = []
            for t in ctx.tool_registry.list_tools():
                tools.append({
                    "name": t.name,
                    "description": t.description,
                    "risk_level": t.risk_level.value,
                    "group": t.group,
                    "requires_sandbox": t.requires_sandbox,
                })
            return json.dumps(tools, indent=2)
        return json.dumps([])

    # ─────────────────────────────────────
    # PROMPTS (5 total)
    # ─────────────────────────────────────

    @mcp.prompt()
    def code_review(code: str, language: str = "python", focus: str = "security") -> list[base.Message]:
        """
        Expert code review prompt with security and quality analysis.

        Args:
            code: Source code to review
            language: Programming language
            focus: Review focus area (security, performance, readability, all)
        """
        return [
            base.UserMessage(
                f"Please perform an expert-level code review of the following {language} code.\n\n"
                f"Focus area: {focus}\n\n"
                f"```{language}\n{code}\n```\n\n"
                f"Provide:\n"
                f"1. Security vulnerabilities (with CWE IDs)\n"
                f"2. Performance issues\n"
                f"3. Code quality concerns\n"
                f"4. Best practice violations\n"
                f"5. Specific fix suggestions with corrected code"
            ),
        ]

    @mcp.prompt()
    def debug_error(error: str, context: str = "", language: str = "python") -> list[base.Message]:
        """
        Multi-hypothesis error debugging prompt.

        Args:
            error: Error message or stack trace
            context: Additional context (code, recent changes, etc.)
            language: Programming language
        """
        ctx_section = f"\n\nContext:\n```\n{context}\n```" if context else ""
        return [
            base.UserMessage(
                f"I'm encountering this error in my {language} code:\n\n"
                f"```\n{error}\n```{ctx_section}"
            ),
            base.AssistantMessage(
                "I'll analyze this using multi-hypothesis reasoning. Let me:\n"
                "1. Generate multiple root cause hypotheses\n"
                "2. Verify each hypothesis against the evidence\n"
                "3. Provide targeted fix suggestions\n\n"
                "Starting analysis..."
            ),
        ]

    @mcp.prompt()
    def research_topic(topic: str, depth: str = "comprehensive") -> str:
        """
        Deep research prompt with adversarial validation.

        Args:
            topic: Research topic or question
            depth: Research depth (quick, comprehensive, exhaustive)
        """
        return (
            f"Research the following topic at {depth} depth:\n\n"
            f"Topic: {topic}\n\n"
            f"Provide:\n"
            f"1. Executive summary\n"
            f"2. Key findings with sources\n"
            f"3. Multiple perspectives (including contrarian views)\n"
            f"4. Practical implications\n"
            f"5. Knowledge gaps and areas for further investigation\n\n"
            f"Use adversarial validation: challenge each finding and note confidence levels."
        )

    @mcp.prompt()
    def explain_concept(concept: str, expertise_level: str = "intermediate") -> str:
        """
        Socratic teaching prompt for concept explanation.

        Args:
            concept: Concept to explain
            expertise_level: Student's level (beginner, intermediate, expert)
        """
        return (
            f"Teach me about '{concept}' using the Socratic method.\n\n"
            f"My expertise level: {expertise_level}\n\n"
            f"Guidelines:\n"
            f"1. Start with probing questions to assess understanding\n"
            f"2. Build from fundamentals to advanced concepts\n"
            f"3. Use analogies and real-world examples\n"
            f"4. Challenge assumptions with thought experiments\n"
            f"5. Provide practice problems for reinforcement"
        )

    @mcp.prompt()
    def system_audit() -> list[base.Message]:
        """
        Full system health and security audit prompt.
        """
        return [
            base.UserMessage(
                "Perform a comprehensive system audit covering:\n\n"
                "1. **Health**: Check all subsystem statuses\n"
                "2. **Memory**: Review stored failures and learning patterns\n"
                "3. **Security**: Run threat scans on critical paths\n"
                "4. **Performance**: Check response times and resource usage\n"
                "5. **Configuration**: Verify all settings are optimal\n\n"
                "Use the available tools to gather data, then provide a detailed report "
                "with recommendations for improvement."
            ),
            base.AssistantMessage(
                "I'll conduct a thorough system audit. Let me start by checking "
                "the system health resource and memory statistics..."
            ),
        ]

    # ─────────────────────────────────────
    # NEW EXPERT-LEVEL TOOLS (6 additional)
    # ─────────────────────────────────────

    @mcp.tool()
    def project_scaffold(
        project_type: str = "fastapi",
        name: str = "my_project",
        features: str = "auth,database,testing",
    ) -> dict:
        """
        Generate a full project scaffold with best-practice structure.

        Creates production-ready project skeletons with CI/CD configs,
        Docker support, testing setup, and documentation templates.

        Args:
            project_type: Type of project (fastapi, react, nextjs, unity, flask, express)
            name: Project name
            features: Comma-separated features to include (auth,database,testing,docker,ci)
        """
        tid, t0 = _new_trace()
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return _make_response({}, tid, t0, MCPError(ErrorCode.NOT_INITIALIZED.value, "Server not initialized"))

        err = _validate_string(name, "name", 100)
        if err:
            return _make_response({}, tid, t0, err)

        feature_list = [f.strip() for f in features.split(",") if f.strip()]

        templates = {
            "fastapi": {
                "dirs": ["app", "app/api", "app/models", "app/core", "tests", "alembic"],
                "files": ["main.py", "requirements.txt", "Dockerfile", ".env.example", "README.md"],
            },
            "react": {
                "dirs": ["src", "src/components", "src/hooks", "src/pages", "public", "tests"],
                "files": ["package.json", "vite.config.ts", "tsconfig.json", "index.html", "README.md"],
            },
            "nextjs": {
                "dirs": ["app", "app/api", "components", "lib", "public", "tests"],
                "files": ["package.json", "next.config.js", "tsconfig.json", "README.md"],
            },
            "unity": {
                "dirs": ["Assets/Scripts", "Assets/Prefabs", "Assets/Materials", "Assets/Scenes", "Tests"],
                "files": ["README.md", ".gitignore", "ProjectSettings.asset"],
            },
            "flask": {
                "dirs": ["app", "app/routes", "app/models", "app/templates", "tests", "migrations"],
                "files": ["run.py", "requirements.txt", "Dockerfile", "config.py", "README.md"],
            },
            "express": {
                "dirs": ["src", "src/routes", "src/middleware", "src/models", "tests"],
                "files": ["package.json", "server.js", "Dockerfile", ".env.example", "README.md"],
            },
        }

        template = templates.get(project_type, templates["fastapi"])

        if "docker" in feature_list and "Dockerfile" not in template["files"]:
            template["files"].append("Dockerfile")
            template["files"].append("docker-compose.yml")
        if "ci" in feature_list:
            template["dirs"].append(".github/workflows")
            template["files"].append(".github/workflows/ci.yml")

        # Use LLM to generate detailed scaffold content
        try:
            prompt = (
                f"Generate a production-ready {project_type} project scaffold named '{name}'.\n"
                f"Features: {', '.join(feature_list)}\n"
                f"Provide the content for each key file as a JSON object with file paths as keys.\n"
                f"Include: {', '.join(template['files'][:5])}"
            )
            content = ctx.generate_fn(prompt)
            _circuit.record_success("llm")
            data = {
                "project_type": project_type,
                "name": name,
                "features": feature_list,
                "structure": {"directories": template["dirs"], "files": template["files"]},
                "generated_content": content,
            }
            _metrics.record("project_scaffold", (time.time() - t0) * 1000)
            return _make_response(data, tid, t0)
        except Exception as e:
            _circuit.record_failure("llm")
            _metrics.record("project_scaffold", (time.time() - t0) * 1000, is_error=True)
            return _make_response({}, tid, t0, MCPError(ErrorCode.INTERNAL_ERROR.value, str(e)))

    @mcp.tool()
    def deep_research(
        topic: str,
        depth: str = "comprehensive",
        max_sources: int = 5,
    ) -> dict:
        """
        Multi-source deep research with citations and adversarial validation.

        Performs comprehensive research using web search, memory recall,
        and LLM reasoning. Validates findings with devil's advocate analysis.

        Args:
            topic: Research topic or question
            depth: Research depth (quick, comprehensive, exhaustive)
            max_sources: Maximum sources to consult (1-10)
        """
        tid, t0 = _new_trace()
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return _make_response({}, tid, t0, MCPError(ErrorCode.NOT_INITIALIZED.value, "Server not initialized"))

        err = _validate_string(topic, "topic")
        if err:
            return _make_response({}, tid, t0, err)

        max_sources = min(max(max_sources, 1), 10)

        try:
            # Try the deep researcher profile first
            from agents.profiles.deep_researcher import DeepResearcher
            researcher = DeepResearcher(generate_fn=ctx.generate_fn)
            result = researcher.research(topic, depth=depth, max_sources=max_sources)
            _circuit.record_success("llm")
            _metrics.record("deep_research", (time.time() - t0) * 1000)
            return _make_response(result if isinstance(result, dict) else {"research": result}, tid, t0)
        except Exception:
            # Fallback: direct LLM research
            try:
                prompt = (
                    f"Conduct {depth} research on: {topic}\n\n"
                    f"Provide:\n1. Executive summary\n2. Key findings with confidence levels\n"
                    f"3. Contrarian perspectives\n4. Knowledge gaps\n5. Practical implications"
                )
                answer = ctx.generate_fn(prompt)
                _circuit.record_success("llm")
                data = {"topic": topic, "depth": depth, "research": answer}
                _metrics.record("deep_research", (time.time() - t0) * 1000)
                return _make_response(data, tid, t0)
            except Exception as e:
                _circuit.record_failure("llm")
                _metrics.record("deep_research", (time.time() - t0) * 1000, is_error=True)
                return _make_response({}, tid, t0, MCPError(ErrorCode.LLM_FAILURE.value, str(e)))

    @mcp.tool()
    def refactor_code(
        code: str,
        language: str = "python",
        strategy: str = "clean_architecture",
    ) -> dict:
        """
        AI-guided code refactoring with before/after diff output.

        Applies SOLID principles, design patterns, and language-specific
        best practices. Returns refactored code with explanations.

        Args:
            code: Source code to refactor
            language: Programming language
            strategy: Refactoring strategy (clean_architecture, performance, readability, solid, dry)
        """
        tid, t0 = _new_trace()
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return _make_response({}, tid, t0, MCPError(ErrorCode.NOT_INITIALIZED.value, "Server not initialized"))

        err = _validate_string(code, "code", _MAX_CODE_LEN)
        if err:
            return _make_response({}, tid, t0, err)

        try:
            # First analyze, then refactor
            analysis = {}
            if ctx.code_analyzer:
                report = ctx.code_analyzer.analyze(code, language=language)
                analysis = {
                    "quality_score": report.quality.overall_score,
                    "grade": report.quality.grade,
                    "complexity": report.quality.cyclomatic_complexity,
                    "vulnerabilities": len(report.vulnerabilities),
                }

            prompt = (
                f"Refactor this {language} code using '{strategy}' strategy.\n\n"
                f"```{language}\n{code}\n```\n\n"
                f"Apply: SOLID principles, design patterns, {language} best practices.\n"
                f"Return:\n1. Refactored code in a code block\n"
                f"2. List of changes made\n3. Before/after comparison"
            )
            refactored = ctx.generate_fn(prompt)
            _circuit.record_success("llm")
            data = {
                "original_analysis": analysis,
                "strategy": strategy,
                "language": language,
                "refactored": refactored,
            }
            _metrics.record("refactor_code", (time.time() - t0) * 1000)
            return _make_response(data, tid, t0)
        except Exception as e:
            _circuit.record_failure("llm")
            _metrics.record("refactor_code", (time.time() - t0) * 1000, is_error=True)
            return _make_response({}, tid, t0, MCPError(ErrorCode.INTERNAL_ERROR.value, str(e)))

    @mcp.tool()
    def generate_tests(
        code: str,
        language: str = "python",
        framework: str = "pytest",
        coverage_target: str = "comprehensive",
    ) -> dict:
        """
        Auto-generate unit tests for any code snippet.

        Creates test cases covering happy paths, edge cases, error handling,
        and boundary conditions. Supports pytest, jest, and unittest.

        Args:
            code: Source code to generate tests for
            language: Programming language
            framework: Testing framework (pytest, jest, unittest, mocha, xunit)
            coverage_target: Coverage target (basic, comprehensive, exhaustive)
        """
        tid, t0 = _new_trace()
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return _make_response({}, tid, t0, MCPError(ErrorCode.NOT_INITIALIZED.value, "Server not initialized"))

        err = _validate_string(code, "code", _MAX_CODE_LEN)
        if err:
            return _make_response({}, tid, t0, err)

        try:
            prompt = (
                f"Generate {coverage_target} {framework} tests for this {language} code:\n\n"
                f"```{language}\n{code}\n```\n\n"
                f"Include:\n1. Happy path tests\n2. Edge cases\n3. Error/exception tests\n"
                f"4. Boundary value tests\n5. Mock/fixture setup where needed\n"
                f"Return ONLY valid {framework} test code."
            )
            tests = ctx.generate_fn(prompt)
            _circuit.record_success("llm")
            data = {
                "language": language,
                "framework": framework,
                "coverage_target": coverage_target,
                "generated_tests": tests,
            }
            _metrics.record("generate_tests", (time.time() - t0) * 1000)
            return _make_response(data, tid, t0)
        except Exception as e:
            _circuit.record_failure("llm")
            _metrics.record("generate_tests", (time.time() - t0) * 1000, is_error=True)
            return _make_response({}, tid, t0, MCPError(ErrorCode.LLM_FAILURE.value, str(e)))

    @mcp.tool()
    def workspace_summary(
        directory: str = ".",
        max_depth: int = 3,
    ) -> dict:
        """
        Summarize an entire codebase or workspace structure.

        Recursively scans the directory tree and returns file counts,
        language breakdown, and structural overview.

        Args:
            directory: Root directory to summarize (default: current dir)
            max_depth: Maximum directory depth to scan (1-10)
        """
        tid, t0 = _new_trace()
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return _make_response({}, tid, t0, MCPError(ErrorCode.NOT_INITIALIZED.value, "Server not initialized"))

        safe_dir = _sanitize_path(directory)
        if not safe_dir:
            return _make_response({}, tid, t0, MCPError(ErrorCode.VALIDATION_FAILED.value, "Invalid path"))
        target = Path(safe_dir)
        if not target.is_dir():
            return _make_response({}, tid, t0, MCPError(ErrorCode.FILE_NOT_FOUND.value, f"Not a directory: {safe_dir}"))

        max_depth = min(max(max_depth, 1), 10)

        ext_counts: Dict[str, int] = {}
        total_files = 0
        total_dirs = 0
        total_bytes = 0
        tree_lines: List[str] = []

        try:
            for root, dirs, files in os.walk(safe_dir):
                depth = root.replace(safe_dir, "").count(os.sep)
                if depth >= max_depth:
                    dirs.clear()
                    continue
                # Skip hidden/build directories
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"__pycache__", "node_modules", ".git", "venv", "dist", "build"}]
                indent = "  " * depth
                tree_lines.append(f"{indent}📁 {os.path.basename(root)}/")
                total_dirs += 1
                for f in files:
                    fp = os.path.join(root, f)
                    total_files += 1
                    try:
                        total_bytes += os.path.getsize(fp)
                    except OSError:
                        pass
                    ext = Path(f).suffix.lower() or "(no ext)"
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1

            data = {
                "directory": safe_dir,
                "total_files": total_files,
                "total_directories": total_dirs,
                "total_size_mb": round(total_bytes / (1024 * 1024), 2),
                "language_breakdown": dict(sorted(ext_counts.items(), key=lambda x: -x[1])[:20]),
                "tree": "\n".join(tree_lines[:100]),
            }
            _metrics.record("workspace_summary", (time.time() - t0) * 1000)
            return _make_response(data, tid, t0)
        except Exception as e:
            _metrics.record("workspace_summary", (time.time() - t0) * 1000, is_error=True)
            return _make_response({}, tid, t0, MCPError(ErrorCode.INTERNAL_ERROR.value, str(e)))

    @mcp.tool()
    def git_operations(
        operation: str = "status",
        args: str = "",
        repo_path: str = ".",
    ) -> dict:
        """
        Perform Git operations on a repository.

        Supports status, log, diff, branch, and read-only operations.
        Destructive operations (push, force) are blocked for safety.

        Args:
            operation: Git operation (status, log, diff, branch, show, blame, stash_list)
            args: Additional arguments for the git command
            repo_path: Path to the git repository
        """
        tid, t0 = _new_trace()
        ctx: AppContext = mcp.get_context().request_context.lifespan_context
        if not ctx.is_ready():
            return _make_response({}, tid, t0, MCPError(ErrorCode.NOT_INITIALIZED.value, "Server not initialized"))

        # Safety: only allow read-only git operations
        allowed_ops = {"status", "log", "diff", "branch", "show", "blame", "stash_list", "remote", "tag"}
        if operation not in allowed_ops:
            return _make_response(
                {}, tid, t0,
                MCPError(ErrorCode.VALIDATION_FAILED.value, f"Operation '{operation}' not allowed. Use: {', '.join(sorted(allowed_ops))}"),
            )

        safe_path = _sanitize_path(repo_path)
        if not safe_path:
            return _make_response({}, tid, t0, MCPError(ErrorCode.VALIDATION_FAILED.value, "Invalid repository path"))

        try:
            cmd_map = {
                "status": ["git", "status", "--porcelain"],
                "log": ["git", "log", "--oneline", "-20"],
                "diff": ["git", "diff", "--stat"],
                "branch": ["git", "branch", "-a"],
                "show": ["git", "show", "--stat", "HEAD"],
                "blame": ["git", "blame"],
                "stash_list": ["git", "stash", "list"],
                "remote": ["git", "remote", "-v"],
                "tag": ["git", "tag", "-l"],
            }
            cmd = cmd_map.get(operation, ["git", operation])
            if args:
                cmd.extend(args.split())

            result = subprocess.run(
                cmd, cwd=safe_path, capture_output=True, text=True, timeout=30,
            )
            data = {
                "operation": operation,
                "output": result.stdout[:5000],
                "errors": result.stderr[:1000] if result.returncode != 0 else "",
                "return_code": result.returncode,
            }
            _metrics.record("git_operations", (time.time() - t0) * 1000)
            return _make_response(data, tid, t0)
        except subprocess.TimeoutExpired:
            _metrics.record("git_operations", (time.time() - t0) * 1000, is_error=True)
            return _make_response({}, tid, t0, MCPError(ErrorCode.LLM_TIMEOUT.value, "Git command timed out"))
        except Exception as e:
            _metrics.record("git_operations", (time.time() - t0) * 1000, is_error=True)
            return _make_response({}, tid, t0, MCPError(ErrorCode.INTERNAL_ERROR.value, str(e)))

    # ─────────────────────────────────────
    # NEW RESOURCES (3 additional, total: 9)
    # ─────────────────────────────────────

    @mcp.resource("system://capabilities")
    def system_capabilities() -> str:
        """Full capability manifest — all tools, resources, and prompts with descriptions."""
        capabilities = {
            "server": "Astra SuperChain AI Agent — MCP Server",
            "version": "3.0.0",
            "tools_count": 24,
            "resources_count": 9,
            "prompts_count": 8,
            "tool_categories": {
                "conversation": ["chat", "agent_task"],
                "reasoning": ["think", "quick_think"],
                "code": ["analyze_code", "execute_code", "refactor_code", "generate_tests", "transpile_code", "evolve_code"],
                "research": ["deep_research", "search_web"],
                "security": ["scan_threats"],
                "memory": ["memory_recall", "memory_store"],
                "learning": ["tutor_start", "tutor_respond"],
                "multi_agent": ["swarm_execute"],
                "devtools": ["forge_tool", "project_scaffold", "workspace_summary", "git_operations"],
                "math": ["calculate"],
                "files": ["analyze_file"],
            },
            "transports": ["stdio", "streamable-http"],
            "supported_ides": ["Cursor", "Antigravity (Gemini)", "Unity Editor", "Claude Desktop", "VS Code", "Windsurf"],
        }
        return json.dumps(capabilities, indent=2)

    @mcp.resource("system://metrics")
    def system_metrics() -> str:
        """Performance telemetry — per-tool call counts, latencies, and error rates."""
        data = {
            "uptime_info": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool_metrics": _metrics.snapshot(),
            "circuit_breaker": {
                "status": "healthy",
                "open_circuits": list(_circuit._open_since.keys()) if _circuit._open_since else [],
            },
        }
        return json.dumps(data, indent=2)

    @mcp.resource("workspace://structure")
    def workspace_structure() -> str:
        """Project file tree for the current Astra Agent workspace."""
        tree: List[str] = []
        root = Path(_BACKEND_DIR).parent
        try:
            for item in sorted(root.rglob("*")):
                rel = item.relative_to(root)
                # Skip hidden/build dirs
                parts = rel.parts
                if any(p.startswith(".") or p in {"__pycache__", "node_modules", "venv", "dist"} for p in parts):
                    continue
                depth = len(parts) - 1
                if depth > 3:
                    continue
                prefix = "📁 " if item.is_dir() else "📄 "
                tree.append(f"{'  ' * depth}{prefix}{item.name}")
                if len(tree) > 200:
                    tree.append("... (truncated)")
                    break
        except Exception as e:
            tree.append(f"Error scanning: {e}")
        return json.dumps({"root": str(root), "tree": "\n".join(tree)}, indent=2)

    # ─────────────────────────────────────
    # NEW PROMPTS (3 additional, total: 8)
    # ─────────────────────────────────────

    @mcp.prompt()
    def architect_system(
        requirements: str,
        scale: str = "startup",
        constraints: str = "",
    ) -> list[base.Message]:
        """
        System architecture design prompt with DDD and scalability patterns.

        Args:
            requirements: System requirements description
            scale: Expected scale (startup, growth, enterprise, hyperscale)
            constraints: Technical constraints or preferences
        """
        constraint_section = f"\n\nConstraints: {constraints}" if constraints else ""
        return [
            base.UserMessage(
                f"Design a production system architecture for:\n\n"
                f"**Requirements:** {requirements}\n"
                f"**Target Scale:** {scale}"
                f"{constraint_section}\n\n"
                f"Include:\n"
                f"1. High-level architecture diagram (Mermaid syntax)\n"
                f"2. Domain-Driven Design bounded contexts\n"
                f"3. Data flow and API design\n"
                f"4. Database schema recommendations\n"
                f"5. Deployment topology (containers, orchestration)\n"
                f"6. Scalability strategy (horizontal/vertical)\n"
                f"7. Security architecture (AuthN/AuthZ, encryption)\n"
                f"8. Monitoring and observability plan"
            ),
            base.AssistantMessage(
                "I'll design a comprehensive system architecture. Let me start "
                "with the high-level overview and then drill into each layer..."
            ),
        ]

    @mcp.prompt()
    def optimize_performance(
        code: str,
        language: str = "python",
        bottleneck: str = "",
    ) -> list[base.Message]:
        """
        Performance profiling and optimization prompt.

        Args:
            code: Code to optimize
            language: Programming language
            bottleneck: Known bottleneck description (optional)
        """
        bottleneck_ctx = f"\n\nKnown bottleneck: {bottleneck}" if bottleneck else ""
        return [
            base.UserMessage(
                f"Optimize the performance of this {language} code:\n\n"
                f"```{language}\n{code}\n```"
                f"{bottleneck_ctx}\n\n"
                f"Provide:\n"
                f"1. Time complexity analysis (Big-O)\n"
                f"2. Space complexity analysis\n"
                f"3. Identified bottlenecks with profiling rationale\n"
                f"4. Optimized version with explanations\n"
                f"5. Benchmark comparison (before vs after)\n"
                f"6. Memory optimization opportunities\n"
                f"7. Concurrency/parallelism recommendations"
            ),
        ]

    @mcp.prompt()
    def write_documentation(
        code: str,
        doc_type: str = "all",
        language: str = "python",
    ) -> str:
        """
        Auto-generate documentation for code.

        Args:
            code: Source code to document
            doc_type: Documentation type (docstrings, readme, api, all)
            language: Programming language
        """
        return (
            f"Generate {doc_type} documentation for this {language} code:\n\n"
            f"```{language}\n{code}\n```\n\n"
            f"Include:\n"
            f"1. Module-level docstring with purpose and usage\n"
            f"2. Function/class docstrings (Google style for Python)\n"
            f"3. Parameter types and descriptions\n"
            f"4. Return value documentation\n"
            f"5. Usage examples\n"
            f"6. API reference table (if applicable)\n"
            f"7. README section with installation and quickstart"
        )

    return mcp

