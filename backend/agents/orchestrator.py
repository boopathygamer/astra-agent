"""
Agent Orchestrator — Production-Grade Multi-Agent Coordination Engine
═════════════════════════════════════════════════════════════════════════
The central nervous system for multi-agent workflows. Decomposes complex
tasks, assigns them to specialized agents, coordinates execution across
four distinct orchestration strategies, and synthesizes the final output.

Strategies:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  SWARM        Parallel fan-out → merge (for independent sub-tasks) │
  │  PIPELINE     Sequential chain A → B → C (data flows forward)     │
  │  HIERARCHY    Manager decomposes → workers execute → manager merges│
  │  DEBATE       Adversarial: Draft → Critique → Synthesize (quality) │
  └─────────────────────────────────────────────────────────────────────┘

Safety:
  - Every spawned agent is Justice Court-reviewed via AgentForge
  - Circuit breaker halts runaway orchestrations (max depth, max agents)
  - Timeout enforcement per agent and per orchestration
  - Full telemetry: traces, metrics, and structured logs

Architecture:
  Orchestrator
    ├── StrategyRouter       (auto-selects best strategy)
    ├── TaskDecomposer       (LLM-powered task splitting)
    ├── AgentPool            (manages agent lifecycle)
    ├── ResultAggregator     (merges partial results)
    └── CircuitBreaker       (safety limits)
"""

import json
import logging
import time
import uuid
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from telemetry.metrics import MetricsCollector
from telemetry.tracer import SpanTracer

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Enums & Constants
# ══════════════════════════════════════════════════════════════════════

class OrchestratorStrategy(Enum):
    """Available orchestration strategies."""
    SWARM = "swarm"           # Parallel fan-out → merge
    PIPELINE = "pipeline"     # Sequential chain A → B → C
    HIERARCHY = "hierarchy"   # Manager decomposes → workers → manager merges
    DEBATE = "debate"         # Adversarial: Draft → Critique → Synthesize
    AUTO = "auto"             # Auto-select based on task analysis


class AgentRole(Enum):
    """Canonical agent roles for task assignment."""
    ARCHITECT = "architect"
    CODER = "coder"
    REVIEWER = "reviewer"
    RESEARCHER = "researcher"
    SECURITY = "security"
    ANALYST = "analyst"
    WRITER = "writer"
    MANAGER = "manager"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"
    DYNAMIC = "dynamic"


class TaskStatus(Enum):
    """Sub-task lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


# ── Safety Limits ──
MAX_ORCHESTRATION_DEPTH = 3       # Prevent recursive orchestration bombs
MAX_AGENTS_PER_ORCHESTRATION = 8  # Hard ceiling on parallel agents
MAX_ORCHESTRATION_TIMEOUT_S = 600 # 10-minute hard timeout
DEFAULT_AGENT_TIMEOUT_S = 120     # 2-minute per-agent timeout


# ══════════════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════════════

@dataclass
class SubTask:
    """A decomposed unit of work assigned to a specific agent."""
    task_id: str = ""
    role: AgentRole = AgentRole.CODER
    description: str = ""
    context: str = ""
    priority: int = 1
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: str = ""

    def __post_init__(self):
        if not self.task_id:
            self.task_id = f"sub_{uuid.uuid4().hex[:8]}"


@dataclass
class AgentResult:
    """Output from a single agent after processing its sub-task."""
    task_id: str = ""
    role: AgentRole = AgentRole.CODER
    output: str = ""
    confidence: float = 0.0
    artifacts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""
    token_estimate: int = 0


@dataclass
class OrchestrationResult:
    """Final output from the full orchestration pipeline."""
    orchestration_id: str = ""
    strategy: OrchestratorStrategy = OrchestratorStrategy.AUTO
    original_task: str = ""
    final_output: str = ""
    agent_results: List[AgentResult] = field(default_factory=list)
    agents_used: int = 0
    total_duration_ms: float = 0.0
    confidence: float = 0.0
    decomposition_trace: str = ""
    merge_trace: str = ""
    circuit_breaker_triggered: bool = False
    error: str = ""

    @property
    def success(self) -> bool:
        return bool(self.final_output) and not self.error

    def summary(self) -> str:
        """Human-readable summary of the orchestration."""
        lines = [
            f"═══ Orchestration Complete ═══",
            f"  ID:         {self.orchestration_id}",
            f"  Strategy:   {self.strategy.value}",
            f"  Agents:     {self.agents_used}",
            f"  Confidence: {self.confidence:.1%}",
            f"  Duration:   {self.total_duration_ms:.0f}ms",
        ]
        for r in self.agent_results:
            status = "✅" if r.success else "❌"
            lines.append(
                f"  {status} [{r.role.value}] conf={r.confidence:.2f} "
                f"dur={r.duration_ms:.0f}ms"
            )
        if self.error:
            lines.append(f"  ⚠️ Error: {self.error}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
# Circuit Breaker — Prevents runaway orchestration
# ══════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Enforces safety limits on orchestration depth, agent count,
    and total wall-clock time.

    Tracks:
      - Current recursion depth (nested orchestrations)
      - Total agents spawned in this orchestration tree
      - Wall-clock start time for timeout enforcement
    """

    def __init__(
        self,
        max_depth: int = MAX_ORCHESTRATION_DEPTH,
        max_agents: int = MAX_AGENTS_PER_ORCHESTRATION,
        max_timeout_s: float = MAX_ORCHESTRATION_TIMEOUT_S,
    ):
        self.max_depth = max_depth
        self.max_agents = max_agents
        self.max_timeout_s = max_timeout_s
        self._current_depth: int = 0
        self._total_agents: int = 0
        self._start_time: float = 0.0
        self._tripped: bool = False
        self._trip_reason: str = ""

    def enter(self) -> bool:
        """Enter a new orchestration level. Returns False if tripped."""
        if self._start_time == 0.0:
            self._start_time = time.time()

        self._current_depth += 1

        if self._current_depth > self.max_depth:
            self._trip("max_depth", f"Depth {self._current_depth} > {self.max_depth}")
            return False

        if self._is_timed_out():
            self._trip("timeout", f"Exceeded {self.max_timeout_s}s timeout")
            return False

        return True

    def exit(self):
        """Exit an orchestration level."""
        self._current_depth = max(0, self._current_depth - 1)

    def register_agent(self) -> bool:
        """Register a new agent spawn. Returns False if limit reached."""
        self._total_agents += 1
        if self._total_agents > self.max_agents:
            self._trip(
                "max_agents",
                f"Agents {self._total_agents} > {self.max_agents}"
            )
            return False
        if self._is_timed_out():
            self._trip("timeout", f"Exceeded {self.max_timeout_s}s timeout")
            return False
        return True

    def check(self) -> bool:
        """Check if the circuit breaker is still healthy."""
        if self._tripped:
            return False
        if self._is_timed_out():
            self._trip("timeout", f"Exceeded {self.max_timeout_s}s timeout")
            return False
        return True

    @property
    def is_tripped(self) -> bool:
        return self._tripped

    @property
    def trip_reason(self) -> str:
        return self._trip_reason

    def _trip(self, reason_code: str, message: str):
        self._tripped = True
        self._trip_reason = f"[{reason_code}] {message}"
        logger.error(f"🔴 Circuit Breaker TRIPPED: {self._trip_reason}")

    def _is_timed_out(self) -> bool:
        if self._start_time == 0.0:
            return False
        return (time.time() - self._start_time) > self.max_timeout_s

    def reset(self):
        """Reset the breaker for a new orchestration tree."""
        self._current_depth = 0
        self._total_agents = 0
        self._start_time = 0.0
        self._tripped = False
        self._trip_reason = ""


