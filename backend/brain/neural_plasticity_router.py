"""
Neural Plasticity Router — Self-Rewiring Architecture Topology
══════════════════════════════════════════════════════════════
Module connections dynamically strengthen or weaken based on
co-activation patterns, exactly like biological neural plasticity.
Implements Hebbian learning: "neurons that fire together wire together."

Architecture:
  Module A calls Module B → Synapse(A→B).strength += Δ  (LTP)
  Module C unused after D  → Synapse(D→C).strength -= Δ  (Atrophy)
  Result: Architecture self-optimizes its own wiring topology.
"""

import logging
import math
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class PlasticSynapse:
    """A dynamic connection between two brain modules."""
    source: str = ""
    target: str = ""
    strength: float = 0.5       # 0.0 (atrophied) → 1.0 (fully potentiated)
    activation_count: int = 0
    last_activated: float = field(default_factory=time.time)
    creation_time: float = field(default_factory=time.time)
    ltp_events: int = 0         # Long-Term Potentiation events
    ltd_events: int = 0         # Long-Term Depression events

    @property
    def synapse_key(self) -> str:
        return f"{self.source}→{self.target}"

    @property
    def age_s(self) -> float:
        return time.time() - self.creation_time

    @property
    def time_since_activation(self) -> float:
        return time.time() - self.last_activated

    @property
    def is_atrophied(self) -> bool:
        return self.strength < 0.1

    @property
    def is_potentiated(self) -> bool:
        return self.strength > 0.8


@dataclass
class ModuleActivation:
    """Record of a module being activated."""
    module_name: str = ""
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    success: bool = True


@dataclass
class PlasticitySnapshot:
    """Snapshot of the current wiring topology."""
    total_synapses: int = 0
    active_synapses: int = 0
    atrophied_synapses: int = 0
    potentiated_synapses: int = 0
    avg_strength: float = 0.0
    strongest_pathway: str = ""
    weakest_pathway: str = ""
    total_ltp_events: int = 0
    total_ltd_events: int = 0
    pruned_count: int = 0

    def summary(self) -> str:
        return (
            f"Plasticity: {self.active_synapses}/{self.total_synapses} active | "
            f"LTP={self.total_ltp_events} LTD={self.total_ltd_events} | "
            f"Avg={self.avg_strength:.2f}"
        )


# ──────────────────────────────────────────────
# Hebbian Learning Engine
# ──────────────────────────────────────────────

class HebbianEngine:
    """
    Implements Hebbian learning rules for synapse plasticity.
    "Neurons that fire together wire together."
    """

    # Learning rate parameters
    LTP_RATE = 0.05            # Strength gain per co-activation
    LTD_RATE = 0.02            # Strength decay per missed window
    ATROPHY_RATE = 0.005       # Passive decay over time
    CO_ACTIVATION_WINDOW_S = 2.0  # Window to detect co-activation

    @classmethod
    def apply_ltp(cls, synapse: PlasticSynapse) -> float:
        """Long-Term Potentiation: strengthen synapse on co-activation."""
        old = synapse.strength
        # Diminishing returns near saturation
        gain = cls.LTP_RATE * (1.0 - synapse.strength)
        synapse.strength = min(1.0, synapse.strength + gain)
        synapse.ltp_events += 1
        synapse.activation_count += 1
        synapse.last_activated = time.time()
        return synapse.strength - old

    @classmethod
    def apply_ltd(cls, synapse: PlasticSynapse) -> float:
        """Long-Term Depression: weaken synapse on failed co-activation."""
        old = synapse.strength
        decay = cls.LTD_RATE * synapse.strength
        synapse.strength = max(0.0, synapse.strength - decay)
        synapse.ltd_events += 1
        return old - synapse.strength

    @classmethod
    def apply_atrophy(cls, synapse: PlasticSynapse) -> float:
        """Passive time-based decay for unused synapses."""
        idle_s = synapse.time_since_activation
        if idle_s < 10.0:
            return 0.0  # Grace period

        # Exponential decay scaled by idle time
        decay = cls.ATROPHY_RATE * math.log1p(idle_s / 60.0)
        old = synapse.strength
        synapse.strength = max(0.0, synapse.strength - decay)
        return old - synapse.strength


# ──────────────────────────────────────────────
# Neural Plasticity Router (Main Interface)
# ──────────────────────────────────────────────

