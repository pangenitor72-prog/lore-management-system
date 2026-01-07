"""Genre configuration for the d20 rules engine."""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from .terminology import (
    GenreTerminology,
    FANTASY_TERMS,
    SCIFI_TERMS,
    MODERN_TERMS,
    HORROR_TERMS,
    GENERIC_TERMS,
    WESTERN_TERMS,
    CYBERPUNK_TERMS,
    STEAMPUNK_TERMS,
    POSTAPOC_TERMS,
    SUPERHERO_TERMS,
    MYTHOLOGY_TERMS,
    NOIR_TERMS,
    WUXIA_TERMS,
    PIRATE_TERMS,
    DARK_FANTASY_TERMS,
    SPACE_OPERA_TERMS,
)


class GenreId(str, Enum):
    """Available genre presets."""
    FANTASY = "fantasy"
    SCIFI = "scifi"
    MODERN = "modern"
    HORROR = "horror"
    WESTERN = "western"
    CYBERPUNK = "cyberpunk"
    STEAMPUNK = "steampunk"
    POSTAPOC = "postapoc"
    SUPERHERO = "superhero"
    MYTHOLOGY = "mythology"
    NOIR = "noir"
    WUXIA = "wuxia"
    PIRATE = "pirate"
    DARK_FANTASY = "dark_fantasy"
    SPACE_OPERA = "space_opera"
    GENERIC = "generic"
    CUSTOM = "custom"


class GenreConfig(BaseModel):
    """
    Complete configuration for a genre.

    Defines terminology, available origins/archetypes, and flavor.
    """

    id: str  # Can be GenreId or custom string for user-defined genres
    name: str
    description: str
    terminology: GenreTerminology
    icon: str = "🎭"  # Emoji icon for UI display

    # Data paths (relative to data/ directory)
    origins_file: str = "origins.json"
    archetypes_file: str = "archetypes.json"
    abilities_file: str = "abilities.json"
    equipment_file: str = "equipment.json"

    # Genre-specific settings
    has_magic: bool = True  # Whether abilities use "magic" or "tech" flavor
    gritty_mode: bool = False  # More lethal, slower healing
    sanity_system: bool = False  # Track mental state (horror)
    is_custom: bool = False  # User-defined genre

    # Example origins/archetypes for this genre (for quick reference)
    example_origins: List[str] = Field(default_factory=list)
    example_archetypes: List[str] = Field(default_factory=list)

    # For custom genres: inline origin/archetype definitions
    custom_origins: Dict[str, Any] = Field(default_factory=dict)
    custom_archetypes: Dict[str, Any] = Field(default_factory=dict)


# Pre-defined genre configurations
FANTASY_CONFIG = GenreConfig(
    id="fantasy",
    name="Fantasy",
    description="Swords, sorcery, and mythical creatures. Classic D&D 5e style.",
    terminology=FANTASY_TERMS,
    icon="⚔️",
    origins_file="fantasy/origins.json",
    archetypes_file="fantasy/archetypes.json",
    abilities_file="fantasy/abilities.json",
    equipment_file="fantasy/equipment.json",
    has_magic=True,
    example_origins=["Human", "Elf", "Dwarf", "Halfling"],
    example_archetypes=["Fighter", "Rogue", "Cleric", "Wizard"],
)

SCIFI_CONFIG = GenreConfig(
    id="scifi",
    name="Science Fiction",
    description="Space exploration, advanced technology, alien species.",
    terminology=SCIFI_TERMS,
    icon="🚀",
    origins_file="scifi/origins.json",
    archetypes_file="scifi/archetypes.json",
    abilities_file="scifi/abilities.json",
    equipment_file="scifi/equipment.json",
    has_magic=False,
    example_origins=["Human", "Android", "Alien", "Cyborg"],
    example_archetypes=["Soldier", "Hacker", "Pilot", "Medic"],
)

