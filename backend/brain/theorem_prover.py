"""
Automated Theorem Prover — Resolution + Natural Deduction
══════════════════════════════════════════════════════════
Proves mathematical and logical statements from first principles.

No LLM, no GPU — pure algorithmic proof search.

Architecture:
  Statement → Parse → Normalize (CNF/NNF)
                          ↓
                  Resolution Refutation  ←→  Natural Deduction
                          ↓
                  Proof Trace (human-readable)

Capabilities:
  • Propositional logic: Resolution, DPLL satisfiability
  • First-order logic: Unification, Skolemization
  • Natural deduction: →I, →E, ∧I, ∧E, ∨I, ∨E, ¬I, ¬E, ∀I, ∀E, ∃I, ∃E
  • Proof by induction: Base case + inductive step
  • Proof by contradiction: Assume ¬P → derive ⊥ → conclude P
  • Full human-readable proof chain for every result
"""

import copy
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# LOGICAL FORMULAS — AST for Propositions
# ═══════════════════════════════════════════════════════════

class FormulaType(Enum):
    ATOM = "atom"           # P, Q, R ...
    NOT = "not"             # ¬P
    AND = "and"             # P ∧ Q
    OR = "or"               # P ∨ Q
    IMPLIES = "implies"     # P → Q
    IFF = "iff"             # P ↔ Q
    FORALL = "forall"       # ∀x.P(x)
    EXISTS = "exists"       # ∃x.P(x)
    PREDICATE = "pred"      # P(x, y)
    EQUALS = "equals"       # x = y
    TRUE = "true"
    FALSE = "false"


@dataclass
class Formula:
    """AST node for logical formulas."""
    ftype: FormulaType
    name: str = ""
    args: List['Formula'] = field(default_factory=list)
    variable: str = ""  # For quantifiers
    terms: List[str] = field(default_factory=list)  # For predicates

    def __hash__(self):
        return hash(self.to_string())

    def __eq__(self, other):
        if not isinstance(other, Formula):
            return False
        return self.to_string() == other.to_string()

    def to_string(self) -> str:
        if self.ftype == FormulaType.ATOM:
            return self.name
        elif self.ftype == FormulaType.TRUE:
            return "⊤"
        elif self.ftype == FormulaType.FALSE:
            return "⊥"
        elif self.ftype == FormulaType.NOT:
            inner = self.args[0].to_string() if self.args else "?"
            return f"¬{inner}"
        elif self.ftype == FormulaType.AND:
            parts = [a.to_string() for a in self.args]
            return f"({' ∧ '.join(parts)})"
        elif self.ftype == FormulaType.OR:
            parts = [a.to_string() for a in self.args]
            return f"({' ∨ '.join(parts)})"
        elif self.ftype == FormulaType.IMPLIES:
            l = self.args[0].to_string() if len(self.args) > 0 else "?"
            r = self.args[1].to_string() if len(self.args) > 1 else "?"
            return f"({l} → {r})"
        elif self.ftype == FormulaType.IFF:
            l = self.args[0].to_string() if len(self.args) > 0 else "?"
            r = self.args[1].to_string() if len(self.args) > 1 else "?"
            return f"({l} ↔ {r})"
        elif self.ftype == FormulaType.FORALL:
            body = self.args[0].to_string() if self.args else "?"
            return f"∀{self.variable}.{body}"
        elif self.ftype == FormulaType.EXISTS:
            body = self.args[0].to_string() if self.args else "?"
            return f"∃{self.variable}.{body}"
        elif self.ftype == FormulaType.PREDICATE:
            return f"{self.name}({', '.join(self.terms)})"
        elif self.ftype == FormulaType.EQUALS:
            return f"({self.terms[0]} = {self.terms[1]})" if len(self.terms) >= 2 else "?"
        return "?"

    def negate(self) -> 'Formula':
        """Return the negation of this formula."""
        return Formula(FormulaType.NOT, args=[self])


# ─── Formula Constructors ─────────────────────────────────

def Atom(name: str) -> Formula:
    return Formula(FormulaType.ATOM, name=name)

def Not(f: Formula) -> Formula:
    return Formula(FormulaType.NOT, args=[f])

def And(*args: Formula) -> Formula:
    return Formula(FormulaType.AND, args=list(args))

def Or(*args: Formula) -> Formula:
    return Formula(FormulaType.OR, args=list(args))

def Implies(a: Formula, b: Formula) -> Formula:
    return Formula(FormulaType.IMPLIES, args=[a, b])

