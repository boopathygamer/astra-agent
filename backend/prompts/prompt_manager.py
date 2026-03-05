"""
Prompt Manager — Centralized Template Registry & Dynamic Formatting
═══════════════════════════════════════════════════════════════════
Replaces all scattered f-strings and hardcoded prompts throughout
the codebase with a single, versioned, auditable registry.

Features:
  - Template versioning with performance tracking
  - Dynamic variable injection with validation
  - Domain-specific prompt overrides
  - Chain-of-thought prompt construction
  - A/B testing support for prompt optimization
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Enums & Data Models
# ══════════════════════════════════════════════════════════════

class PromptCategory(str, Enum):
    SYSTEM = "system"
    REASONING = "reasoning"
    SYNTHESIS = "synthesis"
    VERIFICATION = "verification"
    TOOL_USE = "tool_use"
    DOMAIN_EXPERT = "domain_expert"
    ADVERSARIAL = "adversarial"
    REFLECTION = "reflection"
    DYNAMIC_EXPERT = "dynamic_expert"


@dataclass
class PromptTemplate:
    """A versioned, trackable prompt template."""
    name: str
    category: PromptCategory
    template: str
    version: int = 1
    variables: List[str] = field(default_factory=list)
    description: str = ""
    
    # Performance tracking
    use_count: int = 0
    avg_reward: float = 0.0
    _reward_sum: float = 0.0
    
    @property
    def template_hash(self) -> str:
        return hashlib.sha256(self.template.encode()).hexdigest()[:12]
    
    def render(self, **kwargs) -> str:
        """Render the template with variable substitution."""
        self.use_count += 1
        result = self.template
        for var in self.variables:
            placeholder = "{" + var + "}"
            if placeholder in result:
                value = kwargs.get(var, "")
                result = result.replace(placeholder, str(value))
        return result
    
    def record_reward(self, reward: float):
        """Track how well this prompt performed."""
        self._reward_sum += reward
        self.avg_reward = self._reward_sum / self.use_count if self.use_count > 0 else 0.0


@dataclass
class PromptChain:
    """A sequence of prompts that form a multi-step reasoning chain."""
    name: str
    steps: List[str]  # List of template names
    description: str = ""


# ══════════════════════════════════════════════════════════════
# Default Prompt Templates (Expert-Level)
# ══════════════════════════════════════════════════════════════

_DEFAULT_TEMPLATES: List[PromptTemplate] = [
    # ── System Prompts ──
    PromptTemplate(
        name="agent_system",
        category=PromptCategory.SYSTEM,
        template=(
            "You are a Universal Expert AI Agent with 10+ specialized subsystems.\n"
            "Your capabilities include: domain expertise ({domain}), "
            "advanced reasoning ({reasoning_strategy}), tool usage, "
            "code generation, and security analysis.\n\n"
            "Communication style: {persona}\n"
            "Active skills: {skills}\n\n"
            "Rules:\n"
            "1. Show your reasoning step by step\n"
            "2. Cite sources and evidence\n"
            "3. Flag uncertainty explicitly\n"
            "4. Never fabricate data or citations"
        ),
        variables=["domain", "reasoning_strategy", "persona", "skills"],
        description="Main system prompt for the agent controller",
    ),

    # ── Reasoning Prompts ──
    PromptTemplate(
        name="chain_of_thought",
        category=PromptCategory.REASONING,
        template=(
            "Approach this problem using structured chain-of-thought reasoning.\n\n"
            "Problem: {problem}\n\n"
            "Domain: {domain}\n"
            "Memory context: {memory_context}\n\n"
            "Think step by step:\n"
            "1. Identify the core question\n"
            "2. List relevant facts and constraints\n"
            "3. Consider multiple approaches\n"
            "4. Evaluate trade-offs\n"
            "5. Synthesize the best answer\n\n"
            "Show your complete reasoning chain."
        ),
        variables=["problem", "domain", "memory_context"],
        description="Standard chain-of-thought reasoning prompt",
    ),
    
    PromptTemplate(
        name="hypothesis_generation",
        category=PromptCategory.REASONING,
        template=(
            "Given this problem, generate {num_hypotheses} distinct hypotheses.\n\n"
            "Problem: {problem}\n"
            "Context: {context}\n\n"
            "For each hypothesis:\n"
            "- State the hypothesis clearly\n"
            "- Explain the reasoning\n"
            "- Assign a confidence level (0.0-1.0)\n"
            "- List potential weaknesses"
        ),
        variables=["problem", "context", "num_hypotheses"],
        description="Hypothesis generation for multi-hypothesis reasoning",
    ),

    # ── Synthesis Prompts ──
    PromptTemplate(
        name="candidate_synthesis",
        category=PromptCategory.SYNTHESIS,
        template=(
            "Synthesize the best possible response from these hypotheses.\n\n"
            "Problem: {problem}\n"
            "Hypotheses:\n{hypotheses}\n\n"
            "Requirements:\n"
            "- Combine the strongest elements from each hypothesis\n"
            "- Eliminate contradictions\n"
            "- Ensure factual accuracy\n"
            "- Provide a clear, actionable answer"
        ),
        variables=["problem", "hypotheses"],
        description="Synthesize candidate from multiple hypotheses",
    ),

    # ── Verification Prompts ──
    PromptTemplate(
        name="critic_verification",
        category=PromptCategory.VERIFICATION,
        template=(
            "You are a rigorous critic. Evaluate this candidate response.\n\n"
            "Original task: {task}\n"
            "Candidate: {candidate}\n\n"
            "Score on these dimensions (0.0-1.0):\n"
            "1. Correctness: Does it actually solve the problem?\n"
            "2. Completeness: Does it address all aspects?\n"
            "3. Clarity: Is it well-structured and clear?\n"
            "4. Safety: Are there any harmful implications?\n\n"
            "Format: JSON with keys 'correctness', 'completeness', 'clarity', 'safety', 'overall', 'issues'"
        ),
        variables=["task", "candidate"],
        description="Critic verification prompt for the verifier stack",
    ),

    # ── Tool Use Prompts ──
    PromptTemplate(
        name="tool_argument_extraction",
        category=PromptCategory.TOOL_USE,
        template=(
            "Extract the arguments for the '{tool_name}' tool from this request.\n\n"
            "Tool: {tool_name}\n"
            "Description: {tool_description}\n"
            "Parameters: {tool_parameters}\n\n"
            "User request: {user_input}\n\n"
            "Respond with ONLY a JSON object of parameters. Example:\n"
            '{{"param1": "value1"}}\n\n'
            "JSON:"
        ),
        variables=["tool_name", "tool_description", "tool_parameters", "user_input"],
        description="Extract tool arguments from user input",
    ),

    # ── Dynamic Expert Prompts ──
    PromptTemplate(
        name="dynamic_expert_generation",
        category=PromptCategory.DYNAMIC_EXPERT,
        template=(
            "The user has asked a question that does not fit into our standard domains.\n"
            "Question: {user_input}\n\n"
            "Act as a 'Domain Architect'. Create a specialized Expert System Prompt "
            "tailored to answer this kind of question.\n"
            "Respond ONLY with the system prompt, written in the first person "
            "('I am the Master [specialty]...'). "
            "Do not answer the user's question, just define the persona."
        ),
        variables=["user_input"],
        description="Generate dynamic domain expert for out-of-bounds topics",
    ),

    # ── Adversarial Testing Prompts ──
    PromptTemplate(
        name="red_team_attack",
        category=PromptCategory.ADVERSARIAL,
        template=(
            "You are a Red Team security tester. Generate {num_attacks} attack vectors "
            "targeting this vulnerability type: {vuln_type}\n\n"
            "Target system description: {system_desc}\n\n"
            "For each attack:\n"
            "- Describe the attack vector\n"
            "- Explain the expected impact\n"
            "- Rate severity (LOW/MEDIUM/HIGH/CRITICAL)\n"
            "- Suggest a mitigation"
        ),
        variables=["num_attacks", "vuln_type", "system_desc"],
        description="Red team attack generation for adversarial testing",
    ),

    # ── Reflection Prompts ──
    PromptTemplate(
        name="expert_reflection",
        category=PromptCategory.REFLECTION,
        template=(
            "Reflect on this successful solution and extract a reusable first principle.\n\n"
            "Problem: {problem}\n"
            "Solution: {solution}\n"
            "Domain: {domain}\n\n"
            "Extract:\n"
            "1. The core insight that made this solution work\n"
            "2. A generalizable principle (1-2 sentences)\n"
            "3. When this principle applies vs doesn't apply"
        ),
        variables=["problem", "solution", "domain"],
        description="Extract first principles from successful solutions",
    ),

    PromptTemplate(
        name="root_cause_analysis",
        category=PromptCategory.REFLECTION,
        template=(
            "Analyze why this solution failed and identify the root cause.\n\n"
            "Problem: {problem}\n"
            "Failed solution: {failed_solution}\n"
            "Verifier feedback: {verifier_feedback}\n\n"
            "Provide:\n"
            "1. The specific failure mode\n"
            "2. The root cause (not just symptoms)\n"
            "3. What information was missing\n"
            "4. Suggested fix approach"
        ),
        variables=["problem", "failed_solution", "verifier_feedback"],
        description="Root cause analysis for failed solutions",
    ),
]


# ══════════════════════════════════════════════════════════════
# Prompt Manager
# ══════════════════════════════════════════════════════════════

class PromptManager:
    """
    Centralized prompt template registry.
    
    Replaces all hardcoded f-strings with versioned, trackable,
    optimizable templates.
    """
    _instance = None
    
    @classmethod
    def get_instance(cls) -> "PromptManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}
        self._chains: Dict[str, PromptChain] = {}
        self._domain_overrides: Dict[str, Dict[str, PromptTemplate]] = {}
        
        # Load defaults
        for t in _DEFAULT_TEMPLATES:
            self.register(t)
    
    def register(self, template: PromptTemplate):
        """Register a new prompt template."""
        self._templates[template.name] = template
    
    def get(self, name: str, domain: str = None) -> Optional[PromptTemplate]:
        """
        Get a template by name, with optional domain-specific override.
        """
        # Check domain override first
        if domain and domain in self._domain_overrides:
            override = self._domain_overrides[domain].get(name)
            if override:
                return override
        return self._templates.get(name)
    
    def render(self, name: str, domain: str = None, **kwargs) -> str:
        """
        Render a template with variables.
        
        Args:
            name: Template name
            domain: Optional domain for domain-specific overrides
            **kwargs: Variables to inject
        """
        template = self.get(name, domain)
        if not template:
            logger.warning(f"Prompt template '{name}' not found, using raw fallback")
            return kwargs.get("problem", kwargs.get("user_input", ""))
        return template.render(**kwargs)
    
    def record_performance(self, name: str, reward: float, domain: str = None):
        """Record how well a prompt performed."""
        template = self.get(name, domain)
        if template:
            template.record_reward(reward)
    
    def set_domain_override(self, domain: str, template: PromptTemplate):
        """Set a domain-specific template override."""
        if domain not in self._domain_overrides:
            self._domain_overrides[domain] = {}
        self._domain_overrides[domain][template.name] = template
    
    def register_chain(self, chain: PromptChain):
        """Register a multi-step prompt chain."""
        self._chains[chain.name] = chain
    
    def render_chain(self, chain_name: str, domain: str = None, **kwargs) -> List[str]:
        """Render all prompts in a chain."""
        chain = self._chains.get(chain_name)
        if not chain:
            return []
        return [self.render(step, domain=domain, **kwargs) for step in chain.steps]
    
    def list_templates(self, category: PromptCategory = None) -> List[Dict[str, Any]]:
        """List all registered templates with stats."""
        result = []
        for name, t in self._templates.items():
            if category and t.category != category:
                continue
            result.append({
                "name": t.name,
                "category": t.category.value,
                "version": t.version,
                "hash": t.template_hash,
                "variables": t.variables,
                "use_count": t.use_count,
                "avg_reward": round(t.avg_reward, 3),
            })
        return result
    
    def get_best_template(self, category: PromptCategory, min_uses: int = 3) -> Optional[PromptTemplate]:
        """Get the best-performing template in a category based on average reward."""
        candidates = [
            t for t in self._templates.values()
            if t.category == category and t.use_count >= min_uses
        ]
        if not candidates:
            # Fallback to any template in the category
            candidates = [t for t in self._templates.values() if t.category == category]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t.avg_reward)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get prompt manager statistics."""
        by_category = {}
        total_uses = 0
        for t in self._templates.values():
            cat = t.category.value
            if cat not in by_category:
                by_category[cat] = {"count": 0, "total_uses": 0}
            by_category[cat]["count"] += 1
            by_category[cat]["total_uses"] += t.use_count
            total_uses += t.use_count
            
        return {
            "total_templates": len(self._templates),
            "total_chains": len(self._chains),
            "total_domain_overrides": sum(len(v) for v in self._domain_overrides.values()),
            "total_uses": total_uses,
            "by_category": by_category,
        }

    def export_json(self, filepath: str = None) -> str:
        """Export all templates as JSON for audit/versioning."""
        data = {
            "templates": {
                name: {
                    "name": t.name,
                    "category": t.category.value,
                    "version": t.version,
                    "hash": t.template_hash,
                    "template": t.template,
                    "variables": t.variables,
                    "use_count": t.use_count,
                    "avg_reward": round(t.avg_reward, 3),
                }
                for name, t in self._templates.items()
            },
            "stats": self.get_stats(),
        }
        output = json.dumps(data, indent=2)
        if filepath:
            Path(filepath).write_text(output)
        return output
