"""
Neural Symbiote Bridge — Human-AI Cognitive Fusion
══════════════════════════════════════════════════
Instead of request-response, create a shared cognitive space where the
system learns the user's thinking patterns, anticipates cognitive gaps,
and proactively fills them — becoming a cognitive extension of the human.

Architecture:
  User Interactions → Cognitive Profiler → Gap Detector
                            ↓                    ↓
                    Thinking Style Model   Proactive Insights
                            ↓                    ↓
                    Symbiotic Loop (merged AI + Human thinking)
"""

import hashlib
import logging
import math
import secrets
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CognitiveProfile:
    """Deep model of the user's knowledge and thinking style."""
    profile_id: str = ""
    expertise_domains: Dict[str, float] = field(default_factory=dict)    # domain → level (0-1)
    thinking_style: str = "balanced"      # analytical, creative, pragmatic, balanced
    vocabulary_level: float = 0.5
    avg_query_complexity: float = 0.5
    topics_explored: Set[str] = field(default_factory=set)
    knowledge_gaps: List[str] = field(default_factory=list)
    interaction_count: int = 0
    preferred_detail_level: str = "medium"    # brief, medium, detailed

    def __post_init__(self):
        if not self.profile_id:
            self.profile_id = secrets.token_hex(6)


@dataclass
class ProactiveInsight:
    """An unprompted insight generated for the user."""
    insight_id: str = ""
    content: str = ""
    reason: str = ""
    gap_filled: str = ""
    confidence: float = 0.0
    delivered: bool = False
    accepted: bool = False
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.insight_id:
            self.insight_id = secrets.token_hex(4)


@dataclass
class SymbioticState:
    """Current state of the human-AI symbiosis."""
    fusion_depth: float = 0.0          # 0 (stranger) → 1 (fully symbiotic)
    total_interactions: int = 0
    insights_generated: int = 0
    insights_accepted: int = 0
    gaps_filled: int = 0
    thinking_alignment: float = 0.0    # How aligned AI is with user's style
    proactive_accuracy: float = 0.0

    def summary(self) -> str:
        return (
            f"Symbiote: fusion={self.fusion_depth:.2f} | "
            f"{self.insights_accepted}/{self.insights_generated} insights accepted | "
            f"alignment={self.thinking_alignment:.2f}"
        )


class CognitiveProfiler:
    """Builds and maintains the user's cognitive profile."""

    ANALYTICAL_KEYWORDS = {"analyze", "compare", "logic", "evaluate", "measure", "data"}
    CREATIVE_KEYWORDS = {"design", "create", "imagine", "innovative", "novel", "brainstorm"}
    PRAGMATIC_KEYWORDS = {"implement", "fix", "build", "deploy", "optimize", "practical"}

    def __init__(self):
        self._profile = CognitiveProfile()
        self._query_history: deque = deque(maxlen=200)
        self._topic_frequency: Counter = Counter()

    def analyze_interaction(self, query: str, domain: str = "") -> CognitiveProfile:
        """Analyze a user interaction to update the cognitive profile."""
        self._profile.interaction_count += 1
        self._query_history.append(query)

        words = set(query.lower().split())
        word_count = len(words)

        # Update expertise domains
        if domain:
            current = self._profile.expertise_domains.get(domain, 0.0)
            self._profile.expertise_domains[domain] = min(1.0, current + 0.05)

        # Detect thinking style
        analytical = len(words & self.ANALYTICAL_KEYWORDS)
        creative = len(words & self.CREATIVE_KEYWORDS)
        pragmatic = len(words & self.PRAGMATIC_KEYWORDS)

        max_style = max(analytical, creative, pragmatic)
        if max_style > 0:
            if analytical == max_style:
                self._profile.thinking_style = "analytical"
            elif creative == max_style:
                self._profile.thinking_style = "creative"
            else:
                self._profile.thinking_style = "pragmatic"

        # Update vocabulary level
        unique_ratio = len(words) / max(word_count, 1)
        self._profile.vocabulary_level = (
            0.8 * self._profile.vocabulary_level + 0.2 * unique_ratio
        )

        # Update query complexity
        complexity = min(1.0, word_count / 50.0)
        self._profile.avg_query_complexity = (
            0.9 * self._profile.avg_query_complexity + 0.1 * complexity
        )

        # Track topics
        for word in words:
            if len(word) > 4:
                self._topic_frequency[word] += 1
                self._profile.topics_explored.add(word)

        # Detect detail preference
        if word_count < 10:
            self._profile.preferred_detail_level = "brief"
        elif word_count > 30:
            self._profile.preferred_detail_level = "detailed"
        else:
            self._profile.preferred_detail_level = "medium"

        return self._profile

    @property
    def profile(self) -> CognitiveProfile:
        return self._profile


