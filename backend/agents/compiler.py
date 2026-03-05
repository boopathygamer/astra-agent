"""
Task Compiler — Module 1 of the 5-module blueprint.
─────────────────────────────────────────────────────
Compiler: x ↦ (goal, I/O, constraints, risks, tests)

Parses user requests into structured task specifications.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from agents.prompts.templates import COMPILER_PROMPT
from agents.safety.content_filter import ContentFilter, SafetyAction

logger = logging.getLogger(__name__)


@dataclass
class TaskSpec:
    """Structured task specification produced by the compiler."""
    raw_task: str = ""
    goal: str = ""
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    tools_needed: List[str] = field(default_factory=list)
    action_type: str = "general"

    def to_prompt(self) -> str:
        lines = [f"GOAL: {self.goal}"]
        if self.inputs:
            lines.append(f"INPUTS: {', '.join(self.inputs)}")
        if self.outputs:
            lines.append(f"OUTPUTS: {', '.join(self.outputs)}")
        if self.constraints:
            lines.append(f"CONSTRAINTS: {', '.join(self.constraints)}")
        if self.risks:
            lines.append(f"RISKS: {', '.join(self.risks)}")
        return "\n".join(lines)


class TaskCompiler:
    """
    Module 1 — Compiler: x ↦ (goal, I/O, constraints, risks, tests)

    Takes a raw user request and compiles it into a structured
    task specification that guides the rest of the agent pipeline.
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self._content_filter = ContentFilter()

    def compile(self, task: str, generate_fn: Optional[Callable] = None) -> TaskSpec:
        """
        Compile a raw task into a structured specification.

        Args:
            task: Raw user request
            generate_fn: LLM generation function

        Returns:
            Structured TaskSpec (or refused spec if content is harmful)
        """
        # ── Safety Gate: check input BEFORE any processing ──
        safety_verdict = self._content_filter.check_input(task)
        if safety_verdict.is_blocked:
            logger.warning(
                f"Task REFUSED by content filter: "
                f"category={safety_verdict.category.value}"
            )
            return TaskSpec(
                raw_task=task,
                goal=safety_verdict.refusal_message,
                action_type="refused",
                constraints=["CONTENT_BLOCKED"],
                risks=[safety_verdict.reason],
            )

        gen_fn = generate_fn or self.generate_fn
        spec = TaskSpec(raw_task=task)

        if gen_fn:
            # Use LLM to analyze the task
            prompt = COMPILER_PROMPT.format(task=task)
            response = gen_fn(prompt)
            spec = self._parse_spec(response, task)
        else:
            # Simple rule-based compilation
            spec = self._rule_based_compile(task)

        # Determine action type
        spec.action_type = self._classify_action_type(task)

        logger.info(f"Compiled task: goal='{spec.goal[:60]}', action={spec.action_type}")
        return spec

    def _parse_spec(self, response: str, raw_task: str) -> TaskSpec:
        """Parse LLM-generated specification."""
        spec = TaskSpec(raw_task=raw_task)

        current_section = None
        for line in response.split("\n"):
            line = line.strip()
            upper = line.upper()

            if upper.startswith("GOAL:"):
                spec.goal = line.split(":", 1)[1].strip()
                current_section = "goal"
            elif upper.startswith("INPUT"):
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    spec.inputs.append(content)
                current_section = "inputs"
            elif upper.startswith("OUTPUT"):
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    spec.outputs.append(content)
                current_section = "outputs"
            elif upper.startswith("CONSTRAINT"):
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    spec.constraints.append(content)
                current_section = "constraints"
            elif upper.startswith("RISK"):
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    spec.risks.append(content)
                current_section = "risks"
            elif upper.startswith("TEST"):
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    spec.tests.append(content)
                current_section = "tests"
            elif upper.startswith("TOOLS"):
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    spec.tools_needed.extend(
                        [t.strip() for t in content.split(",")]
                    )
                current_section = "tools"
            elif line.startswith("- ") and current_section:
                content = line[2:].strip()
                if current_section == "inputs":
                    spec.inputs.append(content)
                elif current_section == "outputs":
                    spec.outputs.append(content)
                elif current_section == "constraints":
                    spec.constraints.append(content)
                elif current_section == "risks":
                    spec.risks.append(content)
                elif current_section == "tests":
                    spec.tests.append(content)
                elif current_section == "tools":
                    spec.tools_needed.append(content)

        if not spec.goal:
            spec.goal = raw_task

        return spec

    def _rule_based_compile(self, task: str) -> TaskSpec:
        """Simple rule-based task compilation (no LLM needed)."""
        spec = TaskSpec(raw_task=task, goal=task)

        lower = task.lower()

        # Detect if images are involved
        if any(w in lower for w in ["image", "picture", "photo", "screenshot"]):
            spec.tools_needed.append("analyze_image")

        # Detect if code execution is needed
        if any(w in lower for w in ["run", "execute", "code", "python", "calculate"]):
            spec.tools_needed.append("execute_python")

        # Detect if web search is needed
        if any(w in lower for w in ["search", "find", "look up", "what is", "who is"]):
            spec.tools_needed.append("web_search")

        # Detect if file operations are needed
        if any(w in lower for w in ["file", "read", "write", "save", "create"]):
            spec.tools_needed.append("read_file")

        return spec

    def _classify_action_type(self, task: str) -> str:
        """Classify the risk level of the task."""
        lower = task.lower()

        if any(w in lower for w in ["delete", "remove", "destroy"]):
            return "file_delete"
        if any(w in lower for w in ["write", "save", "create file", "modify"]):
            return "file_write"
        if any(w in lower for w in ["execute", "run code", "run script"]):
            return "code_execution"
        if any(w in lower for w in ["download", "fetch", "request", "api"]):
            return "web_request"
        if any(w in lower for w in ["system", "command", "shell", "terminal"]):
            return "system_command"

        return "general"
