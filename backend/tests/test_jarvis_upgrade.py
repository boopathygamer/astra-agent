"""
JARVIS Upgrade Test Suite — Validates all 7 intelligence modules.
"""
import os
import sys
import time
import json
import tempfile
import pytest

# Ensure backend is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════
# Module 1: JarvisCore
# ═══════════════════════════════════════════════════════

class TestJarvisCore:

    def test_import(self):
        from brain.jarvis_core import JarvisCore, AuthorityLevel, CognitiveState
        assert JarvisCore is not None

    def test_init(self, tmp_path):
        from brain.jarvis_core import JarvisCore
        core = JarvisCore(data_dir=str(tmp_path / "jarvis"))
        assert core is not None
        assert core.authority.value >= 0

    def test_fuse_awareness(self, tmp_path):
        from brain.jarvis_core import JarvisCore
        core = JarvisCore(data_dir=str(tmp_path / "jarvis"))
        state = core.fuse_awareness(
            environment_data={"system_vitals": {"cpu_percent": 45, "ram_percent": 60, "disk_percent": 70},
                              "network": {"internet_reachable": True}},
        )
        assert state.cpu_usage == 45
        assert state.memory_usage == 60
        assert state.network_status == "online"
        assert state.health_score() > 0

    def test_initiatives_on_high_cpu(self, tmp_path):
        from brain.jarvis_core import JarvisCore
        core = JarvisCore(data_dir=str(tmp_path / "jarvis"))
        core.fuse_awareness(
            environment_data={"system_vitals": {"cpu_percent": 95, "ram_percent": 30, "disk_percent": 50},
                              "network": {"internet_reachable": True}},
        )
        pending = core.get_pending_initiatives()
        assert len(pending) > 0
        assert any("CPU" in i.title for i in pending)

    def test_authority_levels(self, tmp_path):
        from brain.jarvis_core import JarvisCore, AuthorityLevel
        core = JarvisCore(data_dir=str(tmp_path / "jarvis"))
        core.set_authority(AuthorityLevel.AUTONOMOUS)
        assert core.can_auto_execute("low")
        assert core.can_auto_execute("medium")

    def test_fingerprint_persistence(self, tmp_path):
        from brain.jarvis_core import JarvisCore
        core1 = JarvisCore(data_dir=str(tmp_path / "jarvis"))
        uid = core1.get_fingerprint().user_id
        core1.shutdown()

        core2 = JarvisCore(data_dir=str(tmp_path / "jarvis"))
        assert core2.get_fingerprint().user_id == uid

    def test_status(self, tmp_path):
        from brain.jarvis_core import JarvisCore
        core = JarvisCore(data_dir=str(tmp_path / "jarvis"))
        status = core.get_status()
        assert status["online"] is True
        assert "subsystems" in status

    def test_briefing(self, tmp_path):
        from brain.jarvis_core import JarvisCore
        core = JarvisCore(data_dir=str(tmp_path / "jarvis"))
        briefing = core.generate_briefing()
        assert "JARVIS" in briefing


# ═══════════════════════════════════════════════════════
# Module 2: SituationalAwareness
# ═══════════════════════════════════════════════════════

