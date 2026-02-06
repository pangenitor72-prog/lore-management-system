# src/mantle/api/session_state.py
"""
Shared Session State Module

Centralizes global state that multiple route modules need access to.
This enables splitting game_routes.py into smaller modules while
maintaining shared access to session data.

Usage:
    from src.mantle.api.session_state import (
        active_sessions, game_states, get_session, get_game_state
    )
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from src.mantle.engine.game_state import GameState

logger = logging.getLogger(__name__)

# ============================================================
# ACTIVE SESSIONS
# ============================================================
# Maps session_id -> session data dict
# Session data includes: world_id, character_concept, genre, history, phase, etc.
active_sessions: Dict[str, Dict[str, Any]] = {}

# ============================================================
# GAME STATES
# ============================================================
# Maps session_id -> GameState object (combat, inventory, world integrity)
game_states: Dict[str, GameState] = {}

# ============================================================
# CONSTANTS
# ============================================================
MAX_SAVES_PER_BROWSER = 50


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session data by ID, or None if not found."""
    return active_sessions.get(session_id)


def get_game_state(session_id: str) -> Optional[GameState]:
    """Get game state by session ID, or None if not found."""
    return game_states.get(session_id)


def session_exists(session_id: str) -> bool:
    """Check if a session exists."""
    return session_id in active_sessions


def create_session(session_id: str, session_data: Dict[str, Any]) -> None:
    """Create a new session."""
    active_sessions[session_id] = session_data
    logger.debug(f"Created session {session_id}")


def update_session(session_id: str, updates: Dict[str, Any]) -> bool:
    """Update an existing session. Returns False if session doesn't exist."""
    if session_id not in active_sessions:
        return False
    active_sessions[session_id].update(updates)
    return True


def delete_session(session_id: str) -> bool:
    """Delete a session and its game state. Returns False if not found."""
    deleted = False
    if session_id in active_sessions:
        del active_sessions[session_id]
        deleted = True
    if session_id in game_states:
        del game_states[session_id]
    return deleted


def set_game_state(session_id: str, state: GameState) -> None:
    """Set game state for a session."""
    game_states[session_id] = state


def list_session_ids() -> list:
    """Get list of all active session IDs."""
    return list(active_sessions.keys())


def get_session_count() -> int:
    """Get count of active sessions."""
    return len(active_sessions)
