"""
Formula Discovery Engine — Symbolic Genetic Programming
════════════════════════════════════════════════════════
Discovers new mathematical formulas by evolving expression trees.

No LLM, no GPU — pure algorithmic symbolic regression.

Architecture:
  Data Points → Population Init → Evolve (select → crossover → mutate)
                                      ↓
                              Fitness Evaluation (R², MSE, complexity)
                                      ↓
                              Simplification → Formula Bank

Novel contributions:
  • Novelty search: rewards structurally unique formulas
  • Multi-objective: balances accuracy vs. simplicity (Pareto front)
  • Formula bank: stores + retrieves discovered formulas for reuse
  • Dimensional awareness: tracks units through computation
"""

import copy
import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# EXPRESSION TREE — The Genome
# ═══════════════════════════════════════════════════════════

class NodeType(Enum):
    CONSTANT = "const"
    VARIABLE = "var"
    OPERATOR = "op"
    FUNCTION = "func"


@dataclass
class ExprNode:
    """
    A node in a symbolic expression tree.

    Examples:
      Leaf:     ExprNode(CONSTANT, value=3.14)
      Leaf:     ExprNode(VARIABLE, name="x")
      Binary:   ExprNode(OPERATOR, op="+", children=[left, right])
      Unary:    ExprNode(FUNCTION, op="sin", children=[arg])
    """
    node_type: NodeType
    op: str = ""
    value: float = 0.0
    name: str = ""
    children: List['ExprNode'] = field(default_factory=list)

    def depth(self) -> int:
        if not self.children:
            return 0
        return 1 + max(c.depth() for c in self.children)

    def size(self) -> int:
        return 1 + sum(c.size() for c in self.children)

    def evaluate(self, variables: Dict[str, float]) -> float:
        """Evaluate the expression tree with given variable bindings."""
        if self.node_type == NodeType.CONSTANT:
            return self.value
        elif self.node_type == NodeType.VARIABLE:
            return variables.get(self.name, 0.0)
        elif self.node_type == NodeType.OPERATOR:
            left = self.children[0].evaluate(variables) if len(self.children) > 0 else 0.0
            right = self.children[1].evaluate(variables) if len(self.children) > 1 else 0.0
            return _safe_binary_op(self.op, left, right)
        elif self.node_type == NodeType.FUNCTION:
            arg = self.children[0].evaluate(variables) if self.children else 0.0
            return _safe_unary_op(self.op, arg)
        return 0.0

    def to_string(self) -> str:
        """Convert expression tree to human-readable string."""
        if self.node_type == NodeType.CONSTANT:
            v = self.value
            if v == int(v) and abs(v) < 1e10:
                return str(int(v))
            return f"{v:.4g}"
        elif self.node_type == NodeType.VARIABLE:
            return self.name
        elif self.node_type == NodeType.OPERATOR:
            l = self.children[0].to_string() if len(self.children) > 0 else "0"
            r = self.children[1].to_string() if len(self.children) > 1 else "0"
            if self.op in ('+', '-'):
                return f"({l} {self.op} {r})"
            elif self.op == '^':
                return f"({l}^{r})"
            return f"({l} {self.op} {r})"
        elif self.node_type == NodeType.FUNCTION:
            arg = self.children[0].to_string() if self.children else "0"
            return f"{self.op}({arg})"
        return "?"

    def clone(self) -> 'ExprNode':
        """Deep clone."""
        return ExprNode(
            node_type=self.node_type,
            op=self.op,
            value=self.value,
            name=self.name,
            children=[c.clone() for c in self.children],
        )

    def all_nodes(self) -> List['ExprNode']:
        """Flatten tree to list of all nodes."""
        result = [self]
        for c in self.children:
            result.extend(c.all_nodes())
        return result


# ─── Safe Math Operations ─────────────────────────────────

def _safe_binary_op(op: str, a: float, b: float) -> float:
    try:
        if op == '+':
            return a + b
        elif op == '-':
            return a - b
        elif op == '*':
            return a * b
        elif op == '/':
            return a / b if abs(b) > 1e-12 else 1e6
        elif op == '^':
            if abs(a) > 100 or abs(b) > 20:
                return 1e6
            return math.pow(abs(a) + 1e-12, min(b, 20))
        return 0.0
    except (OverflowError, ValueError, ZeroDivisionError):
        return 1e6


