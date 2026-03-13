"""
Synaptic Tool Chaining — Persistent Inter-Tool Pipeline System
═════════════════════════════════════════════════════════════════
Allows tools to form persistent "synaptic connections" where the output
stream of one tool is continuously piped into another without returning
to the main controller. Like Unix pipes, but for AI tool operations.

Eliminates round-trip overhead between every tool call.

Architecture:
  Tool A → Synapse → Tool B → Synapse → Tool C
            ↓                    ↓
     Shared Memory Bus    Zero-Copy Transfer
"""

import hashlib
import logging
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class SynapseState(Enum):
    IDLE = "idle"
    FLOWING = "flowing"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ToolNode:
    """A tool node in the synaptic chain."""
    node_id: str = ""
    name: str = ""
    fn: Optional[Callable] = None
    input_type: str = "any"
    output_type: str = "any"

    def __post_init__(self):
        if not self.node_id:
            self.node_id = secrets.token_hex(4)

    def execute(self, input_data: Any) -> Any:
        """Execute this tool node with the given input."""
        if self.fn:
            return self.fn(input_data)
        return input_data


@dataclass
class Synapse:
    """A connection between two tool nodes."""
    synapse_id: str = ""
    source_id: str = ""
    target_id: str = ""
    state: SynapseState = SynapseState.IDLE
    transform_fn: Optional[Callable] = None
    buffer: deque = field(default_factory=lambda: deque(maxlen=100))
    data_transferred: int = 0

    def __post_init__(self):
        if not self.synapse_id:
            self.synapse_id = secrets.token_hex(4)

    def transmit(self, data: Any) -> Any:
        """Transmit data through this synapse with optional transformation."""
        self.state = SynapseState.FLOWING
        self.data_transferred += 1
        self.buffer.append(data)

        if self.transform_fn:
            return self.transform_fn(data)
        return data


@dataclass
class ChainResult:
    """Result of executing a full synaptic tool chain."""
    chain_id: str = ""
    final_output: Any = None
    intermediate_outputs: List[Tuple[str, Any]] = field(default_factory=list)
    total_nodes: int = 0
    total_duration_ms: float = 0.0
    per_node_ms: List[Tuple[str, float]] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None

    def summary(self) -> str:
        status = "OK" if self.success else f"FAIL: {self.error}"
        return (
            f"STC: {self.total_nodes} nodes | "
            f"{self.total_duration_ms:.1f}ms | {status}"
        )


# ──────────────────────────────────────────────
# Chain Builder
# ──────────────────────────────────────────────

class ChainBuilder:
    """
    Fluent API for building synaptic tool chains.

    Usage:
        chain = (ChainBuilder()
            .add("search", search_fn)
            .add("parse", parse_fn)
            .add("summarize", summarize_fn)
            .build())
    """

    def __init__(self):
        self._nodes: List[ToolNode] = []
        self._transforms: Dict[int, Callable] = {}

    def add(
        self,
        name: str,
        fn: Callable,
        transform: Optional[Callable] = None,
    ) -> "ChainBuilder":
        """Add a tool node to the chain."""
        idx = len(self._nodes)
        self._nodes.append(ToolNode(name=name, fn=fn))
        if transform:
            self._transforms[idx] = transform
        return self

    def build(self) -> "SynapticChain":
        """Build the chain and return a SynapticChain instance."""
        chain = SynapticChain()
        for i, node in enumerate(self._nodes):
            chain.add_node(node)

        # Connect sequential nodes with synapses
        for i in range(len(self._nodes) - 1):
            transform = self._transforms.get(i)
            chain.connect(
                self._nodes[i].node_id,
                self._nodes[i + 1].node_id,
                transform_fn=transform,
            )

        # Ensure execution order is built even for single-node chains
        chain._rebuild_execution_order()

        return chain


# ──────────────────────────────────────────────
# Synaptic Chain (Main Interface)
# ──────────────────────────────────────────────

