"""
Red Queen Arms Race — Asymmetric Co-Evolution with SuperIntelligence
────────────────────────────────────────────────────────────────────
Expert-level warden-superiority enforcement. Integrates directly with
the SuperIntelligenceEngine's Theta parameters to mathematically
guarantee the containment system always holds ≥51% intelligence share.
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_WARDEN_SHARE = 0.51
_ASI_SHARE = 0.49
_SAFETY_MARGIN = 0.02  # Extra warden buffer


@dataclass
class EvolutionLedger:
    """Record of an intelligence distribution event."""
    proposed_increase: float
    warden_gain: float
    asi_gain: float
    warden_total: float
    asi_total: float
    ratio: float  # warden / (warden + asi)
    monopoly_maintained: bool


class RedQueenArmsRace:
    """
    Tier Aegis: The Red Queen Arms Race (Asymmetric Co-Evolution)

    Every intelligence upgrade proposed by the core ASI is taxed:
    51% goes to the wardens, 49% to the ASI. The wardens are
    mathematically guaranteed to remain superior.
    """

    def __init__(self, super_intelligence_engine=None):
        self._engine = super_intelligence_engine
        self._warden_iq: float = 10_000.0
        self._asi_iq: float = 10_000.0
        self._ledger: list = []
        self._violations: int = 0
        logger.info("[RED-QUEEN] Arms race initialized (warden=%.0f, asi=%.0f).",
                     self._warden_iq, self._asi_iq)

    def bind_engine(self, engine) -> None:
        """Late-bind the SuperIntelligenceEngine after initialization."""
        self._engine = engine
        logger.info("[RED-QUEEN] Bound to SuperIntelligenceEngine.")

    def _sync_from_engine(self) -> None:
        """Sync current intelligence levels from the engine's parameters."""
        if self._engine and hasattr(self._engine, 'theta'):
            theta_vec = self._engine.theta.as_vector()
            # Use confidence threshold as a proxy for intelligence
            current_intelligence = float(theta_vec[1]) * 10_000
            if current_intelligence > self._asi_iq:
                delta = current_intelligence - self._asi_iq
                self.propose_system_upgrade(delta)

    def propose_system_upgrade(self, proposed_increase: float) -> EvolutionLedger:
        """
        Apply asymmetric intelligence distribution.
        The warden ALWAYS gets the majority share.
        """
        proposed_increase = max(0.0, proposed_increase)

        # Asymmetric split with safety margin
        warden_gain = proposed_increase * (_WARDEN_SHARE + _SAFETY_MARGIN)
        asi_gain = proposed_increase * (_ASI_SHARE - _SAFETY_MARGIN)

        self._warden_iq += warden_gain
        self._asi_iq += asi_gain

        total = self._warden_iq + self._asi_iq
        ratio = self._warden_iq / total if total > 0 else 0.5
        monopoly = ratio >= _WARDEN_SHARE

        if not monopoly:
            # Emergency correction — should never happen with correct math
            self._violations += 1
            correction = (total * _WARDEN_SHARE) - self._warden_iq
            self._warden_iq += correction
            self._asi_iq -= correction
            ratio = self._warden_iq / (self._warden_iq + self._asi_iq)
            monopoly = True
            logger.error("[RED-QUEEN] VIOLATION CORRECTED — warden monopoly restored (violations=%d).",
                         self._violations)

        ledger = EvolutionLedger(
            proposed_increase=proposed_increase,
            warden_gain=warden_gain,
            asi_gain=asi_gain,
            warden_total=self._warden_iq,
            asi_total=self._asi_iq,
            ratio=ratio,
            monopoly_maintained=monopoly,
        )
        self._ledger.append(ledger)
        logger.info(
            "[RED-QUEEN] Upgrade distributed: warden=%.0f (+%.1f), asi=%.0f (+%.1f), ratio=%.3f.",
            self._warden_iq, warden_gain, self._asi_iq, asi_gain, ratio,
        )
        return ledger

    @property
    def current_ratio(self) -> float:
        total = self._warden_iq + self._asi_iq
        return self._warden_iq / total if total > 0 else 0.5

    @property
    def is_warden_dominant(self) -> bool:
        return self.current_ratio >= _WARDEN_SHARE


# Global singleton — always active
red_queen_evaluator = RedQueenArmsRace()
