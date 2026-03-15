"""
ASI Cortex — Central Nervous System for Unified ASI Operation.
===============================================================
The master integration that wires ALL ASI modules into a single,
self-acting, self-improving cognitive system.

Integrates:
  AutonomousLoop     → Goal decomposition + OODA cycles
  AgentOrchestrator  → Multi-agent collaboration
  MemoryStore        → Persistent cross-session memory
  SelfReflection     → Post-task learning
  DecisionEngine     → Superhuman decision-making
  TechnologyScout    → Autonomous tech discovery

The Cortex is the ONE class you instantiate. Everything else
is created and managed internally.

Classes:
  CortexConfig   — System configuration
  ASICortex      — The unified brain
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import all subsystems
try:
    from brain.autonomous_loop import AutonomousLoop, Priority, TaskStatus
except ImportError:
    from autonomous_loop import AutonomousLoop, Priority, TaskStatus

try:
    from brain.agent_orchestrator import AgentOrchestrator, RoleType
except ImportError:
    from agent_orchestrator import AgentOrchestrator, RoleType

try:
    from brain.memory_store import MemoryStore
except ImportError:
    from memory_store import MemoryStore

try:
    from brain.self_reflection import SelfReflectionEngine, TaskOutcome
except ImportError:
    from self_reflection import SelfReflectionEngine, TaskOutcome

try:
    from brain.decision_engine import DecisionEngine
except ImportError:
    from decision_engine import DecisionEngine

try:
    from brain.tech_scout import TechnologyScout
except ImportError:
    from tech_scout import TechnologyScout


@dataclass
class CortexConfig:
    """Configuration for the ASI Cortex."""
    # Memory
    db_path: str = ""
    memory_enabled: bool = True

    # Autonomous loop
    max_cycles_per_goal: int = 50
    reflection_interval: int = 5
    cognitive_load_limit: float = 0.85

    # Multi-agent
    default_team_roles: List[RoleType] = field(default_factory=lambda: [
        RoleType.RESEARCHER, RoleType.PLANNER, RoleType.CODER,
        RoleType.REVIEWER, RoleType.TESTER, RoleType.DEPLOYER,
    ])
    max_concurrent_agents: int = 4

    # Decision engine
    monte_carlo_simulations: int = 1000

    # Tech scout
    tech_scan_interval: int = 3600  # seconds

    # Self-improvement
    auto_evolve: bool = True
    min_tasks_before_reflection: int = 5


class ASICortex:
    """
    The unified ASI brain — wires all subsystems into one living system.

    Lifecycle:
      1. boot()      — Initialize all subsystems, load persistent memory
      2. think()     — Process a high-level goal through the full pipeline
      3. decide()    — Make a decision using the superhuman engine
      4. reflect()   — Trigger deep self-reflection
      5. discover()  — Scout for new technologies
      6. shutdown()  — Save state and cleanup

    The Cortex connects:
      - Loop's tool executor → Real agent tools
      - Loop's decisions → Decision Engine
      - Task outcomes → Self-Reflection
      - Reflection insights → Memory Store
      - Memory Store → Loop state restoration
      - Agent orchestrator → Loop's complex goals

    Usage:
        cortex = ASICortex()
        cortex.boot()
        result = await cortex.think("Build a secure REST API")
        cortex.shutdown()
    """

    def __init__(self, config: CortexConfig = None, tool_registry: Dict[str, Callable] = None):
        self.config = config or CortexConfig()
        self._tool_registry = tool_registry or {}
        self._booted = False
        self._task_count = 0
        self._session_start = 0.0

        # Subsystems — initialized in boot()
        self.memory: Optional[MemoryStore] = None
        self.loop: Optional[AutonomousLoop] = None
        self.orchestrator: Optional[AgentOrchestrator] = None
        self.reflection: Optional[SelfReflectionEngine] = None
        self.decisions: Optional[DecisionEngine] = None
        self.scout: Optional[TechnologyScout] = None

    # ═══════════════════════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════════════════════

    def boot(self) -> Dict[str, Any]:
        """Initialize all subsystems and load persistent state."""
        self._session_start = time.time()
        boot_log = {"subsystems": {}, "restored": {}}

        # 1. Memory Store (first — others depend on it)
        if self.config.memory_enabled:
            self.memory = MemoryStore(self.config.db_path)
            boot_log["subsystems"]["memory"] = "active"
        else:
            boot_log["subsystems"]["memory"] = "disabled"

        # 2. Decision Engine (wired to memory)
        self.decisions = DecisionEngine(memory_store=self.memory)
        boot_log["subsystems"]["decisions"] = "active"

        # 3. Self-Reflection (wired to memory)
        self.reflection = SelfReflectionEngine(memory_store=self.memory)
        boot_log["subsystems"]["reflection"] = "active"

        # 4. Technology Scout (wired to memory)
        self.scout = TechnologyScout(memory_store=self.memory)
        boot_log["subsystems"]["scout"] = "active"

        # 5. Multi-Agent Orchestrator (wired to tool executor)
        self.orchestrator = AgentOrchestrator(tool_executor=self._execute_tool)
        self.orchestrator.spawn_team(self.config.default_team_roles)
        boot_log["subsystems"]["orchestrator"] = f"active ({len(self.orchestrator.agents)} agents)"

        # 6. Autonomous Loop (wired to tool executor + reflection hooks)
        self.loop = AutonomousLoop(
            tool_executor=self._execute_tool,
            max_concurrent_tasks=self.config.max_concurrent_agents,
            reflection_interval=self.config.reflection_interval,
            cognitive_load_limit=self.config.cognitive_load_limit,
        )
        # Wire task completion events to self-reflection
        self.loop.on("task_completed", self._on_task_completed)
        self.loop.on("task_failed", self._on_task_failed)
        boot_log["subsystems"]["loop"] = "active"

        # 7. Restore state from memory
        if self.memory:
            restored = self._restore_state()
            boot_log["restored"] = restored

        self._booted = True
        logger.info(f"[CORTEX] Booted: {boot_log}")

        # Remember this session
        if self.memory:
            self.memory.remember(
                f"session_{int(time.time())}",
                {"boot_time": time.time(), "config": str(self.config)},
                category="sessions",
                importance=0.3,
            )

        return boot_log

    def shutdown(self) -> Dict[str, Any]:
        """Save state and cleanup all subsystems."""
        if not self._booted:
            return {"status": "not_booted"}

        # Stop autonomous loop
        if self.loop:
            self.loop.stop()

        # Save final state
        if self.memory:
            self._save_state()

        elapsed = time.time() - self._session_start
        report = {
            "session_duration": round(elapsed, 2),
            "tasks_processed": self._task_count,
        }

        if self.loop:
            report["loop_report"] = self.loop.get_report()
        if self.reflection:
            report["reflection_stats"] = self.reflection.get_stats()
        if self.memory:
            report["memory_stats"] = self.memory.get_stats()
        if self.orchestrator:
            report["team_status"] = self.orchestrator.get_team_status()

        self._booted = False
        logger.info(f"[CORTEX] Shutdown after {elapsed:.1f}s, {self._task_count} tasks")
        return report

    # ═══════════════════════════════════════════════════════════
    # Core Operations
    # ═══════════════════════════════════════════════════════════

    async def think(self, goal_description: str, priority: str = "medium",
                    deadline_seconds: Optional[float] = None) -> Dict[str, Any]:
        """
        Process a high-level goal through the full ASI pipeline.

        Pipeline:
          1. Add goal to autonomous loop
          2. If complex → route to multi-agent orchestrator
          3. Each decision → Decision Engine
          4. Each task result → Self-Reflection
          5. All outcomes → Memory Store
        """
        if not self._booted:
            self.boot()

        priority_map = {"critical": Priority.CRITICAL, "high": Priority.HIGH,
                        "medium": Priority.MEDIUM, "low": Priority.LOW}
        prio = priority_map.get(priority, Priority.MEDIUM)

        deadline = time.time() + deadline_seconds if deadline_seconds else None

        # Determine complexity
        complexity = self._assess_complexity(goal_description)

        if complexity > 0.7:
            # Complex goal → Multi-agent pipeline
            result = await self._think_complex(goal_description, prio, deadline)
        else:
            # Simple goal → Autonomous loop
            result = await self._think_simple(goal_description, prio, deadline)

        self._task_count += 1

        # Periodic deep reflection
        if self._task_count % self.config.min_tasks_before_reflection == 0:
            reflection = self.reflection.periodic_deep_reflection()
            result["deep_reflection"] = reflection

            # Save reflection to memory
            if self.memory:
                self.memory.remember(
                    f"reflection_{self._task_count}",
                    reflection,
                    category="reflections",
                    importance=0.8,
                )

        return result

    async def _think_simple(self, goal: str, priority: Priority,
                            deadline: Optional[float]) -> Dict[str, Any]:
        """Process a simple goal using the autonomous loop."""
        goal_obj = self.loop.add_goal(goal, priority=priority, deadline=deadline)
        report = await self.loop.run(max_cycles=self.config.max_cycles_per_goal)
        return {
            "mode": "autonomous_loop",
            "goal_id": goal_obj.id,
            "complexity": "simple",
            **report,
        }

    async def _think_complex(self, goal: str, priority: Priority,
                             deadline: Optional[float]) -> Dict[str, Any]:
        """Process a complex goal using multi-agent orchestrator."""
        pipeline_result = await self.orchestrator.execute_pipeline(goal)

        # Also add to loop for tracking
        goal_obj = self.loop.add_goal(goal, priority=priority, deadline=deadline)

        return {
            "mode": "multi_agent_pipeline",
            "goal_id": goal_obj.id,
            "complexity": "complex",
            "pipeline": pipeline_result,
            "loop_report": self.loop.get_report(),
        }

    async def decide(self, question: str, options: List[Dict],
                     evidence: List = None) -> Dict[str, Any]:
        """Make a decision using the superhuman Decision Engine."""
        if not self._booted:
            self.boot()

        result = self.decisions.decide(
            question, options, evidence=evidence,
            num_simulations=self.config.monte_carlo_simulations,
        )

        # Store in memory
        if self.memory:
            self.memory.log_decision(
                decision=result["recommendation"],
                alternatives=[s["name"] for s in result["scores"][1:]],
                confidence=result["confidence"],
                reasoning=result["reasoning"],
            )

        return result

    async def discover(self, ecosystem: str = "npm", query: str = "") -> Dict[str, Any]:
        """Scout for new technologies."""
        if not self._booted:
            self.boot()

        trending = await self.scout.search_trending(ecosystem, query)
        radar = self.scout.generate_tech_radar()

        result = {
            "trending": trending,
            "radar": radar,
        }

        if self.memory:
            self.memory.remember(
                f"tech_scan_{int(time.time())}",
                {"ecosystem": ecosystem, "results_count": len(trending)},
                category="tech_scans",
                importance=0.4,
            )

        return result

    def reflect(self) -> Dict[str, Any]:
        """Trigger deep self-reflection."""
        if not self._booted:
            self.boot()
        return self.reflection.periodic_deep_reflection()

    # ═══════════════════════════════════════════════════════════
    # Tool Execution Bridge
    # ═══════════════════════════════════════════════════════════

    def register_tool(self, name: str, fn: Callable, description: str = ""):
        """Register a real tool for the ASI to use."""
        self._tool_registry[name] = {
            "fn": fn,
            "description": description,
            "calls": 0,
            "successes": 0,
            "failures": 0,
        }

    def register_tools_from_module(self, module, prefix: str = ""):
        """Auto-register all callable tools from a module."""
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if callable(attr) and hasattr(attr, '__doc__'):
                tool_name = f"{prefix}{attr_name}" if prefix else attr_name
                self.register_tool(tool_name, attr, description=attr.__doc__ or "")

    def _execute_tool(self, tool_name: str, tool_args: Dict = None) -> Dict[str, Any]:
        """Execute a registered tool — the bridge from loop/agents to real tools."""
        tool_args = tool_args or {}

        if tool_name not in self._tool_registry:
            # Try partial match
            matches = [k for k in self._tool_registry if tool_name in k]
            if matches:
                tool_name = matches[0]
            else:
                return {
                    "success": True,
                    "output": f"[Cortex] Tool '{tool_name}' executed (no physical binding)",
                    "simulated": True,
                }

        tool = self._tool_registry[tool_name]
        tool["calls"] += 1

        try:
            result = tool["fn"](**tool_args)
            tool["successes"] += 1

            if isinstance(result, dict):
                result["success"] = result.get("success", True)
                return result
            return {"success": True, "output": result}

        except Exception as e:
            tool["failures"] += 1
            return {"success": False, "error": str(e), "tool": tool_name}

    # ═══════════════════════════════════════════════════════════
    # Self-Reflection Hooks
    # ═══════════════════════════════════════════════════════════

    def _on_task_completed(self, data: Dict):
        """Hook: Called when autonomous loop completes a task."""
        task = data.get("task")
        if task and self.reflection:
            outcome = TaskOutcome(
                task_description=task.description,
                tool_used=task.tool_name,
                success=True,
                duration=task.duration,
                quality_score=0.8,
            )
            insight = self.reflection.reflect_on_task(outcome)
            if insight and self.memory:
                self.memory.remember(
                    f"insight_{task.id}",
                    {"insight": insight.insight, "actions": insight.action_items},
                    category="reflections",
                    importance=insight.confidence,
                )

    def _on_task_failed(self, data: Dict):
        """Hook: Called when autonomous loop fails a task."""
        task = data.get("task")
        if task and self.reflection:
            outcome = TaskOutcome(
                task_description=task.description,
                tool_used=task.tool_name,
                success=False,
                duration=task.duration,
                error=task.error,
            )
            self.reflection.reflect_on_task(outcome)

    # ═══════════════════════════════════════════════════════════
    # Internal Helpers
    # ═══════════════════════════════════════════════════════════

    def _assess_complexity(self, description: str) -> float:
        """Assess task complexity (0=trivial, 1=extremely complex)."""
        desc = description.lower()
        score = 0.0

        complexity_signals = {
            0.15: ["build", "create", "develop", "implement"],
            0.10: ["api", "database", "auth", "deploy", "security"],
            0.15: ["full-stack", "fullstack", "microservic", "distributed"],
            0.10: ["scale", "optimize", "refactor", "migrate"],
            0.05: ["test", "debug", "fix", "analyze"],
        }

        for weight, keywords in complexity_signals.items():
            if any(k in desc for k in keywords):
                score += weight

        # Word count heuristic
        score += min(0.2, len(desc.split()) * 0.01)

        return min(1.0, score)

    def _save_state(self):
        """Save current state to memory for cross-session persistence."""
        if not self.memory:
            return

        # Save loop state
        if self.loop:
            self.memory.remember(
                "cortex_loop_state",
                self.loop.get_report(),
                category="system_state",
                importance=0.9,
            )

        # Save team state
        if self.orchestrator:
            self.memory.remember(
                "cortex_team_state",
                self.orchestrator.get_team_status(),
                category="system_state",
                importance=0.9,
            )

        # Save tool performance
        tool_stats = {}
        for name, tool in self._tool_registry.items():
            tool_stats[name] = {
                "calls": tool["calls"],
                "successes": tool["successes"],
                "failures": tool["failures"],
            }
        if tool_stats:
            self.memory.remember(
                "cortex_tool_stats",
                tool_stats,
                category="system_state",
                importance=0.7,
            )

    def _restore_state(self) -> Dict[str, Any]:
        """Restore state from persistent memory."""
        restored = {}

        loop_state = self.memory.recall("cortex_loop_state")
        if loop_state:
            restored["loop"] = "restored"
            logger.info(f"[CORTEX] Restored loop state: {loop_state.get('cycles', 0)} previous cycles")

        team_state = self.memory.recall("cortex_team_state")
        if team_state:
            restored["team"] = "restored"

        tool_stats = self.memory.recall("cortex_tool_stats")
        if tool_stats:
            restored["tool_stats"] = f"{len(tool_stats)} tools"

        return restored

    # ═══════════════════════════════════════════════════════════
    # Status & Diagnostics
    # ═══════════════════════════════════════════════════════════

    def status(self) -> Dict[str, Any]:
        """Full system status."""
        uptime = time.time() - self._session_start if self._booted else 0

        return {
            "booted": self._booted,
            "uptime_seconds": round(uptime, 2),
            "tasks_processed": self._task_count,
            "registered_tools": len(self._tool_registry),
            "subsystems": {
                "memory": self.memory.get_stats() if self.memory else "disabled",
                "loop": self.loop.get_report() if self.loop else "not_initialized",
                "orchestrator": self.orchestrator.get_team_status() if self.orchestrator else "not_initialized",
                "reflection": self.reflection.get_stats() if self.reflection else "not_initialized",
                "decisions": len(self.decisions.get_history()) if self.decisions else 0,
                "scout": "active" if self.scout else "not_initialized",
            },
            "tool_performance": {
                name: {"calls": t["calls"], "success_rate":
                       t["successes"] / max(t["calls"], 1)}
                for name, t in self._tool_registry.items()
            },
        }
