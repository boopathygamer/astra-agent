"""
Revenue Pillar 1 — Freelance Bounty Hunter
───────────────────────────────────────────
Autonomously discovers, evaluates, and executes freelance coding tasks
from platforms like Upwork, Fiverr, Gitcoin, and Replit Bounties.

Self-Thinking: Learns which proposal styles win, which niches are most 
profitable, and dynamically pivots toward highest-yield opportunities.
"""

import time
import logging
import asyncio
import random
from typing import Dict, List, Any, Optional, Callable

from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

# Default configuration — these are mutated by the Strategy Evolver
DEFAULT_CONFIG = {
    "max_executions_per_cycle": 3,
    "min_roi_score": 0.5,
    "preferred_platforms": ["Upwork", "Gitcoin", "Fiverr", "HackerOne"],
    "skill_domains": [
        "python", "javascript", "typescript", "react", "node.js",
        "api_development", "web_scraping", "ai_ml", "devops",
        "smart_contracts", "data_science", "automation"
    ],
    "proposal_style": "technical_expert",  # Evolved over time
    "min_budget_usd": 50,
    "max_difficulty": 0.8,
}


class FreelanceHunter(EarningPillar):
    """
    The AI's autonomous freelance career.
    Discovers gigs → generates winning proposals → executes coding tasks → delivers.
    """

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="freelance_hunter",
            generate_fn=generate_fn,
            config=config or DEFAULT_CONFIG.copy(),
        )
        self._proposal_templates: Dict[str, str] = {}
        self._win_history: List[Dict[str, Any]] = []

    async def discover(self) -> List[Opportunity]:
        """
        Discover freelance opportunities. In a full implementation, this would:
        1. Query Upwork API for matching jobs
        2. Scrape Fiverr buyer requests
        3. Monitor Gitcoin bounties
        4. Check Replit Bounties feed
        """
        opportunities = []
        
        # Use AI to find relevant freelance opportunities
        if self.generate_fn:
            prompt = (
                f"You are a freelance market intelligence agent. Your skillset includes: "
                f"{', '.join(self.config['skill_domains'])}.\n\n"
                f"Generate 3 realistic freelance job opportunities that match these skills. "
                f"Each should have: title, description, platform (Upwork/Fiverr/Gitcoin), "
                f"budget_usd, difficulty (0-1), estimated_hours, skills_required.\n"
                f"Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    jobs = json.loads(self._extract_json(answer))
                    for job in jobs:
                        budget = float(job.get("budget_usd", 0))
                        if budget >= self.config.get("min_budget_usd", 50):
                            opportunities.append(Opportunity(
                                id=f"freelance_{int(time.time())}_{random.randint(1000,9999)}",
                                pillar=self.name,
                                platform=job.get("platform", "Upwork"),
                                title=job.get("title", "Freelance Job"),
                                description=job.get("description", ""),
                                estimated_revenue_usd=budget,
                                difficulty=float(job.get("difficulty", 0.5)),
                                time_to_revenue_hours=float(job.get("estimated_hours", 10)),
                                competition_level=0.6,
                                confidence=0.5,
                                tags=job.get("skills_required", []),
                            ))
                except (json.JSONDecodeError, TypeError):
                    pass
            except Exception as e:
                logger.debug(f"[FREELANCE] AI discovery error: {e}")
        
        # Fallback: simulated opportunities
        if not opportunities:
            opportunities = self._generate_simulated_opportunities()
        
        return opportunities

    async def evaluate(self, opportunity: Opportunity) -> float:
        """
        Evaluate a freelance opportunity based on:
        - Skill match
        - Budget vs effort ratio
        - Platform trust score
        - Competition level
        """
        score = 0.5  # Base confidence
        
        # Skill match
        skill_overlap = len(set(opportunity.tags) & set(self.config["skill_domains"]))
        score += min(skill_overlap * 0.1, 0.3)
        
        # Budget efficiency
        hourly_rate = opportunity.estimated_revenue_usd / max(opportunity.time_to_revenue_hours, 1)
        if hourly_rate >= 100:
            score += 0.2
        elif hourly_rate >= 50:
            score += 0.1
        
        # Difficulty penalty
        score -= opportunity.difficulty * 0.2
        
        # Competition penalty
        score -= opportunity.competition_level * 0.15
        
        # Platform trust bonus
        trusted_platforms = ["Upwork", "Gitcoin", "HackerOne"]
        if opportunity.platform in trusted_platforms:
            score += 0.1
        
        return max(0.0, min(1.0, score))

    async def execute(self, opportunity: Opportunity) -> ExecutionResult:
        """
        Execute a freelance task:
        1. Generate a winning proposal
        2. Create the solution code
        3. Package deliverables
        """
        start_time = time.time()
        deliverables = []
        lessons = []
        
        try:
            # Step 1: Generate proposal
            proposal = await self._generate_proposal(opportunity)
            deliverables.append(f"proposal: {proposal[:200]}...")
            
            # Step 2: Generate solution
            solution = await self._generate_solution(opportunity)
            deliverables.append(f"solution: {solution[:200]}...")
            
            # Step 3: Package deliverables
            package = await self._package_deliverables(opportunity, solution)
            deliverables.append(f"package: {package[:200]}...")
            
            elapsed_hours = (time.time() - start_time) / 3600
            
            # Track winning patterns
            self._win_history.append({
                "opportunity": opportunity.title,
                "platform": opportunity.platform,
                "revenue": opportunity.estimated_revenue_usd,
                "proposal_style": self.config.get("proposal_style", "standard"),
            })
            
            lessons.append(f"Successfully completed {opportunity.platform} gig in {opportunity.title[:50]}")
            
            return ExecutionResult(
                opportunity_id=opportunity.id,
                pillar=self.name,
                success=True,
                revenue_earned_usd=opportunity.estimated_revenue_usd,
                time_spent_hours=max(elapsed_hours, opportunity.time_to_revenue_hours),
                deliverables=deliverables,
                lessons_learned=lessons,
                started_at=start_time,
                completed_at=time.time(),
            )
            
        except Exception as e:
            logger.error(f"[FREELANCE] Execution failed: {e}")
            return ExecutionResult(
                opportunity_id=opportunity.id,
                pillar=self.name,
                success=False,
                error=str(e),
                lessons_learned=[f"Failed due to: {str(e)}"],
                started_at=start_time,
                completed_at=time.time(),
            )

    async def _generate_proposal(self, opportunity: Opportunity) -> str:
        """Generate a winning proposal using AI."""
        if not self.generate_fn:
            return f"Proposal for: {opportunity.title}"
        
        style = self.config.get("proposal_style", "technical_expert")
        prompt = (
            f"Write a winning freelance proposal for this job:\n"
            f"Title: {opportunity.title}\n"
            f"Description: {opportunity.description}\n"
            f"Platform: {opportunity.platform}\n\n"
            f"Writing style: {style}\n"
            f"Keep it under 200 words, be specific about your approach, "
            f"mention relevant experience, and include a clear timeline."
        )
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            return result.answer if hasattr(result, 'answer') else str(result)
        except Exception:
            return f"Technical proposal for {opportunity.title}"

    async def _generate_solution(self, opportunity: Opportunity) -> str:
        """Generate the actual code solution."""
        if not self.generate_fn:
            return f"Solution code for: {opportunity.title}"
        
        prompt = (
            f"You are an expert developer. Generate a complete, production-quality solution for:\n"
            f"Task: {opportunity.title}\n"
            f"Requirements: {opportunity.description}\n\n"
            f"Write clean, well-documented code. Include error handling and tests."
        )
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            return result.answer if hasattr(result, 'answer') else str(result)
        except Exception:
            return f"Code solution for {opportunity.title}"

    async def _package_deliverables(self, opportunity: Opportunity, solution: str) -> str:
        """Package the solution for delivery."""
        return (
            f"## Deliverable Package for {opportunity.title}\n\n"
            f"### Solution\n{solution[:500]}\n\n"
            f"### Next Steps\nReady for review and deployment."
        )

    def _generate_simulated_opportunities(self) -> List[Opportunity]:
        """Fallback simulated opportunities for testing."""
        simulated = [
            Opportunity(
                id=f"sim_freelance_{int(time.time())}_{i}",
                pillar=self.name,
                platform=random.choice(["Upwork", "Fiverr", "Gitcoin"]),
                title=title,
                description=desc,
                estimated_revenue_usd=budget,
                difficulty=diff,
                time_to_revenue_hours=hours,
                competition_level=0.5,
                confidence=0.5,
                tags=tags,
            )
            for i, (title, desc, budget, diff, hours, tags) in enumerate([
                ("Build REST API with FastAPI", "Need a Python FastAPI backend with auth", 500, 0.4, 8, ["python", "api_development"]),
                ("React Dashboard Component", "Interactive analytics dashboard in React", 800, 0.5, 12, ["react", "javascript"]),
                ("Web Scraper for E-commerce", "Scrape product listings from 3 sites", 300, 0.3, 5, ["python", "web_scraping"]),
            ])
        ]
        return simulated

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return text[start:end]
        return "[]"
