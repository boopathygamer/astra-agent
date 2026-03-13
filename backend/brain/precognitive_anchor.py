"""
Pre-Cognitive Anchor — Parallel Speculative Execution Engine
────────────────────────────────────────────────────────────
Expert-level speculative execution using real asyncio parallelism.
Forks multiple execution paths, tests each in a sandbox, and
collapses reality onto the best-performing timeline.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TIMELINES = 5
_DEFAULT_TIMEOUT = 10.0


@dataclass
class TimelineResult:
    """Result from a single speculative timeline."""
    timeline_id: int
    output: Any = None
    success: bool = False
    error: Optional[str] = None
    duration_ms: float = 0.0
    confidence: float = 0.0


@dataclass
class RealityCollapse:
    """Final result after selecting the best timeline."""
    selected_timeline: int
    result: Any
    timelines_run: int
    timelines_succeeded: int
    total_duration_ms: float


class PreCognitiveAnchor:
    """
    Tier 7: Pre-Cognitive Reality Anchoring

    Forks N parallel execution timelines using asyncio, runs each
    candidate solution concurrently, evaluates results, and selects
    the timeline with the highest confidence. Failed timelines are pruned.
    """

    def __init__(self, max_timelines: int = _DEFAULT_TIMELINES, timeout: float = _DEFAULT_TIMEOUT):
        self._max_timelines = max(2, max_timelines)
        self._timeout = max(1.0, timeout)
        self._collapses: int = 0
        logger.info("[PRE-COG] Speculative executor active (timelines=%d, timeout=%.1fs).",
                     self._max_timelines, self._timeout)

    async def _run_timeline(self, timeline_id: int, fn: Callable, *args, **kwargs) -> TimelineResult:
        """Execute a single speculative timeline."""
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(fn):
                output = await asyncio.wait_for(fn(*args, **kwargs), timeout=self._timeout)
            else:
                output = await asyncio.wait_for(
                    asyncio.to_thread(fn, *args, **kwargs),
                    timeout=self._timeout,
                )
            duration = (time.time() - start) * 1000
            return TimelineResult(
                timeline_id=timeline_id,
                output=output,
                success=True,
                duration_ms=duration,
                confidence=1.0 / (1.0 + duration / 1000),  # Faster = higher confidence
            )
        except asyncio.TimeoutError:
            return TimelineResult(
                timeline_id=timeline_id,
                success=False,
                error="Timeout exceeded",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return TimelineResult(
                timeline_id=timeline_id,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )

    async def anchor_best_reality(
        self,
        candidates: List[Callable],
        *args,
        scorer: Optional[Callable] = None,
        **kwargs,
    ) -> Optional[RealityCollapse]:
        """
        Fork multiple timelines, execute each candidate concurrently,
        and collapse onto the best-performing result.
        """
        start = time.time()
        num_timelines = min(len(candidates), self._max_timelines)

        if num_timelines == 0:
            logger.warning("[PRE-COG] No candidates to fork.")
            return None

        # Fork timelines
        tasks = [
            self._run_timeline(i, candidates[i], *args, **kwargs)
            for i in range(num_timelines)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful timelines
        timeline_results = [r for r in results if isinstance(r, TimelineResult)]
        successes = [r for r in timeline_results if r.success]

        if not successes:
            logger.error("[PRE-COG] All %d timelines failed. Reality collapse impossible.", num_timelines)
            return None

        # Select best timeline
        if scorer:
            best = max(successes, key=lambda r: scorer(r.output))
        else:
            best = max(successes, key=lambda r: r.confidence)

        total_duration = (time.time() - start) * 1000
        self._collapses += 1

        collapse = RealityCollapse(
            selected_timeline=best.timeline_id,
            result=best.output,
            timelines_run=num_timelines,
            timelines_succeeded=len(successes),
            total_duration_ms=total_duration,
        )
        logger.info(
            "[PRE-COG] Reality collapsed onto timeline %d (%d/%d succeeded, %.0fms).",
            best.timeline_id, len(successes), num_timelines, total_duration,
        )
        return collapse


# Global singleton — always active
precognitive_anchor = PreCognitiveAnchor()
