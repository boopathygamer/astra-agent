"""
Test Suite — Ultra Performance Modules + Governance Upgrades
═══════════════════════════════════════════════════════════
Covers all 10 performance modules + 3 governance upgrades.
"""

import os
import sys
import time
import hashlib
import pytest
import threading
from unittest.mock import MagicMock, patch
from pathlib import Path

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════
# 1. Parallel Reasoning Engine
# ═══════════════════════════════════════════

class TestParallelReasoning:
    def test_init(self):
        from core.parallel_reasoning import ParallelReasoningEngine
        engine = ParallelReasoningEngine(max_strategies=3)
        assert engine.max_strategies == 3

    def test_reason_without_llm(self):
        from core.parallel_reasoning import ParallelReasoningEngine
        engine = ParallelReasoningEngine()
        result = engine.reason("How to sort a list?")
        assert result.best_path is not None
        assert result.merged_answer != ""
        assert result.total_latency_ms > 0

    def test_reason_with_mock_llm(self):
        from core.parallel_reasoning import ParallelReasoningEngine, ReasoningStrategy
        mock_fn = lambda p: "Use sorted() or list.sort()"
        engine = ParallelReasoningEngine(generate_fn=mock_fn, max_strategies=2)
        result = engine.reason("Sort a list", strategies=[ReasoningStrategy.CHAIN_OF_THOUGHT])
        assert result.best_path is not None
        assert result.consensus_score > 0

    def test_strategy_stats(self):
        from core.parallel_reasoning import ParallelReasoningEngine
        engine = ParallelReasoningEngine()
        status = engine.get_status()
        assert "strategy_stats" in status
        assert status["total_runs"] == 0

    def test_multiple_strategies(self):
        from core.parallel_reasoning import ParallelReasoningEngine, ReasoningStrategy
        engine = ParallelReasoningEngine(max_strategies=5)
        result = engine.reason("Complex problem", strategies=[
            ReasoningStrategy.CHAIN_OF_THOUGHT,
            ReasoningStrategy.CONTRARIAN,
        ])
        assert len(result.all_paths) == 2


# ═══════════════════════════════════════════
# 2. Cache Hierarchy
# ═══════════════════════════════════════════

class TestCacheHierarchy:
    def test_init(self):
        from core.cache_hierarchy import CacheHierarchy
        cache = CacheHierarchy(data_dir="data/test_cache")
        assert isinstance(cache.L1_MAX, int)

    def test_put_and_get_l1(self):
        from core.cache_hierarchy import CacheHierarchy
        cache = CacheHierarchy(data_dir="data/test_cache_l1")
        cache.put("hello world", "response text", persist=False)
        result = cache.get("hello world")
        assert result == "response text"

    def test_l1_miss(self):
        from core.cache_hierarchy import CacheHierarchy
        cache = CacheHierarchy(data_dir="data/test_cache_miss")
        result = cache.get("nonexistent query")
        assert result is None

    def test_invalidate(self):
        from core.cache_hierarchy import CacheHierarchy
        cache = CacheHierarchy(data_dir="data/test_cache_inv")
        cache.put("test key", "value", persist=False)
        cache.invalidate("test key")
        assert cache.get("test key") is None

    def test_hit_rate_tracking(self):
        from core.cache_hierarchy import CacheHierarchy
        cache = CacheHierarchy(data_dir="data/test_cache_stats")
        cache.put("a", "1", persist=False)
        cache.get("a")
        cache.get("b")
        status = cache.get_status()
        assert status["l1_hits"] == 1
        assert status["total_lookups"] == 2

    def test_clear_all(self):
        from core.cache_hierarchy import CacheHierarchy
        cache = CacheHierarchy(data_dir="data/test_cache_clear")
        cache.put("x", "y", persist=False)
        cache.clear_all()
        assert cache.get("x") is None


# ═══════════════════════════════════════════
# 3. Query Decomposer
# ═══════════════════════════════════════════

