"""
Predictive Intent Engine — Anticipate User Needs Before They Ask
════════════════════════════════════════════════════════════════
Learns user behavior patterns and predicts what they'll want next.

Capabilities:
  1. Behavior Pattern Mining    — Markov chain over action sequences
  2. Time-Based Predictions     — Cron-like learned routines
  3. Context-Aware Suggestions  — Based on active files/topics
  4. Proactive Briefings        — Daily/session summaries
  5. Accuracy Self-Calibration  — Tracks hit/miss, improves over time
"""

import hashlib
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PredictionType(Enum):
    NEXT_ACTION = "next_action"
    TIME_ROUTINE = "time_routine"
    CONTEXT_SUGGESTION = "context_suggestion"
    PROACTIVE_BRIEFING = "proactive_briefing"
    FOLLOW_UP = "follow_up"


@dataclass
class Prediction:
    prediction_id: str = ""
    prediction_type: PredictionType = PredictionType.NEXT_ACTION
    predicted_action: str = ""
    description: str = ""
    confidence: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    was_correct: Optional[bool] = None

    def __post_init__(self):
        if not self.prediction_id:
            self.prediction_id = hashlib.md5(
                f"{self.predicted_action}_{self.created_at}".encode()
            ).hexdigest()[:12]
        if self.expires_at == 0:
            self.expires_at = self.created_at + 3600

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