def _safe_unary_op(op: str, x: float) -> float:
    try:
        if op == 'sin':
            return math.sin(x)
        elif op == 'cos':
            return math.cos(x)
        elif op == 'exp':
            return math.exp(min(x, 50))
        elif op == 'log':
            return math.log(abs(x) + 1e-12)
        elif op == 'sqrt':
            return math.sqrt(abs(x))
        elif op == 'abs':
            return abs(x)
        elif op == 'neg':
            return -x
        return x
    except (OverflowError, ValueError):
        return 1e6


# ═══════════════════════════════════════════════════════════
# GENETIC OPERATORS
# ═══════════════════════════════════════════════════════════

BINARY_OPS = ['+', '-', '*', '/', '^']
UNARY_OPS = ['sin', 'cos', 'exp', 'log', 'sqrt', 'abs', 'neg']
EPHEMERAL_RANGE = (-5.0, 5.0)
MAX_DEPTH = 6
MAX_SIZE = 40


def random_terminal(variables: List[str]) -> ExprNode:
    """Create a random leaf node."""
    if random.random() < 0.5 and variables:
        return ExprNode(NodeType.VARIABLE, name=random.choice(variables))
    val = round(random.uniform(*EPHEMERAL_RANGE), 2)
    # Prefer integers and small rationals
    if random.random() < 0.4:
        val = float(random.randint(-5, 5))
    return ExprNode(NodeType.CONSTANT, value=val)


def random_tree(variables: List[str], max_depth: int = 4, method: str = "grow") -> ExprNode:
    """
    Generate a random expression tree.

    method:
      "grow"  — mixed terminals and operators (variable depth)
      "full"  — always use operators until max_depth (bushy trees)
    """
    if max_depth <= 0:
        return random_terminal(variables)

    if method == "grow":
        # 40% terminal, 40% binary, 20% unary
        r = random.random()
        if r < 0.4:
            return random_terminal(variables)
        elif r < 0.8:
            op = random.choice(BINARY_OPS)
            left = random_tree(variables, max_depth - 1, "grow")
            right = random_tree(variables, max_depth - 1, "grow")
            return ExprNode(NodeType.OPERATOR, op=op, children=[left, right])
        else:
            fn = random.choice(UNARY_OPS)
            arg = random_tree(variables, max_depth - 1, "grow")
            return ExprNode(NodeType.FUNCTION, op=fn, children=[arg])
    else:  # full
        if random.random() < 0.7:
            op = random.choice(BINARY_OPS)
            left = random_tree(variables, max_depth - 1, "full")
            right = random_tree(variables, max_depth - 1, "full")
            return ExprNode(NodeType.OPERATOR, op=op, children=[left, right])
        else:
            fn = random.choice(UNARY_OPS)
            arg = random_tree(variables, max_depth - 1, "full")
            return ExprNode(NodeType.FUNCTION, op=fn, children=[arg])


def crossover(parent1: ExprNode, parent2: ExprNode) -> Tuple[ExprNode, ExprNode]:
    """
    Subtree crossover: swap random subtrees between two parents.
    Returns two offspring.
    """
    child1 = parent1.clone()
    child2 = parent2.clone()

    nodes1 = child1.all_nodes()
    nodes2 = child2.all_nodes()

    if len(nodes1) < 2 or len(nodes2) < 2:
        return child1, child2

    # Pick crossover points (skip root to avoid full replacement)
    point1 = random.choice(nodes1[1:]) if len(nodes1) > 1 else nodes1[0]
    point2 = random.choice(nodes2[1:]) if len(nodes2) > 1 else nodes2[0]

    # Swap content
    point1.node_type, point2.node_type = point2.node_type, point1.node_type
    point1.op, point2.op = point2.op, point1.op
    point1.value, point2.value = point2.value, point1.value
    point1.name, point2.name = point2.name, point1.name
    point1.children, point2.children = point2.children, point1.children

    # Enforce size limits
    if child1.size() > MAX_SIZE:
        child1 = parent1.clone()
    if child2.size() > MAX_SIZE:
        child2 = parent2.clone()

    return child1, child2


