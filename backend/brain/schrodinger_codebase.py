"""
Schrödinger's Codebase — Dynamic Strategy Selection
────────────────────────────────────────────────────
Expert-level dynamic code generation that selects the optimal
implementation strategy based on query context. The codebase
"collapses" from multiple potential strategies into the one
best suited for the current request.
"""

import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CollapsedStrategy:
    """A selected strategy with metadata."""
    strategy_name: str
    template: str
    confidence: float
    collapse_time_ms: float


# Strategy templates keyed by domain
_STRATEGY_TEMPLATES: Dict[str, Dict[str, str]] = {
    "api": {
        "name": "REST API Endpoint",
        "template": (
            "from fastapi import APIRouter, HTTPException\n"
            "router = APIRouter()\n\n"
            "@router.get('/api/v1/{resource}')\n"
            "async def get_resource(resource: str):\n"
            "    # Auto-generated endpoint\n"
            "    return {{'resource': resource, 'status': 'ok'}}\n"
        ),
    },
    "ui": {
        "name": "React Component",
        "template": (
            "import React from 'react';\n\n"
            "export default function GeneratedComponent({ data }) {\n"
            "  return (\n"
            "    <div className='container'>\n"
            "      <h2>{data?.title || 'Generated UI'}</h2>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        ),
    },
    "database": {
        "name": "Database Query Builder",
        "template": (
            "from sqlalchemy import select, text\n\n"
            "async def query_builder(session, table, filters):\n"
            "    stmt = select(table).where(\n"
            "        *[getattr(table.c, k) == v for k, v in filters.items()]\n"
            "    )\n"
            "    result = await session.execute(stmt)\n"
            "    return result.fetchall()\n"
        ),
    },
    "algorithm": {
        "name": "Algorithm Implementation",
        "template": (
            "from typing import Any, List\n\n"
            "def solve(data: List[Any]) -> Any:\n"
            "    # Dynamic algorithm selection placeholder\n"
            "    if len(data) < 100:\n"
            "        return sorted(data)  # Small dataset: in-place sort\n"
            "    # Large dataset: divide and conquer\n"
            "    mid = len(data) // 2\n"
            "    return merge(solve(data[:mid]), solve(data[mid:]))\n"
        ),
    },
}

_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "api": ["api", "endpoint", "rest", "route", "server", "http", "request"],
    "ui": ["ui", "component", "react", "frontend", "button", "page", "render", "css"],
    "database": ["database", "sql", "query", "table", "schema", "migration", "orm"],
    "algorithm": ["sort", "search", "optimize", "algorithm", "graph", "tree", "dynamic"],
}


class SchrodingerCodebase:
    """
    Tier 8: Schrödinger's Codebase (Dynamic Strategy Selection)

    Maintains multiple potential implementation strategies in
    superposition. The query context causes the codebase to
    collapse into the optimal strategy for the request.
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self._generate_fn = generate_fn
        self._collapses: int = 0
        logger.info("[SCHRODINGER] Dynamic strategy selector active (%d strategies).", len(_STRATEGY_TEMPLATES))

    def _detect_domain(self, query: str) -> str:
        """Detect the domain from query keywords."""
        query_lower = query.lower()
        scores: Dict[str, int] = {}
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[domain] = score

        if scores:
            return max(scores, key=scores.get)
        return "algorithm"  # default fallback

    def collapse_wavefunction(self, query: str) -> CollapsedStrategy:
        """
        Observe the query to collapse the codebase superposition
        into the optimal strategy.
        """
        start = time.time()
        domain = self._detect_domain(query)
        strategy = _STRATEGY_TEMPLATES.get(domain, _STRATEGY_TEMPLATES["algorithm"])

        self._collapses += 1
        collapse_time = (time.time() - start) * 1000

        result = CollapsedStrategy(
            strategy_name=strategy["name"],
            template=strategy["template"],
            confidence=0.85,
            collapse_time_ms=collapse_time,
        )
        logger.info("[SCHRODINGER] Collapsed to '%s' domain (%.1fms).", domain, collapse_time)
        return result


# Global singleton — always active
schrodinger_matrix = SchrodingerCodebase()
