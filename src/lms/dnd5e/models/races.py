"""D&D 5e Race definitions (Phase 1: 4 core races)."""

from enum import Enum
from typing import Dict, List
from pydantic import BaseModel


class RaceName(str, Enum):
    """Available races in Phase 1."""
    HUMAN = "human"
    ELF = "elf"
    DWARF = "dwarf"
    HALFLING = "halfling"


class RaceData(BaseModel):
    """Race definition with ability bonuses and traits."""
    name: RaceName
    display_name: str
    description: str
    ability_bonuses: Dict[str, int]  # e.g., {"dexterity": 2}
    speed: int = 30
    size: str = "Medium"
    traits: List[str] = []
    languages: List[str] = ["Common"]

    # For guided/concept mode
    personality_hint: str = ""
    suggested_classes: List[str] = []


# Phase 1 Race Definitions
RACES: Dict[RaceName, RaceData] = {
    RaceName.HUMAN: RaceData(
        name=RaceName.HUMAN,
        display_name="Human",
        description="Versatile and ambitious, humans are the most adaptable of all races.",
        ability_bonuses={
            "strength": 1,
            "dexterity": 1,
            "constitution": 1,
            "intelligence": 1,
            "wisdom": 1,
            "charisma": 1,
        },
        speed=30,
        size="Medium",
        traits=["Versatile (+1 to all abilities)", "Extra Language"],
        languages=["Common", "One extra language"],
        personality_hint="Ambitious, adaptable, driven by short lifespans to achieve greatness",
        suggested_classes=["fighter", "rogue", "cleric", "wizard"],
    ),

    RaceName.ELF: RaceData(
        name=RaceName.ELF,
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
        suggested_classes=["rogue", "wizard"],
    ),

    RaceName.DWARF: RaceData(
        name=RaceName.DWARF,
        display_name="Dwarf",
        description="Stout and resilient, dwarves are master craftsmen with an affinity for stone and metal.",
        ability_bonuses={"constitution": 2},
        speed=25,  # Dwarves are slower
        size="Medium",
        traits=[
            "Darkvision (60 ft)",
            "Dwarven Resilience (advantage vs poison, resistance to poison damage)",
            "Stonecunning (History bonus for stonework)",
            "Tool Proficiency (smith's, brewer's, or mason's tools)",
        ],
        languages=["Common", "Dwarvish"],
        personality_hint="Stubborn, loyal, values tradition and craftsmanship, long memory",
        suggested_classes=["fighter", "cleric"],
    ),

    RaceName.HALFLING: RaceData(
        name=RaceName.HALFLING,
        display_name="Halfling",
        description="Small but nimble, halflings are cheerful folk known for their luck and courage.",
        ability_bonuses={"dexterity": 2},
        speed=25,  # Halflings are slower
        size="Small",
        traits=[
            "Lucky (reroll 1s on attacks, checks, saves)",
            "Brave (advantage vs frightened)",
            "Halfling Nimbleness (move through larger creatures' spaces)",
        ],
        languages=["Common", "Halfling"],
        personality_hint="Cheerful, curious, homebodies who love comfort but rise to adventure",
        suggested_classes=["rogue"],
    ),
}


def get_race(name: RaceName) -> RaceData:
    """Get race data by name."""
    return RACES[name]


def get_all_races() -> List[RaceData]:
    """Get all available races."""
    return list(RACES.values())
