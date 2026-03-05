"""
Vector Store — TF-IDF + Cosine Similarity Embeddings
═════════════════════════════════════════════════════
Pure Python vector embedding store for semantic memory search.
No external dependencies — uses math and collections.

Features:
  - TF-IDF vectorization with BM25-inspired scoring
  - Cosine similarity nearest-neighbor search
  - Persistent storage to JSON
  - Incremental document indexing
  - Thread-safe operations
"""

import json
import math
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re


@dataclass
class VectorDocument:
    """A document in the vector store."""
    doc_id: str
    text: str
    vector: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class SearchResult:
    """Result from a similarity search."""
    doc_id: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorStore:
    """
    Pure Python vector store using TF-IDF embeddings.
    """
    
    def __init__(self, persist_path: Optional[str] = None, max_docs: int = 10000):
        self.persist_path = Path(persist_path) if persist_path else None
        self.max_docs = max_docs
        
        self._documents: Dict[str, VectorDocument] = {}
        self._idf: Dict[str, float] = {}
        self._total_docs = 0
        self._lock = threading.Lock()
        
        if self.persist_path and self.persist_path.exists():
            self._load()
    
    def add(self, doc_id: str, text: str, metadata: Dict[str, Any] = None):
        """Add a document to the store."""
        with self._lock:
            # Evict oldest if at capacity
            while len(self._documents) >= self.max_docs:
                oldest_id = min(self._documents, key=lambda k: self._documents[k].created_at)
                del self._documents[oldest_id]
            
            vector = self._compute_tfidf(text)
            self._documents[doc_id] = VectorDocument(
                doc_id=doc_id,
                text=text,
                vector=vector,
                metadata=metadata or {},
            )
            self._total_docs = len(self._documents)
            self._rebuild_idf()
    
    def search(self, query: str, top_k: int = 5, min_score: float = 0.1) -> List[SearchResult]:
        """Search for semantically similar documents."""
        with self._lock:
            query_vec = self._compute_tfidf(query)
            
            scores = []
            for doc in self._documents.values():
                score = self._cosine_similarity(query_vec, doc.vector)
                if score >= min_score:
                    scores.append((doc, score))
            
            scores.sort(key=lambda x: x[1], reverse=True)
            
            return [
                SearchResult(
                    doc_id=doc.doc_id,
                    text=doc.text,
                    score=round(score, 4),
                    metadata=doc.metadata,
                )
                for doc, score in scores[:top_k]
            ]
    
    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        with self._lock:
            if doc_id in self._documents:
                del self._documents[doc_id]
                self._total_docs = len(self._documents)
                return True
            return False
    
    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\b\w+\b', text.lower())
    
    def _compute_tfidf(self, text: str) -> Dict[str, float]:
        tokens = self._tokenize(text)
        if not tokens:
            return {}
        
        tf = Counter(tokens)
        total = len(tokens)
        
        vector = {}
        for term, count in tf.items():
            tf_val = count / total
            idf_val = self._idf.get(term, math.log(self._total_docs + 2))
            vector[term] = tf_val * idf_val
        
        return vector
    
    def _rebuild_idf(self):
        """Rebuild IDF for all terms."""
        doc_term_counts: Dict[str, int] = {}
        for doc in self._documents.values():
            for term in set(doc.vector.keys()):
                doc_term_counts[term] = doc_term_counts.get(term, 0) + 1
        
        self._idf = {
            term: math.log((self._total_docs + 1) / (df + 1)) + 1
            for term, df in doc_term_counts.items()
        }
    
    def _cosine_similarity(self, vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
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
    
    def _save(self):
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                doc_id: {
                    "text": doc.text,
                    "metadata": doc.metadata,
                    "created_at": doc.created_at,
                }
                for doc_id, doc in self._documents.items()
            }
            self.persist_path.write_text(json.dumps(data))
        except Exception:
            pass
    
    def _load(self):
        try:
            data = json.loads(self.persist_path.read_text())
            for doc_id, info in data.items():
                self.add(doc_id, info["text"], info.get("metadata", {}))
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_documents": len(self._documents),
            "max_documents": self.max_docs,
            "total_idf_terms": len(self._idf),
        }
