"""
SSE Streaming — Server-Sent Events for Real-Time Token Streaming
══════════════════════════════════════════════════════════════════
Provides a FastAPI endpoint that streams LLM responses token by token
using SSE format, so users see responses as they generate.

Usage:
    GET /api/stream?prompt=Hello&provider=openai
"""

import asyncio
import json
import logging
import time
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["streaming"])


async def _mock_token_stream(prompt: str) -> AsyncIterator[str]:
    """Mock token stream for development/testing."""
    words = f"Here is a response to your prompt about: {prompt}. ".split()
    words += "This system uses Server-Sent Events for real-time streaming. ".split()
    words += "Each token is sent as it's generated, providing instant feedback.".split()
    for word in words:
        yield word + " "
        await asyncio.sleep(0.05)  # Simulate model latency


async def _real_token_stream(prompt: str, provider_name: str = "openai") -> AsyncIterator[str]:
    """Stream tokens from a real LLM provider."""
    try:
        from providers.real_llm_client import create_providers_from_config, OpenAIProvider
        providers = create_providers_from_config()
        
        # Find requested provider
        provider = None
        for p in providers:
            if p.name == provider_name:
                provider = p
                break
        
        if not provider:
            yield f"Provider '{provider_name}' not available. "
            yield f"Available: {[p.name for p in providers]}"
            return
        
        if isinstance(provider, OpenAIProvider):
            async for token in provider.stream(prompt):
                yield token
        else:
            # Non-streaming fallback
            response = await provider.generate(prompt)
            if response.is_success:
                # Simulate streaming by chunking the response
                words = response.content.split()
                for i in range(0, len(words), 3):
                    yield " ".join(words[i:i+3]) + " "
                    await asyncio.sleep(0.02)
            else:
                yield f"[Error: {response.error}]"
    except Exception as e:
        yield f"[Error: {e}]"


@router.get("/stream")
async def stream_response(
    prompt: str = Query(..., description="The prompt to send to the LLM"),
    provider: str = Query("auto", description="LLM provider to use"),
    mock: bool = Query(False, description="Use mock streaming for testing"),
):
    """
    Stream LLM response as Server-Sent Events.
    
    Each event contains a token chunk. The final event has type 'done'.
    """
    async def event_generator():
        start = time.time()
        token_count = 0
        
        # Send start event
        yield f"event: start\ndata: {json.dumps({'provider': provider, 'timestamp': start})}\n\n"
        
        # Choose stream source
        if mock:
            stream = _mock_token_stream(prompt)
        else:
            stream = _real_token_stream(prompt, provider)
        
        async for token in stream:
            token_count += 1
            data = json.dumps({"token": token, "index": token_count})
            yield f"event: token\ndata: {data}\n\n"
        
        # Send done event
        duration_ms = (time.time() - start) * 1000
        done_data = json.dumps({
            "tokens": token_count,
            "duration_ms": round(duration_ms, 1),
            "provider": provider,
        })
        yield f"event: done\ndata: {done_data}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
