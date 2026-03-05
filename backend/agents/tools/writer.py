"""
Writing Assistant Tool — Professional Text Transformation.
───────────────────────────────────────────────────────────
Helps ALL users with writing tasks:
  - Grammar and style checking
  - Tone adjustment (formal, casual, etc.)
  - Summarization (long text → key points)
  - Email drafting from bullet points
  - Content structuring
  - Readability analysis
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WritingAnalysis:
    """Analysis of a piece of text."""
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    avg_words_per_sentence: float = 0.0
    readability_score: str = ""     # easy, moderate, difficult
    readability_grade: str = ""     # grade level estimate
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    tone: str = ""                  # detected tone


class WritingAssistant:
    """
    Professional writing tool for all users.

    Capabilities:
      - Analyze text quality and readability
      - Detect and suggest fixes for common issues
      - Adjust tone (formal ↔ casual ↔ professional)
      - Generate structured content from notes
      - Summarize long text
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self._generate = generate_fn
        logger.info("WritingAssistant initialized")

    # ──────────────────────────────────────────
    # Text Analysis
    # ──────────────────────────────────────────

    def analyze(self, text: str) -> WritingAnalysis:
        """
        Analyze text for readability, style, and common issues.

        Returns comprehensive writing analysis with suggestions.
        """
        # Basic metrics
        words = text.split()
        word_count = len(words)
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        sentence_count = max(len(sentences), 1)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        paragraph_count = max(len(paragraphs), 1)
        avg_words = word_count / sentence_count

        # Readability (simplified Flesch-Kincaid approximation)
        if avg_words <= 12:
            readability = "easy"
            grade = "5th-8th grade"
        elif avg_words <= 18:
            readability = "moderate"
            grade = "9th-12th grade"
        else:
            readability = "difficult"
            grade = "College level+"

        # Check for common issues
        issues = []
        suggestions = []

        # Passive voice detection (simplified)
        passive_patterns = [
            r'\b(is|are|was|were|been|being)\s+\w+ed\b',
            r'\b(is|are|was|were|been|being)\s+\w+en\b',
        ]
        passive_count = sum(
            len(re.findall(p, text, re.IGNORECASE))
            for p in passive_patterns
        )
        if passive_count > sentence_count * 0.3:
            issues.append(f"High passive voice usage ({passive_count} instances)")
            suggestions.append("Convert passive phrases to active voice for stronger prose")

        # Long sentences
        long_sentences = [s for s in sentences if len(s.split()) > 30]
        if long_sentences:
            issues.append(f"{len(long_sentences)} sentences are too long (>30 words)")
            suggestions.append("Split long sentences for better readability")

        # Repeated words (within proximity)
        word_freq = {}
        for w in words:
            w_lower = w.lower().strip('.,!?;:')
            if len(w_lower) > 4:  # Skip short common words
                word_freq[w_lower] = word_freq.get(w_lower, 0) + 1
        repeated = {w: c for w, c in word_freq.items() if c >= 4}
        if repeated:
            top_repeated = sorted(repeated.items(), key=lambda x: x[1], reverse=True)[:3]
            issues.append(f"Frequently repeated words: {', '.join(f'{w} ({c}x)' for w, c in top_repeated)}")
            suggestions.append("Use synonyms to add variety")

        # Very short paragraphs
        short_paras = [p for p in paragraphs if len(p.split()) < 10]
        if len(short_paras) > paragraph_count * 0.5 and paragraph_count > 2:
            issues.append("Many very short paragraphs — consider combining related ideas")

        # Sentence starters variety
        if sentence_count > 3:
            starters = [s.split()[0].lower() for s in sentences if s.split()]
            starter_freq = {}
            for s in starters:
                starter_freq[s] = starter_freq.get(s, 0) + 1
            repetitive_starts = {s: c for s, c in starter_freq.items() if c >= 3}
            if repetitive_starts:
                suggestions.append("Vary your sentence openings for better flow")

        # Detect tone
        tone = self._detect_tone(text)

        if not issues:
            suggestions.append("Text looks well-written! Consider reading it aloud for final polish.")

        return WritingAnalysis(
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            avg_words_per_sentence=round(avg_words, 1),
            readability_score=readability,
            readability_grade=grade,
            issues=issues,
            suggestions=suggestions,
            tone=tone,
        )

    # ──────────────────────────────────────────
    # Tone Adjustment
    # ──────────────────────────────────────────

    def adjust_tone(self, text: str, target_tone: str) -> str:
        """
        Generate a prompt to adjust the text's tone.

        Args:
            text: Original text
            target_tone: formal, casual, professional, friendly, academic

        Returns:
            Prompt for LLM to rewrite in target tone
        """
        tone_instructions = {
            "formal": "Use formal language, proper grammar, no contractions, academic vocabulary.",
            "casual": "Use conversational language, contractions OK, friendly and relaxed.",
            "professional": "Clear, concise, business-appropriate. Confident but not stiff.",
            "friendly": "Warm, approachable, use 'you' and 'we'. Encourage and engage.",
            "academic": "Scholarly, precise, cite-worthy. Use domain terminology appropriately.",
            "persuasive": "Compelling, action-oriented. Use power words and social proof.",
            "empathetic": "Understanding, compassionate. Acknowledge feelings and perspective.",
        }

        instructions = tone_instructions.get(target_tone, f"Write in a {target_tone} tone.")

        prompt = f"""\
Rewrite the following text to match a {target_tone.upper()} tone.

INSTRUCTIONS: {instructions}

ORIGINAL TEXT:
{text}

REWRITTEN ({target_tone} tone):"""

        if self._generate:
            try:
                return self._generate(prompt)
            except Exception as e:
                logger.error(f"Tone adjustment failed: {e}")

        return prompt

    # ──────────────────────────────────────────
    # Content Generation
    # ──────────────────────────────────────────

    def draft_email(self, bullet_points: List[str], tone: str = "professional", context: str = "") -> str:
        """Generate an email draft from bullet points."""
        points = "\n".join(f"- {p}" for p in bullet_points)
        prompt = f"""\
Write a {tone} email based on these key points:

{points}
{f'Context: {context}' if context else ''}

Include:
- Appropriate greeting
- Clear, well-structured body
- Professional closing
- Keep it concise (under 200 words if possible)

EMAIL DRAFT:"""

        if self._generate:
            try:
                return self._generate(prompt)
            except Exception as e:
                logger.error(f"Email draft failed: {e}")

        return prompt

    def summarize(self, text: str, style: str = "bullet_points", max_points: int = 5) -> str:
        """Summarize text in the requested style."""
        styles = {
            "bullet_points": f"Summarize in {max_points} concise bullet points",
            "one_paragraph": "Summarize in one clear paragraph (3-4 sentences)",
            "tldr": "Provide a TL;DR in 1-2 sentences",
            "executive": "Write an executive summary with Key Findings, Implications, and Recommended Actions",
        }
        instruction = styles.get(style, styles["bullet_points"])

        prompt = f"""\
{instruction}:

TEXT TO SUMMARIZE:
{text}

SUMMARY:"""

        if self._generate:
            try:
                return self._generate(prompt)
            except Exception as e:
                logger.error(f"Summarization failed: {e}")

        return prompt

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _detect_tone(self, text: str) -> str:
        """Detect the tone of text using simple heuristics."""
        text_lower = text.lower()

        # Check for informal markers
        informal = sum(1 for w in ["lol", "hey", "gonna", "wanna", "kinda", "btw", "tbh", "omg"]
                      if w in text_lower)

        # Check for formal markers
        formal = sum(1 for w in ["therefore", "furthermore", "consequently", "regarding",
                                  "pursuant", "herein", "accordingly"]
                    if w in text_lower)

        # Check for emotional words
        emotional = sum(1 for w in ["love", "hate", "amazing", "terrible", "incredible",
                                     "awful", "beautiful", "horrible"]
                       if w in text_lower)

        if formal >= 2:
            return "formal"
        if informal >= 2:
            return "casual"
        if emotional >= 2:
            return "emotional"
        if "?" in text and text.count("?") > 2:
            return "inquisitive"
        return "neutral"
