"""
Advanced Reasoning Engine — Multi-Strategy Intelligent Reasoning.
─────────────────────────────────────────────────────────────────
4 reasoning strategies that the agent auto-selects based on problem type:

  1. Chain-of-Thought  — Sequential step-by-step reasoning
  2. Tree-of-Thought   — Branch multiple approaches, evaluate each
  3. Analogy Reasoning  — Map to known concepts, transfer understanding
  4. Socratic Method    — Guide through questions, promote discovery

Surpasses basic CoT by dynamically choosing the best strategy.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class ReasoningStrategy(Enum):
    """Available reasoning strategies."""
    CHAIN_OF_THOUGHT = "chain_of_thought"
    TREE_OF_THOUGHT = "tree_of_thought"
    ANALOGY = "analogy"
    SOCRATIC = "socratic"
    DIRECT = "direct"          # Simple questions, no deep reasoning needed


@dataclass
class ReasoningStep:
    """A single step in the reasoning process."""
    step_number: int = 0
    strategy: str = ""
    thought: str = ""
    conclusion: str = ""
    confidence: float = 0.0


@dataclass
class ReasoningResult:
    """Complete result of the reasoning process."""
    strategy_used: ReasoningStrategy = ReasoningStrategy.DIRECT
    steps: List[ReasoningStep] = field(default_factory=list)
    final_answer: str = ""
    alternatives_considered: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning_prompt: str = ""   # The prompt built for the LLM

    def get_thinking_display(self) -> str:
        """Get a human-readable display of the thinking process."""
        lines = [f"🧠 Strategy: {self.strategy_used.value}"]
        for step in self.steps:
            lines.append(f"  Step {step.step_number}: {step.thought}")
            if step.conclusion:
                lines.append(f"    → {step.conclusion}")
        if self.alternatives_considered:
            lines.append(f"  Alternatives: {', '.join(self.alternatives_considered)}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Strategy Prompts
# ──────────────────────────────────────────────

CHAIN_OF_THOUGHT_PROMPT = """\
Think through this step-by-step. For each step, explain your reasoning clearly.

QUESTION: {question}

{domain_context}

Instructions:
1. Break the problem into logical steps
2. Show your work at each step
3. State any assumptions you make
4. Arrive at a clear conclusion

Think step by step:

Step 1: """

TREE_OF_THOUGHT_PROMPT = """\
Consider multiple approaches to this problem. Evaluate each before choosing the best one.

QUESTION: {question}

{domain_context}

Instructions:
1. Identify 2-3 different approaches to solve this
2. For each approach, briefly outline the method and trade-offs
3. Evaluate which approach is best and WHY
4. Execute the best approach in detail

APPROACH A: [name]
Method: [brief outline]
Pros: [advantages]
Cons: [drawbacks]

APPROACH B: [name]
Method: [brief outline]
Pros: [advantages]
Cons: [drawbacks]

BEST APPROACH: [which one and why]

SOLUTION: """

ANALOGY_PROMPT = """\
Explain this concept by connecting it to something familiar.

QUESTION: {question}

{domain_context}

Instructions:
1. Identify the core concept that needs explaining
2. Find a familiar real-world ANALOGY that maps to it
3. Explain the analogy: "Think of it like..."
4. Map the analogy's components to the actual concept
5. Note where the analogy breaks down (its limitations)

