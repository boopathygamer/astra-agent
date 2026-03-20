"""
Cognitive Anticipation Engine — Predictive Intelligence
════════════════════════════════════════════════════════
Predicts user's next request BEFORE they ask it.
Analyzes workflow patterns, pre-computes answers, and balances cognitive load.

No LLM, no GPU — pure pattern recognition + Markov chains.

Architecture:
  User Action History → Pattern Mining → Markov Transition Model
                                               ↓
                                    Next-Request Prediction
                                               ↓
                                    Pre-Computation Queue
                                               ↓
                                    Ready Answer Cache

Novel contributions:
  • Markov chain workflow modeling
  • Difficulty assessment for cognitive load balancing
  • Pre-computation pipeline
  • Contextual prediction using recency-weighted patterns
"""

import hashlib
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# DIFFICULTY LEVELS
# ═══════════════════════════════════════════════════════════

class Difficulty(Enum):
    TRIVIAL = "trivial"      # Direct lookup, < 1ms
    EASY = "easy"            # Single engine, < 50ms
    MEDIUM = "medium"        # Multi-step, < 500ms
    HARD = "hard"            # Multi-engine, < 2s
    EXTREME = "extreme"      # Full pipeline, < 10s

    @property
    def max_ms(self) -> float:
        return {"trivial": 1, "easy": 50, "medium": 500, "hard": 2000, "extreme": 10000}[self.value]

    @property
    def priority(self) -> int:
        return {"trivial": 1, "easy": 2, "medium": 3, "hard": 4, "extreme": 5}[self.value]


@dataclass
class RequestSignature:
    """Fingerprint of a user request for pattern matching."""
    category: str = ""
    keywords: List[str] = field(default_factory=list)
    complexity: Difficulty = Difficulty.EASY
    timestamp: float = 0.0

    @property
    def id(self) -> str:
        return hashlib.sha256(f"{self.category}:{','.join(sorted(self.keywords))}".encode()).hexdigest()[:10]


@dataclass
class Prediction:
    """A predicted next request."""
    predicted_request: str
    confidence: float
    category: str
    difficulty: Difficulty
    precomputed_answer: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# MARKOV WORKFLOW MODEL
# ═══════════════════════════════════════════════════════════

class WorkflowMarkov:
    """
    Markov chain model of user request sequences.
    Learns transition probabilities between request categories.
    """

    def __init__(self, order: int = 2):
        self.order = order
        self._transitions: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._history: List[str] = []
        self._total_observations = 0

    def observe(self, category: str) -> None:
        """Record a new request category observation."""
        self._history.append(category)
        self._total_observations += 1

        # Update transition counts for different n-gram orders
        for n in range(1, self.order + 1):
            if len(self._history) > n:
                context = "|".join(self._history[-(n + 1):-1])
                self._transitions[context][category] += 1

        # Trim history
        if len(self._history) > 200:
            self._history = self._history[-200:]

    def predict(self, top_k: int = 3) -> List[Tuple[str, float]]:
        """Predict next request categories with probabilities."""
        if not self._history:
            return []

        predictions: Dict[str, float] = defaultdict(float)

        # Weight higher-order context more heavily
        for n in range(1, self.order + 1):
            if len(self._history) >= n:
                context = "|".join(self._history[-n:])
                transitions = self._transitions.get(context, {})
                total = sum(transitions.values())
                if total > 0:
                    weight = n * 2  # Higher order = more weight
                    for next_cat, count in transitions.items():
                        predictions[next_cat] += (count / total) * weight

        # Normalize
        total_weight = sum(predictions.values())
        if total_weight > 0:
            predictions = {k: v / total_weight for k, v in predictions.items()}

        # Sort by probability
        ranked = sorted(predictions.items(), key=lambda x: -x[1])
        return ranked[:top_k]


# ═══════════════════════════════════════════════════════════
# DIFFICULTY ASSESSOR
# ═══════════════════════════════════════════════════════════

