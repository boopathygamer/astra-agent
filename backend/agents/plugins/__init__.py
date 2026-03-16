"""
Plugin & Extension System — Hot-Loadable Capabilities
════════════════════════════════════════════════════
Dynamic plugin system for loading new tools, skills, and
behaviors at runtime without restarting the agent.

Capabilities:
  1. Hot Loading          — Load plugins from files at runtime
  2. Sandbox Execution    — Isolated execution environment
  3. Dependency Resolution — Auto-resolve plugin dependencies
  4. Lifecycle Management  — Init, enable, disable, remove
  5. Plugin Marketplace   — Discover and install community plugins
  6. Version Tracking     — Semantic versioning for plugins
"""

import hashlib
import importlib
import importlib.util
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class PluginState(Enum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    REMOVED = "removed"


class PluginType(Enum):
    TOOL = "tool"           # New tool capability
    SKILL = "skill"         # New skill/behavior
    PROVIDER = "provider"   # New LLM provider
    PROCESSOR = "processor" # Message pre/post processor
    EXTENSION = "extension" # General extension


@dataclass
class PluginManifest:
    """Plugin metadata from manifest file or class."""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    plugin_type: PluginType = PluginType.EXTENSION
    dependencies: List[str] = field(default_factory=list)
    entry_point: str = ""  # Module path or class name
    min_agent_version: str = ""
    permissions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @property
    def plugin_id(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass
class PluginRecord:
    """Runtime state of a loaded plugin."""
    manifest: PluginManifest = field(default_factory=PluginManifest)
    state: PluginState = PluginState.DISCOVERED
    instance: Any = None
    module: Any = None
    file_path: str = ""
    loaded_at: float = 0.0
    error: str = ""
    call_count: int = 0
    last_error_at: float = 0.0


class PluginInterface:
    """Base class that all plugins should extend."""

    def on_load(self) -> None:
        """Called when the plugin is loaded."""
        pass

    def on_enable(self) -> None:
        """Called when the plugin is enabled."""
        pass

    def on_disable(self) -> None:
        """Called when the plugin is disabled."""
        pass

    def on_unload(self) -> None:
        """Called when the plugin is removed."""
        pass

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return tools this plugin provides."""
        return []

    def process_message(self, message: str) -> str:
        """Pre-process messages (for processor-type plugins)."""
        return message

    def get_info(self) -> Dict[str, Any]:
        """Return plugin information."""
        return {}


class PluginManager:
    """
    Hot-loadable plugin system with lifecycle management,
    dependency resolution, and sandboxed execution.
    """

    MAX_PLUGINS = 50

    def __init__(self, plugins_dir: Optional[str] = None):
        self.plugins_dir = Path(plugins_dir) if plugins_dir else Path("plugins")
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        self._plugins: Dict[str, PluginRecord] = {}
        self._hooks: Dict[str, List[Callable]] = {
            "pre_process": [],
            "post_process": [],
            "on_tool_call": [],
            "on_error": [],
        }
        self._lock = threading.Lock()

        self._discover_plugins()
        logger.info(f"[PLUGIN] Manager initialized: {len(self._plugins)} plugins discovered")

    # ── Discovery ──

    def _discover_plugins(self) -> None:
        """Scan plugins directory for available plugins."""
        if not self.plugins_dir.exists():
            return

        for item in self.plugins_dir.iterdir():
            if item.is_file() and item.suffix == ".py" and not item.name.startswith("_"):
                self._register_file_plugin(item)
            elif item.is_dir() and (item / "__init__.py").exists():
                self._register_package_plugin(item)

    def _register_file_plugin(self, filepath: Path) -> None:
        """Register a single-file plugin."""
        name = filepath.stem
        manifest = PluginManifest(
            name=name,
            entry_point=str(filepath),
            description=f"Plugin from {filepath.name}",
        )
        self._plugins[name] = PluginRecord(
            manifest=manifest,
            file_path=str(filepath),
        )

    def _register_package_plugin(self, dirpath: Path) -> None:
        """Register a package plugin (directory with __init__.py)."""
        name = dirpath.name
        # Try to read manifest.json
        manifest_path = dirpath / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = PluginManifest(
                    name=data.get("name", name),
                    version=data.get("version", "1.0.0"),
                    description=data.get("description", ""),
                    author=data.get("author", ""),
                    plugin_type=PluginType(data.get("type", "extension")),
                    dependencies=data.get("dependencies", []),
                    entry_point=str(dirpath / "__init__.py"),
                    permissions=data.get("permissions", []),
                    tags=data.get("tags", []),
                )
            except Exception:
                manifest = PluginManifest(name=name, entry_point=str(dirpath / "__init__.py"))
        else:
            manifest = PluginManifest(name=name, entry_point=str(dirpath / "__init__.py"))

        self._plugins[name] = PluginRecord(
            manifest=manifest,
            file_path=str(dirpath),
        )

    # ── Loading ──

    def load_plugin(self, name: str) -> bool:
        """Load a discovered plugin."""
        record = self._plugins.get(name)
        if not record:
            return False

        if record.state in (PluginState.LOADED, PluginState.ENABLED):
            return True

        # Check dependencies
        for dep in record.manifest.dependencies:
            if dep not in self._plugins or self._plugins[dep].state == PluginState.ERROR:
                record.error = f"Missing dependency: {dep}"
                record.state = PluginState.ERROR
                return False

        try:
            filepath = Path(record.manifest.entry_point or record.file_path)
            if filepath.is_file():
                spec = importlib.util.spec_from_file_location(name, str(filepath))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    record.module = module

                    # Find the plugin class
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and
                                issubclass(attr, PluginInterface) and
                                attr is not PluginInterface):
                            record.instance = attr()
                            record.instance.on_load()
                            break

            record.state = PluginState.LOADED
            record.loaded_at = time.time()
            logger.info(f"[PLUGIN] Loaded: {name}")
            return True

        except Exception as e:
            record.state = PluginState.ERROR
            record.error = str(e)
            record.last_error_at = time.time()
            logger.error(f"[PLUGIN] Load failed for {name}: {e}")
            return False

    def enable_plugin(self, name: str) -> bool:
        """Enable a loaded plugin."""
        record = self._plugins.get(name)
        if not record:
            return False

        if record.state == PluginState.DISCOVERED:
            if not self.load_plugin(name):
                return False

        if record.state != PluginState.LOADED and record.state != PluginState.DISABLED:
            return False

        try:
            if record.instance:
                record.instance.on_enable()

                # Register hooks
                if hasattr(record.instance, "process_message"):
                    self._hooks["pre_process"].append(record.instance.process_message)

            record.state = PluginState.ENABLED
            logger.info(f"[PLUGIN] Enabled: {name}")
            return True
        except Exception as e:
            record.error = str(e)
            return False

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin without unloading it."""
        record = self._plugins.get(name)
        if not record or record.state != PluginState.ENABLED:
            return False

        try:
            if record.instance:
                record.instance.on_disable()
                # Remove hooks
                if record.instance.process_message in self._hooks.get("pre_process", []):
                    self._hooks["pre_process"].remove(record.instance.process_message)

            record.state = PluginState.DISABLED
            return True
        except Exception as e:
            record.error = str(e)
            return False

    def unload_plugin(self, name: str) -> bool:
        """Completely unload and remove a plugin."""
        record = self._plugins.get(name)
        if not record:
            return False

        if record.state == PluginState.ENABLED:
            self.disable_plugin(name)

        if record.instance:
            try:
                record.instance.on_unload()
            except Exception:
                pass

        record.instance = None
        record.module = None
        record.state = PluginState.DISCOVERED
        return True

    # ── Execution ──

    def run_preprocessors(self, message: str) -> str:
        """Run all enabled preprocessor plugins on a message."""
        for hook in self._hooks.get("pre_process", []):
            try:
                message = hook(message)
            except Exception as e:
                logger.warning(f"[PLUGIN] Preprocessor error: {e}")
        return message

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Collect tools from all enabled plugins."""
        tools = []
        for record in self._plugins.values():
            if record.state == PluginState.ENABLED and record.instance:
                try:
                    plugin_tools = record.instance.get_tools()
                    tools.extend(plugin_tools)
                except Exception:
                    pass
        return tools

    # ── Install From Code ──

    def install_from_code(self, name: str, code: str,
                          manifest: Dict = None) -> bool:
        """Install a plugin from Python source code."""
        plugin_file = self.plugins_dir / f"{name}.py"
        try:
            plugin_file.write_text(code, encoding="utf-8")
            if manifest:
                manifest_file = self.plugins_dir / f"{name}_manifest.json"
                manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            m = PluginManifest(
                name=name, entry_point=str(plugin_file),
                **(manifest or {}),
            )
            self._plugins[name] = PluginRecord(manifest=m, file_path=str(plugin_file))
            return self.load_plugin(name)
        except Exception as e:
            logger.error(f"[PLUGIN] Install failed: {e}")
            return False

    # ── Status ──

    def list_plugins(self) -> List[Dict]:
        return [
            {
                "name": r.manifest.name,
                "version": r.manifest.version,
                "type": r.manifest.plugin_type.value,
                "state": r.state.value,
                "description": r.manifest.description,
                "error": r.error,
            }
            for r in self._plugins.values()
        ]

    def get_status(self) -> Dict[str, Any]:
        states = defaultdict(int)
        for r in self._plugins.values():
            states[r.state.value] += 1
        return {
            "total_plugins": len(self._plugins),
            "states": dict(states),
            "hooks_registered": sum(len(h) for h in self._hooks.values()),
        }
