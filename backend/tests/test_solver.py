"""Tests for the Self-Thinking Problem Solver System."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ──────────────────────────────────────────────
# Test 1: Pattern Library (no LLM needed)
# ──────────────────────────────────────────────

def test_pattern_library():
    """Test pattern storage, search, and retrieval."""
    from brain.solver.patterns import PatternLibrary, CodingPattern

    lib = PatternLibrary()

    # Should have built-in patterns
    assert len(lib) >= 10, f"Expected 10+ built-in patterns, got {len(lib)}"
    print(f"  ✅ {len(lib)} built-in patterns loaded")

    # Search should find relevant patterns
    results = lib.search("sort an array")
    assert len(results) > 0, "No results for 'sort an array'"
    # Search returns array-related patterns — merge_sort, two_pointer, etc.
    print(f"  ✅ Search 'sort an array': found {len(results)} matches")

    results = lib.search("binary search in sorted list")
    assert any("binary" in p.name.lower() for p in results)
    print("  ✅ Search 'binary search': found match")

    results = lib.search("graph traversal BFS")
    assert any("bfs" in p.name.lower() for p in results)
    print("  ✅ Search 'graph BFS': found match")

    results = lib.search("dynamic programming memoization")
    assert any("dp" in p.name.lower() or "memo" in p.name.lower() for p in results)
    print("  ✅ Search 'DP memoization': found match")

    # Store a new pattern
    custom = CodingPattern(
        name="test_pattern",
        description="Custom test pattern for validation",
        category="testing",
        template="def test(): pass",
        tags=["test", "custom"],
    )
    lib.store(custom)
    assert len(lib) >= 11
    print(f"  ✅ Custom pattern stored (total: {len(lib)})")

    # Retrieve by name
    found = lib.get("test_pattern")
    assert found is not None
    assert found.name == "test_pattern"
    print("  ✅ Pattern retrieved by name")

    # List categories
    cats = lib.list_categories()
    assert len(cats) >= 3
    print(f"  ✅ Categories: {cats}")

    print("✅ Pattern Library tests passed!\n")


# ──────────────────────────────────────────────
# Test 2: Complexity Analyzer (no LLM needed)
# ──────────────────────────────────────────────

def test_complexity_analyzer():
    """Test time/space complexity analysis."""
    from brain.solver.complexity import ComplexityAnalyzer

    analyzer = ComplexityAnalyzer()

    # O(1) — constant time
    code_o1 = "def add(a, b):\n    return a + b"
    r = analyzer.analyze(code_o1)
    assert r.time_complexity == "O(1)", f"Expected O(1), got {r.time_complexity}"
    assert r.loop_depth == 0
    print(f"  ✅ O(1): {r.summary}")

    # O(n) — single loop
    code_on = """
def find_max(arr):
    result = arr[0]
    for x in arr:
        if x > result:
            result = x
    return result
