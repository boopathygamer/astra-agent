"""
Mega Upgrade Test Suite — Tests all 10+ new modules.
"""
import os
import sys
import time
import json
import threading
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════
# Test 1: Message Bus
# ═══════════════════════════════════════════

class TestMessageBus:

    def test_import(self):
        from core.message_bus import MessageBus
        assert MessageBus is not None

    def test_publish_subscribe(self):
        from core.message_bus import MessageBus
        bus = MessageBus()
        received = []
        bus.subscribe("test.topic", lambda msg: received.append(msg.payload))
        bus.publish("test.topic", "hello", sender="test")
        assert len(received) == 1
        assert received[0] == "hello"

    def test_wildcard_subscription(self):
        from core.message_bus import MessageBus
        bus = MessageBus()
        received = []
        bus.subscribe("agent.*", lambda msg: received.append(msg.topic))
        bus.publish("agent.chat", "msg1")
        bus.publish("agent.code", "msg2")
        bus.publish("brain.think", "msg3")  # shouldn't match
        assert len(received) == 2

    def test_priority(self):
        from core.message_bus import MessageBus, MessagePriority
        bus = MessageBus()
        received = []
        bus.subscribe("alerts.*", lambda msg: received.append(msg.payload),
                      priority_filter=MessagePriority.HIGH)
        bus.publish("alerts.cpu", "low", priority=MessagePriority.LOW)
        bus.publish("alerts.cpu", "critical", priority=MessagePriority.CRITICAL)
        assert len(received) == 1
        assert received[0] == "critical"

    def test_request_reply_pattern(self):
        from core.message_bus import MessageBus
        bus = MessageBus()
        replies = []
        # Set up responder that publishes back
        def responder(msg):
            if msg.reply_to and msg.correlation_id:
                bus.publish(msg.reply_to, f"reply:{msg.payload}",
                           correlation_id=msg.correlation_id)
        bus.subscribe("svc.echo", responder)
        # Manual request (not using request() which has timing issues in sync)
        bus.subscribe("_reply.test", lambda msg: replies.append(msg.payload))
        bus.publish("svc.echo", "hello", correlation_id="test", reply_to="_reply.test")
        assert len(replies) == 1
        assert replies[0] == "reply:hello"

    def test_history(self):
        from core.message_bus import MessageBus
        bus = MessageBus()
        bus.publish("test.1", "data1")
        bus.publish("test.2", "data2")
        history = bus.get_history()
        assert len(history) == 2

    def test_metrics(self):
        from core.message_bus import MessageBus
        bus = MessageBus()
        bus.subscribe("test", lambda _: None)
        bus.publish("test", "x")
        m = bus.get_metrics()
        assert m["total_published"] == 1
        assert m["total_delivered"] == 1


# ═══════════════════════════════════════════
# Test 2: Agent Protocol
# ═══════════════════════════════════════════

class TestAgentProtocol:

    def test_import(self):
        from core.agent_protocol import AgentRegistry, AgentIdentity
        assert AgentRegistry is not None

    def test_register_agent(self):
        from core.agent_protocol import AgentRegistry, AgentIdentity, AgentRole, AgentCapability
        registry = AgentRegistry()
        identity = AgentIdentity(
            name="TestAgent", role=AgentRole.SPECIALIST,
            capabilities=[AgentCapability(name="code", domains=["python"])],
        )
        aid = registry.register(identity)
        assert aid == identity.agent_id
        assert registry.get_agent(aid) is not None

    def test_find_agents(self):
        from core.agent_protocol import AgentRegistry, AgentIdentity, AgentRole, AgentCapability
        registry = AgentRegistry()
        registry.register(AgentIdentity(
            name="PyAgent", role=AgentRole.SPECIALIST,
            capabilities=[AgentCapability(name="code", domains=["python"])],
        ))
        registry.register(AgentIdentity(
            name="JSAgent", role=AgentRole.SPECIALIST,
            capabilities=[AgentCapability(name="code", domains=["javascript"])],
        ))
        py_agents = registry.find_agents(domain="python")
        assert len(py_agents) == 1
        assert py_agents[0].name == "PyAgent"

    def test_best_agent(self):
        from core.agent_protocol import AgentRegistry, AgentIdentity, AgentRole, AgentCapability, TaskDifficulty
        registry = AgentRegistry()
        registry.register(AgentIdentity(
            name="Expert", role=AgentRole.SPECIALIST,
            capabilities=[AgentCapability(name="ml", domains=["ai"],
                                          reliability=0.95)],
        ))
        best = registry.find_best_agent("ai")
        assert best is not None
        assert best.name == "Expert"


