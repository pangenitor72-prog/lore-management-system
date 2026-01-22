# src/airpg/runtime/interactive_loop.py
from __future__ import annotations
from typing import List, Tuple, Optional, Callable

from .runtime import MinimalRuntime
from .session_state import SessionState
from .session_loop import run_session_step
from .gameplay_rules import GameplayRule
from .interface_adapter import render_prompt, render_trace

def run_interactive_loop(
    *,
    initial_state: SessionState,
    agent_ids: Tuple[str, ...],
    deliver_fn: Callable[..., List[Tuple[str, str]]],
    rules: Optional[List[GameplayRule]] = None,
    runtime: MinimalRuntime,
    input_fn: Callable[[], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """
    Manages a stateless, interactive I/O loop for the runtime.

    This loop holds NO state. All state is received from and passed back to
    the orchestrating `run_session_step` function via the SessionState object.
    """
    state = initial_state
    try:
        while True:
            prompt = render_prompt(state)
            player_input = input_fn(prompt)

            if player_input.lower() in ("quit", "exit"):
                output_fn("Exiting session.")
                break

            next_state, trace = run_session_step(
                state=state,
                player_input=player_input,
                agent_ids=agent_ids,
                deliver_fn=deliver_fn,
                runtime=runtime,
                rules=rules,
            )

            # Render the output of the turn
            output_lines = render_trace(trace)
            for line in output_lines:
                output_fn(line)
            
            # This is the only state update in the entire loop.
            state = next_state

    except KeyboardInterrupt:
        output_fn("\nSession interrupted by user.")
    except Exception as e:
        output_fn(f"\nAn unexpected error occurred: {e}")
