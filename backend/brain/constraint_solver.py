"""
Constraint Satisfaction Solver — AC-3 + Backtracking Search
═══════════════════════════════════════════════════════════
General-purpose CSP solver with arc consistency and intelligent search.

No LLM, no GPU — pure algorithmic constraint solving.

Architecture:
  Problem Definition → Arc Consistency (AC-3)
                              ↓
                    Domain Reduction → Backtracking Search
                              ↓
                    MRV + LCV Heuristics → Solution

Capabilities:
  • N-Queens (any board size)
  • Sudoku (9×9)
  • Graph Coloring
  • Scheduling / Assignment
  • Cryptarithmetic
  • Custom CSPs
"""

import copy
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# CSP DEFINITION
# ═══════════════════════════════════════════════════════════

@dataclass
class Variable:
    """A CSP variable with its domain."""
    name: str
    domain: List[Any] = field(default_factory=list)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, Variable) and self.name == other.name


@dataclass
class Constraint:
    """A constraint between variables."""
    variables: List[str]  # Variable names involved
    check: Callable  # Function(assignment) → bool
    description: str = ""

    def is_satisfied(self, assignment: Dict[str, Any]) -> bool:
        """Check if constraint is satisfied by current assignment."""
        # Only check if all involved variables are assigned
        if not all(v in assignment for v in self.variables):
            return True  # Not all assigned yet — assume consistent
        return self.check(assignment)

    def is_consistent(self, assignment: Dict[str, Any], var: str, value: Any) -> bool:
        """Check if assigning var=value is consistent with constraint."""
        test_assignment = dict(assignment)
        test_assignment[var] = value
        # Only check if all involved variables are now assigned
        if all(v in test_assignment for v in self.variables):
            return self.check(test_assignment)
        return True


@dataclass
class CSP:
    """A Constraint Satisfaction Problem."""
    variables: Dict[str, Variable] = field(default_factory=dict)
    constraints: List[Constraint] = field(default_factory=list)

    def add_variable(self, name: str, domain: List[Any]) -> None:
        self.variables[name] = Variable(name, list(domain))

    def add_constraint(self, var_names: List[str], check: Callable,
                       description: str = "") -> None:
        self.constraints.append(Constraint(var_names, check, description))

    def add_all_different(self, var_names: List[str]) -> None:
        """Add all-different constraint: all listed variables must be different."""
        def check(assignment):
            vals = [assignment[v] for v in var_names if v in assignment]
            return len(vals) == len(set(vals))
        self.add_constraint(var_names, check, f"AllDifferent({', '.join(var_names)})")

    def add_not_equal(self, v1: str, v2: str) -> None:
        """Add inequality constraint: v1 ≠ v2."""
        self.add_constraint(
            [v1, v2],
            lambda a, _v1=v1, _v2=v2: a[_v1] != a[_v2],
            f"{v1} ≠ {v2}",
        )

    def add_sum_equals(self, var_names: List[str], target: int) -> None:
        """Add sum constraint: sum of variables = target."""
        def check(assignment):
            vals = [assignment[v] for v in var_names if v in assignment]
            if len(vals) == len(var_names):
                return sum(vals) == target
            return True
        self.add_constraint(var_names, check, f"Sum({', '.join(var_names)}) = {target}")

    def get_neighbors(self, var_name: str) -> Set[str]:
        """Get all variables that share a constraint with var_name."""
        neighbors = set()
        for c in self.constraints:
            if var_name in c.variables:
                for v in c.variables:
                    if v != var_name:
                        neighbors.add(v)
        return neighbors


# ═══════════════════════════════════════════════════════════
# ARC CONSISTENCY (AC-3)
# ═══════════════════════════════════════════════════════════

