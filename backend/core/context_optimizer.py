"""
Dynamic Context Optimizer — Smart Context Window Compression
══════════════════════════════════════════════════════════
Dynamically scores, prioritizes, and compresses context chunks
to maximize signal-to-noise ratio within token budget limits.

Capabilities:
  1. Relevance Scoring   — Score each context chunk by relevance to query
  2. Priority Ranking    — Rank chunks by importance × relevance
  3. Compression         — Summarize low-value chunks to save space
  4. Budget Enforcement  — Stay within configured token limits
  5. Adaptive Sizing     — Adjust context window based on query complexity
"""

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ChunkPriority(Enum):
    CRITICAL = 5    # System prompts, safety rules
    HIGH = 4        # Direct query context
    MEDIUM = 3      # Related information
    LOW = 2         # Background context
    FILLER = 1      # Can be dropped


@dataclass
class ContextChunk:
    """A scored segment of context."""
    text: str
    source: str = "unknown"
    priority: ChunkPriority = ChunkPriority.MEDIUM
    relevance_score: float = 0.5
    token_count: int = 0
    compressed: bool = False
    original_length: int = 0

    def __post_init__(self):
        self.token_count = len(self.text.split())
        self.original_length = self.token_count

    @property
    def effective_score(self) -> float:
        """Combined priority and relevance score."""
        return self.priority.value * self.relevance_score


class ContextOptimizer:
    """
    Optimizes context windows by scoring relevance, compressing
    low-value sections, and enforcing token budgets.
    """

    DEFAULT_MAX_TOKENS = 4000
    COMPRESSION_RATIO = 0.3  # Compress to 30% of original

    def __init__(self, max_tokens: int = None):
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self._total_optimizations = 0
        self._total_tokens_saved = 0
        self._compression_count = 0
        logger.info(f"[CONTEXT-OPT] Optimizer initialized (max_tokens={self.max_tokens})")

    def optimize(self, context_parts: List[Tuple[str, str, ChunkPriority]],
                 query: str, max_tokens: int = None) -> str:
        """
        Optimize context for the given query.

        Args:
            context_parts: List of (text, source, priority) tuples
            query: The user's query for relevance scoring
            max_tokens: Override max tokens for this call

        Returns:
            Optimized context string within token budget
        """
        budget = max_tokens or self.max_tokens
        start = time.time()

        # Step 1: Create scored chunks
        chunks = []
        for text, source, priority in context_parts:
            chunk = ContextChunk(text=text, source=source, priority=priority)
            chunk.relevance_score = self._score_relevance(text, query)
            chunks.append(chunk)

        # Step 2: Sort by effective score (highest first)
        chunks.sort(key=lambda c: c.effective_score, reverse=True)

        # Step 3: Fit within budget
        result_chunks = []
        used_tokens = 0
        original_tokens = sum(c.token_count for c in chunks)

        for chunk in chunks:
            if used_tokens + chunk.token_count <= budget:
                # Fits entirely
                result_chunks.append(chunk)
                used_tokens += chunk.token_count
            elif used_tokens < budget and chunk.effective_score >= 2.0:
                # Partially fits — compress
                remaining = budget - used_tokens
                compressed = self._compress_chunk(chunk, remaining)
                result_chunks.append(compressed)
                used_tokens += compressed.token_count
                self._compression_count += 1
            # Otherwise drop it

        # Step 4: Assemble optimized context
        optimized = self._assemble(result_chunks)

        tokens_saved = original_tokens - used_tokens
        self._total_optimizations += 1
        self._total_tokens_saved += max(tokens_saved, 0)

        latency = (time.time() - start) * 1000
        logger.info(
            f"[CONTEXT-OPT] Optimized: {original_tokens}→{used_tokens} tokens "
            f"({len(result_chunks)}/{len(chunks)} chunks), "
            f"saved {tokens_saved}, latency={latency:.0f}ms"
        )
        return optimized

    def _score_relevance(self, text: str, query: str) -> float:
        """Score relevance of text to query using token overlap."""
        if not query or not text:
            return 0.3

        query_tokens = set(query.lower().split())
        text_tokens = set(text.lower().split())

        # Remove stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be",
                       "to", "of", "in", "for", "on", "with", "at", "by",
                       "it", "this", "that", "and", "or", "but", "not"}
        query_tokens -= stop_words
        text_tokens -= stop_words

        if not query_tokens:
            return 0.3

        overlap = len(query_tokens & text_tokens)
        coverage = overlap / max(len(query_tokens), 1)

        # Bonus for key terms
        key_terms = {"error", "function", "class", "code", "debug",
                      "fix", "create", "build", "explain", "how"}
        mutual_keys = query_tokens & text_tokens & key_terms
        key_bonus = len(mutual_keys) * 0.1

        return min(coverage + key_bonus, 1.0)

    def _compress_chunk(self, chunk: ContextChunk, max_tokens: int) -> ContextChunk:
        """Compress a chunk to fit within token budget."""
        words = chunk.text.split()
        if len(words) <= max_tokens:
            return chunk

        # Take first and last parts (usually most important)
        head_size = int(max_tokens * 0.6)
        tail_size = max_tokens - head_size - 3  # 3 for "[...]"

        if tail_size > 0:
            compressed_text = " ".join(words[:head_size]) + " [...] " + " ".join(words[-tail_size:])
        else:
            compressed_text = " ".join(words[:max_tokens])

        return ContextChunk(
            text=compressed_text,
            source=chunk.source,
            priority=chunk.priority,
            relevance_score=chunk.relevance_score,
            compressed=True,
            original_length=chunk.original_length,
        )

    def _assemble(self, chunks: List[ContextChunk]) -> str:
        """Assemble optimized chunks into a coherent context string."""
        parts = []
        for chunk in chunks:
            if chunk.compressed:
                parts.append(f"[{chunk.source} (compressed)]:\n{chunk.text}")
            else:
                parts.append(f"[{chunk.source}]:\n{chunk.text}")
        return "\n\n".join(parts)

    def estimate_complexity(self, query: str) -> int:
        """Estimate query complexity → recommended max tokens."""
        words = len(query.split())
        question_marks = query.count("?")
        code_indicators = sum(1 for kw in ["function", "class", "implement", "code", "algorithm"]
                               if kw in query.lower())

        if words < 10 and question_marks <= 1 and code_indicators == 0:
            return int(self.max_tokens * 0.5)
        elif words < 30 and code_indicators <= 1:
            return int(self.max_tokens * 0.75)
        else:
            return self.max_tokens

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_optimizations": self._total_optimizations,
            "total_tokens_saved": self._total_tokens_saved,
            "compression_count": self._compression_count,
            "max_tokens": self.max_tokens,
            "avg_tokens_saved": (
                self._total_tokens_saved /
                max(self._total_optimizations, 1)
            ),
        }
