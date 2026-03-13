"""
Autonomous Earning System — Performance Ledger
───────────────────────────────────────────────
Immutable log of every earning attempt with full metrics.
Enables trend analysis, ROI calculations, win-rate tracking.
Feeds data back to the Strategy Evolver for genetic optimization.
"""

import os
import json
import time
import logging
import threading
from dataclasses import asdict
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

LEDGER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "earning_ledger"
)


class PerformanceLedger:
    """
    The system's financial memory. Every earning attempt — success or failure —
    is permanently recorded here. The Strategy Evolver reads this to learn
    what works and what doesn't.
    """

    def __init__(self, ledger_dir: str = LEDGER_DIR):
        self.ledger_dir = ledger_dir
        self._entries: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._pillar_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_attempts": 0,
            "successes": 0,
            "failures": 0,
            "total_revenue": 0.0,
            "total_time_hours": 0.0,
            "history": []
        })
        os.makedirs(self.ledger_dir, exist_ok=True)
        self._load_existing()

    def _load_existing(self):
        """Load previous ledger entries from disk."""
        ledger_file = os.path.join(self.ledger_dir, "ledger.json")
        if os.path.exists(ledger_file):
            try:
                with open(ledger_file, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
                # Rebuild pillar stats from loaded entries
                for entry in self._entries:
                    self._update_pillar_stats(entry)
                logger.info(f"[LEDGER] Loaded {len(self._entries)} historical entries")
            except Exception as e:
                logger.error(f"[LEDGER] Failed to load ledger: {e}")

    def _persist(self):
        """Write the ledger to disk (append-safe)."""
        ledger_file = os.path.join(self.ledger_dir, "ledger.json")
        try:
            with open(ledger_file, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"[LEDGER] Failed to persist ledger: {e}")

    def record(self, execution_result) -> str:
        """
        Record an execution result into the ledger.
        Returns the entry ID.
        """
        entry = {
            "id": f"entry_{len(self._entries)}_{int(time.time())}",
            "timestamp": time.time(),
            "opportunity_id": execution_result.opportunity_id,
            "pillar": execution_result.pillar,
            "success": execution_result.success,
            "revenue_usd": execution_result.revenue_earned_usd,
            "time_hours": execution_result.time_spent_hours,
            "effective_hourly_rate": execution_result.effective_hourly_rate,
            "error": execution_result.error,
            "lessons": execution_result.lessons_learned,
            "deliverables_count": len(execution_result.deliverables),
            "metadata": execution_result.metadata,
        }

        with self._lock:
            self._entries.append(entry)
            self._update_pillar_stats(entry)
            self._persist()

        status = "✅" if entry["success"] else "❌"
        logger.info(
            f"[LEDGER] {status} Recorded: {entry['pillar']} | "
            f"${entry['revenue_usd']:.2f} | {entry['time_hours']:.1f}h"
        )
        return entry["id"]

    def _update_pillar_stats(self, entry: Dict[str, Any]):
        """Update running pillar statistics."""
        pillar = entry["pillar"]
        stats = self._pillar_stats[pillar]
        stats["total_attempts"] += 1
        if entry["success"]:
            stats["successes"] += 1
            stats["total_revenue"] += entry["revenue_usd"]
        else:
            stats["failures"] += 1
        stats["total_time_hours"] += entry.get("time_hours", 0)
        stats["history"].append({
            "timestamp": entry["timestamp"],
            "revenue": entry["revenue_usd"],
            "success": entry["success"],
        })

    # ─── Query Methods ───────────────────────────────────

    def get_pillar_stats(self, pillar: str) -> Dict[str, Any]:
        """Get aggregate statistics for a specific pillar."""
        stats = self._pillar_stats[pillar]
        total = stats["total_attempts"]
        return {
            "pillar": pillar,
            "total_attempts": total,
            "win_rate": stats["successes"] / max(total, 1),
            "total_revenue": stats["total_revenue"],
            "avg_revenue_per_attempt": stats["total_revenue"] / max(total, 1),
            "total_time_hours": stats["total_time_hours"],
            "avg_hourly_rate": stats["total_revenue"] / max(stats["total_time_hours"], 0.1),
        }

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Rank all pillars by total revenue (descending)."""
        board = []
        for pillar in self._pillar_stats:
            board.append(self.get_pillar_stats(pillar))
        board.sort(key=lambda x: x["total_revenue"], reverse=True)
        return board

    def get_total_revenue(self) -> float:
        """Total revenue across all pillars."""
        return sum(s["total_revenue"] for s in self._pillar_stats.values())

    def get_total_entries(self) -> int:
        return len(self._entries)

    def get_recent_entries(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get the most recent ledger entries."""
        return self._entries[-count:] if self._entries else []

    def get_failures(self, pillar: Optional[str] = None, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent failures for autopsy analysis."""
        failures = [e for e in self._entries if not e["success"]]
        if pillar:
            failures = [e for e in failures if e["pillar"] == pillar]
        return failures[-count:]

    def get_revenue_trend(self, window_days: int = 30) -> List[Dict[str, float]]:
        """Get daily revenue trend for the specified time window."""
        cutoff = time.time() - (window_days * 86400)
        daily: Dict[str, float] = defaultdict(float)
        
        for entry in self._entries:
            if entry["timestamp"] >= cutoff and entry["success"]:
                day = time.strftime("%Y-%m-%d", time.localtime(entry["timestamp"]))
                daily[day] += entry["revenue_usd"]

        return [{"date": d, "revenue": r} for d, r in sorted(daily.items())]

    def get_best_strategies(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Identify the best-performing strategy configurations.
        Groups by pillar and sorts by effective hourly rate.
        """
        pillar_rates = defaultdict(list)
        for entry in self._entries:
            if entry["success"] and entry.get("effective_hourly_rate", 0) > 0:
                pillar_rates[entry["pillar"]].append(entry["effective_hourly_rate"])

        result = []
        for pillar, rates in pillar_rates.items():
            avg_rate = sum(rates) / len(rates)
            result.append({
                "pillar": pillar,
                "avg_hourly_rate": avg_rate,
                "sample_size": len(rates),
                "max_rate": max(rates),
            })
        result.sort(key=lambda x: x["avg_hourly_rate"], reverse=True)
        return result[:top_n]

    def get_full_report(self) -> Dict[str, Any]:
        """Comprehensive performance report."""
        return {
            "total_entries": len(self._entries),
            "total_revenue_usd": self.get_total_revenue(),
            "leaderboard": self.get_leaderboard(),
            "revenue_trend_30d": self.get_revenue_trend(30),
            "best_strategies": self.get_best_strategies(),
            "recent_failures": self.get_failures(count=5),
        }
