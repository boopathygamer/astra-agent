"""
Prompt Evolution Engine — Automatic Prompt Optimization (APO).
Inspired by Agent Lightning's algorithm/apo/ module.

Uses "text gradients" — natural language descriptions of what to
change in prompts — then applies edits to evolve prompt populations.
Domain-specific prompt pools learned from trajectory performance.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PromptCandidate:
    """A versioned prompt template with performance tracking."""
    template: str
    version: int = 1
    domain: str = "general"

    # Performance tracking
    total_uses: int = 0
    total_reward: float = 0.0
    best_reward: float = 0.0
    avg_reward: float = 0.0
    elo_rating: float = 1000.0      # ELO for ranking

    # History
    parent_version: int = 0
    text_gradient: str = ""         # What changed from parent
    created_at: float = field(default_factory=time.time)

    def record_result(self, reward: float) -> None:
        self.total_uses += 1
        self.total_reward += reward
        self.avg_reward = self.total_reward / self.total_uses
        if reward > self.best_reward:
            self.best_reward = reward

    def to_dict(self) -> dict:
        return {
            "template": self.template,
            "version": self.version,
            "domain": self.domain,
            "total_uses": self.total_uses,
            "avg_reward": self.avg_reward,
            "best_reward": self.best_reward,
            "elo_rating": self.elo_rating,
            "parent_version": self.parent_version,
            "text_gradient": self.text_gradient,
        }


@dataclass
class TextGradient:
    """Natural language description of what should change in a prompt.

    The "gradient" in APO — tells us the direction of improvement
    without computing actual numerical gradients.
    """
    source_prompt: str
    criticism: str          # What's wrong with current prompt
    suggestion: str         # How to improve it
    confidence: float = 0.5


class PromptEvolver:
    """Evolves prompt populations using APO-style text gradients.

    Maintains a pool of prompt candidates per domain, evaluates
    them against trajectories, and evolves the best ones.
    """

    # Default prompt templates for each purpose
    DEFAULT_PROMPTS: Dict[str, str] = {
        "synthesis": (
            "You are solving a problem. Consider the context and previous "
            "attempts. Generate the best possible solution.\n\n"
            "Problem: {problem}\n"
            "Context: {context}\n"
            "Previous best: {previous_best}\n\n"
            "Solution:"
        ),
        "verification": (
            "Carefully verify the following solution. Check for correctness, "
            "edge cases, security issues, and code quality.\n\n"
            "Problem: {problem}\n"
            "Solution: {solution}\n\n"
            "Verification (score 0-1 and explanation):"
        ),
        "reasoning": (
            "Think step by step about this problem. Break it down, "
            "consider analogies, and reason carefully.\n\n"
            "Problem: {problem}\n"
            "Mode: {mode}\n"
            "Context: {context}\n\n"
            "Reasoning:"
        ),
        "reflection": (
            "Reflect on the problem-solving process. What worked? "
            "What could be improved? What patterns do you notice?\n\n"
            "Problem: {problem}\n"
            "Steps taken: {steps}\n"
            "Outcome: {outcome}\n\n"
            "Reflection:"
        ),
    }

    def __init__(
        self,
        generate_fn: Callable,
        pool_size: int = 5,
        evolve_threshold: int = 10,
    ):
        self.generate_fn = generate_fn
        self.pool_size = pool_size
        self.evolve_threshold = evolve_threshold    # Evolve after N uses

        # Prompt pools: domain -> purpose -> [candidates]
        self._pools: Dict[str, Dict[str, List[PromptCandidate]]] = {}

        # Initialize default pools
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Seed all domains with default prompts."""
        for purpose, template in self.DEFAULT_PROMPTS.items():
            candidate = PromptCandidate(
                template=template,
                domain="general",
                version=1,
            )
            self._pools.setdefault("general", {})\
                .setdefault(purpose, []).append(candidate)

    def get_best_prompt(self, purpose: str, domain: str = "general") -> str:
        """Get the highest-performing prompt for a purpose+domain.

        Falls back to general domain if domain-specific not available.
        """
        candidates = self._get_candidates(purpose, domain)
        if not candidates:
            candidates = self._get_candidates(purpose, "general")
        if not candidates:
            return self.DEFAULT_PROMPTS.get(purpose, "")

        # Return highest ELO
        best = max(candidates, key=lambda c: c.elo_rating)
        return best.template

    def record_performance(
        self,
        purpose: str,
        prompt_used: str,
        reward: float,
        domain: str = "general",
    ) -> None:
        """Record how a prompt performed.

        After enough recordings, triggers evolution.
        """
        candidates = self._get_candidates(purpose, domain)
        for c in candidates:
            if c.template == prompt_used:
                c.record_result(reward)

                # Check if evolution threshold reached
                total_uses = sum(cc.total_uses for cc in candidates)
                if (total_uses > 0
                        and total_uses % self.evolve_threshold == 0):
                    self._evolve(purpose, domain)
                return

        # New prompt not in pool — add it
        new_candidate = PromptCandidate(
            template=prompt_used,
            domain=domain,
            version=1,
        )
        new_candidate.record_result(reward)
        self._get_or_create_pool(purpose, domain).append(new_candidate)

    def _evolve(self, purpose: str, domain: str) -> None:
        """Evolve the prompt pool using APO-style text gradients.

        1. Identify worst-performing prompt
        2. Generate text gradient (criticism + suggestion)
        3. Apply gradient to create new candidate
        4. Replace worst if pool full
        """
        candidates = self._get_candidates(purpose, domain)
        if len(candidates) < 2:
            return

        # Sort by ELO
        candidates.sort(key=lambda c: c.elo_rating)
        worst = candidates[0]
        best = candidates[-1]

        logger.info(
            f"Evolving {purpose}/{domain}: "
            f"worst ELO={worst.elo_rating:.0f}, "
            f"best ELO={best.elo_rating:.0f}"
        )

        # Step 1: Generate text gradient
        gradient = self._compute_text_gradient(worst, best)

        # Step 2: Apply gradient to create new prompt
        new_template = self._apply_text_gradient(worst, gradient)
        if not new_template or new_template == worst.template:
            return

        # Step 3: Create new candidate
        new_candidate = PromptCandidate(
            template=new_template,
            domain=domain,
            version=best.version + 1,
            parent_version=best.version,
            text_gradient=gradient.suggestion,
        )

        # Step 4: Replace worst if pool full
        if len(candidates) >= self.pool_size:
            candidates.remove(worst)
            logger.info(
                f"Replaced worst prompt (ELO={worst.elo_rating:.0f}) "
                f"with evolved version {new_candidate.version}"
            )

        candidates.append(new_candidate)

    def _compute_text_gradient(
        self,
        worse: PromptCandidate,
        better: PromptCandidate,
    ) -> TextGradient:
        """Generate a text gradient by comparing two prompts.

        APO core: LLM describes what makes the better prompt better.
        """
        prompt = (
            "Compare these two prompt templates. The second one performs "
            "better. Explain what makes it better and suggest specific "
            "improvements for the first one.\n\n"
            f"WORSE prompt (avg reward: {worse.avg_reward:.3f}):\n"
            f'"""{worse.template[:400]}"""\n\n'
            f"BETTER prompt (avg reward: {better.avg_reward:.3f}):\n"
            f'"""{better.template[:400]}"""\n\n'
            "Criticism of the worse prompt (1-2 sentences):\n"
        )

        try:
            response = self.generate_fn(prompt)
            parts = response.split("\n", 1)
            criticism = parts[0].strip() if parts else "Could be more specific"
            suggestion = parts[1].strip() if len(parts) > 1 else criticism

            return TextGradient(
                source_prompt=worse.template,
                criticism=criticism,
                suggestion=suggestion,
                confidence=0.6,
            )
        except Exception as e:
            logger.warning(f"Text gradient computation failed: {e}")
            return TextGradient(
                source_prompt=worse.template,
                criticism="Could not analyze",
                suggestion="Add more specificity and structure",
                confidence=0.3,
            )

    def _apply_text_gradient(
        self,
        candidate: PromptCandidate,
        gradient: TextGradient,
    ) -> str:
        """Apply a text gradient to produce an improved prompt.

        APO core: LLM edits the prompt based on the gradient.
        """
        prompt = (
            "Edit the following prompt template to address the criticism "
            "and apply the suggestion. Keep the same format with "
            "{variable} placeholders.\n\n"
            f"Current prompt:\n"
            f'"""{candidate.template[:500]}"""\n\n'
            f"Criticism: {gradient.criticism}\n"
            f"Suggestion: {gradient.suggestion}\n\n"
            "Improved prompt (keep {variable} placeholders):\n"
        )

        try:
            response = self.generate_fn(prompt)
            new_template = response.strip()

            # Sanity check: must contain at least one placeholder
            if "{" not in new_template:
                logger.warning("Evolved prompt missing placeholders, discarding")
                return ""

            # Sanity check: not too short or too long
            if len(new_template) < 20 or len(new_template) > 2000:
                logger.warning("Evolved prompt has bad length, discarding")
                return ""

            return new_template

        except Exception as e:
            logger.warning(f"Apply text gradient failed: {e}")
            return ""

    def update_elo(
        self,
        purpose: str,
        domain: str,
        winner_template: str,
        loser_template: str,
        k: float = 32.0,
    ) -> None:
        """Update ELO ratings after a head-to-head comparison."""
        candidates = self._get_candidates(purpose, domain)
        winner = next(
            (c for c in candidates if c.template == winner_template), None
        )
        loser = next(
            (c for c in candidates if c.template == loser_template), None
        )

        if not winner or not loser:
            return

        # Standard ELO update
        exp_w = 1 / (1 + 10 ** ((loser.elo_rating - winner.elo_rating) / 400))
        exp_l = 1 - exp_w

        winner.elo_rating += k * (1 - exp_w)
        loser.elo_rating += k * (0 - exp_l)

    def _get_candidates(
        self, purpose: str, domain: str
    ) -> List[PromptCandidate]:
        return self._pools.get(domain, {}).get(purpose, [])

    def _get_or_create_pool(
        self, purpose: str, domain: str
    ) -> List[PromptCandidate]:
        return self._pools.setdefault(domain, {}).setdefault(purpose, [])

    def get_stats(self) -> Dict[str, Any]:
        """Get prompt evolution statistics."""
        stats: Dict[str, Any] = {}
        for domain, purposes in self._pools.items():
            domain_stats: Dict[str, Any] = {}
            for purpose, candidates in purposes.items():
                domain_stats[purpose] = {
                    "pool_size": len(candidates),
                    "best_elo": max(
                        (c.elo_rating for c in candidates), default=1000
                    ),
                    "avg_reward": (
                        sum(c.avg_reward for c in candidates)
                        / max(len(candidates), 1)
                    ),
                    "total_uses": sum(c.total_uses for c in candidates),
                }
            stats[domain] = domain_stats
        return stats
