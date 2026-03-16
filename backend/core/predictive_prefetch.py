"""
Predictive Prefetch Engine — Pre-compute Likely Next Responses
═════════════════════════════════════════════════════════════
Predicts the user's next likely queries using Markov chains on
conversation patterns and pre-computes responses in background.

Capabilities:
  1. Markov Chain Predictor — Learn query transition probabilities
  2. Pattern Matching       — Recognize common follow-up sequences
  3. Background Pre-compute — Speculative execution in threads
  4. Hit Rate Tracking      — Monitor prediction accuracy
"""

import hashlib
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PrefetchEntry:
    """A pre-computed response waiting to be served."""
    predicted_query: str = ""
    predicted_response: str = ""
    confidence: float = 0.0
    computed_at: float = 0.0
    served: bool = False
    ttl_seconds: float = 300  # 5 min staleness limit

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.computed_at) > self.ttl_seconds


class PredictivePrefetchEngine:
    """
    Learns conversation patterns and pre-computes likely next responses
    in background threads for near-zero latency.
    """

    MAX_PREFETCH = 5       # Max concurrent prefetches
    MAX_HISTORY = 200      # Transition history size
    MIN_CONFIDENCE = 0.3   # Min confidence to prefetch

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        # Markov transition: query_category -> {next_category: count}
        self._transitions: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # Follow-up patterns: query_hash -> [predicted_next_queries]
        self._follow_ups: Dict[str, List[str]] = defaultdict(list)
        # Pre-computed cache
        self._prefetch_cache: Dict[str, PrefetchEntry] = {}
        self._lock = threading.Lock()
        # Stats
        self._total_predictions = 0
        self._hits = 0
        self._misses = 0
        self._last_query_category = ""
        self._last_query = ""
        # Common follow-up patterns
        self._common_patterns = {
            "explain": ["show example", "explain more", "how to implement"],
            "code": ["fix the bug", "optimize it", "add comments", "write tests"],
            "error": ["how to fix", "what caused it", "show stacktrace"],
            "compare": ["which is better", "pros and cons", "recommendation"],
            "create": ["improve it", "add more features", "refactor"],
            "list": ["explain each", "which is best", "more details"],
        }
        logger.info("[PREFETCH] Predictive prefetch engine initialized")

    def record_query(self, query: str):
        """Record a query to learn transition patterns."""
        category = self._categorize(query)

        # Update Markov transitions
        if self._last_query_category:
            self._transitions[self._last_query_category][category] += 1

        # Record follow-up pattern
        if self._last_query:
            query_hash = self._hash(self._last_query)
            follow_ups = self._follow_ups[query_hash]
            if query not in follow_ups:
                follow_ups.append(query)
                if len(follow_ups) > 10:
                    follow_ups.pop(0)

        self._last_query_category = category
        self._last_query = query

        # Trigger prefetch for predicted next queries
        self._trigger_prefetch(query)

    def check_prefetch(self, query: str) -> Optional[str]:
        """Check if we have a pre-computed response for this query."""
        self._total_predictions += 1
        query_hash = self._hash(query)

        with self._lock:
            entry = self._prefetch_cache.get(query_hash)
            if entry and not entry.is_stale:
                entry.served = True
                self._hits += 1
                logger.info(f"[PREFETCH] HIT! Pre-computed response served (confidence={entry.confidence:.2f})")
                return entry.predicted_response

        # Try semantic match
        query_lower = query.lower().strip()
        with self._lock:
            for key, entry in self._prefetch_cache.items():
                if entry.is_stale or entry.served:
                    continue
                # Simple token overlap check
                pred_tokens = set(entry.predicted_query.lower().split())
                query_tokens = set(query_lower.split())
                if pred_tokens and query_tokens:
                    overlap = len(pred_tokens & query_tokens) / max(len(pred_tokens | query_tokens), 1)
                    if overlap > 0.6:
                        entry.served = True
                        self._hits += 1
                        logger.info(f"[PREFETCH] SEMANTIC HIT (overlap={overlap:.2f})")
                        return entry.predicted_response

        self._misses += 1
        return None

    def _trigger_prefetch(self, current_query: str):
        """Predict and pre-compute likely next queries."""
        predictions = self._predict_next(current_query)

        # Launch background prefetch for top predictions
        for predicted_query, confidence in predictions[:self.MAX_PREFETCH]:
            if confidence >= self.MIN_CONFIDENCE:
                thread = threading.Thread(
                    target=self._prefetch_worker,
                    args=(predicted_query, confidence),
                    daemon=True,
                )
                thread.start()

    def _predict_next(self, query: str) -> List[Tuple[str, float]]:
        """Predict next likely queries with confidence scores."""
        predictions = []
        category = self._categorize(query)

        # 1. Check direct follow-up history
        query_hash = self._hash(query)
        if query_hash in self._follow_ups:
            for follow_up in self._follow_ups[query_hash][-3:]:
                predictions.append((follow_up, 0.8))

        # 2. Check Markov transitions
        if category in self._transitions:
            total = sum(self._transitions[category].values())
            for next_cat, count in self._transitions[category].items():
                prob = count / max(total, 1)
                if prob > 0.2:
                    # Generate a predicted query for this category
                    pred_query = self._generate_predicted_query(query, next_cat)
                    predictions.append((pred_query, prob))

        # 3. Check common patterns
        for pattern_key, follow_ups in self._common_patterns.items():
            if pattern_key in query.lower():
                for follow_up in follow_ups[:2]:
                    full_query = f"{follow_up} for: {query[:60]}"
                    predictions.append((full_query, 0.4))

        # Deduplicate and sort by confidence
        seen = set()
        unique = []
        for q, c in sorted(predictions, key=lambda x: x[1], reverse=True):
            q_hash = self._hash(q)
            if q_hash not in seen:
                seen.add(q_hash)
                unique.append((q, c))
        return unique

    def _prefetch_worker(self, predicted_query: str, confidence: float):
        """Background worker that pre-computes a response."""
        query_hash = self._hash(predicted_query)

        # Skip if already cached
        with self._lock:
            if query_hash in self._prefetch_cache:
                return

        if not self.generate_fn:
            return

        try:
            response = self.generate_fn(predicted_query)
            with self._lock:
                self._prefetch_cache[query_hash] = PrefetchEntry(
                    predicted_query=predicted_query,
                    predicted_response=response if isinstance(response, str) else str(response),
                    confidence=confidence,
                    computed_at=time.time(),
                )
            # Evict stale entries
            self._evict_stale()
        except Exception as e:
            logger.debug(f"[PREFETCH] Worker error: {e}")

    def _evict_stale(self):
        """Remove stale or served entries from cache."""
        with self._lock:
            stale_keys = [
                k for k, v in self._prefetch_cache.items()
                if v.is_stale or v.served
            ]
            for k in stale_keys:
                del self._prefetch_cache[k]

    def _categorize(self, query: str) -> str:
        """Categorize query into a broad type."""
        q = query.lower()
        categories = [
            ("code", ["code", "function", "implement", "class", "def "]),
            ("explain", ["explain", "what is", "how does", "describe", "tell me"]),
            ("error", ["error", "bug", "crash", "exception", "traceback"]),
            ("create", ["create", "build", "make", "generate", "design"]),
            ("compare", ["compare", "difference", "vs", "versus", "better"]),
            ("list", ["list", "enumerate", "show all", "options"]),
            ("fix", ["fix", "solve", "resolve", "repair", "debug"]),
        ]
        for cat, keywords in categories:
            if any(kw in q for kw in keywords):
                return cat
        return "general"

    def _generate_predicted_query(self, current: str, next_category: str) -> str:
        """Generate a predicted follow-up query for a given category."""
        templates = {
            "explain": f"Explain more about {current[:50]}",
            "code": f"Show the code for {current[:50]}",
            "fix": f"How to fix issues with {current[:50]}",
            "create": f"Create an improved version of {current[:50]}",
            "compare": f"Compare alternatives for {current[:50]}",
        }
        return templates.get(next_category, f"More about {current[:50]}")

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode()).hexdigest()[:12]

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_predictions": self._total_predictions,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / max(self._total_predictions, 1),
            "cache_size": len(self._prefetch_cache),
            "transition_patterns": len(self._transitions),
            "follow_up_patterns": len(self._follow_ups),
        }
