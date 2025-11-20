"""
Data models for Lore Management System
Uses Pydantic for validation
"""

from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import field_validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum

# ---------------- ENUMS ---------------- #

class EntityType(str, Enum):
    """Valid entity types."""
    CHARACTER = "Character"
    LOCATION = "Location"
    FACTION = "Faction"
    EVENT = "Event"
    ITEM = "Item"
    CONCEPT = "Concept"

class ApprovalStatus(str, Enum):
    """Approval status values."""
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"

class ConfidenceLevel(str, Enum):
    """Confidence level values."""
    CONFIRMED = "CONFIRMED"
    PROBABLE = "PROBABLE"
    SPECULATIVE = "SPECULATIVE"
    UNCERTAIN = "UNCERTAIN"

class PartyKnowledge(str, Enum):
    """Party knowledge level values."""
    KNOWN = "KNOWN"
    RUMORED = "RUMORED"
    SECRET = "SECRET"
    FORGOTTEN = "FORGOTTEN"

class ContradictionSeverity(str, Enum):
    """Severity levels for contradictions."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ContradictionStatus(str, Enum):
    """Status of contradiction in triage process."""
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

# ---------------- ENTITY MODELS ---------------- #

class EntityCreate(BaseModel):
    """Model for creating a new entity."""
    entity_type: EntityType
    canonical_name: str = Field(min_length=1, max_length=500)
    aliases: List[str] = Field(default_factory=list)
    approved_fields: Dict[str, Any] = Field(default_factory=dict) # Changed to Any for flexibility
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    confidence_level: ConfidenceLevel
    party_knowledge: PartyKnowledge

class EntityResponse(BaseModel):
    """Model for entity responses."""
    canon_id: str
    entity_type: EntityType
    canonical_name: str
    aliases: List[str]
    approved_fields: Dict[str, Any] # Changed to Any for flexibility
    approval_status: ApprovalStatus
    confidence_level: ConfidenceLevel
    party_knowledge: PartyKnowledge
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator('canonical_name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure canonical name is not empty after stripping."""
        if not v.strip():
            raise ValueError("Canonical name cannot be empty")
        return v.strip()

# ---------------- RELATIONSHIP MODELS ---------------- #

class RelationshipCreate(BaseModel):
    """Model for creating a relationship."""
    from_canon_id: str
    relationship_type: str = Field(min_length=1, max_length=100)
    to_canon_id: str
    confidence_level: ConfidenceLevel

class RelationshipResponse(BaseModel):
    """Model for relationship responses."""
    id: int
    from_canon_id: str
    relationship_type: str
    to_canon_id: str
    confidence_level: ConfidenceLevel
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ---------------- CONTRADICTION MODELS ---------------- #

class ContradictionCreate(BaseModel):
    """Model for adding contradiction to queue, from Auditor Agent."""
    contradiction_id: str = Field(..., description="UUID from Auditor")
    contradiction_type: str
    severity: ContradictionSeverity
    description: str
    evidence: Dict[str, Any] # JSON evidence from Auditor
    entity_ids: List[str]  = Field(default_factory=list, description="Canon IDs involved")
    detected_at: datetime = Field(default_factory=lambda: datetime.now(tz=datetime.now().astimezone().tzinfo)) # Ensure timezone-aware datetime
    status: ContradictionStatus = Field(default=ContradictionStatus.PENDING)

class ContradictionResponse(BaseModel):
    """Model for contradiction responses."""
    id: int
    contradiction_id: str
    contradiction_type: str
    severity: ContradictionSeverity
    description: str
    evidence: Dict[str, Any]
    detected_at: datetime
    status: ContradictionStatus
    created_at: datetime
    entity_ids: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class ContradictionUpdateRequest(BaseModel):
    """
    Payload for resolving or dismissing a contradiction.
    Matches the service spec: (id, user, notes) -> bool
    """
    user: str = Field(default="Human Reviewer", description="Actor performing the action.")
    notes: str = Field(..., min_length=1, description="Required notes explaining the resolution or dismissal.")

# ---------------- TRIAGE ANALYSIS MODELS ---------------- #

class TriageAnalysisCreate(BaseModel):
    """Model for adding Claude's analysis."""
    contradiction_id: str
    analyst: str = "CLAUDE"
    analysis: str
    recommendation: str
    confidence: ContradictionSeverity # Use the Enum for consistency

class TriageAnalysisResponse(BaseModel):
    """Model for triage analysis responses."""
    id: int
    contradiction_id: str
    analyst: str
    analysis: str
    recommendation: str
    confidence: ContradictionSeverity
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ContradictionWithAnalysis(BaseModel):
    """Full contradiction with analysis (if exists)."""
    contradiction: ContradictionResponse
    analysis: Optional[TriageAnalysisResponse] = None

# ---------------- ERROR MODEL ---------------- #

class ErrorResponse(BaseModel):
    """Model for error responses."""
    error: str
    detail: Optional[str] = None
