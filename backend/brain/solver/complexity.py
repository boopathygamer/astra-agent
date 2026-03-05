"""
Complexity Analyzer — Time & Space Big-O Analysis.
───────────────────────────────────────────────────
Analyzes Python code to determine time and space complexity
using AST analysis of loops, recursion, and data structures.

Features:
  - Detects nested loops and calculates depth
  - Identifies recursion patterns
  - Analyzes data structure usage
  - Suggests optimizations
  - Reports in Big-O notation
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class ComplexityResult:
    """Result of complexity analysis."""
    time_complexity: str = "O(1)"
    space_complexity: str = "O(1)"
    loop_depth: int = 0
    has_recursion: bool = False
    data_structures: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    details: Dict[str, str] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        return f"Time: {self.time_complexity}, Space: {self.space_complexity}"

    def full_report(self) -> str:
        """Detailed analysis report."""
        lines = [
            f"⏱️  Time Complexity:  {self.time_complexity}",
            f"💾 Space Complexity: {self.space_complexity}",
            f"🔄 Loop Depth:      {self.loop_depth}",
            f"🔁 Recursion:       {'Yes' if self.has_recursion else 'No'}",
        ]
        if self.data_structures:
            lines.append(f"📦 Data Structures: {', '.join(self.data_structures)}")
        if self.suggestions:
            lines.append("💡 Suggestions:")
            for s in self.suggestions:
                lines.append(f"   - {s}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Complexity Analyzer Engine
# ──────────────────────────────────────────────

class ComplexityAnalyzer:
    """
    Analyzes code for time and space complexity.

    Analysis methods:
      1. Loop analysis — nested loops → O(n^depth)
      2. Recursion detection — recursive calls → O(2^n) or O(n!)
      3. Data structure analysis — what allocations are made
      4. Algorithm pattern matching — known algorithms
    """

    def __init__(self):
        logger.info("ComplexityAnalyzer initialized")

    def analyze(self, code: str) -> ComplexityResult:
        """
        Analyze code complexity.

        Args:
            code: Python source code to analyze

        Returns:
            ComplexityResult with time/space complexity
        """
        result = ComplexityResult()

        try:
            tree = ast.parse(code)
        except SyntaxError:
            result.time_complexity = "Unknown (syntax error)"
            result.space_complexity = "Unknown (syntax error)"
            return result

        # 1. Analyze loops
        result.loop_depth = self._max_loop_depth(tree)
        result.details["loop_depth"] = str(result.loop_depth)

        # 2. Check for recursion
        result.has_recursion = self._detect_recursion(tree)

        # 3. Analyze data structures
        result.data_structures = self._detect_data_structures(code, tree)

        # 4. Determine time complexity
        result.time_complexity = self._determine_time_complexity(
            tree, code, result.loop_depth, result.has_recursion
        )

        # 5. Determine space complexity
        result.space_complexity = self._determine_space_complexity(
            tree, code, result.data_structures, result.has_recursion
        )

        # 6. Generate optimization suggestions
        result.suggestions = self._suggest_optimizations(result, code)

        logger.debug(
            f"Complexity analysis: {result.time_complexity} time, "
            f"{result.space_complexity} space"
        )
        return result

    def _max_loop_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        """Find maximum loop nesting depth."""
        max_depth = current_depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.For, ast.While)):
                max_depth = max(
                    max_depth,
                    self._max_loop_depth(child, current_depth + 1),
                )
            else:
                max_depth = max(
                    max_depth,
                    self._max_loop_depth(child, current_depth),
                )
        return max_depth

    def _detect_recursion(self, tree: ast.AST) -> bool:
        """Detect if any function calls itself."""
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }

        for func_name, func_node in functions.items():
            for node in ast.walk(func_node):
                if isinstance(node, ast.Call):
                    # Direct recursion
                    if isinstance(node.func, ast.Name) and node.func.id == func_name:
                        return True
                    # Method recursion (self.method())
                    if (isinstance(node.func, ast.Attribute) and
                        node.func.attr == func_name):
                        return True
        return False

    def _detect_data_structures(self, code: str, tree: ast.AST) -> List[str]:
        """Detect data structures used in the code."""
        structures = []

        # Pattern-based detection
        ds_patterns = {
            "List": [r"\[\s*\]", r"list\s*\(", r"\.append\(", r"\.extend\("],
            "Dict": [r"\{\s*\}", r"dict\s*\(", r"defaultdict", r"Counter\s*\("],
            "Set": [r"set\s*\(", r"\.add\(", r"\{.+,.+\}"],
            "Stack": [r"\.append\(.*\.pop\(", r"stack"],
            "Queue": [r"deque\s*\(", r"Queue\s*\(", r"queue"],
            "Heap": [r"heapq\.", r"heappush", r"heappop"],
            "Tree": [r"TreeNode", r"\.left", r"\.right", r"\.children"],
            "Graph": [r"graph\[", r"adjacency", r"neighbors"],
            "Matrix": [r"\[\s*\[", r"matrix", r"grid"],
        }

        for ds_name, patterns in ds_patterns.items():
            for pattern in patterns:
                if re.search(pattern, code):
                    if ds_name not in structures:
                        structures.append(ds_name)
                    break

        return structures

    def _determine_time_complexity(
        self,
        tree: ast.AST,
        code: str,
        loop_depth: int,
        has_recursion: bool,
    ) -> str:
        """Determine time complexity from analysis."""

        # Check for known algorithm patterns first
        if re.search(r"sort\s*\(|sorted\s*\(|merge_sort|quick_sort", code):
            if loop_depth <= 1:
                return "O(n log n)"

        if re.search(r"binary_search|bisect|lo.*hi.*mid", code):
            return "O(log n)"

        # Recursion patterns
        if has_recursion:
            # Check for divide-and-conquer pattern
            if re.search(r"//\s*2|len\([^)]+\)\s*//\s*2|mid", code):
                return "O(n log n)"
            # Check for fibonacci-style double recursion
            func_calls = self._count_recursive_calls(tree)
            if func_calls >= 2:
                return "O(2^n)"
            # Single recursion with linear work
            if loop_depth >= 1:
                return "O(n log n)"
            return "O(n)"

        # Loop-based analysis
        if loop_depth == 0:
            return "O(1)"
        elif loop_depth == 1:
            return "O(n)"
        elif loop_depth == 2:
            return "O(n²)"
        elif loop_depth == 3:
            return "O(n³)"
        else:
            return f"O(n^{loop_depth})"

    def _determine_space_complexity(
        self,
        tree: ast.AST,
        code: str,
        data_structures: List[str],
        has_recursion: bool,
    ) -> str:
        """Determine space complexity."""
        # Check for matrix/2D allocations
        if "Matrix" in data_structures:
            if re.search(r"\[\[.*\]\s*(?:for|*)", code):
                return "O(n²)"

        # Recursion adds stack space
        if has_recursion:
            if "Matrix" in data_structures or "Graph" in data_structures:
                return "O(n²)"
            return "O(n)"

        # Significant data structure allocation
        if any(ds in data_structures for ds in ["List", "Dict", "Set"]):
            return "O(n)"

        if data_structures:
            return "O(n)"

        return "O(1)"

    def _count_recursive_calls(self, tree: ast.AST) -> int:
        """Count number of recursive calls in a function."""
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }

        max_calls = 0
        for func_name, func_node in functions.items():
            calls = 0
            for node in ast.walk(func_node):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == func_name:
                        calls += 1
            max_calls = max(max_calls, calls)

        return max_calls

    def _suggest_optimizations(
        self, result: ComplexityResult, code: str
    ) -> List[str]:
        """Generate optimization suggestions."""
        suggestions = []

        # High loop depth
        if result.loop_depth >= 3:
            suggestions.append(
                "Consider reducing nested loops with hash maps or sorting"
            )

        # Inefficient patterns
        if result.loop_depth >= 2 and "Dict" not in result.data_structures:
            suggestions.append(
                "Using a hash map could reduce O(n²) lookups to O(n)"
            )

        if result.has_recursion and "lru_cache" not in code and "memo" not in code.lower():
            suggestions.append(
                "Add memoization (@lru_cache) to avoid redundant calculations"
            )

        if "O(n²)" in result.time_complexity or "O(n³)" in result.time_complexity:
            suggestions.append(
                "Look for sorting-based or two-pointer approaches to reduce complexity"
            )

        if ".append(" in code and "deque" not in code:
            if result.loop_depth >= 2:
                suggestions.append(
                    "Consider using collections.deque for O(1) append/popleft"
                )

        if "in " in code and "set(" not in code and result.loop_depth >= 1:
            suggestions.append(
                "Use set() for O(1) membership checks instead of list 'in'"
            )

        return suggestions
