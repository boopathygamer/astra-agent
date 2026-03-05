"""
Trace Store — Structured Span System for Self-Improvement.
Inspired by Microsoft Agent Lightning's span/store architecture.

Every thinking step emits typed TraceSpans into a TrajectoryTrace.
The LearningStore persists trajectories for credit assignment,
prompt evolution, and continuous learning.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpanType(Enum):
    """Types of spans emitted during problem-solving."""
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    REASONING = "reasoning"
    VERIFICATION = "verification"
    REWARD = "reward"
    HYPOTHESIS = "hypothesis"
    METACOGNITION = "metacognition"
    CLASSIFICATION = "classification"
    RISK_ASSESSMENT = "risk_assessment"


@dataclass
class TraceSpan:
    """A single structured span — one atomic step in problem-solving.

    Inspired by Agent Lightning's Span type, but enriched with
    our cognitive architecture metadata.
    """
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    parent_id: Optional[str] = None
    span_type: SpanType = SpanType.LLM_CALL

    # Content
    input_data: str = ""
    output_data: str = ""
    prompt_template: str = ""       # Track which prompt was used

    # Reward (filled during credit assignment)
    reward: float = 0.0
    reward_dimensions: Dict[str, float] = field(default_factory=dict)

    # Timing
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    # Metadata
    attributes: Dict[str, Any] = field(default_factory=dict)
    cognitive_mode: str = ""        # Which reasoning mode was active
    iteration: int = 0              # Which thinking loop iteration
    was_helpful: Optional[bool] = None  # Set by credit assignment

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "span_type": self.span_type.value,
            "input_data": self.input_data[:500],
            "output_data": self.output_data[:500],
            "prompt_template": self.prompt_template[:200],
            "reward": self.reward,
            "reward_dimensions": self.reward_dimensions,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "attributes": {k: str(v)[:200] for k, v in self.attributes.items()},
            "cognitive_mode": self.cognitive_mode,
            "iteration": self.iteration,
            "was_helpful": self.was_helpful,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TraceSpan":
        span = cls()
        span.span_id = d.get("span_id", span.span_id)
        span.parent_id = d.get("parent_id")
        span.span_type = SpanType(d.get("span_type", "llm_call"))
        span.input_data = d.get("input_data", "")
        span.output_data = d.get("output_data", "")
        span.prompt_template = d.get("prompt_template", "")
        span.reward = d.get("reward", 0.0)
        span.reward_dimensions = d.get("reward_dimensions", {})
        span.timestamp = d.get("timestamp", 0.0)
        span.duration_ms = d.get("duration_ms", 0.0)
        span.attributes = d.get("attributes", {})
        span.cognitive_mode = d.get("cognitive_mode", "")
        span.iteration = d.get("iteration", 0)
        span.was_helpful = d.get("was_helpful")
        return span


@dataclass
class TrajectoryTrace:
    """A complete problem-solving episode — ordered list of spans.

    Like Agent Lightning's Rollout, but for our cognitive architecture.
    """
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    problem: str = ""
    domain: str = "general"

    # Ordered spans
    spans: List[TraceSpan] = field(default_factory=list)

    # Outcome
    final_answer: str = ""
    final_reward: float = 0.0
    reward_dimensions: Dict[str, float] = field(default_factory=dict)
    success: bool = False
    gating_mode: str = "refuse"     # execute / sandbox / refuse

    # Strategy metadata
    strategies_used: List[str] = field(default_factory=list)
    total_iterations: int = 0
    total_duration_ms: float = 0.0

    # Timestamps
    created_at: float = field(default_factory=time.time)

    def add_span(self, span: TraceSpan) -> None:
        """Add a span and auto-set its iteration."""
        span.iteration = len(self.spans)
        self.spans.append(span)

    def get_spans_by_type(self, span_type: SpanType) -> List[TraceSpan]:
        return [s for s in self.spans if s.span_type == span_type]

    def get_llm_calls(self) -> List[TraceSpan]:
        return self.get_spans_by_type(SpanType.LLM_CALL)

    def get_reward_spans(self) -> List[TraceSpan]:
        return self.get_spans_by_type(SpanType.REWARD)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "problem": self.problem[:500],
            "domain": self.domain,
            "spans": [s.to_dict() for s in self.spans],
            "final_answer": self.final_answer[:500],
            "final_reward": self.final_reward,
            "reward_dimensions": self.reward_dimensions,
            "success": self.success,
            "gating_mode": self.gating_mode,
            "strategies_used": self.strategies_used,
            "total_iterations": self.total_iterations,
            "total_duration_ms": self.total_duration_ms,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrajectoryTrace":
        trace = cls()
        trace.trace_id = d.get("trace_id", trace.trace_id)
        trace.problem = d.get("problem", "")
        trace.domain = d.get("domain", "general")
        trace.spans = [TraceSpan.from_dict(s) for s in d.get("spans", [])]
        trace.final_answer = d.get("final_answer", "")
        trace.final_reward = d.get("final_reward", 0.0)
        trace.reward_dimensions = d.get("reward_dimensions", {})
        trace.success = d.get("success", False)
        trace.gating_mode = d.get("gating_mode", "refuse")
        trace.strategies_used = d.get("strategies_used", [])
        trace.total_iterations = d.get("total_iterations", 0)
        trace.total_duration_ms = d.get("total_duration_ms", 0.0)
        trace.created_at = d.get("created_at", 0.0)
        return trace


class LearningStore:
    """Central hub for persisting trajectory data, resources, and learning history.

    Inspired by Agent Lightning's LightningStore, adapted for local
    file-based persistence with our cognitive architecture.
    """

    def __init__(self, store_dir: str = "data/learning_store"):
        self.store_dir = Path(store_dir)
        self.traces_dir = self.store_dir / "traces"
        self.resources_dir = self.store_dir / "resources"
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self.resources_dir.mkdir(parents=True, exist_ok=True)

        # In-memory index for fast lookup
        self._trace_index: Dict[str, dict] = {}  # trace_id -> metadata
        self._load_index()

    def _load_index(self) -> None:
        """Load trace index from disk."""
        index_path = self.store_dir / "trace_index.json"
        if index_path.exists():
            try:
                with open(index_path, "r") as f:
                    self._trace_index = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._trace_index = {}

    def _save_index(self) -> None:
        """Persist trace index to disk."""
        index_path = self.store_dir / "trace_index.json"
        with open(index_path, "w") as f:
            json.dump(self._trace_index, f, indent=2)

    def store_trajectory(self, trace: TrajectoryTrace) -> None:
        """Persist a complete trajectory trace.

        Like AGL's add_span + update_attempt, but for full trajectories.
        """
        trace_path = self.traces_dir / f"{trace.trace_id}.json"
        with open(trace_path, "w") as f:
            json.dump(trace.to_dict(), f, indent=2)

        # Update index
        self._trace_index[trace.trace_id] = {
            "domain": trace.domain,
            "reward": trace.final_reward,
            "success": trace.success,
            "strategies": trace.strategies_used,
            "created_at": trace.created_at,
            "num_spans": len(trace.spans),
        }
        self._save_index()
        logger.info(
            f"Stored trajectory {trace.trace_id}: "
            f"domain={trace.domain}, reward={trace.final_reward:.3f}, "
            f"spans={len(trace.spans)}"
        )

    def get_trajectory(self, trace_id: str) -> Optional[TrajectoryTrace]:
        """Retrieve a specific trajectory by ID."""
        trace_path = self.traces_dir / f"{trace_id}.json"
        if not trace_path.exists():
            return None
        with open(trace_path, "r") as f:
            return TrajectoryTrace.from_dict(json.load(f))

    def query_trajectories(
        self,
        domain: Optional[str] = None,
        min_reward: float = 0.0,
        success_only: bool = False,
        limit: int = 50,
    ) -> List[TrajectoryTrace]:
        """Query trajectories matching criteria.

        Like AGL's query_spans + query_rollouts.
        """
        matching_ids = []
        for tid, meta in self._trace_index.items():
            if domain and meta.get("domain") != domain:
                continue
            if meta.get("reward", 0) < min_reward:
                continue
            if success_only and not meta.get("success", False):
                continue
            matching_ids.append((tid, meta.get("reward", 0)))

        # Sort by reward descending, take top N
        matching_ids.sort(key=lambda x: x[1], reverse=True)
        matching_ids = matching_ids[:limit]

        traces = []
        for tid, _ in matching_ids:
            trace = self.get_trajectory(tid)
            if trace:
                traces.append(trace)
        return traces

    def get_stats(self) -> Dict[str, Any]:
        """Get learning store statistics."""
        total = len(self._trace_index)
        if total == 0:
            return {"total_traces": 0}

        rewards = [m.get("reward", 0) for m in self._trace_index.values()]
        successes = sum(1 for m in self._trace_index.values() if m.get("success"))
        domains = {}
        for m in self._trace_index.values():
            d = m.get("domain", "general")
            domains[d] = domains.get(d, 0) + 1

        return {
            "total_traces": total,
            "success_rate": successes / total,
            "avg_reward": sum(rewards) / total,
            "max_reward": max(rewards),
            "domains": domains,
        }

    def store_resource(self, name: str, data: Any) -> None:
        """Store a learning resource (prompt template, weights, etc.).

        Like AGL's add_resources.
        """
        path = self.resources_dir / f"{name}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_resource(self, name: str) -> Optional[Any]:
        """Retrieve a learning resource."""
        path = self.resources_dir / f"{name}.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)


def emit_span(
    span_type: SpanType,
    input_data: str = "",
    output_data: str = "",
    reward: float = 0.0,
    cognitive_mode: str = "",
    attributes: Optional[Dict[str, Any]] = None,
    parent_id: Optional[str] = None,
    prompt_template: str = "",
) -> TraceSpan:
    """Create a TraceSpan — the primary emit helper.

    Inspired by Agent Lightning's emit_reward() but generalized
    to all span types with cognitive metadata.
    """
    span = TraceSpan(
        span_type=span_type,
        input_data=input_data,
        output_data=output_data,
        reward=reward,
        cognitive_mode=cognitive_mode,
        attributes=attributes or {},
        parent_id=parent_id,
        prompt_template=prompt_template,
    )
    logger.debug(
        f"Emitted span {span.span_id}: type={span_type.value}, "
        f"mode={cognitive_mode}"
    )
    return span
