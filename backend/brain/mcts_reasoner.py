"""
Monte Carlo Tree Search Reasoner
════════════════════════════════
Research-grade MCTS for complex multi-step decision making.

Implements:
  • UCT (Upper Confidence Trees) with tunable exploration
  • Progressive widening for infinite action spaces
  • LLM-pluggable rollout policy
  • RAVE (Rapid Action Value Estimation) for faster convergence
  • Backpropagation with discount factor
  • Transposition table for DAG-structured search

Based on: Kocsis & Szepesvári (2006), Browne et al. (2012) survey,
           and AlphaZero-style value-guided search.

Usage:
    mcts = MCTSReasoner(generate_fn=llm_call)
    result = mcts.search("Design a caching strategy for 10M users")
    print(result.best_action, result.confidence)
"""

import hashlib
import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MCTSNode:
    """A node in the Monte Carlo search tree."""
    node_id: str = ""
    state: str = ""                  # Problem state at this node
    action: str = ""                 # Action that led to this state
    parent_id: str = ""
    children_ids: List[str] = field(default_factory=list)
    visit_count: int = 0
    total_value: float = 0.0
    prior: float = 0.5              # Prior probability from policy network
    depth: int = 0
    is_terminal: bool = False
    is_expanded: bool = False

    # RAVE statistics
    rave_visits: int = 0
    rave_value: float = 0.0

    @property
    def q_value(self) -> float:
        """Mean action value Q(s,a)."""
        if self.visit_count == 0:
            return 0.0
        return self.total_value / self.visit_count

    @property
    def rave_q(self) -> float:
        """RAVE action value."""
        if self.rave_visits == 0:
            return 0.0
        return self.rave_value / self.rave_visits

    def uct_score(self, parent_visits: int, c_puct: float = 1.414,
                  rave_weight: float = 0.0) -> float:
        """
        UCT score combining exploitation + exploration + RAVE.
        
        UCT = Q(s,a) + c_puct * P(a) * sqrt(N_parent) / (1 + N_child)
        
        With RAVE blending:
            β = sqrt(k / (3*N + k))
            score = (1-β)*Q + β*Q_rave + exploration_bonus
        """
        if self.visit_count == 0:
            return float("inf")  # Prioritize unvisited

        # Exploitation: mean value
        exploitation = self.q_value

        # RAVE blending
        if rave_weight > 0 and self.rave_visits > 0:
            k = rave_weight
            beta = math.sqrt(k / (3 * self.visit_count + k))
            exploitation = (1 - beta) * self.q_value + beta * self.rave_q

        # Exploration: UCB1 with prior
        exploration = c_puct * self.prior * math.sqrt(parent_visits) / (1 + self.visit_count)

        return exploitation + exploration


@dataclass
class MCTSResult:
    """Result of an MCTS search."""
    best_action: str = ""
    best_value: float = 0.0
    confidence: float = 0.0
    root_state: str = ""
    total_simulations: int = 0
    total_nodes: int = 0
    max_depth_reached: int = 0
    duration_ms: float = 0.0
    action_values: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_action": self.best_action[:200],
            "confidence": round(self.confidence, 4),
            "simulations": self.total_simulations,
            "nodes": self.total_nodes,
            "max_depth": self.max_depth_reached,
            "duration_ms": round(self.duration_ms, 2),
            "top_actions": self.action_values[:5],
        }


