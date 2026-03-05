"""
Tool Policy Engine — OpenClaw-inspired allow/deny chains.
──────────────────────────────────────────────────────────
Resolution chain:
  Global → Agent → Session → Sandbox
  Deny always wins.

Tool groups expand to multiple tools:
  group:fs       → read_file, write_file, list_directory, apply_patch
  group:runtime  → execute_python, evaluate_expression
  group:web      → web_search, web_fetch
  group:memory   → memory_search, memory_get
  group:sessions → sessions_list, sessions_history, sessions_send, sessions_spawn
  group:ui       → browser, canvas, analyze_image

Tool profiles provide base allowlists:
  minimal   → session_status only
  coding    → group:fs + group:runtime + group:sessions + group:memory
  assistant → coding + group:web + analyze_image
  full      → no restrictions
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Tool Groups
# ──────────────────────────────────────────────

TOOL_GROUPS: Dict[str, FrozenSet[str]] = {
    "group:fs": frozenset(["read_file", "write_file", "list_directory", "apply_patch"]),
    "group:runtime": frozenset(["execute_python", "evaluate_expression"]),
    "group:web": frozenset(["web_search", "web_fetch"]),
    "group:memory": frozenset(["memory_search", "memory_get"]),
    "group:sessions": frozenset([
        "sessions_list", "sessions_history",
        "sessions_send", "sessions_spawn", "session_status",
    ]),
    "group:ui": frozenset(["browser", "canvas", "analyze_image"]),
}


def expand_groups(names: Set[str]) -> Set[str]:
    """Expand group shorthands into individual tool names."""
    expanded = set()
    for name in names:
        if name in TOOL_GROUPS:
            expanded.update(TOOL_GROUPS[name])
        else:
            expanded.add(name)
    return expanded


# ──────────────────────────────────────────────
# Tool Profiles
# ──────────────────────────────────────────────

class ToolProfile(Enum):
    MINIMAL = "minimal"
    CODING = "coding"
    ASSISTANT = "assistant"
    FULL = "full"


PROFILE_ALLOWLISTS: Dict[ToolProfile, Set[str]] = {
    ToolProfile.MINIMAL: {"session_status"},
    ToolProfile.CODING: expand_groups({
        "group:fs", "group:runtime", "group:sessions", "group:memory",
    }),
    ToolProfile.ASSISTANT: expand_groups({
        "group:fs", "group:runtime", "group:sessions",
        "group:memory", "group:web", "analyze_image",
    }),
    ToolProfile.FULL: set(),  # Empty = no restrictions
}


# ──────────────────────────────────────────────
# Policy Layer
# ──────────────────────────────────────────────

@dataclass
class PolicyLayer:
    """A single layer in the policy resolution chain."""
    name: str = ""
    allow: Set[str] = field(default_factory=set)
    deny: Set[str] = field(default_factory=set)

    def __post_init__(self):
        # Expand group shorthands
        self.allow = expand_groups(self.allow)
        self.deny = expand_groups(self.deny)


@dataclass
class PolicyContext:
    """Context for policy resolution — who's asking and from where."""
    agent_id: str = "default"
    session_id: str = "main"
    session_type: str = "main"  # main | group | spawned
    is_sandboxed: bool = False


# ──────────────────────────────────────────────
# Tool Policy Engine
# ──────────────────────────────────────────────

