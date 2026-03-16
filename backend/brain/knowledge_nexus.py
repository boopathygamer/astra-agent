"""
Knowledge Nexus — Self-Growing Knowledge Graph
═══════════════════════════════════════════════
A persistent knowledge system that grows over time, connecting
facts, concepts, and experiences into a queryable graph.

Capabilities:
  1. Entity-Relationship Graph  — Nodes with typed edges
  2. Cross-Domain Synthesis     — Finds hidden connections
  3. Fact Confidence System     — Confidence + source tracking
  4. Query Engine               — Natural language search
  5. Auto-Learning              — Extracts knowledge from conversations
  6. Knowledge Decay            — Old unverified facts lose confidence
"""

import hashlib
import json
import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class NodeType(Enum):
    CONCEPT = "concept"
    FACT = "fact"
    ENTITY = "entity"
    PROCEDURE = "procedure"
    EXPERIENCE = "experience"
    PREFERENCE = "preference"
    SKILL = "skill"


class EdgeType(Enum):
    RELATES_TO = "relates_to"
    IS_A = "is_a"
    PART_OF = "part_of"
    CAUSES = "causes"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    DEPENDS_ON = "depends_on"
    LEARNED_FROM = "learned_from"
    PRECEDES = "precedes"
    SIMILAR_TO = "similar_to"


@dataclass
class KnowledgeNode:
    node_id: str = ""
    node_type: NodeType = NodeType.FACT
    label: str = ""
    content: str = ""
    confidence: float = 0.8
    sources: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_verified: float = field(default_factory=time.time)
    access_count: int = 0
    domain: str = ""

    def __post_init__(self):
        if not self.node_id:
            self.node_id = hashlib.md5(
                f"{self.label}_{self.created_at}".encode()
            ).hexdigest()[:12]

    def decayed_confidence(self, decay_rate: float = 0.01) -> float:
        days_since_verify = (time.time() - self.last_verified) / 86400
        decay = math.exp(-decay_rate * days_since_verify)
        return self.confidence * decay


@dataclass
class KnowledgeEdge:
    source_id: str = ""
    target_id: str = ""
    edge_type: EdgeType = EdgeType.RELATES_TO
    weight: float = 1.0
    label: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class QueryResult:
    nodes: List[KnowledgeNode] = field(default_factory=list)
    edges: List[KnowledgeEdge] = field(default_factory=list)
    relevance_scores: Dict[str, float] = field(default_factory=dict)
    synthesis: str = ""


