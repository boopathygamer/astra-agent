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

import hmac
import logging
import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks, Cookie, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

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
        "http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]


# ──────────────────────────────────────────────
# Security: Rate Limiter
# ──────────────────────────────────────────────

class _RateLimitStore:
    """In-memory sliding-window rate limiter per client IP with memory cap."""

    _MAX_TRACKED_IPS = 10_000  # Prevent memory exhaustion from IP spoofing

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window

        # Memory safety: evict oldest IPs if store grows too large
        if len(self._hits) > self._MAX_TRACKED_IPS:
            oldest_ips = sorted(self._hits, key=lambda ip: self._hits[ip][-1] if self._hits[ip] else 0)
            for ip in oldest_ips[:len(self._hits) - self._MAX_TRACKED_IPS]:
                del self._hits[ip]

        # Prune old entries for this IP
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
    """Dependency: validate API key if one is configured (timing-safe)."""
    if not _API_KEY:
        return  # Auth disabled in dev mode
    
    provided_key = request.headers.get("X-API-Key", "")
    # Use hmac.compare_digest to prevent timing-based side-channel attacks
    if not hmac.compare_digest(provided_key, _API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )


# ──────────────────────────────────────────────
# Middleware: Security Headers + Rate Limiting + Request ID
# ──────────────────────────────────────────────

class SecurityMiddleware(BaseHTTPMiddleware):
    """Adds security headers, rate limiting, and request tracking."""

    async def dispatch(self, request: Request, call_next):
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


# ──────────────────────────────────────────────
# Lifespan (replaces deprecated @app.on_event)
# ──────────────────────────────────────────────

class AppState:
    model = None
    tokenizer = None
    engine = None
    vision_pipeline = None
    agent_controller = None
    predictive_cache = None
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
        
        # Get registry from main module's app state (replaces builtins hack)
        registry = None
        try:
            from main import _app_state
            registry = _app_state.get("registry")
        except ImportError:
            pass

        if not registry:
            from core.model_providers import ProviderRegistry
            registry = ProviderRegistry.auto_detect()
            logger.info("Auto-detected Provider Registry in server process.")

        if registry and registry.active:
            try:
                generate_fn = registry.generate_fn()
                state.agent_controller = AgentController(generate_fn=generate_fn)
                logger.info("✅ Agent controller ready (Active Provider)")
                
                # ── Init PreCognitive Cache ──
                from brain.predictive_cache import PreCognitiveCache
                state.predictive_cache = PreCognitiveCache(generate_fn=generate_fn)
                state.predictive_cache.start()
                logger.info("⚡ PreCognitive Shadow Execution Engine activated.")
                
            except Exception as e:
                logger.error(f"⚠️ Failed to create AgentController with registry: {e}")
        else:
            logger.warning("⚠️ No active LLM Provider found. Using Mock Generator for UI Testing.")
            def mock_generate(prompt: str, **kwargs) -> str:
                import time
                time.sleep(0.5)
                if "TaskSpec" in prompt or "extract" in prompt.lower() or "JSON" in prompt:
                    return '{"action_type": "general", "tools_needed": [], "goal": "Demonstrate the UI", "requires_sandbox": false}'
                if "Reasoning chain" in prompt or "hypothesis" in prompt.lower():
                    return "Hypothesis: By mocking the generator, we can validate the React UI logic."
                if "Verify" in prompt or "verification" in prompt.lower():
                    return '{"passed": true, "confidence": 0.95, "v_static": 1.0, "v_property": 1.0, "v_scenario": 1.0, "v_critic": 1.0, "v_code": 1.0, "v_security": 1.0, "critic_details": "Looks good."}'
                return "This is a simulated response. Processing complete! Fibonacci: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34."
            
            try:
                state.agent_controller = AgentController(generate_fn=mock_generate)
                logger.info("✅ Agent controller ready (Mock Provider)")
            except Exception as e:
                logger.error(f"⚠️ Failed to create AgentController with mock: {e}")

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
    
    if state.predictive_cache:
        state.predictive_cache.stop()
    
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

# Security middleware (must be added before CORS)
app.add_middleware(SecurityMiddleware)

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

try:
    from api.routes.neural_uplink import router as neural_router
    app.include_router(neural_router)
