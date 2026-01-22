# src/lms/arc/__init__.py
"""
Arc Engine - Narrative Structure and Pacing System

Provides story phase tracking, tension management, and episode pacing
based on Campbell's Hero's Journey (monomyth) structure.

Components:
- StoryPhase: State machine for Campbell's 12 stages
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
from .story_phase import StoryPhaseManager
from .tension_tracker import TensionTracker
from .beat_suggester import BeatSuggester
from .episode_manager import EpisodeManager
from .arc_engine import ArcEngine

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
    # Managers
    "StoryPhaseManager",
    "TensionTracker",
    "BeatSuggester",
    "EpisodeManager",
    # Main Engine
    "ArcEngine",
]
