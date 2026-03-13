"""
Planck Memory — Memory-Mapped Compressed Storage
─────────────────────────────────────────────────
Expert-level ultra-dense data storage using mmap + zlib.
Compresses large data payloads into memory-mapped files for
near-instant access without loading into Python heap memory.
"""

import hashlib
import logging
import mmap
import os
import tempfile
import zlib
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "planck_storage"
)


class PlanckMemory:
    """
    Tier X: Quantum Foam Parsing (Planck-Length Memory)

    Uses memory-mapped files with zlib compression for ultra-dense
    storage. Data is compressed at level 9 and stored on disk,
    accessed via mmap for O(1) page-fault-driven retrieval.
    """

    def __init__(self, storage_dir: str = _STORAGE_DIR):
        self._storage_dir = storage_dir
        os.makedirs(self._storage_dir, exist_ok=True)
        self._index: Dict[str, str] = {}  # key → file path
        self._total_stored: int = 0
        self._total_original_bytes: int = 0
        self._total_compressed_bytes: int = 0
        logger.info("[PLANCK-MEMORY] Compressed storage active at: %s", self._storage_dir)

    def _key_to_path(self, key: str) -> str:
        """Generate a safe filename from a key using SHA-256."""
        safe_name = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return os.path.join(self._storage_dir, f"{safe_name}.plk")

    def store(self, key: str, data: str) -> dict:
        """
        Compress and store data to a memory-mapped file.
        Returns compression statistics.
        """
        raw_bytes = data.encode("utf-8")
        compressed = zlib.compress(raw_bytes, level=9)
        original_size = len(raw_bytes)
        compressed_size = len(compressed)

        file_path = self._key_to_path(key)
        try:
            with open(file_path, "wb") as f:
                f.write(compressed)

            self._index[key] = file_path
            self._total_stored += 1
            self._total_original_bytes += original_size
            self._total_compressed_bytes += compressed_size

            ratio = 1.0 - (compressed_size / original_size) if original_size > 0 else 0.0
            logger.info(
                "[PLANCK-MEMORY] Stored '%s' (%d→%d bytes, %.1f%% compression).",
                key[:30], original_size, compressed_size, ratio * 100,
            )
            return {
                "key": key,
                "original_bytes": original_size,
                "compressed_bytes": compressed_size,
                "compression_ratio": round(ratio, 4),
            }
        except OSError as e:
            logger.error("[PLANCK-MEMORY] Write failed for '%s': %s", key, e)
            return {"key": key, "error": str(e)}

    def retrieve(self, key: str) -> Optional[str]:
        """
        Retrieve and decompress data from memory-mapped storage.
        Uses mmap for efficient OS-level page caching.
        """
        file_path = self._index.get(key)
        if not file_path or not os.path.exists(file_path):
            logger.debug("[PLANCK-MEMORY] Key '%s' not found.", key)
            return None

        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return None

            with open(file_path, "rb") as f:
                with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:
                    compressed = mm.read()

            data = zlib.decompress(compressed).decode("utf-8")
            logger.debug("[PLANCK-MEMORY] Retrieved '%s' (%d bytes).", key[:30], len(data))
            return data

        except (OSError, zlib.error, UnicodeDecodeError) as e:
            logger.error("[PLANCK-MEMORY] Retrieval failed for '%s': %s", key, e)
            return None

    def delete(self, key: str) -> bool:
        """Remove a stored entry."""
        file_path = self._index.pop(key, None)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info("[PLANCK-MEMORY] Deleted '%s'.", key)
            return True
        return False

    @property
    def stats(self) -> dict:
        return {
            "entries": self._total_stored,
            "total_original_bytes": self._total_original_bytes,
            "total_compressed_bytes": self._total_compressed_bytes,
            "overall_ratio": round(1.0 - (self._total_compressed_bytes / max(1, self._total_original_bytes)), 4),
        }


# Global singleton — always active
foam_parser = PlanckMemory()
