"""
Swarm Intelligence Mesh — Emergent Micro-Agent Collective
═════════════════════════════════════════════════════════
Instead of 1 monolithic brain, decompose complex tasks into thousands
of micro-agents that exhibit emergent intelligence through simple local
rules — like ant colonies finding optimal paths.

Architecture:
  Task → Decomposer → Micro-Agent Swarm → Pheromone Trails → Emergence
              ↓                ↓                  ↓              ↓
        Sub-problems    Local Rules        Reinforcement    Global Solution
"""

import hashlib
import logging
import math
import secrets
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SwarmBehavior(Enum):
    EXPLORE = "explore"
    EXPLOIT = "exploit"
    SIGNAL = "signal"
    FOLLOW = "follow"
    IDLE = "idle"


@dataclass
class MicroAgent:
    """A single micro-agent with simple local rules."""
    agent_id: str = ""
    position: Tuple[float, float] = (0.0, 0.0)
    behavior: SwarmBehavior = SwarmBehavior.EXPLORE
    energy: float = 1.0
    carrying: Optional[str] = None     # Solution fragment
    confidence: float = 0.0
    steps_taken: int = 0

    def __post_init__(self):
        if not self.agent_id:
            self.agent_id = secrets.token_hex(3)

    def step(self, pheromone_at_pos: float) -> SwarmBehavior:
        """Decide next behavior based on local pheromone concentration."""
        self.steps_taken += 1
        self.energy = max(0.0, self.energy - 0.01)

        if self.energy < 0.1:
            self.behavior = SwarmBehavior.IDLE
        elif pheromone_at_pos > 0.7:
            self.behavior = SwarmBehavior.EXPLOIT
        elif pheromone_at_pos > 0.3:
            self.behavior = SwarmBehavior.FOLLOW
        elif self.carrying:
            self.behavior = SwarmBehavior.SIGNAL
        else:
            self.behavior = SwarmBehavior.EXPLORE

        return self.behavior


@dataclass
class PheromoneTrail:
    """Pheromone deposited by agents to signal solution quality."""
    trail_id: str = ""
    path_key: str = ""
    intensity: float = 0.0
    deposited_by: str = ""
    created_at: float = field(default_factory=time.time)
    evaporation_rate: float = 0.05

    def evaporate(self) -> float:
        old = self.intensity
        self.intensity = max(0.0, self.intensity - self.evaporation_rate)
        return old - self.intensity

    def reinforce(self, amount: float) -> None:
        self.intensity = min(1.0, self.intensity + amount)


@dataclass
class SwarmSolution:
    """Emergent solution from the swarm."""
    fragments: List[str] = field(default_factory=list)
    confidence: float = 0.0
    contributing_agents: int = 0
    iterations: int = 0
    emergence_detected: bool = False
    convergence_score: float = 0.0

    def summary(self) -> str:
        return (
            f"Swarm: {self.contributing_agents} agents | "
            f"{self.iterations} iters | "
            f"Convergence={self.convergence_score:.2f} | "
            f"Emerged={self.emergence_detected}"
        )


