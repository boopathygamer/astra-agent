"""
JARVIS Core — Central Intelligence Nexus
═════════════════════════════════════════
The master brain that unifies all Astra Agent subsystems into
one coherent intelligence layer. This is the "consciousness" that
ties environment awareness, memory, prediction, reasoning, security,
and knowledge into a single fused cognitive state.

Architecture:
  ┌──────────────────────────────────────────────────────────────┐
  │                      JARVIS CORE                             │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
  │  │Awareness │ │Prediction│ │ Guardian │ │  Knowledge   │   │
  │  │  Fusion  │ │  Engine  │ │  Shield  │ │    Nexus     │   │
  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘   │
  │       └────────┬───┴────────┬───┘               │           │
  │          ┌─────┴─────┐  ┌──┴──────────┐  ┌─────┴─────┐    │
  │          │ Initiative│  │   Mission   │  │   Hyper   │    │
  │          │  Engine   │  │ Controller  │  │  Reasoner │    │
  │          └───────────┘  └─────────────┘  └───────────┘    │
  └──────────────────────────────────────────────────────────────┘

Capabilities:
  1. Cognitive Fusion      — Merges all subsystem outputs into unified state
  2. Initiative System     — Proactive suggestions and actions
  3. Authority Levels      — Tiered permission (observe → suggest → auto)
  4. System Fingerprint    — Persistent identity and user preference memory
  5. Heartbeat Monitor     — Health monitoring and auto-recovery
  6. Session Continuity    — Remembers context across conversations
"""

import hashlib
import json
import logging
import os
import platform
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Authority Levels — Tiered Permission System
# ══════════════════════════════════════════════════════════════

class AuthorityLevel(IntEnum):
    """How much autonomy the agent has."""
    OBSERVE = 0       # Only observe, never act
    SUGGEST = 1       # Suggest actions, user must approve
    ASSIST = 2        # Execute safe actions, ask for risky ones
    AUTONOMOUS = 3    # Full autonomous execution within safety bounds
    OVERRIDE = 4      # Emergency override — bypass normal checks


