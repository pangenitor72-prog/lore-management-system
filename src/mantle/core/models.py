"""
Data models for Lore Management System
Uses Pydantic for validation
"""

from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import field_validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum
import random # Added for PersonalityGenerator
import uuid # Added for Contradiction class


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
    AI_GENERATED = "AI_GENERATED"  # For entities created by AI during gameplay/ingestion

class PartyKnowledge(str, Enum):
    """Party knowledge level values."""
    KNOWN = "KNOWN"
    RUMORED = "RUMORED"
    SECRET = "SECRET"
    FORGOTTEN = "FORGOTTEN"


class LoreConfidence(str, Enum):
    """Confidence levels for lore entities (AI vs Human)."""
    HUMAN_APPROVED = "human_approved"       # Manually created/verified by DM
    AI_VERIFIED = "ai_verified"             # AI-generated, stable across sessions
    AI_GENERATED = "ai_generated"           # Recently AI-generated
    AI_FLAGGED = "ai_flagged"               # Has contradiction warnings


from src.mantle.core.config import CONFIDENCE_RULES

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

# ---------------- GAME SESSION MODELS ---------------- #

class InstanceResponse(BaseModel):
    """Generic model for any instance data that is a key-value store."""
    id: str = Field(..., description="Unique identifier for the instance")
    name: str = Field(..., description="Display name of the instance")
    type: str = Field(..., description="Type of instance (e.g., Character, Location)")
    # Allow arbitrary fields for flexibility
    model_config = ConfigDict(extra="allow")

class GameSessionResponse(BaseModel):
    """Model for game session responses."""
    session_id: str
    dm_id: str
    active_entities: List[InstanceResponse] = Field(default_factory=list)
    player_characters: List[InstanceResponse] = Field(default_factory=list)
    current_events: List[str] = Field(default_factory=list)
    world_state_summary: str
    campaign_name: str
    campaign_goal: str
    lore_accuracy_score: float
    active_contradictions_count: int
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True)

# ---------------- ERROR MODEL ---------------- #

class ErrorResponse(BaseModel):
    """Model for error responses."""
    error: str
    detail: Optional[str] = None

#==============================================================================
# NPC Personality System - OCEAN (Five-Factor) Model
#==============================================================================

class PersonalityArchetype(str, Enum):
    """Common NPC archetypes with preset OCEAN profiles."""
    MERCHANT = "merchant"
    GUARD = "guard"
    SCHOLAR = "scholar"
    NOBLE = "noble"
    CRIMINAL = "criminal"
    PRIEST = "priest"
    WARRIOR = "warrior"
    PEASANT = "peasant"


