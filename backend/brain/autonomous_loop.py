"""
Autonomous Agent Loop — Continuous ASI Thinking Engine.
=======================================================
The core missing piece: a self-directed thinking cycle that
breaks goals into sub-tasks, selects tools, executes, observes,
re-plans, and learns — all without waiting for user commands.

Classes:
  Goal           — High-level objective with priority & deadline
  SubTask        — Atomic executable step with tool binding
  AgentState     — Full cognitive state snapshot
  AutonomousLoop — The main thinking engine
"""

import asyncio
import hashlib
import json
import logging
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

class Priority(Enum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubTask:
    """Atomic executable step with tool binding."""
    id: str = ""
    description: str = ""
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    retries: int = 0
    max_retries: int = 3
    depends_on: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    confidence: float = 0.5
    reasoning: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"sub_{secrets.token_hex(4)}"

    @property
    def duration(self) -> float:
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return 0.0

    @property
    def can_execute(self) -> bool:
        return self.status == TaskStatus.PENDING and self.retries < self.max_retries

    def mark_started(self):
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = time.time()

    def mark_completed(self, result: Any):
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = time.time()

    def mark_failed(self, error: str):
        self.retries += 1
        if self.retries >= self.max_retries:
            self.status = TaskStatus.FAILED
            self.error = error
        else:
            self.status = TaskStatus.PENDING
            self.error = error


@dataclass
class Goal:
    """High-level objective with decomposition into sub-tasks."""
    id: str = ""
    description: str = ""
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    sub_tasks: List[SubTask] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None
    parent_goal_id: Optional[str] = None
    success_criteria: str = ""
    progress: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = f"goal_{secrets.token_hex(4)}"

    def update_progress(self):
        if not self.sub_tasks:
            return
        completed = sum(1 for t in self.sub_tasks if t.status == TaskStatus.COMPLETED)
        self.progress = completed / len(self.sub_tasks)
        if all(t.status == TaskStatus.COMPLETED for t in self.sub_tasks):
            self.status = TaskStatus.COMPLETED
        elif any(t.status == TaskStatus.FAILED for t in self.sub_tasks):
            if all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) for t in self.sub_tasks):
                failed = sum(1 for t in self.sub_tasks if t.status == TaskStatus.FAILED)
                self.status = TaskStatus.FAILED if failed > len(self.sub_tasks) / 2 else TaskStatus.COMPLETED

    @property
    def is_overdue(self) -> bool:
        return bool(self.deadline and time.time() > self.deadline)


@dataclass
class ThoughtRecord:
    """A single reasoning step in the agent's thought process."""
    timestamp: float = field(default_factory=time.time)
    thought_type: str = "reasoning"  # reasoning, observation, decision, reflection
    content: str = ""
    confidence: float = 0.5
    supporting_evidence: List[str] = field(default_factory=list)
    alternatives_considered: List[str] = field(default_factory=list)


@dataclass
class AgentState:
    """Full cognitive state snapshot of the autonomous agent."""
    cycle_count: int = 0
    goals: List[Goal] = field(default_factory=list)
    active_goal_id: Optional[str] = None
    thought_log: deque = field(default_factory=lambda: deque(maxlen=500))
    observations: deque = field(default_factory=lambda: deque(maxlen=200))
    decisions_made: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_reasoning_time: float = 0.0
    last_reflection_at: float = 0.0
    cognitive_load: float = 0.0  # 0.0 to 1.0
    mode: str = "active"  # active, reflecting, waiting, sleeping

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 0.0


# ══════════════════════════════════════════════════════════════
# Goal Decomposer — Breaks Goals into Sub-Tasks
# ══════════════════════════════════════════════════════════════

