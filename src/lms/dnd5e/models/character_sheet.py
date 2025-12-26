"""D&D 5e Character Sheet - complete mechanical state."""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, computed_field

from .ability_scores import AbilityScores, AbilityName
from .races import RaceName, RACES
from .classes import ClassName, CLASSES, get_hp_at_level


class CharacterSheet(BaseModel):
    """
    Complete mechanical character state for D&D 5e.

    This is the source of truth for all mechanical properties of a character.
    """
    # Identity
    character_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    player_id: str = ""  # Links to session/player

    # Core Mechanics
    race: RaceName
    character_class: ClassName
    level: int = Field(ge=1, le=3, default=1)  # Phase 1: levels 1-3
    experience_points: int = 0

    # Ability Scores (base + racial bonuses already applied)
    ability_scores: AbilityScores

    # Combat Stats
    max_hit_points: int
    current_hit_points: int
    temporary_hit_points: int = 0
    armor_class: int = 10
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
    gold: int = 0

    # Spellcasting (if applicable)
    spells_known: List[str] = Field(default_factory=list)
    cantrips_known: List[str] = Field(default_factory=list)
    spell_slots_max: Dict[int, int] = Field(default_factory=dict)  # Level -> max slots
    spell_slots_used: Dict[int, int] = Field(default_factory=dict)  # Level -> used slots

    # Conditions & Status
    conditions: List[str] = Field(default_factory=list)
    death_saves_success: int = 0
    death_saves_failure: int = 0

    # Class Features
    features: List[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Visibility preference for this character's player
    rules_visibility: str = "guided"  # storyteller, guided, classic, tactician

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
            # Use higher of STR or DEX for finesse weapons
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

    def use_spell_slot(self, level: int) -> Optional["CharacterSheet"]:
        """
        Use a spell slot of the given level.

        Returns new CharacterSheet if slot available, None otherwise.
        """
        max_slots = self.spell_slots_max.get(level, 0)
        used_slots = self.spell_slots_used.get(level, 0)

        if used_slots >= max_slots:
            return None

        new_used = self.spell_slots_used.copy()
        new_used[level] = used_slots + 1

        return self.model_copy(update={
            "spell_slots_used": new_used,
            "updated_at": datetime.now(timezone.utc),
        })

    def long_rest(self) -> "CharacterSheet":
        """
        Perform a long rest: restore HP and spell slots.

        Returns new CharacterSheet with restored resources.
        """
        return self.model_copy(update={
            "current_hit_points": self.max_hit_points,
            "spell_slots_used": {},
            "death_saves_success": 0,
            "death_saves_failure": 0,
            "conditions": [],
            "updated_at": datetime.now(timezone.utc),
        })

    def to_summary_dict(self) -> Dict:
        """Return a summary for display (respects visibility in presentation layer)."""
        return {
            "name": self.name,
            "race": RACES[self.race].display_name,
            "class": CLASSES[self.character_class].display_name,
            "level": self.level,
            "hp": f"{self.current_hit_points}/{self.max_hit_points}",
            "ac": self.armor_class,
            "abilities": self.ability_scores.to_display_dict(),
        }

    def to_full_dict(self) -> Dict:
        """Return complete character data for save/load."""
        return self.model_dump()


# XP thresholds for levels 1-3 (Phase 1)
XP_THRESHOLDS = {
    1: 0,
    2: 300,
    3: 900,
}


def calculate_level(xp: int) -> int:
    """Calculate level from XP (capped at 3 for Phase 1)."""
    if xp >= 900:
        return 3
    elif xp >= 300:
        return 2
    return 1