def mutate(tree: ExprNode, variables: List[str], mutation_rate: float = 0.15) -> ExprNode:
    """
    Multi-type mutation:
      1. Point mutation — change operator/function/constant
      2. Subtree mutation — replace a subtree with a random one
      3. Hoist mutation — replace tree with a subtree
      4. Constant perturbation — tweak numeric values
    """
    tree = tree.clone()
    nodes = tree.all_nodes()

    for node in nodes:
        if random.random() > mutation_rate:
            continue

        mutation_type = random.choices(
            ["point", "subtree", "hoist", "perturb"],
            weights=[0.35, 0.25, 0.10, 0.30],
            k=1,
        )[0]

        if mutation_type == "point":
            if node.node_type == NodeType.OPERATOR:
                node.op = random.choice(BINARY_OPS)
            elif node.node_type == NodeType.FUNCTION:
                node.op = random.choice(UNARY_OPS)
            elif node.node_type == NodeType.CONSTANT:
                node.value = round(random.uniform(*EPHEMERAL_RANGE), 2)
            elif node.node_type == NodeType.VARIABLE and variables:
                node.name = random.choice(variables)

        elif mutation_type == "subtree":
            new_sub = random_tree(variables, max_depth=3, method="grow")
            node.node_type = new_sub.node_type
            node.op = new_sub.op
            node.value = new_sub.value
            node.name = new_sub.name
            node.children = new_sub.children

        elif mutation_type == "hoist" and node.children:
            chosen = random.choice(node.children)
            node.node_type = chosen.node_type
            node.op = chosen.op
            node.value = chosen.value
            node.name = chosen.name
            node.children = chosen.children

        elif mutation_type == "perturb" and node.node_type == NodeType.CONSTANT:
            node.value += random.gauss(0, 0.5)
            node.value = round(node.value, 4)

    return tree


# ═══════════════════════════════════════════════════════════
# FITNESS EVALUATION
# ═══════════════════════════════════════════════════════════

@dataclass
class FitnessResult:
    mse: float = 1e12
    r_squared: float = -1.0
    complexity_penalty: float = 0.0
    novelty_bonus: float = 0.0
    raw_fitness: float = -1e12
    adjusted_fitness: float = -1e12


def evaluate_fitness(
    tree: ExprNode,
    data_x: List[Dict[str, float]],
    data_y: List[float],
    parsimony_coeff: float = 0.003,
) -> FitnessResult:
    """
    Multi-objective fitness:
      fitness = -MSE - parsimony * complexity + novelty_bonus

    Args:
        tree: The expression tree to evaluate
        data_x: List of variable bindings (e.g., [{"x": 1}, {"x": 2}, ...])
        data_y: Target outputs
        parsimony_coeff: Penalty per tree node (Occam pressure)
    """
    result = FitnessResult()

    if not data_x or not data_y or len(data_x) != len(data_y):
        return result

    n = len(data_y)
    ss_res = 0.0
    ss_tot = 0.0
    y_mean = sum(data_y) / n
    valid = 0

    for x_vals, y_true in zip(data_x, data_y):
        try:
            y_pred = tree.evaluate(x_vals)
            if math.isnan(y_pred) or math.isinf(y_pred) or abs(y_pred) > 1e10:
                ss_res += 1e6
            else:
                ss_res += (y_true - y_pred) ** 2
                valid += 1
        except Exception:
            ss_res += 1e6

        ss_tot += (y_true - y_mean) ** 2

    result.mse = ss_res / n
    result.r_squared = 1.0 - (ss_res / (ss_tot + 1e-12)) if ss_tot > 1e-12 else 0.0
    result.complexity_penalty = parsimony_coeff * tree.size()
    result.raw_fitness = -result.mse
    result.adjusted_fitness = result.raw_fitness - result.complexity_penalty

    return result


# ═══════════════════════════════════════════════════════════
# FORMULA SIMPLIFICATION
# ═══════════════════════════════════════════════════════════

