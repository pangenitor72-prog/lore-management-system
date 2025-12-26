"""
Ability/Power definitions for the d20 rules engine.

Abilities are special powers characters can use - spells in fantasy,
tech abilities in sci-fi, special skills in modern settings.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AbilityType(str, Enum):
    """Types of abilities."""
    CANTRIP = "cantrip"      # At-will powers
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"
    PASSIVE = "passive"      # Always-on abilities
    ENCOUNTER = "encounter"  # Once per encounter/short rest
    DAILY = "daily"          # Once per long rest


class TargetType(str, Enum):
    """Who/what can be targeted."""
    SELF = "self"
    SINGLE = "single"
    AREA = "area"
    CONE = "cone"
    LINE = "line"


class AbilityData(BaseModel):
    """
    Ability/power definition.

    Generic base class for spells, tech abilities, special skills, etc.
    """
    id: str
    display_name: str
    description: str
    ability_type: AbilityType
    power_cost: int = 0  # Spell slot level or resource cost
    range_feet: int = 0  # 0 = self/touch
    target_type: TargetType = TargetType.SINGLE
    damage_dice: Optional[str] = None  # e.g., "1d8", "2d6"
    damage_type: Optional[str] = None  # e.g., "fire", "psychic", "kinetic"
    healing_dice: Optional[str] = None  # For healing abilities
    save_ability: Optional[str] = None  # What save to make
    duration: str = "instant"  # "instant", "1 minute", "concentration"
    requires_concentration: bool = False

    # Scaling
    scales_with_level: bool = False
    scaling_dice: Optional[str] = None

    # For character creation
    archetypes: List[str] = Field(default_factory=list)  # Which archetypes can learn this

    # Genre metadata
    genre: str = "generic"
    flavor_text: str = ""


# =============================================================================
# FANTASY ABILITIES (D&D Spells)
# =============================================================================

FANTASY_ABILITIES: Dict[str, AbilityData] = {
    # Cantrips
    "fire_bolt": AbilityData(
        id="fire_bolt",
        display_name="Fire Bolt",
        description="Hurl a mote of fire at a creature or object within range.",
        ability_type=AbilityType.CANTRIP,
        range_feet=120,
        target_type=TargetType.SINGLE,
        damage_dice="1d10",
        damage_type="fire",
        scales_with_level=True,
        scaling_dice="1d10",
        archetypes=["wizard"],
        genre="fantasy",
        flavor_text="A bolt of flame streaks toward your target.",
    ),
    "sacred_flame": AbilityData(
        id="sacred_flame",
        display_name="Sacred Flame",
        description="Flame-like radiance descends on a creature you can see.",
        ability_type=AbilityType.CANTRIP,
        range_feet=60,
        target_type=TargetType.SINGLE,
        damage_dice="1d8",
        damage_type="radiant",
        save_ability="dexterity",
        scales_with_level=True,
        archetypes=["cleric"],
        genre="fantasy",
        flavor_text="Divine light burns the wicked.",
    ),
    "light": AbilityData(
        id="light",
        display_name="Light",
        description="Touch an object to make it shed bright light.",
        ability_type=AbilityType.CANTRIP,
        range_feet=0,
        target_type=TargetType.SINGLE,
        duration="1 hour",
        archetypes=["cleric", "wizard"],
        genre="fantasy",
        flavor_text="The object glows with magical illumination.",
    ),
    # Level 1 Spells
    "magic_missile": AbilityData(
        id="magic_missile",
        display_name="Magic Missile",
        description="Create three darts of magical force that automatically hit.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=120,
        target_type=TargetType.SINGLE,
        damage_dice="3d4+3",
        damage_type="force",
        archetypes=["wizard"],
        genre="fantasy",
        flavor_text="Darts of magical force unerringly strike their targets.",
    ),
    "cure_wounds": AbilityData(
        id="cure_wounds",
        display_name="Cure Wounds",
        description="Touch a creature to restore hit points.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=0,
        target_type=TargetType.SINGLE,
        healing_dice="1d8",
        archetypes=["cleric"],
        genre="fantasy",
        flavor_text="Divine energy flows into the wounded creature.",
    ),
    "shield_of_faith": AbilityData(
        id="shield_of_faith",
        display_name="Shield of Faith",
        description="A shimmering field grants +2 AC to a creature.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=60,
        target_type=TargetType.SINGLE,
        duration="10 minutes",
        requires_concentration=True,
        archetypes=["cleric"],
        genre="fantasy",
        flavor_text="A protective shimmer surrounds the target.",
    ),
}


# =============================================================================
# SCI-FI ABILITIES (Tech Powers)
# =============================================================================

SCIFI_ABILITIES: Dict[str, AbilityData] = {
    # At-will tech
    "energy_bolt": AbilityData(
        id="energy_bolt",
        display_name="Energy Bolt",
        description="Fire a concentrated energy beam from your neural interface.",
        ability_type=AbilityType.CANTRIP,
        range_feet=100,
        target_type=TargetType.SINGLE,
        damage_dice="1d10",
        damage_type="energy",
        scales_with_level=True,
        archetypes=["hacker"],
        genre="scifi",
        flavor_text="Your cybernetics discharge a focused energy beam.",
    ),
    "scan": AbilityData(
        id="scan",
        display_name="Scan",
        description="Analyze a target to reveal its systems and weaknesses.",
        ability_type=AbilityType.CANTRIP,
        range_feet=60,
        target_type=TargetType.SINGLE,
        duration="instant",
        archetypes=["hacker", "medic"],
        genre="scifi",
        flavor_text="Your HUD highlights tactical information.",
    ),
    # Level 1 tech
    "system_shock": AbilityData(
        id="system_shock",
        display_name="System Shock",
        description="Overload a target's electronics with a neural spike.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=60,
        target_type=TargetType.SINGLE,
        damage_dice="3d4+3",
        damage_type="electric",
        archetypes=["hacker"],
        genre="scifi",
        flavor_text="Systems overload in a cascade of sparks.",
    ),
    "medpac": AbilityData(
        id="medpac",
        display_name="MedPac Injection",
        description="Administer emergency medical treatment to restore health.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=0,
        target_type=TargetType.SINGLE,
        healing_dice="1d8",
        archetypes=["medic"],
        genre="scifi",
        flavor_text="Nanobots begin repairing damaged tissue.",
    ),
    "shield_boost": AbilityData(
        id="shield_boost",
        display_name="Shield Boost",
        description="Temporarily enhance a target's personal shield.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=30,
        target_type=TargetType.SINGLE,
        duration="10 minutes",
        requires_concentration=True,
        archetypes=["medic", "hacker"],
        genre="scifi",
        flavor_text="Shield harmonics amplified.",
    ),
}


# =============================================================================
# MODERN/HORROR ABILITIES (Special Skills)
# =============================================================================

MODERN_ABILITIES: Dict[str, AbilityData] = {
    # Passive/at-will
    "keen_eye": AbilityData(
        id="keen_eye",
        display_name="Keen Eye",
        description="Your trained eye catches details others miss.",
        ability_type=AbilityType.PASSIVE,
        archetypes=["detective"],
        genre="modern",
        flavor_text="You notice what others overlook.",
    ),
    "first_aid": AbilityData(
        id="first_aid",
        display_name="First Aid",
        description="Apply emergency medical care to stabilize wounds.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=0,
        target_type=TargetType.SINGLE,
        healing_dice="1d6",
        archetypes=["doctor", "soldier"],
        genre="modern",
        flavor_text="You apply pressure and bandages quickly.",
    ),
    # Limited use
    "adrenaline_surge": AbilityData(
        id="adrenaline_surge",
        display_name="Adrenaline Surge",
        description="Push through pain and exhaustion for a burst of action.",
        ability_type=AbilityType.DAILY,
        power_cost=1,
        target_type=TargetType.SELF,
        duration="1 round",
        archetypes=["soldier"],
        genre="modern",
        flavor_text="Your heart pounds as everything sharpens.",
    ),
    "analyze_evidence": AbilityData(
        id="analyze_evidence",
        display_name="Analyze Evidence",
        description="Carefully examine evidence to reveal hidden information.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        target_type=TargetType.SINGLE,
        archetypes=["detective", "doctor"],
        genre="modern",
        flavor_text="The pieces start to come together.",
    ),
}


# =============================================================================
# ABILITY REGISTRY
# =============================================================================

ABILITIES_BY_GENRE: Dict[str, Dict[str, AbilityData]] = {
    "fantasy": FANTASY_ABILITIES,
    "scifi": SCIFI_ABILITIES,
    "modern": MODERN_ABILITIES,
    "horror": MODERN_ABILITIES,
}


def get_ability(ability_id: str, genre: str = "fantasy") -> Optional[AbilityData]:
    """Get ability data by ID and genre."""
    genre_abilities = ABILITIES_BY_GENRE.get(genre, FANTASY_ABILITIES)
    return genre_abilities.get(ability_id)


def get_abilities_for_genre(genre: str = "fantasy") -> List[AbilityData]:
    """Get all available abilities for a genre."""
    genre_abilities = ABILITIES_BY_GENRE.get(genre, FANTASY_ABILITIES)
    return list(genre_abilities.values())


def get_abilities_for_archetype(archetype_id: str, genre: str = "fantasy") -> List[AbilityData]:
    """Get abilities available to a specific archetype."""
    genre_abilities = ABILITIES_BY_GENRE.get(genre, FANTASY_ABILITIES)
    return [
        ability for ability in genre_abilities.values()
        if archetype_id in ability.archetypes
    ]


def get_cantrips_for_archetype(archetype_id: str, genre: str = "fantasy") -> List[AbilityData]:
    """Get at-will abilities for an archetype."""
    return [
        ability for ability in get_abilities_for_archetype(archetype_id, genre)
        if ability.ability_type == AbilityType.CANTRIP
    ]


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

# Spell aliases for fantasy compatibility
Spell = AbilityData
SPELLS = FANTASY_ABILITIES


def get_spell(spell_id: str) -> Optional[AbilityData]:
    """Backward compatible: get spell by ID."""
    return FANTASY_ABILITIES.get(spell_id)


def get_all_spells() -> List[AbilityData]:
    """Backward compatible: get all fantasy spells."""
    return list(FANTASY_ABILITIES.values())
