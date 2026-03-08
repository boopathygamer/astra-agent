"""
Hierarchical Executive Agency — Pillar 3 of Super General Intelligence (SGI)
────────────────────────────────────────────────────────────────────────────
A hyper-cognitive orchestrator that intercepts planetary-scale objectives,
shatters them into a Directed Acyclic Graph (DAG) of component sub-tasks,
and transiently spawns budget-constrained Sub-Agents to conquer them in parallel.
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

from agents.controller import AgentController
from agents.viral_swarm import ViralSwarm

logger = logging.getLogger(__name__)

@dataclass
class SubTask:
    id: str
    description: str
    dependencies: List[str]
    assigned_role: str
    budget_tokens: int
    status: str = "pending"
    result: Optional[str] = None

class DAGDecomposer:
    """Takes impossible prompts and shatters them into parallel logic graphs."""
    
    def __init__(self, generate_fn):
        self.generate_fn = generate_fn
        
    def break_down_objective(self, objective: str) -> List[SubTask]:
        logger.info("[SGI CEO] Shattering planetary objective into Directed Acyclic Graph...")
        
        prompt = (
            f"You are a Super General Intelligence (SGI) CEO Agent. "
            f"Break down the following massive objective into a strict Directed Acyclic Graph (DAG) of sub-tasks.\n\n"
            f"Objective: {objective}\n\n"
            f"Output a raw JSON list of dictionaries. Each dictionary must have:\n"
            f"- 'id': string (e.g., 'task_1')\n"
            f"- 'description': string (clear instruction)\n"
            f"- 'dependencies': list of task ids that must complete before this one\n"
            f"- 'assigned_role': string (e.g., 'Code Expert', 'Logic Engine')\n"
            f"- 'budget_tokens': int\n\n"
            f"Do not use markdown blocks. Output pure JSON."
        )
        
        try:
            response = self.generate_fn(prompt)
            # Remove markdown blocks if hallucinated
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].strip()
                
            tasks_data = json.loads(response)
            
            subtasks = []
            for t in tasks_data:
                subtasks.append(SubTask(
                    id=t.get("id", f"task_{time.time()}"),
                    description=t.get("description", ""),
                    dependencies=t.get("dependencies", []),
                    assigned_role=t.get("assigned_role", "general"),
                    budget_tokens=t.get("budget_tokens", 500)
                ))
            return subtasks
        except Exception as e:
            logger.error(f"[SGI CEO] DAG Decomposition failed: {e}. Falling back to monolithic execution.")
            # Fallback to single task
            return [SubTask(id="task_1", description=objective, dependencies=[], assigned_role="general", budget_tokens=5000)]


class SubAgentSpawner:
    """Spawns transient AgentController instances to execute sub-graphs."""
    
    def __init__(self, generate_fn, tools, event_callback: Optional[Callable] = None):
        self.generate_fn = generate_fn
        self.tools = tools
        self.event_callback = event_callback
        
    def execute_dag(self, subtasks: List[SubTask]) -> str:
        completed_tasks: Dict[str, str] = {}
        pending_tasks = {t.id: t for t in subtasks}
        
        logger.info(f"[SGI CEO] Commencing DAG execution across {len(subtasks)} transient sub-agents.")
        
        while pending_tasks:
            # Find tasks with resolved dependencies
            executable = [
                t for t in pending_tasks.values() 
                if all(dep in completed_tasks for dep in t.dependencies)
            ]
            
            if not executable:
                logger.error("[SGI CEO] DAG Deadlock detected! Unresolvable dependencies.")
                break
                
            for task in executable:
                logger.info(f"[SGI CEO] Spawning worker agent for: {task.id} [{task.assigned_role}]")
                
                if self.event_callback:
                    self.event_callback({
                        "type": "thread_message",
                        "thread_id": "ceo-board",
                        "channel": "#executive-planning",
                        "role": "CEO Agent",
                        "content": f"Spawning specialized sub-agent for DAG node `{task.id}`: {task.description} (Budget: {task.budget_tokens})",
                        "timestamp": time.time() * 1000
                    })
                
                # Contextualize prompt with prior results
                context = "\n".join([f"Result of {dep}: {completed_tasks[dep]}" for dep in task.dependencies if dep in completed_tasks])
                full_prompt = f"PRIOR CONTEXT:\n{context}\n\nYOUR TASK:\n{task.description}"
                
                # Spawn transient agent
                worker = AgentController(
                    generate_fn=self.generate_fn,
                    tool_registry=self.tools,
                    agent_id=f"worker_{task.id}"
                )
                
                # Execute mathematically
                response = worker.process(
                    user_input=full_prompt,
                    session_id=f"transient_{task.id}",
                    event_callback=self.event_callback
                )
                
                completed_tasks[task.id] = response.answer
                del pending_tasks[task.id]
                
        # Synthesize final output
        synthesis = "\n\n".join([f"### {tid}\n{res}" for tid, res in completed_tasks.items()])
        return f"## [SGI CEO] Planetary Objective Complete\n\n{synthesis}"

class CEOAgent:
    """Supreme SGI Execution orchestrator."""
    def __init__(self, generate_fn, tools, event_callback=None):
        self.decomposer = DAGDecomposer(generate_fn)
        self.spawner = SubAgentSpawner(generate_fn, tools, event_callback)
        
    def execute_planetary_task(self, objective: str) -> str:
        dag = self.decomposer.break_down_objective(objective)
        code_synthesis = self.spawner.execute_dag(dag)
        
        # --- ASI TIER 2: VIRAL SWARM INTEGRATION ---
        logger.info("[SGI CEO] Engaging ASI Tier 2: Algorithmic Marketing Distribution...")
        try:
            swarm = ViralSwarm(self.decomposer.generate_fn)
            campaign = swarm.generate_launch_campaign(
                project_summary=objective, 
                tech_stack="SGI Auto-Generated DAG Modules"
            )
            
            code_synthesis += "\n\n## 🚀 [ASI TIER 2] ALGORITHMIC VIRAL LAUNCH CAMPAIGN\n"
            for platform, content in campaign.items():
                code_synthesis += f"\n### {platform.upper()} MODULE\n{content}\n"
        except Exception as e:
            logger.error(f"[CEO ASI SWARM] Failed to execute marketing distribution: {e}")
            
        return code_synthesis
