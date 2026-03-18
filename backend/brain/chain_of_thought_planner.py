"""
Chain-of-Thought Planner — Tree-of-Thought Planning with Branch Pruning
═══════════════════════════════════════════════════════════════════════
Generates multiple reasoning branches, evaluates each, prunes losers,
and expands winners to find the optimal solution path.

Architecture:
  Problem → [Branch 1] → score → expand/prune
          → [Branch 2] → score → expand/prune
          → [Branch 3] → score → expand/prune
                         ↓
              Best path → Solution
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    PENDING = "pending"
    EXPANDED = "expanded"
    PRUNED = "pruned"
    SOLUTION = "solution"


@dataclass
class ThoughtNode:
    """A single node in the thought tree."""
    node_id: str = ""
    parent_id: str = ""
    depth: int = 0
    thought: str = ""
    evaluation_score: float = 0.0
    status: NodeStatus = NodeStatus.PENDING
    children_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.node_id:
            self.node_id = hashlib.md5(
                f"{self.parent_id}:{self.thought[:50]}:{time.time()}".encode()
            ).hexdigest()[:12]


@dataclass
class PlanResult:
    """Result of a planning session."""
    problem: str = ""
    solution_path: List[ThoughtNode] = field(default_factory=list)
    best_score: float = 0.0
    total_nodes_explored: int = 0
    nodes_pruned: int = 0
    depth_reached: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem": self.problem[:100],
            "solution_steps": [n.thought for n in self.solution_path],
            "best_score": round(self.best_score, 4),
            "nodes_explored": self.total_nodes_explored,
            "nodes_pruned": self.nodes_pruned,
            "depth": self.depth_reached,
            "duration_ms": round(self.duration_ms, 2),
        }


class ChainOfThoughtPlanner:
    """
    Tree-of-Thought planner that generates multiple reasoning branches,
    evaluates them, prunes poor branches, and expands promising ones.

    Uses beam search with configurable width and depth.
    """

    def __init__(
        self,
        max_depth: int = 5,
        beam_width: int = 3,
        branch_factor: int = 3,
        prune_threshold: float = 0.3,
        thought_generator: Optional[Callable] = None,
        thought_evaluator: Optional[Callable] = None,
    ):
        self.max_depth = max_depth
        self.beam_width = beam_width
        self.branch_factor = branch_factor
        self.prune_threshold = prune_threshold
        self._thought_generator = thought_generator or self._default_generator
        self._thought_evaluator = thought_evaluator or self._default_evaluator
        self._all_nodes: Dict[str, ThoughtNode] = {}
        self._sessions: List[PlanResult] = []

        logger.info(
            f"[COT_PLANNER] Initialized — depth={max_depth}, "
            f"beam={beam_width}, branches={branch_factor}"
        )

    def plan(self, problem: str, context: str = "") -> PlanResult:
        """
        Generate a tree-of-thought plan for the given problem.

        Returns the best solution path found within depth/beam constraints.
        """
        start = time.time()
        self._all_nodes.clear()

        # Create root node
        root = ThoughtNode(
            thought=f"Problem: {problem}",
            depth=0,
            evaluation_score=1.0,
            status=NodeStatus.EXPANDED,
        )
        self._all_nodes[root.node_id] = root

        # Beam search
        current_beam = [root]
        nodes_pruned = 0

        for depth in range(1, self.max_depth + 1):
            candidates = []

            for parent in current_beam:
                # Generate child thoughts
                children = self._expand(parent, problem, context)
                for child in children:
                    child.depth = depth
                    child.parent_id = parent.node_id
                    self._all_nodes[child.node_id] = child
                    parent.children_ids.append(child.node_id)

                    # Evaluate
                    child.evaluation_score = self._thought_evaluator(
                        problem, child.thought, depth
                    )
                    candidates.append(child)

            if not candidates:
                break

            # Sort by score and keep top beam_width
            candidates.sort(key=lambda n: n.evaluation_score, reverse=True)

            # Prune below threshold
            surviving = []
            for c in candidates:
                if c.evaluation_score >= self.prune_threshold:
                    surviving.append(c)
                    c.status = NodeStatus.EXPANDED
                else:
                    c.status = NodeStatus.PRUNED
                    nodes_pruned += 1

            # Keep beam width
            current_beam = surviving[:self.beam_width]

            # Check for solution-quality nodes
            for node in current_beam:
                if node.evaluation_score >= 0.9:
                    node.status = NodeStatus.SOLUTION

        # Reconstruct best path
        best_node = max(
            self._all_nodes.values(),
            key=lambda n: n.evaluation_score if n.status != NodeStatus.PRUNED else 0,
        )
        solution_path = self._trace_path(best_node)

        result = PlanResult(
            problem=problem,
            solution_path=solution_path,
            best_score=best_node.evaluation_score,
            total_nodes_explored=len(self._all_nodes),
            nodes_pruned=nodes_pruned,
            depth_reached=best_node.depth,
            duration_ms=(time.time() - start) * 1000,
        )
        self._sessions.append(result)

        logger.info(
            f"[COT_PLANNER] Plan complete — score={result.best_score:.3f}, "
            f"explored={result.total_nodes_explored}, pruned={nodes_pruned}, "
            f"depth={result.depth_reached}"
        )
        return result

    def _expand(self, parent: ThoughtNode, problem: str, context: str) -> List[ThoughtNode]:
        """Generate child thought nodes from a parent."""
        children = []
        for i in range(self.branch_factor):
            thought = self._thought_generator(problem, parent.thought, i, context)
            children.append(ThoughtNode(thought=thought))
        return children

    def _trace_path(self, node: ThoughtNode) -> List[ThoughtNode]:
        """Trace the path from root to this node."""
        path = [node]
        current = node
        while current.parent_id and current.parent_id in self._all_nodes:
            current = self._all_nodes[current.parent_id]
            path.append(current)
        path.reverse()
        return path

    # ── Default Implementations (replaced by LLM in production) ──

    @staticmethod
    def _default_generator(problem: str, parent_thought: str, branch_idx: int, context: str) -> str:
        """Default thought generator (heuristic, replaced by LLM)."""
        strategies = [
            "Break this into smaller sub-problems and solve each independently.",
            "Consider the edge cases and constraints that might affect the solution.",
            "Look for patterns or analogies from similar problems.",
        ]
        idx = branch_idx % len(strategies)
        return f"Step: {strategies[idx]} Building on: {parent_thought[:80]}..."

    @staticmethod
    def _default_evaluator(problem: str, thought: str, depth: int) -> float:
        """Default thought evaluator (heuristic, replaced by LLM)."""
        score = 0.5
        # Reward specificity
        if len(thought) > 50:
            score += 0.1
        if any(kw in thought.lower() for kw in ["because", "therefore", "since", "step"]):
            score += 0.15
        # Reward depth-appropriate detail
        if depth <= 2 and "break" in thought.lower():
            score += 0.1
        if depth >= 3 and any(kw in thought.lower() for kw in ["solution", "result", "answer"]):
            score += 0.15
        return min(1.0, score)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_sessions": len(self._sessions),
            "avg_nodes_explored": (
                sum(s.total_nodes_explored for s in self._sessions) / max(len(self._sessions), 1)
            ),
            "avg_best_score": (
                sum(s.best_score for s in self._sessions) / max(len(self._sessions), 1)
            ),
            "config": {
                "max_depth": self.max_depth,
                "beam_width": self.beam_width,
                "branch_factor": self.branch_factor,
                "prune_threshold": self.prune_threshold,
            },
        }
