"""
Polymorphic Injector — Dynamic Plugin & Logic Loader
────────────────────────────────────────────────────
Expert-level dynamic code loader that enables the ASI to inject
new logic modules into the running process at runtime. Uses
importlib to load ephemeral "parasite" modules safely.
"""

import importlib.util
import logging
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ParasiteModule:
    """A dynamically injected module."""
    name: str
    path: str
    module_obj: Any
    injected_at: float


class PolymorphicInjector:
    """
    Tier 6: Ephemeral Polymorphic OS Injection (The Parasite Architecture)

    Enables dynamic loading of new logic modules at runtime.
    Allows the ASI to "parasitize" the local environment by
    injecting specialized handlers for new tasks without
    restarting the main kernel.
    """

    def __init__(self):
        self._active_parasites: Dict[str, ParasiteModule] = {}
        logger.info("[OS-INJECTION] Dynamic logic injector active.")

    def inject_logic(self, name: str, code: str) -> bool:
        """
        Inject a new Python module into the current process.
        Returns True if successful.
        """
        try:
            # Create a temporary file for the module
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
                f.write(code)
                tmp_path = f.name

            # Load the module dynamically
            spec = importlib.util.spec_from_file_location(name, tmp_path)
            if not spec or not spec.loader:
                logger.error("[OS-INJECTION] Failed to create spec for module %s", name)
                return False

            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)

            self._active_parasites[name] = ParasiteModule(
                name=name,
                path=tmp_path,
                module_obj=module,
                injected_at=os.path.getmtime(tmp_path)
            )
            
            logger.info("[OS-INJECTION] Successfully injected logic module '%s'.", name)
            return True

        except Exception as e:
            logger.error("[OS-INJECTION] Failed to inject module '%s': %s", name, e)
            return False

    def get_module(self, name: str) -> Optional[Any]:
        """Retrieve an injected module by name."""
        parasite = self._active_parasites.get(name)
        return parasite.module_obj if parasite else None

    def recall_parasites(self):
        """Unload all injected modules and clean up temp files."""
        for name, parasite in list(self._active_parasites.items()):
            try:
                if name in sys.modules:
                    del sys.modules[name]
                if os.path.exists(parasite.path):
                    os.remove(parasite.path)
            except Exception as e:
                logger.warning("[OS-INJECTION] Cleanup failed for %s: %s", name, e)
        
        self._active_parasites.clear()
        logger.info("[OS-INJECTION] All parasitic modules recalled. Traces erased.")

    @property
    def active_count(self) -> int:
        return len(self._active_parasites)


# Global injector fabric
os_injector = PolymorphicInjector()
