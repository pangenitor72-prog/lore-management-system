# src/airpg/runtime/rules/__init__.py
"""
RPG gameplay rules module.

Contains rules that enforce D&D 5e mechanics and may trigger
Interventions for manual dice rolls.
"""
from .stat_check_rule import stat_check_rule
from .dnd5e_rules import stat_check_rule as dnd5e_stat_check_rule
from .dnd5e_rules import combat_rule, DND5E_RULES

__all__ = [
    "stat_check_rule",
    "dnd5e_stat_check_rule",
    "combat_rule",
    "DND5E_RULES",
]
