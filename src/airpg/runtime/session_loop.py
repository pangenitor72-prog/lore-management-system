# src/airpg/runtime/session_loop.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable, Union
import copy

from .runtime import MinimalRuntime, TraceEvent
from .session_state import SessionState
from .gameplay_rules import GameplayRule, Intervention


@dataclass
class StepResult:
    """
    Result of a session step, supporting intervention pauses.

    When intervention is set, the session loop is paused waiting for
    external input. The caller should send the intervention prompt to
    the user, collect the response, and resume with that input.
    """
    state: SessionState
    trace: List[TraceEvent]
    intervention: Optional[Intervention] = None

    @property
    def is_paused(self) -> bool:
        """Returns True if the step is waiting for intervention response."""
        return self.intervention is not None


def run_session_step(
    *,
    state: SessionState,
    player_input: str,
    agent_ids: Tuple[str, ...],
    deliver_fn: Callable[..., List[Tuple[str, str]]],
    runtime: MinimalRuntime,
    rules: Optional[List[GameplayRule]] = None,
) -> Union[Tuple[SessionState, List[TraceEvent]], StepResult]:
    """
    Runs a single, deterministic step of a session loop.

    1. Applies gameplay rules to the initial message.
    2. Runs one full interaction via MinimalRuntime.
    3. Extracts a handoff payload from the resulting trace.
    4. Returns a NEW SessionState and the trace. Does not mutate inputs.

    Returns:
        - Tuple[SessionState, List[TraceEvent]]: Normal completion (backwards compatible)
        - StepResult with intervention: When a rule requests external input (RPG mode)
    """
    # The message for this turn is ALWAYS the player's direct input.
    message = player_input

    # Apply gameplay rules to the player's current input before interaction
    if rules:
        for rule in rules:
            result = rule(message, state)

            # Check for Intervention (RPG/MANUAL mode pause)
            if isinstance(result, Intervention):
                return StepResult(
                    state=state,
                    trace=[],
                    intervention=result,
                )

            if result is None:
                # Rule blocked propagation entirely
                next_state = SessionState(
                    turn_index=state.turn_index + 1,
                    last_player_message=player_input,
                    last_handoff_message="[Action blocked by rule]",
                    config=state.config,
                    session_id=state.session_id,
                    character=state.character,
                )
                return next_state, []

            message = result

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

    # Create and return a NEW state object, preserving config, session_id, and character
    next_state = SessionState(
        turn_index=state.turn_index + 1,
        last_player_message=player_input,
        last_handoff_message=handoff_message,
        config=state.config,
        session_id=state.session_id,
        character=state.character,
    )

    return next_state, trace
