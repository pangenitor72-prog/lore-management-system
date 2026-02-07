# src/mantle/visual/__init__.py
"""
Visual Engine for AIRPG.

Generates contextual images during gameplay using style profiles
and visual assessments from the narrative engine.
"""

from .types import (
    GenerationResult,
    ImageSpecs,
    ImageType,
    Mood,
    PromptResult,
    StyleProfile,
    VisualAssessment,
    WorldDescriptors,
    WorldVisualIdentity,
)
from .prompt_builder import (
    PromptBuilder,
    create_prompt_builder,
    load_all_style_profiles,
    load_style_profile,
)
from .cache_manager import (
    CachedImage,
    CacheManager,
    CacheMetadata,
)
from .engine import (
    ImageResult,
    VisualEngine,
    VisualEngineConfig,
    create_visual_engine,
)

__all__ = [
    # Types
    "GenerationResult",
    "ImageSpecs",
    "ImageType",
    "Mood",
    "PromptResult",
    "StyleProfile",
    "VisualAssessment",
    "WorldDescriptors",
    "WorldVisualIdentity",
    # Prompt Builder
    "PromptBuilder",
    "create_prompt_builder",
    "load_all_style_profiles",
    "load_style_profile",
    # Cache Manager
    "CachedImage",
    "CacheManager",
    "CacheMetadata",
    # Engine
    "ImageResult",
    "VisualEngine",
    "VisualEngineConfig",
    "create_visual_engine",
]
