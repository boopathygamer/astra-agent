"""
Reinforcement Learner — RL-Based Prompt Optimization
═════════════════════════════════════════════════════
Learns from success/failure feedback signals to evolve prompts
over time using a multi-armed bandit approach.

Core Loop:
  1. Maintain a population of prompt variants per task type
  2. Select variants using Thompson Sampling (Beta distribution)
  3. Observe outcomes (user rating, task success, response quality)
  4. Update belief distributions per variant
  5. Periodically mutate top performers to explore new strategies
"""

import hashlib
import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PromptVariant:
    """A single prompt variant being evaluated."""
    variant_id: str = ""
    template: str = ""
    task_type: str = "general"
    # Beta distribution params for Thompson Sampling
    alpha: float = 1.0   # successes + 1
    beta_param: float = 1.0    # failures + 1
    trials: int = 0
    total_reward: float = 0.0
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def mean_reward(self) -> float:
        return self.total_reward / max(self.trials, 1)

    @property
    def ucb_score(self) -> float:
        """Upper Confidence Bound score."""
        if self.trials == 0:
            return float("inf")
        exploitation = self.mean_reward
        exploration = math.sqrt(2.0 * math.log(max(self.trials + 10, 1)) / self.trials)
        return exploitation + exploration

    def thompson_sample(self) -> float:
        """Sample from Beta distribution for Thompson Sampling."""
        return random.betavariate(self.alpha, self.beta_param)

    def update(self, reward: float) -> None:
        """Update with observed reward (0.0 to 1.0)."""
        self.trials += 1
        self.total_reward += reward
        self.last_used = time.time()
        # Update Beta distribution
        if reward >= 0.5:
            self.alpha += reward
        else:
            self.beta_param += (1.0 - reward)


@dataclass
class FeedbackSignal:
    """Observed outcome from using a prompt variant."""
    variant_id: str = ""
    task_type: str = ""
    reward: float = 0.0           # 0.0 (failure) to 1.0 (perfect)
    user_rating: Optional[float] = None  # Explicit user feedback
    response_length: int = 0
    response_time_ms: float = 0.0
    error_occurred: bool = False
    timestamp: float = field(default_factory=time.time)


