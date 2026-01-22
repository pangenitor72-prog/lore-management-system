"""Visibility filtering for rules presentation."""

from typing import Dict, Any, Optional
from ..creation.modes import RulesVisibility
from ..engine.checks import CheckResult
from ..engine.combat_resolver import AttackResult, DamageResult


class VisibilityFilter:
    """
    Filters mechanical output based on visibility mode.

    Transforms raw mechanical results into presentation-appropriate format.
    """

    @staticmethod
    def filter_check_result(
        result: CheckResult,
        visibility: RulesVisibility,
    ) -> Dict[str, Any]:
        """
        Filter a check result based on visibility level.

        Args:
            result: The CheckResult to filter
            visibility: Current visibility mode

        Returns:
            Dict with visibility-appropriate information
        """
        if visibility == RulesVisibility.STORYTELLER:
            # Pure narrative - no numbers
            return {
                "outcome": result.narrative_outcome,
                "success": result.success,
                "description": _get_check_narrative(result),
            }

        elif visibility == RulesVisibility.GUIDED:
            # Light hints about what helped
            hint = _get_ability_hint(result)
            return {
                "outcome": result.narrative_outcome,
                "success": result.success,
                "description": _get_check_narrative(result),
                "hint": hint,
            }

        elif visibility == RulesVisibility.CLASSIC:
            # Standard D&D format
            ability_name = result.ability_used or "ability"
            if result.skill_used:
                check_name = result.skill_used.replace("_", " ").title()
            else:
                check_name = ability_name.upper()[:3]

            return {
                "outcome": result.narrative_outcome,
                "success": result.success,
                "check_name": check_name,
                "total": result.total,
                "dc": result.dc,
                "display": f"{check_name}: {result.total} vs DC {result.dc}",
            }

        else:  # TACTICIAN - full breakdown
            ability_name = result.ability_used or "ability"
            if result.skill_used:
                check_name = result.skill_used.replace("_", " ").title()
            else:
                check_name = ability_name.upper()[:3]

            mod_str = f"+{result.modifier}" if result.modifier >= 0 else str(result.modifier)
            rolls_str = ",".join(str(r) for r in result.rolls)

            return {
                "outcome": result.narrative_outcome,
                "success": result.success,
                "check_name": check_name,
                "d20_roll": result.roll,
                "all_rolls": result.rolls,
                "modifier": result.modifier,
                "total": result.total,
                "dc": result.dc,
                "margin": result.margin,
                "is_natural_20": result.is_natural_20,
                "is_natural_1": result.is_natural_1,
                "display": f"{check_name}: d20({rolls_str}){mod_str}={result.total} vs DC {result.dc}",
            }

    @staticmethod
    def filter_attack_result(
        result: AttackResult,
        visibility: RulesVisibility,
    ) -> Dict[str, Any]:
        """Filter an attack result based on visibility level."""
        if visibility == RulesVisibility.STORYTELLER:
            return {
                "outcome": result.narrative_outcome,
                "is_hit": result.is_hit,
                "is_critical": result.is_critical,
                "description": _get_attack_narrative(result),
            }

        elif visibility == RulesVisibility.GUIDED:
            hint = ""
            if result.is_critical:
                hint = "A perfect strike!"
            elif result.is_critical_miss:
                hint = "A clumsy swing..."
            elif result.is_hit:
                hint = "Your training shows"
            else:
                hint = "The enemy was too quick"

            return {
                "outcome": result.narrative_outcome,
                "is_hit": result.is_hit,
                "is_critical": result.is_critical,
                "description": _get_attack_narrative(result),
                "hint": hint,
            }

        elif visibility == RulesVisibility.CLASSIC:
            return {
                "outcome": result.narrative_outcome,
                "is_hit": result.is_hit,
                "is_critical": result.is_critical,
                "total": result.attack_total,
                "target_ac": result.target_ac,
                "display": f"Attack: {result.attack_total} vs AC {result.target_ac} - {'Hit!' if result.is_hit else 'Miss'}",
            }

        else:  # TACTICIAN
            mod_str = f"+{result.attack_modifier}" if result.attack_modifier >= 0 else str(result.attack_modifier)
            rolls_str = ",".join(str(r) for r in result.attack_rolls)

            return {
                "outcome": result.narrative_outcome,
                "is_hit": result.is_hit,
                "is_critical": result.is_critical,
                "is_critical_miss": result.is_critical_miss,
                "d20_roll": result.attack_roll,
                "all_rolls": result.attack_rolls,
                "modifier": result.attack_modifier,
                "total": result.attack_total,
                "target_ac": result.target_ac,
                "display": f"Attack: d20({rolls_str}){mod_str}={result.attack_total} vs AC {result.target_ac}",
            }

    @staticmethod
    def filter_damage_result(
        result: DamageResult,
        visibility: RulesVisibility,
    ) -> Dict[str, Any]:
        """Filter a damage result based on visibility level."""
        if visibility == RulesVisibility.STORYTELLER:
            severity = "devastating" if result.damage_total >= 15 else \
                       "solid" if result.damage_total >= 8 else "glancing"
            return {
                "severity": severity,
                "is_critical": result.is_critical,
            }

        elif visibility == RulesVisibility.GUIDED:
            return {
                "damage": result.damage_total,
                "damage_type": result.damage_type.value,
                "is_critical": result.is_critical,
                "hint": "Critical damage!" if result.is_critical else None,
            }

        elif visibility == RulesVisibility.CLASSIC:
            return {
                "damage": result.damage_total,
                "damage_type": result.damage_type.value,
                "is_critical": result.is_critical,
                "display": f"{result.damage_total} {result.damage_type.value} damage",
            }

        else:  # TACTICIAN
            rolls_str = "+".join(str(r) for r in result.damage_rolls)
            mod_str = f"+{result.damage_modifier}" if result.damage_modifier > 0 else \
                      str(result.damage_modifier) if result.damage_modifier < 0 else ""

            return {
                "damage": result.damage_total,
                "damage_type": result.damage_type.value,
                "damage_rolls": result.damage_rolls,
                "modifier": result.damage_modifier,
                "is_critical": result.is_critical,
                "display": f"[{rolls_str}]{mod_str}={result.damage_total} {result.damage_type.value}",
            }

    @staticmethod
    def format_for_narrative(
        check_result: Optional[CheckResult] = None,
        attack_result: Optional[AttackResult] = None,
        damage_result: Optional[DamageResult] = None,
        visibility: RulesVisibility = RulesVisibility.GUIDED,
    ) -> str:
        """
        Format results into a single narrative string for DM integration.

        Returns a string that can be appended to DM narrative.
        """
        parts = []

        if check_result:
            filtered = VisibilityFilter.filter_check_result(check_result, visibility)
            if visibility == RulesVisibility.STORYTELLER:
                pass  # No mechanical text
            elif visibility == RulesVisibility.GUIDED:
                if filtered.get("hint"):
                    parts.append(f"({filtered['hint']})")
            else:
                parts.append(f"[{filtered['display']}]")

        if attack_result:
            filtered = VisibilityFilter.filter_attack_result(attack_result, visibility)
            if visibility == RulesVisibility.STORYTELLER:
                pass
            elif visibility == RulesVisibility.GUIDED:
                if filtered.get("hint"):
                    parts.append(f"({filtered['hint']})")
            else:
                parts.append(f"[{filtered['display']}]")

        if damage_result:
            filtered = VisibilityFilter.filter_damage_result(damage_result, visibility)
            if visibility in [RulesVisibility.CLASSIC, RulesVisibility.TACTICIAN]:
                parts.append(f"[{filtered['display']}]")

        return " ".join(parts)


