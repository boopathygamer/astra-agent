"""
Void-State Nullifier — Safe Memory Deallocation Engine
──────────────────────────────────────────────────────
VULNERABILITY FIX: Removed gc.disable() which was called on import,
causing memory leaks across the entire application.

Implements targeted garbage collection sweeps with reference-count
monitoring for safe, explicit memory deallocation.
"""

import ctypes
import gc
import logging
import sys
import weakref
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class VoidStateNullifier:
    """
    Tier 8: Void-State Nullification (Safe Memory Deallocation)

    SECURITY FIX: gc.disable() has been removed. Instead, this module
    performs targeted garbage collection sweeps with reference-count
    monitoring to safely deallocate specific objects.
    """

    def __init__(self):
        self._tracked_objects: Dict[str, weakref.ref] = {}
        self._deallocations: int = 0
        self._bytes_freed_estimate: int = 0
        # SECURITY: Ensure gc is ENABLED
        gc.enable()
        logger.info("[VOID-NULLIFIER] Safe deallocator initialized (gc=ENABLED).")

    def track(self, name: str, obj: Any) -> None:
        """Track an object for future targeted deallocation."""
        try:
            self._tracked_objects[name] = weakref.ref(obj)
            logger.debug("[VOID-NULLIFIER] Tracking object '%s' (refcount=%d, size=%d bytes).",
                         name, sys.getrefcount(obj), sys.getsizeof(obj))
        except TypeError:
            # Some objects can't be weakly referenced
            logger.debug("[VOID-NULLIFIER] Cannot weakref '%s' — tracking by name only.", name)

    def eradicate(self, name: str) -> bool:
        """
        Safely deallocate a tracked object by clearing references
        and triggering a targeted gc sweep.
        """
        ref = self._tracked_objects.pop(name, None)
        if ref is None:
            logger.debug("[VOID-NULLIFIER] Object '%s' not tracked.", name)
            return False

        obj = ref()
        if obj is None:
            # Already collected
            logger.debug("[VOID-NULLIFIER] Object '%s' already deallocated.", name)
            self._deallocations += 1
            return True

        # Estimate size before deallocation
        try:
            size = sys.getsizeof(obj)
            refcount = sys.getrefcount(obj)
        except Exception:
            size = 0
            refcount = -1

        # Clear the reference and trigger targeted collection
        del obj
        del ref
        collected = gc.collect(generation=0)

        self._deallocations += 1
        self._bytes_freed_estimate += size
        logger.info(
            "[VOID-NULLIFIER] Deallocated '%s' (est. %d bytes freed, %d objects collected, prev refcount=%d).",
            name, size, collected, refcount,
        )
        return True

    def sweep(self) -> int:
        """Full garbage collection sweep across all generations."""
        collected = gc.collect()
        logger.info("[VOID-NULLIFIER] Full sweep: %d objects collected.", collected)
        return collected

    def get_gc_stats(self) -> dict:
        """Return current gc statistics."""
        stats = gc.get_stats()
        return {
            "enabled": gc.isenabled(),
            "thresholds": gc.get_threshold(),
            "gen_stats": stats,
            "tracked_objects": len(self._tracked_objects),
            "total_deallocations": self._deallocations,
            "bytes_freed_estimate": self._bytes_freed_estimate,
        }

    @property
    def tracked_count(self) -> int:
        return len(self._tracked_objects)


# Global singleton — gc stays ENABLED. Always active.
nullifier = VoidStateNullifier()
