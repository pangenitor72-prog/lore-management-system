"""D&D 5e Class definitions (Phase 1: 4 core classes)."""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel


class HitDie(str, Enum):
    """Hit dice types."""
    D6 = "d6"
    D8 = "d8"
    D10 = "d10"
    D12 = "d12"


class ClassName(str, Enum):
    """Available classes in Phase 1."""
    FIGHTER = "fighter"
    ROGUE = "rogue"
    CLERIC = "cleric"
    WIZARD = "wizard"


class ClassData(BaseModel):
    """Class definition with features and progression."""
    name: ClassName
    display_name: str
    description: str
    hit_die: HitDie
    primary_ability: str  # Main ability for the class
    saving_throw_proficiencies: List[str]
    armor_proficiencies: List[str]
    weapon_proficiencies: List[str]
    skill_choices: List[str]  # Skills to choose from
    num_skill_choices: int
    features_by_level: Dict[int, List[str]]  # Level -> list of features

    # Spellcasting (for Cleric/Wizard)
    spellcasting: bool = False
    spellcasting_ability: Optional[str] = None
    cantrips_known: int = 0
    spell_slots_by_level: Dict[int, Dict[int, int]] = {}  # Level -> {slot_level: count}

    # For guided/concept mode
    playstyle_hint: str = ""
    suggested_races: List[str] = []


# Phase 1 Class Definitions
CLASSES: Dict[ClassName, ClassData] = {
    ClassName.FIGHTER: ClassData(
        name=ClassName.FIGHTER,
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
        spellcasting=False,
        playstyle_hint="Front-line warrior, reliable damage dealer, protector",
        suggested_races=["human", "dwarf"],
    ),

    ClassName.ROGUE: ClassData(
        name=ClassName.ROGUE,
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
        num_skill_choices=4,  # Rogues get more skills
        features_by_level={
            1: ["Expertise (2 skills)", "Sneak Attack (1d6)", "Thieves' Cant"],
            2: ["Cunning Action"],
            3: ["Roguish Archetype", "Sneak Attack (2d6)"],
        },
        spellcasting=False,
        playstyle_hint="Stealthy striker, skill expert, opportunistic combatant",
        suggested_races=["elf", "halfling"],
    ),

    ClassName.CLERIC: ClassData(
        name=ClassName.CLERIC,
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
        spellcasting=True,
        spellcasting_ability="wisdom",
        cantrips_known=3,
        spell_slots_by_level={
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
        },
        playstyle_hint="Healer, support caster, divine warrior",
        suggested_races=["human", "dwarf"],
    ),

    ClassName.WIZARD: ClassData(
        name=ClassName.WIZARD,
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
        spellcasting=True,
        spellcasting_ability="intelligence",
        cantrips_known=3,
        spell_slots_by_level={
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
        },
        playstyle_hint="Versatile caster, controller, knowledge seeker",
        suggested_races=["elf", "human"],
    ),
}


def get_class(name: ClassName) -> ClassData:
    """Get class data by name."""
    return CLASSES[name]


def get_all_classes() -> List[ClassData]:
    """Get all available classes."""
    return list(CLASSES.values())


def get_starting_hp(class_name: ClassName, con_modifier: int) -> int:
    """
    Calculate starting HP at level 1.

    HP = max hit die value + CON modifier
    """
    hit_die_max = {
        HitDie.D6: 6,
        HitDie.D8: 8,
        HitDie.D10: 10,
        HitDie.D12: 12,
    }
    class_data = CLASSES[class_name]
    return hit_die_max[class_data.hit_die] + con_modifier


def get_hp_at_level(class_name: ClassName, level: int, con_modifier: int) -> int:
    """
    Calculate HP at a given level.

    Level 1: max hit die + CON mod
    Level 2+: previous HP + (average hit die + CON mod) per level
    """
    hit_die_avg = {
        HitDie.D6: 4,
        HitDie.D8: 5,
        HitDie.D10: 6,
        HitDie.D12: 7,
    }
    hit_die_max = {
        HitDie.D6: 6,
        HitDie.D8: 8,
        HitDie.D10: 10,
        HitDie.D12: 12,
    }

    class_data = CLASSES[class_name]
    # Level 1 HP
    hp = hit_die_max[class_data.hit_die] + con_modifier
    # Add HP for levels 2+
    for _ in range(2, level + 1):
        hp += hit_die_avg[class_data.hit_die] + con_modifier
    return max(1, hp)  # Minimum 1 HP
