"""
Cross-Pollination Memory — Inter-Domain Knowledge Transfer
───────────────────────────────────────────────────────────
Applies solutions from one domain to analogous problems in another.
"Binary search in arrays" → "Divide and conquer on ordered structures" → 
"Bisection method in numerical analysis"

Architecture:
  DomainAbstractor  →  AnalogyFinder  →  PollinationEngine
  (extract patterns)    (find matches)    (adapt & apply)
"""

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class AbstractPattern:
    """A domain-independent abstract pattern extracted from a solution."""
    pattern_id: str = ""
    name: str = ""
    description: str = ""
    source_domain: str = ""
    abstract_strategy: str = ""     # Domain-independent description
    key_properties: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    applicability_keywords: Set[str] = field(default_factory=set)
    usage_count: int = 0
    success_rate: float = 0.0

    def __post_init__(self):
        if not self.pattern_id:
            self.pattern_id = hashlib.sha256(
                f"{self.name}{self.source_domain}".encode()
            ).hexdigest()[:12]


@dataclass
class TransferRecord:
    """Records a successful cross-domain knowledge transfer."""
    transfer_id: str = ""
    source_domain: str = ""
    target_domain: str = ""
    source_pattern: str = ""
    target_adaptation: str = ""
    similarity_score: float = 0.0
    success: bool = False
    adaptation_notes: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.transfer_id:
            self.transfer_id = hashlib.sha256(
                f"{self.source_domain}{self.target_domain}{time.time()}".encode()
            ).hexdigest()[:12]
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class Analogy:
    """A discovered analogy between two domain-specific concepts."""
    source_concept: str
    target_concept: str
    source_domain: str
    target_domain: str
    shared_pattern: AbstractPattern
    similarity: float = 0.0
    adaptation_hints: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# Domain Abstractor
# ──────────────────────────────────────────────

