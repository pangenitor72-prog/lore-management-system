"""
D&D 5e Rules System for the Lore Management System.

This module provides:
- Ability scores and modifiers
- Race and class definitions
- Character sheet management
- Dice rolling and check resolution
- Combat mechanics
- Scalable visibility (Storyteller → Tactician)
- Character creation flows (Concept → Expert)
"""

from .models.ability_scores import AbilityScores, AbilityName
from .models.races import RaceName, RaceData, RACES
from .models.classes import ClassName, ClassData, CLASSES
from .models.character_sheet import CharacterSheet
from .engine.dice import DiceRoller
from .engine.checks import CheckEngine, CheckResult
from .engine.combat_resolver import CombatResolver, AttackResult, DamageResult
from .creation.modes import CreationMode, RulesVisibility, DEFAULT_VISIBILITY

__all__ = [
    # Models
    "AbilityScores",
    "AbilityName",
    "RaceName",
    "RaceData",
    "RACES",
    "ClassName",
    "ClassData",
    "CLASSES",
    "CharacterSheet",
    # Engine
    "DiceRoller",
    "CheckEngine",
    "CheckResult",
    "CombatResolver",
    "AttackResult",
    "DamageResult",
    # Creation
    "CreationMode",
    "RulesVisibility",
    "DEFAULT_VISIBILITY",
]