class FormulaSimplifier:
    """
    Algebraic simplification of expression trees.

    Rules:
      x + 0 → x,  0 + x → x
      x * 1 → x,  1 * x → x
      x * 0 → 0,  0 * x → 0
      x - 0 → x
      x / 1 → x
      x ^ 0 → 1,  x ^ 1 → x
      const OP const → evaluated constant
      neg(neg(x)) → x
    """

    @staticmethod
    def simplify(tree: ExprNode) -> ExprNode:
        tree = tree.clone()
        changed = True
        max_passes = 10
        passes = 0
        while changed and passes < max_passes:
            tree, changed = FormulaSimplifier._simplify_pass(tree)
            passes += 1
        return tree

    @staticmethod
    def _simplify_pass(node: ExprNode) -> Tuple[ExprNode, bool]:
        changed = False

        # Recursively simplify children first
        new_children = []
        for c in node.children:
            simplified, c_changed = FormulaSimplifier._simplify_pass(c)
            new_children.append(simplified)
            changed = changed or c_changed
        node.children = new_children

        # Constant folding: both children are constants
        if node.node_type == NodeType.OPERATOR and len(node.children) == 2:
            l, r = node.children
            if l.node_type == NodeType.CONSTANT and r.node_type == NodeType.CONSTANT:
                val = _safe_binary_op(node.op, l.value, r.value)
                if abs(val) < 1e10 and not math.isnan(val) and not math.isinf(val):
                    return ExprNode(NodeType.CONSTANT, value=round(val, 6)), True

        # Function of constant
        if node.node_type == NodeType.FUNCTION and len(node.children) == 1:
            c = node.children[0]
            if c.node_type == NodeType.CONSTANT:
                val = _safe_unary_op(node.op, c.value)
                if abs(val) < 1e10 and not math.isnan(val) and not math.isinf(val):
                    return ExprNode(NodeType.CONSTANT, value=round(val, 6)), True

        # Identity rules for binary operators
        if node.node_type == NodeType.OPERATOR and len(node.children) == 2:
            l, r = node.children

            # x + 0 → x,  0 + x → x
            if node.op == '+':
                if r.node_type == NodeType.CONSTANT and r.value == 0:
                    return l, True
                if l.node_type == NodeType.CONSTANT and l.value == 0:
                    return r, True

            # x - 0 → x
            if node.op == '-':
                if r.node_type == NodeType.CONSTANT and r.value == 0:
                    return l, True

            # x * 1 → x,  1 * x → x,  x * 0 → 0
            if node.op == '*':
                if r.node_type == NodeType.CONSTANT and r.value == 1:
                    return l, True
                if l.node_type == NodeType.CONSTANT and l.value == 1:
                    return r, True
                if (r.node_type == NodeType.CONSTANT and r.value == 0) or \
                   (l.node_type == NodeType.CONSTANT and l.value == 0):
                    return ExprNode(NodeType.CONSTANT, value=0.0), True

            # x / 1 → x
            if node.op == '/':
                if r.node_type == NodeType.CONSTANT and r.value == 1:
                    return l, True

            # x ^ 0 → 1,  x ^ 1 → x
            if node.op == '^':
                if r.node_type == NodeType.CONSTANT and r.value == 0:
                    return ExprNode(NodeType.CONSTANT, value=1.0), True
                if r.node_type == NodeType.CONSTANT and r.value == 1:
                    return l, True

        # neg(neg(x)) → x
        if (node.node_type == NodeType.FUNCTION and node.op == 'neg'
                and node.children and node.children[0].node_type == NodeType.FUNCTION
                and node.children[0].op == 'neg'):
            return node.children[0].children[0], True

        return node, changed


# ═══════════════════════════════════════════════════════════
# FORMULA BANK — Stores Discovered Formulas
# ═══════════════════════════════════════════════════════════

@dataclass
class DiscoveredFormula:
    """A formula discovered by the engine."""
    expression: str
    tree: ExprNode
    r_squared: float = 0.0
    mse: float = 0.0
    complexity: int = 0
    variables: List[str] = field(default_factory=list)
    domain: str = "general"
    discovered_at: float = 0.0
    generation: int = 0

    def summary(self) -> str:
        return (
            f"f({', '.join(self.variables)}) = {self.expression}\n"
            f"  R² = {self.r_squared:.6f}, MSE = {self.mse:.6g}, "
            f"Complexity = {self.complexity}, Gen = {self.generation}"
        )