class KnowledgeNexus:
    """
    Self-growing knowledge graph with entity-relationship storage,
    cross-domain synthesis, confidence decay, and natural language queries.
    """

    MAX_NODES = 10000
    DECAY_RATE = 0.005  # per day
    MIN_CONFIDENCE = 0.1

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path("data/knowledge")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._nodes: Dict[str, KnowledgeNode] = {}
        self._edges: List[KnowledgeEdge] = []
        self._adjacency: Dict[str, List[str]] = defaultdict(list)
        self._reverse_adj: Dict[str, List[str]] = defaultdict(list)
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)
        self._domain_index: Dict[str, Set[str]] = defaultdict(set)
        self._label_index: Dict[str, str] = {}  # lowered label -> node_id

        self._load()
        logger.info(f"[KNOWLEDGE] Nexus initialized: {len(self._nodes)} nodes, "
                    f"{len(self._edges)} edges")

    # ── Node Operations ──

    def add_node(self, label: str, content: str = "",
                 node_type: NodeType = NodeType.FACT,
                 confidence: float = 0.8, sources: List[str] = None,
                 tags: List[str] = None, domain: str = "") -> KnowledgeNode:
        # Check for existing node with same label
        existing_id = self._label_index.get(label.lower())
        if existing_id and existing_id in self._nodes:
            existing = self._nodes[existing_id]
            existing.confidence = max(existing.confidence, confidence)
            existing.access_count += 1
            existing.last_verified = time.time()
            if content and content not in existing.content:
                existing.content += f" | {content}"
            if sources:
                existing.sources.extend(s for s in sources if s not in existing.sources)
            return existing

        node = KnowledgeNode(
            node_type=node_type, label=label, content=content,
            confidence=confidence, sources=sources or [],
            tags=tags or [], domain=domain,
        )
        self._nodes[node.node_id] = node
        self._label_index[label.lower()] = node.node_id
        for tag in node.tags:
            self._tag_index[tag.lower()].add(node.node_id)
        if domain:
            self._domain_index[domain.lower()].add(node.node_id)
        return node

    def add_edge(self, source_label: str, target_label: str,
                 edge_type: EdgeType = EdgeType.RELATES_TO,
                 weight: float = 1.0, label: str = "") -> Optional[KnowledgeEdge]:
        src_id = self._label_index.get(source_label.lower())
        tgt_id = self._label_index.get(target_label.lower())
        if not src_id or not tgt_id:
            return None

        edge = KnowledgeEdge(
            source_id=src_id, target_id=tgt_id,
            edge_type=edge_type, weight=weight, label=label,
        )
        self._edges.append(edge)
        self._adjacency[src_id].append(tgt_id)
        self._reverse_adj[tgt_id].append(src_id)
        return edge

    # ── Query Engine ──

    def query(self, search_text: str, max_results: int = 10,
              min_confidence: float = 0.2) -> QueryResult:
        """Natural-language search across the knowledge graph."""
        terms = search_text.lower().split()
        scores: Dict[str, float] = defaultdict(float)

        for node_id, node in self._nodes.items():
            conf = node.decayed_confidence(self.DECAY_RATE)
            if conf < min_confidence:
                continue

            # Label match
            label_l = node.label.lower()
            for term in terms:
                if term in label_l:
                    scores[node_id] += 3.0 * conf
                if term in node.content.lower():
                    scores[node_id] += 1.5 * conf
                if term in [t.lower() for t in node.tags]:
                    scores[node_id] += 2.0 * conf
                if term == node.domain.lower():
                    scores[node_id] += 1.0 * conf

        # Sort by score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:max_results]

        result_nodes = []
        result_edges = []
        for node_id, score in ranked:
            node = self._nodes[node_id]
            node.access_count += 1
            result_nodes.append(node)

            # Include connected edges
            for edge in self._edges:
                if edge.source_id == node_id or edge.target_id == node_id:
                    other_id = edge.target_id if edge.source_id == node_id else edge.source_id
                    if other_id in self._nodes:
                        result_edges.append(edge)

        return QueryResult(
            nodes=result_nodes,
            edges=result_edges[:20],
            relevance_scores={nid: s for nid, s in ranked},
        )

    def get_related(self, label: str, depth: int = 2) -> List[KnowledgeNode]:
        """Get nodes related to a given label, up to N hops."""
        node_id = self._label_index.get(label.lower())
        if not node_id:
            return []

        visited: Set[str] = set()
        queue = [(node_id, 0)]
        related = []

        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)
            if current != node_id and current in self._nodes:
                related.append(self._nodes[current])

            for neighbor in self._adjacency.get(current, []):
                if neighbor not in visited:
                    queue.append((neighbor, d + 1))
            for neighbor in self._reverse_adj.get(current, []):
                if neighbor not in visited:
                    queue.append((neighbor, d + 1))

        return related

    # ── Cross-Domain Synthesis ──

    def find_cross_domain_links(self) -> List[Dict[str, Any]]:
        """Find surprising connections between different domains."""
        links = []
        domains = list(self._domain_index.keys())

        for i, d1 in enumerate(domains):
            for d2 in domains[i+1:]:
                nodes1 = self._domain_index[d1]
                nodes2 = self._domain_index[d2]

                # Check for edges between domains
                for edge in self._edges:
                    if ((edge.source_id in nodes1 and edge.target_id in nodes2) or
                            (edge.source_id in nodes2 and edge.target_id in nodes1)):
                        src = self._nodes.get(edge.source_id)
                        tgt = self._nodes.get(edge.target_id)
                        if src and tgt:
                            links.append({
                                "domain_a": d1,
                                "domain_b": d2,
                                "connection": f"{src.label} → {tgt.label}",
                                "edge_type": edge.edge_type.value,
                                "weight": edge.weight,
                            })

                # Check for shared tags
                tags1 = set()
                tags2 = set()
                for nid in nodes1:
                    if nid in self._nodes:
                        tags1.update(t.lower() for t in self._nodes[nid].tags)
                for nid in nodes2:
                    if nid in self._nodes:
                        tags2.update(t.lower() for t in self._nodes[nid].tags)

                shared = tags1 & tags2
                if shared:
                    links.append({
                        "domain_a": d1,
                        "domain_b": d2,
                        "connection": f"Shared concepts: {', '.join(list(shared)[:5])}",
                        "edge_type": "shared_tags",
                        "weight": len(shared) * 0.5,
                    })

        return links

    # ── Auto-Learning ──

    def learn_from_conversation(self, user_msg: str, assistant_msg: str,
                                 topic: str = "") -> List[KnowledgeNode]:
        """Extract and store knowledge from a conversation turn."""
        learned = []

        # Extract key phrases (simple heuristic — words >4 characters, capitalized)
        words = user_msg.split() + assistant_msg.split()
        key_terms = set()
        for w in words:
            clean = w.strip(".,!?()[]{}\"'")
            if len(clean) > 4 and clean[0].isupper():
                key_terms.add(clean)

        # Store facts from conversation
        if key_terms:
            domain = topic or "conversation"
            for term in list(key_terms)[:5]:
                node = self.add_node(
                    label=term,
                    content=f"Discussed in context: {user_msg[:100]}",
                    node_type=NodeType.CONCEPT,
                    confidence=0.5,
                    sources=["conversation"],
                    tags=["auto_learned"],
                    domain=domain,
                )
                learned.append(node)

            # Create edges between co-occurring terms
            term_list = list(key_terms)[:5]
            for i, t1 in enumerate(term_list):
                for t2 in term_list[i+1:]:
                    self.add_edge(t1, t2, EdgeType.RELATES_TO, weight=0.5)

        return learned

    # ── Knowledge Decay ──

    def apply_decay(self) -> int:
        """Apply confidence decay to all nodes. Returns count of pruned nodes."""
        pruned = 0
        to_remove = []

        for node_id, node in self._nodes.items():
            new_conf = node.decayed_confidence(self.DECAY_RATE)
            if new_conf < self.MIN_CONFIDENCE and node.access_count < 3:
                to_remove.append(node_id)
                pruned += 1

        for nid in to_remove:
            node = self._nodes.pop(nid, None)
            if node:
                self._label_index.pop(node.label.lower(), None)
                for tag in node.tags:
                    self._tag_index.get(tag.lower(), set()).discard(nid)
                if node.domain:
                    self._domain_index.get(node.domain.lower(), set()).discard(nid)

        self._edges = [
            e for e in self._edges
            if e.source_id in self._nodes and e.target_id in self._nodes
        ]

        if pruned:
            logger.info(f"[KNOWLEDGE] Decay pruned {pruned} low-confidence nodes")
        return pruned

    def verify_fact(self, label: str) -> bool:
        """Mark a fact as recently verified, resetting decay."""
        node_id = self._label_index.get(label.lower())
        if not node_id or node_id not in self._nodes:
            return False
        self._nodes[node_id].last_verified = time.time()
        self._nodes[node_id].confidence = min(1.0, self._nodes[node_id].confidence + 0.1)
        return True

    # ── Status & Persistence ──

    def get_stats(self) -> Dict[str, Any]:
        domains = list(self._domain_index.keys())
        avg_conf = (
            sum(n.decayed_confidence(self.DECAY_RATE) for n in self._nodes.values())
            / max(len(self._nodes), 1)
        )
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "domains": domains,
            "domain_count": len(domains),
            "avg_confidence": round(avg_conf, 3),
            "node_types": dict(defaultdict(int, {
                nt.value: sum(1 for n in self._nodes.values() if n.node_type == nt)
                for nt in NodeType
            })),
        }

    def get_status(self) -> Dict[str, Any]:
        return self.get_stats()

    def save(self) -> None:
        path = self.data_dir / "knowledge_graph.json"
        try:
            data = {
                "nodes": {
                    nid: {
                        "type": n.node_type.value, "label": n.label,
                        "content": n.content, "confidence": n.confidence,
                        "sources": n.sources, "tags": n.tags,
                        "created_at": n.created_at, "last_verified": n.last_verified,
                        "access_count": n.access_count, "domain": n.domain,
                    }
                    for nid, n in self._nodes.items()
                },
                "edges": [
                    {
                        "source": e.source_id, "target": e.target_id,
                        "type": e.edge_type.value, "weight": e.weight,
                        "label": e.label,
                    }
                    for e in self._edges
                ],
            }
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"[KNOWLEDGE] Save failed: {e}")

    def _load(self) -> None:
        path = self.data_dir / "knowledge_graph.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            type_map = {t.value: t for t in NodeType}
            edge_type_map = {t.value: t for t in EdgeType}

            for nid, nd in data.get("nodes", {}).items():
                node = KnowledgeNode(
                    node_type=type_map.get(nd["type"], NodeType.FACT),
                    label=nd["label"], content=nd.get("content", ""),
                    confidence=nd.get("confidence", 0.5),
                    sources=nd.get("sources", []),
                    tags=nd.get("tags", []),
                    domain=nd.get("domain", ""),
                )
                node.node_id = nid
                node.created_at = nd.get("created_at", time.time())
                node.last_verified = nd.get("last_verified", time.time())
                node.access_count = nd.get("access_count", 0)
                self._nodes[nid] = node
                self._label_index[node.label.lower()] = nid
                for tag in node.tags:
                    self._tag_index[tag.lower()].add(nid)
                if node.domain:
                    self._domain_index[node.domain.lower()].add(nid)

            for ed in data.get("edges", []):
                edge = KnowledgeEdge(
                    source_id=ed["source"], target_id=ed["target"],
                    edge_type=edge_type_map.get(ed.get("type", ""), EdgeType.RELATES_TO),
                    weight=ed.get("weight", 1.0), label=ed.get("label", ""),
                )
                self._edges.append(edge)
                self._adjacency[edge.source_id].append(edge.target_id)
                self._reverse_adj[edge.target_id].append(edge.source_id)

            logger.info(f"[KNOWLEDGE] Loaded {len(self._nodes)} nodes, {len(self._edges)} edges")
        except Exception as e:
            logger.warning(f"[KNOWLEDGE] Load failed: {e}")