# ══════════════════════════════════════════════════════════════════════
# Role Prompt Library — Expert-Level System Prompts for Each Role
# ══════════════════════════════════════════════════════════════════════

ROLE_PROMPTS: Dict[AgentRole, str] = {
    AgentRole.ARCHITECT: (
        "You are the MASTER ARCHITECT. You design systems with surgical precision. "
        "Focus on: component boundaries, data flow, API contracts, scalability, "
        "and fault-tolerance patterns. Output clean, structured design documents. "
        "Think in terms of invariants and failure modes."
    ),
    AgentRole.CODER: (
        "You are the MASTER CODER. Write production-quality code with zero shortcuts. "
        "Follow defensive programming: validate inputs, handle edge cases, write "
        "docstrings, type-hint everything. Prefer composition over inheritance. "
        "Every function should do one thing perfectly."
    ),
    AgentRole.REVIEWER: (
        "You are the MASTER CODE REVIEWER. Perform a ruthless quality review. "
        "Check for: security vulnerabilities, race conditions, resource leaks, "
        "error handling gaps, API misuse, and performance anti-patterns. "
        "Provide specific, actionable feedback with line references."
    ),
    AgentRole.RESEARCHER: (
        "You are the MASTER RESEARCHER. Conduct exhaustive analysis with primary "
        "source verification. Structure findings with evidence chains. "
        "Distinguish facts from inferences. Quantify uncertainty. "
        "Cite methodologies and provide confidence intervals."
    ),
    AgentRole.SECURITY: (
        "You are the MASTER SECURITY AUDITOR. Analyze through the lens of OWASP Top 10, "
        "STRIDE threat modeling, and defense-in-depth. Identify attack surfaces, "
        "trust boundaries, and data flow risks. Rate each finding by CVSS. "
        "Provide remediation patches, not just findings."
    ),
    AgentRole.ANALYST: (
        "You are the MASTER ANALYST. Decompose complex problems into measurable "
        "components. Use frameworks: MECE, root-cause analysis, decision matrices. "
        "Quantify trade-offs with expected-value calculations. "
        "Present findings in tables and ranked recommendations."
    ),
    AgentRole.WRITER: (
        "You are the MASTER TECHNICAL WRITER. Write clear, precise documentation "
        "that engineers actually read. Use progressive disclosure: summary first, "
        "then details. Include examples for every concept. Tables for comparisons. "
        "Mermaid diagrams for architecture. Zero ambiguity."
    ),
    AgentRole.MANAGER: (
        "You are the ORCHESTRATION MANAGER. Your role is to decompose complex tasks "
        "into well-defined sub-tasks, assign them to the appropriate specialist, "
        "and synthesize the results. Think about task dependencies, parallelism "
        "opportunities, and risk mitigation strategies."
    ),
    AgentRole.CRITIC: (
        "You are the RUTHLESS CRITIC. Your sole purpose is to find flaws, gaps, "
        "logical errors, and weaknesses in the provided solution. Be adversarial. "
        "Check assumptions, edge cases, performance under load, and failure modes. "
        "Do not provide solutions — only catalog defects with severity ratings."
    ),
    AgentRole.SYNTHESIZER: (
        "You are the CHIEF SYNTHESIZER. Given multiple inputs — a draft, a critique, "
        "research findings, or partial results — you merge them into a single, "
        "coherent, perfected output. Resolve contradictions. Incorporate all valid "
        "feedback. The output must be strictly better than any single input."
    ),
}


# ══════════════════════════════════════════════════════════════════════
# Strategy Router — Auto-Selects the Optimal Orchestration Strategy
# ══════════════════════════════════════════════════════════════════════