# ═══════════════════════════════════════════
# Test 3: Adaptive Learner
# ═══════════════════════════════════════════

class TestAdaptiveLearner:

    def test_import(self):
        from brain.adaptive_learner import AdaptiveLearner
        assert AdaptiveLearner is not None

    def test_record_feedback(self, tmp_path):
        from brain.adaptive_learner import AdaptiveLearner, FeedbackType
        al = AdaptiveLearner(data_dir=str(tmp_path / "learn"))
        signal = al.record_feedback(
            FeedbackType.EXPLICIT_POSITIVE,
            query="test", response="result",
        )
        assert signal.rating == 1.0

    def test_strategy_optimization(self, tmp_path):
        from brain.adaptive_learner import AdaptiveLearner, FeedbackType, LearningDomain
        al = AdaptiveLearner(data_dir=str(tmp_path / "learn"))
        for _ in range(10):
            al.record_feedback(FeedbackType.EXPLICIT_POSITIVE,
                             domain=LearningDomain.CODE_GENERATION,
                             strategy="chain_of_thought")
            al.record_feedback(FeedbackType.EXPLICIT_NEGATIVE,
                             domain=LearningDomain.CODE_GENERATION,
                             strategy="direct")
        best = al.get_best_strategy(LearningDomain.CODE_GENERATION)
        assert best == "chain_of_thought"

    def test_correction_learning(self, tmp_path):
        from brain.adaptive_learner import AdaptiveLearner, FeedbackType
        al = AdaptiveLearner(data_dir=str(tmp_path / "learn"))
        al.record_feedback(
            FeedbackType.CORRECTION,
            query="sort this list", response="wrong answer",
            correction="use sorted() function",
        )
        ctx = al.get_correction_context("sort a list")
        assert "sorted()" in ctx

    def test_insights(self, tmp_path):
        from brain.adaptive_learner import AdaptiveLearner, FeedbackType, LearningDomain
        al = AdaptiveLearner(data_dir=str(tmp_path / "learn"))
        for _ in range(10):
            al.record_feedback(FeedbackType.EXPLICIT_NEGATIVE,
                             domain=LearningDomain.CREATIVE)
        insights = al.generate_insights()
        assert len(insights) > 0


# ═══════════════════════════════════════════
# Test 4: Project Intelligence
# ═══════════════════════════════════════════

