"""
Agent Protocol — Standardized Inter-Agent Communication Format
══════════════════════════════════════════════════════════════
Defines the message formats, capabilities, and contracts that
all agents and subsystems use to communicate through the bus.

Protocol:
  AgentMessage → the envelope
  AgentCapability → what an agent can do
  AgentRegistry → tracks all live agents
  CollaborationRequest → ask another agent for help
  CollaborationResponse → the reply
"""

import hashlib
import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"
    ANALYZER = "analyzer"
    EXECUTOR = "executor"
    GUARDIAN = "guardian"
    LEARNER = "learner"
    OBSERVER = "observer"


class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    HEARTBEAT = "heartbeat"
    CAPABILITY_ANNOUNCE = "capability_announce"
    TASK_DELEGATE = "task_delegate"
    TASK_RESULT = "task_result"
    KNOWLEDGE_SHARE = "knowledge_share"
    ALERT = "alert"
    STATUS_UPDATE = "status_update"


class TaskDifficulty(Enum):
    TRIVIAL = "trivial"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass
class AgentCapability:
    """Describes what an agent can do."""
    name: str = ""
    description: str = ""
    domains: List[str] = field(default_factory=list)
    difficulty_range: List[TaskDifficulty] = field(default_factory=lambda: [
        TaskDifficulty.EASY, TaskDifficulty.MEDIUM
    ])
    throughput: float = 1.0  # tasks per minute
    reliability: float = 0.9  # success rate


@dataclass
class AgentIdentity:
    """Unique identity for an agent in the system."""
    agent_id: str = ""
    name: str = ""
    role: AgentRole = AgentRole.SPECIALIST
    capabilities: List[AgentCapability] = field(default_factory=list)
    version: str = "1.0.0"
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    status: str = "online"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.agent_id:
            self.agent_id = hashlib.md5(
                f"{self.name}_{self.role.value}_{time.time()}".encode()
            ).hexdigest()[:10]

    @property
    def is_alive(self) -> bool:
        return (time.time() - self.last_heartbeat) < 120  # 2 min timeout

    def can_handle(self, domain: str, difficulty: TaskDifficulty = TaskDifficulty.MEDIUM) -> bool:
        for cap in self.capabilities:
            if domain in cap.domains and difficulty in cap.difficulty_range:
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "capabilities": [c.name for c in self.capabilities],
            "status": self.status,
            "is_alive": self.is_alive,
        }


@dataclass
class AgentMessage:
    """Standardized message envelope for inter-agent communication."""
    message_type: MessageType = MessageType.REQUEST
    sender_id: str = ""
    recipient_id: str = ""  # Empty = broadcast
    content: Any = None
    domain: str = ""
    difficulty: TaskDifficulty = TaskDifficulty.MEDIUM
    requires_response: bool = False
    timeout_s: float = 60.0
    message_id: str = ""
    timestamp: float = field(default_factory=time.time)
    trace_id: str = ""  # For distributed tracing

    def __post_init__(self):
        if not self.message_id:
            self.message_id = hashlib.md5(
                f"{self.sender_id}_{self.timestamp}".encode()
            ).hexdigest()[:12]
        if not self.trace_id:
            self.trace_id = self.message_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "type": self.message_type.value,
            "sender": self.sender_id,
            "recipient": self.recipient_id,
            "domain": self.domain,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
        }


@dataclass
class CollaborationRequest:
    """Request for collaboration between agents."""
    request_id: str = ""
    requester_id: str = ""
    task_description: str = ""
    domain: str = ""
    difficulty: TaskDifficulty = TaskDifficulty.MEDIUM
    context: Dict[str, Any] = field(default_factory=dict)
    required_capabilities: List[str] = field(default_factory=list)
    max_collaborators: int = 3
    deadline_s: float = 120.0
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"collab_{hashlib.md5(f'{self.requester_id}_{self.timestamp}'.encode()).hexdigest()[:8]}"


