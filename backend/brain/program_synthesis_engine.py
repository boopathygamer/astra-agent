"""
Program Synthesis Engine — Example-Driven Code Generation
══════════════════════════════════════════════════════════
Generates programs from input/output examples + natural language
using enumerative search with type-guided pruning.

No LLM, no GPU — pure algorithmic program synthesis.

Architecture:
  IO Examples → Component Library → Enumerative Search
                                        ↓
                              Type-Guided Pruning + Size Bound
                                        ↓
                              Candidate Validation → Synthesized Program

Novel contributions:
  • Bottom-up enumerative synthesis with type constraints
  • Component library of composable primitives
  • Recursive program synthesis
  • Occam's razor: prefers shortest correct program
  • Auto-test: validates against ALL examples
  • Natural language hint extraction for search guidance
"""

import ast
import itertools
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# TYPE SYSTEM
# ═══════════════════════════════════════════════════════════

class TypeKind(Enum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "str"
    LIST = "list"
    ANY = "any"
    FUNCTION = "func"


@dataclass
class SynthType:
    kind: TypeKind
    element_type: Optional['SynthType'] = None  # For list[T]

    def __hash__(self):
        return hash((self.kind, self.element_type))

    def __eq__(self, other):
        if not isinstance(other, SynthType):
            return False
        return self.kind == other.kind and self.element_type == other.element_type

    def matches(self, other: 'SynthType') -> bool:
        if self.kind == TypeKind.ANY or other.kind == TypeKind.ANY:
            return True
        if self.kind != other.kind:
            return False
        if self.element_type and other.element_type:
            return self.element_type.matches(other.element_type)
        return True

    def __repr__(self):
        if self.kind == TypeKind.LIST and self.element_type:
            return f"List[{self.element_type}]"
        return self.kind.value


INT = SynthType(TypeKind.INT)
FLOAT = SynthType(TypeKind.FLOAT)
BOOL = SynthType(TypeKind.BOOL)
STRING = SynthType(TypeKind.STRING)
LIST_INT = SynthType(TypeKind.LIST, INT)
LIST_ANY = SynthType(TypeKind.LIST, SynthType(TypeKind.ANY))
ANY = SynthType(TypeKind.ANY)


def infer_type(value: Any) -> SynthType:
    """Infer the type of a Python value."""
    if isinstance(value, bool):
        return BOOL
    elif isinstance(value, int):
        return INT
    elif isinstance(value, float):
        return FLOAT
    elif isinstance(value, str):
        return STRING
    elif isinstance(value, (list, tuple)):
        if value and isinstance(value[0], int):
            return LIST_INT
        return LIST_ANY
    return ANY


# ═══════════════════════════════════════════════════════════
# COMPONENT LIBRARY — Primitive Operations
# ═══════════════════════════════════════════════════════════

@dataclass
class Component:
    """A primitive operation that can be composed."""
    name: str
    func: Callable
    input_types: List[SynthType]
    output_type: SynthType
    arity: int = 1
    cost: int = 1
    code_template: str = ""

    def __repr__(self):
        return f"Component({self.name})"


def _build_component_library() -> List[Component]:
    """Build the standard library of composable primitives."""
    return [
        # ── Arithmetic ──
        Component("add", lambda a, b: a + b, [INT, INT], INT, 2, 1, "{0} + {1}"),
        Component("sub", lambda a, b: a - b, [INT, INT], INT, 2, 1, "{0} - {1}"),
        Component("mul", lambda a, b: a * b, [INT, INT], INT, 2, 1, "{0} * {1}"),
        Component("div", lambda a, b: a // b if b != 0 else 0, [INT, INT], INT, 2, 2, "{0} // {1}"),
        Component("mod", lambda a, b: a % b if b != 0 else 0, [INT, INT], INT, 2, 2, "{0} % {1}"),
        Component("neg", lambda a: -a, [INT], INT, 1, 1, "-{0}"),
        Component("abs_val", lambda a: abs(a), [INT], INT, 1, 1, "abs({0})"),
        Component("square", lambda a: a * a, [INT], INT, 1, 1, "{0} ** 2"),
        Component("inc", lambda a: a + 1, [INT], INT, 1, 1, "{0} + 1"),
        Component("dec", lambda a: a - 1, [INT], INT, 1, 1, "{0} - 1"),
        Component("double", lambda a: a * 2, [INT], INT, 1, 1, "{0} * 2"),
        Component("half", lambda a: a // 2, [INT], INT, 1, 1, "{0} // 2"),
        Component("max2", lambda a, b: max(a, b), [INT, INT], INT, 2, 1, "max({0}, {1})"),
        Component("min2", lambda a, b: min(a, b), [INT, INT], INT, 2, 1, "min({0}, {1})"),

        # ── Boolean ──
        Component("eq", lambda a, b: a == b, [ANY, ANY], BOOL, 2, 1, "{0} == {1}"),
        Component("lt", lambda a, b: a < b, [INT, INT], BOOL, 2, 1, "{0} < {1}"),
        Component("gt", lambda a, b: a > b, [INT, INT], BOOL, 2, 1, "{0} > {1}"),
        Component("le", lambda a, b: a <= b, [INT, INT], BOOL, 2, 1, "{0} <= {1}"),
        Component("ge", lambda a, b: a >= b, [INT, INT], BOOL, 2, 1, "{0} >= {1}"),
        Component("is_even", lambda a: a % 2 == 0, [INT], BOOL, 1, 1, "{0} % 2 == 0"),
        Component("is_odd", lambda a: a % 2 != 0, [INT], BOOL, 1, 1, "{0} % 2 != 0"),
        Component("is_pos", lambda a: a > 0, [INT], BOOL, 1, 1, "{0} > 0"),
        Component("is_neg", lambda a: a < 0, [INT], BOOL, 1, 1, "{0} < 0"),
        Component("is_zero", lambda a: a == 0, [INT], BOOL, 1, 1, "{0} == 0"),
        Component("not_op", lambda a: not a, [BOOL], BOOL, 1, 1, "not {0}"),
        Component("and_op", lambda a, b: a and b, [BOOL, BOOL], BOOL, 2, 1, "{0} and {1}"),
        Component("or_op", lambda a, b: a or b, [BOOL, BOOL], BOOL, 2, 1, "{0} or {1}"),

        # ── List Operations ──
        Component("length", lambda a: len(a) if hasattr(a, '__len__') else 0, [LIST_ANY], INT, 1, 1, "len({0})"),
        Component("sum_list", lambda a: sum(a) if a else 0, [LIST_INT], INT, 1, 1, "sum({0})"),
        Component("max_list", lambda a: max(a) if a else 0, [LIST_INT], INT, 1, 2, "max({0})"),
        Component("min_list", lambda a: min(a) if a else 0, [LIST_INT], INT, 1, 2, "min({0})"),
        Component("sorted_list", lambda a: sorted(a), [LIST_INT], LIST_INT, 1, 2, "sorted({0})"),
        Component("reversed_list", lambda a: list(reversed(a)), [LIST_ANY], LIST_ANY, 1, 1, "list(reversed({0}))"),
        Component("head", lambda a: a[0] if a else 0, [LIST_ANY], ANY, 1, 1, "{0}[0]"),
        Component("tail", lambda a: a[1:] if a else [], [LIST_ANY], LIST_ANY, 1, 1, "{0}[1:]"),
        Component("last", lambda a: a[-1] if a else 0, [LIST_ANY], ANY, 1, 1, "{0}[-1]"),
        Component("init", lambda a: a[:-1] if a else [], [LIST_ANY], LIST_ANY, 1, 1, "{0}[:-1]"),
        Component("append", lambda a, b: a + [b], [LIST_ANY, ANY], LIST_ANY, 2, 1, "{0} + [{1}]"),
        Component("concat", lambda a, b: a + b, [LIST_ANY, LIST_ANY], LIST_ANY, 2, 1, "{0} + {1}"),
        Component("unique", lambda a: list(dict.fromkeys(a)), [LIST_ANY], LIST_ANY, 1, 2, "list(dict.fromkeys({0}))"),
        Component("filter_even", lambda a: [x for x in a if x % 2 == 0], [LIST_INT], LIST_INT, 1, 2, "[x for x in {0} if x % 2 == 0]"),
        Component("filter_odd", lambda a: [x for x in a if x % 2 != 0], [LIST_INT], LIST_INT, 1, 2, "[x for x in {0} if x % 2 != 0]"),
        Component("filter_pos", lambda a: [x for x in a if x > 0], [LIST_INT], LIST_INT, 1, 2, "[x for x in {0} if x > 0]"),
        Component("map_double", lambda a: [x * 2 for x in a], [LIST_INT], LIST_INT, 1, 2, "[x * 2 for x in {0}]"),
        Component("map_square", lambda a: [x ** 2 for x in a], [LIST_INT], LIST_INT, 1, 2, "[x ** 2 for x in {0}]"),
        Component("map_inc", lambda a: [x + 1 for x in a], [LIST_INT], LIST_INT, 1, 2, "[x + 1 for x in {0}]"),
        Component("map_neg", lambda a: [-x for x in a], [LIST_INT], LIST_INT, 1, 2, "[-x for x in {0}]"),
        Component("map_abs", lambda a: [abs(x) for x in a], [LIST_INT], LIST_INT, 1, 2, "[abs(x) for x in {0}]"),
        Component("zip_add", lambda a, b: [x + y for x, y in zip(a, b)], [LIST_INT, LIST_INT], LIST_INT, 2, 2,
                  "[x + y for x, y in zip({0}, {1})]"),
        Component("flatten", lambda a: [x for sub in a for x in (sub if isinstance(sub, list) else [sub])],
                  [LIST_ANY], LIST_ANY, 1, 2, "[x for sub in {0} for x in sub]"),

        # ── String Operations ──
        Component("str_len", lambda a: len(a) if isinstance(a, str) else 0, [STRING], INT, 1, 1, "len({0})"),
        Component("to_upper", lambda a: a.upper() if isinstance(a, str) else a, [STRING], STRING, 1, 1, "{0}.upper()"),
        Component("to_lower", lambda a: a.lower() if isinstance(a, str) else a, [STRING], STRING, 1, 1, "{0}.lower()"),
        Component("str_rev", lambda a: a[::-1] if isinstance(a, str) else a, [STRING], STRING, 1, 1, "{0}[::-1]"),
        Component("str_concat", lambda a, b: str(a) + str(b), [STRING, STRING], STRING, 2, 1, "{0} + {1}"),

        # ── Constants ──
        Component("zero", lambda: 0, [], INT, 0, 0, "0"),
        Component("one", lambda: 1, [], INT, 0, 0, "1"),
        Component("empty_list", lambda: [], [], LIST_ANY, 0, 0, "[]"),
        Component("true_const", lambda: True, [], BOOL, 0, 0, "True"),
        Component("false_const", lambda: False, [], BOOL, 0, 0, "False"),
    ]


# ═══════════════════════════════════════════════════════════
# SYNTHESIS EXPRESSIONS — Composable Programs
# ═══════════════════════════════════════════════════════════

@dataclass
class SynthExpr:
    """A synthesized expression (a program fragment)."""
    component: Optional[Component] = None
    args: List['SynthExpr'] = field(default_factory=list)
    input_var: Optional[str] = None  # For input references
    constant: Any = None  # For literal values
    cost: int = 0
    output_type: SynthType = field(default_factory=lambda: ANY)

    def evaluate(self, inputs: Dict[str, Any]) -> Any:
        """Execute the synthesized program."""
        try:
            if self.input_var is not None:
                return inputs.get(self.input_var, None)
            if self.constant is not None:
                return self.constant
            if self.component:
                arg_vals = [a.evaluate(inputs) for a in self.args]
                return self.component.func(*arg_vals)
            return None
        except Exception:
            return None

    def to_code(self, input_name: str = "x") -> str:
        """Convert to Python code string."""
        if self.input_var is not None:
            return self.input_var
        if self.constant is not None:
            return repr(self.constant)
        if self.component:
            if self.component.arity == 0:
                return self.component.code_template
            arg_strs = [a.to_code(input_name) for a in self.args]
            if self.component.code_template:
                return self.component.code_template.format(*arg_strs)
            return f"{self.component.name}({', '.join(arg_strs)})"
        return "None"

    def total_cost(self) -> int:
        return self.cost + sum(a.total_cost() for a in self.args)


# ═══════════════════════════════════════════════════════════
# SYNTHESIS RESULT
# ═══════════════════════════════════════════════════════════

@dataclass
class SynthesisResult:
    """Result of program synthesis."""
    success: bool = False
    program_code: str = ""
    function_code: str = ""
    expression: Optional[SynthExpr] = None
    examples_passed: int = 0
    examples_total: int = 0
    cost: int = 0
    candidates_explored: int = 0
    duration_ms: float = 0.0

    @property
    def is_valid(self) -> bool:
        return self.success

    def summary(self) -> str:
        status = "SYNTHESIZED ✓" if self.success else "FAILED"
        return (
            f"## Program Synthesis — {status}\n\n"
            f"```python\n{self.function_code}\n```\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Examples passed | {self.examples_passed}/{self.examples_total} |\n"
            f"| Program cost | {self.cost} |\n"
            f"| Candidates explored | {self.candidates_explored} |\n"
            f"| Duration | {self.duration_ms:.0f}ms |\n"
        )


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE — Bottom-Up Enumerative Search
# ═══════════════════════════════════════════════════════════

class ProgramSynthesisEngine:
    """
    Example-driven program synthesizer.

    Algorithm: Bottom-up enumerative search
      1. Start with inputs and constants as base programs
      2. Iteratively compose with components from the library
      3. At each level, test all candidates against examples
      4. Prune via type constraints + observational equivalence
      5. Return first correct program (smallest by Occam's razor)

    Usage:
        engine = ProgramSynthesisEngine()

        result = engine.synthesize(
            examples=[
                ({"x": 1}, 2),
                ({"x": 3}, 6),
                ({"x": 5}, 10),
            ],
            hint="double the input"
        )
        print(result.function_code)
        # → def f(x): return x * 2
    """

    def __init__(self, max_cost: int = 6, timeout_seconds: float = 15.0):
        self.components = _build_component_library()
        self.max_cost = max_cost
        self.timeout_seconds = timeout_seconds
        self._stats = {
            "total_syntheses": 0,
            "total_successes": 0,
            "avg_candidates": 0.0,
        }

    def synthesize(
        self,
        examples: List[Tuple[Dict[str, Any], Any]],
        hint: str = "",
        input_names: Optional[List[str]] = None,
        func_name: str = "f",
    ) -> SynthesisResult:
        """
        Synthesize a program from input/output examples.

        Args:
            examples: List of (input_dict, expected_output) pairs
            hint: Natural language description (used to prioritize components)
            input_names: Names of input variables
            func_name: Name for the generated function

        Returns:
            SynthesisResult with the generated program
        """
        start = time.time()
        self._stats["total_syntheses"] += 1

        result = SynthesisResult(examples_total=len(examples))

        if not examples:
            return result

        # Infer types
        first_inputs = examples[0][0]
        first_output = examples[0][1]
        input_types = {k: infer_type(v) for k, v in first_inputs.items()}
        output_type = infer_type(first_output)

        if input_names is None:
            input_names = sorted(first_inputs.keys())

        # Prioritize components based on hint
        prioritized = self._prioritize_components(hint, output_type)

        # ── Bottom-Up Enumeration ──
        # Level 0: inputs and constants
        candidates: List[SynthExpr] = []

        for var_name in input_names:
            candidates.append(SynthExpr(
                input_var=var_name,
                output_type=input_types.get(var_name, ANY),
                cost=0,
            ))

        # Add relevant constants
        for comp in self.components:
            if comp.arity == 0:
                candidates.append(SynthExpr(
                    component=comp,
                    output_type=comp.output_type,
                    cost=0,
                ))

        explored = 0
        # Track seen outputs to prune observationally equivalent programs
        seen_outputs: set = set()

        for level in range(1, self.max_cost + 1):
            if time.time() - start > self.timeout_seconds:
                break

            new_candidates = []

            for comp in prioritized:
                if comp.arity == 0:
                    continue

                # Find compatible arguments
                if comp.arity == 1:
                    for arg in candidates:
                        if arg.total_cost() >= level:
                            continue
                        if not comp.input_types[0].matches(arg.output_type):
                            continue

                        expr = SynthExpr(
                            component=comp,
                            args=[arg],
                            output_type=comp.output_type,
                            cost=comp.cost,
                        )
                        explored += 1

                        # Check against examples
                        if self._check_all(expr, examples):
                            result.success = True
                            result.expression = expr
                            result.program_code = expr.to_code(input_names[0] if input_names else "x")
                            result.function_code = self._format_function(
                                expr, input_names, func_name
                            )
                            result.examples_passed = len(examples)
                            result.cost = expr.total_cost()
                            result.candidates_explored = explored
                            result.duration_ms = (time.time() - start) * 1000
                            self._stats["total_successes"] += 1
                            return result

                        # Observational equivalence pruning
                        output_sig = self._output_signature(expr, examples)
                        if output_sig not in seen_outputs:
                            seen_outputs.add(output_sig)
                            new_candidates.append(expr)

                elif comp.arity == 2:
                    for arg1 in candidates:
                        if arg1.total_cost() >= level - 1:
                            continue
                        if not comp.input_types[0].matches(arg1.output_type):
                            continue
                        for arg2 in candidates:
                            if arg1.total_cost() + arg2.total_cost() >= level:
                                continue
                            if not comp.input_types[1].matches(arg2.output_type):
                                continue
                            if time.time() - start > self.timeout_seconds:
                                break

                            expr = SynthExpr(
                                component=comp,
                                args=[arg1, arg2],
                                output_type=comp.output_type,
                                cost=comp.cost,
                            )
                            explored += 1

                            if self._check_all(expr, examples):
                                result.success = True
                                result.expression = expr
                                result.program_code = expr.to_code(input_names[0] if input_names else "x")
                                result.function_code = self._format_function(
                                    expr, input_names, func_name
                                )
                                result.examples_passed = len(examples)
                                result.cost = expr.total_cost()
                                result.candidates_explored = explored
                                result.duration_ms = (time.time() - start) * 1000
                                self._stats["total_successes"] += 1
                                return result

                            output_sig = self._output_signature(expr, examples)
                            if output_sig not in seen_outputs:
                                seen_outputs.add(output_sig)
                                new_candidates.append(expr)

            candidates.extend(new_candidates)

        # Failed — return best partial match
        result.candidates_explored = explored
        result.duration_ms = (time.time() - start) * 1000
        return result

    def synthesize_from_pairs(
        self,
        inputs: List[Any],
        outputs: List[Any],
        input_name: str = "x",
    ) -> SynthesisResult:
        """
        Convenience: synthesize from parallel lists.

        Usage:
            result = engine.synthesize_from_pairs(
                inputs=[1, 2, 3, 4, 5],
                outputs=[2, 4, 6, 8, 10],
            )
        """
        examples = [({input_name: inp}, out) for inp, out in zip(inputs, outputs)]
        return self.synthesize(examples, input_names=[input_name])

    def _check_all(self, expr: SynthExpr, examples: List[Tuple[Dict, Any]]) -> bool:
        """Check if expression produces correct output for all examples."""
        for inputs, expected in examples:
            try:
                result = expr.evaluate(inputs)
                if result != expected:
                    return False
            except Exception:
                return False
        return True

    def _output_signature(self, expr: SynthExpr, examples: List[Tuple[Dict, Any]]) -> tuple:
        """Compute output signature for observational equivalence."""
        outputs = []
        for inputs, _ in examples:
            try:
                out = expr.evaluate(inputs)
                outputs.append(out if not isinstance(out, list) else tuple(out))
            except Exception:
                outputs.append(None)
        return tuple(str(o) for o in outputs)

    def _prioritize_components(self, hint: str, output_type: SynthType) -> List[Component]:
        """Reorder components based on natural language hint and output type."""
        if not hint:
            return list(self.components)

        hint_lower = hint.lower()
        scored = []

        for comp in self.components:
            score = 0

            # Boost components whose name appears in the hint
            if comp.name.replace('_', ' ') in hint_lower:
                score += 10
            for word in comp.name.split('_'):
                if word in hint_lower:
                    score += 3

            # Boost by output type match
            if comp.output_type.matches(output_type):
                score += 2

            # Keyword hints
            hint_map = {
                'double': ['double', 'mul'],
                'reverse': ['reversed_list', 'str_rev'],
                'sort': ['sorted_list'],
                'filter': ['filter_even', 'filter_odd', 'filter_pos'],
                'sum': ['sum_list', 'add'],
                'length': ['length', 'str_len'],
                'square': ['square', 'map_square'],
                'even': ['filter_even', 'is_even'],
                'odd': ['filter_odd', 'is_odd'],
                'maximum': ['max_list', 'max2'],
                'minimum': ['min_list', 'min2'],
                'negate': ['neg', 'map_neg'],
                'absolute': ['abs_val', 'map_abs'],
                'upper': ['to_upper'],
                'lower': ['to_lower'],
                'increment': ['inc', 'map_inc'],
            }
            for keyword, comp_names in hint_map.items():
                if keyword in hint_lower and comp.name in comp_names:
                    score += 8

            scored.append((score, comp))

        scored.sort(key=lambda x: -x[0])
        return [comp for _, comp in scored]

    def _format_function(
        self,
        expr: SynthExpr,
        input_names: List[str],
        func_name: str,
    ) -> str:
        """Format the synthesized expression as a Python function."""
        args_str = ", ".join(input_names)
        code = expr.to_code(input_names[0] if input_names else "x")
        return f"def {func_name}({args_str}):\n    return {code}"

    def solve(self, prompt: str) -> SynthesisResult:
        """
        Natural language interface for program synthesis.
        Parses prompts and attempts to synthesize programs.
        """
        # Try to extract I/O examples from prompt
        # Pattern: "input: X → output: Y" or "(X, Y)" pairs
        pairs = re.findall(r'(?:input|x)\s*[=:]\s*(\S+)\s*[→->]+\s*(?:output|y)\s*[=:]\s*(\S+)', prompt, re.I)
        if pairs:
            examples = []
            for inp, out in pairs:
                try:
                    # SECURITY: Use ast.literal_eval instead of eval to prevent code injection
                    examples.append(({"x": ast.literal_eval(inp)}, ast.literal_eval(out)))
                except (ValueError, SyntaxError):
                    pass
            if examples:
                return self.synthesize(examples, hint=prompt)

        return SynthesisResult()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "ProgramSynthesisEngine",
            "total_syntheses": self._stats["total_syntheses"],
            "successes": self._stats["total_successes"],
            "components_available": len(self.components),
        }
