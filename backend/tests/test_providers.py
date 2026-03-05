"""
Multi-Provider & LLM Council — Test Suite
══════════════════════════════════════════
Tests for the 5-provider config, council providers, LLM council engine,
and council-aware provider registry.
"""

import pytest
import os
from unittest.mock import patch, MagicMock, PropertyMock
from dataclasses import dataclass

# Ensure backend is on sys.path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.model_providers import (
    ProviderRegistry,
    UniversalProvider,
    GenerationResult,
    ProviderStatus,
    ProviderType,
    ModelProvider,
)
from config.settings import MultiProviderConfig, ProviderDescriptor


# ══════════════════════════════════════════════
# Test 1: MultiProviderConfig
# ══════════════════════════════════════════════

class TestMultiProviderConfig:
    def test_no_keys_configured(self):
        config = MultiProviderConfig(
            claude_api_key="", gemini_api_key="", openai_api_key="",
            grok_api_key="", openrouter_api_key="", llm_api_key="",
        )
        assert config.active_count == 0
        assert not config.council_eligible
        assert config.configured_providers() == []

    def test_single_key_configured(self):
        config = MultiProviderConfig(
            claude_api_key="", gemini_api_key="", openai_api_key="sk-test",
            grok_api_key="", openrouter_api_key="", llm_api_key="",
        )
        assert config.active_count == 1
        assert not config.council_eligible
        assert config.is_configured
        providers = config.configured_providers()
        assert len(providers) == 1
        assert providers[0].name == "openai"
        assert providers[0].api_key == "sk-test"

    def test_multiple_keys_configured(self):
        config = MultiProviderConfig(
            claude_api_key="sk-ant-test", gemini_api_key="AIza-test",
            openai_api_key="sk-test", grok_api_key="", openrouter_api_key="",
            llm_api_key="",
        )
        assert config.active_count == 3
        assert config.council_eligible
        providers = config.configured_providers()
        assert len(providers) == 3
        names = [p.name for p in providers]
        assert "claude" in names
        assert "gemini" in names
        assert "openai" in names

    def test_all_keys_configured(self):
        config = MultiProviderConfig(
            claude_api_key="key1", gemini_api_key="key2",
            openai_api_key="key3", grok_api_key="key4",
            openrouter_api_key="key5", llm_api_key="",
        )
        assert config.active_count == 5
        assert config.council_eligible

    def test_backward_compat_api_key_property(self):
        config = MultiProviderConfig(
            claude_api_key="claude-key", gemini_api_key="",
            openai_api_key="", grok_api_key="", openrouter_api_key="",
            llm_api_key="",
        )
        # api_key property returns the first configured key
        assert config.api_key == "claude-key"

    def test_backward_compat_fallback_to_llm_key(self):
        config = MultiProviderConfig(
            claude_api_key="", gemini_api_key="", openai_api_key="",
            grok_api_key="", openrouter_api_key="",
            llm_api_key="legacy-key",
        )
        assert config.api_key == "legacy-key"
        assert config.is_configured

    def test_provider_descriptor_slots(self):
        config = MultiProviderConfig(
            claude_api_key="key1", gemini_api_key="key2",
            openai_api_key="key3", grok_api_key="key4",
            openrouter_api_key="key5", llm_api_key="",
        )
        providers = config.configured_providers()
        assert providers[0].slot == 1  # Claude
        assert providers[1].slot == 2  # Gemini
        assert providers[2].slot == 3  # OpenAI
        assert providers[3].slot == 4  # Grok
        assert providers[4].slot == 5  # OpenRouter


# ══════════════════════════════════════════════
# Test 2: ProviderDescriptor
# ══════════════════════════════════════════════

class TestProviderDescriptor:
    def test_configured(self):
        desc = ProviderDescriptor(1, "claude", "key123", "https://api.anthropic.com/v1", "claude-sonnet-4-20250514")
        assert desc.is_configured
        assert desc.name == "claude"
        assert desc.slot == 1

    def test_not_configured(self):
        desc = ProviderDescriptor(1, "claude", "", "https://api.anthropic.com/v1", "claude-sonnet-4-20250514")
        assert not desc.is_configured


# ══════════════════════════════════════════════
# Test 3: Provider Registry (Basic)
# ══════════════════════════════════════════════