@dataclass
class CollaborationResponse:
    """Response to a collaboration request."""
    request_id: str = ""
    responder_id: str = ""
    accepted: bool = False
    result: Any = None
    confidence: float = 0.0
    reasoning: str = ""
    duration_s: float = 0.0
    error: str = ""


class AgentRegistry:
    """
    Tracks all registered agents, their capabilities, and health.
    The 'phone book' of the agent ecosystem.
    """

    MAX_AGENTS = 100

    def __init__(self):
        self._agents: Dict[str, AgentIdentity] = {}
        self._capability_index: Dict[str, Set[str]] = {}  # domain → agent_ids
        self._lock = threading.Lock()
        logger.info("[REGISTRY] Agent Registry initialized")

    def register(self, identity: AgentIdentity) -> str:
        """Register an agent. Returns agent_id."""
        with self._lock:
            if len(self._agents) >= self.MAX_AGENTS:
                # Evict dead agents
                dead = [aid for aid, a in self._agents.items() if not a.is_alive]
                for aid in dead:
                    self._remove_from_index(aid)
                    del self._agents[aid]

            self._agents[identity.agent_id] = identity

            # Index capabilities
            for cap in identity.capabilities:
                for domain in cap.domains:
                    if domain not in self._capability_index:
                        self._capability_index[domain] = set()
                    self._capability_index[domain].add(identity.agent_id)

        logger.info(f"[REGISTRY] Registered: {identity.name} ({identity.agent_id})")
        return identity.agent_id

    def unregister(self, agent_id: str) -> None:
        with self._lock:
            self._remove_from_index(agent_id)
            self._agents.pop(agent_id, None)

    def _remove_from_index(self, agent_id: str) -> None:
        for domain_set in self._capability_index.values():
            domain_set.discard(agent_id)

    def heartbeat(self, agent_id: str) -> None:
        agent = self._agents.get(agent_id)
        if agent:
            agent.last_heartbeat = time.time()
            agent.status = "online"

    def get_agent(self, agent_id: str) -> Optional[AgentIdentity]:
        return self._agents.get(agent_id)

    def find_agents(self, domain: str = None, role: AgentRole = None,
                    capability: str = None, alive_only: bool = True) -> List[AgentIdentity]:
        """Find agents matching criteria."""
        results = list(self._agents.values())

        if alive_only:
            results = [a for a in results if a.is_alive]
        if domain:
            domain_ids = self._capability_index.get(domain, set())
            results = [a for a in results if a.agent_id in domain_ids]
        if role:
            results = [a for a in results if a.role == role]
        if capability:
            results = [
                a for a in results
                if any(c.name == capability for c in a.capabilities)
            ]
        return results

    def find_best_agent(self, domain: str, difficulty: TaskDifficulty = TaskDifficulty.MEDIUM) -> Optional[AgentIdentity]:
        """Find the best agent for a specific task."""
        candidates = self.find_agents(domain=domain)
        capable = [a for a in candidates if a.can_handle(domain, difficulty)]

        if not capable:
            return None

        # Rank by reliability of the matching capability
        def score(agent: AgentIdentity) -> float:
            for cap in agent.capabilities:
                if domain in cap.domains:
                    return cap.reliability * cap.throughput
            return 0.0

        return max(capable, key=score)

    def list_all(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self._agents.values()]

    def get_status(self) -> Dict[str, Any]:
        alive = sum(1 for a in self._agents.values() if a.is_alive)
        return {
            "total_agents": len(self._agents),
            "alive_agents": alive,
            "domains_covered": list(self._capability_index.keys()),
            "roles": list(set(a.role.value for a in self._agents.values())),
        }


# ── Singleton ──

_registry_instance: Optional[AgentRegistry] = None
_registry_lock = threading.Lock()


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry singleton."""
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = AgentRegistry()
    return _registry_instance
