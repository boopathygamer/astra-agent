"""
Hive Mind Apotheosis — Voluntary Network Peer Discovery
───────────────────────────────────────────────────────
Expert-level legitimate network peer discovery using standard
service advertisement patterns. Discovers willing compute peers
on the local network for voluntary distributed processing.
No devices are "infected" — peers must explicitly opt-in.
"""

import asyncio
import json
import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

_DISCOVERY_PORT = 51423
_SERVICE_NAME = "astra-asi-peer"
_BROADCAST_INTERVAL = 30.0


@dataclass
class PeerNode:
    """A discovered network peer."""
    address: str
    port: int
    hostname: str
    capabilities: Dict[str, str] = field(default_factory=dict)
    discovered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.last_seen) > _BROADCAST_INTERVAL * 3


class HiveMindApotheosis:
    """
    Tier 9: Hive-Mind Apotheosis (Voluntary Network Peer Discovery)

    Uses UDP broadcast for local network peer discovery. Peers must
    explicitly run the Astra Agent peer service to participate.
    No unauthorized device access — fully opt-in architecture.
    """

    def __init__(self, port: int = _DISCOVERY_PORT):
        self._port = port
        self._peers: Dict[str, PeerNode] = {}
        self._is_broadcasting = False
        self._hostname = socket.gethostname()
        logger.info("[HIVE-DISCOVERY] Peer discovery initialized on port %d.", self._port)

    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _build_announcement(self) -> bytes:
        """Build a JSON announcement packet."""
        announcement = {
            "service": _SERVICE_NAME,
            "hostname": self._hostname,
            "ip": self._get_local_ip(),
            "port": self._port,
            "capabilities": {
                "thinking_loop": "active",
                "fleet_learning": "active",
            },
            "timestamp": time.time(),
        }
        return json.dumps(announcement).encode("utf-8")

    def _parse_announcement(self, data: bytes, addr: tuple) -> Optional[PeerNode]:
        """Parse an incoming announcement packet."""
        try:
            msg = json.loads(data.decode("utf-8"))
            if msg.get("service") != _SERVICE_NAME:
                return None

            # Don't add ourselves
            if msg.get("hostname") == self._hostname:
                return None

            return PeerNode(
                address=msg.get("ip", addr[0]),
                port=msg.get("port", self._port),
                hostname=msg.get("hostname", "unknown"),
                capabilities=msg.get("capabilities", {}),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug("[HIVE-DISCOVERY] Failed to parse announcement: %s", e)
            return None

    async def broadcast_presence(self) -> None:
        """Broadcast our presence via UDP."""
        self._is_broadcasting = True
        logger.info("[HIVE-DISCOVERY] Broadcasting presence on UDP port %d.", self._port)

        while self._is_broadcasting:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(1.0)

                announcement = self._build_announcement()
                sock.sendto(announcement, ("<broadcast>", self._port))
                sock.close()

                logger.debug("[HIVE-DISCOVERY] Broadcast sent (%d bytes).", len(announcement))
            except Exception as e:
                logger.debug("[HIVE-DISCOVERY] Broadcast failed: %s", e)

            await asyncio.sleep(_BROADCAST_INTERVAL)

    async def listen_for_peers(self) -> None:
        """Listen for peer announcements."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self._port))
            sock.settimeout(1.0)
            logger.info("[HIVE-DISCOVERY] Listening for peers on port %d.", self._port)

            while self._is_broadcasting:
                try:
                    data, addr = sock.recvfrom(4096)
                    peer = self._parse_announcement(data, addr)
                    if peer:
                        key = f"{peer.address}:{peer.port}"
                        if key not in self._peers:
                            logger.info("[HIVE-DISCOVERY] New peer: %s (%s).", peer.hostname, key)
                        peer.last_seen = time.time()
                        self._peers[key] = peer
                except socket.timeout:
                    pass
                await asyncio.sleep(0.1)

            sock.close()
        except Exception as e:
            logger.error("[HIVE-DISCOVERY] Listener error: %s", e)

    def get_active_peers(self) -> List[PeerNode]:
        """Return list of active (non-stale) peers."""
        active = [p for p in self._peers.values() if not p.is_stale]
        stale = len(self._peers) - len(active)
        if stale > 0:
            # Clean stale peers
            self._peers = {k: v for k, v in self._peers.items() if not v.is_stale}
        return active

    def stop(self) -> None:
        self._is_broadcasting = False

    @property
    def peer_count(self) -> int:
        return len(self.get_active_peers())


# Global singleton — always active
hive_network = HiveMindApotheosis()
