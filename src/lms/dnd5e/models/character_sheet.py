"""
Character Sheet - complete mechanical state for the d20 rules engine.

Uses generic terminology (origin, archetype) with backward-compatible
aliases for D&D 5e (race, character_class).
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, computed_field, model_validator

from .ability_scores import AbilityScores, AbilityName


class CharacterSheet(BaseModel):
    """
    Complete mechanical character state.

    This is the source of truth for all mechanical properties of a character.
    Works across all genres (fantasy, sci-fi, modern, horror).
    """
    # Identity
    character_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    player_id: str = ""  # Links to session/player

    # Genre
    genre: str = "fantasy"  # fantasy, scifi, modern, horror

    # Core Mechanics (generic terms)
    origin: str  # Was: race. Generic term for species/background
    archetype: str  # Was: character_class. Generic term for class/role
    level: int = Field(ge=1, le=20, default=1)
    experience_points: int = 0

    # Ability Scores (base + origin bonuses already applied)
    ability_scores: AbilityScores

    # Combat Stats
    max_hit_points: int
    current_hit_points: int
    temporary_hit_points: int = 0
    armor_class: int = 10  # "Defense" in some genres
    speed: int = 30

    # Proficiencies
    proficiency_bonus: int = 2  # +2 at levels 1-4
    skill_proficiencies: List[str] = Field(default_factory=list)
    saving_throw_proficiencies: List[str] = Field(default_factory=list)
    armor_proficiencies: List[str] = Field(default_factory=list)
    weapon_proficiencies: List[str] = Field(default_factory=list)
    tool_proficiencies: List[str] = Field(default_factory=list)

    # Equipment
    equipment: List[str] = Field(default_factory=list)
    gold: int = 0  # Or "credits" in sci-fi

    # Abilities/Powers (spells in fantasy, tech in sci-fi)
    abilities_known: List[str] = Field(default_factory=list)
    cantrips_known: List[str] = Field(default_factory=list)
    power_slots_max: Dict[int, int] = Field(default_factory=dict)  # Level -> max slots
    power_slots_used: Dict[int, int] = Field(default_factory=dict)  # Level -> used slots

    # Conditions & Status
    conditions: List[str] = Field(default_factory=list)
    death_saves_success: int = 0
    death_saves_failure: int = 0
    sanity: Optional[int] = None  # For horror genre

    # Features (from archetype and origin)
    features: List[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Visibility preference for this character's player
    rules_visibility: str = "guided"  # storyteller, guided, classic, tactician

    # =========================================================================
    # BACKWARD COMPATIBILITY - D&D 5e aliases
    # =========================================================================

    @computed_field
    @property
    def race(self) -> str:
        """Backward compatible: race is an alias for origin."""
        return self.origin

    @computed_field
    @property
    def character_class(self) -> str:
        """Backward compatible: character_class is an alias for archetype."""
        return self.archetype

    @computed_field
    @property
    def spells_known(self) -> List[str]:
        """Backward compatible: spells_known is an alias for abilities_known."""
        return self.abilities_known

    @computed_field
    @property
    def spell_slots_max(self) -> Dict[int, int]:
        """Backward compatible: spell_slots_max is an alias for power_slots_max."""
        return self.power_slots_max

    @computed_field
    @property
    def spell_slots_used(self) -> Dict[int, int]:
        """Backward compatible: spell_slots_used is an alias for power_slots_used."""
        return self.power_slots_used

    @model_validator(mode='before')
    @classmethod
    def handle_legacy_fields(cls, data: Any) -> Any:
        """Convert legacy field names to new names."""
        if isinstance(data, dict):
            # Handle race -> origin
            if 'race' in data and 'origin' not in data:
                race_val = data.pop('race')
                data['origin'] = race_val.value if hasattr(race_val, 'value') else str(race_val)

            # Handle character_class -> archetype
            if 'character_class' in data and 'archetype' not in data:
                class_val = data.pop('character_class')
                data['archetype'] = class_val.value if hasattr(class_val, 'value') else str(class_val)

            # Handle spells_known -> abilities_known
            if 'spells_known' in data and 'abilities_known' not in data:
                data['abilities_known'] = data.pop('spells_known')

            # Handle spell_slots_max -> power_slots_max
            if 'spell_slots_max' in data and 'power_slots_max' not in data:
                data['power_slots_max'] = data.pop('spell_slots_max')

            # Handle spell_slots_used -> power_slots_used
            if 'spell_slots_used' in data and 'power_slots_used' not in data:
                data['power_slots_used'] = data.pop('spell_slots_used')

        return data

    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================

    @computed_field
    @property
    def is_alive(self) -> bool:
        """Check if character is alive (not dead from failed death saves)."""
        return self.death_saves_failure < 3

    @computed_field
    @property
    def is_conscious(self) -> bool:
        """Check if character is conscious (has HP > 0)."""
        return self.current_hit_points > 0

    @computed_field
    @property
    def initiative_modifier(self) -> int:
        """Initiative is based on DEX modifier."""
        return self.ability_scores.get_modifier(AbilityName.DEX)

    @computed_field
    @property
    def spell_slots(self) -> Dict[int, int]:
        """Backward compatible: remaining spell slots."""
        return {
            level: self.power_slots_max.get(level, 0) - self.power_slots_used.get(level, 0)
            for level in self.power_slots_max
        }

    # =========================================================================
    # METHODS
    # =========================================================================

    def get_saving_throw_modifier(self, ability: AbilityName) -> int:
        """Calculate saving throw modifier with proficiency if applicable."""
        base_mod = self.ability_scores.get_modifier(ability)
        if ability.value in self.saving_throw_proficiencies:
            return base_mod + self.proficiency_bonus
        return base_mod

    def get_skill_modifier(self, skill: str) -> int:
        """Calculate skill modifier with proficiency if applicable."""
        from ..engine.checks import SKILL_TO_ABILITY

        ability = SKILL_TO_ABILITY.get(skill.lower(), AbilityName.INT)
        base_mod = self.ability_scores.get_modifier(ability)

        if skill.lower() in [s.lower() for s in self.skill_proficiencies]:
            return base_mod + self.proficiency_bonus
        return base_mod

    def get_attack_modifier(self, weapon_type: str = "melee") -> int:
        """
        Calculate attack modifier.

        Melee: STR + proficiency (or DEX for finesse)
        Ranged: DEX + proficiency
        """
        if weapon_type == "ranged":
            ability = AbilityName.DEX
        else:
            ability = AbilityName.STR

        return self.ability_scores.get_modifier(ability) + self.proficiency_bonus

    def take_damage(self, amount: int) -> "CharacterSheet":
        """
        Apply damage to character.

        Returns new CharacterSheet with updated HP.
        """
        # First absorb with temp HP
        remaining = amount
        new_temp = self.temporary_hit_points
        if new_temp > 0:
            absorbed = min(new_temp, remaining)
            new_temp -= absorbed
            remaining -= absorbed

        # Then apply to regular HP
        new_hp = max(0, self.current_hit_points - remaining)

        return self.model_copy(update={
            "current_hit_points": new_hp,
            "temporary_hit_points": new_temp,
            "updated_at": datetime.now(timezone.utc),
        })

    def heal(self, amount: int) -> "CharacterSheet":
        """
        Heal character.

        Returns new CharacterSheet with updated HP (capped at max).
        """
        new_hp = min(self.max_hit_points, self.current_hit_points + amount)
        return self.model_copy(update={
            "current_hit_points": new_hp,
            "updated_at": datetime.now(timezone.utc),
        })

    def use_power_slot(self, level: int) -> Optional["CharacterSheet"]:
        """
        Use a power slot (spell slot) of the given level.

        Returns new CharacterSheet if slot available, None otherwise.
        """
        max_slots = self.power_slots_max.get(level, 0)
        used_slots = self.power_slots_used.get(level, 0)

        if used_slots >= max_slots:
            return None

        new_used = self.power_slots_used.copy()
        new_used[level] = used_slots + 1

        return self.model_copy(update={
            "power_slots_used": new_used,
            "updated_at": datetime.now(timezone.utc),
        })

    def use_spell_slot(self, level: int) -> Optional["CharacterSheet"]:
        """Backward compatible: alias for use_power_slot."""
        return self.use_power_slot(level)

    def long_rest(self) -> "CharacterSheet":
        """
        Perform a long rest: restore HP and power slots.

        Returns new CharacterSheet with restored resources.
        """
        return self.model_copy(update={
            "current_hit_points": self.max_hit_points,
            "power_slots_used": {},
            "death_saves_success": 0,
            "death_saves_failure": 0,
            "conditions": [],
            "updated_at": datetime.now(timezone.utc),
        })

    def to_summary_dict(self) -> Dict:
        """Return a summary for display (respects visibility in presentation layer)."""
        from .origins import get_origin
        from .archetypes import get_archetype

        origin_data = get_origin(self.origin, self.genre)
        archetype_data = get_archetype(self.archetype, self.genre)

        return {
            "name": self.name,
            "origin": origin_data.display_name if origin_data else self.origin,
            "archetype": archetype_data.display_name if archetype_data else self.archetype,
            "level": self.level,
            "hp": f"{self.current_hit_points}/{self.max_hit_points}",
            "ac": self.armor_class,
            "abilities": self.ability_scores.to_display_dict(),
            # Backward compatible aliases
            "race": origin_data.display_name if origin_data else self.origin,
            "class": archetype_data.display_name if archetype_data else self.archetype,
        }

    def to_full_dict(self) -> Dict:
        """Return complete character data for save/load."""
        return self.model_dump()


# XP thresholds (generic across genres)
XP_THRESHOLDS = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
}


def calculate_level(xp: int) -> int:
    """Calculate level from XP."""
    for level in sorted(XP_THRESHOLDS.keys(), reverse=True):
        if xp >= XP_THRESHOLDS[level]:
            return level
    return 1
