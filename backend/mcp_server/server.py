"""
MCP Server — FastMCP integration for SuperChain Universal AI Agent.
───────────────────────────────────────────────────────────────────
Expert-level MCP server exposing:
  • 18 Tools   — chat, agent tasks, thinking loop, code analysis, etc.
  • 6 Resources — system health, config, memory stats, profiles, tools
  • 5 Prompts  — code review, debugging, research, teaching, audit

Architecture:
  Uses FastMCP's lifespan protocol for lazy initialization.
  All subsystems are created once and shared via AppContext.
  Thread-safe via generate_fn isolation per request.
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

    return mcp
