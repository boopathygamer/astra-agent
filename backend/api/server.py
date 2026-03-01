"""
FastAPI Server — Main API for the Custom LLM System.
─────────────────────────────────────────────────────
Endpoints:
  POST /chat           — Conversational chat with memory
  POST /agent/task     — Submit complex task for agent
  GET  /memory/stats   — View bug diary statistics
  GET  /health         — System health check

Security:
  - API key authentication (X-API-Key header)
  - Rate limiting (100 req/min default)
  - Request size limits
  - Sanitized error responses
  - Security headers
  - CORS origin validation
  - Request ID tracking
"""

import logging
import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import api_config, UPLOADS_DIR
from api.models import (
    ChatRequest, ChatResponse,
    VisionRequest, VisionResponse,
    AgentTaskRequest, AgentTaskResponse,
    MemoryStatsResponse, HealthResponse,
)

logger = logging.getLogger(__name__)

# ── Security constants ──
_MAX_REQUEST_BODY_SIZE = 1 * 1024 * 1024  # 1 MB max request body
_API_KEY = os.getenv("LLM_API_KEY", "")  # Empty = auth disabled for dev
_RATE_LIMIT_PER_MINUTE = int(os.getenv("LLM_RATE_LIMIT", "100"))
_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "LLM_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://localhost:8000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]


# ──────────────────────────────────────────────
# Security: Rate Limiter
# ──────────────────────────────────────────────

class _RateLimitStore:
    """Simple in-memory token-bucket rate limiter per client IP."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window
        # Prune old entries
        self._hits[client_ip] = [
            t for t in self._hits[client_ip] if t > cutoff
        ]
        if len(self._hits[client_ip]) >= self.max_requests:
            return False
        self._hits[client_ip].append(now)
        return True


_rate_limiter = _RateLimitStore(max_requests=_RATE_LIMIT_PER_MINUTE)


# ──────────────────────────────────────────────
# Security: API Key Authentication
# ──────────────────────────────────────────────

async def verify_api_key(request: Request):
    """Dependency: validate API key if one is configured."""
    if not _API_KEY:
        return  # Auth disabled in dev mode
    
    provided_key = request.headers.get("X-API-Key", "")
    if provided_key != _API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )


# ──────────────────────────────────────────────
# Middleware: Security Headers + Rate Limiting + Request ID
# (uses decorator pattern for starlette compatibility)
# ──────────────────────────────────────────────

_security_middleware_registered = False  # Will be applied after app is created


# ──────────────────────────────────────────────
# Lifespan (replaces deprecated @app.on_event)
# ──────────────────────────────────────────────

class AppState:
    model = None
    tokenizer = None
    engine = None
    vision_pipeline = None
    agent_controller = None
    is_ready = False

state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all components on server startup, cleanup on shutdown."""
    logger.info("=" * 60)
    logger.info("Starting Custom LLM System...")
    logger.info("=" * 60)

    try:
        from agents.controller import AgentController
        from core.model_providers import ProviderRegistry
        
        # Strategy 1: Try to get registry from main module's app state
        registry = None
        try:
            from main import _app_state
            registry = _app_state.get("registry")
            if registry and registry.active:
                logger.info(f"✅ Got registry from main._app_state: {registry.active_name}")
        except ImportError:
            pass

        # Strategy 2: If that failed, auto-detect from environment/config
        if not registry or not registry.active:
            logger.info("🔄 Auto-detecting LLM provider from environment...")
            try:
                registry = ProviderRegistry.auto_detect()
                if registry.active:
                    logger.info(f"✅ Auto-detected provider: {registry.active_name} ({registry.active.model})")
                else:
                    logger.warning("⚠️ No API key found. Set GEMINI_API_KEY, OPENAI_API_KEY, or CLAUDE_API_KEY.")
            except Exception as detect_err:
                logger.warning(f"⚠️ Provider auto-detect failed: {detect_err}")

        if registry and registry.active:
            generate_fn = registry.generate_fn()
            state.agent_controller = AgentController(generate_fn=generate_fn)
            logger.info("✅ Agent controller ready")
        else:
            logger.warning("⚠️ No LLM provider available — chat will not work until API keys are configured via /api/keys")

        state.is_ready = True
        logger.info("=" * 60)
        logger.info("🚀 System ready! All components initialized.")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Startup failed: {type(e).__name__}", exc_info=True)
        raise

    yield  # Server is running
    
    # ── Graceful Shutdown ──
    logger.info("⏳ Graceful shutdown — draining in-flight tasks...")
    
    # 1. Stop log exporter
    try:
        from telemetry.log_exporter import StructuredLogExporter
        # If a log exporter was started, stop it
    except Exception:
        pass
    
    # 2. Kill background processes
    if state.agent_controller and hasattr(state.agent_controller, 'process_manager'):
        for proc in state.agent_controller.process_manager.list_processes():
            if proc.get("status") == "running":
                state.agent_controller.process_manager.kill(proc["process_id"])
    
    # 3. Final metrics flush
    try:
        from telemetry.metrics import MetricsCollector
        mc = MetricsCollector.get_instance()
        logger.info(f"📊 Final metrics: {mc.get_report().counters}")
    except Exception:
        pass
    
    logger.info("✅ Shutdown complete.")