class MCTSReasoner:
    """
    Monte Carlo Tree Search for complex reasoning problems.

    Frames reasoning as a search problem where:
      - States = partial solution states
      - Actions = reasoning steps / decisions
      - Rewards = quality scores from evaluation
      - Terminal = complete solution reached

    Balances exploration (trying new approaches) with exploitation
    (deepening promising approaches) using UCT.
    """

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        evaluate_fn: Optional[Callable] = None,
        c_puct: float = 1.414,
        max_simulations: int = 100,
        max_depth: int = 8,
        rollout_depth: int = 3,
        progressive_widening_alpha: float = 0.5,
        rave_weight: float = 500.0,
        discount_factor: float = 0.95,
    ):
        self.generate_fn = generate_fn
        self.evaluate_fn = evaluate_fn or self._default_evaluate
        self.c_puct = c_puct
        self.max_simulations = max_simulations
        self.max_depth = max_depth
        self.rollout_depth = rollout_depth
        self.pw_alpha = progressive_widening_alpha
        self.rave_weight = rave_weight
        self.discount = discount_factor

        # Search tree stored as dict for transposition support
        self._nodes: Dict[str, MCTSNode] = {}
        self._search_count = 0
        logger.info(
            f"[MCTS] Initialized — sims={max_simulations}, depth={max_depth}, "
            f"c_puct={c_puct}, rave={rave_weight}"
        )

    def search(self, problem: str, context: str = "") -> MCTSResult:
        """
        Run MCTS search on a reasoning problem.

        1. Create root node from problem statement
        2. Repeat max_simulations times:
           a. SELECT: walk tree using UCT to find leaf
           b. EXPAND: generate child actions from leaf
           c. ROLLOUT: simulate to terminal and get reward
           d. BACKPROP: update all ancestors with reward
        3. Return best action from root
        """
        start = time.time()
        self._nodes.clear()
        self._search_count += 1

        # Create root
        root_id = self._make_id(problem)
        root = MCTSNode(
            node_id=root_id,
            state=problem,
            depth=0,
        )
        self._nodes[root_id] = root

        max_depth_seen = 0

        for sim in range(self.max_simulations):
            # 1. SELECT — walk tree to find promising leaf
            leaf, path = self._select(root_id)

            # 2. EXPAND — generate child actions if not terminal
            if not leaf.is_terminal and leaf.depth < self.max_depth:
                child = self._expand(leaf, problem, context)
                if child:
                    path.append(child.node_id)
                    leaf = child

            max_depth_seen = max(max_depth_seen, leaf.depth)

            # 3. ROLLOUT — simulate to estimate value
            value = self._rollout(leaf, problem, context)

            # 4. BACKPROP — update ancestors
            self._backpropagate(path, value)

        # Extract results from root's children
        result = self._extract_result(root_id, problem, max_depth_seen, start)
        return result

    def _select(self, node_id: str) -> Tuple[MCTSNode, List[str]]:
        """Select a leaf node by walking UCT scores down the tree."""
        path = [node_id]
        node = self._nodes[node_id]

        while node.is_expanded and node.children_ids and not node.is_terminal:
            # Progressive widening check: should we expand more?
            max_children = max(1, int(math.ceil(node.visit_count ** self.pw_alpha)))
            if len(node.children_ids) < max_children:
                break  # Time to expand more

            # UCT selection among existing children
            best_score = -float("inf")
            best_child_id = node.children_ids[0]

            for child_id in node.children_ids:
                child = self._nodes.get(child_id)
                if child is None:
                    continue
                score = child.uct_score(
                    parent_visits=node.visit_count,
                    c_puct=self.c_puct,
                    rave_weight=self.rave_weight,
                )
                if score > best_score:
                    best_score = score
                    best_child_id = child_id

            node = self._nodes[best_child_id]
            path.append(best_child_id)

        return node, path

    def _expand(self, node: MCTSNode, problem: str, context: str) -> Optional[MCTSNode]:
        """Expand a node by generating a new child action."""
        node.is_expanded = True

        # Generate possible actions
        actions = self._generate_actions(node.state, problem, context, node.depth)
        if not actions:
            node.is_terminal = True
            return None

        # Filter out already-explored actions
        existing_actions = set()
        for cid in node.children_ids:
            child = self._nodes.get(cid)
            if child:
                existing_actions.add(child.action)

        new_actions = [a for a in actions if a not in existing_actions]
        if not new_actions:
            return None

        # Create child for first new action
        action = new_actions[0]
        new_state = f"{node.state}\n→ {action}"
        child_id = self._make_id(new_state)

        child = MCTSNode(
            node_id=child_id,
            state=new_state,
            action=action,
            parent_id=node.node_id,
            depth=node.depth + 1,
            prior=1.0 / max(len(actions), 1),
        )
        self._nodes[child_id] = child
        node.children_ids.append(child_id)
        return child

    def _rollout(self, node: MCTSNode, problem: str, context: str) -> float:
        """
        Simulate from node to estimate its value.

        Uses LLM-based evaluation if available, otherwise heuristic scoring.
        """
        state = node.state
        depth = 0

        # Quick rollout: extend reasoning a few steps
        while depth < self.rollout_depth and not node.is_terminal:
            actions = self._generate_actions(state, problem, context, node.depth + depth)
            if not actions:
                break
            action = random.choice(actions)
            state = f"{state}\n→ {action}"
            depth += 1

        # Evaluate final state
        value = self.evaluate_fn(state, problem)

        # Apply discount for depth
        return value * (self.discount ** node.depth)

    def _backpropagate(self, path: List[str], value: float) -> None:
        """Backpropagate value through all nodes in the path."""
        for i, node_id in enumerate(reversed(path)):
            node = self._nodes.get(node_id)
            if node is None:
                continue
            # Apply depth-based discount
            discounted = value * (self.discount ** i)
            node.visit_count += 1
            node.total_value += discounted

        # RAVE update: all actions in the path get updated with the terminal value
        actions_in_path = set()
        for node_id in path:
            node = self._nodes.get(node_id)
            if node and node.action:
                actions_in_path.add(node.action)

        for node_id in path:
            node = self._nodes.get(node_id)
            if node is None:
                continue
            for child_id in node.children_ids:
                child = self._nodes.get(child_id)
                if child and child.action in actions_in_path:
                    child.rave_visits += 1
                    child.rave_value += value

    def _extract_result(self, root_id: str, problem: str,
                        max_depth: int, start_time: float) -> MCTSResult:
        """Extract the best action and statistics from the search tree."""
        root = self._nodes[root_id]
        result = MCTSResult(
            root_state=problem,
            total_simulations=root.visit_count,
            total_nodes=len(self._nodes),
            max_depth_reached=max_depth,
            duration_ms=(time.time() - start_time) * 1000,
        )

        # Rank children by visit count (most robust selection)
        child_stats = []
        for child_id in root.children_ids:
            child = self._nodes.get(child_id)
            if child:
                child_stats.append({
                    "action": child.action,
                    "visits": child.visit_count,
                    "q_value": round(child.q_value, 4),
                    "uct_score": round(child.uct_score(root.visit_count, self.c_puct), 4),
                })

        child_stats.sort(key=lambda x: x["visits"], reverse=True)
        result.action_values = child_stats

        if child_stats:
            best = child_stats[0]
            result.best_action = best["action"]
            result.best_value = best["q_value"]
            # Confidence = visit proportion of best child
            total_visits = sum(c["visits"] for c in child_stats)
            result.confidence = best["visits"] / max(total_visits, 1)

        # Build reasoning trace
        trace = self._trace_best_path(root_id)
        result.reasoning_trace = trace

        logger.info(
            f"[MCTS] Search complete — best_q={result.best_value:.3f}, "
            f"conf={result.confidence:.3f}, nodes={result.total_nodes}, "
            f"depth={max_depth}, time={result.duration_ms:.0f}ms"
        )
        return result

    def _trace_best_path(self, node_id: str) -> List[str]:
        """Trace the most-visited path from root to leaf."""
        trace = []
        current = self._nodes.get(node_id)
        while current and current.children_ids:
            best_child = None
            best_visits = -1
            for cid in current.children_ids:
                child = self._nodes.get(cid)
                if child and child.visit_count > best_visits:
                    best_visits = child.visit_count
                    best_child = child
            if best_child is None:
                break
            trace.append(f"[d{best_child.depth}|v={best_visits}|q={best_child.q_value:.3f}] {best_child.action}")
            current = best_child
        return trace

    # ── Action Generation ──

    def _generate_actions(self, state: str, problem: str,
                          context: str, depth: int) -> List[str]:
        """Generate possible actions from a state using LLM or heuristics."""
        if self.generate_fn:
            prompt = (
                f"Given this reasoning state, suggest 3 distinct next steps.\n\n"
                f"Original problem: {problem[:300]}\n"
                f"Current reasoning:\n{state[-500:]}\n"
                f"{'Context: ' + context[:200] if context else ''}\n\n"
                f"Provide exactly 3 different approaches, one per line:\n"
                f"1. "
            )
            try:
                response = self.generate_fn(prompt)
                return self._parse_actions(response)
            except Exception as e:
                logger.warning(f"[MCTS] Action generation failed: {e}")

        # Fallback heuristic actions
        return self._heuristic_actions(state, depth)

    @staticmethod
    def _parse_actions(response: str) -> List[str]:
        """Parse numbered actions from LLM response."""
        actions = []
        for line in response.strip().split("\n"):
            line = line.strip()
            # Strip leading numbers: "1.", "2)", "- ", etc.
            cleaned = line.lstrip("0123456789.-) ").strip()
            if cleaned and len(cleaned) > 5:
                actions.append(cleaned[:200])
        return actions[:5]  # Cap at 5

    @staticmethod
    def _heuristic_actions(state: str, depth: int) -> List[str]:
        """Fallback heuristic action generation."""
        strategies = [
            "Break into sub-problems and address the most critical one first",
            "Consider edge cases and failure modes",
            "Apply a known design pattern or best practice",
            "Simplify the approach and remove unnecessary complexity",
            "Validate assumptions with a concrete example",
        ]
        # Rotate strategies based on depth to avoid repetition
        start = depth % len(strategies)
        return strategies[start:start + 3]

    # ── Evaluation ──

    @staticmethod
    def _default_evaluate(state: str, problem: str) -> float:
        """Default evaluation function (heuristic)."""
        score = 0.3
        state_lower = state.lower()
        # Reward specificity
        if len(state) > 200:
            score += 0.1
        # Reward structured thinking
        if any(kw in state_lower for kw in ["because", "therefore", "step", "consider"]):
            score += 0.15
        # Reward solution-oriented content
        if any(kw in state_lower for kw in ["solution", "implement", "result", "approach"]):
            score += 0.15
        # Reward completeness signals
        if any(kw in state_lower for kw in ["finally", "conclusion", "complete", "summary"]):
            score += 0.1
        # Penalize vagueness
        if any(kw in state_lower for kw in ["maybe", "perhaps", "not sure", "unclear"]):
            score -= 0.1
        return max(0.0, min(1.0, score))

    @staticmethod
    def _make_id(state: str) -> str:
        return hashlib.md5(f"{state}:{time.time()}:{random.random()}".encode()).hexdigest()[:16]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_searches": self._search_count,
            "config": {
                "max_simulations": self.max_simulations,
                "max_depth": self.max_depth,
                "c_puct": self.c_puct,
                "discount": self.discount,
                "rave_weight": self.rave_weight,
            },
        }
