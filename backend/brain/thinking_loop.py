"""
Thinking Loop — Enhanced Synthesize -> Verify -> Learn with Human-Like Reasoning.
Integrates 10+ brain subsystems for intelligent problem-solving with
Agent Lightning-inspired continuous self-improvement.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from config.settings import brain_config
from brain.memory import MemoryManager, FailureTuple, SuccessRecord
from brain.hypothesis import HypothesisEngine
from brain.verifier import VerifierStack, VerificationReport
from brain.risk_manager import RiskManager, RiskAssessment, GatingMode
from brain.reasoning import ReasoningEngine, CognitiveMode, ReasoningTrace
from brain.metacognition import MetacognitionEngine
from brain.problem_classifier import ProblemClassifier, ProblemDomain
from brain.expert_reflection import ExpertReflectionEngine

# Phase 10: Agent Lightning-Inspired Systems
from brain.trace_store import (
    TraceSpan, TrajectoryTrace, LearningStore, SpanType, emit_span
)
from brain.reward_model import RewardComputer, CompositeReward
from brain.credit_assignment import CreditAssignmentEngine, CreditReport
from brain.prompt_evolver import PromptEvolver
from brain.epistemic_checker import EpistemicChecker

from telemetry.metrics import MetricsCollector
from telemetry.tracer import SpanTracer

# Auto-Gap Detection: optional ToolForge integration
try:
    from agents.tools.tool_forge import ToolForge
except ImportError:
    ToolForge = None

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Auto-Gap Detection Constants
# ──────────────────────────────────────────────
MAX_AUTO_FORGE_ATTEMPTS = 2
TOOL_GAP_KEYWORDS = [
    "insufficient tools", "no tool available", "no suitable tool",
    "missing capability", "tool not found", "cannot find tool",
    "no tool for", "lack a capability", "unable to execute",
    "no matching tool", "tool does not exist",
]


@dataclass
class ThinkingStep:
    """Record of a single thinking iteration."""
    iteration: int = 0
    candidate: str = ""
    verification: Optional[VerificationReport] = None
    risk_assessment: Optional[RiskAssessment] = None
    reasoning_trace: Optional[ReasoningTrace] = None
    action_taken: str = ""
    result: str = ""
    improved: bool = False
    confidence_delta: float = 0.0
    duration_ms: float = 0.0
    strategy_used: str = ""
    meta_state: str = ""


@dataclass
class ThinkingResult:
    """Complete result of the thinking loop."""
    final_answer: str = ""
    final_confidence: float = 0.0
    iterations: int = 0
    mode: GatingMode = GatingMode.REFUSE
    steps: List[ThinkingStep] = field(default_factory=list)
    total_duration_ms: float = 0.0
    domain: str = "general"
    strategies_used: List[str] = field(default_factory=list)
    reflection: str = ""

    def summary(self) -> str:
        lines = [
            f"Thinking Complete [{self.domain}]",
            f"  Iterations:  {self.iterations}",
            f"  Confidence:  {self.final_confidence:.3f}",
            f"  Mode:        {self.mode.value}",
            f"  Strategies:  {self.strategies_used}",
            f"  Duration:    {self.total_duration_ms:.0f}ms",
        ]
        for step in self.steps:
            status = "+" if step.improved else "~"
            conf = step.verification.confidence if step.verification else 0
            lines.append(
                f"  {status} Step {step.iteration}: "
                f"conf={conf:.3f} "
                f"d={step.confidence_delta:+.3f} | {step.action_taken}"
            )
        return "\n".join(lines)


class ThinkingLoop:
    """
    Enhanced Synthesize -> Verify -> Learn loop with continuous self-improvement.

    Integrates 10+ brain subsystems for intelligent problem-solving:
    1. Problem classification -> optimal strategy selection
    2. Chain-of-thought reasoning with 5 cognitive modes
    3. Multi-hypothesis generation and Bayesian weight updates
    4. 6-layer verification (static/property/scenario/critic/code/security)
    5. Metacognition: stuck detection + auto-strategy switching
    6. Tri-Shield risk assessment with zero-vulnerability gate
    7. Memory: Bug Diary + reflections for continuous learning
    8. Structured trace spans (Agent Lightning-inspired)
    9. Multi-dimensional reward model with credit assignment
    10. APO-inspired prompt evolution
    11. Continuous online learning loop
    """

    LEARN_EVERY_N: int = 5  # Trigger learning cycle every N successes

    def __init__(
        self,
        generate_fn: Callable,
        memory: Optional[MemoryManager] = None,
        hypothesis_engine: Optional[HypothesisEngine] = None,
        verifier: Optional[VerifierStack] = None,
        risk_manager: Optional[RiskManager] = None,
        reasoning_engine: Optional[ReasoningEngine] = None,
        metacognition: Optional[MetacognitionEngine] = None,
        problem_classifier: Optional[ProblemClassifier] = None,
        learning_store: Optional[LearningStore] = None,
        reward_computer: Optional[RewardComputer] = None,
        credit_engine: Optional[CreditAssignmentEngine] = None,
        prompt_evolver: Optional[PromptEvolver] = None,
        expert_reflection: Optional[ExpertReflectionEngine] = None,
        tool_forge=None,
        config=None,
    ):
        self.generate_fn = generate_fn
        self.config = config or brain_config

        # Core brain components
        self.memory = memory or MemoryManager()
        self.hypothesis_engine = hypothesis_engine or HypothesisEngine()
        self.verifier = verifier or VerifierStack()
        self.risk_manager = risk_manager or RiskManager()

        # Phase 9: Cognitive systems
        self.reasoning = reasoning_engine or ReasoningEngine(generate_fn)
        self.metacognition = metacognition or MetacognitionEngine()
        self.classifier = problem_classifier or ProblemClassifier(generate_fn)

        self.learning_store = learning_store or LearningStore()
        self.reward_computer = reward_computer or RewardComputer()
        self.credit_engine = credit_engine or CreditAssignmentEngine(generate_fn)
        self.prompt_evolver = prompt_evolver or PromptEvolver(generate_fn)
        
        # Phase 11: Deep Expert Reflection
        self.expert_reflection = expert_reflection or ExpertReflectionEngine(generate_fn)
        
        # Phase 12: Epistemic Fact Checking
        self.epistemic_checker = EpistemicChecker(generate_fn)

        # ── EXPERT TELEMETRY ──
        self.tracer = SpanTracer()
        self.metrics = MetricsCollector.get_instance()

        # Auto-Gap Detection: ToolForge integration
        self.tool_forge = tool_forge
        self._auto_forge_attempts: int = 0
        self._auto_forge_stats = {"attempts": 0, "successes": 0, "failures": 0}

        # Learning counters
        self._success_count: int = 0
        self._total_solves: int = 0

    def think(
        self,
        problem: str,
        action_type: str = "general",
        max_iterations: Optional[int] = None,
        execute_fn: Optional[Callable] = None,
        sandbox_fn: Optional[Callable] = None,
    ) -> ThinkingResult:
        """
        Run the complete Synthesize → Verify → Learn loop.

        Args:
            problem: The task/problem to solve
            action_type: Type of action for risk assessment
            max_iterations: Override max iterations
            execute_fn: Function to execute the solution directly
            sandbox_fn: Function to execute in sandbox

        Returns:
            ThinkingResult with final answer and full thinking trace
        """
        result = ThinkingResult()
        start_time = time.time()

        # Reset auto-forge counter for this task
        self._auto_forge_attempts = 0

        # Initialize trajectory trace for this episode
        trajectory = TrajectoryTrace(problem=problem)

        self.metrics.counter("brain.thinking_loop.started")

        # Phase 1: Classify problem domain
        domain = self.classifier.classify(problem)
        strategy = self.classifier.get_strategy(domain)
        result.domain = domain.value
        trajectory.domain = domain.value
        logger.info(f"Domain: {domain.value} | Strategy: {strategy.summary()}")

        # Emit classification span
        trajectory.add_span(emit_span(
            span_type=SpanType.CLASSIFICATION,
            input_data=problem[:300],
            output_data=f"domain={domain.value}",
            cognitive_mode="classification",
            attributes={"strategy": strategy.summary()},
        ))

        # Phase 2: Estimate cognitive load + set iterations
        load = self.metacognition.estimate_cognitive_load(problem)
        max_iter = max_iterations or strategy.suggested_iterations
        logger.info(f"Cognitive load: {load:.2f} | Max iterations: {max_iter}")

        # Phase 3: Build memory context
        memory_context = self.memory.build_context(problem)
        regression_tests = self.memory.get_regression_tests()

        # Phase 4: Start metacognition monitoring
        current_mode = strategy.primary_mode
        self.metacognition.start_monitoring(current_mode.value)

        # Phase 5: Chain-of-thought reasoning (with evolved prompt)
        reasoning_prompt = self.prompt_evolver.get_best_prompt(
            "reasoning", domain.value
        )
        reasoning_trace = self.reasoning.reason(
            problem=problem,
            mode=current_mode,
            memory_context=memory_context,
        )

        # Emit reasoning span
        trajectory.add_span(emit_span(
            span_type=SpanType.REASONING,
            input_data=problem[:200],
            output_data=reasoning_trace.final_answer[:300],
            cognitive_mode=current_mode.value,
            prompt_template=reasoning_prompt[:200],
        ))

        # Phase 6: Generate hypotheses using reasoning output
        enriched_context = memory_context
        if reasoning_trace.final_answer:
            enriched_context += (
                "\n\nReasoning chain-of-thought:\n"
                + reasoning_trace.final_answer[:500]
            )

        hypotheses = self.hypothesis_engine.generate_hypotheses(
            problem=problem,
            generate_fn=self.generate_fn,
            context=enriched_context,
        )

        # Emit hypothesis span
        trajectory.add_span(emit_span(
            span_type=SpanType.HYPOTHESIS,
            input_data=enriched_context[:200],
            output_data=f"{len(hypotheses)} hypotheses generated",
            cognitive_mode=current_mode.value,
        ))

        prev_confidence = 0.0

        for iteration in range(max_iter):
            step_start = time.time()
            step = ThinkingStep(iteration=iteration)
            step.strategy_used = current_mode.value
            step.reasoning_trace = reasoning_trace

            # SYNTHESIZE: Get best candidate from hypothesis mixture
            step.candidate = self.hypothesis_engine.synthesize_candidate(
                synthesize_fn=self.generate_fn,
                problem=problem,
            )

            # VERIFY: Run 6-layer verification
            step.verification = self.verifier.verify(
                candidate=step.candidate,
                task=problem,
                generate_fn=self.generate_fn,
                regression_tests=regression_tests,
            )
            
            # Universal Feature 3: Epistemic Fact Check
            # Only run if baseline confidence is decent, otherwise it's just wasting tokens
            if step.verification.confidence > 0.6:
                passed_epistemic, epistemic_report = self.epistemic_checker.check_claims(step.candidate)
                if not passed_epistemic:
                    logger.warning("Fact Check Failed: Forcing Confidence to 0.1 to trigger LEARNING LOOP.")
                    step.verification.confidence = 0.1  # Force rejection
                    # Inject the hallucination feedback into the failure loop
                    step.verification.critic_details = f"EPISTEMIC FAILURE: {epistemic_report}"

            # ASSESS RISK: Tri-Shield objective
            step.risk_assessment = self.risk_manager.assess_risk(
                candidate=step.candidate,
                task=problem,
                verification=step.verification,
                action_type=action_type,
            )

            # Track improvement
            step.confidence_delta = step.verification.confidence - prev_confidence
            step.improved = step.confidence_delta > 0

            # GATE: Decide action mode
            mode = step.risk_assessment.mode

            if mode == GatingMode.EXECUTE:
                step.action_taken = "execute"
                if execute_fn:
                    step.result = execute_fn(step.candidate)
                else:
                    step.result = step.candidate

                step.duration_ms = (time.time() - step_start) * 1000
                result.steps.append(step)

                # Success! Store in memory
                self.memory.store_success(SuccessRecord(
                    task=problem,
                    approach=step.candidate[:500],
                    result=step.result[:500],
                    confidence=step.verification.confidence,
                ))

                # Deep Expert Reflection (Success -> Principle)
                principle = self.expert_reflection.extract_first_principle(
                    problem=problem,
                    successful_solution=step.candidate,
                    domain=domain.value
                )
                if principle:
                    self.memory.store_principle(principle)

                # Update verifier calibration
                self.verifier.calibrate(step.verification, actual_success=True)

                # Emit reward span
                comp_reward = self.reward_computer.compute_reward(
                    step.verification, domain.value
                )
                trajectory.add_span(emit_span(
                    span_type=SpanType.REWARD,
                    input_data=f"verification_confidence={step.verification.confidence:.3f}",
                    output_data=comp_reward.summary(),
                    reward=comp_reward.primary_reward,
                    attributes={"dimensions": comp_reward.to_dict()},
                ))

                result.final_answer = step.result
                result.final_confidence = step.verification.confidence
                result.mode = GatingMode.EXECUTE
                break

            elif mode == GatingMode.SANDBOX:
                step.action_taken = "sandbox"
                if sandbox_fn:
                    step.result = sandbox_fn(step.candidate)
                else:
                    step.result = step.candidate
                step.duration_ms = (time.time() - step_start) * 1000
                result.steps.append(step)

                result.final_answer = step.result
                result.final_confidence = step.verification.confidence
                result.mode = GatingMode.SANDBOX
                break

            else:
                # REFUSE/LEARN: Not confident enough, improve and retry
                step.action_taken = "improve"
                
                # Deep Expert Reflection (Failure -> Root Cause)
                str_feedback = (
                    f"static={step.verification.v_static:.2f}, "
                    f"property={step.verification.v_property:.2f}, "
                    f"scenario={step.verification.v_scenario:.2f}, "
                    f"critic={step.verification.v_critic:.2f}"
                )
                
                root_cause = self.expert_reflection.deduce_root_cause(
                    problem=problem,
                    failed_candidate=step.candidate,
                    verifier_feedback=str_feedback
                )

                # ── AUTO-GAP DETECTION ──
                # Check if failure is due to missing tools/capabilities
                failure_text = f"{root_cause} {step.candidate}".lower()
                is_tool_gap = any(kw in failure_text for kw in TOOL_GAP_KEYWORDS)

                if (is_tool_gap
                        and self.tool_forge is not None
                        and self._auto_forge_attempts < MAX_AUTO_FORGE_ATTEMPTS):
                    self._auto_forge_attempts += 1
                    self._auto_forge_stats["attempts"] += 1
                    logger.info(
                        f"🔧 Auto-Gap Detection: Capability gap detected "
                        f"(attempt {self._auto_forge_attempts}/{MAX_AUTO_FORGE_ATTEMPTS})"
                    )

                    # Extract capability description from the root cause
                    forge_desc = (
                        f"Tool needed for: {problem[:200]}. "
                        f"Root cause of failure: {root_cause[:200]}"
                    )

                    try:
                        forged = self.tool_forge.forge_tool(
                            capability_description=forge_desc,
                        )
                        if forged and forged.is_active:
                            self._auto_forge_stats["successes"] += 1
                            logger.info(
                                f"✅ Auto-Forge SUCCESS: Created tool '{forged.name}' "
                                f"— retrying task with new capability"
                            )
                            step.action_taken = "auto_forge_success"
                            # The next iteration will have access to the new tool
                        else:
                            self._auto_forge_stats["failures"] += 1
                            logger.warning(
                                "❌ Auto-Forge FAILED: Could not create needed tool"
                            )
                            # Store limitation in Bug Diary
                            self.memory.store_failure(FailureTuple(
                                task=problem,
                                solution="auto_forge_attempt",
                                action="tool_forge",
                                observation="Tool forge failed to create needed capability",
                                root_cause=forge_desc[:300],
                                category="auto_forge_failure",
                                severity=0.8,
                            ))
                    except Exception as e:
                        self._auto_forge_stats["failures"] += 1
                        logger.error(f"Auto-Forge ERROR: {e}")

                # LEARN: Store failure and update
                failure = FailureTuple(
                    task=problem,
                    solution=step.candidate[:500],
                    action="thinking_loop_iteration",
                    observation=f"Confidence too low: {step.verification.confidence:.3f}",
                    root_cause=root_cause,
                    fix="",
                    new_test="",
                    category="low_confidence",
                    severity=1.0 - step.verification.confidence,
                )
                self.memory.store_failure(failure)

                # Update hypothesis weights based on verification scores
                evidence = {}
                for h in self.hypothesis_engine.hypotheses:
                    # Use inverse confidence as loss
                    evidence[h.id] = 1.0 - step.verification.confidence
                self.hypothesis_engine.update_weights(evidence)

                # Prune weak hypotheses
                self.hypothesis_engine.prune_weak()

                step.duration_ms = (time.time() - step_start) * 1000
                result.steps.append(step)
                prev_confidence = step.verification.confidence

                # Metacognition: update and check if stuck
                self.metacognition.update(step.verification.confidence, iteration)
                step.meta_state = self.metacognition.state.trend()

                # Auto-switch strategy if stuck
                if self.metacognition.should_switch_strategy():
                    all_modes = self.classifier.get_all_modes(domain)
                    mode_names = [m.value for m in all_modes]
                    next_name = self.metacognition.recommend_strategy(mode_names)
                    if next_name:
                        for m in CognitiveMode:
                            if m.value == next_name:
                                current_mode = m
                                break
                        self.metacognition.switch_strategy(current_mode.value)
                        result.strategies_used.append(current_mode.value)

                        # Re-reason with new mode
                        reasoning_trace = self.reasoning.reason(
                            problem=problem,
                            mode=current_mode,
                            memory_context=memory_context,
                        )
                        logger.info(f"Strategy switched to: {current_mode.value}")

                # Check if improvement has plateaued
                if (iteration > 0
                        and abs(step.confidence_delta) < self.config.improvement_threshold
                        and not self.metacognition.should_switch_strategy()):
                    logger.info("Improvement plateaued, stopping early")
                    result.final_answer = step.candidate
                    result.final_confidence = step.verification.confidence
                    result.mode = GatingMode.REFUSE
                    break

        # If we exhausted iterations without execute/sandbox
        if not result.final_answer and result.steps:
            last_step = result.steps[-1]
            result.final_answer = last_step.candidate
            result.final_confidence = last_step.verification.confidence
            result.mode = last_step.risk_assessment.mode

        result.iterations = len(result.steps)
        result.total_duration_ms = (time.time() - start_time) * 1000
        if not result.strategies_used:
            result.strategies_used = [current_mode.value]

        # Universal Feature 5: Goal Tree Visualization Generation
        # Append a Mermaid.js diagram to the final answer detailing how the problem was processed
        if result.final_answer and not result.final_answer.endswith("```mermaid"):
            goal_tree = self._generate_goal_tree(trajectory, result, domain)
            result.final_answer += f"\n\n### Universal Goal Tree Breakdown\n```mermaid\n{goal_tree}\n```\n"

        # ── Phase 10: Post-Solve Learning Pipeline ──
        self._post_solve_learning(trajectory, result, domain)

        self.metrics.histogram("brain.thinking_loop.duration_ms", result.total_duration_ms)
        self.metrics.histogram("brain.thinking_loop.iterations", result.iterations)
        self.metrics.histogram("brain.thinking_loop.final_confidence", result.final_confidence)

        return result
        
    def _generate_goal_tree(self, trajectory: TrajectoryTrace, result: ThinkingResult, domain: ProblemDomain) -> str:
        """Universal Feature 5: Generate a Mermaid Flowchart representing the reasoning path."""
        lines = [
            "graph TD",
            f"  Start[User Request] --> Classify[Domain: {domain.value}]",
            f"  Classify --> Strategy[{result.strategies_used[0] if result.strategies_used else 'Chain_of_thought'}]",
        ]
        
        last_node = "Strategy"
        for i, step in enumerate(result.steps):
            gen_node = f"Gen_{i}[Iteration {i+1}: Synthesize]"
            lines.append(f"  {last_node} --> {gen_node}")
            
            conf_str = f"Conf: {step.verification.confidence:.2f}" if step.verification else "Conf: ???"
            ver_node = f"Verify_{i}[Verify: {conf_str}]"
            lines.append(f"  {gen_node} --> {ver_node}")
            
            act_node = f"Gate_{i}[Gate: {step.action_taken}]"
            lines.append(f"  {ver_node} --> {act_node}")
            
            if step.action_taken in ("execute", "sandbox"):
                lines.append(f"  {act_node} --> Success[Execution Successful]")
                break
            else:
                lines.append(f"  {act_node} --> Fail[Critique & Re-Hypothesize]")
                last_node = "Fail"
                
        return "\n".join(lines)

    def _post_solve_learning(
        self,
        trajectory: TrajectoryTrace,
        result: ThinkingResult,
        domain: ProblemDomain,
    ) -> None:
        """Agent Lightning-inspired post-solve learning pipeline.

        1. Finalize trajectory trace
        2. Compute multi-dimensional reward
        3. Run credit assignment
        4. Update strategy weights
        5. Record prompt performance
        6. Trigger continuous learning cycle periodically
        """
        success = result.mode == GatingMode.EXECUTE

        # Finalize trajectory
        trajectory.final_answer = result.final_answer[:500]
        trajectory.final_reward = result.final_confidence
        trajectory.success = success
        trajectory.gating_mode = result.mode.value
        trajectory.strategies_used = result.strategies_used
        trajectory.total_iterations = result.iterations
        trajectory.total_duration_ms = result.total_duration_ms

        # Compute multi-dimensional reward from last verification
        if result.steps and result.steps[-1].verification:
            comp_reward = self.reward_computer.compute_reward(
                result.steps[-1].verification, domain.value
            )
            trajectory.final_reward = comp_reward.primary_reward
            trajectory.reward_dimensions = comp_reward.to_dict()

        # Credit assignment: which steps actually helped?
        credit_report = self.credit_engine.assign_credit(
            trajectory,
            use_counterfactual=True,
            use_attention=(result.iterations <= 8),  # Skip LLM scoring for long runs
        )

        # Update strategy weights based on outcome
        if hasattr(self.classifier, "update_strategy_weights"):
            for strategy_name in result.strategies_used:
                self.classifier.update_strategy_weights(
                    domain=domain,
                    reward=trajectory.final_reward,
                    strategy_used=strategy_name,
                )

        # Record prompt performance for evolution
        synthesis_prompt = self.prompt_evolver.get_best_prompt(
            "synthesis", domain.value
        )
        self.prompt_evolver.record_performance(
            purpose="synthesis",
            prompt_used=synthesis_prompt,
            reward=trajectory.final_reward,
            domain=domain.value,
        )

        # Persist trajectory
        self.learning_store.store_trajectory(trajectory)

        # Update counters and trigger learning cycle
        self._total_solves += 1
        if success:
            self._success_count += 1

        if self._success_count > 0 and self._success_count % self.LEARN_EVERY_N == 0:
            self._continuous_learning_cycle(domain)

        logger.info(
            f"Post-solve learning: reward={trajectory.final_reward:.3f}, "
            f"helpful_steps={len(credit_report.get_helpful_steps())}, "
            f"total_solves={self._total_solves}"
        )

    def _continuous_learning_cycle(self, domain: ProblemDomain) -> None:
        """Periodic learning cycle inspired by Agent Lightning's online learning.

        Triggered every N successes. Analyzes recent trajectories to:
        1. Update reward dimension weights
        2. Evolve prompts
        3. Refine strategy recommendations
        """
        logger.info(f"=== Continuous Learning Cycle (solve #{self._total_solves}) ===")

        # Query recent trajectories for this domain
        recent = self.learning_store.query_trajectories(
            domain=domain.value,
            limit=20,
        )

        if len(recent) < 3:
            return

        # Analyze success patterns
        successes = [t for t in recent if t.success]
        failures = [t for t in recent if not t.success]

        if successes:
            avg_success_reward = sum(t.final_reward for t in successes) / len(successes)
        else:
            avg_success_reward = 0.0

        if failures:
            avg_fail_reward = sum(t.final_reward for t in failures) / len(failures)
        else:
            avg_fail_reward = 0.0

        logger.info(
            f"Learning from {len(recent)} trajectories: "
            f"{len(successes)} successes (avg={avg_success_reward:.3f}), "
            f"{len(failures)} failures (avg={avg_fail_reward:.3f})"
        )

        # Update reward dimension weights based on success correlation
        for trace in successes:
            for dim_name, dim_value in trace.reward_dimensions.items():
                if dim_name != "composite":
                    self.reward_computer.update_weights(
                        domain=domain.value,
                        dimension_name=dim_name,
                        delta=dim_value - 0.5,  # Positive if above average
                    )

        stats = self.learning_store.get_stats()
        logger.info(f"Learning store stats: {stats}")

    def quick_think(
        self,
        problem: str,
        action_type: str = "general",
    ) -> str:
        """
        Quick single-pass thinking without the full loop.

        For simple queries where the full loop is overkill.
        """
        # Check memory for similar past problems
        context = self.memory.build_context(problem)

        prompt = problem
        if context:
            prompt = f"{context}\n\n---\n\n{problem}"

        response = self.generate_fn(prompt)

        # Light verification
        report = self.verifier.verify(
            candidate=response,
            task=problem,
            generate_fn=self.generate_fn,
        )

        if report.passed:
            self.memory.store_success(SuccessRecord(
                task=problem,
                approach="direct_generation",
                result=response[:500],
                confidence=report.confidence,
            ))

        return response

    def get_thinking_summary(self, result: ThinkingResult) -> str:
        """Get a formatted summary of the thinking process."""
        return result.summary()
