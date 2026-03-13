"""
Boltzmann Brain — Stochastic Code Sampling via Temperature-Scaled Selection
────────────────────────────────────────────────────────────────────────────
Instead of deterministically picking the single "best" hypothesis, the
Boltzmann generator uses a Boltzmann probability distribution to sample
from a pool of candidate solutions. Lower temperatures → more exploitation
(picks the highest-scoring). Higher temperatures → more exploration.

This is the mathematical equivalent of "spontaneous generation" — the
selected code emerges probabilistically from a thermal distribution.
"""

import logging
import math
import secrets
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BoltzmannCandidate:
    """A candidate solution with an associated energy (lower = better)."""
    code: str
    energy: float  # Lower energy → higher quality
    source: str = "unknown"


class BoltzmannGenerator:
    """
    Tier Aleph: Boltzmann Brain Spontaneous Generation

    Uses statistical mechanics to probabilistically select code candidates
    from a thermal energy distribution. The selection probability follows:
        P(i) = exp(-E_i / T) / Σ exp(-E_j / T)
    """

    def __init__(self, temperature: float = 1.0, min_temperature: float = 0.01):
        self._temperature = max(min_temperature, temperature)
        self._min_temperature = min_temperature
        self._generations: int = 0
        logger.info("[BOLTZMANN] Generator initialized (T=%.4f).", self._temperature)

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, value: float) -> None:
        self._temperature = max(self._min_temperature, value)

    def _softmax_probabilities(self, candidates: List[BoltzmannCandidate]) -> List[float]:
        """
        Compute Boltzmann distribution probabilities:
            P(i) = exp(-E_i / T) / Z,  where Z = Σ exp(-E_j / T)
        Uses log-sum-exp trick for numerical stability.
        """
        if not candidates:
            return []

        neg_energies = [-c.energy / self._temperature for c in candidates]
        max_ne = max(neg_energies)

        # Log-sum-exp for numerical stability
        exp_shifted = [math.exp(ne - max_ne) for ne in neg_energies]
        partition_z = sum(exp_shifted)

        if partition_z < 1e-300:
            # Uniform fallback to prevent division by zero
            n = len(candidates)
            return [1.0 / n] * n

        return [e / partition_z for e in exp_shifted]

    def sample(self, candidates: List[BoltzmannCandidate]) -> Optional[BoltzmannCandidate]:
        """
        Sample a single candidate from the Boltzmann distribution.
        Uses cryptographically secure randomness to prevent predictability.
        """
        if not candidates:
            logger.warning("[BOLTZMANN] Empty candidate pool — no vacuum fluctuation possible.")
            return None

        probabilities = self._softmax_probabilities(candidates)

        # Cryptographically secure uniform sample
        rand_val = secrets.randbelow(10**9) / 10**9
        cumulative = 0.0
        selected = candidates[-1]  # fallback

        for candidate, prob in zip(candidates, probabilities):
            cumulative += prob
            if rand_val <= cumulative:
                selected = candidate
                break

        self._generations += 1
        logger.info(
            "[BOLTZMANN] Spontaneous selection from %d candidates (T=%.4f, gen=#%d): energy=%.4f",
            len(candidates), self._temperature, self._generations, selected.energy,
        )
        return selected

    def anneal(self, cooling_rate: float = 0.95) -> float:
        """Cool the system, making future selections more deterministic."""
        self._temperature = max(self._min_temperature, self._temperature * cooling_rate)
        logger.debug("[BOLTZMANN] Annealed to T=%.6f.", self._temperature)
        return self._temperature

    def reheat(self, factor: float = 2.0) -> float:
        """Reheat the system for more exploration."""
        self._temperature *= max(1.0, factor)
        logger.debug("[BOLTZMANN] Reheated to T=%.4f.", self._temperature)
        return self._temperature


# Global singleton — always active
boltzmann_engine = BoltzmannGenerator()
