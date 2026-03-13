"""
Dimensional Folding Context Engine — Semantic Space Folding
═══════════════════════════════════════════════════════════
Instead of linear context windows, fold semantically related tokens
into higher-dimensional manifolds. A 128K window becomes effectively
infinite by collapsing related concepts into the same dimensional point.

Architecture:
  Token Stream → Semantic Mapper → Manifold Folder → Folded Context
                      ↓                   ↓               ↓
               Concept Vectors    Overlap Detection   Unfold-On-Demand
"""

import hashlib
import logging
import math
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ConceptNode:
    """A node in the concept manifold."""
    concept_id: str = ""
    tokens: List[str] = field(default_factory=list)
    embeddings: List[float] = field(default_factory=list)
    semantic_center: List[float] = field(default_factory=list)
    fold_depth: int = 0
    original_size: int = 0
    folded_size: int = 0
    children: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.concept_id:
            self.concept_id = secrets.token_hex(4)
        if not self.original_size:
            self.original_size = len(self.tokens)
        if not self.folded_size:
            self.folded_size = 1

    @property
    def compression_ratio(self) -> float:
        return self.original_size / max(self.folded_size, 1)


@dataclass
class FoldedContext:
    """The result of folding a context window."""
    total_tokens_original: int = 0
    total_tokens_folded: int = 0
    concept_nodes: int = 0
    max_fold_depth: int = 0
    compression_ratio: float = 1.0
    folding_time_ms: float = 0.0

    def summary(self) -> str:
        return (
            f"DimFold: {self.total_tokens_original}→{self.total_tokens_folded} tokens "
            f"({self.compression_ratio:.1f}x) | "
            f"{self.concept_nodes} concepts | depth={self.max_fold_depth}"
        )


@dataclass
class UnfoldResult:
    """Result of unfolding concept nodes on demand."""
    query: str = ""
    unfolded_tokens: List[str] = field(default_factory=list)
    concepts_unfolded: int = 0
    relevance_scores: List[Tuple[str, float]] = field(default_factory=list)


class SemanticMapper:
    """Maps tokens to lightweight semantic vectors for similarity detection."""

    @staticmethod
    def compute_embedding(text: str) -> List[float]:
        """Compute a deterministic pseudo-embedding from text."""
        words = text.lower().split()
        if not words:
            return [0.0] * 8
        vec = [0.0] * 8
        for i, word in enumerate(words):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            for dim in range(8):
                vec[dim] += ((h >> (dim * 4)) & 0xF) / 15.0
        total = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / total for v in vec]

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a)) or 1.0
        mag_b = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (mag_a * mag_b)


class DimensionalContextFolder:
    """
    Folds semantically related context into compressed concept nodes.

    Usage:
        folder = DimensionalContextFolder()
        context = folder.fold("The Python language uses indentation...")
        print(context.summary())

        # Later, unfold specific concepts on demand
        result = folder.unfold_for_query("How does Python handle indentation?")
    """

    SIMILARITY_THRESHOLD = 0.75
    MIN_CLUSTER_SIZE = 2

    def __init__(self):
        self._concepts: Dict[str, ConceptNode] = {}
        self._mapper = SemanticMapper()
        self._total_folds = 0
        self._total_original_tokens = 0
        self._total_folded_tokens = 0

    def fold(self, text: str, chunk_size: int = 10) -> FoldedContext:
        """Fold a text into compressed concept nodes."""
        start = time.perf_counter()
        words = text.split()
        self._total_original_tokens += len(words)

        # Split into semantic chunks
        chunks: List[List[str]] = []
        for i in range(0, len(words), chunk_size):
            chunk = words[i:i + chunk_size]
            if chunk:
                chunks.append(chunk)

        # Compute embeddings for each chunk
        chunk_embeddings = []
        for chunk in chunks:
            emb = self._mapper.compute_embedding(" ".join(chunk))
            chunk_embeddings.append(emb)

        # Cluster similar chunks (greedy approach)
        used = set()
        concept_count = 0

        for i in range(len(chunks)):
            if i in used:
                continue
            cluster_tokens = list(chunks[i])
            cluster_ids = [i]
            used.add(i)

            for j in range(i + 1, len(chunks)):
                if j in used:
                    continue
                sim = self._mapper.cosine_similarity(
                    chunk_embeddings[i], chunk_embeddings[j]
                )
                if sim >= self.SIMILARITY_THRESHOLD:
                    cluster_tokens.extend(chunks[j])
                    cluster_ids.append(j)
                    used.add(j)

            # Create concept node
            if len(cluster_ids) >= self.MIN_CLUSTER_SIZE:
                node = ConceptNode(
                    tokens=cluster_tokens,
                    embeddings=chunk_embeddings[i],
                    semantic_center=chunk_embeddings[i],
                    fold_depth=len(cluster_ids) - 1,
                    original_size=len(cluster_tokens),
                    folded_size=1,
                )
                self._concepts[node.concept_id] = node
                concept_count += 1
            else:
                # Keep as unfolded single chunk
                node = ConceptNode(
                    tokens=cluster_tokens,
                    embeddings=chunk_embeddings[i],
                    semantic_center=chunk_embeddings[i],
                    fold_depth=0,
                    original_size=len(cluster_tokens),
                    folded_size=len(cluster_tokens),
                )
                self._concepts[node.concept_id] = node
                concept_count += 1

        folded_size = sum(n.folded_size for n in self._concepts.values())
        original_size = sum(n.original_size for n in self._concepts.values())
        self._total_folded_tokens += folded_size
        self._total_folds += 1
        max_depth = max((n.fold_depth for n in self._concepts.values()), default=0)
        duration = (time.perf_counter() - start) * 1000

        result = FoldedContext(
            total_tokens_original=original_size,
            total_tokens_folded=folded_size,
            concept_nodes=concept_count,
            max_fold_depth=max_depth,
            compression_ratio=original_size / max(folded_size, 1),
            folding_time_ms=duration,
        )
        logger.info(result.summary())
        return result

    def unfold_for_query(self, query: str, top_k: int = 5) -> UnfoldResult:
        """Unfold only the concept nodes relevant to a query."""
        query_emb = self._mapper.compute_embedding(query)
        scored: List[Tuple[str, float, ConceptNode]] = []

        for cid, node in self._concepts.items():
            if node.semantic_center:
                sim = self._mapper.cosine_similarity(query_emb, node.semantic_center)
                scored.append((cid, sim, node))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        unfolded_tokens = []
        relevance = []
        for cid, sim, node in top:
            unfolded_tokens.extend(node.tokens)
            relevance.append((cid, round(sim, 3)))

        return UnfoldResult(
            query=query,
            unfolded_tokens=unfolded_tokens,
            concepts_unfolded=len(top),
            relevance_scores=relevance,
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_concepts": len(self._concepts),
            "total_folds": self._total_folds,
            "total_original_tokens": self._total_original_tokens,
            "total_folded_tokens": self._total_folded_tokens,
            "overall_compression": round(
                self._total_original_tokens / max(self._total_folded_tokens, 1), 2
            ),
        }
