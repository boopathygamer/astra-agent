"""
Domain Expert System — Universal Multi-Domain AI Expertise.
───────────────────────────────────────────────────────────
10 domain experts that route user requests to specialized
knowledge and prompts. Each expert provides:
  - Domain-specific system prompt injection
  - Specialized reasoning templates
  - Recommended tools for the domain
  - Response formatting hints
"""

from agents.experts.router import DomainRouter, DomainMatch
from agents.experts.domains import (
    DomainExpert,
    DOMAIN_EXPERTS,
    get_expert,
    list_experts,
)

__all__ = [
    "DomainRouter",
    "DomainMatch",
    "DomainExpert",
    "DOMAIN_EXPERTS",
    "get_expert",
    "list_experts",
]
