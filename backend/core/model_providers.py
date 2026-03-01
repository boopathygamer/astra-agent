"""
Multi-Model Provider System — Universal LLM Backend.
─────────────────────────────────────────────────────
Supports any OpenAI-compatible API endpoint.
Features:
  - Universal configuration via LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
  - Streaming support
  - Health checks + error handling
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class ProviderType(Enum):
    """Supported LLM provider types."""
    UNIVERSAL = "universal"
    AUTO = "auto"


@dataclass
class ProviderStatus:
    """Health/status of a provider."""
    name: str
    available: bool = False
    model: str = ""
    latency_ms: float = 0.0
    error: str = ""
    last_check: float = 0.0


@dataclass
class GenerationResult:
    """Standard result from any provider."""
    text: str = ""
    provider: str = ""
    model: str = ""
    tokens_used: int = 0
    latency_ms: float = 0.0
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.error


# ──────────────────────────────────────────────
# Abstract Base Provider
# ──────────────────────────────────────────────

class ModelProvider(ABC):
    """
    Base class for all LLM providers.
    Every provider must implement generate() and optionally stream().
    """

    def __init__(self, name: str, model: str = ""):
        self.name = name
        self.model = model
        self._call_count = 0
        self._total_latency = 0.0
        self._errors = 0

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: str = "",
        **kwargs,
    ) -> GenerationResult:
        """Generate a response from the model."""
        ...

    def stream(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: str = "",
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream a response token by token. Default: yield full result."""
        result = self.generate(prompt, max_tokens, temperature, system_prompt, **kwargs)
        if result.ok:
            yield result.text

    def health_check(self) -> ProviderStatus:
        """Check if this provider is available."""
        start = time.time()
        try:
            result = self.generate("Say 'ok'", max_tokens=5, temperature=0.0)
            latency = (time.time() - start) * 1000
            return ProviderStatus(
                name=self.name,
                available=result.ok,
                model=self.model,
                latency_ms=latency,
                error=result.error,
                last_check=time.time(),
            )
        except Exception as e:
            return ProviderStatus(
                name=self.name,
                available=False,
                error=str(e),
                last_check=time.time(),
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "provider": self.name,
            "model": self.model,
            "calls": self._call_count,
            "errors": self._errors,
            "avg_latency_ms": (
                self._total_latency / self._call_count
                if self._call_count > 0 else 0
            ),
        }

    def _track(self, latency_ms: float, error: bool = False):
        """Track call metrics."""
        self._call_count += 1
        self._total_latency += latency_ms
        if error:
            self._errors += 1


# ──────────────────────────────────────────────
# Auto-detect provider from API key pattern
# ──────────────────────────────────────────────

def detect_provider(api_key: str) -> Dict[str, str]:
    """
    Auto-detect provider config from API key format.
    Returns {"provider", "base_url", "model"}.
    """
    key = api_key.strip()

    if key.startswith("sk-ant-"):
        return {
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "model": "claude-3-5-sonnet-20241022",
        }
    elif key.startswith("AIzaSy"):
        return {
            "provider": "gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "model": "gemini-2.0-flash",
        }
    elif key.startswith("sk-"):
        return {
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
        }
    else:
        # Generic — assume OpenAI-compatible
        return {
            "provider": "generic",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
        }


# ──────────────────────────────────────────────
# 1. Universal Provider
# ──────────────────────────────────────────────

