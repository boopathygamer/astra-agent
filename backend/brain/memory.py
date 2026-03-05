"""
Memory Manager — Bug Diary & Learning From Mistakes
────────────────────────────────────────────────────
Section 6 of the architecture: Store each failure as a tuple
    z = (x, s, a, o, root_cause, fix, new_test)

Three usage modes:
  1. Regression: always rerun new_test in future tasks
  2. Retrieval: when a new task arrives, retrieve similar z
  3. Policy improvement: track recurring mistakes with exponentially
     decayed counter w_k ← γ·w_k + 1
"""

import json
import logging
import math
import re
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import brain_config, MEMORY_DIR
from brain.expert_reflection import ExpertPrinciple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# BM25 Index for Keyword Search
# ──────────────────────────────────────────────

class BM25Index:
    """
    BM25 keyword search index.
    Used alongside ChromaDB vector search for hybrid ranking:
        score = 0.7 * vector_score + 0.3 * bm25_score
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._documents: Dict[str, str] = {}  # id -> text
        self._doc_lengths: Dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._df: Counter = Counter()  # Document frequency per term
        self._doc_tf: Dict[str, Counter] = {}  # Term frequency per doc

    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace + punctuation tokenizer."""
        return re.findall(r'\w+', text.lower())

    def add(self, doc_id: str, text: str):
        """Add a document to the index."""
        tokens = self._tokenize(text)
        self._documents[doc_id] = text
        self._doc_lengths[doc_id] = len(tokens)

        tf = Counter(tokens)
        self._doc_tf[doc_id] = tf

        # Update document frequency
        for term in set(tokens):
            self._df[term] += 1

        # Recalculate average document length
        if self._doc_lengths:
            self._avg_doc_length = sum(self._doc_lengths.values()) / len(self._doc_lengths)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Search with BM25 scoring. Returns [(doc_id, score), ...]."""
        query_tokens = self._tokenize(query)
        n_docs = len(self._documents)
        if n_docs == 0:
            return []

        scores: Dict[str, float] = defaultdict(float)

        for term in query_tokens:
            if term not in self._df:
                continue

            df = self._df[term]
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

            for doc_id, tf_counter in self._doc_tf.items():
                tf = tf_counter.get(term, 0)
                if tf == 0:
                    continue

                doc_len = self._doc_lengths[doc_id]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * doc_len / max(self._avg_doc_length, 1)
                )
                scores[doc_id] += idf * numerator / denominator

        # Normalize scores to [0, 1]
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {k: v / max_score for k, v in scores.items()}

        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]

    def remove(self, doc_id: str):
        """Remove a document from the index."""
        if doc_id in self._documents:
            # Update document frequency
            for term in set(self._doc_tf.get(doc_id, {}).keys()):
                self._df[term] -= 1
                if self._df[term] <= 0:
                    del self._df[term]

            del self._documents[doc_id]
            del self._doc_lengths[doc_id]
            del self._doc_tf[doc_id]

            if self._doc_lengths:
                self._avg_doc_length = sum(self._doc_lengths.values()) / len(self._doc_lengths)


# ──────────────────────────────────────────────
# Document Chunking
# ──────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 80,
) -> List[str]:
    """
    Split text into overlapping chunks for indexing.
    Chunk size and overlap are in whitespace-delimited tokens.
    """
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = ' '.join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


@dataclass
class FailureTuple:
    """A single failure record in the Bug Diary."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)

    # Core tuple: z = (x, s, a, o, root_cause, fix, new_test)
    task: str = ""           # x — the original task/problem
    solution: str = ""       # s — the attempted solution
    action: str = ""         # a — the specific action taken
    observation: str = ""    # o — what happened (error, wrong output, etc.)
    root_cause: str = ""     # why it failed
    fix: str = ""            # how it was fixed
    new_test: str = ""       # regression test to prevent recurrence

    # Metadata
    category: str = ""       # error category (logic, syntax, reasoning, etc.)
    severity: float = 0.5    # 0-1 severity score
    weight: float = 1.0      # w_k — exponentially decayed recurrence counter
    times_retrieved: int = 0  # how often this failure was retrieved


