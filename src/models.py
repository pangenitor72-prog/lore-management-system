"""
Data models for Lore Management System
Uses Pydantic for validation
"""
"""
Models module for Lore Management System
Uses Pydantic for validation
"""

from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import field_validator
from typing import Optional, Dict, List
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


class Config:
    from_attributes = True


# ------------------------------------------------------------
# PHASE V - TRIAGE QUEUE SYSTEM MODELS
# Added: October 27, 2025
# ------------------------------------------------------------
from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional
from typing import Optional, List
from datetime import datetime


# -------------------------------
# ENUMS
# -------------------------------
class ContradictionSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ContradictionStatus(str, Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


# -------------------------------
# CONTRADICTION MODELS
# -------------------------------

class ContradictionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore", kw_only=True)

    contradiction_id: str = Field(..., description="UUID for contradiction")
    contradiction_type: str
    severity: ContradictionSeverity
    description: str
    evidence: dict = Field(default_factory=dict)

    detected_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when contradiction was detected"
    )

    status: ContradictionStatus = Field(       # ✅ use Enum, not str
    default=ContradictionStatus.PENDING,
    description="Current status of the contradiction"
)

    related_entities: Optional[List[str]] = Field(
        default=None,
        description="List of related entity IDs"
    )
# -------------------------------
# TRIAGE ANALYSIS MODELS
# -------------------------------
class TriageAnalysisCreate(BaseModel):
    contradiction_id: str
    analyst: str = Field(default="CLAUDE")
    analysis: str
    recommendation: str
    confidence: ContradictionSeverity


class TriageAnalysisResponse(TriageAnalysisCreate):
    id: int
    analyzed_at: datetime


# -------------------------------
# RELATIONAL / AGGREGATED VIEWS
# -------------------------------
class ContradictionResponse(BaseModel):
    contradiction_id: str
    message: str = "Analysis pending"

class ContradictionWithAnalysis(BaseModel):
    contradiction: ContradictionResponse
    analysis: Optional[TriageAnalysisResponse] = None
    related_entities: Optional[List[str]] = None

    class Config:
        orm_mode = True



class PartyKnowledge(str, Enum):
    """Party knowledge level values."""
    KNOWN = "KNOWN"
    RUMORED = "RUMORED"
    SECRET = "SECRET"
    FORGOTTEN = "FORGOTTEN"


class ContradictionSeverity(str, Enum):
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'


class ContradictionStatus(str, Enum):
    PENDING = 'PENDING'
    IN_REVIEW = 'IN_REVIEW'
    RESOLVED = 'RESOLVED'
    DISMISSED = 'DISMISSED'




# ---------------- ENTITY MODELS ---------------- #

class EntityCreate(BaseModel):
    """Model for creating a new entity."""
    entity_type: EntityType
    canonical_name: str = Field(min_length=1, max_length=500)
    aliases: List[str] = Field(default_factory=list)
    approved_fields: Dict[str, str] = Field(default_factory=dict)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    confidence_level: ConfidenceLevel
    party_knowledge: PartyKnowledge


class EntityResponse(BaseModel):
    """Model for entity responses."""
    canon_id: str
    entity_type: EntityType
    canonical_name: str
    aliases: List[str]
    approved_fields: Dict[str, str]
    approval_status: ApprovalStatus
    confidence_level: ConfidenceLevel
    party_knowledge: PartyKnowledge
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

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

    model_config = {"from_attributes": True}


# ---------------- CONTRADICTION MODELS ---------------- #

class ContradictionCreate(BaseModel):
    contradiction_id: Optional[str] = None  # ← make optional
    contradiction_type: str
    severity: ContradictionSeverity
    description: str
    evidence: dict
    detected_at: datetime
    related_entities: list[str]


class ContradictionResponse(BaseModel):
    contradiction_id: str
    contradiction_type: str
    severity: ContradictionSeverity
    description: str
    evidence: dict
    detected_at: datetime
    status: ContradictionStatus
    created_at: datetime
    involved_entities: Optional[List[str]] = None


# ---------------- TRIAGE MODELS ---------------- #

class TriageAnalysisCreate(BaseModel):
    analyst: str = "CLAUDE"
    analysis: str
    recommendation: str
    confidence: ConfidenceLevel


class TriageAnalysisResponse(BaseModel):
    contradiction_id: str
    analyst: str
    analysis: str
    recommendation: str
    confidence: ConfidenceLevel
    analyzed_at: datetime


class ContradictionWithAnalysis(BaseModel):
    contradiction: ContradictionResponse
    analysis: Optional[TriageAnalysisResponse]


# ---------------- ERROR MODEL ---------------- #

class ErrorResponse(BaseModel):
    """Model for error responses."""
    error: str
    detail: Optional[str] = None

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class ContradictionSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ContradictionStatus(str, Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ContradictionCreate(BaseModel):
    contradiction_id: str = Field(..., description="UUID for contradiction")
    contradiction_type: str
    severity: ContradictionSeverity
    description: str
    evidence: dict = Field(default_factory=dict)
    detected_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    status: ContradictionStatus = Field(default=ContradictionStatus.PENDING)
    related_entities: Optional[List[str]] = None

    # === Phase VIII ===
from pydantic import BaseModel, Field

class ContradictionUpdateRequest(BaseModel):
    """
    Payload for resolving or dismissing a contradiction.
    Matches the service spec: (id, user, notes) -> bool
    """
    user: str = Field(default="Human Reviewer", description="Actor performing the action.")
    notes: str = Field(..., min_length=1, description="Required notes explaining the resolution or dismissal.")

# src/models.py
from pydantic import BaseModel
from typing import List, Optional, Any # Make sure Optional is imported
from datetime import datetime

class Contradiction(BaseModel):
    id: int
    status: str
    confidence: Optional[float] = None  # <-- MAKE THIS CHANGE
    created_at: datetime

# --- Triage Queue System Models ---

class ContradictionStatus(str, Enum):
    """Status of contradiction in triage process."""
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

class ContradictionSeverity(str, Enum):
    """Severity levels matching Auditor Agent."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ContradictionCreate(BaseModel):
    """Model for adding contradiction to queue."""
    contradiction_id: str = Field(..., description="UUID from Auditor")
    contradiction_type: str
    severity: ContradictionSeverity
    description: str
    evidence: dict  # JSON evidence from Auditor
    entity_ids: list[str]  # Canon IDs involved
    detected_at: datetime

class ContradictionResponse(BaseModel):
    """Model for contradiction responses."""
    id: int
    contradiction_id: str
    contradiction_type: str
    severity: ContradictionSeverity
    description: str
    evidence: dict
    detected_at: datetime
    status: ContradictionStatus
    created_at: datetime
    entity_ids: list[str]

    model_config = {"from_attributes": True}

class TriageAnalysisCreate(BaseModel):
    """Model for adding Claude's analysis."""
    contradiction_id: str
    analyst: str = "CLAUDE"
    analysis: str
    recommendation: str
    confidence: str = Field(..., pattern="^(HIGH|MEDIUM|LOW)$")

class TriageAnalysisResponse(BaseModel):
    """Model for triage analysis responses."""
    id: int
    contradiction_id: str
    analyst: str
    analysis: str
    recommendation: str
    confidence: str
    analyzed_at: datetime

    model_config = {"from_attributes": True}

class ContradictionWithAnalysis(BaseModel):
    """Full contradiction with analysis (if exists)."""
    contradiction: ContradictionResponse
    analysis: Optional[TriageAnalysisResponse] = None