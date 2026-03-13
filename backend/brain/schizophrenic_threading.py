"""
Schizophrenic Threading — Divergent-Convergent Ideation Engine
──────────────────────────────────────────────────────────────
Expert-level creative ideation engine that generates multiple
divergent solution candidates asynchronously, then converges
on the best one using quality scoring and pruning.
"""

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Ideation:
    """A generated creative solution candidate."""
    id: int
    content: str
    quality_score: float = 0.0
    generation_time_ms: float = 0.0


@dataclass
class ConvergenceResult:
    """Result of divergent-convergent ideation."""
    best_idea: str
    candidates_generated: int
    candidates_surviving: int
    total_time_ms: float


class SchizophrenicSubSpace:
    """
    Tier 6: Divergent-Convergent Ideation Engine

    Generates N creative solution candidates concurrently using
    high-temperature LLM prompting, then scores and prunes them
    down to the most viable solution.
    """

    def __init__(self, generate_fn: Optional[Callable] = None, default_depth: int = 5):
        self._generate_fn = generate_fn
        self._default_depth = max(2, default_depth)
        self._total_ideations: int = 0
        self._genius_hits: int = 0
        logger.info("[IDEATION-ENGINE] Divergent-convergent engine active (depth=%d).", self._default_depth)

    async def _generate_candidate(self, problem: str, variant_id: int) -> Ideation:
        """Generate a single creative candidate."""
        start = time.time()

        if self._generate_fn:
            prompt = (
                f"Think creatively and propose an unconventional solution to this problem. "
                f"Be bold and innovative. Variant #{variant_id}.\n\n"
                f"PROBLEM: {problem}\n\n"
                f"Output ONLY your solution."
            )
            try:
                if asyncio.iscoroutinefunction(self._generate_fn):
                    content = await self._generate_fn(prompt)
                else:
                    content = await asyncio.to_thread(self._generate_fn, prompt)
            except Exception as e:
                content = f"[Generation failed: {e}]"
        else:
            # Stub candidate
            content = f"[Creative solution variant {variant_id} for: {problem[:50]}]"
            await asyncio.sleep(0.001)  # Simulate async work

        duration = (time.time() - start) * 1000
        return Ideation(id=variant_id, content=content, generation_time_ms=duration)

    def _score_candidate(self, candidate: Ideation) -> float:
        """Score a candidate based on heuristic quality metrics."""
        content = candidate.content
        score = 0.5  # Base score

        # Longer, more detailed solutions score higher
        if len(content) > 200:
            score += 0.1
        if len(content) > 500:
            score += 0.1

        # Code-containing solutions score higher for technical problems
        if "def " in content or "class " in content or "```" in content:
            score += 0.15

        # Solutions with structure score higher
        if "\n" in content and len(content.split("\n")) > 3:
            score += 0.1

        # Penalize error outputs
        if "[Generation failed" in content or "[FAILED" in content:
            score = 0.0

        return min(1.0, score)

    async def brute_force_creativity(self, problem: str, depth: Optional[int] = None) -> ConvergenceResult:
        """
        Generate N creative candidates, score them, and select the best.
        """
        depth = depth or self._default_depth
        start = time.time()

        # Divergent phase: generate candidates concurrently
        tasks = [self._generate_candidate(problem, i) for i in range(depth)]
        candidates = await asyncio.gather(*tasks)
        self._total_ideations += depth

        # Score all candidates
        for candidate in candidates:
            candidate.quality_score = self._score_candidate(candidate)

        # Convergent phase: select the best
        scored = sorted(candidates, key=lambda c: c.quality_score, reverse=True)
        best = scored[0] if scored else None
        surviving = [c for c in scored if c.quality_score > 0.3]

        total_time = (time.time() - start) * 1000

        if best and best.quality_score > 0.5:
            self._genius_hits += 1
            logger.info("[IDEATION-ENGINE] Best candidate scored %.2f (%d/%d survived, %.0fms).",
                        best.quality_score, len(surviving), depth, total_time)
        else:
            logger.warning("[IDEATION-ENGINE] No high-quality candidates from %d ideations.", depth)

        return ConvergenceResult(
            best_idea=best.content if best else "[No viable solution]",
            candidates_generated=depth,
            candidates_surviving=len(surviving),
            total_time_ms=total_time,
        )


# Global singleton — always active
schizo_engine = SchizophrenicSubSpace()