class NeuralPlasticityRouter:
    """
    Self-rewiring inter-module router using Hebbian plasticity.

    Usage:
        router = NeuralPlasticityRouter()

        # Record module activations
        router.activate("thinking_loop")
        router.activate("memory")           # Co-activated → synapse strengthens
        router.activate("verifier")         # Co-activated → synapse strengthens

        # Query optimal routing
        best_next = router.suggest_next("thinking_loop")
        # Returns modules most likely to be needed next

        # Periodic maintenance
        router.run_plasticity_cycle()       # Apply atrophy, prune dead synapses
    """

    PRUNE_THRESHOLD = 0.05     # Synapses below this are pruned
    MAX_SUGGESTIONS = 5

    def __init__(self):
        self._synapses: Dict[str, PlasticSynapse] = {}     # "A→B" → synapse
        self._recent_activations: deque = deque(maxlen=200)
        self._module_registry: Set[str] = set()
        self._total_pruned: int = 0
        self._activation_window: deque = deque(maxlen=50)   # For co-activation detection

    def activate(self, module_name: str, duration_ms: float = 0.0, success: bool = True) -> List[str]:
        """
        Record a module activation. Automatically strengthens synapses
        with recently co-activated modules.
        Returns list of modules whose synapses were strengthened.
        """
        self._module_registry.add(module_name)
        now = time.time()

        activation = ModuleActivation(
            module_name=module_name,
            timestamp=now,
            duration_ms=duration_ms,
            success=success,
        )
        self._recent_activations.append(activation)
        self._activation_window.append(activation)

        # Find co-activated modules within the window
        strengthened = []
        for recent in self._activation_window:
            if recent.module_name == module_name:
                continue
            if now - recent.timestamp <= HebbianEngine.CO_ACTIVATION_WINDOW_S:
                # Bidirectional LTP
                self._strengthen(recent.module_name, module_name)
                self._strengthen(module_name, recent.module_name)
                strengthened.append(recent.module_name)

        if strengthened:
            logger.debug(
                f"Plasticity: {module_name} co-activated with {strengthened}"
            )

        return strengthened

    def suggest_next(self, current_module: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """
        Suggest which modules are most likely needed next,
        based on synapse strength from the current module.
        """
        suggestions = []
        for key, syn in self._synapses.items():
            if syn.source == current_module and not syn.is_atrophied:
                suggestions.append((syn.target, syn.strength))

        suggestions.sort(key=lambda x: x[1], reverse=True)
        return suggestions[:top_k]

    def get_strength(self, source: str, target: str) -> float:
        """Get the synapse strength between two modules."""
        key = f"{source}→{target}"
        syn = self._synapses.get(key)
        return syn.strength if syn else 0.0

    def run_plasticity_cycle(self) -> PlasticitySnapshot:
        """
        Run a full plasticity maintenance cycle:
        1. Apply atrophy to unused synapses
        2. Prune dead synapses
        3. Return topology snapshot
        """
        pruned = 0
        total_ltp = 0
        total_ltd = 0

        # Apply atrophy
        to_prune = []
        for key, syn in self._synapses.items():
            HebbianEngine.apply_atrophy(syn)
            total_ltp += syn.ltp_events
            total_ltd += syn.ltd_events

            if syn.strength < self.PRUNE_THRESHOLD:
                to_prune.append(key)

        # Prune
        for key in to_prune:
            del self._synapses[key]
            pruned += 1
            self._total_pruned += 1

        if pruned > 0:
            logger.info(f"Plasticity: pruned {pruned} atrophied synapses")

        return self._snapshot(pruned)

    def get_topology(self) -> Dict[str, List[Tuple[str, float]]]:
        """Get the full wiring topology as an adjacency list."""
        topology: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        for syn in self._synapses.values():
            if not syn.is_atrophied:
                topology[syn.source].append((syn.target, round(syn.strength, 3)))
        return dict(topology)

    def get_stats(self) -> Dict[str, Any]:
        snapshot = self._snapshot(0)
        return {
            "total_synapses": snapshot.total_synapses,
            "active": snapshot.active_synapses,
            "potentiated": snapshot.potentiated_synapses,
            "atrophied": snapshot.atrophied_synapses,
            "avg_strength": round(snapshot.avg_strength, 3),
            "total_pruned": self._total_pruned,
            "registered_modules": len(self._module_registry),
        }

    # ── Private ──

    def _strengthen(self, source: str, target: str) -> None:
        """Strengthen or create a synapse between source and target."""
        key = f"{source}→{target}"
        if key not in self._synapses:
            self._synapses[key] = PlasticSynapse(source=source, target=target)

        HebbianEngine.apply_ltp(self._synapses[key])

    def _snapshot(self, pruned: int) -> PlasticitySnapshot:
        synapses = list(self._synapses.values())
        if not synapses:
            return PlasticitySnapshot(pruned_count=pruned)

        active = [s for s in synapses if not s.is_atrophied]
        potentiated = [s for s in synapses if s.is_potentiated]
        atrophied = [s for s in synapses if s.is_atrophied]
        strengths = [s.strength for s in synapses]
        strongest = max(synapses, key=lambda s: s.strength)
        weakest = min(synapses, key=lambda s: s.strength)

        return PlasticitySnapshot(
            total_synapses=len(synapses),
            active_synapses=len(active),
            atrophied_synapses=len(atrophied),
            potentiated_synapses=len(potentiated),
            avg_strength=sum(strengths) / len(strengths),
            strongest_pathway=strongest.synapse_key,
            weakest_pathway=weakest.synapse_key,
            total_ltp_events=sum(s.ltp_events for s in synapses),
            total_ltd_events=sum(s.ltd_events for s in synapses),
            pruned_count=pruned,
        )
