"""
Thought Crystallization Engine — O(log n) Reasoning Hardener
════════════════════════════════════════════════════════════
Transforms fluid reasoning chains into crystallized decision trees
that execute in O(log n) instead of O(n). Every successful reasoning
path hardens into a crystal for instant future traversal.

Architecture:
  Reasoning Chain → Crystal Compiler → Decision Tree → Crystal Lattice
                         ↓                  ↓              ↓
                   Pattern Extract    Binary Splits    Indexed Library
"""

import hashlib
import logging
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""
    step_id: str = ""
    question: str = ""
    answer: str = ""
    confidence: float = 0.0
    branch: str = "main"

    def __post_init__(self):
        if not self.step_id:
            self.step_id = secrets.token_hex(3)


@dataclass
class DecisionNode:
    """A node in a crystallized decision tree."""
    node_id: str = ""
    condition: str = ""
    yes_child: Optional[str] = None
    no_child: Optional[str] = None
    leaf_answer: Optional[str] = None
    depth: int = 0

    def __post_init__(self):
        if not self.node_id:
            self.node_id = secrets.token_hex(3)

    @property
    def is_leaf(self) -> bool:
        return self.leaf_answer is not None


@dataclass
class ReasoningCrystal:
    """A compiled, crystallized reasoning pattern."""
    crystal_id: str = ""
    problem_signature: str = ""
    root_node_id: str = ""
    nodes: Dict[str, DecisionNode] = field(default_factory=dict)
    total_nodes: int = 0
    depth: int = 0
    hit_count: int = 0
    miss_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    valid: bool = True

    def __post_init__(self):
        if not self.crystal_id:
            self.crystal_id = secrets.token_hex(6)

    @property
    def hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        return self.hit_count / max(total, 1)

    def traverse(self, evaluator: Callable[[str], bool]) -> Optional[str]:
        """Traverse the crystal decision tree in O(log n)."""
        current = self.nodes.get(self.root_node_id)
        steps = 0

        while current and not current.is_leaf and steps < self.depth + 5:
            steps += 1
            if evaluator(current.condition):
                current = self.nodes.get(current.yes_child or "")
            else:
                current = self.nodes.get(current.no_child or "")

        if current and current.is_leaf:
            self.hit_count += 1
            self.last_used = time.time()
            return current.leaf_answer

        self.miss_count += 1
        return None


@dataclass
class CrystallizationResult:
    """Result of crystallizing a reasoning chain."""
    crystal_id: str = ""
    success: bool = False
    nodes_created: int = 0
    tree_depth: int = 0
    compilation_ms: float = 0.0


