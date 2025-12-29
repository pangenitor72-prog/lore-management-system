# src/airpg/runtime/session_state.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .game_config import GameConfig
    from src.lms.dnd5e.models.character_sheet import CharacterSheet


@dataclass(frozen=True)
class SessionState:
    """
    Explicit, inspectable, and disposable session context.

    This is NOT engine memory or runtime memory. It is a plain data object
    passed between session loop steps to provide explicit continuity.
    It contains no behavior.

    Optional fields for dual-mode gameplay:
    - config: GameConfig for STORY/RPG mode selection (None = STORY mode)
    - session_id: For delta-layer persistence (None = no persistence)
    - character: D&D 5e CharacterSheet for RPG mode (None = STORY mode)
    """
    turn_index: int
    last_player_message: Optional[str] = None
    last_handoff_message: Optional[str] = None
    # Dual-mode support - defaults preserve existing STORY behavior
    config: Optional[GameConfig] = None
    session_id: Optional[str] = None
    # D&D 5e character for RPG mode
    character: Optional[CharacterSheet] = None
