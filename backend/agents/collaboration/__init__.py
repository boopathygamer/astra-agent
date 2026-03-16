"""
Multi-Agent Collaboration Framework
════════════════════════════════════
Enables agents to work together on complex tasks through
structured collaboration, delegation, consensus, and
shared context.

Capabilities:
  1. Team Formation     — Auto-assemble specialist teams
  2. Task Delegation    — Smart routing to best agent
  3. Consensus Engine   — Merge multi-agent outputs
  4. Shared Blackboard  — Inter-agent knowledge sharing
  5. Conflict Resolution — Handle disagreements
  6. Team Metrics       — Track collaboration effectiveness
"""

import hashlib
import logging
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class TeamRole(Enum):
    LEAD = "lead"
    SPECIALIST = "specialist"
    REVIEWER = "reviewer"
    OBSERVER = "observer"


class ConsensusStrategy(Enum):
    MAJORITY = "majority"        # Most common answer wins
    WEIGHTED = "weighted"        # Weighted by agent confidence
    HIERARCHICAL = "hierarchical"  # Lead agent decides
    SYNTHESIS = "synthesis"      # Merge all contributions


@dataclass
class TeamMember:
    agent_id: str = ""
    name: str = ""
    role: TeamRole = TeamRole.SPECIALIST
    capabilities: List[str] = field(default_factory=list)
    confidence: float = 0.8
    assigned_task: str = ""
    result: Any = None
    status: str = "idle"


@dataclass
class SharedBlackboard:
    """Shared knowledge space for a team."""
    entries: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def write(self, key: str, value: Any, author: str = ""):
        with self.lock:
            self.entries[key] = value
            self.history.append({
                "action": "write", "key": key,
                "author": author, "timestamp": time.time(),
            })

    def read(self, key: str) -> Any:
        return self.entries.get(key)

    def read_all(self) -> Dict[str, Any]:
        return dict(self.entries)


@dataclass
class CollaborationTask:
    """A task being worked on collaboratively."""
    task_id: str = ""
    description: str = ""
    domain: str = ""
    team_id: str = ""
    subtasks: Dict[str, str] = field(default_factory=dict)  # agent_id → subtask
    results: Dict[str, Any] = field(default_factory=dict)   # agent_id → result
    consensus_result: Any = None
    status: str = "pending"
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.task_id:
            self.task_id = hashlib.md5(
                f"{self.description[:50]}_{self.started_at}".encode()
            ).hexdigest()[:10]


@dataclass
class Team:
    """A collaboration team."""
    team_id: str = ""
    name: str = ""
    members: Dict[str, TeamMember] = field(default_factory=dict)
    lead_id: str = ""
    blackboard: SharedBlackboard = field(default_factory=SharedBlackboard)
    consensus_strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED
    tasks_completed: int = 0
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.team_id:
            self.team_id = f"team_{hashlib.md5(f'{self.name}_{self.created_at}'.encode()).hexdigest()[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "members": len(self.members),
            "lead": self.lead_id,
            "consensus": self.consensus_strategy.value,
            "tasks_completed": self.tasks_completed,
        }


