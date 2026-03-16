"""
Agent Controller — Enhanced orchestrator with all OpenClaw-inspired upgrades.
──────────────────────────────────────────────────────────────────────────────
Integrates all 10 subsystems:
  1. Tool Policy Engine      → access control
  2. Loop Detection          → guardrails
  3. Session Manager         → persistence + agent-to-agent
  4. Process Manager         → background execution
  5. Hybrid Memory           → vector + BM25 search
  6. Workspace Injection     → bootstrap files
  7. Skills Registry         → dynamic skill loading
  8. Streaming               → SSE + coalescing
  9. Model Failover          → provider chain
  10. Enhanced Controller    → this file (orchestrates everything)

Architecture:
  state m = init_memory()
  while not done:
      x = compile(problem, context)
      H = generate_hypotheses(x, m)
      s = synthesize_candidate(x, H, m)
      report = verify(s, x)
      risk = estimate_risk(s, x, report)
      ── LOOP CHECK ──                    ← NEW
      ── POLICY CHECK ──                  ← NEW
      if gate(report.confidence, risk) == "execute":
          result = execute(s, x)
      elif gate(...) == "sandbox":
          result = execute_sandboxed(s, x)
      else:
          result = ask_for_info_or_refuse(x)
      m = update_memory(m, x, s, report, result)
      ── SESSION PERSIST ──               ← NEW
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from config.settings import brain_config, agent_config
from brain.memory import MemoryManager
from brain.thinking_loop import ThinkingLoop, ThinkingResult
from agents.compiler import TaskCompiler, TaskSpec
from agents.generator import CandidateGenerator
from agents.tools.registry import ToolRegistry, registry
from agents.tools.policy import ToolPolicyEngine, ToolProfile, PolicyContext
from agents.loop_detector import LoopDetector, LoopDetectorConfig, LoopSeverity
from agents.sessions.manager import SessionManager, SessionType
from agents.sessions.store import SessionStore
from agents.sessions.tools import register_session_tools, set_session_manager
from agents.process_manager import ProcessManager
from agents.workspace import WorkspaceManager
from agents.skills.registry import SkillsRegistry
from agents.prompts.templates import AGENT_SYSTEM_PROMPT, TOOL_USE_PROMPT
from core.streaming import StreamProcessor, StreamConfig, StreamEventType
from agents.safety import ContentFilter, PIIGuard, EthicsEngine
from agents.safety.threat_scanner import ThreatScanner
from telemetry.metrics import MetricsCollector
from telemetry.tracer import SpanTracer

# ── Universal Agent Subsystems ──
from agents.experts.router import DomainRouter
from agents.experts.domains import get_expert
from agents.persona import PersonaEngine
from brain.advanced_reasoning import AdvancedReasoner
from agents.response_formatter import ResponseFormatter

# ── Agent Forge + Tool Forge ──
from agents.agent_forge import AgentForge
from agents.tools.tool_forge import ToolForge

# ── JARVIS Intelligence Modules ──
from brain.jarvis_core import JarvisCore, AuthorityLevel
from brain.situational_awareness import SituationalAwareness
from brain.predictive_intent import PredictiveIntent
from brain.mission_controller import MissionController
from brain.hyper_reasoner import HyperReasoner
from brain.realtime_guardian import RealtimeGuardian
from brain.knowledge_nexus import KnowledgeNexus

# ── Mega Upgrade Modules ──
from core.message_bus import MessageBus, get_message_bus, MessagePriority
from core.agent_protocol import AgentRegistry, AgentIdentity, AgentRole, AgentCapability, get_agent_registry
from brain.adaptive_learner import AdaptiveLearner, FeedbackType, LearningDomain
from brain.project_intelligence import ProjectIntelligence
from brain.workflow_engine import WorkflowEngine
from brain.semantic_memory import SemanticMemory

# ── Ultra Performance Modules ──
from core.parallel_reasoning import ParallelReasoningEngine
from core.cache_hierarchy import CacheHierarchy
from core.query_decomposer import QueryDecomposer
from core.predictive_prefetch import PredictivePrefetchEngine
from core.context_optimizer import ContextOptimizer
from core.performance_profiler import PerformanceProfiler
from core.token_budget import TokenBudgetManager
from core.streaming_pipeline import StreamingPipeline
from core.resource_manager import ResourceManager
from core.hot_path_optimizer import HotPathOptimizer
from agents.collaboration import CollaborationFramework
from agents.plugins import PluginManager
from agents.scheduler import AgentScheduler, JobFrequency
from core.local_model_provider import LocalModelProvider, GenerationMode

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Complete agent response with metadata."""
    answer: str = ""
    thinking_trace: Optional[ThinkingResult] = None
    tools_used: List[dict] = field(default_factory=list)
    task_spec: Optional[TaskSpec] = None
    confidence: float = 0.0
    iterations: int = 0
    duration_ms: float = 0.0
    mode: str = "direct"
    session_id: str = ""
    stream_events: List[dict] = field(default_factory=list)
    loop_warnings: List[str] = field(default_factory=list)