except ImportError as e:
    logger.error(f"Failed to mount Neural Uplink router: {e}")

# ──────────────────────────────────────────────
# Provider Configuration Endpoints
# ──────────────────────────────────────────────

@app.post("/providers/configure")
async def configure_providers(request: dict):
    """
    Configure up to 5 API keys for the LLM Council.
    If 2+ keys are valid, council mode activates automatically.

    Body: {
        "claude_api_key": "sk-ant-...",
        "gemini_api_key": "AIza...",
        "openai_api_key": "sk-...",
        "grok_api_key": "xai-...",
        "openrouter_api_key": "sk-or-..."
    }
    """
    from config.settings import provider_config
    from core.model_providers import ProviderRegistry

    # Update config with provided keys
    key_map = {
        "claude_api_key": "claude_api_key",
        "gemini_api_key": "gemini_api_key",
        "openai_api_key": "openai_api_key",
        "grok_api_key": "grok_api_key",
        "openrouter_api_key": "openrouter_api_key",
    }
    # Optional model overrides
    model_map = {
        "openrouter_model": "openrouter_model",
    }

    updated = []
    for req_key, config_attr in key_map.items():
        value = request.get(req_key, "").strip()
        if value:
            setattr(provider_config, config_attr, value)
            updated.append(req_key.replace("_api_key", ""))
    # Apply model overrides
    for req_key, config_attr in model_map.items():
        value = request.get(req_key, "").strip()
        if value:
            setattr(provider_config, config_attr, value)

    if not updated:
        return JSONResponse(
            status_code=400,
            content={"error": "No API keys provided. Supply at least one key."},
        )

    # Reinitialize the provider registry with new keys
    try:
        registry = ProviderRegistry.auto_detect()

        # Update the main app state
        from main import _app_state
        _app_state["registry"] = registry

        # Reinitialize the agent controller with new generate function
        if registry.active or registry.is_council_mode:
            from agents.controller import AgentController
            generate_fn = registry.generate_fn()
            state.agent_controller = AgentController(generate_fn=generate_fn)

        return {
            "status": "configured",
            "providers_updated": updated,
            "active_providers": [p["name"] for p in registry.list_providers()],
            "council_mode": registry.is_council_mode,
            "council_size": registry.council.size if registry.council else 0,
            "active_provider": registry.active_name,
        }
    except Exception as e:
        logger.error(f"Provider configuration failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Configuration failed: {str(e)}"},
        )


@app.get("/providers/status")
async def provider_status():
    """
    Get status of all configured providers and council mode.
    """
    try:
        from main import _app_state
        registry = _app_state.get("registry")

        if not registry:
            return {
                "status": "not_initialized",
                "providers": [],
                "council_mode": False,
            }

        providers_info = registry.list_providers()
        # Enrich with model names from config for frontend display
        from config.settings import provider_config
        model_lookup = {d.name: d.model for d in provider_config.configured_providers()}
        for p in providers_info:
            p["model"] = model_lookup.get(p.get("name", ""), p.get("model", ""))
        council_stats = None
        if registry.council:
            council_stats = registry.council.get_stats()

        return {
            "status": "ready",
            "providers": providers_info,
            "active_provider": registry.active_name,
            "council_mode": registry.is_council_mode,
            "council_stats": council_stats,
        }
    except Exception as e:
        logger.error(f"Provider status error: {e}")
        return {"status": "error", "error": str(e)}


