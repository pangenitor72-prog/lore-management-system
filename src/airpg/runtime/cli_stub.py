# -------------------------------------------------------------------
# AIRPG RUNTIME PROBE (NON-CANONICAL)
#
# This file exists solely to allow a human to experience a single,
# deterministic AIRPG interaction at runtime.
#
# It is NOT:
# - a game
# - a simulation
# - a campaign system
# - an example of intended runtime architecture
#
# Constraints:
# - One interaction only
# - No persistence
# - No memory-informed decisions
# - No branching logic
#
# Any change that alters propagation, recipients, or message content
# relative to the proven engine is INVALID.
# -------------------------------------------------------------------
# src/airpg/runtime/cli_stub.py
from __future__ import annotations
import sys
from typing import List, Tuple, Optional

from .runtime import MinimalRuntime

# ---- TEMP TEST DATA (explicit, visible, disposable) ----
AGENTS = ("Player", "A", "B", "C")
TOPOLOGY = {
    "Player": ["A"],
    "A": ["B"],
    "B": ["C"],
    "C": [],
}

def deliver_fn(
    receiver: str,
    sender: Optional[str],
    message: str,
) -> List[Tuple[str, str]]:
    """
    Minimal deterministic propagation function.
    This intentionally ignores memory.
    """
    forwards = []
    for next_receiver in TOPOLOGY.get(receiver, []):
        forwards.append((next_receiver, message))
    return forwards

# ---- CLI ENTRY POINT ----
def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m src.airpg.runtime.cli_stub \"<player message>\"")
        sys.exit(1)

    player_message = sys.argv[1]

    runtime = MinimalRuntime()
    trace = runtime.run_interaction(
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        initial_receiver="Player",
        initial_sender=None,
        initial_message=player_message,
    )

    print("\n--- AIRPG Minimal Runtime Trace ---\n")
    for event in trace:
        print(f"[step {event.step}]")
        print(f"  sender        : {event.sender}")
        print(f"  receiver      : {event.receiver}")
        print(f"  message       : {event.message}")
        print(f"  memory_before : {event.memory_before}")
        print(f"  memory_after  : {event.memory_after}")
        print()
    print("--- End Interaction ---")

if __name__ == "__main__":
    main()
