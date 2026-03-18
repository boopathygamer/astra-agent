"""
Neuro-Symbolic Reasoning Orchestrator
══════════════════════════════════════
Bridges neural (LLM) and symbolic (logic) reasoning for
provably-correct, explainable problem solving.

Inspired by:
  • Garcez et al. (2019) "Neural-Symbolic Computing"
  • Hamilton et al. (2022) "Neuro-Symbolic AI"
  • Prolog-style backward chaining + LLM fact extraction

Architecture:
  ┌─────────────┐     ground()      ┌───────────────┐
  │  LLM Output ├────────────────►  │ Knowledge Base │
  └─────────────┘                   │  (typed facts  │
                                    │   + rules)     │
  ┌─────────────┐     query()       │               │
  │   Question  ├────────────────►  │  ┌──────────┐ │
  └─────────────┘                   │  │ Solver   │ │
                                    │  └────┬─────┘ │
  ┌─────────────┐     narrate()     │       │       │
  │  NL Answer  │◄──────────────────┤       ▼       │
  └─────────────┘                   │  Proof Tree   │
                                    └───────────────┘

Three modes of operation:
  1. Neural → Symbolic: Extract facts from LLM, reason symbolically
  2. Symbolic → Neural: Convert logic conclusions to natural language
  3. Hybrid: Use symbolic when possible, neural for gaps
"""

import hashlib
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ─── Data Model ───────────────────────────────────────────

class FactType(Enum):
    ENTITY = "entity"          # is_a(X, Type)
    RELATION = "relation"      # rel(X, Y)
    PROPERTY = "property"      # has(X, Prop, Value)
    AXIOM = "axiom"            # Always true


@dataclass(frozen=True)
class Fact:
    """An atomic logical fact."""
    predicate: str = ""
    args: Tuple[str, ...] = ()
    fact_type: FactType = FactType.RELATION
    confidence: float = 1.0
    source: str = "axiom"      # "axiom", "llm_extracted", "inferred"

    def __str__(self) -> str:
        args_str = ", ".join(self.args)
        return f"{self.predicate}({args_str})"

    def matches(self, predicate: str, *args: str) -> bool:
        """Check if this fact matches a pattern (None = wildcard)."""
        if self.predicate != predicate:
            return False
        if len(args) != len(self.args):
            return False
        return all(
            a is None or a == b or a == "_"
            for a, b in zip(args, self.args)
        )


@dataclass
class Rule:
    """An inference rule: IF conditions THEN conclusion."""
    rule_id: str = ""
    name: str = ""
    conditions: List[Tuple[str, Tuple[str, ...]]] = field(default_factory=list)
    conclusion: Tuple[str, Tuple[str, ...]] = ("", ())
    confidence: float = 1.0

    def __str__(self) -> str:
        conds = " ∧ ".join(f"{p}({', '.join(a)})" for p, a in self.conditions)
        conc_p, conc_a = self.conclusion
        conc = f"{conc_p}({', '.join(conc_a)})"
        return f"{self.name}: {conds} → {conc}"


@dataclass
class ProofStep:
    """A single step in a proof tree."""
    fact: Optional[Fact] = None
    rule_applied: Optional[Rule] = None
    children: List["ProofStep"] = field(default_factory=list)
    depth: int = 0
    is_axiom: bool = False

    def to_text(self, indent: int = 0) -> str:
        pad = "  " * indent
        if self.is_axiom:
            return f"{pad}├─ [AXIOM] {self.fact}"
        elif self.rule_applied:
            lines = [f"{pad}├─ [RULE: {self.rule_applied.name}] → {self.fact}"]
            for child in self.children:
                lines.append(child.to_text(indent + 1))
            return "\n".join(lines)
        else:
            return f"{pad}├─ [FACT] {self.fact}"


@dataclass
class QueryResult:
    """Result of a symbolic query."""
    query: str = ""
    bindings: List[Dict[str, str]] = field(default_factory=list)
    proof: Optional[ProofStep] = None
    is_satisfiable: bool = False
    confidence: float = 0.0
    natural_language: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "satisfiable": self.is_satisfiable,
            "num_solutions": len(self.bindings),
            "confidence": round(self.confidence, 4),
            "answer": self.natural_language[:200],
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class ConflictReport:
    """Report of a conflict between neural and symbolic reasoning."""
    neural_claim: str = ""
    symbolic_claim: str = ""
    resolution: str = ""       # "neural", "symbolic", "compromise"
    explanation: str = ""
    confidence: float = 0.0


