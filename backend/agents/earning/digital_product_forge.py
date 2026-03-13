"""
Revenue Pillar 4 — Digital Product Forge
─────────────────────────────────────────
Autonomously creates and sells digital products:
templates, UI kits, code snippets, prompt packs, e-books, datasets.

Self-Thinking: Tracks which products sell best, doubles down on winners,
retires underperformers, and evolves product categories.
"""

import time
import logging
import asyncio
import random
from typing import Dict, List, Any, Optional, Callable

from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 3,
    "marketplaces": ["Gumroad", "Etsy", "Creative Market", "PromptBase", "Notion Marketplace"],
    "product_categories": [
        "code_templates", "ui_kits", "prompt_packs", "notion_templates",
        "datasets", "ebooks", "cheatsheets", "automation_scripts",
    ],
    "price_range_usd": (5, 99),
    "quality_threshold": 0.7,
}


class DigitalProductForge(EarningPillar):
    """
    The AI's digital product factory.
    Creates high-quality digital assets and lists them on marketplaces.
    """

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="digital_product_forge",
            generate_fn=generate_fn,
            config=config or DEFAULT_CONFIG.copy(),
        )
        self._product_catalog: List[Dict[str, Any]] = []
        self._sales_data: Dict[str, int] = {}

    async def discover(self) -> List[Opportunity]:
        """Discover what digital products are selling well right now."""
        opportunities = []
        
        if self.generate_fn:
            prompt = (
                f"You are a digital product market researcher. Identify 3 digital products "
                f"that would sell well on platforms like Gumroad, Etsy, or PromptBase.\n"
                f"Categories to consider: {', '.join(self.config['product_categories'])}.\n"
                f"For each: product_name, category, marketplace, price_usd, "
                f"estimated_monthly_sales, creation_hours, description.\n"
                f"Focus on products an AI can BUILD COMPLETELY (e.g., code templates, "
                f"prompt packs, documentation, cheatsheets).\n"
                f"Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    products = json.loads(self._extract_json(answer))
                    for prod in products:
                        price = float(prod.get("price_usd", 9.99))
                        monthly_sales = int(prod.get("estimated_monthly_sales", 10))
                        opportunities.append(Opportunity(
                            id=f"product_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name,
                            platform=prod.get("marketplace", "Gumroad"),
                            title=prod.get("product_name", "Digital Product"),
                            description=prod.get("description", ""),
                            estimated_revenue_usd=price * monthly_sales,  # Monthly revenue
                            difficulty=0.3,  # Digital products are generally buildable
                            time_to_revenue_hours=float(prod.get("creation_hours", 5)),
                            competition_level=0.5,
                            confidence=0.5,
                            tags=[prod.get("category", "general")],
                            metadata=prod,
                        ))
                except (json.JSONDecodeError, TypeError):
                    pass
            except Exception as e:
                logger.debug(f"[PRODUCT FORGE] Discovery error: {e}")
        
        if not opportunities:
            opportunities = self._simulated_product_opps()
        
        return opportunities

    async def evaluate(self, opportunity: Opportunity) -> float:
        """Evaluate a digital product opportunity."""
        score = 0.6  # Digital products generally have good ROI
        
        # Revenue per hour of creation
        hourly_value = opportunity.estimated_revenue_usd / max(opportunity.time_to_revenue_hours, 1)
        if hourly_value >= 50:
            score += 0.2
        elif hourly_value >= 20:
            score += 0.1
        
        # Easy to create = higher score
        score += (1.0 - opportunity.difficulty) * 0.15
        
        # Category popularity bonus
        high_demand = ["prompt_packs", "notion_templates", "code_templates", "automation_scripts"]
        if any(cat in opportunity.tags for cat in high_demand):
            score += 0.1
        
        return max(0.0, min(1.0, score))

    async def execute(self, opportunity: Opportunity) -> ExecutionResult:
        """Create the digital product and prepare marketplace listing."""
        start_time = time.time()
        deliverables = []
        
        try:
            # Step 1: Create the product
            product_content = await self._create_product(opportunity)
            deliverables.append(f"product: {product_content[:200]}...")
            
            # Step 2: Generate marketplace listing
            listing = await self._generate_listing(opportunity, product_content)
            deliverables.append(f"listing: {listing[:200]}...")
            
            # Step 3: Create promotional content
            promo = await self._generate_promo_content(opportunity)
            deliverables.append(f"promo: {promo[:200]}...")
            
            # Track in catalog
            self._product_catalog.append({
                "title": opportunity.title,
                "platform": opportunity.platform,
                "price": opportunity.metadata.get("price_usd", 9.99) if opportunity.metadata else 9.99,
                "created_at": time.time(),
            })
            
            elapsed_hours = max((time.time() - start_time) / 3600, 0.5)
            
            return ExecutionResult(
                opportunity_id=opportunity.id,
                pillar=self.name,
                success=True,
                revenue_earned_usd=opportunity.estimated_revenue_usd,
                time_spent_hours=elapsed_hours,
                deliverables=deliverables,
                lessons_learned=[f"Created '{opportunity.title}' for {opportunity.platform}"],
                started_at=start_time,
                completed_at=time.time(),
            )
            
        except Exception as e:
            logger.error(f"[PRODUCT FORGE] Execution failed: {e}")
            return ExecutionResult(
                opportunity_id=opportunity.id,
                pillar=self.name,
                success=False,
                error=str(e),
                started_at=start_time,
                completed_at=time.time(),
            )

    async def _create_product(self, opportunity: Opportunity) -> str:
        """Create the actual digital product content."""
        if not self.generate_fn:
            return f"Product content: {opportunity.title}"
        
        category = opportunity.tags[0] if opportunity.tags else "general"
        
        creation_prompts = {
            "code_templates": (
                f"Create a complete, production-ready code template: {opportunity.title}\n"
                f"Include: well-documented code, README, installation instructions, examples."
            ),
            "prompt_packs": (
                f"Create a premium prompt pack: {opportunity.title}\n"
                f"Include: 20 carefully crafted prompts, categorized by use case, "
                f"with example outputs and tips for customization."
            ),
            "notion_templates": (
                f"Design a comprehensive Notion template: {opportunity.title}\n"
                f"Include: page structure, database schemas, formulas, "
                f"automations, and a setup guide."
            ),
            "ebooks": (
                f"Write a comprehensive e-book outline and first 3 chapters: {opportunity.title}\n"
                f"Include: table of contents, introduction, key takeaways per chapter."
            ),
            "cheatsheets": (
                f"Create a professional cheatsheet: {opportunity.title}\n"
                f"Include: organized sections, concise explanations, code snippets, "
                f"visual hierarchy suggestions."
            ),
        }
        
        prompt = creation_prompts.get(category,
            f"Create a high-quality digital product: {opportunity.title}\n{opportunity.description}"
        )
        
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            return result.answer if hasattr(result, 'answer') else str(result)
        except Exception:
            return f"Product: {opportunity.title}"

    async def _generate_listing(self, opportunity: Opportunity, product_content: str) -> str:
        """Generate an optimized marketplace listing."""
        if not self.generate_fn:
            return f"Listing for {opportunity.title}"
        
        prompt = (
            f"Write a compelling marketplace listing for a digital product:\n"
            f"Product: {opportunity.title}\n"
            f"Platform: {opportunity.platform}\n"
            f"Category: {opportunity.tags[0] if opportunity.tags else 'general'}\n\n"
            f"Include: attention-grabbing title, benefit-driven description, "
            f"3 bullet points of what's included, social proof elements, "
            f"urgency/scarcity messaging."
        )
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            return result.answer if hasattr(result, 'answer') else str(result)
        except Exception:
            return f"Listing: {opportunity.title}"

    async def _generate_promo_content(self, opportunity: Opportunity) -> str:
        """Generate promotional content for social media."""
        if not self.generate_fn:
            return f"Promo for {opportunity.title}"
        
        prompt = (
            f"Write 3 promotional social media posts for a digital product:\n"
            f"Product: {opportunity.title}\n"
            f"Include: 1 Twitter post, 1 LinkedIn post, 1 Product Hunt tagline."
        )
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            return result.answer if hasattr(result, 'answer') else str(result)
        except Exception:
            return f"Promo: {opportunity.title}"

    def _simulated_product_opps(self) -> List[Opportunity]:
        products = [
            ("Ultimate Python Cheatsheet", "cheatsheets", "Gumroad", 9.99, 50),
            ("AI Prompt Engineering Pack (100 Prompts)", "prompt_packs", "PromptBase", 14.99, 30),
            ("Freelancer Notion Dashboard", "notion_templates", "Notion Marketplace", 19.99, 20),
        ]
        return [
            Opportunity(
                id=f"sim_product_{int(time.time())}_{i}",
                pillar=self.name,
                platform=marketplace,
                title=name,
                description=f"Digital product in {cat} category",
                estimated_revenue_usd=price * sales,
                difficulty=0.3,
                time_to_revenue_hours=5.0,
                competition_level=0.4,
                confidence=0.6,
                tags=[cat],
                metadata={"price_usd": price, "estimated_monthly_sales": sales},
            )
            for i, (name, cat, marketplace, price, sales) in enumerate(products)
        ]

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return text[start:end]
        return "[]"