class OCEANProfile(BaseModel):
    """
    Five-Factor personality profile using Pydantic for validation.
    
    Each trait ranges from 0.0 to 1.0:
    - 0.0-0.3: Low (reserved, conventional, anxious, etc.)
    - 0.4-0.6: Moderate (balanced)
    - 0.7-1.0: High (creative, organized, outgoing, etc.)
    """
    openness: float = Field(ge=0.0, le=1.0)           # Creative, curious, imaginative (vs conventional, traditional)
    conscientiousness: float = Field(ge=0.0, le=1.0)  # Organized, reliable, disciplined (vs spontaneous, careless)
    extraversion: float = Field(ge=0.0, le=1.0)       # Outgoing, energetic, talkative (vs reserved, withdrawn)
    agreeableness: float = Field(ge=0.0, le=1.0)      # Cooperative, compassionate, trusting (vs competitive, skeptical)
    neuroticism: float = Field(ge=0.0, le=1.0)        # Anxious, sensitive, moody (vs confident, stable)
    
    model_config = ConfigDict(validate_assignment=True)

    @field_validator('openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism')
    @classmethod
    def validate_trait_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Trait value must be between 0.0 and 1.0, got {v}")
        return v
    
    def get_trait_descriptor(self, trait: str, value: float) -> str:
        """
        Get human-readable descriptor for a trait value.
        
        Args:
            trait: Trait name (e.g., 'openness')
            value: Trait value (0.0-1.0)
            
        Returns:
            Descriptor string
        """
        descriptors = {
            'openness': {
                'low': 'conventional and practical',
                'moderate': 'balanced between traditional and creative',
                'high': 'creative and curious'
            },
            'conscientiousness': {
                'low': 'spontaneous and flexible',
                'moderate': 'moderately organized',
                'high': 'disciplined and detail-oriented'
            },
            'extraversion': {
                'low': 'reserved and withdrawn',
                'moderate': 'socially balanced',
                'high': 'outgoing and energetic'
            },
            'agreeableness': {
                'low': 'skeptical and competitive',
                'moderate': 'pragmatically cooperative',
                'high': 'compassionate and trusting'
            },
            'neuroticism': {
                'low': 'confident and emotionally stable',
                'moderate': 'emotionally balanced',
                'high': 'anxious and sensitive'
            }
        }
        
        if value < 0.3:
            level = 'low'
        elif value < 0.7:
            level = 'moderate'
        else:
            level = 'high'
        
        return descriptors[trait][level]
    
    def get_behavioral_summary(self) -> str:
        """
        Get comprehensive behavioral description based on OCEAN traits.
        
        Returns:
            Natural language description of personality
        """
        traits = []
        
        # Focus on extreme traits (< 0.3 or > 0.7) for conciseness
        if self.openness < 0.3 or self.openness > 0.7:
            traits.append(self.get_trait_descriptor('openness', self.openness))
        
        if self.conscientiousness < 0.3 or self.conscientiousness > 0.7:
            traits.append(self.get_trait_descriptor('conscientiousness', self.conscientiousness))
        
        if self.extraversion < 0.3 or self.extraversion > 0.7:
            traits.append(self.get_trait_descriptor('extraversion', self.extraversion))
        
        if self.agreeableness < 0.3 or self.agreeableness > 0.7:
            traits.append(self.get_trait_descriptor('agreeableness', self.agreeableness))
        
        if self.neuroticism < 0.3 or self.neuroticism > 0.7:
            traits.append(self.get_trait_descriptor('neuroticism', self.neuroticism))
        
        if not traits:
            return "personality is balanced across all traits"
        
        return ", ".join(traits)
    
    def get_dialogue_style(self) -> str:
        """
        Get dialogue style guidance based on personality.
        
        Returns:
            String describing how this NPC should speak
        """
        styles = []
        
        # Extraversion affects verbosity
        if self.extraversion > 0.7:
            styles.append("talkative and eager to engage")
        elif self.extraversion < 0.3:
            styles.append("terse and needs prompting")
        
        # Agreeableness affects tone
        if self.agreeableness > 0.7:
            styles.append("warm and helpful")
        elif self.agreeableness < 0.3:
            styles.append("blunt and skeptical")
        
        # Neuroticism affects emotional expression
        if self.neuroticism > 0.7:
            styles.append("expresses worry or uncertainty")
        elif self.neuroticism < 0.3:
            styles.append("confident and assured")
        
        # Conscientiousness affects precision
        if self.conscientiousness > 0.7:
            styles.append("precise and detailed")
        elif self.conscientiousness < 0.3:
            styles.append("vague and casual")
        
        # Openness affects creativity of expression
        if self.openness > 0.7:
            styles.append("uses metaphors and colorful language")
        elif self.openness < 0.3:
            styles.append("straightforward and literal")
        
        return "; ".join(styles) if styles else "neutral conversational style"