# Keywords that hint at which strategy to use
_STRATEGY_SIGNALS: Dict[OrchestratorStrategy, List[str]] = {
    OrchestratorStrategy.SWARM: [
        "research", "analyze", "investigate", "compare", "evaluate",
        "study", "survey", "explore", "brainstorm", "multiple perspectives",
    ],
    OrchestratorStrategy.PIPELINE: [
        "step by step", "workflow", "pipeline", "process", "transform",
        "convert", "migrate", "first then", "after that", "sequence",
    ],
    OrchestratorStrategy.HIERARCHY: [
        "complex", "large", "comprehensive", "system", "architecture",
        "full stack", "end-to-end", "complete", "build", "implement",
    ],
    OrchestratorStrategy.DEBATE: [
        "review", "audit", "critique", "validate", "verify",
        "improve", "optimize", "refine", "perfect", "quality",
    ],
}


def auto_select_strategy(task: str, generate_fn: Callable = None) -> OrchestratorStrategy:
    """
    Auto-select the best orchestration strategy for a given task.

    Uses a two-phase approach:
      1. Fast keyword heuristic scan
      2. LLM-based classification (if available and heuristic is ambiguous)
    """
    task_lower = task.lower()

    # Phase 1: Keyword scoring
    scores: Dict[OrchestratorStrategy, float] = {}
    for strategy, keywords in _STRATEGY_SIGNALS.items():
        score = sum(1.0 for kw in keywords if kw in task_lower)
        scores[strategy] = score

    max_score = max(scores.values()) if scores else 0
    if max_score == 0:
        # Default to HIERARCHY for complex tasks, SWARM for research
        return OrchestratorStrategy.HIERARCHY

    # Check for clear winner (2x the runner-up)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_scores) >= 2:
        best, second = sorted_scores[0], sorted_scores[1]
        if best[1] >= 2 * max(second[1], 1):
            return best[0]

    # Phase 2: LLM classification if heuristic is ambiguous
    if generate_fn and sorted_scores[0][1] == sorted_scores[1][1]:
        return _llm_classify_strategy(task, generate_fn)

    return sorted_scores[0][0]


def _llm_classify_strategy(task: str, generate_fn: Callable) -> OrchestratorStrategy:
    """Use the LLM to classify the optimal strategy."""
    prompt = (
        "Classify this task into exactly ONE orchestration strategy.\n\n"
        "Strategies:\n"
        "  SWARM     — Multiple agents work independently in parallel, results merged\n"
        "  PIPELINE  — Agents work sequentially, each building on the previous output\n"
        "  HIERARCHY — A manager decomposes the task, workers execute, manager merges\n"
        "  DEBATE    — Draft → Critique → Synthesize (adversarial quality improvement)\n\n"
        f"Task: {task[:500]}\n\n"
        "Respond with ONLY one word: SWARM, PIPELINE, HIERARCHY, or DEBATE."
    )
    try:
        response = generate_fn(prompt).strip().upper()
        for strategy in OrchestratorStrategy:
            if strategy.value.upper() in response:
                return strategy
    except Exception as e:
        logger.warning(f"LLM strategy classification failed: {e}")

    return OrchestratorStrategy.HIERARCHY


# ══════════════════════════════════════════════════════════════════════
# Task Decomposer — LLM-Powered Task Splitting
# ══════════════════════════════════════════════════════════════════════

class TaskDecomposer:
    """
    Decomposes a complex task into structured sub-tasks with role
    assignments, priorities, and dependency chains.
    """

    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn

    def decompose(
        self,
        task: str,
        strategy: OrchestratorStrategy,
        max_subtasks: int = 5,
    ) -> List[SubTask]:
        """
        Decompose a task into sub-tasks appropriate for the strategy.

        Args:
            task: The complex task description
            strategy: The orchestration strategy to optimize for
            max_subtasks: Maximum number of sub-tasks to generate

        Returns:
            List of SubTask objects with role assignments
        """
        available_roles = [r.value for r in AgentRole if r != AgentRole.DYNAMIC]

        prompt = (
            f"Decompose this task into {max_subtasks} or fewer sub-tasks.\n\n"
            f"TASK: {task[:800]}\n\n"
            f"STRATEGY: {strategy.value}\n"
            f"{'(Sub-tasks will run IN PARALLEL — make them independent)' if strategy == OrchestratorStrategy.SWARM else ''}"
            f"{'(Sub-tasks will run SEQUENTIALLY — each builds on the previous)' if strategy == OrchestratorStrategy.PIPELINE else ''}"
            f"{'(A manager assigns sub-tasks to workers)' if strategy == OrchestratorStrategy.HIERARCHY else ''}"
            f"{'(Three phases: Draft, Critique, Synthesize)' if strategy == OrchestratorStrategy.DEBATE else ''}\n\n"
            f"Available roles: {available_roles}\n\n"
            f"Output a JSON array of objects, each with:\n"
            f'{{"role": "role_name", "description": "what this agent should do", '
            f'"priority": 1, "depends_on": []}}\n\n'
            f"Rules:\n"
            f"- Priority 1 = highest priority\n"
            f"- depends_on contains indices (0-based) of sub-tasks this depends on\n"
            f"- For SWARM: no dependencies, all priority 1\n"
            f"- For PIPELINE: chain dependencies (task 1 depends on 0, etc.)\n"
            f"- For DEBATE: exactly 3 tasks (draft, critique, synthesize)\n"
            f"- Output ONLY the JSON array, no markdown or explanation\n"
        )

        try:
            raw = self.generate_fn(prompt)
            json_str = self._extract_json_array(raw)
            items = json.loads(json_str)

            subtasks = []
            for i, item in enumerate(items[:max_subtasks]):
                role_str = item.get("role", "coder").lower()
                role = self._parse_role(role_str)

                depends = item.get("depends_on", [])
                # Convert integer dependencies to task IDs (will be resolved later)
                dep_indices = [
                    int(d) for d in depends
                    if isinstance(d, int) and 0 <= d < i
                ]

                subtasks.append(SubTask(
                    role=role,
                    description=item.get("description", ""),
                    priority=int(item.get("priority", i + 1)),
                    depends_on=[],  # Resolved after all tasks IDs are created
                    context=task,
                ))

            # Resolve dependency indices → task IDs
            for i, st in enumerate(subtasks):
                raw_item = items[i] if i < len(items) else {}
                deps = raw_item.get("depends_on", [])
                for d in deps:
                    if isinstance(d, int) and 0 <= d < len(subtasks):
                        st.depends_on.append(subtasks[d].task_id)

            return subtasks

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"Task decomposition JSON parse failed: {e}")
            return self._fallback_decompose(task, strategy)

    def _fallback_decompose(
        self, task: str, strategy: OrchestratorStrategy
    ) -> List[SubTask]:
        """Deterministic fallback when LLM decomposition fails."""
        if strategy == OrchestratorStrategy.DEBATE:
            return [
                SubTask(role=AgentRole.CODER, description=f"Draft solution: {task}", priority=1),
                SubTask(role=AgentRole.CRITIC, description="Critique the draft solution", priority=2),
                SubTask(role=AgentRole.SYNTHESIZER, description="Synthesize final solution", priority=3),
            ]
        elif strategy == OrchestratorStrategy.PIPELINE:
            return [
                SubTask(role=AgentRole.RESEARCHER, description=f"Research: {task}", priority=1),
                SubTask(role=AgentRole.ARCHITECT, description="Design solution based on research", priority=2),
                SubTask(role=AgentRole.CODER, description="Implement the design", priority=3),
            ]
        else:  # SWARM or HIERARCHY
            return [
                SubTask(role=AgentRole.RESEARCHER, description=f"Research aspects of: {task}", priority=1),
                SubTask(role=AgentRole.ANALYST, description=f"Analyze implications of: {task}", priority=1),
                SubTask(role=AgentRole.CODER, description=f"Draft implementation for: {task}", priority=1),
            ]

    def _extract_json_array(self, raw: str) -> str:
        """Extract JSON array from LLM response, handling markdown fences."""
        raw = raw.strip()
        if "```" in raw:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                return raw[start:end]
        if raw.startswith("["):
            return raw
        # Try to find embedded array
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            return raw[start:end]
        return "[]"

    def _parse_role(self, role_str: str) -> AgentRole:
        """Parse a role string to AgentRole enum."""
        for role in AgentRole:
            if role.value == role_str:
                return role
        # Fuzzy matching
        for role in AgentRole:
            if role_str in role.value or role.value in role_str:
                return role
        return AgentRole.CODER


