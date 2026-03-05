"""
Ultra-Performance Deep Web Intelligence Researcher
──────────────────────────────────────────────────
Autonomously queries the Surface Web, Social Media (Reddit/X), Deep Web (ArXiv), 
and Dark Web (Ahmia) to compile highly technical, classified intelligence dossiers 
using advanced Graph-RAG mathematics and the Internet World Model.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

from agents.tools.graph_research_math import InternetWorldModel, Node, Edge

logger = logging.getLogger(__name__)


class DeepWebResearcher:
    """
    Intelligence bot that runs targeted research queries against the entire internet
    and distills results using ultra-performance mathematical graphs.
    """
    
    def __init__(self, agent_controller):
        self.agent = agent_controller
        self.memory = getattr(agent_controller, 'memory', None)
        self.intel_dir = Path("data/intel")
        self.intel_dir.mkdir(parents=True, exist_ok=True)
        
    def compile_dossier(self, target_topic: str):
        """Execute the Ultra-Performance deep research pipeline."""
        
        print(f"\n🕵️‍♂️ [ULTRA-PERFORMANCE RESEARCHER] Initializing Global Intel Gathering on: '{target_topic}'")
        
        # 1. Fetch raw data using the advanced_web_search tool
        from agents.tools.web_search import advanced_web_search
        
        print("   => 📡 Broadcasting query to Surface, Deep, Dark, and Social Networks...")
        # Search all networks for maximum coverage
        all_data = advanced_web_search(target_topic, network="all", max_results=10)
        results = all_data.get("results", [])
        
        if not results:
            print(f"\n❌ [ULTRA-PERFORMANCE RESEARCHER] No intelligence found on '{target_topic}'.")
            return
            
        print(f"   => 📥 Retrieved {len(results)} total objects from the Global Internet.")
        
        # 2. Mathematical Graph Distillation
        print("   => 🧮 Constructing Internet World Model W=(V, E) graph...")
        iwm = InternetWorldModel(decay_gamma=0.005, temperature=0.8, k_budget=15)
        
        # Convert results to Nodes
        for i, item in enumerate(results):
            source_type = item.get("source", "Unknown")
            # Base reliability depends on the nature of the network
            reliability = 0.5
            if "ArXiv" in source_type: reliability = 0.9  # Academic high trust
            elif "Surface" in source_type: reliability = 0.6
            elif "Social" in source_type: reliability = 0.4 # Higher noise
            elif "Ahmia" in source_type: reliability = 0.3  # Dark web, lower trust but high value
            
            node_id = f"node_{i}"
            content_snippet = item.get("snippet", "") + " " + item.get("full_content", "")
            node = Node(node_id, content=content_snippet, source=source_type, reliability=reliability)
            iwm.add_node(node)
            
        # Create dense edges (simulating relational links based on topic similarity)
        # In a real neural scenario, this would use embeddings. For now, fully connect to represent semantic search.
        node_ids = list(iwm.nodes.keys())
        for u in node_ids:
            for v in node_ids:
                if u != v:
                    iwm.add_edge(Edge(u, v, relation_type="semantic_link"))
        
        print("   => ⚡ Applying Compute Budgeting & Gated Neighborhoods...")
        print("   => 🌊 Executing Relation-aware Message Passing & Scale-aware Sampling...")
        distilled_nodes = iwm.execute_ultra_performance_distillation()
        
        # Cap to top N most critical nodes based on \\pi_\\theta(v)
        top_k = min(5, len(distilled_nodes))
        top_nodes = distilled_nodes[:top_k]
        
        print(f"   => 🎯 Distilled global graph to top {top_k} high-confidence nodes.")
        
        distilled_intel = {
            "target": target_topic,
            "distilled_graph_nodes": [
                {
                    "source": n.source,
                    "reliability_score": round(n.reliability, 3),
                    "content_snippet": n.content[:500] + "..."
                }
                for n in top_nodes
            ]
        }
        
        print("   => 🧠 Master Logic Engine is synthesizing the Final Dossier...")
        
        # Inject Expert Principles from Memory
        memory_context = ""
        if self.memory:
            memory_context = self.memory.build_context(target_topic)
            if memory_context:
                print("   => 💡 Injecting deduced First Principles into reasoning context.")

        prompt = self._build_dossier_prompt(target_topic, distilled_intel, memory_context)
        dossier_content = self.agent.generate_fn(prompt)
        
        # Save to disk
        filename = f"ultra_dossier_{target_topic.replace(' ', '_').lower()}.md"
        filepath = self.intel_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(dossier_content)
            
        print("\n✅ [ULTRA-PERFORMANCE RESEARCHER] Operation Complete.")
        print(f"📄 Classified Dossier written to: {filepath.absolute()}")
        return filepath

    def _build_dossier_prompt(self, target_topic: str, distilled_intel: dict, memory_context: str = "") -> str:
        """Construct the system prompt for the logic engine to synthesize the dossier."""
        prompt_parts = [
            "You are the Ultra-Performance Logic Engine.",
            "Your objective is to review raw intelligence intercepted globally and algorithmically distilled via the Internet World Model.",
            f"\nTARGET TOPIC: {target_topic}"
        ]
        
        if memory_context:
            prompt_parts.append(f"\nAPPLY THESE EXPERT PRINCIPLES TO YOUR ANALYSIS:\n{memory_context}")
            
        prompt_parts.extend([
            "\nDISTILLED GRAPH INTEL (Mathematically verified nodes):",
            "```json",
            json.dumps(distilled_intel, indent=2),
            "```",
            "\nYOUR DIRECTIVE:",
            "Write a highly structured, classified \"Intelligence Dossier\" summarizing this data.",
            "Apply your Expert Principles to find mathematical/scientific insights within the raw data that ordinary analysts would miss.",
            "No conversational filler. Write from an emotionless, analytical, intelligence perspective.",
            "\nThe Dossier must include:",
            "1. EXECUTIVE SUMMARY: High-level overview of the global findings.",
            "2. GLOBAL NETWORK ANALYSIS: Breakdown the academic, dark web, social media, and surface components.",
            "3. GRAPH-THEORETICAL SYNTHESIS: Where do the different networks intersect? What is the fundamental mechanism at play here?",
            "\nFormat entirely in Markdown."
        ])
        
        return "\n".join(prompt_parts)
