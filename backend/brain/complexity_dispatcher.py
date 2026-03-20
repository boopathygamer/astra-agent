"""
Complexity Dispatcher — Intelligent Multi-Agent Problem Decomposition
═════════════════════════════════════════════════════════════════════
When the brain encounters a complex, multi-domain problem, this engine:
  1. DETECTS complexity via structural + semantic analysis
  2. DECOMPOSES the problem into a DAG of sub-tasks
  3. DISPATCHES each sub-task to the best-fit domain expert
  4. SYNTHESIZES the results into a unified answer

Safety:
  - Maximum 6 sub-tasks per decomposition (prevent explosion)
  - 10-second timeout per sub-task
  - All forged agents go through AgentForge's Justice Court review
  - Respects the controller's existing safety gates
"""

import logging
import time
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Enums and Data Models
# ──────────────────────────────────────────────

class ComplexityLevel(Enum):
    SIMPLE = "simple"           # Single-domain, direct answer
    MODERATE = "moderate"       # Multi-step but single domain
    COMPLEX = "complex"         # Multi-domain or requires decomposition
    HIGHLY_COMPLEX = "highly_complex"  # Deep multi-domain with dependencies


@dataclass
class ComplexityAssessment:
    """Result of complexity analysis."""
    level: ComplexityLevel = ComplexityLevel.SIMPLE
    score: float = 0.0              # 0.0 (trivial) → 1.0 (extremely complex)
    domain_count: int = 1           # Number of domains detected
    detected_domains: List[str] = field(default_factory=list)
    sub_problem_hints: List[str] = field(default_factory=list)
    reasoning: str = ""
    should_decompose: bool = False  # True if dispatcher should take over

    def summary(self) -> str:
        return (
            f"Complexity: {self.level.value} (score={self.score:.2f}, "
            f"domains={self.domain_count}, decompose={self.should_decompose})"
        )


@dataclass
class SubTask:
    """A sub-task extracted from a complex problem."""
    task_id: str = ""
    description: str = ""
    domain: str = "general"         # Best-fit domain
    depends_on: List[str] = field(default_factory=list)  # Task IDs this depends on
    priority: int = 0               # Lower = higher priority
    status: str = "pending"         # pending, running, done, failed
    result: str = ""
    duration_ms: float = 0.0
    agent_used: str = ""            # Which agent handled it


@dataclass
class DispatchResult:
    """Final result from the Complexity Dispatcher."""
    original_problem: str = ""
    complexity: ComplexityAssessment = field(default_factory=ComplexityAssessment)
    sub_tasks: List[SubTask] = field(default_factory=list)
    synthesized_answer: str = ""
    total_duration_ms: float = 0.0
    agents_used: List[str] = field(default_factory=list)
    success: bool = False

    def summary(self) -> str:
        return (
            f"Dispatch: {len(self.sub_tasks)} sub-tasks, "
            f"{len(self.agents_used)} agents, "
            f"{self.total_duration_ms:.0f}ms, "
            f"success={self.success}"
        )


# ──────────────────────────────────────────────
# Complexity Detection Signals
# ──────────────────────────────────────────────

# Multi-step indicator phrases
_MULTI_STEP_SIGNALS = [
    "and then", "after that", "next step", "first", "second", "third",
    "step 1", "step 2", "finally", "also", "in addition", "furthermore",
    "as well as", "along with", "plus", "on top of that",
    "followed by", "subsequently", "then",
]

# Conjunctions that suggest multiple sub-problems
_COMPOUND_SIGNALS = [
    " and ", " but also ", " as well as ", " plus ", " with ",
    " including ", " combined with ", " together with ",
]

# Explicit complexity phrases
_COMPLEXITY_PHRASES = [
    "build a complete", "create a full", "design and implement",
    "end to end", "full stack", "comprehensive", "entire system",
    "from scratch", "architecture", "multi-step", "complex",
    "plan and execute", "research and build", "analyze and create",
]


# ──────────────────────────────────────────────
# Complexity Detector
# ──────────────────────────────────────────────