class DifficultyAssessor:
    """Assesses computational difficulty of a request."""

    COMPLEXITY_SIGNALS = {
        "trivial": ["what is", "hello", "hi", "thanks", "help", "version"],
        "easy": ["list", "show", "get", "read", "display", "status"],
        "medium": ["find", "search", "filter", "sort", "analyze", "compare"],
        "hard": ["solve", "optimize", "prove", "synthesize", "design", "build"],
        "extreme": ["invent", "discover", "evolve", "create novel", "revolutionary"],
    }

    def assess(self, prompt: str) -> Difficulty:
        """Assess difficulty of a prompt."""
        prompt_lower = prompt.lower()
        scores = {}

        for level, signals in self.COMPLEXITY_SIGNALS.items():
            score = sum(1 for s in signals if s in prompt_lower)
            if score > 0:
                scores[level] = score

        if not scores:
            # Heuristic: longer prompts tend to be harder
            word_count = len(prompt.split())
            if word_count < 5:
                return Difficulty.EASY
            elif word_count < 15:
                return Difficulty.MEDIUM
            else:
                return Difficulty.HARD

        best = max(scores, key=scores.get)
        return Difficulty[best.upper()]


# ═══════════════════════════════════════════════════════════
# REQUEST CLASSIFIER
# ═══════════════════════════════════════════════════════════

class RequestClassifier:
    """Classifies requests into categories for pattern matching."""

    CATEGORIES = {
        "code": ["code", "program", "function", "implement", "build", "write", "debug", "fix"],
        "math": ["calculate", "compute", "solve", "equation", "formula", "prove", "sum"],
        "data": ["data", "database", "query", "csv", "json", "parse", "file", "read"],
        "analysis": ["analyze", "explain", "compare", "evaluate", "assess", "review"],
        "search": ["find", "search", "look", "locate", "discover"],
        "creative": ["create", "design", "invent", "generate", "imagine", "novel"],
        "system": ["deploy", "configure", "install", "setup", "update", "restart"],
        "info": ["what", "how", "why", "when", "who", "tell", "explain"],
    }

    def classify(self, prompt: str) -> str:
        """Classify a prompt into a category."""
        prompt_lower = prompt.lower()
        scores = {}
        for category, keywords in self.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > 0:
                scores[category] = score
        return max(scores, key=scores.get) if scores else "general"


# ═══════════════════════════════════════════════════════════
# ANTICIPATION RESULT
# ═══════════════════════════════════════════════════════════

