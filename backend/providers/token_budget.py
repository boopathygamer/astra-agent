"""
Token Budget Manager — Daily/Monthly Token Spending Control
═══════════════════════════════════════════════════════════
Tracks token consumption across all LLM providers and automatically
downgrades to cheaper models when budget is running low.

Features:
  - Real-time token counting per provider
  - Daily + monthly budget enforcement
  - Auto-downgrade to cheaper models at budget thresholds
  - Cost estimation
  - Persistent daily reset
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenUsageRecord:
    """Record of token usage for a single request."""
    provider_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    timestamp: float = field(default_factory=time.time)


class TokenBudgetManager:
    """
    Manages daily and monthly token budgets.
    Auto-downgrades to cheaper models when budget thresholds are hit.
    """
    
    # Cost per 1K tokens (approximate)
    COST_TABLE = {
        "gpt-4o": 0.030,
        "claude-3-5-sonnet": 0.025,
        "gemini-1.5-pro": 0.020,
        "llama-3-70b": 0.001,
        "mistral-large": 0.002,
    }
    
    PREMIUM_MODELS = {"gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"}
    BUDGET_MODELS = {"llama-3-70b", "mistral-large"}
    
    def __init__(
        self,
        daily_limit: int = 1_000_000,
        monthly_limit: int = 30_000_000,
        auto_downgrade: bool = True,
        persist_path: str = "data/token_budget.json",
    ):
        self.daily_limit = daily_limit
        self.monthly_limit = monthly_limit
        self.auto_downgrade = auto_downgrade
        self._persist_path = Path(persist_path)
        
        self._daily_tokens: int = 0
        self._monthly_tokens: int = 0
        self._daily_cost: float = 0.0
        self._monthly_cost: float = 0.0
        self._last_reset_day: int = datetime.now(timezone.utc).timetuple().tm_yday
        self._last_reset_month: int = datetime.now(timezone.utc).month
        self._records: List[TokenUsageRecord] = []
        
        self._load_state()
    
    def record_usage(self, provider_id: str, prompt_tokens: int, completion_tokens: int):
        """Record token usage from a request."""
        self._maybe_reset()
        
        total = prompt_tokens + completion_tokens
        cost_per_1k = self.COST_TABLE.get(provider_id, 0.01)
        cost = (total / 1000) * cost_per_1k
        
        record = TokenUsageRecord(
            provider_id=provider_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            estimated_cost_usd=cost,
        )
        
        self._daily_tokens += total
        self._monthly_tokens += total
        self._daily_cost += cost
        self._monthly_cost += cost
        self._records.append(record)
        
        # Persist periodically
        if len(self._records) % 10 == 0:
            self._save_state()
    
    def should_downgrade(self) -> bool:
        """Check if we should downgrade to cheaper models."""
        if not self.auto_downgrade:
            return False
        
        daily_pct = self._daily_tokens / self.daily_limit if self.daily_limit > 0 else 0
        monthly_pct = self._monthly_tokens / self.monthly_limit if self.monthly_limit > 0 else 0
        
        # Downgrade if >80% of daily or >90% of monthly budget used
        return daily_pct > 0.80 or monthly_pct > 0.90
    
    def is_over_budget(self) -> bool:
        """Check if budget is completely exhausted."""
        return (self._daily_tokens >= self.daily_limit or 
                self._monthly_tokens >= self.monthly_limit)
    
    def get_allowed_providers(self, requested: List[str]) -> List[str]:
        """Filter provider list based on budget status."""
        if self.is_over_budget():
            # Only allow cheapest models
            return [p for p in requested if p in self.BUDGET_MODELS] or requested[:1]
        
        if self.should_downgrade():
            # Prefer budget models but allow one premium
            budget = [p for p in requested if p in self.BUDGET_MODELS]
            premium = [p for p in requested if p in self.PREMIUM_MODELS][:1]
            return budget + premium if budget else requested
        
        return requested
    
    def _maybe_reset(self):
        """Reset counters on day/month boundaries."""
        now = datetime.now(timezone.utc)
        current_day = now.timetuple().tm_yday
        current_month = now.month
        
        if current_day != self._last_reset_day:
            self._daily_tokens = 0
            self._daily_cost = 0.0
            self._last_reset_day = current_day
        
        if current_month != self._last_reset_month:
            self._monthly_tokens = 0
            self._monthly_cost = 0.0
            self._last_reset_month = current_month
    
    def _save_state(self):
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "daily_tokens": self._daily_tokens,
                "monthly_tokens": self._monthly_tokens,
                "daily_cost": self._daily_cost,
                "monthly_cost": self._monthly_cost,
                "last_reset_day": self._last_reset_day,
                "last_reset_month": self._last_reset_month,
            }
            self._persist_path.write_text(json.dumps(data))
        except Exception as e:
            logger.debug(f"Budget state save failed: {e}")
    
    def _load_state(self):
        try:
            if self._persist_path.exists():
                data = json.loads(self._persist_path.read_text())
                self._daily_tokens = data.get("daily_tokens", 0)
                self._monthly_tokens = data.get("monthly_tokens", 0)
                self._daily_cost = data.get("daily_cost", 0.0)
                self._monthly_cost = data.get("monthly_cost", 0.0)
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "daily_tokens_used": self._daily_tokens,
            "daily_limit": self.daily_limit,
            "daily_pct": round(self._daily_tokens / max(self.daily_limit, 1) * 100, 1),
            "monthly_tokens_used": self._monthly_tokens,
            "monthly_limit": self.monthly_limit,
            "monthly_pct": round(self._monthly_tokens / max(self.monthly_limit, 1) * 100, 1),
            "daily_cost_usd": round(self._daily_cost, 4),
            "monthly_cost_usd": round(self._monthly_cost, 4),
            "should_downgrade": self.should_downgrade(),
            "is_over_budget": self.is_over_budget(),
            "total_requests": len(self._records),
        }