class UniversalProvider(ModelProvider):
    """Universal OpenAI-compatible API provider using httpx directly."""

    def __init__(self, api_key: str, base_url: str, model: str):
        super().__init__(name="universal", model=model)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._provider_hint = ""  # e.g. "gemini", "openai"
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            import httpx
            self._client = httpx.Client(timeout=120.0)
            # Auto-detect provider hint from key
            detected = detect_provider(self._api_key)
            self._provider_hint = detected["provider"]
            logger.info(
                f"✅ Universal provider initialized — "
                f"detected={self._provider_hint} url={self._base_url} model={self.model}"
            )
        except ImportError:
            logger.error("❌ httpx not installed. Run: pip install httpx")
            self._client = None
        except Exception as e:
            logger.error(f"❌ Universal init failed: {e}")
            self._client = None

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: str = "",
        **kwargs,
    ) -> GenerationResult:
        if not self._client:
            return GenerationResult(error="Universal client not initialized")

        start = time.time()
        max_retries = 3
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                import httpx
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                url = f"{self._base_url}/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                }
                payload: Dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                }

                # Provider-specific parameter handling
                if self._provider_hint == "gemini":
                    # Gemini rejects max_tokens, uses its own defaults
                    pass
                else:
                    payload["max_tokens"] = max_tokens

                response = self._client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                latency = (time.time() - start) * 1000
                text = data["choices"][0]["message"]["content"] or ""
                token_count = data.get("usage", {}).get("total_tokens", 0)

                self._track(latency)
                return GenerationResult(
                    text=text,
                    provider="universal",
                    model=self.model,
                    tokens_used=token_count,
                    latency_ms=latency,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited (429). Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    latency = (time.time() - start) * 1000
                    self._track(latency, error=True)
                    logger.error(f"Universal generate HTTP error: {e}")
                    return GenerationResult(error=str(e), provider="universal")
            except Exception as e:
                latency = (time.time() - start) * 1000
                self._track(latency, error=True)
                logger.error(f"Universal generate error: {e}")
                return GenerationResult(error=str(e), provider="universal")

    def stream(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: str = "",
        **kwargs,
    ) -> Generator[str, None, None]:
        if not self._client:
            return

        max_retries = 3
        base_delay = 2.0
        import httpx
        import json

        for attempt in range(max_retries):
            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                url = f"{self._base_url}/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                }
                payload: Dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True,
                }
                if self._provider_hint != "gemini":
                    payload["max_tokens"] = max_tokens

                with self._client.stream("POST", url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line.startswith("data: ") and line != "data: [DONE]":
                            try:
                                chunk = json.loads(line[6:])
                                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if delta:
                                    yield delta
                            except json.JSONDecodeError:
                                pass
                # If stream completes successfully, break out of retry loop
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited (429) in stream. Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Universal stream HTTP error: {e}")
                    break
            except Exception as e:
                logger.error(f"Universal stream error: {e}")
                break


# ──────────────────────────────────────────────
# Provider Registry
# ──────────────────────────────────────────────

class ProviderRegistry:
    """
    Central registry for the Universal LLM provider.
    """

    def __init__(self):
        self._providers: Dict[str, ModelProvider] = {}
        self._active: Optional[str] = None
        self._fallback_order: List[str] = []
        logger.info("ProviderRegistry initialized")

    def register(self, provider: ModelProvider) -> None:
        """Register a provider."""
        self._providers[provider.name] = provider
        if provider.name not in self._fallback_order:
            self._fallback_order.append(provider.name)
        logger.info(f"Registered provider: {provider.name} ({provider.model})")

    def set_active(self, name: str) -> bool:
        """Set the active provider by name."""
        if name in self._providers:
            self._active = name
            p = self._providers[name]
            logger.info(f"🔄 Active provider → {name} ({p.model})")
            return True
        logger.warning(f"Provider '{name}' not found")
        return False

    @property
    def active(self) -> Optional[ModelProvider]:
        """Get the currently active provider."""
        if self._active and self._active in self._providers:
            return self._providers[self._active]
        return None

    @property
    def active_name(self) -> str:
        """Get the name of the active provider."""
        return self._active or "none"

    def get(self, name: str) -> Optional[ModelProvider]:
        """Get a provider by name."""
        return self._providers.get(name)

    def list_providers(self) -> List[Dict[str, Any]]:
        """List all registered providers with status."""
        return [
            {
                "name": p.name,
                "model": p.model,
                "active": p.name == self._active,
                "calls": p._call_count,
                "errors": p._errors,
            }
            for p in self._providers.values()
        ]

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: str = "",
        **kwargs,
    ) -> GenerationResult:
        """
        Generate using active provider.
        """
        if self.active:
            result = self.active.generate(
                prompt, max_tokens, temperature, system_prompt, **kwargs
            )
            if result.ok:
                return result
            logger.warning(
                f"Active provider '{self._active}' failed: {result.error}."
            )
            return result

        return GenerationResult(
            error="No provider available.",
        )

    def generate_fn(self) -> Callable[[str], str]:
        """
        Return a simple generate function compatible with the existing system.
        """
        def _generate(prompt: str, **kwargs) -> str:
            result = self.generate(prompt, **kwargs)
            return result.text if result.ok else f"[Error: {result.error}]"
        return _generate

    @classmethod
    def auto_detect(
        cls,
        preferred: str = "auto",
        # Kept for backwards compatibility but ignored
        gemini_key: str = None,
        claude_key: str = None,
        openai_key: str = None,
    ) -> "ProviderRegistry":
        """
        Initialize the registry from the UniversalAPIConfig.
        """
        registry = cls()

        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
            
        from config.settings import provider_config
        
        # Determine credentials
        api_key = provider_config.api_key
        base_url = provider_config.base_url
        model = provider_config.model
        
        if api_key:
            registry.register(UniversalProvider(api_key=api_key, base_url=base_url, model=model))
            registry.set_active("universal")
        
        logger.info(
            f"🔍 Auto-detected providers: {['universal'] if registry.active else []}. "
            f"Active: {registry.active_name}"
        )

        return registry

    def status_display(self) -> str:
        """Formatted status for display in CLI/logs."""
        lines = ["╔══ Model Providers ══╗"]
        for p in self._providers.values():
            icon = "🟢" if p.name == self._active else "⚪"
            lines.append(f"  {icon} {p.name:<10} → {p.model}")
        lines.append(f"  Active: {self.active_name}")
        lines.append("╚═════════════════════╝")
        return "\n".join(lines)
