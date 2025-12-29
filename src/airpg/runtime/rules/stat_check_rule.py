# src/airpg/runtime/rules/stat_check_rule.py
"""
Stat Check Rule - Proof of Concept for RPG/MANUAL mode.

Detects actions that require ability checks and either:
- AUTO mode: Rolls automatically and resolves
- MANUAL mode: Returns an Intervention to request player dice roll
"""
from __future__ import annotations

import random
import re
from typing import Dict, List, Tuple

from ..session_state import SessionState
from ..gameplay_rules import Intervention, RuleResult


# Keywords that trigger stat checks, mapped to (skill, default DC)
STAT_CHECK_TRIGGERS: Dict[str, Tuple[str, int]] = {
    "climb": ("athletics", 12),
    "jump": ("athletics", 10),
    "swim": ("athletics", 12),
    "lift": ("athletics", 15),
    "push": ("athletics", 12),
    "sneak": ("stealth", 12),
    "hide": ("stealth", 10),
    "pickpocket": ("sleight_of_hand", 15),
    "pick lock": ("sleight_of_hand", 15),
    "lockpick": ("sleight_of_hand", 15),
    "persuade": ("persuasion", 12),
    "convince": ("persuasion", 12),
    "intimidate": ("intimidation", 14),
    "threaten": ("intimidation", 12),
    "deceive": ("deception", 12),
    "lie": ("deception", 10),
    "bluff": ("deception", 12),
    "search": ("investigation", 12),
    "investigate": ("investigation", 14),
    "examine": ("perception", 10),
    "look for": ("perception", 12),
    "spot": ("perception", 12),
    "listen": ("perception", 10),
}


def _detect_check_trigger(message: str) -> Tuple[str, int] | None:
    """
    Detect if a message contains a stat check trigger.

    Returns (skill, dc) if a trigger is found, None otherwise.
    """
    message_lower = message.lower()
    for trigger, (skill, dc) in STAT_CHECK_TRIGGERS.items():
        if trigger in message_lower:
            return (skill, dc)
    return None


def _format_skill_name(skill: str) -> str:
    """Format skill name for display (e.g., 'sleight_of_hand' -> 'Sleight of Hand')."""
    return skill.replace("_", " ").title()


def _resolve_check(message: str, roll: int, dc: int, skill: str) -> str:
    """
    Resolve a stat check and transform the message accordingly.

    Args:
        message: Original player message
        roll: The d20 roll result (1-20)
        dc: Difficulty class to beat
        skill: The skill being checked

    Returns:
        Transformed message reflecting success or failure
    """
    success = roll >= dc
    skill_display = _format_skill_name(skill)

    if success:
        return f"{message} [SUCCESS: {skill_display} check {roll} vs DC {dc}]"
    else:
        return f"attempts to {message.lower()} but fails [FAILURE: {skill_display} check {roll} vs DC {dc}]"


def stat_check_rule(message: str, state: SessionState) -> RuleResult:
    """
    RPG rule that handles ability/skill checks.

    Behavior by mode:
    - STORY mode (config=None or mode="STORY"): Pass-through, no checks
    - RPG/NARRATIVE: Pass-through, narrative handles outcomes
    - RPG/AUTO: Roll d20 automatically, transform message with result
    - RPG/MANUAL: Return Intervention to request player's dice roll

    Args:
        message: The player's input message
        state: Current session state including GameConfig

    Returns:
        - str: Transformed or unchanged message
        - Intervention: Request for manual dice roll (RPG/MANUAL mode)
    """
    # STORY mode or no config = pure narrative, no stat checks
    if state.config is None or state.config.mode != "RPG":
        return message

    # NARRATIVE dice mechanic = let the LLM handle outcomes narratively
    if state.config.dice_mechanic == "NARRATIVE":
        return message

    # Check if message triggers a stat check
    trigger = _detect_check_trigger(message)
    if trigger is None:
        return message

    skill, dc = trigger
    skill_display = _format_skill_name(skill)

    if state.config.dice_mechanic == "MANUAL":
        # Request player to roll dice
        return Intervention(
            type="INPUT_REQUEST",
            prompt=f"Roll {skill_display} Check (DC {dc})",
            context={
                "skill": skill,
                "dc": dc,
                "original_message": message,
                "check_type": "ability_check",
            },
            resume_key=f"stat_check_{skill}",
        )

    # AUTO mode: roll automatically
    roll = random.randint(1, 20)
    return _resolve_check(message, roll, dc, skill)
