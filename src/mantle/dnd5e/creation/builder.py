"""
CharacterBuilder - Fluent interface for building CharacterSheet instances.

Provides a simple builder pattern for character creation that integrates
with the genre-aware origin/archetype system.
"""

import uuid
import logging
from typing import List, Optional, Dict, Any

from ..models.ability_scores import AbilityScores, AbilityName
from ..models.origins import get_origin, get_origins_for_genre
from ..models.archetypes import get_archetype, get_archetypes_for_genre, get_starting_hp
from ..models.character_sheet import CharacterSheet
from ..genre.config import get_genre

logger = logging.getLogger(__name__)


# Standard array for D&D 5e
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]


class CharacterBuilder:
    """
    Fluent builder for creating CharacterSheet instances.

    Supports genre-aware character creation with MANTLE vocabulary
    (custom origins/archetypes that map to D&D base types).

    Usage:
        builder = CharacterBuilder(genre="fantasy")
        builder.set_name("Thorin")
        builder.set_origin("dwarven_smith", base_type="dwarf")
        builder.set_archetype("battlemaster", base_type="fighter")
        builder.set_abilities_from_priorities(["strength", "constitution"])
        builder.set_skill_proficiencies(["athletics", "intimidation"])
        character = builder.build()
    """

    def __init__(self, genre: str = "fantasy"):
        """Initialize the builder for a specific genre."""
        self.genre = genre
        self.genre_config = get_genre(genre)

        # Character data
        self._name: Optional[str] = None
        self._player_id: str = ""
        self._origin_id: Optional[str] = None
        self._origin_base_type: Optional[str] = None
        self._archetype_id: Optional[str] = None
        self._archetype_base_type: Optional[str] = None
        self._ability_scores: Optional[AbilityScores] = None
        self._skill_proficiencies: List[str] = []
        self._level: int = 1
        self._background: str = ""

    def set_name(self, name: str) -> "CharacterBuilder":
        """Set the character's name."""
        self._name = name.strip()
        return self

    def set_player_id(self, player_id: str) -> "CharacterBuilder":
        """Set the player ID."""
        self._player_id = player_id
        return self

    def set_origin(
        self,
        origin_id: str,
        base_type: Optional[str] = None,
    ) -> "CharacterBuilder":
        """
        Set the character's origin (race/species).

        Args:
            origin_id: The MANTLE origin ID (world-specific, e.g., "dwarven_smith")
            base_type: The D&D base type for mechanics lookup (e.g., "dwarf")
        """
        self._origin_id = origin_id
        self._origin_base_type = base_type or origin_id
        return self

    def set_archetype(
        self,
        archetype_id: str,
        base_type: Optional[str] = None,
    ) -> "CharacterBuilder":
        """
        Set the character's archetype (class/profession).

        Args:
            archetype_id: The MANTLE archetype ID (world-specific, e.g., "shadowblade")
            base_type: The D&D base type for mechanics lookup (e.g., "rogue")
        """
        self._archetype_id = archetype_id
        self._archetype_base_type = base_type or archetype_id
        return self

    def set_level(self, level: int) -> "CharacterBuilder":
        """Set the character's starting level (1-20)."""
        self._level = max(1, min(20, level))
        return self

    def set_background(self, background: str) -> "CharacterBuilder":
        """Set the character's background."""
        self._background = background
        return self

    def set_abilities_from_priorities(
        self,
        priorities: List[str],
    ) -> "CharacterBuilder":
        """
        Set ability scores based on priority list.

        Args:
            priorities: Ordered list of ability names, highest priority first.
                       e.g., ["strength", "constitution", "dexterity"]
        """
        # Map standard array to priorities
        scores = {
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        # Assign from standard array based on priority
        available = list(STANDARD_ARRAY)
        for ability in priorities:
            ability_lower = ability.lower()
            if ability_lower in scores and available:
                scores[ability_lower] = available.pop(0)

        # Assign remaining scores to unspecified abilities
        remaining_abilities = [
            a for a in scores.keys()
            if a.lower() not in [p.lower() for p in priorities]
        ]
        for ability in remaining_abilities:
            if available:
                scores[ability] = available.pop(0)

        # Apply origin bonuses
        origin_data = get_origin(self._origin_base_type or "human", self.genre)
        if origin_data and origin_data.ability_bonuses:
            for ability, bonus in origin_data.ability_bonuses.items():
                if ability in scores:
                    scores[ability] = min(20, scores[ability] + bonus)

        self._ability_scores = AbilityScores(**scores)
        return self

    def set_abilities_standard_array(self) -> "CharacterBuilder":
        """
        Set ability scores using standard array with class-optimized placement.
        """
        archetype_data = get_archetype(
            self._archetype_base_type or "fighter",
            self.genre
        )

        # Build priority list from archetype
        if archetype_data:
            primary = archetype_data.primary_ability
            priorities = [primary, "constitution"]

            # Add secondary abilities based on archetype
            if primary != "dexterity":
                priorities.append("dexterity")
            if primary != "wisdom":
                priorities.append("wisdom")
        else:
            priorities = ["strength", "constitution", "dexterity"]

        return self.set_abilities_from_priorities(priorities)

    def set_abilities_direct(
        self,
        ability_scores: AbilityScores,
    ) -> "CharacterBuilder":
        """Set ability scores directly."""
        self._ability_scores = ability_scores
        return self

    def set_skill_proficiencies(
        self,
        skills: List[str],
    ) -> "CharacterBuilder":
        """Set skill proficiencies."""
        self._skill_proficiencies = [s.lower() for s in skills]
        return self

    def build(self) -> CharacterSheet:
        """
        Build the final CharacterSheet.

        Raises:
            ValueError: If required fields are not set.
        """
        # Validate required fields
        if not self._name:
            raise ValueError("Character name is required")
        if not self._origin_id:
            raise ValueError("Origin is required")
        if not self._archetype_id:
            raise ValueError("Archetype is required")

        # Get origin and archetype data using base types for mechanics
        origin_data = get_origin(
            self._origin_base_type or self._origin_id,
            self.genre
        )
        archetype_data = get_archetype(
            self._archetype_base_type or self._archetype_id,
            self.genre
        )

        # Use defaults if data not found
        if not origin_data:
            origins = get_origins_for_genre(self.genre)
            origin_data = origins[0] if origins else None

        if not archetype_data:
            archetypes = get_archetypes_for_genre(self.genre)
            archetype_data = archetypes[0] if archetypes else None

        # Generate ability scores if not set
        if not self._ability_scores:
            self.set_abilities_standard_array()

        # Calculate derived stats
        con_mod = self._ability_scores.get_modifier(AbilityName.CON)
        dex_mod = self._ability_scores.get_modifier(AbilityName.DEX)

        hp = get_starting_hp(
            self._archetype_base_type or self._archetype_id,
            con_mod,
            self.genre
        )

        # Calculate AC (base 10 + DEX, or armor-based)
        base_ac = 10 + dex_mod

        # Proficiency bonus based on level
        proficiency_bonus = 2 + (self._level - 1) // 4

        # Get features for this level
        features = []
        if archetype_data:
            for lvl in range(1, self._level + 1):
                features.extend(archetype_data.features_by_level.get(lvl, []))

        # Default skills if none set
        if not self._skill_proficiencies and archetype_data:
            self._skill_proficiencies = archetype_data.skill_choices[
                :archetype_data.num_skill_choices
            ]

        # Build power/spell setup for casters
        power_slots = {}
        cantrips = []
        abilities_known = []

        if archetype_data and archetype_data.has_powers:
            if archetype_data.power_slots_by_level:
                power_slots = archetype_data.power_slots_by_level.get(
                    self._level, {1: 2}
                )
            else:
                power_slots = {1: 2}

            cantrips = []  # Will be populated by spell selection step
            abilities_known = []

        return CharacterSheet(
            character_id=str(uuid.uuid4()),
            name=self._name,
            player_id=self._player_id,
            genre=self.genre,
            origin=self._origin_id,
            archetype=self._archetype_id,
            level=self._level,
            ability_scores=self._ability_scores,
            max_hit_points=hp,
            current_hit_points=hp,
            armor_class=base_ac,
            proficiency_bonus=proficiency_bonus,
            speed=origin_data.speed if origin_data else 30,
            skill_proficiencies=self._skill_proficiencies,
            saving_throw_proficiencies=(
                archetype_data.saving_throw_proficiencies
                if archetype_data else []
            ),
            armor_proficiencies=(
                archetype_data.armor_proficiencies
                if archetype_data else []
            ),
            weapon_proficiencies=(
                archetype_data.weapon_proficiencies
                if archetype_data else []
            ),
            equipment=[],  # Equipment added separately
            power_slots_max=power_slots,
            cantrips_known=cantrips,
            abilities_known=abilities_known,
            features=features,
            background=self._background,
            rules_visibility="guided",
        )
