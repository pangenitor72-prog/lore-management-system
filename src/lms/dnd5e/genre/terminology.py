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

# Additional genre terminology sets

WESTERN_TERMS = GenreTerminology(
    origin="Heritage",
    origin_plural="Heritages",
    archetype="Calling",
    archetype_plural="Callings",
    ability_power="Trick",
    ability_power_plural="Tricks",
    power_source="Grit",
    power_points="Grit Points",
    hit_points="Grit",
    armor_class="Guts",
    wisdom="Instinct",
    charisma="Swagger",
    wis_short="INS",
    cha_short="SWG",
    level_up_message="You've earned your spurs.",
    rest_message="You hunker down for the night.",
)

CYBERPUNK_TERMS = GenreTerminology(
    origin="Origin",
    origin_plural="Origins",
    archetype="Edge",
    archetype_plural="Edges",
    ability_power="Program",
    ability_power_plural="Programs",
    power_source="Chrome",
    power_points="RAM",
    hit_points="Meat",
    armor_class="Armor",
    intelligence="Processing",
    wisdom="Streetwise",
    charisma="Cool",
    int_short="PRC",
    wis_short="STW",
    cha_short="COL",
    level_up_message="Time to upgrade your chrome.",
    rest_message="You jack out and flatline for a bit.",
)

STEAMPUNK_TERMS = GenreTerminology(
    origin="Lineage",
    origin_plural="Lineages",
    archetype="Vocation",
    archetype_plural="Vocations",
    ability_power="Invention",
    ability_power_plural="Inventions",
    power_source="Steam",
    power_points="Pressure",
    hit_points="Fortitude",
    armor_class="Plating",
    intelligence="Ingenuity",
    wisdom="Perception",
    int_short="ING",
    wis_short="PER",
    level_up_message="Your genius grows!",
    rest_message="You wind down your mechanisms.",
)

POSTAPOC_TERMS = GenreTerminology(
    origin="Origin",
    origin_plural="Origins",
    archetype="Role",
    archetype_plural="Roles",
    ability_power="Survival Trick",
    ability_power_plural="Survival Tricks",
    power_source="Will",
    power_points="Resolve",
    hit_points="Health",
    armor_class="Armor",
    constitution="Endurance",
    wisdom="Awareness",
    charisma="Presence",
    con_short="END",
    wis_short="AWR",
    cha_short="PRS",
    level_up_message="Another day survived.",
    rest_message="You find shelter for the night.",
)

SUPERHERO_TERMS = GenreTerminology(
    origin="Origin Story",
    origin_plural="Origin Stories",
    archetype="Power Set",
    archetype_plural="Power Sets",
    ability_power="Power",
    ability_power_plural="Powers",
    power_source="Hero Energy",
    power_points="Hero Points",
    hit_points="Stamina",
    armor_class="Toughness",
    strength="Might",
    dexterity="Speed",
    charisma="Presence",
    str_short="MGT",
    dex_short="SPD",
    cha_short="PRS",
    level_up_message="Your powers grow stronger!",
    rest_message="You return to your secret identity.",
)

MYTHOLOGY_TERMS = GenreTerminology(
    origin="Divine Lineage",
    origin_plural="Divine Lineages",
    archetype="Heroic Path",
    archetype_plural="Heroic Paths",
    ability_power="Divine Gift",
    ability_power_plural="Divine Gifts",
    power_source="Divine Favor",
    power_points="Favor",
    hit_points="Vitality",
    armor_class="Aegis",
    strength="Might",
    wisdom="Prophecy",
    charisma="Glory",
    str_short="MGT",
    wis_short="PRO",
    cha_short="GLR",
    level_up_message="The gods smile upon you!",
    rest_message="You make offerings to the gods.",
)

NOIR_TERMS = GenreTerminology(
    origin="Background",
    origin_plural="Backgrounds",
    archetype="Archetype",
    archetype_plural="Archetypes",
    ability_power="Knack",
    ability_power_plural="Knacks",
    power_source="Determination",
    power_points="Luck",
    hit_points="Health",
    armor_class="Defense",
    wisdom="Street Smarts",
    charisma="Moxie",
    wis_short="SMS",
    cha_short="MOX",
    level_up_message="You've seen too much to stop now.",
    rest_message="You nurse a drink in a smoky bar.",
)

WUXIA_TERMS = GenreTerminology(
    origin="School",
    origin_plural="Schools",
    archetype="Martial Path",
    archetype_plural="Martial Paths",
    ability_power="Technique",
    ability_power_plural="Techniques",
    power_source="Chi",
    power_points="Chi Points",
    hit_points="Vitality",
    armor_class="Defense",
    strength="Body",
    dexterity="Agility",
    wisdom="Spirit",
    charisma="Presence",
    str_short="BOD",
    dex_short="AGI",
    wis_short="SPI",
    cha_short="PRS",
    level_up_message="Your mastery deepens.",
    rest_message="You meditate and restore your chi.",
)

PIRATE_TERMS = GenreTerminology(
    origin="Background",
    origin_plural="Backgrounds",
    archetype="Crew Role",
    archetype_plural="Crew Roles",
    ability_power="Sea Trick",
    ability_power_plural="Sea Tricks",
    power_source="Luck",
    power_points="Fortune",
    hit_points="Grit",
    armor_class="Defense",
    strength="Brawn",
    dexterity="Agility",
    charisma="Swagger",
    str_short="BRN",
    dex_short="AGI",
    cha_short="SWG",
    level_up_message="Ye've earned yer sea legs!",
    rest_message="You share rum and tales aboard ship.",
)

DARK_FANTASY_TERMS = GenreTerminology(
    origin="Burden",
    origin_plural="Burdens",
    archetype="Calling",
    archetype_plural="Callings",
    ability_power="Dark Art",
    ability_power_plural="Dark Arts",
    power_source="Darkness",
    power_points="Shadow",
    hit_points="Vitality",
    armor_class="Ward",
    constitution="Endurance",
    wisdom="Insight",
    charisma="Will",
    con_short="END",
    wis_short="INS",
    cha_short="WIL",
    level_up_message="You grow stronger, but at what cost?",
    rest_message="You find brief respite from the darkness.",
)

SPACE_OPERA_TERMS = GenreTerminology(
    origin="Homeworld",
    origin_plural="Homeworlds",
    archetype="Role",
    archetype_plural="Roles",
    ability_power="Talent",
    ability_power_plural="Talents",
    power_source="Force",
    power_points="Energy",
    hit_points="Vitality",
    armor_class="Shields",
    intelligence="Knowledge",
    wisdom="Intuition",
    charisma="Presence",
    int_short="KNO",
    wis_short="INT",
    cha_short="PRS",
    level_up_message="Your legend grows across the galaxy!",
    rest_message="You rest aboard your ship between stars.",
)
