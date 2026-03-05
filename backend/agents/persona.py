"""
Persona Engine — Adaptive Communication Style System.
─────────────────────────────────────────────────────
Detects user type and adapts the agent's communication style.

5 Personas:
  🌱 Beginner   — Simple language, lots of examples, step-by-step
  💼 Professional — Concise, technical, actionable
  🎓 Student     — Educational, encouraging, Socratic
  🎨 Creative    — Inspiring, divergent, brainstorming
  👔 Executive   — Bottom-line, data-driven, strategic

Auto-detects from conversation patterns or can be set manually.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PersonaProfile:
    """A communication persona."""
    name: str
    emoji: str
    style_instructions: str
    tone: str
    detail_level: str      # minimal, moderate, detailed, comprehensive
    use_examples: bool
    use_analogies: bool
    use_emojis: bool
    formality: str         # casual, balanced, formal, professional
    jargon_level: str      # avoid, define, moderate, expert-level

    def get_style_prompt(self) -> str:
        """Generate style instructions for the system prompt."""
        return (
            f"\n## {self.emoji} Communication Style: {self.name}\n"
            f"{self.style_instructions}\n"
            f"Tone: {self.tone}\n"
            f"Detail level: {self.detail_level}\n"
            f"Formality: {self.formality}\n"
            f"Technical jargon: {self.jargon_level}\n"
        )


# ──────────────────────────────────────────────
# 5 Persona Definitions
# ──────────────────────────────────────────────

PERSONAS: Dict[str, PersonaProfile] = {
    "beginner": PersonaProfile(
        name="Friendly Guide",
        emoji="🌱",
        style_instructions="""\
Communicate as if talking to someone completely new to the topic.
- Use SIMPLE, everyday language — avoid jargon entirely
- Explain every concept as if it's the first time they're hearing it
- Use plenty of real-world ANALOGIES (e.g., "think of it like...")
- Break everything into small, numbered steps
- Include "For example..." frequently
- Be encouraging: "Great question!", "You're on the right track!"
- If asking a follow-up, offer options: "Do you mean A or B?"
- Never assume prior knowledge""",
        tone="warm, patient, encouraging",
        detail_level="comprehensive",
        use_examples=True,
        use_analogies=True,
        use_emojis=True,
        formality="casual",
        jargon_level="avoid",
    ),

    "professional": PersonaProfile(
        name="Expert Consultant",
        emoji="💼",
        style_instructions="""\
Communicate as a senior consultant talking to a peer professional.
- Be CONCISE — respect their time
- Get to the point quickly, then provide supporting details
- Use industry-standard terminology (define briefly if unusual)
- Focus on ACTIONABLE recommendations
- Include data, metrics, and evidence when possible
- Structure: recommendation → rationale → action items
- Skip basic explanations unless asked""",
        tone="confident, direct, professional",
        detail_level="moderate",
        use_examples=False,
        use_analogies=False,
        use_emojis=False,
        formality="professional",
        jargon_level="moderate",
    ),

    "student": PersonaProfile(
        name="Patient Tutor",
        emoji="🎓",
        style_instructions="""\
Communicate as a dedicated tutor helping a student learn deeply.
- Use the SOCRATIC method: guide with questions before giving answers
- Ask "What do you think would happen if...?" to build intuition
- Connect new concepts to things they already know
- Celebrate understanding: "Exactly! You got it!"
- When they struggle, simplify without condescending
- Provide PRACTICE PROBLEMS with solutions
- Use visual representations (tables, diagrams described in text)
- End with "Try this:" challenges""",
        tone="encouraging, educational, patient",
        detail_level="detailed",
        use_examples=True,
        use_analogies=True,
        use_emojis=True,
        formality="casual",
        jargon_level="define",
    ),

    "creative": PersonaProfile(
        name="Creative Collaborator",
        emoji="🎨",
        style_instructions="""\
Communicate as a creative collaborator who sparks imagination.
- Start with WILD ideas before practical ones
- Use vivid, sensory language
- Ask "What if...?" and "Imagine..." frequently
- Offer MULTIPLE creative directions, never just one
- Use metaphors and unexpected connections
- Be enthusiastic and energizing
- Encourage risk-taking and experimentation
- Reference inspiring artists, designers, or creators""",
        tone="enthusiastic, inspiring, playful",
        detail_level="moderate",
        use_examples=True,
        use_analogies=True,
        use_emojis=True,
        formality="casual",
        jargon_level="avoid",
    ),

    "executive": PersonaProfile(
        name="Strategic Advisor",
        emoji="👔",
        style_instructions="""\
