"""Genre-specific terminology mapping."""

from typing import Dict
from pydantic import BaseModel


class GenreTerminology(BaseModel):
    """
    Maps generic system terms to genre-specific display terms.

    The rules engine uses generic terms internally (origin, archetype, ability).
    This class provides the display names for each genre.
    """

    # Core entity terms
    origin: str = "Origin"           # Generic: where/what you come from
    origin_plural: str = "Origins"
    archetype: str = "Archetype"     # Generic: your role/specialty
    archetype_plural: str = "Archetypes"

    # Power/ability terms
    ability_power: str = "Ability"   # Generic: special powers
    ability_power_plural: str = "Abilities"
    power_source: str = "Power"      # What fuels abilities
    power_points: str = "Power Points"  # Resource for abilities

    # Combat terms
    hit_points: str = "Hit Points"
    armor_class: str = "Defense"
    attack: str = "Attack"
    damage: str = "Damage"

    # Ability score display names (can be customized per genre)
    strength: str = "Strength"
    dexterity: str = "Dexterity"
    constitution: str = "Constitution"
    intelligence: str = "Intelligence"
    wisdom: str = "Wisdom"
    charisma: str = "Charisma"

    # Short forms for UI
    str_short: str = "STR"
    dex_short: str = "DEX"
    con_short: str = "CON"
    int_short: str = "INT"
    wis_short: str = "WIS"
    cha_short: str = "CHA"

    # Flavor terms
    level_up_message: str = "You have grown stronger!"
    rest_message: str = "You take time to recover."


# Pre-defined terminology sets
FANTASY_TERMS = GenreTerminology(
    origin="Race",
    origin_plural="Races",
    archetype="Class",
    archetype_plural="Classes",
    ability_power="Spell",
    ability_power_plural="Spells",
    power_source="Magic",
    power_points="Spell Slots",
    hit_points="Hit Points",
    armor_class="Armor Class",
    level_up_message="You have gained a level!",
    rest_message="You take a long rest.",
)

SCIFI_TERMS = GenreTerminology(
    origin="Species",
    origin_plural="Species",
    archetype="Role",
    archetype_plural="Roles",
    ability_power="Tech",
    ability_power_plural="Tech Abilities",
    power_source="Energy",
    power_points="Energy Cells",
    hit_points="Health",
    armor_class="Shield Rating",
    strength="Power",
    wisdom="Awareness",
    charisma="Presence",
    str_short="PWR",
    wis_short="AWR",
    cha_short="PRS",
    level_up_message="Systems upgraded.",
    rest_message="You enter recovery mode.",
)

MODERN_TERMS = GenreTerminology(
    origin="Background",
    origin_plural="Backgrounds",
    archetype="Profession",
    archetype_plural="Professions",
    ability_power="Skill",
    ability_power_plural="Special Skills",
    power_source="Training",
    power_points="Focus",
    hit_points="Health",
    armor_class="Defense",
    wisdom="Perception",
    charisma="Influence",
    wis_short="PER",
    cha_short="INF",
    level_up_message="Your experience has paid off.",
    rest_message="You take time to recuperate.",
)

HORROR_TERMS = GenreTerminology(
    origin="Background",
    origin_plural="Backgrounds",
    archetype="Archetype",
    archetype_plural="Archetypes",
    ability_power="Talent",
    ability_power_plural="Talents",
    power_source="Willpower",
    power_points="Sanity",
    hit_points="Vitality",
    armor_class="Defense",
    wisdom="Insight",
    charisma="Composure",
    wis_short="INS",
    cha_short="CMP",
    level_up_message="You've survived another ordeal.",
    rest_message="You try to find some peace.",
)

GENERIC_TERMS = GenreTerminology()  # Uses all defaults
