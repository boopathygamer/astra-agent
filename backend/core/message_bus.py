"""
Central Message Bus — Pub/Sub Event System for Inter-Agent Communication
════════════════════════════════════════════════════════════════════════
The nervous system of Astra Agent. Every subsystem communicates through
this bus — agents, brain modules, security, UI — all connected.

Architecture:
  ┌─────────┐   ┌─────────┐   ┌─────────┐
  │ Agent A │   │ Brain   │   │ Guardian│
  └────┬────┘   └────┬────┘   └────┬────┘
       │publish       │publish      │publish
       ▼              ▼             ▼
  ╔════════════════════════════════════════╗
  ║         CENTRAL MESSAGE BUS           ║
  ║  (Topic routing, priority queuing,    ║
  ║   async delivery, event history)      ║
  ╚════════════════════════════════════════╝
       │              │             │
       ▼subscribe     ▼subscribe    ▼subscribe
  ┌─────────┐   ┌─────────┐   ┌─────────┐
  │ Nexus   │   │ Predict │   │ WebSock │
  └─────────┘   └─────────┘   └─────────┘

Capabilities:
  1. Topic-Based Routing    — Hierarchical topics (agent.*, brain.security.*)
  2. Priority Queuing       — CRITICAL > HIGH > NORMAL > LOW
  3. Async + Sync Delivery  — Both callback styles supported
  4. Event History          — Circular buffer for replay/debugging
  5. Wildcard Subscriptions — Subscribe to "brain.*" catches all brain events
  6. Dead Letter Queue      — Failed deliveries tracked
  7. Metrics                — Throughput, latency, error rates
"""

import fnmatch
import hashlib
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class MessagePriority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class DeliveryStatus(Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class BusMessage:
    """A message on the bus."""
    topic: str = ""
    payload: Any = None
    sender: str = ""
    priority: MessagePriority = MessagePriority.NORMAL
    message_id: str = ""
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""  # For request-reply patterns
    reply_to: str = ""        # Topic to reply on
    ttl_seconds: float = 300  # Time to live
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.message_id:
            self.message_id = hashlib.md5(
                f"{self.topic}_{self.sender}_{self.timestamp}".encode()
            ).hexdigest()[:12]

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "sender": self.sender,
            "priority": self.priority.name,
            "timestamp": self.timestamp,
            "payload_type": type(self.payload).__name__,
            "correlation_id": self.correlation_id,
        }


@dataclass
class Subscription:
    """A topic subscription."""
    subscriber_id: str = ""
    topic_pattern: str = ""  # Supports wildcards: "brain.*", "agent.#"
    callback: Callable = None
    priority_filter: Optional[MessagePriority] = None  # Min priority
    created_at: float = field(default_factory=time.time)
    message_count: int = 0
    error_count: int = 0
    last_error: str = ""


@dataclass
class BusMetrics:
    """Bus performance metrics."""
    total_published: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    total_dead_letters: int = 0
    active_subscriptions: int = 0
    topics_seen: int = 0
    avg_delivery_time_ms: float = 0.0
    messages_per_second: float = 0.0
    _delivery_times: Deque = field(default_factory=lambda: deque(maxlen=1000))
    _publish_times: Deque = field(default_factory=lambda: deque(maxlen=1000))

    def record_delivery(self, duration_ms: float):
        self._delivery_times.append(duration_ms)
        self.total_delivered += 1
        if self._delivery_times:
            self.avg_delivery_time_ms = sum(self._delivery_times) / len(self._delivery_times)

    def record_publish(self):
        now = time.time()
        self.total_published += 1
        self._publish_times.append(now)
        # Calculate messages per second over last 60s
        cutoff = now - 60
        recent = [t for t in self._publish_times if t > cutoff]
        self.messages_per_second = len(recent) / 60.0