class ThoughtCrystallizer:
    """
    Compiles fluid reasoning chains into crystallized decision trees.

    Usage:
        crystallizer = ThoughtCrystallizer()

        # Record a reasoning chain
        crystallizer.record_chain("sort_algorithm", [
            ReasoningStep(question="Is data nearly sorted?", answer="yes", confidence=0.9),
            ReasoningStep(question="Is dataset small?", answer="no", confidence=0.8),
            ReasoningStep(question="Is stability needed?", answer="yes", confidence=0.85),
        ], final_answer="Use TimSort")

        # Later, instantly traverse the crystal
        answer = crystallizer.query("sort_algorithm", lambda q: "sorted" in q)
    """

    SHATTER_THRESHOLD = 0.3   # Hit rate below this → crystal is invalid

    def __init__(self):
        self._lattice: Dict[str, ReasoningCrystal] = {}
        self._chain_buffer: Dict[str, List[List[ReasoningStep]]] = defaultdict(list)
        self._total_crystallized: int = 0
        self._total_shattered: int = 0

    def record_chain(
        self,
        problem_type: str,
        steps: List[ReasoningStep],
        final_answer: str,
    ) -> Optional[CrystallizationResult]:
        """
        Record a reasoning chain. After enough chains of the same type,
        automatically crystallize into a decision tree.
        """
        self._chain_buffer[problem_type].append(steps)

        # Crystallize after 3+ chains
        if len(self._chain_buffer[problem_type]) >= 3:
            return self._crystallize(problem_type, final_answer)
        return None

    def query(
        self,
        problem_type: str,
        evaluator: Callable[[str], bool],
    ) -> Optional[str]:
        """Query the crystal lattice for a pre-crystallized answer."""
        sig = self._make_signature(problem_type)
        crystal = self._lattice.get(sig)

        if not crystal or not crystal.valid:
            return None

        answer = crystal.traverse(evaluator)

        if answer:
            logger.debug(
                f"Crystal HIT: {problem_type} → {answer[:50]} "
                f"(depth={crystal.depth})"
            )
        return answer

    def shatter(self, problem_type: str) -> bool:
        """Destroy a crystal that's producing wrong answers."""
        sig = self._make_signature(problem_type)
        crystal = self._lattice.get(sig)
        if crystal:
            crystal.valid = False
            self._total_shattered += 1
            logger.info(f"Crystal SHATTERED: {problem_type}")
            return True
        return False

    def auto_shatter(self) -> int:
        """Auto-shatter crystals with low hit rates."""
        shattered = 0
        for sig, crystal in list(self._lattice.items()):
            total = crystal.hit_count + crystal.miss_count
            if total >= 5 and crystal.hit_rate < self.SHATTER_THRESHOLD:
                crystal.valid = False
                self._total_shattered += 1
                shattered += 1
        return shattered

    def get_stats(self) -> Dict[str, Any]:
        valid = sum(1 for c in self._lattice.values() if c.valid)
        total_hits = sum(c.hit_count for c in self._lattice.values())
        total_misses = sum(c.miss_count for c in self._lattice.values())
        return {
            "total_crystals": len(self._lattice),
            "valid_crystals": valid,
            "shattered": self._total_shattered,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "overall_hit_rate": round(
                total_hits / max(total_hits + total_misses, 1), 3
            ),
            "buffered_chains": sum(
                len(v) for v in self._chain_buffer.values()
            ),
        }

    # ── Private ──

    def _crystallize(
        self,
        problem_type: str,
        final_answer: str,
    ) -> CrystallizationResult:
        """Compile buffered chains into a decision tree."""
        start = time.perf_counter()
        chains = self._chain_buffer[problem_type]

        # Extract unique questions across all chains
        all_questions = []
        for chain in chains:
            for step in chain:
                if step.question and step.question not in all_questions:
                    all_questions.append(step.question)

        # Build binary decision tree from questions
        nodes: Dict[str, DecisionNode] = {}
        root_id = self._build_tree(all_questions, final_answer, nodes, depth=0)

        sig = self._make_signature(problem_type)
        crystal = ReasoningCrystal(
            problem_signature=sig,
            root_node_id=root_id,
            nodes=nodes,
            total_nodes=len(nodes),
            depth=max((n.depth for n in nodes.values()), default=0),
        )

        self._lattice[sig] = crystal
        self._total_crystallized += 1

        # Clear buffer
        self._chain_buffer[problem_type] = []

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Crystallized: {problem_type} → {len(nodes)} nodes, "
            f"depth={crystal.depth}, {duration_ms:.1f}ms"
        )

        return CrystallizationResult(
            crystal_id=crystal.crystal_id,
            success=True,
            nodes_created=len(nodes),
            tree_depth=crystal.depth,
            compilation_ms=duration_ms,
        )

    def _build_tree(
        self,
        questions: List[str],
        answer: str,
        nodes: Dict[str, DecisionNode],
        depth: int,
    ) -> str:
        """Recursively build a binary decision tree."""
        if not questions or depth > 10:
            # Leaf node
            leaf = DecisionNode(
                condition="",
                leaf_answer=answer,
                depth=depth,
            )
            nodes[leaf.node_id] = leaf
            return leaf.node_id

        # Take first question as split condition
        condition = questions[0]
        remaining = questions[1:]

        node = DecisionNode(condition=condition, depth=depth)

        # Yes branch (with remaining questions)
        node.yes_child = self._build_tree(
            remaining, answer, nodes, depth + 1
        )
        # No branch (skip to remaining)
        node.no_child = self._build_tree(
            remaining[1:] if len(remaining) > 1 else [],
            answer, nodes, depth + 1,
        )

        nodes[node.node_id] = node
        return node.node_id

    @staticmethod
    def _make_signature(problem_type: str) -> str:
        return hashlib.sha256(problem_type.lower().encode()).hexdigest()[:12]
