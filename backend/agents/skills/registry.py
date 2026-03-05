"""
Skills Registry — Discover, load, and inject skills.
─────────────────────────────────────────────────────
Skill types (from OpenClaw):
  bundled   — shipped with the system (data/skills/bundled/)
  managed   — installed by user (data/skills/managed/)
  workspace — per-workspace skills (data/workspace/<agent>/skills/)

Each skill is a directory containing:
  SKILL.md      — Skill description, instructions, prompts
  config.json   — Optional config (parameters, toggles)
  tools/        — Optional additional tool scripts
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SkillType(Enum):
    BUNDLED = "bundled"
    MANAGED = "managed"
    WORKSPACE = "workspace"


@dataclass
class Skill:
    """A loaded skill."""
    name: str
    skill_type: SkillType
    path: Path
    description: str = ""
    instructions: str = ""
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)

    def get_injection(self) -> str:
        """Get the skill content to inject into system prompt."""
        if self.instructions:
            return f"## Skill: {self.name}\n{self.instructions}"
        return ""


class SkillsRegistry:
    """
    Discovers and manages skills from multiple sources.

    Skills are loaded from:
      1. Bundled skills (shipped with system)
      2. Managed skills (user-installed)
      3. Workspace skills (per-agent)

    Skills inject instructions into the system prompt and
    can optionally register additional tools.
    """

    def __init__(
        self,
        bundled_dir: str = "data/skills/bundled",
        managed_dir: str = "data/skills/managed",
        workspace_base: str = "data/workspace",
    ):
        self.bundled_dir = Path(bundled_dir)
        self.managed_dir = Path(managed_dir)
        self.workspace_base = Path(workspace_base)
        self._skills: Dict[str, Skill] = {}

    def discover_all(self, agent_id: str = "default") -> List[Skill]:
        """Discover and load all skills from all sources."""
        self._skills.clear()

        # Load in priority order (later overrides earlier)
        self._discover_from_dir(self.bundled_dir, SkillType.BUNDLED)
        self._discover_from_dir(self.managed_dir, SkillType.MANAGED)
        self._discover_from_dir(
            self.workspace_base / agent_id / "skills",
            SkillType.WORKSPACE,
        )

        loaded = list(self._skills.values())
        logger.info(f"Discovered {len(loaded)} skills for agent '{agent_id}'")
        return loaded

    def _discover_from_dir(self, skills_dir: Path, skill_type: SkillType):
        """Discover skills from a directory."""
        if not skills_dir.exists():
            return

        for skill_path in skills_dir.iterdir():
            if not skill_path.is_dir():
                continue

            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                skill = self._load_skill(skill_path, skill_type)
                if skill and skill.enabled:
                    self._skills[skill.name] = skill
                    logger.debug(f"Loaded skill: {skill.name} ({skill_type.value})")
            except Exception as e:
                logger.warning(f"Failed to load skill from {skill_path}: {e}")

    def _load_skill(self, skill_path: Path, skill_type: SkillType) -> Optional[Skill]:
        """Load a single skill from its directory."""
        skill_md = skill_path / "SKILL.md"
        instructions = skill_md.read_text(encoding="utf-8")

        # Parse YAML frontmatter if present
        name = skill_path.name
        description = ""
        if instructions.startswith("---"):
            parts = instructions.split("---", 2)
            if len(parts) >= 3:
                # Parse frontmatter
                frontmatter = parts[1].strip()
                for line in frontmatter.split("\n"):
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("description:"):
                        description = line.split(":", 1)[1].strip().strip('"').strip("'")
                instructions = parts[2].strip()

        # Load optional config
        config = {}
        config_path = skill_path / "config.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning(f"Invalid config.json in {skill_path}")

        # Discover tool files
        tools = []
        tools_dir = skill_path / "tools"
        if tools_dir.exists():
            tools = [f.stem for f in tools_dir.glob("*.py")]

        return Skill(
            name=name,
            skill_type=skill_type,
            path=skill_path,
            description=description,
            instructions=instructions,
            enabled=config.get("enabled", True),
            config=config,
            tools=tools,
        )

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a specific skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all loaded skills with metadata."""
        return [
            {
                "name": s.name,
                "type": s.skill_type.value,
                "description": s.description,
                "enabled": s.enabled,
                "tools": s.tools,
                "path": str(s.path),
            }
            for s in self._skills.values()
        ]

    def get_injections(self) -> str:
        """Get combined skill injections for system prompt."""
        injections = []
        for skill in self._skills.values():
            if skill.enabled:
                injection = skill.get_injection()
                if injection:
                    injections.append(injection)

        if injections:
            return "# Active Skills\n\n" + "\n\n---\n\n".join(injections)
        return ""

    def install_skill(
        self,
        name: str,
        skill_md_content: str,
        config: Dict[str, Any] = None,
        skill_type: SkillType = SkillType.MANAGED,
    ) -> Skill:
        """Install a new skill."""
        if skill_type == SkillType.MANAGED:
            skill_dir = self.managed_dir / name
        else:
            raise ValueError("Can only install MANAGED skills")

        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

        if config:
            (skill_dir / "config.json").write_text(
                json.dumps(config, indent=2), encoding="utf-8"
            )

        skill = self._load_skill(skill_dir, skill_type)
        if skill:
            self._skills[skill.name] = skill

        logger.info(f"Installed skill: {name}")
        return skill

    def uninstall_skill(self, name: str) -> bool:
        """Uninstall a managed skill."""
        skill = self._skills.get(name)
        if not skill or skill.skill_type != SkillType.MANAGED:
            return False

        import shutil
        shutil.rmtree(skill.path, ignore_errors=True)
        del self._skills[name]
        logger.info(f"Uninstalled skill: {name}")
        return True
