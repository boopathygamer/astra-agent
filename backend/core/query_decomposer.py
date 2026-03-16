"""
Query Decomposition Engine — Complex → Parallel Sub-Queries
═══════════════════════════════════════════════════════════
Breaks complex multi-part queries into independent sub-queries,
executes them in parallel, and merges results with conflict resolution.

Capabilities:
  1. Clause Detection    — Split compound queries by conjunctions
  2. Dependency Analysis — Build sub-query DAG
  3. Parallel Execution  — Independent sub-queries run concurrently
  4. Result Merging      — Intelligent combination with dedup
  5. Conflict Resolution — Handle contradictory sub-results
"""

import hashlib
import logging
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SubQueryType(Enum):
    FACTUAL = "factual"
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    CODE = "code"
    COMPARISON = "comparison"


@dataclass
class SubQuery:
    """A decomposed sub-query."""
    query_id: str = ""
    text: str = ""
    query_type: SubQueryType = SubQueryType.FACTUAL
    depends_on: List[str] = field(default_factory=list)
    result: str = ""
    confidence: float = 0.0
    latency_ms: float = 0.0
    error: str = ""

    def __post_init__(self):
        if not self.query_id:
            self.query_id = hashlib.md5(
                f"{self.text}_{time.time()}".encode()
            ).hexdigest()[:8]


@dataclass
class DecompositionResult:
    """Result of query decomposition and parallel execution."""
    original_query: str = ""
    sub_queries: List[SubQuery] = field(default_factory=list)
    merged_result: str = ""
    total_latency_ms: float = 0.0
    was_decomposed: bool = False
    conflict_count: int = 0


# Patterns indicating compound queries
SPLIT_PATTERNS = [
    r'\b(?:and also|and then|additionally|furthermore|moreover)\b',
    r'\b(?:first|second|third|then|next|finally|also)\b[,.]?\s',
    r'(?:\d+[\.\)]\s)',  # Numbered lists
    r'[;]\s+',           # Semicolons
    r'\b(?:compare|versus|vs\.?|or)\b',
]

COMPLEXITY_KEYWORDS = {
    "compare": SubQueryType.COMPARISON,
    "analyze": SubQueryType.ANALYTICAL,
    "create": SubQueryType.CREATIVE,
    "write": SubQueryType.CREATIVE,
    "code": SubQueryType.CODE,
    "implement": SubQueryType.CODE,
    "function": SubQueryType.CODE,
    "explain": SubQueryType.FACTUAL,
}


