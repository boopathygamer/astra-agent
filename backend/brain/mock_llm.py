"""
Mock LLM — Production-Quality Deterministic Mock for Offline Testing.
═══════════════════════════════════════════════════════════════════════

Strategy-aware mock that handles all prompt patterns used by the brain
subsystems. Returns structured, parseable responses that exercise real
logic in the reasoning engine, verifier, hypothesis engine, and more.

Usage:
    from brain.mock_llm import MockLLM
    mock = MockLLM(quality="high")
    result = mock.generate("Break this problem into sub-problems...")
"""

import hashlib
import random
import re
import time
from typing import Dict, List, Optional


class MockLLM:
    """Deterministic mock LLM with strategy-aware responses.

    Matches prompt patterns against known brain subsystem formats and
    returns structured responses that exercise the real parsing/scoring
    logic in each module.

    Quality levels:
        "high"   — Returns well-structured, correct-looking answers (score ~7-9)
        "medium" — Returns adequate answers with minor issues (score ~5-7)
        "low"    — Returns poor answers to test failure/retry paths (score ~2-4)
    """

    def __init__(self, quality: str = "high", latency_ms: float = 0.0,
                 seed: int = 42):
        self.quality = quality
        self.latency_ms = latency_ms
        self._rng = random.Random(seed)
        self._call_count = 0
        self._call_log: List[Dict] = []

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a deterministic response based on prompt patterns."""
        if self.latency_ms > 0:
            time.sleep(self.latency_ms / 1000)

        self._call_count += 1
        response = self._dispatch(prompt)
        self._call_log.append({
            "call_id": self._call_count,
            "prompt_snippet": prompt[:120],
            "response_snippet": response[:120],
            "quality": self.quality,
        })
        return response

    def __call__(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs)

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset(self):
        self._call_count = 0
        self._call_log.clear()

    # ─────────────────────────────────────────────
    # Prompt Pattern Dispatch
    # ─────────────────────────────────────────────

    def _dispatch(self, prompt: str) -> str:
        p = prompt.lower()

        # Reasoning Engine patterns
        if "break this problem into" in p or "sub-problems" in p or "sub_problem" in p:
            return self._decompose_response(prompt)
        if "find 2-3 analogous" in p or "analogy" in p:
            return self._analogize_response(prompt)
        if "abstract to general pattern" in p:
            return self._abstract_response(prompt)
        if "mentally execute" in p or "step-by-step" in p and "state" in p:
            return self._simulate_response(prompt)
        if "solve with fresh approach" in p:
            return self._backtrack_response(prompt)
        if "adapt best analogy" in p:
            return self._adapt_analogy_response(prompt)
        if "solve abstract pattern" in p:
            return self._solve_abstract_response(prompt)
        if "concretize solution" in p:
            return self._concretize_response(prompt)
        if "synthesize final answer" in p or "sub-solutions" in p:
            return self._synthesize_response(prompt)
        if "solve sub-problem" in p:
            return self._solve_subproblem_response(prompt)

        # Mode selection
        if "choose one mode" in p or "best_mode" in p:
            return self._mode_selection_response(prompt)

        # Verifier patterns
        if "overall_score" in p or "score 0-10" in p:
            return self._scoring_response(prompt)
        if "edge case" in p or "property test" in p:
            return self._edge_case_response(prompt)
        if "critic" in p and ("review" in p or "flaw" in p):
            return self._critic_response(prompt)
        if "regression" in p or "scenario test" in p:
            return self._scenario_response(prompt)

        # Hypothesis Engine
        if "generate" in p and "hypothes" in p:
            return self._hypothesis_response(prompt)
        if "synthesize" in p and ("hypothesis" in p or "weighted" in p):
            return self._hypothesis_synthesis_response(prompt)

        # Problem Classifier
        if "classify" in p and ("domain" in p or "problem" in p):
            return self._classify_response(prompt)

        # Metacognition
        if "reflect" in p and ("solve" in p or "learn" in p):
            return self._reflection_response(prompt)

        # Credit Assignment
        if "credit" in p or "helpful" in p and "step" in p:
            return self._credit_response(prompt)

        # Prompt Evolution
        if "improve" in p and "prompt" in p:
            return self._prompt_evolution_response(prompt)

        # Expert Reflection
        if "first principle" in p or "root cause" in p:
            return self._expert_reflection_response(prompt)

        # Epistemic check
        if "fact" in p and "check" in p:
            return self._epistemic_response(prompt)

        # Fallback: generic response
        return self._generic_response(prompt)

    # ─────────────────────────────────────────────
    # Reasoning Engine Responses
    # ─────────────────────────────────────────────

    def _decompose_response(self, prompt: str) -> str:
        return (
            "SUB_PROBLEM 1: Understand the input format and constraints\n"
            "DEPENDS_ON: none\n\n"
            "SUB_PROBLEM 2: Design the core algorithm\n"
            "DEPENDS_ON: 1\n\n"
            "SUB_PROBLEM 3: Implement edge case handling\n"
            "DEPENDS_ON: 1, 2\n"
        )

    def _solve_subproblem_response(self, prompt: str) -> str:
        scores = {"high": "complete", "medium": "adequate", "low": "partial"}
        level = scores.get(self.quality, "adequate")
        return (
            f"Solution ({level}): The sub-problem is resolved by applying "
            f"structured analysis. We validate input types, check boundary "
            f"conditions, and apply the appropriate transformation. "
            f"The implementation uses O(n) time and O(1) extra space."
        )

    def _analogize_response(self, prompt: str) -> str:
        return (
            "ANALOGY 1: Binary Search\n"
            "SIMILARITY: Both problems involve narrowing a search space\n"
            "KNOWN_SOLUTION: Divide and conquer with logarithmic convergence\n\n"
            "ANALOGY 2: Hash Table Lookup\n"
            "SIMILARITY: Both need efficient key-value mapping\n"
            "KNOWN_SOLUTION: Use hash function for O(1) average-case lookup\n"
        )

    def _adapt_analogy_response(self, prompt: str) -> str:
        return (
            "Adapted solution: By combining the divide-and-conquer approach "
            "from binary search with efficient hashing, we can solve this in "
            "O(n log n) time. First sort the data, then use binary search on "
            "the sorted result for each query."
        )

    def _abstract_response(self, prompt: str) -> str:
        return (
            "ABSTRACT_PATTERN: Search-and-Transform Pipeline\n"
            "PATTERN_TYPE: Map-Filter-Reduce\n"
            "The core pattern is: iterate over elements, filter by predicate, "
            "transform matching elements, aggregate results."
        )

    def _solve_abstract_response(self, prompt: str) -> str:
        return (
            "Abstract solution: Apply a three-stage pipeline:\n"
            "1. MAP: Transform each input element\n"
            "2. FILTER: Keep only elements meeting criteria\n"
            "3. REDUCE: Aggregate filtered results to final answer"
        )

    def _concretize_response(self, prompt: str) -> str:
        return (
            "Concrete implementation:\n"
            "def solve(data):\n"
            "    mapped = [transform(x) for x in data]\n"
            "    filtered = [x for x in mapped if predicate(x)]\n"
            "    return aggregate(filtered)\n"
        )

    def _simulate_response(self, prompt: str) -> str:
        if self.quality == "high":
            return (
                "STATE_0: initial — input received, no processing done\n"
                "STEP_1: Parse input into structured format -> STATE_1: parsed\n"
                "STEP_2: Apply core algorithm -> STATE_2: computed\n"
                "STEP_3: Validate output constraints -> STATE_3: validated\n"
                "ERRORS_FOUND: None — all states transition correctly\n"
                "CORRECTED_SOLUTION: The solution is correct as proposed. "
                "It handles edge cases and produces valid output."
            )
        else:
            return (
                "STATE_0: initial\n"
                "STEP_1: Process -> STATE_1: partial\n"
                "ERRORS_FOUND: Potential issue with empty input\n"
                "The solution needs an edge case check."
            )

    def _backtrack_response(self, prompt: str) -> str:
        scores = {"high": "8", "medium": "6", "low": "3"}
        score = scores.get(self.quality, "6")
        if "failed" in prompt.lower():
            return (
                "Taking a completely different approach: Use dynamic programming "
                "instead of the recursive approach that failed. Build solution "
                "bottom-up with memoization table."
            )
        return (
            "Fresh approach: Apply greedy algorithm with local optimization. "
            "Sort elements by priority, then select optimally at each step."
        )

    def _synthesize_response(self, prompt: str) -> str:
        return (
            "Final synthesized answer: Combining all sub-solutions, the "
            "complete approach is:\n"
            "1. Parse and validate input (from sub-problem 1)\n"
            "2. Apply the core O(n log n) algorithm (from sub-problem 2)\n"
            "3. Handle edge cases: empty input, single element, duplicates "
            "(from sub-problem 3)\n\n"
            "The solution achieves optimal time complexity with robust "
            "error handling."
        )

    def _mode_selection_response(self, prompt: str) -> str:
        p = prompt.lower()
        if "math" in p or "calculat" in p or "equation" in p:
            return "BEST_MODE: DECOMPOSE"
        if "sort" in p or "search" in p or "algorithm" in p:
            return "BEST_MODE: SIMULATE"
        if "debug" in p or "fix" in p or "error" in p:
            return "BEST_MODE: BACKTRACK"
        if "design" in p or "architect" in p:
            return "BEST_MODE: ABSTRACT"
        return "BEST_MODE: DECOMPOSE"

    # ─────────────────────────────────────────────
    # Verifier Responses
    # ─────────────────────────────────────────────

    def _scoring_response(self, prompt: str) -> str:
        scores = {"high": "8", "medium": "6", "low": "3"}
        verdicts = {"high": "accept", "medium": "accept", "low": "reject"}
        score = scores.get(self.quality, "6")
        verdict = verdicts.get(self.quality, "accept")
        return (
            f"OVERALL_SCORE: {score}\n"
            f"Analysis: The solution demonstrates good structure and handles "
            f"the main cases effectively.\n"
            f"VERDICT: {verdict}\n"
            f"SCORE: {score}"
        )

    def _edge_case_response(self, prompt: str) -> str:
        return (
            "Edge cases to test:\n"
            "1. Empty input → should return default/empty\n"
            "2. Single element → no processing needed\n"
            "3. Very large input (10^6) → check time limits\n"
            "4. Negative numbers → ensure sign handling\n"
            "5. Duplicate values → verify uniqueness handling\n\n"
            "OVERALL_SCORE: 7\n"
        )

    def _critic_response(self, prompt: str) -> str:
        scores = {"high": "8", "medium": "5", "low": "3"}
        score = scores.get(self.quality, "5")
        return (
            f"Critic Analysis:\n"
            f"Strengths: Clear structure, handles main cases well.\n"
            f"Weaknesses: Could improve error messages, limited documentation.\n"
            f"OVERALL_SCORE: {score}\n"
        )

    def _scenario_response(self, prompt: str) -> str:
        return (
            "Scenario test results:\n"
            "1. Happy path: PASS\n"
            "2. Error recovery: PASS\n"
            "3. Boundary conditions: PASS\n\n"
            "OVERALL_SCORE: 7\n"
        )

    # ─────────────────────────────────────────────
    # Hypothesis Engine Responses
    # ─────────────────────────────────────────────

    def _hypothesis_response(self, prompt: str) -> str:
        return (
            "HYPOTHESIS 1:\n"
            "Description: Use iterative approach with explicit stack\n"
            "Approach: Replace recursion with iteration for better space\n"
            "Assumptions: Input fits in memory, no circular references\n\n"
            "HYPOTHESIS 2:\n"
            "Description: Use divide-and-conquer strategy\n"
            "Approach: Split problem in half, solve recursively, merge\n"
            "Assumptions: Problem has optimal substructure\n\n"
            "HYPOTHESIS 3:\n"
            "Description: Use dynamic programming with memoization\n"
            "Approach: Cache intermediate results, build bottom-up\n"
            "Assumptions: Overlapping subproblems exist\n"
        )

    def _hypothesis_synthesis_response(self, prompt: str) -> str:
        return (
            "Synthesized solution combining best aspects of all hypotheses:\n"
            "Use an iterative bottom-up dynamic programming approach. "
            "This combines the space efficiency of iteration (H1) with the "
            "structural decomposition of divide-and-conquer (H2) and the "
            "memoization benefits of DP (H3).\n\n"
            "Implementation uses O(n) time and O(n) space with a simple "
            "table-filling loop."
        )

    # ─────────────────────────────────────────────
    # Classifier, Metacognition, and Learning
    # ─────────────────────────────────────────────

    def _classify_response(self, prompt: str) -> str:
        p = prompt.lower()
        if "code" in p or "function" in p or "implement" in p:
            return "DOMAIN: coding"
        if "debug" in p or "fix" in p or "error" in p:
            return "DOMAIN: debugging"
        if "math" in p or "equation" in p or "proof" in p:
            return "DOMAIN: math"
        if "sort" in p or "search" in p or "graph" in p:
            return "DOMAIN: algorithm"
        return "DOMAIN: general"

    def _reflection_response(self, prompt: str) -> str:
        return (
            "Reflection:\n"
            "KEY_INSIGHT: The decomposition approach was most effective "
            "because it allowed systematic verification of each component.\n"
            "DIFFICULTY: medium\n"
            "WHAT_WORKED: Breaking the problem into testable sub-problems\n"
            "WHAT_FAILED: Initial attempt at a monolithic solution was fragile\n"
            "NEXT_TIME: Start with decomposition for complex problems"
        )

    def _credit_response(self, prompt: str) -> str:
        return (
            "Credit Assignment:\n"
            "STEP 1 (Classification): HELPFUL — guided strategy selection\n"
            "STEP 2 (Reasoning): VERY_HELPFUL — produced core solution structure\n"
            "STEP 3 (Verification): HELPFUL — caught edge case issues\n"
            "MOST_IMPACTFUL: Step 2 (Reasoning)"
        )

    def _prompt_evolution_response(self, prompt: str) -> str:
        return (
            "Improved prompt: You are an expert problem solver. "
            "Break the problem into small, testable components. "
            "For each component: state the goal, list constraints, "
            "propose a solution, and verify it works on edge cases. "
            "Show your reasoning step by step."
        )

    def _expert_reflection_response(self, prompt: str) -> str:
        if "root cause" in prompt.lower():
            return (
                "Root Cause Analysis:\n"
                "The failure stemmed from insufficient input validation. "
                "The solution assumed well-formed input but received edge "
                "cases that violated preconditions. Fix: add defensive "
                "checks at function entry points."
            )
        return (
            "First Principle Extracted:\n"
            "PRINCIPLE: Always validate inputs before processing\n"
            "DOMAIN: general\n"
            "EVIDENCE: Solutions that include input validation consistently "
            "score higher in verification and handle edge cases correctly."
        )

    def _epistemic_response(self, prompt: str) -> str:
        return (
            "FACT_CHECK: PASS\n"
            "All claims in the response are supported by the reasoning chain. "
            "No hallucinated facts detected."
        )

    # ─────────────────────────────────────────────
    # Generic Fallback
    # ─────────────────────────────────────────────

    def _generic_response(self, prompt: str) -> str:
        # Use prompt hash for deterministic but varied responses
        h = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
        templates = [
            "Based on analysis, the optimal approach is to decompose the "
            "problem into manageable components, verify each independently, "
            "and synthesize the final solution.",

            "The solution involves three key steps: (1) parse and validate "
            "the input, (2) apply the core transformation, (3) verify the "
            "output meets all constraints.",

            "After careful consideration, the best approach uses an "
            "iterative algorithm with O(n) time complexity and constant "
            "space overhead.",
        ]
        return templates[h % len(templates)]
