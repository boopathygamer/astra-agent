"""
Pattern Library — Reusable Coding Pattern Storage & Retrieval.
──────────────────────────────────────────────────────────────
Stores solutions as reusable patterns that the solver recalls
when tackling similar problems. Enables cross-problem learning.

Features:
  - Store patterns with metadata (tags, complexity, category)
  - Search by keyword similarity
  - Suggest patterns for new problems
  - JSON file persistence
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class CodingPattern:
    """A reusable coding pattern."""
    name: str = ""
    description: str = ""
    category: str = "general"      # sorting, graph, dp, string, etc.
    template: str = ""             # Code template
    complexity: str = ""           # e.g., "O(n log n)"
    tags: List[str] = field(default_factory=list)
    usage_count: int = 0
    success_rate: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0

    def match_score(self, query: str) -> float:
        """How well does this pattern match a query? (0-1)"""
        query_lower = query.lower()
        score = 0.0

        # Name match
        if self.name.lower() in query_lower:
            score += 0.3

        # Description word overlap
        desc_words = set(self.description.lower().split())
        query_words = set(query_lower.split())
        overlap = desc_words & query_words
        if desc_words:
            score += 0.3 * (len(overlap) / max(len(desc_words), 1))

        # Category match
        if self.category.lower() in query_lower:
            score += 0.2

        # Tag match
        matching_tags = [t for t in self.tags if t.lower() in query_lower]
        if self.tags:
            score += 0.2 * (len(matching_tags) / max(len(self.tags), 1))

        return min(score, 1.0)


# ──────────────────────────────────────────────
# Built-in Patterns
# ──────────────────────────────────────────────

_BUILTIN_PATTERNS = [
    CodingPattern(
        name="two_pointer",
        description="Two pointer technique for sorted arrays",
        category="array",
        template=(
            "def two_pointer(arr, target):\n"
            "    left, right = 0, len(arr) - 1\n"
            "    while left < right:\n"
            "        total = arr[left] + arr[right]\n"
            "        if total == target:\n"
            "            return (left, right)\n"
            "        elif total < target:\n"
            "            left += 1\n"
            "        else:\n"
            "            right -= 1\n"
            "    return None"
        ),
        complexity="O(n)",
        tags=["array", "sorted", "pair", "sum", "two pointer"],
    ),
    CodingPattern(
        name="sliding_window",
        description="Sliding window for contiguous subarray problems",
        category="array",
        template=(
            "def sliding_window(arr, k):\n"
            "    window_sum = sum(arr[:k])\n"
            "    best = window_sum\n"
            "    for i in range(k, len(arr)):\n"
            "        window_sum += arr[i] - arr[i - k]\n"
            "        best = max(best, window_sum)\n"
            "    return best"
        ),
        complexity="O(n)",
        tags=["array", "subarray", "window", "contiguous", "maximum"],
    ),
    CodingPattern(
        name="binary_search",
        description="Binary search for sorted collections",
        category="searching",
        template=(
            "def binary_search(arr, target):\n"
            "    lo, hi = 0, len(arr) - 1\n"
            "    while lo <= hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        elif arr[mid] < target:\n"
            "            lo = mid + 1\n"
            "        else:\n"
            "            hi = mid - 1\n"
            "    return -1"
        ),
        complexity="O(log n)",
        tags=["search", "binary", "sorted", "find", "lookup"],
    ),
    CodingPattern(
        name="bfs_graph",
        description="Breadth-first search for graphs",
        category="graph",
        template=(
            "from collections import deque\n\n"
            "def bfs(graph, start):\n"
            "    visited = set([start])\n"
            "    queue = deque([start])\n"
            "    while queue:\n"
            "        node = queue.popleft()\n"
            "        for neighbor in graph[node]:\n"
            "            if neighbor not in visited:\n"
            "                visited.add(neighbor)\n"
            "                queue.append(neighbor)\n"
            "    return visited"
        ),
        complexity="O(V + E)",
        tags=["graph", "bfs", "traverse", "shortest", "level"],
    ),
    CodingPattern(
        name="dfs_graph",
        description="Depth-first search for graphs",
        category="graph",
        template=(
            "def dfs(graph, start, visited=None):\n"
            "    if visited is None:\n"
            "        visited = set()\n"
            "    visited.add(start)\n"
            "    for neighbor in graph[start]:\n"
            "        if neighbor not in visited:\n"
            "            dfs(graph, neighbor, visited)\n"
            "    return visited"
        ),
        complexity="O(V + E)",
        tags=["graph", "dfs", "traverse", "path", "cycle"],
    ),
    CodingPattern(
        name="memoization_dp",
        description="Top-down dynamic programming with memoization",
        category="dynamic_programming",
        template=(
            "from functools import lru_cache\n\n"
            "def solve(n):\n"
            "    @lru_cache(maxsize=None)\n"
            "    def dp(state):\n"
            "        # Base case\n"
            "        if state == 0:\n"
            "            return 0\n"
            "        # Recursive case\n"
            "        return min(dp(state - 1) + cost for cost in options)\n"
            "    return dp(n)"
        ),
        complexity="Depends on state space",
        tags=["dp", "dynamic", "memoization", "recursive", "optimize"],
    ),
    CodingPattern(
        name="merge_sort",
        description="Merge sort — divide and conquer sorting",
        category="sorting",
        template=(
            "def merge_sort(arr):\n"
            "    if len(arr) <= 1:\n"
            "        return arr\n"
            "    mid = len(arr) // 2\n"
            "    left = merge_sort(arr[:mid])\n"
            "    right = merge_sort(arr[mid:])\n"
            "    return merge(left, right)\n\n"
            "def merge(left, right):\n"
            "    result = []\n"
            "    i = j = 0\n"
            "    while i < len(left) and j < len(right):\n"
            "        if left[i] <= right[j]:\n"
            "            result.append(left[i]); i += 1\n"
            "        else:\n"
            "            result.append(right[j]); j += 1\n"
            "    result.extend(left[i:])\n"
            "    result.extend(right[j:])\n"
            "    return result"
        ),
        complexity="O(n log n)",
        tags=["sort", "merge", "divide", "conquer", "stable"],
    ),
    CodingPattern(
        name="hash_map_counter",
        description="Use hash map for counting/frequency problems",
        category="data_structure",
        template=(
            "from collections import Counter\n\n"
            "def frequency_analysis(arr):\n"
            "    counts = Counter(arr)\n"
            "    most_common = counts.most_common(1)[0]\n"
            "    return most_common"
        ),
        complexity="O(n)",
        tags=["hash", "map", "counter", "frequency", "count"],
    ),
    CodingPattern(
        name="stack_parsing",
        description="Stack-based parsing for brackets/expressions",
        category="data_structure",
        template=(
            "def is_valid_brackets(s):\n"
            "    stack = []\n"
            "    pairs = {'(': ')', '[': ']', '{': '}'}\n"
            "    for char in s:\n"
            "        if char in pairs:\n"
            "            stack.append(char)\n"
            "        elif stack and pairs.get(stack[-1]) == char:\n"
            "            stack.pop()\n"
            "        else:\n"
            "            return False\n"
            "    return not stack"
        ),
        complexity="O(n)",
        tags=["stack", "brackets", "parse", "validate", "expression"],
    ),
    CodingPattern(
        name="backtracking",
        description="Backtracking template for constraint satisfaction",
        category="algorithm",
        template=(
            "def backtrack(path, choices):\n"
            "    if is_solution(path):\n"
            "        results.append(path[:])\n"
            "        return\n"
            "    for choice in choices:\n"
            "        if is_valid(path, choice):\n"
            "            path.append(choice)\n"
            "            backtrack(path, choices)\n"
            "            path.pop()  # undo choice"
        ),
        complexity="O(n!)",
        tags=["backtrack", "permutation", "combination", "constraint", "recursive"],
    ),
]


# ──────────────────────────────────────────────
# Pattern Library Engine
# ──────────────────────────────────────────────

class PatternLibrary:
    """
    Storage and retrieval system for reusable coding patterns.

    Features:
      - 10 built-in patterns (two pointer, sliding window, BFS, etc.)
      - Store new patterns from successful solutions
      - Search by keyword similarity
      - Suggest patterns for a problem
      - Persist to JSON file
    """

    def __init__(self, persist_path: Optional[str] = None):
        self._patterns: Dict[str, CodingPattern] = {}
        self._persist_path = persist_path

        # Load built-in patterns
        for p in _BUILTIN_PATTERNS:
            self._patterns[p.name] = p

        # Load user patterns from disk
        if persist_path:
            self._load(persist_path)

        logger.info(
            f"PatternLibrary initialized with {len(self._patterns)} patterns"
        )

    def __len__(self) -> int:
        return len(self._patterns)

    def store(self, pattern: CodingPattern) -> None:
        """Store a coding pattern."""
        self._patterns[pattern.name] = pattern
        logger.info(f"Pattern stored: {pattern.name} ({pattern.category})")

        if self._persist_path:
            self._save()

    def search(self, query: str, top_k: int = 5) -> List[CodingPattern]:
        """Search for patterns matching a query."""
        if not query:
            return []

        scored = [
            (p, p.match_score(query))
            for p in self._patterns.values()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Return top matches above threshold
        results = [p for p, s in scored[:top_k] if s > 0.1]

        if results:
            logger.debug(
                f"Pattern search '{query[:40]}': found {len(results)} matches"
            )
        return results

    def suggest(self, problem: str) -> List[CodingPattern]:
        """Suggest patterns for a coding problem."""
        suggestions = self.search(problem, top_k=3)

        # Update usage tracking
        for p in suggestions:
            p.usage_count += 1
            p.last_used = time.time()

        return suggestions

    def get(self, name: str) -> Optional[CodingPattern]:
        """Get a specific pattern by name."""
        return self._patterns.get(name)

    def list_all(self) -> List[CodingPattern]:
        """List all stored patterns."""
        return list(self._patterns.values())

    def list_categories(self) -> Dict[str, int]:
        """List all categories with counts."""
        cats: Dict[str, int] = {}
        for p in self._patterns.values():
            cats[p.category] = cats.get(p.category, 0) + 1
        return cats

    def _save(self) -> None:
        """Save patterns to JSON file."""
        if not self._persist_path:
            return
        try:
            data = {
                name: asdict(p)
                for name, p in self._patterns.items()
                if name not in {bp.name for bp in _BUILTIN_PATTERNS}
            }
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save patterns: {e}")

    def _load(self, path: str) -> None:
        """Load patterns from JSON file."""
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            for name, pdata in data.items():
                self._patterns[name] = CodingPattern(**pdata)
            logger.info(f"Loaded {len(data)} user patterns from {path}")
        except Exception as e:
            logger.warning(f"Failed to load patterns: {e}")