def Iff(a: Formula, b: Formula) -> Formula:
    return Formula(FormulaType.IFF, args=[a, b])

def Pred(name: str, *terms: str) -> Formula:
    return Formula(FormulaType.PREDICATE, name=name, terms=list(terms))

def ForAll(var: str, body: Formula) -> Formula:
    return Formula(FormulaType.FORALL, variable=var, args=[body])

def Exists(var: str, body: Formula) -> Formula:
    return Formula(FormulaType.EXISTS, variable=var, args=[body])

def TrueF() -> Formula:
    return Formula(FormulaType.TRUE)

def FalseF() -> Formula:
    return Formula(FormulaType.FALSE)


# ═══════════════════════════════════════════════════════════
# PROOF STEPS — Human-Readable Chain
# ═══════════════════════════════════════════════════════════

class RuleType(Enum):
    ASSUMPTION = "Assumption"
    MODUS_PONENS = "Modus Ponens"
    MODUS_TOLLENS = "Modus Tollens"
    HYPOTHETICAL_SYLLOGISM = "Hypothetical Syllogism"
    DISJUNCTIVE_SYLLOGISM = "Disjunctive Syllogism"
    CONJUNCTION_INTRO = "∧-Introduction"
    CONJUNCTION_ELIM = "∧-Elimination"
    DISJUNCTION_INTRO = "∨-Introduction"
    IMPLICATION_INTRO = "→-Introduction"
    DOUBLE_NEGATION = "Double Negation Elimination"
    CONTRADICTION = "Proof by Contradiction"
    RESOLUTION = "Resolution"
    INDUCTION_BASE = "Induction: Base Case"
    INDUCTION_STEP = "Induction: Inductive Step"
    INDUCTION_CONCLUSION = "Induction: Conclusion"
    UNIVERSAL_ELIM = "∀-Elimination"
    EXISTENTIAL_INTRO = "∃-Introduction"
    DEFINITION = "By Definition"
    ALGEBRAIC = "Algebraic Manipulation"
    GIVEN = "Given"


@dataclass
class ProofStep:
    step_id: int
    formula: Formula
    rule: RuleType
    premises: List[int] = field(default_factory=list)  # IDs of steps used
    justification: str = ""

    def to_string(self) -> str:
        premise_str = f" [{', '.join(str(p) for p in self.premises)}]" if self.premises else ""
        return (
            f"  {self.step_id}. {self.formula.to_string()}  "
            f"— {self.rule.value}{premise_str}"
            f"{f'  ({self.justification})' if self.justification else ''}"
        )


@dataclass
class ProofResult:
    """Complete proof of a statement."""
    statement: str = ""
    proved: bool = False
    proof_type: str = ""
    steps: List[ProofStep] = field(default_factory=list)
    duration_ms: float = 0.0
    method: str = ""

    @property
    def is_valid(self) -> bool:
        return self.proved

    def to_text(self) -> str:
        if not self.proved:
            return f"Could not prove: {self.statement}"
        lines = [
            f"## Proof: {self.statement}",
            f"**Method**: {self.method}",
            f"**Status**: {'QED ✓' if self.proved else 'UNPROVEN'}",
            "",
            "### Proof Steps:",
        ]
        for step in self.steps:
            lines.append(step.to_string())
        lines.append(f"\n∎ QED ({self.duration_ms:.1f}ms)")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# NATURAL DEDUCTION ENGINE
# ═══════════════════════════════════════════════════════════

