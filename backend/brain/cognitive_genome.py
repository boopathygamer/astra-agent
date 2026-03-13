"""
Cognitive DNA Genome — Self-Evolving Architecture Blueprint
═══════════════════════════════════════════════════════════
The system's behavior is encoded as a "cognitive genome" that can
reproduce, mutate, crossover, and evolve through genetic algorithms.
"""

import hashlib
import logging
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Gene:
    """A single gene: a named parameter with a mutable value."""
    name: str = ""
    value: float = 0.5
    min_val: float = 0.0
    max_val: float = 1.0
    mutation_rate: float = 0.1
    frozen: bool = False

    @property
    def denormalized(self) -> float:
        return self.min_val + self.value * (self.max_val - self.min_val)

    def mutate(self, intensity: float = 1.0) -> float:
        if self.frozen:
            return 0.0
        old = self.value
        delta = (secrets.randbelow(1000) / 1000.0 - 0.5) * self.mutation_rate * intensity
        self.value = max(0.0, min(1.0, self.value + delta))
        return self.value - old


@dataclass
class CognitiveGenome:
    """Complete cognitive genome encoding system behavior."""
    genome_id: str = ""
    parent_ids: List[str] = field(default_factory=list)
    generation: int = 0
    genes: Dict[str, Gene] = field(default_factory=dict)
    fitness: float = 0.0
    fitness_evaluated: bool = False
    created_at: float = field(default_factory=time.time)
    lineage_depth: int = 0

    def __post_init__(self):
        if not self.genome_id:
            self.genome_id = secrets.token_hex(6)
        if not self.genes:
            self.genes = self._default_genes()

    @staticmethod
    def _default_genes() -> Dict[str, Gene]:
        return {
            "reasoning_depth": Gene(name="reasoning_depth", value=0.6, mutation_rate=0.08),
            "exploration_rate": Gene(name="exploration_rate", value=0.3, mutation_rate=0.1),
            "confidence_threshold": Gene(name="confidence_threshold", value=0.7, mutation_rate=0.05),
            "verification_rigor": Gene(name="verification_rigor", value=0.8, mutation_rate=0.06),
            "deductive_bias": Gene(name="deductive_bias", value=0.5, mutation_rate=0.12),
            "inductive_bias": Gene(name="inductive_bias", value=0.5, mutation_rate=0.12),
            "risk_tolerance": Gene(name="risk_tolerance", value=0.3, mutation_rate=0.03),
            "safety_margin": Gene(name="safety_margin", value=0.9, mutation_rate=0.02, frozen=True),
            "novelty_seeking": Gene(name="novelty_seeking", value=0.4, mutation_rate=0.12),
            "patience": Gene(name="patience", value=0.6, mutation_rate=0.1),
        }

    def get_gene_value(self, name: str) -> float:
        gene = self.genes.get(name)
        return gene.denormalized if gene else 0.0

    def fingerprint(self) -> str:
        gene_str = "|".join(f"{k}:{g.value:.4f}" for k, g in sorted(self.genes.items()))
        return hashlib.sha256(gene_str.encode()).hexdigest()[:12]


@dataclass
class EvolutionResult:
    generation: int = 0
    population_size: int = 0
    best_fitness: float = 0.0
    avg_fitness: float = 0.0
    best_genome_id: str = ""
    mutations_applied: int = 0
    crossovers_performed: int = 0


class GenomeEvolver:
    """Evolutionary engine for breeding, mutating, and selecting genomes."""
    ELITE_RATIO = 0.2

    @classmethod
    def crossover(cls, parent_a: CognitiveGenome, parent_b: CognitiveGenome) -> CognitiveGenome:
        child = CognitiveGenome(
            parent_ids=[parent_a.genome_id, parent_b.genome_id],
            generation=max(parent_a.generation, parent_b.generation) + 1,
            lineage_depth=max(parent_a.lineage_depth, parent_b.lineage_depth) + 1,
        )
        gene_names = list(parent_a.genes.keys())
        crossover_point = secrets.randbelow(max(len(gene_names), 1))
        for i, name in enumerate(gene_names):
            source = parent_a if i < crossover_point else parent_b
            if name in source.genes:
                orig = source.genes[name]
                child.genes[name] = Gene(
                    name=orig.name, value=orig.value,
                    min_val=orig.min_val, max_val=orig.max_val,
                    mutation_rate=orig.mutation_rate, frozen=orig.frozen,
                )
        return child

    @classmethod
    def mutate(cls, genome: CognitiveGenome, intensity: float = 1.0) -> int:
        mutations = 0
        for gene in genome.genes.values():
            if not gene.frozen and secrets.randbelow(100) < int(gene.mutation_rate * 100 * intensity):
                gene.mutate(intensity)
                mutations += 1
        return mutations

    @classmethod
    def select(cls, population: List[CognitiveGenome], top_k: int) -> List[CognitiveGenome]:
        evaluated = [g for g in population if g.fitness_evaluated]
        evaluated.sort(key=lambda g: g.fitness, reverse=True)
        return evaluated[:top_k]


