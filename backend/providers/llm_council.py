"""
LLM Council — Multi-Provider Consensus Engine
═══════════════════════════════════════════════
When 2+ API keys are configured, the Council queries all providers
concurrently, has each provider cross-rank the others' responses,
and selects the highest-scoring response.

Architecture:
  1. Concurrent Query   — asyncio.gather across all providers
  2. Cross-Ranking      — Each provider scores all other responses 1-10
  3. Aggregation        — Average scores (excluding self-scores)
  4. Selection          — Highest aggregate score wins

Fallbacks:
  - Single provider → Direct mode (no council)
  - Council ranking fails → Fastest successful response
"""

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.model_providers import ModelProvider, GenerationResult

logger = logging.getLogger(__name__)

# Thread pool for running synchronous provider calls concurrently
_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="council")


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

@dataclass
class ProviderResponse:
    """Response from a single provider in the council."""
    provider_name: str
    model: str
    text: str
    latency_ms: float
    tokens_used: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.error


@dataclass
class RankingScore:
    """Score assigned by one provider to another's response."""
    judge: str          # Provider that did the judging
    target: str         # Provider whose response was judged
    accuracy: float     # 1-10
    completeness: float # 1-10
    clarity: float      # 1-10
    relevance: float    # 1-10

    @property
    def average(self) -> float:
        return (self.accuracy + self.completeness + self.clarity + self.relevance) / 4.0


@dataclass
class RankedResponse:
    """A provider response with its aggregate council score."""
    provider_name: str
    model: str
    text: str
    latency_ms: float
    aggregate_score: float     # Average across all judges
    individual_scores: List[RankingScore] = field(default_factory=list)
    rank: int = 0


@dataclass
class CouncilResult:
    """Full result from a council deliberation."""
    best_response: str         # The winning text
    best_provider: str         # Name of the winning provider
    best_model: str            # Model of the winning provider
    best_score: float          # Aggregate score of the winner
    council_size: int          # Number of providers queried
    mode: str                  # "council" or "direct"
    all_ranked: List[RankedResponse] = field(default_factory=list)
    total_latency_ms: float = 0.0
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.best_response) and not self.error


# ══════════════════════════════════════════════════════════════
# Cross-Ranking Prompt
# ══════════════════════════════════════════════════════════════

_RANKING_PROMPT = """You are an expert evaluator. Below is a user question and multiple AI responses.
Rate EACH response on 4 dimensions (1-10 scale):
- accuracy: Factual correctness
- completeness: Covers the full scope of the question
- clarity: Clear, well-structured explanation
- relevance: Directly addresses the question

USER QUESTION:
{question}

{responses_block}

Return ONLY valid JSON — an array of objects, one per response:
[
  {{"response_id": "A", "accuracy": 8, "completeness": 7, "clarity": 9, "relevance": 8}},
  ...
]

No explanation, no markdown, ONLY the JSON array."""


def _build_responses_block(responses: List[ProviderResponse], exclude: str = "") -> str:
    """Build the labeled response block for the ranking prompt."""
    labels = "ABCDE"
    lines = []
    idx = 0
    for r in responses:
        if r.provider_name == exclude or not r.ok:
            continue
        label = labels[idx] if idx < len(labels) else f"R{idx}"
        lines.append(f"--- RESPONSE {label} (provider: {r.provider_name}) ---")
        # Truncate very long responses to avoid token overflow
        text = r.text[:3000] if len(r.text) > 3000 else r.text
        lines.append(text)
        lines.append("")
        idx += 1
    return "\n".join(lines)