class ToolPolicyEngine:
    """
    Resolves tool access through a layered policy chain.

    Resolution order:
      1. Global policy (base layer)
      2. Profile allowlist (if set)
      3. Agent-specific overrides
      4. Session-specific overrides
      5. Sandbox restrictions (if sandboxed)

    Rule: **Deny always wins** at every layer.
    """

    def __init__(self, profile: ToolProfile = ToolProfile.ASSISTANT):
        self.profile = profile
        self._global = PolicyLayer(name="global")
        self._agent_policies: Dict[str, PolicyLayer] = {}
        self._session_policies: Dict[str, PolicyLayer] = {}
        self._sandbox_policy = PolicyLayer(
            name="sandbox",
            allow={
                "execute_python", "evaluate_expression",
                "read_file", "write_file", "list_directory",
                "sessions_list", "sessions_history",
                "sessions_send", "session_status",
                "memory_search", "memory_get",
            },
            deny={
                "browser", "canvas", "web_fetch",
                "apply_patch",
            },
        )

    def set_global_policy(self, allow: Set[str] = None, deny: Set[str] = None):
        """Set global allow/deny rules."""
        if allow:
            self._global.allow = expand_groups(allow)
        if deny:
            self._global.deny = expand_groups(deny)

    def set_agent_policy(self, agent_id: str, allow: Set[str] = None, deny: Set[str] = None):
        """Set agent-specific policy overrides."""
        self._agent_policies[agent_id] = PolicyLayer(
            name=f"agent:{agent_id}",
            allow=allow or set(),
            deny=deny or set(),
        )

    def set_session_policy(self, session_id: str, allow: Set[str] = None, deny: Set[str] = None):
        """Set session-specific policy overrides."""
        self._session_policies[session_id] = PolicyLayer(
            name=f"session:{session_id}",
            allow=allow or set(),
            deny=deny or set(),
        )

    def resolve(self, tool_name: str, context: PolicyContext = None) -> bool:
        """
        Resolve whether a tool is allowed.

        Returns True if allowed, False if denied.
        Deny always wins at every layer.
        """
        ctx = context or PolicyContext()

        # Layer 1: Global deny — instant reject
        if tool_name in self._global.deny:
            logger.debug(f"Tool '{tool_name}' denied by global policy")
            return False

        # Layer 2: Profile allowlist
        profile_allowlist = PROFILE_ALLOWLISTS.get(self.profile, set())
        if profile_allowlist and tool_name not in profile_allowlist:
            # Check if explicitly allowed at global level
            if tool_name not in self._global.allow:
                logger.debug(f"Tool '{tool_name}' not in profile '{self.profile.value}'")
                return False

        # Layer 3: Agent-specific policy
        agent_policy = self._agent_policies.get(ctx.agent_id)
        if agent_policy:
            if tool_name in agent_policy.deny:
                logger.debug(f"Tool '{tool_name}' denied by agent '{ctx.agent_id}'")
                return False

        # Layer 4: Session-specific policy
        session_policy = self._session_policies.get(ctx.session_id)
        if session_policy:
            if tool_name in session_policy.deny:
                logger.debug(f"Tool '{tool_name}' denied by session '{ctx.session_id}'")
                return False

        # Layer 5: Sandbox restrictions
        if ctx.is_sandboxed:
            if tool_name in self._sandbox_policy.deny:
                logger.debug(f"Tool '{tool_name}' denied by sandbox policy")
                return False
            if self._sandbox_policy.allow and tool_name not in self._sandbox_policy.allow:
                logger.debug(f"Tool '{tool_name}' not in sandbox allowlist")
                return False

        return True

    def get_allowed_tools(
        self,
        available_tools: List[str],
        context: PolicyContext = None,
    ) -> List[str]:
        """Get a filtered list of allowed tools for a given context."""
        return [t for t in available_tools if self.resolve(t, context)]

    def get_policy_summary(self, context: PolicyContext = None) -> dict:
        """Get a human-readable summary of the active policy."""
        ctx = context or PolicyContext()
        return {
            "profile": self.profile.value,
            "global_deny": list(self._global.deny),
            "global_allow": list(self._global.allow),
            "agent_policy": (
                {"allow": list(p.allow), "deny": list(p.deny)}
                if (p := self._agent_policies.get(ctx.agent_id)) else None
            ),
            "session_policy": (
                {"allow": list(p.allow), "deny": list(p.deny)}
                if (p := self._session_policies.get(ctx.session_id)) else None
            ),
            "sandboxed": ctx.is_sandboxed,
        }