class SubsystemStatus(Enum):
    """Health status of a subsystem."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    OFFLINE = "offline"
    INITIALIZING = "initializing"


class InitiativeType(Enum):
    """Types of proactive actions."""
    OBSERVATION = "observation"      # "I noticed..."
    SUGGESTION = "suggestion"        # "You might want to..."
    WARNING = "warning"              # "⚠️ Potential issue..."
    AUTOMATION = "automation"        # "I went ahead and..."
    BRIEFING = "briefing"            # "Here's your daily briefing..."
    OPTIMIZATION = "optimization"    # "I can optimize..."


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

@dataclass
class Initiative:
    """A proactive action or suggestion from the agent."""
    id: str = ""
    initiative_type: InitiativeType = InitiativeType.OBSERVATION
    title: str = ""
    description: str = ""
    confidence: float = 0.0
    priority: int = 5          # 1 (highest) to 10 (lowest)
    source_subsystem: str = ""
    action_required: bool = False
    auto_executable: bool = False
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    acknowledged: bool = False
    executed: bool = False

    def __post_init__(self):
        if not self.id:
            self.id = f"init_{secrets.token_hex(4)}"


@dataclass
class SubsystemHealth:
    """Health report from a subsystem."""
    name: str = ""
    status: SubsystemStatus = SubsystemStatus.OFFLINE
    last_heartbeat: float = 0.0
    error_count: int = 0
    last_error: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    uptime_seconds: float = 0.0


@dataclass
class CognitiveState:
    """Unified awareness state — the agent's complete understanding of reality."""
    timestamp: float = field(default_factory=time.time)

    # Environment awareness
    system_health: str = "unknown"
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_status: str = "unknown"
    active_threats: int = 0

    # User context
    user_activity: str = "unknown"
    current_task_type: str = ""
    session_duration_min: float = 0.0
    interaction_count: int = 0

    # Agent state
    authority_level: AuthorityLevel = AuthorityLevel.SUGGEST
    cognitive_load: float = 0.0
    subsystems_online: int = 0
    subsystems_total: int = 7
    pending_initiatives: int = 0

    # Predictions
    predicted_next_action: str = ""
    prediction_confidence: float = 0.0

    # Knowledge
    knowledge_nodes: int = 0
    recent_learnings: int = 0

    def health_score(self) -> float:
        """Overall system health 0.0 to 1.0."""
        scores = [
            1.0 - min(self.cpu_usage / 100, 1.0) * 0.3,
            1.0 - min(self.memory_usage / 100, 1.0) * 0.3,
            1.0 - min(self.disk_usage / 100, 1.0) * 0.2,
            1.0 if self.network_status == "online" else 0.5,
            1.0 if self.active_threats == 0 else 0.3,
            self.subsystems_online / max(self.subsystems_total, 1),
        ]
        return sum(scores) / len(scores)

    def to_briefing(self) -> str:
        """Generate a human-readable briefing of current state."""
        health = self.health_score()
        health_emoji = "🟢" if health > 0.8 else "🟡" if health > 0.5 else "🔴"

        lines = [
            f"═══ JARVIS Status Briefing ═══",
            f"  {health_emoji} Overall Health: {health:.0%}",
            f"  ⚡ CPU: {self.cpu_usage:.1f}% | RAM: {self.memory_usage:.1f}% | Disk: {self.disk_usage:.1f}%",
            f"  🌐 Network: {self.network_status}",
            f"  🛡️ Threats: {self.active_threats}",
            f"  🧠 Subsystems: {self.subsystems_online}/{self.subsystems_total} online",
            f"  🎯 Authority: {self.authority_level.name}",
            f"  📊 Cognitive Load: {self.cognitive_load:.1%}",
        ]

        if self.predicted_next_action:
            lines.append(
                f"  🔮 Predicted Need: {self.predicted_next_action} "
                f"({self.prediction_confidence:.0%} confident)"
            )

        if self.pending_initiatives > 0:
            lines.append(f"  💡 Pending Suggestions: {self.pending_initiatives}")

        return "\n".join(lines)


@dataclass
class UserFingerprint:
    """Persistent user identity and preferences."""
    user_id: str = ""
    preferred_name: str = ""
    communication_style: str = "professional"  # casual, professional, technical, friendly
    expertise_level: str = "intermediate"       # beginner, intermediate, expert
    timezone: str = ""
    preferred_authority: AuthorityLevel = AuthorityLevel.SUGGEST
    topics_of_interest: List[str] = field(default_factory=list)
    interaction_patterns: Dict[str, int] = field(default_factory=dict)
    session_count: int = 0
    total_interactions: int = 0
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.user_id:
            machine = platform.node()
            self.user_id = hashlib.sha256(
                f"{machine}_{os.getenv('USERNAME', 'default')}".encode()
            ).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════
# JARVIS Core — The Central Intelligence
# ══════════════════════════════════════════════════════════════

