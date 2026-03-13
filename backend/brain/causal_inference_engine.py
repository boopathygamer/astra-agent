"""
Causal Inference Engine — Live Cause-Effect DAG Reasoning
═════════════════════════════════════════════════════════
Builds and maintains a live directed acyclic graph (DAG) of cause-effect
relationships from every interaction. When the user asks "why did X happen?",
the system traverses the causal graph instead of pattern-matching.

This is a fundamentally different reasoning capability than correlational
pattern-matching used by standard LLMs.

Architecture:
  Observations → Causal Extractor → DAG Builder → Causal Queries
                                      ↓
                              Intervention Analysis
                              Counterfactual Reasoning
"""

import hashlib
import logging
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class CausalRelationType(Enum):
    """Type of causal relationship between two nodes."""
    CAUSES = "causes"                # A directly causes B
    ENABLES = "enables"              # A makes B possible
    PREVENTS = "prevents"            # A blocks B from occurring
    CORRELATES = "correlates"        # A and B co-occur (non-causal)
    MEDIATES = "mediates"            # A causes B through intermediate C
    MODERATES = "moderates"          # A changes the strength of B→C


@dataclass
class CausalNode:
    """A node in the causal graph representing an event or state."""
    node_id: str = ""
    label: str = ""
    description: str = ""
    domain: str = "general"
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.5
    observation_count: int = 1
    tags: Set[str] = field(default_factory=set)

    def __post_init__(self):
        if not self.node_id:
            self.node_id = hashlib.sha256(
                f"{self.label}{secrets.token_hex(4)}".encode()
            ).hexdigest()[:10]

    def __hash__(self):
        return hash(self.node_id)

    def __eq__(self, other):
        if isinstance(other, CausalNode):
            return self.node_id == other.node_id
        return False


@dataclass
class CausalEdge:
    """A directed edge representing a causal relationship."""
    edge_id: str = ""
    source_id: str = ""
    target_id: str = ""
    relation: CausalRelationType = CausalRelationType.CAUSES
    strength: float = 0.5           # 0.0 (weak) → 1.0 (deterministic)
    confidence: float = 0.5
    evidence_count: int = 1
    created_at: float = field(default_factory=time.time)
    last_reinforced: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.edge_id:
            self.edge_id = hashlib.sha256(
                f"{self.source_id}{self.target_id}{self.relation.value}".encode()
            ).hexdigest()[:10]

    def reinforce(self, strength_delta: float = 0.05) -> None:
        """Strengthen the causal link based on new evidence."""
        self.evidence_count += 1
        self.strength = min(1.0, self.strength + strength_delta)
        self.confidence = min(
            0.99,
            1.0 - 1.0 / (self.evidence_count + 1),
        )
        self.last_reinforced = time.time()


@dataclass
class CausalPath:
    """A complete causal chain from root cause to effect."""
    nodes: List[CausalNode] = field(default_factory=list)
    edges: List[CausalEdge] = field(default_factory=list)
    total_strength: float = 0.0
    path_length: int = 0

    def summary(self) -> str:
        if not self.nodes:
            return "[empty causal path]"
        chain = " → ".join(n.label for n in self.nodes)
        return f"[strength={self.total_strength:.3f}] {chain}"


@dataclass
class CausalQuery:
    """Result of a causal query."""
    query: str = ""
    query_type: str = "why"          # why, what_if, how
    paths: List[CausalPath] = field(default_factory=list)
    root_causes: List[CausalNode] = field(default_factory=list)
    effects: List[CausalNode] = field(default_factory=list)
    explanation: str = ""
    confidence: float = 0.0


# ──────────────────────────────────────────────
# Causal DAG
# ──────────────────────────────────────────────

