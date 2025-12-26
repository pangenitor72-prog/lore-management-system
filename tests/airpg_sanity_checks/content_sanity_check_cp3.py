# src/airpg/runtime/content_sanity_check_cp3.py
from __future__ import annotations
from typing import List, Tuple, Optional, Dict

from .runtime import MinimalRuntime
from .session_state import SessionState
from .session_loop import run_session_step

# ---- Test Data & Stubs ----
# Topology: Player -> A -> B -> C
AGENTS = ("Player", "A", "B", "C")
TOPOLOGY = {
    "Player": ["A"],
    "A": ["B"],
    "B": ["C"],
    "C": []
}

def deliver_fn(
    receiver: str, sender: Optional[str], message: str
) -> List[Tuple[str, str]]:
    """Minimal deterministic propagation function."""
    forwards = []
    for next_receiver in TOPOLOGY.get(receiver, []):
        forwards.append((next_receiver, message))
    return forwards

# ---- Test-Local Parsing Logic (Reused from CP-2) ----
def build_contradictory_message(atoms: List[Dict[str, str]]) -> str:
    """Encodes a list of atoms into a single string."""
    return "\n".join([f"ATOM|topic={a['topic']}|value={a['value']}" for a in atoms])

def parse_message_atoms(message: str) -> List[Dict[str, str]]:
    """Parses a string back into atoms for verification."""
    atoms = []
    for line in message.splitlines():
        if line.startswith("ATOM|"):
            parts = line.split("|")
            atom = {}
            for part in parts[1:]:
                key, value = part.split("=", 1)
                atom[key] = value
            atoms.append(atom)
    return atoms

# ---- Main Test ----
def main():
    print("--- Running Content Pressure Sanity Check (CP-3) ---")

    runtime = MinimalRuntime()
    initial_state = SessionState(turn_index=0)

    # Define two contradictory atoms
    contradictory_atoms = [
        {"topic": "status", "value": "A"},
        {"topic": "status", "value": "B"},
    ]
    
    # Encode them into a single message string
    initial_message = build_contradictory_message(contradictory_atoms)

    # ---- Run Interaction ----
    _, trace = run_session_step(
        state=initial_state,
        player_input=initial_message,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )

    # ---- Assertions ----
    assert trace, "Trace should not be empty"

    # We expect 4 events:
    # 0: Player -> Player (initial injection in session loop)
    # 1: Player -> A
    # 2: A -> B
    # 3: B -> C
    
    # Check trace length first
    expected_steps = 4
    assert len(trace) == expected_steps, f"Expected {expected_steps} steps, got {len(trace)}"

    # 1. Assert full string propagation at every hop
    # Skip step 0 (injection), check propagation steps 1, 2, 3
    propagation_events = trace[1:]
    path = ["A", "B", "C"]
    
    for i, event in enumerate(propagation_events):
        expected_receiver = path[i]
        assert event.receiver == expected_receiver, f"Step {i+1}: Expected receiver {expected_receiver}, got {event.receiver}"
        
        # A receives, B receives, C receives - all must have the FULL message
        assert event.message == initial_message, f"Step {i+1}: Message corrupted at {event.receiver}"
        
        # Verify atoms are intact
        parsed_atoms = parse_message_atoms(event.message)
        assert len(parsed_atoms) == 2, f"Step {i+1}: Atom count mismatch at {event.receiver}"
        assert parsed_atoms[0]["value"] == "A", f"Step {i+1}: Atom 1 value mismatch at {event.receiver}"
        assert parsed_atoms[1]["value"] == "B", f"Step {i+1}: Atom 2 value mismatch at {event.receiver}"
        
        # Verify no resolution semantics
        assert "resolved" not in event.message.lower(), f"Step {i+1}: Resolution detected at {event.receiver}"

    print("\n[ASSERTION PASSED]: Contradiction propagated unchanged A -> B -> C.")
    print("[ASSERTION PASSED]: Ordering preserved at all hops.")
    print("[ASSERTION PASSED]: No resolution occurred.")

    # 4. Re-run to ensure determinism
    _, trace2 = run_session_step(
        state=initial_state,
        player_input=initial_message,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )
    assert trace == trace2, "Determinism violated on second run."
    print("[ASSERTION PASSED]: Re-running with same input yields identical trace.")

    print("\n--- VERIFICATION COMPLETE ---")
    print("CP-3: Distributed contradiction stability confirmed.")


if __name__ == "__main__":
    main()