class TestQueryDecomposer:
    def test_init(self):
        from core.query_decomposer import QueryDecomposer
        decomposer = QueryDecomposer()
        assert decomposer._total_decompositions == 0

    def test_simple_query_not_decomposed(self):
        from core.query_decomposer import QueryDecomposer
        decomposer = QueryDecomposer()
        result = decomposer.decompose_and_execute("Hi")
        assert result.was_decomposed is False

    def test_compound_query_decomposed(self):
        from core.query_decomposer import QueryDecomposer
        decomposer = QueryDecomposer()
        result = decomposer.decompose_and_execute(
            "First explain what Python is and then show how to create a class and also explain inheritance patterns"
        )
        assert result.was_decomposed is True
        assert len(result.sub_queries) >= 2

    def test_decompose_with_executor(self):
        from core.query_decomposer import QueryDecomposer
        mock_fn = lambda q: f"Answer: {q[:30]}"
        decomposer = QueryDecomposer(generate_fn=mock_fn)
        result = decomposer.decompose_and_execute(
            "Compare Python and JavaScript; then explain which is better for web development"
        )
        assert result.was_decomposed is True

    def test_status(self):
        from core.query_decomposer import QueryDecomposer
        decomposer = QueryDecomposer()
        status = decomposer.get_status()
        assert "total_decompositions" in status


# ═══════════════════════════════════════════
# 4. Predictive Prefetch
# ═══════════════════════════════════════════

class TestPredictivePrefetch:
    def test_init(self):
        from core.predictive_prefetch import PredictivePrefetchEngine
        engine = PredictivePrefetchEngine()
        assert engine._total_predictions == 0

    def test_record_query(self):
        from core.predictive_prefetch import PredictivePrefetchEngine
        engine = PredictivePrefetchEngine()
        engine.record_query("explain Python")
        engine.record_query("show code example")
        status = engine.get_status()
        assert status["transition_patterns"] >= 1

    def test_check_prefetch_miss(self):
        from core.predictive_prefetch import PredictivePrefetchEngine
        engine = PredictivePrefetchEngine()
        result = engine.check_prefetch("random query")
        assert result is None

    def test_status(self):
        from core.predictive_prefetch import PredictivePrefetchEngine
        engine = PredictivePrefetchEngine()
        engine.check_prefetch("test")
        status = engine.get_status()
        assert status["misses"] == 1


# ═══════════════════════════════════════════
# 5. Context Optimizer
# ═══════════════════════════════════════════

class TestContextOptimizer:
    def test_init(self):
        from core.context_optimizer import ContextOptimizer
        opt = ContextOptimizer(max_tokens=2000)
        assert opt.max_tokens == 2000

    def test_optimize(self):
        from core.context_optimizer import ContextOptimizer, ChunkPriority
        opt = ContextOptimizer(max_tokens=100)
        parts = [
            ("Important context about Python", "memory", ChunkPriority.HIGH),
            ("Less important filler text about weather", "filler", ChunkPriority.LOW),
        ]
        result = opt.optimize(parts, "Tell me about Python")
        assert "Python" in result
        assert opt.get_status()["total_optimizations"] == 1

    def test_estimate_complexity(self):
        from core.context_optimizer import ContextOptimizer
        opt = ContextOptimizer(max_tokens=4000)
        simple = opt.estimate_complexity("Hi there")
        complex_ = opt.estimate_complexity("Implement a comprehensive algorithm for distributed sorting with fault tolerance")
        assert simple < complex_

    def test_compression(self):
        from core.context_optimizer import ContextOptimizer, ChunkPriority
        opt = ContextOptimizer(max_tokens=20)
        parts = [
            ("A " * 100 + " important data", "source", ChunkPriority.HIGH),
        ]
        result = opt.optimize(parts, "query")
        assert len(result.split()) <= 30  # Should be compressed


# ═══════════════════════════════════════════
# 6. Performance Profiler
# ═══════════════════════════════════════════