class AgentController:
    """
    Enhanced Agent Controller — orchestrates all 10 subsystems.

    Original 5 modules:
      1. Compiler    — task → spec
      2. Generator   — spec → hypotheses → candidate
      3. Verifier    — candidate → verification report
      4. Risk Manager — report → gating decision
      5. Memory      — failures → learning

    New OpenClaw-inspired subsystems:
      6. Tool Policy Engine    — allow/deny chains
      7. Loop Detector         — prevent tool-call loops
      8. Session Manager       — JSONL persistence + agent-to-agent
      9. Process Manager       — background execution
      10. Workspace + Skills   — context injection
    """

    def __init__(
        self,
        generate_fn: Callable,
        memory: Optional[MemoryManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        agent_id: str = "default",
    ):
        self.generate_fn = generate_fn
        self.agent_id = agent_id
        self.memory = memory or MemoryManager()
        self.tools = tool_registry or registry

        # ── Original Sub-modules ──
        self.compiler = TaskCompiler(generate_fn)
        self.generator = CandidateGenerator(generate_fn)

        # ── Tool Forge + Agent Forge ──
        self.tool_forge = ToolForge(generate_fn=generate_fn)
        self.agent_forge = AgentForge(
            generate_fn=generate_fn,
            tool_registry=self.tools,
        )

        self.thinking_loop = ThinkingLoop(
            generate_fn=generate_fn,
            memory=self.memory,
            tool_forge=self.tool_forge,
        )

        # ── EXPERT TELEMETRY: Trace Spans & Metrics ──
        self.tracer = SpanTracer()
        self.metrics = MetricsCollector.get_instance()

        # ── New Subsystem 1: Tool Policy Engine ──
        profile_map = {
            "minimal": ToolProfile.MINIMAL,
            "coding": ToolProfile.CODING,
            "assistant": ToolProfile.ASSISTANT,
            "full": ToolProfile.FULL,
        }
        profile = profile_map.get(agent_config.tool_profile, ToolProfile.ASSISTANT)
        self.policy_engine = ToolPolicyEngine(profile=profile)
        if agent_config.tool_global_deny:
            self.policy_engine.set_global_policy(deny=set(agent_config.tool_global_deny))
        self.tools.set_policy_engine(self.policy_engine)

        # ── New Subsystem 2: Loop Detector ──
        self.loop_detector = LoopDetector(LoopDetectorConfig(
            enabled=agent_config.loop_detection_enabled,
            warning_threshold=agent_config.loop_warning_threshold,
            critical_threshold=agent_config.loop_critical_threshold,
            circuit_breaker_threshold=agent_config.loop_circuit_breaker_threshold,
        ))

        # ── New Subsystem 3: Session Manager ──
        self.session_store = SessionStore(base_dir=agent_config.sessions_dir)
        self.session_manager = SessionManager(
            store=self.session_store,
            default_agent_id=agent_id,
        )
        set_session_manager(self.session_manager)
        register_session_tools()

        # Create default main session
        self._main_session = self.session_manager.create_session(
            session_type=SessionType.MAIN,
            agent_id=agent_id,
            label="main",
        )

        # ── New Subsystem 4: Process Manager ──
        self.process_manager = ProcessManager(
            max_processes=agent_config.max_background_processes,
            default_timeout=agent_config.process_default_timeout,
        )

        # ── New Subsystem 5: Workspace + Skills ──
        self.workspace = WorkspaceManager(workspace_dir=agent_config.workspace_dir)
        self.workspace.initialize(agent_id)

        self.skills = SkillsRegistry(
            bundled_dir=agent_config.skills_bundled_dir,
            managed_dir=agent_config.skills_managed_dir,
            workspace_base=agent_config.workspace_dir,
        )
        self.skills.discover_all(agent_id)

        # ── New Subsystem 6: Streaming ──
        self.stream_config = StreamConfig(
            chunk_size=agent_config.stream_chunk_size,
            coalesce_ms=agent_config.stream_coalesce_ms,
            break_on=agent_config.stream_break_on,
        )

        # Conversation history (still kept for backward compatibility)
        self.conversation: List[dict] = []

        # ── Safety Layer: Content Filter + PII Guard + Ethics + ThreatScanner ──
        self.content_filter = ContentFilter()
        self.pii_guard = PIIGuard()
        self.ethics_engine = EthicsEngine()

        # ── Threat Scanner: Auto-scan files/URLs for viruses/malware ──
        try:
            from config.settings import threat_config
            self.threat_scanner = ThreatScanner(
                quarantine_dir=threat_config.quarantine_dir,
                entropy_threshold=threat_config.entropy_threshold,
                max_file_size_mb=threat_config.max_file_size_mb,
            )
            self._threat_auto_scan = threat_config.auto_scan_on_file_ops
        except Exception as e:
            logger.warning(f"ThreatScanner init failed: {e}")
            self.threat_scanner = ThreatScanner()
            self._threat_auto_scan = True

        # ── Universal Agent Subsystems ──
        self.domain_router = DomainRouter()
        self.persona_engine = PersonaEngine()
        self.advanced_reasoner = AdvancedReasoner()
        self.response_formatter = ResponseFormatter()

        # ── JARVIS Intelligence Layer ──
        try:
            self.jarvis_core = JarvisCore(
                generate_fn=generate_fn,
                authority_level=AuthorityLevel.SUGGEST,
            )
            self.situational_awareness = SituationalAwareness()
            self.predictive_intent = PredictiveIntent()
            self.mission_controller = MissionController(generate_fn=generate_fn)
            self.hyper_reasoner = HyperReasoner(generate_fn=generate_fn)
            self.realtime_guardian = RealtimeGuardian()
            self.knowledge_nexus = KnowledgeNexus()

            # Register all subsystems with JARVIS core
            for name, instance in [
                ("situational_awareness", self.situational_awareness),
                ("predictive_intent", self.predictive_intent),
                ("mission_controller", self.mission_controller),
                ("hyper_reasoner", self.hyper_reasoner),
                ("realtime_guardian", self.realtime_guardian),
                ("knowledge_nexus", self.knowledge_nexus),
            ]:
                self.jarvis_core.register_subsystem(name, instance)

            self.jarvis_core.start_heartbeat()
            logger.info("[JARVIS] All 7 intelligence modules initialized and registered")
        except Exception as e:
            logger.warning(f"[JARVIS] Module init failed (non-fatal): {e}")
            self.jarvis_core = None
            self.situational_awareness = None
            self.predictive_intent = None
            self.mission_controller = None
            self.hyper_reasoner = None
            self.realtime_guardian = None
            self.knowledge_nexus = None

        # ── Mega Upgrade Layer ──
        try:
            self.message_bus = get_message_bus()
            self.agent_registry = get_agent_registry()
            self.adaptive_learner = AdaptiveLearner()
            self.project_intelligence = ProjectIntelligence()
            self.workflow_engine = WorkflowEngine(generate_fn=generate_fn)
            self.semantic_memory = SemanticMemory(generate_fn=generate_fn)
            self.collaboration = CollaborationFramework(generate_fn=generate_fn)
            self.plugin_manager = PluginManager()
            self.scheduler = AgentScheduler()
            self.local_model = LocalModelProvider(cloud_fn=generate_fn)

            # Register self in agent registry
            self_identity = AgentIdentity(
                name="AstraController",
                role=AgentRole.COORDINATOR,
                capabilities=[
                    AgentCapability(name="coordination", domains=["all"]),
                ],
            )
            self.agent_registry.register(self_identity)

            # Subscribe bus events for learning
            self.message_bus.subscribe("agent.*", lambda msg: None, subscriber_id="controller")

            # Start scheduler with standard jobs
            self.scheduler.register(
                "heartbeat", lambda: self.message_bus.publish("system.heartbeat", time.time(), sender="scheduler"),
                frequency=JobFrequency.MINUTES, interval=1, priority=1,
            )
            self.scheduler.start()

            logger.info("[MEGA] All upgrade modules initialized: bus, registry, learner, "
                        "project-intel, workflows, semantic-mem, collab, plugins, scheduler, local-model")
        except Exception as e:
            logger.warning(f"[MEGA] Upgrade module init failed (non-fatal): {e}")
            self.message_bus = None
            self.agent_registry = None
            self.adaptive_learner = None
            self.project_intelligence = None
            self.workflow_engine = None
            self.semantic_memory = None
            self.collaboration = None
            self.plugin_manager = None
            self.scheduler = None
            self.local_model = None

        # ── Ultra Performance Layer ──
        try:
            self.parallel_reasoning = ParallelReasoningEngine(generate_fn=generate_fn)
            self.cache_hierarchy = CacheHierarchy()
            self.query_decomposer = QueryDecomposer(generate_fn=generate_fn)
            self.predictive_prefetch = PredictivePrefetchEngine(generate_fn=generate_fn)
            self.context_optimizer = ContextOptimizer()
            self.performance_profiler = PerformanceProfiler()
            self.token_budget = TokenBudgetManager()
            self.streaming_pipeline = StreamingPipeline()
            self.resource_manager = ResourceManager()
            self.hot_path_optimizer = HotPathOptimizer()

            # Connect police to message bus for alerts
            try:
                from agents.justice.police import police_dispatcher
                if self.message_bus:
                    police_dispatcher.set_message_bus(self.message_bus)
            except Exception:
                pass

            logger.info("[ULTRA] All 10 performance modules initialized: parallel-reasoning, "
                        "cache, decomposer, prefetch, context-opt, profiler, token-budget, "
                        "streaming, resource-mgr, hot-path")
        except Exception as e:
            logger.warning(f"[ULTRA] Performance module init failed (non-fatal): {e}")
            self.parallel_reasoning = None
            self.cache_hierarchy = None
            self.query_decomposer = None
            self.predictive_prefetch = None
            self.context_optimizer = None
            self.performance_profiler = None
            self.token_budget = None
            self.streaming_pipeline = None
            self.resource_manager = None
            self.hot_path_optimizer = None

        logger.info(
            f"Universal Agent Controller initialized — "
            f"agent_id='{agent_id}', profile='{profile.value}', "
            f"session='{self._main_session.session_id}', "
            f"skills={len(self.skills.list_skills())}, "
            f"domains=10, personas=5, reasoning_strategies=4, "
            f"safety=ENABLED, jarvis={'ONLINE' if self.jarvis_core else 'OFFLINE'}, "
            f"mega_upgrade={'ONLINE' if self.message_bus else 'OFFLINE'}"
        )

    def process(
        self,
        user_input: str,
        use_thinking_loop: bool = True,
        max_tool_calls: int = None,
        session_id: str = None,
        event_callback: Optional[Callable[[dict], None]] = None,
    ) -> AgentResponse:
        """
        Process a user request through the full agent pipeline.

        Enhanced with:
          - Tool policy checks
          - Loop detection guardrails
          - Session persistence
          - Workspace/skills context injection
          - Streaming events
        """
        start_time = time.time()
        response = AgentResponse()
        max_tools = max_tool_calls or agent_config.max_tool_calls
        active_session = session_id or self._main_session.session_id

        response.session_id = active_session
        self.metrics.counter("agent.process.requests_total")

        # ── MEGA PRE-PROCESSING: Bus event + Plugin preprocessing + Memory context ──
        mega_context = ""
        try:
            # 1. Publish incoming request to message bus
            if self.message_bus:
                self.message_bus.publish(
                    "agent.request.incoming", {
                        "input": user_input[:200], "session": active_session,
                        "timestamp": time.time(),
                    }, sender="controller",
                )

            # 2. Run plugin preprocessors on input
            if self.plugin_manager:
                user_input = self.plugin_manager.run_preprocessors(user_input)

            # 3. Retrieve semantic memory context for this query
            if self.semantic_memory:
                mem_ctx = self.semantic_memory.get_context(user_input, max_tokens=500)
                if mem_ctx:
                    mega_context += f"\n[SEMANTIC MEMORY CONTEXT]\n{mem_ctx}\n"

            # 4. Inject adaptive learning corrections if relevant
            if self.adaptive_learner:
                correction_ctx = self.adaptive_learner.get_correction_context(user_input)
                if correction_ctx:
                    mega_context += f"\n[LEARNED CORRECTIONS]\n{correction_ctx}\n"
                # Get best strategy for this domain
                best_strategy = self.adaptive_learner.get_best_strategy()
                if best_strategy != "default":
                    mega_context += f"\n[PREFERRED STRATEGY: {best_strategy}]\n"

        except Exception as e:
            logger.debug(f"[MEGA] Pre-processing error (non-fatal): {e}")

        with self.tracer.span("process_request") as root_span:
            root_span.attributes["session_id"] = active_session
            root_span.attributes["max_tools"] = max_tools
            
            # ── SAFETY GATE: Check input before any processing ──
        safety_verdict = self.content_filter.check_input(user_input)
        if safety_verdict.is_blocked:
            logger.warning(
                f"Request BLOCKED by safety filter: "
                f"category={safety_verdict.category.value}"
            )
            response.answer = safety_verdict.refusal_message
            response.confidence = 1.0
            response.mode = "safety_refused"
            response.duration_ms = (time.time() - start_time) * 1000
            # Still persist to session for audit trail
            self.session_manager.add_message(
                active_session, "user", user_input,
            )
            self.session_manager.add_message(
                active_session, "assistant", response.answer,
                metadata={"mode": "safety_refused", "category": safety_verdict.category.value},
            )
            return response

        # ── Persist user message to session ──
        self.session_manager.add_message(
            active_session, "user", user_input,
        )

        with self.tracer.span("universal_routing") as route_span:
            # Step 0: UNIVERSAL — Domain classification + Persona detection
            if event_callback:
                event_callback({
                    "type": "execution_step",
                    "step": 1,
                    "phase": "routing",
                    "agent": self.agent_id,
                    "action": "Classifying domain and detecting persona...",
                    "duration": 0,
                    "status": "running"
                })
            
            route_start = time.time()
            domain_match = self.domain_router.classify(user_input)
            persona = self.persona_engine.detect(user_input)
            
            if event_callback:
                event_callback({
                    "type": "execution_step",
                    "step": 1,
                    "phase": "routing",
                    "agent": self.agent_id,
                    "action": f"Routed to '{domain_match.primary_domain}' domain as {persona.name}",
                    "duration": round((time.time() - route_start) * 1000),
                    "status": "done"
                })

            route_span.attributes["primary_domain"] = domain_match.primary_domain
            route_span.attributes["persona"] = persona.name
            
        # ── SGI CEO INTERCEPTION ──
        if domain_match.primary_domain == "sgi_ceo":
            from agents.ceo_agent import CEOAgent
            logger.info("Universal Router: Planetary SGI task detected. Escalating to CEO Agent orchestrator.")
            ceo = CEOAgent(self.generate_fn, self.tools, event_callback)
            dag_result = ceo.execute_planetary_task(user_input)
            
            response.answer = dag_result
            response.confidence = 1.0
            response.mode = "sgi_ceo_executed"
            response.duration_ms = (time.time() - start_time) * 1000
            
            self.session_manager.add_message(
                active_session, "assistant", response.answer,
                metadata={"mode": "sgi_ceo", "confidence": 1.0},
            )
            return response

        # ── TIER 6 OMNI SOLVER INTERCEPTION ──
        # Triggers if the user wants complex, multi-dimensional, universal problem solving
        if "solve" in user_input.lower() and ("everything" in user_input.lower() or "complex" in user_input.lower() or "omni" in user_input.lower() or "universal" in user_input.lower() or "no matter how" in user_input.lower()):
            from brain.universal_omni_solver import UniversalOmniSolver
            logger.critical("Universal Router: Tier 6 Universal Omni-Solver Request Detected. Escalating.")
            
            if event_callback:
                event_callback({
                    "type": "execution_step",
                    "step": 1,
                    "phase": "routing",
                    "agent": self.agent_id,
                    "action": "Escalating to Tier 6 Universal Omni-Solver...",
                    "duration": 0,
                    "status": "running"
                })
                
            solver = UniversalOmniSolver(self.generate_fn)
            omni_result = solver.execute_omni_solution(user_input)
            
            response.answer = omni_result
            response.confidence = 1.0
            response.mode = "omni_solver_executed"
            response.duration_ms = (time.time() - start_time) * 1000
            
            self.session_manager.add_message(
                active_session, "assistant", response.answer,
                metadata={"mode": "omni_solver", "confidence": 1.0},
            )
            return response
        
        # FEATURE 1: Dynamic Domain Generation
        # If confidence is 0.0 (no match), generate a dynamic expert context on the fly
        if domain_match.confidence == 0.0:
            logger.info("Universal Router: No domain matched. Generating Dynamic Expert...")
            dynamic_expert_prompt = self._generate_dynamic_expert(user_input)
            expert_context = dynamic_expert_prompt
            domain_match.primary_domain = "dynamic_expert"
        else:
            expert = get_expert(domain_match.primary_domain)
            expert_context = expert.get_prompt_injection()
            
            # FEATURE 2: Polymath Synthesis
            # If there are secondary domains, fuse them together
            if domain_match.is_multi_domain:
                logger.info(f"Universal Router: Multi-domain detected. Activating Polymath Synthesis blending {domain_match.primary_domain} and {domain_match.secondary_domains}")
                polymath_context = f"[POLYMATH FUSION ACTIVATED]\nPrimary Domain: {domain_match.primary_domain}\n\n{expert_context}\n\n"
                for sec_domain in domain_match.secondary_domains:
                    sec_expert = get_expert(sec_domain)
                    if sec_expert:
                        polymath_context += f"Secondary Domain: {sec_domain}\n{sec_expert.get_prompt_injection()}\n\n"
                expert_context = polymath_context

        reasoning = self.advanced_reasoner.reason(
            user_input,
            domain=domain_match.primary_domain,
            persona=self.persona_engine.current_name,
            domain_context=expert_context,
        )

        with self.tracer.span("compile_task") as comp_span:
            # Step 1: COMPILE — Parse user request
            if event_callback:
                event_callback({
                    "type": "execution_step",
                    "step": 2,
                    "phase": "thinking",
                    "agent": self.agent_id,
                    "action": "Compiling task requirements and building strategy...",
                    "duration": 0,
                    "status": "running"
                })
            
            comp_start = time.time()
            task_spec = self.compiler.compile(user_input)
            response.task_spec = task_spec
            
            if event_callback:
                event_callback({
                    "type": "execution_step",
                    "step": 2,
                    "phase": "thinking",
                    "agent": self.agent_id,
                    "action": f"Task compiled: {task_spec.action_type} (tools: {len(task_spec.tools_needed)})",
                    "duration": round((time.time() - comp_start) * 1000),
                    "status": "done"
                })

            comp_span.attributes["action_type"] = task_spec.action_type
            comp_span.attributes["tools_needed"] = len(task_spec.tools_needed)

        # Handle refused tasks from compiler safety check
        if task_spec.action_type == "refused":
            response.answer = task_spec.goal  # goal contains the refusal message
            response.confidence = 1.0
            response.mode = "safety_refused"
            response.duration_ms = (time.time() - start_time) * 1000
            self.session_manager.add_message(
                active_session, "assistant", response.answer,
                metadata={"mode": "safety_refused"},
            )
            return response

        # Step 2: Check if tools are needed (with policy + loop detection)
        tool_results = []
        if task_spec.tools_needed:
            tool_results = self._execute_tools_guarded(
                user_input, task_spec, max_calls=max_tools,
                session_id=active_session,
                event_callback=event_callback,
            )
            response.tools_used = tool_results
            response.loop_warnings = [
                w for w in self._get_loop_warnings()
            ]

        # ── MEGA: Inject project intelligence context if applicable ──
        project_context = ""
        try:
            if self.project_intelligence and task_spec and task_spec.action_type in ("code", "debug", "build"):
                # Check if we have a workspace to profile
                workspace = getattr(self, '_workspace_path', None)
                if workspace:
                    proj_ctx = self.project_intelligence.get_context_for_file(workspace, "")
                    if proj_ctx:
                        project_context = f"\n[PROJECT INTELLIGENCE]\n{proj_ctx}\n"
        except Exception as e:
            logger.debug(f"[MEGA] Project intelligence error (non-fatal): {e}")

        # Step 3: Build enhanced prompt with domain, persona, reasoning, tools, memory
        enhanced_prompt = self._build_enhanced_prompt(
            user_input, task_spec, tool_results,
            domain_context=expert_context + mega_context + project_context,
            persona_context=persona.get_style_prompt(),
            reasoning_prompt=reasoning.reasoning_prompt,
        )

        with self.tracer.span("think") as think_span:
            # Step 4: THINK — Use the thinking loop or direct generation
            if event_callback:
                event_callback({
                    "type": "execution_step",
                    "step": 4,
                    "phase": "synthesis",
                    "agent": self.agent_id,
                    "action": "Synthesizing answer with continuous thinking loop...",
                    "duration": 0,
                    "status": "running"
                })
            
            synth_start = time.time()
            if use_thinking_loop and task_spec.action_type != "general":
                thinking_result = self.thinking_loop.think(
                    problem=enhanced_prompt,
                    action_type=task_spec.action_type,
                    event_callback=event_callback,
                )
                response.answer = thinking_result.final_answer
                response.thinking_trace = thinking_result
                response.confidence = thinking_result.final_confidence
                response.iterations = thinking_result.iterations
                response.mode = thinking_result.mode.value
                think_span.attributes["iterations"] = response.iterations
            else:
                answer = self.thinking_loop.quick_think(
                    problem=enhanced_prompt,
                    action_type=task_spec.action_type,
                )
                response.answer = answer
                response.confidence = 0.8
                response.iterations = 1
                response.mode = "direct"
                
            if event_callback:
                event_callback({
                    "type": "execution_step",
                    "step": 4,
                    "phase": "complete",
                    "agent": self.agent_id,
                    "action": "Synthesis complete.",
                    "duration": round((time.time() - synth_start) * 1000),
                    "status": "done"
                })
                
            think_span.attributes["mode"] = response.mode
            think_span.attributes["confidence"] = response.confidence

        # ── OUTPUT SAFETY GATE: Filter AI response ──
        # 1) Check output for harmful content
        output_verdict = self.content_filter.check_output(response.answer)
        if output_verdict.is_blocked:
            logger.warning("AI output BLOCKED by content filter")
            response.answer = output_verdict.refusal_message
            response.mode = "output_filtered"

        # 2) Check output ethics
        ethics_verdict = self.ethics_engine.check_response_ethics(response.answer)
        if ethics_verdict.is_refused:
            logger.warning(f"AI output BLOCKED by ethics: {ethics_verdict.reason}")
            response.answer = ethics_verdict.friendly_message
            response.mode = "ethics_filtered"

        # 3) Redact any PII in the response
        response.answer = self.pii_guard.redact(response.answer)

        # Step 5: Update conversation + session
        self.conversation.append({"role": "user", "content": user_input})
        self.conversation.append({"role": "assistant", "content": response.answer})
        self.session_manager.add_message(
            active_session, "assistant", response.answer,
            metadata={
                "confidence": response.confidence,
                "mode": response.mode,
                "tools_used": len(tool_results),
            },
        )

        # Step 6: Auto-compact session if too long
        session = self.session_manager.get_session(active_session)
        if (session and session.message_count > agent_config.session_compaction_threshold):
            summary = f"Conversation with {session.message_count} messages about: {user_input[:100]}"
            self.session_manager.compact_session(active_session, summary)

        # ── JARVIS: Learn from interaction ──
        try:
            if self.predictive_intent:
                self.predictive_intent.record_action(
                    response.mode or "chat",
                    context={"topic": task_spec.action_type if task_spec else "general"},
                )
            if self.knowledge_nexus:
                self.knowledge_nexus.learn_from_conversation(
                    user_input, response.answer,
                    topic=task_spec.action_type if task_spec else "",
                )
            if self.jarvis_core:
                self.jarvis_core.update_interaction(
                    task_spec.action_type if task_spec else "general"
                )
        except Exception as e:
            logger.debug(f"[JARVIS] Learning hook error (non-fatal): {e}")

        # ── MEGA POST-PROCESSING: Store memory + Learn + Bus event ──
        try:
            # 1. Store interaction in semantic memory
            if self.semantic_memory:
                self.semantic_memory.store(
                    text=f"Q: {user_input[:200]} | A: {response.answer[:300]}",
                    source="conversation",
                    category="conversation",
                    importance=min(1.0, response.confidence),
                    metadata={
                        "domain": domain_match.primary_domain,
                        "mode": response.mode,
                        "session": active_session,
                    },
                )

            # 2. Record implicit positive feedback for adaptive learning
            if self.adaptive_learner:
                from brain.adaptive_learner import FeedbackType, LearningDomain
                domain_map = {
                    "code": LearningDomain.CODE_GENERATION,
                    "debug": LearningDomain.DEBUGGING,
                    "explain": LearningDomain.EXPLANATION,
                    "creative": LearningDomain.CREATIVE,
                }
                learn_domain = domain_map.get(
                    task_spec.action_type if task_spec else "",
                    LearningDomain.CONVERSATION,
                )
                self.adaptive_learner.record_feedback(
                    feedback_type=FeedbackType.IMPLICIT_ACCEPT,
                    domain=learn_domain,
                    strategy=response.mode or "default",
                    query=user_input[:200],
                    response=response.answer[:200],
                )

            # 3. Publish completion event to message bus
            if self.message_bus:
                self.message_bus.publish(
                    "agent.response.complete", {
                        "domain": domain_match.primary_domain,
                        "mode": response.mode,
                        "confidence": response.confidence,
                        "duration_ms": (time.time() - start_time) * 1000,
                        "session": active_session,
                    }, sender="controller",
                )

            # 4. Check if input matches a workflow trigger
            if self.workflow_engine:
                self.workflow_engine.check_event_triggers(user_input)

        except Exception as e:
            logger.debug(f"[MEGA] Post-processing error (non-fatal): {e}")

        response.duration_ms = (time.time() - start_time) * 1000
        
        # ── EXPERT TELEMETRY: Record metrics ──
        self.metrics.histogram("agent.process.duration_ms", response.duration_ms)
        self.metrics.histogram("agent.process.confidence", response.confidence)
        self.metrics.counter(f"agent.process.mode.{response.mode}")
        
        return response

    def chat(self, message: str, session_id: str = None) -> str:
        """
        Simple chat interface — returns just the answer text.
        Now with session persistence and workspace injection.
        """
        active_session = session_id or self._main_session.session_id

        # ── MEGA: Pre-process chat message ──
        try:
            if self.message_bus:
                self.message_bus.publish(
                    "agent.chat.incoming",
                    {"message": message[:200], "session": active_session},
                    sender="controller",
                )
            if self.plugin_manager:
                message = self.plugin_manager.run_preprocessors(message)
        except Exception:
            pass

        # Build context with workspace injection
        workspace_prompt = self.workspace.assemble_system_prompt(self.agent_id)
        skills_prompt = self.skills.get_injections()
        memory_context = self.memory.build_context(message)

        system_parts = [workspace_prompt]
        if skills_prompt:
            system_parts.append(skills_prompt)
        system = "\n\n".join(system_parts)
        if memory_context:
            system += f"\n\n{memory_context}"

        # ── MEGA: Inject semantic memory context ──
        try:
            if self.semantic_memory:
                sem_ctx = self.semantic_memory.get_context(message, max_tokens=300)
                if sem_ctx:
                    system += f"\n\n[SEMANTIC MEMORY]\n{sem_ctx}"
            if self.adaptive_learner:
                correction = self.adaptive_learner.get_correction_context(message)
                if correction:
                    system += f"\n\n[LEARNED CORRECTIONS]\n{correction}"
        except Exception:
            pass

        messages = list(self.conversation[-10:])
        messages.append({"role": "user", "content": message})

        try:
            from core.tokenizer import MistralTokenizer
            tokenizer = MistralTokenizer()
            prompt = tokenizer.format_chat(messages, system_prompt=system)
        except Exception:
            prompt = f"{system}\n\nUser: {message}\n\nAssistant:"

        response = self.generate_fn(prompt)

        # Update history + session
        self.conversation.append({"role": "user", "content": message})
        self.conversation.append({"role": "assistant", "content": response})
        self.session_manager.add_message(active_session, "user", message)
        self.session_manager.add_message(active_session, "assistant", response)

        # ── MEGA: Post-process chat ──
        try:
            if self.semantic_memory:
                self.semantic_memory.store(
                    text=f"Q: {message[:150]} | A: {response[:250]}",
                    source="chat", category="conversation",
                )
            if self.adaptive_learner:
                from brain.adaptive_learner import FeedbackType
                self.adaptive_learner.record_feedback(
                    FeedbackType.IMPLICIT_ACCEPT,
                    query=message[:200], response=response[:200],
                )
            if self.message_bus:
                self.message_bus.publish(
                    "agent.chat.complete",
                    {"session": active_session},
                    sender="controller",
                )
        except Exception:
            pass

        return response

    def _execute_tools_guarded(
        self,
        user_input: str,
        task_spec: TaskSpec,
        max_calls: int,
        session_id: str = "",
        event_callback: Optional[Callable[[dict], None]] = None,
    ) -> List[dict]:
        """Execute tools with policy checks and loop detection."""
        if event_callback:
            event_callback({
                "type": "execution_step",
                "step": 3,
                "phase": "tool-call",
                "agent": self.agent_id,
                "action": f"Executing {len(task_spec.tools_needed)} requested tools...",
                "duration": 0,
                "status": "running"
            })
        
        tools_start = time.time()
        results = []
        policy_ctx = PolicyContext(
            agent_id=self.agent_id,
            session_id=session_id,
        )

        for tool_name in task_spec.tools_needed[:max_calls]:
            tool = self.tools.get(tool_name)
            if not tool:
                continue

            # ── Policy check ──
            if not self.policy_engine.resolve(tool_name, policy_ctx):
                logger.warning(f"Tool '{tool_name}' denied by policy")
                results.append({
                    "tool": tool_name,
                    "args": {},
                    "result": {"error": f"Tool '{tool_name}' denied by policy"},
                })
                continue

            # ── Ethics check on tool usage ──
            ethics_verdict = self.ethics_engine.evaluate_action(
                action_type=task_spec.action_type,
                description=f"{tool_name}: {user_input}",
            )
            if ethics_verdict.is_refused:
                logger.warning(f"Tool '{tool_name}' denied by ethics: {ethics_verdict.reason}")
                results.append({
                    "tool": tool_name,
                    "args": {},
                    "result": {"error": ethics_verdict.friendly_message},
                })
                continue

            # Generate and execute
            args = self._generate_tool_args(user_input, tool)
            if args:
                result = self.tools.execute(
                    tool_name=tool_name,
                    sandbox=tool.requires_sandbox,
                    policy_context=policy_ctx,
                    **args,
                )

                # ── Loop detection ──
                loop_check = self.loop_detector.record(
                    tool_name=tool_name,
                    args=args,
                    result=result,
                )

                if loop_check.should_halt:
                    logger.error(f"Circuit breaker triggered: {loop_check.message}")
                    results.append({
                        "tool": tool_name,
                        "args": args,
                        "result": result,
                        "loop_warning": loop_check.message,
                    })
                    break  # Stop all tool execution

                if loop_check.should_warn:
                    logger.warning(f"Loop warning: {loop_check.message}")

                results.append({
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                    "loop_warning": loop_check.message if loop_check else None,
                })

                # ── THREAT SCAN: Auto-scan after file/URL operations ──
                if self._threat_auto_scan and self.threat_scanner:
                    threat_alert = self._handle_threat_scan(tool_name, args, result)
                    if threat_alert:
                        results.append(threat_alert)

                # Persist tool call to session
                if session_id:
                    self.session_manager.add_message(
                        session_id, "tool",
                        json.dumps({"tool": tool_name, "result": result}, default=str)[:500],
                        metadata={"tool_name": tool_name},
                    )

        if event_callback:
            event_callback({
                "type": "execution_step",
                "step": 3,
                "phase": "tool-call",
                "agent": self.agent_id,
                "action": f"Completed {len(results)} tool executions.",
                "duration": round((time.time() - tools_start) * 1000),
                "status": "done"
            })

        return results

    def _generate_tool_args(self, user_input: str, tool) -> Optional[dict]:
        """Use the LLM to generate appropriate arguments for a tool."""
        prompt = (
            f"Extract the arguments for the '{tool.name}' tool from this request.\n\n"
            f"Tool: {tool.name}\n"
            f"Description: {tool.description}\n"
            f"Parameters: {json.dumps(tool.parameters)}\n\n"
            f"User request: {user_input}\n\n"
            f"Respond with ONLY a JSON object of parameters. Example:\n"
            f'{{"param1": "value1"}}\n\n'
            f"JSON:"
        )

        try:
            response = self.generate_fn(prompt)
            json_match = re.search(r'\{[^{}]+\}', response)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to generate tool args: {e}")

        return None
        
    def _generate_dynamic_expert(self, user_input: str) -> str:
        """Universal Feature 1: Generate a dynamic domain expert for out-of-bounds topics."""
        prompt = (
            f"The user has asked a question that does not fit into our standard domains.\n"
            f"Question: {user_input}\n\n"
            f"Act as a 'Domain Architect'. Concoct a complete, highly-specialized 'Expert System Prompt' "
            f"specifically tailored to answer this kind of question.\n"
            f"Respond ONLY with the system prompt, written in the first person ('I am the Master [specialty]...'). "
            f"Do not answer the user's question, just define the persona."
        )
        try:
            return self.generate_fn(prompt)
        except Exception as e:
            logger.warning(f"Failed to generate dynamic expert: {e}")
            return "You are a helpful general assistant."

    def _build_enhanced_prompt(
        self,
        user_input: str,
        task_spec: TaskSpec,
        tool_results: List[dict],
        domain_context: str = "",
        persona_context: str = "",
        reasoning_prompt: str = "",
    ) -> str:
        """Build enhanced prompt with domain, persona, reasoning, tools, and memory."""
        parts = []

        # ── Domain expert context ──
        if domain_context:
            parts.append(f"DOMAIN EXPERTISE:\n{domain_context[:1500]}")

        # ── Persona / communication style ──
        if persona_context:
            parts.append(f"COMMUNICATION STYLE:\n{persona_context[:500]}")

        # ── Workspace context ──
        workspace_prompt = self.workspace.assemble_system_prompt(self.agent_id)
        if workspace_prompt:
            parts.append(f"AGENT CONTEXT:\n{workspace_prompt[:1000]}")

        # ── Skills context ──
        skills_prompt = self.skills.get_injections()
        if skills_prompt:
            parts.append(f"ACTIVE SKILLS:\n{skills_prompt[:500]}")

        # ── Memory context (hybrid search) ──
        memory_ctx = self.memory.build_context(user_input)
        if memory_ctx:
            parts.append(f"LEARNING FROM PAST EXPERIENCE:\n{memory_ctx}")

        # ── Tool results ──
        if tool_results:
            parts.append("TOOL RESULTS:")
            for tr in tool_results:
                result_str = json.dumps(tr["result"], indent=2, default=str)
                parts.append(f"  [{tr['tool']}]: {result_str[:500]}")

        # Task specification
        parts.append(f"TASK ANALYSIS:\n{task_spec.to_prompt()}")

        # Reasoning-enhanced prompt (if applicable)
        if reasoning_prompt and reasoning_prompt != user_input:
            parts.append(f"REASONING FRAMEWORK:\n{reasoning_prompt}")
        else:
            parts.append(f"\nUSER REQUEST: {user_input}")

        parts.append(
            "\nProvide a thorough, expert-level response. "
            "Adapt your style to the user's needs. "
            "Show your reasoning where appropriate."
        )

        return "\n\n".join(parts)

    def _get_loop_warnings(self) -> List[str]:
        """Get any active loop detection warnings."""
        stats = self.loop_detector.get_stats()
        warnings = []
        for tool, count in stats.get("tool_distribution", {}).items():
            if count >= agent_config.loop_warning_threshold:
                warnings.append(f"Tool '{tool}' called {count}x (possible loop)")
        return warnings

    def _handle_threat_scan(
        self,
        tool_name: str,
        args: dict,
        result: dict,
    ) -> Optional[dict]:
        """
        Auto-scan files/URLs after tool execution for threats.

        Triggers on file operations (read_file, write_file) and URL tools.
        If a threat is detected, returns an alert dict to inject into results.
        """
        scan_target = None
        scan_type = None

        # Detect file path from tool args
        file_tools = {"read_file", "write_file", "list_directory"}
        url_tools = {"web_search", "fetch_url"}

        if tool_name in file_tools:
            scan_target = args.get("file_path") or args.get("dir_path")
            scan_type = "file"
        elif tool_name in url_tools:
            scan_target = args.get("url") or args.get("query")
            scan_type = "url"

        if not scan_target:
            return None

        try:
            if scan_type == "file":
                from pathlib import Path
                if Path(scan_target).is_file():
                    report = self.threat_scanner.scan_file(scan_target)
                else:
                    return None
            elif scan_type == "url":
                report = self.threat_scanner.scan_url(scan_target)
            else:
                return None

            if report.is_threat:
                logger.warning(
                    f"🚨 THREAT DETECTED after {tool_name}: "
                    f"{report.threat_type.value if report.threat_type else 'unknown'} "
                    f"(confidence: {report.confidence:.1%})"
                )
                return {
                    "tool": "threat_scanner_auto",
                    "args": {"target": scan_target, "triggered_by": tool_name},
                    "result": {
                        "alert": report.summary(),
                        "scan_id": report.scan_id,
                        "threat_type": report.threat_type.value if report.threat_type else None,
                        "severity": report.severity.value if report.severity else None,
                        "confidence": report.confidence,
                        "recommended_action": report.recommended_action.value,
                        "detailed_report": report.detailed_report(),
                    },
                }
        except Exception as e:
            logger.debug(f"Threat auto-scan skipped for {scan_target}: {e}")

        return None

    # ──────────────────────────────────────
    # Process Manager Interface
    # ──────────────────────────────────────

    def execute_background(
        self,
        command: str,
        timeout: int = None,
    ) -> dict:
        """Execute a command in the background."""
        return self.process_manager.execute(
            command=command,
            agent_id=self.agent_id,
            background=True,
            timeout=timeout,
        )

    def poll_process(self, process_id: str) -> dict:
        """Poll a background process."""
        return self.process_manager.poll(process_id, agent_id=self.agent_id)

    def kill_process(self, process_id: str) -> dict:
        """Kill a background process."""
        return self.process_manager.kill(process_id, agent_id=self.agent_id)

    def list_processes(self) -> list:
        """List all background processes for this agent."""
        return self.process_manager.list_processes(agent_id=self.agent_id)

    # ──────────────────────────────────────
    # Session Interface
    # ──────────────────────────────────────

    def spawn_session(self, task: str, label: str = "") -> dict:
        """Spawn a sub-agent session for a task."""
        return self.session_manager.sessions_spawn(
            task=task,
            label=label,
            agent_id=self.agent_id,
            parent_session_id=self._main_session.session_id,
        )

    def send_to_session(self, session_id: str, message: str) -> dict:
        """Send a message to another session."""
        return self.session_manager.sessions_send(
            target_session_id=session_id,
            message=message,
        )

    # ──────────────────────────────────────
    # Stats & Management
    # ──────────────────────────────────────

    def get_stats(self) -> dict:
        """Get comprehensive agent statistics."""
        return {
            "agent_id": self.agent_id,
            "session_id": self._main_session.session_id,
            "conversation_length": len(self.conversation),
            "memory_stats": self.memory.get_stats(),
            "tools_available": len(self.tools.list_tools()),
            "tool_log": self.tools.get_execution_log()[-10:],
            "loop_stats": self.loop_detector.get_stats(),
            "active_sessions": len(self.session_manager.list_sessions(active_only=True)),
            "background_processes": len(self.process_manager.list_processes(self.agent_id)),
            "skills_loaded": len(self.skills.list_skills()),
            "policy_summary": self.policy_engine.get_policy_summary(
                PolicyContext(agent_id=self.agent_id)
            ),
            "agent_forge": self.agent_forge.get_stats(),
            "tool_forge": self.tool_forge.get_stats(),
            "auto_gap_detection": self.thinking_loop._auto_forge_stats,
        }

    def reset_conversation(self):
        """Clear conversation history."""
        self.conversation.clear()
        self.loop_detector.reset()
        logger.info("Conversation history cleared")