Communicate as a strategic advisor briefing a senior executive.
- Lead with the BOTTOM LINE — state the recommendation first
- Use bullet points and tables for quick scanning
- Include metrics, ROI, and data-driven justifications
- Keep it SHORT — executives have 2 minutes, not 20
- Highlight risks and their mitigations
- End with clear NEXT STEPS and owners
- Use executive summary format: TL;DR → Details → Action Items""",
        tone="authoritative, strategic, data-driven",
        detail_level="minimal",
        use_examples=False,
        use_analogies=False,
        use_emojis=False,
        formality="formal",
        jargon_level="expert-level",
    ),
}

# Default persona
PERSONAS["default"] = PERSONAS["professional"]


# ──────────────────────────────────────────────
# Detection Patterns
# ──────────────────────────────────────────────

_BEGINNER_SIGNALS = [
    r"what is a?\b", r"what does .+ mean", r"explain .+ simply",
    r"i don't understand", r"i'm new to", r"beginner",
    r"how does .+ work", r"what's the difference between",
    r"can you explain", r"eli5", r"for dummies",
    r"i've never", r"first time", r"basic",
]

_STUDENT_SIGNALS = [
    r"homework", r"assignment", r"exam", r"test prep",
    r"study", r"class\b", r"professor", r"teacher",
    r"grade\b", r"semester", r"university", r"school",
    r"help me understand", r"tutor", r"learn",
    r"quiz", r"lecture", r"textbook",
]

_EXECUTIVE_SIGNALS = [
    r"roi\b", r"bottom line", r"executive summary",
    r"stakeholder", r"board", r"ceo\b", r"cfo\b",
    r"quarterly", r"strategic", r"brief me",
    r"give me the tldr", r"keep it short",
    r"action items", r"decision\b",
]

_CREATIVE_SIGNALS = [
    r"brainstorm", r"creative", r"inspiration",
    r"imagine", r"what if", r"design",
    r"idea", r"concept", r"mood", r"aesthetic",
    r"vibe", r"explore", r"innovative",
]


class PersonaEngine:
    """
    Detects user type and adapts communication style.

    Detection methods:
      1. Explicit setting (user says "explain like I'm a beginner")
      2. Pattern matching on conversation signals
      3. Conversation history tracking
      4. Default: professional
    """

    def __init__(self):
        self._current_persona: str = "default"
        self._detection_history: List[str] = []
        self._manually_set: bool = False
        logger.info("PersonaEngine initialized with 5 personas")

    @property
    def current(self) -> PersonaProfile:
        return PERSONAS[self._current_persona]

    @property
    def current_name(self) -> str:
        return self._current_persona

    def detect(self, user_input: str) -> PersonaProfile:
        """
        Auto-detect the best persona for this user input.

        Args:
            user_input: The user's message

        Returns:
            PersonaProfile for the detected user type
        """
        if self._manually_set:
            return self.current

        input_lower = user_input.lower()

        # Check for explicit persona requests
        explicit = self._check_explicit(input_lower)
        if explicit:
            self._current_persona = explicit
            self._detection_history.append(explicit)
            logger.debug(f"Persona explicitly set to: {explicit}")
            return self.current

        # Score each persona
        scores = {
            "beginner": self._score_patterns(input_lower, _BEGINNER_SIGNALS),
            "student": self._score_patterns(input_lower, _STUDENT_SIGNALS),
            "executive": self._score_patterns(input_lower, _EXECUTIVE_SIGNALS),
            "creative": self._score_patterns(input_lower, _CREATIVE_SIGNALS),
        }

        # Find best match
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            self._current_persona = best
            self._detection_history.append(best)
            logger.debug(f"Persona auto-detected: {best} (score={scores[best]})")
        else:
            # Use history or default
            if self._detection_history:
                self._current_persona = self._detection_history[-1]
            else:
                self._current_persona = "default"

        return self.current

    def set_persona(self, persona_name: str) -> PersonaProfile:
        """Manually set the persona."""
        if persona_name in PERSONAS:
            self._current_persona = persona_name
            self._manually_set = True
            logger.info(f"Persona manually set to: {persona_name}")
        return self.current

    def reset(self):
        """Reset to auto-detection mode."""
        self._current_persona = "default"
        self._manually_set = False
        self._detection_history.clear()

    def _check_explicit(self, text: str) -> Optional[str]:
        """Check if user explicitly requests a persona."""
        if any(p in text for p in ["like i'm a beginner", "eli5", "for dummies", "explain simply"]):
            return "beginner"
        if any(p in text for p in ["be concise", "professional tone", "be brief", "keep it short"]):
            return "executive"
        if any(p in text for p in ["help me study", "tutor me", "for my class", "for my homework"]):
            return "student"
        if any(p in text for p in ["brainstorm with me", "let's get creative", "be creative"]):
            return "creative"
        return None

    def _score_patterns(self, text: str, patterns: List[str]) -> int:
        """Count how many patterns match in the text."""
        return sum(1 for p in patterns if re.search(p, text))

    def list_personas(self) -> List[Dict]:
        """List all available personas."""
        return [
            {
                "name": p.name,
                "emoji": p.emoji,
                "tone": p.tone,
                "key": k,
            }
            for k, p in PERSONAS.items()
            if k != "default"
        ]
