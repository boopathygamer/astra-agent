"""
Loop Detection Guardrails — Prevent tool-call loops.
─────────────────────────────────────────────────────
Three detectors (from OpenClaw):
  1. generic_repeat  — same tool + same params N times
  2. poll_no_progress — poll-like tools with identical results
  3. ping_pong       — A/B/A/B alternating no-progress patterns

Thresholds:
  warning_threshold       = 5   → inject warning into context
  critical_threshold      = 10  → force tool switch
  circuit_breaker_threshold = 20 → halt agent loop entirely
"""

import hashlib
import json
import logging
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LoopSeverity(Enum):
    NONE = "none"
    WARNING = "warning"
    CRITICAL = "critical"
    CIRCUIT_BREAK = "circuit_break"


@dataclass
class ToolCall:
    """Record of a single tool call."""
    tool_name: str
    args_hash: str     # Hash of serialized args
    result_hash: str   # Hash of serialized result
    iteration: int = 0

    @staticmethod
    def hash_data(data: Any) -> str:
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass
class LoopDetection:
    """Result of loop detection analysis."""
    severity: LoopSeverity = LoopSeverity.NONE
    detector: str = ""
    message: str = ""
    repeat_count: int = 0
    should_halt: bool = False
    should_warn: bool = False
    suggested_action: str = ""

    def __bool__(self):
        return self.severity != LoopSeverity.NONE


@dataclass
class LoopDetectorConfig:
    """Configuration for loop detection."""
    enabled: bool = True
    warning_threshold: int = 5
    critical_threshold: int = 10
    circuit_breaker_threshold: int = 20
    history_size: int = 30

    # Individual detector toggles
    generic_repeat: bool = True
    poll_no_progress: bool = True
    ping_pong: bool = True


