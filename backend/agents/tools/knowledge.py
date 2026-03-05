"""
Knowledge Retrieval Tool — Structured Knowledge Access.
────────────────────────────────────────────────────────
Provides structured answers for common knowledge queries:
  - Definitions and explanations
  - Comparisons between concepts
  - Quick facts and data
  - Topic summaries
  - Pro/con analysis

Works alongside web_search for real-time data.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeQuery:
    """A structured knowledge request."""
    query_type: str    # definition, comparison, facts, summary, pros_cons
    topic: str
    context: str = ""
    subtopics: List[str] = field(default_factory=list)


@dataclass
class KnowledgeResult:
    """Structured knowledge result."""
    query_type: str
    content: str
    structured_data: Dict[str, Any] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    confidence: float = 0.0


class KnowledgeEngine:
    """
    Structured knowledge retrieval that generates comprehensive,
    well-organized answers using the LLM.

    Provides templates for different query types:
    - Definitions: clear, multi-level explanations
    - Comparisons: structured side-by-side analysis
    - Facts: key data points about a topic
    - Summaries: concise topic overviews
    - Pros/cons: balanced analysis with recommendations
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self._generate = generate_fn
        self._cache: Dict[str, KnowledgeResult] = {}
        logger.info("KnowledgeEngine initialized")

    def query(self, query: str, query_type: str = "auto") -> KnowledgeResult:
        """
        Process a knowledge query.

        Args:
            query: The knowledge question
            query_type: Type of query (auto, definition, comparison, facts, summary, pros_cons)

        Returns:
            KnowledgeResult with structured content
        """
        # Auto-detect query type
        if query_type == "auto":
            query_type = self._detect_type(query)

        # Build structured prompt
        prompt = self._build_prompt(query, query_type)

        # Generate answer
        if self._generate:
            try:
                content = self._generate(prompt)
                result = KnowledgeResult(
                    query_type=query_type,
                    content=content,
                    confidence=0.8,
                )
                return result
            except Exception as e:
                logger.error(f"Knowledge generation failed: {e}")

        # Return prompt template as fallback
        return KnowledgeResult(
            query_type=query_type,
            content=prompt,
            confidence=0.0,
        )

    def _detect_type(self, query: str) -> str:
        """Auto-detect the type of knowledge query."""
        q = query.lower()

        if any(w in q for w in ["what is", "define", "definition", "meaning of", "what does"]):
            return "definition"
        if any(w in q for w in ["compare", "difference between", "vs", "versus", "compared to"]):
            return "comparison"
        if any(w in q for w in ["pros and cons", "advantages", "disadvantages", "benefits", "drawbacks"]):
            return "pros_cons"
        if any(w in q for w in ["facts about", "key facts", "tell me about", "overview"]):
            return "summary"
        return "facts"

    def _build_prompt(self, query: str, query_type: str) -> str:
        """Build a structured prompt for the query type."""
        prompts = {
            "definition": f"""\
Provide a clear, comprehensive definition for: {query}

Structure your response as:
1. **One-line definition**: A single clear sentence
2. **Detailed explanation**: 2-3 paragraphs explaining the concept
3. **Key characteristics**: Bullet points of the most important features
4. **Example**: A concrete real-world example
5. **Related concepts**: 3-5 related terms to explore further""",

            "comparison": f"""\
Provide a detailed comparison: {query}

Structure your response as:
1. **Overview**: Brief intro to both items being compared
2. **Comparison Table**: Key dimensions compared side by side
3. **Key Differences**: Most important distinguishing factors
4. **Key Similarities**: What they have in common
5. **When to use each**: Practical guidance on choosing
6. **Verdict**: Bottom-line recommendation""",

            "pros_cons": f"""\
Provide a balanced pros and cons analysis: {query}

Structure your response as:
1. **Overview**: Brief context about the topic
2. **Pros** (advantages/benefits): 4-6 clear advantages
3. **Cons** (disadvantages/drawbacks): 4-6 clear disadvantages
4. **Who it's best for**: Ideal users/situations
5. **Who should avoid it**: People/situations where it's not ideal
6. **Bottom line**: Balanced final assessment""",

            "summary": f"""\
Provide a comprehensive summary: {query}

Structure your response as:
1. **TL;DR**: 2-3 sentence overview
2. **Key Points**: 5-7 most important facts or ideas
3. **Background/History**: Brief relevant history
4. **Current State**: Where things stand today
5. **Key Takeaways**: What matters most
6. **Learn More**: Suggested topics for deeper exploration""",

            "facts": f"""\
Provide key facts and information about: {query}

Structure your response as:
1. **Quick Facts**: 5-8 important data points
2. **Detailed Information**: Fuller explanation of the topic
3. **Common Misconceptions**: Things people often get wrong
4. **Interesting Details**: Lesser-known facts
5. **Related Topics**: What to explore next""",
        }

        return prompts.get(query_type, prompts["facts"])

    def get_comparison_template(self, item_a: str, item_b: str) -> str:
        """Get a comparison template for two items."""
        return f"""\
| Dimension | {item_a} | {item_b} |
|-----------|----------|----------|
| **Definition** | ... | ... |
| **Key Strengths** | ... | ... |
| **Weaknesses** | ... | ... |
| **Best For** | ... | ... |
| **Cost** | ... | ... |
| **Ease of Use** | ... | ... |
| **Overall Rating** | ★★★★☆ | ★★★★☆ |"""
