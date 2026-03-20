"""
Phantom Execution Sandbox — Virtual Pre-Execution Simulation
═══════════════════════════════════════════════════════════════
Simulates every action in a virtual environment BEFORE real execution.
Predicts side-effects, risk scores, cascading failures, and temporal impacts.

No LLM, no GPU — pure deterministic simulation.

Architecture:
  Action → Phantom State Clone → Virtual Execution
                                      ↓
                              Effect Propagation Graph
                                      ↓
                              Risk Score + Temporal Projection
                                      ↓
                              APPROVE / REJECT / WARN

Novel contributions:
  • State snapshot/restore with copy-on-write efficiency
  • Side-effect DAG: models cascading consequences
  • Risk scoring: quantifies danger of any action
  • Temporal projection: simulates future state evolution
  • Rollback guarantee: no real state is ever touched during simulation
"""

import copy
import hashlib
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# RISK LEVELS & ACTIONS
# ═══════════════════════════════════════════════════════════

class RiskLevel(Enum):
    SAFE = "safe"              # No side effects
    LOW = "low"                # Reversible side effects
    MEDIUM = "medium"          # Non-trivial but contained effects
    HIGH = "high"              # Potentially destructive
    CRITICAL = "critical"      # Irreversible, dangerous

    @property
    def score(self) -> float:
        return {"safe": 0.0, "low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}[self.value]


class ActionType(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    NETWORK = "network"
    COMPUTE = "compute"
    MODIFY_STATE = "modify_state"
    CREATE = "create"


@dataclass
class Action:
    """An action to be simulated before execution."""
    action_type: ActionType
    target: str                          # What is being acted upon
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    estimated_duration_ms: float = 0.0

    @property
    def id(self) -> str:
        return hashlib.sha256(f"{self.action_type.value}:{self.target}".encode()).hexdigest()[:10]


# ═══════════════════════════════════════════════════════════
# PHANTOM STATE — Copy-on-Write Virtual State
# ═══════════════════════════════════════════════════════════

class PhantomState:
    """
    Virtual state that mirrors the real system state.
    Uses copy-on-write for efficiency — only copies data when modified.
    """

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._original: Dict[str, Any] = {}
        self._modifications: List[Tuple[str, Any, Any]] = []  # (key, old, new)
        self._deleted_keys: Set[str] = set()
        self._created_keys: Set[str] = set()

    def snapshot_from(self, real_state: Dict[str, Any]) -> 'PhantomState':
        """Create a phantom clone of real state."""
        self._original = dict(real_state)
        self._store = dict(real_state)
        self._modifications.clear()
        self._deleted_keys.clear()
        self._created_keys.clear()
        return self

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._deleted_keys:
            return default
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        old_value = self._store.get(key)
        if key not in self._original:
            self._created_keys.add(key)
        self._modifications.append((key, old_value, value))
        self._store[key] = value

    def delete(self, key: str) -> None:
        if key in self._store:
            self._modifications.append((key, self._store[key], None))
            self._deleted_keys.add(key)
            del self._store[key]

    def has(self, key: str) -> bool:
        return key in self._store and key not in self._deleted_keys

    def get_diff(self) -> Dict[str, Any]:
        """Get all changes made in the phantom state."""
        return {
            "modified": [(k, old, new) for k, old, new in self._modifications],
            "deleted": list(self._deleted_keys),
            "created": list(self._created_keys),
            "total_changes": len(self._modifications),
        }

    def rollback(self) -> None:
        """Discard all phantom changes."""
        self._store = dict(self._original)
        self._modifications.clear()
        self._deleted_keys.clear()
        self._created_keys.clear()


# ═══════════════════════════════════════════════════════════
# EFFECT PROPAGATION — Side-Effect DAG
# ═══════════════════════════════════════════════════════════

@dataclass
class Effect:
    """A predicted side effect of an action."""
    source_action: str
    effect_type: str           # "state_change", "resource_usage", "timing", "dependency"
    target: str                # What is affected
    description: str = ""
    severity: float = 0.0      # 0.0 = harmless, 1.0 = critical
    reversible: bool = True
    cascading: bool = False    # Can this trigger further effects?

    def __hash__(self):
        return hash((self.source_action, self.target, self.effect_type))


class EffectPropagator:
    """
    Models cascading side effects as a Directed Acyclic Graph.
    Propagates effects through dependency chains.
    """

    # Known effect rules: (action_type, target_pattern) → list of effects
    EFFECT_RULES = {
        ActionType.DELETE: [
            Effect("", "state_change", "", "Data permanently removed", 0.9, False, True),
            Effect("", "dependency", "", "Dependent components may break", 0.7, False, True),
        ],
        ActionType.WRITE: [
            Effect("", "state_change", "", "State modified", 0.3, True, False),
            Effect("", "resource_usage", "", "Storage consumed", 0.1, True, False),
        ],
        ActionType.EXECUTE: [
            Effect("", "resource_usage", "", "CPU/memory consumed", 0.2, True, False),
            Effect("", "timing", "", "Execution takes time", 0.1, True, False),
        ],
        ActionType.NETWORK: [
            Effect("", "resource_usage", "", "Network bandwidth consumed", 0.3, True, False),
            Effect("", "dependency", "", "External service dependency", 0.5, False, True),
        ],
        ActionType.MODIFY_STATE: [
            Effect("", "state_change", "", "System state altered", 0.5, True, True),
        ],
    }

    def __init__(self):
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._effect_cache: Dict[str, List[Effect]] = {}

    def register_dependency(self, source: str, depends_on: str) -> None:
        """Register that 'source' depends on 'depends_on'."""
        self._dependency_graph[depends_on].add(source)

    def propagate(self, action: Action, max_depth: int = 5) -> List[Effect]:
        """Predict all effects of an action, including cascading ones."""
        effects = []
        visited = set()
        self._propagate_recursive(action, effects, visited, 0, max_depth)
        return effects

    def _propagate_recursive(self, action: Action, effects: List[Effect],
                             visited: Set[str], depth: int, max_depth: int) -> None:
        if depth >= max_depth or action.id in visited:
            return
        visited.add(action.id)

        # Get direct effects from rules
        templates = self.EFFECT_RULES.get(action.action_type, [])
        for template in templates:
            effect = Effect(
                source_action=action.id,
                effect_type=template.effect_type,
                target=action.target,
                description=f"[Depth {depth}] {template.description} on '{action.target}'",
                severity=template.severity * (0.8 ** depth),  # Decay with depth
                reversible=template.reversible,
                cascading=template.cascading,
            )
            effects.append(effect)

            # Cascade to dependents
            if effect.cascading:
                dependents = self._dependency_graph.get(action.target, set())
                for dep in dependents:
                    cascade_action = Action(
                        action_type=ActionType.MODIFY_STATE,
                        target=dep,
                        description=f"Cascading from {action.target}",
                    )
                    self._propagate_recursive(cascade_action, effects, visited,
                                              depth + 1, max_depth)


# ═══════════════════════════════════════════════════════════
# RISK SCORER — Quantifies Danger
# ═══════════════════════════════════════════════════════════

class RiskScorer:
    """Calculates composite risk score for simulated actions."""

    # Base risk by action type
    BASE_RISK = {
        ActionType.READ: 0.0,
        ActionType.COMPUTE: 0.05,
        ActionType.CREATE: 0.15,
        ActionType.WRITE: 0.3,
        ActionType.MODIFY_STATE: 0.5,
        ActionType.EXECUTE: 0.4,
        ActionType.NETWORK: 0.35,
        ActionType.DELETE: 0.8,
    }

    # Dangerous target patterns
    DANGER_PATTERNS = {
        "system": 0.3, "config": 0.25, "database": 0.3, "password": 0.5,
        "secret": 0.5, "key": 0.4, "root": 0.4, "admin": 0.3,
        "production": 0.5, "delete": 0.3, "drop": 0.5, "truncate": 0.4,
        "credential": 0.5, "token": 0.4, "env": 0.2, "backup": 0.2,
    }

    def score_action(self, action: Action, effects: List[Effect]) -> Tuple[float, RiskLevel]:
        """Calculate risk score for an action and its effects."""
        # Base risk from action type
        base = self.BASE_RISK.get(action.action_type, 0.2)

        # Target danger assessment
        target_risk = 0.0
        target_lower = action.target.lower()
        for pattern, danger in self.DANGER_PATTERNS.items():
            if pattern in target_lower:
                target_risk = max(target_risk, danger)

        # Effect severity aggregation
        effect_risk = 0.0
        if effects:
            effect_risk = max(e.severity for e in effects) * 0.5
            irreversible_count = sum(1 for e in effects if not e.reversible)
            effect_risk += irreversible_count * 0.1

        # Cascade penalty
        cascade_count = sum(1 for e in effects if e.cascading)
        cascade_risk = min(cascade_count * 0.1, 0.3)

        # Composite score
        total = min(1.0, base + target_risk + effect_risk + cascade_risk)

        # Map to risk level
        if total <= 0.1:
            level = RiskLevel.SAFE
        elif total <= 0.3:
            level = RiskLevel.LOW
        elif total <= 0.55:
            level = RiskLevel.MEDIUM
        elif total <= 0.8:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        return total, level

    def score_batch(self, actions: List[Action],
                    effects_map: Dict[str, List[Effect]]) -> Tuple[float, RiskLevel]:
        """Score a batch of actions — compounding risk."""
        if not actions:
            return 0.0, RiskLevel.SAFE

        scores = []
        for action in actions:
            score, _ = self.score_action(action, effects_map.get(action.id, []))
            scores.append(score)

        # Compounding: multiple risky actions are worse than their sum
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)
        compound = min(1.0, max_score * 0.7 + avg_score * 0.3 + len(scores) * 0.02)

        if compound <= 0.1:
            level = RiskLevel.SAFE
        elif compound <= 0.3:
            level = RiskLevel.LOW
        elif compound <= 0.55:
            level = RiskLevel.MEDIUM
        elif compound <= 0.8:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        return compound, level


# ═══════════════════════════════════════════════════════════
# TEMPORAL PROJECTOR — Future State Simulation
# ═══════════════════════════════════════════════════════════

@dataclass
class TimePoint:
    """A projected state at a future time point."""
    time_offset_ms: float
    state_snapshot: Dict[str, Any]
    events: List[str]
    risk_level: RiskLevel = RiskLevel.SAFE


class TemporalProjector:
    """Projects system state evolution across time horizons."""

    def __init__(self):
        self._decay_rules: List[Tuple[str, float, Callable]] = []

    def add_decay_rule(self, target_pattern: str, half_life_ms: float,
                       decay_fn: Optional[Callable] = None) -> None:
        """Add a rule for how state decays over time."""
        self._decay_rules.append((target_pattern, half_life_ms, decay_fn or (lambda v, t: v)))

    def project(self, initial_state: PhantomState, effects: List[Effect],
                time_horizons: List[float] = None) -> List[TimePoint]:
        """Project state at multiple future time points."""
        if time_horizons is None:
            time_horizons = [100, 500, 1000, 5000, 10000]  # milliseconds

        projections = []
        for t in time_horizons:
            snapshot = dict(initial_state._store)
            events = []

            # Apply effects with temporal decay
            for effect in effects:
                decay_factor = math.exp(-t / 5000)  # Natural decay
                if effect.severity * decay_factor > 0.1:
                    events.append(f"[+{t}ms] {effect.description} (severity: {effect.severity * decay_factor:.2f})")

            # Apply custom decay rules
            for pattern, half_life, fn in self._decay_rules:
                for key in list(snapshot.keys()):
                    if pattern in key.lower():
                        decay = math.exp(-t * math.log(2) / half_life)
                        snapshot[key] = fn(snapshot[key], decay)

            risk = RiskLevel.SAFE
            active_effects = sum(1 for e in effects if e.severity * math.exp(-t / 5000) > 0.1)
            if active_effects > 3:
                risk = RiskLevel.HIGH
            elif active_effects > 1:
                risk = RiskLevel.MEDIUM
            elif active_effects > 0:
                risk = RiskLevel.LOW

            projections.append(TimePoint(
                time_offset_ms=t,
                state_snapshot=snapshot,
                events=events,
                risk_level=risk,
            ))

        return projections


# ═══════════════════════════════════════════════════════════
# SIMULATION RESULT
# ═══════════════════════════════════════════════════════════

@dataclass
class SimulationResult:
    """Complete result of a phantom simulation."""
    approved: bool = False
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.SAFE
    effects: List[Effect] = field(default_factory=list)
    state_diff: Dict[str, Any] = field(default_factory=dict)
    temporal_projections: List[TimePoint] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def is_safe(self) -> bool:
        return self.risk_level in (RiskLevel.SAFE, RiskLevel.LOW)

    def summary(self) -> str:
        status = "APPROVED ✓" if self.approved else "REJECTED ✗"
        lines = [
            f"## Phantom Simulation — {status}",
            f"**Risk**: {self.risk_score:.3f} ({self.risk_level.value})",
            f"**Effects predicted**: {len(self.effects)}",
            f"**Duration**: {self.duration_ms:.0f}ms",
        ]
        if self.warnings:
            lines.append("\n### ⚠️ Warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.effects:
            lines.append("\n### Side Effects:")
            for e in self.effects[:5]:
                rev = "✓" if e.reversible else "✗"
                lines.append(f"  - [{rev}] {e.description} (severity: {e.severity:.2f})")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE — Phantom Execution Sandbox
# ═══════════════════════════════════════════════════════════

class PhantomSandbox:
    """
    Virtual pre-execution simulation engine.

    Usage:
        sandbox = PhantomSandbox()

        # Simulate an action
        result = sandbox.simulate(
            Action(ActionType.DELETE, "user_database"),
            real_state={"user_database": "users.db", "backup": True}
        )
        print(result.risk_level)    # RiskLevel.HIGH
        print(result.approved)      # False
        print(result.summary())

        # Simulate a batch
        actions = [
            Action(ActionType.READ, "config.yaml"),
            Action(ActionType.WRITE, "output.log"),
        ]
        result = sandbox.simulate_batch(actions, real_state={})
    """

    def __init__(self, auto_approve_threshold: float = 0.3,
                 auto_reject_threshold: float = 0.8):
        self.propagator = EffectPropagator()
        self.scorer = RiskScorer()
        self.projector = TemporalProjector()
        self.auto_approve_threshold = auto_approve_threshold
        self.auto_reject_threshold = auto_reject_threshold
        self._stats = {
            "simulations": 0, "approved": 0, "rejected": 0,
            "avg_risk": 0.0, "max_risk_seen": 0.0,
        }
        self._simulation_history: List[SimulationResult] = []

    def register_dependency(self, source: str, depends_on: str) -> None:
        """Register a dependency for cascade propagation."""
        self.propagator.register_dependency(source, depends_on)

    def simulate(self, action: Action, real_state: Optional[Dict[str, Any]] = None,
                 time_horizons: Optional[List[float]] = None) -> SimulationResult:
        """Simulate a single action in the phantom environment."""
        start = time.time()
        self._stats["simulations"] += 1

        result = SimulationResult()

        # Create phantom state
        phantom = PhantomState().snapshot_from(real_state or {})

        # Propagate effects
        effects = self.propagator.propagate(action)
        result.effects = effects

        # Apply effects to phantom state
        self._apply_effects(phantom, action, effects)
        result.state_diff = phantom.get_diff()

        # Score risk
        risk_score, risk_level = self.scorer.score_action(action, effects)
        result.risk_score = risk_score
        result.risk_level = risk_level

        # Temporal projection
        result.temporal_projections = self.projector.project(phantom, effects, time_horizons)

        # Generate warnings
        result.warnings = self._generate_warnings(action, effects, risk_level)

        # Auto-approve/reject decision
        if risk_score <= self.auto_approve_threshold:
            result.approved = True
            self._stats["approved"] += 1
        elif risk_score >= self.auto_reject_threshold:
            result.approved = False
            self._stats["rejected"] += 1
        else:
            result.approved = False  # Needs human review
            result.warnings.append("Risk in gray zone — manual review recommended")

        result.duration_ms = (time.time() - start) * 1000

        # Update stats
        self._stats["avg_risk"] = (
            (self._stats["avg_risk"] * (self._stats["simulations"] - 1) + risk_score)
            / self._stats["simulations"]
        )
        self._stats["max_risk_seen"] = max(self._stats["max_risk_seen"], risk_score)

        # Keep history (capped)
        self._simulation_history.append(result)
        if len(self._simulation_history) > 100:
            self._simulation_history = self._simulation_history[-100:]

        return result

    def simulate_batch(self, actions: List[Action],
                       real_state: Optional[Dict[str, Any]] = None) -> SimulationResult:
        """Simulate multiple actions as a batch."""
        start = time.time()
        combined = SimulationResult()
        all_effects: Dict[str, List[Effect]] = {}

        phantom = PhantomState().snapshot_from(real_state or {})

        for action in actions:
            effects = self.propagator.propagate(action)
            all_effects[action.id] = effects
            combined.effects.extend(effects)
            self._apply_effects(phantom, action, effects)

        combined.state_diff = phantom.get_diff()
        combined.risk_score, combined.risk_level = self.scorer.score_batch(actions, all_effects)
        combined.warnings = self._generate_batch_warnings(actions, combined.effects, combined.risk_level)
        combined.approved = combined.risk_score <= self.auto_approve_threshold
        combined.duration_ms = (time.time() - start) * 1000
        return combined

    def _apply_effects(self, phantom: PhantomState, action: Action,
                       effects: List[Effect]) -> None:
        """Apply predicted effects to phantom state."""
        if action.action_type == ActionType.DELETE:
            phantom.delete(action.target)
        elif action.action_type in (ActionType.WRITE, ActionType.MODIFY_STATE):
            phantom.set(action.target, action.params.get("value", f"<modified:{action.target}>"))
        elif action.action_type == ActionType.CREATE:
            phantom.set(action.target, action.params.get("value", f"<created:{action.target}>"))

    def _generate_warnings(self, action: Action, effects: List[Effect],
                           risk_level: RiskLevel) -> List[str]:
        """Generate human-readable warnings."""
        warnings = []
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            warnings.append(f"⚠️ {risk_level.value.upper()} risk action: {action.action_type.value} on '{action.target}'")

        irreversible = [e for e in effects if not e.reversible]
        if irreversible:
            warnings.append(f"🔴 {len(irreversible)} irreversible effect(s) detected")

        cascading = [e for e in effects if e.cascading]
        if cascading:
            warnings.append(f"⚡ {len(cascading)} cascading effect(s) — may trigger chain reactions")

        return warnings

    def _generate_batch_warnings(self, actions: List[Action],
                                 effects: List[Effect], risk: RiskLevel) -> List[str]:
        warnings = []
        delete_count = sum(1 for a in actions if a.action_type == ActionType.DELETE)
        if delete_count > 1:
            warnings.append(f"🔴 Batch contains {delete_count} DELETE operations")

        if len(actions) > 5:
            warnings.append(f"⚠️ Large batch: {len(actions)} actions")

        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            warnings.append(f"⚠️ Overall batch risk: {risk.value}")

        return warnings

    def solve(self, prompt: str) -> SimulationResult:
        """Natural language interface for phantom simulation."""
        prompt_lower = prompt.lower()

        # Parse action type
        action_type = ActionType.COMPUTE
        if any(kw in prompt_lower for kw in ["delete", "remove", "drop"]):
            action_type = ActionType.DELETE
        elif any(kw in prompt_lower for kw in ["write", "save", "store", "update"]):
            action_type = ActionType.WRITE
        elif any(kw in prompt_lower for kw in ["read", "get", "fetch", "load"]):
            action_type = ActionType.READ
        elif any(kw in prompt_lower for kw in ["execute", "run", "launch"]):
            action_type = ActionType.EXECUTE
        elif any(kw in prompt_lower for kw in ["send", "request", "api", "http"]):
            action_type = ActionType.NETWORK

        action = Action(action_type=action_type, target=prompt[:80], description=prompt)
        return self.simulate(action)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "PhantomSandbox",
            "simulations": self._stats["simulations"],
            "approved": self._stats["approved"],
            "rejected": self._stats["rejected"],
            "avg_risk": round(self._stats["avg_risk"], 4),
            "max_risk_seen": round(self._stats["max_risk_seen"], 4),
        }