class TestProviderRegistry:
    def test_empty_registry(self):
        registry = ProviderRegistry()
        assert registry.active is None
        assert registry.active_name == "none"
        assert len(registry.list_providers()) == 0
        assert not registry.is_council_mode

    def test_register_and_activate(self):
        registry = ProviderRegistry()

        class MockProvider(ModelProvider):
            def __init__(self):
                super().__init__("mock", "mock-model")
            def generate(self, prompt, **kwargs):
                return GenerationResult(text=f"Echo: {prompt}", provider="mock")

        registry.register(MockProvider())
        registry.set_active("mock")
        assert registry.active_name == "mock"
        assert len(registry.list_providers()) == 1

    def test_generate_no_provider(self):
        registry = ProviderRegistry()
        result = registry.generate("test")
        assert result.error == "No provider available."

    def test_generate_fn_bridge(self):
        registry = ProviderRegistry()

        class MockProvider(ModelProvider):
            def __init__(self):
                super().__init__("mock", "mock-model")
            def generate(self, prompt, max_tokens=2048, temperature=0.7,
                         system_prompt="", **kwargs):
                if "fail" in prompt:
                    return GenerationResult(error="Simulated failure", provider="mock")
                return GenerationResult(text=f"Echo: {prompt}", provider="mock")

        registry.register(MockProvider())
        registry.set_active("mock")

        generate_fn = registry.generate_fn()
        assert generate_fn("hello") == "Echo: hello"
        assert "[Error: Simulated failure]" in generate_fn("please fail")


# ══════════════════════════════════════════════
# Test 4: ProviderType enum
# ══════════════════════════════════════════════

class TestProviderType:
    def test_all_types(self):
        assert ProviderType.CLAUDE.value == "claude"
        assert ProviderType.GEMINI.value == "gemini"
        assert ProviderType.OPENAI.value == "openai"
        assert ProviderType.GROK.value == "grok"
        assert ProviderType.OPENROUTER.value == "openrouter"
        assert ProviderType.COUNCIL.value == "council"
        assert ProviderType.UNIVERSAL.value == "universal"
        assert ProviderType.AUTO.value == "auto"


# ══════════════════════════════════════════════
# Test 5: LLM Council
# ══════════════════════════════════════════════

class TestLLMCouncil:
    def _make_mock_provider(self, name: str, response_text: str):
        """Create a mock provider that returns a fixed response."""
        class MockCouncilProvider(ModelProvider):
            def __init__(self, provider_name, text):
                super().__init__(provider_name, f"{provider_name}-model")
                self._response_text = text

            def generate(self, prompt, max_tokens=2048, temperature=0.7,
                         system_prompt="", **kwargs):
                import time
                start = time.time()
                # Check if this is a ranking prompt
                if "Rate EACH response" in prompt or "evaluator" in system_prompt:
                    # Return mock ranking JSON
                    import json
                    ranks = [
                        {"response_id": "A", "accuracy": 8, "completeness": 7, "clarity": 9, "relevance": 8},
                        {"response_id": "B", "accuracy": 7, "completeness": 8, "clarity": 7, "relevance": 7},
                        {"response_id": "C", "accuracy": 9, "completeness": 9, "clarity": 8, "relevance": 9},
                    ]
                    return GenerationResult(
                        text=json.dumps(ranks),
                        provider=self.name,
                        model=self.model,
                        latency_ms=10.0,
                    )
                latency = (time.time() - start) * 1000
                return GenerationResult(
                    text=self._response_text,
                    provider=self.name,
                    model=self.model,
                    latency_ms=latency + 1.0,
                )

        return MockCouncilProvider(name, response_text)

    def test_single_provider_direct_mode(self):
        from providers.llm_council import LLMCouncil
        provider = self._make_mock_provider("test", "Hello World")
        council = LLMCouncil([provider])

        assert council.size == 1
        assert not council.is_council_mode

        result = council.query("test prompt")
        assert result.mode == "direct"
        assert result.best_response == "Hello World"
        assert result.best_provider == "test"

    def test_multi_provider_council_mode(self):
        from providers.llm_council import LLMCouncil
        providers = [
            self._make_mock_provider("alpha", "Alpha response"),
            self._make_mock_provider("beta", "Beta response"),
            self._make_mock_provider("gamma", "Gamma response"),
        ]
        council = LLMCouncil(providers)

        assert council.size == 3
        assert council.is_council_mode

        result = council.query("test question")
        assert result.mode == "council"
        assert result.council_size == 3
        assert result.best_response  # Got some response
        assert result.best_provider in ["alpha", "beta", "gamma"]
        assert result.best_score > 0

    def test_empty_council(self):
        from providers.llm_council import LLMCouncil
        council = LLMCouncil([])
        result = council.query("test")
        assert result.error == "No providers configured"
        assert result.mode == "error"

    def test_council_stats(self):
        from providers.llm_council import LLMCouncil
        providers = [
            self._make_mock_provider("a", "Response A"),
            self._make_mock_provider("b", "Response B"),
        ]
        council = LLMCouncil(providers)
        stats = council.get_stats()
        assert stats["council_size"] == 2
        assert stats["is_council_mode"] is True
        assert stats["total_queries"] == 0

    def test_council_generate_fn(self):
        from providers.llm_council import LLMCouncil
        provider = self._make_mock_provider("solo", "Solo answer")
        council = LLMCouncil([provider])
        fn = council.generate_fn()
        result = fn("test")
        assert result == "Solo answer"


