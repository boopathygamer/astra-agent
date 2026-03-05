"""
Brain Schemas — Pydantic I/O Contracts for Brain Subsystems
═══════════════════════════════════════════════════════════
Typed contracts for memory, reasoning, verification, and learning.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════════════
# Memory Schemas
# ══════════════════════════════════════════════════════════════

class MemoryTierEnum(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    FROZEN = "frozen"
    EVICTED = "evicted"


class FailureInput(BaseModel):
    """Input for storing a failure in the Bug Diary."""
    task: str = Field(..., min_length=1)
    observation: str = Field(default="", description="What was observed")
    root_cause: str = Field(default="", description="Deduced root cause")
    fix: str = Field(default="", description="Applied or suggested fix")
    category: str = Field(default="general")
    severity: float = Field(default=0.5, ge=0.0, le=1.0)


class FailureRecord(BaseModel):
    """Stored failure record."""
    id: str
    timestamp: float
    task: str
    observation: str
    root_cause: str
    fix: str
    category: str
    severity: float
    weight: float = 1.0
    times_retrieved: int = 0


class MemorySearchResult(BaseModel):
    """Result from memory search."""
    id: str
    content: str
    score: float = Field(ge=0.0, le=1.0)
    source: str = Field(description="failure, success, or principle")
    category: str = ""


class MemoryStats(BaseModel):
    """Memory system statistics."""
    total_failures: int = 0
    total_successes: int = 0
    total_principles: int = 0
    categories: Dict[str, int] = Field(default_factory=dict)
    vector_store_active: bool = False


# ══════════════════════════════════════════════════════════════
# Thinking Loop Schemas
# ══════════════════════════════════════════════════════════════

class ProblemDomainEnum(str, Enum):
    CODING = "coding"
    MATH = "math"
    LOGIC = "logic"
    DEBUGGING = "debugging"
    CREATIVE = "creative"
    SECURITY = "security"
    GENERAL = "general"


class ThinkingInput(BaseModel):
    """Input for the thinking loop."""
    problem: str = Field(..., min_length=1)
    action_type: str = Field(default="general")
    max_iterations: Optional[int] = Field(default=None, ge=1, le=20)


class ThinkingStepOutput(BaseModel):
    """Output of a single thinking step."""
    iteration: int = Field(ge=0)
    candidate: str = ""
    verification_passed: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_delta: float = 0.0
    strategy_used: str = ""
    improved: bool = False
    duration_ms: float = Field(default=0.0, ge=0.0)


class ThinkingOutput(BaseModel):
    """Output of the thinking loop."""
    final_answer: str
    final_confidence: float = Field(ge=0.0, le=1.0)
    iterations: int = Field(ge=0)
    domain: ProblemDomainEnum = ProblemDomainEnum.GENERAL
    steps: List[ThinkingStepOutput] = Field(default_factory=list)
    strategies_used: List[str] = Field(default_factory=list)
    total_duration_ms: float = Field(ge=0.0)


# ══════════════════════════════════════════════════════════════
# Verification / Risk Schemas
# ══════════════════════════════════════════════════════════════

class VerificationResult(BaseModel):
    """Result of multi-layer verification."""
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    static_score: float = Field(default=0.0, ge=0.0, le=1.0)
    property_score: float = Field(default=0.0, ge=0.0, le=1.0)
    scenario_score: float = Field(default=0.0, ge=0.0, le=1.0)
    critic_score: float = Field(default=0.0, ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    """Risk assessment for a proposed action."""
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: str = Field(pattern="^(low|medium|high|critical)$", default="low")
    should_sandbox: bool = False
    should_refuse: bool = False
    reasons: List[str] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════
# Reward / Learning Schemas
# ══════════════════════════════════════════════════════════════

class RewardDimensionSchema(BaseModel):
    """Single reward dimension."""
    name: str
    value: float = 0.0
    weight: float = 1.0
    is_primary: bool = False


class CompositeRewardSchema(BaseModel):
    """Multi-dimensional reward signal."""
    composite_score: float = Field(ge=0.0, le=1.0)
    normalized_score: float = Field(ge=0.0, le=1.0)
    dimensions: List[RewardDimensionSchema] = Field(default_factory=list)
    domain: str = "general"


class CalibrationInput(BaseModel):
    """Input for confidence calibration."""
    predicted_confidence: float = Field(ge=0.0, le=1.0)
    was_correct: bool
    domain: str = "general"
    task_type: str = ""


class CalibrationOutput(BaseModel):
    """Output from confidence calibration."""
    calibrated_confidence: float = Field(ge=0.0, le=1.0)
    reliability: float = Field(ge=0.0, le=1.0)
    ece: float = Field(ge=0.0, description="Expected Calibration Error")
    is_overconfident: bool = False
    is_underconfident: bool = False


# ══════════════════════════════════════════════════════════════
# ZK Proof Schemas
# ══════════════════════════════════════════════════════════════

class ExecutionStepSchema(BaseModel):
    """Single step in an integrity chain."""
    step_id: int
    operation: str
    input_hash: str
    output_hash: str
    timestamp: float


class ExecutionProofSchema(BaseModel):
    """Cryptographic execution proof."""
    proof_id: str
    root_hash: str
    step_count: int
    merkle_root: str
    valid: bool = False
    chain_intact: bool = False


# ══════════════════════════════════════════════════════════════
# Temporal Memory Schemas
# ══════════════════════════════════════════════════════════════

class TemporalMemoryInput(BaseModel):
    """Input for storing a temporal memory."""
    content: str = Field(..., min_length=1)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    domain: str = "general"
    tags: List[str] = Field(default_factory=list)
    decay_rate: float = Field(default=1.0, gt=0.0)


class TemporalMemoryItem(BaseModel):
    """A temporal memory item."""
    memory_id: str
    content: str
    tier: MemoryTierEnum
    importance: float
    effective_strength: float
    age_hours: float
    domain: str
    tags: List[str]


class TemporalMemoryStats(BaseModel):
    """Statistics for the temporal memory system."""
    total_memories: int = 0
    hot_count: int = 0
    warm_count: int = 0
    cold_count: int = 0
    frozen_count: int = 0
    evicted_total: int = 0
    resurrections_total: int = 0


# ══════════════════════════════════════════════════════════════
# Adversarial Testing Schemas
# ══════════════════════════════════════════════════════════════

class AdversarialTestInput(BaseModel):
    """Input for adversarial testing."""
    target_context: str = ""
    vulnerability_types: List[str] = Field(default_factory=list)


class AdversarialTestResult(BaseModel):
    """Result of a single adversarial test."""
    test_id: str
    attack_type: str
    passed: bool
    vulnerability_found: bool = False
    details: str = ""
    severity: int = Field(default=0, ge=0, le=4)


class AdversarialReportSchema(BaseModel):
    """Full adversarial testing report."""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    vulnerabilities_found: int = 0
    critical_vulnerabilities: int = 0
    robustness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    results: List[AdversarialTestResult] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
