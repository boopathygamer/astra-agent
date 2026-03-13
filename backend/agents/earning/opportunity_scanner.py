"""
Autonomous Earning System — Opportunity Scanner
────────────────────────────────────────────────
The AI's "eyes" for online money-making. Continuously monitors
market signals across multiple sources to discover earning opportunities.

Signal Sources:
  - Freelance platforms (Upwork, Fiverr, Gitcoin, HackerOne)
  - Trending content (Google Trends, Reddit, Twitter/X, HN)
  - Product gaps (Product Hunt, GitHub Trending)
  - Marketplace data (Gumroad, Etsy bestsellers)
"""

import os
import json
import time
import logging
import asyncio
import hashlib
import random
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict

from agents.earning.base_pillar import Opportunity

logger = logging.getLogger(__name__)


@dataclass
class MarketSignal:
    """A raw signal from a market source before it becomes an Opportunity."""
    source: str
    category: str
    title: str
    description: str
    url: str = ""
    estimated_value: float = 0.0
    urgency: float = 0.0  # 0.0 (no rush) to 1.0 (time-critical)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    discovered_at: float = field(default_factory=time.time)

    @property
    def signal_id(self) -> str:
        return hashlib.md5(f"{self.source}:{self.title}:{self.url}".encode()).hexdigest()[:12]


class MarketCache:
    """L1 (Memory) and L2 (Disk JSON/SQLite substitute) caching for market data."""
    def __init__(self, ttl_seconds: int = 3600):
        self.l1_cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds
        
        self.l2_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
            "data", "market_cache.json"
        )
        os.makedirs(os.path.dirname(self.l2_path), exist_ok=True)
        self._load_l2()

    def _load_l2(self):
        try:
            if os.path.exists(self.l2_path):
                with open(self.l2_path, "r") as f:
                    data = json.load(f)
                now = time.time()
                for key, entry in data.items():
                    if now - entry["timestamp"] < self.ttl:
                        self.l1_cache[key] = entry
        except Exception as e:
            logger.error(f"[CACHE] Error loading L2 cache: {e}")

    def _save_l2(self):
        try:
            with open(self.l2_path, "w") as f:
                json.dump(self.l1_cache, f)
        except Exception as e:
            logger.error(f"[CACHE] Error saving L2 cache: {e}")

    def get(self, key: str) -> Optional[Any]:
        if key in self.l1_cache:
            entry = self.l1_cache[key]
            if time.time() - entry["timestamp"] < self.ttl:
                logger.debug(f"[CACHE] L1/L2 Hit for: {key[:30]}...")
                return entry["data"]
            else:
                del self.l1_cache[key]
        return None

    def set(self, key: str, data: Any):
        self.l1_cache[key] = {
            "timestamp": time.time(),
            "data": data
        }
        self._save_l2()


class SignalSource:
    """Base class for all market signal sources."""
    
    def __init__(self, name: str, generate_fn: Optional[Callable] = None, cache: Optional[MarketCache] = None):
        self.name = name
        self.generate_fn = generate_fn
        self.cache = cache
        self._last_scan: float = 0
        self._scan_interval: float = 3600  # Default: 1 hour between scans
    
    async def scan(self) -> List[MarketSignal]:
        """Override in subclasses to scan a specific source."""
        return []
    
    @property
    def ready_to_scan(self) -> bool:
        return (time.time() - self._last_scan) >= self._scan_interval