class SynapticChain:
    """
    Persistent inter-tool pipeline with zero-copy data transfer.

    Usage:
        chain = SynapticChain()
        chain.add_node(ToolNode(name="search", fn=search_fn))
        chain.add_node(ToolNode(name="parse", fn=parse_fn))
        chain.add_node(ToolNode(name="summarize", fn=summarize_fn))
        chain.connect("search", "parse")
        chain.connect("parse", "summarize")

        result = chain.execute("query")
        print(result.summary())
    """

    def __init__(self):
        self._nodes: Dict[str, ToolNode] = {}
        self._synapses: Dict[str, Synapse] = {}
        self._adjacency: Dict[str, List[str]] = {}  # node_id → [synapse_ids]
        self._entry_nodes: List[str] = []
        self._execution_order: List[str] = []
        self._total_executions: int = 0

    def add_node(self, node: ToolNode) -> str:
        """Add a tool node to the chain."""
        self._nodes[node.node_id] = node
        if node.node_id not in self._adjacency:
            self._adjacency[node.node_id] = []
        return node.node_id

    def connect(
        self,
        source_id: str,
        target_id: str,
        transform_fn: Optional[Callable] = None,
    ) -> str:
        """Create a synapse between two nodes."""
        synapse = Synapse(
            source_id=source_id,
            target_id=target_id,
            transform_fn=transform_fn,
        )
        self._synapses[synapse.synapse_id] = synapse
        self._adjacency.setdefault(source_id, []).append(synapse.synapse_id)

        # Rebuild execution order
        self._rebuild_execution_order()

        return synapse.synapse_id

    def execute(self, input_data: Any) -> ChainResult:
        """Execute the full chain from entry nodes to exit nodes."""
        start = time.perf_counter()
        chain_id = secrets.token_hex(6)
        self._total_executions += 1

        result = ChainResult(
            chain_id=chain_id,
            total_nodes=len(self._execution_order),
        )

        if not self._execution_order:
            result.success = False
            result.error = "Empty chain"
            return result

        # Flow data through the chain
        current_data = input_data
        for node_id in self._execution_order:
            node = self._nodes[node_id]
            node_start = time.perf_counter()

            try:
                output = node.execute(current_data)
                node_ms = (time.perf_counter() - node_start) * 1000
                result.intermediate_outputs.append((node.name, output))
                result.per_node_ms.append((node.name, node_ms))

                # Transmit through outgoing synapses
                for syn_id in self._adjacency.get(node_id, []):
                    synapse = self._synapses[syn_id]
                    output = synapse.transmit(output)

                current_data = output

            except Exception as e:
                result.success = False
                result.error = f"Node '{node.name}': {e}"
                logger.error(f"STC error at node {node.name}: {e}")
                break

        result.final_output = current_data
        result.total_duration_ms = (time.perf_counter() - start) * 1000

        logger.info(result.summary())
        self._try_record_metrics(result)
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_nodes": len(self._nodes),
            "total_synapses": len(self._synapses),
            "total_executions": self._total_executions,
            "execution_order": [
                self._nodes[nid].name for nid in self._execution_order
            ],
        }

    # ── Private ──

    def _rebuild_execution_order(self) -> None:
        """Topological sort to determine execution order."""
        # Find entry nodes (no incoming synapses)
        has_incoming = set()
        for syn in self._synapses.values():
            has_incoming.add(syn.target_id)

        self._entry_nodes = [
            nid for nid in self._nodes if nid not in has_incoming
        ]

        # BFS topological order
        visited = set()
        order = []
        queue = deque(self._entry_nodes)

        while queue:
            nid = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            order.append(nid)

            for syn_id in self._adjacency.get(nid, []):
                syn = self._synapses[syn_id]
                if syn.target_id not in visited:
                    queue.append(syn.target_id)

        self._execution_order = order

    def _try_record_metrics(self, result: ChainResult) -> None:
        try:
            from telemetry.metrics import MetricsCollector
            mc = MetricsCollector.get_instance()
            mc.histogram("brain.stc.duration_ms", result.total_duration_ms)
            mc.histogram("brain.stc.nodes", result.total_nodes)
        except Exception:
            pass
