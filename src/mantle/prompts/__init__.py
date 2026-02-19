"""
Prompt Library - Centralized AI prompt management.

All prompts used across the LMS/AIRpg system.
Versioned, testable, and easily iterable.
"""

from .dm_prompts import DMPrompts
from .query_prompts import QueryPrompts
from .auditor_prompts import AuditorPrompts
from .boundary_prompts import BoundaryPrompts
from .context_manager import PromptContextManager, ContextPriority, PromptBudget
from .formatters import (
    format_character_compact,
    format_npc_compact,
    format_npcs_section,
    format_entity_compact,
    format_graph_section,
    format_history_turn_compact,
    format_history_section,
    format_arc_compact,
    format_memory_relationship_compact,
    format_memory_section,
    format_warning_compact,
    format_warnings_section,
    format_npc_state_compact,
    format_world_lore_compact,
    format_storytelling_prefs_compact,
)

__all__ = [
    # Prompt classes
    'DMPrompts',
    'QueryPrompts',
    'AuditorPrompts',
    'BoundaryPrompts',
    # Context manager
    'PromptContextManager',
    'ContextPriority',
    'PromptBudget',
    # Formatters
    'format_character_compact',
    'format_npc_compact',
    'format_npcs_section',
    'format_entity_compact',
    'format_graph_section',
    'format_history_turn_compact',
    'format_history_section',
    'format_arc_compact',
    'format_memory_relationship_compact',
    'format_memory_section',
    'format_warning_compact',
    'format_warnings_section',
    'format_npc_state_compact',
    'format_world_lore_compact',
    'format_storytelling_prefs_compact',
]

PROMPT_VERSION = "3.0.0"
LAST_UPDATED = "2026-02-19"