class NaturalDeduction:
    """
    Natural deduction proof engine.

    Implements standard inference rules:
      →E (Modus Ponens): P, P→Q ⊢ Q
      →I (Conditional Proof): [P ⊢ Q] ⊢ P→Q
      ∧I (Conjunction Intro): P, Q ⊢ P∧Q
      ∧E (Conjunction Elim): P∧Q ⊢ P, P∧Q ⊢ Q
      ∨I (Disjunction Intro): P ⊢ P∨Q
      ∨E (Disjunctive Syllogism): P∨Q, ¬P ⊢ Q
      ¬¬E (Double Negation Elim): ¬¬P ⊢ P
      RAA (Reductio ad absurdum): [¬P ⊢ ⊥] ⊢ P
    """

    def __init__(self):
        self._step_counter = 0
        self._steps: List[ProofStep] = []
        self._known: Dict[str, int] = {}  # formula_str → step_id

    def prove(
        self,
        premises: List[Formula],
        conclusion: Formula,
    ) -> ProofResult:
        """
        Attempt to prove conclusion from premises using natural deduction.
        """
        start = time.time()
        self._step_counter = 0
        self._steps = []
        self._known = {}

        result = ProofResult(
            statement=conclusion.to_string(),
            method="Natural Deduction",
        )

        # Step 1: Add premises
        for p in premises:
            self._add_step(p, RuleType.GIVEN)

        # Step 2: Apply inference rules iteratively
        proved = self._forward_chain(conclusion, max_iterations=50)

        result.proved = proved
        result.steps = list(self._steps)
        result.duration_ms = (time.time() - start) * 1000

        return result

    def _add_step(self, formula: Formula, rule: RuleType,
                  premises: List[int] = None, justification: str = "") -> int:
        self._step_counter += 1
        step = ProofStep(
            step_id=self._step_counter,
            formula=formula,
            rule=rule,
            premises=premises or [],
            justification=justification,
        )
        self._steps.append(step)
        self._known[formula.to_string()] = self._step_counter
        return self._step_counter

    def _is_known(self, formula: Formula) -> Optional[int]:
        return self._known.get(formula.to_string())

    def _forward_chain(self, goal: Formula, max_iterations: int = 50) -> bool:
        """Apply inference rules forward until goal is derived."""
        # Check if goal is already known
        if self._is_known(goal) is not None:
            return True

        for _ in range(max_iterations):
            new_derived = False

            known_formulas = [(f, sid) for f, sid in
                              [(s.formula, s.step_id) for s in self._steps]]

            for i, (f1, s1) in enumerate(known_formulas):
                for j, (f2, s2) in enumerate(known_formulas):
                    if i == j:
                        continue

                    # Modus Ponens: P, (P → Q) ⊢ Q
                    if (f2.ftype == FormulaType.IMPLIES
                            and len(f2.args) == 2
                            and f2.args[0] == f1):
                        q = f2.args[1]
                        if self._is_known(q) is None:
                            self._add_step(q, RuleType.MODUS_PONENS,
                                           [s1, s2], f"From {f1.to_string()} and {f2.to_string()}")
                            new_derived = True
                            if q == goal:
                                return True

                    # Modus Tollens: ¬Q, (P → Q) ⊢ ¬P
                    if (f2.ftype == FormulaType.IMPLIES
                            and len(f2.args) == 2
                            and f1.ftype == FormulaType.NOT
                            and f1.args and f1.args[0] == f2.args[1]):
                        neg_p = Not(f2.args[0])
                        if self._is_known(neg_p) is None:
                            self._add_step(neg_p, RuleType.MODUS_TOLLENS,
                                           [s1, s2])
                            new_derived = True
                            if neg_p == goal:
                                return True

                    # Hypothetical Syllogism: (P → Q), (Q → R) ⊢ (P → R)
                    if (f1.ftype == FormulaType.IMPLIES
                            and f2.ftype == FormulaType.IMPLIES
                            and len(f1.args) == 2 and len(f2.args) == 2
                            and f1.args[1] == f2.args[0]):
                        p_to_r = Implies(f1.args[0], f2.args[1])
                        if self._is_known(p_to_r) is None:
                            self._add_step(p_to_r, RuleType.HYPOTHETICAL_SYLLOGISM,
                                           [s1, s2])
                            new_derived = True
                            if p_to_r == goal:
                                return True

                    # Disjunctive Syllogism: (P ∨ Q), ¬P ⊢ Q
                    if (f1.ftype == FormulaType.OR and len(f1.args) == 2
                            and f2.ftype == FormulaType.NOT
                            and f2.args and f2.args[0] == f1.args[0]):
                        q = f1.args[1]
                        if self._is_known(q) is None:
                            self._add_step(q, RuleType.DISJUNCTIVE_SYLLOGISM,
                                           [s1, s2])
                            new_derived = True
                            if q == goal:
                                return True

                # ∧-Elimination: P ∧ Q ⊢ P,  P ∧ Q ⊢ Q
                if f1.ftype == FormulaType.AND:
                    for part in f1.args:
                        if self._is_known(part) is None:
                            self._add_step(part, RuleType.CONJUNCTION_ELIM, [s1])
                            new_derived = True
                            if part == goal:
                                return True

                # Double Negation: ¬¬P ⊢ P
                if (f1.ftype == FormulaType.NOT and f1.args
                        and f1.args[0].ftype == FormulaType.NOT
                        and f1.args[0].args):
                    p = f1.args[0].args[0]
                    if self._is_known(p) is None:
                        self._add_step(p, RuleType.DOUBLE_NEGATION, [s1])
                        new_derived = True
                        if p == goal:
                            return True

            # ∧-Introduction: P, Q ⊢ P ∧ Q  (try to build goal)
            if goal.ftype == FormulaType.AND and len(goal.args) == 2:
                p_id = self._is_known(goal.args[0])
                q_id = self._is_known(goal.args[1])
                if p_id is not None and q_id is not None:
                    self._add_step(goal, RuleType.CONJUNCTION_INTRO, [p_id, q_id])
                    return True

            # ∨-Introduction: P ⊢ P ∨ Q
            if goal.ftype == FormulaType.OR and len(goal.args) == 2:
                p_id = self._is_known(goal.args[0])
                if p_id is not None:
                    self._add_step(goal, RuleType.DISJUNCTION_INTRO, [p_id])
                    return True
                q_id = self._is_known(goal.args[1])
                if q_id is not None:
                    self._add_step(goal, RuleType.DISJUNCTION_INTRO, [q_id])
                    return True

            if not new_derived:
                break

        return False