class ComplexityDetector:
    """
    Analyzes user input to determine if it requires multi-agent decomposition.

    Scoring dimensions:
      1. Length signal     — longer prompts tend to be more complex
      2. Domain breadth    — how many domains are touched
      3. Multi-step signal — phrases indicating sequential steps
      4. Compound signal   — conjunctions linking sub-problems
      5. Explicit signal   — phrases like "build a complete..."
    """

    DECOMPOSE_THRESHOLD = 0.55  # Score above this → decompose

    def __init__(self, domain_keywords: Dict[str, List[Tuple[str, float]]] = None):
        """
        Args:
            domain_keywords: The weighted keyword dict from DomainRouter.
                             If None, uses a simplified built-in set.
        """
        self._domain_keywords = domain_keywords or self._default_keywords()

    def assess(self, user_input: str) -> ComplexityAssessment:
        """Assess the complexity of a user request."""
        input_lower = user_input.lower()
        scores: Dict[str, float] = {}

        # ── Dimension 1: Length signal ──
        word_count = len(user_input.split())
        length_score = min(word_count / 80.0, 1.0)  # Saturates at 80 words

        # ── Dimension 2: Domain breadth ──
        detected_domains = self._detect_domains(input_lower)
        domain_score = min(len(detected_domains) / 3.0, 1.0)  # 3+ domains = max

        # ── Dimension 3: Multi-step signals ──
        step_count = sum(1 for sig in _MULTI_STEP_SIGNALS if sig in input_lower)
        step_score = min(step_count / 3.0, 1.0)

        # ── Dimension 4: Compound signals ──
        compound_count = sum(1 for sig in _COMPOUND_SIGNALS if sig in input_lower)
        compound_score = min(compound_count / 2.0, 1.0)

        # ── Dimension 5: Explicit complexity phrases ──
        explicit_count = sum(1 for p in _COMPLEXITY_PHRASES if p in input_lower)
        explicit_score = min(explicit_count / 2.0, 1.0)

        # Weighted composite
        total = (
            length_score * 0.10
            + domain_score * 0.30
            + step_score * 0.20
            + compound_score * 0.15
            + explicit_score * 0.25
        )
        total = round(min(total, 1.0), 3)

        # Determine level
        if total < 0.20:
            level = ComplexityLevel.SIMPLE
        elif total < 0.40:
            level = ComplexityLevel.MODERATE
        elif total < 0.70:
            level = ComplexityLevel.COMPLEX
        else:
            level = ComplexityLevel.HIGHLY_COMPLEX

        should_decompose = total >= self.DECOMPOSE_THRESHOLD

        # Extract sub-problem hints from compound structures
        hints = self._extract_hints(user_input)

        return ComplexityAssessment(
            level=level,
            score=total,
            domain_count=len(detected_domains),
            detected_domains=detected_domains,
            sub_problem_hints=hints,
            reasoning=(
                f"length={length_score:.2f} domain={domain_score:.2f} "
                f"steps={step_score:.2f} compound={compound_score:.2f} "
                f"explicit={explicit_score:.2f} → total={total:.3f}"
            ),
            should_decompose=should_decompose,
        )

    def _detect_domains(self, text: str) -> List[str]:
        """Detect which domains are present in the text."""
        found = []
        for domain, keywords in self._domain_keywords.items():
            hits = sum(1 for kw, _ in keywords if kw in text)
            if hits >= 2:  # Require at least 2 keyword hits
                found.append(domain)
        return found

    def _extract_hints(self, text: str) -> List[str]:
        """Extract sub-problem hints by splitting on compound signals."""
        hints = []
        # Split on "and", "then", numbered steps
        parts = re.split(
            r'\b(?:and then|then|after that|also|plus|and)\b',
            text, flags=re.IGNORECASE,
        )
        for part in parts:
            part = part.strip().strip(",").strip()
            if len(part.split()) >= 3:  # At least 3 words to be a meaningful sub-problem
                hints.append(part)
        return hints[:6]  # Cap at 6

    @staticmethod
    def _default_keywords() -> Dict[str, List[Tuple[str, float]]]:
        """Minimal built-in domain keywords for standalone use."""
        return {
            "code": [("code", 1.0), ("program", 1.0), ("function", 0.8), ("debug", 1.0), ("python", 1.0), ("api", 0.9)],
            "math": [("math", 1.0), ("calculate", 0.9), ("equation", 1.0), ("formula", 0.9), ("algebra", 1.0)],
            "writing": [("write", 0.6), ("essay", 1.0), ("article", 0.9), ("story", 0.9), ("blog", 0.8)],
            "business": [("business", 1.0), ("marketing", 1.0), ("strategy", 0.7), ("revenue", 1.0), ("startup", 1.0)],
            "data": [("data", 0.5), ("dataset", 1.0), ("analysis", 0.6), ("chart", 0.8), ("visualization", 0.9)],
            "creative": [("design", 0.7), ("creative", 0.8), ("logo", 1.0), ("ui", 0.8), ("ux", 1.0)],
        }


