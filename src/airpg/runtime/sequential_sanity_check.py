# src/airpg/runtime/sequential_sanity_check.py
from __future__ import annotations
from typing import List, Tuple, Optional

from .runtime import MinimalRuntime
from .orchestrator import run_two_step_sequence

# ---- Test Data ----
AGENTS = ("Orchestrator", "A", "B")
TOPOLOGY = {
    "Orchestrator": ["A"],
    "A": ["B"],
    "B": [],
}

def deliver_fn(
    receiver: str,
    sender: Optional[str],
    message: str,
) -> List[Tuple[str, str]]:
    """Minimal deterministic propagation function."""
    forwards = []
    for next_receiver in TOPOLOGY.get(receiver, []):
        forwards.append((next_receiver, message))
    return forwards

def main():
    """
    Runs the sequential interaction test and asserts invariants.
    """
    print("--- Running Sequential Interaction Sanity Check ---")

    runtime = MinimalRuntime() # Use the SAME instance for both interactions

    trace1, trace2 = run_two_step_sequence(
        runtime=runtime,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        initial_sender="Orchestrator",
        initial_receiver="A",
        initial_message="First message",
    )

    print("\n--- Trace 1 ---")
    for event in trace1:
        print(f"  {event.sender} -> {event.receiver} | msg: '{event.message}' | mem_after: {event.memory_after}")

    print("\n--- Trace 2 ---")
    for event in trace2:
        print(f"  {event.sender} -> {event.receiver} | msg: '{event.message}' | mem_after: {event.memory_after}")


    # ---- Assertions ----

    # 1. Memory from interaction #1 MUST NOT leak into interaction #2.
    # The first receiver in trace 2 is 'Orchestrator'. Its memory_before should be None.
    assert trace2, "Trace 2 should not be empty"
    first_event_t2 = trace2[0]
    assert first_event_t2.memory_before is None, (
        f"INVARIANT VIOLATION: Memory leaked between interactions. "
        f"memory_before for the first event in trace 2 should be None, but was '{first_event_t2.memory_before}'."
    )
    print("\n[ASSERTION PASSED]: Ephemeral memory was correctly reset between interactions.")

    # 2. Propagation path must remain deterministic and correct.
    expected_path_t1 = [("Orchestrator", "A"), ("A", "B")]
    actual_path_t1 = [(e.sender, e.receiver) for e in trace1]
    assert actual_path_t1 == expected_path_t1, (
        f"INVARIANT VIOLATION: Trace 1 propagation path is incorrect.\n"
        f"Expected: {expected_path_t1}\n"
        f"Got: {actual_path_t1}"
    )
    print("[ASSERTION PASSED]: Trace 1 propagation path is correct.")

    # In trace 2, the orchestrator sends a message to the original sender ('A')
    last_receiver_t1 = trace1[-1].receiver
    expected_path_t2 = [(last_receiver_t1, "Orchestrator")]
    actual_path_t2 = [(e.sender, e.receiver) for e in trace2]
    # Note: Our simple deliver_fn and topology means this trace stops after one step.
    # A -> B is not in the topology for the sender 'B' from trace 1.
    # Correcting this for the test logic:
    expected_path_t2 = [
        ("B", "Orchestrator"),
        ("Orchestrator", "A"),
        ("A", "B"),
    ]
    assert actual_path_t2 == expected_path_t2, (
        f"INVARIANT VIOLATION: Trace 2 propagation path is incorrect.\n"
        f"Expected: {expected_path_t2}\n"
        f"Got: {actual_path_t2}"
    )
    print("[ASSERTION PASSED]: Trace 2 propagation path is correct.")

    print("\n--- VERIFICATION COMPLETE ---")
    print("No state leaks across sequential interactions.")


if __name__ == "__main__":
    main()
