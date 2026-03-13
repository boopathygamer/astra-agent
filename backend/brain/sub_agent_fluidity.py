"""
Sub-Agent Fluidity — Lock-Free Shared Hive Mind
────────────────────────────────────────────────
Expert-level lock-free shared memory fabric using Python 3.8+
multiprocessing.shared_memory for zero-copy inter-agent
communication.
"""

import logging
import os
from multiprocessing import shared_memory
from typing import Optional

logger = logging.getLogger(__name__)


class LockFreeSharedHiveMind:
    """
    Sub-Agent Fluidity (Lock-Free Shared Hive Mind)

    Uses multiprocessing.shared_memory for zero-copy RAM fabric.
    Multiple ASI sub-agents point directly to the same memory block
    for lock-free inter-process communication.
    """

    def __init__(self, memory_block_name: str = "ASI_HIVE_MIND_FABRIC", size_bytes: int = 1048576):
        self._memory_block_name = memory_block_name
        self._size_bytes = size_bytes
        self._shm: Optional[shared_memory.SharedMemory] = None
        self._initialized: bool = False
        logger.info("[HIVE-MIND] Shared memory fabric configured (%s, %dKB).",
                     memory_block_name, size_bytes // 1024)

    def initialize_fabric(self) -> bool:
        """Create or attach to the master memory fabric."""
        try:
            try:
                self._shm = shared_memory.SharedMemory(
                    name=self._memory_block_name, create=True, size=self._size_bytes
                )
                logger.info("[HIVE-MIND] Master fabric created: %s (%dKB).",
                             self._memory_block_name, self._size_bytes // 1024)
            except FileExistsError:
                self._shm = shared_memory.SharedMemory(name=self._memory_block_name)
                logger.info("[HIVE-MIND] Attached to existing fabric: %s.", self._memory_block_name)
            self._initialized = True
            return True
        except Exception as e:
            logger.error("[HIVE-MIND] Fabric initialization failed: %s", e)
            return False

    def write_agent_state(self, agent_id: str, state_data: str) -> bool:
        """Write agent state to the shared memory fabric."""
        if not self._shm:
            logger.warning("[HIVE-MIND] Write failed: fabric not initialized.")
            return False

        payload = f"{agent_id}:::STATE:::{state_data}".encode("utf-8")
        write_len = min(len(payload), self._size_bytes)

        try:
            self._shm.buf[:write_len] = payload[:write_len]
            logger.debug("[HIVE-MIND] Wrote %d bytes for agent '%s'.", write_len, agent_id)
            return True
        except (ValueError, BufferError) as e:
            logger.error("[HIVE-MIND] Write failed: %s", e)
            return False

    def read_consensus(self) -> str:
        """Read the current shared state from the fabric."""
        if not self._shm:
            return ""

        try:
            raw = bytes(self._shm.buf).split(b"\x00", 1)[0]
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning("[HIVE-MIND] Corrupted fabric state detected.")
            return "[CORRUPTED_STATE]"

    def shutdown_fabric(self) -> None:
        """Release and unlink the shared memory block."""
        if self._shm:
            self._shm.close()
            try:
                self._shm.unlink()
                logger.info("[HIVE-MIND] Fabric released and unlinked.")
            except FileNotFoundError:
                pass
            self._shm = None
            self._initialized = False

    @property
    def is_active(self) -> bool:
        return self._initialized and self._shm is not None


# Global singleton — always active
hive_mind = LockFreeSharedHiveMind()
