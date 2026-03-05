"""
Session Tools — Register agent-to-agent tools.
───────────────────────────────────────────────
Tools registered:
  sessions_list    — discover active sessions
  sessions_history — fetch transcript logs
  sessions_send    — message another session
  sessions_spawn   — start a sub-agent task
  session_status   — get current session info
"""

import logging
from typing import Optional

from agents.tools.registry import tool_registry, ToolRiskLevel

logger = logging.getLogger(__name__)

# Session manager will be injected at startup
_session_manager = None


def set_session_manager(manager):
    """Inject the session manager instance (called at startup)."""
    global _session_manager
    _session_manager = manager


def _get_manager():
    if _session_manager is None:
        raise RuntimeError("SessionManager not initialized. Call set_session_manager() first.")
    return _session_manager


def register_session_tools():
    """Register all session tools with the tool registry."""

    @tool_registry.register(
        name="sessions_list",
        description=(
            "List active sessions. Returns session IDs, types, labels, "
            "and message counts. Use to discover available sessions for "
            "inter-agent communication."
        ),
        risk_level=ToolRiskLevel.LOW,
        parameter_schema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Filter by agent ID. Omit for all agents.",
                },
                "active_only": {
                    "type": "boolean",
                    "description": "Only show active sessions. Default true.",
                    "default": True,
                },
            },
        },
    )
    def sessions_list(agent_id: str = None, active_only: bool = True) -> dict:
        mgr = _get_manager()
        sessions = mgr.list_sessions(agent_id=agent_id, active_only=active_only)
        return {"sessions": sessions, "count": len(sessions)}

    @tool_registry.register(
        name="sessions_history",
        description=(
            "Fetch transcript history for a session. Returns messages "
            "with roles, content, and timestamps. Use include_tools=false "
            "to filter out tool messages."
        ),
        risk_level=ToolRiskLevel.LOW,
        parameter_schema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID to fetch history for.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max messages to return. Returns last N.",
                    "default": 20,
                },
                "include_tools": {
                    "type": "boolean",
                    "description": "Include tool call messages. Default false.",
                    "default": False,
                },
            },
            "required": ["session_id"],
        },
    )
    def sessions_history(
        session_id: str,
        limit: int = 20,
        include_tools: bool = False,
    ) -> dict:
        mgr = _get_manager()
        messages = mgr.get_history(
            session_id=session_id,
            limit=limit,
            include_tools=include_tools,
        )
        return {"session_id": session_id, "messages": messages, "count": len(messages)}

    @tool_registry.register(
        name="sessions_send",
        description=(
            "Send a message to another session. The target agent will "
            "process the message and return a response. Use for "
            "inter-agent coordination without switching chat surfaces."
        ),
        risk_level=ToolRiskLevel.MEDIUM,
        parameter_schema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Target session ID to send message to.",
                },
                "message": {
                    "type": "string",
                    "description": "Message content to send.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Max wait time for response. 0 = fire-and-forget.",
                    "default": 30,
                },
            },
            "required": ["session_id", "message"],
        },
    )
    def sessions_send(
        session_id: str,
        message: str,
        timeout_seconds: int = 30,
    ) -> dict:
        mgr = _get_manager()
        return mgr.sessions_send(
            target_session_id=session_id,
            message=message,
            timeout_seconds=timeout_seconds,
        )

    @tool_registry.register(
        name="sessions_spawn",
        description=(
            "Spawn a sub-agent session for a specific task. Creates a new "
            "isolated session and runs the task. Returns session_id for "
            "tracking. Use for delegating independent work."
        ),
        risk_level=ToolRiskLevel.MEDIUM,
        parameter_schema={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description for the sub-agent.",
                },
                "label": {
                    "type": "string",
                    "description": "Human-readable label for the session.",
                },
                "agent_id": {
                    "type": "string",
                    "description": "Agent to handle the task. Default: current agent.",
                },
            },
            "required": ["task"],
        },
    )
    def sessions_spawn(
        task: str,
        label: str = "",
        agent_id: str = None,
    ) -> dict:
        mgr = _get_manager()
        return mgr.sessions_spawn(task=task, label=label, agent_id=agent_id)

    @tool_registry.register(
        name="session_status",
        description=(
            "Get status of the current or a specific session. Returns "
            "session type, message count, model, and activity timestamps."
        ),
        risk_level=ToolRiskLevel.LOW,
        parameter_schema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID. Omit for current session.",
                },
            },
        },
    )
    def session_status(session_id: str = None) -> dict:
        mgr = _get_manager()
        return mgr.session_status(session_id=session_id)

    logger.info("Registered 5 session tools")