class PersonalityTemplates:
    """Preset OCEAN profiles for common NPC archetypes."""
    
    TEMPLATES = {
        PersonalityArchetype.MERCHANT: OCEANProfile(
            openness=0.5,           # Moderate - open to deals but practical
            conscientiousness=0.7,  # High - organized, tracks inventory
            extraversion=0.6,       # Moderate-high - friendly but professional
            agreeableness=0.5,      # Moderate - fair but profit-motivated
            neuroticism=0.4         # Low-moderate - stable under pressure
        ),
        
        PersonalityArchetype.GUARD: OCEANProfile(
            openness=0.3,           # Low - follows rules, traditional
            conscientiousness=0.8,  # High - disciplined, dutiful
            extraversion=0.4,       # Low-moderate - professional distance
            agreeableness=0.5,      # Moderate - fair but authoritative
            neuroticism=0.3         # Low - calm under pressure
        ),
        
        PersonalityArchetype.SCHOLAR: OCEANProfile(
            openness=0.8,           # High - curious, loves ideas
            conscientiousness=0.7,  # High - meticulous, detail-oriented
            extraversion=0.4,       # Low-moderate - introverted but passionate
            agreeableness=0.6,      # Moderate-high - collaborative
            neuroticism=0.5         # Moderate - anxious about accuracy
        ),
        
        PersonalityArchetype.NOBLE: OCEANProfile(
            openness=0.6,           # Moderate-high - cultured, refined
            conscientiousness=0.6,  # Moderate-high - proper, maintains image
            extraversion=0.7,       # High - socially confident
            agreeableness=0.4,      # Low-moderate - entitled, expects deference
            neuroticism=0.3         # Low - poised, controlled
        ),
        
        PersonalityArchetype.CRIMINAL: OCEANProfile(
            openness=0.6,           # Moderate-high - creative problem-solving
            conscientiousness=0.3,  # Low - flexible morals, opportunistic
            extraversion=0.5,       # Moderate - adaptable socially
            agreeableness=0.3,      # Low - self-interested, manipulative
            neuroticism=0.6         # Moderate-high - paranoid, wary
        ),
        
        PersonalityArchetype.PRIEST: OCEANProfile(
            openness=0.5,           # Moderate - tradition balanced with compassion
            conscientiousness=0.7,  # High - devoted, ritualistic
            extraversion=0.6,       # Moderate-high - comforting presence
            agreeableness=0.8,      # High - compassionate, serving
            neuroticism=0.4         # Low-moderate - calm, reassuring
        ),
        
        PersonalityArchetype.WARRIOR: OCEANProfile(
            openness=0.4,           # Low-moderate - practical, tactical
            conscientiousness=0.6,  # Moderate-high - disciplined training
            extraversion=0.6,       # Moderate-high - camaraderie, leadership
            agreeableness=0.4,      # Low-moderate - competitive, honor-bound
            neuroticism=0.3         # Low - brave, steady
        ),
        
        PersonalityArchetype.PEASANT: OCEANProfile(
            openness=0.4,           # Low-moderate - traditional, superstitious
            conscientiousness=0.6,  # Moderate-high - hardworking, dutiful
            extraversion=0.5,       # Moderate - community-oriented
            agreeableness=0.7,      # High - cooperative, humble
            neuroticism=0.6         # Moderate-high - worried about survival
        )
    }
    
    @staticmethod
    def get_template(archetype: PersonalityArchetype) -> OCEANProfile:
        """Get preset profile for archetype."""
        return PersonalityTemplates.TEMPLATES[archetype]
    
    @staticmethod
    def get_archetype_from_role(role: str) -> Optional[PersonalityArchetype]:
        """
        Infer archetype from role description.
        
        Args:
            role: Role string (e.g., "merchant", "city guard", "scholar")
            
        Returns:
            Matching archetype or None
        """
        role_lower = role.lower()
        
        # Map role keywords to archetypes
        mappings = {
            PersonalityArchetype.MERCHANT: ['merchant', 'trader', 'shopkeeper', 'vendor', 'innkeeper'],
            PersonalityArchetype.GUARD: ['guard', 'soldier', 'sentry', 'watchman', 'captain'],
            PersonalityArchetype.SCHOLAR: ['scholar', 'sage', 'researcher', 'academic', 'librarian', 'wizard', 'mage'],
            PersonalityArchetype.NOBLE: ['noble', 'lord', 'lady', 'aristocrat', 'baron', 'duke', 'count', 'king', 'queen'],
            PersonalityArchetype.CRIMINAL: ['thief', 'criminal', 'bandit', 'smuggler', 'assassin', 'rogue'],
            PersonalityArchetype.PRIEST: ['priest', 'cleric', 'monk', 'priestess', 'healer', 'acolyte'],
            PersonalityArchetype.WARRIOR: ['warrior', 'fighter', 'knight', 'mercenary', 'barbarian', 'paladin'],
            PersonalityArchetype.PEASANT: ['peasant', 'farmer', 'commoner', 'laborer', 'servant', 'villager']
        }
        
        for archetype, keywords in mappings.items():
            if any(keyword in role_lower for keyword in keywords):
                return archetype
        
        return None