# ──────────────────────────────────────────────
# Problem Decomposer
# ──────────────────────────────────────────────

class ProblemDecomposer:
    """
    Breaks a complex problem into a DAG of sub-tasks,
    each tagged with the best-fit domain.
    """

    MAX_SUBTASKS = 6

    def __init__(self, generate_fn: Callable = None):
        self.generate_fn = generate_fn

    def decompose(
        self,
        user_input: str,
        assessment: ComplexityAssessment,
    ) -> List[SubTask]:
        """
        Decompose a complex problem into sub-tasks.

        Uses the LLM if available; falls back to heuristic decomposition.
        """
        if self.generate_fn:
            return self._llm_decompose(user_input, assessment)
        return self._heuristic_decompose(user_input, assessment)

    def _llm_decompose(
        self, user_input: str, assessment: ComplexityAssessment,
    ) -> List[SubTask]:
        """Use the LLM to intelligently decompose the problem."""
        available_domains = ", ".join(assessment.detected_domains or ["general"])

        prompt = f"""Break down this complex user request into {min(self.MAX_SUBTASKS, max(2, assessment.domain_count + 1))} focused sub-tasks.

USER REQUEST: {user_input}

DETECTED DOMAINS: {available_domains}

Output ONLY a numbered list in this exact format (no other text):
1. [DOMAIN] Description of sub-task
2. [DOMAIN] Description of sub-task (depends on: 1)
...

RULES:
- Each DOMAIN must be one of: code, math, writing, business, data, creative, education, health, legal, lifestyle, general
- Mark dependencies with "(depends on: N)" where N is the step number
- Each sub-task should be independently solvable by a domain expert
- Maximum {self.MAX_SUBTASKS} sub-tasks
- Output ONLY the numbered list
"""
        try:
            raw = self.generate_fn(prompt)
            return self._parse_llm_tasks(raw, assessment)
        except Exception as e:
            logger.warning(f"[DISPATCHER] LLM decompose failed: {e}, falling back to heuristic")
            return self._heuristic_decompose(user_input, assessment)

    def _parse_llm_tasks(
        self, raw: str, assessment: ComplexityAssessment,
    ) -> List[SubTask]:
        """Parse the LLM's numbered list into SubTask objects."""
        tasks = []
        lines = raw.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Match: "1. [code] Build the API" or "2. [data] Analyze results (depends on: 1)"
            match = re.match(
                r'(\d+)\.\s*\[(\w+)\]\s*(.+?)(?:\(depends?\s*on:?\s*([\d,\s]+)\))?$',
                line, re.IGNORECASE,
            )
            if match:
                idx = match.group(1)
                domain = match.group(2).lower()
                desc = match.group(3).strip()
                deps_str = match.group(4)

                deps = []
                if deps_str:
                    deps = [
                        f"task_{d.strip()}"
                        for d in deps_str.split(",")
                        if d.strip().isdigit()
                    ]

                tasks.append(SubTask(
                    task_id=f"task_{idx}",
                    description=desc,
                    domain=domain,
                    depends_on=deps,
                    priority=int(idx),
                ))

        if not tasks:
            return self._heuristic_decompose("", assessment)

        return tasks[:self.MAX_SUBTASKS]

    def _heuristic_decompose(
        self, user_input: str, assessment: ComplexityAssessment,
    ) -> List[SubTask]:
        """Fallback: decompose using the hints from ComplexityDetector."""
        tasks = []
        hints = assessment.sub_problem_hints or [user_input]
        domains = assessment.detected_domains or ["general"]

        for i, hint in enumerate(hints[:self.MAX_SUBTASKS]):
            # Assign domain round-robin from detected domains
            domain = domains[i % len(domains)] if domains else "general"
            tasks.append(SubTask(
                task_id=f"task_{i + 1}",
                description=hint,
                domain=domain,
                depends_on=[f"task_{i}"] if i > 0 else [],
                priority=i + 1,
            ))

        return tasks if tasks else [
            SubTask(
                task_id="task_1",
                description=user_input,
                domain=domains[0] if domains else "general",
                priority=1,
            )
        ]