class JarvisCore:
    """
    Central Intelligence Nexus — The unified brain of Astra Agent.

    Orchestrates all subsystems into a single coherent AI:
      - Fuses environment + memory + predictions into awareness
      - Generates proactive initiatives (like JARVIS anticipating Tony)
      - Monitors subsystem health with auto-recovery
      - Maintains persistent user identity and preferences
      - Provides authority-tiered autonomous execution
    """

    FINGERPRINT_FILE = "jarvis_fingerprint.json"
    MAX_INITIATIVES = 100
    HEARTBEAT_INTERVAL = 30.0  # seconds

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        authority_level: AuthorityLevel = AuthorityLevel.SUGGEST,
        data_dir: Optional[str] = None,
    ):
        self.generate_fn = generate_fn
        self.authority = authority_level
        self.data_dir = Path(data_dir) if data_dir else Path("data/jarvis")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Core state
        self._cognitive_state = CognitiveState(authority_level=authority_level)
        self._fingerprint = self._load_fingerprint()
        self._initiatives: Deque[Initiative] = deque(maxlen=self.MAX_INITIATIVES)
        self._subsystem_health: Dict[str, SubsystemHealth] = {}
        self._session_start = time.time()
        self._interaction_count = 0

        # Subsystem references (injected during integration)
        self._subsystems: Dict[str, Any] = {}

        # Heartbeat monitoring
        self._heartbeat_lock = threading.Lock()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._running = False

        # Event log
        self._event_log: Deque[Dict] = deque(maxlen=500)

        # Boot sequence
        self._boot_time = time.time()
        self._register_core_subsystem()

        logger.info(
            f"[JARVIS] Core initialized — authority={authority_level.name}, "
            f"user={self._fingerprint.user_id[:8]}..."
        )

    # ── Subsystem Registration ──

    def register_subsystem(self, name: str, instance: Any) -> None:
        """Register a subsystem for health monitoring and fusion."""
        self._subsystems[name] = instance
        self._subsystem_health[name] = SubsystemHealth(
            name=name,
            status=SubsystemStatus.HEALTHY,
            last_heartbeat=time.time(),
        )
        self._cognitive_state.subsystems_total = len(self._subsystem_health)
        self._cognitive_state.subsystems_online = sum(
            1 for h in self._subsystem_health.values()
            if h.status in (SubsystemStatus.HEALTHY, SubsystemStatus.DEGRADED)
        )
        logger.info(f"[JARVIS] Registered subsystem: {name}")

    def _register_core_subsystem(self):
        """Register self as a subsystem."""
        self._subsystem_health["jarvis_core"] = SubsystemHealth(
            name="jarvis_core",
            status=SubsystemStatus.HEALTHY,
            last_heartbeat=time.time(),
        )

    # ── Cognitive Fusion ──

    def fuse_awareness(
        self,
        environment_data: Optional[Dict] = None,
        memory_context: Optional[str] = None,
        predictions: Optional[Dict] = None,
        security_status: Optional[Dict] = None,
        knowledge_stats: Optional[Dict] = None,
    ) -> CognitiveState:
        """
        Merge all subsystem outputs into a unified cognitive state.

        This is the core JARVIS operation — taking disparate data
        streams and synthesizing them into coherent situational awareness.
        """
        state = self._cognitive_state
        state.timestamp = time.time()

        # Fuse environment data
        if environment_data:
            vitals = environment_data.get("system_vitals", {})
            state.cpu_usage = vitals.get("cpu_percent", 0.0)
            state.memory_usage = vitals.get("ram_percent", 0.0)
            state.disk_usage = vitals.get("disk_percent", 0.0)

            network = environment_data.get("network", {})
            state.network_status = (
                "online" if network.get("internet_reachable", False) else "offline"
            )

            # Determine system health from vitals
            if state.cpu_usage > 90 or state.memory_usage > 95:
                state.system_health = "critical"
            elif state.cpu_usage > 70 or state.memory_usage > 80:
                state.system_health = "stressed"
            else:
                state.system_health = "healthy"

        # Fuse security data
        if security_status:
            state.active_threats = security_status.get("active_threats", 0)

        # Fuse knowledge stats
        if knowledge_stats:
            state.knowledge_nodes = knowledge_stats.get("total_nodes", 0)
            state.recent_learnings = knowledge_stats.get("recent_learnings", 0)

        # Fuse predictions
        if predictions:
            state.predicted_next_action = predictions.get("next_action", "")
            state.prediction_confidence = predictions.get("confidence", 0.0)

        # Session metrics
        state.session_duration_min = (time.time() - self._session_start) / 60
        state.interaction_count = self._interaction_count

        # Subsystem status
        state.subsystems_online = sum(
            1 for h in self._subsystem_health.values()
            if h.status in (SubsystemStatus.HEALTHY, SubsystemStatus.DEGRADED)
        )
        state.subsystems_total = len(self._subsystem_health)

        # Generate initiatives based on fused state
        self._generate_context_initiatives(state)

        self._cognitive_state = state
        return state

    def get_awareness(self) -> CognitiveState:
        """Get current cognitive state without re-fusing."""
        return self._cognitive_state

    # ── Initiative System ──

    def _generate_context_initiatives(self, state: CognitiveState) -> None:
        """Generate proactive suggestions based on current awareness."""

        # High CPU warning
        if state.cpu_usage > 85:
            self._add_initiative(
                initiative_type=InitiativeType.WARNING,
                title="High CPU Usage Detected",
                description=(
                    f"CPU usage is at {state.cpu_usage:.1f}%. "
                    "Consider closing resource-heavy applications."
                ),
                confidence=0.95,
                priority=2,
                source="awareness_fusion",
            )

        # High memory warning
        if state.memory_usage > 90:
            self._add_initiative(
                initiative_type=InitiativeType.WARNING,
                title="Memory Pressure Critical",
                description=(
                    f"RAM usage is at {state.memory_usage:.1f}%. "
                    "System performance may degrade. "
                    "I can identify memory-heavy processes if needed."
                ),
                confidence=0.95,
                priority=1,
                source="awareness_fusion",
            )

        # Disk space warning
        if state.disk_usage > 90:
            self._add_initiative(
                initiative_type=InitiativeType.SUGGESTION,
                title="Disk Space Running Low",
                description=(
                    f"Disk usage is at {state.disk_usage:.1f}%. "
                    "I can scan for large temporary files to clean up."
                ),
                confidence=0.9,
                priority=3,
                source="awareness_fusion",
                auto_executable=(self.authority >= AuthorityLevel.ASSIST),
            )

        # Network loss
        if state.network_status == "offline":
            self._add_initiative(
                initiative_type=InitiativeType.WARNING,
                title="Network Connection Lost",
                description=(
                    "Internet connectivity is unavailable. "
                    "Operations requiring API calls will fail."
                ),
                confidence=1.0,
                priority=1,
                source="awareness_fusion",
            )

        # Security threats
        if state.active_threats > 0:
            self._add_initiative(
                initiative_type=InitiativeType.WARNING,
                title=f"{state.active_threats} Active Security Threats",
                description=(
                    "Security Guardian has detected active threats. "
                    "Immediate review recommended."
                ),
                confidence=0.95,
                priority=1,
                source="guardian",
                action_required=True,
            )

        state.pending_initiatives = sum(
            1 for i in self._initiatives if not i.acknowledged
        )

    def _add_initiative(
        self,
        initiative_type: InitiativeType,
        title: str,
        description: str,
        confidence: float = 0.5,
        priority: int = 5,
        source: str = "",
        action_required: bool = False,
        auto_executable: bool = False,
        data: Dict = None,
    ) -> Initiative:
        """Add a proactive initiative, avoiding duplicates within a time window."""
        # Dedup: skip if same title was added within last 60 seconds
        recent_titles = {
            i.title for i in self._initiatives
            if time.time() - i.created_at < 60
        }
        if title in recent_titles:
            return Initiative()

        initiative = Initiative(
            initiative_type=initiative_type,
            title=title,
            description=description,
            confidence=confidence,
            priority=priority,
            source_subsystem=source,
            action_required=action_required,
            auto_executable=auto_executable,
            data=data or {},
        )
        self._initiatives.append(initiative)

        self._log_event("initiative_created", {
            "id": initiative.id,
            "type": initiative_type.value,
            "title": title,
            "priority": priority,
        })

        logger.info(
            f"[JARVIS] Initiative: [{initiative_type.value.upper()}] {title} "
            f"(pri={priority}, conf={confidence:.0%})"
        )
        return initiative

    def get_pending_initiatives(self) -> List[Initiative]:
        """Get all unacknowledged initiatives, sorted by priority."""
        pending = [i for i in self._initiatives if not i.acknowledged]
        pending.sort(key=lambda i: i.priority)
        return pending

    def acknowledge_initiative(self, initiative_id: str) -> bool:
        """Mark an initiative as acknowledged by the user."""
        for initiative in self._initiatives:
            if initiative.id == initiative_id:
                initiative.acknowledged = True
                return True
        return False

    # ── Authority Management ──

    def set_authority(self, level: AuthorityLevel) -> None:
        """Set the agent's authority level."""
        old = self.authority
        self.authority = level
        self._cognitive_state.authority_level = level
        self._fingerprint.preferred_authority = level
        self._save_fingerprint()
        logger.info(f"[JARVIS] Authority changed: {old.name} → {level.name}")

    def can_auto_execute(self, risk_level: str = "low") -> bool:
        """Check if the agent can auto-execute an action."""
        risk_thresholds = {
            "low": AuthorityLevel.ASSIST,
            "medium": AuthorityLevel.AUTONOMOUS,
            "high": AuthorityLevel.OVERRIDE,
        }
        required = risk_thresholds.get(risk_level, AuthorityLevel.OVERRIDE)
        return self.authority >= required

    # ── User Fingerprint ──

    def _load_fingerprint(self) -> UserFingerprint:
        """Load persistent user fingerprint from disk."""
        path = self.data_dir / self.FINGERPRINT_FILE
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                fp = UserFingerprint(
                    user_id=data.get("user_id", ""),
                    preferred_name=data.get("preferred_name", ""),
                    communication_style=data.get("communication_style", "professional"),
                    expertise_level=data.get("expertise_level", "intermediate"),
                    timezone=data.get("timezone", ""),
                    topics_of_interest=data.get("topics_of_interest", []),
                    interaction_patterns=data.get("interaction_patterns", {}),
                    session_count=data.get("session_count", 0),
                    total_interactions=data.get("total_interactions", 0),
                    first_seen=data.get("first_seen", time.time()),
                    last_seen=data.get("last_seen", time.time()),
                )
                try:
                    fp.preferred_authority = AuthorityLevel(
                        data.get("preferred_authority", 1)
                    )
                except (ValueError, KeyError):
                    fp.preferred_authority = AuthorityLevel.SUGGEST
                fp.session_count += 1
                fp.last_seen = time.time()
                logger.info(f"[JARVIS] Loaded user fingerprint: {fp.user_id[:8]}...")
                return fp
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(f"[JARVIS] Corrupted fingerprint, creating new: {exc}")

        fp = UserFingerprint()
        fp.timezone = time.strftime("%Z")
        return fp

    def _save_fingerprint(self) -> None:
        """Persist user fingerprint to disk."""
        path = self.data_dir / self.FINGERPRINT_FILE
        data = {
            "user_id": self._fingerprint.user_id,
            "preferred_name": self._fingerprint.preferred_name,
            "communication_style": self._fingerprint.communication_style,
            "expertise_level": self._fingerprint.expertise_level,
            "timezone": self._fingerprint.timezone,
            "preferred_authority": self._fingerprint.preferred_authority.value,
            "topics_of_interest": self._fingerprint.topics_of_interest,
            "interaction_patterns": self._fingerprint.interaction_patterns,
            "session_count": self._fingerprint.session_count,
            "total_interactions": self._fingerprint.total_interactions,
            "first_seen": self._fingerprint.first_seen,
            "last_seen": self._fingerprint.last_seen,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def update_interaction(self, intent_type: str = "general") -> None:
        """Track an interaction for pattern learning."""
        self._interaction_count += 1
        self._fingerprint.total_interactions += 1
        self._fingerprint.last_seen = time.time()
        patterns = self._fingerprint.interaction_patterns
        patterns[intent_type] = patterns.get(intent_type, 0) + 1

        # Periodically save (every 10 interactions)
        if self._interaction_count % 10 == 0:
            self._save_fingerprint()

    def get_fingerprint(self) -> UserFingerprint:
        """Get the current user fingerprint."""
        return self._fingerprint

    # ── Heartbeat Monitor ──

    def start_heartbeat(self) -> None:
        """Start the background heartbeat monitor."""
        if self._running:
            return
        self._running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="jarvis-heartbeat",
        )
        self._heartbeat_thread.start()
        logger.info("[JARVIS] Heartbeat monitor started")

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat monitor."""
        self._running = False

    def _heartbeat_loop(self) -> None:
        """Background loop checking subsystem health."""
        while self._running:
            with self._heartbeat_lock:
                now = time.time()
                for name, health in self._subsystem_health.items():
                    # Check if subsystem has gone silent
                    silence = now - health.last_heartbeat
                    if silence > self.HEARTBEAT_INTERVAL * 3:
                        if health.status != SubsystemStatus.FAILED:
                            health.status = SubsystemStatus.FAILED
                            logger.warning(
                                f"[JARVIS] Subsystem FAILED: {name} "
                                f"(no heartbeat for {silence:.0f}s)"
                            )
                            self._add_initiative(
                                InitiativeType.WARNING,
                                f"Subsystem Failure: {name}",
                                f"The {name} subsystem has not responded "
                                f"for {silence:.0f} seconds.",
                                confidence=1.0,
                                priority=1,
                                source="heartbeat_monitor",
                            )
                    elif silence > self.HEARTBEAT_INTERVAL * 2:
                        health.status = SubsystemStatus.DEGRADED

                    health.uptime_seconds = now - self._boot_time

            time.sleep(self.HEARTBEAT_INTERVAL)

    def report_heartbeat(self, subsystem_name: str, metrics: Dict = None) -> None:
        """Called by subsystems to report they're alive."""
        with self._heartbeat_lock:
            if subsystem_name in self._subsystem_health:
                health = self._subsystem_health[subsystem_name]
                health.last_heartbeat = time.time()
                health.status = SubsystemStatus.HEALTHY
                if metrics:
                    health.metrics.update(metrics)

    # ── Event Logging ──

    def _log_event(self, event_type: str, data: Dict = None) -> None:
        """Log an event with timestamp."""
        self._event_log.append({
            "timestamp": time.time(),
            "type": event_type,
            "data": data or {},
        })

    # ── Status & Reporting ──

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive JARVIS status."""
        return {
            "online": True,
            "authority": self.authority.name,
            "health_score": self._cognitive_state.health_score(),
            "uptime_seconds": time.time() - self._boot_time,
            "session_duration_min": (time.time() - self._session_start) / 60,
            "interactions": self._interaction_count,
            "subsystems": {
                name: {
                    "status": health.status.value,
                    "uptime": health.uptime_seconds,
                    "errors": health.error_count,
                }
                for name, health in self._subsystem_health.items()
            },
            "pending_initiatives": len(self.get_pending_initiatives()),
            "cognitive_state": {
                "cpu": self._cognitive_state.cpu_usage,
                "memory": self._cognitive_state.memory_usage,
                "disk": self._cognitive_state.disk_usage,
                "network": self._cognitive_state.network_status,
                "threats": self._cognitive_state.active_threats,
                "predicted_action": self._cognitive_state.predicted_next_action,
            },
            "user": {
                "id": self._fingerprint.user_id[:8],
                "sessions": self._fingerprint.session_count,
                "total_interactions": self._fingerprint.total_interactions,
                "style": self._fingerprint.communication_style,
            },
        }

    def generate_briefing(self) -> str:
        """Generate a comprehensive status briefing."""
        state = self._cognitive_state
        briefing = state.to_briefing()

        # Add pending initiatives
        pending = self.get_pending_initiatives()
        if pending:
            briefing += f"\n\n  ── Pending Actions ({len(pending)}) ──"
            for init in pending[:5]:
                emoji = {
                    InitiativeType.WARNING: "⚠️",
                    InitiativeType.SUGGESTION: "💡",
                    InitiativeType.OPTIMIZATION: "⚙️",
                    InitiativeType.BRIEFING: "📋",
                    InitiativeType.OBSERVATION: "👁️",
                    InitiativeType.AUTOMATION: "🤖",
                }.get(init.initiative_type, "•")
                briefing += f"\n  {emoji} {init.title}"

        return briefing

    def shutdown(self) -> None:
        """Graceful shutdown — persist state and stop monitors."""
        logger.info("[JARVIS] Shutting down gracefully...")
        self._running = False
        self._save_fingerprint()
        self._log_event("shutdown", {
            "uptime": time.time() - self._boot_time,
            "interactions": self._interaction_count,
        })
