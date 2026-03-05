"""
Task Planner Tool — Intelligent Goal Decomposition & Scheduling.
─────────────────────────────────────────────────────────────────
Helps ALL users break big goals into actionable steps:
  - Goal → subtask decomposition
  - Priority assignment (urgent/important matrix)
  - Time estimation
  - Dependency tracking
  - Daily/weekly schedule generation
  - Progress tracking
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Eisenhower matrix priority levels."""
    CRITICAL = "🔴 Do First"        # Urgent + Important
    HIGH = "🟠 Schedule"             # Not Urgent + Important
    MEDIUM = "🟡 Delegate"           # Urgent + Not Important
    LOW = "🟢 Eliminate/Defer"       # Not Urgent + Not Important


@dataclass
class Task:
    """A single actionable task."""
    id: int = 0
    title: str = ""
    description: str = ""
    priority: Priority = Priority.MEDIUM
    estimated_hours: float = 1.0
    depends_on: List[int] = field(default_factory=list)
    category: str = ""
    completed: bool = False
    due_date: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority.value,
            "hours": self.estimated_hours,
            "depends_on": self.depends_on,
            "category": self.category,
            "completed": self.completed,
            "due_date": self.due_date,
        }


@dataclass
class Plan:
    """A complete task plan."""
    goal: str = ""
    tasks: List[Task] = field(default_factory=list)
    total_hours: float = 0.0
    estimated_days: int = 0
    categories: List[str] = field(default_factory=list)

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self.tasks if t.completed)

    @property
    def progress_percent(self) -> float:
        if not self.tasks:
            return 0.0
        return round(self.completed_count / len(self.tasks) * 100, 1)


class TaskPlanner:
    """
    Intelligent task planning and scheduling.

    Capabilities:
      - Decompose goals into subtasks
      - Assign priorities using Eisenhower matrix
      - Estimate time and create schedules
      - Track dependencies between tasks
      - Generate daily/weekly views
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self._generate = generate_fn
        self._plans: Dict[str, Plan] = {}
        self._next_id = 1
        logger.info("TaskPlanner initialized")

    def create_plan(self, goal: str, tasks: List[Dict] = None) -> Plan:
        """
        Create a new plan from a goal and optional task list.

        Args:
            goal: The high-level goal
            tasks: Optional list of task dicts with title, priority, hours

        Returns:
            Plan with structured tasks
        """
        plan = Plan(goal=goal)

        if tasks:
            for t in tasks:
                task = Task(
                    id=self._next_id,
                    title=t.get("title", ""),
                    description=t.get("description", ""),
                    priority=self._parse_priority(t.get("priority", "medium")),
                    estimated_hours=t.get("hours", 1.0),
                    depends_on=t.get("depends_on", []),
                    category=t.get("category", ""),
                )
                plan.tasks.append(task)
                self._next_id += 1

        plan.total_hours = sum(t.estimated_hours for t in plan.tasks)
        plan.estimated_days = max(1, int(plan.total_hours / 6))  # ~6 productive hours/day
        plan.categories = list(set(t.category for t in plan.tasks if t.category))

        self._plans[goal] = plan
        return plan

    def decompose_goal(self, goal: str, context: str = "") -> str:
        """
        Generate a prompt to decompose a goal into tasks using LLM.

        Returns a structured prompt that produces a task breakdown.
        """
        prompt = f"""\
Break down this goal into specific, actionable tasks:

GOAL: {goal}
{f'CONTEXT: {context}' if context else ''}

For each task, provide:
1. Task title (clear, actionable — starts with a verb)
2. Priority: critical / high / medium / low
3. Estimated time (hours)
4. Dependencies (which tasks must be done first)
5. Category (group related tasks)

Format each task as:
TASK: [title]
PRIORITY: [critical/high/medium/low]
HOURS: [estimated hours]
DEPENDS_ON: [list of prerequisite task numbers, or "none"]
CATEGORY: [category name]

Aim for 5-10 specific tasks. Make them:
- Specific enough to act on immediately
- Small enough to complete in 1-4 hours
- Ordered logically (dependencies first)