def _get_check_narrative(result: CheckResult) -> str:
    """Generate narrative description for a check result."""
    outcomes = {
        "critical_success": [
            "succeeds brilliantly",
            "accomplishes the task with exceptional skill",
            "exceeds all expectations",
        ],
        "success": [
            "succeeds",
            "manages to accomplish the task",
            "pulls it off",
        ],
        "close_success": [
            "barely succeeds",
            "just manages to pull through",
            "succeeds by the skin of their teeth",
        ],
        "close_failure": [
            "comes close but fails",
            "almost succeeds",
            "falls just short",
        ],
        "failure": [
            "fails",
            "doesn't quite manage it",
            "comes up short",
        ],
        "critical_failure": [
            "fails spectacularly",
            "makes a costly mistake",
            "fumbles badly",
        ],
    }
    import random
    options = outcomes.get(result.narrative_outcome, outcomes["failure"])
    return random.choice(options)


def _get_ability_hint(result: CheckResult) -> str:
    """Generate a hint about which ability helped or hindered."""
    ability = result.ability_used
    if not ability:
        return ""

    ability_descriptions = {
        "strength": "physical power",
        "dexterity": "quick reflexes",
        "constitution": "endurance",
        "intelligence": "sharp mind",
        "wisdom": "keen perception",
        "charisma": "force of personality",
    }

    desc = ability_descriptions.get(ability, ability)

    if result.success:
        return f"Your {desc} helped here"
    else:
        return f"Your {desc} wasn't quite enough"


def _get_attack_narrative(result: AttackResult) -> str:
    """Generate narrative description for an attack result."""
    if result.is_critical:
        return "strikes with devastating precision"
    elif result.is_critical_miss:
        return "swings wildly and misses completely"
    elif result.is_hit:
        return "lands a solid blow"
    else:
        return "fails to connect"
