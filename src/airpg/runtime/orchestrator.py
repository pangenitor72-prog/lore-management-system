# src/airpg/runtime/orchestrator.py
from __future__ import annotations
from typing import List, Tuple, Optional, Callable, Dict, Any

from .runtime import MinimalRuntime, TraceEvent

def run_two_step_sequence(
    *,
    runtime: MinimalRuntime,
    agent_ids: Tuple[str, ...],
    deliver_fn: Callable[..., List[Tuple[str, str]]],
    initial_sender: Optional[str],
    initial_receiver: str,
    initial_message: str,
    max_steps: int = 200,
) -> Tuple[List[TraceEvent], List[TraceEvent]]:
    """
    Runs two sequential interactions to test for state leakage.

    1. Runs a first interaction.
    2. Derives a handoff payload from the *last event* of the first trace.
    3. Runs a second interaction using the payload as the new input.
    """
    # ---- Interaction 1 ----
    trace1 = runtime.run_interaction(
        agent_ids=agent_ids,
        deliver_fn=deliver_fn,
        initial_sender=initial_sender,
        initial_receiver=initial_receiver,
        initial_message=initial_message,
        max_steps=max_steps,
    )

    if not trace1:
        return trace1, []

    # ---- Handoff Derivation ----
    last_event = trace1[-1]
    handoff_payload = f"In response to '{last_event.message[:32]}', {last_event.receiver} considers their next action."
    next_sender = last_event.receiver # The last receiver acts next

    # For this simple test, the next receiver is the original sender, or the first agent if none.
    next_receiver = initial_sender if initial_sender is not None else agent_ids[0]


    # ---- Interaction 2 ----
    trace2 = runtime.run_interaction(
        agent_ids=agent_ids,
        deliver_fn=deliver_fn,
        initial_sender=next_sender,
        initial_receiver=next_receiver,
        initial_message=handoff_payload,
        max_steps=max_steps,
    )

    return trace1, trace2