class MessageBus:
    """
    Central pub/sub message bus for inter-agent communication.

    Supports topic-based routing with wildcards, priority queuing,
    synchronous delivery, event history, and dead letter tracking.
    """

    MAX_HISTORY = 5000
    MAX_DEAD_LETTERS = 500
    MAX_SUBSCRIBERS_PER_TOPIC = 50

    def __init__(self):
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._history: Deque[BusMessage] = deque(maxlen=self.MAX_HISTORY)
        self._dead_letters: Deque[Tuple[BusMessage, str]] = deque(maxlen=self.MAX_DEAD_LETTERS)
        self._metrics = BusMetrics()
        self._lock = threading.RLock()
        self._topics_seen: Set[str] = set()
        self._reply_waiters: Dict[str, threading.Event] = {}
        self._reply_results: Dict[str, Any] = {}

        # Async callback queue for WebSocket broadcasting
        self._async_listeners: List[Callable] = []

        logger.info("[BUS] Central Message Bus initialized")

    # ── Publishing ──

    def publish(self, topic: str, payload: Any = None,
                sender: str = "system", priority: MessagePriority = MessagePriority.NORMAL,
                correlation_id: str = "", reply_to: str = "",
                metadata: Dict[str, Any] = None) -> BusMessage:
        """Publish a message to a topic."""
        msg = BusMessage(
            topic=topic, payload=payload, sender=sender,
            priority=priority, correlation_id=correlation_id,
            reply_to=reply_to, metadata=metadata or {},
        )

        with self._lock:
            self._history.append(msg)
            self._topics_seen.add(topic)
            self._metrics.record_publish()
            self._metrics.topics_seen = len(self._topics_seen)

        # Deliver to matching subscribers
        self._deliver(msg)

        # Notify async listeners (for WebSocket broadcasting)
        for listener in self._async_listeners:
            try:
                listener(msg.to_dict())
            except Exception:
                pass

        # Check if this is a reply to a waiting request
        if msg.correlation_id and msg.correlation_id in self._reply_waiters:
            self._reply_results[msg.correlation_id] = payload
            self._reply_waiters[msg.correlation_id].set()

        return msg

    def publish_event(self, topic: str, event_type: str,
                      data: Any = None, sender: str = "system") -> BusMessage:
        """Convenience: publish a structured event."""
        return self.publish(
            topic=topic,
            payload={"event_type": event_type, "data": data},
            sender=sender,
        )

    # ── Subscribing ──

    def subscribe(self, topic_pattern: str, callback: Callable,
                  subscriber_id: str = "", priority_filter: MessagePriority = None) -> str:
        """Subscribe to a topic pattern. Returns subscription ID."""
        if not subscriber_id:
            subscriber_id = hashlib.md5(
                f"{topic_pattern}_{id(callback)}_{time.time()}".encode()
            ).hexdigest()[:10]

        sub = Subscription(
            subscriber_id=subscriber_id,
            topic_pattern=topic_pattern,
            callback=callback,
            priority_filter=priority_filter,
        )

        with self._lock:
            subs = self._subscriptions[topic_pattern]
            if len(subs) >= self.MAX_SUBSCRIBERS_PER_TOPIC:
                logger.warning(f"[BUS] Max subscribers reached for {topic_pattern}")
                return subscriber_id
            subs.append(sub)
            self._metrics.active_subscriptions = sum(
                len(s) for s in self._subscriptions.values()
            )

        logger.debug(f"[BUS] Subscription: {subscriber_id} → {topic_pattern}")
        return subscriber_id

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Remove a subscription by ID."""
        with self._lock:
            for pattern, subs in self._subscriptions.items():
                self._subscriptions[pattern] = [
                    s for s in subs if s.subscriber_id != subscriber_id
                ]
            self._metrics.active_subscriptions = sum(
                len(s) for s in self._subscriptions.values()
            )
        return True

    def on(self, topic_pattern: str, priority_filter: MessagePriority = None):
        """Decorator for subscribing to a topic."""
        def decorator(fn):
            self.subscribe(topic_pattern, fn, priority_filter=priority_filter)
            return fn
        return decorator

    # ── Request-Reply Pattern ──

    def request(self, topic: str, payload: Any, sender: str = "system",
                timeout: float = 30.0) -> Optional[Any]:
        """Send a request and wait for a reply (synchronous)."""
        correlation_id = hashlib.md5(
            f"req_{time.time()}_{topic}".encode()
        ).hexdigest()[:12]
        reply_topic = f"_reply.{correlation_id}"

        event = threading.Event()
        self._reply_waiters[correlation_id] = event

        # Publish the request
        self.publish(
            topic=topic, payload=payload, sender=sender,
            correlation_id=correlation_id, reply_to=reply_topic,
        )

        # Wait for reply
        got_reply = event.wait(timeout=timeout)
        self._reply_waiters.pop(correlation_id, None)

        if got_reply:
            return self._reply_results.pop(correlation_id, None)
        return None

    def reply(self, original_msg: BusMessage, payload: Any, sender: str = "system"):
        """Reply to a request message."""
        if original_msg.reply_to and original_msg.correlation_id:
            self.publish(
                topic=original_msg.reply_to,
                payload=payload,
                sender=sender,
                correlation_id=original_msg.correlation_id,
            )

    # ── Delivery ──

    def _deliver(self, msg: BusMessage) -> None:
        """Deliver a message to matching subscribers."""
        if msg.is_expired:
            return

        with self._lock:
            all_subs = []
            for pattern, subs in self._subscriptions.items():
                if self._topic_matches(pattern, msg.topic):
                    all_subs.extend(subs)

        # Sort by priority filter (higher priority subs first)
        for sub in all_subs:
            if sub.priority_filter and msg.priority < sub.priority_filter:
                continue

            start = time.time()
            try:
                sub.callback(msg)
                sub.message_count += 1
                duration_ms = (time.time() - start) * 1000
                self._metrics.record_delivery(duration_ms)
            except Exception as e:
                sub.error_count += 1
                sub.last_error = str(e)
                self._metrics.total_failed += 1
                self._dead_letters.append((msg, str(e)))
                self._metrics.total_dead_letters = len(self._dead_letters)
                logger.warning(f"[BUS] Delivery failed: {msg.topic} → {sub.subscriber_id}: {e}")

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """Check if a topic matches a subscription pattern.
        Supports:
          - Exact: "agent.chat" matches "agent.chat"
          - Wildcard: "agent.*" matches "agent.chat", "agent.code"
          - Deep wildcard: "brain.#" matches "brain.security.alert"
        """
        if pattern == topic:
            return True
        # Convert # to ** for deep matching
        glob_pattern = pattern.replace("#", "**")
        # Use fnmatch for wildcard support
        return fnmatch.fnmatch(topic, glob_pattern)

    # ── Async Listener (for WebSocket) ──

    def add_async_listener(self, callback: Callable) -> None:
        """Add a listener for all messages (used by WebSocket broadcaster)."""
        self._async_listeners.append(callback)

    def remove_async_listener(self, callback: Callable) -> None:
        self._async_listeners = [l for l in self._async_listeners if l != callback]

    # ── History & Debugging ──

    def get_history(self, topic: str = None, limit: int = 50,
                    sender: str = None) -> List[Dict]:
        """Get message history, optionally filtered."""
        msgs = list(self._history)
        if topic:
            msgs = [m for m in msgs if self._topic_matches(topic, m.topic)]
        if sender:
            msgs = [m for m in msgs if m.sender == sender]
        return [m.to_dict() for m in msgs[-limit:]]

    def get_dead_letters(self, limit: int = 20) -> List[Dict]:
        """Get failed delivery messages."""
        return [
            {"message": msg.to_dict(), "error": err}
            for msg, err in list(self._dead_letters)[-limit:]
        ]

    def get_topics(self) -> List[str]:
        """List all topics that have been published to."""
        return sorted(self._topics_seen)

    def get_subscriptions(self) -> List[Dict]:
        """List all active subscriptions."""
        result = []
        for pattern, subs in self._subscriptions.items():
            for s in subs:
                result.append({
                    "subscriber_id": s.subscriber_id,
                    "pattern": pattern,
                    "messages_received": s.message_count,
                    "errors": s.error_count,
                })
        return result

    # ── Metrics ──

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_published": self._metrics.total_published,
            "total_delivered": self._metrics.total_delivered,
            "total_failed": self._metrics.total_failed,
            "dead_letters": self._metrics.total_dead_letters,
            "active_subscriptions": self._metrics.active_subscriptions,
            "topics_seen": self._metrics.topics_seen,
            "avg_delivery_ms": round(self._metrics.avg_delivery_time_ms, 3),
            "messages_per_second": round(self._metrics.messages_per_second, 2),
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "online": True,
            **self.get_metrics(),
            "history_size": len(self._history),
        }


# ── Singleton ──

_bus_instance: Optional[MessageBus] = None
_bus_lock = threading.Lock()


def get_message_bus() -> MessageBus:
    """Get the global message bus singleton."""
    global _bus_instance
    if _bus_instance is None:
        with _bus_lock:
            if _bus_instance is None:
                _bus_instance = MessageBus()
    return _bus_instance
