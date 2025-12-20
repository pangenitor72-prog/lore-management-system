# src/airpg/runtime/gameplay_rules.py
from __future__ import annotations
from typing import Callable, Optional

from .session_state import SessionState

# A GameplayRule is a pure function that takes a message and the current
# session state, and returns either a transformed message or None to
# block the message entirely.
GameplayRule = Callable[[str, SessionState], Optional[str]]

# This function will be implemented in Task C
def rule_prevent_attack_on_turn_3(
    message: str, state: SessionState
) -> Optional[str]:
    """
    Example gameplay rule: If the turn index is 2 or more and the message
    contains "attack", transform it. Otherwise, allow it.
    """
    if state.turn_index >= 2 and "attack" in message.lower():
        return "hesitates instead of attacking"
    return message
