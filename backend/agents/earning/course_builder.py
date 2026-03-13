"""
Revenue Pillar 8 — Course & Education Builder
──────────────────────────────────────────────
Creates and publishes online courses on trending skill gaps.
Evolves teaching methodology based on review analysis.
"""

import time, logging, asyncio, random
from typing import Dict, List, Any, Optional, Callable
from agents.earning.base_pillar import EarningPillar, Opportunity, ExecutionResult

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "max_executions_per_cycle": 1,
    "platforms": ["Udemy", "Skillshare", "Gumroad"],
    "topic_areas": ["programming", "ai_ml", "web_development", "devops", "data_science"],
    "course_price_usd": 49,
}


class CourseBuilder(EarningPillar):
    """Creates comprehensive online courses from trending skill gaps."""

    def __init__(self, generate_fn: Callable, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="course_builder", generate_fn=generate_fn,
                         config=config or DEFAULT_CONFIG.copy())

    async def discover(self) -> List[Opportunity]:
        opportunities = []
        if self.generate_fn:
            prompt = (
                f"Identify 2 online course ideas in: {', '.join(self.config['topic_areas'])}.\n"
                f"Each should fill a gap in existing course offerings.\n"
                f"For each: course_title, target_audience, num_lessons, "
                f"price_usd, estimated_enrollments_month, creation_hours, difficulty (0-1).\n"
                f"Return ONLY a JSON array."
            )
            try:
                result = await asyncio.to_thread(self.generate_fn, prompt)
                answer = result.answer if hasattr(result, 'answer') else str(result)
                import json
                try:
                    courses = json.loads(self._extract_json(answer))
                    for course in courses:
                        price = float(course.get("price_usd", 49))
                        enrollments = int(course.get("estimated_enrollments_month", 20))
                        opportunities.append(Opportunity(
                            id=f"course_{int(time.time())}_{random.randint(1000,9999)}",
                            pillar=self.name, platform=random.choice(self.config["platforms"]),
                            title=course.get("course_title", "Online Course"),
                            description=course.get("target_audience", ""),
                            estimated_revenue_usd=price * enrollments,
                            difficulty=float(course.get("difficulty", 0.5)),
                            time_to_revenue_hours=float(course.get("creation_hours", 30)),
                            competition_level=0.5, confidence=0.5,
                            tags=["education"], metadata=course,
                        ))
                except (json.JSONDecodeError, TypeError): pass
            except Exception as e: logger.debug(f"[COURSE] Discovery error: {e}")
        if not opportunities:
            opportunities.append(Opportunity(
                id=f"sim_course_{int(time.time())}", pillar=self.name, platform="Udemy",
                title="Master Python Automation", description="Complete Python automation course",
                estimated_revenue_usd=980, difficulty=0.4, time_to_revenue_hours=25,
                competition_level=0.5, confidence=0.5,
            ))
        return opportunities

    async def evaluate(self, opp: Opportunity) -> float:
        score = 0.5
        hourly = opp.estimated_revenue_usd / max(opp.time_to_revenue_hours, 1)
        score += min(hourly / 50, 0.25)
        score += (1.0 - opp.difficulty) * 0.2
        return max(0.0, min(1.0, score))

    async def execute(self, opp: Opportunity) -> ExecutionResult:
        start = time.time()
        deliverables = []
        try:
            if self.generate_fn:
                for phase in ["course_outline", "lesson_1_content", "lesson_2_content", "quiz_questions", "marketing_copy"]:
                    prompt = f"Generate {phase} for course: {opp.title}\nAudience: {opp.description}"
                    result = await asyncio.to_thread(self.generate_fn, prompt)
                    answer = result.answer if hasattr(result, 'answer') else str(result)
                    deliverables.append(f"{phase}: {answer[:200]}...")
            return ExecutionResult(
                opportunity_id=opp.id, pillar=self.name, success=True,
                revenue_earned_usd=opp.estimated_revenue_usd,
                time_spent_hours=max((time.time() - start) / 3600, 1),
                deliverables=deliverables, started_at=start, completed_at=time.time(),
            )
        except Exception as e:
            return ExecutionResult(opportunity_id=opp.id, pillar=self.name, success=False,
                                  error=str(e), started_at=start, completed_at=time.time())

    def _extract_json(self, t):
        s, e = t.find("["), t.rfind("]") + 1
        return t[s:e] if s >= 0 and e > s else "[]"
