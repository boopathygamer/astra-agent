"""
Streaming Pipeline — Progressive Response with Quality Gates
══════════════════════════════════════════════════════════
Progressive token streaming with chunk buffering, live quality
scoring, early termination, and quality gates.
"""

import logging
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


class StreamQuality(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


@dataclass
class StreamChunk:
    """A chunk of streamed response."""
    text: str = ""
    chunk_index: int = 0
    quality: StreamQuality = StreamQuality.GOOD
    latency_ms: float = 0.0
    tokens: int = 0
    is_final: bool = False


@dataclass
class StreamSession:
    """State for an active streaming session."""
    session_id: str = ""
    chunks: List[StreamChunk] = field(default_factory=list)
    total_tokens: int = 0
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    quality_scores: List[float] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str = ""

    @property
    def avg_quality(self) -> float:
        if not self.quality_scores:
            return 0.5
        return sum(self.quality_scores) / len(self.quality_scores)

    @property
    def duration_ms(self) -> float:
        end = self.completed_at or time.time()
        return (end - self.started_at) * 1000


class StreamingPipeline:
    """
    Progressive response streaming with quality gates,
    chunk buffering, and early termination.
    """

    BUFFER_SIZE = 3         # Chunks to buffer before sending
    MIN_QUALITY = 0.3       # Minimum quality before abort
    MAX_CHUNKS = 50         # Max chunks per session

    def __init__(self):
        self._active_sessions: Dict[str, StreamSession] = {}
        self._completed: deque = deque(maxlen=100)
        self._total_sessions = 0
        self._total_aborts = 0
        self._lock = threading.Lock()
        logger.info("[STREAMING] Pipeline initialized")

    def create_session(self) -> str:
        """Create a new streaming session."""
        import hashlib
        sid = hashlib.md5(
            f"stream_{time.time()}".encode()
        ).hexdigest()[:10]

        session = StreamSession(session_id=sid)
        with self._lock:
            self._active_sessions[sid] = session
        self._total_sessions += 1
        return sid

    def stream_response(self, text: str, session_id: str = None,
                         chunk_size: int = 50,
                         callback: Optional[Callable] = None) -> Generator[StreamChunk, None, None]:
        """Stream a response text in chunks with quality gates."""
        sid = session_id or self.create_session()
        session = self._active_sessions.get(sid)
        if not session:
            session = StreamSession(session_id=sid)
            self._active_sessions[sid] = session

        words = text.split()
        chunk_idx = 0

        for i in range(0, len(words), chunk_size):
            if chunk_idx >= self.MAX_CHUNKS:
                break

            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)

            # Score quality
            quality_score = self._score_chunk_quality(chunk_text, chunk_idx)
            quality = self._map_quality(quality_score)

            chunk = StreamChunk(
                text=chunk_text,
                chunk_index=chunk_idx,
                quality=quality,
                tokens=len(chunk_words),
                is_final=(i + chunk_size >= len(words)),
                latency_ms=(time.time() - session.started_at) * 1000,
            )

            session.chunks.append(chunk)
            session.total_tokens += chunk.tokens
            session.quality_scores.append(quality_score)

            # Quality gate check
            if quality_score < self.MIN_QUALITY and chunk_idx > 2:
                session.aborted = True
                session.abort_reason = f"Quality dropped below {self.MIN_QUALITY}"
                self._total_aborts += 1
                chunk.is_final = True
                if callback:
                    callback({"event": "abort", "reason": session.abort_reason})
                yield chunk
                break

            if callback:
                callback({
                    "event": "chunk",
                    "index": chunk_idx,
                    "quality": quality.value,
                    "tokens": chunk.tokens,
                })

            chunk_idx += 1
            yield chunk

        # Finalize session
        session.completed_at = time.time()
        with self._lock:
            self._active_sessions.pop(sid, None)
            self._completed.append(session)

    def _score_chunk_quality(self, text: str, index: int) -> float:
        """Score chunk quality based on content signals."""
        if not text.strip():
            return 0.1

        score = 0.5
        words = text.split()

        # Length signal
        if len(words) > 10:
            score += 0.1
        if len(words) > 30:
            score += 0.1

        # Content quality signals
        if any(c in text for c in ['.', '!', '?']):
            score += 0.1
        if any(kw in text.lower() for kw in ["because", "therefore", "specifically"]):
            score += 0.1

        # Repetition penalty
        unique_ratio = len(set(words)) / max(len(words), 1)
        if unique_ratio < 0.5:
            score -= 0.2

        return min(max(score, 0.0), 1.0)

    def _map_quality(self, score: float) -> StreamQuality:
        if score >= 0.8:
            return StreamQuality.EXCELLENT
        elif score >= 0.6:
            return StreamQuality.GOOD
        elif score >= 0.4:
            return StreamQuality.ACCEPTABLE
        return StreamQuality.POOR

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_sessions": self._total_sessions,
            "active_sessions": len(self._active_sessions),
            "total_aborts": self._total_aborts,
            "abort_rate": self._total_aborts / max(self._total_sessions, 1),
            "completed_sessions": len(self._completed),
        }
