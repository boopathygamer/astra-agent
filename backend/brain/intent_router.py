"""
Intent Router — Intelligent Query-to-System Classifier
───────────────────────────────────────────────────────
Classifies incoming chat messages to detect when a specialized
backend system/agent/tool should be activated instead of the
default AgentController chat pipeline.

Fast, deterministic keyword+regex matching (no LLM calls).

Supported Targets:
  orchestrator     → Multi-Agent Debate / Pipeline
  threat_scanner   → File/directory/URL scanning
  deep_researcher  → Deep web intelligence
  devops_reviewer  → CI/CD and DevOps fixes
  contract_hunter  → Legal contract auditing
  archivist        → Directory organization
  transpiler       → Code migration/transpilation
  evolution        → Code optimization via RLHF
  multimodal       → Image/PDF/audio analysis
  content_factory  → Content syndication
  devils_advocate  → Business plan critique
  tutor            → Socratic tutoring
  swarm            → Multi-agent swarm intelligence
  chat             → Default (no special routing)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """Result of intent classification."""
    target_system: str = "chat"
    confidence: float = 0.0
    display_name: str = ""
    display_emoji: str = "💬"
    extracted_params: Dict[str, str] = field(default_factory=dict)
    reasoning: str = ""


# ── Pattern Definitions ──────────────────────────
# Each entry: (compiled_regex, target_system, confidence, display_name, emoji)

_ROUTE_PATTERNS: List[Tuple[re.Pattern, str, float, str, str]] = []


def _p(pattern: str, target: str, confidence: float, name: str, emoji: str):
    """Register a routing pattern."""
    _ROUTE_PATTERNS.append((
        re.compile(pattern, re.IGNORECASE),
        target, confidence, name, emoji,
    ))


# ── Multi-Agent Orchestrator / Debate ──
_p(r'\b(?:debate|multi[- ]?agent|orchestrat|devil.?s\s*advocate)\b.*\b(?:pros?\s*(?:and|&|vs)\s*cons?|versus|compare|argue|discuss|analyze\s*both)', "orchestrator", 0.92, "Multi-Agent Debate", "🤝")
_p(r'\b(?:debate|multi[- ]?agent\s*debate)\b', "orchestrator", 0.85, "Multi-Agent Debate", "🤝")
_p(r'\b(?:orchestrat(?:e|ion|or))\b.*\b(?:task|agents?|swarm|pipeline|hierarch)', "orchestrator", 0.88, "Agent Orchestrator", "🎭")
_p(r'\b(?:expert\s*(?:vs|versus|and)\s*critic|draft\s*(?:and|then)\s*review)', "orchestrator", 0.80, "Multi-Agent Debate", "🤝")

# ── Threat Scanner ──
_p(r'\b(?:scan|virus|malware|trojan|ransomware|spyware|rootkit|threat\s*scan|quarantin|destroy\s*threat)\b', "threat_scanner", 0.90, "Threat Scanner", "🛡️")
_p(r'\b(?:is\s*(?:this|it)\s*(?:a\s*)?(?:virus|malware|safe|infected|clean))\b', "threat_scanner", 0.85, "Threat Scanner", "🛡️")
_p(r'\b(?:check\s*(?:for\s*)?(?:virus|threat|malware))\b', "threat_scanner", 0.88, "Threat Scanner", "🛡️")

# ── Deep Researcher ──
_p(r'\b(?:deep\s*research|compile\s*(?:a\s*)?dossier|intelligence\s*report|investigate\s*(?:thoroughly|deeply))\b', "deep_researcher", 0.90, "Deep Researcher", "🔍")
_p(r'\b(?:research\s*(?:everything|all)\s*(?:about|on))\b', "deep_researcher", 0.82, "Deep Researcher", "🔍")

# ── DevOps Reviewer ──
_p(r'\b(?:devops|ci/?cd|deploy(?:ment)?|docker(?:file)?|kubernetes|k8s|pipeline\s*(?:fix|review|debug))\b.*\b(?:fix|review|debug|issue|error|broken|fail)', "devops_reviewer", 0.88, "DevOps Reviewer", "🛠️")
_p(r'\b(?:fix\s*(?:the\s*)?(?:build|deploy|pipeline|ci|cd))\b', "devops_reviewer", 0.85, "DevOps Reviewer", "🛠️")

# ── Contract Hunter ──
_p(r'\b(?:contract|legal\s*(?:document|review)|nda|agreement|clause|toxic\s*clause|predatory)\b.*\b(?:audit|review|check|analyz|hunt|find)\b', "contract_hunter", 0.90, "Contract Hunter", "📜")
_p(r'\b(?:review\s*(?:this|my|the)\s*(?:contract|agreement|nda))\b', "contract_hunter", 0.88, "Contract Hunter", "📜")

# ── Digital Archivist ──
_p(r'\b(?:organiz|sort|clean\s*up|archiv|tidyup|declutter)\b.*\b(?:folder|director|files?|downloads?|desktop)\b', "archivist", 0.88, "Digital Archivist", "📁")
_p(r'\b(?:organiz(?:e|ing)\s*(?:my\s*)?(?:folders?|files?|downloads?))\b', "archivist", 0.85, "Digital Archivist", "📁")

# ── Transpiler ──
_p(r'\b(?:transpil|migrat|convert|port)\b.*\b(?:code|language|python|rust|go|java|typescript|javascript|c\+\+|csharp|c#)\b', "transpiler", 0.88, "Code Transpiler", "🔄")
_p(r'\b(?:convert|rewrite|port)\s+(?:from\s+)?\w+\s+(?:to|into)\s+\w+', "transpiler", 0.82, "Code Transpiler", "🔄")

# ── Code Evolution ──
_p(r'\b(?:evolv|optimiz|rlhf|genetic\s*algorithm|mutation)\b.*\b(?:code|function|algorithm|program)\b', "evolution", 0.85, "Code Evolution", "🧬")
_p(r'\b(?:evolve\s*(?:this|my|the)\s*(?:code|function))\b', "evolution", 0.88, "Code Evolution", "🧬")

# ── Multimodal Analysis ──
_p(r'\b(?:analyz|process|read|extract|describe)\b.*\b(?:image|photo|picture|pdf|audio|video|screenshot)\b', "multimodal", 0.85, "Multimodal Analysis", "🧠")
_p(r'\b(?:what.?s\s*(?:in|on)\s*(?:this|the)\s*(?:image|photo|picture|screenshot))\b', "multimodal", 0.88, "Multimodal Analysis", "🧠")

# ── Content Factory ──
_p(r'\b(?:syndicat|content\s*factory|repurpos|cross[- ]?post)\b.*\b(?:content|article|blog|post|tweet)\b', "content_factory", 0.85, "Content Factory", "📰")

# ── Devil's Advocate / Board Meeting ──
_p(r'\b(?:devil.?s\s*advocate|risk\s*matrix|board\s*meeting|business\s*plan\s*(?:review|critique|analyz))\b', "devils_advocate", 0.88, "Devil's Advocate", "👔")

# ── Tutor ──
_p(r'\b(?:teach\s*me|tutor|explain\s*(?:like|as\s*if)|socratic|learn(?:ing)?\s*(?:about|session))\b', "tutor", 0.82, "Socratic Tutor", "🎓")

# ── Swarm Intelligence ──
_p(r'\b(?:swarm\s*(?:intelligence|task)|multi[- ]?agent\s*swarm|deploy\s*(?:agent\s*)?swarm)\b', "swarm", 0.88, "Swarm Intelligence", "🐝")


# ── Local File Finder ──
_p(r'\b(?:find|locate|search\s*for|where\s*is|look\s*for)\b.*\b(?:file|document|my\s*(?:resume|report|image|picture|video|code)|folder|directory)\b', "file_finder", 0.88, "File Finder", "🔍")
_p(r'\b(?:i\s*lost\s*(?:a|my)\s*file|can.?t\s*find\s*(?:a|my)\s*file)\b', "file_finder", 0.90, "File Finder", "🔍")

class IntentRouter:
    """
    Classifies user queries to route them to the appropriate backend system.
    
    Usage:
        router = IntentRouter()
        result = router.classify("scan my downloads folder for viruses")
        # result.target_system → "threat_scanner"
        # result.confidence → 0.90
        # result.display_name → "Threat Scanner"
    """

    def __init__(self):
        self._history: List[RoutingResult] = []

    def classify(self, query: str) -> RoutingResult:
        """
        Classify a user query and return the best routing target.
        
        If multiple patterns match, the highest-confidence one wins.
        """
        if not query or not query.strip():
            return RoutingResult()

        query_clean = query.strip()
        best_match: Optional[RoutingResult] = None

        for pattern, target, confidence, display_name, emoji in _ROUTE_PATTERNS:
            if pattern.search(query_clean):
                if best_match is None or confidence > best_match.confidence:
                    best_match = RoutingResult(
                        target_system=target,
                        confidence=confidence,
                        display_name=display_name,
                        display_emoji=emoji,
                        reasoning=f"Matched pattern: {pattern.pattern[:60]}",
                    )

        if best_match and best_match.confidence >= 0.75:
            logger.info(
                f"IntentRouter: '{query_clean[:50]}...' → {best_match.target_system} "
                f"(conf={best_match.confidence:.2f})"
            )
            self._history.append(best_match)
            return best_match

        # Default: normal chat
        default = RoutingResult(
            target_system="chat",
            confidence=1.0,
            display_name="Chat",
            display_emoji="💬",
            reasoning="No specialized pattern matched",
        )
        self._history.append(default)
        return default

    def get_stats(self) -> dict:
        """Return routing statistics."""
        from collections import Counter
        targets = Counter(r.target_system for r in self._history)
        return {
            "total_routed": len(self._history),
            "target_distribution": dict(targets),
        }


# Module-level singleton
_router_instance: Optional[IntentRouter] = None


def get_intent_router() -> IntentRouter:
    """Get or create the singleton IntentRouter."""
    global _router_instance
    if _router_instance is None:
        _router_instance = IntentRouter()
    return _router_instance