# ══════════════════════════════════════════════
# Test 6: Council Data Models
# ══════════════════════════════════════════════

class TestCouncilDataModels:
    def test_provider_response(self):
        from providers.llm_council import ProviderResponse
        r = ProviderResponse("test", "model", "hello", 100.0)
        assert r.ok
        r_err = ProviderResponse("test", "model", "", 0.0, error="fail")
        assert not r_err.ok

    def test_ranking_score(self):
        from providers.llm_council import RankingScore
        score = RankingScore("judge", "target", 8.0, 7.0, 9.0, 8.0)
        assert score.average == 8.0

    def test_council_result(self):
        from providers.llm_council import CouncilResult
        result = CouncilResult(
            best_response="test", best_provider="p", best_model="m",
            best_score=8.5, council_size=3, mode="council",
        )
        assert result.ok
        assert result.best_score == 8.5


# ══════════════════════════════════════════════
# Test 7: Registry Council Integration
# ══════════════════════════════════════════════

class TestRegistryCouncilIntegration:
    def test_registry_council_property(self):
        from providers.llm_council import LLMCouncil
        registry = ProviderRegistry()
        assert registry.council is None
        assert not registry.is_council_mode

        class MockProvider(ModelProvider):
            def __init__(self, name):
                super().__init__(name, f"{name}-model")
            def generate(self, prompt, **kwargs):
                return GenerationResult(text="test", provider=self.name)

        p1 = MockProvider("a")
        p2 = MockProvider("b")
        registry.register(p1)
        registry.register(p2)
        registry.set_active("a")

        council = LLMCouncil([p1, p2])
        registry._council = council

        assert registry.is_council_mode
        assert registry.council.size == 2

    def test_status_display_council(self):
        registry = ProviderRegistry()

        class MockProvider(ModelProvider):
            def __init__(self, name):
                super().__init__(name, f"{name}-model")
            def generate(self, prompt, **kwargs):
                return GenerationResult(text="test", provider=self.name)

        p1 = MockProvider("claude")
        p2 = MockProvider("openai")
        registry.register(p1)
        registry.register(p2)
        registry.set_active("claude")

        from providers.llm_council import LLMCouncil
        registry._council = LLMCouncil([p1, p2])

        display = registry.status_display()
        assert "COUNCIL MODE" in display
        assert "claude" in display
        assert "openai" in display
        assert "2 providers" in display


# ══════════════════════════════════════════════
# Test 8: Ranking JSON Parser
# ══════════════════════════════════════════════

class TestRankingParser:
    def test_parse_clean_json(self):
        from providers.llm_council import _parse_ranking_json
        raw = '[{"response_id": "A", "accuracy": 8, "completeness": 7, "clarity": 9, "relevance": 8}]'
        result = _parse_ranking_json(raw, [])
        assert len(result) == 1
        assert result[0]["accuracy"] == 8

    def test_parse_markdown_fenced_json(self):
        from providers.llm_council import _parse_ranking_json
        raw = '```json\n[{"response_id": "A", "accuracy": 8, "completeness": 7, "clarity": 9, "relevance": 8}]\n```'
        result = _parse_ranking_json(raw, [])
        assert len(result) == 1

    def test_parse_json_with_surrounding_text(self):
        from providers.llm_council import _parse_ranking_json
        raw = 'Here are the scores: [{"accuracy": 8, "completeness": 7, "clarity": 9, "relevance": 8}] end'
        result = _parse_ranking_json(raw, [])
        assert len(result) == 1

    def test_parse_invalid_json(self):
        from providers.llm_council import _parse_ranking_json
        raw = 'not json at all'
        result = _parse_ranking_json(raw, [])
        assert result == []


if __name__ == "__main__":
    pytest.main(["-v", __file__])
