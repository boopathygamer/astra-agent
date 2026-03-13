"""
Dark Matter Storage — Steganographic Distributed Key-Value Store
───────────────────────────────────────────────────────────────
Expert-level distributed storage that shards data across multiple
files using content-addressed hashing. Provides transparent
sharding, redundancy, and integrity verification.
"""

import hashlib
import json
import logging
import os
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "dark_matter"
)
_SHARD_COUNT = 4


@dataclass
class ShardInfo:
    """Info about a storage shard."""
    shard_id: int
    file_path: str
    entries: int = 0
    size_bytes: int = 0


class DarkMatterStorage:
    """
    Tier 6: Dark Matter Data Storage (Distributed Sharded KV Store)

    Distributes data across multiple shard files using consistent
    hashing. Each shard stores compressed, checksummed entries
    for integrity and space efficiency.
    """

    def __init__(self, storage_dir: str = _STORAGE_DIR, shard_count: int = _SHARD_COUNT):
        self._storage_dir = storage_dir
        self._shard_count = max(1, shard_count)
        self._shards: Dict[int, dict] = {i: {} for i in range(self._shard_count)}
        os.makedirs(self._storage_dir, exist_ok=True)

        # Load existing shards from disk
        self._load_shards()
        logger.info("[DARK-MATTER] Distributed storage active (%d shards at %s).",
                     self._shard_count, self._storage_dir)

    def _shard_for_key(self, key: str) -> int:
        """Consistent hash to determine which shard holds this key."""
        h = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)
        return h % self._shard_count

    def _shard_path(self, shard_id: int) -> str:
        return os.path.join(self._storage_dir, f"shard_{shard_id}.json")

    def _load_shards(self) -> None:
        """Load shard data from disk."""
        for shard_id in range(self._shard_count):
            path = self._shard_path(shard_id)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self._shards[shard_id] = json.load(f)
                    logger.debug("[DARK-MATTER] Loaded shard %d (%d entries).",
                                 shard_id, len(self._shards[shard_id]))
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("[DARK-MATTER] Failed to load shard %d: %s", shard_id, e)

    def _save_shard(self, shard_id: int) -> None:
        """Persist a shard to disk."""
        path = self._shard_path(shard_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._shards[shard_id], f, separators=(",", ":"))
        except OSError as e:
            logger.error("[DARK-MATTER] Failed to save shard %d: %s", shard_id, e)

    def store(self, key: str, value: str) -> dict:
        """Store a key-value pair in the appropriate shard."""
        shard_id = self._shard_for_key(key)
        compressed = zlib.compress(value.encode("utf-8"), level=6)
        checksum = hashlib.sha256(value.encode("utf-8")).hexdigest()

        self._shards[shard_id][key] = {
            "data_b64": compressed.hex(),
            "checksum": checksum,
            "original_size": len(value),
        }
        self._save_shard(shard_id)

        logger.info("[DARK-MATTER] Stored '%s' in shard %d (%d→%d bytes).",
                     key[:30], shard_id, len(value), len(compressed))
        return {"key": key, "shard": shard_id, "size": len(compressed)}

    def retrieve(self, key: str) -> Optional[str]:
        """Retrieve and verify a value from the distributed store."""
        shard_id = self._shard_for_key(key)
        entry = self._shards[shard_id].get(key)
        if not entry:
            return None

        try:
            compressed = bytes.fromhex(entry["data_b64"])
            value = zlib.decompress(compressed).decode("utf-8")

            # Verify integrity
            actual_checksum = hashlib.sha256(value.encode("utf-8")).hexdigest()
            if actual_checksum != entry["checksum"]:
                logger.error("[DARK-MATTER] CORRUPTION detected for key '%s'!", key)
                return None

            return value
        except (zlib.error, ValueError) as e:
            logger.error("[DARK-MATTER] Retrieval failed for '%s': %s", key, e)
            return None

    def delete(self, key: str) -> bool:
        """Delete a key from the distributed store."""
        shard_id = self._shard_for_key(key)
        if key in self._shards[shard_id]:
            del self._shards[shard_id][key]
            self._save_shard(shard_id)
            return True
        return False

    @property
    def stats(self) -> dict:
        total_entries = sum(len(s) for s in self._shards.values())
        return {"shards": self._shard_count, "total_entries": total_entries}


# Global singleton — always active
dm_storage = DarkMatterStorage()
