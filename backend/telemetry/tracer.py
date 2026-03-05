"""
Span Tracer — Lightweight Request-Level Tracing
════════════════════════════════════════════════
OpenTelemetry-inspired tracing with:
  - Nested spans (parent-child relationships)
  - Automatic duration measurement
  - Status tracking (OK, ERROR)
  - Attribute recording
  - JSON export for analysis

Zero external dependencies. Context-manager based.
"""

import json
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

@dataclass
class Span:
    """A single trace span representing a unit of work."""
    span_id: str = ""
    trace_id: str = ""
    parent_id: str = ""
    name: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    status: str = "OK"  # OK, ERROR
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    children: List[str] = field(default_factory=list)  # child span IDs

    def __post_init__(self):
        if not self.span_id:
            self.span_id = str(uuid.uuid4())[:12]

    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """Add a timestamped event to this span."""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def set_error(self, error: str):
        """Mark this span as errored."""
        self.status = "ERROR"
        self.attributes["error.message"] = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 3),
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
            "children": self.children,
        }


@dataclass
class Trace:
    """A complete trace consisting of multiple spans."""
    trace_id: str = ""
    root_span_id: str = ""
    spans: Dict[str, Span] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0
    total_duration_ms: float = 0.0

    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_span_id": self.root_span_id,
            "total_duration_ms": round(self.total_duration_ms, 3),
            "span_count": len(self.spans),
            "spans": {sid: s.to_dict() for sid, s in self.spans.items()},
        }


# ══════════════════════════════════════════════════════════════
# Span Context (Thread-Local Stack)
# ══════════════════════════════════════════════════════════════

class _SpanContext(threading.local):
    """Thread-local span stack for nested context tracking."""
    def __init__(self):
        self.stack: List[Span] = []
        self.current_trace: Optional[Trace] = None


_context = _SpanContext()


# ══════════════════════════════════════════════════════════════
# Span Tracer
# ══════════════════════════════════════════════════════════════

class SpanTracer:
    """
    Lightweight request-level tracer.

    Usage:
        tracer = SpanTracer()

        # Start a trace
        with tracer.trace("process_request") as trace:
            with tracer.span("compile") as s1:
                s1.attributes["input_length"] = len(user_input)
                # ... do compilation ...

            with tracer.span("thinking_loop") as s2:
                for i in range(iterations):
                    with tracer.span(f"iteration_{i}") as s3:
                        s3.attributes["strategy"] = "chain_of_thought"
                        # ... think ...

        # Export
        print(tracer.export_json())
    """

    def __init__(self, max_traces: int = 100):
        self._traces: List[Trace] = []
        self._max_traces = max_traces
        self._lock = threading.Lock()

    @contextmanager
    def trace(self, name: str = "request", attributes: Dict[str, Any] = None):
        """Start a new trace (top-level operation)."""
        trace = Trace()
        _context.current_trace = trace
        _context.stack = []

        try:
            with self.span(name, attributes=attributes) as root_span:
                trace.root_span_id = root_span.span_id
                trace.start_time = root_span.start_time
                yield trace
        finally:
            trace.end_time = time.time()
            trace.total_duration_ms = (trace.end_time - trace.start_time) * 1000
            with self._lock:
                self._traces.append(trace)
                if len(self._traces) > self._max_traces:
                    self._traces = self._traces[-self._max_traces:]
            _context.current_trace = None
            _context.stack = []

    @contextmanager
    def span(self, name: str, attributes: Dict[str, Any] = None):
        """Create a span (nested unit of work within a trace)."""
        trace = _context.current_trace
        if trace is None:
            # No active trace — create a standalone span
            span = Span(name=name, start_time=time.time())
            if attributes:
                span.attributes.update(attributes)
            try:
                yield span
            except Exception as e:
                span.set_error(str(e))
                raise
            finally:
                span.end_time = time.time()
                span.duration_ms = (span.end_time - span.start_time) * 1000
            return

        # Create span within trace
        parent = _context.stack[-1] if _context.stack else None
        span = Span(
            trace_id=trace.trace_id,
            parent_id=parent.span_id if parent else "",
            name=name,
            start_time=time.time(),
        )
        if attributes:
            span.attributes.update(attributes)

        # Register
        trace.spans[span.span_id] = span
        if parent:
            parent.children.append(span.span_id)
        _context.stack.append(span)

        try:
            yield span
        except Exception as e:
            span.set_error(str(e))
            raise
        finally:
            span.end_time = time.time()
            span.duration_ms = (span.end_time - span.start_time) * 1000
            if _context.stack and _context.stack[-1] is span:
                _context.stack.pop()

    def get_traces(self, last_n: int = 10) -> List[Trace]:
        """Get recent traces."""
        with self._lock:
            return list(self._traces[-last_n:])

    def get_last_trace(self) -> Optional[Trace]:
        """Get the most recent trace."""
        with self._lock:
            return self._traces[-1] if self._traces else None

    def export_json(self, filepath: str = None) -> str:
        """Export all traces as JSON."""
        with self._lock:
            data = {
                "total_traces": len(self._traces),
                "traces": [t.to_dict() for t in self._traces[-50:]],
            }
        json_str = json.dumps(data, indent=2, default=str)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str

    def print_trace(self, trace: Trace = None, indent: int = 0):
        """Pretty-print a trace tree."""
        if trace is None:
            trace = self.get_last_trace()
        if trace is None:
            print("No traces available")
            return

        print(f"\n{'═' * 60}")
        print(f"  Trace: {trace.trace_id} ({trace.total_duration_ms:.1f}ms)")
        print(f"{'═' * 60}")

        def print_span(span_id: str, depth: int = 0):
            span = trace.spans.get(span_id)
            if not span:
                return
            prefix = "  │ " * depth + "  ├─ " if depth > 0 else "  "
            status_icon = "✅" if span.status == "OK" else "❌"
            print(f"{prefix}{status_icon} {span.name} ({span.duration_ms:.1f}ms)")
            for attr_key, attr_val in span.attributes.items():
                attr_prefix = "  │ " * (depth + 1) + "     "
                print(f"{attr_prefix}{attr_key}: {attr_val}")
            for child_id in span.children:
                print_span(child_id, depth + 1)

        if trace.root_span_id:
            print_span(trace.root_span_id)
        print(f"{'═' * 60}\n")

    def get_stats(self) -> Dict[str, Any]:
        """Get tracing statistics."""
        with self._lock:
            if not self._traces:
                return {"total_traces": 0}

            durations = [t.total_duration_ms for t in self._traces]
            span_counts = [len(t.spans) for t in self._traces]

            return {
                "total_traces": len(self._traces),
                "avg_duration_ms": round(sum(durations) / len(durations), 2),
                "max_duration_ms": round(max(durations), 2),
                "avg_spans_per_trace": round(sum(span_counts) / len(span_counts), 1),
                "total_spans": sum(span_counts),
            }
