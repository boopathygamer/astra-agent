"""
Tool Schemas — Pydantic I/O Contracts for Tool Registry
════════════════════════════════════════════════════════
Typed contracts for tool registration, execution, and policy enforcement.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════

class ToolCategory(str, Enum):
    SEARCH = "search"
    CODE = "code"
    FILE = "file"
    DATA = "data"
    DEVICE = "device"
    KNOWLEDGE = "knowledge"
    SECURITY = "security"
    CREATIVE = "creative"
    MATH = "math"
    SYSTEM = "system"


class ToolRiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyProfile(str, Enum):
    MINIMAL = "minimal"
    CODING = "coding"
    ASSISTANT = "assistant"
    FULL = "full"


# ══════════════════════════════════════════════════════════════
# Tool Definition Schemas
# ══════════════════════════════════════════════════════════════

class ToolParameter(BaseModel):
    """Definition of a tool parameter."""
    name: str
    type: str = Field(description="Expected type: str, int, float, bool, list, dict")
    required: bool = True
    default: Any = None
    description: str = ""


class ToolDefinition(BaseModel):
    """Complete tool definition for registry."""
    name: str = Field(..., pattern="^[a-z_][a-z0-9_]*$",
                      description="Tool name (snake_case)")
    description: str = Field(..., min_length=10)
    category: ToolCategory
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE
    parameters: List[ToolParameter] = Field(default_factory=list)
    requires_approval: bool = False
    max_calls_per_session: int = Field(default=100, ge=1)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


# ══════════════════════════════════════════════════════════════
# Tool Execution Schemas
# ══════════════════════════════════════════════════════════════

class ToolExecutionRequest(BaseModel):
    """Request to execute a tool."""
    tool_name: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    session_id: str = ""
    require_approval: bool = False


class ToolExecutionResult(BaseModel):
    """Result of tool execution."""
    tool_name: str
    success: bool
    result: Any = None
    error: str = ""
    duration_ms: float = Field(default=0.0, ge=0.0)
    was_sandboxed: bool = False
    threat_scan_result: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# Tool Forge Schemas
# ══════════════════════════════════════════════════════════════

class ForgeToolRequest(BaseModel):
    """Request to dynamically create a new tool."""
    description: str = Field(..., min_length=10, max_length=5000)
    tool_name: Optional[str] = None
    category: ToolCategory = ToolCategory.SYSTEM
    risk_level: ToolRiskLevel = ToolRiskLevel.MEDIUM


class ForgeToolResult(BaseModel):
    """Result of dynamic tool creation."""
    tool_name: str
    created: bool
    code: str = ""
    test_passed: bool = False
    safety_approved: bool = False
    error: str = ""


# ══════════════════════════════════════════════════════════════
# Threat Scanning Schemas
# ══════════════════════════════════════════════════════════════

class ThreatScanRequest(BaseModel):
    """Request to scan a target for threats."""
    target_path: str = Field(..., min_length=1)
    scan_archives: bool = True
    max_file_size_mb: int = Field(default=100, ge=1)


class ThreatEvidence(BaseModel):
    """Evidence supporting a threat detection."""
    layer: str
    rule_name: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    raw_match: str = ""


class ThreatScanResult(BaseModel):
    """Result of a threat scan."""
    scan_id: str
    target: str
    is_threat: bool = False
    threat_type: Optional[str] = None
    severity: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: List[ThreatEvidence] = Field(default_factory=list)
    file_hash: str = ""
    remediation_status: str = "pending"


class ThreatRemediationRequest(BaseModel):
    """Request to remediate a detected threat."""
    scan_id: str
    action: str = Field(..., pattern="^(quarantine|destroy|allow)$")
    confirm_destroy: bool = False