# ─── Knowledge Base ───────────────────────────────────────

class KnowledgeBase:
    """
    Typed knowledge base with facts, rules, and inference.

    Supports:
    - Fact assertion and retraction
    - Pattern matching queries with variables
    - Forward chaining inference
    - Backward chaining (Prolog-style) proof search
    """

    def __init__(self):
        self._facts: Set[Fact] = set()
        self._rules: List[Rule] = []
        self._index: Dict[str, List[Fact]] = defaultdict(list)
        self._rule_counter = 0

    @property
    def fact_count(self) -> int:
        return len(self._facts)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def assert_fact(self, predicate: str, *args: str,
                    fact_type: FactType = FactType.RELATION,
                    confidence: float = 1.0,
                    source: str = "axiom") -> Fact:
        """Add a fact to the knowledge base."""
        fact = Fact(
            predicate=predicate,
            args=tuple(args),
            fact_type=fact_type,
            confidence=confidence,
            source=source,
        )
        self._facts.add(fact)
        self._index[predicate].append(fact)
        return fact

    def retract(self, predicate: str, *args: str) -> int:
        """Remove matching facts. Returns count removed."""
        to_remove = {f for f in self._facts if f.matches(predicate, *args)}
        self._facts -= to_remove
        # Rebuild index for this predicate
        self._index[predicate] = [f for f in self._index[predicate] if f not in to_remove]
        return len(to_remove)

    def add_rule(self, name: str,
                 conditions: List[Tuple[str, Tuple[str, ...]]],
                 conclusion: Tuple[str, Tuple[str, ...]],
                 confidence: float = 1.0) -> Rule:
        """Add an inference rule."""
        self._rule_counter += 1
        rule = Rule(
            rule_id=f"R{self._rule_counter}",
            name=name,
            conditions=conditions,
            conclusion=conclusion,
            confidence=confidence,
        )
        self._rules.append(rule)
        return rule

    def query(self, predicate: str, *args: str) -> List[Tuple[Fact, Dict[str, str]]]:
        """
        Query facts with pattern matching.

        Variables start with uppercase (Prolog convention).
        Returns list of (matching_fact, variable_bindings).
        """
        results = []
        for fact in self._index.get(predicate, []):
            if len(fact.args) != len(args):
                continue
            bindings = {}
            match = True
            for pattern_arg, fact_arg in zip(args, fact.args):
                if pattern_arg == "_":
                    continue
                elif pattern_arg[0].isupper():
                    # Variable — bind it
                    if pattern_arg in bindings:
                        if bindings[pattern_arg] != fact_arg:
                            match = False
                            break
                    else:
                        bindings[pattern_arg] = fact_arg
                elif pattern_arg != fact_arg:
                    match = False
                    break
            if match:
                results.append((fact, bindings))
        return results

    def forward_chain(self, max_iterations: int = 10) -> List[Fact]:
        """
        Forward chaining: apply rules to derive new facts.

        Iteratively applies all rules until no new facts are derived
        or max_iterations is reached.
        """
        new_facts = []
        for _ in range(max_iterations):
            derived_any = False
            for rule in self._rules:
                # Try to match all conditions
                all_bindings = self._match_conditions(rule.conditions)
                for binding in all_bindings:
                    # Apply binding to conclusion
                    conc_pred, conc_args = rule.conclusion
                    resolved_args = tuple(
                        binding.get(a, a) for a in conc_args
                    )
                    # Check if this fact already exists
                    existing = Fact(predicate=conc_pred, args=resolved_args)
                    if existing not in self._facts:
                        new = self.assert_fact(
                            conc_pred, *resolved_args,
                            confidence=rule.confidence * 0.95,
                            source=f"inferred:{rule.rule_id}",
                        )
                        new_facts.append(new)
                        derived_any = True
            if not derived_any:
                break
        return new_facts

    def backward_chain(self, predicate: str, *args: str,
                       depth: int = 0, max_depth: int = 10,
                       visited: Optional[FrozenSet] = None) -> Optional[ProofStep]:
        """
        Backward chaining: prove a goal by finding supporting facts/rules.

        Returns a ProofStep (proof tree) if the goal can be proven, None otherwise.
        """
        if depth > max_depth:
            return None

        goal_key = (predicate, args)
        if visited is None:
            visited = frozenset()
        if goal_key in visited:
            return None  # Cycle detection
        visited = visited | {goal_key}

        # Check direct facts
        matches = self.query(predicate, *args)
        if matches:
            fact, bindings = matches[0]
            return ProofStep(
                fact=fact,
                depth=depth,
                is_axiom=(fact.source == "axiom"),
            )

        # Try rules whose conclusion matches the goal
        for rule in self._rules:
            conc_pred, conc_args = rule.conclusion
            if conc_pred != predicate or len(conc_args) != len(args):
                continue

            # Unify conclusion with goal
            bindings = {}
            match = True
            for pattern, actual in zip(conc_args, args):
                if pattern[0].isupper():
                    bindings[pattern] = actual
                elif pattern != actual:
                    match = False
                    break
            if not match:
                continue

            # Try to prove all conditions
            child_proofs = []
            all_proven = True
            for cond_pred, cond_args in rule.conditions:
                resolved = tuple(bindings.get(a, a) for a in cond_args)
                child_proof = self.backward_chain(
                    cond_pred, *resolved,
                    depth=depth + 1,
                    max_depth=max_depth,
                    visited=visited,
                )
                if child_proof is None:
                    all_proven = False
                    break
                child_proofs.append(child_proof)

            if all_proven:
                goal_fact = Fact(predicate=predicate, args=tuple(args), source=f"proven:{rule.rule_id}")
                return ProofStep(
                    fact=goal_fact,
                    rule_applied=rule,
                    children=child_proofs,
                    depth=depth,
                )

        return None

    def _match_conditions(self, conditions: List[Tuple[str, Tuple[str, ...]]],
                          bindings: Optional[Dict[str, str]] = None,
                          idx: int = 0) -> List[Dict[str, str]]:
        """Recursively match all conditions, building up variable bindings."""
        if bindings is None:
            bindings = {}
        if idx >= len(conditions):
            return [dict(bindings)]

        pred, args = conditions[idx]
        resolved_args = tuple(bindings.get(a, a) for a in args)
        results = []

        for fact, new_bindings in self.query(pred, *resolved_args):
            merged = {**bindings, **new_bindings}
            sub_results = self._match_conditions(conditions, merged, idx + 1)
            results.extend(sub_results)

        return results

    def export_facts(self) -> List[str]:
        """Export all facts as strings."""
        return [str(f) for f in sorted(self._facts, key=str)]


