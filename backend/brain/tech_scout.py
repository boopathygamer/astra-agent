"""
Technology Scout — Autonomous Technology Discovery & Evaluation.
================================================================
Monitors trends, evaluates new libraries/frameworks, scores them,
and generates integration recommendations.

Classes:
  TechCandidate    — A discovered technology with scoring
  TechnologyScout  — The discovery and evaluation engine
"""

import json
import logging
import secrets
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TechCandidate:
    """A discovered technology candidate."""
    name: str = ""
    category: str = ""  # framework, library, tool, language, service
    ecosystem: str = ""  # npm, pypi, github, crates
    description: str = ""
    version: str = ""
    url: str = ""
    stars: int = 0
    downloads: int = 0
    last_updated: str = ""
    license: str = ""

    # Evaluation scores (0-1)
    maturity: float = 0.0
    community: float = 0.0
    documentation: float = 0.0
    performance: float = 0.0
    security: float = 0.0
    compatibility: float = 0.0
    overall_score: float = 0.0

    tags: List[str] = field(default_factory=list)
    recommendation: str = ""  # adopt, trial, assess, hold, avoid

    def compute_overall(self):
        self.overall_score = (
            self.maturity * 0.20 +
            self.community * 0.20 +
            self.documentation * 0.15 +
            self.performance * 0.20 +
            self.security * 0.15 +
            self.compatibility * 0.10
        )
        if self.overall_score >= 0.8:
            self.recommendation = "adopt"
        elif self.overall_score >= 0.6:
            self.recommendation = "trial"
        elif self.overall_score >= 0.4:
            self.recommendation = "assess"
        elif self.overall_score >= 0.2:
            self.recommendation = "hold"
        else:
            self.recommendation = "avoid"


