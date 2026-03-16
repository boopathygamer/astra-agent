"""
Workflow Engine — Natural Language → Automated Recurring Missions
════════════════════════════════════════════════════════════════
Converts natural language instructions into scheduled, recurring
workflows that execute autonomously via the mission controller.

Capabilities:
  1. NL Parsing         — "Every morning, check my repos" → cron schedule
  2. Workflow DAG       — Multi-step workflows with conditions
  3. Cron Scheduler     — Flexible scheduling with cron expressions
  4. Trigger System     — Event-based triggers (file change, time, etc.)
  5. Execution History  — Full audit trail of workflow runs
  6. Pause/Resume       — Control workflow lifecycle
"""

import hashlib
import json
import logging
import re
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    SCHEDULE = "schedule"         # Cron-based
    EVENT = "event"              # Bus event
    FILE_CHANGE = "file_change"  # File system change
    MANUAL = "manual"            # User-triggered
    STARTUP = "startup"          # On system start
    CONDITION = "condition"      # When condition is met


class WorkflowStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


class StepType(Enum):
    ACTION = "action"
    CONDITION = "condition"
    PARALLEL = "parallel"
    WAIT = "wait"
    NOTIFY = "notify"


@dataclass
class WorkflowTrigger:
    """When to execute a workflow."""
    trigger_type: TriggerType = TriggerType.MANUAL
    cron_expression: str = ""    # e.g., "0 9 * * *" for 9am daily
    event_topic: str = ""        # Bus topic to listen on
    file_path: str = ""          # File to watch
    condition: str = ""          # Natural language condition
    next_run: float = 0.0
    last_run: float = 0.0

    def is_due(self) -> bool:
        if self.trigger_type == TriggerType.SCHEDULE and self.next_run > 0:
            return time.time() >= self.next_run
        return False

    def compute_next_run(self) -> None:
        """Compute next run time from cron expression."""
        if not self.cron_expression:
            return
        self.last_run = time.time()
        parts = self.cron_expression.strip().split()
        if len(parts) < 5:
            return

        # Simple cron parsing for common patterns
        minute, hour = parts[0], parts[1]
        now = time.time()

        try:
            target_hour = int(hour) if hour != "*" else -1
            target_minute = int(minute) if minute != "*" else 0

            import datetime
            dt = datetime.datetime.fromtimestamp(now)

            if target_hour >= 0:
                next_dt = dt.replace(hour=target_hour, minute=target_minute, second=0)
                if next_dt <= dt:
                    next_dt += datetime.timedelta(days=1)
                self.next_run = next_dt.timestamp()
            else:
                # Every hour at target_minute
                next_dt = dt.replace(minute=target_minute, second=0)
                if next_dt <= dt:
                    next_dt += datetime.timedelta(hours=1)
                self.next_run = next_dt.timestamp()
        except Exception:
            self.next_run = now + 3600  # Fallback: 1 hour


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    step_id: str = ""
    name: str = ""
    step_type: StepType = StepType.ACTION
    action: str = ""            # What to do (natural language or command)
    condition: str = ""         # For conditional steps
    timeout_s: float = 120.0
    on_failure: str = "continue"  # continue, abort, retry
    result: Any = None
    status: str = "pending"
    error: str = ""

    def __post_init__(self):
        if not self.step_id:
            self.step_id = hashlib.md5(
                f"{self.name}_{time.time()}".encode()
            ).hexdigest()[:8]


@dataclass
class Workflow:
    """A complete workflow definition."""
    workflow_id: str = ""
    name: str = ""
    description: str = ""
    original_instruction: str = ""  # The NL instruction that created this
    trigger: WorkflowTrigger = field(default_factory=WorkflowTrigger)
    steps: List[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.DRAFT
    run_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_run_at: float = 0.0
    max_runs: int = 0          # 0 = unlimited
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.workflow_id:
            self.workflow_id = f"wf_{hashlib.md5(f'{self.name}_{self.created_at}'.encode()).hexdigest()[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "trigger_type": self.trigger.trigger_type.value,
            "cron": self.trigger.cron_expression,
            "steps": len(self.steps),
            "run_count": self.run_count,
            "success_rate": (
                f"{self.success_count / max(self.run_count, 1):.0%}"
            ),
        }


