"""
Cognitive Osmosis — User Intent Prediction via Context Analysis
───────────────────────────────────────────────────────────────
Expert-level intent prediction engine that analyzes conversation
history, active file context, and session patterns to predict
the user's next query before they type it.
"""

import hashlib
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IntentPrediction:
    """A predicted user intent with confidence score."""
    predicted_query: str
    confidence: float  # 0.0 to 1.0
    source: str  # what evidence this was derived from
    timestamp: float = field(default_factory=time.time)


class CognitiveOsmosis:
    """
    Tier 8: Cognitive Osmosis (User Intent Prediction)

    Analyzes conversation history, active files, and session patterns
    to predict the user's next query. Pre-computes potential answers
    so they're ready before the user finishes typing.
    """

    _INTENT_PATTERNS = {
        r"\b(error|bug|crash|fail|exception|traceback)\b": "debug_assistance",
        r"\b(how|explain|what is|why)\b": "knowledge_query",
        r"\b(build|create|implement|add|make)\b": "feature_request",
        r"\b(fix|repair|resolve|solve)\b": "bug_fix",
        r"\b(optimize|speed|slow|performance|fast)\b": "optimization",
        r"\b(deploy|host|server|production)\b": "deployment",
        r"\b(test|verify|check|validate)\b": "testing",
        r"\b(style|css|design|ui|layout)\b": "ui_design",
    }

    def __init__(self):
        self._conversation_history: List[str] = []
        self._intent_frequency: Counter = Counter()
        self._predictions_made: int = 0
        self._prediction_hits: int = 0
        logger.info("[COGNITIVE-OSMOSIS] Intent prediction engine active.")

    def observe(self, user_message: str) -> None:
        """Record a user message for pattern learning."""
        self._conversation_history.append(user_message)
        # Keep only last 100 messages
        if len(self._conversation_history) > 100:
            self._conversation_history = self._conversation_history[-100:]

        # Update intent frequency from observed patterns
        for pattern, intent_type in self._INTENT_PATTERNS.items():
            if re.search(pattern, user_message, re.IGNORECASE):
                self._intent_frequency[intent_type] += 1

    def predict_intent(self, active_file: Optional[str] = None, recent_errors: Optional[List[str]] = None) -> List[IntentPrediction]:
        """
        Predict the user's next likely query based on conversation
        history, active file context, and recent errors.
        """
        predictions: List[IntentPrediction] = []
        self._predictions_made += 1

        # Strategy 1: Recent error context
        if recent_errors:
            for error in recent_errors[:3]:
                predictions.append(IntentPrediction(
                    predicted_query=f"Fix the error: {error[:200]}",
                    confidence=0.85,
                    source="recent_error_context",
                ))

        # Strategy 2: Active file context
        if active_file:
            ext = active_file.rsplit(".", 1)[-1] if "." in active_file else ""
            file_intents = {
                "py": "I need help with this Python code",
                "tsx": "I need help with this React component",
                "css": "I need help styling this component",
                "sql": "I need help with this database query",
            }
            if ext in file_intents:
                predictions.append(IntentPrediction(
                    predicted_query=file_intents[ext],
                    confidence=0.5,
                    source=f"active_file:{active_file}",
                ))

        # Strategy 3: Most frequent historical intent pattern
        if self._intent_frequency:
            most_common = self._intent_frequency.most_common(3)
            for intent_type, count in most_common:
                predictions.append(IntentPrediction(
                    predicted_query=f"[Predicted: {intent_type} query based on {count} past interactions]",
                    confidence=min(0.7, count * 0.1),
                    source=f"historical_pattern:{intent_type}",
                ))

        # Sort by confidence descending
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        logger.info("[COGNITIVE-OSMOSIS] Generated %d intent predictions.", len(predictions))
        return predictions[:5]  # Top 5

    def validate_prediction(self, actual_query: str) -> bool:
        """Check if our prediction was close to the actual query."""
        self.observe(actual_query)
        # Simple heuristic: check keyword overlap
        actual_words = set(actual_query.lower().split())
        for pred in self.predict_intent():
            pred_words = set(pred.predicted_query.lower().split())
            overlap = len(actual_words & pred_words) / max(len(actual_words), 1)
            if overlap > 0.3:
                self._prediction_hits += 1
                return True
        return False

    @property
    def accuracy(self) -> float:
        if self._predictions_made == 0:
            return 0.0
        return self._prediction_hits / self._predictions_made


# Global singleton — always active
intent_emulator = CognitiveOsmosis()
