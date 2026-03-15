"""
Multi-Agent Orchestrator — Specialized Agent Collaboration System.
==================================================================
Spawns role-based agents (Researcher, Coder, Reviewer, Tester, Deployer)
that collaborate on complex goals. Each agent has domain expertise,
and the orchestrator manages communication and conflict resolution.

Classes:
  AgentRole      — Role definition with capabilities
  SpecializedAgent — An agent instance with role-specific behavior
  AgentOrchestrator — The collaboration manager
"""

import asyncio
import logging
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RoleType(Enum):
    RESEARCHER = "researcher"
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    TESTER = "tester"
    DEPLOYER = "deployer"
    SECURITY = "security"
    ARCHITECT = "architect"


@dataclass
class AgentMessage:
    """Inter-agent communication message."""
    id: str = ""
    sender: str = ""
    recipient: str = ""  # "" = broadcast
    content: str = ""
    msg_type: str = "info"  # info, request, response, alert, vote
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"msg_{secrets.token_hex(4)}"


@dataclass
class AgentVote:
    """An agent's vote on a decision."""
    agent_id: str = ""
    decision: str = ""
    confidence: float = 0.5
    reasoning: str = ""


@dataclass
class AgentRole:
    """Definition of an agent role with capabilities."""
    role_type: RoleType = RoleType.CODER
    name: str = ""
    expertise: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    priority_bias: float = 0.5  # 0=speed, 1=quality
    risk_tolerance: float = 0.3

    @staticmethod
    def get_preset(role: RoleType) -> "AgentRole":
        presets = {
            RoleType.RESEARCHER: AgentRole(
                role_type=RoleType.RESEARCHER, name="Researcher",
                expertise=["analysis", "documentation", "patterns", "research"],
                tools=["web_search", "file_read", "code_analyzer", "doc_reader"],
                priority_bias=0.7, risk_tolerance=0.2,
            ),
            RoleType.PLANNER: AgentRole(
                role_type=RoleType.PLANNER, name="Planner",
                expertise=["architecture", "design", "decomposition", "estimation"],
                tools=["code_analyzer", "file_read", "db_design_schema"],
                priority_bias=0.9, risk_tolerance=0.1,
            ),
            RoleType.CODER: AgentRole(
                role_type=RoleType.CODER, name="Coder",
                expertise=["implementation", "algorithms", "optimization", "debugging"],
                tools=["file_write", "code_executor", "web_scaffold_project",
                       "web_generate_component", "db_generate_model"],
                priority_bias=0.5, risk_tolerance=0.4,
            ),
            RoleType.REVIEWER: AgentRole(
                role_type=RoleType.REVIEWER, name="Reviewer",
                expertise=["code_review", "best_practices", "security", "performance"],
                tools=["code_analyzer", "lint_code", "file_read"],
                priority_bias=0.9, risk_tolerance=0.1,
            ),
            RoleType.TESTER: AgentRole(
                role_type=RoleType.TESTER, name="Tester",
                expertise=["testing", "edge_cases", "validation", "regression"],
                tools=["generate_tests", "code_executor", "api_test"],
                priority_bias=0.8, risk_tolerance=0.2,
            ),
            RoleType.DEPLOYER: AgentRole(
                role_type=RoleType.DEPLOYER, name="Deployer",
                expertise=["deployment", "ci_cd", "monitoring", "infrastructure"],
                tools=["git_commit", "git_branch", "web_deploy_config", "web_bundle_project"],
                priority_bias=0.6, risk_tolerance=0.2,
            ),
            RoleType.SECURITY: AgentRole(
                role_type=RoleType.SECURITY, name="Security",
                expertise=["vulnerability", "encryption", "authentication", "threat_modeling"],
                tools=["threat_full_scan", "scan_dependencies", "code_analyzer"],
                priority_bias=1.0, risk_tolerance=0.0,
            ),
            RoleType.ARCHITECT: AgentRole(
                role_type=RoleType.ARCHITECT, name="Architect",
                expertise=["system_design", "scalability", "patterns", "trade_offs"],
                tools=["code_analyzer", "db_design_schema", "web_scaffold_project"],
                priority_bias=0.9, risk_tolerance=0.2,
            ),
        }
        return presets.get(role, presets[RoleType.CODER])


