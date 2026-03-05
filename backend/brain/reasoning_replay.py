"""
Reasoning Graph Replay — Rewindable Thought Chains
────────────────────────────────────────────────────
Records full reasoning graphs so any decision can be replayed, audited,
or modified. Like version control for thoughts.

Architecture:
  ReasoningNode  →  ReasoningGraph (DAG)  →  ReplayEngine
  (single step)     (full chain)             (rewind + re-execute)
     ↓
  AuditTrail (human-readable log)
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class NodeType(Enum):
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    REASONING = "reasoning"
    DECISION = "decision"
    VERIFICATION = "verification"
    ACTION = "action"
    RESULT = "result"


@dataclass
class ReasoningNode:
    """A single reasoning step in the thought graph."""
    node_id: str = ""
    node_type: NodeType = NodeType.REASONING
    description: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    output: Any = None
    confidence: float = 0.0
    alternatives_considered: List[str] = field(default_factory=list)
    chosen_reason: str = ""       # Why this path was chosen
    parent_ids: List[str] = field(default_factory=list)
    child_ids: List[str] = field(default_factory=list)
    timestamp: float = 0.0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.node_id:
            self.node_id = hashlib.sha256(
                f"{self.description}{time.time()}".encode()
            ).hexdigest()[:12]
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class BranchPoint:
    """A point where reasoning diverged into multiple paths."""
    node_id: str
    branches: List[str] = field(default_factory=list)
    selected_branch: str = ""
    selection_reason: str = ""


@dataclass
class GraphSnapshot:
    """A snapshot of the reasoning graph at a specific point."""
    snapshot_id: str = ""
    node_id: str = ""          # The node at which this snapshot was taken
    timestamp: float = 0.0
    nodes: Dict[str, ReasoningNode] = field(default_factory=dict)


# ──────────────────────────────────────────────
# Reasoning Graph
# ──────────────────────────────────────────────

class ReasoningGraph:
    """
    Directed acyclic graph (DAG) of reasoning steps.
    Supports branching, merging, and querying.
    """

    def __init__(self, graph_id: str = ""):
        self.graph_id = graph_id or hashlib.sha256(
            str(time.time()).encode()
        ).hexdigest()[:12]
        self.nodes: Dict[str, ReasoningNode] = {}
        self.root_id: Optional[str] = None
        self.branch_points: List[BranchPoint] = []
        self._snapshots: List[GraphSnapshot] = []
        self.created_at: float = time.time()

    def add_node(self, node: ReasoningNode, parent_id: str = None) -> str:
        """Add a reasoning node to the graph."""
        self.nodes[node.node_id] = node

        if parent_id and parent_id in self.nodes:
            node.parent_ids.append(parent_id)
            self.nodes[parent_id].child_ids.append(node.node_id)

        if self.root_id is None:
            self.root_id = node.node_id

        return node.node_id

    def add_branch(self, parent_id: str, branch_nodes: List[ReasoningNode],
                   selected_idx: int = 0, reason: str = "") -> BranchPoint:
        """Add a branching point where reasoning diverges."""
        branch_ids = []
        for node in branch_nodes:
            self.add_node(node, parent_id=parent_id)
            branch_ids.append(node.node_id)

        bp = BranchPoint(
            node_id=parent_id,
            branches=branch_ids,
            selected_branch=branch_ids[selected_idx] if branch_ids else "",
            selection_reason=reason,
        )
        self.branch_points.append(bp)
        return bp

    def get_path(self, from_id: str = None, to_id: str = None) -> List[ReasoningNode]:
        """Get the reasoning path between two nodes."""
        start = from_id or self.root_id
        end = to_id

        if not start or start not in self.nodes:
            return []

        # BFS to find path
        queue = [(start, [start])]
        visited = set()

        while queue:
            current, path = queue.pop(0)
            if current == end:
                return [self.nodes[nid] for nid in path]
            if current in visited:
                continue
            visited.add(current)

            for child_id in self.nodes[current].child_ids:
                if child_id not in visited:
                    queue.append((child_id, path + [child_id]))

        # If no specific end, return full chain from start
        if end is None:
            return [self.nodes[nid] for nid in self._dfs_order(start)]

        return []

    def get_decision_chain(self) -> List[ReasoningNode]:
        """Get only the decision nodes in order."""
        return [
            n for n in self.get_path()
            if n.node_type == NodeType.DECISION
        ]

    def snapshot(self, label: str = "") -> str:
        """Take a snapshot of the current graph state."""
        snap = GraphSnapshot(
            snapshot_id=hashlib.sha256(
                f"{label}{time.time()}".encode()
            ).hexdigest()[:12],
            timestamp=time.time(),
            nodes={k: v for k, v in self.nodes.items()},
        )
        self._snapshots.append(snap)
        return snap.snapshot_id

    def _dfs_order(self, start_id: str) -> List[str]:
        """Depth-first traversal order."""
        visited = []
        stack = [start_id]
        seen = set()

        while stack:
            node_id = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            visited.append(node_id)

            if node_id in self.nodes:
                for child in reversed(self.nodes[node_id].child_ids):
                    if child not in seen:
                        stack.append(child)

        return visited

    @property
    def depth(self) -> int:
        """Maximum depth of the reasoning chain."""
        if not self.root_id:
            return 0

        def _depth(node_id: str, visited: set) -> int:
            if node_id in visited or node_id not in self.nodes:
                return 0
            visited.add(node_id)
            children = self.nodes[node_id].child_ids
            if not children:
                return 1
            return 1 + max(_depth(c, visited) for c in children)

        return _depth(self.root_id, set())


# ──────────────────────────────────────────────
# Replay Engine
# ──────────────────────────────────────────────

class ReplayEngine:
    """
    Can rewind to any node in a reasoning graph, modify inputs,
    and re-execute from that point using the original reasoning functions.
    """

    def __init__(self, execute_fn: Optional[Callable] = None):
        self._execute_fn = execute_fn
        self._replay_history: List[Dict[str, Any]] = []

    def rewind_to(self, graph: ReasoningGraph, node_id: str) -> ReasoningGraph:
        """
        Create a new graph that is a copy up to the specified node.
        All nodes after node_id are removed.
        """
        if node_id not in graph.nodes:
            return graph

        # Find all ancestors of the target node
        ancestors = self._find_ancestors(graph, node_id)
        ancestors.add(node_id)

        # Create new graph with only ancestor nodes
        new_graph = ReasoningGraph(graph_id=f"{graph.graph_id}_replay")
        for nid in ancestors:
            node = graph.nodes[nid]
            # Deep copy the node
            new_node = ReasoningNode(
                node_id=node.node_id,
                node_type=node.node_type,
                description=node.description,
                inputs=dict(node.inputs),
                output=node.output,
                confidence=node.confidence,
                alternatives_considered=list(node.alternatives_considered),
                chosen_reason=node.chosen_reason,
                parent_ids=[pid for pid in node.parent_ids if pid in ancestors],
                child_ids=[cid for cid in node.child_ids if cid in ancestors],
                timestamp=node.timestamp,
                duration_ms=node.duration_ms,
                metadata=dict(node.metadata),
            )
            new_graph.nodes[nid] = new_node

        new_graph.root_id = graph.root_id

        self._replay_history.append({
            "original_graph": graph.graph_id,
            "rewind_to": node_id,
            "new_graph": new_graph.graph_id,
            "timestamp": time.time(),
        })

        return new_graph

    def replay_from(self, graph: ReasoningGraph, node_id: str,
                    modified_inputs: Dict[str, Any] = None) -> Optional[ReasoningNode]:
        """
        Re-execute reasoning from a specific node with optionally modified inputs.
        """
        if not self._execute_fn or node_id not in graph.nodes:
            return None

        node = graph.nodes[node_id]
        inputs = dict(node.inputs)
        if modified_inputs:
            inputs.update(modified_inputs)

        # Re-execute
        start = time.time()
        try:
            new_output = self._execute_fn(inputs)
            duration_ms = (time.time() - start) * 1000

            replayed = ReasoningNode(
                node_type=node.node_type,
                description=f"[REPLAY] {node.description}",
                inputs=inputs,
                output=new_output,
                parent_ids=node.parent_ids[:],
                duration_ms=duration_ms,
                metadata={"replayed_from": node_id, **node.metadata},
            )

            graph.add_node(replayed, parent_id=node.parent_ids[0] if node.parent_ids else None)
            return replayed

        except Exception as e:
            logger.error(f"Replay failed at node {node_id}: {e}")
            return None

    def _find_ancestors(self, graph: ReasoningGraph, node_id: str) -> Set[str]:
        """Find all ancestor nodes of the given node."""
        ancestors = set()
        queue = [node_id]

        while queue:
            current = queue.pop(0)
            if current in graph.nodes:
                for parent in graph.nodes[current].parent_ids:
                    if parent not in ancestors:
                        ancestors.add(parent)
                        queue.append(parent)

        return ancestors


# ──────────────────────────────────────────────
# Audit Trail
# ──────────────────────────────────────────────

class AuditTrail:
    """
    Generates human-readable audit trails from reasoning graphs.
    """

    @staticmethod
    def generate(graph: ReasoningGraph) -> str:
        """Generate a full audit trail for a reasoning graph."""
        lines = [
            "═" * 60,
            "  REASONING AUDIT TRAIL",
            f"  Graph: {graph.graph_id}",
            f"  Nodes: {len(graph.nodes)} | Depth: {graph.depth}",
            f"  Branches: {len(graph.branch_points)}",
            "═" * 60,
        ]

        path = graph.get_path()
        for i, node in enumerate(path):
            emoji = {
                NodeType.OBSERVATION: "👁️",
                NodeType.HYPOTHESIS: "💭",
                NodeType.REASONING: "🧠",
                NodeType.DECISION: "⚖️",
                NodeType.VERIFICATION: "✅",
                NodeType.ACTION: "⚡",
                NodeType.RESULT: "🎯",
            }.get(node.node_type, "•")

            lines.append(f"\n{emoji} Step {i + 1}: {node.node_type.value.upper()}")
            lines.append(f"   {node.description}")

            if node.confidence > 0:
                conf_bar = "█" * int(node.confidence * 10) + "░" * (10 - int(node.confidence * 10))
                lines.append(f"   Confidence: {conf_bar} {node.confidence:.0%}")

            if node.alternatives_considered:
                lines.append(f"   Alternatives: {', '.join(node.alternatives_considered[:3])}")
                if node.chosen_reason:
                    lines.append(f"   Choice reason: {node.chosen_reason}")

            if node.duration_ms > 0:
                lines.append(f"   Duration: {node.duration_ms:.0f}ms")

        # Branch points
        if graph.branch_points:
            lines.append(f"\n{'─' * 40}")
            lines.append("  BRANCH DECISIONS:")
            for bp in graph.branch_points:
                lines.append(f"  ├ At node {bp.node_id}: {len(bp.branches)} branches")
                lines.append(f"  └ Selected: {bp.selected_branch} — {bp.selection_reason}")

        lines.append("\n" + "═" * 60)
        return "\n".join(lines)

    @staticmethod
    def generate_mermaid(graph: ReasoningGraph) -> str:
        """Generate a Mermaid flowchart of the reasoning graph."""
        lines = ["graph TD"]

        type_styles = {
            NodeType.OBSERVATION: "fill:#e3f2fd",
            NodeType.HYPOTHESIS: "fill:#fff3e0",
            NodeType.REASONING: "fill:#f3e5f5",
            NodeType.DECISION: "fill:#fff9c4",
            NodeType.VERIFICATION: "fill:#e8f5e9",
            NodeType.ACTION: "fill:#fce4ec",
            NodeType.RESULT: "fill:#c8e6c9",
        }

        for nid, node in graph.nodes.items():
            label = node.description[:40].replace('"', "'")
            conf = f" ({node.confidence:.0%})" if node.confidence > 0 else ""
            lines.append(f'    {nid}["{node.node_type.value}: {label}{conf}"]')

            for child_id in node.child_ids:
                lines.append(f"    {nid} --> {child_id}")

        # Styles
        for nid, node in graph.nodes.items():
            style = type_styles.get(node.node_type, "fill:#f5f5f5")
            lines.append(f"    style {nid} {style}")

        return "\n".join(lines)
