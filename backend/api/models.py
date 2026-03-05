"""
Pydantic request/response models for the API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for continuity")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1, le=8192)
    use_thinking: bool = Field(True, description="Enable thinking loop")


class ChatResponse(BaseModel):
    answer: str
    confidence: float = 0.0
    iterations: int = 1
    mode: str = "direct"
    thinking_steps: List[str] = []
    tools_used: List[str] = []
    duration_ms: float = 0.0


# ──────────────────────────────────────────────
# Vision
# ──────────────────────────────────────────────

class VisionRequest(BaseModel):
    question: str = Field("Describe this image in detail.", description="Question about the image")
    mode: str = Field("general", description="Analysis mode: general, technical, medical, document, creative, code")
    chain_of_thought: bool = Field(True, description="Use step-by-step reasoning")
    max_tokens: Optional[int] = Field(None, ge=1, le=4096)


class VisionResponse(BaseModel):
    analysis: str
    mode: str
    confidence: float = 0.0
    duration_ms: float = 0.0


# ──────────────────────────────────────────────
# Agent
# ──────────────────────────────────────────────

class AgentTaskRequest(BaseModel):
    task: str = Field(..., description="Task for the agent to complete")
    use_thinking: bool = Field(True, description="Enable thinking loop")
    max_tool_calls: int = Field(10, ge=0, le=50)


class AgentTaskResponse(BaseModel):
    answer: str
    confidence: float = 0.0
    iterations: int = 0
    mode: str = "direct"
    tools_used: List[dict] = []
    thinking_trace: Optional[dict] = None
    duration_ms: float = 0.0


# ──────────────────────────────────────────────
# Memory
# ──────────────────────────────────────────────

class MemoryStatsResponse(BaseModel):
    total_failures: int = 0
    total_successes: int = 0
    regression_tests: int = 0
    category_weights: Dict[str, float] = {}
    most_retrieved: List[Any] = []


# ──────────────────────────────────────────────
# System
# ──────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    model_loaded: bool = False
    vision_ready: bool = False
    memory_entries: int = 0
    tools_available: int = 0