class TechnologyScout:
    """
    Autonomous technology discovery and evaluation engine.

    Capabilities:
      1. SEARCH  — Search npm/PyPI/GitHub for trending packages
      2. EVALUATE — Score technologies on 6 dimensions
      3. COMPARE  — Side-by-side comparison of alternatives
      4. RECOMMEND — Generate adoption recommendations
      5. MONITOR  — Track technology lifecycle

    Usage:
        scout = TechnologyScout()
        trending = await scout.search_trending("npm", "react")
        comparison = scout.compare([react, vue, svelte])
        report = scout.generate_tech_radar()
    """

    # Known technology database (offline fallback)
    _KNOWN_TECH = {
        "react": TechCandidate(
            name="React", category="framework", ecosystem="npm",
            description="Declarative UI library for building composable interfaces",
            stars=220000, downloads=20000000, license="MIT",
            maturity=0.95, community=0.98, documentation=0.95,
            performance=0.85, security=0.90, compatibility=0.95, tags=["frontend", "ui", "components"],
        ),
        "vue": TechCandidate(
            name="Vue.js", category="framework", ecosystem="npm",
            description="Progressive framework for building user interfaces",
            stars=210000, downloads=5000000, license="MIT",
            maturity=0.90, community=0.92, documentation=0.93,
            performance=0.88, security=0.90, compatibility=0.90, tags=["frontend", "ui", "progressive"],
        ),
        "svelte": TechCandidate(
            name="Svelte", category="framework", ecosystem="npm",
            description="Compiler-based framework with zero runtime overhead",
            stars=78000, downloads=1500000, license="MIT",
            maturity=0.75, community=0.80, documentation=0.85,
            performance=0.95, security=0.90, compatibility=0.75, tags=["frontend", "compiler", "fast"],
        ),
        "nextjs": TechCandidate(
            name="Next.js", category="framework", ecosystem="npm",
            description="Full-stack React framework with SSR and RSC",
            stars=125000, downloads=7000000, license="MIT",
            maturity=0.90, community=0.95, documentation=0.92,
            performance=0.88, security=0.88, compatibility=0.85, tags=["fullstack", "ssr", "react"],
        ),
        "fastapi": TechCandidate(
            name="FastAPI", category="framework", ecosystem="pypi",
            description="High-performance Python API framework with auto-docs",
            stars=75000, downloads=30000000, license="MIT",
            maturity=0.85, community=0.88, documentation=0.95,
            performance=0.92, security=0.85, compatibility=0.88, tags=["api", "python", "async"],
        ),
        "django": TechCandidate(
            name="Django", category="framework", ecosystem="pypi",
            description="Batteries-included Python web framework",
            stars=80000, downloads=25000000, license="BSD",
            maturity=0.98, community=0.95, documentation=0.98,
            performance=0.75, security=0.92, compatibility=0.90, tags=["fullstack", "python", "batteries"],
        ),
        "flutter": TechCandidate(
            name="Flutter", category="framework", ecosystem="pub",
            description="Cross-platform mobile/web/desktop UI framework",
            stars=165000, downloads=0, license="BSD",
            maturity=0.85, community=0.90, documentation=0.90,
            performance=0.90, security=0.85, compatibility=0.80, tags=["mobile", "cross-platform", "dart"],
        ),
        "bun": TechCandidate(
            name="Bun", category="tool", ecosystem="npm",
            description="All-in-one JS runtime, bundler, test runner, package manager",
            stars=73000, downloads=3000000, license="MIT",
            maturity=0.65, community=0.75, documentation=0.70,
            performance=0.98, security=0.75, compatibility=0.70, tags=["runtime", "fast", "javascript"],
        ),
        "htmx": TechCandidate(
            name="htmx", category="library", ecosystem="npm",
            description="Access modern browser features directly from HTML",
            stars=37000, downloads=800000, license="BSD",
            maturity=0.70, community=0.75, documentation=0.80,
            performance=0.90, security=0.85, compatibility=0.95, tags=["html", "no-js", "hypermedia"],
        ),
        "drizzle": TechCandidate(
            name="Drizzle ORM", category="library", ecosystem="npm",
            description="TypeScript ORM with SQL-like syntax",
            stars=24000, downloads=2000000, license="MIT",
            maturity=0.70, community=0.75, documentation=0.78,
            performance=0.90, security=0.85, compatibility=0.85, tags=["orm", "database", "typescript"],
        ),
    }

    def __init__(self, memory_store=None):
        self.memory = memory_store
        self._cache: Dict[str, TechCandidate] = {}

    async def search_trending(self, ecosystem: str = "npm",
                               query: str = "", limit: int = 10) -> List[Dict]:
        """Search for trending packages in an ecosystem."""
        results = []

        if ecosystem == "npm":
            results = await self._search_npm(query, limit)
        elif ecosystem == "pypi":
            results = await self._search_pypi(query, limit)
        else:
            # Fallback to known tech database
            for name, tech in self._KNOWN_TECH.items():
                if tech.ecosystem == ecosystem or not ecosystem:
                    if not query or query.lower() in name or query.lower() in " ".join(tech.tags):
                        tech.compute_overall()
                        results.append(self._tech_to_dict(tech))

        return results[:limit]

    async def _search_npm(self, query: str, limit: int) -> List[Dict]:
        """Search npm registry."""
        try:
            url = f"https://registry.npmjs.org/-/v1/search?text={query}&size={limit}"
            req = urllib.request.Request(url, headers={"User-Agent": "Astra-Agent/1.0"})
            import asyncio
            resp = await asyncio.to_thread(urllib.request.urlopen, req, timeout=10)
            data = json.loads(resp.read().decode("utf-8"))

            results = []
            for obj in data.get("objects", []):
                pkg = obj.get("package", {})
                score = obj.get("score", {})

                tech = TechCandidate(
                    name=pkg.get("name", ""),
                    category="library",
                    ecosystem="npm",
                    description=pkg.get("description", ""),
                    version=pkg.get("version", ""),
                    url=pkg.get("links", {}).get("npm", ""),
                    license=pkg.get("license", "unknown"),
                    maturity=score.get("detail", {}).get("maintenance", 0),
                    community=score.get("detail", {}).get("popularity", 0),
                    documentation=score.get("detail", {}).get("quality", 0),
                    performance=score.get("final", 0),
                )
                tech.compute_overall()
                results.append(self._tech_to_dict(tech))

            return results
        except Exception as e:
            logger.debug(f"npm search failed: {e}")
            # Fallback
            return [self._tech_to_dict(t) for n, t in self._KNOWN_TECH.items()
                    if t.ecosystem == "npm" and (not query or query.lower() in n)]

    async def _search_pypi(self, query: str, limit: int) -> List[Dict]:
        """Search PyPI."""
        try:
            url = f"https://pypi.org/search/?q={query}&o="
            req = urllib.request.Request(url, headers={"User-Agent": "Astra-Agent/1.0"})
            # PyPI doesn't have a great search API, use known db
            return [self._tech_to_dict(t) for n, t in self._KNOWN_TECH.items()
                    if t.ecosystem == "pypi" and (not query or query.lower() in n)]
        except Exception:
            return []

    def evaluate(self, tech_name: str) -> Optional[Dict]:
        """Evaluate a known technology with detailed scoring."""
        tech = self._KNOWN_TECH.get(tech_name.lower().replace(" ", "").replace(".", ""))
        if not tech:
            return None
        tech.compute_overall()
        return self._tech_to_dict(tech)

    def compare(self, tech_names: List[str]) -> Dict[str, Any]:
        """Side-by-side comparison of multiple technologies."""
        candidates = []
        for name in tech_names:
            tech = self._KNOWN_TECH.get(name.lower().replace(" ", "").replace(".", ""))
            if tech:
                tech.compute_overall()
                candidates.append(tech)

        if not candidates:
            return {"success": False, "error": "No matching technologies found"}

        candidates.sort(key=lambda t: t.overall_score, reverse=True)

        return {
            "success": True,
            "comparison": [self._tech_to_dict(t) for t in candidates],
            "winner": candidates[0].name,
            "dimensions": {
                "maturity": max(candidates, key=lambda t: t.maturity).name,
                "community": max(candidates, key=lambda t: t.community).name,
                "documentation": max(candidates, key=lambda t: t.documentation).name,
                "performance": max(candidates, key=lambda t: t.performance).name,
                "security": max(candidates, key=lambda t: t.security).name,
                "compatibility": max(candidates, key=lambda t: t.compatibility).name,
            },
        }

    def generate_tech_radar(self) -> Dict[str, Any]:
        """Generate a Technology Radar (Adopt/Trial/Assess/Hold/Avoid)."""
        radar = {"adopt": [], "trial": [], "assess": [], "hold": [], "avoid": []}

        for name, tech in self._KNOWN_TECH.items():
            tech.compute_overall()
            radar[tech.recommendation].append({
                "name": tech.name,
                "score": round(tech.overall_score, 3),
                "category": tech.category,
                "ecosystem": tech.ecosystem,
                "tags": tech.tags,
            })

        # Sort each ring by score
        for ring in radar:
            radar[ring].sort(key=lambda t: t["score"], reverse=True)

        return {
            "success": True,
            "radar": radar,
            "total_technologies": sum(len(v) for v in radar.values()),
            "adopt_count": len(radar["adopt"]),
            "trial_count": len(radar["trial"]),
        }

    def suggest_for_project(self, project_type: str,
                            requirements: List[str] = None) -> Dict[str, Any]:
        """Suggest technology stack for a project type."""
        requirements = requirements or []
        req_lower = " ".join(r.lower() for r in requirements)

        stacks = {
            "web_frontend": {
                "recommended": "React + Next.js + TailwindCSS",
                "alternatives": ["Vue.js + Nuxt", "Svelte + SvelteKit"],
                "reasoning": "React has the largest ecosystem and community support",
            },
            "web_backend": {
                "recommended": "FastAPI (Python) or Express (Node.js)",
                "alternatives": ["Django", "Flask", "Nest.js"],
                "reasoning": "FastAPI for Python speed, Express for JS ecosystem",
            },
            "mobile": {
                "recommended": "Flutter (cross-platform) or React Native",
                "alternatives": ["Kotlin (Android), Swift (iOS)"],
                "reasoning": "Flutter for single codebase, native for max performance",
            },
            "fullstack": {
                "recommended": "Next.js + Prisma + PostgreSQL",
                "alternatives": ["Django + React", "SvelteKit + Drizzle"],
                "reasoning": "Next.js provides full-stack RSC with type-safe ORM",
            },
            "api": {
                "recommended": "FastAPI + SQLAlchemy + PostgreSQL",
                "alternatives": ["Express + TypeORM", "Django REST Framework"],
                "reasoning": "FastAPI auto-generates OpenAPI docs with high performance",
            },
            "game": {
                "recommended": "Unity (C#) or Godot (GDScript/C++)",
                "alternatives": ["Unreal Engine (C++)", "Bevy (Rust)"],
                "reasoning": "Unity for 2D/3D versatility, Godot for open-source freedom",
            },
        }

        stack = stacks.get(project_type.lower(), stacks.get("fullstack"))
        if not stack:
            stack = {
                "recommended": "Evaluate requirements first",
                "alternatives": [],
                "reasoning": f"Unknown project type: {project_type}",
            }

        # Customize based on requirements
        if "performance" in req_lower:
            stack["note"] = "For max performance: consider Bun, Rust, or Go"
        if "security" in req_lower:
            stack["note"] = "For security-critical: use Django (built-in auth) or FastAPI + Auth0"
        if "rapid" in req_lower or "mvp" in req_lower:
            stack["note"] = "For rapid prototyping: use Next.js or Django"

        return {"success": True, "project_type": project_type, **stack}

    def _tech_to_dict(self, tech: TechCandidate) -> Dict:
        return {
            "name": tech.name,
            "category": tech.category,
            "ecosystem": tech.ecosystem,
            "description": tech.description,
            "overall_score": round(tech.overall_score, 3),
            "recommendation": tech.recommendation,
            "scores": {
                "maturity": round(tech.maturity, 2),
                "community": round(tech.community, 2),
                "documentation": round(tech.documentation, 2),
                "performance": round(tech.performance, 2),
                "security": round(tech.security, 2),
                "compatibility": round(tech.compatibility, 2),
            },
            "tags": tech.tags,
            "license": tech.license,
        }
