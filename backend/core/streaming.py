"""
Streaming Infrastructure — SSE streaming with block coalescing.
───────────────────────────────────────────────────────────────
Features (inspired by OpenClaw streaming/chunking):
  - Server-Sent Events (SSE) for real-time token streaming
  - Block streaming with configurable break points
  - Response coalescing for short messages
  - Tool-use event streaming
  - Chunk size control for channel-appropriate responses
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


class StreamEventType(Enum):
    """Types of streaming events."""
    TOKEN = "token"        # Single generated token  # nosec B105
    TEXT_CHUNK = "chunk"   # Coalesced text chunk
    TOOL_START = "tool_start"   # Tool call initiated
    TOOL_RESULT = "tool_result" # Tool call completed
    THINKING = "thinking"       # Internal thinking step
    STATUS = "status"           # Status update
    DONE = "done"              # Generation complete
    ERROR = "error"            # Error occurred


@dataclass
class StreamEvent:
    """A single streaming event."""
    event_type: StreamEventType
    data: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        payload = {
            "type": self.event_type.value,
            "data": self.data,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        return f"data: {json.dumps(payload)}\n\n"

    def to_dict(self) -> dict:
        return {
            "type": self.event_type.value,
            "data": self.data,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class StreamConfig:
    """Configuration for streaming behavior."""
    # Chunking
    chunk_size: int = 50          # Tokens per chunk
    coalesce_ms: int = 100        # Coalesce tokens within this window
    max_chunk_chars: int = 2000   # Max characters per chunk

    # Block streaming
    break_on: str = "sentence"    # "token", "sentence", "paragraph"
    min_chunk_tokens: int = 5     # Minimum tokens before sending chunk

    # Channel-specific limits
    max_message_length: int = 4000  # Split long messages at this length


class StreamCoalescer:
    """
    Coalesces individual tokens into larger chunks for smoother streaming.

    Instead of sending every single token, this buffers tokens and
    flushes either when:
      - Buffer reaches chunk_size tokens
      - Sentence boundary detected
      - Coalesce timeout exceeded
      - Generation completes
    """

    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()
        self._buffer: List[str] = []
        self._token_count: int = 0
        self._last_flush_time: float = time.time()
        self._total_text: str = ""

    def add_token(self, token: str) -> Optional[StreamEvent]:
        """
        Add a token to the buffer.
        Returns a StreamEvent if the buffer should be flushed.
        """
        self._buffer.append(token)
        self._token_count += 1
        self._total_text += token

        # Check flush conditions
        should_flush = False
        buffer_text = "".join(self._buffer)

        # 1. Chunk size reached
        if self._token_count >= self.config.chunk_size:
            should_flush = True

        # 2. Sentence boundary
        elif (self.config.break_on == "sentence"
              and self._token_count >= self.config.min_chunk_tokens
              and any(buffer_text.rstrip().endswith(p) for p in [".", "!", "?", "\n"])):
            should_flush = True

        # 3. Paragraph boundary
        elif (self.config.break_on == "paragraph"
              and "\n\n" in buffer_text):
            should_flush = True

        # 4. Max chars reached
        elif len(buffer_text) >= self.config.max_chunk_chars:
            should_flush = True

        # 5. Coalesce timeout
        elif (time.time() - self._last_flush_time) * 1000 > self.config.coalesce_ms:
            if self._token_count >= self.config.min_chunk_tokens:
                should_flush = True

        if should_flush:
            return self._flush()
        return None

    def _flush(self) -> Optional[StreamEvent]:
        """Flush the buffer and return a chunk event."""
        if not self._buffer:
            return None

        text = "".join(self._buffer)
        self._buffer.clear()
        self._token_count = 0
        self._last_flush_time = time.time()

        return StreamEvent(
            event_type=StreamEventType.TEXT_CHUNK,
            data=text,
            metadata={"total_length": len(self._total_text)},
        )

    def finish(self) -> Optional[StreamEvent]:
        """Flush remaining buffer and return final chunk."""
        return self._flush()

    def reset(self):
        """Reset the coalescer state."""
        self._buffer.clear()
        self._token_count = 0
        self._total_text = ""
        self._last_flush_time = time.time()


class StreamProcessor:
    """
    Processes a generation stream and produces coalesced events.

    Handles:
      - Token coalescing
      - Tool use events
      - Thinking/status events
      - Message splitting for channel limits
    """

    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()
        self.coalescer = StreamCoalescer(config)
        self._events: List[StreamEvent] = []

    def process_token(self, token: str) -> List[StreamEvent]:
        """Process a single generated token. Returns events to emit."""
        events = []
        chunk_event = self.coalescer.add_token(token)
        if chunk_event:
            events.append(chunk_event)
            self._events.append(chunk_event)
        return events

    def emit_tool_start(self, tool_name: str, args: dict) -> StreamEvent:
        """Emit a tool start event."""
        event = StreamEvent(
            event_type=StreamEventType.TOOL_START,
            data=tool_name,
            metadata={"args": args},
        )
        self._events.append(event)
        return event

    def emit_tool_result(self, tool_name: str, result: Any) -> StreamEvent:
        """Emit a tool result event."""
        event = StreamEvent(
            event_type=StreamEventType.TOOL_RESULT,
            data=str(result)[:500],  # Truncate long results
            metadata={"tool": tool_name},
        )
        self._events.append(event)
        return event

    def emit_thinking(self, step: str, detail: str = "") -> StreamEvent:
        """Emit a thinking/reasoning step event."""
        event = StreamEvent(
            event_type=StreamEventType.THINKING,
            data=step,
            metadata={"detail": detail} if detail else {},
        )
        self._events.append(event)
        return event

    def emit_status(self, message: str) -> StreamEvent:
        """Emit a status update event."""
        event = StreamEvent(
            event_type=StreamEventType.STATUS,
            data=message,
        )
        self._events.append(event)
        return event

    def finish(self) -> List[StreamEvent]:
        """Finish streaming. Returns final events."""
        events = []

        # Flush remaining tokens
        final_chunk = self.coalescer.finish()
        if final_chunk:
            events.append(final_chunk)

        # Emit done event
        total_text = self.coalescer._total_text
        done_event = StreamEvent(
            event_type=StreamEventType.DONE,
            data="",
            metadata={
                "total_length": len(total_text),
                "total_events": len(self._events),
            },
        )
        events.append(done_event)
        return events

    def split_for_channel(self, text: str) -> List[str]:
        """
        Split a long response into channel-appropriate chunks.
        Respects sentence boundaries when splitting.
        """
        max_len = self.config.max_message_length
        if len(text) <= max_len:
            return [text]

        chunks = []
        remaining = text

        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining)
                break

            # Find a good split point (sentence boundary)
            split_at = max_len
            for delim in ["\n\n", "\n", ". ", "! ", "? "]:
                pos = remaining[:max_len].rfind(delim)
                if pos > max_len // 2:  # Only split if past halfway
                    split_at = pos + len(delim)
                    break

            chunks.append(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()

        return chunks

    def get_full_text(self) -> str:
        """Get the full generated text."""
        return self.coalescer._total_text

    def reset(self):
        """Reset the processor."""
        self.coalescer.reset()
        self._events.clear()
