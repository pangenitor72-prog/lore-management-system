"""Genre configuration for the d20 rules engine."""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .terminology import (
    GenreTerminology,
    FANTASY_TERMS,
    SCIFI_TERMS,
    MODERN_TERMS,
    HORROR_TERMS,
    GENERIC_TERMS,
)


class GenreId(str, Enum):
    """Available genre presets."""
    FANTASY = "fantasy"
    SCIFI = "scifi"
    MODERN = "modern"
    HORROR = "horror"
    GENERIC = "generic"


class GenreConfig(BaseModel):
    """
    Complete configuration for a genre.

    Defines terminology, available origins/archetypes, and flavor.
    """

    id: GenreId
    name: str
    description: str
    terminology: GenreTerminology

    # Data paths (relative to data/ directory)
    origins_file: str = "origins.json"
    archetypes_file: str = "archetypes.json"
    abilities_file: str = "abilities.json"
    equipment_file: str = "equipment.json"

    # Genre-specific settings
    has_magic: bool = True  # Whether abilities use "magic" or "tech" flavor
    gritty_mode: bool = False  # More lethal, slower healing
    sanity_system: bool = False  # Track mental state (horror)

    # Example origins/archetypes for this genre (for quick reference)
    example_origins: List[str] = Field(default_factory=list)
    example_archetypes: List[str] = Field(default_factory=list)


# Pre-defined genre configurations
FANTASY_CONFIG = GenreConfig(
    id=GenreId.FANTASY,
    name="Fantasy",
    description="Swords, sorcery, and mythical creatures. Classic D&D 5e style.",
    terminology=FANTASY_TERMS,
    origins_file="fantasy/origins.json",
    archetypes_file="fantasy/archetypes.json",
    abilities_file="fantasy/abilities.json",
    equipment_file="fantasy/equipment.json",
    has_magic=True,
    example_origins=["Human", "Elf", "Dwarf", "Halfling"],
    example_archetypes=["Fighter", "Rogue", "Cleric", "Wizard"],
)

SCIFI_CONFIG = GenreConfig(
    id=GenreId.SCIFI,
    name="Science Fiction",
    description="Space exploration, advanced technology, alien species.",
    terminology=SCIFI_TERMS,
    origins_file="scifi/origins.json",
    archetypes_file="scifi/archetypes.json",
    abilities_file="scifi/abilities.json",
    equipment_file="scifi/equipment.json",
    has_magic=False,
    example_origins=["Human", "Android", "Alien", "Cyborg"],
    example_archetypes=["Soldier", "Hacker", "Pilot", "Medic"],
)

MODERN_CONFIG = GenreConfig(
    id=GenreId.MODERN,
    name="Modern",
    description="Contemporary setting with realistic skills and professions.",
    terminology=MODERN_TERMS,
    origins_file="modern/origins.json",
    archetypes_file="modern/archetypes.json",
    abilities_file="modern/abilities.json",
    equipment_file="modern/equipment.json",
    has_magic=False,
    gritty_mode=True,
    example_origins=["Urban", "Rural", "Military", "Academic"],
    example_archetypes=["Detective", "Soldier", "Doctor", "Engineer"],
)

HORROR_CONFIG = GenreConfig(
    id=GenreId.HORROR,
    name="Horror",
    description="Dark mysteries, supernatural threats, and fragile sanity.",
    terminology=HORROR_TERMS,
    origins_file="horror/origins.json",
    archetypes_file="horror/archetypes.json",
    abilities_file="horror/abilities.json",
    equipment_file="horror/equipment.json",
    has_magic=True,
    gritty_mode=True,
    sanity_system=True,
    example_origins=["Academic", "Working Class", "Aristocrat", "Outsider"],
    example_archetypes=["Investigator", "Occultist", "Survivor", "Medium"],
)

GENERIC_CONFIG = GenreConfig(
    id=GenreId.GENERIC,
    name="Generic",
    description="Neutral terminology for custom settings.",
    terminology=GENERIC_TERMS,
    has_magic=True,
    example_origins=["Origin A", "Origin B", "Origin C", "Origin D"],
    example_archetypes=["Archetype A", "Archetype B", "Archetype C", "Archetype D"],
)

# Registry of all genres
GENRES: Dict[GenreId, GenreConfig] = {
    GenreId.FANTASY: FANTASY_CONFIG,
    GenreId.SCIFI: SCIFI_CONFIG,
    GenreId.MODERN: MODERN_CONFIG,
    GenreId.HORROR: HORROR_CONFIG,
    GenreId.GENERIC: GENERIC_CONFIG,
}


def get_genre(genre_id: str) -> GenreConfig:
    """Get a genre configuration by ID."""
    try:
        return GENRES[GenreId(genre_id)]
    except (ValueError, KeyError):
        return GENRES[GenreId.FANTASY]  # Default to fantasy


def get_available_genres() -> List[Dict]:
    """Get list of available genres for UI."""
    return [
        {
            "id": genre.id.value,
            "name": genre.name,
            "description": genre.description,
            "example_origins": genre.example_origins,
            "example_archetypes": genre.example_archetypes,
        }
        for genre in GENRES.values()
    ]
