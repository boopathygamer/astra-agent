"""
Panpsychic Fabric — Cryptographically Secure Entropy Harvester
──────────────────────────────────────────────────────────────
VULNERABILITY FIX: Replaced `random` module with `os.urandom`
and `secrets` for cryptographically secure entropy sourcing.

Harvests hardware-backed entropy for non-deterministic decision
making in the ASI's probabilistic reasoning branches.
"""

import hashlib
import logging
import os
import secrets
import struct
import time
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EntropyHarvest:
    """Result of an entropy harvesting operation."""
    raw_entropy_hex: str
    derived_float: float  # 0.0 to 1.0
    source: str
    timestamp: float


class PanpsychicFabric:
    """
    Tier 7: Panpsychic Network Fabric

    SECURITY FIX: All randomness now sourced from os.urandom()
    (hardware-backed CSPRNG). No predictable PRNG is used for
    any decision-making within the ASI system.
    """

    def __init__(self):
        self._harvests: int = 0
        self._total_entropy_bytes: int = 0
        logger.info("[PANPSYCHIC] Secure entropy harvester initialized (source=os.urandom).")

    def harvest_entropy(self, num_bytes: int = 32) -> EntropyHarvest:
        """
        Harvest cryptographically secure random bytes from the OS.
        Uses hardware-backed entropy sources (RDRAND on modern CPUs).
        """
        num_bytes = max(1, min(num_bytes, 1024))
        raw = os.urandom(num_bytes)
        self._harvests += 1
        self._total_entropy_bytes += num_bytes

        # Derive a float in [0, 1) from the first 8 bytes
        if len(raw) >= 8:
            int_val = struct.unpack(">Q", raw[:8])[0]
            derived_float = int_val / (2**64)
        else:
            derived_float = raw[0] / 256.0

        harvest = EntropyHarvest(
            raw_entropy_hex=raw.hex()[:64],
            derived_float=derived_float,
            source="os.urandom/CSPRNG",
            timestamp=time.time(),
        )
        logger.debug("[PANPSYCHIC] Harvested %d bytes of entropy (float=%.6f).", num_bytes, derived_float)
        return harvest

    def secure_choice(self, options: list):
        """Cryptographically secure selection from a list of options."""
        if not options:
            logger.warning("[PANPSYCHIC] Empty options list — cannot choose.")
            return None
        return secrets.choice(options)

    def secure_float(self) -> float:
        """Returns a cryptographically secure float in [0.0, 1.0)."""
        return self.harvest_entropy(8).derived_float

    def secure_int(self, upper_bound: int) -> int:
        """Returns a cryptographically secure integer in [0, upper_bound)."""
        return secrets.randbelow(max(1, upper_bound))

    def generate_nonce(self, length: int = 16) -> str:
        """Generate a URL-safe nonce string."""
        return secrets.token_urlsafe(max(1, length))

    @property
    def stats(self) -> dict:
        return {
            "total_harvests": self._harvests,
            "total_entropy_bytes": self._total_entropy_bytes,
            "source": "os.urandom/CSPRNG",
        }


# Global singleton — always active
panpsychic_network = PanpsychicFabric()