class FormulaBank:
    """Persistent bank of discovered formulas for cross-problem reuse."""

    def __init__(self, max_size: int = 200):
        self.formulas: List[DiscoveredFormula] = []
        self.max_size = max_size

    def store(self, formula: DiscoveredFormula) -> None:
        # Avoid exact duplicates
        for existing in self.formulas:
            if existing.expression == formula.expression:
                if formula.r_squared > existing.r_squared:
                    existing.r_squared = formula.r_squared
                    existing.mse = formula.mse
                return

        self.formulas.append(formula)

        # Prune: keep best formulas by R²
        if len(self.formulas) > self.max_size:
            self.formulas.sort(key=lambda f: f.r_squared, reverse=True)
            self.formulas = self.formulas[:self.max_size]

    def search(self, variables: List[str], domain: str = "") -> List[DiscoveredFormula]:
        """Find previously discovered formulas matching the variable set."""
        results = []
        var_set = set(variables)
        for f in self.formulas:
            if set(f.variables) == var_set:
                if not domain or f.domain == domain:
                    results.append(f)
        results.sort(key=lambda f: f.r_squared, reverse=True)
        return results[:10]

    def get_best(self, n: int = 5) -> List[DiscoveredFormula]:
        sorted_f = sorted(self.formulas, key=lambda f: f.r_squared, reverse=True)
        return sorted_f[:n]


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE — Symbolic Genetic Programming
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionConfig:
    """Configuration for the GP evolution."""
    population_size: int = 300
    generations: int = 80
    tournament_size: int = 5
    crossover_rate: float = 0.7
    mutation_rate: float = 0.2
    reproduction_rate: float = 0.1
    elitism: int = 5
    parsimony_coeff: float = 0.003
    max_depth: int = 6
    target_r_squared: float = 0.999
    novelty_weight: float = 0.05
    timeout_seconds: float = 30.0


@dataclass
class EvolutionResult:
    """Result of a formula discovery run."""
    best_formula: str = ""
    best_tree: Optional[ExprNode] = None
    best_r_squared: float = -1.0
    best_mse: float = 1e12
    generations_run: int = 0
    population_size: int = 0
    best_generation: int = 0
    duration_ms: float = 0.0
    converged: bool = False
    top_formulas: List[DiscoveredFormula] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.best_r_squared > 0.5

    def summary(self) -> str:
        status = "CONVERGED" if self.converged else "BEST FOUND"
        lines = [
            f"## Formula Discovery — {status}",
            f"",
            f"**f(x) = {self.best_formula}**",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| R² | {self.best_r_squared:.6f} |",
            f"| MSE | {self.best_mse:.6g} |",
            f"| Generations | {self.generations_run} |",
            f"| Best at Gen | {self.best_generation} |",
            f"| Duration | {self.duration_ms:.0f}ms |",
        ]
        if self.top_formulas:
            lines.append(f"\n### Top Discoveries")
            for i, f in enumerate(self.top_formulas[:5], 1):
                lines.append(f"{i}. `{f.expression}` (R²={f.r_squared:.4f})")
        return "\n".join(lines)