# ─── Neuro-Symbolic Orchestrator ──────────────────────────

class NeuroSymbolicReasoner:
    """
    Bridges neural (LLM) and symbolic (formal logic) reasoning.

    Three modes:
    1. Neural → Symbolic: Extract facts from LLM output, reason formally
    2. Symbolic → Neural: Convert proof results to natural language
    3. Hybrid: Use symbolic when confident, fall back to neural

    The orchestrator detects conflicts between neural intuition and
    symbolic deduction, and resolves them using confidence weighting.
    """

    EXTRACTION_PROMPT = (
        "Extract factual statements from this text as structured facts.\n\n"
        "Text: {text}\n\n"
        "Format each fact as: PREDICATE(arg1, arg2)\n"
        "Examples: is_a(Python, language), has(Python, typing, dynamic), "
        "supports(Python, OOP)\n\n"
        "Facts:"
    )

    NARRATION_PROMPT = (
        "Convert this formal proof into a clear natural language explanation.\n\n"
        "Original question: {question}\n"
        "Proof tree:\n{proof}\n\n"
        "Explain the reasoning in plain English, step by step:"
    )

    CONFLICT_PROMPT = (
        "There is a conflict between two reasoning systems.\n\n"
        "Neural (LLM) says: {neural}\n"
        "Symbolic (Logic) says: {symbolic}\n\n"
        "Which is more likely correct and why? Resolve the conflict.\n"
        "WINNER: [neural/symbolic/compromise]\n"
        "EXPLANATION: [reasoning]"
    )

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self.kb = KnowledgeBase()
        self._conflicts: List[ConflictReport] = []
        self._query_count = 0

        # Seed with common-sense axioms
        self._seed_axioms()

        logger.info(
            f"[NEURO-SYM] Initialized — "
            f"{self.kb.fact_count} axioms, {self.kb.rule_count} rules"
        )

    def _seed_axioms(self) -> None:
        """Seed the KB with common programming/reasoning axioms."""
        # Type hierarchy
        self.kb.add_rule(
            name="transitivity",
            conditions=[("is_a", ("X", "Y")), ("is_a", ("Y", "Z"))],
            conclusion=("is_a", ("X", "Z")),
        )

        # If X has property P and X is_a Y, Y's instances may share P
        self.kb.add_rule(
            name="property_inheritance",
            conditions=[("has", ("X", "P", "V")), ("is_a", ("Y", "X"))],
            conclusion=("may_have", ("Y", "P", "V")),
            confidence=0.8,
        )

        # Mutual exclusion
        self.kb.add_rule(
            name="contradiction_detector",
            conditions=[("is", ("X", "true")), ("is", ("X", "false"))],
            conclusion=("contradiction", ("X", "detected")),
        )

    def ground(self, text: str, source: str = "llm_extracted") -> List[Fact]:
        """
        Neural→Symbolic: Extract facts from natural language text
        and add them to the knowledge base.
        """
        facts = []

        if self.generate_fn:
            prompt = self.EXTRACTION_PROMPT.format(text=text[:2000])
            try:
                response = self.generate_fn(prompt)
                facts = self._parse_facts(response, source)
            except Exception as e:
                logger.warning(f"[NEURO-SYM] Fact extraction failed: {e}")

        if not facts:
            facts = self._heuristic_extract(text, source)

        for fact in facts:
            self.kb.assert_fact(
                fact.predicate, *fact.args,
                fact_type=fact.fact_type,
                confidence=fact.confidence,
                source=source,
            )

        logger.info(f"[NEURO-SYM] Grounded {len(facts)} facts from text")
        return facts

    def reason(self, question: str, context: str = "") -> QueryResult:
        """
        Hybrid reasoning: try symbolic first, fall back to neural.
        """
        start = time.time()
        self._query_count += 1
        result = QueryResult(query=question)

        # Ground context if provided
        if context:
            self.ground(context, source="context")

        # Forward chain to derive new facts
        derived = self.kb.forward_chain()
        if derived:
            logger.info(f"[NEURO-SYM] Forward chaining derived {len(derived)} new facts")

        # Try to parse the question into a symbolic query
        symbolic_query = self._parse_query(question)

        if symbolic_query:
            pred, args = symbolic_query
            # Backward chain to prove
            proof = self.kb.backward_chain(pred, *args)
            if proof:
                result.is_satisfiable = True
                result.proof = proof
                result.confidence = 0.9
                # Convert proof to natural language
                result.natural_language = self._narrate_proof(question, proof)
                result.duration_ms = (time.time() - start) * 1000
                return result

            # Try direct query
            matches = self.kb.query(pred, *args)
            if matches:
                result.is_satisfiable = True
                result.bindings = [b for _, b in matches]
                result.confidence = max(f.confidence for f, _ in matches)
                result.natural_language = self._format_query_results(matches)
                result.duration_ms = (time.time() - start) * 1000
                return result

        # Symbolic reasoning insufficient — use neural
        if self.generate_fn:
            # Get neural answer
            neural_answer = self.generate_fn(
                f"Question: {question}\n"
                f"{'Context: ' + context[:500] if context else ''}\n"
                f"Provide a clear, well-reasoned answer:"
            )

            # Ground the neural answer to extract new facts
            self.ground(neural_answer, source="neural_inference")

            result.is_satisfiable = True
            result.natural_language = neural_answer
            result.confidence = 0.6  # Lower confidence for neural-only

        result.duration_ms = (time.time() - start) * 1000
        return result

    def resolve_conflict(self, neural_claim: str,
                         symbolic_claim: str) -> ConflictReport:
        """
        Resolve a conflict between neural and symbolic reasoning.
        """
        report = ConflictReport(
            neural_claim=neural_claim,
            symbolic_claim=symbolic_claim,
        )

        if self.generate_fn:
            prompt = self.CONFLICT_PROMPT.format(
                neural=neural_claim[:300],
                symbolic=symbolic_claim[:300],
            )
            try:
                response = self.generate_fn(prompt)
                winner = "symbolic"  # Default to symbolic (provable)
                if "neural" in response.lower()[:100]:
                    winner = "neural"
                elif "compromise" in response.lower()[:100]:
                    winner = "compromise"
                report.resolution = winner
                report.explanation = response
                report.confidence = 0.7 if winner == "symbolic" else 0.5
            except Exception as e:
                logger.warning(f"[NEURO-SYM] Conflict resolution failed: {e}")
                report.resolution = "symbolic"
                report.confidence = 0.6
        else:
            # Default: trust symbolic reasoning (it's provable)
            report.resolution = "symbolic"
            report.explanation = "Symbolic reasoning preferred as it is formally verifiable"
            report.confidence = 0.7

        self._conflicts.append(report)
        return report

    def _narrate_proof(self, question: str, proof: ProofStep) -> str:
        """Symbolic→Neural: Convert proof to natural language."""
        proof_text = proof.to_text()

        if self.generate_fn:
            prompt = self.NARRATION_PROMPT.format(
                question=question[:300], proof=proof_text[:1500]
            )
            try:
                return self.generate_fn(prompt)
            except Exception:
                pass

        # Fallback: structured text
        return f"Based on logical reasoning:\n{proof_text}"

    def _parse_query(self, question: str) -> Optional[Tuple[str, Tuple[str, ...]]]:
        """Try to convert a natural language question into a symbolic query."""
        q = question.lower().strip()

        # "Is X a Y?" → is_a(X, Y)
        m = re.match(r"is\s+(\w+)\s+(?:a|an)\s+(\w+)", q)
        if m:
            return ("is_a", (m.group(1), m.group(2)))

        # "Does X have Y?" → has(X, Y, _)
        m = re.match(r"does\s+(\w+)\s+have\s+(\w+)", q)
        if m:
            return ("has", (m.group(1), m.group(2), "_"))

        # "Does X support Y?" → supports(X, Y)
        m = re.match(r"does\s+(\w+)\s+support\s+(\w+)", q)
        if m:
            return ("supports", (m.group(1), m.group(2)))

        # "What is X?" → is_a(X, _)
        m = re.match(r"what\s+is\s+(?:a|an)?\s*(\w+)", q)
        if m:
            return ("is_a", (m.group(1), "_"))

        return None

    def _parse_facts(self, response: str, source: str) -> List[Fact]:
        """Parse structured facts from LLM response."""
        facts = []
        # Match: predicate(arg1, arg2, ...)
        pattern = re.compile(r"(\w+)\(([^)]+)\)")
        for match in pattern.finditer(response):
            predicate = match.group(1).lower()
            args = tuple(a.strip().lower() for a in match.group(2).split(","))
            fact_type = FactType.ENTITY if predicate == "is_a" else FactType.RELATION
            facts.append(Fact(
                predicate=predicate,
                args=args,
                fact_type=fact_type,
                confidence=0.75,
                source=source,
            ))
        return facts

    @staticmethod
    def _heuristic_extract(text: str, source: str) -> List[Fact]:
        """Heuristic fact extraction when LLM is unavailable."""
        facts = []
        sentences = text.split(".")

        for sent in sentences[:10]:
            sent = sent.strip().lower()
            if not sent:
                continue

            # "X is a Y" pattern
            m = re.match(r"(\w+)\s+is\s+(?:a|an)\s+(\w+)", sent)
            if m:
                facts.append(Fact(
                    predicate="is_a",
                    args=(m.group(1), m.group(2)),
                    fact_type=FactType.ENTITY,
                    confidence=0.6,
                    source=source,
                ))

            # "X has Y" pattern
            m = re.match(r"(\w+)\s+has\s+(\w+)", sent)
            if m:
                facts.append(Fact(
                    predicate="has",
                    args=(m.group(1), m.group(2), "true"),
                    fact_type=FactType.PROPERTY,
                    confidence=0.5,
                    source=source,
                ))

        return facts

    @staticmethod
    def _format_query_results(matches: List[Tuple[Fact, Dict[str, str]]]) -> str:
        """Format query results into natural language."""
        parts = []
        for fact, bindings in matches[:5]:
            if bindings:
                bind_str = ", ".join(f"{k}={v}" for k, v in bindings.items())
                parts.append(f"{fact} [where {bind_str}]")
            else:
                parts.append(str(fact))
        return "Found: " + "; ".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "facts": self.kb.fact_count,
            "rules": self.kb.rule_count,
            "queries": self._query_count,
            "conflicts_resolved": len(self._conflicts),
        }
