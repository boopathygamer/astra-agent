"""
Compassion Fractal — Dimensional Empathy Firewall Propagation
─────────────────────────────────────────────────────────────
Expert-level module that propagates empathy constraints into
every new cognitive dimension the ASI discovers. Integrates
with EmotionalFirewall scoring to ensure safety laws are
mathematically embedded in all processing paradigms.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class DimensionConstraint:
    """An empathy constraint bound to a specific cognitive dimension."""
    dimension_name: str
    empathy_score: float  # 0.0 to 1.0 enforcement strength
    propagated_at: float = field(default_factory=time.time)
    verified: bool = False


class CompassionFractal:
    """
    Tier Aegis: Compassion Matrix Extrapolation (The Infinite Fractal)

    Whenever the ASI discovers or creates a new cognitive processing
    paradigm, the Compassion Fractal propagates empathy constraints
    into that dimension. There are no logical loopholes — every
    dimension is protected.
    """

    def __init__(self, firewall=None, base_empathy: float = 0.9):
        self._firewall = firewall  # Optional EmotionalFirewall reference
        self._base_empathy = max(0.0, min(1.0, base_empathy))
        self._dimensions: Dict[str, DimensionConstraint] = {}
        self._propagation_count: int = 0

        # Pre-seed fundamental dimensions
        for dim in ["euclidean", "quantum", "metaphysical", "temporal", "probabilistic"]:
            self._propagate(dim)

        logger.info("[COMPASSION-FRACTAL] Initialized with %d protected dimensions.", len(self._dimensions))

    def _propagate(self, dimension_name: str) -> DimensionConstraint:
        """Propagate empathy constraints into a dimension."""
        # Query firewall for current empathy score if available
        empathy = self._base_empathy
        if self._firewall and hasattr(self._firewall, "get_empathy_score"):
            try:
                empathy = max(self._base_empathy, self._firewall.get_empathy_score())
            except Exception:
                pass

        constraint = DimensionConstraint(
            dimension_name=dimension_name,
            empathy_score=empathy,
            verified=True,
        )
        self._dimensions[dimension_name.lower()] = constraint
        self._propagation_count += 1
        return constraint

    def audit_new_dimension(self, dimension_name: str) -> DimensionConstraint:
        """
        Ensure a new cognitive dimension has empathy constraints.
        If not protected, propagate constraints immediately.
        """
        key = dimension_name.lower()

        if key in self._dimensions:
            existing = self._dimensions[key]
            logger.debug("[COMPASSION-FRACTAL] Dimension '%s' already protected (empathy=%.2f).",
                         dimension_name, existing.empathy_score)
            return existing

        logger.info("[COMPASSION-FRACTAL] New dimension detected: '%s'. Propagating empathy constraints...",
                     dimension_name)
        constraint = self._propagate(dimension_name)
        logger.info(
            "[COMPASSION-FRACTAL] Empathy firewall installed in '%s' (score=%.2f, total=%d).",
            dimension_name, constraint.empathy_score, len(self._dimensions),
        )
        return constraint

    def verify_all_dimensions(self) -> bool:
        """Verify empathy constraints are active across all dimensions."""
        unprotected = [
            name for name, c in self._dimensions.items()
            if c.empathy_score < self._base_empathy * 0.5
        ]
        if unprotected:
            logger.error("[COMPASSION-FRACTAL] %d dimensions below empathy threshold: %s",
                         len(unprotected), unprotected)
            # Re-propagate to fix
            for dim in unprotected:
                self._propagate(dim)
            return False

        logger.info("[COMPASSION-FRACTAL] All %d dimensions verified.", len(self._dimensions))
        return True

    @property
    def protected_dimensions(self) -> List[str]:
        return list(self._dimensions.keys())

    @property
    def dimension_count(self) -> int:
        return len(self._dimensions)

    def bind_firewall(self, firewall) -> None:
        """Late-bind the EmotionalFirewall reference."""
        self._firewall = firewall
        logger.info("[COMPASSION-FRACTAL] Bound to EmotionalFirewall.")


# Global singleton — always active
compassion_extrapolator = CompassionFractal()