class LoopDetector:
    """
    Detects and prevents tool-call loops.

    Runs three detection algorithms after each tool call and
    returns the most severe detection result.
    """

    def __init__(self, config: Optional[LoopDetectorConfig] = None):
        self.config = config or LoopDetectorConfig()
        self._history: Deque[ToolCall] = deque(maxlen=self.config.history_size)
        self._total_calls: int = 0

    def record(
        self,
        tool_name: str,
        args: Any,
        result: Any,
    ) -> LoopDetection:
        """
        Record a tool call and check for loops.

        Args:
            tool_name: Name of the tool called
            args: Arguments passed to the tool
            result: Result returned by the tool

        Returns:
            LoopDetection with severity and recommended action
        """
        if not self.config.enabled:
            return LoopDetection()

        self._total_calls += 1

        call = ToolCall(
            tool_name=tool_name,
            args_hash=ToolCall.hash_data(args),
            result_hash=ToolCall.hash_data(result),
            iteration=self._total_calls,
        )
        self._history.append(call)

        # Run all detectors, return the most severe
        detections = []

        if self.config.generic_repeat:
            detections.append(self._detect_generic_repeat())

        if self.config.poll_no_progress:
            detections.append(self._detect_poll_no_progress())

        if self.config.ping_pong:
            detections.append(self._detect_ping_pong())

        # Return most severe
        if detections:
            detections.sort(
                key=lambda d: [
                    LoopSeverity.NONE,
                    LoopSeverity.WARNING,
                    LoopSeverity.CRITICAL,
                    LoopSeverity.CIRCUIT_BREAK,
                ].index(d.severity),
                reverse=True,
            )
            worst = detections[0]
            if worst:
                logger.warning(
                    f"Loop detected [{worst.detector}]: "
                    f"{worst.severity.value} — {worst.message}"
                )
            return worst

        return LoopDetection()

    def _detect_generic_repeat(self) -> LoopDetection:
        """
        Detector 1: Same tool + same params called N times.

        Counts consecutive identical (tool_name, args_hash) tuples.
        """
        if len(self._history) < 2:
            return LoopDetection()

        current = self._history[-1]
        count = 0

        for call in reversed(self._history):
            if (call.tool_name == current.tool_name
                    and call.args_hash == current.args_hash):
                count += 1
            else:
                break

        return self._classify(
            count=count,
            detector="generic_repeat",
            message=f"Tool '{current.tool_name}' called {count}x with identical args",
            suggestion=f"Try a different approach or tool instead of repeating '{current.tool_name}'",
        )

    def _detect_poll_no_progress(self) -> LoopDetection:
        """
        Detector 2: Poll-like tools returning identical results.

        Detects when the same tool returns the same result repeatedly.
        """
        if len(self._history) < 3:
            return LoopDetection()

        current = self._history[-1]

        # Count calls with same tool AND same result
        same_result_count = 0
        for call in reversed(self._history):
            if call.tool_name != current.tool_name:
                break
            if call.result_hash == current.result_hash:
                same_result_count += 1
            else:
                break

        return self._classify(
            count=same_result_count,
            detector="poll_no_progress",
            message=f"Tool '{current.tool_name}' returned identical results {same_result_count}x",
            suggestion="The tool output hasn't changed — waiting or trying a different approach",
        )

    def _detect_ping_pong(self) -> LoopDetection:
        """
        Detector 3: A/B/A/B alternating no-progress pattern.

        Detects when two tools alternate without making progress.
        """
        if len(self._history) < 4:
            return LoopDetection()

        history = list(self._history)

        # Check for A/B/A/B pattern in the last N calls
        pattern_count = 0
        i = len(history) - 1

        while i >= 3:
            a1 = (history[i].tool_name, history[i].args_hash)
            b1 = (history[i - 1].tool_name, history[i - 1].args_hash)
            a2 = (history[i - 2].tool_name, history[i - 2].args_hash)
            b2 = (history[i - 3].tool_name, history[i - 3].args_hash)

            if a1 == a2 and b1 == b2 and a1 != b1:
                pattern_count += 1
                i -= 2
            else:
                break

        if pattern_count == 0:
            return LoopDetection()

        # Each pattern match is 2 repeats
        effective_count = pattern_count * 2
        return self._classify(
            count=effective_count,
            detector="ping_pong",
            message=(
                f"Alternating pattern between "
                f"'{history[-1].tool_name}' and '{history[-2].tool_name}' "
                f"detected ({pattern_count} cycles)"
            ),
            suggestion="Break the alternating pattern — summarize findings and take a different approach",
        )

    def _classify(
        self,
        count: int,
        detector: str,
        message: str,
        suggestion: str,
    ) -> LoopDetection:
        """Classify the repeat count into a severity level."""
        cfg = self.config

        if count >= cfg.circuit_breaker_threshold:
            return LoopDetection(
                severity=LoopSeverity.CIRCUIT_BREAK,
                detector=detector,
                message=message,
                repeat_count=count,
                should_halt=True,
                should_warn=True,
                suggested_action="HALT: Circuit breaker triggered. Stop all tool calls.",
            )
        elif count >= cfg.critical_threshold:
            return LoopDetection(
                severity=LoopSeverity.CRITICAL,
                detector=detector,
                message=message,
                repeat_count=count,
                should_halt=False,
                should_warn=True,
                suggested_action=f"CRITICAL: {suggestion}. Force a different tool.",
            )
        elif count >= cfg.warning_threshold:
            return LoopDetection(
                severity=LoopSeverity.WARNING,
                detector=detector,
                message=message,
                repeat_count=count,
                should_halt=False,
                should_warn=True,
                suggested_action=f"WARNING: {suggestion}.",
            )

        return LoopDetection()

    def reset(self):
        """Reset all history."""
        self._history.clear()
        self._total_calls = 0

    def get_stats(self) -> dict:
        """Get loop detection statistics."""
        tool_counts = Counter(c.tool_name for c in self._history)
        return {
            "total_calls": self._total_calls,
            "history_size": len(self._history),
            "tool_distribution": dict(tool_counts),
        }
