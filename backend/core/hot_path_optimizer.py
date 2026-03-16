"""
Neural Hot Path Optimizer — Frequency-Based Execution Cache
══════════════════════════════════════════════════════════
Learns which code paths and operations are used most frequently,
pre-warms them, and caches intermediate results for rapid execution.

Capabilities:
  1. Frequency Tracking  — Count execution frequency per path
  2. Hot Path Detection  — Identify top N most-used paths
  3. Pre-warming         — Pre-compute results for hot paths
  4. Intermediate Cache  — Cache partial computation results
  5. Decay Scoring       — Time-weighted frequency for recency bias
"""

import hashlib
import logging
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PathStats:
    """Statistics for a single execution path."""
    path_id: str = ""
    description: str = ""
    call_count: int = 0
    last_called: float = 0.0
    avg_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    cached_result: Any = None
    cache_hits: int = 0
    is_hot: bool = False
    decay_score: float = 0.0

    def record_call(self, latency_ms: float):
        self.call_count += 1
        self.last_called = time.time()
        self.total_latency_ms += latency_ms
        self.avg_latency_ms = self.total_latency_ms / self.call_count

    def compute_decay_score(self, current_time: float, half_life: float = 3600):
        """Time-weighted frequency score with exponential decay."""
        age = current_time - self.last_called
        recency = math.exp(-age / half_life)
        self.decay_score = self.call_count * recency


class HotPathOptimizer:
    """
    Neural hot path optimizer that learns execution patterns,
    identifies hotspots, and pre-warms frequently used operations.
    """

    TOP_N = 20          # Number of paths to consider "hot"
    DECAY_HALF_LIFE = 3600  # 1 hour half-life for decay scoring
    PREWARM_THRESHOLD = 5   # Min calls before pre-warming

    def __init__(self):
        self._paths: Dict[str, PathStats] = {}
        self._intermediate_cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._total_calls = 0
        self._total_cache_hits = 0
        self._hot_path_ids: List[str] = []
        logger.info("[HOT-PATH] Optimizer initialized")

    def track(self, path_id: str, description: str = "",
              latency_ms: float = 0.0):
        """Track an execution path invocation."""
        with self._lock:
            if path_id not in self._paths:
                self._paths[path_id] = PathStats(
                    path_id=path_id, description=description or path_id,
                )
            self._paths[path_id].record_call(latency_ms)
            self._total_calls += 1

        # Recompute hot paths periodically
        if self._total_calls % 10 == 0:
            self._recompute_hot_paths()

    def check_cache(self, path_id: str) -> Optional[Any]:
        """Check if we have a cached result for a hot path."""
        with self._lock:
            path = self._paths.get(path_id)
            if path and path.cached_result is not None:
                path.cache_hits += 1
                self._total_cache_hits += 1
                return path.cached_result

            # Check intermediate cache
            if path_id in self._intermediate_cache:
                self._total_cache_hits += 1
                return self._intermediate_cache[path_id]

        return None

    def cache_result(self, path_id: str, result: Any):
        """Cache a result for a hot path."""
        with self._lock:
            path = self._paths.get(path_id)
            if path and path.is_hot:
                path.cached_result = result

    def cache_intermediate(self, key: str, value: Any, ttl_seconds: float = 300):
        """Cache an intermediate computation result."""
        with self._lock:
            self._intermediate_cache[key] = value
            # Simple TTL via background cleanup
            if len(self._intermediate_cache) > 500:
                oldest_keys = list(self._intermediate_cache.keys())[:100]
                for k in oldest_keys:
                    self._intermediate_cache.pop(k, None)

    def prewarm(self, path_id: str, compute_fn: Callable) -> bool:
        """Pre-compute and cache result for a hot path."""
        path = self._paths.get(path_id)
        if not path or path.call_count < self.PREWARM_THRESHOLD:
            return False

        try:
            result = compute_fn()
            with self._lock:
                path.cached_result = result
            logger.info(f"[HOT-PATH] Pre-warmed: {path_id}")
            return True
        except Exception as e:
            logger.debug(f"[HOT-PATH] Pre-warm failed for {path_id}: {e}")
            return False

    def _recompute_hot_paths(self):
        """Recompute which paths are hot based on decay-weighted frequency."""
        now = time.time()
        with self._lock:
            for path in self._paths.values():
                path.compute_decay_score(now, self.DECAY_HALF_LIFE)
                path.is_hot = False

            # Sort by decay score and mark top N as hot
            sorted_paths = sorted(
                self._paths.values(),
                key=lambda p: p.decay_score,
                reverse=True,
            )
            self._hot_path_ids = []
            for path in sorted_paths[:self.TOP_N]:
                if path.call_count >= 2:
                    path.is_hot = True
                    self._hot_path_ids.append(path.path_id)

    def get_hot_paths(self) -> List[Dict]:
        """Get current hot paths with statistics."""
        self._recompute_hot_paths()
        return [
            {
                "path_id": p.path_id,
                "description": p.description,
                "call_count": p.call_count,
                "avg_latency_ms": round(p.avg_latency_ms, 1),
                "cache_hits": p.cache_hits,
                "decay_score": round(p.decay_score, 2),
                "has_cached_result": p.cached_result is not None,
            }
            for p in sorted(
                self._paths.values(),
                key=lambda p: p.decay_score, reverse=True,
            )[:self.TOP_N]
            if p.is_hot
        ]

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_paths_tracked": len(self._paths),
            "hot_paths": len(self._hot_path_ids),
            "total_calls": self._total_calls,
            "total_cache_hits": self._total_cache_hits,
            "cache_hit_rate": round(
                self._total_cache_hits / max(self._total_calls, 1), 3
            ),
            "intermediate_cache_size": len(self._intermediate_cache),
        }
