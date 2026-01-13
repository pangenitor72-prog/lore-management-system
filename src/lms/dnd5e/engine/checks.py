"""D&D 5e Check Resolution Engine - ability checks, skill checks, saving throws."""

from typing import Optional
from pydantic import BaseModel

from ..models.ability_scores import AbilityName
from ..models.character_sheet import CharacterSheet
from .dice import DiceRoller, DiceResult


class CheckResult(BaseModel):
    """Result of an ability check, skill check, or saving throw."""
    roll: int  # The d20 roll result
    rolls: list[int]  # All dice rolled (for adv/disadv)
    modifier: int  # Total modifier applied
    total: int  # Final result (roll + modifier)
    dc: int  # Difficulty class
    success: bool  # Whether the check succeeded
    margin: int  # How much over/under the DC

    # For natural 20/1 handling
    is_natural_20: bool = False
    is_natural_1: bool = False

    # Context for narrative
    check_type: str = ""  # "ability", "skill", "save"
    ability_used: Optional[str] = None
    skill_used: Optional[str] = None

    # Narrative outcome for presentation layer
    narrative_outcome: str = ""  # "success", "failure", "critical_success", etc.


# Skill to Ability mapping (5e standard + genre extensions)
SKILL_TO_ABILITY = {
    # ===================
    # STANDARD 5e SKILLS
    # ===================
    # Strength
    "athletics": AbilityName.STR,
    # Dexterity
    "acrobatics": AbilityName.DEX,
    "sleight_of_hand": AbilityName.DEX,
    "stealth": AbilityName.DEX,
    # Intelligence
    "arcana": AbilityName.INT,
    "history": AbilityName.INT,
    "investigation": AbilityName.INT,
    "nature": AbilityName.INT,
    "religion": AbilityName.INT,
    # Wisdom
    "animal_handling": AbilityName.WIS,
    "insight": AbilityName.WIS,
    "medicine": AbilityName.WIS,
    "perception": AbilityName.WIS,
    "survival": AbilityName.WIS,
    # Charisma
    "deception": AbilityName.CHA,
    "intimidation": AbilityName.CHA,
    "performance": AbilityName.CHA,
    "persuasion": AbilityName.CHA,

    # ===================
    # GENRE-SPECIFIC SKILLS
    # ===================
    # Tech/Sci-Fi/Cyberpunk (Intelligence-based)
    "hacking": AbilityName.INT,
    "computers": AbilityName.INT,
    "electronics": AbilityName.INT,
    "science": AbilityName.INT,
    "demolitions": AbilityName.INT,
    "engineering": AbilityName.INT,

    # Mechanical/Vehicle (Dexterity-based)
    "mechanics": AbilityName.DEX,
    "piloting": AbilityName.DEX,
    "vehicles": AbilityName.DEX,
    "driving": AbilityName.DEX,

    # Street/Urban (Wisdom or Charisma-based)
    "streetwise": AbilityName.WIS,
    "contacts": AbilityName.CHA,

    # Medical (Wisdom-based, extends medicine)
    "first_aid": AbilityName.WIS,
    "surgery": AbilityName.WIS,

    # Combat/Physical (various)
    "firearms": AbilityName.DEX,
    "martial_arts": AbilityName.DEX,
    "brawling": AbilityName.STR,

    # Artisan/Craft (Dexterity or Intelligence)
    "calligraphy": AbilityName.DEX,
    "forgery": AbilityName.DEX,
    "tinker": AbilityName.INT,

    # Social/Subterfuge (Charisma-based)
    "disguise": AbilityName.CHA,
    "etiquette": AbilityName.CHA,
    "gambling": AbilityName.CHA,
    "interrogation": AbilityName.CHA,

    # Wilderness/Survival variants
    "tracking": AbilityName.WIS,
    "navigation": AbilityName.WIS,
    "riding": AbilityName.DEX,
}

ALL_SKILLS = list(SKILL_TO_ABILITY.keys())


def _determine_narrative_outcome(
    success: bool,
    margin: int,
    is_nat_20: bool,
    is_nat_1: bool
) -> str:
    """
    Determine narrative outcome based on roll result.

    Returns one of:
    - "critical_success": Natural 20 or beat DC by 10+
    - "success": Normal success
    - "close_success": Beat DC by 1-2
    - "close_failure": Missed DC by 1-2
    - "failure": Normal failure
    - "critical_failure": Natural 1 or missed DC by 10+
    """
    if is_nat_20:
        return "critical_success"
    if is_nat_1:
        return "critical_failure"

    if success:
        if margin >= 10:
            return "critical_success"
        elif margin <= 2:
            return "close_success"
        else:
            return "success"
    else:
        if margin <= -10:
            return "critical_failure"
        elif margin >= -2:
            return "close_failure"
        else:
            return "failure"


