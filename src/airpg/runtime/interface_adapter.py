# src/airpg/runtime/interface_adapter.py
from __future__ import annotations
from typing import List

from .runtime import TraceEvent
from .session_state import SessionState

def render_trace(trace: List[TraceEvent]) -> List[str]:
    """
    Converts a list of TraceEvent objects into human-readable strings.
    This is a pure function for formatting only.
    """
    lines = []
    if not trace:
        return ["- No action taken -"]
    
    for event in trace:
        lines.append(
            f"  {event.sender or 'System'} -> {event.receiver}: '{event.message}'"
        )
    return lines

def render_prompt(state: SessionState) -> str:
    """
    Generates a player prompt based ONLY on the explicit SessionState.
    """
    if state.last_handoff_message:
        return f"\nTurn {state.turn_index}. {state.last_handoff_message}\n> "
    
    return f"\nTurn {state.turn_index}. What do you do?\n> "