@dataclass
class SuccessRecord:
    """A successful approach worth remembering."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    task: str = ""
    approach: str = ""
    result: str = ""
    confidence: float = 0.0
    category: str = ""


class MemoryManager:
    """
    Bug Diary + Knowledge Store for self-improving AI.

    Implements Section 6 of the architecture:
    - Store failures with full context (z-tuples)
    - Retrieve similar failures for new tasks
    - Track recurring mistakes with exponential decay
    - Maintain regression test suite
    - Store successful approaches for retrieval

    Uses ChromaDB for vector similarity search on failure descriptions.
    Falls back to JSON file storage if ChromaDB is unavailable.
    """

    def __init__(self, config=None, persist_dir: Optional[str] = None):
        self.config = config or brain_config
        self.persist_dir = Path(persist_dir or self.config.memory_persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Configurable capacity limits
        self._max_failures = 1000
        self._max_successes = 500

        # Storage
        self.failures: List[FailureTuple] = []
        self.successes: List[SuccessRecord] = []
        self.principles: List[ExpertPrinciple] = []
        self.regression_tests: List[str] = []

        # Category-level recurrence counters
        self._category_weights: Dict[str, float] = {}

        # Try to use ChromaDB for vector search
        self._chroma_client = None
        self._chroma_collection = None
        self._init_vector_store()

        # BM25 index for keyword search (hybrid with vector)
        self._bm25 = BM25Index()

        # Debounced write tracking
        self._last_save_time: float = 0.0
        self._save_interval: float = 5.0  # seconds between disk writes
        self._dirty: bool = False

        # Context cache
        self._context_cache: Dict[str, tuple] = {}  # query -> (timestamp, result)
        self._context_cache_ttl: float = 30.0  # seconds

        # Load persisted data
        self._load_from_disk()

        # Build BM25 index from loaded failures
        self._rebuild_bm25()

        logger.info(
            f"Memory initialized: {len(self.failures)} failures, "
            f"{len(self.successes)} successes, "
            f"{len(self.regression_tests)} regression tests"
        )

    def _init_vector_store(self):
        """Initialize ChromaDB for semantic similarity search."""
        try:
            import chromadb
            self._chroma_client = chromadb.PersistentClient(
                path=str(self.persist_dir / "chroma")
            )
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name=self.config.memory_collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB vector store initialized")
        except Exception as e:
            logger.warning(f"ChromaDB unavailable, using JSON fallback: {e}")

    # ──────────────────────────────────────
    # Store Operations
    # ──────────────────────────────────────

    def store_failure(self, failure: FailureTuple) -> str:
        """
        Store a failure in the Bug Diary.

        Updates the exponentially decayed recurrence counter:
            w_k ← γ·w_k + 1
        """
        # Update category weight (exponential decay)
        category = failure.category or "uncategorized"
        gamma = self.config.decay_factor
        prev_weight = self._category_weights.get(category, 0.0)
        self._category_weights[category] = gamma * prev_weight + 1.0
        failure.weight = self._category_weights[category]

        self.failures.append(failure)

        # Enforce capacity limit — remove oldest when full
        if len(self.failures) > self._max_failures:
            removed = self.failures[:len(self.failures) - self._max_failures]
            self.failures = self.failures[-self._max_failures:]
            # Clean removed entries from BM25
            for r in removed:
                self._bm25.remove(r.id)

        # Add to BM25 index
        doc_text = f"{failure.task} {failure.observation} {failure.root_cause} {failure.fix}"
        self._bm25.add(failure.id, doc_text)

        # Add regression test
        if failure.new_test:
            self.regression_tests.append(failure.new_test)

        # Store in vector DB for retrieval
        if self._chroma_collection is not None:
            doc_text = (
                f"Task: {failure.task}\n"
                f"Error: {failure.observation}\n"
                f"Root Cause: {failure.root_cause}\n"
                f"Fix: {failure.fix}"
            )
            self._chroma_collection.add(
                ids=[failure.id],
                documents=[doc_text],
                metadatas=[{
                    "category": category,
                    "severity": failure.severity,
                    "timestamp": failure.timestamp,
                }],
            )

        self._save_to_disk()
        logger.info(
            f"Stored failure [{failure.id}] category='{category}' "
            f"weight={failure.weight:.2f}"
        )
        return failure.id

    def store_success(self, success: SuccessRecord) -> str:
        """Store a successful approach."""
        self.successes.append(success)

        # Enforce capacity limit
        if len(self.successes) > self._max_successes:
            self.successes = self.successes[-self._max_successes:]

        self._debounced_save()
        logger.info(f"Stored success [{success.id}]")
        return success.id

    def store_principle(self, principle: ExpertPrinciple):
        """Store a deduced Expert Principle."""
        self.principles.append(principle)
        self._save_to_disk()
        logger.info(f"Stored Expert Principle: {principle.actionable_rule}")

    # ──────────────────────────────────────
    # Retrieval Operations (Hybrid Search)
    # ──────────────────────────────────────

    def _rebuild_bm25(self):
        """Rebuild BM25 index from all failures."""
        self._bm25 = BM25Index()
        for f in self.failures:
            doc_text = f"{f.task} {f.observation} {f.root_cause} {f.fix}"
            self._bm25.add(f.id, doc_text)

    def retrieve_similar_failures(
        self,
        query: str,
        n_results: int = None,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ) -> List[FailureTuple]:
        """
        Retrieve failures similar to the current task.

        Hybrid search:
            score = vector_weight * vector_score + bm25_weight * bm25_score

        Falls back to BM25-only if ChromaDB is unavailable.
        """
        n_results = n_results or self.config.max_memory_retrieval
        if not self.failures:
            return []

        hybrid_scores: Dict[str, float] = defaultdict(float)

        # ---- Vector search (ChromaDB) ----
        vector_ids = set()
        if self._chroma_collection is not None:
            try:
                results = self._chroma_collection.query(
                    query_texts=[query],
                    n_results=min(n_results * 2, len(self.failures)),
                )
                if results["ids"] and results["ids"][0]:
                    ids = results["ids"][0]
                    distances = results.get("distances", [[]])[0]
                    for i, doc_id in enumerate(ids):
                        # ChromaDB cosine distance → similarity
                        dist = distances[i] if i < len(distances) else 0.5
                        similarity = max(0.0, 1.0 - dist)
                        hybrid_scores[doc_id] += vector_weight * similarity
                        vector_ids.add(doc_id)
            except Exception as e:
                logger.warning(f"ChromaDB query failed: {e}")

        # ---- BM25 keyword search ----
        bm25_results = self._bm25.search(query, top_k=n_results * 2)
        for doc_id, score in bm25_results:
            hybrid_scores[doc_id] += bm25_weight * score

        # If no vector search was done, normalize BM25 to full weight
        if not vector_ids and bm25_results:
            for doc_id in hybrid_scores:
                hybrid_scores[doc_id] /= bm25_weight  # Scale up

        # Sort by hybrid score
        ranked = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)
        top_ids = [doc_id for doc_id, _ in ranked[:n_results]]

        # Map back to FailureTuple objects
        id_to_failure = {f.id: f for f in self.failures}
        matches = [id_to_failure[fid] for fid in top_ids if fid in id_to_failure]

        # Update retrieval counter
        for m in matches:
            m.times_retrieved += 1

        return matches

    def memory_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic memory search tool (OpenClaw-compatible).
        Returns both failures and successes ranked by relevance.
        """
        results = []

        # Search failures
        failures = self.retrieve_similar_failures(query, n_results=top_k)
        for f in failures:
            results.append({
                "type": "failure",
                "id": f.id,
                "task": f.task,
                "observation": f.observation,
                "root_cause": f.root_cause,
                "fix": f.fix,
                "category": f.category,
                "weight": f.weight,
            })

        # Search successes (simple keyword match)
        query_lower = query.lower()
        for s in self.successes:
            text = f"{s.task} {s.approach} {s.result}".lower()
            if any(word in text for word in query_lower.split()):
                results.append({
                    "type": "success",
                    "id": s.id,
                    "task": s.task,
                    "approach": s.approach,
                    "confidence": s.confidence,
                })

        return results[:top_k]

    def memory_get(self, failure_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific memory entry by ID."""
        for f in self.failures:
            if f.id == failure_id:
                return asdict(f)
        for s in self.successes:
            if s.id == failure_id:
                return asdict(s)
        return None

    def get_regression_tests(self) -> List[str]:
        """Get all accumulated regression tests."""
        return list(self.regression_tests)

    def get_recurring_categories(self, top_n: int = 5) -> List[tuple]:
        """Get most recurring failure categories by weight."""
        sorted_cats = sorted(
            self._category_weights.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_cats[:top_n]

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "total_failures": len(self.failures),
            "total_successes": len(self.successes),
            "regression_tests": len(self.regression_tests),
            "category_weights": dict(self._category_weights),
            "most_retrieved": sorted(
                [(f.id, f.times_retrieved, f.category) for f in self.failures],
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }

    # ──────────────────────────────────────
    # Context Building
    # ──────────────────────────────────────

    def build_context(self, task: str) -> str:
        """
        Build a context string from relevant memories for a new task.
        Cached for 30 seconds to avoid redundant hybrid searches.
        """
        # Check cache
        if task in self._context_cache:
            cached_time, cached_result = self._context_cache[task]
            if time.time() - cached_time < self._context_cache_ttl:
                return cached_result

        parts = []

        # Retrieve similar failures
        failures = self.retrieve_similar_failures(task, n_results=3)
        if failures:
            parts.append("⚠️ RELEVANT PAST FAILURES (learn from these):")
            for f in failures:
                parts.append(
                    f"  • Task: {f.task}\n"
                    f"    Error: {f.observation}\n"
                    f"    Root Cause: {f.root_cause}\n"
                    f"    Fix: {f.fix}"
                )

        # Retrieve Expert Principles
        if self.principles:
            parts.append("\n🧠 EXPERT PRINCIPLES (Axioms to follow):")
            # For now, append the last 3 deduced principles globally.
            for p in self.principles[-3:]:
                parts.append(f"  • {p.format_for_prompt()}")

        # Get recurring categories
        recurring = self.get_recurring_categories(top_n=3)
        if recurring:
            parts.append("\n⚠️ RECURRING ERROR PATTERNS:")
            for cat, weight in recurring:
                parts.append(f"  • {cat}: severity={weight:.1f}")

        # Get regression tests
        tests = self.get_regression_tests()
        if tests:
            parts.append(f"\n✅ REGRESSION TESTS TO RUN: {len(tests)} tests available")

        result = "\n".join(parts) if parts else ""
        
        # Cache the result
        self._context_cache[task] = (time.time(), result)
        # Prune old cache entries
        if len(self._context_cache) > 100:
            oldest = sorted(self._context_cache.items(), key=lambda x: x[1][0])[:50]
            for k, _ in oldest:
                del self._context_cache[k]
        
        return result

    # ──────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────

    def _debounced_save(self):
        """Save to disk at most once per save_interval."""
        now = time.time()
        if now - self._last_save_time >= self._save_interval:
            self._save_to_disk()
            self._last_save_time = now
            self._dirty = False
        else:
            self._dirty = True

    def _save_to_disk(self):
        """Persist all memory to JSON files."""
        from dataclasses import asdict
        data = {
            "failures": [asdict(f) for f in self.failures],
            "successes": [asdict(s) for s in self.successes],
            "principles": [asdict(p) for p in self.principles],
            "regression_tests": self.regression_tests,
            "category_weights": self._category_weights,
        }
        path = self.persist_dir / "memory.json"
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, default=str)

    def _load_from_disk(self):
        """Load persisted memory from JSON."""
        path = self.persist_dir / "memory.json"
        if not path.exists():
            return

        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)

            self.failures = [
                FailureTuple(**f) for f in data.get("failures", [])
            ]
            self.successes = [
                SuccessRecord(**s) for s in data.get("successes", [])
            ]
            self.principles = [
                ExpertPrinciple(**p) for p in data.get("principles", [])
            ]
            self.regression_tests = data.get("regression_tests", [])
            self._category_weights = data.get("category_weights", {})

        except Exception as e:
            logger.warning(f"Failed to load memory: {e}")