class AC3:
    """
    AC-3 Arc Consistency Algorithm.

    Reduces variable domains by enforcing arc consistency:
    For every pair (Xi, Xj) with a constraint, every value in Di
    must have at least one compatible value in Dj.
    """

    @staticmethod
    def enforce(csp: CSP) -> bool:
        """
        Enforce arc consistency on the CSP.

        Returns False if any domain becomes empty (no solution possible).
        Modifies domains in-place.
        """
        # Build queue of all arcs
        queue = deque()
        for constraint in csp.constraints:
            if len(constraint.variables) == 2:
                v1, v2 = constraint.variables
                queue.append((v1, v2, constraint))
                queue.append((v2, v1, constraint))

        while queue:
            xi_name, xj_name, constraint = queue.popleft()

            if AC3._revise(csp, xi_name, xj_name, constraint):
                if not csp.variables[xi_name].domain:
                    return False  # Domain wiped out — no solution

                # Re-add arcs from neighbors of Xi
                for neighbor in csp.get_neighbors(xi_name):
                    if neighbor != xj_name:
                        for c in csp.constraints:
                            if xi_name in c.variables and neighbor in c.variables:
                                queue.append((neighbor, xi_name, c))

        return True

    @staticmethod
    def _revise(csp: CSP, xi_name: str, xj_name: str,
                constraint: Constraint) -> bool:
        """Remove values from Xi's domain that have no support in Xj."""
        revised = False
        xi = csp.variables[xi_name]
        xj = csp.variables[xj_name]

        to_remove = []
        for val_i in xi.domain:
            # Check if any value in Xj is consistent
            has_support = False
            for val_j in xj.domain:
                test = {xi_name: val_i, xj_name: val_j}
                if constraint.check(test):
                    has_support = True
                    break
            if not has_support:
                to_remove.append(val_i)
                revised = True

        for val in to_remove:
            xi.domain.remove(val)

        return revised


# ═══════════════════════════════════════════════════════════
# BACKTRACKING SEARCH
# ═══════════════════════════════════════════════════════════

@dataclass
class CSPResult:
    """Result of CSP solving."""
    solved: bool = False
    solution: Dict[str, Any] = field(default_factory=dict)
    nodes_explored: int = 0
    backtracks: int = 0
    duration_ms: float = 0.0
    problem_type: str = ""

    @property
    def is_valid(self) -> bool:
        return self.solved

    def summary(self) -> str:
        status = "SOLVED ✓" if self.solved else "UNSOLVABLE"
        lines = [
            f"## Constraint Satisfaction — {status}",
            f"**Problem**: {self.problem_type}",
        ]
        if self.solved:
            lines.append(f"\n**Solution**:")
            for k, v in sorted(self.solution.items()):
                lines.append(f"  {k} = {v}")
        lines.append(f"\n| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Nodes explored | {self.nodes_explored} |")
        lines.append(f"| Backtracks | {self.backtracks} |")
        lines.append(f"| Duration | {self.duration_ms:.0f}ms |")
        return "\n".join(lines)


