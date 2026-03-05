"""
Neural Response Compression — Token Budget Optimizer
─────────────────────────────────────────────────────
Compresses prompts and contexts to fit within token limits while
preserving maximum semantic content. Like a neural codec for text.

Architecture:
  TokenEstimator  →  SemanticDeduplicator  →  ContextCompressor  →  PromptPacker
  (count tokens)     (remove redundancy)      (compress verbosity)   (pack budget)
"""

import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class ContentPriority(Enum):
    CRITICAL = 4    # Must keep (safety, core instructions)
    HIGH = 3        # Important (recent context, direct answers)
    MEDIUM = 2      # Helpful (examples, elaboration)
    LOW = 1         # Optional (pleasantries, redundant info)
    EXPENDABLE = 0  # Can drop (filler, duplicates)


@dataclass
class ContentBlock:
    """A block of content with priority and token estimate."""
    content: str
    priority: ContentPriority = ContentPriority.MEDIUM
    estimated_tokens: int = 0
    category: str = ""          # system, context, query, history, etc.
    compressible: bool = True
    content_hash: str = ""

    def __post_init__(self):
        if not self.estimated_tokens:
            self.estimated_tokens = TokenEstimator.estimate(self.content)
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()[:12]


@dataclass
class CompressionResult:
    """Result of a compression operation."""
    original_tokens: int = 0
    compressed_tokens: int = 0
    compression_ratio: float = 0.0
    blocks_kept: int = 0
    blocks_dropped: int = 0
    blocks_compressed: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def savings_pct(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return (1 - self.compressed_tokens / self.original_tokens) * 100


@dataclass
class BudgetAllocation:
    """Token budget allocation for different prompt sections."""
    system_prompt: int = 0
    context: int = 0
    history: int = 0
    query: int = 0
    reserved: int = 0  # Safety margin
    total: int = 0


# ──────────────────────────────────────────────
# Token Estimator
# ──────────────────────────────────────────────

class TokenEstimator:
    """Estimates token count without requiring a tokenizer dependency."""

    # Average chars per token (English text, BPE-based)
    CHARS_PER_TOKEN = 3.8

    @staticmethod
    def estimate(text: str) -> int:
        """Estimate token count from text."""
        if not text:
            return 0
        # Heuristic: ~3.8 chars per token for English text
        base = len(text) / TokenEstimator.CHARS_PER_TOKEN
        # Adjust for code (more tokens per char due to syntax)
        code_indicators = text.count("def ") + text.count("class ") + text.count("{")
        if code_indicators > 2:
            base *= 1.2
        return max(1, int(base))

    @staticmethod
    def estimate_batch(texts: List[str]) -> int:
        return sum(TokenEstimator.estimate(t) for t in texts)


# ──────────────────────────────────────────────
# Semantic Deduplicator
# ──────────────────────────────────────────────

class SemanticDeduplicator:
    """
    Detects near-duplicate information in context and removes redundancy.
    Uses shingling + Jaccard similarity for fast approximate matching.
    """

    def __init__(self, similarity_threshold: float = 0.6, shingle_size: int = 3):
        self._threshold = similarity_threshold
        self._shingle_size = shingle_size

    def deduplicate(self, blocks: List[ContentBlock]) -> Tuple[List[ContentBlock], int]:
        """Remove near-duplicate blocks. Returns (unique_blocks, removed_count)."""
        if len(blocks) <= 1:
            return blocks, 0

        unique = []
        removed = 0
        seen_shingles: List[set] = []

        for block in blocks:
            if block.priority == ContentPriority.CRITICAL:
                unique.append(block)
                seen_shingles.append(self._shingle(block.content))
                continue

            block_shingles = self._shingle(block.content)
            is_duplicate = False

            for seen in seen_shingles:
                similarity = self._jaccard(block_shingles, seen)
                if similarity >= self._threshold:
                    is_duplicate = True
                    removed += 1
                    break

            if not is_duplicate:
                unique.append(block)
                seen_shingles.append(block_shingles)

        return unique, removed

    def _shingle(self, text: str) -> set:
        """Create character-level shingles."""
        words = text.lower().split()
        if len(words) < self._shingle_size:
            return {text.lower().strip()}
        return {
            " ".join(words[i:i + self._shingle_size])
            for i in range(len(words) - self._shingle_size + 1)
        }

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)


# ──────────────────────────────────────────────
# Context Compressor
# ──────────────────────────────────────────────

