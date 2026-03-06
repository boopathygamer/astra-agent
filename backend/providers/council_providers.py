"""
Council Provider Clients — 5 Named LLM Providers
══════════════════════════════════════════════════
Concrete provider implementations for the LLM Council system.
All use the OpenAI-compatible Python SDK pointed at each provider's base URL.

Providers:
  1. Claude (Anthropic)   — claude-sonnet-4-20250514
  2. Gemini (Google)      — gemini-2.5-pro-preview-05-06
  3. OpenAI               — gpt-4o
  4. Grok (xAI)           — grok-3
  5. OpenRouter            — meta-llama/llama-4-maverick
"""

import logging
import time
from typing import Generator

from core.model_providers import ModelProvider, GenerationResult

logger = logging.getLogger(__name__)


class CouncilProvider(ModelProvider):
    """
    A named LLM provider for the council system.
    Uses the `openai` SDK pointed at any OpenAI-compatible base URL.
    """

    def __init__(self, name: str, api_key: str, base_url: str, model: str):
        super().__init__(name=name, model=model)
        self._api_key = api_key
        self._base_url = base_url
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            import openai
            extra_kwargs: dict = {}
            # OpenRouter requires HTTP-Referer & X-Title for proper attribution
            if self.name == "openrouter":
                extra_kwargs["default_headers"] = {
                    "HTTP-Referer": "https://astra-agent.dev",
                    "X-Title": "Astra Agent",
                }
            self._client = openai.OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                **extra_kwargs,
            )
            logger.info(
                f"✅ Council provider [{self.name}] initialized "
                f"— url={self._base_url} model={self.model}"
            )
        except ImportError:
            logger.error("❌ openai not installed. Run: pip install openai")
            self._client = None
        except Exception as e:
            logger.error(f"❌ [{self.name}] init failed: {e}")
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
            return GenerationResult(
                error=f"[{self.name}] client not initialized",
                provider=self.name,
            )

        start = time.time()
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            latency = (time.time() - start) * 1000
            text = response.choices[0].message.content or ""
            token_count = response.usage.total_tokens if response.usage else 0

            self._track(latency)
            return GenerationResult(
                text=text,
                provider=self.name,
                model=self.model,
                tokens_used=token_count,
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            self._track(latency, error=True)
            logger.error(f"[{self.name}] generate error: {e}")
            return GenerationResult(error=str(e), provider=self.name)

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

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"[{self.name}] stream error: {e}")


# ──────────────────────────────────────────────
# Factory: Create providers from config
# ──────────────────────────────────────────────

def create_council_providers() -> list:
    """
    Read MultiProviderConfig and instantiate a CouncilProvider
    for each slot that has an API key configured.
    Returns a list of CouncilProvider instances.
    """
    from config.settings import provider_config

    providers = []
    for desc in provider_config.configured_providers():
        try:
            p = CouncilProvider(
                name=desc.name,
                api_key=desc.api_key,
                base_url=desc.base_url,
                model=desc.model,
            )
            providers.append(p)
        except Exception as e:
            logger.error(f"Failed to create provider [{desc.name}]: {e}")

    # Legacy fallback: if no named keys but LLM_API_KEY is set
    if not providers and provider_config.llm_api_key:
        providers.append(CouncilProvider(
            name="universal",
            api_key=provider_config.llm_api_key,
            base_url=provider_config.llm_base_url,
            model=provider_config.llm_model,
        ))

    logger.info(
        f"🏛️ Council providers created: "
        f"{[p.name for p in providers]} ({len(providers)} total)"
    )
    return providers