class CheckEngine:
    """
    Resolves ability checks, skill checks, and saving throws.

    All methods return a CheckResult with full information for
    both mechanical resolution and narrative presentation.
    """

    @staticmethod
    def ability_check(
        character: CharacterSheet,
        ability: AbilityName,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False,
        bonus: int = 0
    ) -> CheckResult:
        """
        Perform an ability check.

        Args:
            character: The character making the check
            ability: The ability to use (STR, DEX, etc.)
            dc: Difficulty class to beat
            advantage: Whether the roll has advantage
            disadvantage: Whether the roll has disadvantage
            bonus: Any additional bonus (from spells, items, etc.)

        Returns:
            CheckResult with full breakdown
        """
        # Get ability modifier
        modifier = character.ability_scores.get_modifier(ability) + bonus

        # Roll the d20
        roll, rolls, is_nat_20, is_nat_1 = DiceRoller.roll_d20(
            advantage, disadvantage
        )

        total = roll + modifier
        success = total >= dc
        margin = total - dc

        return CheckResult(
            roll=roll,
            rolls=rolls,
            modifier=modifier,
            total=total,
            dc=dc,
            success=success,
            margin=margin,
            is_natural_20=is_nat_20,
            is_natural_1=is_nat_1,
            check_type="ability",
            ability_used=ability.value,
            narrative_outcome=_determine_narrative_outcome(
                success, margin, is_nat_20, is_nat_1
            ),
        )

    @staticmethod
    def skill_check(
        character: CharacterSheet,
        skill: str,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False,
        bonus: int = 0
    ) -> CheckResult:
        """
        Perform a skill check.

        Args:
            character: The character making the check
            skill: The skill to use (e.g., "stealth", "perception")
            dc: Difficulty class to beat
            advantage: Whether the roll has advantage
            disadvantage: Whether the roll has disadvantage
            bonus: Any additional bonus (from spells, items, etc.)

        Returns:
            CheckResult with full breakdown
        """
        skill_lower = skill.lower().replace(" ", "_")

        # Get the ability for this skill
        ability = SKILL_TO_ABILITY.get(skill_lower, AbilityName.INT)

        # Calculate modifier
        base_mod = character.ability_scores.get_modifier(ability)

        # Add proficiency if applicable
        is_proficient = skill_lower in [s.lower() for s in character.skill_proficiencies]
        proficiency = character.proficiency_bonus if is_proficient else 0

        modifier = base_mod + proficiency + bonus

        # Roll the d20
        roll, rolls, is_nat_20, is_nat_1 = DiceRoller.roll_d20(
            advantage, disadvantage
        )

        total = roll + modifier
        success = total >= dc
        margin = total - dc

        return CheckResult(
            roll=roll,
            rolls=rolls,
            modifier=modifier,
            total=total,
            dc=dc,
            success=success,
            margin=margin,
            is_natural_20=is_nat_20,
            is_natural_1=is_nat_1,
            check_type="skill",
            ability_used=ability.value,
            skill_used=skill_lower,
            narrative_outcome=_determine_narrative_outcome(
                success, margin, is_nat_20, is_nat_1
            ),
        )

    @staticmethod
    def saving_throw(
        character: CharacterSheet,
        ability: AbilityName,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False,
        bonus: int = 0
    ) -> CheckResult:
        """
        Perform a saving throw.

        Args:
            character: The character making the save
            ability: The ability to save with (STR, DEX, etc.)
            dc: Difficulty class to beat
            advantage: Whether the roll has advantage
            disadvantage: Whether the roll has disadvantage
            bonus: Any additional bonus (from spells, items, etc.)

        Returns:
            CheckResult with full breakdown
        """
        # Get saving throw modifier (includes proficiency if applicable)
        modifier = character.get_saving_throw_modifier(ability) + bonus

        # Roll the d20
        roll, rolls, is_nat_20, is_nat_1 = DiceRoller.roll_d20(
            advantage, disadvantage
        )

        total = roll + modifier
        success = total >= dc
        margin = total - dc

        return CheckResult(
            roll=roll,
            rolls=rolls,
            modifier=modifier,
            total=total,
            dc=dc,
            success=success,
            margin=margin,
            is_natural_20=is_nat_20,
            is_natural_1=is_nat_1,
            check_type="save",
            ability_used=ability.value,
            narrative_outcome=_determine_narrative_outcome(
                success, margin, is_nat_20, is_nat_1
            ),
        )

    @staticmethod
    def contested_check(
        actor: CharacterSheet,
        actor_skill: str,
        target: CharacterSheet,
        target_skill: str,
        actor_advantage: bool = False,
        actor_disadvantage: bool = False,
        target_advantage: bool = False,
        target_disadvantage: bool = False,
    ) -> tuple[CheckResult, CheckResult, bool]:
        """
        Perform a contested check between two characters.

        Args:
            actor: The initiating character
            actor_skill: The skill the actor uses
            target: The opposing character
            target_skill: The skill the target uses
            *_advantage/*_disadvantage: Advantage/disadvantage for each

        Returns:
            Tuple of (actor_result, target_result, actor_wins)
        """
        # Roll for actor (use high DC, we'll compare directly)
        actor_result = CheckEngine.skill_check(
            actor, actor_skill, 0,
            actor_advantage, actor_disadvantage
        )

        # Roll for target
        target_result = CheckEngine.skill_check(
            target, target_skill, 0,
            target_advantage, target_disadvantage
        )

        # Actor wins ties
        actor_wins = actor_result.total >= target_result.total

        return actor_result, target_result, actor_wins


# Common DC reference
DIFFICULTY_CLASS = {
    "very_easy": 5,
    "easy": 10,
    "medium": 15,
    "hard": 20,
    "very_hard": 25,
    "nearly_impossible": 30,
}
