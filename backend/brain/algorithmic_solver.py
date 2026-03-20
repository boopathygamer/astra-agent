"""
Algorithmic Solver Pipeline — CPU-Only Problem Solvers
══════════════════════════════════════════════════════
Multi-strategy solver that handles math, code, logic, extraction,
and planning problems using pure algorithms — no neural networks.

Solvers:
  • MathSolver    — Symbolic arithmetic, algebra, statistics
  • CodeSolver    — AST analysis, pattern-based code generation
  • LogicSolver   — Predicate logic, forward/backward chaining
  • ExtractionSolver — Structured data extraction from text
  • PlanSolver    — Task decomposition and step ordering
"""

import ast
import logging
import math
import operator
import re
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Shared Types ─────────────────────────────────────────

@dataclass
class SolverResult:
    """Result from any solver."""
    answer: str = ""
    confidence: float = 0.0
    solver_name: str = ""
    reasoning_trace: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def is_valid(self) -> bool:
        return bool(self.answer) and self.confidence > 0.1


# ═══════════════════════════════════════════════════════════
# MATH SOLVER — Symbolic Arithmetic & Algebra
# ═══════════════════════════════════════════════════════════

class MathSolver:
    """
    Solves math problems using symbolic computation.
    No GPU, no ML — pure algorithmic math.

    Capabilities:
      • Arithmetic: +, -, *, /, **, %, //
      • Statistics: mean, median, mode, std, variance
      • Algebra: simple equation solving (ax + b = c)
      • Number theory: primes, factorials, GCD, LCM, fibonacci
      • Trigonometry: sin, cos, tan (radians)
      • Conversions: binary, hex, unit conversions
    """

    # Safe operators for eval-free computation
    _OPS = {
        '+': operator.add, '-': operator.sub,
        '*': operator.mul, '/': operator.truediv,
        '**': operator.pow, '%': operator.mod,
        '//': operator.floordiv,
    }

    _FUNCTIONS = {
        'sqrt': math.sqrt, 'abs': abs,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'log': math.log, 'log2': math.log2, 'log10': math.log10,
        'ceil': math.ceil, 'floor': math.floor,
        'factorial': math.factorial, 'gcd': math.gcd,
        'pi': math.pi, 'e': math.e,
    }

    def solve(self, prompt: str) -> SolverResult:
        """Solve a math problem from natural language."""
        start = time.time()
        result = SolverResult(solver_name="MathSolver")
        prompt_lower = prompt.lower()

        try:
            # Try direct expression evaluation first
            expr = self._extract_expression(prompt)
            if expr:
                value = self._safe_eval(expr)
                if value is not None:
                    result.answer = self._format_math_answer(expr, value, prompt)
                    result.confidence = 0.95
                    result.reasoning_trace = [
                        f"Extracted expression: {expr}",
                        f"Computed result: {value}",
                    ]
                    result.duration_ms = (time.time() - start) * 1000
                    return result

            # Try fibonacci
            fib_match = re.search(r'fibonacci.*?(\d+)', prompt_lower)
            if fib_match or 'fibonacci' in prompt_lower:
                n = int(fib_match.group(1)) if fib_match else 10
                seq = self._fibonacci(min(n, 50))
                result.answer = (
                    f"Fibonacci sequence (first {len(seq)} numbers):\n"
                    f"{', '.join(map(str, seq))}\n\n"
                    f"The Fibonacci sequence is defined as: F(0)=0, F(1)=1, F(n)=F(n-1)+F(n-2)\n"
                    f"Each number is the sum of the two preceding ones.\n\n"
                    f"Implementation (Python):\n```python\ndef fibonacci(n):\n"
                    f"    a, b = 0, 1\n    result = []\n    for _ in range(n):\n"
                    f"        result.append(a)\n        a, b = b, a + b\n    return result\n```"
                )
                result.confidence = 0.95
                result.duration_ms = (time.time() - start) * 1000
                return result

            # Try prime check
            prime_match = re.search(r'(?:is|check).*?(\d+).*prime', prompt_lower)
            if prime_match:
                n = int(prime_match.group(1))
                is_prime = self._is_prime(n)
                result.answer = (
                    f"{n} is {'a prime' if is_prime else 'NOT a prime'} number.\n\n"
                    f"A prime number is divisible only by 1 and itself."
                )
                if not is_prime and n > 1:
                    factors = self._factorize(n)
                    result.answer += f"\nPrime factorization: {n} = {' × '.join(map(str, factors))}"
                result.confidence = 0.95
                result.duration_ms = (time.time() - start) * 1000
                return result

            # Try statistics
            numbers = re.findall(r'-?\d+\.?\d*', prompt)
            if numbers and len(numbers) >= 3 and any(
                kw in prompt_lower for kw in ['mean', 'average', 'median', 'sum', 'statistics', 'std', 'variance']
            ):
                nums = [float(n) for n in numbers]
                result.answer = self._compute_statistics(nums)
                result.confidence = 0.90
                result.duration_ms = (time.time() - start) * 1000
                return result

            # Try factorial
            fact_match = re.search(r'factorial.*?(\d+)|(\d+)\s*!', prompt_lower)
            if fact_match:
                n = int(fact_match.group(1) or fact_match.group(2))
                if n <= 170:
                    val = math.factorial(n)
                    result.answer = f"{n}! = {val}"
                    result.confidence = 0.95
                    result.duration_ms = (time.time() - start) * 1000
                    return result

            # Try simple algebra: "what is x if 3x + 5 = 20"
            algebra_result = self._solve_linear_equation(prompt)
            if algebra_result:
                result.answer = algebra_result
                result.confidence = 0.85
                result.duration_ms = (time.time() - start) * 1000
                return result

        except Exception as e:
            logger.debug(f"[MATH] Solver error: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _extract_expression(self, text: str) -> str:
        """Extract a mathematical expression from text."""
        # Direct expressions: "15 * 23 + 7"
        expr_match = re.search(
            r'([\d.]+\s*[+\-*/^%]+\s*[\d.]+(?:\s*[+\-*/^%]+\s*[\d.]+)*)',
            text
        )
        if expr_match:
            expr = expr_match.group(1)
            expr = expr.replace('^', '**')
            return expr.strip()

        # "what is X op Y" patterns
        what_match = re.search(
            r'(?:what is|calculate|compute|evaluate)\s+([\d.]+\s*[+\-*/^%]+\s*[\d.]+(?:\s*[+\-*/^%]+\s*[\d.]+)*)',
            text.lower()
        )
        if what_match:
            expr = what_match.group(1).replace('^', '**')
            return expr.strip()

        # "X times Y", "X plus Y" patterns
        word_ops = {
            'plus': '+', 'minus': '-', 'times': '*', 'multiplied by': '*',
            'divided by': '/', 'to the power of': '**', 'mod': '%'
        }
        text_lower = text.lower()
        for word, op in word_ops.items():
            pattern = rf'(\d+\.?\d*)\s+{re.escape(word)}\s+(\d+\.?\d*)'
            m = re.search(pattern, text_lower)
            if m:
                return f"{m.group(1)} {op} {m.group(2)}"

        return ""

    def _safe_eval(self, expr: str) -> Optional[float]:
        """Safely evaluate a math expression using AST parsing (no exec/eval)."""
        try:
            tree = ast.parse(expr, mode='eval')
            return self._eval_node(tree.body)
        except Exception:
            return None

    def _eval_node(self, node) -> float:
        """Recursively evaluate an AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported constant: {node.value}")
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op).__name__
            op_map = {
                'Add': operator.add, 'Sub': operator.sub,
                'Mult': operator.mul, 'Div': operator.truediv,
                'Pow': operator.pow, 'Mod': operator.mod,
                'FloorDiv': operator.floordiv,
            }
            if op_type in op_map:
                return op_map[op_type](left, right)
            raise ValueError(f"Unsupported operator: {op_type}")
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.UAdd):
                return operand
            raise ValueError(f"Unsupported unary op")
        elif isinstance(node, ast.Call):
            func_name = getattr(node.func, 'id', '')
            if func_name in self._FUNCTIONS:
                args = [self._eval_node(a) for a in node.args]
                return self._FUNCTIONS[func_name](*args)
        elif isinstance(node, ast.Name):
            if node.id in self._FUNCTIONS and not callable(self._FUNCTIONS[node.id]):
                return self._FUNCTIONS[node.id]
        raise ValueError(f"Unsupported node: {type(node)}")

    def _format_math_answer(self, expr: str, value: float, prompt: str) -> str:
        """Format a mathematical answer with explanation."""
        if value == int(value):
            formatted = str(int(value))
        else:
            formatted = f"{value:.6f}".rstrip('0').rstrip('.')

        return (
            f"**Result**: {expr} = **{formatted}**\n\n"
            f"Step-by-step:\n"
            f"  Expression: {expr}\n"
            f"  Evaluation: {formatted}\n\n"
            f"This was computed using safe symbolic arithmetic (AST-parsed, no eval)."
        )

    @staticmethod
    def _fibonacci(n: int) -> List[int]:
        a, b = 0, 1
        result = []
        for _ in range(n):
            result.append(a)
            a, b = b, a + b
        return result

    @staticmethod
    def _is_prime(n: int) -> bool:
        if n < 2:
            return False
        if n < 4:
            return True
        if n % 2 == 0 or n % 3 == 0:
            return False
        i = 5
        while i * i <= n:
            if n % i == 0 or n % (i + 2) == 0:
                return False
            i += 6
        return True

    @staticmethod
    def _factorize(n: int) -> List[int]:
        factors = []
        d = 2
        while d * d <= n:
            while n % d == 0:
                factors.append(d)
                n //= d
            d += 1
        if n > 1:
            factors.append(n)
        return factors

    @staticmethod
    def _compute_statistics(nums: List[float]) -> str:
        lines = [f"**Statistical Analysis** of {len(nums)} values:\n"]
        lines.append(f"  Values: {', '.join(f'{n:g}' for n in nums[:20])}")
        lines.append(f"  Sum: {sum(nums):g}")
        lines.append(f"  Mean: {statistics.mean(nums):.4f}")
        lines.append(f"  Median: {statistics.median(nums):.4f}")
        if len(nums) >= 2:
            lines.append(f"  Std Dev: {statistics.stdev(nums):.4f}")
            lines.append(f"  Variance: {statistics.variance(nums):.4f}")
        lines.append(f"  Min: {min(nums):g}")
        lines.append(f"  Max: {max(nums):g}")
        lines.append(f"  Range: {max(nums) - min(nums):g}")
        return "\n".join(lines)

    def _solve_linear_equation(self, prompt: str) -> str:
        """Solve simple linear equations: ax + b = c."""
        # Pattern: "3x + 5 = 20" or "solve 2x - 7 = 15"
        m = re.search(r'(-?\d*\.?\d*)x\s*([+\-])\s*(\d+\.?\d*)\s*=\s*(-?\d+\.?\d*)', prompt)
        if m:
            a = float(m.group(1) if m.group(1) and m.group(1) != '-' else (m.group(1) + '1' if m.group(1) == '-' else '1'))
            sign = 1 if m.group(2) == '+' else -1
            b = float(m.group(3)) * sign
            c = float(m.group(4))
            if a != 0:
                x = (c - b) / a
                x_fmt = f"{x:g}"
                return (
                    f"**Solving**: {m.group(0)}\n\n"
                    f"Step 1: Subtract {b:g} from both sides: {a:g}x = {c - b:g}\n"
                    f"Step 2: Divide both sides by {a:g}: x = {x_fmt}\n\n"
                    f"**Solution: x = {x_fmt}**\n\n"
                    f"Verification: {a:g}({x_fmt}) {'+' if sign > 0 else '-'} {abs(b):g} = {a*x + b:g} ✓"
                )
        return ""


# ═══════════════════════════════════════════════════════════
# CODE SOLVER — AST Analysis & Pattern-Based Generation
# ═══════════════════════════════════════════════════════════

class CodeSolver:
    """
    Solves coding problems using AST analysis and template patterns.
    No ML — pure algorithmic code generation.
    """

    # Code templates for common patterns
    _TEMPLATES = {
        "fibonacci": '''def fibonacci(n: int) -> list:
    """Generate the first n Fibonacci numbers."""
    if n <= 0:
        return []
    if n == 1:
        return [0]
    
    result = [0, 1]
    for i in range(2, n):
        result.append(result[i-1] + result[i-2])
    return result


# Example usage:
# >>> fibonacci(10)
# [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]''',

        "binary_search": '''def binary_search(arr: list, target) -> int:
    """Binary search for target in sorted array. Returns index or -1."""
    left, right = 0, len(arr) - 1
    
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    
    return -1  # Not found


# Time: O(log n), Space: O(1)
# Example: binary_search([1, 3, 5, 7, 9], 5) → 2''',

        "bubble_sort": '''def bubble_sort(arr: list) -> list:
    """Sort array using bubble sort algorithm."""
    n = len(arr)
    arr = arr.copy()  # Don't modify original
    
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break  # Already sorted
    
    return arr


# Time: O(n²) worst/average, O(n) best | Space: O(1)''',

        "quick_sort": '''def quick_sort(arr: list) -> list:
    """Sort array using QuickSort algorithm."""
    if len(arr) <= 1:
        return arr
    
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    
    return quick_sort(left) + middle + quick_sort(right)


# Time: O(n log n) average, O(n²) worst | Space: O(n)''',

        "merge_sort": '''def merge_sort(arr: list) -> list:
    """Sort array using MergeSort algorithm."""
    if len(arr) <= 1:
        return arr
    
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    
    return _merge(left, right)


def _merge(left: list, right: list) -> list:
    """Merge two sorted arrays."""
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


# Time: O(n log n) guaranteed | Space: O(n) | Stable: Yes''',

        "linked_list": '''class Node:
    """Singly linked list node."""
    def __init__(self, data, next_node=None):
        self.data = data
        self.next = next_node


class LinkedList:
    """Singly linked list implementation."""
    
    def __init__(self):
        self.head = None
        self.size = 0
    
    def append(self, data):
        new_node = Node(data)
        if not self.head:
            self.head = new_node
        else:
            current = self.head
            while current.next:
                current = current.next
            current.next = new_node
        self.size += 1
    
    def prepend(self, data):
        self.head = Node(data, self.head)
        self.size += 1
    
    def delete(self, data):
        if not self.head:
            return
        if self.head.data == data:
            self.head = self.head.next
            self.size -= 1
            return
        current = self.head
        while current.next:
            if current.next.data == data:
                current.next = current.next.next
                self.size -= 1
                return
            current = current.next
    
    def find(self, data):
        current = self.head
        while current:
            if current.data == data:
                return True
            current = current.next
        return False
    
    def to_list(self):
        result = []
        current = self.head
        while current:
            result.append(current.data)
            current = current.next
        return result
    
    def __len__(self):
        return self.size
    
    def __repr__(self):
        return " -> ".join(str(x) for x in self.to_list()) + " -> None"''',

        "stack": '''class Stack:
    """Stack implementation using Python list."""
    
    def __init__(self):
        self._items = []
    
    def push(self, item):
        self._items.append(item)
    
    def pop(self):
        if self.is_empty():
            raise IndexError("Stack is empty")
        return self._items.pop()
    
    def peek(self):
        if self.is_empty():
            raise IndexError("Stack is empty")
        return self._items[-1]
    
    def is_empty(self):
        return len(self._items) == 0
    
    def size(self):
        return len(self._items)
    
    def __repr__(self):
        return f"Stack({self._items})"


# All operations O(1) amortized''',

        "queue": '''from collections import deque


class Queue:
    """Queue implementation using deque for O(1) operations."""
    
    def __init__(self):
        self._items = deque()
    
    def enqueue(self, item):
        self._items.append(item)
    
    def dequeue(self):
        if self.is_empty():
            raise IndexError("Queue is empty")
        return self._items.popleft()
    
    def peek(self):
        if self.is_empty():
            raise IndexError("Queue is empty")
        return self._items[0]
    
    def is_empty(self):
        return len(self._items) == 0
    
    def size(self):
        return len(self._items)


# All operations O(1)''',

        "bfs": '''from collections import deque


def bfs(graph: dict, start):
    """Breadth-First Search traversal of a graph."""
    visited = set()
    queue = deque([start])
    visited.add(start)
    order = []
    
    while queue:
        node = queue.popleft()
        order.append(node)
        
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    
    return order


# Time: O(V + E) | Space: O(V)
# Example:
# graph = {0: [1, 2], 1: [2], 2: [0, 3], 3: [3]}
# bfs(graph, 2) → [2, 0, 3, 1]''',

        "dfs": '''def dfs(graph: dict, start, visited=None):
    """Depth-First Search traversal of a graph (recursive)."""
    if visited is None:
        visited = set()
    
    visited.add(start)
    result = [start]
    
    for neighbor in graph.get(start, []):
        if neighbor not in visited:
            result.extend(dfs(graph, neighbor, visited))
    
    return result


def dfs_iterative(graph: dict, start):
    """DFS using explicit stack (no recursion)."""
    visited = set()
    stack = [start]
    order = []
    
    while stack:
        node = stack.pop()
        if node not in visited:
            visited.add(node)
            order.append(node)
            for neighbor in reversed(graph.get(node, [])):
                if neighbor not in visited:
                    stack.append(neighbor)
    
    return order


# Time: O(V + E) | Space: O(V)''',

        "hash_map": '''class HashMap:
    """Simple hash map implementation with chaining."""
    
    def __init__(self, capacity=16):
        self.capacity = capacity
        self.size = 0
        self.buckets = [[] for _ in range(capacity)]
    
    def _hash(self, key):
        return hash(key) % self.capacity
    
    def put(self, key, value):
        index = self._hash(key)
        bucket = self.buckets[index]
        
        for i, (k, v) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)
                return
        
        bucket.append((key, value))
        self.size += 1
        
        if self.size > self.capacity * 0.75:
            self._resize()
    
    def get(self, key, default=None):
        index = self._hash(key)
        for k, v in self.buckets[index]:
            if k == key:
                return v
        return default
    
    def delete(self, key):
        index = self._hash(key)
        bucket = self.buckets[index]
        for i, (k, v) in enumerate(bucket):
            if k == key:
                del bucket[i]
                self.size -= 1
                return True
        return False
    
    def _resize(self):
        old = self.buckets
        self.capacity *= 2
        self.buckets = [[] for _ in range(self.capacity)]
        self.size = 0
        for bucket in old:
            for key, value in bucket:
                self.put(key, value)


# Average: O(1) get/put/delete | Worst: O(n) with bad hash''',

        "decorator": '''import functools
import time


def timer(func):
    """Decorator that measures function execution time."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper


def retry(max_attempts=3, delay=1.0):
    """Decorator that retries a function on failure."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts:
                        time.sleep(delay)
            raise last_error
        return wrapper
    return decorator


def cache(func):
    """Simple memoization decorator."""
    _cache = {}
    @functools.wraps(func)
    def wrapper(*args):
        if args not in _cache:
            _cache[args] = func(*args)
        return _cache[args]
    return wrapper


# Usage:
# @timer
# @retry(max_attempts=3)
# def fetch_data(url): ...''',
    }

    def solve(self, prompt: str) -> SolverResult:
        """Solve a coding problem using template matching and generation."""
        start = time.time()
        result = SolverResult(solver_name="CodeSolver")
        prompt_lower = prompt.lower()

        # Match against known patterns
        for pattern_key, code_template in self._TEMPLATES.items():
            # Check if the prompt matches this pattern
            keywords = pattern_key.replace('_', ' ').split()
            if all(kw in prompt_lower for kw in keywords):
                result.answer = (
                    f"Here's a complete implementation:\n\n```python\n{code_template}\n```\n\n"
                    f"This implementation follows best practices:\n"
                    f"- Clean, readable code with type hints\n"
                    f"- Comprehensive docstrings\n"
                    f"- Time and space complexity noted\n"
                    f"- Example usage included"
                )
                result.confidence = 0.90
                result.reasoning_trace = [f"Matched pattern: {pattern_key}"]
                result.duration_ms = (time.time() - start) * 1000
                return result

        # Try fuzzy pattern matching
        best_match, best_score = self._fuzzy_match(prompt_lower)
        if best_match and best_score > 0.4:
            code = self._TEMPLATES[best_match]
            result.answer = (
                f"Based on your request, here's a relevant implementation:\n\n"
                f"```python\n{code}\n```\n\n"
                f"Pattern: **{best_match.replace('_', ' ').title()}**"
            )
            result.confidence = 0.70 * best_score
            result.reasoning_trace = [f"Fuzzy matched: {best_match} (score={best_score:.2f})"]
            result.duration_ms = (time.time() - start) * 1000
            return result

        # Generate generic function structure
        func_name = self._extract_function_name(prompt)
        if func_name:
            code = self._generate_skeleton(func_name, prompt)
            result.answer = (
                f"Here's a function skeleton based on your description:\n\n"
                f"```python\n{code}\n```\n\n"
                f"This provides a starting structure. Implement the TODO section "
                f"with your specific logic."
            )
            result.confidence = 0.50
            result.duration_ms = (time.time() - start) * 1000
            return result

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _fuzzy_match(self, query: str) -> Tuple[str, float]:
        """Fuzzy match query against template names."""
        best_name = ""
        best_score = 0.0

        query_words = set(re.findall(r'[a-z]+', query))

        # Also check for common synonyms
        synonyms = {
            'sort': ['sorting', 'order', 'arrange'],
            'search': ['find', 'lookup', 'locate'],
            'list': ['linked', 'array'],
            'tree': ['bst', 'binary'],
            'graph': ['network', 'node', 'edge'],
            'hash': ['dictionary', 'map', 'table'],
        }

        expanded_query = set(query_words)
        for word in list(query_words):
            for key, syns in synonyms.items():
                if word in syns:
                    expanded_query.add(key)
                if word == key:
                    expanded_query.update(syns)

        for name in self._TEMPLATES:
            name_words = set(name.split('_'))
            # Score = Jaccard similarity
            intersection = expanded_query & name_words
            union = expanded_query | name_words
            score = len(intersection) / max(len(union), 1)
            if score > best_score:
                best_score = score
                best_name = name

        return best_name, best_score

    @staticmethod
    def _extract_function_name(prompt: str) -> str:
        """Extract a function name from the prompt."""
        patterns = [
            r'(?:write|create|implement|build|make)\s+(?:a\s+)?(?:function|method|def)\s+(?:called\s+|named\s+|for\s+)?(\w+)',
            r'(?:function|method)\s+(?:to|that|for)\s+(\w+(?:\s+\w+)?)',
            r'(?:write|create|implement)\s+(\w+)',
        ]
        for p in patterns:
            m = re.search(p, prompt.lower())
            if m:
                name = m.group(1).replace(' ', '_')
                return name
        return ""

    @staticmethod
    def _generate_skeleton(func_name: str, description: str) -> str:
        """Generate a function skeleton from name and description."""
        return (
            f'def {func_name}(*args, **kwargs):\n'
            f'    """{description[:80]}"""\n'
            f'    # TODO: Implement the logic here\n'
            f'    #\n'
            f'    # Based on the description:\n'
            f'    # {description[:120]}\n'
            f'    #\n'
            f'    raise NotImplementedError("{func_name} not yet implemented")\n'
        )


# ═══════════════════════════════════════════════════════════
# LOGIC SOLVER — Predicate Logic & Reasoning
# ═══════════════════════════════════════════════════════════

class LogicSolver:
    """Solves logic problems using forward/backward chaining."""

    def solve(self, prompt: str) -> SolverResult:
        """Solve a logic problem."""
        start = time.time()
        result = SolverResult(solver_name="LogicSolver")
        prompt_lower = prompt.lower()

        # Try to handle boolean logic
        bool_result = self._evaluate_boolean(prompt)
        if bool_result:
            result.answer = bool_result
            result.confidence = 0.85
            result.duration_ms = (time.time() - start) * 1000
            return result

        # Try syllogism detection
        syl_result = self._check_syllogism(prompt)
        if syl_result:
            result.answer = syl_result
            result.confidence = 0.80
            result.duration_ms = (time.time() - start) * 1000
            return result

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _evaluate_boolean(self, prompt: str) -> str:
        """Evaluate boolean expressions."""
        # Simple truth table generation
        if 'truth table' in prompt.lower():
            # Extract variable names
            vars_found = sorted(set(re.findall(r'\b([A-Z])\b', prompt)))
            if not vars_found:
                vars_found = ['A', 'B']
            return self._generate_truth_table(vars_found[:4])

        # Evaluate: "True AND False OR True"
        expr = prompt.upper()
        expr = expr.replace(' AND ', ' and ').replace(' OR ', ' or ').replace(' NOT ', ' not ')
        expr = expr.replace('TRUE', 'True').replace('FALSE', 'False')
        try:
            if re.match(r'^[\sA-Za-z()andornot]+$', expr):
                # Only evaluate if it looks like a boolean expression
                val = eval(expr)  # Safe: only booleans/operators
                if isinstance(val, bool):
                    return f"**Result**: `{expr.strip()}` evaluates to **{val}**"
        except Exception:
            pass
        return ""

    @staticmethod
    def _generate_truth_table(variables: List[str]) -> str:
        """Generate a truth table for given variables."""
        n = len(variables)
        header = " | ".join(variables) + " | AND | OR | XOR"
        lines = [f"**Truth Table for {', '.join(variables)}**:\n"]
        lines.append(header)
        lines.append("-" * len(header))

        for i in range(2 ** n):
            vals = [(i >> (n - 1 - j)) & 1 for j in range(n)]
            bool_vals = [bool(v) for v in vals]
            and_val = int(all(bool_vals))
            or_val = int(any(bool_vals))
            xor_val = int(sum(bool_vals) % 2 == 1)

            row = " | ".join(f" {v} " for v in vals)
            row += f" |  {and_val}  |  {or_val} |  {xor_val}"
            lines.append(row)

        return "\n".join(lines)

    @staticmethod
    def _check_syllogism(prompt: str) -> str:
        """Check basic syllogistic reasoning."""
        # "All X are Y. Z is X. Therefore Z is Y."
        m = re.search(
            r'all\s+(\w+)\s+are\s+(\w+).*?(\w+)\s+is\s+(?:a|an)?\s*(\w+)',
            prompt.lower()
        )
        if m:
            category = m.group(1)
            property_ = m.group(2)
            instance_ = m.group(3)
            inst_cat = m.group(4)

            if inst_cat == category or inst_cat in category:
                return (
                    f"**Syllogistic Reasoning**:\n\n"
                    f"Premise 1: All {category} are {property_}\n"
                    f"Premise 2: {instance_.title()} is a {inst_cat}\n"
                    f"**Conclusion: {instance_.title()} is {property_}** ✓\n\n"
                    f"This is a valid Barbara syllogism (AAA-1)."
                )
        return ""


# ═══════════════════════════════════════════════════════════
# EXTRACTION SOLVER — Structured Data Extraction
# ═══════════════════════════════════════════════════════════

class ExtractionSolver:
    """Extracts structured data from natural language prompts."""

    def solve(self, prompt: str) -> SolverResult:
        """Extract structured data from the prompt."""
        start = time.time()
        result = SolverResult(solver_name="ExtractionSolver")

        # Check if prompt asks for JSON extraction
        if 'json' in prompt.lower() or 'extract' in prompt.lower():
            extracted = self._extract_json_fields(prompt)
            if extracted:
                import json
                result.answer = f"```json\n{json.dumps(extracted, indent=2)}\n```"
                result.confidence = 0.75
                result.duration_ms = (time.time() - start) * 1000
                return result

        # Check for task specification extraction
        if 'taskspec' in prompt.lower() or 'task_type' in prompt.lower() or 'action_type' in prompt.lower():
            task_data = self._extract_task_spec(prompt)
            if task_data:
                import json
                result.answer = json.dumps(task_data)
                result.confidence = 0.80
                result.duration_ms = (time.time() - start) * 1000
                return result

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _extract_json_fields(self, text: str) -> Dict[str, Any]:
        """Extract key-value pairs from text."""
        data = {}

        # Look for "key: value" patterns
        for match in re.finditer(r'(\w+)\s*[:=]\s*"?([^"\n,]+)"?', text):
            key = match.group(1).lower().strip()
            value = match.group(2).strip()
            # Try to parse as number
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    if value.lower() in ('true', 'yes'):
                        value = True
                    elif value.lower() in ('false', 'no'):
                        value = False
            data[key] = value

        return data if data else {}

    @staticmethod
    def _extract_task_spec(prompt: str) -> Dict[str, Any]:
        """Extract task specification for the agent pipeline."""
        prompt_lower = prompt.lower()

        # Determine action type
        action_type = "general"
        if any(kw in prompt_lower for kw in ['code', 'write', 'implement', 'function', 'class', 'program']):
            action_type = "code_generation"
        elif any(kw in prompt_lower for kw in ['fix', 'debug', 'error', 'bug']):
            action_type = "debugging"
        elif any(kw in prompt_lower for kw in ['explain', 'what is', 'how does', 'describe']):
            action_type = "explanation"
        elif any(kw in prompt_lower for kw in ['analyze', 'review', 'evaluate']):
            action_type = "analysis"
        elif any(kw in prompt_lower for kw in ['plan', 'design', 'architect']):
            action_type = "planning"

        # Determine tools needed
        tools_needed = []
        if any(kw in prompt_lower for kw in ['file', 'read', 'write', 'save']):
            tools_needed.append("filesystem")
        if any(kw in prompt_lower for kw in ['search', 'find', 'look up', 'google']):
            tools_needed.append("web_search")
        if any(kw in prompt_lower for kw in ['run', 'execute', 'test', 'compile']):
            tools_needed.append("code_executor")

        return {
            "action_type": action_type,
            "tools_needed": tools_needed,
            "goal": prompt[:200].strip(),
            "requires_sandbox": action_type in ("code_generation", "debugging"),
        }


# ═══════════════════════════════════════════════════════════
# PLAN SOLVER — Task Decomposition
# ═══════════════════════════════════════════════════════════

class PlanSolver:
    """Decomposes complex tasks into ordered steps."""

    def solve(self, prompt: str) -> SolverResult:
        """Create a structured plan from a task description."""
        start = time.time()
        result = SolverResult(solver_name="PlanSolver")
        prompt_lower = prompt.lower()

        # Detect if this is a planning/design request
        is_plan_request = any(kw in prompt_lower for kw in [
            'plan', 'design', 'architect', 'build', 'create', 'implement',
            'step by step', 'how to', 'guide', 'tutorial',
        ])

        if not is_plan_request:
            return result

        # Decompose into phases
        phases = self._decompose_task(prompt)
        if phases:
            lines = [f"## Execution Plan\n"]
            for i, (phase, steps) in enumerate(phases, 1):
                lines.append(f"### Phase {i}: {phase}")
                for j, step in enumerate(steps, 1):
                    lines.append(f"  {j}. {step}")
                lines.append("")

            lines.append("### Dependencies")
            lines.append("Each phase should be completed before the next begins.")
            lines.append("Steps within a phase can be parallelized where possible.")

            result.answer = "\n".join(lines)
            result.confidence = 0.70
            result.duration_ms = (time.time() - start) * 1000

        return result

    @staticmethod
    def _decompose_task(prompt: str) -> List[Tuple[str, List[str]]]:
        """Decompose a task into phases and steps."""
        prompt_lower = prompt.lower()

        # Common project phases
        phases = []

        if any(kw in prompt_lower for kw in ['web', 'app', 'application', 'website', 'frontend']):
            phases = [
                ("Requirements & Design", [
                    "Define user requirements and success criteria",
                    "Design component architecture and data flow",
                    "Create wireframes/mockups for key screens",
                    "Define API contracts and data models",
                ]),
                ("Foundation", [
                    "Set up project structure and tooling",
                    "Configure build system and dependencies",
                    "Implement design system (colors, typography, spacing)",
                    "Set up routing and navigation",
                ]),
                ("Core Implementation", [
                    "Build core data models and state management",
                    "Implement primary user-facing components",
                    "Connect to backend APIs / data layer",
                    "Add form validation and error handling",
                ]),
                ("Polish & Testing", [
                    "Add responsive design and accessibility",
                    "Implement loading states and error boundaries",
                    "Write unit and integration tests",
                    "Performance optimization and asset compression",
                ]),
                ("Deployment", [
                    "Configure production build pipeline",
                    "Set up CI/CD workflow",
                    "Deploy to staging for review",
                    "Production release and monitoring",
                ]),
            ]
        elif any(kw in prompt_lower for kw in ['api', 'backend', 'server', 'microservice']):
            phases = [
                ("Design", [
                    "Define API endpoints and data contracts",
                    "Design database schema and relationships",
                    "Plan authentication and authorization model",
                    "Document error handling strategy",
                ]),
                ("Infrastructure", [
                    "Set up project structure and framework",
                    "Configure database and ORM",
                    "Implement middleware (auth, logging, CORS)",
                    "Set up configuration management",
                ]),
                ("Implementation", [
                    "Implement core business logic",
                    "Build CRUD endpoints",
                    "Add validation and error handling",
                    "Implement background task processing",
                ]),
                ("Testing & Security", [
                    "Write unit tests for business logic",
                    "Add integration tests for API endpoints",
                    "Security audit (injection, auth bypass, etc.)",
                    "Load testing and performance profiling",
                ]),
            ]
        else:
            # Generic task decomposition
            phases = [
                ("Research & Planning", [
                    "Analyze the problem and constraints",
                    "Research existing solutions and best practices",
                    "Define success criteria and scope",
                    "Create a detailed technical plan",
                ]),
                ("Implementation", [
                    "Set up the development environment",
                    "Build the core functionality",
                    "Handle edge cases and error conditions",
                    "Integrate with existing systems",
                ]),
                ("Verification", [
                    "Test all components thoroughly",
                    "Validate against success criteria",
                    "Review code quality and documentation",
                    "Prepare for deployment/delivery",
                ]),
            ]

        return phases


# ═══════════════════════════════════════════════════════════
# SOLVER PIPELINE — Orchestration
# ═══════════════════════════════════════════════════════════

class SolverPipeline:
    """
    Orchestrates all solvers, picking the best for each problem.

    Usage:
        pipeline = SolverPipeline()
        result = pipeline.solve("math", "What is 15 * 23 + 7?")
    """

    def __init__(self):
        self.math = MathSolver()
        self.code = CodeSolver()
        self.logic = LogicSolver()
        self.extraction = ExtractionSolver()
        self.plan = PlanSolver()

        self._solve_count = 0

    def solve(self, intent: str, prompt: str) -> SolverResult:
        """Route to the best solver based on classified intent."""
        self._solve_count += 1

        solver_map = {
            "math": self.math,
            "code": self.code,
            "logic": self.logic,
            "extraction": self.extraction,
            "plan": self.plan,
        }

        # Primary solver
        solver = solver_map.get(intent)
        if solver:
            result = solver.solve(prompt)
            if result.is_valid:
                return result

        # Fallback: try all solvers in order of likelihood
        fallback_order = ["math", "code", "extraction", "logic", "plan"]
        for fallback_intent in fallback_order:
            if fallback_intent == intent:
                continue
            solver = solver_map.get(fallback_intent)
            if solver:
                result = solver.solve(prompt)
                if result.is_valid:
                    return result

        return SolverResult(solver_name="none", confidence=0.0)

    def get_stats(self) -> Dict[str, Any]:
        return {"total_solves": self._solve_count}
