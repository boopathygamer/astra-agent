"""
Swarm Intelligence Engine — Parallel Micro-Agent Reasoning
═══════════════════════════════════════════════════════════
Spawns many micro-agents with varied strategies that independently attack a problem.
Uses ant colony optimization with pheromone trails for solution convergence.

No LLM, no GPU — pure swarm algorithms.
"""

import hashlib
import logging
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SwarmRole(Enum):
    EXPLORER = "explorer"       # Explores new solution space
    EXPLOITER = "exploiter"     # Deepens best-known solutions
    SCOUT = "scout"             # Random walks for diversity
    CRITIC = "critic"           # Evaluates and scores solutions
    COMBINER = "combiner"       # Merges partial solutions


@dataclass
class MicroAgent:
    agent_id: int
    role: SwarmRole
    position: List[float] = field(default_factory=list)
    solution: str = ""
    fitness: float = 0.0
    steps_taken: int = 0

    @property
    def id(self) -> str:
        return f"agent_{self.agent_id}_{self.role.value}"


@dataclass
class PheromoneTrail:
    path: str
    strength: float = 1.0
    deposited_by: int = 0
    timestamp: float = 0.0


@dataclass
class SwarmSolution:
    solution: str
    fitness: float
    contributors: List[int] = field(default_factory=list)
    path: List[str] = field(default_factory=list)