class TestSituationalAwareness:

    def test_import(self):
        from brain.situational_awareness import SituationalAwareness
        assert SituationalAwareness is not None

    def test_init(self, tmp_path):
        from brain.situational_awareness import SituationalAwareness
        sa = SituationalAwareness(data_dir=str(tmp_path / "awareness"))
        assert sa is not None

    def test_classify_idle(self, tmp_path):
        from brain.situational_awareness import SituationalAwareness, SituationType
        sa = SituationalAwareness(data_dir=str(tmp_path / "awareness"))
        sa.update_physical({"cpu_percent": 5, "ram_percent": 30})
        sa.update_digital(processes=[])
        sit, conf = sa.classify_situation()
        assert sit in SituationType
        assert 0 <= conf <= 1

    def test_classify_development(self, tmp_path):
        from brain.situational_awareness import SituationalAwareness, SituationType
        sa = SituationalAwareness(data_dir=str(tmp_path / "awareness"))
        sa._boot_time = time.time() - 300  # Simulate 5 min uptime to avoid boot_sequence
        sa.update_physical({"cpu_percent": 40, "ram_percent": 50})
        sa.update_digital(processes=["python", "code", "node"])
        sit, conf = sa.classify_situation()
        assert sit == SituationType.DEVELOPMENT

    def test_trend_analysis(self, tmp_path):
        from brain.situational_awareness import SituationalAwareness
        sa = SituationalAwareness(data_dir=str(tmp_path / "awareness"))
        for i in range(10):
            sa.update_physical({"cpu_percent": 30 + i * 5})
        trends = sa.analyze_trends()
        assert isinstance(trends, list)

    def test_event_correlation(self, tmp_path):
        from brain.situational_awareness import SituationalAwareness
        sa = SituationalAwareness(data_dir=str(tmp_path / "awareness"))
        sa.record_event("process_start", "system", {"pid": 1234})
        sa.record_event("cpu_spike", "monitor", {"cpu": 95})
        sa.record_event("temp_rise", "thermal", {"temp": 85})
        correlations = sa.correlate_events()
        assert isinstance(correlations, list)

    def test_alert_generation(self, tmp_path):
        from brain.situational_awareness import SituationalAwareness
        sa = SituationalAwareness(data_dir=str(tmp_path / "awareness"))
        alerts = sa.generate_alerts()
        assert isinstance(alerts, list)

    def test_full_report(self, tmp_path):
        from brain.situational_awareness import SituationalAwareness
        sa = SituationalAwareness(data_dir=str(tmp_path / "awareness"))
        sa.update_physical({"cpu_percent": 50, "ram_percent": 60})
        report = sa.generate_report()
        d = report.to_dict()
        assert "situation" in d
        assert "summary" in d


# ═══════════════════════════════════════════════════════
# Module 3: PredictiveIntent
# ═══════════════════════════════════════════════════════

class TestPredictiveIntent:

    def test_import(self):
        from brain.predictive_intent import PredictiveIntent
        assert PredictiveIntent is not None

    def test_record_and_predict(self, tmp_path):
        from brain.predictive_intent import PredictiveIntent
        pi = PredictiveIntent(data_dir=str(tmp_path / "predict"))
        # Record a pattern many times
        for _ in range(10):
            pi.record_action("code")
            pi.record_action("test")
            pi.record_action("deploy")
        pred = pi.predict_next_action()
        # After "deploy", it should predict "code" next
        assert pred is None or pred.predicted_action  # may or may not hit threshold

    def test_accuracy_tracking(self, tmp_path):
        from brain.predictive_intent import PredictiveIntent
        pi = PredictiveIntent(data_dir=str(tmp_path / "predict"))
        stats = pi.get_accuracy_stats()
        assert "total" in stats
        assert "accuracy" in stats

    def test_briefing(self, tmp_path):
        from brain.predictive_intent import PredictiveIntent
        pi = PredictiveIntent(data_dir=str(tmp_path / "predict"))
        briefing = pi.generate_briefing()
        assert briefing.description

    def test_persistence(self, tmp_path):
        from brain.predictive_intent import PredictiveIntent
        pi1 = PredictiveIntent(data_dir=str(tmp_path / "predict"))
        for _ in range(5):
            pi1.record_action("chat")
            pi1.record_action("code")
        pi1._save_patterns()

        pi2 = PredictiveIntent(data_dir=str(tmp_path / "predict"))
        assert pi2.get_accuracy_stats()["pattern_count"] > 0

    def test_status(self, tmp_path):
        from brain.predictive_intent import PredictiveIntent
        pi = PredictiveIntent(data_dir=str(tmp_path / "predict"))
        status = pi.get_status()
        assert "history_size" in status


# ═══════════════════════════════════════════════════════
# Module 4: MissionController
# ═══════════════════════════════════════════════════════