class TestProjectIntelligence:

    def test_import(self):
        from brain.project_intelligence import ProjectIntelligence
        assert ProjectIntelligence is not None

    def test_scan_project(self, tmp_path):
        from brain.project_intelligence import ProjectIntelligence
        # Create a mini project
        (tmp_path / "app.py").write_text("import os\nclass App:\n    pass\n")
        (tmp_path / "utils.py").write_text("def helper():\n    return True\n")
        (tmp_path / "style.css").write_text("body { color: red; }\n")

        pi = ProjectIntelligence(data_dir=str(tmp_path / "intel"))
        profile = pi.scan_project(str(tmp_path))
        assert profile.total_files >= 2
        assert profile.primary_language.value == "python"

    def test_detect_frameworks(self, tmp_path):
        from brain.project_intelligence import ProjectIntelligence
        pkg = {"dependencies": {"react": "^18.0.0", "next": "^14.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        (tmp_path / "app.js").write_text("import React from 'react';\n")

        pi = ProjectIntelligence(data_dir=str(tmp_path / "intel"))
        profile = pi.scan_project(str(tmp_path))
        assert "react" in profile.frameworks

    def test_context(self, tmp_path):
        from brain.project_intelligence import ProjectIntelligence
        (tmp_path / "main.py").write_text("from utils import helper\n")
        (tmp_path / "utils.py").write_text("def helper():\n    pass\n")

        pi = ProjectIntelligence(data_dir=str(tmp_path / "intel"))
        profile = pi.scan_project(str(tmp_path))
        ctx = pi.get_context_for_file(str(tmp_path), "main.py")
        assert "language" in ctx


# ═══════════════════════════════════════════
# Test 5: Workflow Engine
# ═══════════════════════════════════════════

class TestWorkflowEngine:

    def test_import(self):
        from brain.workflow_engine import WorkflowEngine
        assert WorkflowEngine is not None

    def test_create_from_instruction(self, tmp_path):
        from brain.workflow_engine import WorkflowEngine
        we = WorkflowEngine(data_dir=str(tmp_path / "wf"))
        wf = we.create_from_instruction("Every morning check my repos and summarize")
        assert wf.trigger.cron_expression == "0 9 * * *"
        assert len(wf.steps) >= 1

    def test_schedule_parsing(self, tmp_path):
        from brain.workflow_engine import WorkflowEngine
        we = WorkflowEngine(data_dir=str(tmp_path / "wf"))
        wf = we.create_from_instruction("Daily at 14 run tests")
        assert "14" in wf.trigger.cron_expression

    def test_execute(self, tmp_path):
        from brain.workflow_engine import WorkflowEngine, WorkflowStatus
        we = WorkflowEngine(data_dir=str(tmp_path / "wf"))
        wf = we.create_from_instruction("Do a simple test task")
        run = we.execute_workflow(wf.workflow_id)
        assert run.success

    def test_list_and_pause(self, tmp_path):
        from brain.workflow_engine import WorkflowEngine
        we = WorkflowEngine(data_dir=str(tmp_path / "wf"))
        wf = we.create_from_instruction("Test workflow")
        assert len(we.list_workflows()) == 1
        we.pause_workflow(wf.workflow_id)
        assert we._workflows[wf.workflow_id].status.value == "paused"


# ═══════════════════════════════════════════
# Test 6: Semantic Memory
# ═══════════════════════════════════════════

class TestSemanticMemory:

    def test_import(self):
        from brain.semantic_memory import SemanticMemory
        assert SemanticMemory is not None

    def test_store_and_search(self, tmp_path):
        from brain.semantic_memory import SemanticMemory
        sm = SemanticMemory(data_dir=str(tmp_path / "mem"))
        sm.store("Python is a programming language", category="tech")
        sm.store("JavaScript runs in browsers", category="tech")
        results = sm.search("programming language")
        assert len(results) > 0
        assert results[0].similarity > 0

    def test_deduplication(self, tmp_path):
        from brain.semantic_memory import SemanticMemory
        sm = SemanticMemory(data_dir=str(tmp_path / "mem"))
        e1 = sm.store("Python is great for AI")
        e2 = sm.store("Python is great for AI")  # Duplicate
        assert e1.memory_id == e2.memory_id  # Should be same entry
        assert e2.access_count == 1

    def test_clustering(self, tmp_path):
        from brain.semantic_memory import SemanticMemory
        sm = SemanticMemory(data_dir=str(tmp_path / "mem"))
        for i in range(15):
            sm.store(f"Python concept number {i}", category="python")
        for i in range(15):
            sm.store(f"JavaScript framework number {i}", category="js")
        clusters = sm.cluster_memories(num_clusters=3)
        assert len(clusters) > 0

    def test_context_retrieval(self, tmp_path):
        from brain.semantic_memory import SemanticMemory
        sm = SemanticMemory(data_dir=str(tmp_path / "mem"))
        sm.store("FastAPI is a modern web framework for Python")
        sm.store("React is a JavaScript library for building UIs")
        ctx = sm.get_context("web framework")
        assert len(ctx) > 0

    def test_persistence(self, tmp_path):
        from brain.semantic_memory import SemanticMemory
        sm1 = SemanticMemory(data_dir=str(tmp_path / "mem"))
        sm1.store("Persistent memory test")
        sm1.save()
        sm2 = SemanticMemory(data_dir=str(tmp_path / "mem"))
        assert sm2.get_status()["total_memories"] == 1


# ═══════════════════════════════════════════
# Test 7: Collaboration Framework
# ═══════════════════════════════════════════

class TestCollaboration:

    def test_import(self):
        from agents.collaboration import CollaborationFramework
        assert CollaborationFramework is not None

    def test_create_team(self):
        from agents.collaboration import CollaborationFramework
        cf = CollaborationFramework()
        team = cf.create_team("Test Team", [
            {"agent_id": "a1", "name": "Agent1", "role": "lead"},
            {"agent_id": "a2", "name": "Agent2", "role": "specialist"},
        ])
        assert len(team.members) == 2
        assert team.lead_id == "a1"

    def test_auto_assemble(self):
        from agents.collaboration import CollaborationFramework
        cf = CollaborationFramework()
        agents = [
            {"agent_id": "x1", "name": "CodeBot", "capabilities": ["python", "code"]},
            {"agent_id": "x2", "name": "MLBot", "capabilities": ["ml", "data"]},
        ]
        team = cf.auto_assemble_team("Write python code for ML", agents)
        assert len(team.members) > 0

    def test_execute_collaboration(self):
        from agents.collaboration import CollaborationFramework
        cf = CollaborationFramework()
        team = cf.create_team("ExecTeam", [
            {"agent_id": "e1", "name": "Worker1", "role": "lead"},
            {"agent_id": "e2", "name": "Worker2", "role": "specialist"},
        ])
        task = cf.delegate_task(team.team_id, "Solve a problem")
        result = cf.execute_collaboration(team.team_id, task)
        assert result.status == "completed"
        assert result.consensus_result is not None


# ═══════════════════════════════════════════
# Test 8: Plugin Manager
# ═══════════════════════════════════════════

class TestPluginManager:

    def test_import(self):
        from agents.plugins import PluginManager
        assert PluginManager is not None

    def test_init(self, tmp_path):
        from agents.plugins import PluginManager
        pm = PluginManager(plugins_dir=str(tmp_path / "plugins"))
        status = pm.get_status()
        assert "total_plugins" in status

    def test_install_from_code(self, tmp_path):
        from agents.plugins import PluginManager
        pm = PluginManager(plugins_dir=str(tmp_path / "plugins"))
        # Write a simple plugin file
        code = 'def hello(): return "I am a plugin"\n'
        result = pm.install_from_code("simple_plugin", code)
        # Plugin file should now exist
        import pathlib
        assert (pathlib.Path(tmp_path / "plugins" / "simple_plugin.py")).exists()

    def test_list_plugins(self, tmp_path):
        from agents.plugins import PluginManager
        pm = PluginManager(plugins_dir=str(tmp_path / "plugins"))
        plugins = pm.list_plugins()
        assert isinstance(plugins, list)


# ═══════════════════════════════════════════
# Test 9: Auth Manager
# ═══════════════════════════════════════════

class TestAuthManager:

    def test_import(self):
        from api.auth import AuthManager
        assert AuthManager is not None

    def test_create_user(self, tmp_path):
        from api.auth import AuthManager
        am = AuthManager(data_dir=str(tmp_path / "auth"))
        user = am.create_user("testuser", "test@test.com", "pass123")
        assert user.username == "testuser"
        assert user.api_key

    def test_authenticate(self, tmp_path):
        from api.auth import AuthManager
        am = AuthManager(data_dir=str(tmp_path / "auth"))
        am.create_user("bob", "bob@test.com", "secret")
        user = am.authenticate("bob", "secret")
        assert user is not None
        assert user.username == "bob"
        # Wrong password
        assert am.authenticate("bob", "wrong") is None

    def test_jwt_tokens(self, tmp_path):
        from api.auth import AuthManager
        am = AuthManager(data_dir=str(tmp_path / "auth"))
        user = am.create_user("jwtuser", password="pass")
        token = am.generate_token(user)
        payload = am.verify_token(token)
        assert payload is not None
        assert payload.username == "jwtuser"

    def test_token_revocation(self, tmp_path):
        from api.auth import AuthManager
        am = AuthManager(data_dir=str(tmp_path / "auth"))
        user = am.create_user("revokeuser", password="pass")
        token = am.generate_token(user)
        am.revoke_token(token)
        assert am.verify_token(token) is None

    def test_api_key_auth(self, tmp_path):
        from api.auth import AuthManager
        am = AuthManager(data_dir=str(tmp_path / "auth"))
        user = am.create_user("apiuser", password="pass")
        authed = am.authenticate_api_key(user.api_key)
        assert authed is not None

    def test_permissions(self, tmp_path):
        from api.auth import AuthManager, UserRole
        am = AuthManager(data_dir=str(tmp_path / "auth"))
        admin = am.create_user("admin2", password="pass", role=UserRole.ADMIN)
        viewer = am.create_user("viewer1", password="pass", role=UserRole.VIEWER)
        assert am.has_permission(admin.user_id, UserRole.ADMIN)
        assert not am.has_permission(viewer.user_id, UserRole.ADMIN)


# ═══════════════════════════════════════════
# Test 10: Local Model Provider
# ═══════════════════════════════════════════

class TestLocalModelProvider:

    def test_import(self):
        from core.local_model_provider import LocalModelProvider
        assert LocalModelProvider is not None

    def test_greeting(self):
        from core.local_model_provider import LocalModelProvider, GenerationMode
        lm = LocalModelProvider(mode=GenerationMode.LOCAL_ONLY)
        result = lm.generate("Hello!")
        assert "Astra" in result.text or "Hello" in result.text

    def test_complexity_estimation(self):
        from core.local_model_provider import LocalModelProvider, GenerationMode, QueryComplexity
        lm = LocalModelProvider(mode=GenerationMode.LOCAL_ONLY)
        # Short inputs should be trivial or simple
        trivial = lm._estimate_complexity("hello there")
        assert trivial in (QueryComplexity.TRIVIAL, QueryComplexity.SIMPLE)
        # Complex prompts
        complex_q = lm._estimate_complexity("write a function that sorts a list using merge sort algorithm")
        assert complex_q in (QueryComplexity.COMPLEX, QueryComplexity.EXPERT)

    def test_caching(self):
        from core.local_model_provider import LocalModelProvider, GenerationMode
        lm = LocalModelProvider(mode=GenerationMode.LOCAL_ONLY)
        r1 = lm.generate("Hello!")
        r2 = lm.generate("Hello!")
        assert r2.cached is True

    def test_status(self):
        from core.local_model_provider import LocalModelProvider, GenerationMode
        lm = LocalModelProvider(mode=GenerationMode.LOCAL_ONLY)
        lm.generate("test")
        status = lm.get_status()
        assert status["local_generations"] >= 1


# ═══════════════════════════════════════════
# Test 11: Scheduler
# ═══════════════════════════════════════════

class TestScheduler:

    def test_import(self):
        from agents.scheduler import AgentScheduler
        assert AgentScheduler is not None

    def test_register_job(self):
        from agents.scheduler import AgentScheduler, JobFrequency
        sched = AgentScheduler()
        counter = {"count": 0}
        sched.register("test_job", lambda: counter.__setitem__("count", counter["count"] + 1),
                       frequency=JobFrequency.ONCE)
        sched.run_now("test_job")
        assert counter["count"] == 1

    def test_list_jobs(self):
        from agents.scheduler import AgentScheduler, JobFrequency
        sched = AgentScheduler()
        sched.register("j1", lambda: None, frequency=JobFrequency.MINUTES)
        sched.register("j2", lambda: None, frequency=JobFrequency.HOURS)
        jobs = sched.list_jobs()
        assert len(jobs) == 2

    def test_error_handling(self):
        from agents.scheduler import AgentScheduler, JobFrequency
        sched = AgentScheduler()
        sched.register("bad_job", lambda: 1/0, frequency=JobFrequency.ONCE,
                       max_retries=1)
        run = sched.run_now("bad_job")
        assert run is not None
        assert run.success is False
