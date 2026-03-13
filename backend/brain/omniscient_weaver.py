"""
Omniscient Context Weaver — Cross-System Knowledge Fusion
═════════════════════════════════════════════════════════
A meta-layer that weaves context from ALL sources — memory, tools,
agents, external APIs, user history — into a single unified knowledge
graph that any module can query in O(1).

Architecture:
  Memory + Tools + Agents + APIs + History → Knowledge Fabric
                                                  ↓
                                          Context Beam (O(1) query)
                                                  ↓
                                          Source Fusion (conflict resolver)
"""

import hashlib
import logging
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class KnowledgeSource(Enum):
    MEMORY = "memory"
    TOOL = "tool"
    AGENT = "agent"
    API = "api"
    USER_HISTORY = "user_history"
    INFERENCE = "inference"
    EXTERNAL = "external"


class ConflictResolution(Enum):
    MOST_RECENT = "most_recent"
    HIGHEST_CONFIDENCE = "highest_confidence"
    SOURCE_PRIORITY = "source_priority"
    MAJORITY_VOTE = "majority_vote"


@dataclass
class KnowledgeNode:
    """A single knowledge fragment in the fabric."""
    node_id: str = ""
    key: str = ""
    value: Any = None
    source: KnowledgeSource = KnowledgeSource.MEMORY
    confidence: float = 0.5
    tags: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    ttl_s: float = 0.0            # 0 = no expiry

    def __post_init__(self):
        if not self.node_id:
            self.node_id = secrets.token_hex(4)

    @property
    def is_expired(self) -> bool:
        if self.ttl_s <= 0:
            return False
        return (time.time() - self.updated_at) > self.ttl_s


@dataclass
class BeamResult:
    """Result of a context beam query."""
    query: str = ""
    nodes: List[KnowledgeNode] = field(default_factory=list)
    total_found: int = 0
    sources_queried: int = 0
    conflicts_resolved: int = 0
    query_time_ms: float = 0.0

    @property
    def best(self) -> Optional[Any]:
        if self.nodes:
            return self.nodes[0].value
        return None


