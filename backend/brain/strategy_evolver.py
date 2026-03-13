"""
Self-Evolving Intelligence — Strategy Evolver
──────────────────────────────────────────────
Genetic algorithm that evolves earning strategies over time.
Combines elements of winning strategies (crossover), randomly
introduces new variations (mutation), and eliminates failures (selection).

This is the AI's "self-thinking" brain for money-making.
"""

import time
import copy
import math
import random
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class StrategyGene:
    """A single strategy configuration — the 'DNA' of an earning approach."""
    id: str
    pillar: str
    config: Dict[str, Any]
    fitness: float = 0.0
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    mutations_applied: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class EvolutionStats:
    """Tracks the evolution process."""
    total_generations: int = 0
    total_mutations: int = 0
    total_crossovers: int = 0
    total_selections: int = 0
    best_fitness_ever: float = 0.0
    best_gene_id: str = ""
    fitness_history: List[float] = field(default_factory=list)


class StrategyEvolver:
    """
    Genetic algorithm that evolves earning strategies.
    
    How it works:
    1. SELECTION — Read the Performance Ledger to identify top performers
    2. CROSSOVER — Combine configuration elements from winning strategies
    3. MUTATION  — Randomly tweak parameters to explore new possibilities
    4. EVALUATION — Deploy mutated strategies and measure results
    5. REPEAT    — Kill failures, breed winners, iterate forever
    """

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        population_size: int = 20,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.6,
        elite_ratio: float = 0.2,
    ):
        self.generate_fn = generate_fn
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_ratio = elite_ratio
        
        # Gene pool — all strategy configurations
        self._population: Dict[str, StrategyGene] = {}
        self._graveyard: List[StrategyGene] = []  # Dead strategies
        self.stats = EvolutionStats()
        
        # Mutation ranges for common config parameters
        self._mutation_ranges = {
            "max_executions_per_cycle": (1, 10),
            "min_roi_score": (0.1, 0.9),
            "min_budget_usd": (10, 500),
            "max_difficulty": (0.3, 1.0),
            "quality_threshold": (0.3, 1.0),
            "engagement_threshold": (0.1, 0.8),
            "price_range_usd": [(1, 10), (10, 200)],
        }

    def initialize_population(self, pillar_configs: Dict[str, Dict[str, Any]]):
        """
        Bootstrap the gene pool with initial configurations from all pillars.
        Creates variations of each pillar's default config.
        """
        logger.info(f"[EVOLVER] 🧬 Initializing gene pool with {len(pillar_configs)} pillar configs...")
        
        for pillar_name, base_config in pillar_configs.items():
            # Add the original config
            base_gene = StrategyGene(
                id=f"gene_{pillar_name}_base",
                pillar=pillar_name,
                config=copy.deepcopy(base_config),
                fitness=0.5,  # Neutral starting fitness
                generation=0,
            )
            self._population[base_gene.id] = base_gene
            
            # Create 2 mutated variations per pillar
            for v in range(2):
                mutated = self._mutate(base_gene)
                mutated.id = f"gene_{pillar_name}_v{v}"
                self._population[mutated.id] = mutated
        
        logger.info(f"[EVOLVER] Gene pool initialized with {len(self._population)} genes")

    def evolve(self, fitness_scores: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        """
        Run one generation of evolution.
        
        Args:
            fitness_scores: Map of gene_id → fitness (0.0 to 1.0)
                           Based on revenue, win rate, hourly rate from ledger
        
        Returns:
            Dict of pillar_name → evolved_config to apply
        """
        self.stats.total_generations += 1
        logger.info(f"[EVOLVER] 🧬 Generation #{self.stats.total_generations} starting...")
        
        # Update fitness scores
        for gene_id, fitness in fitness_scores.items():
            if gene_id in self._population:
                self._population[gene_id].fitness = fitness
        
        # 1. SELECTION — Keep the elite, kill the weak
        ranked = sorted(self._population.values(), key=lambda g: g.fitness, reverse=True)
        elite_count = max(2, int(len(ranked) * self.elite_ratio))
        elite = ranked[:elite_count]
        
        # Track best ever
        if elite and elite[0].fitness > self.stats.best_fitness_ever:
            self.stats.best_fitness_ever = elite[0].fitness
            self.stats.best_gene_id = elite[0].id
        
        self.stats.fitness_history.append(
            sum(g.fitness for g in ranked) / max(len(ranked), 1)
        )
        
        # Send weak genes to graveyard
        dead = ranked[elite_count:]
        for gene in dead:
            self._graveyard.append(gene)
        self.stats.total_selections += len(dead)
        
        logger.info(
            f"[EVOLVER] Selection: {len(elite)} survivors, {len(dead)} eliminated. "
            f"Best fitness: {elite[0].fitness:.3f}"
        )
        
        # 2. CROSSOVER — Breed elite genes together
        new_population: Dict[str, StrategyGene] = {}
        for gene in elite:
            new_population[gene.id] = gene
        
        while len(new_population) < self.population_size and len(elite) >= 2:
            parent_a, parent_b = random.sample(elite, 2)
            
            if random.random() < self.crossover_rate:
                child = self._crossover(parent_a, parent_b)
                new_population[child.id] = child
                self.stats.total_crossovers += 1
        
        # 3. MUTATION — Randomly tweak some genes
        for gene_id in list(new_population.keys()):
            if random.random() < self.mutation_rate:
                mutated = self._mutate(new_population[gene_id])
                new_population[mutated.id] = mutated
                self.stats.total_mutations += 1
        
        self._population = new_population
        
        # 4. Extract best config per pillar
        evolved_configs = self._extract_best_per_pillar()
        
        logger.info(
            f"[EVOLVER] Generation #{self.stats.total_generations} complete. "
            f"Population: {len(self._population)}, Avg fitness: {self.stats.fitness_history[-1]:.3f}"
        )
        
        return evolved_configs

    def _crossover(self, parent_a: StrategyGene, parent_b: StrategyGene) -> StrategyGene:
        """
        Uniform crossover: randomly pick config values from each parent.
        """
        child_config = {}
        all_keys = set(list(parent_a.config.keys()) + list(parent_b.config.keys()))
        
        for key in all_keys:
            if key in parent_a.config and key in parent_b.config:
                # Randomly pick from either parent
                child_config[key] = random.choice([parent_a.config[key], parent_b.config[key]])
            elif key in parent_a.config:
                child_config[key] = parent_a.config[key]
            else:
                child_config[key] = parent_b.config[key]
        
        child = StrategyGene(
            id=f"gene_{parent_a.pillar}_gen{self.stats.total_generations}_{random.randint(1000,9999)}",
            pillar=parent_a.pillar,
            config=child_config,
            fitness=0.0,
            generation=self.stats.total_generations,
            parent_ids=[parent_a.id, parent_b.id],
        )
        return child

    def _mutate(self, gene: StrategyGene) -> StrategyGene:
        """
        Mutate a gene by randomly tweaking numeric parameters.
        """
        new_config = copy.deepcopy(gene.config)
        mutations = []
        
        for key, value in new_config.items():
            if random.random() > 0.3:  # Only mutate 70% of parameters
                continue
                
            if isinstance(value, (int, float)) and key in self._mutation_ranges:
                range_min, range_max = self._mutation_ranges[key]
                # Gaussian perturbation
                perturbation = random.gauss(0, (range_max - range_min) * 0.1)
                new_value = max(range_min, min(range_max, value + perturbation))
                if isinstance(value, int):
                    new_value = int(round(new_value))
                new_config[key] = new_value
                mutations.append(f"{key}: {value} → {new_value}")
            
            elif isinstance(value, list) and len(value) > 2:
                # Randomly shuffle or add/remove elements
                if random.random() < 0.3:
                    random.shuffle(new_config[key])
                    mutations.append(f"{key}: shuffled")
        
        mutated = StrategyGene(
            id=f"gene_{gene.pillar}_mut{self.stats.total_generations}_{random.randint(1000,9999)}",
            pillar=gene.pillar,
            config=new_config,
            fitness=gene.fitness * 0.9,  # Slight fitness penalty for untested mutation
            generation=self.stats.total_generations,
            parent_ids=[gene.id],
            mutations_applied=mutations,
        )
        return mutated

    def _extract_best_per_pillar(self) -> Dict[str, Dict[str, Any]]:
        """Get the highest-fitness configuration for each pillar."""
        pillar_best: Dict[str, StrategyGene] = {}
        
        for gene in self._population.values():
            if gene.pillar not in pillar_best or gene.fitness > pillar_best[gene.pillar].fitness:
                pillar_best[gene.pillar] = gene
        
        return {pillar: gene.config for pillar, gene in pillar_best.items()}

    def calculate_fitness_from_ledger(self, ledger) -> Dict[str, float]:
        """
        Convert Performance Ledger data into fitness scores for each gene.
        
        Fitness = normalized(revenue * win_rate * hourly_rate)
        """
        fitness_scores = {}
        leaderboard = ledger.get_leaderboard()
        
        if not leaderboard:
            return fitness_scores
        
        # Normalize scores against the best performer
        max_revenue = max(entry.get("total_revenue", 0) for entry in leaderboard) or 1.0
        
        for entry in leaderboard:
            pillar = entry["pillar"]
            revenue_norm = entry.get("total_revenue", 0) / max_revenue
            win_rate = entry.get("win_rate", 0)
            
            # Composite fitness
            fitness = (revenue_norm * 0.5) + (win_rate * 0.3) + (0.2 * min(entry.get("total_attempts", 0) / 10, 1.0))
            
            # Find genes for this pillar and assign fitness
            for gene_id, gene in self._population.items():
                if gene.pillar == pillar:
                    fitness_scores[gene_id] = fitness
        
        return fitness_scores

    def get_evolution_report(self) -> Dict[str, Any]:
        """Get a summary of the evolution process."""
        return {
            "stats": asdict(self.stats),
            "population_size": len(self._population),
            "graveyard_size": len(self._graveyard),
            "population_by_pillar": self._count_by_pillar(),
            "fitness_trend": self.stats.fitness_history[-20:],  # Last 20 generations
        }

    def _count_by_pillar(self) -> Dict[str, int]:
        counts = defaultdict(int)
        for gene in self._population.values():
            counts[gene.pillar] += 1
        return dict(counts)

    # ─── AI-Assisted Evolution ──────────────────────────

    async def suggest_new_strategy(self, pillar: str, failure_data: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        Use AI reasoning to suggest entirely new strategy configurations
        when genetic mutation alone isn't finding improvements.
        """
        if not self.generate_fn:
            return None
        
        import asyncio
        prompt = (
            f"You are a strategy optimization AI. Analyze these failed earning attempts "
            f"for the '{pillar}' pillar and suggest an improved configuration.\n\n"
            f"Recent failures:\n"
            f"{str(failure_data[:5])}\n\n"
            f"Suggest a new configuration as a JSON object with the following fields:\n"
            f"- max_executions_per_cycle (1-10)\n"
            f"- min_roi_score (0.1-0.9)\n"
            f"- preferred approach (string)\n"
            f"- risk_tolerance (0.1-0.9)\n"
            f"Return ONLY a JSON object."
        )
        
        try:
            result = await asyncio.to_thread(self.generate_fn, prompt)
            answer = result.answer if hasattr(result, 'answer') else str(result)
            import json
            config = json.loads(self._extract_json_obj(answer))
            return config
        except Exception as e:
            logger.debug(f"[EVOLVER] AI suggestion failed: {e}")
            return None

    def _extract_json_obj(self, text: str) -> str:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return text[start:end]
        return "{}"
