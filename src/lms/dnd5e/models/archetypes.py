"""
Archetype definitions for the d20 rules engine.

Archetypes define a character's role and abilities - their profession,
class, or specialty. In fantasy this is "Class", in sci-fi "Role".
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class HitDie(str, Enum):
    """Hit dice types (health per level)."""
    D6 = "d6"
    D8 = "d8"
    D10 = "d10"
    D12 = "d12"


class ArchetypeData(BaseModel):
    """
    Archetype definition with features and progression.

    Generic base class that works across all genres.
    """
    id: str
    display_name: str
    description: str
    hit_die: HitDie
    primary_ability: str
    saving_throw_proficiencies: List[str] = Field(default_factory=list)
    armor_proficiencies: List[str] = Field(default_factory=list)
    weapon_proficiencies: List[str] = Field(default_factory=list)
    skill_choices: List[str] = Field(default_factory=list)
    num_skill_choices: int = 2
    features_by_level: Dict[int, List[str]] = Field(default_factory=dict)

    # Powers/abilities (spells in fantasy, tech in sci-fi)
    has_powers: bool = False
    power_ability: Optional[str] = None
    cantrips_known: int = 0
    power_slots_by_level: Dict[int, Dict[int, int]] = Field(default_factory=dict)

    # For guided/concept mode
    playstyle_hint: str = ""
    suggested_origins: List[str] = Field(default_factory=list)

    # Genre metadata
    genre: str = "generic"


# =============================================================================
# FANTASY ARCHETYPES (D&D 5e Classes)
# =============================================================================

class FantasyArchetype(str, Enum):
    """Fantasy genre archetypes (D&D classes)."""
    FIGHTER = "fighter"
    ROGUE = "rogue"
    CLERIC = "cleric"
    WIZARD = "wizard"


FANTASY_ARCHETYPES: Dict[str, ArchetypeData] = {
    "fighter": ArchetypeData(
        id="fighter",
        display_name="Fighter",
        description="A master of martial combat, skilled with weapons and armor.",
        hit_die=HitDie.D10,
        primary_ability="strength",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium", "heavy", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["acrobatics", "animal_handling", "athletics", "history",
                       "insight", "intimidation", "perception", "survival"],
        num_skill_choices=2,
        features_by_level={
            1: ["Fighting Style", "Second Wind"],
            2: ["Action Surge (1 use)"],
            3: ["Martial Archetype"],
        },
        has_powers=False,
        playstyle_hint="Front-line warrior, reliable damage dealer, protector",
        suggested_origins=["human", "dwarf"],
        genre="fantasy",
    ),
    "rogue": ArchetypeData(
        id="rogue",
        display_name="Rogue",
        description="A cunning trickster who uses stealth and guile to overcome obstacles.",
        hit_die=HitDie.D8,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "intelligence"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "hand_crossbow", "longsword", "rapier", "shortsword"],
        skill_choices=["acrobatics", "athletics", "deception", "insight", "intimidation",
                       "investigation", "perception", "performance", "persuasion",
                       "sleight_of_hand", "stealth"],
        num_skill_choices=4,
        features_by_level={
            1: ["Expertise (2 skills)", "Sneak Attack (1d6)", "Thieves' Cant"],
            2: ["Cunning Action"],
            3: ["Roguish Archetype", "Sneak Attack (2d6)"],
        },
        has_powers=False,
        playstyle_hint="Stealthy striker, skill expert, opportunistic combatant",
        suggested_origins=["elf", "halfling"],
        genre="fantasy",
    ),
    "cleric": ArchetypeData(
        id="cleric",
        display_name="Cleric",
        description="A divine spellcaster who channels the power of their deity.",
        hit_die=HitDie.D8,
        primary_ability="wisdom",
        saving_throw_proficiencies=["wisdom", "charisma"],
        armor_proficiencies=["light", "medium", "shields"],
        weapon_proficiencies=["simple"],
        skill_choices=["history", "insight", "medicine", "persuasion", "religion"],
        num_skill_choices=2,
        features_by_level={
            1: ["Spellcasting", "Divine Domain"],
            2: ["Channel Divinity (1 use)", "Divine Domain Feature"],
            3: ["2nd Level Spells"],
        },
        has_powers=True,
        power_ability="wisdom",
        cantrips_known=3,
        power_slots_by_level={
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
        },
        playstyle_hint="Healer, support caster, divine warrior",
        suggested_origins=["human", "dwarf"],
        genre="fantasy",
    ),
    "wizard": ArchetypeData(
        id="wizard",
        display_name="Wizard",
        description="A scholarly magic-user who commands arcane power through study.",
        hit_die=HitDie.D6,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=[],
        weapon_proficiencies=["dagger", "dart", "sling", "quarterstaff", "light_crossbow"],
        skill_choices=["arcana", "history", "insight", "investigation", "medicine", "religion"],
        num_skill_choices=2,
        features_by_level={
            1: ["Spellcasting", "Arcane Recovery"],
            2: ["Arcane Tradition"],
            3: ["2nd Level Spells"],
        },
        has_powers=True,
        power_ability="intelligence",
        cantrips_known=3,
        power_slots_by_level={
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
        },
        playstyle_hint="Versatile caster, controller, knowledge seeker",
        suggested_origins=["elf", "human"],
        genre="fantasy",
    ),
}


# =============================================================================
# SCI-FI ARCHETYPES
# =============================================================================

class SciFiArchetype(str, Enum):
    """Sci-fi genre archetypes (roles)."""
    SOLDIER = "soldier"
    HACKER = "hacker"
    PILOT = "pilot"
    MEDIC = "medic"


SCIFI_ARCHETYPES: Dict[str, ArchetypeData] = {
    "soldier": ArchetypeData(
        id="soldier",
        display_name="Soldier",
        description="A trained combat specialist, skilled in weapons and tactical warfare.",
        hit_die=HitDie.D10,
        primary_ability="strength",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium", "heavy", "shields"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["athletics", "intimidation", "perception", "survival",
                       "vehicles", "demolitions"],
        num_skill_choices=2,
        features_by_level={
            1: ["Combat Training", "Adrenaline Rush"],
            2: ["Tactical Awareness"],
            3: ["Specialization"],
        },
        has_powers=False,
        playstyle_hint="Front-line combatant, squad leader, heavy weapons",
        suggested_origins=["human", "cyborg"],
        genre="scifi",
    ),
    "hacker": ArchetypeData(
        id="hacker",
        display_name="Hacker",
        description="A digital infiltrator who manipulates systems and information.",
        hit_die=HitDie.D6,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "dexterity"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["computers", "electronics", "deception", "investigation",
                       "perception", "stealth"],
        num_skill_choices=4,
        features_by_level={
            1: ["Neural Interface", "System Breach"],
            2: ["Data Mining"],
            3: ["Network Ghost"],
        },
        has_powers=True,
        power_ability="intelligence",
        cantrips_known=2,
        power_slots_by_level={
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
        },
        playstyle_hint="Digital warfare, information control, security bypass",
        suggested_origins=["android", "cyborg"],
        genre="scifi",
    ),
    "pilot": ArchetypeData(
        id="pilot",
        display_name="Pilot",
        description="A skilled vehicle operator who excels in navigation and quick reflexes.",
        hit_die=HitDie.D8,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["acrobatics", "perception", "vehicles", "navigation",
                       "mechanics", "persuasion"],
        num_skill_choices=3,
        features_by_level={
            1: ["Ace Pilot", "Evasive Maneuvers"],
            2: ["Quick Repairs"],
            3: ["Vehicle Bond"],
        },
        has_powers=False,
        playstyle_hint="Vehicle combat, exploration, getaway specialist",
        suggested_origins=["human", "alien"],
        genre="scifi",
    ),
    "medic": ArchetypeData(
        id="medic",
        display_name="Medic",
        description="A field medic who keeps the team alive using advanced medical tech.",
        hit_die=HitDie.D8,
        primary_ability="wisdom",
        saving_throw_proficiencies=["wisdom", "intelligence"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["medicine", "science", "insight", "perception",
                       "persuasion", "investigation"],
        num_skill_choices=2,
        features_by_level={
            1: ["Medical Training", "Trauma Care"],
            2: ["Stimulant Injection"],
            3: ["Field Surgery"],
        },
        has_powers=True,
        power_ability="wisdom",
        cantrips_known=2,
        power_slots_by_level={
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
        },
        playstyle_hint="Healer, support, keeps the team operational",
        suggested_origins=["human", "android"],
        genre="scifi",
    ),
}


# =============================================================================
# MODERN/HORROR ARCHETYPES
# =============================================================================

class ModernArchetype(str, Enum):
    """Modern/horror genre archetypes (professions)."""
    DETECTIVE = "detective"
    SOLDIER = "soldier"
    DOCTOR = "doctor"
    ENGINEER = "engineer"


MODERN_ARCHETYPES: Dict[str, ArchetypeData] = {
    "detective": ArchetypeData(
        id="detective",
        display_name="Detective",
        description="An investigator who uncovers secrets and solves mysteries.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["investigation", "insight", "perception", "deception",
                       "persuasion", "streetwise"],
        num_skill_choices=4,
        features_by_level={
            1: ["Keen Observer", "Contacts"],
            2: ["Deductive Reasoning"],
            3: ["Interrogation"],
        },
        has_powers=False,
        playstyle_hint="Investigation, social manipulation, finding the truth",
        suggested_origins=["urban", "academic"],
        genre="modern",
    ),
    "soldier": ArchetypeData(
        id="soldier",
        display_name="Soldier",
        description="A trained combatant with military or law enforcement experience.",
        hit_die=HitDie.D10,
        primary_ability="strength",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium", "heavy"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["athletics", "intimidation", "perception", "survival",
                       "vehicles", "first_aid"],
        num_skill_choices=2,
        features_by_level={
            1: ["Combat Training", "Adrenaline"],
            2: ["Tactical Movement"],
            3: ["Suppressive Fire"],
        },
        has_powers=False,
        playstyle_hint="Combat specialist, protector, tactical expert",
        suggested_origins=["military", "rural"],
        genre="modern",
    ),
    "doctor": ArchetypeData(
        id="doctor",
        display_name="Doctor",
        description="A medical professional who can heal wounds and diagnose conditions.",
        hit_die=HitDie.D6,
        primary_ability="wisdom",
        saving_throw_proficiencies=["wisdom", "intelligence"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple"],
        skill_choices=["medicine", "investigation", "insight", "science",
                       "persuasion", "perception"],
        num_skill_choices=3,
        features_by_level={
            1: ["Medical Training", "Diagnosis"],
            2: ["Steady Hands"],
            3: ["Emergency Care"],
        },
        has_powers=False,
        playstyle_hint="Healer, knowledge expert, calm under pressure",
        suggested_origins=["academic", "urban"],
        genre="modern",
    ),
    "engineer": ArchetypeData(
        id="engineer",
        display_name="Engineer",
        description="A technical expert who can build, repair, and improvise solutions.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "dexterity"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple"],
        skill_choices=["mechanics", "electronics", "investigation", "perception",
                       "science", "vehicles"],
        num_skill_choices=3,
        features_by_level={
            1: ["Technical Expert", "Improvised Repair"],
            2: ["Jury Rig"],
            3: ["Upgrade"],
        },
        has_powers=False,
        playstyle_hint="Problem solver, gadgeteer, technical support",
        suggested_origins=["academic", "military"],
        genre="modern",
    ),
}


# =============================================================================
# ARCHETYPE REGISTRY
# =============================================================================

# Static registry for non-fantasy genres
ARCHETYPES_BY_GENRE: Dict[str, Dict[str, ArchetypeData]] = {
    "fantasy": FANTASY_ARCHETYPES,  # Fallback, prefer SRD loader
    "scifi": SCIFI_ARCHETYPES,
    "modern": MODERN_ARCHETYPES,
    "horror": MODERN_ARCHETYPES,  # Horror uses modern professions
}


def _get_fantasy_archetypes_from_srd() -> Dict[str, ArchetypeData]:
    """Load fantasy archetypes from SRD data."""
    try:
        from ..data.loader import get_srd_loader
        loader = get_srd_loader()
        srd_classes = loader.get_all_classes(genre="fantasy")

        archetypes = {}
        for class_data in srd_classes:
            class_id = class_data.get("id", "")

            # Parse hit die
            hit_die_str = class_data.get("hit_die", "1d8")
            hit_die_map = {"1d6": HitDie.D6, "1d8": HitDie.D8, "1d10": HitDie.D10, "1d12": HitDie.D12}
            hit_die = hit_die_map.get(hit_die_str, HitDie.D8)

            # Parse saving throws
            saving_throws = class_data.get("saving_throws", [])

            # Parse primary ability from saving throws (first one usually)
            primary_ability = saving_throws[0] if saving_throws else "strength"

            # Check if spellcaster
            spellcasting_ability = class_data.get("spellcasting_ability")
            has_powers = spellcasting_ability is not None and spellcasting_ability != ""

            archetypes[class_id] = ArchetypeData(
                id=class_id,
                display_name=class_data.get("display_name", class_id.title()),
                description=class_data.get("description", "")[:500],
                hit_die=hit_die,
                primary_ability=primary_ability,
                saving_throw_proficiencies=saving_throws,
                armor_proficiencies=class_data.get("armor_proficiencies", []),
                weapon_proficiencies=class_data.get("weapon_proficiencies", []),
                has_powers=has_powers,
                power_ability=spellcasting_ability.lower() if spellcasting_ability else None,
                genre="fantasy",
            )

        return archetypes if archetypes else FANTASY_ARCHETYPES
    except Exception as e:
        # Fallback to hardcoded if loader fails
        print(f"Warning: Could not load SRD archetypes: {e}")
        return FANTASY_ARCHETYPES


def get_archetype(archetype_id: str, genre: str = "fantasy") -> Optional[ArchetypeData]:
    """Get archetype data by ID and genre."""
    if genre == "fantasy":
        # Try SRD first
        srd_archetypes = _get_fantasy_archetypes_from_srd()
        if archetype_id in srd_archetypes:
            return srd_archetypes[archetype_id]

    genre_archetypes = ARCHETYPES_BY_GENRE.get(genre, FANTASY_ARCHETYPES)
    return genre_archetypes.get(archetype_id)


def get_archetypes_for_genre(genre: str = "fantasy") -> List[ArchetypeData]:
    """Get all available archetypes for a genre."""
    if genre == "fantasy":
        # Use SRD data
        return list(_get_fantasy_archetypes_from_srd().values())

    genre_archetypes = ARCHETYPES_BY_GENRE.get(genre, FANTASY_ARCHETYPES)
    return list(genre_archetypes.values())


def get_starting_hp(archetype_id: str, con_modifier: int, genre: str = "fantasy") -> int:
    """Calculate starting HP at level 1."""
    hit_die_max = {
        HitDie.D6: 6, HitDie.D8: 8, HitDie.D10: 10, HitDie.D12: 12,
    }
    archetype = get_archetype(archetype_id, genre)
    if not archetype:
        return 8 + con_modifier
    return hit_die_max[archetype.hit_die] + con_modifier


def get_hp_at_level(archetype_id: str, level: int, con_modifier: int, genre: str = "fantasy") -> int:
    """Calculate HP at a given level."""
    hit_die_avg = {
        HitDie.D6: 4, HitDie.D8: 5, HitDie.D10: 6, HitDie.D12: 7,
    }
    hit_die_max = {
        HitDie.D6: 6, HitDie.D8: 8, HitDie.D10: 10, HitDie.D12: 12,
    }

    archetype = get_archetype(archetype_id, genre)
    if not archetype:
        return max(1, (5 + con_modifier) * level)

    hp = hit_die_max[archetype.hit_die] + con_modifier
    for _ in range(2, level + 1):
        hp += hit_die_avg[archetype.hit_die] + con_modifier
    return max(1, hp)


# =============================================================================
# BACKWARD COMPATIBILITY (D&D 5e aliases)
# =============================================================================

ClassName = FantasyArchetype
ClassData = ArchetypeData
CLASSES = FANTASY_ARCHETYPES


def get_class(name) -> ArchetypeData:
    """Backward compatible: get class by name."""
    if hasattr(name, 'value'):
        name = name.value
    return FANTASY_ARCHETYPES.get(name)


def get_all_classes() -> List[ArchetypeData]:
    """Backward compatible: get all fantasy classes."""
    return list(FANTASY_ARCHETYPES.values())