@dataclass
class WorkflowRun:
    """Record of a single workflow execution."""
    run_id: str = ""
    workflow_id: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    success: bool = False
    steps_completed: int = 0
    steps_total: int = 0
    error: str = ""
    results: List[Dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.run_id:
            self.run_id = hashlib.md5(
                f"{self.workflow_id}_{self.started_at}".encode()
            ).hexdigest()[:10]


# NL → Schedule parsing patterns
SCHEDULE_PATTERNS = [
    (r"every\s+morning", "0 9 * * *"),
    (r"every\s+evening", "0 18 * * *"),
    (r"every\s+hour", "0 * * * *"),
    (r"every\s+(\d+)\s+minutes?", "*/\\1 * * * *"),
    (r"every\s+(\d+)\s+hours?", "0 */\\1 * * *"),
    (r"daily\s+at\s+(\d{1,2})", "0 \\1 * * *"),
    (r"every\s+day", "0 9 * * *"),
    (r"twice\s+a\s+day", "0 9,18 * * *"),
    (r"every\s+monday", "0 9 * * 1"),
    (r"weekly", "0 9 * * 1"),
    (r"at\s+(\d{1,2}):(\d{2})", "\\2 \\1 * * *"),
]


class WorkflowEngine:
    """
    Natural language workflow builder with cron scheduling,
    event triggers, and automated execution via missions.
    """

    MAX_WORKFLOWS = 100
    MAX_HISTORY = 500

    def __init__(self, generate_fn: Optional[Callable] = None,
                 data_dir: Optional[str] = None):
        self.generate_fn = generate_fn
        self.data_dir = Path(data_dir) if data_dir else Path("data/workflows")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._workflows: Dict[str, Workflow] = {}
        self._run_history: Deque[WorkflowRun] = deque(maxlen=self.MAX_HISTORY)
        self._scheduler_running = False
        self._scheduler_thread: Optional[threading.Thread] = None

        self._load()
        logger.info(f"[WORKFLOW] Engine initialized with {len(self._workflows)} workflows")

    # ── NL Parsing ──

    def create_from_instruction(self, instruction: str) -> Workflow:
        """Parse natural language instruction into a workflow."""
        # Detect schedule
        cron = self._parse_schedule(instruction)
        trigger_type = TriggerType.SCHEDULE if cron else TriggerType.MANUAL

        trigger = WorkflowTrigger(
            trigger_type=trigger_type,
            cron_expression=cron,
        )
        if cron:
            trigger.compute_next_run()

        # Extract action steps
        steps = self._parse_steps(instruction)

        # Generate name and description
        name = self._generate_name(instruction)

        workflow = Workflow(
            name=name,
            description=instruction,
            original_instruction=instruction,
            trigger=trigger,
            steps=steps,
            status=WorkflowStatus.ACTIVE,
        )

        self._workflows[workflow.workflow_id] = workflow
        self._save()
        logger.info(f"[WORKFLOW] Created: '{name}' ({len(steps)} steps, trigger={trigger_type.value})")
        return workflow

    def _parse_schedule(self, text: str) -> str:
        """Extract cron schedule from natural language."""
        text_lower = text.lower()
        for pattern, cron_template in SCHEDULE_PATTERNS:
            m = re.search(pattern, text_lower)
            if m:
                cron = cron_template
                for i, group in enumerate(m.groups(), 1):
                    cron = cron.replace(f"\\{i}", group)
                return cron
        return ""

    def _parse_steps(self, instruction: str) -> List[WorkflowStep]:
        """Extract workflow steps from instruction."""
        steps = []

        # Try to split by "then", "and then", numbers
        parts = re.split(
            r'(?:,?\s*(?:then|and then|after that|next|finally)\s+|'
            r'\d+[\.\)]\s*)',
            instruction, flags=re.IGNORECASE,
        )
        parts = [p.strip() for p in parts if p.strip() and len(p) > 5]

        # Remove schedule-related prefixes
        for pattern, _ in SCHEDULE_PATTERNS:
            parts = [re.sub(pattern, "", p, flags=re.IGNORECASE).strip() for p in parts]
        parts = [p for p in parts if p and len(p) > 3]

        if not parts:
            parts = [instruction]

        for i, part in enumerate(parts):
            # Detect step type
            if any(kw in part.lower() for kw in ["if ", "when ", "only if"]):
                step_type = StepType.CONDITION
            elif any(kw in part.lower() for kw in ["notify", "alert", "email", "send"]):
                step_type = StepType.NOTIFY
            elif any(kw in part.lower() for kw in ["wait", "pause", "delay"]):
                step_type = StepType.WAIT
            else:
                step_type = StepType.ACTION

            steps.append(WorkflowStep(
                name=f"Step {i + 1}: {part[:50]}",
                step_type=step_type,
                action=part,
            ))

        return steps

    def _generate_name(self, instruction: str) -> str:
        """Generate a concise workflow name."""
        words = instruction.split()[:6]
        name = " ".join(words)
        if len(name) > 50:
            name = name[:47] + "..."
        return name

    # ── Execution ──

    def execute_workflow(self, workflow_id: str,
                         task_callback: Optional[Callable] = None) -> WorkflowRun:
        """Execute a workflow's steps."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")

        run = WorkflowRun(
            workflow_id=workflow_id,
            steps_total=len(wf.steps),
        )

        for step in wf.steps:
            step.status = "running"
            try:
                if step.step_type == StepType.WAIT:
                    # Parse wait duration
                    m = re.search(r'(\d+)\s*(seconds?|minutes?|hours?)',
                                  step.action, re.IGNORECASE)
                    if m:
                        amount = int(m.group(1))
                        unit = m.group(2).lower()
                        if "minute" in unit:
                            amount *= 60
                        elif "hour" in unit:
                            amount *= 3600
                        time.sleep(min(amount, 10))
                    step.result = "Wait completed"
                elif self.generate_fn:
                    prompt = f"Execute this workflow step:\n{step.action}\nProvide a concise result."
                    step.result = self.generate_fn(prompt)
                else:
                    step.result = f"Step '{step.name}' executed (no executor)"

                step.status = "completed"
                run.steps_completed += 1
                run.results.append({
                    "step": step.name, "status": "completed",
                    "result": str(step.result)[:200],
                })

                if task_callback:
                    task_callback({
                        "event": "step_completed",
                        "workflow_id": workflow_id,
                        "step": step.name,
                    })

            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                run.results.append({
                    "step": step.name, "status": "failed", "error": str(e),
                })
                if step.on_failure == "abort":
                    run.error = f"Step '{step.name}' failed: {e}"
                    break

        # Finalize run
        run.completed_at = time.time()
        run.success = run.steps_completed == run.steps_total
        wf.run_count += 1
        wf.last_run_at = time.time()
        if run.success:
            wf.success_count += 1
        else:
            wf.fail_count += 1

        # Check max runs
        if wf.max_runs > 0 and wf.run_count >= wf.max_runs:
            wf.status = WorkflowStatus.COMPLETED

        # Update trigger schedule
        if wf.trigger.trigger_type == TriggerType.SCHEDULE:
            wf.trigger.compute_next_run()

        self._run_history.append(run)
        self._save()
        return run

    # ── Scheduler ──

    def start_scheduler(self) -> None:
        """Start the background scheduler thread."""
        if self._scheduler_running:
            return
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="workflow-scheduler",
        )
        self._scheduler_thread.start()
        logger.info("[WORKFLOW] Scheduler started")

    def stop_scheduler(self) -> None:
        self._scheduler_running = False
        logger.info("[WORKFLOW] Scheduler stopped")

    def _scheduler_loop(self) -> None:
        while self._scheduler_running:
            try:
                for wf in self._workflows.values():
                    if (wf.status == WorkflowStatus.ACTIVE and
                            wf.trigger.is_due()):
                        logger.info(f"[WORKFLOW] Scheduled run: {wf.name}")
                        self.execute_workflow(wf.workflow_id)
            except Exception as e:
                logger.error(f"[WORKFLOW] Scheduler error: {e}")
            time.sleep(30)  # Check every 30 seconds

    # ── Management ──

    def pause_workflow(self, workflow_id: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if wf:
            wf.status = WorkflowStatus.PAUSED
            self._save()
            return True
        return False

    def resume_workflow(self, workflow_id: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if wf and wf.status == WorkflowStatus.PAUSED:
            wf.status = WorkflowStatus.ACTIVE
            self._save()
            return True
        return False

    def delete_workflow(self, workflow_id: str) -> bool:
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            self._save()
            return True
        return False

    def check_event_triggers(self, event_text: str) -> List[str]:
        """Check if any workflows have event triggers matching this text.
        Returns list of triggered workflow IDs."""
        triggered = []
        event_lower = event_text.lower()
        event_words = set(event_lower.split())

        for wf in self._workflows.values():
            if wf.status != WorkflowStatus.ACTIVE:
                continue
            if wf.trigger.trigger_type != TriggerType.EVENT:
                continue

            # Check keyword overlap with event topic
            topic_words = set(wf.trigger.event_topic.lower().split())
            if topic_words & event_words:
                logger.info(f"[WORKFLOW] Event trigger matched: {wf.name}")
                try:
                    self.execute_workflow(wf.workflow_id)
                    triggered.append(wf.workflow_id)
                except Exception as e:
                    logger.warning(f"[WORKFLOW] Event-triggered run failed: {e}")

        return triggered

    def list_workflows(self) -> List[Dict]:
        return [wf.to_dict() for wf in self._workflows.values()]

    def get_run_history(self, workflow_id: str = None, limit: int = 20) -> List[Dict]:
        runs = list(self._run_history)
        if workflow_id:
            runs = [r for r in runs if r.workflow_id == workflow_id]
        return [
            {
                "run_id": r.run_id, "workflow_id": r.workflow_id,
                "success": r.success, "steps": f"{r.steps_completed}/{r.steps_total}",
                "duration_s": r.completed_at - r.started_at if r.completed_at else 0,
            }
            for r in runs[-limit:]
        ]

    # ── Persistence ──

    def _save(self) -> None:
        path = self.data_dir / "workflows.json"
        try:
            data = {wid: wf.to_dict() for wid, wf in self._workflows.items()}
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"[WORKFLOW] Save failed: {e}")

    def _load(self) -> None:
        path = self.data_dir / "workflows.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"[WORKFLOW] Loaded {len(data)} workflow definitions")
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        active = sum(1 for wf in self._workflows.values()
                    if wf.status == WorkflowStatus.ACTIVE)
        return {
            "total_workflows": len(self._workflows),
            "active_workflows": active,
            "total_runs": sum(wf.run_count for wf in self._workflows.values()),
            "scheduler_running": self._scheduler_running,
        }