TASK BREAKDOWN:"""

        if self._generate:
            try:
                return self._generate(prompt)
            except Exception as e:
                logger.error(f"Goal decomposition failed: {e}")

        return prompt

    # ──────────────────────────────────────────
    # Schedule Generation
    # ──────────────────────────────────────────

    def generate_schedule(
        self,
        plan: Plan,
        hours_per_day: float = 6.0,
        start_date: str = None,
    ) -> List[Dict]:
        """
        Generate a day-by-day schedule from a plan.

        Args:
            plan: The plan to schedule
            hours_per_day: Available productive hours per day
            start_date: Start date (YYYY-MM-DD), defaults to today

        Returns:
            List of daily schedules with tasks
        """
        if start_date:
            current_date = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            current_date = datetime.now()

        # Sort tasks: critical first, then by dependencies
        sorted_tasks = sorted(
            [t for t in plan.tasks if not t.completed],
            key=lambda t: (
                0 if t.priority == Priority.CRITICAL else
                1 if t.priority == Priority.HIGH else
                2 if t.priority == Priority.MEDIUM else 3,
                len(t.depends_on),
            ),
        )

        schedule = []
        remaining_today = hours_per_day
        day_tasks = []

        for task in sorted_tasks:
            if task.estimated_hours <= remaining_today:
                day_tasks.append(task.to_dict())
                remaining_today -= task.estimated_hours
            else:
                # Save current day and start new one
                if day_tasks:
                    schedule.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "day": current_date.strftime("%A"),
                        "tasks": day_tasks,
                        "hours_planned": round(hours_per_day - remaining_today, 1),
                    })
                current_date += timedelta(days=1)
                # Skip weekends
                while current_date.weekday() >= 5:
                    current_date += timedelta(days=1)
                day_tasks = [task.to_dict()]
                remaining_today = hours_per_day - task.estimated_hours

        # Don't forget last day
        if day_tasks:
            schedule.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "day": current_date.strftime("%A"),
                "tasks": day_tasks,
                "hours_planned": round(hours_per_day - remaining_today, 1),
            })

        return schedule

    # ──────────────────────────────────────────
    # Progress Tracking
    # ──────────────────────────────────────────

    def mark_complete(self, plan: Plan, task_id: int) -> bool:
        """Mark a task as complete."""
        for task in plan.tasks:
            if task.id == task_id:
                task.completed = True
                return True
        return False

    def get_progress(self, plan: Plan) -> Dict[str, Any]:
        """Get progress report for a plan."""
        total = len(plan.tasks)
        done = plan.completed_count
        remaining_hours = sum(t.estimated_hours for t in plan.tasks if not t.completed)

        # Priority breakdown
        priority_counts = {}
        for t in plan.tasks:
            key = t.priority.value
            if key not in priority_counts:
                priority_counts[key] = {"total": 0, "done": 0}
            priority_counts[key]["total"] += 1
            if t.completed:
                priority_counts[key]["done"] += 1

        return {
            "goal": plan.goal,
            "total_tasks": total,
            "completed": done,
            "remaining": total - done,
            "progress": f"{plan.progress_percent}%",
            "remaining_hours": remaining_hours,
            "by_priority": priority_counts,
        }

    # ──────────────────────────────────────────
    # Display
    # ──────────────────────────────────────────

    def format_plan(self, plan: Plan) -> str:
        """Format a plan as a readable string."""
        lines = [
            f"📋 **Plan: {plan.goal}**",
            f"Tasks: {len(plan.tasks)} | Hours: {plan.total_hours} | "
            f"Days: ~{plan.estimated_days}",
            "",
        ]

        for task in plan.tasks:
            status = "✅" if task.completed else "⬜"
            lines.append(
                f"{status} {task.id}. {task.title} "
                f"({task.priority.value}, {task.estimated_hours}h)"
            )
            if task.depends_on:
                lines.append(f"   └─ depends on: {task.depends_on}")

        lines.append(f"\n📊 Progress: {plan.progress_percent}%")
        return "\n".join(lines)

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _parse_priority(text: str) -> Priority:
        """Parse a priority string."""
        t = text.lower().strip()
        if t in ("critical", "urgent", "do first"):
            return Priority.CRITICAL
        if t in ("high", "important", "schedule"):
            return Priority.HIGH
        if t in ("medium", "delegate", "normal"):
            return Priority.MEDIUM
        return Priority.LOW
