"""
Phantom Computation Layer — Speculative Future Execution
════════════════════════════════════════════════════════
Run "phantom" computations across all possible future user actions
simultaneously. When the user acts, the correct phantom is materialized
instantly. Failed phantoms are garbage-collected.

Architecture:
  User State → Predictor → Phantom Tree (weighted branches)
                                ↓
                    Background Compute → Materialize on Match
                                ↓
                    Phantom GC → Prune Low-Probability Branches
"""

import hashlib
import logging
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PhantomBranch:
    """A speculative future computation branch."""
    branch_id: str = ""
    predicted_action: str = ""
    probability: float = 0.0
    result: Optional[str] = None
    state: str = "pending"       # pending | computing | ready | stale | materialized
    compute_ms: float = 0.0
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.branch_id:
            self.branch_id = secrets.token_hex(4)

    @property
    def is_ready(self) -> bool:
        return self.state == "ready" and self.result is not None


@dataclass
class PhantomTree:
    """A tree of speculative future computations."""
    tree_id: str = ""
    context: str = ""
    branches: Dict[str, PhantomBranch] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    materialized_branch: Optional[str] = None

    def __post_init__(self):
        if not self.tree_id:
            self.tree_id = secrets.token_hex(6)


@dataclass
class MaterializeResult:
    """Result of materializing a phantom branch."""
    hit: bool = False
    branch_id: str = ""
    predicted_action: str = ""
    actual_action: str = ""
    result: Optional[str] = None
    match_score: float = 0.0
    saved_ms: float = 0.0
    branches_gc: int = 0


class ActionPredictor:
    """Predicts likely next user actions from context and history."""

    def __init__(self):
        self._history: deque = deque(maxlen=200)
        self._transition_counts: Dict[str, Dict[str, int]] = {}

    def record(self, action: str) -> None:
        self._history.append(action)
        if len(self._history) >= 2:
            prev = self._history[-2]
            if prev not in self._transition_counts:
                self._transition_counts[prev] = {}
            counts = self._transition_counts[prev]
            counts[action] = counts.get(action, 0) + 1

    def predict(self, current_context: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Predict next actions with probabilities."""
        predictions: List[Tuple[str, float]] = []

        # From transition model
        if self._history:
            last = self._history[-1]
            counts = self._transition_counts.get(last, {})
            total = sum(counts.values()) or 1
            for action, count in counts.items():
                predictions.append((action, count / total))

        # From context keywords
        keywords = set(current_context.lower().split())
        common_actions = [
            ("explain", 0.15), ("fix", 0.12), ("implement", 0.10),
            ("optimize", 0.08), ("debug", 0.08), ("test", 0.07),
            ("refactor", 0.06), ("deploy", 0.05),
        ]
        for action, base_prob in common_actions:
            if any(action in kw for kw in keywords):
                predictions.append((action, base_prob * 2))
            else:
                predictions.append((action, base_prob * 0.5))

        # Deduplicate and normalize
        merged: Dict[str, float] = {}
        for action, prob in predictions:
            merged[action] = max(merged.get(action, 0), prob)

        total = sum(merged.values()) or 1.0
        normalized = [
            (action, prob / total)
            for action, prob in merged.items()
        ]
        normalized.sort(key=lambda x: x[1], reverse=True)
        return normalized[:top_k]


class PhantomComputationLayer:
    """
    Speculative future execution engine.

    Usage:
        phantom = PhantomComputationLayer(compute_fn=my_solver)

        # Pre-compute phantoms based on current context
        phantom.speculate("User is debugging a Python error")

        # When user acts, materialize the matching phantom
        result = phantom.materialize("fix the TypeError in line 42")
        if result.hit:
            print(f"Instant response! Saved {result.saved_ms:.0f}ms")
    """

    MAX_BRANCHES = 8
    MIN_PROBABILITY = 0.05
    STALE_AFTER_S = 60.0

    def __init__(self, compute_fn: Optional[Callable[[str], str]] = None):
        self._compute_fn = compute_fn
        self._predictor = ActionPredictor()
        self._active_tree: Optional[PhantomTree] = None
        self._total_speculations: int = 0
        self._total_materializations: int = 0
        self._total_hits: int = 0
        self._total_saved_ms: float = 0.0

    def speculate(self, context: str) -> PhantomTree:
        """Generate and pre-compute phantom branches for likely futures."""
        self._total_speculations += 1

        predictions = self._predictor.predict(context, top_k=self.MAX_BRANCHES)
        tree = PhantomTree(context=context)

        for action, probability in predictions:
            if probability < self.MIN_PROBABILITY:
                continue

            branch = PhantomBranch(
                predicted_action=action,
                probability=probability,
            )

            # Pre-compute the result
            if self._compute_fn:
                start = time.perf_counter()
                try:
                    branch.result = self._compute_fn(
                        f"Context: {context}\nAction: {action}"
                    )
                    branch.state = "ready"
                    branch.compute_ms = (time.perf_counter() - start) * 1000
                except Exception as e:
                    branch.state = "stale"
                    logger.warning(f"Phantom compute failed: {e}")
            else:
                branch.result = f"[phantom] {action}: {context[:80]}"
                branch.state = "ready"

            tree.branches[branch.branch_id] = branch

        self._active_tree = tree
        logger.debug(
            f"Phantom: speculated {len(tree.branches)} futures "
            f"for context '{context[:50]}'"
        )
        return tree

    def materialize(self, actual_action: str) -> MaterializeResult:
        """Match the actual user action to a phantom branch."""
        self._total_materializations += 1
        self._predictor.record(actual_action)

        if not self._active_tree:
            return MaterializeResult(hit=False, actual_action=actual_action)

        tree = self._active_tree
        best_match: Optional[PhantomBranch] = None
        best_score = 0.0
        actual_words = set(actual_action.lower().split())

        for branch in tree.branches.values():
            if not branch.is_ready:
                continue

            predicted_words = set(branch.predicted_action.lower().split())
            if not predicted_words:
                continue

            overlap = len(actual_words & predicted_words)
            union = len(actual_words | predicted_words)
            jaccard = overlap / max(union, 1)

            # Boost by probability
            score = jaccard * 0.7 + branch.probability * 0.3

            if score > best_score:
                best_score = score
                best_match = branch

        if best_match and best_score > 0.3:
            best_match.state = "materialized"
            tree.materialized_branch = best_match.branch_id
            self._total_hits += 1
            self._total_saved_ms += best_match.compute_ms

            gc_count = self._garbage_collect(tree, best_match.branch_id)

            return MaterializeResult(
                hit=True,
                branch_id=best_match.branch_id,
                predicted_action=best_match.predicted_action,
                actual_action=actual_action,
                result=best_match.result,
                match_score=best_score,
                saved_ms=best_match.compute_ms,
                branches_gc=gc_count,
            )

        return MaterializeResult(hit=False, actual_action=actual_action)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_speculations": self._total_speculations,
            "total_materializations": self._total_materializations,
            "total_hits": self._total_hits,
            "hit_rate": round(
                self._total_hits / max(self._total_materializations, 1), 3
            ),
            "total_saved_ms": round(self._total_saved_ms, 1),
            "active_branches": (
                len(self._active_tree.branches) if self._active_tree else 0
            ),
        }

    def _garbage_collect(self, tree: PhantomTree, keep_id: str) -> int:
        """Remove non-materialized branches."""
        gc_count = 0
        to_remove = [
            bid for bid in tree.branches
            if bid != keep_id
        ]
        for bid in to_remove:
            del tree.branches[bid]
            gc_count += 1
        return gc_count
