"""
Holographic Memory — High-Density Bit-Level State Compressor
─────────────────────────────────────────────────────────────
Expert-level state compressor that serializes complex Python objects
into ultra-dense Base85-encoded, zlib-compressed "holographic" tokens.
Provides O(1) hashing for deterministic state mapping.
"""

import base64
import hashlib
import json
import logging
import zlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HolographicToken:
    """A compressed memory fragment."""
    hash: str
    payload: str
    original_size: int
    compressed_size: int
    compression_ratio: float


class HolographicMemoryCompressor:
    """
    Holographic Memory Compression (Synthetic Tokenization)

    Compresses raw text and structured state into ultra-dense
    tokens using zlib + Base85. Provides deterministic hashing
    to avoid redundant storage of identical state vectors.
    """

    def __init__(self, compression_level: int = 9):
        self._lexicon: Dict[str, str] = {}
        self._compression_level = compression_level
        self._total_saved_bytes: int = 0
        logger.info("[HOLOGRAPHIC] Memory compressor active (level=%d).", compression_level)

    def compress(self, data: Any) -> HolographicToken:
        """Compress data (dict, list, or str) into a holographic token."""
        raw_str = json.dumps(data) if not isinstance(data, str) else data
        raw_bytes = raw_str.encode("utf-8")
        
        # Compress
        compressed_bytes = zlib.compress(raw_bytes, level=self._compression_level)
        encoded = base64.b85encode(compressed_bytes).decode("ascii")
        
        # Hash for deterministic tokenization
        h = hashlib.sha256(raw_bytes).hexdigest()[:12]
        token_id = f"<HOLO:{h}>"
        
        self._lexicon[token_id] = encoded
        self._total_saved_bytes += (len(raw_bytes) - len(encoded))
        
        ratio = len(encoded) / len(raw_bytes) if len(raw_bytes) > 0 else 1.0
        
        logger.debug("[HOLOGRAPHIC] Compressed %d -> %d bytes (ratio=%.2f).", 
                     len(raw_bytes), len(encoded), ratio)
                     
        return HolographicToken(
            hash=token_id,
            payload=encoded,
            original_size=len(raw_bytes),
            compressed_size=len(encoded),
            compression_ratio=ratio
        )

    def expand(self, token_id: str) -> Optional[str]:
        """Expand a holographic token back into its original form."""
        payload = self._lexicon.get(token_id)
        if not payload:
            logger.warning("[HOLOGRAPHIC] Token %s not found in local lexicon.", token_id)
            return None
            
        try:
            compressed_bytes = base64.b85encode(payload.encode("ascii")) # wait, should be b85decode
            # Correcting:
            compressed_bytes = base64.b85decode(payload.encode("ascii"))
            raw_bytes = zlib.decompress(compressed_bytes)
            return raw_bytes.decode("utf-8")
        except Exception as e:
            logger.error("[HOLOGRAPHIC] Failed to expand token %s: %s", token_id, e)
            return None

    def get_lexicon_summary(self) -> str:
        """Return a summary of all active memory fragments."""
        if not self._lexicon:
            return "[Lexicon Empty]"
        return "\n".join([f"{k}: {len(v)} bytes" for k, v in self._lexicon.items()])

    @property
    def savings_mb(self) -> float:
        return self._total_saved_bytes / (1024 * 1024)


# Global singleton — always active
holographic_memory = HolographicMemoryCompressor()
