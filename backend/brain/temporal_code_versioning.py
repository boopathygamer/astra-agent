"""
Temporal Code Versioning — Branching Timeline Version Tree
══════════════════════════════════════════════════════════
Every Kernel Mutator mutation is stored in a branching temporal version
tree (not a linear history — a branching tree). The system can fork
alternate timelines of its own code, run them in parallel sandboxes,
and automatically converge on the highest-performing branch. Failed
mutations are preserved as "anti-patterns" to avoid permanently.

Architecture:
  Mutation → Fork Timeline → Sandbox Eval → Converge on Best → Prune Losers
                ↓                ↓                ↓
          Version Node    Parallel Benchmarks   Anti-Pattern Cache
"""

import hashlib
import logging
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class VersionState(Enum):
    ACTIVE = "active"
    CANDIDATE = "candidate"
    MERGED = "merged"
    PRUNED = "pruned"
    ANTI_PATTERN = "anti_pattern"


@dataclass
class VersionNode:
    """A node in the temporal version tree."""
    version_id: str = ""
    parent_id: Optional[str] = None
    code_snapshot: str = ""
    description: str = ""
    state: VersionState = VersionState.CANDIDATE
    performance_score: float = 0.0
    latency_ms: float = 0.0
    created_at: float = field(default_factory=time.time)
    evaluated_at: float = 0.0
    depth: int = 0
    tags: Set[str] = field(default_factory=set)

    def __post_init__(self):
        if not self.version_id:
            self.version_id = secrets.token_hex(6)


@dataclass
class TimelineFork:
    """A fork in the version tree creating parallel timelines."""
    fork_id: str = ""
    parent_version: str = ""
    branches: List[str] = field(default_factory=list)  # version_ids
    winner_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    resolved: bool = False


@dataclass
class AntiPattern:
    """A mutation that failed and should be avoided in the future."""
    pattern_id: str = ""
    code_hash: str = ""
    description: str = ""
    failure_reason: str = ""
    failure_score: float = 0.0
    occurrences: int = 1
    created_at: float = field(default_factory=time.time)


@dataclass
class ConvergenceResult:
    """Result of converging parallel timelines."""
    winning_version: Optional[VersionNode] = None
    pruned_versions: List[str] = field(default_factory=list)
    anti_patterns_added: int = 0
    performance_improvement: float = 0.0


# ──────────────────────────────────────────────
# Temporal Version Tree
# ──────────────────────────────────────────────

