# src/lms/arc/__init__.py
"""
Arc Engine - Narrative Structure and Pacing System

Provides story phase tracking, tension management, and episode pacing.
Supports multiple narrative structures:
- Campbell's Hero's Journey (default for fantasy/adventure)
- Genre-specific arcs (horror, mystery, heist, romance, etc.)

Components:
- StoryPhase: State machine for Campbell's 12 stages
- GenrePhase: Dynamic phases for genre-specific arcs
- TensionTracker: Rising/falling action awareness
- BeatSuggester: Narrative guidance hints for the DM
- EpisodeManager: Session pacing and boundaries
"""

from .models import (
    StoryPhase,
    StoryAct,
    TensionLevel,
    BeatType,
    ArcState,
    NarrativeBeat,
    EpisodeBoundary,
    StoryContext,
)
from .genre_arcs import (
    GenreArcType,
    GenrePhase,
    get_arc_type_for_genre,
    get_phases_for_arc,
    get_beat_templates_for_phase,
    get_valid_transitions,
    get_phase_indicators,
    GENRE_TO_ARC,
    GENRE_ARC_PHASES,
    GENRE_BEAT_TEMPLATES,
    GENRE_TRANSITIONS,
)
from .story_phase import StoryPhaseManager
from .tension_tracker import TensionTracker
from .beat_suggester import BeatSuggester
from .episode_manager import EpisodeManager
from .arc_engine import ArcEngine
from .preference_adapter import (
    get_adapted_description,
    get_adapted_guidance,
    get_adapted_tension_target,
    get_adapted_pacing_guidance,
)

__all__ = [
    # Models
    "StoryPhase",
    "StoryAct",
    "TensionLevel",
    "BeatType",
    "ArcState",
    "NarrativeBeat",
    "EpisodeBoundary",
    "StoryContext",
    # Genre Arc Types
    "GenreArcType",
    "GenrePhase",
    "get_arc_type_for_genre",
    "get_phases_for_arc",
    "get_beat_templates_for_phase",
    "get_valid_transitions",
    "get_phase_indicators",
    "GENRE_TO_ARC",
    "GENRE_ARC_PHASES",
    "GENRE_BEAT_TEMPLATES",
    "GENRE_TRANSITIONS",
    # Managers
    "StoryPhaseManager",
    "TensionTracker",
    "BeatSuggester",
    "EpisodeManager",
    # Main Engine
    "ArcEngine",
    # Preference Adapter
    "get_adapted_description",
    "get_adapted_guidance",
    "get_adapted_tension_target",
    "get_adapted_pacing_guidance",
]