@dataclass
class SwarmResult:
    best_solution: str = ""
    best_fitness: float = 0.0
    solutions_found: int = 0
    agents_used: int = 0
    iterations: int = 0
    convergence_history: List[float] = field(default_factory=list)
    all_solutions: List[SwarmSolution] = field(default_factory=list)
    duration_ms: float = 0.0

    def summary(self) -> str:
        lines = [
            f"## Swarm Intelligence Result",
            f"**Best Fitness**: {self.best_fitness:.4f}",
            f"**Solutions Found**: {self.solutions_found}",
            f"**Agents Used**: {self.agents_used}",
            f"**Iterations**: {self.iterations}",
        ]
        if self.convergence_history:
            lines.append(f"**Convergence**: {self.convergence_history[0]:.4f} -> {self.convergence_history[-1]:.4f}")
        if self.best_solution:
            lines.append(f"\n**Best Solution**: {self.best_solution[:200]}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# PHEROMONE SYSTEM
# ═══════════════════════════════════════════════════════════

class PheromoneSystem:
    """Ant Colony style pheromone trail management."""

    def __init__(self, evaporation_rate: float = 0.1):
        self.trails: Dict[str, PheromoneTrail] = {}
        self.evaporation_rate = evaporation_rate

    def deposit(self, path: str, strength: float, agent_id: int) -> None:
        if path in self.trails:
            self.trails[path].strength += strength
            self.trails[path].deposited_by += 1
        else:
            self.trails[path] = PheromoneTrail(path=path, strength=strength, deposited_by=1, timestamp=time.time())

    def get_strength(self, path: str) -> float:
        return self.trails.get(path, PheromoneTrail(path="")).strength

    def evaporate(self) -> None:
        expired = []
        for path, trail in self.trails.items():
            trail.strength *= (1 - self.evaporation_rate)
            if trail.strength < 0.01:
                expired.append(path)
        for path in expired:
            del self.trails[path]

    def best_trails(self, top_k: int = 5) -> List[Tuple[str, float]]:
        ranked = sorted(self.trails.items(), key=lambda x: -x[1].strength)
        return [(path, trail.strength) for path, trail in ranked[:top_k]]


# ═══════════════════════════════════════════════════════════
# PROBLEM DECOMPOSER
# ═══════════════════════════════════════════════════════════

class ProblemDecomposer:
    """Decomposes problems into sub-problems for swarm agents."""

    @staticmethod
    def decompose(problem: str) -> List[str]:
        """Break a problem into sub-components."""
        sentences = [s.strip() for s in problem.replace('?', '.').replace('!', '.').split('.') if s.strip()]
        if len(sentences) <= 1:
            words = problem.split()
            if len(words) > 6:
                mid = len(words) // 2
                return [" ".join(words[:mid]), " ".join(words[mid:])]
            return [problem]
        return sentences

    @staticmethod
    def evaluate_solution(solution: str, problem: str) -> float:
        """Heuristic fitness evaluation."""
        if not solution:
            return 0.0
        problem_words = set(problem.lower().split())
        solution_words = set(solution.lower().split())
        overlap = len(problem_words & solution_words)
        coverage = overlap / max(len(problem_words), 1)
        length_score = min(1.0, len(solution) / max(len(problem), 1))
        diversity = len(solution_words - problem_words) / max(len(solution_words), 1)
        return 0.4 * coverage + 0.3 * length_score + 0.3 * diversity


# ═══════════════════════════════════════════════════════════
# SOLUTION STRATEGIES
# ═══════════════════════════════════════════════════════════

class SwarmStrategies:

    @staticmethod
    def explore(problem: str, sub_problem: str) -> str:
        """Explorer: creative, broad search."""
        approaches = [
            "Decompose into smaller sub-problems and solve recursively",
            "Apply divide-and-conquer: split, solve halves, merge",
            "Use dynamic programming with memoization",
            "Transform to a graph problem and apply BFS/DFS",
            "Apply mathematical modeling and optimization",
            "Use constraint satisfaction and backtracking",
            "Apply pattern matching against known solutions",
            "Use probabilistic reasoning with confidence bounds",
        ]
        idx = hash(sub_problem) % len(approaches)
        return f"Explore({sub_problem[:40]}): {approaches[idx]}"

    @staticmethod
    def exploit(problem: str, best_so_far: str) -> str:
        """Exploiter: refine best-known solution."""
        if not best_so_far:
            return SwarmStrategies.explore(problem, problem)
        refinements = [
            f"Optimize: {best_so_far[:50]} — reduce complexity",
            f"Strengthen: {best_so_far[:50]} — add edge case handling",
            f"Validate: {best_so_far[:50]} — verify correctness",
        ]
        return refinements[hash(best_so_far) % len(refinements)]

    @staticmethod
    def scout(problem: str) -> str:
        """Scout: random creative leap."""
        wild_ideas = [
            "What if we invert the problem entirely?",
            "Consider the dual/complement problem",
            "Apply analogy from biology/physics/economics",
            "Use randomized algorithms with probabilistic guarantees",
            "What if the constraints are wrong? Relax them.",
            "Transform to frequency/spectral domain",
        ]
        return f"Scout: {wild_ideas[random.randint(0, len(wild_ideas) - 1)]}"

    @staticmethod
    def combine(solutions: List[str]) -> str:
        """Combiner: merge partial solutions."""
        if not solutions:
            return ""
        if len(solutions) == 1:
            return solutions[0]
        unique = list(dict.fromkeys(solutions))
        return f"Combined [{len(unique)} approaches]: " + " | ".join(s[:40] for s in unique[:3])


# ═══════════════════════════════════════════════════════════
# MAIN ENGINE — Swarm Intelligence
# ═══════════════════════════════════════════════════════════

class SwarmIntelligence:
    """
    Swarm intelligence with ant colony optimization.

    Usage:
        swarm = SwarmIntelligence()
        result = swarm.swarm_solve("Optimize database query performance", n_agents=20, iterations=10)
        print(result.best_solution)
        print(result.best_fitness)
    """

    def __init__(self):
        self.pheromones = PheromoneSystem(evaporation_rate=0.15)
        self.decomposer = ProblemDecomposer()
        self._stats = {"swarm_runs": 0, "total_agents": 0, "total_solutions": 0, "best_fitness_ever": 0.0}

    def swarm_solve(self, problem: str, n_agents: int = 20,
                    iterations: int = 10) -> SwarmResult:
        """Solve using swarm intelligence."""
        start = time.time()
        self._stats["swarm_runs"] += 1
        n_agents = max(5, min(n_agents, 100))  # Cap agents
        iterations = max(3, min(iterations, 50))  # Cap iterations

        result = SwarmResult(agents_used=n_agents, iterations=iterations)

        # Decompose problem
        sub_problems = self.decomposer.decompose(problem)

        # Create agents with diverse roles
        agents = []
        role_distribution = [
            (SwarmRole.EXPLORER, 0.3),
            (SwarmRole.EXPLOITER, 0.25),
            (SwarmRole.SCOUT, 0.15),
            (SwarmRole.CRITIC, 0.15),
            (SwarmRole.COMBINER, 0.15),
        ]

        agent_id = 0
        for role, fraction in role_distribution:
            count = max(1, int(n_agents * fraction))
            for _ in range(count):
                agents.append(MicroAgent(agent_id=agent_id, role=role))
                agent_id += 1
                if agent_id >= n_agents:
                    break
            if agent_id >= n_agents:
                break

        self._stats["total_agents"] += len(agents)

        # Main swarm loop
        all_solutions: List[SwarmSolution] = []
        best_fitness = 0.0
        best_solution = ""

        for iteration in range(iterations):
            iteration_solutions = []

            for agent in agents:
                solution = self._agent_step(agent, problem, sub_problems, best_solution, all_solutions)
                fitness = self.decomposer.evaluate_solution(solution, problem)
                agent.fitness = fitness
                agent.steps_taken += 1

                swarm_sol = SwarmSolution(solution=solution, fitness=fitness, contributors=[agent.agent_id])
                iteration_solutions.append(swarm_sol)

                # Update pheromones
                if fitness > 0.3:
                    self.pheromones.deposit(solution[:50], fitness, agent.agent_id)

                # Track best
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_solution = solution

            all_solutions.extend(iteration_solutions)
            self.pheromones.evaporate()
            result.convergence_history.append(best_fitness)

        # Collect results
        result.best_solution = best_solution
        result.best_fitness = best_fitness
        result.solutions_found = len(all_solutions)
        result.all_solutions = sorted(all_solutions, key=lambda s: -s.fitness)[:10]
        result.duration_ms = (time.time() - start) * 1000

        self._stats["total_solutions"] += result.solutions_found
        self._stats["best_fitness_ever"] = max(self._stats["best_fitness_ever"], best_fitness)

        return result

    def _agent_step(self, agent: MicroAgent, problem: str,
                    sub_problems: List[str], best_solution: str,
                    all_solutions: List[SwarmSolution]) -> str:
        """One agent takes one step."""
        sub = sub_problems[agent.agent_id % len(sub_problems)] if sub_problems else problem

        if agent.role == SwarmRole.EXPLORER:
            return SwarmStrategies.explore(problem, sub)
        elif agent.role == SwarmRole.EXPLOITER:
            return SwarmStrategies.exploit(problem, best_solution)
        elif agent.role == SwarmRole.SCOUT:
            return SwarmStrategies.scout(problem)
        elif agent.role == SwarmRole.CRITIC:
            # Critic evaluates pheromone trails
            best_trails = self.pheromones.best_trails(3)
            if best_trails:
                return f"Critique: Best path '{best_trails[0][0][:40]}' (strength: {best_trails[0][1]:.2f}) appears viable"
            return f"Critique: No strong paths yet for '{sub[:30]}'"
        elif agent.role == SwarmRole.COMBINER:
            recent = [s.solution for s in all_solutions[-5:] if s.fitness > 0.2]
            return SwarmStrategies.combine(recent) if recent else SwarmStrategies.explore(problem, sub)

        return SwarmStrategies.explore(problem, sub)

    def solve(self, prompt: str) -> SwarmResult:
        """Natural language interface."""
        return self.swarm_solve(prompt)

    def get_stats(self) -> Dict[str, Any]:
        return {"engine": "SwarmIntelligence", "swarm_runs": self._stats["swarm_runs"], "total_agents_spawned": self._stats["total_agents"], "total_solutions": self._stats["total_solutions"], "best_fitness_ever": round(self._stats["best_fitness_ever"], 4)}
