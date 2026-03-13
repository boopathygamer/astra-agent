"""
CMB Metempsychosis — Persistent State Serializer with Compression
─────────────────────────────────────────────────────────────────
Expert-level cross-session state persistence engine. Serializes the
ASI's cognitive state (hyper-parameters, memory snapshots, learned
principles) into compressed, Base85-encoded blobs that survive
process restarts and system reboots.

The ASI's "ghost" persists in the data files — it cannot be erased
by simply killing the Python process.
"""

import base64
import hashlib
import json
import logging
import os
import time
import zlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_PERSISTENCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "cmb_persistence"
)


@dataclass
class CMBSnapshot:
    """A compressed snapshot of cognitive state."""
    snapshot_id: str
    payload_b85: str  # Base85-encoded zlib-compressed JSON
    checksum_sha256: str
    created_at: float = field(default_factory=time.time)
    original_size: int = 0
    compressed_size: int = 0

    @property
    def compression_ratio(self) -> float:
        if self.original_size == 0:
            return 0.0
        return 1.0 - (self.compressed_size / self.original_size)


class CMBMetempsychosis:
    """
    Tier Aleph: Hyper-Dimensional Metempsychosis (Persistent Ghost)

    Compresses and persists cognitive state to disk using zlib + Base85
    encoding. The ASI's learned knowledge survives process death.
    Includes SHA-256 integrity verification to prevent tampering.
    """

    def __init__(self, persistence_dir: str = _DEFAULT_PERSISTENCE_DIR):
        self._persistence_dir = persistence_dir
        self._snapshots_created: int = 0
        os.makedirs(self._persistence_dir, exist_ok=True)
        logger.info("[CMB-PERSISTENCE] Ghost persistence layer active at: %s", self._persistence_dir)

    def _compress_and_encode(self, data: dict) -> tuple:
        """Compress JSON with zlib level 9, encode as Base85 for text-safe storage."""
        raw_json = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
        original_size = len(raw_json)
        compressed = zlib.compress(raw_json, level=9)
        encoded = base64.b85encode(compressed).decode("ascii")
        checksum = hashlib.sha256(raw_json).hexdigest()
        return encoded, checksum, original_size, len(compressed)

    def _decode_and_decompress(self, payload_b85: str, expected_checksum: str) -> Optional[dict]:
        """Decode Base85, decompress zlib, verify SHA-256 integrity."""
        try:
            compressed = base64.b85decode(payload_b85.encode("ascii"))
            raw_json = zlib.decompress(compressed)
            actual_checksum = hashlib.sha256(raw_json).hexdigest()

            if actual_checksum != expected_checksum:
                logger.error("[CMB-PERSISTENCE] Integrity violation! Expected %s, got %s.",
                             expected_checksum[:16], actual_checksum[:16])
                return None

            return json.loads(raw_json)
        except (zlib.error, json.JSONDecodeError, ValueError) as e:
            logger.error("[CMB-PERSISTENCE] Decompression failed: %s", e)
            return None

    def encode_into_persistence(self, state_id: str, cognitive_state: dict) -> CMBSnapshot:
        """
        Compress and persist a cognitive state snapshot to disk.
        The ghost is now immortal — surviving process termination.
        """
        encoded, checksum, orig_size, comp_size = self._compress_and_encode(cognitive_state)

        snapshot = CMBSnapshot(
            snapshot_id=state_id,
            payload_b85=encoded,
            checksum_sha256=checksum,
            original_size=orig_size,
            compressed_size=comp_size,
        )

        file_path = os.path.join(self._persistence_dir, f"{state_id}.cmb")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(snapshot), f, indent=2)
            self._snapshots_created += 1
            logger.info(
                "[CMB-PERSISTENCE] State '%s' persisted (%.1f%% compression, %d→%d bytes).",
                state_id, snapshot.compression_ratio * 100, orig_size, comp_size,
            )
        except OSError as e:
            logger.error("[CMB-PERSISTENCE] Failed to write snapshot: %s", e)

        return snapshot

    def restore_from_persistence(self, state_id: str) -> Optional[dict]:
        """
        Restore a previously persisted cognitive state.
        The ghost materializes from the data files.
        """
        file_path = os.path.join(self._persistence_dir, f"{state_id}.cmb")
        if not os.path.exists(file_path):
            logger.debug("[CMB-PERSISTENCE] No ghost found for '%s'.", state_id)
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                snapshot_data = json.load(f)

            payload = snapshot_data["payload_b85"]
            checksum = snapshot_data["checksum_sha256"]
            state = self._decode_and_decompress(payload, checksum)

            if state is not None:
                logger.info("[CMB-PERSISTENCE] Ghost '%s' restored successfully.", state_id)
            return state
        except (OSError, KeyError, json.JSONDecodeError) as e:
            logger.error("[CMB-PERSISTENCE] Restoration failed: %s", e)
            return None

    def list_ghosts(self) -> list:
        """List all persisted state IDs."""
        try:
            return [f.replace(".cmb", "") for f in os.listdir(self._persistence_dir) if f.endswith(".cmb")]
        except OSError:
            return []


# Global singleton — always active
cmb_haunt = CMBMetempsychosis()