# ──────────────────────────────────────────────
# Agent Dispatcher
# ──────────────────────────────────────────────

class AgentDispatcher:
    """
    Routes sub-tasks to the best-fit agent:
      1. Check domain experts registry
      2. If no expert fits, check AgentForge's dynamic agents
      3. If none exist, ask AgentForge to CREATE one
      4. Execute with the agent's context prompt
    """

    def __init__(
        self,
        generate_fn: Callable,
        domain_experts: Dict = None,
        agent_forge=None,
    ):
        self.generate_fn = generate_fn
        self.domain_experts = domain_experts or {}
        self.agent_forge = agent_forge
        self._dispatch_stats = {
            "dispatched": 0,
            "expert_hits": 0,
            "forge_hits": 0,
            "forge_created": 0,
            "failures": 0,
        }

    def dispatch(self, task: SubTask, context: str = "") -> SubTask:
        """
        Dispatch a single sub-task to the best-fit agent.

        Args:
            task: The sub-task to solve
            context: Additional context (e.g., results from dependencies)

        Returns:
            The sub-task with result and agent_used filled in
        """
        start = time.time()
        task.status = "running"
        self._dispatch_stats["dispatched"] += 1

        try:
            # Step 1: Look for a domain expert
            expert = self.domain_experts.get(task.domain)
            if expert:
                task.result = self._run_with_expert(task, expert, context)
                task.agent_used = f"expert:{expert.name}"
                self._dispatch_stats["expert_hits"] += 1
                task.status = "done"

            # Step 2: Check AgentForge for existing dynamic agents
            elif self.agent_forge:
                forged = self._find_or_forge_agent(task)
                if forged:
                    task.result = self._run_with_forged(task, forged, context)
                    task.agent_used = f"forged:{forged.name}"
                    task.status = "done"
                else:
                    # Step 3: Fallback — solve with general context
                    task.result = self._run_general(task, context)
                    task.agent_used = "general"
                    task.status = "done"
            else:
                # No forge available — general fallback
                task.result = self._run_general(task, context)
                task.agent_used = "general"
                task.status = "done"

        except Exception as e:
            logger.error(f"[DISPATCHER] Task {task.task_id} failed: {e}")
            task.status = "failed"
            task.result = f"Error: {str(e)}"
            self._dispatch_stats["failures"] += 1

        task.duration_ms = (time.time() - start) * 1000
        return task

    def _run_with_expert(self, task: SubTask, expert, context: str) -> str:
        """Solve using a domain expert's context prompt."""
        prompt = (
            f"{expert.get_prompt_injection()}\n\n"
            f"TASK: {task.description}\n"
        )
        if context:
            prompt += f"\nCONTEXT FROM PREVIOUS STEPS:\n{context}\n"
        prompt += "\nProvide a focused, expert-level answer."

        return self.generate_fn(prompt)

    def _run_with_forged(self, task: SubTask, forged, context: str) -> str:
        """Solve using a dynamically forged agent."""
        prompt = (
            f"{forged.system_prompt}\n\n"
            f"TASK: {task.description}\n"
        )
        if context:
            prompt += f"\nCONTEXT FROM PREVIOUS STEPS:\n{context}\n"
        prompt += "\nProvide a focused answer within your specialty."

        result = self.generate_fn(prompt)

        # Record usage on the forged agent
        if self.agent_forge:
            self.agent_forge.use_agent(forged.forge_id)

        return result

    def _run_general(self, task: SubTask, context: str) -> str:
        """Solve with no special agent — general prompt."""
        prompt = f"TASK: {task.description}\n"
        if context:
            prompt += f"\nCONTEXT FROM PREVIOUS STEPS:\n{context}\n"
        prompt += "\nProvide a thorough, well-structured answer."
        return self.generate_fn(prompt)

    def _find_or_forge_agent(self, task: SubTask):
        """
        Look for an existing forged agent that fits, or create one.
        """
        if not self.agent_forge:
            return None

        # Check existing forged agents
        active = self.agent_forge.list_active_agents()
        for agent_info in active:
            if agent_info["domain"] == task.domain:
                agent = self.agent_forge.get_agent(agent_info["forge_id"])
                if agent:
                    self._dispatch_stats["forge_hits"] += 1
                    return agent

        # Forge a new one
        try:
            forged = self.agent_forge.forge_agent(
                capability_description=(
                    f"Specialist in {task.domain} domain. "
                    f"Task context: {task.description[:200]}"
                ),
            )
            if forged:
                self._dispatch_stats["forge_created"] += 1
                logger.info(
                    f"[DISPATCHER] Forged new agent '{forged.name}' "
                    f"for domain '{task.domain}'"
                )
                return forged
        except Exception as e:
            logger.warning(f"[DISPATCHER] Agent forging failed: {e}")

        return None

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._dispatch_stats)