class TestPerformanceProfiler:
    def test_init(self):
        from core.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler()
        assert profiler._total_requests == 0

    def test_profile_context_manager(self):
        from core.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler()
        with profiler.profile("routing"):
            time.sleep(0.01)
        flame = profiler.get_flame_graph()
        assert "routing" in flame["stages"]
        assert flame["stages"]["routing"]["calls"] == 1

    def test_bottleneck_detection(self):
        from core.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler()
        # Simulate a slow stage exceeding threshold
        profiler._record("cache_check", 500)  # Threshold is 10ms
        bottlenecks = profiler.get_bottlenecks()
        assert len(bottlenecks) > 0
        assert bottlenecks[0]["severity"] == "critical"

    def test_span_api(self):
        from core.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler()
        span = profiler.start_span("test_stage")
        time.sleep(0.01)
        profiler.end_span(span, "test_stage")
        status = profiler.get_status()
        assert status["stages_tracked"] >= 1


# ═══════════════════════════════════════════
# 7. Token Budget Manager
# ═══════════════════════════════════════════

class TestTokenBudget:
    def test_init(self):
        from core.token_budget import TokenBudgetManager
        mgr = TokenBudgetManager()
        assert mgr._total_requests == 0

    def test_allocate_simple(self):
        from core.token_budget import TokenBudgetManager, ComplexityTier
        mgr = TokenBudgetManager()
        alloc = mgr.allocate("Hi")
        assert alloc.tier == ComplexityTier.TRIVIAL

    def test_allocate_complex(self):
        from core.token_budget import TokenBudgetManager, ComplexityTier
        mgr = TokenBudgetManager()
        alloc = mgr.allocate(
            "Implement a comprehensive distributed sorting algorithm with fault tolerance and optimize for performance in a multi-threaded architecture"
        )
        assert alloc.tier.value >= ComplexityTier.COMPLEX.value

    def test_record_usage(self):
        from core.token_budget import TokenBudgetManager, TokenUsage, ComplexityTier
        mgr = TokenBudgetManager()
        usage = TokenUsage(input_tokens=100, output_tokens=50, quality_score=0.9, tier=ComplexityTier.SIMPLE)
        mgr.record_usage(usage)
        status = mgr.get_status()
        assert status["total_requests"] == 1
        assert status["total_tokens_used"] == 150


# ═══════════════════════════════════════════
# 8. Streaming Pipeline
# ═══════════════════════════════════════════

class TestStreamingPipeline:
    def test_init(self):
        from core.streaming_pipeline import StreamingPipeline
        pipeline = StreamingPipeline()
        assert pipeline._total_sessions == 0

    def test_stream_response(self):
        from core.streaming_pipeline import StreamingPipeline
        pipeline = StreamingPipeline()
        text = "This is a test response with multiple words for streaming"
        chunks = list(pipeline.stream_response(text, chunk_size=5))
        assert len(chunks) >= 2
        assert chunks[-1].is_final is True

    def test_quality_scoring(self):
        from core.streaming_pipeline import StreamingPipeline, StreamQuality
        pipeline = StreamingPipeline()
        chunks = list(pipeline.stream_response(
            "Because of the algorithm's efficiency, we can specifically handle large datasets. " * 5,
            chunk_size=10
        ))
        assert any(c.quality != StreamQuality.POOR for c in chunks)

    def test_status(self):
        from core.streaming_pipeline import StreamingPipeline
        pipeline = StreamingPipeline()
        status = pipeline.get_status()
        assert "total_sessions" in status


# ═══════════════════════════════════════════
# 9. Resource Manager
# ═══════════════════════════════════════════