class CollaborationFramework:
    """
    Multi-agent collaboration with team formation, delegation,
    consensus, shared blackboard, and conflict resolution.
    """

    MAX_TEAMS = 20
    MAX_TEAM_SIZE = 10

    def __init__(self, generate_fn: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self._teams: Dict[str, Team] = {}
        self._collab_history: Deque[Dict] = deque(maxlen=200)
        self._conflict_log: Deque[Dict] = deque(maxlen=100)
        logger.info("[COLLAB] Collaboration Framework initialized")

    # ── Team Formation ──

    def create_team(self, name: str, members: List[Dict[str, Any]],
                    lead_id: str = "",
                    consensus: ConsensusStrategy = ConsensusStrategy.WEIGHTED) -> Team:
        """Create a collaboration team."""
        team = Team(name=name, consensus_strategy=consensus)

        for m in members[:self.MAX_TEAM_SIZE]:
            member = TeamMember(
                agent_id=m.get("agent_id", ""),
                name=m.get("name", ""),
                role=TeamRole(m.get("role", "specialist")),
                capabilities=m.get("capabilities", []),
            )
            team.members[member.agent_id] = member
            if not lead_id and member.role == TeamRole.LEAD:
                lead_id = member.agent_id

        team.lead_id = lead_id or (list(team.members.keys())[0] if team.members else "")
        self._teams[team.team_id] = team
        logger.info(f"[COLLAB] Team created: '{name}' ({len(team.members)} members)")
        return team

    def auto_assemble_team(self, task_description: str,
                           available_agents: List[Dict]) -> Team:
        """Auto-assemble the best team for a task."""
        # Score each agent by relevance
        task_lower = task_description.lower()
        scored = []
        for agent in available_agents:
            score = 0
            caps = agent.get("capabilities", [])
            for cap in caps:
                if isinstance(cap, str) and cap.lower() in task_lower:
                    score += 2
            if agent.get("reliability", 0) > 0.8:
                score += 1
            scored.append((agent, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_agents = [a for a, s in scored[:5] if s > 0]

        if not top_agents:
            top_agents = [a for a, _ in scored[:3]]

        # Assign roles
        members = []
        for i, agent in enumerate(top_agents):
            role = "lead" if i == 0 else ("reviewer" if i == len(top_agents) - 1 else "specialist")
            members.append({**agent, "role": role})

        return self.create_team(
            name=f"Auto-team: {task_description[:30]}",
            members=members,
        )

    # ── Delegation ──

    def delegate_task(self, team_id: str, task_description: str,
                      subtask_split: Dict[str, str] = None) -> CollaborationTask:
        """Delegate a task across team members."""
        team = self._teams.get(team_id)
        if not team:
            raise ValueError(f"Team not found: {team_id}")

        task = CollaborationTask(
            description=task_description,
            team_id=team_id,
        )

        if subtask_split:
            task.subtasks = subtask_split
        else:
            # Auto-split: give everyone the full task
            for agent_id in team.members:
                task.subtasks[agent_id] = task_description

        task.status = "delegated"
        return task

    def execute_collaboration(self, team_id: str, task: CollaborationTask,
                               agent_executor: Optional[Callable] = None) -> CollaborationTask:
        """Execute a collaborative task across the team."""
        team = self._teams.get(team_id)
        if not team:
            raise ValueError(f"Team not found: {team_id}")

        task.status = "executing"

        # Each member works on their subtask
        for agent_id, subtask in task.subtasks.items():
            member = team.members.get(agent_id)
            if not member:
                continue

            member.status = "working"
            try:
                if agent_executor:
                    result = agent_executor(subtask, agent_id)
                elif self.generate_fn:
                    prompt = (
                        f"You are agent '{member.name}' ({member.role.value}).\n"
                        f"Task: {subtask}\n"
                        f"Shared context: {team.blackboard.read_all()}\n"
                        f"Provide your contribution."
                    )
                    result = self.generate_fn(prompt)
                else:
                    result = f"Agent {agent_id} completed: {subtask[:50]}"

                member.result = result
                member.status = "done"
                task.results[agent_id] = result

                # Write to shared blackboard
                team.blackboard.write(
                    f"result_{agent_id}", result, author=agent_id,
                )
            except Exception as e:
                member.status = "failed"
                task.results[agent_id] = f"ERROR: {e}"

        # Run consensus
        task.consensus_result = self._build_consensus(
            team, task.results,
        )
        task.status = "completed"
        task.completed_at = time.time()
        team.tasks_completed += 1

        self._collab_history.append({
            "team_id": team_id,
            "task_id": task.task_id,
            "members": len(task.subtasks),
            "consensus_strategy": team.consensus_strategy.value,
            "timestamp": time.time(),
        })

        return task

    # ── Consensus ──

    def _build_consensus(self, team: Team, results: Dict[str, Any]) -> Any:
        """Build consensus from multiple agent results."""
        strategy = team.consensus_strategy

        if not results:
            return "No results to synthesize"

        if strategy == ConsensusStrategy.HIERARCHICAL:
            # Lead's result wins
            if team.lead_id in results:
                return results[team.lead_id]
            return list(results.values())[0]

        elif strategy == ConsensusStrategy.MAJORITY:
            # Most common result (simplified: longest common substring)
            return max(results.values(), key=lambda r: len(str(r)))

        elif strategy == ConsensusStrategy.WEIGHTED:
            # Weight by member confidence
            if self.generate_fn:
                all_results = "\n".join(
                    f"- [{team.members.get(aid, TeamMember()).name}]: {str(r)[:200]}"
                    for aid, r in results.items()
                )
                try:
                    return self.generate_fn(
                        f"Synthesize these team contributions into one cohesive answer:\n{all_results}"
                    )
                except Exception:
                    pass
            return " | ".join(str(r)[:100] for r in results.values())

        elif strategy == ConsensusStrategy.SYNTHESIS:
            # Full synthesis
            parts = [str(r) for r in results.values()]
            return " ".join(parts)

        return list(results.values())[0]

    # ── Conflict Resolution ──

    def detect_conflicts(self, results: Dict[str, Any]) -> List[Dict]:
        """Detect conflicting results between agents."""
        conflicts = []
        agents = list(results.keys())
        for i, a1 in enumerate(agents):
            for a2 in agents[i+1:]:
                r1, r2 = str(results[a1]).lower(), str(results[a2]).lower()
                # Simple conflict detection: contradictory statements
                if ("yes" in r1 and "no" in r2) or ("no" in r1 and "yes" in r2):
                    conflicts.append({
                        "agent_a": a1, "agent_b": a2,
                        "type": "contradiction",
                        "a_says": results[a1][:100],
                        "b_says": results[a2][:100],
                    })
                elif len(r1) > 10 and len(r2) > 10:
                    # Check for opposing sentiment keywords
                    pos = {"good", "correct", "agree", "yes", "true", "should"}
                    neg = {"bad", "wrong", "disagree", "no", "false", "shouldn't"}
                    w1, w2 = set(r1.split()), set(r2.split())
                    if (w1 & pos and w2 & neg) or (w1 & neg and w2 & pos):
                        conflicts.append({
                            "agent_a": a1, "agent_b": a2,
                            "type": "sentiment_clash",
                        })

        if conflicts:
            self._conflict_log.extend(conflicts)
        return conflicts

    # ── Status ──

    def get_teams(self) -> List[Dict]:
        return [t.to_dict() for t in self._teams.values()]

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_teams": len(self._teams),
            "total_collaborations": len(self._collab_history),
            "conflicts_detected": len(self._conflict_log),
            "teams": self.get_teams(),
        }