class BacktrackingSolver:
    """
    Backtracking search with:
      • MRV (Minimum Remaining Values) variable ordering
      • LCV (Least Constraining Value) value ordering
      • Forward checking (constraint propagation)
      • AC-3 as preprocessing
    """

    def __init__(self, use_ac3: bool = True, use_mrv: bool = True,
                 use_lcv: bool = True, use_forward_check: bool = True):
        self.use_ac3 = use_ac3
        self.use_mrv = use_mrv
        self.use_lcv = use_lcv
        self.use_forward_check = use_forward_check
        self._nodes_explored = 0
        self._backtracks = 0

    def solve(self, csp: CSP, timeout: float = 30.0) -> CSPResult:
        """Solve the CSP using backtracking with heuristics."""
        start = time.time()
        self._nodes_explored = 0
        self._backtracks = 0

        # Deep copy to avoid modifying original
        csp_copy = self._deep_copy_csp(csp)

        # Preprocessing: AC-3
        if self.use_ac3:
            if not AC3.enforce(csp_copy):
                return CSPResult(
                    solved=False,
                    duration_ms=(time.time() - start) * 1000,
                )

        # Backtrack
        assignment = {}
        solution = self._backtrack(csp_copy, assignment, start, timeout)

        result = CSPResult(
            solved=solution is not None,
            solution=solution or {},
            nodes_explored=self._nodes_explored,
            backtracks=self._backtracks,
            duration_ms=(time.time() - start) * 1000,
        )
        return result

    def _backtrack(
        self,
        csp: CSP,
        assignment: Dict[str, Any],
        start_time: float,
        timeout: float,
    ) -> Optional[Dict[str, Any]]:
        """Recursive backtracking with heuristics."""
        # Check timeout
        if time.time() - start_time > timeout:
            return None

        # All variables assigned?
        if len(assignment) == len(csp.variables):
            return dict(assignment)

        self._nodes_explored += 1

        # Select unassigned variable (MRV heuristic)
        var_name = self._select_variable(csp, assignment)
        if var_name is None:
            return None

        # Order domain values (LCV heuristic)
        values = self._order_values(csp, var_name, assignment)

        for value in values:
            # Check consistency
            if self._is_consistent(csp, var_name, value, assignment):
                assignment[var_name] = value

                # Forward checking
                if self.use_forward_check:
                    saved_domains = self._forward_check(csp, var_name, value, assignment)
                    if saved_domains is not None:
                        result = self._backtrack(csp, assignment, start_time, timeout)
                        if result is not None:
                            return result
                        # Restore domains
                        self._restore_domains(csp, saved_domains)
                else:
                    result = self._backtrack(csp, assignment, start_time, timeout)
                    if result is not None:
                        return result

                del assignment[var_name]
                self._backtracks += 1

        return None

    def _select_variable(self, csp: CSP, assignment: Dict[str, Any]) -> Optional[str]:
        """MRV: Select unassigned variable with fewest remaining values."""
        unassigned = [
            name for name in csp.variables if name not in assignment
        ]
        if not unassigned:
            return None

        if not self.use_mrv:
            return unassigned[0]

        # MRV + degree heuristic as tiebreaker
        def mrv_key(name):
            domain_size = len(csp.variables[name].domain)
            degree = len(csp.get_neighbors(name) - set(assignment.keys()))
            return (domain_size, -degree)

        return min(unassigned, key=mrv_key)

    def _order_values(self, csp: CSP, var_name: str,
                      assignment: Dict[str, Any]) -> List[Any]:
        """LCV: Order values by least constraining (most options left for neighbors)."""
        values = list(csp.variables[var_name].domain)

        if not self.use_lcv or len(values) <= 1:
            return values

        def lcv_score(value):
            count = 0
            for neighbor in csp.get_neighbors(var_name):
                if neighbor in assignment:
                    continue
                for nval in csp.variables[neighbor].domain:
                    test = dict(assignment)
                    test[var_name] = value
                    test[neighbor] = nval
                    if all(c.is_satisfied(test) for c in csp.constraints
                           if var_name in c.variables and neighbor in c.variables):
                        count += 1
            return count

        values.sort(key=lcv_score, reverse=True)
        return values

    def _is_consistent(self, csp: CSP, var_name: str, value: Any,
                       assignment: Dict[str, Any]) -> bool:
        """Check if assigning var=value is consistent with all constraints."""
        for constraint in csp.constraints:
            if var_name in constraint.variables:
                if not constraint.is_consistent(assignment, var_name, value):
                    return False
        return True

    def _forward_check(self, csp: CSP, var_name: str, value: Any,
                       assignment: Dict[str, Any]) -> Optional[Dict]:
        """Remove inconsistent values from neighbors' domains."""
        saved = {}

        for neighbor in csp.get_neighbors(var_name):
            if neighbor in assignment:
                continue

            saved[neighbor] = list(csp.variables[neighbor].domain)
            to_remove = []

            for nval in csp.variables[neighbor].domain:
                test = dict(assignment)
                test[neighbor] = nval
                consistent = all(
                    c.is_satisfied(test)
                    for c in csp.constraints
                    if neighbor in c.variables and var_name in c.variables
                )
                if not consistent:
                    to_remove.append(nval)

            for val in to_remove:
                csp.variables[neighbor].domain.remove(val)

            if not csp.variables[neighbor].domain:
                self._restore_domains(csp, saved)
                return None

        return saved

    @staticmethod
    def _restore_domains(csp: CSP, saved: Dict) -> None:
        for var_name, domain in saved.items():
            csp.variables[var_name].domain = domain

    @staticmethod
    def _deep_copy_csp(csp: CSP) -> CSP:
        new_csp = CSP()
        for name, var in csp.variables.items():
            new_csp.variables[name] = Variable(name, list(var.domain))
        new_csp.constraints = list(csp.constraints)
        return new_csp


# ═══════════════════════════════════════════════════════════
# PROBLEM BUILDERS — Classic CSP Problems
# ═══════════════════════════════════════════════════════════

