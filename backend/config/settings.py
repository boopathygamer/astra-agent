"""
Global configuration for the Custom LLM System.
All paths, hyperparameters, and thresholds live here.
Loads .env file automatically for secure secret management.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── Load .env file if present (before any os.getenv calls) ──
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key = _key.strip()
                _val = _val.strip().strip("'\"")
                if _key and _key not in os.environ:  # Don't override real env vars
                    os.environ[_key] = _val


# ──────────────────────────────────────────────
# Base Paths
# ──────────────────────────────────────────────
_DEFAULT_BASE = str(Path(__file__).parent.parent / "data")
BASE_DIR = Path(os.getenv("LLM_BASE_DIR", _DEFAULT_BASE))
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = DATA_DIR / "memory_store"
UPLOADS_DIR = DATA_DIR / "uploads"

# Ensure data directories exist
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)



@dataclass
class BrainConfig:
    """Self-thinking brain configuration."""
    # Memory / Bug Diary
    memory_collection_name: str = "failure_memory"
    memory_persist_dir: str = str(MEMORY_DIR)
    max_memory_retrieval: int = 5
    decay_factor: float = 0.9  # γ for exponential decay

    # Multi-Hypothesis
    max_hypotheses: int = 5
    hypothesis_temperature: float = 1.0  # β for weight updates
    min_hypothesis_weight: float = 0.01

    # Verifier
    confidence_threshold: float = 0.7  # τ — minimum confidence to execute
    risk_threshold: float = 0.3  # κ — maximum risk to execute
    sandbox_risk_threshold: float = 0.6  # κ' — max risk for sandbox
    sandbox_confidence_threshold: float = 0.4  # τ' — min confidence for sandbox

    # Tri-Shield weights (λ₁, λ₂, λ₃, λ₄)
    lambda_robust: float = 1.0
    lambda_detect: float = 0.8
    lambda_contain: float = 0.5
    lambda_complexity: float = 0.2

    # Thinking loop
    max_iterations: int = 5
    improvement_threshold: float = 0.05  # Minimum confidence gain to continue


@dataclass
class AgentConfig:
    """Agent framework configuration."""
    max_tool_calls: int = 10
    sandbox_timeout: int = 30  # seconds
    max_retries: int = 3

    # Tool Policy Engine
    tool_profile: str = "assistant"  # minimal | coding | assistant | full
    tool_global_deny: list = field(default_factory=list)

    # Loop Detection Guardrails
    loop_detection_enabled: bool = True
    loop_warning_threshold: int = 5
    loop_critical_threshold: int = 10
    loop_circuit_breaker_threshold: int = 20

    # Session Manager
    sessions_dir: str = str(DATA_DIR / "sessions")
    session_compaction_threshold: int = 100  # messages before compaction

    # Process Manager
    max_background_processes: int = 20
    process_default_timeout: int = 300
    process_yield_ms: int = 10000  # auto-background timeout

    # Workspace Injection
    workspace_dir: str = str(DATA_DIR / "workspace")

    # Skills Registry
    skills_bundled_dir: str = str(DATA_DIR / "skills" / "bundled")
    skills_managed_dir: str = str(DATA_DIR / "skills" / "managed")

    # Streaming
    stream_chunk_size: int = 50
    stream_coalesce_ms: int = 100
    stream_break_on: str = "sentence"  # token | sentence | paragraph

    # Model Failover
    model_failover_enabled: bool = True
    model_circuit_breaker_threshold: int = 5
    model_circuit_breaker_reset_seconds: int = 60


@dataclass
class ProviderDescriptor:
    """Describes a single LLM provider slot."""
    slot: int
    name: str
    api_key: str
    base_url: str
    model: str

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class MultiProviderConfig:
    """Multi-provider API configuration — 5 named provider slots."""
    # Slot 1: Claude (Anthropic)
    claude_api_key: str = os.getenv("CLAUDE_API_KEY", "")
    claude_base_url: str = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    # Slot 2: Gemini (Google)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_base_url: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro-preview-05-06")

    # Slot 3: OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Slot 4: Grok (xAI)
    grok_api_key: str = os.getenv("GROK_API_KEY", "")
    grok_base_url: str = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1")
    grok_model: str = os.getenv("GROK_MODEL", "grok-3")

    # Slot 5: OpenRouter
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-4-maverick")

    # Legacy fallback
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")

    @property
    def is_configured(self) -> bool:
        """True if at least one provider key is set."""
        return any(d.is_configured for d in self.configured_providers()) or bool(self.llm_api_key)

    def configured_providers(self) -> list:
        """Return list of ProviderDescriptors for all slots that have API keys."""
        slots = [
            ProviderDescriptor(1, "claude", self.claude_api_key, self.claude_base_url, self.claude_model),
            ProviderDescriptor(2, "gemini", self.gemini_api_key, self.gemini_base_url, self.gemini_model),
            ProviderDescriptor(3, "openai", self.openai_api_key, self.openai_base_url, self.openai_model),
            ProviderDescriptor(4, "grok", self.grok_api_key, self.grok_base_url, self.grok_model),
            ProviderDescriptor(5, "openrouter", self.openrouter_api_key, self.openrouter_base_url, self.openrouter_model),
        ]
        return [s for s in slots if s.is_configured]

    @property
    def active_count(self) -> int:
        """Number of configured providers."""
        return len(self.configured_providers())

    @property
    def council_eligible(self) -> bool:
        """True if 2+ providers are configured (council mode)."""
        return self.active_count >= 2

    # ── Backward-compat shims for old UniversalAPIConfig usage ──
    @property
    def api_key(self) -> str:
        """Return the first available key, or legacy LLM_API_KEY."""
        providers = self.configured_providers()
        if providers:
            return providers[0].api_key
        return self.llm_api_key

    @api_key.setter
    def api_key(self, value: str):
        self.llm_api_key = value

    @property
    def base_url(self) -> str:
        providers = self.configured_providers()
        if providers:
            return providers[0].base_url
        return self.llm_base_url

    @base_url.setter
    def base_url(self, value: str):
        self.llm_base_url = value

    @property
    def model(self) -> str:
        providers = self.configured_providers()
        if providers:
            return providers[0].model
        return self.llm_model

    @model.setter
    def model(self, value: str):
        self.llm_model = value


@dataclass
class ThreatScanConfig:
    """Threat Scanner configuration."""
    quarantine_dir: str = str(DATA_DIR / "threat_quarantine")
    max_file_size_mb: int = 100
    entropy_threshold: float = 7.2
    auto_scan_on_file_ops: bool = True


@dataclass
class APIConfig:
    """API server configuration."""
    host: str = os.getenv("LLM_API_HOST", "127.0.0.1")
    port: int = int(os.getenv("LLM_API_PORT", "8000"))
    reload: bool = False
    workers: int = 1


@dataclass
class SSLConfig:
    """HTTPS / TLS configuration."""
    enabled: bool = bool(os.getenv("SSL_ENABLED", ""))
    certfile: str = os.getenv("SSL_CERTFILE", "certs/server.crt")
    keyfile: str = os.getenv("SSL_KEYFILE", "certs/server.key")

    @property
    def is_ready(self) -> bool:
        return self.enabled and Path(self.certfile).exists() and Path(self.keyfile).exists()


@dataclass
class TokenBudgetConfig:
    """Token budget management."""
    daily_limit: int = int(os.getenv("TOKEN_DAILY_LIMIT", "1000000"))
    monthly_limit: int = int(os.getenv("TOKEN_MONTHLY_LIMIT", "30000000"))
    cost_per_1k_premium: float = 0.03   # GPT-4o / Claude 3.5
    cost_per_1k_budget: float = 0.001   # Llama / Mistral
    auto_downgrade: bool = True


# ──────────────────────────────────────────────
# Global Singleton Configs
# ──────────────────────────────────────────────

agent_config = AgentConfig()
provider_config = MultiProviderConfig()
api_config = APIConfig()
brain_config = BrainConfig()
threat_config = ThreatScanConfig()
ssl_config = SSLConfig()
token_budget_config = TokenBudgetConfig()


