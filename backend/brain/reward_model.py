"""
Reward Model — Multi-Dimensional Composite Rewards.
Inspired by Agent Lightning's multi-dimensional emit_reward() system.

Converts 6-layer verification scores into structured reward signals
with learnable dimension weights and EMA normalization.
"""

import json
import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RewardDimension:
    """A single named reward dimension.

    Like AGL's RewardDimension but with weight and history tracking.
    """
    name: str
    value: float = 0.0
    weight: float = 1.0             # Learnable weight
    is_primary: bool = False


@dataclass
class CompositeReward:
    """Multi-dimensional reward aggregated from all verification layers.

    Agent Lightning uses emit_reward({k: v}) — we go further with
    learnable weights, domain-specific scaling, and history.
    """
    dimensions: List[RewardDimension] = field(default_factory=list)
    primary_reward: float = 0.0     # Weighted composite score
    raw_reward: float = 0.0         # Unweighted average
    domain: str = "general"

    # Security override
    has_critical_vulns: bool = False
    security_penalty: float = 0.0

    def add_dimension(self, name: str, value: float, weight: float = 1.0,
                      is_primary: bool = False) -> None:
        self.dimensions.append(RewardDimension(
            name=name, value=value, weight=weight, is_primary=is_primary
        ))

    def compute(self) -> float:
        """Compute weighted composite reward."""
        if not self.dimensions:
            return 0.0

        total_weight = sum(d.weight for d in self.dimensions)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(d.value * d.weight for d in self.dimensions)
        self.raw_reward = sum(d.value for d in self.dimensions) / len(self.dimensions)
        self.primary_reward = weighted_sum / total_weight

        # Security penalty: critical vulns drastically reduce reward
        if self.has_critical_vulns:
            self.security_penalty = self.primary_reward * 0.8
            self.primary_reward *= 0.2
            logger.warning(
                f"Security penalty applied: reward {self.primary_reward:.3f} "
                f"(penalty: {self.security_penalty:.3f})"
            )

        return self.primary_reward

    def to_dict(self) -> Dict[str, float]:
        """Convert to AGL-style reward dict for emit_reward compatibility."""
        result = {}
        for d in self.dimensions:
            result[d.name] = d.value
        result["composite"] = self.primary_reward
        return result

    def summary(self) -> str:
        lines = [f"Composite Reward: {self.primary_reward:.4f}"]
        for d in self.dimensions:
            marker = " *" if d.is_primary else ""
            lines.append(f"  {d.name}: {d.value:.3f} (w={d.weight:.2f}){marker}")
        if self.has_critical_vulns:
            lines.append(f"  [SECURITY PENALTY: -{self.security_penalty:.3f}]")
        return "\n".join(lines)