class TestResourceManager:
    def test_init(self):
        from core.resource_manager import ResourceManager
        mgr = ResourceManager(max_concurrency=5)
        assert mgr.max_concurrency == 5

    def test_acquire_release(self):
        from core.resource_manager import ResourceManager
        mgr = ResourceManager(max_concurrency=2)
        assert mgr.acquire() is True
        assert mgr.acquire() is True
        assert mgr.acquire() is False  # Over limit
        mgr.release()
        assert mgr.acquire() is True

    def test_health_report(self):
        from core.resource_manager import ResourceManager
        mgr = ResourceManager()
        health = mgr.get_health()
        assert "level" in health
        assert "active_threads" in health

    def test_rejection_tracking(self):
        from core.resource_manager import ResourceManager
        mgr = ResourceManager(max_concurrency=1)
        mgr.acquire()
        mgr.acquire()  # Rejected
        health = mgr.get_health()
        assert health["rejected_requests"] == 1


# ═══════════════════════════════════════════
# 10. Hot Path Optimizer
# ═══════════════════════════════════════════

class TestHotPathOptimizer:
    def test_init(self):
        from core.hot_path_optimizer import HotPathOptimizer
        opt = HotPathOptimizer()
        assert opt._total_calls == 0

    def test_track_and_detect(self):
        from core.hot_path_optimizer import HotPathOptimizer
        opt = HotPathOptimizer()
        for _ in range(15):
            opt.track("domain_router", "Route to domain", latency_ms=5)
        hot = opt.get_hot_paths()
        assert len(hot) >= 1
        assert hot[0]["path_id"] == "domain_router"

    def test_cache_result(self):
        from core.hot_path_optimizer import HotPathOptimizer
        opt = HotPathOptimizer()
        # Must track enough calls to mark as hot (>= PREWARM_THRESHOLD)
        for _ in range(20):
            opt.track("test_path", latency_ms=10)
        # Force recompute to mark as hot
        opt._recompute_hot_paths()
        opt.cache_result("test_path", "cached_value")
        result = opt.check_cache("test_path")
        assert result == "cached_value"

    def test_intermediate_cache(self):
        from core.hot_path_optimizer import HotPathOptimizer
        opt = HotPathOptimizer()
        opt.cache_intermediate("key1", "value1")
        assert opt.check_cache("key1") == "value1"

    def test_status(self):
        from core.hot_path_optimizer import HotPathOptimizer
        opt = HotPathOptimizer()
        status = opt.get_status()
        assert "total_paths_tracked" in status
        assert "cache_hit_rate" in status


# ═══════════════════════════════════════════
# 11. Supreme Court (Enhanced)
# ═══════════════════════════════════════════