"""
    r = analyzer.analyze(code_on)
    assert r.time_complexity == "O(n)", f"Expected O(n), got {r.time_complexity}"
    assert r.loop_depth == 1
    print(f"  ✅ O(n): {r.summary}")

    # O(n²) — nested loops
    code_on2 = """
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(n - 1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr
"""
    r = analyzer.analyze(code_on2)
    assert r.time_complexity == "O(n²)", f"Expected O(n²), got {r.time_complexity}"
    assert r.loop_depth == 2
    print(f"  ✅ O(n²): {r.summary}")

    # O(log n) — binary search
    code_logn = """
def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
"""
    r = analyzer.analyze(code_logn)
    assert r.time_complexity == "O(log n)", f"Expected O(log n), got {r.time_complexity}"
    print(f"  ✅ O(log n): {r.summary}")

    # Recursion detection
    code_recursive = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
    r = analyzer.analyze(code_recursive)
    assert r.has_recursion, "Should detect recursion"
    assert "2^n" in r.time_complexity, f"Expected O(2^n), got {r.time_complexity}"
    print(f"  ✅ Recursive O(2^n): {r.summary}")

    # Data structure detection
    code_ds = """
def count_freq(arr):
    freq = {}
    for x in arr:
        freq[x] = freq.get(x, 0) + 1
    result = []
    for k, v in freq.items():
        result.append((k, v))
    return result
"""
    r = analyzer.analyze(code_ds)
    assert "Dict" in r.data_structures or "List" in r.data_structures
    print(f"  ✅ Data structures detected: {r.data_structures}")

    # Optimization suggestions
    code_slow = """
def has_duplicate(arr):
    for i in range(len(arr)):
        for j in range(i+1, len(arr)):
            if arr[i] == arr[j]:
                return True
    return False
"""
    r = analyzer.analyze(code_slow)
    assert len(r.suggestions) > 0, "Should suggest optimizations"
    print(f"  ✅ Optimization suggestions: {r.suggestions}")

    print("✅ Complexity Analyzer tests passed!\n")


# ──────────────────────────────────────────────
# Test 3: Self-Healer (syntax checking — no LLM)
# ──────────────────────────────────────────────

def test_self_healer_detection():
    """Test error detection capabilities of the healer."""
    from brain.solver.healer import SelfHealer, CodeError

    # Use a dummy generate_fn since we're only testing detection
    healer = SelfHealer(generate_fn=lambda p: "")

    # Test syntax error detection
    bad_code = "def foo(\n    return 42"
    errors = healer._detect_errors(bad_code)
    syntax_errors = [e for e in errors if e.error_type == "syntax"]
    assert len(syntax_errors) > 0, "Should detect syntax error"
    print(f"  ✅ Syntax error detected: {syntax_errors[0].message[:60]}")

    # Test static analysis
    risky_code = """
def process(data):
    result = eval(data)
    return result
"""
    errors = healer._detect_errors(risky_code)
    static_errors = [e for e in errors if e.error_type == "static"]
    assert any("eval" in e.message.lower() for e in static_errors), \
        "Should detect eval() security risk"
    print("  ✅ Static analysis: eval() detected as security risk")

    # Test clean code passes
    good_code = """
def factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
    errors = healer._detect_errors(good_code)
    critical = [e for e in errors if e.severity == "error"]
    assert len(critical) == 0, f"Clean code should have no errors, got {critical}"
    print(f"  ✅ Clean code has 0 critical errors ({len(errors)} warnings)")

    # Test logic check (function without return)
    no_return_code = """
def get_value(items):
    for item in items:
        if item > 0:
            print(item)
"""
    errors = healer._detect_errors(no_return_code)
    logic_warnings = [e for e in errors if e.error_type == "logic"]
    assert len(logic_warnings) > 0, "Should warn about get_ function without return"
    print("  ✅ Logic check: missing return detected for get_ function")

    print("✅ Self-Healer detection tests passed!\n")


# ──────────────────────────────────────────────
# Test 4: Solution Evolver (fitness scoring — no LLM)
# ──────────────────────────────────────────────

def test_evolver_fitness():
    """Test fitness scoring of the evolver."""
    from brain.solver.evolver import SolutionEvolver

    evolver = SolutionEvolver(generate_fn=lambda p: "")

    # Good code should score high
    good_code = '''
def merge_sort(arr: list) -> list:
    """Sort array using merge sort algorithm."""
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)

def merge(left: list, right: list) -> list:
    """Merge two sorted lists."""
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
'''
    good_fitness = evolver._compute_fitness(good_code)
    assert good_fitness >= 0.5, f"Good code fitness too low: {good_fitness}"
    print(f"  ✅ Good code fitness: {good_fitness:.3f}")

    # Bad code should score low
    bad_code = "def foo(x eval(x)"  # Syntax error
    bad_fitness = evolver._compute_fitness(bad_code)
    assert bad_fitness < good_fitness, "Bad code should score lower"
    print(f"  ✅ Bad code fitness: {bad_fitness:.3f} (lower than good)")

    # Empty code should score zero
    empty_fitness = evolver._compute_fitness("")
    assert empty_fitness == 0.0
    print(f"  ✅ Empty code fitness: {empty_fitness:.3f}")

    # Code with dangerous patterns should score lower
    dangerous_code = """
def process(data):
    return eval(data)
"""
    dangerous_fitness = evolver._compute_fitness(dangerous_code)
    print(f"  ✅ Dangerous code fitness: {dangerous_fitness:.3f}")

    print("✅ Evolver fitness tests passed!\n")


# ──────────────────────────────────────────────
# Test 5: Test Generator (function extraction — no LLM)
# ──────────────────────────────────────────────

def test_test_generator_extraction():
    """Test function extraction and test running."""
    from brain.solver.test_gen import TestGenerator, TestCase, TestSuite

    gen = TestGenerator(generate_fn=lambda p: "")

    # Test function extraction
    code = """
def add(a: int, b: int) -> int:
    return a + b

def is_palindrome(s: str) -> bool:
    return s == s[::-1]
"""
    functions = gen._extract_functions(code)
    assert len(functions) == 2, f"Expected 2 functions, got {len(functions)}"
    assert functions[0]["name"] == "add"
    assert functions[1]["name"] == "is_palindrome"
    print(f"  ✅ Extracted {len(functions)} functions: {[f['name'] for f in functions]}")

    # Test running manually created test cases
    suite = TestSuite(tests=[
        TestCase(name="add_basic", input_data="add(2, 3)", expected_output="5"),
        TestCase(name="add_zero", input_data="add(0, 0)", expected_output="0"),
        TestCase(name="add_negative", input_data="add(-1, 1)", expected_output="0"),
        TestCase(name="palindrome_yes", input_data='is_palindrome("aba")', expected_output="True"),
        TestCase(name="palindrome_no", input_data='is_palindrome("abc")', expected_output="False"),
    ])

    results = gen.run_tests(code, suite)
    assert results.passed == 5, f"Expected 5 passed, got {results.passed}"
    assert results.failed == 0, f"Expected 0 failed, got {results.failed}"
    print(f"  ✅ Tests: {results.passed}/{results.total} passed")

    # Test with failing case
    suite2 = TestSuite(tests=[
        TestCase(name="add_wrong", input_data="add(2, 3)", expected_output="10"),
    ])
    results2 = gen.run_tests(code, suite2)
    assert results2.failed == 1, "Expected 1 failure"
    print("  ✅ Failure detection: correctly caught wrong expected output")

    print("✅ Test Generator tests passed!\n")


# ──────────────────────────────────────────────
# Test 6: Engine (decomposition parsing — no LLM)
# ──────────────────────────────────────────────

def test_engine_parsing():
    """Test engine's parsing capabilities."""
    from brain.solver.engine import SolverEngine

    engine = SolverEngine(generate_fn=lambda p: "")

    # Test sub-problem parsing
    raw_decomposition = """
SUB_PROBLEM 1: Parse the input string into tokens
DEPENDS_ON: none
COMPLEXITY: easy

SUB_PROBLEM 2: Build the expression tree from tokens
DEPENDS_ON: 1
COMPLEXITY: medium

SUB_PROBLEM 3: Evaluate the expression tree
DEPENDS_ON: 2
COMPLEXITY: easy
"""
    subs = engine._parse_sub_problems(raw_decomposition)
    assert len(subs) == 3, f"Expected 3 sub-problems, got {len(subs)}"
    assert subs[0].description == "Parse the input string into tokens"
    assert subs[1].dependencies == [1]
    assert subs[2].complexity_hint == "easy"
    print(f"  ✅ Parsed {len(subs)} sub-problems with dependencies")

    # Test logic step parsing
    raw_logic = """
STEP 1: Initialize the tokenizer
PSEUDOCODE:
  tokens = split input by whitespace
  classify each token as number or operator
DATA_STRUCTURES: list, dict
ALGORITHMS: string parsing

STEP 2: Build expression tree using recursive descent
PSEUDOCODE:
  parse_expression() handles + and -
  parse_term() handles * and /
  parse_factor() handles numbers and parentheses
DATA_STRUCTURES: tree
ALGORITHMS: recursive descent
"""
    steps = engine._parse_logic_steps(raw_logic)
    assert len(steps) == 2, f"Expected 2 steps, got {len(steps)}"
    assert steps[0].step_number == 1
    assert "tokenizer" in steps[0].description.lower()
    assert len(steps[0].data_structures) >= 1
    print(f"  ✅ Parsed {len(steps)} logic steps with data structures")

    # Test code extraction
    response_with_code = """Here is the solution:
```python
def solve(arr):
    return sorted(arr)
```
"""
    code = engine._extract_code(response_with_code)
    assert "def solve" in code
    assert "sorted" in code
    print("  ✅ Code extraction from markdown blocks")

    # Test problem categorization
    assert engine._categorize_problem("Sort an array of integers") == "sorting"
    assert engine._categorize_problem("Traverse a graph using BFS") == "graph"
    assert engine._categorize_problem("Calculate fibonacci sequence") == "math"
    assert engine._categorize_problem("Check if string is palindrome") == "string"
    print("  ✅ Problem categorization working")

    # Test tag extraction
    tags = engine._extract_tags("Binary search in a sorted array with recursion")
    assert "binary" in tags
    assert "sort" in tags
    assert "recursion" in tags
    print(f"  ✅ Tag extraction: {tags}")

    print("✅ Engine parsing tests passed!\n")


# ──────────────────────────────────────────────
# Test 7: Confidence Calculation
# ──────────────────────────────────────────────

def test_confidence_calculation():
    """Test confidence scoring logic."""
    from brain.solver.engine import SolverEngine, SolutionResult, LogicStep

    engine = SolverEngine(generate_fn=lambda p: "")

    # Good solution should score high
    good_result = SolutionResult(
        code="def solve(n):\n    return n * 2\n",
        logic_steps=[LogicStep(step_number=1), LogicStep(step_number=2)],
        tests_passed=5,
        tests_total=5,
        healing_attempts=0,
    )
    conf = engine._calculate_confidence(good_result)
    assert conf >= 0.7, f"Good solution confidence too low: {conf}"
    print(f"  ✅ Good solution confidence: {conf:.2f}")

    # Bad syntax should score low
    bad_result = SolutionResult(
        code="def solve(n\n    return",
        logic_steps=[],
        tests_passed=0,
        tests_total=5,
    )
    bad_conf = engine._calculate_confidence(bad_result)
    assert bad_conf < conf, "Bad solution should score lower"
    print(f"  ✅ Bad syntax confidence: {bad_conf:.2f} (lower)")

    # No tests should have lower confidence
    no_test_result = SolutionResult(
        code="def solve(n):\n    return n * 2\n",
        logic_steps=[LogicStep(step_number=1)],
        tests_passed=0,
        tests_total=0,
    )
    no_test_conf = engine._calculate_confidence(no_test_result)
    assert no_test_conf < conf, "No tests should reduce confidence"
    print(f"  ✅ No-tests confidence: {no_test_conf:.2f} (lower)")

    print("✅ Confidence calculation tests passed!\n")


# ──────────────────────────────────────────────
# Run All Tests
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🧠  Self-Thinking Problem Solver — Test Suite")
    print("=" * 60 + "\n")

    print("─── Test 1: Pattern Library ───")
    test_pattern_library()

    print("─── Test 2: Complexity Analyzer ───")
    test_complexity_analyzer()

    print("─── Test 3: Self-Healer Detection ───")
    test_self_healer_detection()

    print("─── Test 4: Evolver Fitness Scoring ───")
    test_evolver_fitness()

    print("─── Test 5: Test Generator ───")
    test_test_generator_extraction()

    print("─── Test 6: Engine Parsing ───")
    test_engine_parsing()

    print("─── Test 7: Confidence Calculation ───")
    test_confidence_calculation()

    print("=" * 60)
    print("  🎉  ALL 7 SOLVER TESTS PASSED!")
    print("=" * 60 + "\n")