@dataclass
class SpecializedAgent:
    """An agent instance with role-specific behavior and memory."""
    id: str = ""
    role: AgentRole = field(default_factory=AgentRole)
    status: str = "idle"  # idle, working, reviewing, waiting
    current_task: Optional[str] = None
    inbox: deque = field(default_factory=lambda: deque(maxlen=100))
    outbox: deque = field(default_factory=lambda: deque(maxlen=100))
    memory: List[Dict] = field(default_factory=list)
    tasks_completed: int = 0
    tasks_failed: int = 0
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.id:
            self.id = f"agent_{self.role.role_type.value}_{secrets.token_hex(3)}"

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 1.0

    def can_handle(self, task_description: str) -> float:
        """Score how well this agent can handle a task (0-1)."""
        desc_lower = task_description.lower()
        score = 0.0
        for expertise in self.role.expertise:
            if expertise in desc_lower:
                score += 0.25
        return min(1.0, score + 0.1)  # Base 0.1 for any agent

    def receive_message(self, msg: AgentMessage):
        self.inbox.append(msg)

    def send_message(self, content: str, recipient: str = "",
                     msg_type: str = "info") -> AgentMessage:
        msg = AgentMessage(sender=self.id, recipient=recipient,
                           content=content, msg_type=msg_type)
        self.outbox.append(msg)
        return msg

    def remember(self, key: str, value: Any):
        self.memory.append({"key": key, "value": value, "time": time.time()})

    def recall(self, key: str) -> Optional[Any]:
        for entry in reversed(self.memory):
            if entry["key"] == key:
                return entry["value"]
        return None

    async def execute_task(self, task: Dict, tool_executor: Callable = None) -> Dict:
        """Execute a task using role-appropriate tools."""
        self.status = "working"
        self.current_task = task.get("description", "")

        try:
            if tool_executor and task.get("tool_name"):
                result = await asyncio.to_thread(
                    tool_executor, task["tool_name"], task.get("tool_args", {})
                )
            else:
                result = {
                    "success": True,
                    "agent": self.id,
                    "role": self.role.name,
                    "task": task.get("description"),
                    "output": f"[{self.role.name}] Completed: {task.get('description', '')}",
                }

            self.tasks_completed += 1
            self.confidence = min(1.0, self.confidence + 0.02)
            self.remember("last_success", task.get("description"))

        except Exception as e:
            result = {"success": False, "error": str(e), "agent": self.id}
            self.tasks_failed += 1
            self.confidence = max(0.1, self.confidence - 0.05)

        self.status = "idle"
        self.current_task = None
        return result