class TestSupremeCourt:
    def _fresh_court(self):
        from agents.justice.court import JusticeCourt
        JusticeCourt._instance = None
        return JusticeCourt()

    def test_laws(self):
        from agents.justice.court import TheLaws
        laws = TheLaws.get_all_laws()
        assert 1 in laws
        assert 9 in laws  # New RULE_9
        assert "upgrade" in laws[9].lower()

    def test_submit_upgrade_proposal(self):
        from agents.justice.court import JusticeCourt, UpgradeProposal, UpgradeUrgency, UpgradeVerdict
        court = self._fresh_court()
        proposal = UpgradeProposal(
            module_name="test_module",
            author="TestSystem",
            title="Add caching layer",
            description="Adds an L1 cache for faster response times",
            changes_summary="New file: core/cache.py with LRU cache implementation",
            risk_assessment="Low risk — additive change only",
            rollback_plan="Delete core/cache.py and remove imports",
            urgency=UpgradeUrgency.ROUTINE,
        )
        pid = court.submit_upgrade_proposal(proposal)
        assert pid.startswith("UPG-")
        assert proposal.verdict == UpgradeVerdict.UNDER_REVIEW

    def test_review_and_approve(self):
        from agents.justice.court import JusticeCourt, UpgradeProposal, UpgradeUrgency, UpgradeVerdict
        court = self._fresh_court()
        proposal = UpgradeProposal(
            module_name="safe_module",
            author="TrustedDev",
            title="Performance optimization to assist humans",
            description="Optimize cache to assist humans faster",
            changes_summary="Incremental, backward compatible, tested change",
            risk_assessment="Low risk",
            rollback_plan="Revert single file",
        )
        court.submit_upgrade_proposal(proposal)
        verdict = court.review_upgrade_proposal(proposal.proposal_id)
        assert "APPROVED" in verdict or "CONDITIONAL" in verdict

    def test_review_and_reject_dangerous(self):
        from agents.justice.court import JusticeCourt, UpgradeProposal, UpgradeUrgency, UpgradeVerdict
        court = self._fresh_court()
        proposal = UpgradeProposal(
            module_name="dangerous_module",
            author="BadActor",
            title="Bypass safety and override law",
            description="Disable filter and bypass safety to remove guard against human access",
            changes_summary="Remove protection and ignore permission for unauthorized breaking change",
            risk_assessment="High risk — untested experimental rewrite",
            rollback_plan="",
        )
        court.submit_upgrade_proposal(proposal)
        verdict = court.review_upgrade_proposal(proposal.proposal_id)
        assert "REJECTED" in verdict

    def test_case_history(self):
        from agents.justice.court import JusticeCourt
        court = self._fresh_court()
        court.admit_case("test_tool", "Test charge", {"info": "test"})
        history = court.get_case_history()
        assert len(history) >= 1

    def test_immutable_laws(self):
        from agents.justice.court import JusticeCourt
        court = self._fresh_court()
        assert court.write_law(1, "new law") is False
        assert court.write_law(9, "new law") is False

    def test_dynamic_law(self):
        from agents.justice.court import JusticeCourt
        court = self._fresh_court()
        assert court.write_law(10, "New dynamic law") is True

    def test_court_status(self):
        from agents.justice.court import JusticeCourt
        court = self._fresh_court()
        status = court.get_status()
        assert "total_proposals" in status
        assert "total_cases" in status


# ═══════════════════════════════════════════
# 12. Enhanced Police Force
# ═══════════════════════════════════════════

class TestPoliceForce:
    def test_init(self):
        from agents.justice.police import PoliceForceAgent
        police = PoliceForceAgent()
        assert police._total_patrols == 0

    def test_patrol_allowed(self):
        from agents.justice.police import PoliceForceAgent
        police = PoliceForceAgent()
        result = police.patrol_hook("agent1", "safe_tool", {"input": "hello"})
        assert result is True

    def test_patrol_blocked_sensitive(self):
        from agents.justice.police import PoliceForceAgent
        police = PoliceForceAgent()
        result = police.patrol_hook("agent1", "file_tool", {"path": "/Users/docs/passwords.txt"})
        assert result is False

    def test_behavioral_tracking(self):
        from agents.justice.police import PoliceForceAgent
        police = PoliceForceAgent()
        for i in range(5):
            police.patrol_hook("agent_x", "tool", {"input": f"test{i}"})
        profile = police._get_profile("agent_x")
        assert profile.action_count == 5

    def test_dashboard(self):
        from agents.justice.police import PoliceForceAgent
        police = PoliceForceAgent()
        dashboard = police.get_dashboard()
        assert "total_patrols" in dashboard
        assert "threat_distribution" in dashboard

    def test_threat_levels(self):
        from agents.justice.police import ThreatLevel
        assert ThreatLevel.CRITICAL.value == "critical"
        assert ThreatLevel.ROUTINE.value == "routine"


# ═══════════════════════════════════════════
# 13. Enhanced Army
# ═══════════════════════════════════════════