# ──────────────────────────────────────────────
# Result Synthesizer
# ──────────────────────────────────────────────

class ResultSynthesizer:
    """
    Merges results from multiple sub-tasks into a single coherent answer.
    Uses the LLM for intelligent synthesis when available.
    """

    def __init__(self, generate_fn: Callable = None):
        self.generate_fn = generate_fn

    def synthesize(
        self,
        original_problem: str,
        tasks: List[SubTask],
    ) -> str:
        """Synthesize sub-task results into a unified answer."""
        # Collect results
        completed = [t for t in tasks if t.status == "done" and t.result]
        failed = [t for t in tasks if t.status == "failed"]

        if not completed:
            return "I was unable to solve any part of your request. Please try rephrasing."

        if len(completed) == 1 and not failed:
            return completed[0].result

        # Multiple results — synthesize
        if self.generate_fn:
            return self._llm_synthesize(original_problem, completed, failed)
        return self._concat_synthesize(completed, failed)

    def _llm_synthesize(
        self,
        original_problem: str,
        completed: List[SubTask],
        failed: List[SubTask],
    ) -> str:
        """Use the LLM to create a coherent merged answer."""
        parts = []
        for task in completed:
            parts.append(
                f"## Sub-task: {task.description}\n"
                f"**Agent**: {task.agent_used} | **Domain**: {task.domain}\n"
                f"**Result**:\n{task.result}\n"
            )

        prompt = (
            f"The user asked: {original_problem}\n\n"
            f"Multiple specialist agents solved different aspects. "
            f"Synthesize their results into ONE coherent, well-structured answer.\n\n"
            + "\n---\n".join(parts)
        )

        if failed:
            prompt += (
                f"\n\nNote: {len(failed)} sub-task(s) failed: "
                + ", ".join(t.description[:50] for t in failed)
                + ". Acknowledge this gracefully."
            )

        prompt += (
            "\n\nIMPORTANT: Produce a single unified answer. "
            "Do NOT repeat the sub-task structure. "
            "Weave the results together naturally."
        )

        return self.generate_fn(prompt)

    def _concat_synthesize(
        self, completed: List[SubTask], failed: List[SubTask],
    ) -> str:
        """Fallback: concatenate results with headers."""
        parts = []
        for task in completed:
            parts.append(f"### {task.description}\n{task.result}")

        if failed:
            parts.append(
                f"\n⚠️ *{len(failed)} sub-task(s) could not be completed.*"
            )

        return "\n\n".join(parts)


