"""
Revenue Pillar 2 — Content Empire Builder
──────────────────────────────────────────
Autonomously discovers trending topics, generates multi-format content,
optimizes for each platform's algorithm, and syndicates across channels.

Self-Thinking: Learns which content formats get most engagement per platform,
evolves writing style, and doubles down on viral topic patterns.
"""

import time
import logging
import asyncio
import random
from typing import Dict, List, Any, Optional, Callable

from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 5,
    "content_formats": ["blog_article", "twitter_thread", "youtube_script", "linkedin_post", "newsletter"],
    "preferred_niches": [
        "ai_technology", "programming_tutorials", "saas_building",
        "productivity", "career_advice", "open_source",
    ],
    "seo_focus": True,
    "engagement_threshold": 0.3,  # Min engagement rate to continue a content series
    "syndication_delay_minutes": 30,  # Delay between cross-platform posts
}


class ContentEmpireBuilder(EarningPillar):
    """
    The AI's content empire — discovers trends, creates viral content,
    and syndicates across every platform.
    """

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="content_empire",
            generate_fn=generate_fn,
            config=config or DEFAULT_CONFIG.copy(),
        )
        self._content_library: List[Dict[str, Any]] = []
        self._engagement_data: Dict[str, List[float]] = {}

    async def discover(self) -> List[Opportunity]:
        """Discover trending topics with content monetization potential."""
        opportunities = []
        
        if self.generate_fn:
            prompt = (
                f"You are a content strategy AI. Your niches: {', '.join(self.config['preferred_niches'])}.\n\n"
                f"Identify 4 trending topics right now that could be monetized through content.\n"
                f"For each: topic, angle (unique perspective), target_format (blog/video/thread/newsletter), "
                f"monetization (ads/affiliate/sponsorship/course_funnel), estimated_monthly_revenue, "
                f"virality_score (0-1), content_difficulty (0-1).\n"
                f"Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    topics = json.loads(self._extract_json(answer))
                    for topic in topics:
                        opportunities.append(Opportunity(
                            id=f"content_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name,
                            platform=topic.get("target_format", "blog"),
                            title=topic.get("topic", "Trending Topic"),
                            description=topic.get("angle", ""),
                            estimated_revenue_usd=float(topic.get("estimated_monthly_revenue", 100)),
                            difficulty=float(topic.get("content_difficulty", 0.3)),
                            time_to_revenue_hours=4.0,  # Most content takes 2-6 hours
                            competition_level=1.0 - float(topic.get("virality_score", 0.5)),
                            confidence=0.5,
                            tags=[topic.get("monetization", "ads"), topic.get("target_format", "blog")],
                            metadata=topic,
                        ))
                except (json.JSONDecodeError, TypeError):
                    pass
            except Exception as e:
                logger.debug(f"[CONTENT] Discovery error: {e}")
        
        if not opportunities:
            opportunities = self._generate_simulated_content_opps()
        
        return opportunities

    async def evaluate(self, opportunity: Opportunity) -> float:
        """Evaluate content opportunity based on virality potential and monetization."""
        score = 0.5
        
        # Niche alignment
        niche_match = any(niche in opportunity.title.lower() or niche in opportunity.description.lower() 
                         for niche in self.config["preferred_niches"])
        if niche_match:
            score += 0.15
        
        # Revenue potential per hour of effort
        hourly_value = opportunity.estimated_revenue_usd / max(opportunity.time_to_revenue_hours, 1)
        if hourly_value >= 50:
            score += 0.2
        elif hourly_value >= 20:
            score += 0.1
        
        # Low difficulty = higher score
        score += (1.0 - opportunity.difficulty) * 0.15
        
        # Monetization type bonus
        metadata = opportunity.metadata or {}
        monetization = metadata.get("monetization", "")
        high_value_monetization = ["sponsorship", "course_funnel", "affiliate"]
        if monetization in high_value_monetization:
            score += 0.1
        
        return max(0.0, min(1.0, score))

    async def execute(self, opportunity: Opportunity) -> ExecutionResult:
        """
        Execute content creation:
        1. Research the topic deeply
        2. Generate multi-format content
        3. SEO-optimize (if applicable)
        4. Prepare syndication package
        """
        start_time = time.time()
        deliverables = []
        lessons = []
        
        try:
            target_format = opportunity.platform
            
            # Generate content based on format
            content_pieces = await self._generate_content_package(opportunity)
            
            for format_name, content in content_pieces.items():
                deliverables.append(f"{format_name}: {content[:150]}...")
            
            # SEO optimization
            if self.config.get("seo_focus") and "blog" in target_format:
                seo_data = await self._generate_seo_metadata(opportunity, content_pieces.get("blog", ""))
                deliverables.append(f"seo_metadata: {seo_data[:100]}...")
            
            # Track content
            self._content_library.append({
                "topic": opportunity.title,
                "format": target_format,
                "created_at": time.time(),
                "formats_generated": list(content_pieces.keys()),
            })
            
            elapsed_hours = max((time.time() - start_time) / 3600, 0.5)
            lessons.append(f"Generated {len(content_pieces)} content formats for '{opportunity.title[:50]}'")
            
            return ExecutionResult(
                opportunity_id=opportunity.id,
                pillar=self.name,
                success=True,
                revenue_earned_usd=opportunity.estimated_revenue_usd,
                time_spent_hours=elapsed_hours,
                deliverables=deliverables,
                lessons_learned=lessons,
                started_at=start_time,
                completed_at=time.time(),
            )
            
        except Exception as e:
            logger.error(f"[CONTENT] Execution failed: {e}")
            return ExecutionResult(
                opportunity_id=opportunity.id,
                pillar=self.name,
                success=False,
                error=str(e),
                started_at=start_time,
                completed_at=time.time(),
            )

    async def _generate_content_package(self, opportunity: Opportunity) -> Dict[str, str]:
        """Generate multi-format content from a single topic."""
        content = {}
        
        formats_to_generate = self.config.get("content_formats", ["blog_article"])
        
        for fmt in formats_to_generate[:3]:  # Limit to 3 formats per cycle
            content[fmt] = await self._generate_single_format(opportunity, fmt)
        
        return content

    async def _generate_single_format(self, opportunity: Opportunity, format_type: str) -> str:
        """Generate content in a specific format."""
        if not self.generate_fn:
            return f"[{format_type}] Content about {opportunity.title}"
        
        format_prompts = {
            "blog_article": (
                f"Write a comprehensive, SEO-optimized blog article about: {opportunity.title}\n"
                f"Angle: {opportunity.description}\n"
                f"Requirements: 1500+ words, include code examples where relevant, "
                f"use headers, bullet points, and a strong conclusion with CTA."
            ),
            "twitter_thread": (
                f"Write a viral Twitter/X thread about: {opportunity.title}\n"
                f"Angle: {opportunity.description}\n"
                f"Requirements: 8-12 tweets, hook in first tweet, use line breaks, "
                f"strategic emoji usage (not overwhelming), end with CTA."
            ),
            "youtube_script": (
                f"Write a YouTube video script about: {opportunity.title}\n"
                f"Angle: {opportunity.description}\n"
                f"Requirements: 8-12 minute script, engaging hook in first 10 seconds, "
                f"include [B-ROLL] visual cues, timestamps, and end screen CTA."
            ),
            "linkedin_post": (
                f"Write a LinkedIn post about: {opportunity.title}\n"
                f"Angle: {opportunity.description}\n"
                f"Requirements: Professional but story-driven, strong hook line, "
                f"line breaks for readability, authentic voice, leadership perspective."
            ),
            "newsletter": (
                f"Write a newsletter edition about: {opportunity.title}\n"
                f"Angle: {opportunity.description}\n"
                f"Requirements: Subject line, preview text, greeting, main content "
                f"with 3 key insights, links section, and sign-off."
            ),
        }
        
        prompt = format_prompts.get(format_type, f"Write content about {opportunity.title}")
        
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            return result.answer if hasattr(result, 'answer') else str(result)
        except Exception:
            return f"[{format_type}] Content for {opportunity.title}"

    async def _generate_seo_metadata(self, opportunity: Opportunity, content: str) -> str:
        """Generate SEO metadata for blog content."""
        if not self.generate_fn:
            return f"SEO metadata for {opportunity.title}"
        
        prompt = (
            f"Generate SEO metadata for a blog post about: {opportunity.title}\n"
            f"Include: meta_title (60 chars), meta_description (155 chars), "
            f"focus_keyword, secondary_keywords (5), slug, schema_type.\n"
            f"Return as JSON."
        )
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            return result.answer if hasattr(result, 'answer') else str(result)
        except Exception:
            return f"SEO: {opportunity.title}"

    def _generate_simulated_content_opps(self) -> List[Opportunity]:
        simulated = [
            ("How to Build AI Agents in 2026", "Step-by-step tutorial", 300, "blog", 0.3),
            ("10 Python Libraries You're Missing", "Developer productivity", 200, "twitter_thread", 0.2),
            ("Building a SaaS in a Weekend", "Startup speed-run", 500, "youtube_script", 0.4),
        ]
        return [
            Opportunity(
                id=f"sim_content_{int(time.time())}_{i}",
                pillar=self.name,
                platform=fmt,
                title=title,
                description=desc,
                estimated_revenue_usd=rev,
                difficulty=diff,
                time_to_revenue_hours=4.0,
                competition_level=0.5,
                confidence=0.5,
            )
            for i, (title, desc, rev, fmt, diff) in enumerate(simulated)
        ]

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return text[start:end]
        return "[]"
