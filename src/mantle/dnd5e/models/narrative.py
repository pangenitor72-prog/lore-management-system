# src/mantle/dnd5e/models/narrative.py
"""
Narrative Character Models

Models for the narrative-first character creation system.
Captures competencies (proven/untested/weak) and emotional friction points.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class CompetenceLevel(str, Enum):
    """The three levels of the competence spectrum."""
    PROVEN = "proven"      # Mastery - character succeeds at this domain
    UNTESTED = "untested"  # Capable but learning - failure teaches
    WEAK = "weak"          # Struggles - success is hard-won


# Core fixed domains that map cleanly to gameplay
CORE_DOMAINS = [
    "combat",    # Fighting, weapons, tactics
    "social",    # Persuasion, deception, intimidation, insight
    "stealth",   # Sneaking, infiltration, theft
    "magic",     # Spellcasting, arcane/divine knowledge
    "knowledge", # Lore, history, investigation, medicine
    "survival",  # Nature, tracking, endurance, athletics
]


class Competency(BaseModel):
    """
    A domain of competence for a character.

    Maps to the V3.0 DM prompt's competence spectrum:
    - PROVEN: Character succeeds. Challenge through situation, not skill.
    - UNTESTED: Capable but learning. Failure is revelation, not punishment.
    - WEAK: Success is hard-won. Weakness creates interesting constraints.
    """
    domain: str = Field(
        ...,
        description="The competency domain (combat, social, stealth, magic, knowledge, survival, or custom)"
    )
    level: CompetenceLevel = Field(
        ...,
        description="The character's competence level in this domain"
    )
    evidence: str = Field(
        default="",
        description="Quote or reference from description that supports this competency"
    )
    dm_guidance: str = Field(
        default="",
        description="How the DM should handle this competency in play"
    )
    is_custom: bool = Field(
        default=False,
        description="True if this is a custom domain (not one of the 6 core domains)"
    )

    def get_default_guidance(self) -> str:
        """Get default DM guidance based on competence level."""
        guidance_map = {
            CompetenceLevel.PROVEN: f"Character succeeds at {self.domain}. Challenge through situation, not skill checks.",
            CompetenceLevel.UNTESTED: f"Capable at {self.domain} but still learning. Failure teaches - make it revelation, not punishment.",
            CompetenceLevel.WEAK: f"Struggles with {self.domain}. Success is hard-won. Let weakness create interesting constraints.",
        }
        return guidance_map.get(self.level, "")


class FrictionPointCategory(str, Enum):
    """Categories of emotional friction points."""
    PROTECTS = "protects"  # What they would sacrifice everything for
    LOST = "lost"          # What absence still haunts them
    AVOIDS = "avoids"      # What truth they refuse to face
    BELIEVES = "believes"  # What conviction shapes their actions


class FrictionPoint(BaseModel):
    """
    An emotional friction point for a character.

    These are the places where narrative pressure produces response.
    The DM uses these to make the story personal.
    """
    category: FrictionPointCategory = Field(
        ...,
        description="The type of friction point"
    )
    target: str = Field(
        ...,
        description="The specific thing, person, ideal, or truth"
    )
    intensity: str = Field(
        default="significant",
        description="How central this is to the character: central, significant, or minor"
    )
    narrative_hook: str = Field(
        default="",
        description="How the DM might engage this friction point"
    )

    def get_default_hook(self) -> str:
        """Get default narrative hook based on category."""
        hook_map = {
            FrictionPointCategory.PROTECTS: f"Put {self.target} under pressure. Not constant threat, but meaningful risk.",
            FrictionPointCategory.LOST: f"Offer echoes of {self.target}. Chances to save what they couldn't before.",
            FrictionPointCategory.AVOIDS: f"Let the tension around {self.target} build. The confrontation will be powerful.",
            FrictionPointCategory.BELIEVES: f"Test their belief in {self.target}. Challenge it. Make them prove it or question it.",
        }
        return hook_map.get(self.category, "")


class CharacterExtraction(BaseModel):
    """
    The result of AI extraction from a character description.

    Contains competencies, friction points, and mechanical mappings
    that the player can confirm or adjust.
    """
    # Character identity
    name: Optional[str] = Field(default=None, description="Extracted character name")
    origin_id: Optional[str] = Field(default=None, description="Recommended origin from world options")
    archetype_id: Optional[str] = Field(default=None, description="Recommended archetype from world options")

    # Narrative elements
    competencies: List[Competency] = Field(
        default_factory=list,
        description="Extracted competency spectrum"
    )
    friction_points: List[FrictionPoint] = Field(
        default_factory=list,
        description="Extracted emotional friction points"
    )

    # Mechanical mappings (derived from competencies)
    ability_priorities: List[str] = Field(
        default_factory=list,
        description="Suggested ability score priority order"
    )
    suggested_skills: List[str] = Field(
        default_factory=list,
        description="Skills that fit the character concept"
    )

    # Personality synthesis (for legacy compatibility)
    personality_traits: List[str] = Field(default_factory=list)
    ideals: List[str] = Field(default_factory=list)
    bonds: List[str] = Field(default_factory=list)
    flaws: List[str] = Field(default_factory=list)

    # Metadata
    backstory_summary: str = Field(
        default="",
        description="AI-generated backstory summary"
    )
    extraction_confidence: float = Field(
        default=0.0,
        description="AI confidence in the extraction (0.0-1.0)"
    )


# Domain to ability score mapping for mechanical inference
DOMAIN_ABILITY_MAP = {
    "combat": ["strength", "dexterity", "constitution"],
    "social": ["charisma", "wisdom"],
    "stealth": ["dexterity", "intelligence"],
    "magic": ["intelligence", "wisdom", "charisma"],
    "knowledge": ["intelligence", "wisdom"],
    "survival": ["wisdom", "constitution", "strength"],
}

# Domain to skill mapping for suggestions
DOMAIN_SKILL_MAP = {
    "combat": ["athletics", "acrobatics", "intimidation"],
    "social": ["persuasion", "deception", "insight", "performance"],
    "stealth": ["stealth", "sleight_of_hand", "perception"],
    "magic": ["arcana", "religion", "history"],
    "knowledge": ["history", "investigation", "medicine", "nature", "religion"],
    "survival": ["survival", "nature", "athletics", "perception"],
}