def _parse_ranking_json(raw: str, responses: List[ProviderResponse]) -> List[dict]:
    """Extract JSON array from the ranking response, tolerating markdown fences."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the text
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse ranking JSON from response")
    return []


# ══════════════════════════════════════════════════════════════
# LLM Council
# ══════════════════════════════════════════════════════════════

class LLMCouncil:
    """
    Multi-provider consensus engine.
    Queries all providers, cross-ranks responses, selects the best.
    """

    def __init__(self, providers: List[ModelProvider]):
        self.providers = providers
        self._query_count = 0
        logger.info(
            f"🏛️ LLM Council initialized with {len(providers)} providers: "
            f"{[p.name for p in providers]}"
        )

    @property
    def size(self) -> int:
        return len(self.providers)

    @property
    def is_council_mode(self) -> bool:
        return len(self.providers) >= 2

    def query(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        skip_ranking: bool = False,
        **kwargs,
    ) -> CouncilResult:
        """
        Query the council. If only 1 provider, runs in direct mode.
        If 2+, gathers all responses and cross-ranks them.
        """
        self._query_count += 1
        start = time.time()

        if not self.providers:
            return CouncilResult(
                best_response="",
                best_provider="none",
                best_model="",
                best_score=0.0,
                council_size=0,
                mode="error",
                error="No providers configured",
            )

        # Single provider → direct mode
        if len(self.providers) == 1:
            return self._direct_query(
                self.providers[0], prompt, system_prompt,
                max_tokens, temperature, **kwargs
            )

        # Multi-provider → council mode
        try:
            # Step 1: Gather responses from all providers concurrently
            responses = self._gather_responses(
                prompt, system_prompt, max_tokens, temperature, **kwargs
            )

            successful = [r for r in responses if r.ok]
            if not successful:
                return CouncilResult(
                    best_response="",
                    best_provider="none",
                    best_model="",
                    best_score=0.0,
                    council_size=len(self.providers),
                    mode="council",
                    error="All providers failed",
                    total_latency_ms=(time.time() - start) * 1000,
                )

            # If only 1 succeeded, use it directly
            if len(successful) == 1 or skip_ranking:
                best = successful[0]
                return CouncilResult(
                    best_response=best.text,
                    best_provider=best.provider_name,
                    best_model=best.model,
                    best_score=10.0 if skip_ranking else 7.0,
                    council_size=len(self.providers),
                    mode="council-single" if len(successful) == 1 else "council-skip",
                    total_latency_ms=(time.time() - start) * 1000,
                )

            # Step 2: Cross-rank responses
            ranked = self._cross_rank(prompt, successful)

            if not ranked:
                # Ranking failed — fall back to fastest response
                best = min(successful, key=lambda r: r.latency_ms)
                return CouncilResult(
                    best_response=best.text,
                    best_provider=best.provider_name,
                    best_model=best.model,
                    best_score=6.0,
                    council_size=len(self.providers),
                    mode="council-fallback",
                    total_latency_ms=(time.time() - start) * 1000,
                )

            # Step 3: Select best
            best = ranked[0]
            total_latency = (time.time() - start) * 1000

            logger.info(
                f"🏛️ Council result: winner={best.provider_name} "
                f"score={best.aggregate_score:.1f}/10 "
                f"council_size={len(successful)} "
                f"total={total_latency:.0f}ms"
            )

            return CouncilResult(
                best_response=best.text,
                best_provider=best.provider_name,
                best_model=best.model,
                best_score=best.aggregate_score,
                council_size=len(self.providers),
                mode="council",
                all_ranked=ranked,
                total_latency_ms=total_latency,
            )

        except Exception as e:
            logger.error(f"Council query failed: {e}", exc_info=True)
            # Emergency fallback: try first provider directly
            return self._direct_query(
                self.providers[0], prompt, system_prompt,
                max_tokens, temperature, **kwargs
            )

    def _direct_query(
        self, provider: ModelProvider, prompt: str,
        system_prompt: str, max_tokens: int, temperature: float,
        **kwargs,
    ) -> CouncilResult:
        """Single-provider direct mode."""
        result = provider.generate(
            prompt, max_tokens, temperature, system_prompt, **kwargs
        )
        return CouncilResult(
            best_response=result.text,
            best_provider=provider.name,
            best_model=provider.model,
            best_score=7.0 if result.ok else 0.0,
            council_size=1,
            mode="direct",
            total_latency_ms=result.latency_ms,
            error=result.error,
        )

    def _gather_responses(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs,
    ) -> List[ProviderResponse]:
        """Query all providers concurrently using a thread pool."""

        def _call_provider(provider: ModelProvider) -> ProviderResponse:
            try:
                result = provider.generate(
                    prompt, max_tokens, temperature, system_prompt, **kwargs
                )
                return ProviderResponse(
                    provider_name=provider.name,
                    model=provider.model,
                    text=result.text,
                    latency_ms=result.latency_ms,
                    tokens_used=result.tokens_used,
                    error=result.error,
                )
            except Exception as e:
                return ProviderResponse(
                    provider_name=provider.name,
                    model=provider.model,
                    text="",
                    latency_ms=0.0,
                    error=str(e),
                )

        # Use threads to call all providers concurrently
        # (the openai SDK calls are blocking I/O)
        import concurrent.futures
        futures = {
            _executor.submit(_call_provider, p): p
            for p in self.providers
        }

        responses = []
        for future in concurrent.futures.as_completed(futures, timeout=60):
            try:
                responses.append(future.result())
            except Exception as e:
                provider = futures[future]
                responses.append(ProviderResponse(
                    provider_name=provider.name,
                    model=provider.model,
                    text="",
                    latency_ms=0.0,
                    error=f"Thread error: {e}",
                ))

        logger.info(
            f"🏛️ Gathered {len(responses)} responses: "
            f"{sum(1 for r in responses if r.ok)} successful, "
            f"{sum(1 for r in responses if not r.ok)} failed"
        )
        return responses

    def _cross_rank(
        self,
        original_prompt: str,
        responses: List[ProviderResponse],
    ) -> List[RankedResponse]:
        """
        Have each provider rank all other responses.
        Returns responses sorted by aggregate score (highest first).
        """
        labels = "ABCDE"
        # Build provider→label mapping
        provider_labels = {}
        for i, r in enumerate(responses):
            label = labels[i] if i < len(labels) else f"R{i}"
            provider_labels[r.provider_name] = label

        # Collect all scores
        all_scores: Dict[str, List[RankingScore]] = {
            r.provider_name: [] for r in responses
        }

        # Ask each provider to rank the others
        for judge_provider in self.providers:
            # Skip if this provider didn't return a successful response
            judge_response = next(
                (r for r in responses if r.provider_name == judge_provider.name and r.ok),
                None,
            )
            if not judge_response:
                continue

            # Build the ranking prompt with all responses (including judge's own)
            responses_block = _build_responses_block(responses)
            ranking_prompt = _RANKING_PROMPT.format(
                question=original_prompt,
                responses_block=responses_block,
            )

            try:
                rank_result = judge_provider.generate(
                    ranking_prompt,
                    max_tokens=500,
                    temperature=0.1,
                    system_prompt="You are a precise evaluator. Return ONLY valid JSON.",
                )

                if not rank_result.ok:
                    logger.warning(
                        f"[{judge_provider.name}] ranking failed: {rank_result.error}"
                    )
                    continue

                parsed = _parse_ranking_json(rank_result.text, responses)
                if not parsed:
                    continue

                # Map parsed scores back to providers
                for i, score_data in enumerate(parsed):
                    if i >= len(responses):
                        break
                    target = responses[i]

                    # Skip self-scoring
                    if target.provider_name == judge_provider.name:
                        continue

                    score = RankingScore(
                        judge=judge_provider.name,
                        target=target.provider_name,
                        accuracy=float(score_data.get("accuracy", 5)),
                        completeness=float(score_data.get("completeness", 5)),
                        clarity=float(score_data.get("clarity", 5)),
                        relevance=float(score_data.get("relevance", 5)),
                    )
                    all_scores[target.provider_name].append(score)

            except Exception as e:
                logger.warning(f"[{judge_provider.name}] ranking error: {e}")
                continue

        # Aggregate scores
        ranked: List[RankedResponse] = []
        for r in responses:
            scores = all_scores.get(r.provider_name, [])
            if scores:
                avg = sum(s.average for s in scores) / len(scores)
            else:
                # No external scores — default to neutral
                avg = 5.0

            ranked.append(RankedResponse(
                provider_name=r.provider_name,
                model=r.model,
                text=r.text,
                latency_ms=r.latency_ms,
                aggregate_score=round(avg, 2),
                individual_scores=scores,
            ))

        # Sort by score descending, then by latency ascending (tiebreaker)
        ranked.sort(key=lambda x: (-x.aggregate_score, x.latency_ms))

        # Assign ranks
        for i, r in enumerate(ranked):
            r.rank = i + 1

        return ranked

    def generate_fn(self) -> Callable[[str], str]:
        """Return a simple string→string function for backward compat."""
        def _fn(prompt: str, **kwargs) -> str:
            result = self.query(prompt, **kwargs)
            return result.best_response if result.ok else f"[Council Error: {result.error}]"
        return _fn

    def get_stats(self) -> dict:
        return {
            "council_size": self.size,
            "is_council_mode": self.is_council_mode,
            "total_queries": self._query_count,
            "providers": [
                {
                    "name": p.name,
                    "model": p.model,
                    "calls": p._call_count,
                    "errors": p._errors,
                }
                for p in self.providers
            ],
        }