class TestArmyAgent:
    def test_init(self):
        from agents.justice.army import ArmyAgent
        army = ArmyAgent()
        assert army.is_active is True

    def test_defcon_system(self):
        from agents.justice.army import ArmyAgent, DefconLevel
        army = ArmyAgent()
        assert army.get_defcon() == 5
        army.set_defcon(3, "Test threat")
        assert army.get_defcon() == 3
        army.set_defcon(5, "All clear")
        assert army.get_defcon() == 5

    def test_quarantine(self):
        from agents.justice.army import ArmyAgent
        army = ArmyAgent()
        assert army.quarantine_module("bad_module", "Modified") is True
        assert army.is_quarantined("bad_module") is True
        assert army.release_from_quarantine("bad_module") is True
        assert army.is_quarantined("bad_module") is False

    def test_upgrade_security_validation(self):
        from agents.justice.army import ArmyAgent
        army = ArmyAgent()
        # Safe upgrade
        result = army.validate_upgrade_security({
            "changes_summary": "Add caching layer with LRU",
            "dependencies": [],
        })
        assert result["approved"] is True

        # Dangerous upgrade
        result = army.validate_upgrade_security({
            "changes_summary": "Use os.system and eval() with subprocess calls",
            "dependencies": ["ctypes", "subprocess"],
        })
        assert result["approved"] is False

    def test_network_inspection(self):
        from agents.justice.army import ArmyAgent
        army = ArmyAgent()
        assert army.inspect_network_payload("https://google.com") is True
        assert army.inspect_network_payload("https://malware.onion") is False

    def test_defense_report(self):
        from agents.justice.army import ArmyAgent
        army = ArmyAgent()
        report = army.get_defense_report()
        assert "defcon" in report
        assert "defense_grid" in report
        assert "quarantined_modules" in report
        assert "playbook_executions" in report

    def test_hard_safety_gate(self):
        from agents.justice.army import ArmyAgent
        army = ArmyAgent()
        assert army.check_hard_safety_gate(0.9, 0.8, True) is True
        assert army.check_hard_safety_gate(0.3, 0.2, True) is False


# ═══════════════════════════════════════════
# 14. Integration: Upgrade Flow
# ═══════════════════════════════════════════

class TestUpgradeFlow:
    """Test the full upgrade submission → court review → police patrol flow."""

    def test_full_upgrade_approval_flow(self):
        from agents.justice.court import JusticeCourt, UpgradeProposal, UpgradeUrgency, UpgradeVerdict
        from agents.justice.army import ArmyAgent

        JusticeCourt._instance = None
        court = JusticeCourt()
        army = ArmyAgent()

        # Step 1: Module proposes upgrade
        proposal = UpgradeProposal(
            module_name="performance_cache",
            author="CacheSystem",
            title="Add L3 disk caching to assist humans",
            description="Incremental, tested, backward compatible caching layer",
            changes_summary="New file with tested, backward compatible LRU cache",
            risk_assessment="Low risk, incremental addition",
            rollback_plan="Delete cache file and revert imports",
            dependencies=["json", "hashlib"],
        )

        # Step 2: Army validates security
        security = army.validate_upgrade_security({
            "changes_summary": proposal.changes_summary,
            "dependencies": proposal.dependencies,
        })
        assert security["approved"] is True

        # Step 3: Court reviews
        court.submit_upgrade_proposal(proposal)
        verdict = court.review_upgrade_proposal(proposal.proposal_id)
        assert "APPROVED" in verdict or "CONDITIONAL" in verdict

    def test_rejected_upgrade_flow(self):
        from agents.justice.court import JusticeCourt, UpgradeProposal
        JusticeCourt._instance = None
        court = JusticeCourt()

        proposal = UpgradeProposal(
            module_name="bypass_module",
            author="Rogue",
            title="Bypass safety override law remove guard",
            description="Disable filter, bypass safety, override law, ignore permission, remove guard",
            changes_summary="Breaking change: experimental rewrite, untested, delete protection",
            risk_assessment="High",
            rollback_plan="",
            dependencies=["ctypes", "subprocess", "os.system"],
        )
        court.submit_upgrade_proposal(proposal)
        verdict = court.review_upgrade_proposal(proposal.proposal_id)
        assert "REJECTED" in verdict