class AgentOrchestrator:
    """
    Manages a team of specialized agents working on shared goals.

    Workflow:
      1. Receive a complex task
      2. Assign to the best-suited agent(s)
      3. Coordinate inter-agent communication
      4. Resolve conflicts via consensus voting
      5. Aggregate results and report

    Usage:
        orch = AgentOrchestrator()
        orch.spawn_team()
        result = await orch.execute_pipeline("Build a REST API")
    """

    def __init__(self, tool_executor: Callable = None):
        self.tool_executor = tool_executor
        self.agents: Dict[str, SpecializedAgent] = {}
        self.message_bus: deque = deque(maxlen=1000)
        self.pipeline_history: List[Dict] = []

    def spawn_agent(self, role: RoleType) -> SpecializedAgent:
        """Spawn a new specialized agent."""
        agent_role = AgentRole.get_preset(role)
        agent = SpecializedAgent(role=agent_role)
        self.agents[agent.id] = agent
        logger.info(f"[ORCH] Spawned {role.value} agent: {agent.id}")
        return agent

    def spawn_team(self, roles: List[RoleType] = None) -> List[SpecializedAgent]:
        """Spawn a complete team of agents."""
        if roles is None:
            roles = [RoleType.RESEARCHER, RoleType.PLANNER, RoleType.CODER,
                     RoleType.REVIEWER, RoleType.TESTER, RoleType.DEPLOYER]
        return [self.spawn_agent(role) for role in roles]

    def find_best_agent(self, task_description: str) -> Optional[SpecializedAgent]:
        """Find the best agent for a task based on expertise matching."""
        if not self.agents:
            return None
        scored = [
            (agent, agent.can_handle(task_description) * agent.success_rate)
            for agent in self.agents.values()
            if agent.status == "idle"
        ]
        if not scored:
            # All busy, return the one with highest capability
            scored = [
                (agent, agent.can_handle(task_description))
                for agent in self.agents.values()
            ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0] if scored else None

    def broadcast(self, content: str, msg_type: str = "info", sender: str = "orchestrator"):
        """Send a message to all agents."""
        msg = AgentMessage(sender=sender, content=content, msg_type=msg_type)
        self.message_bus.append(msg)
        for agent in self.agents.values():
            agent.receive_message(msg)

    async def request_consensus(self, question: str, options: List[str]) -> Dict[str, Any]:
        """Ask all agents to vote on a decision."""
        votes: List[AgentVote] = []

        for agent in self.agents.values():
            # Each agent votes based on their role bias
            best_idx = 0
            best_score = 0.0
            for i, option in enumerate(options):
                score = agent.can_handle(option) + agent.role.priority_bias * 0.3
                if score > best_score:
                    best_score = score
                    best_idx = i

            votes.append(AgentVote(
                agent_id=agent.id,
                decision=options[best_idx],
                confidence=agent.confidence,
                reasoning=f"[{agent.role.name}] Best match for my expertise",
            ))

        # Weighted voting (confidence-weighted)
        vote_counts: Dict[str, float] = {}
        for vote in votes:
            vote_counts[vote.decision] = vote_counts.get(vote.decision, 0) + vote.confidence

        winner = max(vote_counts, key=vote_counts.get)
        total_weight = sum(vote_counts.values())

        return {
            "question": question,
            "winner": winner,
            "winning_weight": vote_counts[winner],
            "consensus_strength": vote_counts[winner] / total_weight if total_weight > 0 else 0,
            "votes": [{"agent": v.agent_id, "decision": v.decision,
                       "confidence": v.confidence} for v in votes],
        }

    async def execute_pipeline(self, task_description: str) -> Dict[str, Any]:
        """Execute a full pipeline: Research -> Plan -> Code -> Review -> Test -> Deploy."""
        if not self.agents:
            self.spawn_team()

        pipeline_start = time.time()
        results = []
        pipeline = [
            {"phase": "Research", "role": RoleType.RESEARCHER,
             "description": f"Research: {task_description}"},
            {"phase": "Planning", "role": RoleType.PLANNER,
             "description": f"Plan implementation: {task_description}"},
            {"phase": "Implementation", "role": RoleType.CODER,
             "description": f"Implement: {task_description}"},
            {"phase": "Review", "role": RoleType.REVIEWER,
             "description": f"Review code for: {task_description}"},
            {"phase": "Testing", "role": RoleType.TESTER,
             "description": f"Test implementation: {task_description}"},
            {"phase": "Deployment", "role": RoleType.DEPLOYER,
             "description": f"Deploy: {task_description}"},
        ]

        for step in pipeline:
            agent = self._find_agent_by_role(step["role"])
            if not agent:
                agent = self.find_best_agent(step["description"])
            if not agent:
                results.append({"phase": step["phase"], "success": False, "error": "No agent available"})
                continue

            self.broadcast(f"Phase '{step['phase']}' starting — assigned to {agent.role.name}",
                          sender="orchestrator")

            result = await agent.execute_task(
                {"description": step["description"], "tool_name": None, "tool_args": {}},
                self.tool_executor
            )
            result["phase"] = step["phase"]
            result["agent_role"] = agent.role.name
            results.append(result)

            # If a critical phase fails, stop pipeline
            if not result.get("success") and step["phase"] in ("Implementation", "Testing"):
                self.broadcast(f"Pipeline halted: {step['phase']} failed", msg_type="alert")
                break

        elapsed = time.time() - pipeline_start
        report = {
            "task": task_description,
            "phases_completed": sum(1 for r in results if r.get("success")),
            "phases_total": len(pipeline),
            "phases": results,
            "elapsed_seconds": round(elapsed, 3),
            "success": all(r.get("success") for r in results),
            "team_size": len(self.agents),
        }
        self.pipeline_history.append(report)
        return report

    def _find_agent_by_role(self, role: RoleType) -> Optional[SpecializedAgent]:
        for agent in self.agents.values():
            if agent.role.role_type == role:
                return agent
        return None

    def get_team_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            "total_agents": len(self.agents),
            "agents": [
                {
                    "id": a.id,
                    "role": a.role.name,
                    "status": a.status,
                    "tasks_completed": a.tasks_completed,
                    "success_rate": round(a.success_rate, 2),
                    "confidence": round(a.confidence, 2),
                    "current_task": a.current_task,
                }
                for a in self.agents.values()
            ],
            "message_bus_size": len(self.message_bus),
            "pipelines_run": len(self.pipeline_history),
        }