class PersonalityGenerator:
    """Generates OCEAN profiles for NPCs."""
    
    @staticmethod
    def generate_random(
        min_extreme_traits: int = 1,
        max_extreme_traits: int = 3
    ) -> OCEANProfile:
        """
        Generate a random personality with some extreme traits for memorability.
        
        Args:
            min_extreme_traits: Minimum number of traits that should be extreme (< 0.3 or > 0.7)
            max_extreme_traits: Maximum number of traits that should be extreme
            
        Returns:
            OCEAN profile with random values
        """
        
        traits = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
        values = {}
        
        # Determine how many traits will be extreme
        num_extreme = random.randint(min_extreme_traits, max_extreme_traits)
        extreme_traits = random.sample(traits, num_extreme)
        
        for trait in traits:
            if trait in extreme_traits:
                # Generate extreme value (< 0.3 or > 0.7)
                if random.random() < 0.5:
                    values[trait] = random.uniform(0.0, 0.3)
                else:
                    values[trait] = random.uniform(0.7, 1.0)
            else:
                # Generate moderate value (0.3-0.7)
                values[trait] = random.uniform(0.3, 0.7)
        
        return OCEANProfile(**values)

    @staticmethod
    def generate_from_archetype(archetype: PersonalityArchetype, variation: float = 0.1) -> OCEANProfile:
        """
        Generate personality based on an archetype with random variation.
        
        Args:
            archetype: Base archetype
            variation: Amount of random variation to apply (0.0-1.0)
            
        Returns:
            Varied OCEAN profile
        """
        template = PersonalityTemplates.get_template(archetype)
        values = {}
        
        for trait in ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']:
            base_val = getattr(template, trait)
            # Apply random variation centered on base value
            delta = random.uniform(-variation, variation)
            new_val = max(0.0, min(1.0, base_val + delta))
            values[trait] = new_val
            
        return OCEANProfile(**values)

    @staticmethod
    def generate_from_role(role: str, variation: float = 0.1) -> OCEANProfile:
        """
        Generate personality appropriate for a role/occupation.
        Falls back to balanced/random if role is unknown.
        """
        archetype = PersonalityTemplates.get_archetype_from_role(role)
        
        if archetype:
            return PersonalityGenerator.generate_from_archetype(archetype, variation)
        
        # Fallback: Generate a somewhat balanced random personality
        return PersonalityGenerator.generate_random(min_extreme_traits=0, max_extreme_traits=0)


class Contradiction:
    """Represents a detected contradiction."""

    def __init__(
        self,
        contradiction_type: str,
        severity: str,
        description: str,
        entity_ids: List[str],
        evidence: Dict
    ):
        self.type = contradiction_type
        self.severity = severity
        self.description = description
        self.entity_ids = entity_ids
        self.evidence = evidence

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "severity": self.severity,
            "description": self.description,
            "entity_ids": self.entity_ids,
            "evidence": self.evidence
        }