class FreelancePlatformScanner(SignalSource):
    """Scans freelance platforms for high-value coding bounties."""
    
    def __init__(self, generate_fn: Optional[Callable] = None, cache: Optional[MarketCache] = None):
        super().__init__("freelance_platforms", generate_fn, cache)
        self._scan_interval = 1800  # 30 minutes
    
    async def scan(self) -> List[MarketSignal]:
        self._last_scan = time.time()
        logger.info("[SCANNER] 🔍 Scanning freelance platforms...")
        
        # In production, this connects to real APIs. Architecture-ready for:
        # - Upwork GraphQL API
        # - Fiverr buyer request scraping
        # - Replit Bounties API
        # - Gitcoin API
        # - Toptal opportunity feed
        
        signals = []
        platforms = [
            {
                "platform": "Upwork",
                "categories": ["Web Development", "Mobile Apps", "AI/ML", "Data Science", "DevOps"],
                "avg_budget_range": (200, 5000),
            },
            {
                "platform": "Fiverr",
                "categories": ["Programming", "WordPress", "Chatbot Development", "API Integration"],
                "avg_budget_range": (50, 1500),
            },
            {
                "platform": "Gitcoin",
                "categories": ["Smart Contracts", "DApp Development", "ZK Proofs", "DeFi"],
                "avg_budget_range": (500, 10000),
            },
            {
                "platform": "HackerOne",
                "categories": ["Web Vulnerabilities", "API Security", "Mobile Security"],
                "avg_budget_range": (100, 50000),
            },
        ]
        
        if self.generate_fn:
            # Use AI to generate realistic market-aware opportunities
            prompt = (
                "You are a market intelligence scanner. Generate 3 realistic, currently "
                "trending freelance development opportunities that an AI coding assistant could complete. "
                "Format each as JSON with fields: platform, title, description, estimated_usd, "
                "difficulty (0-1), skills_needed. Return ONLY a JSON array."
            )
            
            cached_answer = self.cache.get(prompt) if self.cache else None
            if cached_answer:
                answer = cached_answer
            else:
                try:
                    result = await asyncio.to_thread(self.generate_fn, prompt)
                    answer = result.answer if hasattr(result, 'answer') else str(result)
                    if self.cache:
                        self.cache.set(prompt, answer)
                except Exception as e:
                    logger.debug(f"[SCANNER] AI scan error: {e}")
                    answer = "[]"

            try:
                opps = json.loads(self._extract_json(answer))
                    for opp in opps:
                        signals.append(MarketSignal(
                            source="freelance_ai_scan",
                            category=opp.get("platform", "Unknown"),
                            title=opp.get("title", "Untitled"),
                            description=opp.get("description", ""),
                            estimated_value=float(opp.get("estimated_usd", 0)),
                            raw_data=opp,
                        ))
                except (json.JSONDecodeError, TypeError):
                    logger.debug("[SCANNER] AI scan response not parseable, using fallback")
            except Exception as e:
                logger.debug(f"[SCANNER] Format extraction error: {e}")
        
        # Fallback: Generate structured simulated signals
        if not signals:
            for platform_data in platforms:
                cat = random.choice(platform_data["categories"])
                budget = random.randint(*platform_data["avg_budget_range"])
                signals.append(MarketSignal(
                    source="freelance_scan",
                    category=cat,
                    title=f"{cat} project on {platform_data['platform']}",
                    description=f"Looking for expert in {cat}. Budget: ${budget}",
                    estimated_value=budget,
                    raw_data={"platform": platform_data["platform"], "category": cat},
                ))
        
        logger.info(f"[SCANNER] Found {len(signals)} freelance signals")
        return signals

    def _extract_json(self, text: str) -> str:
        """Extract JSON array from LLM response."""
        text = text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return text[start:end]
        return "[]"


