"""
Agent Schemas — Pydantic I/O Contracts for Agent Interfaces
═══════════════════════════════════════════════════════════
Strict typed schemas with validation for every agent boundary.
Ensures deterministic, reproducible, and testable I/O.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════

class ProviderName(str, Enum):
    AUTO = "auto"
    GEMINI = "gemini"
    CLAUDE = "claude"
    CHATGPT = "chatgpt"


class ProcessingMode(str, Enum):
    DIRECT = "direct"
    THINKING = "thinking"
    QUICK_THINK = "quick_think"
    ERROR = "error"
    REFUSED = "refused"


class ToolCallStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"
    DENIED = "denied"


# ══════════════════════════════════════════════════════════════
# Request Schemas
# ══════════════════════════════════════════════════════════════

class AgentRequest(BaseModel):
    """Input contract for AgentController.process()."""
    user_input: str = Field(..., min_length=1, max_length=100_000,
                            description="The user's message or query")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()),
                            description="Session identifier for context persistence")
    use_thinking_loop: bool = Field(default=True,
                                    description="Whether to use the full thinking loop")
    max_tool_calls: int = Field(default=10, ge=0, le=100,
                                description="Maximum tool calls allowed")
    provider: ProviderName = Field(default=ProviderName.AUTO,
                                   description="LLM provider to use")

    model_config = {"json_schema_extra": {
        "examples": [{
            "user_input": "Write a fibonacci function in Python",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "use_thinking_loop": True,
            "max_tool_calls": 10,
            "provider": "auto",
        }]
    }}


class ChatRequest(BaseModel):
    """Simplified request for AgentController.chat()."""
    message: str = Field(..., min_length=1, max_length=50_000)
    session_id: Optional[str] = Field(default=None)


# ══════════════════════════════════════════════════════════════
# Tool Schemas
# ══════════════════════════════════════════════════════════════

class ToolCallRecord(BaseModel):
    """Record of a single tool invocation."""
    tool_name: str = Field(..., description="Name of the tool that was called")
    arguments: Dict[str, Any] = Field(default_factory=dict,
                                      description="Arguments passed to the tool")
    result: Any = Field(default=None, description="Result returned by the tool")
    status: ToolCallStatus = Field(default=ToolCallStatus.SUCCESS)
    duration_ms: float = Field(default=0.0, ge=0.0)
    error: str = Field(default="", description="Error message if status is ERROR")


class ToolPolicy(BaseModel):
    """Permission policy for a tool."""
    tool_name: str
    allowed: bool = True
    requires_approval: bool = False
    max_calls_per_session: int = Field(default=100, ge=0)
    denied_reason: str = ""


# ══════════════════════════════════════════════════════════════
# Thinking / Reasoning Schemas
# ══════════════════════════════════════════════════════════════

class ThinkingStepSchema(BaseModel):
    """Single iteration of the thinking loop."""
    iteration: int = Field(ge=0)
    candidate: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_delta: float = 0.0
    strategy_used: str = ""
    action_taken: str = ""
    improved: bool = False
    duration_ms: float = Field(default=0.0, ge=0.0)


class ThinkingTraceSchema(BaseModel):
    """Full trace of the thinking loop execution."""
    final_answer: str = ""
    final_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    iterations: int = Field(default=0, ge=0)
    mode: str = ""
    steps: List[ThinkingStepSchema] = Field(default_factory=list)
    total_duration_ms: float = Field(default=0.0, ge=0.0)
    domain: str = "general"
    strategies_used: List[str] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════
# Response Schemas
# ══════════════════════════════════════════════════════════════

class AgentResponse(BaseModel):
    """Output contract for AgentController.process()."""
    answer: str = Field(default="", description="The agent's response text")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0,
                              description="Calibrated confidence score")
    iterations: int = Field(default=0, ge=0,
                            description="Number of thinking loop iterations")
    duration_ms: float = Field(default=0.0, ge=0.0,
                               description="Total processing time in milliseconds")
    mode: ProcessingMode = Field(default=ProcessingMode.DIRECT,
                                 description="Processing mode used")
    tools_used: List[ToolCallRecord] = Field(default_factory=list)
    session_id: str = Field(default="")
    thinking_trace: Optional[ThinkingTraceSchema] = Field(
        default=None, description="Full thinking loop trace (if enabled)")
    loop_warnings: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ChatResponse(BaseModel):
    """Simplified response from AgentController.chat()."""
    answer: str
    session_id: str = ""


# ══════════════════════════════════════════════════════════════
# Session Schemas
# ══════════════════════════════════════════════════════════════

class SessionInfo(BaseModel):
    """Session metadata."""
    session_id: str
    created_at: datetime
    message_count: int = 0
    label: str = ""
    is_active: bool = True


class SessionMessage(BaseModel):
    """A single message in a session."""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
# Provider Schemas
# ══════════════════════════════════════════════════════════════

class ProviderInfo(BaseModel):
    """Provider status information."""
    name: str
    model: str
    active: bool = False
    calls: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0


class ProviderRegistryStatus(BaseModel):
    """Full registry status."""
    active_provider: Optional[str] = None
    providers: List[ProviderInfo] = Field(default_factory=list)
    failover_enabled: bool = True


# ══════════════════════════════════════════════════════════════
# Forge Schemas
# ══════════════════════════════════════════════════════════════

class ForgeAgentRequest(BaseModel):
    """Request to forge a new specialist agent."""
    capability_description: str = Field(..., min_length=10, max_length=5000)
    agent_name: Optional[str] = None
    test_queries: List[str] = Field(default_factory=list, max_length=10)


class ForgeAgentResponse(BaseModel):
    """Response from agent forge."""
    forge_id: str
    name: str
    domain: str
    is_active: bool
    justice_approved: bool
    test_results: List[Dict[str, Any]] = Field(default_factory=list)
