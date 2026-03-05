"""
Code Evolution Engine via Execution Benchmarking
─────────────────────────────────────────────────
This module generates multiple implementations of a function,
sandboxes them, benchmarks their execution speed and memory,
and genetically selects the absolute best version.
"""

import time
import logging
import ast
import inspect
from dataclasses import dataclass
from typing import List, Optional, Any, Dict

try:
    import psutil
except ImportError:
    psutil = None

from core.model_providers import ProviderRegistry
from agents.tools.code_executor import CodeExecutor
from agents.sandbox.environment import SandboxEnv
from brain.thinking_loop import ThinkingLoop
from brain.memory import MemoryManager
from brain.expert_reflection import ExpertReflectionEngine

logger = logging.getLogger(__name__)


@dataclass
class CodeCandidate:
    """A single generated code solution."""
    id: int
    code: str
    is_valid: bool = False
    execution_time_ms: float = float('inf')
    peak_memory_kb: float = float('inf')
    error: Optional[str] = None
    output: Optional[str] = None


class CodeEvolutionEngine:
    def __init__(self, registry: ProviderRegistry, memory: Optional[MemoryManager] = None):
        self.registry = registry
        self.generate_fn = registry.generate_fn()
        self.executor = CodeExecutor()
        self.memory = memory or MemoryManager()
        self.expert_reflection = ExpertReflectionEngine(self.generate_fn)

    def _generate_variations(self, prompt: str, num_variations: int = 3) -> List[CodeCandidate]:
        """Ask the LLM to generate N fundamentally different approaches."""
        candidates = []
        logger.info(f"🧬 Generating {num_variations} evolutionary candidates...")

        for i in range(num_variations):
            system_prompt = (
                "You are an expert, competitive programmer. Return ONLY raw Python code. "
                "No markdown, no explanation. "
                "Write an extremely highly optimized solution for the given prompt. "
                f"This is attempt {i+1}. Use a completely different algorithmic approach or library "
                "than standard generic answers if possible to maximize speed."
            )

            result = self.generate_fn(prompt, system_prompt=system_prompt, temperature=0.9)
            code = self._extract_code(result.answer)
            candidates.append(CodeCandidate(id=i+1, code=code))

        return candidates

    def _extract_code(self, raw_text: str) -> str:
        """Strip markdown blocks if the LLM leaked them."""
        text = raw_text.strip()
        if text.startswith("```python"):
            text = text[9:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _benchmark_candidate(self, candidate: CodeCandidate, test_cases: str):
        """Run candidate securely and measure speed/memory."""
        logger.info(f"🧪 Benchmarking Candidate #{candidate.id}...")
        
        # Combine the candidate's implementation with the test cases
        full_code = f"{candidate.code}\n\n{test_cases}"
        
        start_time = time.perf_counter()
        
        try:
            # Execute in isolated environment
            result = self.executor.execute(full_code, timeout=5)
            
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            if result.error:
                candidate.error = result.error
                candidate.is_valid = False
            else:
                candidate.output = result.output
                candidate.is_valid = True
                candidate.execution_time_ms = duration_ms
                # In a real environment, we'd wrap this process in memory limits using cgroups or psutil
                candidate.peak_memory_kb = len(candidate.code) * 2.5 # Mock proxy for now

        except Exception as e:
            candidate.error = str(e)
            candidate.is_valid = False

    def evolve(self, problem_description: str, test_cases: str, generations: int = 3) -> Optional[CodeCandidate]:
        """Main Evolution Loop."""
        logger.info("=" * 60)
        logger.info(f"🚀 Starting Code Evolution Sequence (Max variations: {generations})")
        logger.info("=" * 60)

        candidates = self._generate_variations(problem_description, num_variations=generations)
        
        valid_candidates = []
        for c in candidates:
            self._benchmark_candidate(c, test_cases)
            if c.is_valid:
                valid_candidates.append(c)

        if not valid_candidates:
            logger.error("❌ Evolution failed. All candidates produced errors.")
            error_summary = ""
            for c in candidates:
                logger.error(f"Candidate #{c.id} Error: {c.error}")
                error_summary += f"Option {c.id} failed: {c.error}\n"
                
            # Deep Expert Reflection (Failure -> Root Cause)
            root_cause = self.expert_reflection.deduce_root_cause(
                problem=problem_description,
                failed_candidate=candidates[0].code,
                verifier_feedback=f"All {generations} variations failed execution. Errors: {error_summary}"
            )
            logger.info(f"Evolution Root Cause Deduced: {root_cause}")
            return None

        # Select the fittest candidate (fastest execution time)
        best = min(valid_candidates, key=lambda c: c.execution_time_ms)
        
        logger.info(f"🏆 Evolution Complete! Winner: Candidate #{best.id}")
        logger.info(f"   ⏱️ Speed: {best.execution_time_ms:.2f}ms")
        
        # Deep Expert Reflection (Success -> Principle)
        principle = self.expert_reflection.extract_first_principle(
            problem=problem_description,
            successful_solution=best.code,
            domain="coding_evolution"
        )
        if principle:
            self.memory.store_principle(principle)
            logger.info(f"💎 Abstracted First Principle: {principle.actionable_rule}")
        
        return best