class TrendScanner(SignalSource):
    """Scans trending topics for content and product opportunities."""
    
    def __init__(self, generate_fn: Optional[Callable] = None, cache: Optional[MarketCache] = None):
        super().__init__("trend_scanner", generate_fn, cache)
        self._scan_interval = 3600  # 1 hour
    
    async def scan(self) -> List[MarketSignal]:
        self._last_scan = time.time()
        logger.info("[SCANNER] 📈 Scanning trending topics...")
        
        signals = []
        
        if self.generate_fn:
            prompt = (
                "You are a trend intelligence engine. Identify 3 currently VIRAL topics "
                "that have monetization potential through content, courses, or tools. "
                "For each, provide: topic, why_trending, monetization_angle, estimated_monthly_usd, "
                "content_type (blog/video/tool/course). Return ONLY a JSON array."
            )
            
            cached_answer = self.cache.get(prompt) if self.cache else None
            answer = cached_answer
            
            if not answer:
                try:
                    result = await asyncio.to_thread(self.generate_fn, prompt)
                    answer = result.answer if hasattr(result, 'answer') else str(result)
                    if self.cache:
                        self.cache.set(prompt, answer)
                except Exception as e:
                    logger.debug(f"[SCANNER] Trend scan error: {e}")
                    answer = "[]"
                    
            try:
                trends = json.loads(self._extract_json(answer))
                    for trend in trends:
                        signals.append(MarketSignal(
                            source="trend_scan",
                            category=trend.get("content_type", "content"),
                            title=trend.get("topic", "Trending Topic"),
                            description=trend.get("monetization_angle", ""),
                            estimated_value=float(trend.get("estimated_monthly_usd", 0)),
                            raw_data=trend,
                        ))
                except (json.JSONDecodeError, TypeError):
                    pass
            except Exception as e:
                pass
        
        # Fallback simulated trends
        if not signals:
            trend_topics = [
                ("AI Agent Development", "blog", 500),
                ("Building Chrome Extensions with AI", "video", 800),
                ("Prompt Engineering Masterclass", "course", 2000),
                ("Rust for Web Developers", "blog", 400),
                ("Local LLM Deployment Guide", "tool", 1500),
            ]
            for topic, content_type, value in random.sample(trend_topics, min(3, len(trend_topics))):
                signals.append(MarketSignal(
                    source="trend_scan",
                    category=content_type,
                    title=topic,
                    description=f"Trending topic with {content_type} monetization potential",
                    estimated_value=value,
                ))
        
        return signals

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return text[start:end]
        return "[]"


class ProductGapScanner(SignalSource):
    """Identifies gaps in the market for SaaS / digital product opportunities."""
    
    def __init__(self, generate_fn: Optional[Callable] = None, cache: Optional[MarketCache] = None):
        super().__init__("product_gap_scanner", generate_fn, cache)
        self._scan_interval = 7200  # 2 hours
    
    async def scan(self) -> List[MarketSignal]:
        self._last_scan = time.time()
        logger.info("[SCANNER] 🕳️ Scanning for product gaps...")
        
        signals = []
        
        if self.generate_fn:
            prompt = (
                "You are a product market intelligence engine. Identify 2 REAL market gaps "
                "where a micro-SaaS or digital product could earn money. Consider: "
                "underserved niches, popular tools with missing features, expensive tools "
                "that could be replaced with simpler alternatives. "
                "For each: product_idea, target_market, pricing_model, estimated_mrr, "
                "build_time_hours, competition_level (0-1). Return ONLY a JSON array."
            )
            
            cached_answer = self.cache.get(prompt) if self.cache else None
            answer = cached_answer
            
            if not answer:
                try:
                    result = await asyncio.to_thread(self.generate_fn, prompt)
                    answer = result.answer if hasattr(result, 'answer') else str(result)
                    if self.cache:
                        self.cache.set(prompt, answer)
                except Exception as e:
                    logger.debug(f"[SCANNER] Product gap scan error: {e}")
                    answer = "[]"
                    
            try:
                gaps = json.loads(self._extract_json(answer))
                    for gap in gaps:
                        signals.append(MarketSignal(
                            source="product_gap",
                            category="saas",
                            title=gap.get("product_idea", "Product Idea"),
                            description=gap.get("target_market", ""),
                            estimated_value=float(gap.get("estimated_mrr", 0)),
                            raw_data=gap,
                        ))
                except (json.JSONDecodeError, TypeError):
                    pass
            except Exception as e:
                pass
        
        if not signals:
            gaps = [
                ("CLI Dashboard for API Monitoring", "Developers", 1000),
                ("AI-Powered README Generator", "Open Source Maintainers", 500),
                ("Notion Template Pack for Freelancers", "Freelancers", 300),
            ]
            for idea, market, mrr in random.sample(gaps, min(2, len(gaps))):
                signals.append(MarketSignal(
                    source="product_gap",
                    category="saas",
                    title=idea,
                    description=f"Target market: {market}",
                    estimated_value=mrr,
                ))
        
        return signals

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return text[start:end]
        return "[]"


