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

        logger.info(
            f"Universal Agent Controller initialized — "
            f"agent_id='{agent_id}', profile='{profile.value}', "
            f"session='{self._main_session.session_id}', "
            f"skills={len(self.skills.list_skills())}, "
            f"domains=10, personas=5, reasoning_strategies=4, "
            f"safety=ENABLED"
        )

    def process(
        self,
        user_input: str,
        use_thinking_loop: bool = True,
        max_tool_calls: int = None,
        session_id: str = None,
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
            domain_match = self.domain_router.classify(user_input)
            persona = self.persona_engine.detect(user_input)
            
            route_span.attributes["primary_domain"] = domain_match.primary_domain
            route_span.attributes["persona"] = persona.name
        
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
            task_spec = self.compiler.compile(user_input)
            response.task_spec = task_spec
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
            )
            response.tools_used = tool_results
            response.loop_warnings = [
                w for w in self._get_loop_warnings()
            ]

        # Step 3: Build enhanced prompt with domain, persona, reasoning, tools, memory
        enhanced_prompt = self._build_enhanced_prompt(
            user_input, task_spec, tool_results,
            domain_context=expert_context,
            persona_context=persona.get_style_prompt(),
            reasoning_prompt=reasoning.reasoning_prompt,
        )

        with self.tracer.span("think") as think_span:
            # Step 4: THINK — Use the thinking loop or direct generation
            if use_thinking_loop and task_spec.action_type != "general":
                thinking_result = self.thinking_loop.think(
                    problem=enhanced_prompt,
                    action_type=task_spec.action_type,
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

        from core.tokenizer import MistralTokenizer
        messages = list(self.conversation[-10:])
        messages.append({"role": "user", "content": message})

        try:
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

        return response

    def _execute_tools_guarded(
        self,
        user_input: str,
        task_spec: TaskSpec,
        max_calls: int,
        session_id: str = "",
    ) -> List[dict]:
        """Execute tools with policy checks and loop detection."""
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
