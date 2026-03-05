"""
Real LLM Client — Production HTTP Clients for Universal APIs
══════════════════════════════════════════════════════════════════════
Universal HTTP client using httpx. Allows connecting to any OpenAI-compatible API.
Uses configuration from settings.py.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    logger.warning("httpx not installed. Real LLM clients will not work. Run: pip install httpx")


@dataclass
class LLMResponse:
    """Response from a real LLM API."""
    provider: str
    content: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    is_success: bool = True
    error: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


class RealLLMProvider:
    """Base class for real LLM API providers."""
    
    def __init__(self, api_key: str, model: str, base_url: str, name: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.name = name
        self._client: Optional[Any] = None
    
    def _get_client(self):
        if not HAS_HTTPX:
            raise RuntimeError("httpx is required. Install with: pip install httpx")
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class UniversalLLMClient(RealLLMProvider):
    """Real Universal API client (OpenAI-compatible)"""
    
    def __init__(self, api_key: str, model: str, base_url: str):
        super().__init__(
            api_key=api_key or "sk-no-key",
            model=model,
            base_url=base_url,
            name="universal",
        )
    
    async def generate(self, prompt: str, max_tokens: int = 4096, temperature: float = 0.7) -> LLMResponse:
        start = time.time()
        try:
            client = self._get_client()
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            usage = data.get("usage", {})
            return LLMResponse(
                provider=self.name,
                content=data["choices"][0]["message"]["content"],
                model=data.get("model", self.model),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                latency_ms=(time.time() - start) * 1000,
                raw_response=data,
            )
        except Exception as e:
            return LLMResponse(
                provider=self.name, content="", is_success=False,
                error=str(e), latency_ms=(time.time() - start) * 1000,
            )
    
    async def stream(self, prompt: str, max_tokens: int = 4096) -> AsyncIterator[str]:
        """Stream tokens from the universal API."""
        try:
            client = self._get_client()
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError):
                            continue
        except Exception as e:
            yield f"[Error: {e}]"


def create_providers_from_config() -> List[RealLLMProvider]:
    """Create real providers from settings configuration."""
    from config.settings import provider_config
    
    providers = []
    if provider_config.is_configured:
        providers.append(UniversalLLMClient(
            api_key=provider_config.api_key,
            model=provider_config.model,
            base_url=provider_config.base_url,
        ))
    return providers
