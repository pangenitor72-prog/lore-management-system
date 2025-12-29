# src/airpg/runtime/rules/dnd5e_rules.py
"""
D&D 5e Rule Pack - Wraps the existing src/lms/dnd5e/engine for GameplayRule integration.

These rules use the established CheckEngine and CombatResolver instead of
reimplementing mechanics. They bridge the gap between player intent detection
and the 5e resolution system.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from ..session_state import SessionState
from ..gameplay_rules import Intervention, RuleResult

# Import the existing 5e engine
from src.lms.dnd5e.engine.checks import (
    CheckEngine,
    CheckResult,
    SKILL_TO_ABILITY,
    ALL_SKILLS,
    DIFFICULTY_CLASS,
)
from src.lms.dnd5e.engine.combat_resolver import (
    CombatResolver,
    AttackResult,
    DamageResult,
    DamageType,
    WEAPON_DAMAGE,
)


# ============================================================================
# SKILL CHECK TRIGGERS - Maps player intent to skill checks
# ============================================================================

SKILL_CHECK_TRIGGERS: Dict[str, Tuple[str, int]] = {
    # Athletics (STR)
    "climb": ("athletics", DIFFICULTY_CLASS["medium"]),
    "jump": ("athletics", DIFFICULTY_CLASS["easy"]),
    "swim": ("athletics", DIFFICULTY_CLASS["medium"]),
    "lift": ("athletics", DIFFICULTY_CLASS["hard"]),
    "push": ("athletics", DIFFICULTY_CLASS["medium"]),
    "grapple": ("athletics", DIFFICULTY_CLASS["medium"]),
    "shove": ("athletics", DIFFICULTY_CLASS["medium"]),

    # Acrobatics (DEX)
    "balance": ("acrobatics", DIFFICULTY_CLASS["medium"]),
    "tumble": ("acrobatics", DIFFICULTY_CLASS["medium"]),
    "flip": ("acrobatics", DIFFICULTY_CLASS["medium"]),
    "dodge": ("acrobatics", DIFFICULTY_CLASS["medium"]),

    # Stealth (DEX)
    "sneak": ("stealth", DIFFICULTY_CLASS["medium"]),
    "hide": ("stealth", DIFFICULTY_CLASS["easy"]),
    "creep": ("stealth", DIFFICULTY_CLASS["medium"]),

    # Sleight of Hand (DEX)
    "pickpocket": ("sleight_of_hand", DIFFICULTY_CLASS["hard"]),
    "pick lock": ("sleight_of_hand", DIFFICULTY_CLASS["hard"]),
    "lockpick": ("sleight_of_hand", DIFFICULTY_CLASS["hard"]),
    "palm": ("sleight_of_hand", DIFFICULTY_CLASS["medium"]),

    # Persuasion (CHA)
    "persuade": ("persuasion", DIFFICULTY_CLASS["medium"]),
    "convince": ("persuasion", DIFFICULTY_CLASS["medium"]),
    "negotiate": ("persuasion", DIFFICULTY_CLASS["medium"]),
    "charm": ("persuasion", DIFFICULTY_CLASS["hard"]),

    # Intimidation (CHA)
    "intimidate": ("intimidation", DIFFICULTY_CLASS["medium"]),
    "threaten": ("intimidation", DIFFICULTY_CLASS["medium"]),
    "scare": ("intimidation", DIFFICULTY_CLASS["medium"]),

    # Deception (CHA)
    "deceive": ("deception", DIFFICULTY_CLASS["medium"]),
    "lie": ("deception", DIFFICULTY_CLASS["easy"]),
    "bluff": ("deception", DIFFICULTY_CLASS["medium"]),
    "disguise": ("deception", DIFFICULTY_CLASS["hard"]),

    # Investigation (INT)
    "search": ("investigation", DIFFICULTY_CLASS["medium"]),
    "investigate": ("investigation", DIFFICULTY_CLASS["medium"]),
    "examine": ("investigation", DIFFICULTY_CLASS["easy"]),
    "analyze": ("investigation", DIFFICULTY_CLASS["medium"]),

    # Perception (WIS)
    "look": ("perception", DIFFICULTY_CLASS["easy"]),
    "spot": ("perception", DIFFICULTY_CLASS["medium"]),
    "listen": ("perception", DIFFICULTY_CLASS["easy"]),
    "notice": ("perception", DIFFICULTY_CLASS["medium"]),
    "watch": ("perception", DIFFICULTY_CLASS["easy"]),

    # Insight (WIS)
    "read": ("insight", DIFFICULTY_CLASS["medium"]),
    "sense motive": ("insight", DIFFICULTY_CLASS["medium"]),

    # Survival (WIS)
    "track": ("survival", DIFFICULTY_CLASS["medium"]),
    "forage": ("survival", DIFFICULTY_CLASS["medium"]),
    "navigate": ("survival", DIFFICULTY_CLASS["medium"]),

    # Arcana (INT)
    "identify spell": ("arcana", DIFFICULTY_CLASS["medium"]),
    "recall magic": ("arcana", DIFFICULTY_CLASS["medium"]),

    # Medicine (WIS)
    "stabilize": ("medicine", DIFFICULTY_CLASS["easy"]),
    "diagnose": ("medicine", DIFFICULTY_CLASS["medium"]),
    "treat": ("medicine", DIFFICULTY_CLASS["medium"]),
}

# Combat intent patterns
COMBAT_PATTERNS = [
    r"\battack\b",
    r"\bstrike\b",
    r"\bhit\b",
    r"\bslash\b",
    r"\bstab\b",
    r"\bshoot\b",
    r"\bfire at\b",
    r"\bswing at\b",
    r"\bpunch\b",
    r"\bkick\b",
]


def _format_skill_name(skill: str) -> str:
    """Format skill name for display (e.g., 'sleight_of_hand' -> 'Sleight of Hand')."""
    return skill.replace("_", " ").title()


def _detect_skill_check(message: str) -> Optional[Tuple[str, int]]:
    """
    Detect if a message triggers a skill check.

    Returns (skill, dc) if found, None otherwise.
    """
    message_lower = message.lower()
    for trigger, (skill, dc) in SKILL_CHECK_TRIGGERS.items():
        if trigger in message_lower:
            return (skill, dc)
    return None


def _detect_combat_intent(message: str) -> bool:
    """Detect if the message expresses combat intent."""
    message_lower = message.lower()
    for pattern in COMBAT_PATTERNS:
        if re.search(pattern, message_lower):
            return True
    return False


def _format_check_result(result: CheckResult, original_message: str) -> str:
    """Format a CheckResult into a narrative message."""
    skill_display = _format_skill_name(result.skill_used or "")
    outcome = result.narrative_outcome

    if outcome == "critical_success":
        prefix = "CRITICAL SUCCESS!"
    elif outcome == "success":
        prefix = "Success!"
    elif outcome == "close_success":
        prefix = "Barely succeeds!"
    elif outcome == "close_failure":
        prefix = "Just misses!"
    elif outcome == "failure":
        prefix = "Fails."
    else:  # critical_failure
        prefix = "CRITICAL FAILURE!"

    return (
        f"{original_message} "
        f"[{prefix} {skill_display} check: {result.roll}+{result.modifier}={result.total} vs DC {result.dc}]"
    )


def _format_attack_result(result: AttackResult, original_message: str) -> str:
    """Format an AttackResult into a narrative message."""
    if result.is_critical:
        outcome = "CRITICAL HIT!"
    elif result.is_critical_miss:
        outcome = "Critical miss!"
    elif result.is_hit:
        outcome = "Hit!"
    else:
        outcome = "Miss."

    return (
        f"{original_message} "
        f"[{outcome} Attack: {result.attack_roll}+{result.attack_modifier}={result.attack_total} vs AC {result.target_ac}]"
    )


# ============================================================================
# GAMEPLAY RULES
# ============================================================================

def stat_check_rule(message: str, state: SessionState) -> RuleResult:
    """
    D&D 5e Skill Check Rule using the existing CheckEngine.

    Behavior:
    - STORY mode or no config: Pass-through (no mechanical checks)
    - RPG/NARRATIVE: Pass-through (let LLM handle outcomes)
    - RPG/AUTO: Use CheckEngine to resolve, append result to message
    - RPG/MANUAL: Return Intervention requesting dice roll

    Requires state.character to be set for AUTO mode resolution.
    """
    # STORY mode = pure narrative, no stat checks
    if state.config is None or state.config.mode != "RPG":
        return message

    # NARRATIVE dice = LLM handles outcomes
    if state.config.dice_mechanic == "NARRATIVE":
        return message

    # Check if message triggers a skill check
    trigger = _detect_skill_check(message)
    if trigger is None:
        return message

    skill, dc = trigger
    skill_display = _format_skill_name(skill)

    if state.config.dice_mechanic == "MANUAL":
        # Request player to roll dice
        modifier = 0
        if state.character:
            modifier = state.character.get_skill_modifier(skill)

        return Intervention(
            type="INPUT_REQUEST",
            prompt=f"Roll {skill_display} Check (DC {dc}) [Modifier: +{modifier}]",
            context={
                "check_type": "skill",
                "skill": skill,
                "dc": dc,
                "modifier": modifier,
                "original_message": message,
            },
            resume_key=f"skill_check_{skill}",
        )

    # AUTO mode: resolve using CheckEngine
    if state.character is None:
        # No character = can't resolve mechanically, fall back to narrative
        return message

    result = CheckEngine.skill_check(
        character=state.character,
        skill=skill,
        dc=dc,
    )

    return _format_check_result(result, message)


def combat_rule(message: str, state: SessionState) -> RuleResult:
    """
    D&D 5e Combat Rule using the existing CombatResolver.

    Behavior:
    - STORY mode or no config: Pass-through
    - RPG/NARRATIVE: Pass-through
    - RPG/AUTO: Use CombatResolver to resolve attack
    - RPG/MANUAL: Return Intervention requesting attack roll

    Note: This is a simplified implementation. Full combat would require
    target selection, AC lookup, weapon selection, etc.
    """
    # STORY mode = pure narrative
    if state.config is None or state.config.mode != "RPG":
        return message

    # NARRATIVE dice = LLM handles combat
    if state.config.dice_mechanic == "NARRATIVE":
        return message

    # Check for combat intent
    if not _detect_combat_intent(message):
        return message

    if state.config.dice_mechanic == "MANUAL":
        # Request attack roll
        attack_mod = 0
        if state.character:
            attack_mod = state.character.get_attack_modifier()

        return Intervention(
            type="INPUT_REQUEST",
            prompt=f"Roll Attack (d20) [Modifier: +{attack_mod}]",
            context={
                "check_type": "attack",
                "attack_modifier": attack_mod,
                "original_message": message,
                # Target AC would come from combat state in full implementation
                "target_ac": 15,  # Default placeholder
            },
            resume_key="attack_roll",
        )

    # AUTO mode: resolve using CombatResolver
    if state.character is None:
        return message

    # Simplified: assume melee attack against AC 15
    # Full implementation would track target entity and their AC
    result = CombatResolver.resolve_attack(
        attacker=state.character,
        target_ac=15,
        weapon_type="melee",
    )

    return _format_attack_result(result, message)


# ============================================================================
# RULE PACK EXPORT
# ============================================================================

DND5E_RULES = [
    stat_check_rule,
    combat_rule,
]