class TemporalVersionTree:
    """
    Branching version tree that tracks the evolution of code mutations.
    """

    def __init__(self):
        self._nodes: Dict[str, VersionNode] = {}
        self._children: Dict[str, List[str]] = {}  # parent_id → [child_ids]
        self._root_id: Optional[str] = None
        self._active_id: Optional[str] = None

    def create_root(self, code: str, description: str = "initial") -> str:
        """Create the root version node."""
        node = VersionNode(
            code_snapshot=code,
            description=description,
            state=VersionState.ACTIVE,
            depth=0,
        )
        self._nodes[node.version_id] = node
        self._root_id = node.version_id
        self._active_id = node.version_id
        self._children[node.version_id] = []
        return node.version_id

    def fork(
        self,
        parent_id: str,
        mutations: List[Tuple[str, str]],
    ) -> TimelineFork:
        """
        Fork a version into multiple parallel branches.

        Args:
            parent_id: The version to fork from
            mutations: List of (code_snapshot, description) for each branch
        """
        parent = self._nodes.get(parent_id)
        if not parent:
            raise ValueError(f"Parent version {parent_id} not found")

        fork = TimelineFork(
            fork_id=secrets.token_hex(4),
            parent_version=parent_id,
        )

        for code, desc in mutations:
            child = VersionNode(
                parent_id=parent_id,
                code_snapshot=code,
                description=desc,
                state=VersionState.CANDIDATE,
                depth=parent.depth + 1,
            )
            self._nodes[child.version_id] = child
            self._children.setdefault(parent_id, []).append(child.version_id)
            self._children[child.version_id] = []
            fork.branches.append(child.version_id)

        logger.info(
            f"Temporal: forked {parent_id} into {len(mutations)} branches"
        )
        return fork

    def evaluate(
        self,
        version_id: str,
        benchmark_fn: Optional[Callable[[str], float]] = None,
    ) -> float:
        """Evaluate a version's performance score."""
        node = self._nodes.get(version_id)
        if not node:
            return 0.0

        if benchmark_fn:
            start = time.perf_counter()
            score = benchmark_fn(node.code_snapshot)
            node.latency_ms = (time.perf_counter() - start) * 1000
        else:
            # Default: score based on code characteristics
            score = self._default_benchmark(node.code_snapshot)

        node.performance_score = score
        node.evaluated_at = time.time()
        return score

    def converge(
        self,
        fork: TimelineFork,
        anti_pattern_threshold: float = 0.3,
    ) -> ConvergenceResult:
        """
        Converge parallel branches: select winner, prune losers,
        and record anti-patterns.
        """
        result = ConvergenceResult()

        # Find best-performing branch
        candidates = [
            self._nodes[vid]
            for vid in fork.branches
            if vid in self._nodes
        ]

        if not candidates:
            return result

        evaluated = [n for n in candidates if n.evaluated_at > 0]
        if not evaluated:
            # Evaluate all candidates with default benchmark
            for node in candidates:
                self.evaluate(node.version_id)
            evaluated = candidates

        winner = max(evaluated, key=lambda n: n.performance_score)
        winner.state = VersionState.MERGED
        result.winning_version = winner
        fork.winner_id = winner.version_id
        fork.resolved = True

        # Set as new active version
        if self._active_id:
            old_active = self._nodes.get(self._active_id)
            if old_active:
                old_score = old_active.performance_score
                result.performance_improvement = (
                    winner.performance_score - old_score
                )

        self._active_id = winner.version_id

        # Prune losers and record anti-patterns
        for node in candidates:
            if node.version_id != winner.version_id:
                node.state = VersionState.PRUNED
                result.pruned_versions.append(node.version_id)

                if node.performance_score < anti_pattern_threshold:
                    node.state = VersionState.ANTI_PATTERN
                    result.anti_patterns_added += 1

        logger.info(
            f"Temporal: converged on {winner.version_id} "
            f"(score={winner.performance_score:.3f}, "
            f"pruned={len(result.pruned_versions)})"
        )

        return result

    @property
    def active_version(self) -> Optional[VersionNode]:
        if self._active_id:
            return self._nodes.get(self._active_id)
        return None

    @property
    def tree_depth(self) -> int:
        return max(
            (n.depth for n in self._nodes.values()),
            default=0,
        )

    def get_anti_patterns(self) -> List[VersionNode]:
        return [
            n for n in self._nodes.values()
            if n.state == VersionState.ANTI_PATTERN
        ]

    def get_lineage(self, version_id: str) -> List[VersionNode]:
        """Get the full lineage from root to the given version."""
        lineage = []
        current_id = version_id
        while current_id:
            node = self._nodes.get(current_id)
            if not node:
                break
            lineage.append(node)
            current_id = node.parent_id
        lineage.reverse()
        return lineage

    def get_stats(self) -> Dict[str, Any]:
        states = {}
        for node in self._nodes.values():
            s = node.state.value
            states[s] = states.get(s, 0) + 1

        return {
            "total_versions": len(self._nodes),
            "tree_depth": self.tree_depth,
            "states": states,
            "active_version": self._active_id,
            "anti_patterns": len(self.get_anti_patterns()),
        }

    def _default_benchmark(self, code: str) -> float:
        """Default scoring heuristic based on code characteristics."""
        score = 0.5
        if len(code) > 50:
            score += 0.1
        if "def " in code or "class " in code:
            score += 0.1
        if "return" in code:
            score += 0.05
        if "try" in code and "except" in code:
            score += 0.05
        if "# " in code:
            score += 0.05  # Has comments
        # Penalize
        if "pass" in code and len(code) < 30:
            score -= 0.2
        return max(0.0, min(1.0, score))
