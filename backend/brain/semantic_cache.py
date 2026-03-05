"""
Semantic Response Cache — TF-IDF + Cosine Similarity Cache
═════════════════════════════════════════════════════════
Instead of exact-match caching, uses vector similarity to deduplicate
semantically identical or near-identical queries.

Features:
  - TF-IDF vectorization (no external dependencies)
  - Cosine similarity scoring
  - Configurable similarity threshold
  - TTL-based expiration
  - LRU eviction when max size exceeded
  - Hit/miss metrics via MetricsCollector
"""

import hashlib
import math
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CacheEntry:
    """A cached response with metadata."""
    query: str
    response: str
    tf_idf_vector: Dict[str, float]
    provider: str = ""
    confidence: float = 0.0
    created_at: float = field(default_factory=time.time)
    ttl_s: float = 3600.0  # 1 hour default
    hits: int = 0
    
    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_s


class SemanticCache:
    """
    Semantic response cache using TF-IDF + cosine similarity.
    """
    
    def __init__(
        self,
        max_entries: int = 1000,
        similarity_threshold: float = 0.85,
        default_ttl_s: float = 3600.0,
    ):
        self.max_entries = max_entries
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl_s
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._idf: Dict[str, float] = {}
        self._doc_count = 0
        
        # Stats
        self._hits = 0
        self._misses = 0
    
    def get(self, query: str) -> Optional[CacheEntry]:
        """
        Look up a query in the cache using semantic similarity.
        Returns the cached entry if a sufficiently similar query exists.
        """
        query_vec = self._compute_tf_idf(query)
        
        best_match: Optional[CacheEntry] = None
        best_score = 0.0
        expired_keys = []
        
        for key, entry in self._cache.items():
            if entry.is_expired:
                expired_keys.append(key)
                continue
            
            score = self._cosine_similarity(query_vec, entry.tf_idf_vector)
            if score > best_score:
                best_score = score
                best_match = entry
        
        # Clean expired
        for k in expired_keys:
            del self._cache[k]
        
        if best_match and best_score >= self.similarity_threshold:
            best_match.hits += 1
            self._hits += 1
            self._try_record_metric("brain.cache.hits")
            # Move to end (most recently used)
            key = hashlib.sha256(best_match.query.encode()).hexdigest()[:16]
            if key in self._cache:
                self._cache.move_to_end(key)
            return best_match
        
        self._misses += 1
        self._try_record_metric("brain.cache.misses")
        return None
    
    def put(self, query: str, response: str, provider: str = "", confidence: float = 0.0):
        """Store a response in the cache."""
        # Evict LRU if at capacity
        while len(self._cache) >= self.max_entries:
            self._cache.popitem(last=False)
        
        vec = self._compute_tf_idf(query)
        key = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        self._cache[key] = CacheEntry(
            query=query,
            response=response,
            tf_idf_vector=vec,
            provider=provider,
            confidence=confidence,
            ttl_s=self.default_ttl,
        )
        self._update_idf(query)
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace + lowercased tokenizer."""
        import re
        return re.findall(r'\b\w+\b', text.lower())
    
    def _compute_tf_idf(self, text: str) -> Dict[str, float]:
        """Compute TF-IDF vector for a text."""
        tokens = self._tokenize(text)
        if not tokens:
            return {}
        
        tf = Counter(tokens)
        total = len(tokens)
        
        vector = {}
        for term, count in tf.items():
            tf_val = count / total
            idf_val = self._idf.get(term, math.log(max(self._doc_count, 1) + 1))
            vector[term] = tf_val * idf_val
        
        return vector
    
    def _update_idf(self, text: str):
        """Update IDF scores with a new document."""
        self._doc_count += 1
        unique_terms = set(self._tokenize(text))
        for term in unique_terms:
            doc_freq = sum(1 for e in self._cache.values() if term in e.tf_idf_vector)
            self._idf[term] = math.log((self._doc_count + 1) / (doc_freq + 1)) + 1
    
    def _cosine_similarity(self, vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        """Compute cosine similarity between two sparse vectors."""
        if not vec_a or not vec_b:
            return 0.0
        
        common = set(vec_a.keys()) & set(vec_b.keys())
        if not common:
            return 0.0
        
        dot = sum(vec_a[k] * vec_b[k] for k in common)
        norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def _try_record_metric(self, name: str):
        try:
            from telemetry.metrics import MetricsCollector
            MetricsCollector.get_instance().counter(name)
        except Exception:
            pass
    
    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 3),
            "idf_terms": len(self._idf),
        }