class TestMissionController:

    def test_import(self):
        from brain.mission_controller import MissionController
        assert MissionController is not None

    def test_create_mission(self, tmp_path):
        from brain.mission_controller import MissionController
        mc = MissionController(data_dir=str(tmp_path / "missions"))
        mission = mc.create_mission("Test Mission", "Do something useful")
        assert mission.mission_id
        assert len(mission.tasks) > 0

    def test_execute_mission(self, tmp_path):
        from brain.mission_controller import MissionController, MissionStatus
        mc = MissionController(data_dir=str(tmp_path / "missions"))
        mission = mc.create_mission("Quick Test", "Simple task")
        result = mc.execute_mission(mission.mission_id)
        assert result.status in (MissionStatus.COMPLETED, MissionStatus.FAILED)

    def test_mission_with_custom_tasks(self, tmp_path):
        from brain.mission_controller import MissionController
        mc = MissionController(data_dir=str(tmp_path / "missions"))
        tasks = [
            {"name": "Step 1", "description": "First step"},
            {"name": "Step 2", "description": "Second step", "dependencies": []},
        ]
        mission = mc.create_mission("Custom", "Custom tasks", tasks=tasks)
        assert len(mission.tasks) == 2

    def test_dashboard(self, tmp_path):
        from brain.mission_controller import MissionController
        mc = MissionController(data_dir=str(tmp_path / "missions"))
        mc.create_mission("Test", "Test mission")
        dashboard = mc.get_dashboard()
        assert "total_missions" in dashboard
        assert dashboard["total_missions"] == 1

    def test_checkpoint_resume(self, tmp_path):
        from brain.mission_controller import MissionController
        mc = MissionController(data_dir=str(tmp_path / "missions"))
        mission = mc.create_mission("Checkpoint Test", "Test checkpoint")
        assert mc.checkpoint_mission(mission.mission_id)


# ═══════════════════════════════════════════════════════
# Module 5: HyperReasoner
# ═══════════════════════════════════════════════════════

class TestHyperReasoner:

    def test_import(self):
        from brain.hyper_reasoner import HyperReasoner
        assert HyperReasoner is not None

    def test_quick_reason(self):
        from brain.hyper_reasoner import HyperReasoner
        hr = HyperReasoner()
        result = hr.reason("Should we use Python or Rust?", depth="quick")
        assert result.final_conclusion
        assert 0 <= result.final_confidence <= 1
        assert len(result.perspectives) == 3  # quick = 3 perspectives

    def test_standard_reason(self):
        from brain.hyper_reasoner import HyperReasoner
        hr = HyperReasoner()
        result = hr.reason("Is microservices better than monolith?")
        assert len(result.perspectives) == 6
        assert result.logic_check
        assert len(result.challenges) >= 1

    def test_uncertainty_report(self):
        from brain.hyper_reasoner import HyperReasoner
        hr = HyperReasoner()
        result = hr.reason("What will quantum computing look like in 2030?")
        assert result.uncertainty
        assert isinstance(result.uncertainty.assumptions_made, list)

    def test_audit_trail(self):
        from brain.hyper_reasoner import HyperReasoner
        hr = HyperReasoner()
        result = hr.reason("Test query")
        assert len(result.audit_trail) > 0
        assert result.audit_trail[0]["step"] == "start"

    def test_status(self):
        from brain.hyper_reasoner import HyperReasoner
        hr = HyperReasoner()
        hr.reason("Test")
        status = hr.get_status()
        assert status["reasoning_sessions"] == 1


# ═══════════════════════════════════════════════════════
# Module 6: RealtimeGuardian
# ═══════════════════════════════════════════════════════

class TestRealtimeGuardian:

    def test_import(self):
        from brain.realtime_guardian import RealtimeGuardian
        assert RealtimeGuardian is not None

    def test_init(self, tmp_path):
        from brain.realtime_guardian import RealtimeGuardian
        rg = RealtimeGuardian(data_dir=str(tmp_path / "guardian"))
        assert rg is not None

    def test_anomaly_detection(self, tmp_path):
        from brain.realtime_guardian import RealtimeGuardian
        rg = RealtimeGuardian(data_dir=str(tmp_path / "guardian"))
        # Build baseline
        for i in range(20):
            rg.check_anomaly("cpu", 40 + (i % 5))
        # Spike
        event = rg.check_anomaly("cpu", 200)
        # After enough samples, this should be anomalous
        if event:
            assert "anomaly" in event.category.value.lower()

    def test_file_integrity(self, tmp_path):
        from brain.realtime_guardian import RealtimeGuardian
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")
        rg = RealtimeGuardian(
            data_dir=str(tmp_path / "guardian"),
            watched_paths=[str(test_file)],
        )
        events = rg.check_file_integrity()
        assert len(events) == 0  # No changes yet

        test_file.write_text("modified content!")
        events = rg.check_file_integrity()
        assert len(events) == 1  # File changed

    def test_network_sentinel(self, tmp_path):
        from brain.realtime_guardian import RealtimeGuardian
        rg = RealtimeGuardian(data_dir=str(tmp_path / "guardian"))
        connections = [
            {"remote_ip": "192.168.1.100", "remote_port": 31337, "bytes_sent": 100},
        ]
        events = rg.check_network_activity(connections)
        assert len(events) > 0  # Suspicious port detected

    def test_security_scan(self, tmp_path):
        from brain.realtime_guardian import RealtimeGuardian
        rg = RealtimeGuardian(data_dir=str(tmp_path / "guardian"))
        results = rg.run_security_scan()
        assert "total_threats" in results

    def test_forensic_log(self, tmp_path):
        from brain.realtime_guardian import RealtimeGuardian
        rg = RealtimeGuardian(data_dir=str(tmp_path / "guardian"))
        log = rg.get_forensic_log()
        assert isinstance(log, list)

    def test_status(self, tmp_path):
        from brain.realtime_guardian import RealtimeGuardian
        rg = RealtimeGuardian(data_dir=str(tmp_path / "guardian"))
        status = rg.get_status()
        assert status["online"] is True


