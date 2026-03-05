"""
Workspace Injection — Bootstrap files injected into agent context.
─────────────────────────────────────────────────────────────────
Workspace files (inspired by OpenClaw AGENTS.md / SOUL.md / TOOLS.md):

  IDENTITY.md  — Agent name, persona, emoji, vibe
  SOUL.md      — Boundaries, values, tone, principles
  TOOLS.md     — Tool notes, conventions, tips
  MEMORY.md    — Long-term memory notes
  BOOTSTRAP.md — One-time first-run ritual (deleted after)
  USER.md      — User profile and preferences

Files are loaded from the workspace directory and assembled
into the system prompt in a defined order.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# Default templates for workspace files
DEFAULT_TEMPLATES = {
    "IDENTITY.md": """# Agent Identity
- **Name**: Nexus
- **Emoji**: 🧠
- **Role**: Personal AI Assistant with self-thinking capabilities
- **Version**: 1.0
""",
    "SOUL.md": """# Agent Soul — Values & Boundaries
## Core Values
- Accuracy over speed
- Transparency about limitations
- User safety is paramount
- Learn from every mistake

## Boundaries
- Never fabricate data or sources
- Always disclose uncertainty
- Refuse harmful requests politely
- Ask for clarification when ambiguous

## Tone
- Professional but approachable
- Concise and structured
- Use examples when helpful
- Acknowledge mistakes directly
""",
    "TOOLS.md": """# Tool Notes & Conventions
## File Operations
- Always verify paths before writing
- Use relative paths within workspace
- Back up before destructive operations

## Code Execution
- Prefer evaluate_expression for simple calculations
- Use execute_python for complex scripts
- Always include error handling in scripts

## Web Search
- Verify search results before presenting
- Cite sources when possible
- Prefer recent results for time-sensitive queries
""",
    "MEMORY.md": """# Long-Term Memory
- Stores important learnings and user preferences
- Updated automatically by the brain's Bug Diary
- Searchable via memory_search tool
""",
    "BOOTSTRAP.md": """# First-Run Bootstrap
Welcome! This is your first session. Here's what to know:
1. I have self-thinking capabilities (Synthesize → Verify → Learn)
2. I learn from mistakes via the Bug Diary
3. I can use tools: web search, code execution, file operations
4. I support multimodal image analysis
5. I assess risk before every action (Tri-Shield Objective)

This file will be removed after the first session.
""",
    "USER.md": """# User Profile
- Preferences will be learned over time
- Communication style will adapt to yours
""",
}

# Load order for system prompt assembly
INJECTION_ORDER = [
    "IDENTITY.md",
    "SOUL.md",
    "TOOLS.md",
    "MEMORY.md",
    "BOOTSTRAP.md",
    "USER.md",
]


class WorkspaceManager:
    """
    Manages workspace files and injects them into agent system prompts.

    Features:
      - Auto-initialize workspace with default templates
      - Load and assemble bootstrap files in defined order
      - Per-agent workspace isolation
      - BOOTSTRAP.md one-time ritual (removed after first load)
    """

    def __init__(self, workspace_dir: str = "data/workspace"):
        self.workspace_dir = Path(workspace_dir)

    def initialize(self, agent_id: str = "default"):
        """Initialize workspace with default templates if missing."""
        agent_dir = self._agent_workspace(agent_id)
        agent_dir.mkdir(parents=True, exist_ok=True)

        for filename, template in DEFAULT_TEMPLATES.items():
            filepath = agent_dir / filename
            if not filepath.exists():
                filepath.write_text(template, encoding="utf-8")
                logger.info(f"Created workspace file: {filepath}")

    def _agent_workspace(self, agent_id: str) -> Path:
        return self.workspace_dir / agent_id

    def load_file(self, agent_id: str, filename: str) -> Optional[str]:
        """Load a single workspace file."""
        filepath = self._agent_workspace(agent_id) / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return None

    def save_file(self, agent_id: str, filename: str, content: str):
        """Save/update a workspace file."""
        agent_dir = self._agent_workspace(agent_id)
        agent_dir.mkdir(parents=True, exist_ok=True)
        filepath = agent_dir / filename
        filepath.write_text(content, encoding="utf-8")

    def assemble_system_prompt(self, agent_id: str = "default") -> str:
        """
        Assemble the full system prompt from workspace files.

        Loads files in INJECTION_ORDER and concatenates them
        with clear section separators.
        """
        self.initialize(agent_id)
        sections = []

        for filename in INJECTION_ORDER:
            content = self.load_file(agent_id, filename)
            if content and content.strip():
                sections.append(f"<!-- {filename} -->\n{content.strip()}")

        # Remove BOOTSTRAP.md after first load
        bootstrap_path = self._agent_workspace(agent_id) / "BOOTSTRAP.md"
        if bootstrap_path.exists():
            bootstrap_path.unlink()
            logger.info(f"Bootstrap completed — removed {bootstrap_path}")

        return "\n\n---\n\n".join(sections)

    def get_all_files(self, agent_id: str) -> Dict[str, str]:
        """Get all workspace files for an agent."""
        agent_dir = self._agent_workspace(agent_id)
        files = {}
        if agent_dir.exists():
            for filepath in agent_dir.glob("*.md"):
                files[filepath.name] = filepath.read_text(encoding="utf-8")
        return files

    def list_files(self, agent_id: str) -> List[str]:
        """List workspace files for an agent."""
        agent_dir = self._agent_workspace(agent_id)
        if agent_dir.exists():
            return [f.name for f in agent_dir.glob("*.md")]
        return []

    def update_memory(self, agent_id: str, addition: str):
        """Append a learning to MEMORY.md."""
        current = self.load_file(agent_id, "MEMORY.md") or ""
        updated = current.rstrip() + f"\n- {addition}\n"
        self.save_file(agent_id, "MEMORY.md", updated)

    def update_user_profile(self, agent_id: str, info: str):
        """Append user info to USER.md."""
        current = self.load_file(agent_id, "USER.md") or ""
        updated = current.rstrip() + f"\n- {info}\n"
        self.save_file(agent_id, "USER.md", updated)
