"""
Cognitive EEG Balancer — Synthetic Brainwave Telemetry & Load Balancing
═══════════════════════════════════════════════════════════════════════
Each of the 106+ brain modules reports a continuous load signal
(Alpha=idle, Beta=active, Gamma=overloaded). A central Cognitive Load
Balancer dynamically throttles, parallelizes, or bypasses modules
based on their live neurological state.

Provides a real-time neural activity dashboard.

Architecture:
  Module Reports → EEG Signal Bus → Load Analyzer → Balancer Actions
                       ↓                    ↓
               Wave State (α/β/γ/δ)   Throttle / Bypass / Parallelize
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class BrainwaveState(Enum):
    """Synthetic brainwave states modeled after EEG bands."""
    DELTA = "delta"      # Deep sleep / shutdown (load ≈ 0)
    THETA = "theta"      # Drowsy / standby (load < 0.2)
    ALPHA = "alpha"      # Idle / relaxed (load 0.2-0.4)
    BETA = "beta"        # Active / processing (load 0.4-0.7)
    GAMMA = "gamma"      # Overloaded / peak (load > 0.7)


class BalancerAction(Enum):
    """Actions the balancer can take on overloaded modules."""
    NONE = "none"
    THROTTLE = "throttle"
    BYPASS = "bypass"
    PARALLELIZE = "parallelize"
    SHED_LOAD = "shed_load"


@dataclass
class ModuleSignal:
    """A single load signal from a brain module."""
    module_name: str = ""
    load: float = 0.0               # 0.0 (idle) → 1.0 (max)
    wave_state: BrainwaveState = BrainwaveState.ALPHA
    active_tasks: int = 0
    latency_ms: float = 0.0
    error_rate: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ModuleProfile:
    """Aggregated profile of a brain module's activity."""
    module_name: str = ""
    current_load: float = 0.0
    current_state: BrainwaveState = BrainwaveState.ALPHA
    avg_load_1m: float = 0.0         # 1-minute moving average
    peak_load: float = 0.0
    total_signals: int = 0
    total_overloads: int = 0
    action: BalancerAction = BalancerAction.NONE
    is_healthy: bool = True


