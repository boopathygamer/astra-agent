"""
Quantum Pathway Pruner — Simulated Annealing Branch Selector
────────────────────────────────────────────────────────────
Expert-level Tree-of-Thoughts branch pruner using simulated
annealing with Metropolis-Hastings acceptance. Evaluates
code quality heuristics to prune dead-end logic branches.
"""

import logging
import math
import secrets
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class QuantumPathwayPruner:
    """
    Quantum-Inspired Pathway Pruning (Tree-of-Thoughts Collapse)

    Uses simulated annealing to evaluate and prune dead-end logic
    branches before they consume LLM tokens. Applies lightweight
    heuristic energy scoring + Metropolis-Hastings acceptance.
    """

    _BAD_PATTERNS = ("syntax error", "infinite loop", "undefined", "notimplemented",
                     "todo", "fixme", "hack", "xxx")
    _GOOD_PATTERNS = ("return", "yield", "try", "except", "class", "def",
                      "async", "await", "import", "logging")

    def __init__(self, initial_temp: float = 100.0, cooling_rate: float = 0.95):
        self._initial_temp = max(1.0, initial_temp)
        self._cooling_rate = max(0.01, min(0.99, cooling_rate))
        self._total_pruned: int = 0
        self._total_evaluated: int = 0
        logger.info("[QUANTUM-PRUNER] Annealing pruner active (T=%.1f, cooling=%.2f).",
                     initial_temp, cooling_rate)

    def _calculate_energy(self, branch: str) -> float:
        """Heuristic energy function. Lower energy = better solution."""
        energy = 100.0
        lower = branch.lower()

        for p in self._BAD_PATTERNS:
            if p in lower:
                energy += 50.0

        for p in self._GOOD_PATTERNS:
            if p in lower:
                energy -= 10.0

        # Complexity penalty
        energy += len(branch) * 0.01
        # Empty penalty
        if len(branch.strip()) < 10:
            energy += 100.0

        return max(1.0, energy)

    def prune_branches(self, thought_branches: List[str]) -> List[str]:
        """
        Prune dead-end branches using simulated annealing.
        Always keeps the best branch; others survive based on
        Metropolis-Hastings probability.
        """
        if not thought_branches:
            return []

        self._total_evaluated += len(thought_branches)

        # Score all branches
        scored: List[Tuple[str, float]] = [
            (b, self._calculate_energy(b)) for b in thought_branches
        ]
        scored.sort(key=lambda x: x[1])

        best_energy = scored[0][1]
        survivors: List[str] = [scored[0][0]]  # Always keep the best
        temp = self._initial_temp

        for branch, energy in scored[1:]:
            delta = energy - best_energy
            # Metropolis-Hastings acceptance criterion
            if delta <= 0:
                acceptance_prob = 1.0
            else:
                acceptance_prob = math.exp(-delta / max(temp, 0.001))

            # Use secrets for non-predictable randomness
            threshold = secrets.randbelow(1000) / 1000.0
            if threshold < acceptance_prob:
                survivors.append(branch)

            temp *= self._cooling_rate

        pruned = len(thought_branches) - len(survivors)
        self._total_pruned += pruned
        logger.info("[QUANTUM-PRUNER] Pruned %d/%d branches (kept %d survivors).",
                     pruned, len(thought_branches), len(survivors))

        return survivors

    @property
    def stats(self) -> dict:
        return {"evaluated": self._total_evaluated, "pruned": self._total_pruned}


# Global singleton — always active
quantum_pruner = QuantumPathwayPruner()
