# src/airpg/runtime/session_loop.py
from __future__ import annotations
from typing import List, Tuple, Optional, Callable
import copy

from .runtime import MinimalRuntime, TraceEvent
from .session_state import SessionState
from .gameplay_rules import GameplayRule

def run_session_step(
    *,
    state: SessionState,
    player_input: str,
    agent_ids: Tuple[str, ...],
    deliver_fn: Callable[..., List[Tuple[str, str]]],
    runtime: MinimalRuntime,
    rules: Optional[List[GameplayRule]] = None,
) -> Tuple[SessionState, List[TraceEvent]]:
    """
    Runs a single, deterministic step of a session loop.

    1. Applies gameplay rules to the initial message.
    2. Runs one full interaction via MinimalRuntime.
    3. Extracts a handoff payload from the resulting trace.
    4. Returns a NEW SessionState and the trace. Does not mutate inputs.
    """
    # The message for this turn is ALWAYS the player's direct input.
    message = player_input

    # Apply gameplay rules to the player's current input before interaction
    if rules:
        for rule in rules:
            transformed_message = rule(message, state)
            if transformed_message is None:
                # Rule blocked propagation entirely
                next_state = SessionState(
                    turn_index=state.turn_index + 1,
                    last_player_message=player_input,
                    last_handoff_message="[Action blocked by rule]",
                )
                return next_state, []
            message = transformed_message

    initial_message = message

    # The player's action is injected into the world by targeting themselves.
    # The deliver_fn then determines propagation to other agents.
    initial_sender = "Player"
    initial_receiver = "Player"

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