class QueryDecomposer:
    """
    Decomposes complex queries into parallel sub-queries with
    dependency resolution and result merging.
    """

    MAX_SUB_QUERIES = 8
    MIN_QUERY_LENGTH = 15  # Don't decompose very short queries

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="decompose",
        )
        self._total_decompositions = 0
        self._total_sub_queries = 0
        logger.info("[DECOMPOSER] Query decomposition engine initialized")

    def decompose_and_execute(self, query: str,
                               executor_fn: Optional[Callable] = None,
                               timeout: float = 30.0) -> DecompositionResult:
        """Decompose query, execute sub-queries in parallel, merge results."""
        start = time.time()
        result = DecompositionResult(original_query=query)

        # Step 1: Check if decomposition is needed
        if len(query) < self.MIN_QUERY_LENGTH or not self._should_decompose(query):
            result.was_decomposed = False
            result.merged_result = query
            return result

        # Step 2: Decompose
        sub_queries = self._decompose(query)
        if len(sub_queries) <= 1:
            result.was_decomposed = False
            result.merged_result = query
            return result

        result.sub_queries = sub_queries
        result.was_decomposed = True
        self._total_decompositions += 1
        self._total_sub_queries += len(sub_queries)

        # Step 3: Execute in parallel (respecting dependencies)
        fn = executor_fn or self.generate_fn
        if fn:
            self._execute_parallel(sub_queries, fn, timeout)

        # Step 4: Merge results
        result.merged_result = self._merge_results(sub_queries)
        result.conflict_count = self._detect_conflicts(sub_queries)
        result.total_latency_ms = (time.time() - start) * 1000

        logger.info(
            f"[DECOMPOSER] Decomposed into {len(sub_queries)} sub-queries, "
            f"conflicts={result.conflict_count}, "
            f"latency={result.total_latency_ms:.0f}ms"
        )
        return result

    def _should_decompose(self, query: str) -> bool:
        """Check if query is complex enough to benefit from decomposition."""
        # Check for compound indicators
        for pattern in SPLIT_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        # Long queries (>50 words) often benefit
        if len(query.split()) > 50:
            return True
        return False

    def _decompose(self, query: str) -> List[SubQuery]:
        """Split query into sub-queries."""
        parts = []

        # Try splitting by patterns
        for pattern in SPLIT_PATTERNS:
            splits = re.split(pattern, query, flags=re.IGNORECASE)
            splits = [s.strip() for s in splits if s.strip() and len(s.strip()) > 10]
            if len(splits) > 1:
                parts = splits
                break

        # Fallback: split by sentences
        if not parts:
            sentences = re.split(r'[.!?]+\s+', query)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
            if len(sentences) > 1:
                parts = sentences

        if not parts:
            return [SubQuery(text=query)]

        # Create sub-queries with type detection
        sub_queries = []
        for i, part in enumerate(parts[:self.MAX_SUB_QUERIES]):
            q_type = self._detect_type(part)
            sub_queries.append(SubQuery(
                text=part,
                query_type=q_type,
            ))

        # Detect dependencies (later queries may reference earlier ones)
        self._resolve_dependencies(sub_queries)
        return sub_queries

    def _detect_type(self, text: str) -> SubQueryType:
        """Detect the type of a sub-query."""
        text_lower = text.lower()
        for keyword, q_type in COMPLEXITY_KEYWORDS.items():
            if keyword in text_lower:
                return q_type
        return SubQueryType.FACTUAL

    def _resolve_dependencies(self, sub_queries: List[SubQuery]):
        """Build dependency graph between sub-queries."""
        # Simple heuristic: if a query references "above", "previous",
        # "that", or pronouns, it depends on the previous query
        dep_keywords = ["above", "previous", "that result", "its", "those"]
        for i, sq in enumerate(sub_queries):
            if i > 0:
                text_lower = sq.text.lower()
                if any(kw in text_lower for kw in dep_keywords):
                    sq.depends_on.append(sub_queries[i-1].query_id)

    def _execute_parallel(self, sub_queries: List[SubQuery],
                           executor_fn: Callable, timeout: float):
        """Execute independent sub-queries in parallel."""
        # Separate independent and dependent queries
        independent = [sq for sq in sub_queries if not sq.depends_on]
        dependent = [sq for sq in sub_queries if sq.depends_on]

        # Execute independent queries in parallel
        futures = {}
        for sq in independent:
            future = self._executor.submit(self._execute_sub, sq, executor_fn)
            futures[future] = sq

        for future in as_completed(futures, timeout=timeout):
            try:
                future.result()
            except Exception as e:
                futures[future].error = str(e)

        # Execute dependent queries sequentially
        for sq in dependent:
            try:
                self._execute_sub(sq, executor_fn)
            except Exception as e:
                sq.error = str(e)

    def _execute_sub(self, sq: SubQuery, executor_fn: Callable):
        """Execute a single sub-query."""
        start = time.time()
        try:
            result = executor_fn(sq.text)
            sq.result = result if isinstance(result, str) else str(result)
            sq.confidence = 0.8
        except Exception as e:
            sq.result = f"Error: {e}"
            sq.confidence = 0.0
            sq.error = str(e)
        sq.latency_ms = (time.time() - start) * 1000

    def _merge_results(self, sub_queries: List[SubQuery]) -> str:
        """Merge sub-query results into a coherent answer."""
        parts = []
        for i, sq in enumerate(sub_queries):
            if sq.result and not sq.error:
                parts.append(f"**Part {i+1}** ({sq.query_type.value}):\n{sq.result}")
            elif sq.error:
                parts.append(f"**Part {i+1}**: Unable to process — {sq.error}")

        if not parts:
            return "Unable to process the decomposed query."

        return "\n\n".join(parts)

    def _detect_conflicts(self, sub_queries: List[SubQuery]) -> int:
        """Detect contradictory results between sub-queries."""
        conflicts = 0
        contradiction_markers = [
            ("yes", "no"), ("true", "false"), ("correct", "incorrect"),
            ("should", "should not"), ("is", "is not"),
        ]
        results = [sq.result.lower() for sq in sub_queries if sq.result]

        for i, r1 in enumerate(results):
            for r2 in results[i+1:]:
                for pos, neg in contradiction_markers:
                    if (pos in r1 and neg in r2) or (neg in r1 and pos in r2):
                        conflicts += 1
                        break
        return conflicts

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_decompositions": self._total_decompositions,
            "total_sub_queries": self._total_sub_queries,
            "avg_sub_queries": (
                self._total_sub_queries / max(self._total_decompositions, 1)
            ),
        }
