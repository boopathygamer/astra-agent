import asyncio
import logging
from typing import Dict, Optional, List
import time
from collections import deque

logger = logging.getLogger(__name__)

class PreCognitiveCache:
    """
    Predictive Shadow Execution Engine.
    Monitors UI state and anticipates user queries, pre-computing responses
    to achieve perceived zero-latency execution.
    """
    def __init__(self, generate_fn, max_cache_size=10):
        self.generate_fn = generate_fn
        self.cache: Dict[str, str] = {}
        self.anticipation_queue = deque(maxlen=max_cache_size)
        self.is_running = False
        
    def anticipate_tasks(self, ui_context: Dict) -> List[str]:
        """Analyzes frontend state and predicts the next 3 tasks the user will ask for."""
        # In a real system, this would use a fast local model to parse UI state.
        # For now, we simulate with rule-based heuristics to prove the architecture.
        predicted = []
        
        active_file = ui_context.get("active_file", "")
        cursor_line = ui_context.get("cursor_line_content", "")
        
        if active_file.endswith(".py"):
            if "def " in cursor_line and "pass" in ui_context.get("file_content", ""):
                 predicted.append(f"Implement the function {cursor_line.strip()} in {active_file}")
            if "try:" in ui_context.get("file_content", "") and "except" not in ui_context.get("file_content", ""):
                 predicted.append(f"Add error handling to the try block in {active_file}")
            
        if not predicted:
            predicted.append(f"Analyze the structure of {active_file} and suggest optimizations.")
            
        return predicted

    async def _precompute_worker(self):
        """Background thread that constantly chews through the anticipation queue."""
        logger.info("[Pre-Cognitive Cache] Shadow execution worker started.")
        while self.is_running:
            if self.anticipation_queue:
                query = self.anticipation_queue.popleft()
                if query not in self.cache:
                    logger.debug(f"[Pre-Cognitive] 🧠 Shadow-computing: '{query}'")
                    try:
                        # Simulate prompt building and generation
                        prompt = f"System: Provide a precise and actionable response to the anticipated task.\nTask: {query}"
                        
                        # We use to_thread to prevent blocking the main event loop
                        result = await asyncio.to_thread(self.generate_fn, prompt)
                        self.cache[query] = result
                        logger.debug(f"[Pre-Cognitive] ✅ Cached result for: '{query}'")
                    except Exception as e:
                        logger.error(f"[Pre-Cognitive] Shadow execution failed for '{query}': {e}")
            
            await asyncio.sleep(0.5)

    def start(self):
        if not self.is_running:
            self.is_running = True
            asyncio.create_task(self._precompute_worker())
            
    def stop(self):
        self.is_running = False

    def update_context(self, ui_context: Dict):
        """Called by the frontend API to push UI state updates."""
        predictions = self.anticipate_tasks(ui_context)
        for p in predictions:
            if p not in self.cache and p not in self.anticipation_queue:
                self.anticipation_queue.append(p)

    def get_instant_response(self, query: str) -> Optional[str]:
        """Check if an exact or highly semantic match exists in the pre-cognitive cache."""
        # Simplistic exact match for MVP. 
        # In full production, this uses semantic vector similarity (Cosine > 0.95).
        if query in self.cache:
            res = self.cache.pop(query)
            logger.info(f"⚡ [Pre-Cognitive HIT] Zero-latency response served for: '{query}'")
            return res
        return None
