# src/airpg/runtime/content_sanity_check_cp4.py
from __future__ import annotations
from typing import List, Tuple, Optional, Dict

from .runtime import MinimalRuntime
from .session_state import SessionState
from .session_loop import run_session_step

# ---- Test Data & Stubs ----
# Topology: Player -> A -> B -> D
#                   -> C -> D (Blocked)
AGENTS = ("Player", "A", "B", "C", "D")
TOPOLOGY = {
    "Player": ["A"],
    "A": ["B", "C"],
    "B": ["D"],
    "C": ["D"],
    "D": []
}

# Define halting behavior for Agent C
# In a real run, this would be derived from personality.
# Here, we hardcode it in the delivery function for the proof.
HALTING_AGENTS = {"C"}

def deliver_fn(
    receiver: str, sender: Optional[str], message: str
) -> List[Tuple[str, str]]:
    """Minimal deterministic propagation function with halting support."""
    
    # Simulate personality-based halting
    if receiver in HALTING_AGENTS:
        return [] # Halt propagation
        
    forwards = []
    for next_receiver in TOPOLOGY.get(receiver, []):
        forwards.append((next_receiver, message))
    
    # Sort for deterministic ordering (B before C or vice versa doesn't matter for the set,
    # but matters for the list trace)
    forwards.sort(key=lambda x: x[0])
    return forwards

# ---- Test-Local Parsing Logic (Reused from CP-2/3) ----
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
    print("--- Running Content Pressure Sanity Check (CP-4) ---")

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

    # Trace expectations:
    # 0: Player -> Player (Injection)
    # 1: Player -> A
    # 2: A -> B
    # 3: A -> C
    # 4: B -> D
    # C -> D should NOT happen.
    
    # Because A->B and A->C happen at the same step, the order in trace depends on 
    # how MinimalRuntime processes the queue. MinimalRuntime uses a FIFO queue.
    # deliver_fn returns forwards sorted alphabetically: B, then C.
    # So A's output puts B and C into the queue.
    # Then B is processed (outputting D).
    # Then C is processed (outputting nothing).
    # Then D is processed (outputting nothing).
    
    # Expected Event Order (Step-based grouping):
    # Step 0: Player -> Player
    # Step 1: Player -> A
    # Step 2: A -> B, A -> C
    # Step 3: B -> D (from A->B processing)
    # Step 4: (C processed, halts) -> No output events for C->?
    
    # Let's verify the trace events.
    
    # Helper to find events by receiver
    def get_events_for(receiver: str) -> List:
        return [e for e in trace if e.receiver == receiver]

    # 1. Verify A received it
    events_A = get_events_for("A")
    assert len(events_A) == 1
    assert events_A[0].message == initial_message
    
    # 2. Verify B and C received it
    events_B = get_events_for("B")
    events_C = get_events_for("C")
    assert len(events_B) == 1
    assert len(events_C) == 1
    assert events_B[0].message == initial_message
    assert events_C[0].message == initial_message
    
    # 3. Verify D received it ONLY from B
    events_D = get_events_for("D")
    assert len(events_D) == 1, f"D should receive exactly once, got {len(events_D)}"
    assert events_D[0].sender == "B", f"D should receive from B, got {events_D[0].sender}"
    assert events_D[0].message == initial_message
    print("\n[ASSERTION PASSED]: D received message only via B (C halted).")

    # 4. Verify Content Integrity at D
    parsed_atoms = parse_message_atoms(events_D[0].message)
    assert len(parsed_atoms) == 2
    assert parsed_atoms[0]["value"] == "A"
    assert parsed_atoms[1]["value"] == "B"
    print("[ASSERTION PASSED]: D received full contradictory payload unchanged.")

    # 5. Verify No Fallback / Resolution
    # Ensure no other events exist for D
    # Ensure C did not send anything
    events_from_C = [e for e in trace if e.sender == "C"]
    assert len(events_from_C) == 0, "C should not have sent any messages."
    print("[ASSERTION PASSED]: C did not forward (Halting logic respected).")

    # 6. Re-run to ensure determinism
    _, trace2 = run_session_step(
        state=initial_state,
        player_input=initial_message,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )
    # We compare the relevant attributes of the trace events to ensure identity
    trace1_dump = [(e.sender, e.receiver, e.message) for e in trace]
    trace2_dump = [(e.sender, e.receiver, e.message) for e in trace2]
    assert trace1_dump == trace2_dump, "Determinism violated on second run."
    print("[ASSERTION PASSED]: Re-running with same input yields identical trace.")

    print("\n--- VERIFICATION COMPLETE ---")
    print("CP-4: Topological divergence and halting confirmed.")


if __name__ == "__main__":
    main()
