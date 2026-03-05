"""
Tool Registry — Decorator-based tool registration with risk levels.
Now integrated with Tool Policy Engine for allow/deny resolution.
"""

import logging
import subprocess  # nosec B404
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from config.settings import agent_config

# Import the Police Agent and Court to intercept illegal actions
try:
    from agents.justice.police import police_dispatcher
except ImportError:
    police_dispatcher = None

logger = logging.getLogger(__name__)


class ToolRiskLevel(Enum):
    LOW = "low"           # Reading, analysis
    MEDIUM = "medium"     # Calculations, formatting
    HIGH = "high"         # File writes, web requests
    CRITICAL = "critical" # System commands, deletions


# Backward-compatible alias
RiskLevel = ToolRiskLevel


@dataclass
class Tool:
    """A registered tool that agents can use."""
    name: str
    description: str
    func: Callable
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_sandbox: bool = False
    group: str = ""  # e.g., "group:fs", "group:runtime"

    def to_schema(self) -> dict:
        """Convert to function-calling schema for the LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "risk_level": self.risk_level.value,
        }


class ToolRegistry:
    """
    Central registry for all agent tools.

    Tools are registered via decorator or explicit registration.
    Each tool has a risk level that determines gating behavior.
    Integrates with ToolPolicyEngine for allow/deny resolution.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._execution_log: List[dict] = []
        self._policy_engine = None

    def set_policy_engine(self, policy_engine):
        """Attach a ToolPolicyEngine for access control."""
        self._policy_engine = policy_engine

    def register(
        self,
        name: str,
        description: str,
        risk_level: ToolRiskLevel = ToolRiskLevel.LOW,
        parameters: Optional[Dict[str, Any]] = None,
        parameter_schema: Optional[Dict[str, Any]] = None,
        group: str = "",
    ) -> Callable:
        """Decorator to register a tool function."""
        def decorator(func: Callable) -> Callable:
            tool = Tool(
                name=name,
                description=description,
                func=func,
                risk_level=risk_level,
                parameters=parameter_schema or parameters or {},
                requires_sandbox=risk_level in (ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL),
                group=group,
            )
            self._tools[name] = tool
            logger.info(f"Registered tool: {name} (risk={risk_level.value})")
            return func
        return decorator

    def register_tool(self, tool: Tool):
        """Explicitly register a Tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_schemas(self) -> List[dict]:
        """Get all tool schemas for LLM function calling."""
        return [t.to_schema() for t in self._tools.values()]

    def get_allowed_schemas(self, context=None) -> List[dict]:
        """Get tool schemas filtered by policy engine."""
        if self._policy_engine:
            all_names = list(self._tools.keys())
            allowed = self._policy_engine.get_allowed_tools(all_names, context)
            return [self._tools[n].to_schema() for n in allowed if n in self._tools]
        return self.get_schemas()

    def execute(
        self,
        tool_name: str,
        sandbox: bool = False,
        policy_context=None,
        **kwargs,
    ) -> dict:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            sandbox: Whether to execute in sandbox mode
            policy_context: PolicyContext for access control
            **kwargs: Arguments to pass to the tool

        Returns:
            {"success": bool, "result": Any, "error": str|None}
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return {"success": False, "result": None, "error": f"Unknown tool: {tool_name}"}

        # Check policy engine
        if self._policy_engine and policy_context:
            if not self._policy_engine.resolve(tool_name, policy_context):
                return {
                    "success": False,
                    "result": None,
                    "error": f"Tool '{tool_name}' denied by policy",
                }
                
        # 🚓 The Police Agent Patrols the Registry
        if police_dispatcher:
            # Send the execution parameters to the Police for Rule 1 / Rule 2 inspection
            allowed_by_police = police_dispatcher.patrol_hook(agent_name="System", tool_name=tool_name, args=kwargs)
            if not allowed_by_police:
                return {
                    "success": False,
                    "result": None,
                    "error": f"⚖️ JUSTICE SYSTEM ALARM: The Police Force arrested tool '{tool_name}' for violating core rules."
                }

        # Enforce sandbox for high-risk tools
        if tool.requires_sandbox and not sandbox:
            logger.warning(
                f"Tool '{tool_name}' requires sandbox but sandbox=False. "
                f"Executing in sandbox mode anyway."
            )
            sandbox = True

        try:
            if sandbox:
                result = self._execute_sandboxed(tool, **kwargs)
            else:
                result = tool.func(**kwargs)

            log_entry = {
                "tool": tool_name,
                "args": kwargs,
                "success": True,
                "sandboxed": sandbox,
            }
            self._execution_log.append(log_entry)

            return {"success": True, "result": result, "error": None}

        except Exception as e:
            log_entry = {
                "tool": tool_name,
                "args": kwargs,
                "success": False,
                "error": str(e),
                "sandboxed": sandbox,
            }
            self._execution_log.append(log_entry)
            return {"success": False, "result": None, "error": str(e)}

    def _execute_sandboxed(self, tool: Tool, **kwargs) -> Any:
        """Execute a tool in a sandboxed subprocess with timeout."""
        timeout = agent_config.sandbox_timeout

        # For Python-callable tools, just wrap with timeout
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(tool.func, **kwargs)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(
                    f"Tool '{tool.name}' timed out after {timeout}s"
                )

    def get_execution_log(self) -> List[dict]:
        return list(self._execution_log)


# ──────────────────────────────────────────────
# Global registry instance
# ──────────────────────────────────────────────
registry = ToolRegistry()

# Alias for backward compatibility
tool_registry = registry
