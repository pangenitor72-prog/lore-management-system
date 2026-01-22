"""
SRD Data Loader - Singleton service for loading and accessing D&D 5e SRD data.

Loads all data at startup, provides fast lookups with genre conversion support.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache


class SRDDataLoader:
    """
    Singleton data loader for SRD content.

    Usage:
        loader = SRDDataLoader.get_instance()
        spell = loader.get_spell("fireball", genre="fantasy")
        all_cantrips = loader.get_spells_by_level(0)
        wizard_spells = loader.get_spells_for_class("wizard")
    """

    _instance: Optional["SRDDataLoader"] = None
    _initialized: bool = False

    def __new__(cls) -> "SRDDataLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "SRDDataLoader":
        """Get the singleton instance, initializing if needed."""
        instance = cls()
        if not cls._initialized:
            instance._load_all()
            cls._initialized = True
        return instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing)."""
        cls._instance = None
        cls._initialized = False

    def __init__(self):
        if not SRDDataLoader._initialized:
            self._data_dir = Path(__file__).parent
            self._srd_dir = self._data_dir / "srd"

            # Data storage
            self._spells: Dict[str, Dict[str, Any]] = {}
            self._spells_by_level: Dict[int, List[str]] = {}
            self._spells_by_class: Dict[str, List[str]] = {}
            self._classes: Dict[str, Dict[str, Any]] = {}
            self._races: Dict[str, Dict[str, Any]] = {}
            self._equipment: Dict[str, Any] = {}
            self._genre_mappings: Dict[str, Any] = {}

    def _load_all(self) -> None:
        """Load all SRD data from JSON files."""
        self._load_spells()
        self._load_classes()
        self._load_races()
        self._load_equipment()
        self._load_genre_mappings()
        self._build_indexes()

    def _load_json(self, path: Path) -> Dict:
        """Load a JSON file with UTF-8 encoding."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Data file not found: {path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in {path}: {e}")
            return {}

    def _load_spells(self) -> None:
        """Load spells from srd/spells.json."""
        data = self._load_json(self._srd_dir / "spells.json")

        level_map = {
            "cantrips": 0,
            "level_1": 1, "level_2": 2, "level_3": 3,
            "level_4": 4, "level_5": 5, "level_6": 6,
            "level_7": 7, "level_8": 8, "level_9": 9
        }

        for level_key, level_num in level_map.items():
            spells_at_level = data.get(level_key, {})
            for spell_id, spell_data in spells_at_level.items():
                spell_data["id"] = spell_id
                spell_data["level"] = level_num
                self._spells[spell_id] = spell_data

    def _load_classes(self) -> None:
        """Load classes from srd/classes.json."""
        self._classes = self._load_json(self._srd_dir / "classes.json")

        # Add id field to each class
        for class_id, class_data in self._classes.items():
            class_data["id"] = class_id

    def _load_races(self) -> None:
        """Load races from srd/races.json."""
        self._races = self._load_json(self._srd_dir / "races.json")

        # Add id field to each race
        for race_id, race_data in self._races.items():
            race_data["id"] = race_id

    def _load_equipment(self) -> None:
        """Load equipment from equipment.json."""
        self._equipment = self._load_json(self._data_dir / "equipment.json")

    def _load_genre_mappings(self) -> None:
        """Load genre conversion mappings."""
        self._genre_mappings = self._load_json(self._data_dir / "genre_mappings.json")

    def _build_indexes(self) -> None:
        """Build lookup indexes for fast queries."""
        # Index spells by level
        self._spells_by_level = {i: [] for i in range(10)}
        for spell_id, spell in self._spells.items():
            level = spell.get("level", 0)
            self._spells_by_level[level].append(spell_id)

        # Index spells by class
        self._spells_by_class = {}
        for spell_id, spell in self._spells.items():
            for cls in spell.get("classes", []):
                cls_lower = cls.lower()
                if cls_lower not in self._spells_by_class:
                    self._spells_by_class[cls_lower] = []
                self._spells_by_class[cls_lower].append(spell_id)

    # =========================================================================
    # SPELL ACCESS
    # =========================================================================

    def get_spell(self, spell_id: str, genre: str = "fantasy") -> Optional[Dict[str, Any]]:
        """Get a spell by ID, optionally converted to genre flavor."""
        spell = self._spells.get(spell_id)
        if spell is None:
            return None

        if genre == "fantasy":
            return spell.copy()

        return self._convert_spell_to_genre(spell, genre)

    def get_spells_by_level(self, level: int, genre: str = "fantasy") -> List[Dict[str, Any]]:
        """Get all spells of a given level."""
        spell_ids = self._spells_by_level.get(level, [])
        return [self.get_spell(sid, genre) for sid in spell_ids if self.get_spell(sid, genre)]

    def get_spells_for_class(self, class_id: str, genre: str = "fantasy") -> List[Dict[str, Any]]:
        """Get all spells available to a class."""
        spell_ids = self._spells_by_class.get(class_id.lower(), [])
        return [self.get_spell(sid, genre) for sid in spell_ids if self.get_spell(sid, genre)]

    def get_cantrips_for_class(self, class_id: str, genre: str = "fantasy") -> List[Dict[str, Any]]:
        """Get all cantrips available to a class."""
        return [s for s in self.get_spells_for_class(class_id, genre) if s.get("level") == 0]

    def get_all_spells(self, genre: str = "fantasy") -> List[Dict[str, Any]]:
        """Get all spells."""
        return [self.get_spell(sid, genre) for sid in self._spells.keys()]

    def search_spells(self, query: str, genre: str = "fantasy") -> List[Dict[str, Any]]:
        """Search spells by name or description."""
        query_lower = query.lower()
        results = []
        for spell_id, spell in self._spells.items():
            if (query_lower in spell.get("name", "").lower() or
                query_lower in spell.get("description", "").lower()):
                results.append(self.get_spell(spell_id, genre))
        return results

    # =========================================================================
    # CLASS ACCESS
    # =========================================================================

    def get_class(self, class_id: str, genre: str = "fantasy") -> Optional[Dict[str, Any]]:
        """Get a class by ID, optionally converted to genre flavor."""
        cls = self._classes.get(class_id.lower())
        if cls is None:
            return None

        if genre == "fantasy":
            return cls.copy()

        return self._convert_class_to_genre(cls, genre)

    def get_all_classes(self, genre: str = "fantasy") -> List[Dict[str, Any]]:
        """Get all classes."""
        return [self.get_class(cid, genre) for cid in self._classes.keys()]

    # =========================================================================
    # RACE ACCESS
    # =========================================================================

    def get_race(self, race_id: str, genre: str = "fantasy") -> Optional[Dict[str, Any]]:
        """Get a race by ID, optionally converted to genre flavor."""
        race = self._races.get(race_id.lower())
        if race is None:
            return None

        if genre == "fantasy":
            return race.copy()

        return self._convert_race_to_genre(race, genre)

    def get_all_races(self, genre: str = "fantasy") -> List[Dict[str, Any]]:
        """Get all races."""
        return [self.get_race(rid, genre) for rid in self._races.keys()]

    # =========================================================================
    # EQUIPMENT ACCESS
    # =========================================================================

    def get_weapon(self, weapon_id: str) -> Optional[Dict[str, Any]]:
        """Get a weapon by ID."""
        weapons = self._equipment.get("weapons", {})
        weapon = weapons.get(weapon_id)
        if weapon:
            result = weapon.copy()
            result["id"] = weapon_id
            return result
        return None

    def get_armor(self, armor_id: str) -> Optional[Dict[str, Any]]:
        """Get an armor by ID."""
        armor_items = self._equipment.get("armor", {})
        armor = armor_items.get(armor_id)
        if armor:
            result = armor.copy()
            result["id"] = armor_id
            return result
        return None

    def get_pack(self, pack_id: str) -> Optional[Dict[str, Any]]:
        """Get a pack by ID."""
        packs = self._equipment.get("packs", {})
        pack = packs.get(pack_id)
        if pack:
            result = pack.copy()
            result["id"] = pack_id
            return result
        return None

    def get_equipment_choices_for_class(self, class_id: str) -> Optional[Dict[str, Any]]:
        """Get equipment choices for a class."""
        class_choices = self._equipment.get("class_choices", {})
        return class_choices.get(class_id.lower())

    def get_all_equipment(self) -> Dict[str, Any]:
        """Get all equipment data."""
        return self._equipment.copy()

    # =========================================================================
    # GENRE CONVERSION
    # =========================================================================

    def _convert_spell_to_genre(self, spell: Dict[str, Any], genre: str) -> Dict[str, Any]:
        """Convert a spell's flavor text to a different genre."""
        converted = spell.copy()

        # Convert school name
        schools = self._genre_mappings.get("schools", {}).get(genre, {})
        original_school = spell.get("school", "")
        converted["school_display"] = schools.get(original_school, original_school.title())

        # Convert damage types in description
        damage_types = self._genre_mappings.get("damage_types", {}).get(genre, {})
        desc = spell.get("description", "")
        for fantasy_type, genre_type in damage_types.items():
            desc = desc.replace(fantasy_type, genre_type)
        converted["description"] = desc

        # Add genre-specific terminology
        terminology = self._genre_mappings.get("terminology", {}).get(genre, {})
        converted["terminology"] = terminology

        return converted

    def _convert_class_to_genre(self, cls: Dict[str, Any], genre: str) -> Dict[str, Any]:
        """Convert a class's flavor to a different genre."""
        converted = cls.copy()

        class_mappings = self._genre_mappings.get("class_mappings", {}).get(genre, {})
        class_id = cls.get("id", "")

        if class_id in class_mappings:
            mapping = class_mappings[class_id]
            converted["display_name"] = mapping.get("name", converted.get("display_name"))
            converted["genre_description"] = mapping.get("description", "")

        return converted

    def _convert_race_to_genre(self, race: Dict[str, Any], genre: str) -> Dict[str, Any]:
        """Convert a race's flavor to a different genre."""
        converted = race.copy()

        race_mappings = self._genre_mappings.get("race_mappings", {}).get(genre, {})
        race_id = race.get("id", "")

        if race_id in race_mappings:
            mapping = race_mappings[race_id]
            converted["display_name"] = mapping.get("name", converted.get("display_name"))
            converted["genre_description"] = mapping.get("description", "")

        return converted

    def get_terminology(self, genre: str = "fantasy") -> Dict[str, str]:
        """Get terminology mappings for a genre."""
        return self._genre_mappings.get("terminology", {}).get(genre, {})

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, int]:
        """Get counts of loaded data."""
        return {
            "spells": len(self._spells),
            "classes": len(self._classes),
            "races": len(self._races),
            "cantrips": len(self._spells_by_level.get(0, [])),
            "level_1_spells": len(self._spells_by_level.get(1, [])),
            "level_9_spells": len(self._spells_by_level.get(9, [])),
        }


# Convenience function for quick access
def get_srd_loader() -> SRDDataLoader:
    """Get the SRD data loader singleton."""
    return SRDDataLoader.get_instance()


# Export commonly used functions
def get_spell(spell_id: str, genre: str = "fantasy") -> Optional[Dict[str, Any]]:
    """Get a spell by ID."""
    return get_srd_loader().get_spell(spell_id, genre)


def get_class(class_id: str, genre: str = "fantasy") -> Optional[Dict[str, Any]]:
    """Get a class by ID."""
    return get_srd_loader().get_class(class_id, genre)


def get_race(race_id: str, genre: str = "fantasy") -> Optional[Dict[str, Any]]:
    """Get a race by ID."""
    return get_srd_loader().get_race(race_id, genre)


def get_all_spells(genre: str = "fantasy") -> List[Dict[str, Any]]:
    """Get all spells."""
    return get_srd_loader().get_all_spells(genre)


def get_all_classes(genre: str = "fantasy") -> List[Dict[str, Any]]:
    """Get all classes."""
    return get_srd_loader().get_all_classes(genre)


def get_all_races(genre: str = "fantasy") -> List[Dict[str, Any]]:
    """Get all races."""
    return get_srd_loader().get_all_races(genre)
