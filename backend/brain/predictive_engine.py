"""
Predictive Pre-Computation Engine — Speculative Execution for AI
────────────────────────────────────────────────────────────────
Predicts likely next actions and pre-computes results before they're requested.
Like CPU branch prediction, but for AI reasoning pipelines.

Architecture:
  PatternPredictor  →  SpeculativeExecutor  →  PredictiveCache
  (n-gram history)     (background compute)     (LRU results)
"""

import hashlib
import logging
import threading
import time
from collections import OrderedDict, Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class PreComputedResult:
    """A cached pre-computed answer."""
    task_key: str
    result: Any
    confidence: float = 0.0
    computed_at: float = 0.0
    ttl_seconds: float = 300.0  # 5 min default
    hit_count: int = 0
    miss_count: int = 0
    compute_time_ms: float = 0.0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.computed_at) > self.ttl_seconds

    @property
    def hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        return self.hit_count / max(total, 1)


@dataclass
class Prediction:
    """A predicted next query."""
    task_key: str
    predicted_query: str
    confidence: float = 0.0
    pattern_source: str = ""   # Which pattern triggered this


class CacheStrategy(Enum):
    LRU = "lru"
    LFU = "lfu"
    TTL = "ttl"


# ──────────────────────────────────────────────
# Pattern Predictor
# ──────────────────────────────────────────────

class PatternPredictor:
    """
    Uses n-gram patterns from task history to predict next actions.
    Tracks sequences of (task_type, domain) tuples and finds recurring patterns.
    """

    def __init__(self, max_history: int = 500, ngram_sizes: Tuple[int, ...] = (2, 3, 4)):
        self._history: List[str] = []
        self._max_history = max_history
        self._ngram_sizes = ngram_sizes
        self._ngram_counts: Dict[int, Counter] = {n: Counter() for n in ngram_sizes}
        self._transition_matrix: Dict[str, Counter] = defaultdict(Counter)

    def record(self, task_key: str):
        """Record a task occurrence for pattern learning."""
        if self._history:
            prev = self._history[-1]
            self._transition_matrix[prev][task_key] += 1

        self._history.append(task_key)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Update n-gram counts
        for n in self._ngram_sizes:
            if len(self._history) >= n:
                ngram = tuple(self._history[-n:])
                self._ngram_counts[n][ngram] += 1

    def predict_next(self, top_k: int = 3) -> List[Prediction]:
        """Predict the top-K most likely next tasks."""
        if not self._history:
            return []

        predictions = []
        current = self._history[-1]

        # Method 1: Markov transition probability
        if current in self._transition_matrix:
            transitions = self._transition_matrix[current]
            total = sum(transitions.values())
            for task_key, count in transitions.most_common(top_k):
                conf = count / total
                predictions.append(Prediction(
                    task_key=task_key,
                    predicted_query=task_key,
                    confidence=conf,
                    pattern_source="markov_transition",
                ))

        # Method 2: N-gram suffix matching
        for n in sorted(self._ngram_sizes, reverse=True):
            if len(self._history) >= n - 1:
                prefix = tuple(self._history[-(n-1):])
                for ngram, count in self._ngram_counts[n].most_common(top_k * 2):
                    if ngram[:-1] == prefix:
                        next_task = ngram[-1]
                        total = sum(1 for ng in self._ngram_counts[n] if ng[:-1] == prefix)
                        conf = count / max(total, 1) * 0.8  # Slight discount vs Markov
                        if not any(p.task_key == next_task for p in predictions):
                            predictions.append(Prediction(
                                task_key=next_task,
                                predicted_query=next_task,
                                confidence=min(conf, 0.95),
                                pattern_source=f"ngram_{n}",
                            ))

        # Sort by confidence and return top-K
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        return predictions[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "history_size": len(self._history),
            "unique_tasks": len(set(self._history)),
            "transition_states": len(self._transition_matrix),
            "ngram_counts": {n: len(c) for n, c in self._ngram_counts.items()},
        }


# ──────────────────────────────────────────────
# Predictive Cache
# ──────────────────────────────────────────────

class PredictiveCache:
    """
    LRU cache of (task_key → pre-computed result) with TTL expiry.
    Thread-safe for concurrent access from speculative executor.
    """

    def __init__(self, max_size: int = 128, default_ttl: float = 300.0):
        self._cache: OrderedDict[str, PreComputedResult] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._total_hits = 0
        self._total_misses = 0

    def get(self, task_key: str) -> Optional[PreComputedResult]:
        """Retrieve a cached result. Returns None if miss or expired."""
        with self._lock:
            if task_key in self._cache:
                entry = self._cache[task_key]
                if entry.is_expired:
                    del self._cache[task_key]
                    self._total_misses += 1
                    return None
                # Move to end (most recently used)
                self._cache.move_to_end(task_key)
                entry.hit_count += 1
                self._total_hits += 1
                return entry

            self._total_misses += 1
            return None

    def put(self, task_key: str, result: Any, confidence: float = 0.5,
            compute_time_ms: float = 0.0, ttl: float = None):
        """Store a pre-computed result."""
        with self._lock:
            entry = PreComputedResult(
                task_key=task_key,
                result=result,
                confidence=confidence,
                computed_at=time.time(),
                ttl_seconds=ttl or self._default_ttl,
                compute_time_ms=compute_time_ms,
            )
            self._cache[task_key] = entry
            self._cache.move_to_end(task_key)

            # Enforce max size (LRU eviction)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self, task_key: str):
        """Remove a specific entry."""
        with self._lock:
            self._cache.pop(task_key, None)

    def clear_expired(self):
        """Remove all expired entries."""
        with self._lock:
            expired = [k for k, v in self._cache.items() if v.is_expired]
            for k in expired:
                del self._cache[k]

    @property
    def hit_rate(self) -> float:
        total = self._total_hits + self._total_misses
        return self._total_hits / max(total, 1)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate": round(self.hit_rate, 4),
            "expired_entries": sum(1 for v in self._cache.values() if v.is_expired),
        }