@dataclass
class PredictionAccuracy:
    total_predictions: int = 0
    correct: int = 0
    incorrect: int = 0
    expired_unevaluated: int = 0

    @property
    def accuracy(self) -> float:
        evaluated = self.correct + self.incorrect
        return self.correct / evaluated if evaluated else 0.0

    @property
    def evaluated_ratio(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return (self.correct + self.incorrect) / self.total_predictions


class PredictiveIntent:
    """
    Learns user patterns and anticipates needs via Markov chains,
    temporal analysis, contextual reasoning, and self-calibration.
    """

    MAX_HISTORY = 1000
    MARKOV_ORDER = 2
    MIN_PATTERN_COUNT = 3
    ROUTINE_CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path("data/predictions")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._action_history: Deque[Tuple[str, float]] = deque(maxlen=self.MAX_HISTORY)
        self._transitions: Dict[Tuple[str, ...], Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._time_patterns: Dict[Tuple[int, int], Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._context_patterns: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._active_predictions: Deque[Prediction] = deque(maxlen=50)
        self._accuracy = PredictionAccuracy()
        self._session_start = time.time()
        self._session_actions: List[str] = []
        self._load_patterns()
        logger.info("[PREDICT] Predictive Intent engine initialized")

    def record_action(self, action: str, context: Dict[str, Any] = None) -> None:
        now = time.time()
        self._action_history.append((action, now))
        self._session_actions.append(action)
        history_list = [a for a, _ in self._action_history]
        if len(history_list) > self.MARKOV_ORDER:
            prev = tuple(history_list[-(self.MARKOV_ORDER + 1):-1])
            self._transitions[prev][action] += 1
        local = time.localtime(now)
        self._time_patterns[(local.tm_hour, local.tm_wday)][action] += 1
        self._time_patterns[(local.tm_hour, -1)][action] += 1
        if context:
            topic = context.get("topic", "")
            if topic:
                self._context_patterns[topic][action] += 1
        self._evaluate_predictions(action)
        if len(self._action_history) % 50 == 0:
            self._save_patterns()

    def _evaluate_predictions(self, actual_action: str) -> None:
        for pred in self._active_predictions:
            if pred.was_correct is not None:
                continue
            if pred.is_expired():
                pred.was_correct = False
                self._accuracy.expired_unevaluated += 1
                continue
            if (pred.predicted_action == actual_action or
                    actual_action in pred.predicted_action or
                    pred.predicted_action in actual_action):
                pred.was_correct = True
                self._accuracy.correct += 1
            elif time.time() - pred.created_at > 300:
                pred.was_correct = False
                self._accuracy.incorrect += 1

    def predict_next_action(self) -> Optional[Prediction]:
        history_list = [a for a, _ in self._action_history]
        if len(history_list) < self.MARKOV_ORDER:
            return None
        prev = tuple(history_list[-self.MARKOV_ORDER:])
        transitions = self._transitions.get(prev)
        if not transitions:
            prev_1 = (history_list[-1],)
            transitions = self._transitions.get(prev_1)
            if not transitions:
                return None
        total = sum(transitions.values())
        if total < self.MIN_PATTERN_COUNT:
            return None
        best_action = max(transitions, key=transitions.get)
        confidence = self._calibrate_confidence(transitions[best_action] / total)
        if confidence < 0.2:
            return None
        pred = Prediction(
            prediction_type=PredictionType.NEXT_ACTION,
            predicted_action=best_action,
            description=f"Based on your pattern, you'll likely: {best_action}",
            confidence=confidence,
            context={"previous": list(prev)},
            expires_at=time.time() + 600,
        )
        self._active_predictions.append(pred)
        self._accuracy.total_predictions += 1
        return pred

    def predict_time_routine(self) -> Optional[Prediction]:
        local = time.localtime()
        hour, day = local.tm_hour, local.tm_wday
        candidates = []
        for key in [(hour, day), (hour, -1)]:
            patterns = self._time_patterns.get(key, {})
            total = sum(patterns.values())
            if total >= self.MIN_PATTERN_COUNT:
                best = max(patterns, key=patterns.get)
                candidates.append((best, patterns[best] / total, total))
        if not candidates:
            return None
        best_action, confidence, total = max(candidates, key=lambda c: c[1])
        confidence = self._calibrate_confidence(confidence)
        if confidence < self.ROUTINE_CONFIDENCE_THRESHOLD:
            return None
        day_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day]
        pred = Prediction(
            prediction_type=PredictionType.TIME_ROUTINE,
            predicted_action=best_action,
            description=f"At {hour}:00 on {day_name}, you usually: {best_action}",
            confidence=confidence,
            context={"hour": hour, "day": day},
            expires_at=time.time() + 1800,
        )
        self._active_predictions.append(pred)
        self._accuracy.total_predictions += 1
        return pred

    def suggest_from_context(self, topic: str = "",
                              active_files: List[str] = None) -> List[Prediction]:
        suggestions = []
        if topic and topic in self._context_patterns:
            patterns = self._context_patterns[topic]
            total = sum(patterns.values())
            if total >= self.MIN_PATTERN_COUNT:
                for action, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:3]:
                    conf = self._calibrate_confidence(count / total)
                    if conf >= 0.3:
                        suggestions.append(Prediction(
                            prediction_type=PredictionType.CONTEXT_SUGGESTION,
                            predicted_action=action,
                            description=f"When working on '{topic}', you often: {action}",
                            confidence=conf,
                            context={"topic": topic},
                        ))
        return suggestions

    def generate_briefing(self) -> Prediction:
        parts = []
        time_pred = self.predict_time_routine()
        if time_pred:
            parts.append(f"🔮 {time_pred.description}")
        next_pred = self.predict_next_action()
        if next_pred:
            parts.append(f"📊 {next_pred.description}")
        acc = self._accuracy
        if acc.total_predictions > 10:
            parts.append(f"📈 Accuracy: {acc.accuracy:.0%} ({acc.correct}/{acc.correct + acc.incorrect})")
        dur = (time.time() - self._session_start) / 60
        if self._session_actions:
            parts.append(f"⏱️ Session: {dur:.0f}min, {len(self._session_actions)} actions")
        desc = "\n".join(parts) if parts else "No patterns learned yet."
        return Prediction(
            prediction_type=PredictionType.PROACTIVE_BRIEFING,
            predicted_action="briefing",
            description=desc,
            confidence=0.9,
        )

    def _calibrate_confidence(self, raw: float) -> float:
        acc = self._accuracy
        if acc.total_predictions < 10:
            return raw * 0.7
        return max(0.0, min(1.0, raw * 0.6 + acc.accuracy * 0.4))

    def get_active_predictions(self) -> List[Prediction]:
        return [p for p in self._active_predictions if not p.is_expired() and p.was_correct is None]

    def get_accuracy_stats(self) -> Dict[str, Any]:
        return {
            "total": self._accuracy.total_predictions,
            "correct": self._accuracy.correct,
            "incorrect": self._accuracy.incorrect,
            "accuracy": self._accuracy.accuracy,
            "pattern_count": len(self._transitions),
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "history_size": len(self._action_history),
            "active_predictions": len(self.get_active_predictions()),
            "accuracy": self.get_accuracy_stats(),
            "session_actions": len(self._session_actions),
        }

    def _save_patterns(self) -> None:
        path = self.data_dir / "patterns.json"
        try:
            data = {
                "transitions": {"|".join(k): dict(v) for k, v in self._transitions.items()},
                "time_patterns": {f"{h}:{d}": dict(v) for (h, d), v in self._time_patterns.items()},
                "context_patterns": {k: dict(v) for k, v in self._context_patterns.items()},
                "accuracy": {"total": self._accuracy.total_predictions, "correct": self._accuracy.correct, "incorrect": self._accuracy.incorrect},
            }
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"[PREDICT] Save failed: {e}")

    def _load_patterns(self) -> None:
        path = self.data_dir / "patterns.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for key_str, trans in data.get("transitions", {}).items():
                key = tuple(key_str.split("|"))
                for action, count in trans.items():
                    self._transitions[key][action] = count
            for key_str, pats in data.get("time_patterns", {}).items():
                h, d = key_str.split(":")
                for action, count in pats.items():
                    self._time_patterns[(int(h), int(d))][action] = count
            for topic, pats in data.get("context_patterns", {}).items():
                for action, count in pats.items():
                    self._context_patterns[topic][action] = count
            acc = data.get("accuracy", {})
            self._accuracy.total_predictions = acc.get("total", 0)
            self._accuracy.correct = acc.get("correct", 0)
            self._accuracy.incorrect = acc.get("incorrect", 0)
            logger.info(f"[PREDICT] Loaded {len(self._transitions)} transitions")
        except Exception as e:
            logger.warning(f"[PREDICT] Load failed: {e}")
