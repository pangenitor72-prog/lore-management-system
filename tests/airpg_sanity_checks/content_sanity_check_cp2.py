# src/airpg/runtime/content_sanity_check_cp2.py
from __future__ import annotations
from typing import List, Tuple, Optional, Dict

from .runtime import MinimalRuntime
from .session_state import SessionState
from .session_loop import run_session_step

# ---- Test Data & Stubs ----
AGENTS = ("Player", "A")
TOPOLOGY = {"Player": ["A"], "A": []}

def deliver_fn(
    receiver: str, sender: Optional[str], message: str
) -> List[Tuple[str, str]]:
    """Minimal deterministic propagation function."""
    forwards = []
    for next_receiver in TOPOLOGY.get(receiver, []):
        forwards.append((next_receiver, message))
    return forwards

# ---- Test-Local Parsing Logic (NOT for runtime use) ----
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
    print("--- Running Content Pressure Sanity Check (CP-2) ---")

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

    # 1. Assert that the full, unchanged string was delivered to the next agent
    delivered_message = trace[1].message
    assert delivered_message == initial_message
    print("\n[ASSERTION PASSED]: Composite string was delivered verbatim.")

    # 2. Parse the delivered message and assert both atoms are present
    parsed_atoms = parse_message_atoms(delivered_message)
    assert len(parsed_atoms) == 2, "Both contradictory atoms should be present."
    assert parsed_atoms[0]["value"] == "A"
    assert parsed_atoms[1]["value"] == "B"
    print("[ASSERTION PASSED]: Both contradictory atoms were preserved in order.")

    # 3. Assert no resolution semantics have been added
    assert "resolved" not in delivered_message.lower()
    assert "winner" not in delivered_message.lower()
    assert "final" not in delivered_message.lower()
    print("[ASSERTION PASSED]: No resolution semantics were introduced by the runtime.")

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
    print("CP-2: Contradictory content is handled as opaque, deterministic pressure.")


if __name__ == "__main__":
    main()