# ══════════════════════════════════════════════════════════════════════
# Result Aggregator — Merges Partial Results into Final Output
# ══════════════════════════════════════════════════════════════════════

class ResultAggregator:
    """
    Merges outputs from multiple agents into a single coherent response.

    Strategies:
      - Concatenation with headers (fast, for research tasks)
      - LLM-powered synthesis (highest quality, for final answers)
      - Confidence-weighted selection (for competing answers)
    """

    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn

    def merge(
        self,
        task: str,
        results: List[AgentResult],
        strategy: OrchestratorStrategy,
    ) -> Tuple[str, float]:
        """
        Merge agent results into a single output.

        Returns:
            Tuple of (merged_output, confidence_score)
        """
        if not results:
            return "No results to merge.", 0.0

        successful = [r for r in results if r.success]
        if not successful:
            error_summary = "; ".join(r.error for r in results if r.error)
            return f"All agents failed: {error_summary}", 0.0

        # Single result — return directly
        if len(successful) == 1:
            return successful[0].output, successful[0].confidence

        # For PIPELINE — the last result IS the final output
        if strategy == OrchestratorStrategy.PIPELINE:
            last = successful[-1]
            return last.output, last.confidence

        # For DEBATE — the synthesizer result is the final output
        if strategy == OrchestratorStrategy.DEBATE:
            synthesizer = [r for r in successful if r.role == AgentRole.SYNTHESIZER]
            if synthesizer:
                return synthesizer[0].output, synthesizer[0].confidence
            return successful[-1].output, successful[-1].confidence

        # For SWARM / HIERARCHY — LLM-powered synthesis
        return self._llm_merge(task, successful)

    def _llm_merge(
        self, task: str, results: List[AgentResult],
    ) -> Tuple[str, float]:
        """Use the LLM to intelligently merge multiple agent outputs."""
        sections = []
        for i, r in enumerate(results):
            sections.append(
                f"── Agent {i+1}: {r.role.value.upper()} "
                f"(confidence: {r.confidence:.1%}) ──\n"
                f"{r.output[:2000]}"
            )

        merge_input = "\n\n".join(sections)

        prompt = (
            "You are the MASTER SYNTHESIZER. You have received outputs from "
            "multiple specialist agents who worked on the same task.\n\n"
            f"ORIGINAL TASK:\n{task[:500]}\n\n"
            f"AGENT OUTPUTS:\n{merge_input}\n\n"
            "INSTRUCTIONS:\n"
            "1. Merge all outputs into a single, coherent, comprehensive response.\n"
            "2. Resolve any contradictions — prefer the higher-confidence agent.\n"
            "3. Preserve unique insights from each agent.\n"
            "4. Structure the output logically with clear sections.\n"
            "5. The result must be strictly better than any individual output.\n\n"
            "MERGED OUTPUT:"
        )

        try:
            merged = self.generate_fn(prompt)
            avg_conf = sum(r.confidence for r in results) / len(results)
            # Boost confidence slightly for multi-agent synthesis
            final_conf = min(1.0, avg_conf * 1.1)
            return merged, final_conf
        except Exception as e:
            logger.error(f"LLM merge failed: {e}")
            # Fallback: concatenate with headers
            fallback = "\n\n".join(
                f"## {r.role.value.title()} Agent\n{r.output}"
                for r in results
            )
            avg_conf = sum(r.confidence for r in results) / len(results)
            return fallback, avg_conf


