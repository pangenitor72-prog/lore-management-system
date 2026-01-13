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

    # Starting equipment (genre-appropriate)
    starting_equipment: List[str] = Field(default_factory=list)

    # For guided/concept mode
    playstyle_hint: str = ""
    suggested_origins: List[str] = Field(default_factory=list)

    # Genre metadata
    genre: str = "generic"


# =============================================================================
# FANTASY ARCHETYPES (D&D 5e Classes)
# =============================================================================

class FantasyArchetype(str, Enum):
    """Fantasy genre archetypes (D&D 5e classes)."""
    BARBARIAN = "barbarian"
    BARD = "bard"
    CLERIC = "cleric"
    DRUID = "druid"
    FIGHTER = "fighter"
    MONK = "monk"
    PALADIN = "paladin"
    RANGER = "ranger"
    ROGUE = "rogue"
    SORCERER = "sorcerer"
    WARLOCK = "warlock"
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
    "barbarian": ArchetypeData(
        id="barbarian",
        display_name="Barbarian",
        description="A fierce warrior who channels primal rage for devastating attacks.",
        hit_die=HitDie.D12,
        primary_ability="strength",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["animal_handling", "athletics", "intimidation", "nature", "perception", "survival"],
        num_skill_choices=2,
        features_by_level={
            1: ["Rage", "Unarmored Defense"],
            2: ["Reckless Attack", "Danger Sense"],
            3: ["Primal Path"],
        },
        has_powers=False,
        playstyle_hint="Tanky damage dealer, frontline berserker, relentless attacker",
        suggested_origins=["human", "half-orc"],
        genre="fantasy",
    ),
    "bard": ArchetypeData(
        id="bard",
        display_name="Bard",
        description="A performer whose magic weaves through words and music.",
        hit_die=HitDie.D8,
        primary_ability="charisma",
        saving_throw_proficiencies=["dexterity", "charisma"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "hand_crossbow", "longsword", "rapier", "shortsword"],
        skill_choices=["acrobatics", "animal_handling", "arcana", "athletics", "deception", "history",
                       "insight", "intimidation", "investigation", "medicine", "nature", "perception",
                       "performance", "persuasion", "religion", "sleight_of_hand", "stealth", "survival"],
        num_skill_choices=3,
        features_by_level={
            1: ["Spellcasting", "Bardic Inspiration (d6)"],
            2: ["Jack of All Trades", "Song of Rest (d6)"],
            3: ["Bard College", "Expertise"],
        },
        has_powers=True,
        power_ability="charisma",
        cantrips_known=2,
        power_slots_by_level={
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
        },
        playstyle_hint="Support caster, face character, versatile performer",
        suggested_origins=["half-elf", "human"],
        genre="fantasy",
    ),
    "druid": ArchetypeData(
        id="druid",
        display_name="Druid",
        description="A priest of nature who channels the forces of the natural world.",
        hit_die=HitDie.D8,
        primary_ability="wisdom",
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=["light", "medium", "shields"],
        weapon_proficiencies=["club", "dagger", "dart", "javelin", "mace", "quarterstaff", "scimitar", "sickle", "sling", "spear"],
        skill_choices=["arcana", "animal_handling", "insight", "medicine", "nature", "perception", "religion", "survival"],
        num_skill_choices=2,
        features_by_level={
            1: ["Druidic", "Spellcasting"],
            2: ["Wild Shape", "Druid Circle"],
            3: ["2nd Level Spells"],
        },
        has_powers=True,
        power_ability="wisdom",
        cantrips_known=2,
        power_slots_by_level={
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
        },
        playstyle_hint="Nature magic, shapeshifting, versatile caster",
        suggested_origins=["elf", "human"],
        genre="fantasy",
    ),
    "monk": ArchetypeData(
        id="monk",
        display_name="Monk",
        description="A martial artist who harnesses the power of body and mind.",
        hit_die=HitDie.D8,
        primary_ability="dexterity",
        saving_throw_proficiencies=["strength", "dexterity"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple", "shortsword"],
        skill_choices=["acrobatics", "athletics", "history", "insight", "religion", "stealth"],
        num_skill_choices=2,
        features_by_level={
            1: ["Unarmored Defense", "Martial Arts"],
            2: ["Ki", "Unarmored Movement"],
            3: ["Monastic Tradition", "Deflect Missiles"],
        },
        has_powers=False,
        playstyle_hint="Mobile striker, unarmed combatant, agile defender",
        suggested_origins=["human", "elf"],
        genre="fantasy",
    ),
    "paladin": ArchetypeData(
        id="paladin",
        display_name="Paladin",
        description="A holy warrior bound by a sacred oath.",
        hit_die=HitDie.D10,
        primary_ability="strength",
        saving_throw_proficiencies=["wisdom", "charisma"],
        armor_proficiencies=["light", "medium", "heavy", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["athletics", "insight", "intimidation", "medicine", "persuasion", "religion"],
        num_skill_choices=2,
        features_by_level={
            1: ["Divine Sense", "Lay on Hands"],
            2: ["Fighting Style", "Spellcasting", "Divine Smite"],
            3: ["Divine Health", "Sacred Oath"],
        },
        has_powers=True,
        power_ability="charisma",
        cantrips_known=0,
        power_slots_by_level={
            2: {1: 2},
            3: {1: 3},
        },
        playstyle_hint="Tank healer, smite damage, righteous protector",
        suggested_origins=["human", "dragonborn"],
        genre="fantasy",
    ),
    "ranger": ArchetypeData(
        id="ranger",
        display_name="Ranger",
        description="A skilled hunter and tracker who protects the wilderness.",
        hit_die=HitDie.D10,
        primary_ability="dexterity",
        saving_throw_proficiencies=["strength", "dexterity"],
        armor_proficiencies=["light", "medium", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["animal_handling", "athletics", "insight", "investigation", "nature", "perception", "stealth", "survival"],
        num_skill_choices=3,
        features_by_level={
            1: ["Favored Enemy", "Natural Explorer"],
            2: ["Fighting Style", "Spellcasting"],
            3: ["Ranger Archetype", "Primeval Awareness"],
        },
        has_powers=True,
        power_ability="wisdom",
        cantrips_known=0,
        power_slots_by_level={
            2: {1: 2},
            3: {1: 3},
        },
        playstyle_hint="Wilderness warrior, archer, scout and tracker",
        suggested_origins=["elf", "human"],
        genre="fantasy",
    ),
    "sorcerer": ArchetypeData(
        id="sorcerer",
        display_name="Sorcerer",
        description="A spellcaster with innate magical power flowing through their blood.",
        hit_die=HitDie.D6,
        primary_ability="charisma",
        saving_throw_proficiencies=["constitution", "charisma"],
        armor_proficiencies=[],
        weapon_proficiencies=["dagger", "dart", "sling", "quarterstaff", "light_crossbow"],
        skill_choices=["arcana", "deception", "insight", "intimidation", "persuasion", "religion"],
        num_skill_choices=2,
        features_by_level={
            1: ["Spellcasting", "Sorcerous Origin"],
            2: ["Font of Magic"],
            3: ["Metamagic", "2nd Level Spells"],
        },
        has_powers=True,
        power_ability="charisma",
        cantrips_known=4,
        power_slots_by_level={
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
        },
        playstyle_hint="Flexible caster, raw magical power, metamagic manipulation",
        suggested_origins=["human", "tiefling"],
        genre="fantasy",
    ),
    "warlock": ArchetypeData(
        id="warlock",
        display_name="Warlock",
        description="A wielder of magic granted by a pact with an otherworldly patron.",
        hit_die=HitDie.D8,
        primary_ability="charisma",
        saving_throw_proficiencies=["wisdom", "charisma"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple"],
        skill_choices=["arcana", "deception", "history", "intimidation", "investigation", "nature", "religion"],
        num_skill_choices=2,
        features_by_level={
            1: ["Otherworldly Patron", "Pact Magic"],
            2: ["Eldritch Invocations"],
            3: ["Pact Boon"],
        },
        has_powers=True,
        power_ability="charisma",
        cantrips_known=2,
        power_slots_by_level={
            1: {1: 1},
            2: {1: 2},
            3: {2: 2},
        },
        playstyle_hint="Eldritch blaster, dark pact caster, versatile invocations",
        suggested_origins=["tiefling", "human"],
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
# CYBERPUNK ARCHETYPES
# =============================================================================

class CyberpunkArchetype(str, Enum):
    """Cyberpunk genre archetypes (roles)."""
    NETRUNNER = "netrunner"
    SOLO = "solo"
    TECHIE = "techie"
    FIXER = "fixer"


CYBERPUNK_ARCHETYPES: Dict[str, ArchetypeData] = {
    "netrunner": ArchetypeData(
        id="netrunner",
        display_name="Netrunner",
        description="A hacker who jacks into cyberspace to steal data, crash systems, and fight ICE.",
        hit_die=HitDie.D6,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "dexterity"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["hacking", "electronics", "investigation", "stealth",
                       "deception", "perception"],
        num_skill_choices=4,
        features_by_level={
            1: ["Neural Interface", "ICE Breaker"],
            2: ["Quick Hack"],
            3: ["Daemon Upload"],
        },
        has_powers=True,
        power_ability="intelligence",
        starting_equipment=["Cyberdeck", "Neural interface", "Light pistol", "Synth-leather jacket", "Credchip (500eb)"],
        playstyle_hint="Digital infiltration, system manipulation, information warfare",
        suggested_origins=["corporate", "street_kid", "synthetic"],
        genre="cyberpunk",
    ),
    "solo": ArchetypeData(
        id="solo",
        display_name="Solo",
        description="A combat specialist - bodyguard, assassin, or street samurai for hire.",
        hit_die=HitDie.D10,
        primary_ability="dexterity",
        saving_throw_proficiencies=["strength", "dexterity"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["athletics", "intimidation", "perception", "stealth",
                       "streetwise", "vehicles"],
        num_skill_choices=3,
        features_by_level={
            1: ["Combat Sense", "Reflex Boost"],
            2: ["Tactical Awareness"],
            3: ["Killing Blow"],
        },
        has_powers=False,
        starting_equipment=["Assault rifle or SMG", "Heavy pistol", "Armored vest", "Combat knife", "Stimulants (3)", "Credchip (200eb)"],
        playstyle_hint="Combat specialist, bodyguard, street enforcer",
        suggested_origins=["street_kid", "nomad", "synthetic"],
        genre="cyberpunk",
    ),
    "techie": ArchetypeData(
        id="techie",
        display_name="Techie",
        description="A mechanical genius who can build, repair, and modify anything with circuits or gears.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "constitution"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["mechanics", "electronics", "science", "investigation",
                       "perception", "vehicles"],
        num_skill_choices=4,
        features_by_level={
            1: ["Jury Rig", "Tech Scanner"],
            2: ["Upgrade"],
            3: ["Masterwork"],
        },
        has_powers=False,
        starting_equipment=["Tool kit", "Tech scanner", "Light pistol", "Work jumpsuit", "Spare parts", "Credchip (300eb)"],
        playstyle_hint="Inventor, mechanic, cyberware specialist",
        suggested_origins=["corporate", "nomad", "synthetic"],
        genre="cyberpunk",
    ),
    "fixer": ArchetypeData(
        id="fixer",
        display_name="Fixer",
        description="A dealmaker who knows everyone, can get anything, and always has an angle.",
        hit_die=HitDie.D8,
        primary_ability="charisma",
        saving_throw_proficiencies=["charisma", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["persuasion", "deception", "insight", "streetwise",
                       "investigation", "intimidation"],
        num_skill_choices=4,
        features_by_level={
            1: ["Network", "Reputation"],
            2: ["Inside Information"],
            3: ["Call in Favor"],
        },
        has_powers=False,
        starting_equipment=["Concealed pistol", "Expensive suit", "Encrypted phone", "Contact list", "Credchip (1000eb)"],
        playstyle_hint="Face, negotiator, information broker",
        suggested_origins=["corporate", "street_kid"],
        genre="cyberpunk",
    ),
}


# =============================================================================
# STEAMPUNK ARCHETYPES
# =============================================================================

class SteampunkArchetype(str, Enum):
    """Steampunk genre archetypes."""
    ARTIFICER = "artificer"
    AERONAUT = "aeronaut"
    GENTLEMAN_ADVENTURER = "gentleman_adventurer"
    DETECTIVE = "detective"


STEAMPUNK_ARCHETYPES: Dict[str, ArchetypeData] = {
    "artificer": ArchetypeData(
        id="artificer",
        display_name="Artificer",
        description="An inventor who creates impossible machines powered by steam and clockwork.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "constitution"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "firearms"],
        skill_choices=["mechanics", "science", "investigation", "perception",
                       "history", "arcana"],
        num_skill_choices=4,
        features_by_level={
            1: ["Tinker", "Prototype Device"],
            2: ["Mechanical Familiar"],
            3: ["Improved Prototype"],
        },
        has_powers=True,
        power_ability="intelligence",
        starting_equipment=["Tool kit", "Prototype gadget", "Derringer", "Brass goggles", "Leather apron", "10 shillings"],
        playstyle_hint="Inventor, gadgeteer, mad scientist",
        suggested_origins=["inventor", "street_urchin"],
        genre="steampunk",
    ),
    "aeronaut": ArchetypeData(
        id="aeronaut",
        display_name="Aeronaut",
        description="A daring pilot of airships, balloons, and ornithopters who lives for adventure.",
        hit_die=HitDie.D10,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "wisdom"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["acrobatics", "athletics", "navigation", "perception",
                       "survival", "vehicles"],
        num_skill_choices=3,
        features_by_level={
            1: ["Air Sense", "Daredevil"],
            2: ["Evasive Maneuvers"],
            3: ["Ace Pilot"],
        },
        has_powers=False,
        starting_equipment=["Revolver", "Saber", "Flight jacket", "Aviator goggles", "Compass", "5 pounds"],
        playstyle_hint="Airship pilot, explorer, action hero",
        suggested_origins=["aristocrat", "colonial", "inventor"],
        genre="steampunk",
    ),
    "gentleman_adventurer": ArchetypeData(
        id="gentleman_adventurer",
        display_name="Gentleman Adventurer",
        description="A refined explorer who seeks excitement in the world's dark corners.",
        hit_die=HitDie.D8,
        primary_ability="charisma",
        saving_throw_proficiencies=["charisma", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["persuasion", "history", "insight", "investigation",
                       "athletics", "perception"],
        num_skill_choices=4,
        features_by_level={
            1: ["Social Grace", "World Traveler"],
            2: ["Stiff Upper Lip"],
            3: ["Inspiring Presence"],
        },
        has_powers=False,
        starting_equipment=["Walking cane (sword concealed)", "Revolver", "Fine suit", "Top hat", "Pocket watch", "20 pounds"],
        playstyle_hint="Explorer, socialite, amateur detective",
        suggested_origins=["aristocrat", "colonial"],
        genre="steampunk",
    ),
    "detective": ArchetypeData(
        id="detective",
        display_name="Detective",
        description="A brilliant investigator who solves mysteries through observation and deduction.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "firearms"],
        skill_choices=["investigation", "insight", "perception", "deception",
                       "persuasion", "streetwise"],
        num_skill_choices=4,
        features_by_level={
            1: ["Keen Observer", "Deduction"],
            2: ["Read the Room"],
            3: ["Elementary"],
        },
        has_powers=False,
        starting_equipment=["Magnifying glass", "Revolver", "Tweed coat", "Pipe", "Notebook", "5 pounds"],
        playstyle_hint="Mystery solver, analyst, observer",
        suggested_origins=["street_urchin", "aristocrat", "inventor"],
        genre="steampunk",
    ),
}


# =============================================================================
# WESTERN ARCHETYPES
# =============================================================================

class WesternArchetype(str, Enum):
    """Western genre archetypes."""
    GUNSLINGER = "gunslinger"
    LAWMAN = "lawman"
    GAMBLER = "gambler"
    SCOUT = "scout"


WESTERN_ARCHETYPES: Dict[str, ArchetypeData] = {
    "gunslinger": ArchetypeData(
        id="gunslinger",
        display_name="Gunslinger",
        description="A deadly shooter who lives and dies by the speed of their draw.",
        hit_die=HitDie.D10,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "firearms"],
        skill_choices=["acrobatics", "intimidation", "perception", "sleight_of_hand",
                       "survival", "stealth"],
        num_skill_choices=3,
        features_by_level={
            1: ["Quick Draw", "Dead Eye"],
            2: ["Fan the Hammer"],
            3: ["Trick Shot"],
        },
        has_powers=False,
        starting_equipment=["Colt revolver (2)", "Gun belt with holsters", "50 rounds", "Duster coat", "Cowboy hat", "$20"],
        playstyle_hint="Shootist, duelist, bounty hunter",
        suggested_origins=["outlaw", "frontier", "native"],
        genre="western",
    ),
    "lawman": ArchetypeData(
        id="lawman",
        display_name="Lawman",
        description="A sheriff, marshal, or ranger who brings order to the frontier.",
        hit_die=HitDie.D10,
        primary_ability="wisdom",
        saving_throw_proficiencies=["wisdom", "constitution"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["insight", "intimidation", "investigation", "perception",
                       "persuasion", "survival"],
        num_skill_choices=3,
        features_by_level={
            1: ["Authority", "Manhunter"],
            2: ["Read the Law"],
            3: ["Posse"],
        },
        has_powers=False,
        starting_equipment=["Winchester rifle", "Revolver", "Badge", "Handcuffs", "Horse", "$15"],
        playstyle_hint="Law enforcement, tracker, protector",
        suggested_origins=["frontier", "immigrant"],
        genre="western",
    ),
    "gambler": ArchetypeData(
        id="gambler",
        display_name="Gambler",
        description="A card sharp and con artist who relies on luck, skill, and a derringer up the sleeve.",
        hit_die=HitDie.D8,
        primary_ability="charisma",
        saving_throw_proficiencies=["charisma", "dexterity"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["deception", "insight", "persuasion", "sleight_of_hand",
                       "perception", "performance"],
        num_skill_choices=4,
        features_by_level={
            1: ["Poker Face", "Lucky"],
            2: ["Card Sharp"],
            3: ["All In"],
        },
        has_powers=False,
        starting_equipment=["Derringer (concealed)", "Deck of cards", "Fancy suit", "Gold watch", "Rigged dice", "$50"],
        playstyle_hint="Con artist, card sharp, smooth talker",
        suggested_origins=["outlaw", "immigrant"],
        genre="western",
    ),
    "scout": ArchetypeData(
        id="scout",
        display_name="Scout",
        description="A wilderness expert who knows every trail, watering hole, and danger in the territory.",
        hit_die=HitDie.D10,
        primary_ability="wisdom",
        saving_throw_proficiencies=["dexterity", "wisdom"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["animal_handling", "nature", "perception", "stealth",
                       "survival", "athletics"],
        num_skill_choices=4,
        features_by_level={
            1: ["Natural Explorer", "Tracker"],
            2: ["Ambush"],
            3: ["Pathfinder"],
        },
        has_powers=False,
        starting_equipment=["Rifle", "Hunting knife", "Buckskins", "Bedroll", "Horse", "$10"],
        playstyle_hint="Tracker, guide, wilderness survivor",
        suggested_origins=["native", "frontier"],
        genre="western",
    ),
}


# =============================================================================
# POST-APOCALYPTIC ARCHETYPES
# =============================================================================

class PostApocArchetype(str, Enum):
    """Post-apocalyptic genre archetypes."""
    SURVIVOR = "survivor"
    SCAVENGER = "scavenger"
    RAIDER = "raider"
    MEDIC = "medic"


POSTAPOC_ARCHETYPES: Dict[str, ArchetypeData] = {
    "survivor": ArchetypeData(
        id="survivor",
        display_name="Survivor",
        description="An expert at staying alive when everything wants you dead.",
        hit_die=HitDie.D10,
        primary_ability="constitution",
        saving_throw_proficiencies=["constitution", "wisdom"],
        armor_proficiencies=["light", "medium", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["survival", "athletics", "perception", "stealth",
                       "medicine", "nature"],
        num_skill_choices=3,
        features_by_level={
            1: ["Wasteland Wisdom", "Endurance"],
            2: ["Danger Sense"],
            3: ["Self-Reliant"],
        },
        has_powers=False,
        starting_equipment=["Machete", "Crossbow", "Scrap armor", "Water canteen", "Fire starter", "3 days rations"],
        playstyle_hint="Endurance specialist, wasteland navigator",
        suggested_origins=["wasteland", "tribal"],
        genre="postapoc",
    ),
    "scavenger": ArchetypeData(
        id="scavenger",
        display_name="Scavenger",
        description="An expert at finding useful items in the ruins of the old world.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "dexterity"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "firearms"],
        skill_choices=["investigation", "perception", "stealth", "mechanics",
                       "history", "sleight_of_hand"],
        num_skill_choices=4,
        features_by_level={
            1: ["Salvage Expert", "Appraise"],
            2: ["Lucky Find"],
            3: ["Repair Anything"],
        },
        has_powers=False,
        starting_equipment=["Pipe rifle", "Crowbar", "Backpack (large)", "Lock picks", "Geiger counter", "Trade goods"],
        playstyle_hint="Treasure hunter, mechanic, trader",
        suggested_origins=["vault_dweller", "wasteland"],
        genre="postapoc",
    ),
    "raider": ArchetypeData(
        id="raider",
        display_name="Raider",
        description="A fierce warrior who takes what they need by force.",
        hit_die=HitDie.D12,
        primary_ability="strength",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["intimidation", "athletics", "survival", "perception",
                       "stealth", "vehicles"],
        num_skill_choices=2,
        features_by_level={
            1: ["Rage", "Fearsome"],
            2: ["Reckless Attack"],
            3: ["War Cry"],
        },
        has_powers=False,
        starting_equipment=["Spiked bat", "Sawed-off shotgun", "Leather armor with spikes", "War paint", "Trophies", "Chems (3)"],
        playstyle_hint="Berserker, intimidator, road warrior",
        suggested_origins=["wasteland", "tribal", "mutant"],
        genre="postapoc",
    ),
    "medic": ArchetypeData(
        id="medic",
        display_name="Medic",
        description="A healer who keeps people alive in a world with no hospitals.",
        hit_die=HitDie.D8,
        primary_ability="wisdom",
        saving_throw_proficiencies=["wisdom", "intelligence"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple"],
        skill_choices=["medicine", "nature", "science", "perception",
                       "insight", "survival"],
        num_skill_choices=4,
        features_by_level={
            1: ["Field Medic", "Diagnose"],
            2: ["Stabilize"],
            3: ["Combat Medic"],
        },
        has_powers=False,
        starting_equipment=["Medical kit", "Scalpel", "Antibiotics (5)", "Stimpaks (3)", "Medical journal", "Clean water (3)"],
        playstyle_hint="Healer, scientist, community pillar",
        suggested_origins=["vault_dweller", "tribal"],
        genre="postapoc",
    ),
}


# =============================================================================
# NOIR ARCHETYPES
# =============================================================================

class NoirArchetype(str, Enum):
    """Noir genre archetypes."""
    PRIVATE_EYE = "private_eye"
    FEMME_FATALE = "femme_fatale"
    MUSCLE = "muscle"
    REPORTER = "reporter"


NOIR_ARCHETYPES: Dict[str, ArchetypeData] = {
    "private_eye": ArchetypeData(
        id="private_eye",
        display_name="Private Eye",
        description="A cynical detective who takes the cases the cops won't touch.",
        hit_die=HitDie.D8,
        primary_ability="wisdom",
        saving_throw_proficiencies=["wisdom", "intelligence"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["investigation", "insight", "perception", "deception",
                       "persuasion", "streetwise"],
        num_skill_choices=4,
        features_by_level={
            1: ["Keen Observer", "Contacts"],
            2: ["Read People"],
            3: ["Sixth Sense"],
        },
        has_powers=False,
        starting_equipment=[".38 revolver", "Trench coat", "Fedora", "Cigarettes", "Flask of whiskey", "$50"],
        playstyle_hint="Investigator, cynic, truth-seeker",
        suggested_origins=["veteran", "working_class"],
        genre="noir",
    ),
    "femme_fatale": ArchetypeData(
        id="femme_fatale",
        display_name="Femme Fatale",
        description="A dangerous seducer who uses charm and guile to get what they want.",
        hit_die=HitDie.D6,
        primary_ability="charisma",
        saving_throw_proficiencies=["charisma", "dexterity"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple", "pistols"],
        skill_choices=["deception", "persuasion", "insight", "performance",
                       "sleight_of_hand", "stealth"],
        num_skill_choices=4,
        features_by_level={
            1: ["Seduction", "Dangerous Beauty"],
            2: ["Whispered Secrets"],
            3: ["Betrayal"],
        },
        has_powers=False,
        starting_equipment=["Derringer (concealed)", "Evening gown", "Cigarette holder", "Perfume", "Love letters", "$100"],
        playstyle_hint="Manipulator, spy, survivor",
        suggested_origins=["socialite", "criminal"],
        genre="noir",
    ),
    "muscle": ArchetypeData(
        id="muscle",
        display_name="Muscle",
        description="An enforcer who solves problems with fists, intimidation, and violence.",
        hit_die=HitDie.D12,
        primary_ability="strength",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["athletics", "intimidation", "perception", "stealth",
                       "streetwise", "vehicles"],
        num_skill_choices=2,
        features_by_level={
            1: ["Tough", "Intimidating Presence"],
            2: ["Take a Punch"],
            3: ["Bone Breaker"],
        },
        has_powers=False,
        starting_equipment=["Brass knuckles", "Tommy gun", "Cheap suit", "Cigarettes", "Switchblade", "$20"],
        playstyle_hint="Enforcer, bodyguard, leg-breaker",
        suggested_origins=["criminal", "working_class", "veteran"],
        genre="noir",
    ),
    "reporter": ArchetypeData(
        id="reporter",
        display_name="Reporter",
        description="A journalist who chases stories into the city's dark underbelly.",
        hit_die=HitDie.D6,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "charisma"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple"],
        skill_choices=["investigation", "insight", "perception", "persuasion",
                       "deception", "history"],
        num_skill_choices=4,
        features_by_level={
            1: ["Press Pass", "Nose for News"],
            2: ["Source Network"],
            3: ["Expose"],
        },
        has_powers=False,
        starting_equipment=["Notebook", "Camera", "Press pass", "Typewriter", "Contacts list", "$30"],
        playstyle_hint="Truth-seeker, information gatherer, idealist",
        suggested_origins=["working_class", "socialite"],
        genre="noir",
    ),
}


# =============================================================================
# WUXIA ARCHETYPES
# =============================================================================

class WuxiaArchetype(str, Enum):
    """Wuxia genre archetypes."""
    SWORDSMAN = "swordsman"
    MARTIAL_ARTIST = "martial_artist"
    SCHOLAR_WARRIOR = "scholar_warrior"
    ASSASSIN = "assassin"


WUXIA_ARCHETYPES: Dict[str, ArchetypeData] = {
    "swordsman": ArchetypeData(
        id="swordsman",
        display_name="Swordsman",
        description="A wandering warrior whose blade is an extension of their soul.",
        hit_die=HitDie.D10,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["acrobatics", "athletics", "insight", "perception",
                       "performance", "intimidation"],
        num_skill_choices=3,
        features_by_level={
            1: ["Blade Dance", "Sword Spirit"],
            2: ["Counter Strike"],
            3: ["One with the Blade"],
        },
        has_powers=True,
        power_ability="wisdom",
        starting_equipment=["Jian (straight sword)", "Traveling robes", "Waterskin", "Rice", "Bedroll", "5 taels silver"],
        playstyle_hint="Duelist, wanderer, honorable warrior",
        suggested_origins=["noble", "wanderer"],
        genre="wuxia",
    ),
    "martial_artist": ArchetypeData(
        id="martial_artist",
        display_name="Martial Artist",
        description="A master of unarmed combat whose body is the ultimate weapon.",
        hit_die=HitDie.D8,
        primary_ability="dexterity",
        saving_throw_proficiencies=["strength", "dexterity"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple", "monk"],
        skill_choices=["acrobatics", "athletics", "insight", "stealth",
                       "perception", "medicine"],
        num_skill_choices=3,
        features_by_level={
            1: ["Martial Arts", "Ki"],
            2: ["Flurry of Blows"],
            3: ["Deflect Missiles"],
        },
        has_powers=True,
        power_ability="wisdom",
        starting_equipment=["Monk robes", "Prayer beads", "Iron palm training tools", "Medicine kit", "2 taels silver"],
        playstyle_hint="Monk, internal arts master, disciplined warrior",
        suggested_origins=["temple", "peasant"],
        genre="wuxia",
    ),
    "scholar_warrior": ArchetypeData(
        id="scholar_warrior",
        display_name="Scholar-Warrior",
        description="A learned fighter who combines literary knowledge with martial skill.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["history", "medicine", "insight", "persuasion",
                       "calligraphy", "perception"],
        num_skill_choices=4,
        features_by_level={
            1: ["Classical Education", "Strategy"],
            2: ["Pressure Points"],
            3: ["Art of War"],
        },
        has_powers=True,
        power_ability="intelligence",
        starting_equipment=["Folding fan (weapon)", "Brush and ink", "Classical texts", "Scholar robes", "10 taels silver"],
        playstyle_hint="Strategist, healer, refined warrior",
        suggested_origins=["noble", "temple"],
        genre="wuxia",
    ),
    "assassin": ArchetypeData(
        id="assassin",
        display_name="Assassin",
        description="A shadow who kills for coin, vengeance, or duty.",
        hit_die=HitDie.D8,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "intelligence"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "martial", "poison"],
        skill_choices=["stealth", "acrobatics", "deception", "perception",
                       "sleight_of_hand", "disguise"],
        num_skill_choices=4,
        features_by_level={
            1: ["Sneak Attack", "Poison Use"],
            2: ["Shadow Step"],
            3: ["Death Strike"],
        },
        has_powers=False,
        starting_equipment=["Hidden blades", "Throwing stars", "Black clothes", "Poison vials (3)", "Rope", "1 tael silver"],
        playstyle_hint="Silent killer, spy, master of stealth",
        suggested_origins=["wanderer", "peasant"],
        genre="wuxia",
    ),
}


# =============================================================================
# PIRATE ARCHETYPES
# =============================================================================

class PirateArchetype(str, Enum):
    """Pirate genre archetypes."""
    SWASHBUCKLER = "swashbuckler"
    NAVIGATOR = "navigator"
    GUNNER = "gunner"
    CAPTAIN = "captain"


PIRATE_ARCHETYPES: Dict[str, ArchetypeData] = {
    "swashbuckler": ArchetypeData(
        id="swashbuckler",
        display_name="Swashbuckler",
        description="A dashing fighter who combines acrobatics with deadly swordplay.",
        hit_die=HitDie.D10,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "charisma"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["acrobatics", "athletics", "performance", "persuasion",
                       "sleight_of_hand", "intimidation"],
        num_skill_choices=3,
        features_by_level={
            1: ["Fancy Footwork", "Rakish Audacity"],
            2: ["Riposte"],
            3: ["Panache"],
        },
        has_powers=False,
        starting_equipment=["Cutlass", "Flintlock pistol", "Baldric", "Tricorn hat", "Boots", "10 pieces of eight"],
        playstyle_hint="Duelist, acrobat, charming rogue",
        suggested_origins=["sailor", "navy", "islander"],
        genre="pirate",
    ),
    "navigator": ArchetypeData(
        id="navigator",
        display_name="Navigator",
        description="A master of charts, stars, and currents who guides ships to treasure.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "firearms"],
        skill_choices=["navigation", "nature", "perception", "survival",
                       "history", "investigation"],
        num_skill_choices=4,
        features_by_level={
            1: ["Star Reader", "Weather Sense"],
            2: ["Plot Course"],
            3: ["Find the Way"],
        },
        has_powers=False,
        starting_equipment=["Sextant", "Spyglass", "Charts", "Compass", "Flintlock pistol", "20 pieces of eight"],
        playstyle_hint="Cartographer, astronomer, treasure finder",
        suggested_origins=["merchant", "navy", "islander"],
        genre="pirate",
    ),
    "gunner": ArchetypeData(
        id="gunner",
        display_name="Gunner",
        description="An expert with cannons and firearms who brings destruction to enemies.",
        hit_die=HitDie.D10,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "constitution"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial", "firearms", "cannons"],
        skill_choices=["athletics", "perception", "intimidation", "mechanics",
                       "survival", "stealth"],
        num_skill_choices=3,
        features_by_level={
            1: ["Master Gunner", "Steady Aim"],
            2: ["Quick Load"],
            3: ["Broadside"],
        },
        has_powers=False,
        starting_equipment=["Blunderbuss", "Cutlass", "Powder horn", "Shot pouch", "Slow match", "5 pieces of eight"],
        playstyle_hint="Artillery expert, sharpshooter, demolitions",
        suggested_origins=["navy", "sailor"],
        genre="pirate",
    ),
    "captain": ArchetypeData(
        id="captain",
        display_name="Captain",
        description="A born leader who commands loyalty and inspires their crew.",
        hit_die=HitDie.D10,
        primary_ability="charisma",
        saving_throw_proficiencies=["charisma", "wisdom"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["persuasion", "intimidation", "insight", "perception",
                       "deception", "history"],
        num_skill_choices=4,
        features_by_level={
            1: ["Commanding Presence", "Crew Loyalty"],
            2: ["Battle Orders"],
            3: ["Legendary Reputation"],
        },
        has_powers=False,
        starting_equipment=["Fine cutlass", "Brace of pistols", "Captain's coat", "Tricorn hat", "Ship's articles", "50 pieces of eight"],
        playstyle_hint="Leader, strategist, negotiator",
        suggested_origins=["navy", "merchant", "sailor"],
        genre="pirate",
    ),
}


# =============================================================================
# SUPERHERO ARCHETYPES
# =============================================================================

class SuperheroArchetype(str, Enum):
    """Superhero genre archetypes."""
    TANK = "tank"
    BLASTER = "blaster"
    SPEEDSTER = "speedster"
    CONTROLLER = "controller"


SUPERHERO_ARCHETYPES: Dict[str, ArchetypeData] = {
    "tank": ArchetypeData(
        id="tank",
        display_name="Tank",
        description="A nigh-invulnerable powerhouse who protects others and smashes threats.",
        hit_die=HitDie.D12,
        primary_ability="constitution",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple"],
        skill_choices=["athletics", "intimidation", "perception", "survival",
                       "insight", "persuasion"],
        num_skill_choices=2,
        features_by_level={
            1: ["Invulnerability", "Super Strength"],
            2: ["Ground Pound"],
            3: ["Unstoppable"],
        },
        has_powers=True,
        power_ability="constitution",
        starting_equipment=["Costume", "Communicator", "Secret identity gear"],
        playstyle_hint="Front-line defender, heavy hitter",
        suggested_origins=["mutant", "experiment", "alien"],
        genre="superhero",
    ),
    "blaster": ArchetypeData(
        id="blaster",
        display_name="Blaster",
        description="A ranged combatant who fires energy, elements, or other projectiles.",
        hit_die=HitDie.D8,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "constitution"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple"],
        skill_choices=["acrobatics", "perception", "stealth", "investigation",
                       "intimidation", "athletics"],
        num_skill_choices=3,
        features_by_level={
            1: ["Energy Blast", "Fly"],
            2: ["Charged Shot"],
            3: ["Area Burst"],
        },
        has_powers=True,
        power_ability="dexterity",
        starting_equipment=["Costume", "Communicator", "Visor/focus item"],
        playstyle_hint="Ranged damage dealer, mobile striker",
        suggested_origins=["mutant", "experiment"],
        genre="superhero",
    ),
    "speedster": ArchetypeData(
        id="speedster",
        display_name="Speedster",
        description="A blur of motion who can run faster than the eye can follow.",
        hit_die=HitDie.D8,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "wisdom"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple"],
        skill_choices=["acrobatics", "athletics", "perception", "stealth",
                       "investigation", "sleight_of_hand"],
        num_skill_choices=3,
        features_by_level={
            1: ["Super Speed", "Vibration"],
            2: ["Speed Steal"],
            3: ["Time Perception"],
        },
        has_powers=True,
        power_ability="dexterity",
        starting_equipment=["Friction-proof costume", "Communicator", "Energy bars"],
        playstyle_hint="Mobile striker, scout, rescue specialist",
        suggested_origins=["mutant", "experiment"],
        genre="superhero",
    ),
    "controller": ArchetypeData(
        id="controller",
        display_name="Controller",
        description="A hero who manipulates the battlefield with telekinesis, illusions, or other powers.",
        hit_die=HitDie.D6,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple"],
        skill_choices=["insight", "perception", "investigation", "persuasion",
                       "deception", "intimidation"],
        num_skill_choices=4,
        features_by_level={
            1: ["Telekinesis", "Mind Shield"],
            2: ["Crowd Control"],
            3: ["Dominate"],
        },
        has_powers=True,
        power_ability="intelligence",
        starting_equipment=["Costume", "Communicator", "Meditation focus"],
        playstyle_hint="Battlefield control, support, mentalist",
        suggested_origins=["mutant", "alien"],
        genre="superhero",
    ),
}


# =============================================================================
# MYTHOLOGY ARCHETYPES
# =============================================================================

class MythologyArchetype(str, Enum):
    """Mythology genre archetypes."""
    CHAMPION = "champion"
    ORACLE = "oracle"
    HUNTER = "hunter"
    TRICKSTER = "trickster"


MYTHOLOGY_ARCHETYPES: Dict[str, ArchetypeData] = {
    "champion": ArchetypeData(
        id="champion",
        display_name="Champion",
        description="A mighty warrior favored by the gods, destined for glory.",
        hit_die=HitDie.D12,
        primary_ability="strength",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium", "heavy", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["athletics", "intimidation", "perception", "survival",
                       "religion", "persuasion"],
        num_skill_choices=3,
        features_by_level={
            1: ["Divine Favor", "Heroic Might"],
            2: ["Champion's Challenge"],
            3: ["Legendary Deed"],
        },
        has_powers=True,
        power_ability="charisma",
        starting_equipment=["Bronze armor", "Spear and shield", "Xiphos (sword)", "Cloak", "Divine token", "10 drachmas"],
        playstyle_hint="Monster slayer, warrior-king, hero of legend",
        suggested_origins=["demigod", "mortal_hero"],
        genre="mythology",
    ),
    "oracle": ArchetypeData(
        id="oracle",
        display_name="Oracle",
        description="A seer blessed (or cursed) with divine visions and prophecy.",
        hit_die=HitDie.D6,
        primary_ability="wisdom",
        saving_throw_proficiencies=["wisdom", "charisma"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple"],
        skill_choices=["insight", "religion", "history", "medicine",
                       "perception", "persuasion"],
        num_skill_choices=4,
        features_by_level={
            1: ["Divine Visions", "Prophecy"],
            2: ["Read Fate"],
            3: ["Oracle's Curse"],
        },
        has_powers=True,
        power_ability="wisdom",
        starting_equipment=["Oracle's robes", "Sacred laurel", "Divination tools", "Incense", "5 drachmas"],
        playstyle_hint="Prophet, spiritual guide, cursed seer",
        suggested_origins=["chosen", "demigod"],
        genre="mythology",
    ),
    "hunter": ArchetypeData(
        id="hunter",
        display_name="Hunter",
        description="A skilled tracker who hunts monsters and men across wild lands.",
        hit_die=HitDie.D10,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "wisdom"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["survival", "nature", "perception", "stealth",
                       "athletics", "animal_handling"],
        num_skill_choices=4,
        features_by_level={
            1: ["Favored Prey", "Natural Explorer"],
            2: ["Hunter's Mark"],
            3: ["Monster Slayer"],
        },
        has_powers=False,
        starting_equipment=["Bow and arrows", "Hunting spear", "Leather armor", "Hunting dog", "Snares", "5 drachmas"],
        playstyle_hint="Monster hunter, wilderness guide, tracker",
        suggested_origins=["mortal_hero", "chosen"],
        genre="mythology",
    ),
    "trickster": ArchetypeData(
        id="trickster",
        display_name="Trickster",
        description="A cunning hero who defeats foes through wit, guile, and clever schemes.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["dexterity", "intelligence"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["deception", "stealth", "sleight_of_hand", "persuasion",
                       "acrobatics", "investigation"],
        num_skill_choices=4,
        features_by_level={
            1: ["Cunning Action", "Silver Tongue"],
            2: ["Misdirection"],
            3: ["Master Plan"],
        },
        has_powers=False,
        starting_equipment=["Concealed dagger", "Disguise kit", "Rope", "Traveler's clothes", "Dice (loaded)", "15 drachmas"],
        playstyle_hint="Con artist, spy, clever hero",
        suggested_origins=["demigod", "monster_born"],
        genre="mythology",
    ),
}


# =============================================================================
# SPACE OPERA ARCHETYPES
# =============================================================================

class SpaceOperaArchetype(str, Enum):
    """Space opera genre archetypes."""
    ACE_PILOT = "ace_pilot"
    SPACE_MARINE = "space_marine"
    SMUGGLER = "smuggler"
    BOUNTY_HUNTER = "bounty_hunter"


SPACE_OPERA_ARCHETYPES: Dict[str, ArchetypeData] = {
    "ace_pilot": ArchetypeData(
        id="ace_pilot",
        display_name="Ace Pilot",
        description="A legendary starfighter pilot who can outfly anyone in the galaxy.",
        hit_die=HitDie.D8,
        primary_ability="dexterity",
        saving_throw_proficiencies=["dexterity", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "blasters"],
        skill_choices=["piloting", "acrobatics", "perception", "mechanics",
                       "athletics", "persuasion"],
        num_skill_choices=4,
        features_by_level={
            1: ["Starfighter Ace", "Evasive Maneuvers"],
            2: ["Trick Shot"],
            3: ["One in a Million"],
        },
        has_powers=False,
        starting_equipment=["Blaster pistol", "Flight suit", "Helmet", "Personal starfighter", "Tool kit", "500 credits"],
        playstyle_hint="Dogfighter, daredevil, hotshot",
        suggested_origins=["human", "robot"],
        genre="space_opera",
    ),
    "space_marine": ArchetypeData(
        id="space_marine",
        display_name="Space Marine",
        description="An elite soldier trained for combat in any environment.",
        hit_die=HitDie.D10,
        primary_ability="strength",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium", "heavy", "powered"],
        weapon_proficiencies=["simple", "martial", "blasters", "heavy"],
        skill_choices=["athletics", "intimidation", "perception", "survival",
                       "vehicles", "medicine"],
        num_skill_choices=2,
        features_by_level={
            1: ["Combat Training", "Battle Hardened"],
            2: ["Suppressive Fire"],
            3: ["Tactical Strike"],
        },
        has_powers=False,
        starting_equipment=["Blaster rifle", "Combat armor", "Vibroblade", "Grenades (3)", "Med kit", "200 credits"],
        playstyle_hint="Front-line soldier, commando, veteran",
        suggested_origins=["human", "alien_warrior"],
        genre="space_opera",
    ),
    "smuggler": ArchetypeData(
        id="smuggler",
        display_name="Smuggler",
        description="A charming rogue who makes a living moving cargo the Empire doesn't want moved.",
        hit_die=HitDie.D8,
        primary_ability="charisma",
        saving_throw_proficiencies=["dexterity", "charisma"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple", "blasters"],
        skill_choices=["deception", "persuasion", "stealth", "piloting",
                       "sleight_of_hand", "streetwise"],
        num_skill_choices=4,
        features_by_level={
            1: ["Fast Talk", "Hidden Compartments"],
            2: ["Lucky Escape"],
            3: ["I Know a Guy"],
        },
        has_powers=False,
        starting_equipment=["Blaster pistol", "Leather jacket", "Cargo ship (shared)", "Forged papers", "Contacts", "300 credits"],
        playstyle_hint="Scoundrel, pilot, charmer",
        suggested_origins=["human", "alien_warrior"],
        genre="space_opera",
    ),
    "bounty_hunter": ArchetypeData(
        id="bounty_hunter",
        display_name="Bounty Hunter",
        description="A professional tracker who hunts fugitives across the galaxy for credits.",
        hit_die=HitDie.D10,
        primary_ability="wisdom",
        saving_throw_proficiencies=["dexterity", "wisdom"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial", "blasters", "exotic"],
        skill_choices=["investigation", "perception", "stealth", "survival",
                       "intimidation", "insight"],
        num_skill_choices=3,
        features_by_level={
            1: ["Mark Target", "Hunter's Gear"],
            2: ["Relentless Pursuit"],
            3: ["No Disintegrations"],
        },
        has_powers=False,
        starting_equipment=["Blaster rifle", "Blaster pistol", "Bounty hunter armor", "Tracking fob", "Binders", "100 credits"],
        playstyle_hint="Hunter, tracker, lone wolf",
        suggested_origins=["human", "alien_warrior", "robot"],
        genre="space_opera",
    ),
}


# =============================================================================
# DARK FANTASY ARCHETYPES
# =============================================================================

class DarkFantasyArchetype(str, Enum):
    """Dark fantasy genre archetypes."""
    WITCH_HUNTER = "witch_hunter"
    MERCENARY = "mercenary"
    PLAGUE_DOCTOR = "plague_doctor"
    OCCULTIST = "occultist"


DARK_FANTASY_ARCHETYPES: Dict[str, ArchetypeData] = {
    "witch_hunter": ArchetypeData(
        id="witch_hunter",
        display_name="Witch Hunter",
        description="A zealous hunter of dark magic, monsters, and heresy.",
        hit_die=HitDie.D10,
        primary_ability="wisdom",
        saving_throw_proficiencies=["wisdom", "charisma"],
        armor_proficiencies=["light", "medium"],
        weapon_proficiencies=["simple", "martial", "firearms"],
        skill_choices=["religion", "investigation", "insight", "intimidation",
                       "survival", "perception"],
        num_skill_choices=3,
        features_by_level={
            1: ["Monster Slayer", "Silver Tongue"],
            2: ["Sense Evil"],
            3: ["Righteous Fury"],
        },
        has_powers=True,
        power_ability="wisdom",
        starting_equipment=["Silver sword", "Crossbow", "Holy symbol", "Witch hunter garb", "Silver bolts (10)", "5 crowns"],
        playstyle_hint="Inquisitor, monster hunter, fanatic",
        suggested_origins=["human", "cursed"],
        genre="dark_fantasy",
    ),
    "mercenary": ArchetypeData(
        id="mercenary",
        display_name="Mercenary",
        description="A hardened sellsword who fights for coin in a world gone mad.",
        hit_die=HitDie.D10,
        primary_ability="strength",
        saving_throw_proficiencies=["strength", "constitution"],
        armor_proficiencies=["light", "medium", "heavy", "shields"],
        weapon_proficiencies=["simple", "martial"],
        skill_choices=["athletics", "intimidation", "perception", "survival",
                       "insight", "stealth"],
        num_skill_choices=3,
        features_by_level={
            1: ["Fighting Style", "Battle Scars"],
            2: ["Action Surge"],
            3: ["Know Your Enemy"],
        },
        has_powers=False,
        starting_equipment=["Longsword", "Shield", "Chain mail", "Dagger", "Bedroll", "10 crowns"],
        playstyle_hint="Soldier of fortune, pragmatic warrior",
        suggested_origins=["human", "cursed", "revenant"],
        genre="dark_fantasy",
    ),
    "plague_doctor": ArchetypeData(
        id="plague_doctor",
        display_name="Plague Doctor",
        description="A healer who walks among the sick and dying, fighting plagues both natural and supernatural.",
        hit_die=HitDie.D8,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "wisdom"],
        armor_proficiencies=["light"],
        weapon_proficiencies=["simple"],
        skill_choices=["medicine", "nature", "investigation", "insight",
                       "religion", "perception"],
        num_skill_choices=4,
        features_by_level={
            1: ["Plague Mask", "Battlefield Medicine"],
            2: ["Poison Resistance"],
            3: ["Experimental Cure"],
        },
        has_powers=True,
        power_ability="intelligence",
        starting_equipment=["Plague mask", "Medical bag", "Leech jar", "Herbs and poultices", "Walking stick", "8 crowns"],
        playstyle_hint="Healer, scientist, dealer with death",
        suggested_origins=["human", "halfbreed"],
        genre="dark_fantasy",
    ),
    "occultist": ArchetypeData(
        id="occultist",
        display_name="Occultist",
        description="A scholar of forbidden knowledge who dabbles in dark powers.",
        hit_die=HitDie.D6,
        primary_ability="intelligence",
        saving_throw_proficiencies=["intelligence", "charisma"],
        armor_proficiencies=[],
        weapon_proficiencies=["simple"],
        skill_choices=["arcana", "history", "investigation", "religion",
                       "insight", "deception"],
        num_skill_choices=4,
        features_by_level={
            1: ["Forbidden Knowledge", "Dark Pact"],
            2: ["Eldritch Blast"],
            3: ["Glimpse Beyond"],
        },
        has_powers=True,
        power_ability="intelligence",
        starting_equipment=["Grimoire", "Ritual dagger", "Candles", "Chalk", "Dark robes", "3 crowns"],
        playstyle_hint="Dark mage, knowledge seeker, dabbler in forbidden arts",
        suggested_origins=["cursed", "halfbreed", "revenant"],
        genre="dark_fantasy",
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
    "cyberpunk": CYBERPUNK_ARCHETYPES,
    "steampunk": STEAMPUNK_ARCHETYPES,
    "western": WESTERN_ARCHETYPES,
    "postapoc": POSTAPOC_ARCHETYPES,
    "noir": NOIR_ARCHETYPES,
    "wuxia": WUXIA_ARCHETYPES,
    "pirate": PIRATE_ARCHETYPES,
    "superhero": SUPERHERO_ARCHETYPES,
    "mythology": MYTHOLOGY_ARCHETYPES,
    "space_opera": SPACE_OPERA_ARCHETYPES,
    "dark_fantasy": DARK_FANTASY_ARCHETYPES,
}


def _get_fantasy_archetypes_from_srd() -> Dict[str, ArchetypeData]:
    """Load fantasy archetypes from SRD data, merged with hardcoded skill data."""
    try:
        from ..data.loader import get_srd_loader
        loader = get_srd_loader()
        srd_classes = loader.get_all_classes(genre="fantasy")

        archetypes = {}
        for class_data in srd_classes:
            class_id = class_data.get("id", "")

            # Get hardcoded data for skill choices and other complete info
            hardcoded = FANTASY_ARCHETYPES.get(class_id)

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

            # Merge skill data from hardcoded FANTASY_ARCHETYPES
            skill_choices = hardcoded.skill_choices if hardcoded else []
            num_skill_choices = hardcoded.num_skill_choices if hardcoded else 2
            features = hardcoded.features_by_level if hardcoded else {}
            playstyle = hardcoded.playstyle_hint if hardcoded else ""
            cantrips = hardcoded.cantrips_known if hardcoded else 0

            archetypes[class_id] = ArchetypeData(
                id=class_id,
                display_name=class_data.get("display_name", class_id.title()),
                description=class_data.get("description", "")[:500],
                hit_die=hit_die,
                primary_ability=primary_ability,
                saving_throw_proficiencies=saving_throws,
                armor_proficiencies=class_data.get("armor_proficiencies", []),
                weapon_proficiencies=class_data.get("weapon_proficiencies", []),
                skill_choices=skill_choices,
                num_skill_choices=num_skill_choices,
                features_by_level=features,
                has_powers=has_powers,
                power_ability=spellcasting_ability.lower() if spellcasting_ability else None,
                cantrips_known=cantrips,
                playstyle_hint=playstyle,
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
