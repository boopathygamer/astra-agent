"""
Earning System — Dashboard API
──────────────────────────────
REST API endpoints for the autonomous earning system.
Provides real-time revenue metrics, active pillars, strategy leaderboard,
and human approval/rejection of pending opportunities.
"""

import json
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class EarningDashboardAPI:
    """
    API layer for the earning system dashboard.
    
    Endpoints (to be wired into the FastAPI/Flask router):
    - GET  /earning/dashboard     — Full dashboard overview
    - GET  /earning/leaderboard   — Strategy leaderboard
    - GET  /earning/revenue       — Revenue data and trends
    - GET  /earning/pillars       — All pillar statuses
    - GET  /earning/approvals     — Pending human approvals
    - POST /earning/approve/{id}  — Approve an opportunity
    - POST /earning/reject/{id}   — Reject an opportunity
    - GET  /earning/evolution     — Strategy evolution report
    - POST /earning/start         — Start the earning system
    - POST /earning/stop          — Stop the earning system
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def get_dashboard(self) -> Dict[str, Any]:
        """Full system overview."""
        return self.orchestrator.get_dashboard()

    def get_leaderboard(self) -> Dict[str, Any]:
        """Pillar performance ranking."""
        return {
            "leaderboard": self.orchestrator.ledger.get_leaderboard(),
            "total_revenue": self.orchestrator.ledger.get_total_revenue(),
            "best_strategies": self.orchestrator.ledger.get_best_strategies(),
        }

    def get_revenue(self, days: int = 30) -> Dict[str, Any]:
        """Revenue data and trends."""
        return {
            "total_revenue": self.orchestrator.ledger.get_total_revenue(),
            "trend": self.orchestrator.ledger.get_revenue_trend(days),
            "recent_entries": self.orchestrator.ledger.get_recent_entries(10),
        }

    def get_pillar_statuses(self) -> Dict[str, Any]:
        """Status of all earning pillars."""
        return {
            name: pillar.get_status()
            for name, pillar in self.orchestrator._pillars.items()
        }

    def get_pending_approvals(self) -> Dict[str, Any]:
        """Opportunities awaiting human approval."""
        return {
            "count": len(self.orchestrator.get_pending_approvals()),
            "approvals": self.orchestrator.get_pending_approvals(),
        }

    def approve_opportunity(self, opportunity_id: str) -> Dict[str, Any]:
        """Approve a pending opportunity."""
        success = self.orchestrator.approve_opportunity(opportunity_id)
        return {"approved": success, "opportunity_id": opportunity_id}

    def reject_opportunity(self, opportunity_id: str) -> Dict[str, Any]:
        """Reject a pending opportunity."""
        success = self.orchestrator.reject_opportunity(opportunity_id)
        return {"rejected": success, "opportunity_id": opportunity_id}

    def get_evolution_report(self) -> Dict[str, Any]:
        """Strategy evolution progress."""
        if hasattr(self.orchestrator, 'evolver') and self.orchestrator.evolver:
            return self.orchestrator.evolver.get_evolution_report()
        return {"message": "Evolution engine not active"}

    def get_ethics_stats(self) -> Dict[str, Any]:
        """Ethics filter statistics."""
        return self.orchestrator.ethics.get_stats()

    def get_scanner_stats(self) -> Dict[str, Any]:
        """Opportunity scanner statistics."""
        return self.orchestrator.scanner.get_stats()


def register_earning_routes(app, orchestrator):
    """
    Register earning system routes with a FastAPI or Flask app.
    Call this from main.py to wire up the dashboard.
    
    Usage:
        from api.earning_dashboard import register_earning_routes, EarningDashboardAPI
        dashboard = EarningDashboardAPI(orchestrator)
        register_earning_routes(app, orchestrator)
    """
    dashboard = EarningDashboardAPI(orchestrator)
    
    try:
        # Try FastAPI-style routing first
        from fastapi import APIRouter
        router = APIRouter(prefix="/earning", tags=["Earning System"])
        
        @router.get("/dashboard")
        async def dashboard_overview():
            return dashboard.get_dashboard()
        
        @router.get("/leaderboard")
        async def leaderboard():
            return dashboard.get_leaderboard()
        
        @router.get("/revenue")
        async def revenue(days: int = 30):
            return dashboard.get_revenue(days)
        
        @router.get("/pillars")
        async def pillar_statuses():
            return dashboard.get_pillar_statuses()
        
        @router.get("/approvals")
        async def pending_approvals():
            return dashboard.get_pending_approvals()
        
        @router.post("/approve/{opportunity_id}")
        async def approve(opportunity_id: str):
            return dashboard.approve_opportunity(opportunity_id)
        
        @router.post("/reject/{opportunity_id}")
        async def reject(opportunity_id: str):
            return dashboard.reject_opportunity(opportunity_id)
        
        @router.get("/evolution")
        async def evolution():
            return dashboard.get_evolution_report()
        
        @router.get("/ethics")
        async def ethics():
            return dashboard.get_ethics_stats()
        
        @router.get("/scanner")
        async def scanner():
            return dashboard.get_scanner_stats()
        
        app.include_router(router)
        logger.info("[DASHBOARD] Earning API routes registered (FastAPI)")
        
    except ImportError:
        # Fallback: just log that routes need manual wiring
        logger.info("[DASHBOARD] FastAPI not available. Use EarningDashboardAPI directly.")
