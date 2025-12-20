# src/airpg/runtime/session_state.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SessionState:
    """
    Explicit, inspectable, and disposable session context.

    This is NOT engine memory or runtime memory. It is a plain data object
    passed between session loop steps to provide explicit continuity.
    It contains no behavior.
    """
    turn_index: int
    last_player_message: Optional[str] = None
    last_handoff_message: Optional[str] = None