class CausalDAG:
    """
    Directed acyclic graph for causal relationships.
    Supports topological queries, path finding, and cycle prevention.
    """

    def __init__(self):
        self._nodes: Dict[str, CausalNode] = {}
        self._edges: Dict[str, CausalEdge] = {}
        self._adjacency: Dict[str, List[str]] = defaultdict(list)       # source → [edge_ids]
        self._reverse_adj: Dict[str, List[str]] = defaultdict(list)     # target → [edge_ids]
        self._label_index: Dict[str, str] = {}                          # label → node_id

    def add_node(self, node: CausalNode) -> str:
        """Add a node to the graph. Returns node_id."""
        self._nodes[node.node_id] = node
        self._label_index[node.label.lower()] = node.node_id
        return node.node_id

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: CausalRelationType = CausalRelationType.CAUSES,
        strength: float = 0.5,
    ) -> Optional[str]:
        """
        Add a causal edge. Returns edge_id or None if it would create a cycle.
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            logger.warning(f"Cannot add edge: missing node(s)")
            return None

        # Cycle detection: check if target can already reach source
        if self._can_reach(target_id, source_id):
            logger.warning(
                f"Cycle detected: {target_id} can reach {source_id}. "
                f"Edge rejected."
            )
            return None

        # Check if edge already exists → reinforce it
        for eid in self._adjacency.get(source_id, []):
            edge = self._edges[eid]
            if edge.target_id == target_id and edge.relation == relation:
                edge.reinforce()
                logger.debug(f"Reinforced edge {eid} (strength={edge.strength:.3f})")
                return eid

        edge = CausalEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            strength=strength,
        )
        self._edges[edge.edge_id] = edge
        self._adjacency[source_id].append(edge.edge_id)
        self._reverse_adj[target_id].append(edge.edge_id)

        return edge.edge_id

    def find_causes(self, node_id: str, max_depth: int = 5) -> List[CausalPath]:
        """Find all causal paths leading TO a node (root cause analysis)."""
        paths = []
        self._dfs_backward(node_id, [], [], max_depth, paths)
        paths.sort(key=lambda p: p.total_strength, reverse=True)
        return paths

    def find_effects(self, node_id: str, max_depth: int = 5) -> List[CausalPath]:
        """Find all causal paths leading FROM a node (impact analysis)."""
        paths = []
        self._dfs_forward(node_id, [], [], max_depth, paths)
        paths.sort(key=lambda p: p.total_strength, reverse=True)
        return paths

    def find_node_by_label(self, label: str) -> Optional[CausalNode]:
        """Look up a node by its label (case-insensitive)."""
        nid = self._label_index.get(label.lower())
        if nid:
            return self._nodes.get(nid)
        # Fuzzy match: check for substring containment
        for stored_label, nid in self._label_index.items():
            if label.lower() in stored_label or stored_label in label.lower():
                return self._nodes.get(nid)
        return None

    def get_root_causes(self) -> List[CausalNode]:
        """Get all nodes with no incoming causal edges (root causes)."""
        targets = set()
        for edge in self._edges.values():
            if edge.relation == CausalRelationType.CAUSES:
                targets.add(edge.target_id)

        return [
            self._nodes[nid]
            for nid in self._nodes
            if nid not in targets
        ]

    def get_leaf_effects(self) -> List[CausalNode]:
        """Get all nodes with no outgoing causal edges (terminal effects)."""
        sources = set()
        for edge in self._edges.values():
            if edge.relation == CausalRelationType.CAUSES:
                sources.add(edge.source_id)

        return [
            self._nodes[nid]
            for nid in self._nodes
            if nid not in sources
        ]

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    # ── Private traversal methods ──

    def _can_reach(self, start: str, target: str) -> bool:
        """BFS to check if start can reach target via forward edges."""
        visited = set()
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            for eid in self._adjacency.get(current, []):
                edge = self._edges[eid]
                queue.append(edge.target_id)
        return False

    def _dfs_backward(
        self,
        node_id: str,
        current_nodes: List[CausalNode],
        current_edges: List[CausalEdge],
        max_depth: int,
        results: List[CausalPath],
    ) -> None:
        """DFS backward through causal edges to find root causes."""
        node = self._nodes.get(node_id)
        if not node:
            return

        current_nodes = [node] + current_nodes

        incoming = self._reverse_adj.get(node_id, [])
        causal_incoming = [
            self._edges[eid] for eid in incoming
            if self._edges[eid].relation in (
                CausalRelationType.CAUSES,
                CausalRelationType.ENABLES,
                CausalRelationType.MEDIATES,
            )
        ]

        if not causal_incoming or max_depth <= 0:
            # Reached a root cause
            if len(current_nodes) > 1:
                total_strength = (
                    sum(e.strength for e in current_edges) / max(len(current_edges), 1)
                )
                results.append(CausalPath(
                    nodes=list(current_nodes),
                    edges=list(current_edges),
                    total_strength=total_strength,
                    path_length=len(current_edges),
                ))
            return

        for edge in causal_incoming:
            if edge.source_id not in [n.node_id for n in current_nodes]:
                self._dfs_backward(
                    edge.source_id,
                    current_nodes,
                    [edge] + current_edges,
                    max_depth - 1,
                    results,
                )

    def _dfs_forward(
        self,
        node_id: str,
        current_nodes: List[CausalNode],
        current_edges: List[CausalEdge],
        max_depth: int,
        results: List[CausalPath],
    ) -> None:
        """DFS forward through causal edges to find effects."""
        node = self._nodes.get(node_id)
        if not node:
            return

        current_nodes = current_nodes + [node]

        outgoing = self._adjacency.get(node_id, [])
        causal_outgoing = [
            self._edges[eid] for eid in outgoing
            if self._edges[eid].relation in (
                CausalRelationType.CAUSES,
                CausalRelationType.ENABLES,
            )
        ]

        if not causal_outgoing or max_depth <= 0:
            if len(current_nodes) > 1:
                total_strength = (
                    sum(e.strength for e in current_edges) / max(len(current_edges), 1)
                )
                results.append(CausalPath(
                    nodes=list(current_nodes),
                    edges=list(current_edges),
                    total_strength=total_strength,
                    path_length=len(current_edges),
                ))
            return

        for edge in causal_outgoing:
            if edge.target_id not in [n.node_id for n in current_nodes]:
                self._dfs_forward(
                    edge.target_id,
                    current_nodes,
                    current_edges + [edge],
                    max_depth - 1,
                    results,
                )


# ──────────────────────────────────────────────
# Causal Inference Engine (Main Interface)
# ──────────────────────────────────────────────

class CausalInferenceEngine:
    """
    High-level interface for causal reasoning.

    Usage:
        engine = CausalInferenceEngine()
        engine.observe("bug_in_code", "causes", "test_failure")
        engine.observe("test_failure", "causes", "deployment_blocked")
        result = engine.why("deployment_blocked")
        # → bug_in_code → test_failure → deployment_blocked
    """

    def __init__(self):
        self.dag = CausalDAG()

    def observe(
        self,
        cause_label: str,
        relation: str,
        effect_label: str,
        strength: float = 0.5,
        domain: str = "general",
    ) -> Tuple[str, str, str]:
        """
        Record a causal observation.
        Creates nodes if they don't exist, adds or reinforces the edge.

        Returns:
            Tuple of (cause_node_id, edge_id, effect_node_id)
        """
        # Find or create cause node
        cause_node = self.dag.find_node_by_label(cause_label)
        if not cause_node:
            cause_node = CausalNode(label=cause_label, domain=domain)
            self.dag.add_node(cause_node)
        else:
            cause_node.observation_count += 1

        # Find or create effect node
        effect_node = self.dag.find_node_by_label(effect_label)
        if not effect_node:
            effect_node = CausalNode(label=effect_label, domain=domain)
            self.dag.add_node(effect_node)
        else:
            effect_node.observation_count += 1

        # Map relation string
        rel_map = {
            "causes": CausalRelationType.CAUSES,
            "enables": CausalRelationType.ENABLES,
            "prevents": CausalRelationType.PREVENTS,
            "correlates": CausalRelationType.CORRELATES,
            "mediates": CausalRelationType.MEDIATES,
            "moderates": CausalRelationType.MODERATES,
        }
        rel_type = rel_map.get(relation.lower(), CausalRelationType.CAUSES)

        edge_id = self.dag.add_edge(
            cause_node.node_id,
            effect_node.node_id,
            relation=rel_type,
            strength=strength,
        )

        logger.info(
            f"Causal: {cause_label} --[{rel_type.value}]--> {effect_label} "
            f"(strength={strength:.2f})"
        )

        return cause_node.node_id, edge_id or "", effect_node.node_id

    def why(self, effect_label: str, max_depth: int = 5) -> CausalQuery:
        """Answer 'why did X happen?' by traversing causal chains backward."""
        node = self.dag.find_node_by_label(effect_label)
        if not node:
            return CausalQuery(
                query=f"Why: {effect_label}",
                query_type="why",
                explanation=f"No causal data found for '{effect_label}'",
            )

        paths = self.dag.find_causes(node.node_id, max_depth=max_depth)
        root_causes = [p.nodes[0] for p in paths] if paths else []

        explanation_parts = []
        for i, path in enumerate(paths[:5]):
            explanation_parts.append(f"{i + 1}. {path.summary()}")

        return CausalQuery(
            query=f"Why: {effect_label}",
            query_type="why",
            paths=paths,
            root_causes=root_causes,
            explanation="\n".join(explanation_parts) if explanation_parts else "No causal chains found.",
            confidence=max((p.total_strength for p in paths), default=0.0),
        )

    def what_if(self, cause_label: str, max_depth: int = 5) -> CausalQuery:
        """Answer 'what would happen if X?' by traversing forward."""
        node = self.dag.find_node_by_label(cause_label)
        if not node:
            return CausalQuery(
                query=f"What if: {cause_label}",
                query_type="what_if",
                explanation=f"No causal data found for '{cause_label}'",
            )

        paths = self.dag.find_effects(node.node_id, max_depth=max_depth)
        effects = [p.nodes[-1] for p in paths] if paths else []

        explanation_parts = []
        for i, path in enumerate(paths[:5]):
            explanation_parts.append(f"{i + 1}. {path.summary()}")

        return CausalQuery(
            query=f"What if: {cause_label}",
            query_type="what_if",
            paths=paths,
            effects=effects,
            explanation="\n".join(explanation_parts) if explanation_parts else "No downstream effects found.",
            confidence=max((p.total_strength for p in paths), default=0.0),
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_nodes": self.dag.node_count,
            "total_edges": self.dag.edge_count,
            "root_causes": len(self.dag.get_root_causes()),
            "leaf_effects": len(self.dag.get_leaf_effects()),
        }
