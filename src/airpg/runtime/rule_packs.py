# src/airpg/runtime/rule_packs.py
"""
Rule pack registry for dual-mode gameplay.

Provides collections of GameplayRules organized by game mode.
STORY mode uses minimal/no rules to preserve pure narrative flow.
RPG mode uses mechanical rules for D&D 5e-style gameplay.
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from .gameplay_rules import GameplayRule
from .rules.dnd5e_rules import DND5E_RULES

if TYPE_CHECKING:
    from .game_config import GameConfig


# STORY mode rules - empty by default to preserve existing behavior
# Pure narrative flow without mechanical interruptions
STORY_RULES: List[GameplayRule] = []

# RPG mode rules - uses the D&D 5e engine integration
# These rules wrap CheckEngine and CombatResolver from src/lms/dnd5e/
RPG_RULES: List[GameplayRule] = DND5E_RULES.copy()


def get_rules_for_config(config: Optional[GameConfig]) -> List[GameplayRule]:
    """
    Returns the appropriate rule pack for the given game configuration.

    Args:
        config: The GameConfig specifying mode and dice mechanics.
                If None, returns STORY_RULES (backwards compatible).

    Returns:
        List of GameplayRules to apply during session steps.
    """
    if config is None:
        return STORY_RULES

    if config.mode == "STORY":
        return STORY_RULES

    return RPG_RULES


def register_story_rule(rule: GameplayRule) -> GameplayRule:
    """
    Decorator to register a rule for STORY mode.

    Example:
        @register_story_rule
        def my_narrative_rule(message: str, state: SessionState) -> RuleResult:
            ...
    """
    STORY_RULES.append(rule)
    return rule


def register_rpg_rule(rule: GameplayRule) -> GameplayRule:
    """
    Decorator to register a rule for RPG mode.

    Example:
        @register_rpg_rule
        def stat_check_rule(message: str, state: SessionState) -> RuleResult:
            ...
    """
    RPG_RULES.append(rule)
    return rule