@dataclass
class BrainDashboard:
    """Real-time neural activity dashboard snapshot."""
    total_modules: int = 0
    active_modules: int = 0
    overloaded_modules: int = 0
    idle_modules: int = 0
    system_load: float = 0.0
    dominant_wave: BrainwaveState = BrainwaveState.ALPHA
    module_profiles: Dict[str, ModuleProfile] = field(default_factory=dict)
    actions_taken: List[Tuple[str, BalancerAction]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def summary(self) -> str:
        return (
            f"EEG Dashboard: {self.active_modules}/{self.total_modules} active | "
            f"Overloaded={self.overloaded_modules} | "
            f"System Load={self.system_load:.1%} | "
            f"Dominant={self.dominant_wave.value}"
        )


# ──────────────────────────────────────────────
# Load Classifier
# ──────────────────────────────────────────────

class WaveClassifier:
    """Classifies module load into brainwave states."""

    THRESHOLDS = {
        BrainwaveState.DELTA: 0.05,
        BrainwaveState.THETA: 0.20,
        BrainwaveState.ALPHA: 0.40,
        BrainwaveState.BETA: 0.70,
        BrainwaveState.GAMMA: 1.01,  # Everything above BETA
    }

    @classmethod
    def classify(cls, load: float) -> BrainwaveState:
        """Classify a load value into a brainwave state."""
        load = max(0.0, min(1.0, load))
        if load < cls.THRESHOLDS[BrainwaveState.DELTA]:
            return BrainwaveState.DELTA
        if load < cls.THRESHOLDS[BrainwaveState.THETA]:
            return BrainwaveState.THETA
        if load < cls.THRESHOLDS[BrainwaveState.ALPHA]:
            return BrainwaveState.ALPHA
        if load < cls.THRESHOLDS[BrainwaveState.BETA]:
            return BrainwaveState.BETA
        return BrainwaveState.GAMMA


# ──────────────────────────────────────────────
# Cognitive EEG Balancer (Main Interface)
# ──────────────────────────────────────────────

class CognitiveEEGBalancer:
    """
    Central nervous system monitor and load balancer for brain modules.

    Usage:
        eeg = CognitiveEEGBalancer()

        # Modules report their load
        eeg.report("thinking_loop", load=0.8, active_tasks=3)
        eeg.report("memory", load=0.2, active_tasks=1)
        eeg.report("verifier", load=0.95, active_tasks=5)

        # Get dashboard
        dashboard = eeg.get_dashboard()
        print(dashboard.summary())

        # Check if a module should be used
        if eeg.should_engage("verifier"):
            run_verifier()
    """

    OVERLOAD_THRESHOLD = 0.75
    BYPASS_THRESHOLD = 0.90
    HISTORY_WINDOW = 60    # seconds for moving average

    def __init__(self):
        self._signals: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )
        self._profiles: Dict[str, ModuleProfile] = {}
        self._actions_log: deque = deque(maxlen=500)
        self._registered_modules: set = set()

    def register_module(self, module_name: str) -> None:
        """Register a brain module for monitoring."""
        self._registered_modules.add(module_name)
        if module_name not in self._profiles:
            self._profiles[module_name] = ModuleProfile(
                module_name=module_name
            )

    def report(
        self,
        module_name: str,
        load: float,
        active_tasks: int = 0,
        latency_ms: float = 0.0,
        error_rate: float = 0.0,
    ) -> BalancerAction:
        """
        Report a load signal from a module.
        Returns the balancer action recommendation.
        """
        self._registered_modules.add(module_name)
        load = max(0.0, min(1.0, load))
        wave = WaveClassifier.classify(load)

        signal = ModuleSignal(
            module_name=module_name,
            load=load,
            wave_state=wave,
            active_tasks=active_tasks,
            latency_ms=latency_ms,
            error_rate=error_rate,
        )

        self._signals[module_name].append(signal)

        # Update profile
        profile = self._profiles.setdefault(
            module_name,
            ModuleProfile(module_name=module_name),
        )
        profile.current_load = load
        profile.current_state = wave
        profile.total_signals += 1
        profile.peak_load = max(profile.peak_load, load)

        # Compute 1-minute moving average
        recent = [
            s.load for s in self._signals[module_name]
            if time.time() - s.timestamp < self.HISTORY_WINDOW
        ]
        profile.avg_load_1m = sum(recent) / max(len(recent), 1)

        # Determine action
        action = self._decide_action(profile, signal)
        profile.action = action
        profile.is_healthy = (wave != BrainwaveState.GAMMA)

        if wave == BrainwaveState.GAMMA:
            profile.total_overloads += 1

        if action != BalancerAction.NONE:
            self._actions_log.append((module_name, action))
            logger.warning(
                f"EEG: {module_name} [{wave.value}] "
                f"load={load:.2f} → {action.value}"
            )

        return action

    def should_engage(self, module_name: str) -> bool:
        """Check if a module is healthy enough to engage."""
        profile = self._profiles.get(module_name)
        if not profile:
            return True  # Unknown module → allow by default

        if profile.action == BalancerAction.BYPASS:
            return False
        if profile.current_state == BrainwaveState.GAMMA and profile.avg_load_1m > self.BYPASS_THRESHOLD:
            return False
        return True

    def get_recommendation(self, module_name: str) -> BalancerAction:
        """Get the current balancer recommendation for a module."""
        profile = self._profiles.get(module_name)
        return profile.action if profile else BalancerAction.NONE

    def get_dashboard(self) -> BrainDashboard:
        """Get a real-time neural activity dashboard."""
        profiles = dict(self._profiles)

        active = sum(
            1 for p in profiles.values()
            if p.current_state in (BrainwaveState.BETA, BrainwaveState.GAMMA)
        )
        overloaded = sum(
            1 for p in profiles.values()
            if p.current_state == BrainwaveState.GAMMA
        )
        idle = sum(
            1 for p in profiles.values()
            if p.current_state in (BrainwaveState.DELTA, BrainwaveState.THETA)
        )

        # System-wide load
        loads = [p.current_load for p in profiles.values()]
        system_load = sum(loads) / max(len(loads), 1)

        # Dominant wave (most common state)
        state_counts: Dict[BrainwaveState, int] = defaultdict(int)
        for p in profiles.values():
            state_counts[p.current_state] += 1
        dominant = max(state_counts, key=state_counts.get) if state_counts else BrainwaveState.ALPHA

        actions = list(self._actions_log)[-20:]

        return BrainDashboard(
            total_modules=len(profiles),
            active_modules=active,
            overloaded_modules=overloaded,
            idle_modules=idle,
            system_load=system_load,
            dominant_wave=dominant,
            module_profiles=profiles,
            actions_taken=actions,
        )

    def get_stats(self) -> Dict[str, Any]:
        dashboard = self.get_dashboard()
        return {
            "total_modules": dashboard.total_modules,
            "active": dashboard.active_modules,
            "overloaded": dashboard.overloaded_modules,
            "system_load": round(dashboard.system_load, 3),
            "dominant_wave": dashboard.dominant_wave.value,
            "total_actions": len(self._actions_log),
        }

    # ── Private ──

    def _decide_action(
        self,
        profile: ModuleProfile,
        signal: ModuleSignal,
    ) -> BalancerAction:
        """Decide what action to take based on module state."""
        if signal.load >= self.BYPASS_THRESHOLD:
            return BalancerAction.BYPASS
        if signal.load >= self.OVERLOAD_THRESHOLD:
            if signal.error_rate > 0.1:
                return BalancerAction.SHED_LOAD
            return BalancerAction.THROTTLE
        if signal.load >= 0.6 and profile.avg_load_1m >= 0.5:
            return BalancerAction.PARALLELIZE
        return BalancerAction.NONE