MODERN_CONFIG = GenreConfig(
    id="modern",
    name="Modern",
    description="Contemporary setting with realistic skills and professions.",
    terminology=MODERN_TERMS,
    icon="🏙️",
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
    id="horror",
    name="Horror",
    description="Dark mysteries, supernatural threats, and fragile sanity.",
    terminology=HORROR_TERMS,
    icon="👻",
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

WESTERN_CONFIG = GenreConfig(
    id="western",
    name="Western",
    description="Frontier justice, outlaws, and the untamed wilderness.",
    terminology=WESTERN_TERMS,
    icon="🤠",
    has_magic=False,
    gritty_mode=True,
    example_origins=["Settler", "Native", "Immigrant", "Outlaw"],
    example_archetypes=["Gunslinger", "Sheriff", "Outlaw", "Prospector"],
)

CYBERPUNK_CONFIG = GenreConfig(
    id="cyberpunk",
    name="Cyberpunk",
    description="High tech, low life. Megacorps, hackers, and chrome.",
    terminology=CYBERPUNK_TERMS,
    icon="🌃",
    has_magic=False,
    gritty_mode=True,
    example_origins=["Street Kid", "Corporate", "Nomad", "Synthetic"],
    example_archetypes=["Netrunner", "Solo", "Techie", "Fixer"],
)

STEAMPUNK_CONFIG = GenreConfig(
    id="steampunk",
    name="Steampunk",
    description="Victorian era meets impossible technology and adventure.",
    terminology=STEAMPUNK_TERMS,
    icon="⚙️",
    has_magic=True,
    example_origins=["Aristocrat", "Inventor", "Street Urchin", "Colonial"],
    example_archetypes=["Inventor", "Aeronaut", "Detective", "Automaton"],
)

POSTAPOC_CONFIG = GenreConfig(
    id="postapoc",
    name="Post-Apocalyptic",
    description="Survive in the ashes of civilization. Scavenge, adapt, overcome.",
    terminology=POSTAPOC_TERMS,
    icon="☢️",
    has_magic=False,
    gritty_mode=True,
    example_origins=["Vault Dweller", "Wastelander", "Tribal", "Mutant"],
    example_archetypes=["Scavenger", "Warlord", "Medic", "Mechanic"],
)

SUPERHERO_CONFIG = GenreConfig(
    id="superhero",
    name="Superhero",
    description="Capes, powers, and the eternal struggle of good vs evil.",
    terminology=SUPERHERO_TERMS,
    icon="🦸",
    has_magic=True,
    example_origins=["Mutant", "Alien", "Experiment", "Chosen One"],
    example_archetypes=["Powerhouse", "Speedster", "Mentalist", "Gadgeteer"],
)

MYTHOLOGY_CONFIG = GenreConfig(
    id="mythology",
    name="Mythology",
    description="Heroes of legend, divine quests, and the favor of gods.",
    terminology=MYTHOLOGY_TERMS,
    icon="🏛️",
    has_magic=True,
    example_origins=["Demigod", "Blessed Mortal", "Cursed", "Monster-Kin"],
    example_archetypes=["Champion", "Oracle", "Trickster", "Beast Master"],
)

NOIR_CONFIG = GenreConfig(
    id="noir",
    name="Noir",
    description="Hard-boiled detectives, femme fatales, and moral ambiguity.",
    terminology=NOIR_TERMS,
    icon="🕵️",
    has_magic=False,
    gritty_mode=True,
    example_origins=["War Vet", "Ex-Cop", "Society Dropout", "Immigrant"],
    example_archetypes=["Private Eye", "Grifter", "Muscle", "Reporter"],
)

WUXIA_CONFIG = GenreConfig(
    id="wuxia",
    name="Wuxia",
    description="Martial arts masters, ancient schools, and honor-bound warriors.",
    terminology=WUXIA_TERMS,
    icon="🥋",
    has_magic=True,
    example_origins=["Noble House", "Wanderer", "Monastery", "Outcast"],
    example_archetypes=["Swordsman", "Monk", "Scholar", "Assassin"],
)

GENERIC_CONFIG = GenreConfig(
    id="generic",
    name="Generic",
    description="Neutral terminology for custom settings.",
    terminology=GENERIC_TERMS,
    icon="🎲",
    has_magic=True,
    example_origins=["Origin A", "Origin B", "Origin C", "Origin D"],
    example_archetypes=["Archetype A", "Archetype B", "Archetype C", "Archetype D"],
)

PIRATE_CONFIG = GenreConfig(
    id="pirate",
    name="Pirate",
    description="Swashbuckling adventures on the high seas, buried treasure, and naval battles.",
    terminology=PIRATE_TERMS,
    icon="🏴‍☠️",
    has_magic=True,
    gritty_mode=True,
    example_origins=["Naval Deserter", "Merchant Sailor", "Island Native", "Shipwreck Survivor"],
    example_archetypes=["Captain", "Swashbuckler", "Gunner", "Navigator"],
)

DARK_FANTASY_CONFIG = GenreConfig(
    id="dark_fantasy",
    name="Dark Fantasy",
    description="Grim worlds where hope is scarce, choices have consequences, and nothing comes free.",
    terminology=DARK_FANTASY_TERMS,
    icon="🌑",
    has_magic=True,
    gritty_mode=True,
    sanity_system=True,
    example_origins=["Cursed Noble", "Fallen Knight", "Plague Survivor", "Branded Outcast"],
    example_archetypes=["Hollow", "Pyromancer", "Knight", "Cleric"],
)

SPACE_OPERA_CONFIG = GenreConfig(
    id="space_opera",
    name="Space Opera",
    description="Epic galactic adventures with starships, alien empires, and legendary heroes.",
    terminology=SPACE_OPERA_TERMS,
    icon="🌌",
    has_magic=True,
    example_origins=["Core Worlder", "Rim Dweller", "Clone Soldier", "Force Sensitive"],
    example_archetypes=["Jedi", "Smuggler", "Bounty Hunter", "Diplomat"],
)

# Registry of all built-in genres
GENRES: Dict[str, GenreConfig] = {
    "fantasy": FANTASY_CONFIG,
    "scifi": SCIFI_CONFIG,
    "modern": MODERN_CONFIG,
    "horror": HORROR_CONFIG,
    "western": WESTERN_CONFIG,
    "cyberpunk": CYBERPUNK_CONFIG,
    "steampunk": STEAMPUNK_CONFIG,
    "postapoc": POSTAPOC_CONFIG,
    "superhero": SUPERHERO_CONFIG,
    "mythology": MYTHOLOGY_CONFIG,
    "noir": NOIR_CONFIG,
    "wuxia": WUXIA_CONFIG,
    "pirate": PIRATE_CONFIG,
    "dark_fantasy": DARK_FANTASY_CONFIG,
    "space_opera": SPACE_OPERA_CONFIG,
    "generic": GENERIC_CONFIG,
}

# Custom genres storage (populated at runtime)
CUSTOM_GENRES: Dict[str, GenreConfig] = {}


def get_genre(genre_id: str) -> GenreConfig:
    """Get a genre configuration by ID."""
    # Check built-in genres first
    if genre_id in GENRES:
        return GENRES[genre_id]
    # Check custom genres
    if genre_id in CUSTOM_GENRES:
        return CUSTOM_GENRES[genre_id]
    # Default to fantasy
    return GENRES["fantasy"]


def get_available_genres() -> List[Dict]:
    """Get list of available genres for UI."""
    all_genres = {**GENRES, **CUSTOM_GENRES}
    return [
        {
            "id": genre.id,
            "name": genre.name,
            "description": genre.description,
            "icon": genre.icon,
            "example_origins": genre.example_origins,
            "example_archetypes": genre.example_archetypes,
            "is_custom": genre.is_custom,
            "has_magic": genre.has_magic,
            "gritty_mode": genre.gritty_mode,
            "sanity_system": genre.sanity_system,
        }
        for genre in all_genres.values()
    ]


def register_custom_genre(genre_config: GenreConfig) -> None:
    """Register a custom genre configuration."""
    genre_config.is_custom = True
    CUSTOM_GENRES[genre_config.id] = genre_config


def create_custom_genre(
    genre_id: str,
    name: str,
    description: str,
    icon: str = "🎭",
    has_magic: bool = True,
    gritty_mode: bool = False,
    sanity_system: bool = False,
    origin_term: str = "Origin",
    archetype_term: str = "Archetype",
    ability_term: str = "Ability",
    power_source: str = "Power",
    example_origins: List[str] = None,
    example_archetypes: List[str] = None,
) -> GenreConfig:
    """Create and register a custom genre."""
    terminology = GenreTerminology(
        origin=origin_term,
        origin_plural=f"{origin_term}s",
        archetype=archetype_term,
        archetype_plural=f"{archetype_term}s",
        ability_power=ability_term,
        ability_power_plural=f"{ability_term}s",
        power_source=power_source,
    )

    config = GenreConfig(
        id=genre_id,
        name=name,
        description=description,
        terminology=terminology,
        icon=icon,
        has_magic=has_magic,
        gritty_mode=gritty_mode,
        sanity_system=sanity_system,
        is_custom=True,
        example_origins=example_origins or [],
        example_archetypes=example_archetypes or [],
    )

    register_custom_genre(config)
    return config


def delete_custom_genre(genre_id: str) -> bool:
    """Delete a custom genre. Returns True if deleted."""
    if genre_id in CUSTOM_GENRES:
        del CUSTOM_GENRES[genre_id]
        return True
    return False


def get_genre_categories() -> Dict[str, List[str]]:
    """Get genres organized by category for UI display."""
    return {
        "Popular": ["fantasy", "scifi", "horror", "modern"],
        "Historical": ["western", "mythology", "noir", "wuxia", "pirate"],
        "Speculative": ["cyberpunk", "steampunk", "postapoc", "superhero", "space_opera"],
        "Dark & Gritty": ["dark_fantasy"],
        "Other": ["generic"] + list(CUSTOM_GENRES.keys()),
    }
