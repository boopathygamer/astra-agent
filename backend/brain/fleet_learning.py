"""
Persistent Fleet Learning — Pillar 2 of Super General Intelligence (SGI)
────────────────────────────────────────────────────────────────────────
A background swarm optimization daemon that prevents computational memory
loss between processes. It persists mathematical Hyperparameters (Θ) to a
global JSON state, and generates synthetic edge-case tasks to run during
"Self-Play" idle times, continually evolving the core Super Intelligence
Engine without human intervention.
"""

import json
import logging
import asyncio
import os
import time
import numpy as np
from typing import Dict, Any, List

from brain.super_intelligence import SuperIntelligenceEngine

logger = logging.getLogger(__name__)

GLOBAL_WEIGHTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    "data", "global_weights.json"
)

class GlobalWeightManager:
    """Manages the persistence of N-dimensional Theta tensors onto disk for lifetime continuous learning."""
    
    @staticmethod
    def save_weights(engine: SuperIntelligenceEngine) -> None:
        try:
            os.makedirs(os.path.dirname(GLOBAL_WEIGHTS_PATH), exist_ok=True)
            vec = engine.theta.as_vector().tolist()
            
            data = {
                "exploration_rate": vec[0],
                "confidence_threshold": vec[1],
                "max_reasoning_depth": int(vec[2]),
                "risk_tolerance": vec[3],
                "timestamp": time.time()
            }
            
            with open(GLOBAL_WEIGHTS_PATH, 'w') as f:
                json.dump(data, f, indent=4)
                
            logger.info(f"[SGI Fleet] Global weights successfully mathematically persisted to disk.")
        except Exception as e:
            logger.error(f"[SGI Fleet] Failed to persist weights: {e}")

    @staticmethod
    def load_weights(engine: SuperIntelligenceEngine) -> bool:
        """Hydrates the SuperIntelligenceEngine from the permanent planetary weights file."""
        if not os.path.exists(GLOBAL_WEIGHTS_PATH):
            return False
            
        try:
            with open(GLOBAL_WEIGHTS_PATH, 'r') as f:
                data = json.load(f)
                
            vec = np.array([
                data.get("exploration_rate", 0.2),
                data.get("confidence_threshold", 0.85),
                float(data.get("max_reasoning_depth", 5)),
                data.get("risk_tolerance", 0.1)
            ])
            
            engine.theta.from_vector(vec)
            logger.info("[SGI Fleet] Successfully bootstrapped super-intelligence parameters from historical global file.")
            return True
        except Exception as e:
            logger.error(f"[SGI Fleet] Global weight hydration failed ({e}). Falling back to pristine initialization.")
            return False

class SyntheticTaskGenerator:
    """Uses LLMs to hallucinate highly complex, mathematically dense programming scenarios for self-play."""
    
    def __init__(self, generate_fn):
        self.generate_fn = generate_fn
        
    def generate_task(self) -> str:
        prompt = (
            "You are a mathematical and algorithmic task generator for an AGI. "
            "Generate an incredibly difficult, multi-step problem that requires "
            "algorithmic coding, systems design, and formal logic to solve. "
            "Do NOT output the solution. Do NOT use markdown. Output ONLY the complex task description natively."
        )
        try:
            return self.generate_fn(prompt)
        except Exception as e:
            logger.error(f"Task generation failed: {e}")
            return "Write a Python script that calculates the 10,000th prime number efficiently."

class SwarmOptimizer:
    """
    Background worker that runs self-play loops.
    Spawns multiple conceptual tasks and forces the Thinking Loop to solve them, 
    evolving the global gradient matrices while the system is theoretically 'idle'.
    """
    
    def __init__(self, thinking_loop, generate_fn):
        self.thinking_loop = thinking_loop
        self.task_generator = SyntheticTaskGenerator(generate_fn)
        self.is_running = False
        
    async def run_swarm_loop(self):
        """Asynchronous execution of background self-play."""
        logger.info("[SGI Fleet Swarm] Initializing Background Fleet Learning Daemon...")
        self.is_running = True
        
        while self.is_running:
            try:
                # 1. Generate an impossible task
                synthetic_task = self.task_generator.generate_task()
                logger.debug(f"[SGI Fleet Swarm] Generated self-play task: {synthetic_task[:100]}...")
                
                # 2. Assign to the thinking loop synchronously within an async thread
                # This engages the complete suite: Math, Code analysis, Verifier Layer 7
                result = await asyncio.to_thread(
                    self.thinking_loop.think,
                    problem=synthetic_task,
                    action_type="swarm_sandbox",
                    max_iterations=5
                )
                
                # 3. Synchronize the newly evolved Math Matrices to disk permanently
                if hasattr(self.thinking_loop, "super_intelligence"):
                    GlobalWeightManager.save_weights(self.thinking_loop.super_intelligence)
                    
                logger.info("[SGI Fleet Swarm] Swarm epoch complete. Global hyperparameters permanently evolved.")
                
                # Sleep heavily to prevent CPU meltdown on the host machine
                await asyncio.sleep(600)  # Rest 10 minutes between epoch evolutions
                
            except Exception as e:
                logger.error(f"[SGI Fleet Swarm] Critical exception in swarm loop: {e}")
                await asyncio.sleep(60) # Backoff
                
    def stop(self):
        self.is_running = False