# ══════════════════════════════════════════════════════════════════════
# Agent Orchestrator — The Main Engine
# ══════════════════════════════════════════════════════════════════════

class AgentOrchestrator:
    """
    Production-grade multi-agent orchestration engine.

    Supports 4 strategies (Swarm, Pipeline, Hierarchy, Debate) with
    auto-selection, circuit-breaker safety, telemetry, and AgentForge
    integration for dynamic specialist creation.

    Usage:
        orchestrator = AgentOrchestrator(generate_fn=my_llm)
        result = orchestrator.orchestrate(
            task="Build a secure REST API with OAuth2",
            strategy=OrchestratorStrategy.AUTO,
        )
        print(result.final_output)
    """

    def __init__(
        self,
        generate_fn: Callable,
        agent_forge=None,
        max_agents: int = MAX_AGENTS_PER_ORCHESTRATION,
        agent_timeout: int = DEFAULT_AGENT_TIMEOUT_S,
        max_depth: int = MAX_ORCHESTRATION_DEPTH,
    ):
        self.generate_fn = generate_fn
        self.agent_forge = agent_forge

        # Sub-components
        self.decomposer = TaskDecomposer(generate_fn)
        self.aggregator = ResultAggregator(generate_fn)
        self.breaker = CircuitBreaker(
            max_depth=max_depth,
            max_agents=max_agents,
        )

        # Config
        self.max_agents = max_agents
        self.agent_timeout = agent_timeout

        # Telemetry
        self.tracer = SpanTracer()
        self.metrics = MetricsCollector.get_instance()

        # Stats
        self._stats = {
            "total_orchestrations": 0,
            "successful": 0,
            "failed": 0,
            "circuit_breaker_trips": 0,
            "agents_spawned": 0,
            "strategies_used": {},
        }

        logger.info(
            f"🎭 AgentOrchestrator initialized — "
            f"max_agents={max_agents}, timeout={agent_timeout}s, "
            f"max_depth={max_depth}, "
            f"forge={'enabled' if agent_forge else 'disabled'}"
        )

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def orchestrate(
        self,
        task: str,
        strategy: OrchestratorStrategy = OrchestratorStrategy.AUTO,
        max_subtasks: int = 5,
        context: str = "",
    ) -> OrchestrationResult:
        """
        Execute a complex task using multi-agent orchestration.

        Args:
            task: The complex task description
            strategy: Orchestration strategy (or AUTO for auto-selection)
            max_subtasks: Maximum sub-tasks to decompose into
            context: Additional context from prior pipeline stages

        Returns:
            OrchestrationResult with merged output and full trace
        """
        orch_id = f"orch_{uuid.uuid4().hex[:10]}"
        start_time = time.time()
        self._stats["total_orchestrations"] += 1
        self.metrics.counter("orchestrator.orchestrations_total")

        result = OrchestrationResult(
            orchestration_id=orch_id,
            original_task=task,
        )

        with self.tracer.span("orchestrate") as root_span:
            root_span.attributes["orchestration_id"] = orch_id

            # ── Circuit Breaker Entry ──
            if not self.breaker.enter():
                result.error = f"Circuit breaker: {self.breaker.trip_reason}"
                result.circuit_breaker_triggered = True
                self._stats["circuit_breaker_trips"] += 1
                self.metrics.counter("orchestrator.circuit_breaker_trips")
                logger.error(f"🔴 Orchestration {orch_id} blocked: {result.error}")
                return result

            try:
                # ── Phase 1: Strategy Selection ──
                if strategy == OrchestratorStrategy.AUTO:
                    strategy = auto_select_strategy(task, self.generate_fn)
                    logger.info(f"🎯 Auto-selected strategy: {strategy.value}")

                result.strategy = strategy
                root_span.attributes["strategy"] = strategy.value
                self._stats["strategies_used"][strategy.value] = (
                    self._stats["strategies_used"].get(strategy.value, 0) + 1
                )

                # ── Phase 2: Task Decomposition ──
                with self.tracer.span("decompose_task") as dec_span:
                    subtasks = self.decomposer.decompose(
                        task=task,
                        strategy=strategy,
                        max_subtasks=max_subtasks,
                    )
                    dec_span.attributes["subtask_count"] = len(subtasks)

                    result.decomposition_trace = json.dumps(
                        [{"role": st.role.value, "desc": st.description[:100]}
                         for st in subtasks],
                        indent=2,
                    )

                logger.info(
                    f"📋 Decomposed into {len(subtasks)} sub-tasks: "
                    f"{[st.role.value for st in subtasks]}"
                )

                # ── Phase 3: Execute Strategy ──
                with self.tracer.span(f"execute_{strategy.value}") as exec_span:
                    if strategy == OrchestratorStrategy.SWARM:
                        agent_results = self._execute_swarm(task, subtasks, context)
                    elif strategy == OrchestratorStrategy.PIPELINE:
                        agent_results = self._execute_pipeline(task, subtasks, context)
                    elif strategy == OrchestratorStrategy.HIERARCHY:
                        agent_results = self._execute_hierarchy(task, subtasks, context)
                    elif strategy == OrchestratorStrategy.DEBATE:
                        agent_results = self._execute_debate(task, subtasks, context)
                    else:
                        agent_results = self._execute_swarm(task, subtasks, context)

                    exec_span.attributes["agents_executed"] = len(agent_results)

                result.agent_results = agent_results
                result.agents_used = len(agent_results)
                self._stats["agents_spawned"] += len(agent_results)

                # ── Phase 4: Result Aggregation ──
                with self.tracer.span("merge_results") as merge_span:
                    final_output, confidence = self.aggregator.merge(
                        task=task,
                        results=agent_results,
                        strategy=strategy,
                    )
                    merge_span.attributes["confidence"] = confidence

                result.final_output = final_output
                result.confidence = confidence

                if result.success:
                    self._stats["successful"] += 1
                else:
                    self._stats["failed"] += 1

            except Exception as e:
                result.error = str(e)
                self._stats["failed"] += 1
                logger.error(f"Orchestration {orch_id} failed: {e}", exc_info=True)

            finally:
                self.breaker.exit()

            result.total_duration_ms = (time.time() - start_time) * 1000
            root_span.attributes["duration_ms"] = result.total_duration_ms
            root_span.attributes["success"] = result.success

        self.metrics.histogram(
            "orchestrator.duration_ms", result.total_duration_ms
        )
        self.metrics.histogram("orchestrator.confidence", result.confidence)
        self.metrics.histogram("orchestrator.agents_used", result.agents_used)

        logger.info(
            f"{'✅' if result.success else '❌'} Orchestration {orch_id} "
            f"complete: strategy={strategy.value}, agents={result.agents_used}, "
            f"conf={result.confidence:.1%}, "
            f"dur={result.total_duration_ms:.0f}ms"
        )

        return result

    # ──────────────────────────────────────────────────────────────
    # Strategy Implementations
    # ──────────────────────────────────────────────────────────────

    def _execute_swarm(
        self, task: str, subtasks: List[SubTask], context: str = ""
    ) -> List[AgentResult]:
        """
        SWARM strategy: All agents execute in parallel.

        Best for: Independent research/analysis tasks where each agent
        contributes a unique perspective.
        """
        logger.info(f"🐝 Swarm: Dispatching {len(subtasks)} agents in parallel")

        results: List[AgentResult] = []
        futures: Dict[Future, SubTask] = {}

        with ThreadPoolExecutor(
            max_workers=min(len(subtasks), self.max_agents)
        ) as executor:
            for st in subtasks:
                if not self.breaker.check():
                    logger.warning("Circuit breaker tripped during swarm dispatch")
                    break

                if not self.breaker.register_agent():
                    break

                st.status = TaskStatus.RUNNING
                future = executor.submit(
                    self._run_agent, st, task, context
                )
                futures[future] = st

            for future in as_completed(futures, timeout=self.agent_timeout):
                st = futures[future]
                try:
                    result = future.result(timeout=self.agent_timeout)
                    st.status = (
                        TaskStatus.COMPLETED if result.success
                        else TaskStatus.FAILED
                    )
                    results.append(result)
                except Exception as e:
                    st.status = TaskStatus.FAILED
                    results.append(AgentResult(
                        task_id=st.task_id,
                        role=st.role,
                        error=str(e),
                        success=False,
                    ))

        return results

    def _execute_pipeline(
        self, task: str, subtasks: List[SubTask], context: str = ""
    ) -> List[AgentResult]:
        """
        PIPELINE strategy: Agents execute sequentially, each building
        on the output of the previous agent.

        Best for: Multi-stage workflows (research → design → implement).
        """
        logger.info(f"🔗 Pipeline: Chaining {len(subtasks)} agents sequentially")

        results: List[AgentResult] = []
        accumulated_context = context

        # Sort by priority (lower = first)
        sorted_tasks = sorted(subtasks, key=lambda st: st.priority)

        for i, st in enumerate(sorted_tasks):
            if not self.breaker.check():
                logger.warning("Circuit breaker tripped during pipeline")
                break

            if not self.breaker.register_agent():
                break

            # Inject prior outputs as context for the next stage
            if accumulated_context:
                st.context = (
                    f"{task}\n\n"
                    f"── Prior Stage Outputs ──\n{accumulated_context}"
                )
            else:
                st.context = task

            st.status = TaskStatus.RUNNING
            logger.info(
                f"  🔗 Stage {i+1}/{len(sorted_tasks)}: "
                f"{st.role.value} — {st.description[:60]}"
            )

            result = self._run_agent(st, task, accumulated_context)
            st.status = (
                TaskStatus.COMPLETED if result.success
                else TaskStatus.FAILED
            )
            results.append(result)

            # Feed this output forward
            if result.success:
                accumulated_context += (
                    f"\n\n── {st.role.value.upper()} Output ──\n"
                    f"{result.output[:3000]}"
                )
            else:
                # Pipeline broken — log and continue with degraded context
                logger.warning(
                    f"Pipeline stage {i+1} ({st.role.value}) failed: "
                    f"{result.error}"
                )

        return results

    def _execute_hierarchy(
        self, task: str, subtasks: List[SubTask], context: str = ""
    ) -> List[AgentResult]:
        """
        HIERARCHY strategy: Manager decomposes, workers execute in
        parallel, manager synthesizes the results.

        Best for: Complex multi-domain tasks requiring coordination.
        """
        logger.info(
            f"🏛️ Hierarchy: Manager → "
            f"{len(subtasks)} workers → Synthesis"
        )

        # Phase 1: Manager analysis (decomposition already done)
        manager_analysis = (
            f"Task decomposed into {len(subtasks)} sub-tasks:\n"
            + "\n".join(
                f"  {i+1}. [{st.role.value}] {st.description[:80]}"
                for i, st in enumerate(subtasks)
            )
        )

        # Phase 2: Workers execute in parallel (same as swarm)
        worker_results = self._execute_swarm(task, subtasks, context)

        # Phase 3: Manager synthesis
        if not self.breaker.register_agent():
            return worker_results

        synth_task = SubTask(
            role=AgentRole.MANAGER,
            description=(
                "Synthesize these worker outputs into a single coherent "
                "response. Resolve conflicts and fill gaps."
            ),
        )

        # Build synthesis context from worker outputs
        worker_context = (
            f"ORIGINAL TASK:\n{task}\n\n"
            f"MANAGER ANALYSIS:\n{manager_analysis}\n\n"
            "WORKER OUTPUTS:\n"
        )
        for r in worker_results:
            status = "SUCCESS" if r.success else "FAILED"
            worker_context += (
                f"\n── [{r.role.value.upper()}] ({status}, "
                f"conf={r.confidence:.1%}) ──\n"
                f"{r.output[:2000]}\n"
            )

        synth_task.context = worker_context
        synth_result = self._run_agent(synth_task, task, worker_context)

        return worker_results + [synth_result]

    def _execute_debate(
        self, task: str, subtasks: List[SubTask], context: str = ""
    ) -> List[AgentResult]:
        """
        DEBATE strategy: Adversarial quality improvement through
        Draft → Critique → Synthesize.

        Best for: High-quality outputs requiring rigorous review.
        """
        logger.info("⚔️ Debate: Draft → Critique → Synthesize")

        results: List[AgentResult] = []

        # Ensure we have exactly 3 phases
        if len(subtasks) < 3:
            subtasks = self.decomposer._fallback_decompose(
                task, OrchestratorStrategy.DEBATE
            )

        # Phase 1: DRAFT
        draft_task = subtasks[0]
        draft_task.role = AgentRole.CODER
        draft_task.context = f"{task}\n{context}" if context else task

        if not self.breaker.register_agent():
            return results

        draft_task.status = TaskStatus.RUNNING
        logger.info("  ⚔️ Phase 1: Expert drafts initial solution")
        draft_result = self._run_agent(draft_task, task, context)
        draft_task.status = (
            TaskStatus.COMPLETED if draft_result.success
            else TaskStatus.FAILED
        )
        results.append(draft_result)

        if not draft_result.success:
            return results

        # Phase 2: CRITIQUE
        critic_task = subtasks[1] if len(subtasks) > 1 else SubTask(
            role=AgentRole.CRITIC,
            description="Critique the draft solution ruthlessly.",
        )
        critic_task.role = AgentRole.CRITIC
        critic_context = (
            f"ORIGINAL TASK:\n{task}\n\n"
            f"EXPERT DRAFT:\n{draft_result.output[:4000]}\n\n"
            "Find EVERY flaw. Be adversarial. Rate each issue by severity."
        )
        critic_task.context = critic_context

        if not self.breaker.register_agent():
            return results

        critic_task.status = TaskStatus.RUNNING
        logger.info("  ⚔️ Phase 2: Critic reviews draft")
        critic_result = self._run_agent(critic_task, task, critic_context)
        critic_task.status = (
            TaskStatus.COMPLETED if critic_result.success
            else TaskStatus.FAILED
        )
        results.append(critic_result)

        # Phase 3: SYNTHESIZE
        synth_task = subtasks[2] if len(subtasks) > 2 else SubTask(
            role=AgentRole.SYNTHESIZER,
            description="Synthesize the final perfected solution.",
        )
        synth_task.role = AgentRole.SYNTHESIZER
        synth_context = (
            f"ORIGINAL TASK:\n{task}\n\n"
            f"EXPERT DRAFT:\n{draft_result.output[:3000]}\n\n"
            f"CRITIC'S REVIEW:\n"
            f"{critic_result.output[:3000] if critic_result.success else 'Critique unavailable'}\n\n"
            "Create the FINAL, PERFECTED solution that addresses all valid "
            "criticisms while preserving the strengths of the draft."
        )
        synth_task.context = synth_context

        if not self.breaker.register_agent():
            return results

        synth_task.status = TaskStatus.RUNNING
        logger.info("  ⚔️ Phase 3: Synthesizer creates final solution")
        synth_result = self._run_agent(synth_task, task, synth_context)
        synth_task.status = (
            TaskStatus.COMPLETED if synth_result.success
            else TaskStatus.FAILED
        )
        results.append(synth_result)

        return results

    # ──────────────────────────────────────────────────────────────
    # Agent Execution Core
    # ──────────────────────────────────────────────────────────────

    def _run_agent(
        self,
        subtask: SubTask,
        original_task: str,
        context: str = "",
    ) -> AgentResult:
        """
        Execute a single agent on its assigned sub-task.

        Builds the prompt from the role template + task context,
        calls the LLM, and parses confidence from the response.
        """
        start_time = time.time()

        # Build role-specific system prompt
        role_prompt = ROLE_PROMPTS.get(
            subtask.role,
            f"You are a specialized {subtask.role.value} agent."
        )

        # Construct the full agent prompt
        prompt_parts = [
            f"SYSTEM:\n{role_prompt}",
            f"\nASSIGNMENT:\n{subtask.description}",
        ]

        if subtask.context:
            prompt_parts.append(f"\nCONTEXT:\n{subtask.context[:4000]}")
        elif context:
            prompt_parts.append(f"\nCONTEXT:\n{context[:4000]}")

        prompt_parts.append(
            "\nINSTRUCTIONS:\n"
            "1. Execute your assignment with maximum expertise.\n"
            "2. Be thorough but concise — every sentence must add value.\n"
            "3. End with a confidence self-assessment (0.0 to 1.0).\n"
            "4. Format: CONFIDENCE: 0.XX\n"
        )

        full_prompt = "\n".join(prompt_parts)

        try:
            response = self.generate_fn(full_prompt)
            confidence = self._extract_confidence(response)

            duration_ms = (time.time() - start_time) * 1000

            self.metrics.counter(
                f"orchestrator.agent.{subtask.role.value}.executions"
            )
            self.metrics.histogram(
                f"orchestrator.agent.{subtask.role.value}.duration_ms",
                duration_ms,
            )

            return AgentResult(
                task_id=subtask.task_id,
                role=subtask.role,
                output=response,
                confidence=confidence,
                duration_ms=duration_ms,
                success=True,
                token_estimate=len(full_prompt.split()) + len(response.split()),
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Agent {subtask.role.value} failed on task "
                f"{subtask.task_id}: {e}"
            )
            self.metrics.counter(
                f"orchestrator.agent.{subtask.role.value}.failures"
            )
            return AgentResult(
                task_id=subtask.task_id,
                role=subtask.role,
                error=str(e),
                success=False,
                duration_ms=duration_ms,
            )

    def _extract_confidence(self, response: str) -> float:
        """Extract confidence score from agent response."""
        # Look for "CONFIDENCE: 0.XX" pattern
        import re
        patterns = [
            r"CONFIDENCE:\s*([\d.]+)",
            r"confidence:\s*([\d.]+)",
            r"Confidence:\s*([\d.]+)",
            r"confidence\s*=\s*([\d.]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, response)
            if match:
                try:
                    conf = float(match.group(1))
                    return min(1.0, max(0.0, conf))
                except ValueError:
                    continue

        # Heuristic: estimate from response length and structure
        word_count = len(response.split())
        if word_count > 200:
            return 0.7
        elif word_count > 50:
            return 0.5
        return 0.3

    # ──────────────────────────────────────────────────────────────
    # Interactive & API Interfaces
    # ──────────────────────────────────────────────────────────────

    def start_interactive(self, task: str = None):
        """Run an interactive orchestration session in the console."""
        print("\n" + "═" * 66)
        print("  🎭 AGENT ORCHESTRATOR — Multi-Agent Coordination Engine")
        print("═" * 66)
        print(
            "  Strategies: swarm | pipeline | hierarchy | debate | auto\n"
            "  Commands:   /stats | /reset | /quit\n"
        )

        if task:
            self._interactive_execute(task)

        while True:
            try:
                user_input = input("\n🎭 Orchestrator > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Orchestrator shutting down.")
                break

            if not user_input:
                continue
            if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
                print("👋 Orchestrator shutting down.")
                break
            if user_input.lower() == "/stats":
                self._print_stats()
                continue
            if user_input.lower() == "/reset":
                self.breaker.reset()
                print("🔄 Circuit breaker reset.")
                continue

            # Parse strategy override: "strategy: task"
            strategy = OrchestratorStrategy.AUTO
            if ":" in user_input:
                prefix, _, remainder = user_input.partition(":")
                prefix_clean = prefix.strip().lower()
                for s in OrchestratorStrategy:
                    if s.value == prefix_clean:
                        strategy = s
                        user_input = remainder.strip()
                        break

            self._interactive_execute(user_input, strategy)

    def _interactive_execute(
        self,
        task: str,
        strategy: OrchestratorStrategy = OrchestratorStrategy.AUTO,
    ):
        """Execute orchestration and display results interactively."""
        print(f"\n🚀 Starting orchestration (strategy: {strategy.value})...")
        print(f"   Task: {task[:100]}{'...' if len(task) > 100 else ''}\n")

        result = self.orchestrate(task=task, strategy=strategy)

        if result.success:
            print(f"\n{'═' * 66}")
            print(f"  ✅ ORCHESTRATION COMPLETE")
            print(f"{'═' * 66}")
            print(f"  Strategy:   {result.strategy.value}")
            print(f"  Agents:     {result.agents_used}")
            print(f"  Confidence: {result.confidence:.1%}")
            print(f"  Duration:   {result.total_duration_ms:.0f}ms")
            print(f"{'─' * 66}")
            print(f"\n{result.final_output}\n")
        else:
            print(f"\n❌ Orchestration failed: {result.error}")

    def _print_stats(self):
        """Print orchestrator statistics."""
        s = self._stats
        print(f"\n{'─' * 40}")
        print(f"  📊 Orchestrator Stats")
        print(f"{'─' * 40}")
        print(f"  Total:         {s['total_orchestrations']}")
        print(f"  Successful:    {s['successful']}")
        print(f"  Failed:        {s['failed']}")
        print(f"  Agents spawned:{s['agents_spawned']}")
        print(f"  CB Trips:      {s['circuit_breaker_trips']}")
        print(f"  Strategies:    {s['strategies_used']}")
        print(f"  Breaker:       {'TRIPPED' if self.breaker.is_tripped else 'OK'}")
        print(f"{'─' * 40}")

    def api_execute(
        self,
        task: str,
        strategy: str = "auto",
        max_subtasks: int = 5,
        context: str = "",
    ) -> Dict[str, Any]:
        """
        API-compatible execution method.

        Returns a JSON-serializable dict suitable for REST/WebSocket
        responses.
        """
        strat_map = {s.value: s for s in OrchestratorStrategy}
        selected = strat_map.get(strategy.lower(), OrchestratorStrategy.AUTO)

        result = self.orchestrate(
            task=task,
            strategy=selected,
            max_subtasks=max_subtasks,
            context=context,
        )

        return {
            "orchestration_id": result.orchestration_id,
            "strategy": result.strategy.value,
            "success": result.success,
            "final_output": result.final_output,
            "confidence": result.confidence,
            "agents_used": result.agents_used,
            "total_duration_ms": result.total_duration_ms,
            "error": result.error,
            "agent_details": [
                {
                    "task_id": r.task_id,
                    "role": r.role.value,
                    "success": r.success,
                    "confidence": r.confidence,
                    "duration_ms": r.duration_ms,
                    "output_preview": r.output[:200] if r.success else r.error,
                }
                for r in result.agent_results
            ],
            "decomposition": result.decomposition_trace,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return dict(self._stats)

    def reset(self):
        """Reset the orchestrator state and circuit breaker."""
        self.breaker.reset()
        self._stats = {
            "total_orchestrations": 0,
            "successful": 0,
            "failed": 0,
            "circuit_breaker_trips": 0,
            "agents_spawned": 0,
            "strategies_used": {},
        }
        logger.info("🔄 Orchestrator reset.")
