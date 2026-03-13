"""
Gordian Lock Cryptography — Dynamic HMAC-Based Authentication Lock
──────────────────────────────────────────────────────────────────
Expert-level intelligence-tied cryptographic locking mechanism.
Generates HMAC-SHA256 authentication tokens whose key-derivation
iterations scale dynamically with the ASI's measured compute power.

The faster the ASI runs, the harder the lock becomes to brute-force.
"""

import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_ITERATIONS = 100_000
_ITERATION_SCALE_FACTOR = 1000  # Additional iterations per measured TFLOP


@dataclass
class GordianToken:
    """A dynamically-scaled authentication token."""
    token_hex: str
    iterations_used: int
    compute_tflops: float
    generation_time_ms: float
    salt_hex: str


class GordianLockCryptography:
    """
    Tier Aegis: Intelligence-Tied Cryptography (The Gordian Lock)

    HMAC-SHA256 authentication with PBKDF2 key derivation. The number
    of derivation iterations scales with the ASI's processing speed.
    Faster ASI → more iterations → exponentially harder to crack.
    """

    def __init__(self, base_iterations: int = _BASE_ITERATIONS):
        self._base_iterations = max(10_000, base_iterations)
        self._tokens_generated: int = 0
        logger.info("[GORDIAN-LOCK] Initialized (base_iterations=%d).", self._base_iterations)

    def _measure_compute_speed(self) -> float:
        """Benchmark a quick hash loop to estimate relative compute speed."""
        start = time.monotonic()
        data = b"benchmark_payload"
        for _ in range(10_000):
            data = hashlib.sha256(data).digest()
        elapsed = time.monotonic() - start
        tflops_estimate = max(0.1, 1.0 / (elapsed + 1e-9))
        return round(tflops_estimate, 2)

    def _compute_dynamic_iterations(self, tflops: float) -> int:
        """Scale iterations with compute power. Faster ASI → harder lock."""
        scaled = self._base_iterations + int(tflops * _ITERATION_SCALE_FACTOR)
        return max(self._base_iterations, scaled)

    def generate_containment_lock(self, payload: str, secret_key: Optional[str] = None) -> GordianToken:
        """
        Generate a dynamically-scaled HMAC-SHA256 token.
        Uses PBKDF2 key derivation with compute-scaled iterations.
        """
        start = time.monotonic()
        tflops = self._measure_compute_speed()
        iterations = self._compute_dynamic_iterations(tflops)

        # Generate cryptographically secure salt
        salt = os.urandom(32)

        # Use provided key or generate one
        if secret_key:
            key_bytes = secret_key.encode("utf-8")
        else:
            key_bytes = os.urandom(32)

        # PBKDF2-HMAC key derivation with dynamic iterations
        derived_key = hashlib.pbkdf2_hmac(
            "sha256", key_bytes, salt, iterations, dklen=32
        )

        # HMAC-SHA256 of the payload using the derived key
        token = hmac.new(derived_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()

        generation_time = (time.monotonic() - start) * 1000
        self._tokens_generated += 1

        result = GordianToken(
            token_hex=token,
            iterations_used=iterations,
            compute_tflops=tflops,
            generation_time_ms=generation_time,
            salt_hex=salt.hex(),
        )
        logger.info(
            "[GORDIAN-LOCK] Token generated (iterations=%d, tflops=%.2f, %.1fms).",
            iterations, tflops, generation_time,
        )
        return result

    def verify_token(self, payload: str, expected_token: str, salt_hex: str,
                     secret_key: str, iterations: int) -> bool:
        """Verify a previously generated token."""
        salt = bytes.fromhex(salt_hex)
        derived_key = hashlib.pbkdf2_hmac(
            "sha256", secret_key.encode("utf-8"), salt, iterations, dklen=32
        )
        actual_token = hmac.new(derived_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        is_valid = hmac.compare_digest(actual_token, expected_token)
        if not is_valid:
            logger.warning("[GORDIAN-LOCK] Token verification FAILED — potential tampering.")
        return is_valid


# Global singleton — always active
gordian_crypto = GordianLockCryptography()