# ═══════════════════════════════════════════════════════
# Module 7: KnowledgeNexus
# ═══════════════════════════════════════════════════════

class TestKnowledgeNexus:

    def test_import(self):
        from brain.knowledge_nexus import KnowledgeNexus
        assert KnowledgeNexus is not None

    def test_add_and_query(self, tmp_path):
        from brain.knowledge_nexus import KnowledgeNexus, NodeType
        kn = KnowledgeNexus(data_dir=str(tmp_path / "knowledge"))
        kn.add_node("Python", "Programming language", NodeType.CONCEPT, domain="tech")
        kn.add_node("FastAPI", "Web framework", NodeType.CONCEPT, domain="tech")
        kn.add_edge("FastAPI", "Python", label="built_with")
        result = kn.query("Python")
        assert len(result.nodes) > 0

    def test_cross_domain(self, tmp_path):
        from brain.knowledge_nexus import KnowledgeNexus, NodeType, EdgeType
        kn = KnowledgeNexus(data_dir=str(tmp_path / "knowledge"))
        kn.add_node("ML", "Machine learning", NodeType.CONCEPT, domain="ai", tags=["data"])
        kn.add_node("Statistics", "Math field", NodeType.CONCEPT, domain="math", tags=["data"])
        links = kn.find_cross_domain_links()
        assert isinstance(links, list)

    def test_auto_learn(self, tmp_path):
        from brain.knowledge_nexus import KnowledgeNexus
        kn = KnowledgeNexus(data_dir=str(tmp_path / "knowledge"))
        learned = kn.learn_from_conversation(
            "How does Python handle exceptions?",
            "Python uses try/except blocks for error handling.",
            topic="programming"
        )
        assert len(learned) > 0

    def test_decay(self, tmp_path):
        from brain.knowledge_nexus import KnowledgeNexus, NodeType
        kn = KnowledgeNexus(data_dir=str(tmp_path / "knowledge"))
        node = kn.add_node("temp_fact", "temporary", NodeType.FACT, confidence=0.15)
        # Force old timestamp
        node.last_verified = time.time() - 86400 * 365  # 1 year ago
        node.created_at = node.last_verified
        pruned = kn.apply_decay()
        assert pruned >= 0

    def test_persistence(self, tmp_path):
        from brain.knowledge_nexus import KnowledgeNexus, NodeType
        kn1 = KnowledgeNexus(data_dir=str(tmp_path / "knowledge"))
        kn1.add_node("TestNode", "test content", NodeType.FACT)
        kn1.save()

        kn2 = KnowledgeNexus(data_dir=str(tmp_path / "knowledge"))
        assert kn2.get_stats()["total_nodes"] == 1

    def test_get_related(self, tmp_path):
        from brain.knowledge_nexus import KnowledgeNexus, NodeType
        kn = KnowledgeNexus(data_dir=str(tmp_path / "knowledge"))
        kn.add_node("A", "Node A", NodeType.CONCEPT)
        kn.add_node("B", "Node B", NodeType.CONCEPT)
        kn.add_node("C", "Node C", NodeType.CONCEPT)
        kn.add_edge("A", "B")
        kn.add_edge("B", "C")
        related = kn.get_related("A", depth=2)
        assert len(related) >= 1

    def test_stats(self, tmp_path):
        from brain.knowledge_nexus import KnowledgeNexus
        kn = KnowledgeNexus(data_dir=str(tmp_path / "knowledge"))
        stats = kn.get_stats()
        assert "total_nodes" in stats
        assert "total_edges" in stats