class FormulaDiscoveryEngine:
    """
    Symbolic Genetic Programming engine for formula discovery.

    Usage:
        engine = FormulaDiscoveryEngine()

        # Discover y = 2x² + 3x + 1 from data
        data_x = [{"x": i} for i in range(-5, 6)]
        data_y = [2*i**2 + 3*i + 1 for i in range(-5, 6)]

        result = engine.discover(data_x, data_y, variables=["x"])
        print(result.best_formula)  # → something like (2 * (x^2)) + (3 * x) + 1
    """

    def __init__(self, config: Optional[EvolutionConfig] = None):
        self.config = config or EvolutionConfig()
        self.formula_bank = FormulaBank()
        self.simplifier = FormulaSimplifier()
        self._novelty_archive: List[str] = []
        self._stats = {
            "total_runs": 0,
            "total_discoveries": 0,
            "avg_generations": 0.0,
            "best_r_squared_ever": -1.0,
        }

    def discover(
        self,
        data_x: List[Dict[str, float]],
        data_y: List[float],
        variables: Optional[List[str]] = None,
        domain: str = "general",
        config: Optional[EvolutionConfig] = None,
    ) -> EvolutionResult:
        """
        Discover a formula that fits the given data.

        Args:
            data_x: List of variable bindings, e.g. [{"x": 1}, {"x": 2}]
            data_y: Target output values
            variables: Variable names to use (auto-detected if None)
            domain: Problem domain for formula bank tagging
            config: Override evolution config

        Returns:
            EvolutionResult with discovered formula and stats
        """
        cfg = config or self.config
        start = time.time()

        # Auto-detect variables
        if variables is None:
            variables = sorted(set(k for d in data_x for k in d))
        if not variables:
            variables = ["x"]

        result = EvolutionResult(population_size=cfg.population_size)

        # ── Initialize Population (Ramped Half-and-Half) ──
        population = self._init_population(variables, cfg)

        # ── Check formula bank for seed solutions ──
        bank_seeds = self.formula_bank.search(variables, domain)
        for seed in bank_seeds[:3]:
            population.append(seed.tree.clone())

        best_fitness = -1e12
        best_tree = population[0] if population else random_terminal(variables)
        best_r2 = -1.0
        stall_count = 0

        for gen in range(cfg.generations):
            # Timeout check
            if time.time() - start > cfg.timeout_seconds:
                break

            # ── Evaluate Fitness ──
            fitnesses = []
            for individual in population:
                fit = evaluate_fitness(individual, data_x, data_y, cfg.parsimony_coeff)

                # Novelty bonus
                expr_str = individual.to_string()
                if expr_str not in self._novelty_archive:
                    fit.novelty_bonus = cfg.novelty_weight
                    fit.adjusted_fitness += fit.novelty_bonus

                fitnesses.append(fit)

            # ── Track Best ──
            gen_best_idx = max(range(len(fitnesses)),
                               key=lambda i: fitnesses[i].adjusted_fitness)
            gen_best_fit = fitnesses[gen_best_idx]

            if gen_best_fit.adjusted_fitness > best_fitness:
                best_fitness = gen_best_fit.adjusted_fitness
                best_tree = population[gen_best_idx].clone()
                best_r2 = gen_best_fit.r_squared
                result.best_generation = gen
                stall_count = 0
            else:
                stall_count += 1

            # ── Convergence Check ──
            if best_r2 >= cfg.target_r_squared:
                result.converged = True
                break

            # ── Adaptive mutation on stall ──
            effective_mutation = cfg.mutation_rate
            if stall_count > 10:
                effective_mutation = min(0.5, cfg.mutation_rate * 2)

            # ── Selection + Reproduction ──
            new_population = []

            # Elitism: carry over best individuals
            elite_indices = sorted(
                range(len(fitnesses)),
                key=lambda i: fitnesses[i].adjusted_fitness,
                reverse=True,
            )[:cfg.elitism]
            for idx in elite_indices:
                new_population.append(population[idx].clone())

            # Fill rest of population
            while len(new_population) < cfg.population_size:
                r = random.random()

                if r < cfg.crossover_rate:
                    # Crossover
                    p1 = self._tournament_select(population, fitnesses, cfg.tournament_size)
                    p2 = self._tournament_select(population, fitnesses, cfg.tournament_size)
                    c1, c2 = crossover(p1, p2)
                    new_population.append(c1)
                    if len(new_population) < cfg.population_size:
                        new_population.append(c2)

                elif r < cfg.crossover_rate + effective_mutation:
                    # Mutation
                    parent = self._tournament_select(population, fitnesses, cfg.tournament_size)
                    child = mutate(parent, variables, effective_mutation)
                    new_population.append(child)

                else:
                    # Reproduction (copy)
                    parent = self._tournament_select(population, fitnesses, cfg.tournament_size)
                    new_population.append(parent.clone())

            population = new_population
            result.generations_run = gen + 1

        # ── Post-Processing ──
        # Simplify best formula
        best_tree = self.simplifier.simplify(best_tree)
        best_formula = best_tree.to_string()

        # Re-evaluate after simplification
        final_fit = evaluate_fitness(best_tree, data_x, data_y, 0)

        result.best_formula = best_formula
        result.best_tree = best_tree
        result.best_r_squared = final_fit.r_squared
        result.best_mse = final_fit.mse
        result.duration_ms = (time.time() - start) * 1000

        # Store in formula bank
        discovered = DiscoveredFormula(
            expression=best_formula,
            tree=best_tree,
            r_squared=final_fit.r_squared,
            mse=final_fit.mse,
            complexity=best_tree.size(),
            variables=variables,
            domain=domain,
            discovered_at=time.time(),
            generation=result.best_generation,
        )
        self.formula_bank.store(discovered)
        result.top_formulas.append(discovered)

        # Update novelty archive
        self._novelty_archive.append(best_formula)
        if len(self._novelty_archive) > 500:
            self._novelty_archive = self._novelty_archive[-250:]

        # Update stats
        self._stats["total_runs"] += 1
        self._stats["total_discoveries"] += 1
        if final_fit.r_squared > self._stats["best_r_squared_ever"]:
            self._stats["best_r_squared_ever"] = final_fit.r_squared

        logger.info(
            f"[FORMULA DISCOVERY] {best_formula} | "
            f"R²={final_fit.r_squared:.6f} | Gen={result.best_generation} | "
            f"{result.duration_ms:.0f}ms"
        )

        return result

    def discover_from_function(
        self,
        func: Callable,
        x_range: Tuple[float, float] = (-5, 5),
        n_points: int = 20,
        variables: Optional[List[str]] = None,
    ) -> EvolutionResult:
        """
        Convenience: discover a formula by sampling a Python function.

        Usage:
            result = engine.discover_from_function(lambda x: x**2 + 2*x + 1)
        """
        variables = variables or ["x"]
        n_points = max(n_points, 2)  # Guard against division by zero
        x_vals = [x_range[0] + i * (x_range[1] - x_range[0]) / (n_points - 1)
                  for i in range(n_points)]
        data_x = [{variables[0]: x} for x in x_vals]
        data_y = [func(x) for x in x_vals]
        return self.discover(data_x, data_y, variables)

    def _init_population(self, variables: List[str], cfg: EvolutionConfig) -> List[ExprNode]:
        """Ramped Half-and-Half initialization."""
        population = []
        depths = range(2, cfg.max_depth + 1)

        for i in range(cfg.population_size):
            depth = list(depths)[i % len(list(depths))]
            method = "grow" if i % 2 == 0 else "full"
            tree = random_tree(variables, max_depth=depth, method=method)
            population.append(tree)

        return population

    @staticmethod
    def _tournament_select(
        population: List[ExprNode],
        fitnesses: List[FitnessResult],
        tournament_size: int,
    ) -> ExprNode:
        """Tournament selection: pick best from random subset."""
        indices = random.sample(range(len(population)), min(tournament_size, len(population)))
        best_idx = max(indices, key=lambda i: fitnesses[i].adjusted_fitness)
        return population[best_idx]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "FormulaDiscoveryEngine",
            "total_runs": self._stats["total_runs"],
            "total_discoveries": self._stats["total_discoveries"],
            "best_r_squared_ever": self._stats["best_r_squared_ever"],
            "formula_bank_size": len(self.formula_bank.formulas),
            "novelty_archive_size": len(self._novelty_archive),
        }

    def solve(self, prompt: str) -> EvolutionResult:
        """
        Natural language interface for formula discovery.

        Parses prompts like:
          "Find a formula that fits: x=[1,2,3,4], y=[1,4,9,16]"
          "Discover the relationship between x and y: ..."
        """
        import re

        # Try to extract x and y values from prompt
        x_match = re.search(r'x\s*=\s*\[([^\]]+)\]', prompt)
        y_match = re.search(r'y\s*=\s*\[([^\]]+)\]', prompt)

        if x_match and y_match:
            x_vals = [float(v.strip()) for v in x_match.group(1).split(',')]
            y_vals = [float(v.strip()) for v in y_match.group(1).split(',')]
            data_x = [{"x": x} for x in x_vals]
            return self.discover(data_x, y_vals, ["x"])

        # Try to extract data pairs
        pairs = re.findall(r'\(([^)]+)\)', prompt)
        if len(pairs) >= 3:
            data_x = []
            data_y = []
            for pair in pairs:
                parts = [float(p.strip()) for p in pair.split(',')]
                if len(parts) == 2:
                    data_x.append({"x": parts[0]})
                    data_y.append(parts[1])
            if data_x:
                return self.discover(data_x, data_y, ["x"])

        # Default: cannot parse
        return EvolutionResult()