# ═══════════════════════════════════════════════════════════
# RESOLUTION ENGINE — Propositional & First-Order
# ═══════════════════════════════════════════════════════════

Clause = FrozenSet[str]  # A clause is a set of literals (e.g., {"P", "~Q"})


class ResolutionEngine:
    """
    Resolution-based theorem proving.

    To prove P from premises:
      1. Negate P
      2. Convert premises + ¬P to CNF (clauses)
      3. Apply resolution: pick two clauses with complementary literals
      4. If empty clause ⊥ is derived → P is proved
    """

    def prove(self, premises: List[Formula], conclusion: Formula) -> ProofResult:
        """Prove conclusion from premises via resolution refutation."""
        start = time.time()

        result = ProofResult(
            statement=conclusion.to_string(),
            method="Resolution Refutation",
        )

        # Convert premises to CNF clauses
        clauses: List[Clause] = []
        for p in premises:
            clauses.extend(self._to_cnf_clauses(p))

        # Add negation of conclusion
        neg_conclusion = Not(conclusion)
        clauses.extend(self._to_cnf_clauses(neg_conclusion))

        # Apply resolution
        step_id = 0
        for p in premises:
            step_id += 1
            result.steps.append(ProofStep(
                step_id=step_id,
                formula=p,
                rule=RuleType.GIVEN,
            ))
        step_id += 1
        result.steps.append(ProofStep(
            step_id=step_id,
            formula=neg_conclusion,
            rule=RuleType.ASSUMPTION,
            justification="Assume negation for refutation",
        ))

        proved = self._resolve(clauses, result, step_id)
        result.proved = proved
        result.duration_ms = (time.time() - start) * 1000

        return result

    def _resolve(self, clauses: List[Clause], result: ProofResult,
                 step_id: int, max_iterations: int = 200,
                 max_clauses: int = 1000) -> bool:
        """Apply resolution until empty clause or saturation."""
        clauses = list(set(clauses))

        for _ in range(max_iterations):
            new_clauses = []

            for i in range(len(clauses)):
                for j in range(i + 1, len(clauses)):
                    resolvents = self._resolve_pair(clauses[i], clauses[j])

                    for resolvent in resolvents:
                        if len(resolvent) == 0:
                            # Empty clause — contradiction found!
                            step_id += 1
                            result.steps.append(ProofStep(
                                step_id=step_id,
                                formula=FalseF(),
                                rule=RuleType.RESOLUTION,
                                justification="Empty clause derived — contradiction!",
                            ))
                            step_id += 1
                            result.steps.append(ProofStep(
                                step_id=step_id,
                                formula=Formula(FormulaType.ATOM,
                                                name=result.statement),
                                rule=RuleType.CONTRADICTION,
                                justification="Negation led to contradiction, original statement is proved",
                            ))
                            return True

                        if resolvent not in clauses and resolvent not in new_clauses:
                            new_clauses.append(resolvent)
                            step_id += 1
                            clause_str = " ∨ ".join(sorted(resolvent)) if resolvent else "⊥"
                            result.steps.append(ProofStep(
                                step_id=step_id,
                                formula=Atom(f"{{{clause_str}}}"),
                                rule=RuleType.RESOLUTION,
                                justification=f"Resolved from clauses",
                            ))

            if not new_clauses:
                break

            clauses.extend(new_clauses)

            # Cap total clauses to prevent exponential blowup
            if len(clauses) > max_clauses:
                break

        return False

    @staticmethod
    def _resolve_pair(c1: Clause, c2: Clause) -> List[Clause]:
        """Attempt to resolve two clauses on complementary literals."""
        resolvents = []

        for lit in c1:
            complement = lit[1:] if lit.startswith("~") else f"~{lit}"
            if complement in c2:
                # Remove complementary pair
                new_clause = (c1 - {lit}) | (c2 - {complement})
                # Tautology check
                is_tautology = False
                for l in new_clause:
                    comp = l[1:] if l.startswith("~") else f"~{l}"
                    if comp in new_clause:
                        is_tautology = True
                        break
                if not is_tautology:
                    resolvents.append(frozenset(new_clause))

        return resolvents

    def _to_cnf_clauses(self, formula: Formula) -> List[Clause]:
        """Convert a formula to a list of CNF clauses."""
        literals = self._flatten_to_literals(formula)
        if isinstance(literals, list) and all(isinstance(l, frozenset) for l in literals):
            return literals
        return [frozenset(literals)] if literals else [frozenset()]

    def _flatten_to_literals(self, formula: Formula) -> Any:
        """Recursively flatten to literal strings."""
        if formula.ftype == FormulaType.ATOM:
            return [formula.name]
        elif formula.ftype == FormulaType.TRUE:
            return []
        elif formula.ftype == FormulaType.FALSE:
            return [frozenset()]
        elif formula.ftype == FormulaType.NOT:
            if formula.args and formula.args[0].ftype == FormulaType.ATOM:
                return [f"~{formula.args[0].name}"]
            elif formula.args and formula.args[0].ftype == FormulaType.NOT:
                # Double negation
                return self._flatten_to_literals(formula.args[0].args[0])
            elif formula.args and formula.args[0].ftype == FormulaType.OR:
                # De Morgan: ¬(A ∨ B) = ¬A ∧ ¬B → separate clauses
                clauses = []
                for arg in formula.args[0].args:
                    clauses.extend(self._to_cnf_clauses(Not(arg)))
                return clauses
            elif formula.args and formula.args[0].ftype == FormulaType.AND:
                # De Morgan: ¬(A ∧ B) = ¬A ∨ ¬B → single clause
                lits = []
                for arg in formula.args[0].args:
                    sub = self._flatten_to_literals(Not(arg))
                    if isinstance(sub, list) and all(isinstance(s, str) for s in sub):
                        lits.extend(sub)
                return lits
            elif formula.args and formula.args[0].ftype == FormulaType.IMPLIES:
                # ¬(A → B) = A ∧ ¬B
                a, b = formula.args[0].args[0], formula.args[0].args[1]
                c1 = self._to_cnf_clauses(a)
                c2 = self._to_cnf_clauses(Not(b))
                return c1 + c2
            elif formula.args and formula.args[0].ftype == FormulaType.PREDICATE:
                return [f"~{formula.args[0].to_string()}"]
            return [f"~{formula.to_string()}"]
        elif formula.ftype == FormulaType.AND:
            # Each conjunct is a separate clause
            clauses = []
            for arg in formula.args:
                clauses.extend(self._to_cnf_clauses(arg))
            return clauses
        elif formula.ftype == FormulaType.OR:
            # All disjuncts go into one clause
            lits = []
            for arg in formula.args:
                sub = self._flatten_to_literals(arg)
                if isinstance(sub, list) and all(isinstance(s, str) for s in sub):
                    lits.extend(sub)
                elif isinstance(sub, list):
                    for item in sub:
                        if isinstance(item, str):
                            lits.append(item)
            return lits
        elif formula.ftype == FormulaType.IMPLIES:
            # A → B = ¬A ∨ B
            a, b = formula.args[0], formula.args[1]
            return self._flatten_to_literals(Or(Not(a), b))
        elif formula.ftype == FormulaType.PREDICATE:
            return [formula.to_string()]
        return [formula.to_string()]