@app.post("/council/query", dependencies=[Depends(verify_api_key)])
async def council_query(request: dict):
    """
    Directly query the LLM Council for debugging/testing.
    Returns all responses, rankings, and the selected best.

    Body: {"prompt": "Explain quantum computing", "system_prompt": "Be concise"}
    """
    prompt = request.get("prompt", "").strip()
    system_prompt = request.get("system_prompt", "")

    if not prompt:
        raise HTTPException(400, "prompt is required")
    if len(prompt) > 50_000:
        raise HTTPException(400, "Prompt too long (max 50,000 characters)")

    try:
        from main import _app_state
        registry = _app_state.get("registry")

        if not registry:
            raise HTTPException(503, "Provider registry not initialized")

        if not registry.council:
            raise HTTPException(400, "Council mode not active. Configure 2+ API keys.")

        result = registry.council.query(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        return {
            "best_response": result.best_response,
            "best_provider": result.best_provider,
            "best_model": result.best_model,
            "best_score": result.best_score,
            "council_size": result.council_size,
            "mode": result.mode,
            "total_latency_ms": round(result.total_latency_ms, 1),
            "all_ranked": [
                {
                    "rank": r.rank,
                    "provider": r.provider_name,
                    "model": r.model,
                    "score": r.aggregate_score,
                    "latency_ms": round(r.latency_ms, 1),
                    "text_preview": r.text[:500] if r.text else "",
                }
                for r in result.all_ranked
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Council query error: {e}", exc_info=True)
        raise HTTPException(500, "Council query failed")




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
    """Conversational chat with memory, self-thinking, and intelligent routing."""
    if not state.is_ready:
        raise HTTPException(503, "System not ready")

    # Input validation
    if not request.message or not request.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    if len(request.message) > 50_000:
        raise HTTPException(400, "Message too long (max 50,000 characters)")

    start = time.time()

    # ── INTELLIGENT INTENT ROUTING ──
    # Classify the query to see if a specialized system should handle it
    try:
        from brain.intent_router import get_intent_router
        router = get_intent_router()
        routing = router.classify(request.message)
    except Exception as e:
        logger.warning(f"Intent router error: {e}")
        routing = None

    routing_meta = {}
    if routing and routing.target_system != "chat":
        routing_meta = {
            "routed_to": routing.target_system,
            "routing_confidence": routing.confidence,
            "routing_display": routing.display_name,
            "routing_emoji": routing.display_emoji,
        }
        logger.info(f"Chat routed to: {routing.target_system} (conf={routing.confidence:.2f})")

        # Dispatch to specialized systems
        try:
            routed_answer = _dispatch_to_system(routing.target_system, request.message)
            if routed_answer is not None:
                return ChatResponse(
                    answer=routed_answer,
                    confidence=routing.confidence,
                    mode=f"routed:{routing.target_system}",
                    duration_ms=(time.time() - start) * 1000,
                    **routing_meta,
                )
        except Exception as e:
            logger.warning(f"Specialized routing failed ({routing.target_system}): {e}, falling back to chat")

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
                **routing_meta,
            )
        else:
            answer = state.agent_controller.chat(request.message)
            return ChatResponse(
                answer=answer,
                confidence=0.8,
                duration_ms=(time.time() - start) * 1000,
                **routing_meta,
            )

    except Exception as e:
        logger.error(f"Chat error: {type(e).__name__}", exc_info=True)
        raise HTTPException(500, "Generation failed. Please try again.")


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
# AirLLM Deep Thought Endpoint (auth required)
# ──────────────────────────────────────────────
from pydantic import BaseModel as _PydanticBaseModel

class AirLLMRequest(_PydanticBaseModel):
    prompt: str
    max_tokens: int = 512

@app.post("/airllm/generate", dependencies=[Depends(verify_api_key)])
async def airllm_generate(request: AirLLMRequest):
    """Generate a highly complex response using the VRAM-swapping AirLLM engine."""
    from brain.airllm_engine import deep_thought_engine
    if not request.prompt or not request.prompt.strip():
        raise HTTPException(400, "Prompt cannot be empty")
        
    try:
        response = deep_thought_engine.generate(request.prompt, max_new_tokens=request.max_tokens)
        return {"answer": response, "engine": "AirLLM (Deep Thought)"}
    except Exception as e:
        logger.error(f"AirLLM Generation failed: {e}")
        raise HTTPException(500, f"AirLLM Engine Failure: {str(e)}")

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
    
    if not request.message or not request.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    from fastapi.responses import StreamingResponse
    from core.streaming import StreamProcessor, StreamConfig

    processor = StreamProcessor(StreamConfig(
        chunk_size=50,
        break_on="sentence",
    ))

    def event_stream():
        try:
            answer = state.agent_controller.chat(request.message)

            chunk_size = processor.config.chunk_size if hasattr(processor, 'config') else 50
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                events = processor.process_token(chunk)
                for evt in events:
                    yield evt.to_sse()

            for evt in processor.finish():
                yield evt.to_sse()

        except Exception as e:
            import json
            logger.error(f"Stream error: {type(e).__name__}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'data': 'Streaming failed'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
        from agents.profiles.ultimate_tutor import UltimateTutorEngine
        state._tutor = UltimateTutorEngine(
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
# Multi-Agent Orchestrator Endpoints
# ──────────────────────────────────────────────

@app.post("/orchestrate/debate", dependencies=[Depends(verify_api_key)])
async def orchestrate_debate(request: dict):
    """
    Run a Multi-Agent Debate on a topic.
    
    Uses 3-stage flow: Expert Draft → Critic Review → Final Synthesis.
    
    Body: {"topic": "microservices vs monolith", "strategy": "debate"}
    """
    if not state.agent_controller:
        raise HTTPException(503, "Agent not initialized")
    
    topic = request.get("topic", "").strip()
    if not topic:
        raise HTTPException(400, "Topic is required")
    if len(topic) > 5000:
        raise HTTPException(400, "Topic too long (max 5000 chars)")
    
    strategy = request.get("strategy", "debate").strip().lower()
    
    try:
        import time as _time
        start = _time.time()
        
        if strategy == "debate":
            from agents.profiles.multi_agent_orchestrator import MultiAgentOrchestrator
            orchestrator = MultiAgentOrchestrator(state.agent_controller)
            result = orchestrator.orchestrate_debate(topic)
            
            return {
                "strategy": "debate",
                "topic": topic,
                "answer": result.answer,
                "confidence": result.confidence,
                "mode": result.mode,
                "error": result.error,
                "duration_ms": (_time.time() - start) * 1000,
            }
        else:
            # Use the full AgentOrchestrator for other strategies
            from agents.orchestrator import AgentOrchestrator, OrchestratorStrategy
            try:
                strat_enum = OrchestratorStrategy(strategy)
            except ValueError:
                strat_enum = OrchestratorStrategy.AUTO
            
            orch = AgentOrchestrator(generate_fn=state.agent_controller.generate_fn)
            result = orch.execute(topic, strategy=strat_enum)
            
            return {
                "strategy": strategy,
                "topic": topic,
                "answer": result.final_output,
                "confidence": result.confidence,
                "sub_tasks": len(result.sub_results),
                "duration_ms": result.total_duration_ms,
                "summary": result.summary(),
                "error": result.error,
            }
    except Exception as e:
        logger.error(f"Orchestrate error: {type(e).__name__}", exc_info=True)
        raise HTTPException(500, f"Orchestration failed: {str(e)}")


@app.get("/orchestrate/status", dependencies=[Depends(verify_api_key)])
async def orchestrate_status():
    """Get orchestrator capabilities and routing stats."""
    strategies = ["debate", "swarm", "pipeline", "hierarchy", "auto"]
    
    routing_stats = {}
    try:
        from brain.intent_router import get_intent_router
        routing_stats = get_intent_router().get_stats()
    except Exception:
        pass
    
    return {
        "available_strategies": strategies,
        "agent_initialized": state.agent_controller is not None,
        "routing_stats": routing_stats,
    }


# ──────────────────────────────────────────────
# Intelligent Query Dispatch (used by /chat)
# ──────────────────────────────────────────────

def _dispatch_to_system(target: str, message: str) -> str:
    """
    Dispatch a chat message to a specialized backend system.
    Returns the answer string, or None to fall back to normal chat.
    """
    if not state.agent_controller:
        return None

    if target == "orchestrator":
        from agents.profiles.multi_agent_orchestrator import MultiAgentOrchestrator
        orch = MultiAgentOrchestrator(state.agent_controller)
        result = orch.orchestrate_debate(message)
        return result.answer if not result.error else None

    if target == "threat_scanner":
        # Threat scanning through chat is handled by the agent's tools
        return None

    if target == "deep_researcher":
        from agents.profiles.deep_researcher import DeepWebResearcher
        researcher = DeepWebResearcher(state.agent_controller)
        result = researcher.compile_dossier(message)
        return result.answer if hasattr(result, 'answer') and not getattr(result, 'error', None) else None

    if target == "devops_reviewer":
        # DevOps needs a repo path — let the agent handle it naturally
        return None

    if target == "contract_hunter":
        # Contract hunter needs a file — let agent handle it
        return None

    if target == "archivist":
        # Archivist needs a directory — let agent handle it
        return None

    if target == "transpiler":
        # Transpiler needs file paths — let agent handle it
        return None

    if target == "evolution":
        from brain.evolution import CodeEvolutionEngine
        from main import _app_state
        registry = _app_state.get("registry")
        if registry:
            engine = CodeEvolutionEngine(registry)
            test_cases = "if __name__ == '__main__':\n    pass"
            best = engine.evolve(message, test_cases, generations=2)
            if best:
                return f"# 🧬 Code Evolution Result\n\n```python\n{best.code}\n```"
        return None

    if target == "devils_advocate":
        from agents.profiles.devils_advocate import DevilsAdvocate
        board = DevilsAdvocate(state.agent_controller)
        result = board.audit_business_plan_text(message) if hasattr(board, 'audit_business_plan_text') else None
        if result and hasattr(result, 'answer'):
            return result.answer
        return None

    if target == "swarm":
        from agents.profiles.swarm_intelligence import SwarmOrchestrator
        swarm = SwarmOrchestrator(
            generate_fn=state.agent_controller.generate_fn,
            agent_controller=state.agent_controller,
        )
        result = swarm.api_execute(message)
        return result.get("final_output") or result.get("answer") if isinstance(result, dict) else None

    # For any unhandled targets, fall back to normal chat
    return None



# ──────────────────────────────────────────────
# MCP (Model Context Protocol) Endpoints
# ──────────────────────────────────────────────

@app.get("/mcp/config", dependencies=[Depends(verify_api_key)])
async def mcp_config(client: str = "claude"):
    """
    Generate ready-to-use MCP config JSON for a specific client.

    Query: ?client=claude | cursor | vscode
    """
    import os
    from pathlib import Path

    project_root = str(Path(__file__).parent.parent.resolve()).replace("\\", "\\\\")
    python_cmd = "python"

    mcp_tools = [
        "chat", "agent_task", "think", "quick_think", "analyze_code",
        "execute_code", "search_web", "scan_threats", "analyze_file",
        "memory_recall", "memory_store", "tutor_start", "tutor_respond",
        "swarm_execute", "forge_tool", "transpile_code", "orchestrate_debate",
        "evolve_code",
    ]

    base_config = {
        "command": python_cmd,
        "args": ["-m", "mcp_server"],
        "cwd": project_root,
        "env": {"LLM_PROVIDER": "auto"},
    }

    if client == "cursor":
        return {
            "mcpServers": {
                "astra-agent": base_config
            }
        }
    elif client == "vscode":
        return {
            "mcp": {
                "servers": {
                    "astra-agent": {
                        "type": "stdio",
                        **base_config,
                    }
                }
            }
        }
    else:
        # Claude Desktop (default)
        return {
            "mcpServers": {
                "astra-agent": base_config
            }
        }


@app.get("/mcp/status", dependencies=[Depends(verify_api_key)])
async def mcp_status():
    """Get MCP server info and available tools."""
    from pathlib import Path

    project_root = str(Path(__file__).parent.parent.resolve())

    mcp_tools = [
        {"name": "chat", "description": "Conversational AI with full agent pipeline"},
        {"name": "agent_task", "description": "Complex task solving with tool orchestration"},
        {"name": "think", "description": "Multi-iteration Synthesize → Verify → Learn loop"},
        {"name": "quick_think", "description": "Fast single-pass reasoning"},
        {"name": "analyze_code", "description": "Deep static analysis with 15 vulnerability detectors"},
        {"name": "execute_code", "description": "Sandboxed code execution (Python, JS, Bash)"},
        {"name": "search_web", "description": "Internet search via DuckDuckGo"},
        {"name": "scan_threats", "description": "4-layer threat detection for files and directories"},
        {"name": "analyze_file", "description": "Multimodal file analysis (PDF, image, audio)"},
        {"name": "memory_recall", "description": "Query episodic long-term memory"},
        {"name": "memory_store", "description": "Store episodes in long-term memory"},
        {"name": "tutor_start", "description": "Start a Socratic tutoring session"},
        {"name": "tutor_respond", "description": "Continue a tutoring conversation"},
        {"name": "swarm_execute", "description": "Multi-agent swarm intelligence"},
        {"name": "forge_tool", "description": "Create new tools at runtime"},
        {"name": "transpile_code", "description": "Translate code between languages"},
        {"name": "orchestrate_debate", "description": "Multi-agent debate pipeline"},
        {"name": "evolve_code", "description": "RLHF-based code optimization"},
    ]

    return {
        "project_root": project_root,
        "transports": ["stdio", "http"],
        "stdio_command": f"python -m mcp_server",
        "http_command": f"python -m mcp_server --transport http --port 8080",
        "http_url": "http://localhost:8080/mcp",
        "tools_count": len(mcp_tools),
        "tools": mcp_tools,
        "agent_initialized": state.agent_controller is not None,
    }


# ──────────────────────────────────────────────
# Security Scanner Endpoints (Core Agent)
# ──────────────────────────────────────────────

def _get_scanner():
    """Get the ThreatScanner from the agent controller or create one."""
    if state.agent_controller and hasattr(state.agent_controller, 'threat_scanner'):
        return state.agent_controller.threat_scanner
    from agents.safety.threat_scanner import ThreatScanner
    return ThreatScanner()


@app.post("/scan/file", dependencies=[Depends(verify_api_key)])
async def scan_file(request: dict):
    """
    Deep scan a single file for viruses, malware, trojans, etc.

    Body: {"file_path": "C:/Users/user/Downloads/suspicious.exe"}
    """
    file_path = request.get("file_path", "").strip()
    if not file_path:
        raise HTTPException(400, "file_path is required")

    import os
    if not os.path.isfile(file_path):
        raise HTTPException(404, f"File not found: {file_path}")

    scanner = _get_scanner()
    report = scanner.scan_file(file_path)
    return report.to_dict()


@app.post("/scan/directory", dependencies=[Depends(verify_api_key)])
async def scan_directory(request: dict):
    """
    Deep scan all files in a directory for threats.

    Body: {"directory": "C:/Users/user/Downloads", "recursive": true, "max_files": 100}
    """
    directory = request.get("directory", "").strip()
    if not directory:
        raise HTTPException(400, "directory is required")

    import os
    from pathlib import Path
    if not os.path.isdir(directory):
        raise HTTPException(404, f"Directory not found: {directory}")

    recursive = request.get("recursive", True)
    max_files = min(request.get("max_files", 100), 500)
    scanner = _get_scanner()

    results = []
    threats_found = 0
    files_scanned = 0

    dir_path = Path(directory)
    pattern = "**/*" if recursive else "*"

    for file_path in dir_path.glob(pattern):
        if not file_path.is_file():
            continue
        if files_scanned >= max_files:
            break

        try:
            report = scanner.scan_file(str(file_path))
            files_scanned += 1
            entry = {
                "file": str(file_path),
                "is_threat": report.is_threat,
                "threat_type": report.threat_type.value if report.threat_type else None,
                "severity": report.severity.value if report.severity else None,
                "confidence": report.confidence,
                "recommended_action": report.recommended_action.value if report.recommended_action else "allow",
                "summary": report.summary(),
            }
            results.append(entry)
            if report.is_threat:
                threats_found += 1
        except Exception as e:
            results.append({
                "file": str(file_path),
                "is_threat": False,
                "error": str(e),
            })
            files_scanned += 1

    return {
        "directory": directory,
        "files_scanned": files_scanned,
        "threats_found": threats_found,
        "results": results,
    }


@app.post("/scan/url", dependencies=[Depends(verify_api_key)])
async def scan_url(request: dict):
    """
    Scan a URL for phishing, malicious domains, and reputation.

    Body: {"url": "https://suspicious-site.com"}
    """
    url = request.get("url", "").strip()
    if not url:
        raise HTTPException(400, "url is required")

    scanner = _get_scanner()
    report = scanner.scan_url(url)
    return report.to_dict()


@app.get("/scan/stats", dependencies=[Depends(verify_api_key)])
async def scan_stats():
    """Get scanner statistics — total scans, threats found, quarantined files."""
    scanner = _get_scanner()
    return scanner.stats()


@app.get("/scan/history", dependencies=[Depends(verify_api_key)])
async def scan_history():
    """Get the scan history from this session."""
    scanner = _get_scanner()
    history = scanner.get_scan_history()
    return {"scans": [r.to_dict() for r in history]}


@app.get("/scan/quarantine", dependencies=[Depends(verify_api_key)])
async def scan_quarantine_list():
    """List all quarantined files."""
    scanner = _get_scanner()
    return {"quarantined": scanner.get_quarantine_list()}


@app.post("/scan/quarantine", dependencies=[Depends(verify_api_key)])
async def scan_quarantine_file(request: dict):
    """
    Quarantine a threat — move to secure vault.

    Body: {"file_path": "C:/path/to/threat.exe"}
    """
    file_path = request.get("file_path", "").strip()
    if not file_path:
        raise HTTPException(400, "file_path is required")

    import os
    if not os.path.isfile(file_path):
        raise HTTPException(404, f"File not found: {file_path}")

    scanner = _get_scanner()
    report = scanner.scan_file(file_path)
    if not report.is_threat:
        return {"status": "clean", "message": "File is not a threat, quarantine skipped."}

    result = scanner.quarantine(report)
    return result


@app.post("/scan/destroy", dependencies=[Depends(verify_api_key)])
async def scan_destroy_threat(request: dict):
    """
    Securely destroy a threat with 3-pass overwrite + cryptographic proof.

    Body: {"file_path": "C:/path/to/threat.exe"}
    """
    file_path = request.get("file_path", "").strip()
    if not file_path:
        raise HTTPException(400, "file_path is required")

    import os
    if not os.path.isfile(file_path):
        raise HTTPException(404, f"File not found: {file_path}")

    scanner = _get_scanner()
    report = scanner.scan_file(file_path)
    if not report.is_threat:
        return {"status": "clean", "message": "File is not a threat, destruction skipped."}

    result = scanner.destroy(report)
    return result


# ──────────────────────────────────────────────
# Dev Studio Endpoints
# ──────────────────────────────────────────────

_STRONG_MODELS = {
    "gpt-4", "gpt-4o", "gpt-4-turbo", "gpt-4o-mini",
    "claude-3-opus", "claude-3-sonnet", "claude-3-haiku", "claude-3.5-sonnet", "claude-4",
    "gemini-pro", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash",
    "grok-2", "grok-3",
    "deepseek-coder-v2", "codestral", "qwen-2.5-coder-32b",
}


@app.post("/dev/validate-model")
async def dev_validate_model():
    """Check if the active LLM provider is capable of full-stack generation."""
    try:
        from config.settings import settings as _settings
        active_model = getattr(_settings, "active_model", None) or "unknown"
        active_provider = getattr(_settings, "active_provider", None) or "unknown"

        has_any_key = any([
            os.getenv("GEMINI_API_KEY"),
            os.getenv("CLAUDE_API_KEY"),
            os.getenv("OPENAI_API_KEY"),
            os.getenv("GROK_API_KEY"),
            os.getenv("OPENROUTER_API_KEY"),
        ])

        if not has_any_key:
            return {
                "eligible": False,
                "model": "none",
                "reason": "No API keys configured. Add at least one provider key in .env to enable AI-powered code generation.",
                "capabilities": [],
            }

        model_lower = active_model.lower()
        is_strong = any(m in model_lower for m in _STRONG_MODELS)

        capabilities = []
        if is_strong:
            capabilities = ["full-stack HTML/CSS/JS", "responsive design", "complex logic", "multi-page apps", "API integration"]
        else:
            capabilities = ["basic HTML generation", "simple components"]

        return {
            "eligible": is_strong or has_any_key,
            "model": active_model,
            "reason": (
                f"{active_model} via {active_provider} is fully capable of generating production-quality full-stack applications."
                if is_strong
                else f"{active_model} is configured. Code generation quality depends on model capability."
            ),
            "capabilities": capabilities,
        }
    except Exception:
        return {
            "eligible": True,
            "model": "auto",
            "reason": "Provider auto-detection active. Code generation available.",
            "capabilities": ["HTML/CSS/JS generation"],
        }


class _GitHubPushRequest(_PydanticBaseModel):
    repo_url: str
    token: str
    files: list
    commit_message: str = "feat: generated by ASTRA Builder"


@app.post("/dev/github-push")
async def dev_github_push(request: _GitHubPushRequest):
    """Push generated files to a GitHub repository."""
    import base64 as _b64

    try:
        import httpx
    except ImportError:
        raise HTTPException(500, "httpx not installed. Run: pip install httpx")

    # Parse owner/repo from URL
    url = request.repo_url.strip().rstrip("/").rstrip(".git")
    parts = url.replace("https://github.com/", "").replace("http://github.com/", "").split("/")
    if len(parts) < 2:
        raise HTTPException(400, "Invalid repo URL. Format: https://github.com/owner/repo")
    owner, repo = parts[0], parts[1]

    headers = {
        "Authorization": f"Bearer {request.token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Get default branch + latest commit SHA
        repo_resp = await client.get(api_base, headers=headers)
        if repo_resp.status_code == 404:
            raise HTTPException(404, f"Repository {owner}/{repo} not found or token lacks access.")
        if repo_resp.status_code != 200:
            raise HTTPException(repo_resp.status_code, f"GitHub API error: {repo_resp.text}")
        default_branch = repo_resp.json().get("default_branch", "main")

        ref_resp = await client.get(f"{api_base}/git/ref/heads/{default_branch}", headers=headers)
        if ref_resp.status_code != 200:
            raise HTTPException(400, f"Could not get branch ref: {ref_resp.text}")
        base_sha = ref_resp.json()["object"]["sha"]

        # 2. Create blobs for each file
        tree_items = []
        for f in request.files:
            blob_resp = await client.post(f"{api_base}/git/blobs", headers=headers, json={
                "content": _b64.b64encode(f["content"].encode()).decode(),
                "encoding": "base64",
            })
            if blob_resp.status_code != 201:
                raise HTTPException(500, f"Failed to create blob for {f.get('path', '?')}: {blob_resp.text}")
            tree_items.append({
                "path": f.get("path", "index.html"),
                "mode": "100644",
                "type": "blob",
                "sha": blob_resp.json()["sha"],
            })

        # 3. Create tree
        tree_resp = await client.post(f"{api_base}/git/trees", headers=headers, json={
            "base_tree": base_sha,
            "tree": tree_items,
        })
        if tree_resp.status_code != 201:
            raise HTTPException(500, f"Failed to create tree: {tree_resp.text}")

        # 4. Create commit
        commit_resp = await client.post(f"{api_base}/git/commits", headers=headers, json={
            "message": request.commit_message,
            "tree": tree_resp.json()["sha"],
            "parents": [base_sha],
        })
        if commit_resp.status_code != 201:
            raise HTTPException(500, f"Failed to create commit: {commit_resp.text}")
        commit_sha = commit_resp.json()["sha"]

        # 5. Update ref
        ref_update = await client.patch(f"{api_base}/git/refs/heads/{default_branch}", headers=headers, json={
            "sha": commit_sha,
        })
        if ref_update.status_code != 200:
            raise HTTPException(500, f"Failed to update ref: {ref_update.text}")

    return {
        "success": True,
        "message": f"Pushed {len(request.files)} files to {owner}/{repo}@{default_branch}",
        "commit_sha": commit_sha,
    }


class _ApkBuildRequest(_PydanticBaseModel):
    html: str
    app_name: str = "AstraApp"
    package_name: str = "com.astra.app"


@app.post("/dev/build-apk")
async def dev_build_apk(request: _ApkBuildRequest):
    """Build an APK from generated HTML (returns HTML for wrapping via Capacitor)."""
    # In production, this would invoke Capacitor CLI to wrap the HTML.
    # For now, we return the HTML content for client-side download
    # with instructions for APK building.
    import base64 as _b64

    html_bytes = request.html.encode("utf-8")
    html_b64 = _b64.b64encode(html_bytes).decode()

    return {
        "success": True,
        "message": f"App '{request.app_name}' ({request.package_name}) packaged. "
                   f"For native APK, install Capacitor: npx cap init && npx cap add android && npx cap open android",
        "apk_base64": html_b64,
        "size_mb": round(len(html_bytes) / (1024 * 1024), 2),
    }
