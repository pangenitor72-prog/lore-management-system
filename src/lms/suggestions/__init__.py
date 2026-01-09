# src/lms/suggestions/__init__.py
"""
Context-aware action suggestion system for AIRPG.

Provides mode-aware suggestions for both Quick Start (narrative-first)
and TTRPG (mechanics-visible) player modes.
"""

from .action_engine import (
    ActionSuggestionEngine,
    ActionSuggestion,
    ActionCategory,
    PlayerMode,
    generate_action_suggestions,
    get_action_engine,
)

__all__ = [
    "ActionSuggestionEngine",
    "ActionSuggestion",
    "ActionCategory",
    "PlayerMode",
    "generate_action_suggestions",
    "get_action_engine",
]