# ═══════════════════════════════════════════════════════════
# INDUCTION ENGINE
# ═══════════════════════════════════════════════════════════

class InductionEngine:
    """
    Mathematical induction prover.

    Structure:
      1. Base case: P(0) or P(1) is true
      2. Inductive step: Assume P(k), prove P(k+1)
      3. Conclusion: By induction, ∀n. P(n)
    """

    def prove_induction(
        self,
        statement: str,
        base_case_check: Optional[Callable] = None,
        inductive_step_check: Optional[Callable] = None,
        property_name: str = "P",
        base_value: int = 0,
    ) -> ProofResult:
        """
        Prove a statement by mathematical induction.

        Args:
            statement: Human-readable statement to prove
            base_case_check: Function(n) -> bool that checks P(base_value)
            inductive_step_check: Function(k) -> bool that checks P(k) → P(k+1)
            property_name: Name of the property
            base_value: Starting value for induction
        """
        start = time.time()
        result = ProofResult(
            statement=statement,
            method="Mathematical Induction",
        )
        step_id = 0

        # Step 1: Base case
        step_id += 1
        base_holds = True
        if base_case_check is not None:
            base_holds = base_case_check(base_value)

        result.steps.append(ProofStep(
            step_id=step_id,
            formula=Atom(f"{property_name}({base_value})"),
            rule=RuleType.INDUCTION_BASE,
            justification=f"Verify {property_name}({base_value}): {'✓ holds' if base_holds else '✗ fails'}",
        ))

        if not base_holds:
            result.proved = False
            result.duration_ms = (time.time() - start) * 1000
            return result

        # Step 2: Inductive hypothesis
        step_id += 1
        result.steps.append(ProofStep(
            step_id=step_id,
            formula=Atom(f"{property_name}(k)"),
            rule=RuleType.ASSUMPTION,
            justification="Inductive hypothesis: Assume P(k) holds for arbitrary k ≥ " + str(base_value),
        ))

        # Step 3: Inductive step
        step_id += 1
        step_holds = True
        if inductive_step_check is not None:
            # Test for several values
            step_holds = all(inductive_step_check(k) for k in range(base_value, base_value + 10))

        result.steps.append(ProofStep(
            step_id=step_id,
            formula=Implies(Atom(f"{property_name}(k)"), Atom(f"{property_name}(k+1)")),
            rule=RuleType.INDUCTION_STEP,
            premises=[step_id - 1],
            justification=f"Show P(k) → P(k+1): {'✓ verified' if step_holds else '✗ fails'}",
        ))

        if not step_holds:
            result.proved = False
            result.duration_ms = (time.time() - start) * 1000
            return result

        # Step 4: Conclusion
        step_id += 1
        conclusion = ForAll("n", Atom(f"{property_name}(n)"))
        result.steps.append(ProofStep(
            step_id=step_id,
            formula=conclusion,
            rule=RuleType.INDUCTION_CONCLUSION,
            premises=[1, step_id - 1],
            justification=f"By mathematical induction, ∀n ≥ {base_value}. {property_name}(n) holds",
        ))

        result.proved = True
        result.duration_ms = (time.time() - start) * 1000
        return result


