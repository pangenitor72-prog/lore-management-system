"""
Origin definitions for the d20 rules engine.

Origins define where a character comes from - their species, background,
or heritage. In fantasy this is "Race", in sci-fi "Species", in modern "Background".
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class OriginData(BaseModel):
    """
    Origin definition with ability bonuses and traits.

    Generic base class that works across all genres.
    """
    id: str  # Unique identifier
    display_name: str
    description: str
    ability_bonuses: Dict[str, int] = Field(default_factory=dict)
    speed: int = 30
    size: str = "Medium"
    traits: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=lambda: ["Common"])

    # For guided/concept mode
    personality_hint: str = ""
    suggested_archetypes: List[str] = Field(default_factory=list)

    # Genre metadata
    genre: str = "generic"


# =============================================================================
# FANTASY ORIGINS (D&D 5e Races)
# =============================================================================

class FantasyOrigin(str, Enum):
    """Fantasy genre origins (traditional D&D races)."""
    HUMAN = "human"
    ELF = "elf"
    DWARF = "dwarf"
    HALFLING = "halfling"


FANTASY_ORIGINS: Dict[str, OriginData] = {
    "human": OriginData(
        id="human",
        display_name="Human",
        description="Versatile and ambitious, humans are the most adaptable of all races.",
        ability_bonuses={
            "strength": 1, "dexterity": 1, "constitution": 1,
            "intelligence": 1, "wisdom": 1, "charisma": 1,
        },
        speed=30,
        size="Medium",
        traits=["Versatile (+1 to all abilities)", "Extra Language"],
        languages=["Common", "One extra language"],
        personality_hint="Ambitious, adaptable, driven by short lifespans to achieve greatness",
        suggested_archetypes=["fighter", "rogue", "cleric", "wizard"],
        genre="fantasy",
    ),
    "elf": OriginData(
        id="elf",
        display_name="Elf",
        description="Graceful and long-lived, elves possess keen senses and a deep connection to magic.",
        ability_bonuses={"dexterity": 2},
        speed=30,
        size="Medium",
        traits=[
            "Darkvision (60 ft)",
            "Keen Senses (Perception proficiency)",
            "Fey Ancestry (advantage vs charm, immune to sleep)",
            "Trance (4 hours of meditation instead of 8 hours sleep)",
        ],
        languages=["Common", "Elvish"],
        personality_hint="Patient, observant, values beauty and artistry, ancient perspective",
        suggested_archetypes=["rogue", "wizard"],
        genre="fantasy",
    ),
    "dwarf": OriginData(
        id="dwarf",
        display_name="Dwarf",
        description="Stout and resilient, dwarves are master craftsmen with an affinity for stone and metal.",
        ability_bonuses={"constitution": 2},
        speed=25,
        size="Medium",
        traits=[
            "Darkvision (60 ft)",
            "Dwarven Resilience (advantage vs poison, resistance to poison damage)",
            "Stonecunning (History bonus for stonework)",
            "Tool Proficiency (smith's, brewer's, or mason's tools)",
        ],
        languages=["Common", "Dwarvish"],
        personality_hint="Stubborn, loyal, values tradition and craftsmanship, long memory",
        suggested_archetypes=["fighter", "cleric"],
        genre="fantasy",
    ),
    "halfling": OriginData(
        id="halfling",
        display_name="Halfling",
        description="Small but nimble, halflings are cheerful folk known for their luck and courage.",
        ability_bonuses={"dexterity": 2},
        speed=25,
        size="Small",
        traits=[
            "Lucky (reroll 1s on attacks, checks, saves)",
            "Brave (advantage vs frightened)",
            "Halfling Nimbleness (move through larger creatures' spaces)",
        ],
        languages=["Common", "Halfling"],
        personality_hint="Cheerful, curious, homebodies who love comfort but rise to adventure",
        suggested_archetypes=["rogue"],
        genre="fantasy",
    ),
}


# =============================================================================
# SCI-FI ORIGINS
# =============================================================================

class SciFiOrigin(str, Enum):
    """Sci-fi genre origins (species/backgrounds)."""
    HUMAN = "human"
    ANDROID = "android"
    ALIEN = "alien"
    CYBORG = "cyborg"


SCIFI_ORIGINS: Dict[str, OriginData] = {
    "human": OriginData(
        id="human",
        display_name="Human",
        description="Adaptable and ambitious, humans have spread across the galaxy through sheer determination.",
        ability_bonuses={
            "strength": 1, "dexterity": 1, "constitution": 1,
            "intelligence": 1, "wisdom": 1, "charisma": 1,
        },
        speed=30,
        size="Medium",
        traits=["Adaptable (+1 to all abilities)", "Quick Learner"],
        languages=["Galactic Standard", "One regional language"],
        personality_hint="Resourceful, driven, believes in potential over heritage",
        suggested_archetypes=["soldier", "hacker", "pilot", "medic"],
        genre="scifi",
    ),
    "android": OriginData(
        id="android",
        display_name="Android",
        description="Synthetic beings with advanced AI, androids process information with inhuman precision.",
        ability_bonuses={"intelligence": 2, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Machine Mind (advantage on logic puzzles, immune to charm)",
            "No Sleep (does not need rest, but requires maintenance)",
            "Perfect Recall (advantage on memory-based checks)",
        ],
        languages=["Galactic Standard", "Binary"],
        personality_hint="Logical, curious about emotions, struggles with intuition",
        suggested_archetypes=["hacker", "medic"],
        genre="scifi",
    ),
    "alien": OriginData(
        id="alien",
        display_name="Alien",
        description="A being from a distant world, with physiology and perspectives unlike humanity.",
        ability_bonuses={"wisdom": 2, "dexterity": 1},
        speed=30,
        size="Medium",
        traits=[
            "Alien Physiology (advantage on one type of environmental hazard)",
            "Strange Senses (can perceive in an unusual spectrum)",
            "Outsider Perspective (advantage on insight vs humans)",
        ],
        languages=["Galactic Standard", "Native Tongue"],
        personality_hint="Observant of human customs, values different things, unique worldview",
        suggested_archetypes=["pilot", "medic"],
        genre="scifi",
    ),
    "cyborg": OriginData(
        id="cyborg",
        display_name="Cyborg",
        description="Humans enhanced with cybernetic implants, blending flesh and machine.",
        ability_bonuses={"strength": 1, "dexterity": 1, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Cybernetic Enhancement (choose one: +2 STR, +2 DEX, or +2 CON)",
            "Built-in Systems (has one integrated tool or weapon)",
            "EMP Vulnerability (disadvantage when hit by electromagnetic attacks)",
        ],
        languages=["Galactic Standard"],
        personality_hint="Struggles with identity, pragmatic about body modification",
        suggested_archetypes=["soldier", "hacker"],
        genre="scifi",
    ),
}


# =============================================================================
# MODERN/HORROR ORIGINS
# =============================================================================

class ModernOrigin(str, Enum):
    """Modern/horror genre origins (backgrounds)."""
    URBAN = "urban"
    RURAL = "rural"
    MILITARY = "military"
    ACADEMIC = "academic"


MODERN_ORIGINS: Dict[str, OriginData] = {
    "urban": OriginData(
        id="urban",
        display_name="Urban",
        description="Raised in the city, you know how to navigate crowds, read people, and find resources.",
        ability_bonuses={"charisma": 2, "intelligence": 1},
        speed=30,
        size="Medium",
        traits=[
            "Street Smart (advantage on checks to navigate cities)",
            "Network (you know people who know people)",
            "Jaded (advantage vs fear from mundane sources)",
        ],
        languages=["English", "One other language"],
        personality_hint="Skeptical, resourceful, values connections, seen it all",
        suggested_archetypes=["detective", "doctor"],
        genre="modern",
    ),
    "rural": OriginData(
        id="rural",
        display_name="Rural",
        description="From the countryside, you have practical skills and a connection to the land.",
        ability_bonuses={"constitution": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Hardy (advantage on checks vs weather and fatigue)",
            "Self-Reliant (proficient with improvised tools)",
            "Close Community (loyal allies but outsider suspicion)",
        ],
        languages=["English"],
        personality_hint="Practical, honest, distrustful of outsiders, values hard work",
        suggested_archetypes=["soldier", "engineer"],
        genre="modern",
    ),
    "military": OriginData(
        id="military",
        display_name="Military",
        description="Trained in the armed forces, you have discipline, combat skills, and trauma.",
        ability_bonuses={"strength": 1, "dexterity": 1, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Combat Training (proficient with all weapons)",
            "Discipline (advantage vs fear in combat)",
            "Haunted (disadvantage on checks to relax or open up)",
        ],
        languages=["English", "Military jargon"],
        personality_hint="Disciplined, hypervigilant, bonds with squad, follows orders",
        suggested_archetypes=["soldier"],
        genre="modern",
    ),
    "academic": OriginData(
        id="academic",
        display_name="Academic",
        description="Educated in universities, you have deep knowledge but limited street experience.",
        ability_bonuses={"intelligence": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Research Expert (advantage on checks to find information)",
            "Specialist (deep expertise in one field)",
            "Ivory Tower (disadvantage on streetwise checks)",
        ],
        languages=["English", "One ancient or academic language"],
        personality_hint="Curious, analytical, sometimes naive, values knowledge",
        suggested_archetypes=["detective", "doctor", "engineer"],
        genre="modern",
    ),
}


# =============================================================================
# ORIGIN REGISTRY
# =============================================================================

ORIGINS_BY_GENRE: Dict[str, Dict[str, OriginData]] = {
    "fantasy": FANTASY_ORIGINS,
    "scifi": SCIFI_ORIGINS,
    "modern": MODERN_ORIGINS,
    "horror": MODERN_ORIGINS,  # Horror uses modern backgrounds
}


def get_origin(origin_id: str, genre: str = "fantasy") -> Optional[OriginData]:
    """Get origin data by ID and genre."""
    genre_origins = ORIGINS_BY_GENRE.get(genre, FANTASY_ORIGINS)
    return genre_origins.get(origin_id)


def get_origins_for_genre(genre: str = "fantasy") -> List[OriginData]:
    """Get all available origins for a genre."""
    genre_origins = ORIGINS_BY_GENRE.get(genre, FANTASY_ORIGINS)
    return list(genre_origins.values())


# =============================================================================
# BACKWARD COMPATIBILITY (D&D 5e aliases)
# =============================================================================

# Keep old names working
RaceName = FantasyOrigin
RaceData = OriginData
RACES = FANTASY_ORIGINS


def get_race(name) -> OriginData:
    """Backward compatible: get race by name."""
    if hasattr(name, 'value'):
        name = name.value
    return FANTASY_ORIGINS.get(name)


def get_all_races() -> List[OriginData]:
    """Backward compatible: get all fantasy races."""
    return list(FANTASY_ORIGINS.values())