class CSPBuilder:
    """Factory for classic CSP problems."""

    @staticmethod
    def n_queens(n: int = 8) -> CSP:
        """
        Build the N-Queens CSP.
        Variables: Q0..Qn-1 (row placement for each column)
        Domain: 0..n-1
        Constraints: No two queens on same row, or same diagonal
        """
        csp = CSP()

        for col in range(n):
            csp.add_variable(f"Q{col}", list(range(n)))

        for i in range(n):
            for j in range(i + 1, n):
                vi, vj = f"Q{i}", f"Q{j}"
                diff = j - i
                csp.add_constraint(
                    [vi, vj],
                    lambda a, _vi=vi, _vj=vj, _d=diff: (
                        a[_vi] != a[_vj] and
                        abs(a[_vi] - a[_vj]) != _d
                    ),
                    f"{vi} and {vj} not attacking",
                )

        return csp

    @staticmethod
    def sudoku(grid: List[List[int]]) -> CSP:
        """
        Build a Sudoku CSP from a 9×9 grid (0 = empty).

        Variables: C_r_c for each cell
        Domain: 1-9 for empty cells, fixed for givens
        Constraints: All-different in each row, column, and 3x3 box
        """
        csp = CSP()

        # Variables
        for r in range(9):
            for c in range(9):
                name = f"C{r}{c}"
                if grid[r][c] != 0:
                    csp.add_variable(name, [grid[r][c]])
                else:
                    csp.add_variable(name, list(range(1, 10)))

        # Row constraints
        for r in range(9):
            row_vars = [f"C{r}{c}" for c in range(9)]
            for i in range(9):
                for j in range(i + 1, 9):
                    csp.add_not_equal(row_vars[i], row_vars[j])

        # Column constraints
        for c in range(9):
            col_vars = [f"C{r}{c}" for r in range(9)]
            for i in range(9):
                for j in range(i + 1, 9):
                    csp.add_not_equal(col_vars[i], col_vars[j])

        # Box constraints
        for box_r in range(3):
            for box_c in range(3):
                box_vars = [
                    f"C{box_r*3+r}{box_c*3+c}"
                    for r in range(3) for c in range(3)
                ]
                for i in range(9):
                    for j in range(i + 1, 9):
                        csp.add_not_equal(box_vars[i], box_vars[j])

        return csp

    @staticmethod
    def graph_coloring(edges: List[Tuple[str, str]], n_colors: int = 3) -> CSP:
        """
        Build a Graph Coloring CSP.

        Variables: one per node
        Domain: colors 0..n_colors-1
        Constraints: adjacent nodes must have different colors
        """
        csp = CSP()

        # Collect all nodes
        nodes = set()
        for u, v in edges:
            nodes.add(u)
            nodes.add(v)

        for node in nodes:
            csp.add_variable(node, list(range(n_colors)))

        for u, v in edges:
            csp.add_not_equal(u, v)

        return csp

    @staticmethod
    def scheduling(
        tasks: List[str],
        durations: Dict[str, int],
        precedences: List[Tuple[str, str]],
        max_time: int = 20,
    ) -> CSP:
        """
        Build a Scheduling CSP.

        Variables: start time for each task
        Domain: 0..max_time
        Constraints: precedence (task A must finish before task B starts)
        """
        csp = CSP()

        for task in tasks:
            csp.add_variable(task, list(range(max_time + 1)))

        for before, after in precedences:
            dur = durations.get(before, 1)
            csp.add_constraint(
                [before, after],
                lambda a, _b=before, _a=after, _d=dur: a[_b] + _d <= a[_a],
                f"{before} + {dur} ≤ {after}",
            )

        return csp


# ═══════════════════════════════════════════════════════════
# MAIN SOLVER — Unified Interface
# ═══════════════════════════════════════════════════════════