class SwarmIntelligenceMesh:
    """
    Emergent intelligence through micro-agent collective behavior.

    Usage:
        swarm = SwarmIntelligenceMesh(num_agents=100)
        solution = swarm.solve("Optimize database query performance",
                               solve_fn=lambda sub: f"Solution for: {sub}")
        print(solution.summary())
    """

    CONVERGENCE_THRESHOLD = 0.8
    MAX_ITERATIONS = 50
    EVAPORATION_CYCLE = 5

    def __init__(self, num_agents: int = 50):
        self._agents: List[MicroAgent] = [
            MicroAgent(
                position=(
                    (secrets.randbelow(100) - 50) / 50.0,
                    (secrets.randbelow(100) - 50) / 50.0,
                ),
                energy=0.5 + secrets.randbelow(50) / 100.0,
            )
            for _ in range(num_agents)
        ]
        self._pheromones: Dict[str, PheromoneTrail] = {}
        self._solutions: List[SwarmSolution] = []
        self._total_solves: int = 0

    def solve(
        self,
        problem: str,
        solve_fn: Optional[Callable[[str], str]] = None,
        max_iterations: Optional[int] = None,
    ) -> SwarmSolution:
        """Deploy the swarm to solve a problem through emergence."""
        self._total_solves += 1
        max_iter = max_iterations or self.MAX_ITERATIONS

        # Decompose into sub-problems
        sub_problems = self._decompose(problem)
        solution_fragments: Dict[str, str] = {}
        fragment_confidence: Dict[str, float] = defaultdict(float)

        for iteration in range(max_iter):
            # Each agent takes a step
            for agent in self._agents:
                if agent.behavior == SwarmBehavior.IDLE:
                    continue

                # Get pheromone at position
                pos_key = f"{int(agent.position[0]*10)},{int(agent.position[1]*10)}"
                trail = self._pheromones.get(pos_key)
                pheromone = trail.intensity if trail else 0.0

                behavior = agent.step(pheromone)

                if behavior == SwarmBehavior.EXPLORE:
                    # Try to solve a random sub-problem
                    if sub_problems:
                        idx = secrets.randbelow(len(sub_problems))
                        sub = sub_problems[idx]
                        if solve_fn:
                            result = solve_fn(sub)
                            agent.carrying = result
                            agent.confidence = 0.5 + secrets.randbelow(50) / 100.0

                elif behavior == SwarmBehavior.SIGNAL:
                    # Deposit pheromone for good solutions
                    if agent.carrying and agent.confidence > 0.4:
                        self._deposit_pheromone(pos_key, agent)
                        key = hashlib.md5(agent.carrying.encode()).hexdigest()[:8]
                        solution_fragments[key] = agent.carrying
                        fragment_confidence[key] += agent.confidence

                elif behavior == SwarmBehavior.EXPLOIT:
                    # Refine existing solution at this position
                    if trail and agent.carrying:
                        trail.reinforce(0.1)
                        agent.confidence = min(1.0, agent.confidence + 0.05)

            # Evaporate pheromones periodically
            if iteration % self.EVAPORATION_CYCLE == 0:
                for trail in self._pheromones.values():
                    trail.evaporate()

            # Check convergence
            convergence = self._check_convergence(fragment_confidence)
            if convergence >= self.CONVERGENCE_THRESHOLD:
                break

        # Assemble final solution
        sorted_frags = sorted(
            fragment_confidence.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        final_fragments = [
            solution_fragments[k]
            for k, _ in sorted_frags
            if k in solution_fragments
        ]

        active_agents = sum(1 for a in self._agents if a.behavior != SwarmBehavior.IDLE)
        convergence = self._check_convergence(fragment_confidence)

        solution = SwarmSolution(
            fragments=final_fragments[:10],
            confidence=convergence,
            contributing_agents=active_agents,
            iterations=iteration + 1,
            emergence_detected=convergence >= self.CONVERGENCE_THRESHOLD,
            convergence_score=convergence,
        )

        self._solutions.append(solution)
        logger.info(solution.summary())
        return solution

    def get_stats(self) -> Dict[str, Any]:
        active = sum(1 for a in self._agents if a.behavior != SwarmBehavior.IDLE)
        return {
            "total_agents": len(self._agents),
            "active_agents": active,
            "total_pheromones": len(self._pheromones),
            "total_solves": self._total_solves,
            "avg_convergence": round(
                sum(s.convergence_score for s in self._solutions) /
                max(len(self._solutions), 1), 3
            ),
        }

    def _decompose(self, problem: str) -> List[str]:
        """Decompose a problem into sub-problems."""
        words = problem.split()
        if len(words) <= 5:
            return [problem]
        chunk_size = max(3, len(words) // 4)
        return [
            " ".join(words[i:i + chunk_size])
            for i in range(0, len(words), chunk_size)
        ]

    def _deposit_pheromone(self, pos_key: str, agent: MicroAgent) -> None:
        if pos_key not in self._pheromones:
            self._pheromones[pos_key] = PheromoneTrail(
                trail_id=secrets.token_hex(3),
                path_key=pos_key,
                deposited_by=agent.agent_id,
            )
        self._pheromones[pos_key].reinforce(agent.confidence * 0.2)

    def _check_convergence(self, confidences: Dict[str, float]) -> float:
        if not confidences:
            return 0.0
        values = list(confidences.values())
        max_conf = max(values)
        total = sum(values)
        return max_conf / max(total, 1e-9)