THE CONCEPT: [what we're explaining]

THE ANALOGY: Think of it like...

HOW IT MAPS:
- [analogy part 1] → [concept part 1]
- [analogy part 2] → [concept part 2]

WHERE THE ANALOGY BREAKS DOWN: [limitations]

FULL EXPLANATION: """

SOCRATIC_PROMPT = """\
Guide the user to discover the answer through thoughtful questions.
Do NOT give the answer directly — help them think it through.

QUESTION: {question}

{domain_context}

Instructions:
1. Acknowledge what the user already knows
2. Ask a guiding question that leads toward understanding
3. If they seem stuck, ask a simpler sub-question
4. Build understanding incrementally through dialogue
5. Only reveal the answer after guiding them close to it

SOCRATIC DIALOGUE:

What you already seem to understand: [acknowledge their knowledge]

Let me ask you this: [guiding question]

Think about: [hint or sub-question]

Here's a clue: [partial insight]

The key insight is: """


# ──────────────────────────────────────────────
# Strategy Selection Patterns
# ──────────────────────────────────────────────

# Keywords that signal which strategy to use
_STRATEGY_SIGNALS: Dict[ReasoningStrategy, List[str]] = {
    ReasoningStrategy.CHAIN_OF_THOUGHT: [
        "how to", "step by step", "walk me through", "process",
        "calculate", "solve", "derive", "prove", "debug",
        "what happens when", "troubleshoot", "diagnose",
    ],
    ReasoningStrategy.TREE_OF_THOUGHT: [
        "best approach", "compare", "which is better", "pros and cons",
        "trade-offs", "alternatives", "should i", "options",
        "evaluate", "decide", "choose between", "recommend",
    ],
    ReasoningStrategy.ANALOGY: [
        "explain", "what is", "eli5", "like i'm", "simply",
        "analogy", "metaphor", "in simple terms", "for dummies",
        "help me understand", "concept", "intuition",
    ],
    ReasoningStrategy.SOCRATIC: [
        "teach me", "tutor", "help me learn", "homework",
        "why does", "how does", "study", "understand",
        "quiz me", "test me", "practice",
    ],
}

# Questions that are too simple for deep reasoning
_DIRECT_PATTERNS = [
    r"^(hi|hello|hey|thanks|thank you|ok|yes|no|sure)\b",
    r"^what time", r"^what date", r"^who is",
    r"^translate", r"^define\b",
]


# ──────────────────────────────────────────────
# Advanced Reasoner Engine
# ──────────────────────────────────────────────

class AdvancedReasoner:
    """
    Multi-strategy reasoning engine that auto-selects the best
    reasoning approach based on the problem type.

    4 Strategies:
      - Chain-of-Thought: step-by-step for procedural problems
      - Tree-of-Thought: branching for decision problems
      - Analogy: mapping to familiar concepts for explanation
      - Socratic: questioning for teaching/learning

    Usage:
        reasoner = AdvancedReasoner()
        result = reasoner.reason("How do I sort a list?", domain="code")
        print(result.reasoning_prompt)  # Enhanced prompt for the LLM
    """

    def __init__(self):
        self._usage_stats: Dict[str, int] = {s.value: 0 for s in ReasoningStrategy}
        logger.info("AdvancedReasoner initialized with 4 strategies")

    def select_strategy(
        self,
        user_input: str,
        domain: str = "general",
        persona: str = "default",
    ) -> ReasoningStrategy:
        """
        Auto-select the best reasoning strategy.

        Args:
            user_input: The user's question/request
            domain: Current domain (from domain router)
            persona: Current persona (from persona engine)

        Returns:
            Best ReasoningStrategy for this input
        """
        input_lower = user_input.lower()

        # Check if it's too simple for deep reasoning
        for pattern in _DIRECT_PATTERNS:
            if re.search(pattern, input_lower):
                return ReasoningStrategy.DIRECT

        # Persona overrides
        if persona == "student":
            # Students benefit from Socratic method
            return ReasoningStrategy.SOCRATIC
        if persona == "beginner":
            # Beginners benefit from analogies
            return ReasoningStrategy.ANALOGY

        # Score each strategy based on keyword signals
        scores: Dict[ReasoningStrategy, int] = {}
        for strategy, keywords in _STRATEGY_SIGNALS.items():
            score = sum(1 for kw in keywords if kw in input_lower)
            scores[strategy] = score

        # Domain-based defaults
        domain_defaults = {
            "math": ReasoningStrategy.CHAIN_OF_THOUGHT,
            "code": ReasoningStrategy.CHAIN_OF_THOUGHT,
            "education": ReasoningStrategy.SOCRATIC,
            "business": ReasoningStrategy.TREE_OF_THOUGHT,
            "creative": ReasoningStrategy.TREE_OF_THOUGHT,
        }

        # Find best strategy
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best

        # Fall back to domain default
        if domain in domain_defaults:
            return domain_defaults[domain]

        return ReasoningStrategy.CHAIN_OF_THOUGHT

    def build_reasoning_prompt(
        self,
        user_input: str,
        strategy: ReasoningStrategy,
        domain_context: str = "",
    ) -> str:
        """
        Build an enhanced prompt with the selected reasoning strategy.

        Args:
            user_input: The user's question
            strategy: Selected reasoning strategy
            domain_context: Domain expert injection

        Returns:
            Enhanced prompt string for the LLM
        """
        if strategy == ReasoningStrategy.DIRECT:
            return user_input

        templates = {
            ReasoningStrategy.CHAIN_OF_THOUGHT: CHAIN_OF_THOUGHT_PROMPT,
            ReasoningStrategy.TREE_OF_THOUGHT: TREE_OF_THOUGHT_PROMPT,
            ReasoningStrategy.ANALOGY: ANALOGY_PROMPT,
            ReasoningStrategy.SOCRATIC: SOCRATIC_PROMPT,
        }

        template = templates.get(strategy, CHAIN_OF_THOUGHT_PROMPT)
        prompt = template.format(
            question=user_input,
            domain_context=domain_context,
        )

        self._usage_stats[strategy.value] += 1
        return prompt

    def reason(
        self,
        user_input: str,
        domain: str = "general",
        persona: str = "default",
        domain_context: str = "",
    ) -> ReasoningResult:
        """
        Full reasoning pipeline: select strategy → build prompt.

        Args:
            user_input: The user's question
            domain: Current domain
            persona: Current persona
            domain_context: Expert context

        Returns:
            ReasoningResult with strategy and enhanced prompt
        """
        strategy = self.select_strategy(user_input, domain, persona)
        prompt = self.build_reasoning_prompt(user_input, strategy, domain_context)

        result = ReasoningResult(
            strategy_used=strategy,
            reasoning_prompt=prompt,
            steps=[ReasoningStep(
                step_number=1,
                strategy=strategy.value,
                thought=f"Selected {strategy.value} strategy for this problem",
            )],
        )

        logger.debug(f"Reasoning strategy: {strategy.value} for domain={domain}")
        return result

    def get_stats(self) -> dict:
        """Get strategy usage statistics."""
        return dict(self._usage_stats)