# ──────────────────────────────────────────────
# Speculative Executor
# ──────────────────────────────────────────────

class SpeculativeExecutor:
    """
    Analyzes current context, predicts likely next queries, and
    pre-computes results in background threads.
    """

    def __init__(self, compute_fn: Optional[Callable] = None, max_workers: int = 3):
        self._compute_fn = compute_fn
        self._max_workers = max_workers
        self._active_tasks: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def speculate(self, predictions: List[Prediction], cache: PredictiveCache):
        """
        Launch background computation for predicted queries.
        Only computes if not already in cache or being computed.
        """
        for pred in predictions[:self._max_workers]:
            if pred.confidence < 0.2:
                continue  # Too uncertain to waste compute

            if cache.get(pred.task_key) is not None:
                continue  # Already cached

            with self._lock:
                if pred.task_key in self._active_tasks:
                    continue  # Already being computed

            # Launch background computation
            thread = threading.Thread(
                target=self._compute_and_cache,
                args=(pred, cache),
                daemon=True,
                name=f"speculate-{pred.task_key[:20]}",
            )
            with self._lock:
                self._active_tasks[pred.task_key] = thread
            thread.start()

    def _compute_and_cache(self, prediction: Prediction, cache: PredictiveCache):
        """Compute a result and store in cache."""
        if not self._compute_fn:
            return

        start = time.time()
        try:
            result = self._compute_fn(prediction.predicted_query)
            elapsed_ms = (time.time() - start) * 1000

            cache.put(
                task_key=prediction.task_key,
                result=result,
                confidence=prediction.confidence,
                compute_time_ms=elapsed_ms,
            )
            logger.debug(
                f"🔮 Pre-computed '{prediction.task_key[:40]}' "
                f"in {elapsed_ms:.0f}ms (conf={prediction.confidence:.2f})"
            )
        except Exception as e:
            logger.debug(f"🔮 Speculation failed for '{prediction.task_key[:40]}': {e}")
        finally:
            with self._lock:
                self._active_tasks.pop(prediction.task_key, None)


# ──────────────────────────────────────────────
# Predictive Pre-Computation Engine
# ──────────────────────────────────────────────

class PredictiveEngine:
    """
    The main engine that orchestrates prediction → speculation → caching.

    Usage:
        engine = PredictiveEngine(compute_fn=my_llm_fn)

        # Record each task as it occurs
        engine.record_task("code_review", query="Review my Python function")

        # Check for pre-computed results before doing expensive work
        cached = engine.get_precomputed("code_review")
        if cached:
            return cached.result  # Cache hit — skip expensive computation

        # Otherwise compute normally and the engine learns the pattern
    """

    def __init__(
        self,
        compute_fn: Optional[Callable] = None,
        cache_size: int = 128,
        cache_ttl: float = 300.0,
        enable_speculation: bool = True,
    ):
        self.predictor = PatternPredictor()
        self.cache = PredictiveCache(max_size=cache_size, default_ttl=cache_ttl)
        self.executor = SpeculativeExecutor(compute_fn=compute_fn)
        self._enable_speculation = enable_speculation
        self._total_tasks = 0
        self._speculation_hits = 0

    def record_task(self, task_type: str, query: str = "", domain: str = "general"):
        """Record a task and trigger speculative pre-computation."""
        task_key = self._make_key(task_type, domain)
        self.predictor.record(task_key)
        self._total_tasks += 1

        # Speculate on likely next tasks
        if self._enable_speculation:
            predictions = self.predictor.predict_next(top_k=3)
            if predictions:
                self.executor.speculate(predictions, self.cache)
                logger.debug(
                    f"🔮 Speculating: {[f'{p.task_key}({p.confidence:.2f})' for p in predictions]}"
                )

        # Periodic cache cleanup
        if self._total_tasks % 50 == 0:
            self.cache.clear_expired()

    def get_precomputed(self, task_type: str, domain: str = "general") -> Optional[PreComputedResult]:
        """Check if a pre-computed result exists for this task."""
        task_key = self._make_key(task_type, domain)
        result = self.cache.get(task_key)
        if result:
            self._speculation_hits += 1
            logger.info(f"🎯 Speculation HIT: '{task_key}' (saved {result.compute_time_ms:.0f}ms)")
        return result

    def store_result(self, task_type: str, result: Any, domain: str = "general",
                     confidence: float = 0.8, compute_time_ms: float = 0.0):
        """Manually store a computed result for future cache hits."""
        task_key = self._make_key(task_type, domain)
        self.cache.put(task_key, result, confidence, compute_time_ms)

    def _make_key(self, task_type: str, domain: str) -> str:
        return f"{domain}:{task_type}"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_tasks": self._total_tasks,
            "speculation_hits": self._speculation_hits,
            "speculation_hit_rate": round(
                self._speculation_hits / max(self._total_tasks, 1), 4
            ),
            "cache": self.cache.get_stats(),
            "predictor": self.predictor.get_stats(),
        }