class CognitiveGenomeSystem:
    """
    Self-evolving architecture blueprint using genetic algorithms.

    Usage:
        system = CognitiveGenomeSystem()
        system.initialize(population_size=10)
        result = system.evolve(fitness_fn=lambda g: g.get_gene_value("reasoning_depth"))
        champion = system.get_champion()
    """

    def __init__(self, population_size: int = 10):
        self._population: List[CognitiveGenome] = []
        self._population_size = population_size
        self._generation: int = 0
        self._bank: List[CognitiveGenome] = []

    def initialize(self, population_size: Optional[int] = None) -> None:
        size = population_size or self._population_size
        self._population = []
        for _ in range(size):
            genome = CognitiveGenome(generation=0)
            GenomeEvolver.mutate(genome, intensity=0.5)
            self._population.append(genome)
        logger.info(f"CognitiveGenome: initialized population of {size}")

    def evolve(self, fitness_fn: Optional[Callable[[CognitiveGenome], float]] = None) -> EvolutionResult:
        self._generation += 1
        if fitness_fn:
            for genome in self._population:
                genome.fitness = fitness_fn(genome)
                genome.fitness_evaluated = True

        elite_count = max(2, int(len(self._population) * GenomeEvolver.ELITE_RATIO))
        elites = GenomeEvolver.select(self._population, elite_count)
        new_population = list(elites)
        total_mutations = 0
        total_crossovers = 0

        while len(new_population) < self._population_size:
            if len(elites) >= 2:
                idx_a = secrets.randbelow(len(elites))
                idx_b = secrets.randbelow(len(elites))
                while idx_b == idx_a and len(elites) > 1:
                    idx_b = secrets.randbelow(len(elites))
                child = GenomeEvolver.crossover(elites[idx_a], elites[idx_b])
                total_crossovers += 1
            else:
                child = CognitiveGenome(generation=self._generation)
            total_mutations += GenomeEvolver.mutate(child)
            child.generation = self._generation
            new_population.append(child)

        self._population = new_population
        self._bank.extend(new_population)

        fitnesses = [g.fitness for g in self._population if g.fitness_evaluated]
        best = max(self._population, key=lambda g: g.fitness) if fitnesses else self._population[0]

        return EvolutionResult(
            generation=self._generation,
            population_size=len(self._population),
            best_fitness=best.fitness if best.fitness_evaluated else 0.0,
            avg_fitness=sum(fitnesses) / max(len(fitnesses), 1),
            best_genome_id=best.genome_id,
            mutations_applied=total_mutations,
            crossovers_performed=total_crossovers,
        )

    def get_champion(self) -> Optional[CognitiveGenome]:
        evaluated = [g for g in self._population if g.fitness_evaluated]
        return max(evaluated, key=lambda g: g.fitness) if evaluated else None

    @property
    def population(self) -> List[CognitiveGenome]:
        return list(self._population)

    @property
    def generation(self) -> int:
        return self._generation

    def get_stats(self) -> Dict[str, Any]:
        fitnesses = [g.fitness for g in self._population if g.fitness_evaluated]
        return {
            "generation": self._generation,
            "population_size": len(self._population),
            "best_fitness": max(fitnesses) if fitnesses else 0.0,
            "avg_fitness": sum(fitnesses) / max(len(fitnesses), 1) if fitnesses else 0.0,
            "total_genes": len(CognitiveGenome._default_genes()),
        }
