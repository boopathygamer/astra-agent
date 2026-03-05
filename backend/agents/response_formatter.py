"""
Smart Response Formatter — Adaptive Output Formatting.
──────────────────────────────────────────────────────
Formats agent responses based on domain + persona:
  - Structured headers for complex topics
  - Tables for comparisons
  - Bullet points for lists
  - Code blocks only when relevant
  - TL;DR summaries for long answers
  - Emoji section markers
  - Disclaimer injection for sensitive domains
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FormatConfig:
    """Configuration for response formatting."""
    use_headers: bool = True
    use_emojis: bool = True
    use_tables: bool = True
    add_tldr: bool = False         # Add TL;DR for long responses
    max_length: int = 0            # 0 = no limit
    add_disclaimer: str = ""       # Domain-specific disclaimer
    add_sources_note: bool = False
    section_style: str = "emoji"   # emoji, numbered, plain


# Domain-specific format presets
DOMAIN_FORMATS: Dict[str, FormatConfig] = {
    "code": FormatConfig(
        use_headers=True, use_emojis=False, use_tables=False,
        section_style="plain",
    ),
    "writing": FormatConfig(
        use_headers=True, use_emojis=False, use_tables=False,
        section_style="plain",
    ),
    "math": FormatConfig(
        use_headers=True, use_emojis=True, use_tables=True,
        section_style="numbered",
    ),
    "business": FormatConfig(
        use_headers=True, use_emojis=True, use_tables=True,
        add_tldr=True, section_style="emoji",
    ),
    "creative": FormatConfig(
        use_headers=True, use_emojis=True, use_tables=False,
        section_style="emoji",
    ),
    "education": FormatConfig(
        use_headers=True, use_emojis=True, use_tables=True,
        section_style="emoji",
    ),
    "health": FormatConfig(
        use_headers=True, use_emojis=True, use_tables=True,
        add_disclaimer="⚕️ *This is general wellness information, not medical advice. Please consult a healthcare professional for personal health decisions.*",
        section_style="emoji",
    ),
    "legal": FormatConfig(
        use_headers=True, use_emojis=False, use_tables=True,
        add_disclaimer="⚖️ *This is general legal information for educational purposes only. It does not constitute legal advice. Please consult a licensed attorney for your specific situation.*",
        section_style="plain",
    ),
    "data": FormatConfig(
        use_headers=True, use_emojis=True, use_tables=True,
        add_tldr=True, section_style="emoji",
    ),
    "lifestyle": FormatConfig(
        use_headers=True, use_emojis=True, use_tables=True,
        section_style="emoji",
    ),
    "general": FormatConfig(
        use_headers=True, use_emojis=True, use_tables=True,
        section_style="emoji",
    ),
}


class ResponseFormatter:
    """
    Formats agent responses to be clear, structured, and
    appropriate for the domain and user persona.

    Features:
      - Domain-aware formatting (code vs business vs education)
      - Persona-aware detail levels
      - Auto-inject disclaimers for sensitive domains
      - TL;DR generation for long responses
      - Consistent section styling
    """

    def __init__(self):
        logger.info("ResponseFormatter initialized")

    def format(
        self,
        response: str,
        domain: str = "general",
        persona: str = "default",
    ) -> str:
        """
        Format a response for the given domain and persona.

        Args:
            response: Raw response text
            domain: Current domain
            persona: Current persona

        Returns:
            Formatted response string
        """
        config = DOMAIN_FORMATS.get(domain, DOMAIN_FORMATS["general"])

        formatted = response

        # Add TL;DR for long business/data responses
        if config.add_tldr and len(response) > 800:
            formatted = self._add_tldr(formatted)

        # Add disclaimer for sensitive domains
        if config.add_disclaimer:
            formatted = self._add_disclaimer(formatted, config.add_disclaimer)

        return formatted

    def build_structured_response(
        self,
        sections: Dict[str, str],
        domain: str = "general",
        title: str = "",
    ) -> str:
        """
        Build a well-structured response from sections.

        Args:
            sections: Dict of section_name → content
            domain: Current domain for formatting
            title: Optional title

        Returns:
            Formatted markdown response
        """
        config = DOMAIN_FORMATS.get(domain, DOMAIN_FORMATS["general"])
        parts = []

        if title:
            parts.append(f"## {title}\n")

        section_emojis = {
            "summary": "📌", "overview": "📌", "tldr": "⚡",
            "steps": "📝", "process": "📝", "how to": "📝",
            "example": "💡", "examples": "💡",
            "tips": "✨", "best practices": "✨",
            "warning": "⚠️", "caution": "⚠️",
            "resources": "📚", "references": "📚",
            "next steps": "➡️", "action items": "➡️",
            "conclusion": "🎯", "result": "🎯",
        }

        for name, content in sections.items():
            if config.section_style == "emoji" and config.use_emojis:
                emoji = section_emojis.get(name.lower(), "▸")
                parts.append(f"### {emoji} {name.title()}\n{content}\n")
            elif config.section_style == "numbered":
                idx = len(parts)
                parts.append(f"### {idx}. {name.title()}\n{content}\n")
            else:
                parts.append(f"### {name.title()}\n{content}\n")

        return "\n".join(parts)

    def format_comparison(
        self,
        item_a: str,
        item_b: str,
        dimensions: Dict[str, tuple],
    ) -> str:
        """
        Format a comparison table.

        Args:
            item_a: First item name
            item_b: Second item name
            dimensions: Dict of dimension → (value_a, value_b)
        """
        lines = [
            f"| **Dimension** | **{item_a}** | **{item_b}** |",
            "|:---|:---|:---|",
        ]
        for dim, (val_a, val_b) in dimensions.items():
            lines.append(f"| {dim} | {val_a} | {val_b} |")
        return "\n".join(lines)

    def format_action_items(self, items: List[Dict[str, str]]) -> str:
        """Format a list of action items with priorities."""
        lines = ["### ➡️ Action Items\n"]
        for item in items:
            priority = item.get("priority", "")
            owner = item.get("owner", "")
            title = item.get("title", "")
            deadline = item.get("deadline", "")

            line = f"- [ ] **{title}**"
            if priority:
                line += f" [{priority}]"
            if owner:
                line += f" → {owner}"
            if deadline:
                line += f" (by {deadline})"
            lines.append(line)

        return "\n".join(lines)

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _add_tldr(self, text: str) -> str:
        """Add a TL;DR note at the top for long responses."""
        # Extract first meaningful sentence as TL;DR
        sentences = re.split(r'[.!?]\s', text)
        if sentences:
            tldr = sentences[0].strip()
            if len(tldr) > 20:
                return f"**⚡ TL;DR:** {tldr}.\n\n---\n\n{text}"
        return text

    def _add_disclaimer(self, text: str, disclaimer: str) -> str:
        """Add a disclaimer at the end."""
        return f"{text}\n\n---\n\n{disclaimer}"
