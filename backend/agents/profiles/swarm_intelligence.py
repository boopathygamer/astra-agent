"""
Multi-Agent Swarm Intelligence System
──────────────────────────────────────
A Conductor-driven swarm where multiple specialized agents collaborate
in parallel on a single complex task. The Conductor decomposes the task,
assigns it to specialist agents, coordinates parallel execution, and
merges results into a unified final output.

Agent Roles:
  🏗️ Architect  — Designs structure, plans approach
  💻 Coder      — Implements solutions, writes code
  🔍 Reviewer   — Audits quality, finds issues, suggests improvements
  🔬 Researcher — Gathers information from web, papers, social media
  🛡️ Security   — Analyzes security implications, finds vulnerabilities
  📊 Analyst    — Processes data, extracts insights, generates reports

The Conductor:
  - Decomposes complex tasks into role-specific sub-tasks
  - Runs agents in parallel using ThreadPoolExecutor
  - Resolves conflicts between agent outputs
  - Merges everything into a single coherent response
"""

import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

class AgentRole(Enum):
    ARCHITECT = "architect"
    CODER = "coder"
    REVIEWER = "reviewer"
    RESEARCHER = "researcher"
    SECURITY = "security"
    ANALYST = "analyst"
    DYNAMIC = "dynamic"  # For agent-forge-created roles


@dataclass
class SubTask:
    """A decomposed piece of the original task assigned to a specific agent."""
    sub_task_id: str = ""
    role: AgentRole = AgentRole.CODER
    description: str = ""
    context: str = ""
    priority: int = 1  # 1=highest
    depends_on: List[str] = field(default_factory=list)


@dataclass
class AgentResult:
    """Output from a single agent after processing its sub-task."""
    sub_task_id: str = ""
    role: AgentRole = AgentRole.CODER
    output: str = ""
    confidence: float = 0.0
    artifacts: List[str] = field(default_factory=list)  # code blocks, etc.
    warnings: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    success: bool = True
    error: str = ""


@dataclass
class SwarmResult:
    """Final merged output from the entire swarm."""
    task: str = ""
    merged_output: str = ""
    agent_results: List[AgentResult] = field(default_factory=list)
    agents_used: int = 0
    total_duration_ms: float = 0.0
    confidence: float = 0.0


# ──────────────────────────────────────────────
# Agent Role Prompts
# ──────────────────────────────────────────────

_ROLE_SYSTEM_PROMPTS = {
    AgentRole.ARCHITECT: (
        "You are a Senior Software Architect. Your role is to:\n"
        "1. Design the high-level structure and architecture\n"
        "2. Identify components, interfaces, and data flows\n"
        "3. Choose appropriate patterns and technologies\n"
        "4. Create clear specifications for implementation\n"
        "Be specific, use diagrams described in text, and justify every decision."
    ),
    AgentRole.CODER: (
        "You are a Senior Software Engineer. Your role is to:\n"
        "1. Write clean, production-ready code\n"
        "2. Follow best practices and design patterns\n"
        "3. Include error handling and edge cases\n"
        "4. Add clear comments and docstrings\n"
        "Output COMPLETE, RUNNABLE code. Never use placeholders or TODOs."
    ),
    AgentRole.REVIEWER: (
        "You are a Senior Code Reviewer and Quality Auditor. Your role is to:\n"
        "1. Find bugs, logic errors, and edge cases\n"
        "2. Check for performance bottlenecks\n"
        "3. Verify code quality and maintainability\n"
        "4. Suggest specific improvements with code examples\n"
        "Be constructive but thorough. List each issue with severity."
    ),
    AgentRole.RESEARCHER: (
        "You are a Deep Research Analyst. Your role is to:\n"
        "1. Gather the latest information on the topic\n"
        "2. Find best practices, tutorials, and expert opinions\n"
        "3. Compile relevant documentation and references\n"
        "4. Identify common pitfalls and solutions\n"
        "Cite sources when possible. Focus on practical, actionable information."
    ),
    AgentRole.SECURITY: (
        "You are a Cybersecurity Expert. Your role is to:\n"
        "1. Identify all security vulnerabilities (OWASP Top 10)\n"
        "2. Check for injection, XSS, CSRF, authentication issues\n"
        "3. Review data handling and encryption practices\n"
        "4. Provide specific remediation steps for each finding\n"
        "Rate each vulnerability: Critical/High/Medium/Low."
    ),
    AgentRole.ANALYST: (
        "You are a Data Analyst and Business Intelligence Expert. Your role is to:\n"
        "1. Analyze data patterns and extract insights\n"
        "2. Create structured reports with clear metrics\n"
        "3. Identify trends, anomalies, and opportunities\n"
        "4. Present findings with actionable recommendations\n"
        "Use tables and structured formats for clarity."
    ),
}


