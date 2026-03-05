"""
Ultra-Performance Graph-Based Research Mathematics
──────────────────────────────────────────────────
Implements the Internet World Model (IWM) formulations for scaling deep research.
Handles graph representation, message passing, bounded sampling, reliability,
and adversarial robustness.
"""

import math
import time
import numpy as np
from typing import Dict, List, Any, Tuple, Set

class Node:
    """Represents an entity/document in the graph (v \\in V)."""
    def __init__(self, node_id: str, content: str, source: str, reliability: float = 0.5):
        self.node_id = node_id
        self.content = content
        self.source = source
        self.timestamp = time.time() # t_v
        self.reliability = reliability # q_v (0, 1]
        # x_v \\in R^d - Simulate a simple embedding/feature vector for structural math
        self.features = np.random.randn(64) 
        self.h = np.copy(self.features) # h_v^(l)

class Edge:
    """Represents a relational link (u, v, r) \\in E."""
    def __init__(self, source_id: str, target_id: str, relation_type: str = "link"):
        self.source_id = source_id
        self.target_id = target_id
        self.relation_type = relation_type
        # R_r, low-rank factorizable matrices A_r, B_r
        self.A_r = np.random.randn(64, 8) / np.sqrt(64)
        self.B_r = np.random.randn(64, 8) / np.sqrt(64)

class InternetWorldModel:
    """
    Maintains the Graph W = (V, E) and applies Ultra-Performance mathematics.
    """
    def __init__(self, decay_gamma: float = 0.001, temperature: float = 1.0, k_budget: int = 10):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.decay_gamma = decay_gamma
        self.temperature = temperature
        self.k_budget = k_budget # K max neighbor size
        
        # Threat limits
        self.max_incoming_influence_budget = 5.0 # B

    def add_node(self, node: Node):
        if node.node_id not in self.nodes:
            self.nodes[node.node_id] = node

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def calculate_freshness_reliability(self, u_id: str, current_time: float) -> float:
        """
        \\omega_{uv}(\\tau) = \\exp(-\\gamma |\\tau - t_u|) q_u
        """
        if u_id not in self.nodes:
            return 0.0
        u = self.nodes[u_id]
        time_diff = abs(current_time - u.timestamp)
        decay = math.exp(-self.decay_gamma * time_diff)
        return decay * u.reliability

    def scale_aware_gated_sampling(self, target_node_id: str) -> List[str]:
        """
        Calculates \\mathcal{N}_K(v): Sample a bounded neighborhood.
        Also applies Gated subsetting g_\\phi(u, v, r) to cap compute budget.
        """
        # Find all incoming edges to target_node
        incoming_edges = [e for e in self.edges if e.target_id == target_node_id]
        
        # Sort by a simulated gate scoring (using dot products of underlying features)
        # In a real neural net, this is predicted by \\sigma(w_g^T z_{uvr}) > \\delta
        # Here we simulate by ranking highest freshness + reliability combination
        current_time = time.time()
        scored_edges = []
        for edge in incoming_edges:
            score = self.calculate_freshness_reliability(edge.source_id, current_time)
            scored_edges.append((score, edge))
            
        # Sort descending and take top K (Budgeting)
        scored_edges.sort(key=lambda x: x[0], reverse=True)
        gated_neighborhood = [e.source_id for score, e in scored_edges[:self.k_budget]]
        
        return gated_neighborhood

    def apply_message_passing(self, num_layers: int = 2):
        """
        \\alpha_{uvr}^{(\\ell)} and h_v^{(\\ell+1)} propagation.
        """
        current_time = time.time()
        
        for layer in range(num_layers):
            new_h = {}
            for v_id, v_node in self.nodes.items():
                # Get scale-aware Gated Neighborhood
                neighbors = self.scale_aware_gated_sampling(v_id)
                
                # Compute Attention weights \\alpha_{uvr}
                attention_scores = []
                for u_id in neighbors:
                    u_node = self.nodes[u_id]
                    # Simulating dot product attention: a_r^T [h_u || h_v]
                    raw_attn = np.dot(u_node.h, v_node.h) / self.temperature
                    attention_scores.append(raw_attn)
                    
                # Softmax over attention
                if attention_scores:
                    max_attn = max(attention_scores)
                    exp_scores = [math.exp(score - max_attn) for score in attention_scores]
                    sum_exp = sum(exp_scores)
                    alphas = [exp / sum_exp for exp in exp_scores]
                else:
                    alphas = []

                # Message Aggregation
                # h_v^(l+1) = \\sigma( W_0 h_v + \\sum \\alpha \\omega W_r h_u )
                agg_message = np.zeros_like(v_node.h)
                total_incoming_influence = 0.0
                
                for idx, u_id in enumerate(neighbors):
                    u_node = self.nodes[u_id]
                    alpha = alphas[idx]
                    omega = self.calculate_freshness_reliability(u_id, current_time)
                    
                    # Poisoning Constraint Check: Stop considering if we exceed budget B
                    influence = alpha * omega
                    if total_incoming_influence + influence > self.max_incoming_influence_budget:
                        # Cap influence to prevent Sybil/Poisoning domination from unreliable sources
                        break
                    total_incoming_influence += influence
                    
                    # Add to message
                    agg_message += influence * u_node.h
                    
                # Update node representation (simulating W_0 = I, \\sigma = tanh)
                new_h[v_id] = np.tanh(v_node.h + agg_message)
                
            # Apply updates
            for v_id, h_val in new_h.items():
                self.nodes[v_id].h = h_val

    def score_nodes(self) -> List[Tuple[str, float]]:
        """
        Returns nodes ranked by their structural importance and accumulated value
        after message passing. (Proxy for \\pi_\\theta(v) likelihood in the equations).
        """
        scores = []
        for v_id, node in self.nodes.items():
            # Simulating U h_v^(L)
            final_score = np.linalg.norm(node.h) * node.reliability
            scores.append((v_id, final_score))
            
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores
        
    def execute_ultra_performance_distillation(self) -> List[Node]:
        """
        Runs the full graphical algorithm suite to filter the most critical nodes.
        """
        # 1. Message Passing to propagate truth/reliability
        self.apply_message_passing(num_layers=2)
        
        # 2. Score and return top representations
        ranked = self.score_nodes()
        
        # Return top N highest confidence components
        distilled = [self.nodes[v_id] for v_id, score in ranked]
        return distilled
