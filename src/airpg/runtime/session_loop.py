# src/airpg/runtime/session_loop.py
from __future__ import annotations
from typing import List, Tuple, Optional, Callable
import copy

from .runtime import MinimalRuntime, TraceEvent
from .session_state import SessionState

def run_session_step(
    *,
    state: SessionState,
    player_input: str,
    agent_ids: Tuple[str, ...],
    deliver_fn: Callable[..., List[Tuple[str, str]]],
    runtime: MinimalRuntime,
) -> Tuple[SessionState, List[TraceEvent]]:
    """
    Runs a single, deterministic step of a session loop.

    1. Derives interaction input ONLY from the current state and player input.
    2. Runs one full interaction via MinimalRuntime.
    3. Extracts a handoff payload from the resulting trace.
    4. Returns a NEW SessionState and the trace. Does not mutate inputs.
    """
    # Use last handoff as context if available, otherwise use player input directly
    initial_message = state.last_handoff_message or player_input

    # For this simple loop, the player always initiates contact with the first agent
    initial_sender = "Player"
    initial_receiver = agent_ids[1] if len(agent_ids) > 1 else agent_ids[0]

    trace = runtime.run_interaction(
        agent_ids=agent_ids,
        deliver_fn=deliver_fn,
        initial_sender=initial_sender,
        initial_receiver=initial_receiver,
        initial_message=initial_message,
    )

    handoff_message = None
    if trace:
        last_event = trace[-1]
        handoff_message = (
            f"After '{last_event.message[:32]}', "
            f"{last_event.receiver} considers what to do next."
        )

    # Create and return a NEW state object
    next_state = SessionState(
        turn_index=state.turn_index + 1,
        last_player_message=player_input,
        last_handoff_message=handoff_message,
    )

    return next_state, trace