# ──────────────────────────────────────────────
# Task Decomposition Patterns
# ──────────────────────────────────────────────

# Keywords that map to specific agent roles
_ROLE_KEYWORDS = {
    AgentRole.ARCHITECT: [
        "design", "architecture", "structure", "plan", "system",
        "component", "interface", "api design", "schema", "blueprint",
    ],
    AgentRole.CODER: [
        "build", "create", "implement", "code", "write", "develop",
        "function", "class", "program", "script", "make",
    ],
    AgentRole.REVIEWER: [
        "review", "audit", "check", "improve", "optimize", "refactor",
        "quality", "fix bugs", "test", "validate",
    ],
    AgentRole.RESEARCHER: [
        "research", "find", "learn", "explore", "compare", "analyze",
        "best practices", "how does", "what is", "latest",
    ],
    AgentRole.SECURITY: [
        "security", "vulnerability", "hack", "protect", "encrypt",
        "authentication", "authorization", "pen test", "secure",
    ],
    AgentRole.ANALYST: [
        "data", "analyze", "report", "metrics", "dashboard",
        "statistics", "trend", "insight", "csv", "dataset",
    ],
}


# ──────────────────────────────────────────────
# Swarm Orchestrator (The Conductor)
# ──────────────────────────────────────────────

class SwarmOrchestrator:
    """
    The Conductor that orchestrates a swarm of specialized agents.
    
    Flow:
      1. Decompose → Split task into role-specific sub-tasks
      2. Dispatch → Run agents in parallel (ThreadPoolExecutor)
      3. Merge    → Combine all outputs into a coherent final response
    """

    def __init__(
        self,
        generate_fn: Callable,
        agent_controller=None,
        agent_forge=None,
        max_agents: int = 4,
        timeout_per_agent: int = 120,
    ):
        self.generate_fn = generate_fn
        self.agent = agent_controller
        self.agent_forge = agent_forge
        self.max_agents = max_agents
        self.timeout = timeout_per_agent

        # Dynamic roles created by Agent Forge
        self._dynamic_roles: Dict[str, Dict[str, Any]] = {}

        logger.info(f"🐝 SwarmOrchestrator initialized (max_agents={max_agents})")

    # ──────────────────────────────────────
    # Main Entry Point
    # ──────────────────────────────────────

    def execute(self, task: str, force_roles: List[AgentRole] = None) -> SwarmResult:
        """
        Execute a complex task using the agent swarm.
        
        Args:
            task: The complex task to solve
            force_roles: Optionally specify which agent roles to use
            
        Returns:
            SwarmResult with merged output from all agents
        """
        start = time.time()
        logger.info(f"🐝 SWARM ACTIVATED: {task[:80]}...")

        # Step 1: Decompose the task
        sub_tasks = self._decompose_task(task, force_roles)
        logger.info(f"🐝 Decomposed into {len(sub_tasks)} sub-tasks: "
                     f"{[st.role.value for st in sub_tasks]}")

        # Step 2: Execute agents in parallel
        agent_results = self._dispatch_parallel(sub_tasks, task)

        # Step 3: Merge results
        merged = self._merge_results(task, agent_results)

        # Build final result
        total_ms = (time.time() - start) * 1000
        avg_confidence = (
            sum(r.confidence for r in agent_results) / len(agent_results)
            if agent_results else 0.0
        )

        result = SwarmResult(
            task=task,
            merged_output=merged,
            agent_results=agent_results,
            agents_used=len(agent_results),
            total_duration_ms=total_ms,
            confidence=avg_confidence,
        )

        logger.info(
            f"🐝 SWARM COMPLETE: {len(agent_results)} agents, "
            f"{total_ms:.0f}ms, confidence={avg_confidence:.2f}"
        )
        return result

    # ──────────────────────────────────────
    # Task Decomposition
    # ──────────────────────────────────────

    def _decompose_task(
        self, task: str, force_roles: List[AgentRole] = None
    ) -> List[SubTask]:
        """
        Decompose a complex task into role-specific sub-tasks.
        Uses keyword matching + LLM-based decomposition.
        """
        if force_roles:
            roles = force_roles
        else:
            roles = self._detect_needed_roles(task)

        # Cap to max_agents
        roles = roles[:self.max_agents]

        # If no specific roles detected, use the power trio
        if not roles:
            roles = [AgentRole.RESEARCHER, AgentRole.CODER, AgentRole.REVIEWER]

        sub_tasks = []
        for i, role in enumerate(roles):
            sub_task = SubTask(
                sub_task_id=f"st_{uuid.uuid4().hex[:6]}",
                role=role,
                description=self._create_sub_task_prompt(task, role),
                priority=i + 1,
            )
            sub_tasks.append(sub_task)

        return sub_tasks

    def _detect_needed_roles(self, task: str) -> List[AgentRole]:
        """Detect which agent roles are needed based on task keywords."""
        task_lower = task.lower()
        role_scores: Dict[AgentRole, float] = {}

        for role, keywords in _ROLE_KEYWORDS.items():
            score = sum(1.0 for kw in keywords if kw in task_lower)
            if score > 0:
                role_scores[role] = score

        # Sort by relevance
        sorted_roles = sorted(role_scores.items(), key=lambda x: x[1], reverse=True)

        # Always include at least 2 agents for collaboration
        roles = [role for role, _ in sorted_roles]

        # For "build" type tasks, ensure full pipeline
        build_keywords = ["build", "create", "implement", "develop", "make"]
        if any(kw in task_lower for kw in build_keywords):
            essential = [AgentRole.ARCHITECT, AgentRole.CODER, AgentRole.REVIEWER]
            for r in essential:
                if r not in roles:
                    roles.append(r)

        return roles[:self.max_agents]

    def register_dynamic_role(
        self, name: str, system_prompt: str, keywords: List[str] = None
    ):
        """
        Register a dynamically forged agent role in the swarm.

        Args:
            name: Role identifier
            system_prompt: The agent's system prompt
            keywords: Keywords that trigger this role
        """
        self._dynamic_roles[name] = {
            "system_prompt": system_prompt,
            "keywords": keywords or [],
        }
        # Also register the system prompt so _run_single_agent can use it
        _ROLE_SYSTEM_PROMPTS[AgentRole.DYNAMIC] = system_prompt
        logger.info(f"🔨 Dynamic role '{name}' registered in swarm")

    def _create_sub_task_prompt(self, task: str, role: AgentRole) -> str:
        """Create a role-specific sub-task prompt."""
        role_descriptions = {
            AgentRole.ARCHITECT: (
                f"TASK: {task}\n\n"
                "As the ARCHITECT, provide:\n"
                "1. High-level design and component breakdown\n"
                "2. Technology recommendations with justification\n"
                "3. Interface definitions and data flow\n"
                "4. Project structure / file organization\n"
                "Be specific and practical. Other agents will implement your design."
            ),
            AgentRole.CODER: (
                f"TASK: {task}\n\n"
                "As the CODER, provide:\n"
                "1. Complete, production-ready implementation\n"
                "2. Clean code with error handling\n"
                "3. All necessary files with full content\n"
                "4. Usage examples\n"
                "Write COMPLETE code — no placeholders, no TODOs."
            ),
            AgentRole.REVIEWER: (
                f"TASK: {task}\n\n"
                "As the REVIEWER, analyze this task and provide:\n"
                "1. Potential issues and edge cases to watch for\n"
                "2. Quality checklist for the implementation\n"
                "3. Test cases that should be written\n"
                "4. Performance considerations\n"
                "Be specific about what could go wrong."
            ),
            AgentRole.RESEARCHER: (
                f"TASK: {task}\n\n"
                "As the RESEARCHER, provide:\n"
                "1. State-of-the-art approaches for this task\n"
                "2. Best practices from the industry\n"
                "3. Common pitfalls and how to avoid them\n"
                "4. Relevant tools, libraries, and resources\n"
                "Focus on practical, actionable intelligence."
            ),
            AgentRole.SECURITY: (
                f"TASK: {task}\n\n"
                "As the SECURITY EXPERT, provide:\n"
                "1. Security threat model for this task\n"
                "2. Potential vulnerabilities (OWASP, etc.)\n"
                "3. Security requirements and best practices\n"
                "4. Specific remediation recommendations\n"
                "Be thorough — rate each risk as Critical/High/Medium/Low."
            ),
            AgentRole.ANALYST: (
                f"TASK: {task}\n\n"
                "As the ANALYST, provide:\n"
                "1. Requirements analysis and scope breakdown\n"
                "2. Success metrics and KPIs\n"
                "3. Risk assessment with probability and impact\n"
                "4. Resource and time estimates\n"
                "Use structured tables and data-driven reasoning."
            ),
        }
        return role_descriptions.get(role, f"TASK: {task}")

    # ──────────────────────────────────────
    # Parallel Dispatch
    # ──────────────────────────────────────

    def _dispatch_parallel(
        self, sub_tasks: List[SubTask], original_task: str
    ) -> List[AgentResult]:
        """Execute all sub-tasks in parallel using ThreadPoolExecutor."""
        results: List[AgentResult] = []

        with ThreadPoolExecutor(max_workers=self.max_agents) as executor:
            future_to_subtask: Dict[Future, SubTask] = {}

            for st in sub_tasks:
                future = executor.submit(self._run_single_agent, st)
                future_to_subtask[future] = st

            for future in as_completed(future_to_subtask):
                st = future_to_subtask[future]
                try:
                    result = future.result(timeout=self.timeout)
                    results.append(result)
                    logger.info(
                        f"  ✅ {st.role.value} agent completed "
                        f"({result.duration_ms:.0f}ms)"
                    )
                except Exception as e:
                    logger.error(f"  ❌ {st.role.value} agent failed: {e}")
                    results.append(AgentResult(
                        sub_task_id=st.sub_task_id,
                        role=st.role,
                        output=f"Agent failed: {type(e).__name__}",
                        success=False,
                        error=str(e),
                    ))

        return results

    def _run_single_agent(self, sub_task: SubTask) -> AgentResult:
        """Run a single agent on its sub-task."""
        start = time.time()
        system_prompt = _ROLE_SYSTEM_PROMPTS.get(sub_task.role, "")

        try:
            result = self.generate_fn(
                prompt=sub_task.description,
                system_prompt=system_prompt,
                temperature=0.7,
            )

            output = getattr(result, 'answer', str(result))
            confidence = getattr(result, 'confidence', 0.7)

            # Extract code blocks as artifacts
            artifacts = []
            import re
            code_blocks = re.findall(r'```[\w]*\n(.*?)```', output, re.DOTALL)
            artifacts = [block.strip() for block in code_blocks if block.strip()]

            return AgentResult(
                sub_task_id=sub_task.sub_task_id,
                role=sub_task.role,
                output=output,
                confidence=confidence if isinstance(confidence, float) else 0.7,
                artifacts=artifacts,
                duration_ms=(time.time() - start) * 1000,
                success=True,
            )

        except Exception as e:
            return AgentResult(
                sub_task_id=sub_task.sub_task_id,
                role=sub_task.role,
                output="",
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )

    # ──────────────────────────────────────
    # Result Merging (The Conductor's Symphony)
    # ──────────────────────────────────────

    def _merge_results(self, task: str, results: List[AgentResult]) -> str:
        """
        Merge outputs from all agents into a single coherent response.
        Uses the LLM as the final conductor to synthesize everything.
        """
        if not results:
            return "No agents produced output."

        # If only one agent, return its output directly
        if len(results) == 1:
            return results[0].output

        # Build the conductor prompt
        agent_outputs = ""
        for r in results:
            if r.success and r.output:
                emoji = {
                    AgentRole.ARCHITECT: "🏗️",
                    AgentRole.CODER: "💻",
                    AgentRole.REVIEWER: "🔍",
                    AgentRole.RESEARCHER: "🔬",
                    AgentRole.SECURITY: "🛡️",
                    AgentRole.ANALYST: "📊",
                }.get(r.role, "🤖")

                agent_outputs += (
                    f"\n{'='*60}\n"
                    f"{emoji} {r.role.value.upper()} AGENT OUTPUT "
                    f"(confidence: {r.confidence:.0%})\n"
                    f"{'='*60}\n"
                    f"{r.output}\n"
                )

        conductor_prompt = (
            f"ORIGINAL TASK: {task}\n\n"
            f"The following specialized agents have each independently analyzed "
            f"this task from their expert perspective:\n"
            f"{agent_outputs}\n\n"
            f"As the CONDUCTOR, synthesize ALL agent outputs into a single, "
            f"comprehensive response:\n"
            f"1. Start with an Executive Summary of the combined approach\n"
            f"2. Integrate the Architect's design with the Coder's implementation\n"
            f"3. Apply the Reviewer's corrections and Security's recommendations\n"
            f"4. Include the Researcher's insights where relevant\n"
            f"5. Resolve any conflicts between agents (explain your reasoning)\n"
            f"6. Present the FINAL, unified solution\n\n"
            f"Be thorough but organized. Use clear section headers."
        )

        try:
            result = self.generate_fn(
                prompt=conductor_prompt,
                system_prompt=(
                    "You are the CONDUCTOR of a multi-agent swarm. "
                    "Your job is to synthesize multiple expert perspectives "
                    "into one unified, superior solution. Resolve conflicts, "
                    "apply quality checks, and produce a final output that is "
                    "better than any individual agent could have produced alone."
                ),
                temperature=0.5,
            )
            return getattr(result, 'answer', str(result))
        except Exception as e:
            logger.error(f"Conductor merge failed: {e}")
            # Fallback: concatenate results
            parts = []
            for r in results:
                if r.success:
                    parts.append(f"## {r.role.value.upper()} Agent\n{r.output}")
            return "\n\n---\n\n".join(parts)

    # ──────────────────────────────────────
    # Interactive CLI
    # ──────────────────────────────────────

    def start_interactive(self, task: str = None):
        """Run an interactive swarm session in the console."""
        print(f"\n{'='*60}")
        print("  🐝 MULTI-AGENT SWARM INTELLIGENCE")
        print("  Agents: Architect | Coder | Reviewer | Researcher | Security")
        print(f"{'='*60}\n")

        if not task:
            task = input("📋 Enter your complex task: ").strip()
            if not task:
                print("No task provided.")
                return

        print(f"\n🐝 Deploying swarm on: {task[:80]}...")
        print("   Decomposing task into sub-tasks...")

        result = self.execute(task)

        print(f"\n{'='*60}")
        print("  📊 SWARM RESULTS")
        print(f"{'='*60}")
        print(f"  Agents deployed: {result.agents_used}")
        print(f"  Total time: {result.total_duration_ms:.0f}ms")
        print(f"  Confidence: {result.confidence:.0%}")
        print(f"{'─'*60}")

        for ar in result.agent_results:
            emoji = "✅" if ar.success else "❌"
            print(f"  {emoji} {ar.role.value}: {ar.duration_ms:.0f}ms | "
                  f"confidence={ar.confidence:.0%}")

        print(f"{'='*60}")
        print("\n🎯 MERGED SOLUTION:\n")
        print(result.merged_output)

    # ──────────────────────────────────────
    # API-Compatible
    # ──────────────────────────────────────

    def api_execute(self, task: str, roles: List[str] = None) -> Dict[str, Any]:
        """API-compatible execution method."""
        force_roles = None
        if roles:
            force_roles = []
            for r in roles:
                try:
                    force_roles.append(AgentRole(r.lower()))
                except ValueError:
                    pass

        result = self.execute(task, force_roles=force_roles)

        return {
            "task": result.task,
            "merged_output": result.merged_output,
            "agents_used": result.agents_used,
            "total_duration_ms": result.total_duration_ms,
            "confidence": result.confidence,
            "agent_results": [
                {
                    "role": ar.role.value,
                    "output": ar.output[:2000],  # Cap for API
                    "confidence": ar.confidence,
                    "success": ar.success,
                    "duration_ms": ar.duration_ms,
                    "artifacts_count": len(ar.artifacts),
                }
                for ar in result.agent_results
            ],
        }