class DomainAbstractor:
    """
    Extracts domain-independent abstract patterns from domain-specific solutions.
    E.g., "binary search" → "divide and conquer on ordered structures"
    """

    # Built-in pattern library keyed by abstraction name
    CORE_PATTERNS = {
        "divide_and_conquer": AbstractPattern(
            name="Divide and Conquer",
            abstract_strategy="Split problem into smaller subproblems, solve each, combine results",
            key_properties=["decomposable", "independent_subproblems", "combinable_results"],
            preconditions=["problem_is_divisible"],
            applicability_keywords={"binary search", "merge sort", "quicksort", "bisection",
                                    "split", "divide", "partition", "half"},
        ),
        "memoization": AbstractPattern(
            name="Memoization / Caching",
            abstract_strategy="Cache results of expensive computations for reuse",
            key_properties=["overlapping_subproblems", "deterministic"],
            preconditions=["repeated_computations", "pure_function"],
            applicability_keywords={"cache", "memoize", "dynamic programming", "dp",
                                    "store result", "lookup table", "fibonacci"},
        ),
        "producer_consumer": AbstractPattern(
            name="Producer-Consumer Pipeline",
            abstract_strategy="Decouple production and consumption with a buffer",
            key_properties=["async", "buffered", "rate_independent"],
            preconditions=["different_rates", "independent_stages"],
            applicability_keywords={"queue", "buffer", "pipeline", "stream",
                                    "producer", "consumer", "channel"},
        ),
        "observer": AbstractPattern(
            name="Observer / Pub-Sub",
            abstract_strategy="Notify interested parties when state changes",
            key_properties=["loose_coupling", "one_to_many", "event_driven"],
            preconditions=["state_changes", "multiple_dependents"],
            applicability_keywords={"event", "listener", "callback", "subscribe",
                                    "notify", "watch", "trigger", "hook"},
        ),
        "backtracking": AbstractPattern(
            name="Backtracking / Exploration",
            abstract_strategy="Explore solution space, undo choices that fail",
            key_properties=["reversible", "constraint_satisfaction"],
            preconditions=["discrete_choices", "testable_constraints"],
            applicability_keywords={"backtrack", "try", "undo", "constraint",
                                    "permutation", "combination", "puzzle", "sudoku"},
        ),
        "gradient_descent": AbstractPattern(
            name="Iterative Local Optimization",
            abstract_strategy="Repeatedly adjust parameters toward better solution",
            key_properties=["continuous", "differentiable", "convergent"],
            preconditions=["measurable_quality", "adjustable_params"],
            applicability_keywords={"optimize", "gradient", "converge", "loss",
                                    "minimize", "maximize", "tune", "calibrate"},
        ),
        "consensus": AbstractPattern(
            name="Majority Consensus",
            abstract_strategy="Multiple independent agents vote on the answer",
            key_properties=["redundancy", "fault_tolerant", "independent"],
            preconditions=["multiple_sources", "comparable_outputs"],
            applicability_keywords={"vote", "consensus", "majority", "ensemble",
                                    "quorum", "agree", "committee"},
        ),
        "layered_defense": AbstractPattern(
            name="Defense in Depth",
            abstract_strategy="Multiple independent layers of protection",
            key_properties=["redundant_checks", "independent_layers"],
            preconditions=["security_critical", "multiple_attack_vectors"],
            applicability_keywords={"validate", "sanitize", "verify", "check",
                                    "firewall", "guard", "filter", "defense"},
        ),
    }

    def __init__(self, generate_fn: Optional[Callable] = None):
        self._generate_fn = generate_fn
        self._learned_patterns: Dict[str, AbstractPattern] = {}

    def abstract(self, solution_description: str, domain: str) -> List[AbstractPattern]:
        """Extract abstract patterns from a domain-specific solution."""
        matches = []
        desc_lower = solution_description.lower()

        # Match against core patterns
        for pat_id, pattern in {**self.CORE_PATTERNS, **self._learned_patterns}.items():
            keyword_hits = sum(
                1 for kw in pattern.applicability_keywords
                if kw in desc_lower
            )
            if keyword_hits >= 1:
                # Clone with source domain
                matched = AbstractPattern(
                    name=pattern.name,
                    abstract_strategy=pattern.abstract_strategy,
                    source_domain=domain,
                    key_properties=pattern.key_properties[:],
                    preconditions=pattern.preconditions[:],
                    applicability_keywords=pattern.applicability_keywords.copy(),
                    usage_count=pattern.usage_count + 1,
                )
                matched.pattern_id = pattern.pattern_id or pat_id
                matches.append(matched)

        return matches

    def register_pattern(self, pattern: AbstractPattern):
        """Register a new abstract pattern."""
        self._learned_patterns[pattern.pattern_id] = pattern
        logger.info(f"🧬 Registered new pattern: {pattern.name}")


# ──────────────────────────────────────────────
# Analogy Finder
# ──────────────────────────────────────────────