class ContextCompressor:
    """
    Compresses verbose content into concise summaries while
    preserving key information. Uses rule-based compression
    with optional LLM-assisted summarization.
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self._generate_fn = generate_fn

    def compress(self, text: str, target_ratio: float = 0.5) -> str:
        """
        Compress text to approximately target_ratio of original tokens.
        target_ratio=0.5 means compress to ~50% of original size.
        """
        if not text or target_ratio >= 1.0:
            return text

        original_tokens = TokenEstimator.estimate(text)
        target_tokens = int(original_tokens * target_ratio)

        # Stage 1: Remove filler
        compressed = self._remove_filler(text)

        # Stage 2: Condense bullet points
        compressed = self._condense_bullets(compressed)

        # Stage 3: Shorten verbose phrases
        compressed = self._shorten_phrases(compressed)

        # Stage 4: LLM summarization if still too long
        current_tokens = TokenEstimator.estimate(compressed)
        if current_tokens > target_tokens and self._generate_fn:
            compressed = self._llm_compress(compressed, target_tokens)

        return compressed

    def _remove_filler(self, text: str) -> str:
        """Remove filler phrases that add no information."""
        fillers = [
            r'\bbasically\b', r'\bessentially\b', r'\bactually\b',
            r'\binterestingly\b', r'\bin fact\b', r'\bas you can see\b',
            r'\bit is worth noting that\b', r'\bit should be noted that\b',
            r'\bas mentioned (earlier|above|before)\b',
            r'\bplease note that\b', r'\bkeep in mind that\b',
        ]
        result = text
        for filler in fillers:
            result = re.sub(filler, '', result, flags=re.IGNORECASE)
        # Clean up double spaces
        result = re.sub(r'  +', ' ', result)
        return result.strip()

    def _condense_bullets(self, text: str) -> str:
        """Condense verbose bullet points."""
        lines = text.split('\n')
        condensed = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('-', '*', '•')):
                # Remove redundant "The" at start of bullets
                content = stripped.lstrip('-*• ')
                if content.startswith(('The ', 'A ', 'An ')):
                    content = content.split(' ', 1)[1] if ' ' in content else content
                condensed.append(f"- {content}")
            else:
                condensed.append(line)
        return '\n'.join(condensed)

    def _shorten_phrases(self, text: str) -> str:
        """Replace verbose phrases with concise alternatives."""
        replacements = [
            (r'in order to', 'to'),
            (r'due to the fact that', 'because'),
            (r'at this point in time', 'now'),
            (r'in the event that', 'if'),
            (r'with regard to', 're:'),
            (r'a large number of', 'many'),
            (r'a small number of', 'few'),
            (r'the majority of', 'most'),
            (r'in addition to', 'plus'),
            (r'for the purpose of', 'for'),
        ]
        result = text
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def _llm_compress(self, text: str, target_tokens: int) -> str:
        """Use LLM for intelligent compression."""
        if not self._generate_fn:
            return text
        try:
            prompt = (
                f"Compress the following text to approximately {target_tokens} tokens. "
                f"Preserve ALL key facts, numbers, and technical details. "
                f"Remove only filler and redundancy.\n\n{text}"
            )
            return self._generate_fn(prompt)
        except Exception:
            return text


# ──────────────────────────────────────────────
# Prompt Packer
# ──────────────────────────────────────────────

class PromptPacker:
    """
    Packs system prompt + context + query into an optimal token
    budget allocation, respecting priorities and limits.
    """

    # Default budget split ratios
    DEFAULT_RATIOS = {
        "system_prompt": 0.25,
        "context": 0.35,
        "history": 0.20,
        "query": 0.15,
        "reserved": 0.05,
    }

    def __init__(self, max_tokens: int = 4096, ratios: Dict[str, float] = None):
        self._max_tokens = max_tokens
        self._ratios = ratios or self.DEFAULT_RATIOS

    def allocate_budget(self, **actual_tokens) -> BudgetAllocation:
        """
        Calculate optimal token allocation given actual content sizes.
        Reallocates unused budget from sections that don't need it.
        """
        budget = BudgetAllocation(total=self._max_tokens)

        # Initial allocation by ratio
        for section, ratio in self._ratios.items():
            setattr(budget, section, int(self._max_tokens * ratio))

        # Reallocate unused budget to sections that need more
        surplus = 0
        needs_more = []

        for section, actual in actual_tokens.items():
            allocated = getattr(budget, section, 0)
            if actual < allocated:
                surplus += allocated - actual
                setattr(budget, section, actual)
            elif actual > allocated:
                needs_more.append((section, actual - allocated))

        # Distribute surplus proportionally to sections that need more
        if surplus > 0 and needs_more:
            total_need = sum(need for _, need in needs_more)
            for section, need in needs_more:
                extra = int(surplus * need / total_need)
                current = getattr(budget, section)
                setattr(budget, section, current + extra)

        return budget

    def pack(self, blocks: List[ContentBlock], budget: BudgetAllocation = None
             ) -> Tuple[str, CompressionResult]:
        """
        Pack content blocks into the token budget.
        Returns packed text and compression stats.
        """
        if budget is None:
            budget = self.allocate_budget()

        result = CompressionResult()
        result.original_tokens = sum(b.estimated_tokens for b in blocks)

        # Sort blocks: CRITICAL first, then by priority descending
        sorted_blocks = sorted(blocks, key=lambda b: b.priority.value, reverse=True)

        packed_parts = []
        remaining_tokens = self._max_tokens

        for block in sorted_blocks:
            if block.estimated_tokens <= remaining_tokens:
                packed_parts.append(block.content)
                remaining_tokens -= block.estimated_tokens
                result.blocks_kept += 1
            elif block.priority == ContentPriority.CRITICAL:
                # Critical blocks are always included
                packed_parts.append(block.content)
                remaining_tokens -= block.estimated_tokens
                result.blocks_kept += 1
                if remaining_tokens < 0:
                    result.warnings.append("Critical content exceeds budget")
            else:
                result.blocks_dropped += 1

        packed_text = "\n\n".join(packed_parts)
        result.compressed_tokens = TokenEstimator.estimate(packed_text)
        result.compression_ratio = (
            result.compressed_tokens / max(result.original_tokens, 1)
        )

        return packed_text, result


# ──────────────────────────────────────────────
# Token Budget Optimizer (Main Interface)
# ──────────────────────────────────────────────

class TokenBudgetOptimizer:
    """
    Main interface for the Neural Response Compression system.

    Usage:
        optimizer = TokenBudgetOptimizer(max_tokens=4096)
        packed, stats = optimizer.optimize(
            system_prompt="You are a helpful assistant...",
            context=["Previous conversation...", "Relevant docs..."],
            query="How do I fix this bug?",
        )
        # packed is the compressed prompt text
        # stats shows compression ratio, tokens saved, etc.
    """

    def __init__(
        self,
        max_tokens: int = 4096,
        generate_fn: Optional[Callable] = None,
        dedup_threshold: float = 0.6,
    ):
        self._max_tokens = max_tokens
        self.deduplicator = SemanticDeduplicator(similarity_threshold=dedup_threshold)
        self.compressor = ContextCompressor(generate_fn=generate_fn)
        self.packer = PromptPacker(max_tokens=max_tokens)

    def optimize(
        self,
        system_prompt: str = "",
        context: List[str] = None,
        history: List[str] = None,
        query: str = "",
    ) -> Tuple[str, CompressionResult]:
        """Optimize all prompt components to fit within token budget."""
        blocks = []

        # System prompt — always critical
        if system_prompt:
            blocks.append(ContentBlock(
                content=system_prompt,
                priority=ContentPriority.CRITICAL,
                category="system_prompt",
                compressible=False,
            ))

        # Context blocks
        for ctx in (context or []):
            blocks.append(ContentBlock(
                content=ctx,
                priority=ContentPriority.HIGH,
                category="context",
            ))

        # History (older = lower priority)
        for i, msg in enumerate(history or []):
            priority = ContentPriority.HIGH if i >= len(history or []) - 2 else ContentPriority.MEDIUM
            blocks.append(ContentBlock(
                content=msg,
                priority=priority,
                category="history",
            ))

        # Query — always critical
        if query:
            blocks.append(ContentBlock(
                content=query,
                priority=ContentPriority.CRITICAL,
                category="query",
                compressible=False,
            ))

        # Step 1: Deduplicate
        blocks, dedup_count = self.deduplicator.deduplicate(blocks)

        # Step 2: Compress compressible blocks if over budget
        total_tokens = sum(b.estimated_tokens for b in blocks)
        if total_tokens > self._max_tokens:
            target_ratio = self._max_tokens / total_tokens
            for block in blocks:
                if block.compressible and block.priority.value <= ContentPriority.HIGH.value:
                    block.content = self.compressor.compress(block.content, target_ratio)
                    block.estimated_tokens = TokenEstimator.estimate(block.content)

        # Step 3: Pack into budget
        packed, result = self.packer.pack(blocks)
        result.blocks_compressed = sum(
            1 for b in blocks if b.category == "context" and b.compressible
        )

        if dedup_count > 0:
            logger.info(f"⚡ Token optimizer: removed {dedup_count} duplicate blocks")

        return packed, result

    def estimate_tokens(self, text: str) -> int:
        """Quick token estimation."""
        return TokenEstimator.estimate(text)

    def get_budget_allocation(self, **kwargs) -> BudgetAllocation:
        """Get current budget allocation."""
        return self.packer.allocate_budget(**kwargs)