class ConstraintSolver:
    """
    Unified Constraint Satisfaction Solver.

    Usage:
        solver = ConstraintSolver()

        # N-Queens
        result = solver.solve_n_queens(8)

        # Sudoku
        result = solver.solve_sudoku(grid)

        # Graph Coloring
        result = solver.solve_graph_coloring(edges, 3)

        # Custom CSP
        csp = CSP()
        csp.add_variable("x", [1, 2, 3])
        csp.add_variable("y", [1, 2, 3])
        csp.add_not_equal("x", "y")
        result = solver.solve_csp(csp)
    """

    def __init__(self):
        self.backend = BacktrackingSolver(
            use_ac3=True,
            use_mrv=True,
            use_lcv=True,
            use_forward_check=True,
        )
        self._stats = {"problems_solved": 0, "total_nodes": 0}

    def solve_csp(self, csp: CSP, timeout: float = 30.0) -> CSPResult:
        """Solve any CSP."""
        result = self.backend.solve(csp, timeout)
        self._stats["problems_solved"] += 1 if result.solved else 0
        self._stats["total_nodes"] += result.nodes_explored
        return result

    def solve_n_queens(self, n: int = 8) -> CSPResult:
        """Solve the N-Queens problem."""
        # Cap board size to prevent resource exhaustion
        n = max(1, min(n, 20))
        csp = CSPBuilder.n_queens(n)
        result = self.solve_csp(csp)
        result.problem_type = f"{n}-Queens"

        if result.solved:
            # Format as board
            board_lines = [f"\n### {n}-Queens Solution:"]
            board_lines.append("```")
            for row in range(n):
                line = ""
                for col in range(n):
                    if result.solution.get(f"Q{col}") == row:
                        line += " ♛"
                    else:
                        line += " ·"
                board_lines.append(line)
            board_lines.append("```")
            result.problem_type += "\n" + "\n".join(board_lines)

        return result

    def solve_sudoku(self, grid: List[List[int]]) -> CSPResult:
        """Solve a Sudoku puzzle (0 = empty)."""
        # Validate grid dimensions
        if len(grid) != 9 or any(len(row) != 9 for row in grid):
            return CSPResult(solved=False, problem_type="Sudoku 9×9 — invalid grid dimensions")
        csp = CSPBuilder.sudoku(grid)
        result = self.solve_csp(csp, timeout=60.0)
        result.problem_type = "Sudoku 9×9"

        if result.solved:
            # Format as grid
            lines = ["\n### Sudoku Solution:"]
            lines.append("```")
            for r in range(9):
                if r > 0 and r % 3 == 0:
                    lines.append("------+-------+------")
                row = ""
                for c in range(9):
                    if c > 0 and c % 3 == 0:
                        row += " |"
                    row += f" {result.solution.get(f'C{r}{c}', '?')}"
                lines.append(row)
            lines.append("```")
            result.problem_type += "\n" + "\n".join(lines)

        return result

    def solve_graph_coloring(self, edges: List[Tuple[str, str]],
                              n_colors: int = 3) -> CSPResult:
        """Solve a graph coloring problem."""
        csp = CSPBuilder.graph_coloring(edges, n_colors)
        result = self.solve_csp(csp)
        result.problem_type = f"Graph Coloring ({n_colors} colors)"
        return result

    def solve_scheduling(
        self,
        tasks: List[str],
        durations: Dict[str, int],
        precedences: List[Tuple[str, str]],
        max_time: int = 20,
    ) -> CSPResult:
        """Solve a scheduling problem."""
        csp = CSPBuilder.scheduling(tasks, durations, precedences, max_time)
        result = self.solve_csp(csp)
        result.problem_type = "Task Scheduling"
        return result

    def solve(self, prompt: str) -> CSPResult:
        """Natural language interface for constraint solving."""
        prompt_lower = prompt.lower()

        # N-Queens
        queens_match = re.search(r'(\d+)[\s-]*queens?', prompt_lower)
        if queens_match:
            n = int(queens_match.group(1))
            return self.solve_n_queens(min(n, 20))

        if 'queen' in prompt_lower:
            return self.solve_n_queens(8)

        # Sudoku
        if 'sudoku' in prompt_lower:
            # Try to extract grid from prompt
            numbers = re.findall(r'\d', prompt)
            if len(numbers) >= 81:
                grid = []
                for i in range(9):
                    row = [int(numbers[i * 9 + j]) for j in range(9)]
                    grid.append(row)
                return self.solve_sudoku(grid)

        # Graph coloring
        if 'color' in prompt_lower or 'graph' in prompt_lower:
            # Default example
            edges = [("A", "B"), ("A", "C"), ("B", "C"), ("C", "D")]
            return self.solve_graph_coloring(edges, 3)

        return CSPResult()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "ConstraintSolver",
            "problems_solved": self._stats["problems_solved"],
            "total_nodes_explored": self._stats["total_nodes"],
        }
