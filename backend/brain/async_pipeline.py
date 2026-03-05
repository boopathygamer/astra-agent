"""
Adaptive Concurrency Pipeline — Async Thinking Stream
──────────────────────────────────────────────────────
Runs multiple reasoning paths concurrently and merges results.
Dynamically adjusts parallelism based on system load and stage completion times.

Architecture:
  PipelineOrchestrator  →  ConcurrencyStage[]  →  StreamMerger
  (topo-sort + schedule)   (async workers)        (confidence-vote)
"""

import asyncio
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result from a single pipeline stage."""
    stage_id: str
    output: Any = None
    confidence: float = 0.0
    duration_ms: float = 0.0
    status: StageStatus = StageStatus.PENDING
    error: str = ""
    retries: int = 0


@dataclass
class ConcurrencyStage:
    """A single stage in the concurrent pipeline."""
    stage_id: str
    name: str
    fn: Callable                          # (input_data) → Any
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: float = 30.0
    max_retries: int = 2
    estimated_latency_ms: float = 1000.0  # Expected execution time
    priority: int = 0                     # Higher = runs first among equals
    optional: bool = False                # Can pipeline continue without this?

    def __post_init__(self):
        if not self.stage_id:
            self.stage_id = self.name.lower().replace(" ", "_")


@dataclass
class MergedResult:
    """Result of merging multiple concurrent reasoning paths."""
    best_output: Any = None
    best_confidence: float = 0.0
    all_outputs: List[Tuple[Any, float]] = field(default_factory=list)
    consensus_score: float = 0.0        # How much outputs agree
    total_duration_ms: float = 0.0
    stages_completed: int = 0
    stages_failed: int = 0
    merge_strategy: str = ""


@dataclass 
class PipelineConfig:
    """Configuration for the adaptive pipeline."""
    max_workers: int = 4
    default_timeout: float = 30.0
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 3    # Consecutive failures before tripping
    adaptive_parallelism: bool = True
    min_workers: int = 1
    max_workers_cap: int = 8
    load_sample_window: int = 10          # Rolling window for load estimation


# ──────────────────────────────────────────────
# Stream Merger
# ──────────────────────────────────────────────

class StreamMerger:
    """
    Merges results from concurrent reasoning paths using
    confidence-weighted voting, consensus detection, and fallback selection.
    """

    def merge_by_confidence(self, results: List[StageResult]) -> MergedResult:
        """Select the highest-confidence result."""
        successful = [r for r in results if r.status == StageStatus.COMPLETED and r.output is not None]
        if not successful:
            return MergedResult(merge_strategy="none")

        best = max(successful, key=lambda r: r.confidence)
        return MergedResult(
            best_output=best.output,
            best_confidence=best.confidence,
            all_outputs=[(r.output, r.confidence) for r in successful],
            consensus_score=self._compute_consensus(successful),
            stages_completed=len(successful),
            stages_failed=sum(1 for r in results if r.status == StageStatus.FAILED),
            merge_strategy="confidence_max",
        )

    def merge_by_vote(self, results: List[StageResult]) -> MergedResult:
        """Merge using majority voting (for discrete outputs)."""
        successful = [r for r in results if r.status == StageStatus.COMPLETED]
        if not successful:
            return MergedResult(merge_strategy="none")

        # Group by output hash
        output_groups: Dict[str, List[StageResult]] = {}
        for r in successful:
            key = str(r.output)[:200]
            if key not in output_groups:
                output_groups[key] = []
            output_groups[key].append(r)

        # Find majority
        majority_key = max(output_groups, key=lambda k: len(output_groups[k]))
        majority_results = output_groups[majority_key]
        best = max(majority_results, key=lambda r: r.confidence)

        return MergedResult(
            best_output=best.output,
            best_confidence=best.confidence,
            all_outputs=[(r.output, r.confidence) for r in successful],
            consensus_score=len(majority_results) / len(successful),
            stages_completed=len(successful),
            stages_failed=sum(1 for r in results if r.status == StageStatus.FAILED),
            merge_strategy="majority_vote",
        )

    def merge_weighted(self, results: List[StageResult]) -> MergedResult:
        """Merge using confidence-weighted combination (for numeric outputs)."""
        successful = [r for r in results if r.status == StageStatus.COMPLETED]
        if not successful:
            return MergedResult(merge_strategy="none")

        total_confidence = sum(r.confidence for r in successful)
        if total_confidence == 0:
            return self.merge_by_confidence(results)

        # For string outputs, fall back to confidence max
        if isinstance(successful[0].output, str):
            return self.merge_by_confidence(results)

        # Weighted average for numeric outputs
        try:
            weighted_sum = sum(
                float(r.output) * r.confidence for r in successful
            )
            weighted_result = weighted_sum / total_confidence
            return MergedResult(
                best_output=weighted_result,
                best_confidence=total_confidence / len(successful),
                all_outputs=[(r.output, r.confidence) for r in successful],
                consensus_score=self._compute_consensus(successful),
                stages_completed=len(successful),
                merge_strategy="weighted_average",
            )
        except (TypeError, ValueError):
            return self.merge_by_confidence(results)

    @staticmethod
    def _compute_consensus(results: List[StageResult]) -> float:
        """Compute how much results agree (0=divergent, 1=unanimous)."""
        if len(results) <= 1:
            return 1.0
        outputs = [str(r.output)[:200] for r in results]
        unique = len(set(outputs))
        return 1.0 - (unique - 1) / len(results)


# ──────────────────────────────────────────────
# Pipeline Orchestrator
# ──────────────────────────────────────────────

class PipelineOrchestrator:
    """
    Manages topological ordering of stages, handles failures with
    circuit breakers, and dynamically adjusts parallelism.
    """

    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._circuit_breaker_counts: Dict[str, int] = {}
        self._latency_history: List[float] = []
        self._current_workers = self.config.max_workers
        self.merger = StreamMerger()

    def execute(
        self,
        stages: List[ConcurrencyStage],
        input_data: Any = None,
    ) -> Dict[str, StageResult]:
        """
        Execute all stages respecting dependencies.
        Independent stages run concurrently.
        """
        start_time = time.time()

        # Build dependency graph
        results: Dict[str, StageResult] = {}
        completed: Set[str] = set()

        # Topological ordering
        execution_order = self._topological_sort(stages)

        # Group by dependency level for concurrent execution
        levels = self._group_by_level(execution_order, stages)

        workers = self._adjust_workers()
        self._executor = ThreadPoolExecutor(max_workers=workers)

        try:
            for level_stages in levels:
                # All stages in a level can run concurrently
                futures: Dict[Future, ConcurrencyStage] = {}

                for stage in level_stages:
                    # Check circuit breaker
                    if self._is_circuit_broken(stage.stage_id):
                        results[stage.stage_id] = StageResult(
                            stage_id=stage.stage_id,
                            status=StageStatus.SKIPPED,
                            error="Circuit breaker open",
                        )
                        continue

                    # Gather inputs from dependencies
                    dep_outputs = {
                        dep_id: results[dep_id].output
                        for dep_id in stage.dependencies
                        if dep_id in results and results[dep_id].status == StageStatus.COMPLETED
                    }

                    # Check if required dependencies failed
                    missing_deps = [
                        dep_id for dep_id in stage.dependencies
                        if dep_id not in results or results[dep_id].status != StageStatus.COMPLETED
                    ]
                    if missing_deps and not stage.optional:
                        results[stage.stage_id] = StageResult(
                            stage_id=stage.stage_id,
                            status=StageStatus.SKIPPED,
                            error=f"Missing dependencies: {missing_deps}",
                        )
                        continue

                    # Submit to executor
                    stage_input = dep_outputs if dep_outputs else input_data
                    future = self._executor.submit(
                        self._execute_stage, stage, stage_input
                    )
                    futures[future] = stage

                # Collect results from this level
                for future in as_completed(futures, timeout=max(
                    s.timeout_seconds for s in level_stages
                ) if level_stages else 30):
                    stage = futures[future]
                    try:
                        result = future.result()
                        results[stage.stage_id] = result
                        completed.add(stage.stage_id)

                        # Track latency for adaptive sizing
                        self._latency_history.append(result.duration_ms)
                        if len(self._latency_history) > self.config.load_sample_window:
                            self._latency_history = self._latency_history[-self.config.load_sample_window:]

                    except Exception as e:
                        results[stage.stage_id] = StageResult(
                            stage_id=stage.stage_id,
                            status=StageStatus.FAILED,
                            error=str(e),
                        )
                        self._record_failure(stage.stage_id)

        finally:
            self._executor.shutdown(wait=False)
            self._executor = None

        total_ms = (time.time() - start_time) * 1000
        logger.info(
            f"🌊 Pipeline completed: {len(completed)}/{len(stages)} stages "
            f"in {total_ms:.0f}ms ({workers} workers)"
        )

        return results

    def execute_parallel_reasoning(
        self,
        reasoning_fns: List[Callable],
        input_data: Any = None,
        merge_strategy: str = "confidence",
    ) -> MergedResult:
        """
        Execute multiple reasoning approaches concurrently and merge results.
        Simplified interface for parallel hypothesis exploration.
        """
        stages = []
        for i, fn in enumerate(reasoning_fns):
            stages.append(ConcurrencyStage(
                stage_id=f"reasoning_{i}",
                name=f"Reasoning Path {i}",
                fn=fn,
                priority=i,
            ))

        results = self.execute(stages, input_data)
        stage_results = list(results.values())

        if merge_strategy == "vote":
            return self.merger.merge_by_vote(stage_results)
        elif merge_strategy == "weighted":
            return self.merger.merge_weighted(stage_results)
        else:
            return self.merger.merge_by_confidence(stage_results)

    def _execute_stage(self, stage: ConcurrencyStage, input_data: Any) -> StageResult:
        """Execute a single stage with retry logic."""
        for attempt in range(stage.max_retries + 1):
            start = time.time()
            try:
                output = stage.fn(input_data)
                duration_ms = (time.time() - start) * 1000

                confidence = 0.8
                if isinstance(output, dict) and "confidence" in output:
                    confidence = output["confidence"]
                elif isinstance(output, tuple) and len(output) == 2:
                    output, confidence = output

                # Reset circuit breaker on success
                self._circuit_breaker_counts.pop(stage.stage_id, None)

                return StageResult(
                    stage_id=stage.stage_id,
                    output=output,
                    confidence=confidence,
                    duration_ms=duration_ms,
                    status=StageStatus.COMPLETED,
                    retries=attempt,
                )
            except Exception as e:
                if attempt >= stage.max_retries:
                    return StageResult(
                        stage_id=stage.stage_id,
                        status=StageStatus.FAILED,
                        error=str(e),
                        duration_ms=(time.time() - start) * 1000,
                        retries=attempt,
                    )
                logger.debug(f"  Stage '{stage.name}' retry {attempt + 1}: {e}")

        return StageResult(stage_id=stage.stage_id, status=StageStatus.FAILED)

    def _topological_sort(self, stages: List[ConcurrencyStage]) -> List[str]:
        """Topological sort of stages based on dependencies."""
        graph = {s.stage_id: set(s.dependencies) for s in stages}
        result = []
        visited = set()

        def visit(node):
            if node in visited:
                return
            visited.add(node)
            for dep in graph.get(node, set()):
                visit(dep)
            result.append(node)

        for stage in stages:
            visit(stage.stage_id)

        return result

    def _group_by_level(
        self,
        sorted_ids: List[str],
        stages: List[ConcurrencyStage],
    ) -> List[List[ConcurrencyStage]]:
        """Group stages by dependency level for concurrent execution."""
        stage_map = {s.stage_id: s for s in stages}
        levels: List[List[ConcurrencyStage]] = []
        placed = set()

        while len(placed) < len(sorted_ids):
            level = []
            for sid in sorted_ids:
                if sid in placed:
                    continue
                stage = stage_map.get(sid)
                if not stage:
                    placed.add(sid)
                    continue
                # Can place if all dependencies are placed
                if all(d in placed for d in stage.dependencies):
                    level.append(stage)

            for s in level:
                placed.add(s.stage_id)

            if level:
                levels.append(level)
            elif len(placed) < len(sorted_ids):
                # Circular dependency — break by adding remaining
                remaining = [stage_map[s] for s in sorted_ids if s not in placed and s in stage_map]
                if remaining:
                    levels.append(remaining)
                break

        return levels

    def _adjust_workers(self) -> int:
        """Dynamically adjust worker count based on recent latencies."""
        if not self.config.adaptive_parallelism or not self._latency_history:
            return self.config.max_workers

        avg_latency = sum(self._latency_history) / len(self._latency_history)

        # If stages are fast, fewer workers suffice
        if avg_latency < 100:
            self._current_workers = max(self.config.min_workers, self._current_workers - 1)
        elif avg_latency > 2000:
            # Slow stages benefit from more parallelism
            self._current_workers = min(self.config.max_workers_cap, self._current_workers + 1)

        return self._current_workers

    def _is_circuit_broken(self, stage_id: str) -> bool:
        if not self.config.enable_circuit_breaker:
            return False
        return self._circuit_breaker_counts.get(stage_id, 0) >= self.config.circuit_breaker_threshold

    def _record_failure(self, stage_id: str):
        self._circuit_breaker_counts[stage_id] = self._circuit_breaker_counts.get(stage_id, 0) + 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "current_workers": self._current_workers,
            "circuit_breakers": dict(self._circuit_breaker_counts),
            "avg_latency_ms": (
                sum(self._latency_history) / len(self._latency_history)
                if self._latency_history else 0
            ),
        }