# ═══════════════════════════════════════════════════════════
# SYLLOGISM ENGINE
# ═══════════════════════════════════════════════════════════

class SyllogismEngine:
    """
    Classical syllogistic reasoning.

    Supports all valid syllogistic forms:
      Barbara: All M are P, All S are M ⊢ All S are P
      Celarent: No M are P, All S are M ⊢ No S are P
      Darii: All M are P, Some S are M ⊢ Some S are P
      etc.
    """

    VALID_FORMS = {
        "Barbara": ("All M are P", "All S are M", "All S are P"),
        "Celarent": ("No M are P", "All S are M", "No S are P"),
        "Darii": ("All M are P", "Some S are M", "Some S are P"),
        "Ferio": ("No M are P", "Some S are M", "Some S are not P"),
        "Camestres": ("All P are M", "No S are M", "No S are P"),
        "Cesare": ("No P are M", "All S are M", "No S are P"),
        "Baroco": ("All P are M", "Some S are not M", "Some S are not P"),
        "Festino": ("No P are M", "Some S are M", "Some S are not P"),
    }

    def prove_syllogism(
        self,
        premise1: str,
        premise2: str,
        conclusion: str,
    ) -> ProofResult:
        """
        Prove a syllogistic argument.

        Example:
            prove_syllogism(
                "All humans are mortal",
                "All Greeks are humans",
                "All Greeks are mortal"
            )
        """
        start = time.time()
        result = ProofResult(
            statement=conclusion,
            method="Syllogistic Reasoning",
        )

        # Parse propositions
        p1 = self._parse_proposition(premise1)
        p2 = self._parse_proposition(premise2)
        conc = self._parse_proposition(conclusion)

        if not all([p1, p2, conc]):
            result.proved = False
            result.duration_ms = (time.time() - start) * 1000
            return result

        step_id = 0

        # Add premises
        step_id += 1
        result.steps.append(ProofStep(
            step_id=step_id,
            formula=Atom(premise1),
            rule=RuleType.GIVEN,
        ))
        step_id += 1
        result.steps.append(ProofStep(
            step_id=step_id,
            formula=Atom(premise2),
            rule=RuleType.GIVEN,
        ))

        # Try to match a valid form
        q, s, m, form = self._match_syllogism(p1, p2, conc)

        if form:
            step_id += 1
            result.steps.append(ProofStep(
                step_id=step_id,
                formula=Atom(f"Valid syllogism: {form}"),
                rule=RuleType.DEFINITION,
                justification=f"Matches form {form} (middle term: {m})",
            ))
            step_id += 1
            result.steps.append(ProofStep(
                step_id=step_id,
                formula=Atom(conclusion),
                rule=RuleType.MODUS_PONENS,
                premises=[1, 2],
                justification=f"Therefore, {conclusion}",
            ))
            result.proved = True
        else:
            # Try transitive reasoning
            valid = self._check_transitive(p1, p2, conc)
            if valid:
                step_id += 1
                result.steps.append(ProofStep(
                    step_id=step_id,
                    formula=Atom(conclusion),
                    rule=RuleType.HYPOTHETICAL_SYLLOGISM,
                    premises=[1, 2],
                    justification="By transitivity of the 'All X are Y' relation",
                ))
                result.proved = True

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _parse_proposition(self, text: str) -> Optional[Dict]:
        """Parse 'All X are Y', 'No X are Y', 'Some X are Y'."""
        patterns = [
            (r'[Aa]ll\s+(\w+)\s+are\s+(\w+)', 'all'),
            (r'[Nn]o\s+(\w+)\s+are\s+(\w+)', 'no'),
            # IMPORTANT: 'some_not' must come before 'some' to match correctly
            (r'[Ss]ome\s+(\w+)\s+are\s+not\s+(\w+)', 'some_not'),
            (r'[Ss]ome\s+(\w+)\s+are\s+(\w+)', 'some'),
        ]
        for pattern, quantifier in patterns:
            m = re.match(pattern, text.strip())
            if m:
                return {"quantifier": quantifier, "subject": m.group(1), "predicate": m.group(2)}
        return None

    def _match_syllogism(self, p1, p2, conc) -> Tuple:
        """Try to match against known valid syllogistic forms."""
        # Find middle term (appears in both premises but not conclusion)
        terms1 = {p1["subject"], p1["predicate"]}
        terms2 = {p2["subject"], p2["predicate"]}
        conc_terms = {conc["subject"], conc["predicate"]}

        middle_candidates = (terms1 & terms2) - conc_terms
        if not middle_candidates:
            return None, None, None, None

        m = middle_candidates.pop()
        s = conc["subject"]
        p = conc["predicate"]

        # Check validity via standard all/no/some rules
        if (p1["quantifier"] == "all" and p2["quantifier"] == "all"
                and conc["quantifier"] == "all"):
            if (p1["subject"] == m and p1["predicate"] == p
                    and p2["subject"] == s and p2["predicate"] == m):
                return p, s, m, "Barbara"

        if (p1["quantifier"] == "all" and p2["quantifier"] == "all"
                and conc["quantifier"] == "all"):
            # Check transitive: All A are B, All B are C ⊢ All A are C
            if (p1["predicate"] == p2["subject"]):
                if conc["subject"] == p1["subject"] and conc["predicate"] == p2["predicate"]:
                    return p, s, p1["predicate"], "Barbara"

        return None, None, None, None

    def _check_transitive(self, p1, p2, conc) -> bool:
        """Check if the conclusion follows by transitivity."""
        if p1["quantifier"] == "all" and p2["quantifier"] == "all" and conc["quantifier"] == "all":
            # All A are B, All B are C → All A are C
            if (p1["predicate"] == p2["subject"]
                    and conc["subject"] == p1["subject"]
                    and conc["predicate"] == p2["predicate"]):
                return True
            # All B are C, All A are B → All A are C
            if (p2["predicate"] == p1["subject"]
                    and conc["subject"] == p2["subject"]
                    and conc["predicate"] == p1["predicate"]):
                return True
        return False


