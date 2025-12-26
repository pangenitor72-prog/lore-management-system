"""D&D 5e Combat Resolution Engine."""

from typing import Optional, Tuple
from pydantic import BaseModel
from enum import Enum

from ..models.ability_scores import AbilityName
from ..models.character_sheet import CharacterSheet
from .dice import DiceRoller, DiceResult


class DamageType(str, Enum):
    """D&D 5e damage types."""
    SLASHING = "slashing"
    PIERCING = "piercing"
    BLUDGEONING = "bludgeoning"
    FIRE = "fire"
    COLD = "cold"
    LIGHTNING = "lightning"
    THUNDER = "thunder"
    POISON = "poison"
    ACID = "acid"
    PSYCHIC = "psychic"
    RADIANT = "radiant"
    NECROTIC = "necrotic"
    FORCE = "force"


class AttackResult(BaseModel):
    """Result of an attack roll."""
    attack_roll: int  # The d20 result
    attack_rolls: list[int]  # All dice (for adv/disadv)
    attack_modifier: int
    attack_total: int
    target_ac: int
    is_hit: bool
    is_critical: bool  # Natural 20
    is_critical_miss: bool  # Natural 1

    # Context
    attacker_id: str = ""
    target_id: str = ""
    weapon_name: str = ""

    # Narrative
    narrative_outcome: str = ""  # "hit", "miss", "critical_hit", "critical_miss"


class DamageResult(BaseModel):
    """Result of a damage roll."""
    damage_rolls: list[int]
    damage_modifier: int
    damage_total: int
    damage_type: DamageType
    is_critical: bool = False  # Double dice for crits

    # Narrative
    narrative: str = ""


class CombatResolver:
    """
    Resolves combat actions: attacks, damage, and conditions.
    """

    @staticmethod
    def resolve_attack(
        attacker: CharacterSheet,
        target_ac: int,
        weapon_type: str = "melee",
        is_finesse: bool = False,
        weapon_bonus: int = 0,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> AttackResult:
        """
        Resolve an attack roll.

        Args:
            attacker: The attacking character
            target_ac: Target's armor class
            weapon_type: "melee" or "ranged"
            is_finesse: Whether to use DEX for melee
            weapon_bonus: Magic weapon bonus
            advantage: Whether attack has advantage
            disadvantage: Whether attack has disadvantage

        Returns:
            AttackResult with full breakdown
        """
        # Determine ability modifier
        if weapon_type == "ranged":
            ability = AbilityName.DEX
        elif is_finesse:
            # Use higher of STR or DEX
            str_mod = attacker.ability_scores.get_modifier(AbilityName.STR)
            dex_mod = attacker.ability_scores.get_modifier(AbilityName.DEX)
            ability_mod = max(str_mod, dex_mod)
        else:
            ability_mod = attacker.ability_scores.get_modifier(AbilityName.STR)

        if weapon_type == "ranged" or is_finesse:
            ability_mod = attacker.ability_scores.get_modifier(AbilityName.DEX)
        else:
            ability_mod = attacker.ability_scores.get_modifier(AbilityName.STR)

        # Calculate total attack modifier
        attack_modifier = ability_mod + attacker.proficiency_bonus + weapon_bonus

        # Roll the attack
        roll, rolls, is_nat_20, is_nat_1 = DiceRoller.roll_d20(
            advantage, disadvantage
        )

        attack_total = roll + attack_modifier

        # Determine hit/miss
        # Natural 20 always hits, natural 1 always misses
        if is_nat_20:
            is_hit = True
        elif is_nat_1:
            is_hit = False
        else:
            is_hit = attack_total >= target_ac

        # Determine narrative outcome
        if is_nat_20:
            narrative = "critical_hit"
        elif is_nat_1:
            narrative = "critical_miss"
        elif is_hit:
            narrative = "hit"
        else:
            narrative = "miss"

        return AttackResult(
            attack_roll=roll,
            attack_rolls=rolls,
            attack_modifier=attack_modifier,
            attack_total=attack_total,
            target_ac=target_ac,
            is_hit=is_hit,
            is_critical=is_nat_20,
            is_critical_miss=is_nat_1,
            attacker_id=attacker.character_id,
            narrative_outcome=narrative,
        )

    @staticmethod
    def roll_damage(
        damage_dice: str,
        damage_type: DamageType,
        ability_modifier: int = 0,
        is_critical: bool = False,
        bonus_damage: int = 0,
    ) -> DamageResult:
        """
        Roll damage for an attack.

        Args:
            damage_dice: Dice notation (e.g., "1d8", "2d6")
            damage_type: Type of damage
            ability_modifier: STR/DEX modifier to add
            is_critical: Whether to double dice (not modifier)
            bonus_damage: Additional flat bonus

        Returns:
            DamageResult with full breakdown
        """
        # Parse dice notation
        count, sides, dice_mod = DiceRoller.parse_notation(damage_dice)

        # Critical hits double the dice
        if is_critical:
            count *= 2

        # Roll the damage
        rolls = DiceRoller.roll(sides, count)
        total_modifier = ability_modifier + dice_mod + bonus_damage
        damage_total = sum(rolls) + total_modifier

        # Minimum 1 damage on a hit
        damage_total = max(1, damage_total)

        return DamageResult(
            damage_rolls=rolls,
            damage_modifier=total_modifier,
            damage_total=damage_total,
            damage_type=damage_type,
            is_critical=is_critical,
        )

    @staticmethod
    def apply_damage(
        target: CharacterSheet,
        damage: int,
        damage_type: DamageType,
    ) -> Tuple[CharacterSheet, int]:
        """
        Apply damage to a character.

        Args:
            target: The character taking damage
            damage: Amount of damage
            damage_type: Type of damage (for resistances/immunities)

        Returns:
            Tuple of (updated_character, actual_damage_taken)
        """
        # Note: Phase 1 doesn't implement resistances/immunities
        # This is an extension point for Phase 2

        actual_damage = damage
        new_character = target.take_damage(actual_damage)

        return new_character, actual_damage

    @staticmethod
    def apply_healing(
        target: CharacterSheet,
        healing: int,
    ) -> Tuple[CharacterSheet, int]:
        """
        Apply healing to a character.

        Args:
            target: The character being healed
            healing: Amount of healing

        Returns:
            Tuple of (updated_character, actual_healing)
        """
        old_hp = target.current_hit_points
        new_character = target.heal(healing)
        actual_healing = new_character.current_hit_points - old_hp

        return new_character, actual_healing

    @staticmethod
    def roll_initiative(character: CharacterSheet) -> Tuple[int, int]:
        """
        Roll initiative for a character.

        Returns:
            Tuple of (total, dex_modifier)
        """
        dex_mod = character.initiative_modifier
        roll = DiceRoller.roll(20, 1)[0]
        return roll + dex_mod, dex_mod


# Common weapon damage for quick reference
WEAPON_DAMAGE = {
    "longsword": ("1d8", DamageType.SLASHING),
    "shortsword": ("1d6", DamageType.PIERCING),
    "rapier": ("1d8", DamageType.PIERCING),
    "dagger": ("1d4", DamageType.PIERCING),
    "quarterstaff": ("1d6", DamageType.BLUDGEONING),
    "mace": ("1d6", DamageType.BLUDGEONING),
    "shortbow": ("1d6", DamageType.PIERCING),
    "light_crossbow": ("1d8", DamageType.PIERCING),
    "unarmed": ("1", DamageType.BLUDGEONING),  # 1 + STR mod
}
