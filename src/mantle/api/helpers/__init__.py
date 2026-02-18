# src/mantle/api/helpers/__init__.py
"""
Helper modules extracted from game_routes.py for better organization.

- prompt_builders: Functions that build DM prompt context sections
- narrative_extraction: Functions that extract information from narrative text
"""

from .prompt_builders import (
    get_story_scope_guidance,
    get_genre_guidance,
    get_style_instructions,
    get_protagonist_arc_guidance,
    get_lethality_guidance,
    get_moral_complexity_guidance,
    build_storytelling_preferences_context,
    get_guidance_instruction,
)

from .narrative_extraction import (
    extract_entity_names_from_text,
    extract_scene_npcs_from_narrative,
    get_npc_ids_for_memory_context,
    apply_legend_reputation_to_new_npcs,
)

__all__ = [
    # Prompt builders
    "get_story_scope_guidance",
    "get_genre_guidance",
    "get_style_instructions",
    "get_protagonist_arc_guidance",
    "get_lethality_guidance",
    "get_moral_complexity_guidance",
    "build_storytelling_preferences_context",
    "get_guidance_instruction",
    # Narrative extraction
    "extract_entity_names_from_text",
    "extract_scene_npcs_from_narrative",
    "get_npc_ids_for_memory_context",
    "apply_legend_reputation_to_new_npcs",
]