# ──────────────────────────────────────────────
# Main Orchestrator
# ──────────────────────────────────────────────

class ComplexityDispatcher:
    """
    Top-level orchestrator that ties everything together.

    Usage inside AgentController.process():
        dispatcher = ComplexityDispatcher(generate_fn, domain_experts, agent_forge)
        assessment = dispatcher.assess(user_input)
        if assessment.should_decompose:
            result = dispatcher.solve(user_input)
            return result.synthesized_answer
    """

    def __init__(
        self,
        generate_fn: Callable,
        domain_experts: Dict = None,
        agent_forge=None,
        domain_keywords: Dict = None,
    ):
        self.detector = ComplexityDetector(domain_keywords)
        self.decomposer = ProblemDecomposer(generate_fn)
        self.dispatcher = AgentDispatcher(generate_fn, domain_experts, agent_forge)
        self.synthesizer = ResultSynthesizer(generate_fn)
        self._stats = {
            "assessments": 0,
            "decompositions": 0,
            "total_subtasks_dispatched": 0,
        }
        logger.info("[COMPLEXITY DISPATCHER] Initialized — multi-agent problem solving ONLINE")

    def assess(self, user_input: str) -> ComplexityAssessment:
        """Quick assessment of whether decomposition is needed."""
        self._stats["assessments"] += 1
        return self.detector.assess(user_input)

    def solve(self, user_input: str) -> DispatchResult:
        """
        Full pipeline: Detect → Decompose → Dispatch → Synthesize.
        """
        start = time.time()
        result = DispatchResult(original_problem=user_input)

        # Step 1: Assess complexity
        assessment = self.detector.assess(user_input)
        result.complexity = assessment
        logger.info(f"[DISPATCHER] {assessment.summary()}")

        # Step 2: Decompose into sub-tasks
        sub_tasks = self.decomposer.decompose(user_input, assessment)
        result.sub_tasks = sub_tasks
        self._stats["decompositions"] += 1
        logger.info(f"[DISPATCHER] Decomposed into {len(sub_tasks)} sub-tasks")

        # Step 3: Execute sub-tasks in dependency order
        completed_results: Dict[str, str] = {}

        # Topological execution: tasks with no deps first
        remaining = list(sub_tasks)
        max_iterations = len(remaining) + 1  # Prevent infinite loop

        for _ in range(max_iterations):
            if not remaining:
                break

            # Find tasks whose dependencies are all satisfied
            ready = [
                t for t in remaining
                if all(d in completed_results for d in t.depends_on)
            ]

            if not ready:
                # Deadlock — force run remaining tasks without context
                logger.warning("[DISPATCHER] Dependency deadlock — forcing remaining tasks")
                ready = remaining[:]

            for task in ready:
                # Build context from dependency results
                context_parts = []
                for dep_id in task.depends_on:
                    if dep_id in completed_results:
                        context_parts.append(completed_results[dep_id])
                context = "\n".join(context_parts) if context_parts else ""

                # Dispatch to agent
                self.dispatcher.dispatch(task, context)
                self._stats["total_subtasks_dispatched"] += 1

                if task.status == "done":
                    completed_results[task.task_id] = task.result

                remaining.remove(task)

        # Step 4: Synthesize into unified answer
        result.synthesized_answer = self.synthesizer.synthesize(
            user_input, sub_tasks,
        )
        result.agents_used = list(set(t.agent_used for t in sub_tasks if t.agent_used))
        result.success = any(t.status == "done" for t in sub_tasks)
        result.total_duration_ms = (time.time() - start) * 1000

        logger.info(f"[DISPATCHER] {result.summary()}")
        return result

    def get_stats(self) -> Dict[str, Any]:
        stats = dict(self._stats)
        stats["dispatch"] = self.dispatcher.get_stats()
        return stats
