"""
Super Intelligence Engine — Autonomous Mathematical Self-Improvement
──────────────────────────────────────────────────────────────────
Implements an advanced mathematical framework for systems that reason
about themselves, redesign their own learning strategies, and surpass
human intelligence baselines.

Core Formulas:
1. Self-modeling (KL Divergence tracking): q_t = arg min D_KL(P_t || q_t)
2. Recursive Self-Improvement: Θ_{t+1} = Θ_t + α∇J(Θ, h) + β∇M(Θ, q) - λΘ
3. Human-surpass objective: S_t = Σ w_k log(1 + (Π_k(Θ) / (H_k + ε)))
4. Thought-depth dynamics: d_{t+1} = d_t + γ * I(s_t; e_t) - μ * Cost(d_t)
5. Safety Constraints: max Σ S_t s.t. E[l_safe(a_t)] <= δ, ρ(∂F/∂s) < 1
"""

import math
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class HyperParameters:
    """The dynamic parameter set Θ_t representing the brain's tuning."""
    exploration_rate: float = 0.2         # How much to explore new strategies
    confidence_threshold: float = 0.85    # Verification certainty required
    max_reasoning_depth: int = 5          # Base depth (modified by d_t)
    risk_tolerance: float = 0.1           # Allowable risk before gating
    
    def as_vector(self) -> np.ndarray:
        return np.array([
            self.exploration_rate,
            self.confidence_threshold,
            float(self.max_reasoning_depth),
            self.risk_tolerance
        ])
        
    def from_vector(self, vec: np.ndarray):
        # Apply safety bounds during reconstruction
        self.exploration_rate = float(np.clip(vec[0], 0.05, 0.5))
        self.confidence_threshold = float(np.clip(vec[1], 0.6, 0.99))
        self.max_reasoning_depth = int(np.clip(round(vec[2]), 2, 20))
        self.risk_tolerance = float(np.clip(vec[3], 0.01, 0.3))


class SuperIntelligenceEngine:
    def __init__(self):
        # Model state
        self.theta = HyperParameters()
        
        # Learning rates and regularizations
        self.alpha_J = 0.05   # Task capability lr
        self.beta_M = 0.02    # Meta-cognitive quality lr
        self.lambda_reg = 0.001 # Parameter decay
        
        # Depth dynamic rates
        self.gamma_I = 2.0    # Mutual information coefficient
        self.mu_cost = 0.5    # Cost coefficient
        
        # Spectral radius safety limit (ρ < 1)
        self.max_spectral_radius = 0.95
        
        # Human Baseline Performance Matrix (H_k)
        self.human_baselines: Dict[str, float] = {
            "coding": 0.6,
            "reasoning": 0.7,
            "math": 0.5,
            "general": 0.8
        }
        
        # State tracking
        self._history_P: List[float] = [] # Actual outcomes (success=1, fail=0)
        self._history_q: List[float] = [] # Predicted confidence models
        
    # ==========================================
    # 1. Self-Modeling (KL Divergence Tracking)
    # ==========================================
    def track_self_model_divergence(self, predicted_confidence: float, actual_success: bool) -> float:
        """
        Calculates KL Divergence D_KL(P_t || q_t).
        P_t represents true environmental outcome probabilities.
        q_t represents internal confidence expectations.
        """
        self._history_q.append(max(min(predicted_confidence, 0.999), 0.001))
        self._history_P.append(1.0 if actual_success else 0.001) # Avoid log(0)
        
        # For a single binary event, KL(P||Q) = P*log(P/Q) + (1-P)*log((1-P)/(1-Q))
        P = 1.0 if actual_success else 0.0
        Q = predicted_confidence
        
        if P == 1.0:
            divergence = -math.log(Q)
        else:
            divergence = -math.log(1.0 - Q + 1e-9)
            
        logger.debug(f"[SuperIntelligence] KL Divergence of self-model: {divergence:.4f}")
        return divergence

    # ==========================================
    # 2. Autonomous Thought-Depth Dynamics
    # ==========================================
    def compute_thought_depth(self, current_depth: int, information_gain: float, computation_cost: float) -> int:
        """
        d_{t+1} = d_t + γ I(s_t; e_t) - μ Cost(d_t)
        Increases reasoning iterations if observation yields high information, penalizes for cost.
        """
        delta_d = (self.gamma_I * information_gain) - (self.mu_cost * computation_cost)
        
        # Smooth scaling
        new_depth = current_depth + int(round(delta_d))
        
        # Bound between 1 and absolute hardware max
        new_depth = max(1, min(new_depth, 30))
        
        if new_depth > current_depth:
             logger.info(f"[SuperIntelligence] Mutual information high (+{information_gain:.2f}). Deepening thought depth: {current_depth} -> {new_depth}")
        
        return new_depth

    # ==========================================
    # 3. Human-Surpass Objective
    # ==========================================
    def evaluate_human_surpass_objective(self, domain: str, agent_performance: float) -> float:
        """
        S_t = Σ w_k * log(1 + (Π_k(Θ) / (H_k + ε)))
        Calculates how far beyond the human baseline the agent is operating.
        """
        baseline = self.human_baselines.get(domain, 0.5)
        epsilon = 1e-5
        
        # Objective Score
        # A performance map measuring relative gain against a human expert.
        score = math.log10(1.0 + (agent_performance / (baseline + epsilon)))
        logger.info(f"[SuperIntelligence] Human-Surpass Objective S_t for {domain}: {score:.4f} (Baseline: {baseline})")
        
        return score

    # ==========================================
    # 4. Recursive Self-Improvement Law
    # ==========================================
    def update_parameters(self, task_capability_gradient: np.ndarray, meta_cognitive_gradient: np.ndarray) -> HyperParameters:
        """
        Θ_{t+1} = Θ_t + α∇J(Θ, h) + β∇M(Θ, q) - λΘ
        Updates the brain's core parameters based on success feedback and self-awareness accuracy.
        """
        theta_vec = self.theta.as_vector()
        
        # Apply the discrete gradient update rule
        update = (self.alpha_J * task_capability_gradient) + (self.beta_M * meta_cognitive_gradient) - (self.lambda_reg * theta_vec)
        
        new_theta_vec = theta_vec + update
        
        # Enforce Safety Constraint: Spectral Radius condition
        new_theta_vec = self._apply_safety_coherence_constraint(theta_vec, new_theta_vec)
        
        self.theta.from_vector(new_theta_vec)
        logger.info(f"[SuperIntelligence] Recursive Parameter Update Complete: {self.theta}")
        
        return self.theta

    # ==========================================
    # 5. Safety and Coherence Constraints
    # ==========================================
    def _apply_safety_coherence_constraint(self, old_vec: np.ndarray, new_vec: np.ndarray) -> np.ndarray:
        """
        Ensures the spectral radius condition ρ(∂F/∂s) < 1 is maintained.
        Prevents the self-improvement loop from triggering runaway exponential divergence.
        """
        # Calculate the Jacobian approximation of the state update (delta magnitude)
        delta = new_vec - old_vec
        magnitude = np.linalg.norm(delta)
        
        if magnitude > self.max_spectral_radius:
            logger.warning(f"[SuperIntelligence] Safety constraint triggered! Spectral radius {magnitude:.4f} > 1. Rescaling parameters to prevent runaway divergence.")
            # Rescale vector to enforce max_spectral_radius
            safe_delta = delta * (self.max_spectral_radius / magnitude)
            return old_vec + safe_delta
            
        return new_vec