class GapDetector:
    """Identifies knowledge gaps the user might have."""

    DOMAIN_PREREQUISITES: Dict[str, List[str]] = {
        "machine_learning": ["linear_algebra", "statistics", "python"],
        "web_development": ["html", "css", "javascript"],
        "databases": ["sql", "data_modeling"],
        "devops": ["linux", "networking", "containers"],
        "security": ["networking", "cryptography"],
    }

    def detect_gaps(self, profile: CognitiveProfile) -> List[str]:
        """Detect knowledge gaps based on what the user asks about."""
        gaps = []
        explored = {t.lower() for t in profile.topics_explored}

        for domain, prereqs in self.DOMAIN_PREREQUISITES.items():
            # Check if user explores advanced domain without prerequisites
            if any(kw in explored for kw in domain.split("_")):
                for prereq in prereqs:
                    if not any(p in explored for p in prereq.split("_")):
                        gaps.append(
                            f"You're exploring {domain} — you might benefit "
                            f"from reviewing {prereq}"
                        )

        # Detect repetitive questions (potential confusion)
        if len(profile.topics_explored) > 0:
            topic_list = list(profile.topics_explored)
            counter = Counter(topic_list)
            for topic, count in counter.most_common(3):
                if count > 3:
                    gaps.append(
                        f"You've asked about '{topic}' multiple times — "
                        f"would a comprehensive overview help?"
                    )

        return gaps[:5]


class NeuralSymbioteBridge:
    """
    Human-AI cognitive fusion system.

    Usage:
        bridge = NeuralSymbioteBridge()

        # Process user interaction
        bridge.interact("How do I implement a REST API?", domain="web_development")

        # Get proactive insights
        insights = bridge.generate_insights()
        for insight in insights:
            print(f"💡 {insight.content}")

        # Record feedback
        bridge.feedback(insight_id, accepted=True)

        # Check symbiosis state
        state = bridge.get_state()
    """

    def __init__(self):
        self._profiler = CognitiveProfiler()
        self._gap_detector = GapDetector()
        self._insights: Dict[str, ProactiveInsight] = {}
        self._total_interactions: int = 0

    def interact(self, query: str, domain: str = "") -> CognitiveProfile:
        """Process a user interaction to deepen the cognitive profile."""
        self._total_interactions += 1
        return self._profiler.analyze_interaction(query, domain)

    def generate_insights(self) -> List[ProactiveInsight]:
        """Generate proactive insights based on detected knowledge gaps."""
        profile = self._profiler.profile
        gaps = self._gap_detector.detect_gaps(profile)

        insights = []
        for gap_desc in gaps:
            insight = ProactiveInsight(
                content=gap_desc,
                reason="knowledge_gap",
                gap_filled=gap_desc.split("—")[0].strip() if "—" in gap_desc else gap_desc[:30],
                confidence=0.6,
            )
            self._insights[insight.insight_id] = insight
            insights.append(insight)

        # Style-based insights
        style = profile.thinking_style
        if style == "analytical" and profile.avg_query_complexity < 0.3:
            insight = ProactiveInsight(
                content="You have an analytical style — try framing more specific, measurable questions for better results.",
                reason="style_optimization",
                confidence=0.5,
            )
            self._insights[insight.insight_id] = insight
            insights.append(insight)

        return insights

    def feedback(self, insight_id: str, accepted: bool) -> None:
        """Record user feedback on a proactive insight."""
        insight = self._insights.get(insight_id)
        if insight:
            insight.delivered = True
            insight.accepted = accepted

    def get_state(self) -> SymbioticState:
        """Get the current symbiosis state."""
        profile = self._profiler.profile
        delivered = [i for i in self._insights.values() if i.delivered]
        accepted = [i for i in delivered if i.accepted]

        # Fusion depth based on interaction count (logarithmic approach)
        fusion = min(1.0, math.log1p(self._total_interactions) / 5.0)

        # Proactive accuracy
        accuracy = len(accepted) / max(len(delivered), 1)

        # Thinking alignment
        alignment = min(1.0, profile.interaction_count / 20.0)

        return SymbioticState(
            fusion_depth=round(fusion, 3),
            total_interactions=self._total_interactions,
            insights_generated=len(self._insights),
            insights_accepted=len(accepted),
            gaps_filled=len(accepted),
            thinking_alignment=round(alignment, 3),
            proactive_accuracy=round(accuracy, 3),
        )

    def get_stats(self) -> Dict[str, Any]:
        state = self.get_state()
        profile = self._profiler.profile
        return {
            "fusion_depth": state.fusion_depth,
            "interactions": state.total_interactions,
            "thinking_style": profile.thinking_style,
            "expertise_domains": len(profile.expertise_domains),
            "insights_generated": state.insights_generated,
            "insights_accepted": state.insights_accepted,
            "proactive_accuracy": state.proactive_accuracy,
            "knowledge_gaps": len(profile.knowledge_gaps),
        }
