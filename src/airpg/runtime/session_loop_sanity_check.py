# src/airpg/runtime/session_loop_sanity_check.py
from __future__ import annotations
from typing import List, Tuple, Optional

from .runtime import MinimalRuntime
from .session_state import SessionState
from .session_loop import run_session_step

# ---- Test Data ----
AGENTS = ("Player", "A", "B")
TOPOLOGY = {"Player": ["A"], "A": ["B"], "B": []}

def deliver_fn(
    receiver: str, sender: Optional[str], message: str
) -> List[Tuple[str, str]]:
    """Minimal deterministic propagation function."""
    forwards = []
    for next_receiver in TOPOLOGY.get(receiver, []):
        forwards.append((next_receiver, message))
    return forwards

def main():
    """
    Runs the session loop test and asserts invariants.
    """
    print("--- Running Session Loop Sanity Check ---")

    runtime = MinimalRuntime()
    
    # ---- Step 1: Initial State ----
    state1 = SessionState(turn_index=0)
    
    print("\n[STEP 1: Running first interaction]")
    state2, trace1 = run_session_step(
        state=state1,
        player_input="Hello world",
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )

    # ---- Step 2: Second interaction using state from first ----
    print("[STEP 2: Running second interaction]")
    state3, trace2 = run_session_step(
        state=state2,
        player_input="Follow-up message",
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )

    # ---- Assertions ----
    
    # 1. Turn index increments correctly
    assert state1.turn_index == 0
    assert state2.turn_index == 1
    assert state3.turn_index == 2
    print("\n[ASSERTION PASSED]: turn_index increments correctly.")

    # 2. SessionState correctly stores explicit player input
    assert state2.last_player_message == "Hello world"
    assert state3.last_player_message == "Follow-up message"
    print("[ASSERTION PASSED]: last_player_message is stored correctly.")

    # 3. No memory from interaction 1 appears in interaction 2
    # The first receiver in trace2 is 'A'. Its memory should be reset.
    first_event_t2 = trace2[0]
    assert first_event_t2.memory_before is None, (
        f"INVARIANT VIOLATION: Memory leaked. "
        f"memory_before for first event in trace 2 should be None, but was '{first_event_t2.memory_before}'."
    )
    print("[ASSERTION PASSED]: Ephemeral memory does not persist between session steps.")
    
    # 4. Running with a fresh state yields identical behavior
    print("\n[STEP 3: Running a fresh interaction to test determinism]")
    fresh_state = SessionState(turn_index=0)
    _, fresh_trace = run_session_step(
        state=fresh_state,
        player_input="Hello world",
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )
    
    trace1_messages = [(e.sender, e.receiver, e.message) for e in trace1]
    fresh_trace_messages = [(e.sender, e.receiver, e.message) for e in fresh_trace]

    assert trace1_messages == fresh_trace_messages, (
        "INVARIANT VIOLATION: Identical inputs produced different traces."
    )
    print("[ASSERTION PASSED]: Re-running with fresh state yields identical trace.")


    print("\n--- VERIFICATION COMPLETE ---")
    print("Session loop manages state explicitly without hidden memory.")


if __name__ == "__main__":
    main()
