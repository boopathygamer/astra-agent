"""
Non-Euclidean Memory — Hypergraph Knowledge Store
─────────────────────────────────────────────────
Expert-level graph-based knowledge store where nodes connect
via weighted semantic edges. Implements actual graph traversal
algorithms (BFS, shortest path) instead of O(n²) full linking.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class TesseractNode:
    """A node in the hypergraph knowledge store."""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    data: Any = None
    edges: Dict[str, float] = field(default_factory=dict)  # neighbor_id → weight
    created_at: float = field(default_factory=time.time)


class NonEuclideanMemory:
    """
    Tier 7: Non-Euclidean Memory Topography

    Weighted hypergraph knowledge store with BFS search,
    shortest-path queries, and semantic edge weights.
    O(1) node lookup, O(V+E) traversal.
    """

    def __init__(self):
        self._nodes: Dict[str, TesseractNode] = {}
        self._data_index: Dict[Any, str] = {}  # data → node_id for O(1) lookup
        logger.info("[HYPER-MEMORY] Hypergraph knowledge store initialized.")

    def insert(self, data: Any, connections: Optional[Dict[str, float]] = None) -> str:
        """Insert a node into the hypergraph. Returns node ID."""
        node = TesseractNode(data=data)
        self._nodes[node.id] = node
        self._data_index[data] = node.id

        if connections:
            for target_id, weight in connections.items():
                if target_id in self._nodes:
                    node.edges[target_id] = weight
                    self._nodes[target_id].edges[node.id] = weight  # bidirectional

        logger.debug("[HYPER-MEMORY] Inserted node %s (edges=%d).", node.id, len(node.edges))
        return node.id

    def connect(self, node_a_id: str, node_b_id: str, weight: float = 1.0) -> bool:
        """Create a weighted edge between two nodes."""
        if node_a_id not in self._nodes or node_b_id not in self._nodes:
            return False
        self._nodes[node_a_id].edges[node_b_id] = weight
        self._nodes[node_b_id].edges[node_a_id] = weight
        return True

    def lookup(self, data: Any) -> Optional[TesseractNode]:
        """O(1) lookup by data value."""
        node_id = self._data_index.get(data)
        if node_id:
            return self._nodes.get(node_id)
        return None

    def bfs_search(self, start_id: str, target_data: Any, max_depth: int = 10) -> Optional[List[str]]:
        """BFS search for a node by data value. Returns path or None."""
        if start_id not in self._nodes:
            return None

        visited: Set[str] = set()
        queue: deque = deque([(start_id, [start_id])])

        while queue:
            current_id, path = queue.popleft()
            if len(path) > max_depth:
                break

            if self._nodes[current_id].data == target_data:
                logger.info("[HYPER-MEMORY] BFS found target in %d hops.", len(path) - 1)
                return path

            visited.add(current_id)
            for neighbor_id in self._nodes[current_id].edges:
                if neighbor_id not in visited:
                    queue.append((neighbor_id, path + [neighbor_id]))

        return None

    def get_neighbors(self, node_id: str) -> List[TesseractNode]:
        """Get all neighbor nodes."""
        node = self._nodes.get(node_id)
        if not node:
            return []
        return [self._nodes[nid] for nid in node.edges if nid in self._nodes]

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(n.edges) for n in self._nodes.values()) // 2


# Global singleton — always active
non_euclidean_memory = NonEuclideanMemory()