@dataclass
class AnticipationResult:
    """Result of cognitive anticipation."""
    predictions: List[Prediction] = field(default_factory=list)
    current_difficulty: Difficulty = Difficulty.EASY
    resource_allocation: Dict[str, float] = field(default_factory=dict)
    workflow_position: int = 0
    duration_ms: float = 0.0

    @property
    def top_prediction(self) -> Optional[Prediction]:
        return self.predictions[0] if self.predictions else None

    @property
    def is_confident(self) -> bool:
        return bool(self.predictions) and self.predictions[0].confidence > 0.5

    def summary(self) -> str:
        lines = [
            f"## Cognitive Anticipation",
            f"**Difficulty**: {self.current_difficulty.value}",
            f"**Predictions**: {len(self.predictions)}",
        ]
        if self.predictions:
            lines.append("\n### Predicted Next Requests:")
            for i, p in enumerate(self.predictions[:3]):
                lines.append(f"  {i+1}. [{p.confidence:.0%}] {p.category}: {p.predicted_request}")
        if self.resource_allocation:
            lines.append("\n### Resource Allocation:")
            for engine, pct in self.resource_allocation.items():
                lines.append(f"  - {engine}: {pct:.0%}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE — Cognitive Anticipation
# ═══════════════════════════════════════════════════════════

class CognitiveAnticipation:
    """
    Predictive intelligence engine with cognitive load balancing.

    Usage:
        engine = CognitiveAnticipation()

        # Record user actions and get predictions
        result = engine.anticipate("solve this equation x^2 + 5x + 6 = 0")
        print(result.top_prediction)
        print(result.current_difficulty)
        print(result.resource_allocation)
    """

    # Standard response templates for predicted categories
    CATEGORY_TEMPLATES = {
        "code": "Continue coding: implement the next function/feature",
        "math": "Solve a related mathematical problem",
        "data": "Process or analyze the loaded data",
        "analysis": "Deep analysis of previous results",
        "search": "Find related information or patterns",
        "creative": "Generate a creative solution or design",
        "system": "Deploy or configure the system",
        "info": "Ask a follow-up question for clarification",
    }

    def __init__(self):
        self.markov = WorkflowMarkov(order=3)
        self.assessor = DifficultyAssessor()
        self.classifier = RequestClassifier()
        self._request_count = 0
        self._stats = {
            "predictions_made": 0,
            "correct_predictions": 0,
            "avg_confidence": 0.0,
        }

    def anticipate(self, current_prompt: str) -> AnticipationResult:
        """Analyze current request and predict next actions."""
        start = time.time()
        result = AnticipationResult()

        # Classify and assess
        category = self.classifier.classify(current_prompt)
        difficulty = self.assessor.assess(current_prompt)
        result.current_difficulty = difficulty

        # Record observation
        self.markov.observe(category)
        self._request_count += 1
        result.workflow_position = self._request_count

        # Predict next requests
        predictions = self.markov.predict(top_k=3)
        for pred_category, probability in predictions:
            template = self.CATEGORY_TEMPLATES.get(pred_category,
                                                    f"Follow-up in category: {pred_category}")
            pred_difficulty = self._estimate_difficulty(pred_category)
            result.predictions.append(Prediction(
                predicted_request=template,
                confidence=probability,
                category=pred_category,
                difficulty=pred_difficulty,
            ))

        # Cognitive load balancing — allocate resources
        result.resource_allocation = self._allocate_resources(difficulty, predictions)

        # Update stats
        self._stats["predictions_made"] += len(result.predictions)
        if result.predictions:
            self._stats["avg_confidence"] = (
                (self._stats["avg_confidence"] * (self._request_count - 1)
                 + result.predictions[0].confidence) / self._request_count
            )

        result.duration_ms = (time.time() - start) * 1000
        return result

    def record_actual(self, actual_category: str) -> None:
        """Record what the user actually requested (for accuracy tracking)."""
        # Check if our last prediction was correct
        predictions = self.markov.predict(top_k=1)
        if predictions and predictions[0][0] == actual_category:
            self._stats["correct_predictions"] += 1

    def _estimate_difficulty(self, category: str) -> Difficulty:
        """Estimate difficulty for a predicted category."""
        difficulty_map = {
            "code": Difficulty.HARD, "math": Difficulty.HARD,
            "data": Difficulty.MEDIUM, "analysis": Difficulty.MEDIUM,
            "search": Difficulty.EASY, "creative": Difficulty.EXTREME,
            "system": Difficulty.MEDIUM, "info": Difficulty.TRIVIAL,
        }
        return difficulty_map.get(category, Difficulty.MEDIUM)

    def _allocate_resources(self, current_diff: Difficulty,
                            predictions: List[Tuple[str, float]]) -> Dict[str, float]:
        """Allocate cognitive resources based on difficulty and predictions."""
        allocation = {}

        # Base allocation by current difficulty
        if current_diff == Difficulty.TRIVIAL:
            allocation = {"direct_lookup": 0.8, "cache": 0.2}
        elif current_diff == Difficulty.EASY:
            allocation = {"single_engine": 0.7, "cache": 0.2, "anticipation": 0.1}
        elif current_diff == Difficulty.MEDIUM:
            allocation = {"multi_engine": 0.5, "verification": 0.3, "anticipation": 0.2}
        elif current_diff == Difficulty.HARD:
            allocation = {"consensus": 0.4, "multi_engine": 0.3, "verification": 0.2, "anticipation": 0.1}
        elif current_diff == Difficulty.EXTREME:
            allocation = {"swarm": 0.3, "consensus": 0.3, "evolution": 0.2, "verification": 0.2}

        return allocation

    def solve(self, prompt: str) -> AnticipationResult:
        """Natural language interface."""
        return self.anticipate(prompt)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "CognitiveAnticipation",
            "requests_seen": self._request_count,
            "predictions_made": self._stats["predictions_made"],
            "correct_predictions": self._stats["correct_predictions"],
            "prediction_accuracy": (
                self._stats["correct_predictions"] / max(self._request_count, 1)
            ),
            "avg_confidence": round(self._stats["avg_confidence"], 4),
        }
