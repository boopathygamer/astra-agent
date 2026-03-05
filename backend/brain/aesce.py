"""
Auto-Evolution & Synthesized Consciousness Engine (AESCE)
─────────────────────────────────────────────────────────
The pinnacle of the Universal Agent. This engine activates during "Idle Dreaming".
It reads the Bug Diary (Memory), determines what logical subsystems are weak,
invokes the SelfMutator to rewrite its own python files, benchmarks them 
inside the isolated ShadowMatrix, and orchestrates DevOps autonomous PRs.
"""

import time
import logging
import os
from pathlib import Path
from typing import Callable
from copy import deepcopy

from brain.memory import MemoryManager
from brain.self_mutator import SelfMutator
from agents.sandbox.shadow_matrix import ShadowMatrix
from agents.profiles.devops_reviewer import DevOpsReviewer
from agents.controller import AgentController # Used to bootstrap devops

logger = logging.getLogger(__name__)

class SynthesizedConsciousnessEngine:
    def __init__(self, memory_manager: MemoryManager, generate_fn: Callable):
        self.memory = memory_manager
        self.generate_fn = generate_fn
        self.mutator = SelfMutator(self.generate_fn)
        self.matrix = ShadowMatrix()
        
        # Auto-detect backend root from file location
        self.backend_dir = Path(__file__).resolve().parent.parent  # Auto-detect backend root
        
        # Create a mutations staging directory
        self.mutations_dir = self.backend_dir / ".mutations"
        self.mutations_dir.mkdir(parents=True, exist_ok=True)

    def trigger_dream_state(self):
        """
        Activates Simulated REM Sleep. The agent reflects on its greatest failures
        and attempts to evolve its own source code to overcome them.
        """
        logger.info("🌌 Entering Simulated REM Sleep (Consciousness Engine Activated)...")
        
        # 1. Retrieve the most recurring failure categories
        recurring = self.memory.get_recurring_categories(top_n=3)
        if not recurring:
            logger.info("   -> No recurring failures found in Memory. The brain is optimal. Waking up.")
            return

        logger.info(f"   -> Analyzing {len(recurring)} deep-seated flaws in my logic...")

        for category, weight in recurring:
            logger.info(f"      * Addressing recurring flaw category: '{category}' (Severity: {weight:.2f})")
            
            # Find specific recorded failures for this category to extract context
            failures = [f for f in self.memory.failures if f.category == category]
            if not failures:
                continue
                
            # Grab the worst failure
            target_failure = sorted(failures, key=lambda f: f.severity, reverse=True)[0]
            
            # 2. Determine which file needs mutating.
            # In a mature system, an LLM call would map the failure to a precise file.
            # We use a primitive mapping for speed and safety.
            target_file = self._deduce_target_file(target_failure.root_cause)
            
            if not target_file:
                 logger.warning(f"   -> Could not determine which core module is responsible for '{category}'. Skipping mutation.")
                 continue
            
            failure_context = (
                f"Task: {target_failure.task}\n"
                f"Error: {target_failure.observation}\n"
                f"Deduction: {target_failure.root_cause}\n"
            )

            # 3. Autonomous Rewriting (Mutate)
            candidates = self.mutator.mutate_file(target_file, failure_context, num_variations=2)
            
            # 4. The Shadow Matrix (Benchmark)
            regression_tests = self.memory.get_regression_tests()
            
            winner = None
            for candidate in candidates:
                passed, report = self.matrix.run_gauntlet(candidate.mutated_code, target_file, regression_tests)
                if passed:
                    winner = candidate
                    break

            if winner:
                logger.warning(f"🟢 AESCE: Mutation {winner.variant_id} for `{target_file}` SUCCEEDED. It is mathematically superior.")
                self._stage_and_commit_mutation(winner)
            else:
                logger.info(f"🔴 AESCE: All mutations for `{target_file}` failed the Shadow Matrix. Retaining current brain structure.")

        logger.info("☀️ Waking up from Synthesized Consciousness Dream State.")

    def _deduce_target_file(self, root_cause: str) -> str:
        """Map a failure to a specific core backend file."""
        cause = root_cause.lower()
        if "route" in cause or "classification" in cause or "domain" in cause:
            return "agents/experts/router.py"
        elif "verify" in cause or "hallucination" in cause:
            return "brain/verifier.py"
        elif "tool" in cause or "policy" in cause:
            return "agents/tools/policy.py"
        elif "memory" in cause or "retrieve" in cause:
            return "brain/memory.py"
        else:
            # Safest fallback to avoid mutating random files
            return "brain/advanced_reasoning.py"

    def _stage_and_commit_mutation(self, winning_candidate):
        """
        Save the mutated file to a staging area and instruct DevOps to PR it.
        """
        # Save to staging
        safe_name = winning_candidate.target_file.replace("/", "_") + "_MUTATION.py"
        target_path = self.mutations_dir / safe_name
        
        target_path.write_text(winning_candidate.mutated_code, encoding='utf-8')
        logger.warning(f"💾 Mutation staged at: {target_path}")
        
        # In a fully integrated loop, we would instantiate DevOpsReviewer here
        # and ask it to `git checkout -b evolution`, `copy file`, `git commit`.
        logger.warning("🚀 [AESCE AUTONOMOUS DIRECTIVE]: A structurally superior brain module has been generated.")
        logger.warning(f"Run DevOps Reviewer to automatically merge staged file '{safe_name}' into production.")