class RewardNormalizer:
    """EMA-based reward normalization to prevent reward hacking.

    Tracks running statistics and normalizes rewards to [0, 1] range.
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.running_mean: float = 0.5
        self.running_var: float = 0.1
        self.count: int = 0

    def normalize(self, reward: float) -> float:
        """Normalize reward using running statistics."""
        self.count += 1

        # Update running stats with EMA
        self.running_mean = (1 - self.alpha) * self.running_mean + self.alpha * reward
        diff = reward - self.running_mean
        self.running_var = ((1 - self.alpha) * self.running_var
                           + self.alpha * diff * diff)

        # Normalize: z-score then sigmoid to [0, 1]
        std = max(math.sqrt(self.running_var), 1e-6)
        z = (reward - self.running_mean) / std
        normalized = 1.0 / (1.0 + math.exp(-z))
        return normalized

    def get_stats(self) -> Dict[str, float]:
        return {
            "mean": self.running_mean,
            "std": math.sqrt(max(self.running_var, 0)),
            "count": self.count,
        }


# Default dimension weights per domain
DOMAIN_REWARD_WEIGHTS: Dict[str, Dict[str, float]] = {
    "coding": {
        "static": 1.0, "property": 1.2, "scenario": 1.5,
        "critic": 0.8, "code_quality": 2.0, "security": 2.5,
    },
    "debugging": {
        "static": 1.5, "property": 1.0, "scenario": 1.8,
        "critic": 1.0, "code_quality": 1.5, "security": 2.0,
    },
    "algorithm": {
        "static": 1.0, "property": 2.0, "scenario": 1.5,
        "critic": 1.0, "code_quality": 1.0, "security": 1.0,
    },
    "architecture": {
        "static": 0.8, "property": 1.0, "scenario": 1.5,
        "critic": 2.0, "code_quality": 1.5, "security": 1.5,
    },
    "logic": {
        "static": 1.0, "property": 2.5, "scenario": 2.0,
        "critic": 1.0, "code_quality": 0.5, "security": 0.5,
    },
    "math": {
        "static": 1.0, "property": 2.5, "scenario": 2.0,
        "critic": 1.0, "code_quality": 0.5, "security": 0.5,
    },
    "general": {
        "static": 1.0, "property": 1.0, "scenario": 1.0,
        "critic": 1.0, "code_quality": 1.0, "security": 1.0,
    },
}


class RewardComputer:
    """Computes multi-dimensional rewards from VerificationReport.

    Integrates all 6 verifier layers into structured reward signal.
    Weights are domain-specific and learnable.
    """

    def __init__(self, persist_dir: str = "data/reward_weights"):
        self.normalizer = RewardNormalizer()
        self.domain_weights = dict(DOMAIN_REWARD_WEIGHTS)
        # Per-domain normalizers for better calibration
        self._domain_normalizers: Dict[str, RewardNormalizer] = {}
        # Weight change history for auditing
        self._weight_history: List[Dict] = []
        # Persistence
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._load_weights()

    def compute_reward(
        self,
        verification_report: Any,
        domain: str = "general",
        normalize: bool = True,
    ) -> CompositeReward:
        """Convert a VerificationReport into a CompositeReward.

        Args:
            verification_report: VerificationReport from verifier stack
            domain: Problem domain for weight selection
            normalize: Whether to apply EMA normalization

        Returns:
            CompositeReward with all dimension scores
        """
        reward = CompositeReward(domain=domain)
        weights = self.domain_weights.get(domain, self.domain_weights["general"])

        # Extract 6 verification layer scores
        layers = [
            ("static", getattr(verification_report, "v_static", 0.0)),
            ("property", getattr(verification_report, "v_property", 0.0)),
            ("scenario", getattr(verification_report, "v_scenario", 0.0)),
            ("critic", getattr(verification_report, "v_critic", 0.0)),
            ("code_quality", getattr(verification_report, "v_code", 0.0)),
            ("security", getattr(verification_report, "v_security", 0.0)),
        ]

        for name, value in layers:
            reward.add_dimension(
                name=name,
                value=value,
                weight=weights.get(name, 1.0),
                is_primary=(name == "security"),
            )

        # Security override
        reward.has_critical_vulns = getattr(
            verification_report, "has_critical_vulns", False
        )

        # Compute composite
        raw = reward.compute()

        # Normalize if requested
        if normalize and self.normalizer.count > 5:
            if domain not in self._domain_normalizers:
                self._domain_normalizers[domain] = RewardNormalizer()
            normalized = self._domain_normalizers[domain].normalize(raw)
            reward.primary_reward = normalized

        # Also update global normalizer
        self.normalizer.normalize(raw)

        logger.info(f"Reward computed: {reward.summary()}")
        return reward

    def update_weights(
        self,
        domain: str,
        dimension_name: str,
        delta: float,
        learning_rate: float = 0.01,
    ) -> None:
        """Update a domain-specific dimension weight based on learning signal.

        Args:
            domain: The task domain
            dimension_name: Which reward dimension to adjust
            delta: Positive = increase weight, negative = decrease
            learning_rate: How fast to adjust
        """
        if domain not in self.domain_weights:
            self.domain_weights[domain] = dict(
                self.domain_weights.get("general", {})
            )

        current = self.domain_weights[domain].get(dimension_name, 1.0)
        new_weight = max(0.1, min(5.0, current + learning_rate * delta))
        self.domain_weights[domain][dimension_name] = new_weight

        # Track history
        self._weight_history.append({
            "domain": domain,
            "dimension": dimension_name,
            "old_weight": current,
            "new_weight": new_weight,
            "delta": learning_rate * delta,
        })

        # Auto-save periodically
        if len(self._weight_history) % 10 == 0:
            self.save_weights()

        logger.debug(
            f"Updated weight {domain}/{dimension_name}: "
            f"{current:.3f} -> {new_weight:.3f}"
        )

    def get_dimension_weights(self, domain: str) -> Dict[str, float]:
        """Get current weights for a domain."""
        return self.domain_weights.get(
            domain, self.domain_weights.get("general", {})
        )

    def save_weights(self) -> None:
        """Persist current domain weights to disk."""
        path = self._persist_dir / "domain_weights.json"
        data = {
            "domain_weights": self.domain_weights,
            "history_length": len(self._weight_history),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        # Save history (last 500 entries)
        hist_path = self._persist_dir / "weight_history.json"
        with open(hist_path, "w") as f:
            json.dump(self._weight_history[-500:], f, indent=2)

        logger.info(f"Saved reward weights to {path}")

    def _load_weights(self) -> None:
        """Load persisted weights from disk if available."""
        path = self._persist_dir / "domain_weights.json"
        if path.exists():
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                loaded = data.get("domain_weights", {})
                # Merge with defaults (new domains get defaults)
                for domain, weights in loaded.items():
                    self.domain_weights[domain] = weights
                logger.info(f"Loaded reward weights from {path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load reward weights: {e}")

        hist_path = self._persist_dir / "weight_history.json"
        if hist_path.exists():
            try:
                with open(hist_path, "r") as f:
                    self._weight_history = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._weight_history = []

    def get_weight_history(self) -> List[Dict]:
        """Get the weight change history for auditing."""
        return list(self._weight_history)

    def get_learning_stats(self) -> Dict[str, Any]:
        """Get statistics about weight changes."""
        if not self._weight_history:
            return {"total_updates": 0}
        return {
            "total_updates": len(self._weight_history),
            "domains_updated": list(set(
                h["domain"] for h in self._weight_history
            )),
            "avg_delta": sum(
                abs(h["delta"]) for h in self._weight_history
            ) / len(self._weight_history),
        }
