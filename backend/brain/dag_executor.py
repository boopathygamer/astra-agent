import asyncio
import logging
import uuid
from typing import Dict, List, Any, Callable, Awaitable, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class DAGNode:
    """Represents a discrete computational thought or sub-task in the Swarm."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Anonymous_Node"
    task_fn: Callable[..., Awaitable[Any]] = None
    kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # Topology
    dependencies: List[str] = field(default_factory=list) # IDs of nodes that must complete first
    
    # State
    result: Any = None
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    error: Exception = None

class DAGExecutor:
    """
    Neuromorphic execution engine. Takes an unorganized swarm of tasks
    and topologically executes them with maximum asyncio concurrency.
    """
    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        
    def add_node(self, node: DAGNode):
        self.nodes[node.id] = node
        
    def _get_topological_generations(self) -> List[List[DAGNode]]:
        """Kahn's algorithm to resolve execution layers."""
        in_degree = {node_id: 0 for node_id in self.nodes}
        adj_list = {node_id: [] for node_id in self.nodes}
        
        for node_id, node in self.nodes.items():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise ValueError(f"Dependency {dep} not found in DAG.")
                adj_list[dep].append(node_id)
                in_degree[node_id] += 1
                
        generations = []
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        
        while queue:
            current_generation = queue
            generations.append([self.nodes[nid] for nid in current_generation])
            queue = []
            
            for node_id in current_generation:
                for neighbor in adj_list[node_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
                        
        if sum(len(gen) for gen in generations) != len(self.nodes):
            raise ValueError("Cycle detected in DAG. Cannot execute neuromorphically.")
            
        return generations

    async def execute(self) -> Dict[str, Any]:
        """Runs the entire DAG using max concurrency per generation."""
        logger.info(f"⚡ [DAG Engine] Firing {len(self.nodes)} synthetic swarm threads...")
        
        try:
            generations = self._get_topological_generations()
        except Exception as e:
            logger.error(f"[DAG Engine] Topology resolution failed: {e}")
            raise

        results = {}
        for idx, generation in enumerate(generations):
            logger.debug(f"[DAG Engine] Executing Generation {idx} ({len(generation)} concurrent nodes)")
            
            # Map up dependencies from prior results
            async def run_node(node: DAGNode):
                node.status = "RUNNING"
                try:
                    # Inject inputs from parents if needed
                    # (Simplified for now - passes all specific kwargs directly)
                    node.result = await node.task_fn(**node.kwargs)
                    node.status = "COMPLETED"
                    logger.debug(f"[DAG Engine] ✅ {node.name} resolved.")
                    return node.id, node.result
                except Exception as e:
                    node.status = "FAILED"
                    node.error = e
                    logger.error(f"[DAG Engine] ❌ {node.name} failed: {e}")
                    raise
                    
            tasks = [run_node(node) for node in generation]
            
            # Fire the generation simultaneously
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in completed:
                if isinstance(res, Exception):
                    raise RuntimeError(f"DAG Execution halted due to swarm collapse: {res}")
                node_id, val = res
                results[node_id] = val
                
        logger.info(f"⚡ [DAG Engine] Swarm topology resolved successfully.")
        return results