class ReinforcementLearner:
    """
    RL-based prompt optimization engine.

    Maintains a population of prompt variants per task type and
    uses Thompson Sampling to select the best-performing variant
    for each new request. Learns from feedback to continuously improve.
    """

    MAX_VARIANTS_PER_TYPE = 20
    MUTATION_RATE = 0.1
    MIN_TRIALS_FOR_PRUNING = 10
    PRUNE_THRESHOLD = 0.3  # Remove variants below this mean reward

    def __init__(self):
        # task_type → list of PromptVariant
        self._variants: Dict[str, List[PromptVariant]] = {}
        self._feedback_history: List[FeedbackSignal] = []
        self._generation = 0
        self._total_feedback = 0

        # Seed default variants
        self._seed_defaults()
        logger.info("[RL_LEARNER] Reinforcement Learner initialized")

    def _seed_defaults(self) -> None:
        """Seed initial prompt variants for common task types."""
        defaults = {
            "general": [
                "You are a highly capable AI assistant. Think step by step before answering.",
                "You are an expert problem solver. Break down the problem, then provide a clear solution.",
                "Analyze the request carefully. Provide a thorough, well-structured response.",
            ],
            "coding": [
                "You are a senior software engineer. Write clean, documented, production-ready code.",
                "You are a code architect. Think about edge cases, performance, and maintainability.",
                "Write code that is simple, tested, and follows best practices. Explain your design choices.",
            ],
            "analysis": [
                "You are a data analyst. Use evidence-based reasoning and cite specific details.",
                "Think critically about this problem. Consider multiple perspectives before concluding.",
                "Break this into sub-problems. Analyze each systematically, then synthesize.",
            ],
            "creative": [
                "You are a creative expert. Be original, vivid, and engaging in your response.",
                "Think outside the box. Combine unexpected ideas to create something unique.",
            ],
        }
        for task_type, templates in defaults.items():
            self._variants[task_type] = []
            for tmpl in templates:
                vid = hashlib.md5(f"{task_type}:{tmpl[:50]}".encode()).hexdigest()[:10]
                self._variants[task_type].append(PromptVariant(
                    variant_id=vid, template=tmpl, task_type=task_type,
                ))

    def select_variant(self, task_type: str = "general") -> PromptVariant:
        """
        Select the best prompt variant using Thompson Sampling.
        Higher-reward variants are selected more often, but exploration
        ensures we still try lower-confidence variants.
        """
        variants = self._variants.get(task_type, self._variants.get("general", []))
        if not variants:
            return PromptVariant(template="You are a helpful AI assistant.", task_type=task_type)

        # Thompson Sampling: sample from each variant's Beta distribution
        scored = [(v, v.thompson_sample()) for v in variants]
        scored.sort(key=lambda x: x[1], reverse=True)

        winner = scored[0][0]
        winner.last_used = time.time()

        logger.debug(
            f"[RL_LEARNER] Selected variant {winner.variant_id} for [{task_type}] "
            f"(mean={winner.mean_reward:.3f}, trials={winner.trials})"
        )
        return winner

    def record_feedback(self, signal: FeedbackSignal) -> None:
        """Record an outcome and update the variant's beliefs."""
        self._feedback_history.append(signal)
        self._total_feedback += 1

        # Find and update the variant
        variants = self._variants.get(signal.task_type, [])
        for v in variants:
            if v.variant_id == signal.variant_id:
                v.update(signal.reward)
                break

        # Periodic evolution
        if self._total_feedback % 50 == 0:
            self._evolve()

        logger.debug(
            f"[RL_LEARNER] Feedback recorded: variant={signal.variant_id} "
            f"reward={signal.reward:.2f} (total={self._total_feedback})"
        )

    def _evolve(self) -> None:
        """Periodically mutate top variants and prune worst performers."""
        self._generation += 1
        logger.info(f"[RL_LEARNER] Evolution cycle {self._generation}")

        for task_type, variants in self._variants.items():
            # Prune underperformers
            before = len(variants)
            variants = [
                v for v in variants
                if v.trials < self.MIN_TRIALS_FOR_PRUNING
                or v.mean_reward >= self.PRUNE_THRESHOLD
            ]

            # Mutate top performers
            if len(variants) >= 2 and random.random() < self.MUTATION_RATE:
                top = sorted(variants, key=lambda v: v.mean_reward, reverse=True)[:2]
                child_template = self._crossover(top[0].template, top[1].template)
                child_id = hashlib.md5(
                    f"{task_type}:gen{self._generation}:{time.time()}".encode()
                ).hexdigest()[:10]
                child = PromptVariant(
                    variant_id=child_id, template=child_template, task_type=task_type,
                    metadata={"parents": [top[0].variant_id, top[1].variant_id], "generation": self._generation},
                )
                if len(variants) < self.MAX_VARIANTS_PER_TYPE:
                    variants.append(child)

            self._variants[task_type] = variants
            pruned = before - len(variants)
            if pruned:
                logger.info(f"[RL_LEARNER] Pruned {pruned} underperforming variants for [{task_type}]")

    @staticmethod
    def _crossover(parent_a: str, parent_b: str) -> str:
        """Create a child template by combining two parent templates."""
        sentences_a = [s.strip() for s in parent_a.split(".") if s.strip()]
        sentences_b = [s.strip() for s in parent_b.split(".") if s.strip()]
        child_parts = []
        for i in range(max(len(sentences_a), len(sentences_b))):
            if random.random() < 0.5 and i < len(sentences_a):
                child_parts.append(sentences_a[i])
            elif i < len(sentences_b):
                child_parts.append(sentences_b[i])
            elif i < len(sentences_a):
                child_parts.append(sentences_a[i])
        return ". ".join(child_parts) + "."

    def get_leaderboard(self, task_type: str = None) -> List[Dict[str, Any]]:
        """Get ranked variants for a task type or all types."""
        results = []
        types = [task_type] if task_type else list(self._variants.keys())
        for tt in types:
            for v in sorted(self._variants.get(tt, []), key=lambda x: x.mean_reward, reverse=True):
                results.append({
                    "variant_id": v.variant_id,
                    "task_type": v.task_type,
                    "template_preview": v.template[:80] + "..." if len(v.template) > 80 else v.template,
                    "mean_reward": round(v.mean_reward, 4),
                    "trials": v.trials,
                    "ucb_score": round(v.ucb_score, 4),
                })
        return results

    def get_stats(self) -> Dict[str, Any]:
        total_variants = sum(len(v) for v in self._variants.values())
        return {
            "total_variants": total_variants,
            "task_types": len(self._variants),
            "total_feedback": self._total_feedback,
            "generation": self._generation,
            "variants_per_type": {k: len(v) for k, v in self._variants.items()},
        }