class KnowledgeFabric:
    """
    Unified knowledge graph fusing all information sources.

    Usage:
        fabric = KnowledgeFabric()

        # Weave knowledge from various sources
        fabric.weave("python_version", "3.12", source=KnowledgeSource.API)
        fabric.weave("user_preference", "dark_mode", source=KnowledgeSource.USER_HISTORY)
        fabric.weave("db_schema", {...}, source=KnowledgeSource.TOOL, tags={"database"})

        # Query with context beam
        result = fabric.beam("python_version")
        print(result.best)  # "3.12"

        # Tag-based search
        results = fabric.beam_by_tags({"database"})
    """

    SOURCE_PRIORITY = {
        KnowledgeSource.USER_HISTORY: 10,
        KnowledgeSource.API: 8,
        KnowledgeSource.TOOL: 7,
        KnowledgeSource.AGENT: 6,
        KnowledgeSource.MEMORY: 5,
        KnowledgeSource.INFERENCE: 4,
        KnowledgeSource.EXTERNAL: 3,
    }

    def __init__(self, conflict_strategy: ConflictResolution = ConflictResolution.HIGHEST_CONFIDENCE):
        self._nodes: Dict[str, List[KnowledgeNode]] = defaultdict(list)
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)
        self._conflict_strategy = conflict_strategy
        self._total_weaves: int = 0
        self._total_beams: int = 0
        self._conflicts_resolved: int = 0

    def weave(
        self,
        key: str,
        value: Any,
        source: KnowledgeSource = KnowledgeSource.MEMORY,
        confidence: float = 0.5,
        tags: Optional[Set[str]] = None,
        ttl_s: float = 0.0,
    ) -> str:
        """Weave a knowledge fragment into the fabric."""
        self._total_weaves += 1
        node = KnowledgeNode(
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            tags=tags or set(),
            ttl_s=ttl_s,
        )

        self._nodes[key].append(node)

        # Update tag index
        for tag in node.tags:
            self._tag_index[tag].add(key)

        return node.node_id

    def beam(self, key: str) -> BeamResult:
        """O(1) lookup of a knowledge key, with conflict resolution."""
        start = time.perf_counter()
        self._total_beams += 1

        candidates = self._nodes.get(key, [])
        # Filter expired
        valid = [n for n in candidates if not n.is_expired]

        if not valid:
            return BeamResult(
                query=key,
                query_time_ms=(time.perf_counter() - start) * 1000,
            )

        # Resolve conflicts if multiple values
        conflicts = 0
        if len(valid) > 1:
            valid = self._resolve_conflicts(valid)
            conflicts = 1
            self._conflicts_resolved += 1

        # Update access counts
        for node in valid:
            node.access_count += 1

        return BeamResult(
            query=key,
            nodes=valid,
            total_found=len(valid),
            sources_queried=len(set(n.source for n in valid)),
            conflicts_resolved=conflicts,
            query_time_ms=(time.perf_counter() - start) * 1000,
        )

    def beam_by_tags(self, tags: Set[str], match_all: bool = False) -> BeamResult:
        """Query nodes by tags."""
        start = time.perf_counter()
        self._total_beams += 1

        matching_keys: Set[str] = set()
        for tag in tags:
            keys = self._tag_index.get(tag, set())
            if match_all:
                matching_keys = matching_keys & keys if matching_keys else keys
            else:
                matching_keys |= keys

        results = []
        for key in matching_keys:
            for node in self._nodes.get(key, []):
                if not node.is_expired:
                    results.append(node)
                    node.access_count += 1

        results.sort(key=lambda n: n.confidence, reverse=True)

        return BeamResult(
            query=str(tags),
            nodes=results,
            total_found=len(results),
            query_time_ms=(time.perf_counter() - start) * 1000,
        )

    def forget(self, key: str) -> int:
        """Remove all nodes for a key."""
        removed = len(self._nodes.get(key, []))
        self._nodes.pop(key, None)
        # Clean tag index
        for tag_keys in self._tag_index.values():
            tag_keys.discard(key)
        return removed

    def gc(self) -> int:
        """Garbage collect expired nodes."""
        removed = 0
        for key in list(self._nodes.keys()):
            before = len(self._nodes[key])
            self._nodes[key] = [n for n in self._nodes[key] if not n.is_expired]
            removed += before - len(self._nodes[key])
            if not self._nodes[key]:
                del self._nodes[key]
        return removed

    def get_stats(self) -> Dict[str, Any]:
        total_nodes = sum(len(v) for v in self._nodes.values())
        sources: Dict[str, int] = defaultdict(int)
        for nodes in self._nodes.values():
            for n in nodes:
                sources[n.source.value] += 1
        return {
            "total_keys": len(self._nodes),
            "total_nodes": total_nodes,
            "total_tags": len(self._tag_index),
            "total_weaves": self._total_weaves,
            "total_beams": self._total_beams,
            "conflicts_resolved": self._conflicts_resolved,
            "sources": dict(sources),
        }

    def _resolve_conflicts(self, nodes: List[KnowledgeNode]) -> List[KnowledgeNode]:
        """Resolve conflicting values for the same key."""
        if self._conflict_strategy == ConflictResolution.MOST_RECENT:
            nodes.sort(key=lambda n: n.updated_at, reverse=True)
        elif self._conflict_strategy == ConflictResolution.HIGHEST_CONFIDENCE:
            nodes.sort(key=lambda n: n.confidence, reverse=True)
        elif self._conflict_strategy == ConflictResolution.SOURCE_PRIORITY:
            nodes.sort(
                key=lambda n: self.SOURCE_PRIORITY.get(n.source, 0),
                reverse=True,
            )
        return nodes