class OpportunityScanner:
    """
    Master scanner that aggregates signals from all sources,
    deduplicates, scores, and converts them into Opportunity objects
    for the earning pillars.
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self.cache = MarketCache()
        self.sources: List[SignalSource] = [
            FreelancePlatformScanner(generate_fn, cache=self.cache),
            TrendScanner(generate_fn, cache=self.cache),
            ProductGapScanner(generate_fn, cache=self.cache),
        ]
        self._seen_signals: set = set()  # Deduplication
        self._total_scans = 0
        self._total_signals = 0

    def add_source(self, source: SignalSource):
        """Register a new signal source."""
        self.sources.append(source)
        logger.info(f"[SCANNER] Registered new signal source: {source.name}")

    async def scan_all(self) -> List[Opportunity]:
        """
        Scan all sources and return deduplicated, scored Opportunities.
        """
        self._total_scans += 1
        logger.info(f"[SCANNER] 🌐 Starting full market scan (scan #{self._total_scans})...")
        
        all_signals: List[MarketSignal] = []
        
        # Scan all ready sources concurrently
        scan_tasks = []
        for source in self.sources:
            if source.ready_to_scan:
                scan_tasks.append(source.scan())
        
        if scan_tasks:
            results = await asyncio.gather(*scan_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_signals.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"[SCANNER] Source error: {result}")
        
        # Deduplicate
        unique_signals = []
        for signal in all_signals:
            if signal.signal_id not in self._seen_signals:
                self._seen_signals.add(signal.signal_id)
                unique_signals.append(signal)
        
        self._total_signals += len(unique_signals)
        
        # Convert signals to Opportunities
        opportunities = self._signals_to_opportunities(unique_signals)
        
        logger.info(
            f"[SCANNER] Scan complete: {len(unique_signals)} new signals → "
            f"{len(opportunities)} opportunities"
        )
        return opportunities

    def _signals_to_opportunities(self, signals: List[MarketSignal]) -> List[Opportunity]:
        """Convert raw MarketSignals into structured Opportunities."""
        opportunities = []
        
        pillar_map = {
            "freelance_scan": "freelance_hunter",
            "freelance_ai_scan": "freelance_hunter",
            "trend_scan": "content_empire",
            "product_gap": "saas_factory",
        }
        
        for signal in signals:
            pillar = pillar_map.get(signal.source, "general")
            
            opp = Opportunity(
                id=f"opp_{signal.signal_id}",
                pillar=pillar,
                platform=signal.category,
                title=signal.title,
                description=signal.description,
                estimated_revenue_usd=signal.estimated_value,
                difficulty=signal.raw_data.get("difficulty", 0.5),
                time_to_revenue_hours=signal.raw_data.get("build_time_hours", 
                    self._estimate_time(signal.estimated_value)),
                competition_level=signal.raw_data.get("competition_level", 0.5),
                confidence=0.5,  # Initial confidence, refined by pillar's evaluate()
                tags=[signal.source, signal.category],
                metadata=signal.raw_data,
            )
            opportunities.append(opp)
        
        return opportunities

    def _estimate_time(self, value: float) -> float:
        """Rough time estimate based on project value."""
        if value <= 100:
            return 2.0
        elif value <= 500:
            return 8.0
        elif value <= 2000:
            return 20.0
        elif value <= 10000:
            return 60.0
        else:
            return 120.0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_scans": self._total_scans,
            "total_signals_discovered": self._total_signals,
            "unique_signals": len(self._seen_signals),
            "sources": [s.name for s in self.sources],
        }