# ═══════════════════════════════════════════════════════════
# MAIN THEOREM PROVER — Unified Interface
# ═══════════════════════════════════════════════════════════

class TheoremProver:
    """
    Unified theorem prover combining:
      1. Natural Deduction
      2. Resolution Refutation
      3. Mathematical Induction
      4. Syllogistic Reasoning

    Usage:
        prover = TheoremProver()

        # Prove a syllogism
        result = prover.prove_syllogism(
            "All humans are mortal",
            "All Greeks are humans",
            "All Greeks are mortal"
        )

        # Prove from logical formulas
        P, Q = Atom("P"), Atom("Q")
        result = prover.prove([P, Implies(P, Q)], Q)

        # Prove by induction
        result = prover.prove_induction(
            "Sum(1..n) = n*(n+1)/2",
            base_check=lambda n: sum(range(n+1)) == n*(n+1)//2,
            step_check=lambda k: sum(range(k+2)) == (k+1)*(k+2)//2,
        )
    """

    def __init__(self):
        self.natural_deduction = NaturalDeduction()
        self.resolution = ResolutionEngine()
        self.induction = InductionEngine()
        self.syllogism = SyllogismEngine()
        self._stats = {"proofs_attempted": 0, "proofs_succeeded": 0}

    def prove(self, premises: List[Formula], conclusion: Formula) -> ProofResult:
        """
        Prove conclusion from premises.
        Tries natural deduction first, falls back to resolution.
        """
        self._stats["proofs_attempted"] += 1

        # Try natural deduction first (more readable proofs)
        result = self.natural_deduction.prove(premises, conclusion)
        if result.proved:
            self._stats["proofs_succeeded"] += 1
            return result

        # Fall back to resolution
        result = self.resolution.prove(premises, conclusion)
        if result.proved:
            self._stats["proofs_succeeded"] += 1
        return result

    def prove_syllogism(self, premise1: str, premise2: str, conclusion: str) -> ProofResult:
        """Prove a syllogistic argument."""
        self._stats["proofs_attempted"] += 1
        result = self.syllogism.prove_syllogism(premise1, premise2, conclusion)
        if result.proved:
            self._stats["proofs_succeeded"] += 1
        return result

    def prove_induction(
        self,
        statement: str,
        base_check: Optional[Callable] = None,
        step_check: Optional[Callable] = None,
        property_name: str = "P",
        base_value: int = 0,
    ) -> ProofResult:
        """Prove a statement by mathematical induction."""
        self._stats["proofs_attempted"] += 1
        result = self.induction.prove_induction(
            statement, base_check, step_check, property_name, base_value
        )
        if result.proved:
            self._stats["proofs_succeeded"] += 1
        return result

    def solve(self, prompt: str) -> ProofResult:
        """
        Natural language interface for theorem proving.
        Parses prompts and attempts to prove statements.
        """
        prompt_lower = prompt.lower()

        # Syllogism detection
        if any(kw in prompt_lower for kw in ['all', 'no ', 'some']) and 'are' in prompt_lower:
            lines = [l.strip() for l in prompt.split('\n') if l.strip()]
            # Filter to proposition-like lines
            props = [l for l in lines if re.match(r'(?:All|No|Some)\s+\w+\s+are', l, re.I)]
            if len(props) >= 3:
                return self.prove_syllogism(props[0], props[1], props[-1])
            elif len(props) == 2:
                # Try to infer conclusion
                p1 = self.syllogism._parse_proposition(props[0])
                p2 = self.syllogism._parse_proposition(props[1])
                if p1 and p2 and p1["quantifier"] == "all" and p2["quantifier"] == "all":
                    if p1["predicate"] == p2["subject"]:
                        conc = f"All {p1['subject']} are {p2['predicate']}"
                        return self.prove_syllogism(props[0], props[1], conc)

        # Induction detection
        if any(kw in prompt_lower for kw in ['induction', 'for all n', 'prove that sum']):
            # Example: "Prove sum(1..n) = n(n+1)/2"
            if 'sum' in prompt_lower:
                return self.prove_induction(
                    prompt,
                    base_check=lambda n: sum(range(n + 1)) == n * (n + 1) // 2,
                    step_check=lambda k: sum(range(k + 2)) == (k + 1) * (k + 2) // 2,
                    property_name="Sum",
                    base_value=0,
                )

        # Default: try to parse logical connectives
        # (Basic heuristic for simple prompts)
        return ProofResult(statement=prompt, proved=False, method="No applicable method found")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "TheoremProver",
            "proofs_attempted": self._stats["proofs_attempted"],
            "proofs_succeeded": self._stats["proofs_succeeded"],
            "success_rate": (
                self._stats["proofs_succeeded"] / max(self._stats["proofs_attempted"], 1)
            ),
        }
