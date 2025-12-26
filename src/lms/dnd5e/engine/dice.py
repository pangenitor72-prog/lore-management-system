"""D&D 5e Dice Rolling Engine."""

import random
import re
from typing import List, Tuple, Optional
from pydantic import BaseModel


class DiceResult(BaseModel):
    """Result of a dice roll with full breakdown."""
    rolls: List[int]  # Individual die results
    modifier: int = 0
    total: int
    notation: str  # Original notation (e.g., "2d6+3")
    is_natural_20: bool = False  # For d20 rolls
    is_natural_1: bool = False  # For d20 rolls


class DiceRoller:
    """
    D&D dice rolling with support for:
    - Standard dice (d4, d6, d8, d10, d12, d20, d100)
    - Advantage/disadvantage on d20
    - Dice notation parsing (2d6+3)
    """

    @staticmethod
    def roll(sides: int, count: int = 1) -> List[int]:
        """
        Roll count dice with given number of sides.

        Args:
            sides: Number of sides on the die (e.g., 20 for d20)
            count: Number of dice to roll

        Returns:
            List of individual roll results
        """
        return [random.randint(1, sides) for _ in range(count)]

    @staticmethod
    def roll_d20(
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Tuple[int, List[int], bool, bool]:
        """
        Roll a d20 with optional advantage/disadvantage.

        Advantage: Roll 2d20, take higher
        Disadvantage: Roll 2d20, take lower
        Both cancel out: Roll 1d20

        Args:
            advantage: Whether the roll has advantage
            disadvantage: Whether the roll has disadvantage

        Returns:
            Tuple of (final_result, all_rolls, is_nat_20, is_nat_1)
        """
        # Advantage and disadvantage cancel out
        if advantage and disadvantage:
            rolls = [random.randint(1, 20)]
        elif advantage:
            rolls = [random.randint(1, 20), random.randint(1, 20)]
        elif disadvantage:
            rolls = [random.randint(1, 20), random.randint(1, 20)]
        else:
            rolls = [random.randint(1, 20)]

        # Determine final result
        if advantage and not disadvantage:
            result = max(rolls)
        elif disadvantage and not advantage:
            result = min(rolls)
        else:
            result = rolls[0]

        is_nat_20 = result == 20
        is_nat_1 = result == 1

        return result, rolls, is_nat_20, is_nat_1

    @staticmethod
    def parse_notation(notation: str) -> Tuple[int, int, int]:
        """
        Parse dice notation like "2d6+3" or "1d20-2".

        Args:
            notation: Dice notation string

        Returns:
            Tuple of (count, sides, modifier)

        Raises:
            ValueError: If notation is invalid
        """
        # Pattern: NdS or NdS+M or NdS-M
        pattern = r'^(\d+)d(\d+)([+-]\d+)?$'
        match = re.match(pattern, notation.lower().replace(' ', ''))

        if not match:
            raise ValueError(f"Invalid dice notation: {notation}")

        count = int(match.group(1))
        sides = int(match.group(2))
        modifier_str = match.group(3)
        modifier = int(modifier_str) if modifier_str else 0

        return count, sides, modifier

    @staticmethod
    def roll_notation(notation: str) -> DiceResult:
        """
        Parse and roll dice notation.

        Args:
            notation: Dice notation string (e.g., "2d6+3")

        Returns:
            DiceResult with full breakdown
        """
        count, sides, modifier = DiceRoller.parse_notation(notation)
        rolls = DiceRoller.roll(sides, count)
        total = sum(rolls) + modifier

        # Check for natural 20/1 only on single d20
        is_nat_20 = (count == 1 and sides == 20 and rolls[0] == 20)
        is_nat_1 = (count == 1 and sides == 20 and rolls[0] == 1)

        return DiceResult(
            rolls=rolls,
            modifier=modifier,
            total=total,
            notation=notation,
            is_natural_20=is_nat_20,
            is_natural_1=is_nat_1,
        )

    @staticmethod
    def roll_with_modifier(
        sides: int,
        modifier: int = 0,
        count: int = 1,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> DiceResult:
        """
        Roll dice with a modifier, optionally with advantage/disadvantage for d20.

        Args:
            sides: Number of sides on the die
            modifier: Modifier to add to result
            count: Number of dice to roll
            advantage: Whether roll has advantage (d20 only)
            disadvantage: Whether roll has disadvantage (d20 only)

        Returns:
            DiceResult with full breakdown
        """
        if sides == 20 and count == 1:
            result, rolls, is_nat_20, is_nat_1 = DiceRoller.roll_d20(
                advantage, disadvantage
            )
            return DiceResult(
                rolls=rolls,
                modifier=modifier,
                total=result + modifier,
                notation=f"1d20{'+' if modifier >= 0 else ''}{modifier}" if modifier else "1d20",
                is_natural_20=is_nat_20,
                is_natural_1=is_nat_1,
            )
        else:
            rolls = DiceRoller.roll(sides, count)
            notation = f"{count}d{sides}"
            if modifier:
                notation += f"{'+' if modifier >= 0 else ''}{modifier}"
            return DiceResult(
                rolls=rolls,
                modifier=modifier,
                total=sum(rolls) + modifier,
                notation=notation,
            )

    @staticmethod
    def format_result(result: DiceResult, verbose: bool = False) -> str:
        """
        Format a dice result for display.

        Args:
            result: The DiceResult to format
            verbose: Whether to show individual rolls

        Returns:
            Formatted string (e.g., "14" or "d20(14)+3=17")
        """
        if not verbose:
            return str(result.total)

        if len(result.rolls) == 1:
            base = f"d{20 if result.is_natural_20 or result.is_natural_1 else '?'}({result.rolls[0]})"
        else:
            base = f"[{'+'.join(str(r) for r in result.rolls)}]"

        if result.modifier:
            mod_str = f"{'+' if result.modifier >= 0 else ''}{result.modifier}"
            return f"{base}{mod_str}={result.total}"
        return f"{base}={result.total}"


# Convenience functions
def d20(modifier: int = 0, advantage: bool = False, disadvantage: bool = False) -> DiceResult:
    """Roll a d20 with optional modifier and advantage/disadvantage."""
    return DiceRoller.roll_with_modifier(20, modifier, 1, advantage, disadvantage)


def d6(count: int = 1, modifier: int = 0) -> DiceResult:
    """Roll d6(s) with optional modifier."""
    return DiceRoller.roll_with_modifier(6, modifier, count)


def d8(count: int = 1, modifier: int = 0) -> DiceResult:
    """Roll d8(s) with optional modifier."""
    return DiceRoller.roll_with_modifier(8, modifier, count)


def d10(count: int = 1, modifier: int = 0) -> DiceResult:
    """Roll d10(s) with optional modifier."""
    return DiceRoller.roll_with_modifier(10, modifier, count)