class GoalDecomposer:
    """Breaks high-level goals into executable sub-tasks using reasoning."""

    # Tool catalog for task-tool matching
    TOOL_CATALOG = {
        "file_read": {"domain": "file", "verbs": ["read", "view", "open", "inspect", "analyze"]},
        "file_write": {"domain": "file", "verbs": ["write", "create", "save", "generate"]},
        "file_find": {"domain": "file", "verbs": ["find", "search", "locate", "discover"]},
        "web_search": {"domain": "web", "verbs": ["search", "find", "look up", "research"]},
        "code_executor": {"domain": "code", "verbs": ["run", "execute", "test", "evaluate"]},
        "code_analyzer": {"domain": "code", "verbs": ["analyze", "review", "lint", "check"]},
        "web_scaffold_project": {"domain": "web_dev", "verbs": ["scaffold", "create project", "init"]},
        "web_generate_component": {"domain": "web_dev", "verbs": ["component", "widget", "ui"]},
        "git_commit": {"domain": "git", "verbs": ["commit", "save", "version"]},
        "git_push": {"domain": "git", "verbs": ["push", "deploy", "upload"]},
        "db_design_schema": {"domain": "database", "verbs": ["schema", "database", "table"]},
        "generate_tests": {"domain": "testing", "verbs": ["test", "verify", "validate"]},
        "threat_full_scan": {"domain": "security", "verbs": ["scan", "security", "virus", "malware"]},
        "api_test": {"domain": "api", "verbs": ["api", "endpoint", "request", "http"]},
    }

    @classmethod
    def decompose(cls, goal: Goal, available_tools: List[str] = None) -> List[SubTask]:
        """Decompose a high-level goal into ordered sub-tasks."""
        description = goal.description.lower()
        sub_tasks = []

        # Pattern-based decomposition
        if any(w in description for w in ["build", "create", "develop", "make"]):
            sub_tasks = cls._decompose_build_goal(goal, description)
        elif any(w in description for w in ["fix", "debug", "repair", "solve"]):
            sub_tasks = cls._decompose_fix_goal(goal, description)
        elif any(w in description for w in ["analyze", "review", "inspect", "check"]):
            sub_tasks = cls._decompose_analyze_goal(goal, description)
        elif any(w in description for w in ["deploy", "push", "release", "ship"]):
            sub_tasks = cls._decompose_deploy_goal(goal, description)
        elif any(w in description for w in ["scan", "security", "virus", "threat"]):
            sub_tasks = cls._decompose_security_goal(goal, description)
        else:
            sub_tasks = cls._decompose_generic_goal(goal, description)

        # Set dependencies (each step depends on the previous)
        for i in range(1, len(sub_tasks)):
            sub_tasks[i].depends_on = [sub_tasks[i - 1].id]

        return sub_tasks

    @classmethod
    def _decompose_build_goal(cls, goal, desc):
        tasks = [
            SubTask(description="Analyze requirements", tool_name="code_analyzer",
                    reasoning="Understand what needs to be built before coding"),
            SubTask(description="Design architecture", tool_name="code_analyzer",
                    reasoning="Plan the structure before implementation"),
            SubTask(description="Implement core logic", tool_name="file_write",
                    reasoning="Write the main implementation code"),
            SubTask(description="Write tests", tool_name="generate_tests",
                    reasoning="Ensure correctness with automated tests"),
            SubTask(description="Run tests", tool_name="code_executor",
                    reasoning="Verify implementation passes all tests"),
        ]
        if "deploy" in desc or "push" in desc:
            tasks.append(SubTask(description="Deploy/push", tool_name="git_commit",
                                  reasoning="Version control and deployment"))
        return tasks

    @classmethod
    def _decompose_fix_goal(cls, goal, desc):
        return [
            SubTask(description="Reproduce the issue", tool_name="code_executor",
                    reasoning="Understand the bug by reproducing it"),
            SubTask(description="Analyze root cause", tool_name="code_analyzer",
                    reasoning="Find the source of the bug"),
            SubTask(description="Apply fix", tool_name="file_write",
                    reasoning="Write the correction"),
            SubTask(description="Verify fix", tool_name="code_executor",
                    reasoning="Ensure the fix works and no regressions"),
        ]

    @classmethod
    def _decompose_analyze_goal(cls, goal, desc):
        return [
            SubTask(description="Scan codebase", tool_name="code_analyzer",
                    reasoning="Gather analysis data"),
            SubTask(description="Identify issues", tool_name="code_analyzer",
                    reasoning="Find problems and patterns"),
            SubTask(description="Generate report", tool_name="file_write",
                    reasoning="Document findings"),
        ]

    @classmethod
    def _decompose_deploy_goal(cls, goal, desc):
        return [
            SubTask(description="Run pre-deploy checks", tool_name="code_executor",
                    reasoning="Verify everything works before deploying"),
            SubTask(description="Build project", tool_name="code_executor",
                    reasoning="Create production build"),
            SubTask(description="Version and commit", tool_name="git_commit",
                    reasoning="Save changes to version control"),
            SubTask(description="Push to remote", tool_name="git_commit",
                    reasoning="Deploy to remote repository"),
        ]

    @classmethod
    def _decompose_security_goal(cls, goal, desc):
        return [
            SubTask(description="Full system scan", tool_name="threat_full_scan",
                    reasoning="Scan all files for threats"),
            SubTask(description="Network scan", tool_name="threat_full_scan",
                    reasoning="Check for network-level threats"),
            SubTask(description="Dependency audit", tool_name="scan_dependencies",
                    reasoning="Check packages for CVEs"),
            SubTask(description="Generate security report", tool_name="file_write",
                    reasoning="Document all findings"),
        ]

    @classmethod
    def _decompose_generic_goal(cls, goal, desc):
        return [
            SubTask(description="Research and understand", tool_name="web_search",
                    reasoning="Gather information about the task"),
            SubTask(description="Plan approach", tool_name="code_analyzer",
                    reasoning="Decide on the best approach"),
            SubTask(description="Execute plan", tool_name="file_write",
                    reasoning="Carry out the planned action"),
            SubTask(description="Verify results", tool_name="code_executor",
                    reasoning="Check that the goal was achieved"),
        ]