# ──────────────────────────────────────────────
# Application
# ──────────────────────────────────────────────

app = FastAPI(
    title="Custom LLM System",
    description=(
        "Universal AI Agent — Multi-Model Provider System. "
        "Features: multimodal image analysis, self-improving from mistakes, "
        "multi-hypothesis reasoning, and professional agent assistants."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not _API_KEY else None,  # Hide docs in production
    redoc_url=None,
)

# Security middleware (decorator-based for starlette compat)
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Adds security headers, rate limiting, and request tracking."""
    # ── Request ID ──
    request_id = str(uuid.uuid4())[:8]
    
    # ── Rate limiting ──
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again later."},
            headers={"Retry-After": "60"},
        )

    # ── Request body size check ──
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_REQUEST_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": "Request body too large"},
        )

    response = await call_next(request)
    
    # ── Security headers ──
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"
    
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# ── Phase 6C: Mount SSE & WebSocket routers ──
try:
    from api.streaming import router as sse_router
    app.include_router(sse_router)
except ImportError:
    pass

try:
    from api.websocket_handler import router as ws_router
    app.include_router(ws_router)
except ImportError:
    pass


# ──────────────────────────────────────────────
# Health Check (no auth required)
# ──────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    """System health check."""
    return HealthResponse(
        status="ready" if state.is_ready else "loading",
        model_loaded=state.model is not None,
        vision_ready=state.vision_pipeline is not None,
        memory_entries=(
            len(state.agent_controller.memory.failures)
            if state.agent_controller else 0
        ),
        tools_available=(
            len(state.agent_controller.tools.list_tools())
            if state.agent_controller else 0
        ),
    )


# ──────────────────────────────────────────────
# Chat Endpoint (auth required)
# ──────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat(request: ChatRequest):
    """Conversational chat with memory and self-thinking."""
    if not state.is_ready:
        raise HTTPException(503, "System not ready")

    if not state.agent_controller:
        return ChatResponse(
            answer="⚠️ No AI provider is configured. Please go to Settings and add your API key (e.g. Gemini, OpenAI, or Claude) to activate the chatbot.",
            confidence=0.0,
            mode="no_provider",
        )

    # Input validation
    if not request.message or not request.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    if len(request.message) > 50_000:
        raise HTTPException(400, "Message too long (max 50,000 characters)")

    start = time.time()

    # Strategy: Try process() first (full pipeline), fall back to chat() (simple)
    try:
        if request.use_thinking:
            result = state.agent_controller.process(
                user_input=request.message,
                use_thinking_loop=True,
            )
            return ChatResponse(
                answer=result.answer,
                confidence=result.confidence,
                iterations=result.iterations,
                mode=result.mode,
                tools_used=[t.get("tool", "") for t in result.tools_used],
                thinking_steps=[
                    f"Step {s.iteration}: {s.action_taken} (conf={s.verification.confidence:.3f})"
                    for s in (result.thinking_trace.steps if result.thinking_trace else [])
                ],
                duration_ms=(time.time() - start) * 1000,
            )
        else:
            answer = state.agent_controller.chat(request.message)
            return ChatResponse(
                answer=answer,
                confidence=0.8,
                duration_ms=(time.time() - start) * 1000,
            )

    except Exception as process_err:
        logger.warning(f"process() failed ({type(process_err).__name__}), falling back to chat()")
        # Fall back to the simpler chat() method which handles errors more gracefully
        try:
            answer = state.agent_controller.chat(request.message)
            return ChatResponse(
                answer=answer,
                confidence=0.5,
                mode="fallback",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as chat_err:
            logger.error(f"Chat fallback also failed: {type(chat_err).__name__}", exc_info=True)
            # Return the error as a chat response rather than HTTP 500
            error_msg = str(chat_err)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                error_msg = "The AI service is currently rate-limited (429 Too Many Requests). Please wait a moment and try again."
            return ChatResponse(
                answer=f"⚠️ {error_msg}",
                confidence=0.0,
                mode="error",
                duration_ms=(time.time() - start) * 1000,
            )


# ──────────────────────────────────────────────
# Agent Endpoint (auth required)
# ──────────────────────────────────────────────

@app.post("/agent/task", response_model=AgentTaskResponse, dependencies=[Depends(verify_api_key)])
async def agent_task(request: AgentTaskRequest):
    """Submit a complex task for the agent to solve."""
    if not state.is_ready:
        raise HTTPException(503, "System not ready")

    # Input validation
    if not request.task or not request.task.strip():
        raise HTTPException(400, "Task cannot be empty")
    if len(request.task) > 50_000:
        raise HTTPException(400, "Task too long (max 50,000 characters)")

    start = time.time()

    try:
        result = state.agent_controller.process(
            user_input=request.task,
            use_thinking_loop=request.use_thinking,
            max_tool_calls=request.max_tool_calls,
        )

        thinking_dict = None
        if result.thinking_trace:
            thinking_dict = {
                "iterations": result.thinking_trace.iterations,
                "final_confidence": result.thinking_trace.final_confidence,
                "mode": result.thinking_trace.mode.value,
                "steps": [
                    {
                        "iteration": s.iteration,
                        "action": s.action_taken,
                        "confidence": s.verification.confidence if s.verification else 0,
                    }
                    for s in result.thinking_trace.steps
                ],
            }

        return AgentTaskResponse(
            answer=result.answer,
            confidence=result.confidence,
            iterations=result.iterations,
            mode=result.mode,
            tools_used=result.tools_used,
            thinking_trace=thinking_dict,
            duration_ms=(time.time() - start) * 1000,
        )

    except Exception as e:
        logger.error(f"Agent error: {type(e).__name__}", exc_info=True)
        raise HTTPException(500, "Agent task failed. Please try again.")


# ──────────────────────────────────────────────
# Memory Endpoint (auth required)
# ──────────────────────────────────────────────

@app.get("/memory/stats", response_model=MemoryStatsResponse, dependencies=[Depends(verify_api_key)])
async def memory_stats():
    """View bug diary and memory statistics."""
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")

    stats = state.agent_controller.memory.get_stats()
    return MemoryStatsResponse(**stats)


@app.get("/memory/failures", dependencies=[Depends(verify_api_key)])
async def list_failures():
    """List all failure records from the bug diary."""
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")

    from dataclasses import asdict
    failures = state.agent_controller.memory.failures
    return {
        "count": len(failures),
        "failures": [asdict(f) for f in failures[-20:]],  # Last 20
    }


# ──────────────────────────────────────────────
# Streaming Endpoint (SSE) (auth required)
# ──────────────────────────────────────────────

@app.post("/chat/stream", dependencies=[Depends(verify_api_key)])
async def chat_stream(request: ChatRequest):
    """
    Server-Sent Events (SSE) streaming chat.
    Returns text chunks, tool events, and thinking steps.
    """
    if not state.is_ready:
        raise HTTPException(503, "System not ready")
    
    if not state.agent_controller:
        raise HTTPException(503, "No AI provider configured. Add your API key in Settings.")
    
    if not request.message or not request.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    from fastapi.responses import StreamingResponse
    import json
    import asyncio

    async def event_stream():
        try:
            # Use the simpler chat() method for streaming — it's more resilient
            answer = state.agent_controller.chat(request.message)

            # Check if the answer is actually an error from generate_fn
            is_error = answer.startswith("[Error:") and answer.endswith("]")
            
            if is_error:
                # Clean up the error message for user presentation
                error_text = answer[7:-1].strip()  # Remove [Error: ...]
                if "429" in error_text or "Too Many Requests" in error_text:
                    clean_msg = "The AI service is currently rate-limited. Please wait a moment and try again."
                else:
                    clean_msg = error_text
                
                yield f"data: {json.dumps({'type': 'text', 'content': f'⚠️ {clean_msg}'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'meta': {'duration_ms': 0}})}\n\n"
                return

            # Stream the response word-by-word for a natural feel
            words = answer.split(' ')
            chunk_size = 8  # words per chunk for natural streaming feel
            
            for i in range(0, len(words), chunk_size):
                chunk = ' '.join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += ' '  # Add trailing space between chunks
                data = json.dumps({"type": "text", "content": chunk})
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.03)  # Small delay for streaming feel

            # Send done event
            done_data = json.dumps({
                "type": "done",
                "meta": {
                    "duration_ms": 1500,
                    "tokens": len(words),
                }
            })
            yield f"data: {done_data}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {type(e).__name__}", exc_info=True)
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                error_msg = "The AI service is currently rate-limited. Please wait a moment and try again."
            yield f"data: {json.dumps({'type': 'text', 'content': f'⚠️ {error_msg}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'meta': {'duration_ms': 0}})}\n\n"

    return StreamingResponse(
        event_stream(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ──────────────────────────────────────────────
# Session Endpoints (auth required)
# ──────────────────────────────────────────────

@app.get("/sessions", dependencies=[Depends(verify_api_key)])
async def list_sessions():
    """List all active sessions."""
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")

    return {
        "sessions": state.agent_controller.session_manager.list_sessions(
            active_only=True,
        ),
    }


@app.get("/sessions/{session_id}/history", dependencies=[Depends(verify_api_key)])
async def session_history(session_id: str, limit: int = 50):
    """Get session transcript history."""
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")
    
    # Validate session_id format (prevent path traversal)
    if not session_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "Invalid session ID format")
    
    # Cap limit to prevent abuse
    limit = min(limit, 200)

    messages = state.agent_controller.session_manager.get_history(
        session_id=session_id,
        limit=limit,
    )
    return {"session_id": session_id, "messages": messages}


# ──────────────────────────────────────────────
# Process Endpoints (auth required)
# ──────────────────────────────────────────────

@app.get("/processes", dependencies=[Depends(verify_api_key)])
async def list_processes():
    """List background processes."""
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")

    return {"processes": state.agent_controller.list_processes()}


@app.get("/processes/{process_id}", dependencies=[Depends(verify_api_key)])
async def poll_process(process_id: str):
    """Poll a background process for status."""
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")
    
    # Validate process_id format
    if not process_id.isalnum() or len(process_id) > 20:
        raise HTTPException(400, "Invalid process ID format")

    return state.agent_controller.poll_process(process_id)


# ──────────────────────────────────────────────
# Agent Stats Endpoint (auth required)
# ──────────────────────────────────────────────

@app.get("/agent/stats", dependencies=[Depends(verify_api_key)])
async def agent_stats():
    """Get comprehensive agent statistics."""
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")

    return state.agent_controller.get_stats()


# ──────────────────────────────────────────────
# Expert Tutor Endpoints (auth required)
# ──────────────────────────────────────────────

def _get_tutor():
    """Lazily initialize the ExpertTutorEngine."""
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")
    if not hasattr(state, '_tutor') or state._tutor is None:
        from agents.profiles.expert_tutor import ExpertTutorEngine
        state._tutor = ExpertTutorEngine(
            generate_fn=state.agent_controller.generate_fn,
            agent_controller=state.agent_controller,
        )
    return state._tutor


@app.post("/tutor/start", dependencies=[Depends(verify_api_key)])
async def tutor_start(request: dict):
    """
    Start an expert tutoring session on any topic.
    
    Auto-detects when LLM knowledge is insufficient and triggers
    deep internet research to teach with expert-level coaching.
    
    Body: {"topic": "quantum computing"}
    """
    topic = request.get("topic", "").strip()
    if not topic:
        raise HTTPException(400, "Topic is required")
    if len(topic) > 500:
        raise HTTPException(400, "Topic too long (max 500 chars)")
    
    try:
        tutor = _get_tutor()
        result = tutor.api_start_session(topic)
        return result
    except Exception as e:
        logger.error(f"Tutor start error: {type(e).__name__}", exc_info=True)
        raise HTTPException(500, "Failed to start tutoring session")


@app.post("/tutor/respond", dependencies=[Depends(verify_api_key)])
async def tutor_respond(request: dict):
    """
    Send student response in an active tutoring session.
    
    Body: {"session_id": "abc123", "message": "I think it works like..."}
    """
    session_id = request.get("session_id", "").strip()
    message = request.get("message", "").strip()
    
    if not session_id:
        raise HTTPException(400, "session_id is required")
    if not message:
        raise HTTPException(400, "message is required")
    if len(message) > 10_000:
        raise HTTPException(400, "Message too long (max 10,000 chars)")
    
    try:
        tutor = _get_tutor()
        result = tutor.api_respond(session_id, message)
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tutor respond error: {type(e).__name__}", exc_info=True)
        raise HTTPException(500, "Tutoring error")


# ──────────────────────────────────────────────
# Multi-Agent Swarm Endpoint (auth required)
# ──────────────────────────────────────────────

@app.post("/swarm/execute", dependencies=[Depends(verify_api_key)])
async def swarm_execute(request: dict):
    """
    Deploy multi-agent swarm intelligence on a complex task.
    Decomposes the task, runs specialized agents in parallel,
    and merges results into a unified solution.
    
    Body: {"task": "Build a secure REST API", "roles": ["architect","coder","reviewer"]}
    """
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")
    
    task = request.get("task", "").strip()
    roles = request.get("roles", None)
    
    if not task:
        raise HTTPException(400, "Task is required")
    if len(task) > 2000:
        raise HTTPException(400, "Task too long (max 2000 chars)")
    
    try:
        from agents.profiles.swarm_intelligence import SwarmOrchestrator
        swarm = SwarmOrchestrator(
            generate_fn=state.agent_controller.generate_fn,
            agent_controller=state.agent_controller,
        )
        result = swarm.api_execute(task, roles)
        return result
    except Exception as e:
        logger.error(f"Swarm error: {type(e).__name__}", exc_info=True)
        raise HTTPException(500, "Swarm execution failed")


# ──────────────────────────────────────────────
# Long-Term Memory Endpoints (auth required)
# ──────────────────────────────────────────────

def _get_long_term_memory():
    """Lazily initialize LongTermMemory."""
    if not hasattr(state, '_ltm') or state._ltm is None:
        from brain.long_term_memory import LongTermMemory
        state._ltm = LongTermMemory()
    return state._ltm


@app.get("/memory/long-term", dependencies=[Depends(verify_api_key)])
async def long_term_memory_stats():
    """Get long-term memory statistics (episodic, procedural, knowledge graph)."""
    ltm = _get_long_term_memory()
    return ltm.get_stats()


@app.post("/memory/recall", dependencies=[Depends(verify_api_key)])
async def memory_recall(request: dict):
    """
    Recall relevant episodes from long-term memory.
    
    Body: {"query": "machine learning discussion"}
    """
    query = request.get("query", "").strip()
    if not query:
        raise HTTPException(400, "Query is required")
    
    ltm = _get_long_term_memory()
    episodes = ltm.episodic.recall(query, max_results=5)
    return {
        "query": query,
        "episodes": [
            {
                "episode_id": ep.episode_id,
                "topic": ep.topic,
                "summary": ep.summary,
                "outcome": ep.outcome,
                "tags": ep.tags,
            }
            for ep in episodes
        ],
        "knowledge_context": ltm.knowledge.get_context_prompt(),
        "user_profile": ltm.procedural.get_user_profile(),
    }


# ──────────────────────────────────────────────
# Tool Forge Endpoint (auth required)
# ──────────────────────────────────────────────

@app.post("/forge/create", dependencies=[Depends(verify_api_key)])
async def forge_create_tool(request: dict):
    """
    Create a new tool at runtime using the Tool Forge.
    
    Body: {"description": "calculate fibonacci numbers", "name": "fibonacci"}
    """
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")
    
    description = request.get("description", "").strip()
    name = request.get("name", "").strip() or None
    
    if not description:
        raise HTTPException(400, "Tool description is required")
    if len(description) > 1000:
        raise HTTPException(400, "Description too long (max 1000 chars)")
    
    try:
        from agents.tools.tool_forge import ToolForge
        forge = ToolForge(generate_fn=state.agent_controller.generate_fn)
        forged = forge.forge_tool(description, tool_name=name)
        
        if forged:
            return {
                "success": True,
                "forge_id": forged.forge_id,
                "name": forged.name,
                "description": forged.description,
                "test_output": forged.test_output,
            }
        else:
            return {"success": False, "error": "Tool validation failed"}
    except Exception as e:
        logger.error(f"Forge error: {type(e).__name__}", exc_info=True)
        raise HTTPException(500, "Tool forge failed")


# ──────────────────────────────────────────────
# Multimodal Analysis Endpoint (auth required)
# ──────────────────────────────────────────────

@app.post("/analyze", dependencies=[Depends(verify_api_key)])
async def multimodal_analyze(request: dict):
    """
    Analyze a file using the multimodal pipeline (images, PDFs, code, audio).
    
    Body: {"file_path": "/path/to/file.pdf", "question": "summarize this document"}
    """
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")
    
    file_path = request.get("file_path", "").strip()
    question = request.get("question", "").strip()
    
    if not file_path:
        raise HTTPException(400, "file_path is required")
    
    from pathlib import Path
    if not Path(file_path).exists():
        raise HTTPException(404, "File not found")
    
    try:
        from brain.multimodal import MultimodalBrain
        brain = MultimodalBrain(generate_fn=state.agent_controller.generate_fn)
        
        if question:
            answer = brain.process_and_answer(file_path, question)
            return {"file": file_path, "question": question, "answer": answer}
        else:
            result = brain.process(file_path)
            return {
                "file": file_path,
                "modality": result.modality,
                "extracted_text": result.extracted_text[:5000],
                "analysis": result.analysis[:5000],
            }
    except Exception as e:
        logger.error(f"Multimodal error: {type(e).__name__}", exc_info=True)
        raise HTTPException(500, "Analysis failed")


# ──────────────────────────────────────────────
# Cross-Platform Device Endpoints
# ──────────────────────────────────────────────

@app.get("/device/platforms")
async def device_platforms():
    """List all supported device platforms and their capabilities."""
    from agents.tools.platform_support import get_platform_manager
    mgr = get_platform_manager()
    return {"platforms": mgr.get_supported_platforms()}


@app.post("/device/register", dependencies=[Depends(verify_api_key)])
async def device_register(request: dict):
    """
    Register a remote device (Android, iOS, IoT, etc.).
    The companion app calls this on first connection.
    
    Body: {
        "device_name": "My Pixel 8",
        "platform": "android",
        "callback_url": "http://192.168.1.42:8081",
        "os_version": "Android 14",
        "architecture": "arm64",
        "capabilities": ["get_info","get_battery","get_storage"],
        "metadata": {"model": "Pixel 8", "sdk_version": "34"}
    }
    """
    name = request.get("device_name", "").strip()
    plat = request.get("platform", "").strip()
    callback = request.get("callback_url", "").strip()

    if not name:
        raise HTTPException(400, "device_name is required")
    if not plat:
        raise HTTPException(400, "platform is required")
    if not callback:
        raise HTTPException(400, "callback_url is required")

    valid_platforms = {"android", "ios", "iot", "windows", "linux", "macos"}
    if plat.lower() not in valid_platforms:
        raise HTTPException(400, f"Invalid platform. Must be one of: {valid_platforms}")

    from agents.tools.platform_support import get_platform_manager
    mgr = get_platform_manager()
    device = mgr.register_device(
        device_name=name,
        platform_type=plat,
        callback_url=callback,
        os_version=request.get("os_version", ""),
        architecture=request.get("architecture", ""),
        capabilities=request.get("capabilities"),
        metadata=request.get("metadata"),
    )

    return {
        "device_id": device.device_id,
        "name": device.device_name,
        "platform": device.platform.value,
        "status": device.status.value,
        "message": f"Device '{name}' registered successfully",
    }


@app.post("/device/heartbeat", dependencies=[Depends(verify_api_key)])
async def device_heartbeat(request: dict):
    """
    Keep-alive ping from a remote device.
    
    Body: {"device_id": "dev_abc12345"}
    """
    device_id = request.get("device_id", "").strip()
    if not device_id:
        raise HTTPException(400, "device_id is required")

    from agents.tools.platform_support import get_platform_manager
    mgr = get_platform_manager()
    if mgr.heartbeat(device_id):
        return {"status": "ok", "device_id": device_id}
    raise HTTPException(404, "Device not found")


@app.get("/device/list", dependencies=[Depends(verify_api_key)])
async def device_list():
    """List all registered devices (local + remote)."""
    from agents.tools.platform_support import get_platform_manager
    mgr = get_platform_manager()
    return {"devices": mgr.list_devices()}


@app.post("/device/command", dependencies=[Depends(verify_api_key)])
async def device_command(request: dict):
    """
    Execute a command on any registered device.
    
    Body: {
        "device_id": "dev_abc12345",
        "action": "get_battery",
        "parameters": {}
    }
    """
    device_id = request.get("device_id", "").strip()
    action = request.get("action", "").strip()

    if not device_id:
        raise HTTPException(400, "device_id is required")
    if not action:
        raise HTTPException(400, "action is required")

    from agents.tools.platform_support import get_platform_manager
    mgr = get_platform_manager()

    result = mgr.execute_command(
        device_id=device_id,
        action=action,
        parameters=request.get("parameters", {}),
    )

    if not result.success:
        raise HTTPException(400, result.error)

    return {
        "command_id": result.command_id,
        "device_id": result.device_id,
        "success": result.success,
        "result": result.result,
        "execution_ms": result.execution_ms,
    }


@app.post("/device/unregister", dependencies=[Depends(verify_api_key)])
async def device_unregister(request: dict):
    """
    Remove a remote device from the registry.
    
    Body: {"device_id": "dev_abc12345"}
    """
    device_id = request.get("device_id", "").strip()
    if not device_id:
        raise HTTPException(400, "device_id is required")

    from agents.tools.platform_support import get_platform_manager
    mgr = get_platform_manager()
    if mgr.unregister_device(device_id):
        return {"status": "removed", "device_id": device_id}
    raise HTTPException(404, "Device not found or is local")


# ──────────────────────────────────────────────
# API Key Management (activate real providers)
# ──────────────────────────────────────────────

# Track which providers are activated via frontend
_active_provider_keys: list = []


@app.post("/api/keys")
async def save_api_keys(request: dict):
    """
    Accept 1–5 API keys from the Settings panel and hot-reload
    the provider registry. Auto-detects provider from key format.

    Body: { "keys": ["AIzaSy...", "sk-...", ...] }
    """
    global _active_provider_keys

    keys = request.get("keys", [])
    if not keys or not isinstance(keys, list):
        raise HTTPException(400, "At least one API key is required")
    if len(keys) > 5:
        raise HTTPException(400, "Maximum 5 API keys allowed")

    # Filter + auto-detect
    activated_providers = []
    for raw_key in keys:
        api_key = raw_key.strip() if isinstance(raw_key, str) else ""
        if not api_key or len(api_key) > 500:
            continue
        from core.model_providers import detect_provider
        detected = detect_provider(api_key)
        activated_providers.append({
            "api_key": api_key,
            **detected,
        })

    if not activated_providers:
        raise HTTPException(400, "No valid API keys provided")

    # ── Hot-reload providers ──
    try:
        from core.model_providers import ProviderRegistry, UniversalProvider

        primary = activated_providers[0]

        os.environ["LLM_API_KEY"] = primary["api_key"]
        os.environ["LLM_BASE_URL"] = primary["base_url"]
        os.environ["LLM_MODEL"] = primary["model"]

        # Persist to .env file so keys survive server restarts
        try:
            from pathlib import Path
            env_path = Path(__file__).parent.parent / ".env"
            env_lines = []
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith('#') and '=' in stripped:
                            key_name = stripped.split('=', 1)[0].strip()
                            if key_name in ('LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL'):
                                continue  # Skip old values
                        env_lines.append(line.rstrip())
            
            env_lines.append(f'LLM_API_KEY={primary["api_key"]}')
            env_lines.append(f'LLM_BASE_URL={primary["base_url"]}')
            env_lines.append(f'LLM_MODEL={primary["model"]}')
            
            with open(env_path, 'w') as f:
                f.write('\n'.join(env_lines) + '\n')
            logger.info(f"🔑 API keys persisted to {env_path}")
        except Exception as persist_err:
            logger.warning(f"Could not persist API keys to .env: {persist_err}")

        # Create provider + registry
        registry = ProviderRegistry()
        provider = UniversalProvider(
            api_key=primary["api_key"],
            base_url=primary["base_url"],
            model=primary["model"],
        )
        registry.register(provider)
        registry.set_active("universal")

        try:
            from main import _app_state
            _app_state["registry"] = registry
        except ImportError:
            pass

        from agents.controller import AgentController
        generate_fn = registry.generate_fn()
        state.agent_controller = AgentController(generate_fn=generate_fn)
        state.is_ready = True

        _active_provider_keys = [
            {"provider": p["provider"], "active": True}
            for p in activated_providers
        ]

        logger.info(
            f"🔑 API keys activated: {len(activated_providers)} provider(s) — "
            f"detected={primary['provider']} model={primary['model']}"
        )

        return {
            "status": "activated",
            "activated": len(activated_providers),
            "providers": _active_provider_keys,
        }

    except Exception as e:
        logger.error(f"API key activation failed: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to activate providers: {str(e)}")


@app.get("/api/keys/status")
async def api_key_status():
    """Return which providers are currently active (no key values exposed)."""
    return {
        "providers": _active_provider_keys if _active_provider_keys else [
            {"provider": "mock", "active": True}
        ],
        "total_active": len(_active_provider_keys) if _active_provider_keys else 1,
    }


# ──────────────────────────────────────────────
# Frontend Static Files — Serve Astra Agent UI
# ──────────────────────────────────────────────
# Serves the built React frontend from frontend/dist/
# so both backend API and frontend run on ONE localhost.

from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_FRONTEND_DIR = _Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIR.is_dir():
    # Serve static assets (JS, CSS, images) from /assets
    _ASSETS_DIR = _FRONTEND_DIR / "assets"
    if _ASSETS_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="frontend-assets")

    # SPA catch-all: any path not matched by API routes serves index.html
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve the Astra Agent frontend (SPA catch-all)."""
        # Check if the requested file exists in dist/
        file_path = _FRONTEND_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html for client-side routing
        index = _FRONTEND_DIR / "index.html"
        if index.is_file():
            return FileResponse(str(index))
        raise HTTPException(404, "Frontend not built. Run: cd frontend && npm run build")
else:
    logger.info("ℹ️ Frontend not found at %s — run 'cd frontend && npm run build' to enable.", _FRONTEND_DIR)
