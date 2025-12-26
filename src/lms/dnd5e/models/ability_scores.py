"""D&D 5e Ability Scores model."""

from enum import Enum
from typing import Dict
from pydantic import BaseModel, Field


class AbilityName(str, Enum):
    """The six core ability scores in D&D 5e."""
    STR = "strength"
    DEX = "dexterity"
    CON = "constitution"
    INT = "intelligence"
    WIS = "wisdom"
    CHA = "charisma"


class AbilityScores(BaseModel):
    """
    D&D 5e ability scores with computed modifiers.

    Scores range from 1-30 (typically 3-18 for player characters).
    Modifier = (score - 10) // 2
    """
    strength: int = Field(ge=1, le=30, default=10)
    dexterity: int = Field(ge=1, le=30, default=10)
    constitution: int = Field(ge=1, le=30, default=10)
    intelligence: int = Field(ge=1, le=30, default=10)
    wisdom: int = Field(ge=1, le=30, default=10)
    charisma: int = Field(ge=1, le=30, default=10)

    def get_score(self, ability: AbilityName) -> int:
        """Get the score for a specific ability."""
        return getattr(self, ability.value)

    def get_modifier(self, ability: AbilityName) -> int:
        """
        Calculate modifier for an ability.

        Modifier = (score - 10) // 2
        Examples: 10 → +0, 14 → +2, 8 → -1, 18 → +4
        """
        score = self.get_score(ability)
        return (score - 10) // 2

    def get_all_modifiers(self) -> Dict[AbilityName, int]:
        """Get modifiers for all abilities."""
        return {ability: self.get_modifier(ability) for ability in AbilityName}

    def apply_bonuses(self, bonuses: Dict[str, int]) -> "AbilityScores":
        """
        Return a new AbilityScores with bonuses applied.

        Args:
            bonuses: Dict mapping ability name to bonus (e.g., {"dexterity": 2})

        Returns:
            New AbilityScores with bonuses applied (capped at 30)
        """
        new_scores = self.model_copy()
        for ability_name, bonus in bonuses.items():
            current = getattr(new_scores, ability_name)
            setattr(new_scores, ability_name, min(30, current + bonus))
        return new_scores

    def to_display_dict(self) -> Dict[str, Dict[str, int]]:
        """
        Return scores and modifiers in a display-friendly format.

        Returns:
            Dict with ability abbreviations as keys, containing score and modifier.
        """
        return {
            "STR": {"score": self.strength, "modifier": self.get_modifier(AbilityName.STR)},
            "DEX": {"score": self.dexterity, "modifier": self.get_modifier(AbilityName.DEX)},
            "CON": {"score": self.constitution, "modifier": self.get_modifier(AbilityName.CON)},
            "INT": {"score": self.intelligence, "modifier": self.get_modifier(AbilityName.INT)},
            "WIS": {"score": self.wisdom, "modifier": self.get_modifier(AbilityName.WIS)},
            "CHA": {"score": self.charisma, "modifier": self.get_modifier(AbilityName.CHA)},
        }


# Standard array for character creation
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

# Point buy costs (for Expert mode)
POINT_BUY_COSTS = {
    8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9
}
POINT_BUY_TOTAL = 27