# ══════════════════════════════════════════════════════════════
# Autonomous Loop — The Core ASI Engine
# ══════════════════════════════════════════════════════════════

class AutonomousLoop:
    """
    Continuous self-directed thinking engine.

    The OODA Loop (Observe-Orient-Decide-Act):
      1. OBSERVE  — Gather information about current state
      2. ORIENT   — Analyze observations, update world model
      3. DECIDE   — Choose the best action from alternatives
      4. ACT      — Execute the chosen action
      5. REFLECT  — Learn from the outcome
      6. REPEAT   — Continue until all goals are met

    Usage:
        loop = AutonomousLoop(tool_executor=my_executor)
        loop.add_goal("Build a REST API for user management")
        await loop.run(max_cycles=50)
    """

    def __init__(
        self,
        tool_executor: Optional[Callable] = None,
        generate_fn: Optional[Callable] = None,
        max_concurrent_tasks: int = 3,
        reflection_interval: int = 10,
        cognitive_load_limit: float = 0.85,
    ):
        self.tool_executor = tool_executor
        self.generate_fn = generate_fn
        self.max_concurrent = max_concurrent_tasks
        self.reflection_interval = reflection_interval
        self.cognitive_load_limit = cognitive_load_limit
        self.state = AgentState()
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {}
        self._decision_log: List[Dict] = []

    # ── Goal Management ──

    def add_goal(
        self,
        description: str,
        priority: Priority = Priority.MEDIUM,
        deadline: Optional[float] = None,
        context: Dict = None,
        success_criteria: str = "",
    ) -> Goal:
        """Add a new high-level goal."""
        goal = Goal(
            description=description,
            priority=priority,
            deadline=deadline,
            context=context or {},
            success_criteria=success_criteria,
        )
        # Decompose into sub-tasks
        goal.sub_tasks = GoalDecomposer.decompose(goal)
        self.state.goals.append(goal)

        self._think("decision", f"New goal added: '{description}' with {len(goal.sub_tasks)} sub-tasks",
                     confidence=0.8)
        logger.info(f"[ASI] Goal added: {goal.id} — {description}")
        return goal

    def cancel_goal(self, goal_id: str) -> bool:
        """Cancel a goal and all its sub-tasks."""
        for goal in self.state.goals:
            if goal.id == goal_id:
                goal.status = TaskStatus.CANCELLED
                for task in goal.sub_tasks:
                    if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                        task.status = TaskStatus.CANCELLED
                return True
        return False

    # ── Core Loop ──

    async def run(self, max_cycles: int = 100) -> Dict[str, Any]:
        """Run the autonomous thinking loop."""
        self._running = True
        self._think("reasoning", f"Autonomous loop starting. {len(self.state.goals)} goals to process.")

        while self._running and self.state.cycle_count < max_cycles:
            self.state.cycle_count += 1
            cycle_start = time.time()

            # Phase 1: OBSERVE — Gather state information
            observations = self._observe()

            # Phase 2: ORIENT — Analyze and prioritize
            priorities = self._orient(observations)

            # Phase 3: DECIDE — Choose next action
            decision = self._decide(priorities)

            # Phase 4: ACT — Execute the decision
            if decision:
                result = await self._act(decision)
            else:
                self._think("reasoning", "No actionable decisions — all goals complete or blocked.")
                break

            # Phase 5: REFLECT — Learn from outcome (periodic)
            if self.state.cycle_count % self.reflection_interval == 0:
                self._reflect()

            # Update cognitive load
            cycle_time = time.time() - cycle_start
            self.state.total_reasoning_time += cycle_time
            self.state.cognitive_load = min(1.0, self.state.cognitive_load + 0.05)

            # Check if all goals are resolved
            active_goals = [g for g in self.state.goals
                           if g.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)]
            if not active_goals:
                self._think("reasoning", "All goals resolved. Loop complete.")
                break

            # Prevent overload
            if self.state.cognitive_load > self.cognitive_load_limit:
                self._think("observation", "Cognitive load limit reached. Cooling down.")
                self.state.cognitive_load *= 0.7
                await asyncio.sleep(0.1)

        self._running = False
        self._reflect()  # Final reflection

        return self.get_report()

    def stop(self):
        """Stop the autonomous loop."""
        self._running = False

    # ── OODA Phases ──

    def _observe(self) -> Dict[str, Any]:
        """OBSERVE: Gather information about current state."""
        observations = {
            "active_goals": [],
            "pending_tasks": [],
            "blocked_tasks": [],
            "overdue_goals": [],
            "recent_failures": [],
        }

        for goal in self.state.goals:
            if goal.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                continue

            goal.update_progress()
            observations["active_goals"].append({
                "id": goal.id,
                "description": goal.description,
                "priority": goal.priority.value,
                "progress": goal.progress,
                "overdue": goal.is_overdue,
            })

            if goal.is_overdue:
                observations["overdue_goals"].append(goal.id)

            for task in goal.sub_tasks:
                if task.status == TaskStatus.PENDING and task.can_execute:
                    # Check dependencies
                    deps_met = all(
                        any(t.id == dep and t.status == TaskStatus.COMPLETED
                            for g in self.state.goals for t in g.sub_tasks)
                        for dep in task.depends_on
                    ) if task.depends_on else True

                    if deps_met:
                        observations["pending_tasks"].append({
                            "task_id": task.id,
                            "goal_id": goal.id,
                            "description": task.description,
                            "tool": task.tool_name,
                            "priority": goal.priority.value,
                        })
                    else:
                        observations["blocked_tasks"].append(task.id)

                elif task.status == TaskStatus.FAILED:
                    observations["recent_failures"].append({
                        "task_id": task.id,
                        "error": task.error,
                        "retries": task.retries,
                    })

        self.state.observations.append(observations)
        return observations

    def _orient(self, observations: Dict) -> List[Dict]:
        """ORIENT: Analyze observations and create prioritized action list."""
        priorities = []

        # Priority 1: Overdue goals
        for goal_id in observations["overdue_goals"]:
            for task in observations["pending_tasks"]:
                if task["goal_id"] == goal_id:
                    priorities.append({**task, "urgency": "critical",
                                        "reason": "Goal is overdue"})

        # Priority 2: High-priority goals
        for task in observations["pending_tasks"]:
            if task["priority"] <= Priority.HIGH.value:
                if not any(p["task_id"] == task["task_id"] for p in priorities):
                    priorities.append({**task, "urgency": "high",
                                        "reason": f"Priority {task['priority']}"})

        # Priority 3: Everything else
        for task in observations["pending_tasks"]:
            if not any(p["task_id"] == task["task_id"] for p in priorities):
                priorities.append({**task, "urgency": "normal",
                                    "reason": "Normal priority"})

        return priorities

    def _decide(self, priorities: List[Dict]) -> Optional[Dict]:
        """DECIDE: Choose the best action using multi-criteria analysis."""
        if not priorities:
            return None

        # Score each candidate action
        scored = []
        for action in priorities:
            score = 0.0

            # Urgency weight
            urgency_scores = {"critical": 100, "high": 70, "normal": 30}
            score += urgency_scores.get(action["urgency"], 10)

            # Priority weight (lower value = higher priority)
            score += (5 - action.get("priority", 3)) * 20

            # Prefer actions with higher confidence
            score += action.get("confidence", 0.5) * 10

            scored.append((score, action))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_action = scored[0]

        # Log the decision with alternatives
        alternatives = [s[1]["description"] for s in scored[1:3]]
        self._think(
            "decision",
            f"Chose: '{best_action['description']}' (score={best_score:.0f})",
            confidence=min(1.0, best_score / 100),
            alternatives=alternatives,
        )

        self.state.decisions_made += 1
        self._decision_log.append({
            "cycle": self.state.cycle_count,
            "chosen": best_action["description"],
            "score": best_score,
            "alternatives": len(scored) - 1,
            "urgency": best_action["urgency"],
        })

        return best_action

    async def _act(self, decision: Dict) -> Dict[str, Any]:
        """ACT: Execute the chosen action."""
        task_id = decision["task_id"]
        goal_id = decision["goal_id"]

        # Find the actual task
        task = None
        goal = None
        for g in self.state.goals:
            if g.id == goal_id:
                goal = g
                for t in g.sub_tasks:
                    if t.id == task_id:
                        task = t
                        break

        if not task:
            return {"success": False, "error": "Task not found"}

        task.mark_started()
        self._think("observation", f"Executing: {task.description} (tool={task.tool_name})")

        try:
            if self.tool_executor:
                result = await asyncio.to_thread(
                    self.tool_executor, task.tool_name, task.tool_args
                )
            else:
                # Simulate execution
                result = {"success": True, "simulated": True, "output": f"Executed {task.description}"}

            if isinstance(result, dict) and result.get("success", True):
                task.mark_completed(result)
                self.state.tasks_completed += 1
                self._think("observation",
                           f"Task completed: {task.description} ({task.duration:.2f}s)")
            else:
                error = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
                task.mark_failed(error)
                if task.status == TaskStatus.FAILED:
                    self.state.tasks_failed += 1
                self._think("observation", f"Task failed: {task.description} — {error}")

            # Update goal progress
            if goal:
                goal.update_progress()

            # Emit callback
            self._emit("task_completed" if task.status == TaskStatus.COMPLETED else "task_failed",
                       {"task": task, "goal": goal})

            return result

        except Exception as e:
            task.mark_failed(str(e))
            self.state.tasks_failed += 1
            logger.error(f"[ASI] Execution error: {e}")
            return {"success": False, "error": str(e)}

    def _reflect(self):
        """REFLECT: Analyze recent performance and adapt."""
        self.state.last_reflection_at = time.time()
        self.state.mode = "reflecting"

        # Analyze success rate
        rate = self.state.success_rate
        self._think(
            "reflection",
            f"Cycle {self.state.cycle_count}: {self.state.tasks_completed} completed, "
            f"{self.state.tasks_failed} failed. Success rate: {rate:.1%}",
            confidence=0.9,
        )

        # Identify patterns in failures
        recent_failures = [
            t for g in self.state.goals for t in g.sub_tasks
            if t.status == TaskStatus.FAILED
        ]
        if recent_failures:
            failure_tools = {}
            for f in recent_failures:
                failure_tools[f.tool_name] = failure_tools.get(f.tool_name, 0) + 1
            worst_tool = max(failure_tools, key=failure_tools.get)
            self._think(
                "reflection",
                f"Tool '{worst_tool}' has highest failure count ({failure_tools[worst_tool]}). "
                f"Consider alternative approaches.",
                confidence=0.7,
            )

        # Cognitive load management
        if self.state.cognitive_load > 0.8:
            self._think("reflection", "High cognitive load — simplifying remaining tasks.")
            self.state.cognitive_load *= 0.6

        self.state.mode = "active"

    # ── Helper Methods ──

    def _think(self, thought_type: str, content: str,
               confidence: float = 0.5, alternatives: List[str] = None):
        """Record a thought in the agent's thought log."""
        record = ThoughtRecord(
            thought_type=thought_type,
            content=content,
            confidence=confidence,
            alternatives_considered=alternatives or [],
        )
        self.state.thought_log.append(record)

    def _emit(self, event: str, data: Any):
        """Emit event to registered callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"[ASI] Callback error: {e}")

    def on(self, event: str, callback: Callable):
        """Register event callback."""
        self._callbacks.setdefault(event, []).append(callback)

    def get_report(self) -> Dict[str, Any]:
        """Generate comprehensive execution report."""
        return {
            "cycles": self.state.cycle_count,
            "goals_total": len(self.state.goals),
            "goals_completed": sum(1 for g in self.state.goals if g.status == TaskStatus.COMPLETED),
            "goals_failed": sum(1 for g in self.state.goals if g.status == TaskStatus.FAILED),
            "tasks_completed": self.state.tasks_completed,
            "tasks_failed": self.state.tasks_failed,
            "success_rate": self.state.success_rate,
            "decisions_made": self.state.decisions_made,
            "total_reasoning_time": round(self.state.total_reasoning_time, 3),
            "thought_log_size": len(self.state.thought_log),
            "cognitive_load": round(self.state.cognitive_load, 3),
            "recent_thoughts": [
                {"type": t.thought_type, "content": t.content, "confidence": t.confidence}
                for t in list(self.state.thought_log)[-10:]
            ],
            "decision_log": self._decision_log[-20:],
        }

    def get_goal_status(self, goal_id: str) -> Optional[Dict]:
        """Get detailed status of a specific goal."""
        for goal in self.state.goals:
            if goal.id == goal_id:
                return {
                    "id": goal.id,
                    "description": goal.description,
                    "status": goal.status.value,
                    "progress": goal.progress,
                    "sub_tasks": [
                        {"id": t.id, "description": t.description,
                         "status": t.status.value, "tool": t.tool_name,
                         "duration": t.duration, "error": t.error}
                        for t in goal.sub_tasks
                    ],
                }
        return None
