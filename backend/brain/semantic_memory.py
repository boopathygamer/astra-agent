"""
Semantic Memory — Vector-Enhanced Knowledge System
═══════════════════════════════════════════════════
Upgrades the KnowledgeNexus with semantic similarity search
using lightweight vector embeddings, enabling meaning-based
retrieval instead of keyword matching.

Capabilities:
  1. Embedding Generation — Text → vector via LLM or hashing
  2. Similarity Search    — Find conceptually similar knowledge
  3. Auto-Clustering      — Group related concepts automatically
  4. Semantic Dedup       — Detect near-duplicate knowledge
  5. Context Retrieval    — Get most relevant context for a query
  6. Memory Consolidation — Merge similar memories over time
"""

import hashlib
import json
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A memory with text content and vector embedding."""
    memory_id: str = ""
    text: str = ""
    source: str = ""           # Where this memory came from
    category: str = "general"  # conversation, fact, procedure, etc.
    embedding: List[float] = field(default_factory=list)
    importance: float = 0.5    # 0-1, how important
    access_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.memory_id:
            self.memory_id = hashlib.md5(
                f"{self.text[:100]}_{self.created_at}".encode()
            ).hexdigest()[:12]


@dataclass
class SearchResult:
    """Result from a semantic search."""
    memory: MemoryEntry
    similarity: float = 0.0
    relevance_score: float = 0.0  # Combined score


@dataclass
class MemoryCluster:
    """A group of related memories."""
    cluster_id: str = ""
    label: str = ""
    memory_ids: List[str] = field(default_factory=list)
    centroid: List[float] = field(default_factory=list)
    coherence: float = 0.0


class SemanticMemory:
    """
    Vector-enhanced memory system with semantic similarity search,
    auto-clustering, deduplication, and context retrieval.
    """

    EMBEDDING_DIM = 128  # Lightweight hash-based embeddings
    MAX_MEMORIES = 10000
    SIMILARITY_THRESHOLD = 0.85  # For dedup detection
    CLUSTER_THRESHOLD = 0.7

    def __init__(self, generate_fn: Optional[Callable] = None,
                 data_dir: Optional[str] = None):
        self.generate_fn = generate_fn
        self.data_dir = Path(data_dir) if data_dir else Path("data/semantic_memory")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._memories: Dict[str, MemoryEntry] = {}
        self._clusters: List[MemoryCluster] = []
        self._category_index: Dict[str, List[str]] = defaultdict(list)

        self._load()
        logger.info(f"[SEMANTIC] Memory initialized: {len(self._memories)} memories")

    # ── Embedding Generation ──

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate a vector embedding for text.
        Uses a deterministic hash-based approach for speed.
        Can be upgraded to use actual LLM embeddings later.
        """
        # Character n-gram hashing for lightweight semantic embeddings
        embedding = [0.0] * self.EMBEDDING_DIM
        text_lower = text.lower()

        # Unigram features
        words = text_lower.split()
        for word in words:
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            idx = h % self.EMBEDDING_DIM
            embedding[idx] += 1.0

        # Bigram features
        for i in range(len(words) - 1):
            bigram = f"{words[i]}_{words[i+1]}"
            h = int(hashlib.sha256(bigram.encode()).hexdigest(), 16)
            idx = h % self.EMBEDDING_DIM
            embedding[idx] += 0.5

        # Character trigram features
        for i in range(len(text_lower) - 2):
            trigram = text_lower[i:i+3]
            h = int(hashlib.md5(trigram.encode()).hexdigest(), 16)
            idx = h % self.EMBEDDING_DIM
            embedding[idx] += 0.2

        # Normalize
        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    # ── Memory Operations ──

    def store(self, text: str, source: str = "user",
              category: str = "general", importance: float = 0.5,
              metadata: Dict = None) -> MemoryEntry:
        """Store a new memory with auto-embedding."""
        # Check for near-duplicates
        embedding = self._generate_embedding(text)
        duplicate = self._find_duplicate(embedding)
        if duplicate:
            duplicate.access_count += 1
            duplicate.importance = max(duplicate.importance, importance)
            duplicate.last_accessed = time.time()
            if metadata:
                duplicate.metadata.update(metadata)
            return duplicate

        # Evict old memories if at capacity
        if len(self._memories) >= self.MAX_MEMORIES:
            self._evict_least_important()

        entry = MemoryEntry(
            text=text, source=source, category=category,
            embedding=embedding, importance=importance,
            metadata=metadata or {},
        )
        self._memories[entry.memory_id] = entry
        self._category_index[category].append(entry.memory_id)
        return entry

    def search(self, query: str, top_k: int = 5,
               category: str = None, min_similarity: float = 0.1) -> List[SearchResult]:
        """Semantic search across all memories."""
        query_embedding = self._generate_embedding(query)

        results = []
        candidates = self._memories.values()
        if category:
            cat_ids = set(self._category_index.get(category, []))
            candidates = [m for m in candidates if m.memory_id in cat_ids]

        for memory in candidates:
            sim = self._cosine_similarity(query_embedding, memory.embedding)
            if sim < min_similarity:
                continue

            # Compute relevance score (similarity + importance + recency)
            recency = math.exp(-0.001 * (time.time() - memory.last_accessed) / 3600)
            relevance = sim * 0.6 + memory.importance * 0.25 + recency * 0.15

            results.append(SearchResult(
                memory=memory, similarity=sim, relevance_score=relevance,
            ))

        results.sort(key=lambda r: r.relevance_score, reverse=True)

        # Update access counts
        for r in results[:top_k]:
            r.memory.access_count += 1
            r.memory.last_accessed = time.time()

        return results[:top_k]

    def get_context(self, query: str, max_tokens: int = 2000,
                    category: str = None) -> str:
        """Get the most relevant memory context for a query."""
        results = self.search(query, top_k=10, category=category)
        context_parts = []
        token_estimate = 0

        for r in results:
            text = r.memory.text
            tokens = len(text.split())
            if token_estimate + tokens > max_tokens:
                break
            context_parts.append(
                f"[{r.memory.category}|sim={r.similarity:.2f}] {text}"
            )
            token_estimate += tokens

        return "\n".join(context_parts) if context_parts else ""

    # ── Deduplication ──

    def _find_duplicate(self, embedding: List[float]) -> Optional[MemoryEntry]:
        """Find a near-duplicate memory."""
        for memory in self._memories.values():
            sim = self._cosine_similarity(embedding, memory.embedding)
            if sim >= self.SIMILARITY_THRESHOLD:
                return memory
        return None

    def find_duplicates(self) -> List[Tuple[str, str, float]]:
        """Find all near-duplicate pairs in memory."""
        duplicates = []
        items = list(self._memories.values())
        for i, m1 in enumerate(items):
            for m2 in items[i+1:]:
                sim = self._cosine_similarity(m1.embedding, m2.embedding)
                if sim >= self.SIMILARITY_THRESHOLD:
                    duplicates.append((m1.memory_id, m2.memory_id, sim))
        return duplicates

    def consolidate(self) -> int:
        """Merge near-duplicate memories. Returns count of merged."""
        merged = 0
        dupes = self.find_duplicates()
        to_remove = set()

        for id1, id2, sim in dupes:
            if id1 in to_remove or id2 in to_remove:
                continue
            m1 = self._memories.get(id1)
            m2 = self._memories.get(id2)
            if not m1 or not m2:
                continue

            # Keep the more important one
            keep, remove = (m1, m2) if m1.importance >= m2.importance else (m2, m1)
            keep.importance = max(keep.importance, remove.importance)
            keep.access_count += remove.access_count
            if remove.text not in keep.text:
                keep.text += f" | {remove.text[:100]}"
            to_remove.add(remove.memory_id)
            merged += 1

        for mid in to_remove:
            self._memories.pop(mid, None)

        if merged:
            logger.info(f"[SEMANTIC] Consolidated {merged} duplicate memories")
        return merged

    # ── Clustering ──

    def cluster_memories(self, num_clusters: int = 10) -> List[MemoryCluster]:
        """Auto-cluster memories using simple k-means-like approach."""
        if len(self._memories) < num_clusters:
            return []

        items = list(self._memories.values())

        # Initialize centroids from equally-spaced memories
        step = max(1, len(items) // num_clusters)
        centroids = [items[i * step].embedding[:] for i in range(num_clusters)]

        # Run iterations
        clusters_map: Dict[int, List[str]] = defaultdict(list)
        for _ in range(5):  # 5 iterations
            clusters_map = defaultdict(list)
            for memory in items:
                if not memory.embedding:
                    continue
                best_cluster = 0
                best_sim = -1
                for ci, centroid in enumerate(centroids):
                    sim = self._cosine_similarity(memory.embedding, centroid)
                    if sim > best_sim:
                        best_sim = sim
                        best_cluster = ci
                clusters_map[best_cluster].append(memory.memory_id)

            # Update centroids
            for ci in range(num_clusters):
                if not clusters_map[ci]:
                    continue
                dim = self.EMBEDDING_DIM
                new_centroid = [0.0] * dim
                for mid in clusters_map[ci]:
                    m = self._memories.get(mid)
                    if m and m.embedding:
                        for d in range(dim):
                            new_centroid[d] += m.embedding[d]
                n = len(clusters_map[ci])
                centroids[ci] = [x / n for x in new_centroid]

        # Build cluster objects
        self._clusters = []
        for ci, member_ids in clusters_map.items():
            if not member_ids:
                continue
            # Label from most common words
            texts = [self._memories[mid].text for mid in member_ids if mid in self._memories]
            label = self._summarize_cluster(texts)
            cluster = MemoryCluster(
                cluster_id=f"cluster_{ci}",
                label=label,
                memory_ids=member_ids,
                centroid=centroids[ci],
            )
            self._clusters.append(cluster)

        return self._clusters

    def _summarize_cluster(self, texts: List[str]) -> str:
        """Generate a label for a cluster from its texts."""
        word_freq: Dict[str, int] = defaultdict(int)
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on",
                       "at", "to", "for", "of", "and", "or", "but", "with", "this", "that"}
        for text in texts:
            for word in text.lower().split():
                clean = word.strip(".,!?()[]{}\"'")
                if len(clean) > 2 and clean not in stop_words:
                    word_freq[clean] += 1
        top = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:3]
        return ", ".join(w for w, _ in top) if top else "misc"

    # ── Eviction ──

    def _evict_least_important(self, count: int = 100) -> None:
        """Evict least important memories to make room."""
        scored = [
            (mid, m.importance * 0.5 + (m.access_count / max(m.access_count, 1)) * 0.3 +
             math.exp(-0.01 * (time.time() - m.last_accessed) / 3600) * 0.2)
            for mid, m in self._memories.items()
        ]
        scored.sort(key=lambda x: x[1])
        for mid, _ in scored[:count]:
            self._memories.pop(mid, None)

    # ── Persistence ──

    def save(self) -> None:
        path = self.data_dir / "semantic_memory.json"
        try:
            data = {
                "memories": {
                    mid: {
                        "text": m.text, "source": m.source, "category": m.category,
                        "embedding": m.embedding[:20],  # Store compressed
                        "importance": m.importance, "access_count": m.access_count,
                        "created_at": m.created_at, "last_accessed": m.last_accessed,
                    }
                    for mid, m in self._memories.items()
                },
            }
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"[SEMANTIC] Save failed: {e}")

    def _load(self) -> None:
        path = self.data_dir / "semantic_memory.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for mid, md in data.get("memories", {}).items():
                entry = MemoryEntry(
                    text=md["text"], source=md.get("source", ""),
                    category=md.get("category", "general"),
                    importance=md.get("importance", 0.5),
                    access_count=md.get("access_count", 0),
                )
                entry.memory_id = mid
                entry.created_at = md.get("created_at", time.time())
                entry.last_accessed = md.get("last_accessed", time.time())
                entry.embedding = self._generate_embedding(entry.text)
                self._memories[mid] = entry
                self._category_index[entry.category].append(mid)
        except Exception as e:
            logger.warning(f"[SEMANTIC] Load failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_memories": len(self._memories),
            "categories": dict(
                (cat, len(ids)) for cat, ids in self._category_index.items()
            ),
            "clusters": len(self._clusters),
            "embedding_dim": self.EMBEDDING_DIM,
        }