class AnalogyFinder:
    """
    Given a problem in domain A, searches for structurally similar
    solved problems in domain B by matching abstract patterns.
    """

    def __init__(self):
        self._solution_registry: List[Dict[str, Any]] = []

    def register_solution(self, domain: str, problem: str, solution: str,
                          patterns: List[AbstractPattern]):
        """Register a solved problem with its abstract patterns."""
        self._solution_registry.append({
            "domain": domain,
            "problem": problem,
            "solution": solution,
            "patterns": patterns,
            "pattern_ids": {p.pattern_id for p in patterns},
            "timestamp": time.time(),
        })

    def find_analogies(self, problem_patterns: List[AbstractPattern],
                       target_domain: str, top_k: int = 5) -> List[Analogy]:
        """Find analogous solutions from other domains."""
        query_ids = {p.pattern_id for p in problem_patterns}
        if not query_ids:
            return []

        analogies = []
        for entry in self._solution_registry:
            if entry["domain"] == target_domain:
                continue  # Skip same domain

            # Compute pattern overlap (Jaccard similarity)
            entry_ids = entry["pattern_ids"]
            intersection = query_ids & entry_ids
            union = query_ids | entry_ids

            if not intersection:
                continue

            similarity = len(intersection) / len(union)

            # Find the shared pattern for the analogy
            shared_pattern_id = next(iter(intersection))
            shared_pattern = next(
                (p for p in entry["patterns"] if p.pattern_id == shared_pattern_id),
                problem_patterns[0],
            )

            analogies.append(Analogy(
                source_concept=entry["problem"][:100],
                target_concept="",  # To be filled by caller
                source_domain=entry["domain"],
                target_domain=target_domain,
                shared_pattern=shared_pattern,
                similarity=similarity,
                adaptation_hints=[
                    f"This solution from '{entry['domain']}' used "
                    f"'{shared_pattern.name}' — the same strategy may apply.",
                    f"Key properties to preserve: {', '.join(shared_pattern.key_properties[:3])}",
                ],
            ))

        analogies.sort(key=lambda a: a.similarity, reverse=True)
        return analogies[:top_k]


# ──────────────────────────────────────────────
# Pollination Engine (Main Interface)
# ──────────────────────────────────────────────

class PollinationEngine:
    """
    Orchestrates cross-domain knowledge transfer.

    Usage:
        engine = PollinationEngine()

        # Register solved problems
        engine.register_solution(
            domain="algorithms",
            problem="Find element in sorted array",
            solution="Binary search with O(log n)",
        )

        # Find cross-domain insights for a new problem
        insights = engine.find_cross_domain_insights(
            problem="Find optimal parameter in continuous space",
            domain="optimization",
        )
        # Returns: analogy to binary search → bisection method
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.abstractor = DomainAbstractor(generate_fn=generate_fn)
        self.finder = AnalogyFinder()
        self._transfers: List[TransferRecord] = []

    def register_solution(self, domain: str, problem: str, solution: str):
        """Register a solved problem for future cross-pollination."""
        patterns = self.abstractor.abstract(solution, domain)
        if patterns:
            self.finder.register_solution(domain, problem, solution, patterns)
            logger.debug(
                f"🧬 Registered solution in '{domain}': "
                f"{len(patterns)} patterns extracted"
            )

    def find_cross_domain_insights(
        self,
        problem: str,
        domain: str,
        top_k: int = 3,
    ) -> List[Analogy]:
        """Find insights from other domains that might apply to this problem."""
        # Extract abstract patterns from the new problem
        patterns = self.abstractor.abstract(problem, domain)
        if not patterns:
            return []

        # Find analogies from other domains
        analogies = self.finder.find_analogies(patterns, domain, top_k)

        if analogies:
            logger.info(
                f"🧬 Cross-pollination: found {len(analogies)} analogies "
                f"for '{domain}' problem from: "
                f"{', '.join(set(a.source_domain for a in analogies))}"
            )

        return analogies

    def record_transfer(self, source_domain: str, target_domain: str,
                        pattern: str, adaptation: str, success: bool):
        """Record the outcome of a knowledge transfer attempt."""
        record = TransferRecord(
            source_domain=source_domain,
            target_domain=target_domain,
            source_pattern=pattern,
            target_adaptation=adaptation,
            success=success,
        )
        self._transfers.append(record)

    def get_stats(self) -> Dict[str, Any]:
        successful = sum(1 for t in self._transfers if t.success)
        return {
            "registered_solutions": len(self.finder._solution_registry),
            "core_patterns": len(self.abstractor.CORE_PATTERNS),
            "learned_patterns": len(self.abstractor._learned_patterns),
            "total_transfers": len(self._transfers),
            "successful_transfers": successful,
            "transfer_success_rate": round(
                successful / max(len(self._transfers), 1), 4
            ),
            "domains_covered": list(set(
                s["domain"] for s in self.finder._solution_registry
            )),
        }
