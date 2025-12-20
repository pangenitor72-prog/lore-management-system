# src/airpg/runtime/sanity_check.py
"""
MANDATORY SANITY CHECK

Verifies that the MinimalRuntime wrapper does not alter or corrupt the
underlying deterministic output of a proven phase's logic.

It runs a simulation in two ways:
1. "Bare": A manual simulation loop using a stateful delivery function.
2. "Runtime": Using the MinimalRuntime to wrap the same delivery function.

The propagation traces of both runs MUST be identical.
"""
from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Callable

from .runtime import MinimalRuntime
from .invariants import assert_equivalent_propagation

# --- Test Data & Logic adapted from phase5b_conflict_resolution.py ---

NPCS: Dict[str, Dict[str, float]] = {
    "A": {"O": 0.80, "C": 0.40, "E": 0.50, "A": 0.50, "N": 0.20},
    "B": {"O": 0.20, "C": 0.85, "E": 0.40, "A": 0.30, "N": 0.25},
    "C": {"O": 0.35, "C": 0.40, "E": 0.30, "A": 0.55, "N": 0.75},
    "D": {"O": 0.50, "C": 0.50, "E": 0.50, "A": 0.50, "N": 0.50},
}
TOPOLOGY: Dict[str, List[str]] = {
    "Source1": ["A"], "Source2": ["B"], "A": ["C"], "B": ["C"], "C": ["D"], "D": [],
}
CLAIM_X = "The duke is dead."
CLAIM_Y = "The duke is alive."
CONFLICT_PAIRS: List[Tuple[str, str]] = [(CLAIM_X, CLAIM_Y), (CLAIM_Y, CLAIM_X)]
TRAIT_TO_OUTCOME = {
    "N": "DUAL-HOLD", "C": "RETAIN", "O": "TRANSFORM", "A": "REPLACE", "E": "REPLACE",
}
TIE_BREAK_ORDER = ["N", "C", "O", "A", "E"]

def dominant_trait(profile: Dict[str, float]) -> str:
    max_value = max(profile.values())
    tied = [t for t, v in profile.items() if v == max_value]
    for t in TIE_BREAK_ORDER:
        if t in tied:
            return t
    return tied[0]

def conflicts(existing: str, incoming: str) -> bool:
    return (existing, incoming) in CONFLICT_PAIRS

class StatefulPhase5Logic:
    """Encapsulates the stateful logic from Phase 5B for testing."""
    def __init__(self):
        self.held_claims: Dict[str, List[str]] = {}

    def reset(self):
        self.held_claims = {}

    def deliver(
        self,
        receiver: str,
        sender: Optional[str],
        message: str
    ) -> List[Tuple[str, str]]:
        """
        A pure-python implementation of the Phase 5B propagation and
        conflict resolution logic. It uses instance state `self.held_claims`
        to track claims within a single interaction.
        """
        forwards = []

        if receiver not in self.held_claims:
            self.held_claims[receiver] = [message]
            for next_receiver in sorted(TOPOLOGY.get(receiver, [])):
                forwards.append((next_receiver, message))
            return forwards

        existing_claims = self.held_claims[receiver][:]
        is_conflicting = False
        for existing in existing_claims:
            if conflicts(existing, message):
                is_conflicting = True
                trait = dominant_trait(NPCS[receiver])
                outcome = TRAIT_TO_OUTCOME[trait]

                if outcome == "RETAIN":
                    break
                if outcome == "REPLACE":
                    self.held_claims[receiver] = [message]
                    for next_receiver in sorted(TOPOLOGY.get(receiver, [])):
                        forwards.append((next_receiver, message))
                    break
                if outcome == "DUAL-HOLD":
                    if message not in self.held_claims[receiver]:
                        self.held_claims[receiver].append(message)
                    for claim in self.held_claims[receiver]:
                        for next_receiver in sorted(TOPOLOGY.get(receiver, [])):
                            forwards.append((next_receiver, claim))
                    break
                if outcome == "TRANSFORM":
                    transformed = "Reports conflict about the duke."
                    self.held_claims[receiver] = [transformed]
                    for next_receiver in sorted(TOPOLOGY.get(receiver, [])):
                        forwards.append((next_receiver, transformed))
                    break

        if not is_conflicting:
            if message not in self.held_claims[receiver]:
                self.held_claims[receiver].append(message)
                for next_receiver in sorted(TOPOLOGY.get(receiver, [])):
                    forwards.append((next_receiver, message))

        return forwards

if __name__ == "__main__":
    print("--- Running Structural Invariant Sanity Check ---")

    agents = ("A", "B", "C", "D", "Source1", "Source2")
    
    # Test 1: First half of the conflict
    injection1 = [("Source1", "A", CLAIM_X)]
    logic1 = StatefulPhase5Logic()
    
    print("\n[TEST 1: Enforcing invariant for injection 'Source1 -> A']")
    assert_equivalent_propagation(
        agent_ids=agents,
        deliver_fn=logic1.deliver,
        initial_sender=injection1[0][0],
        initial_receiver=injection1[0][1],
        initial_message=injection1[0][2],
    )
    print("  ✅ SUCCESS: Invariant holds.")
    
    # Test 2: Second half of the conflict (on a fresh state)
    injection2 = [("Source2", "B", CLAIM_Y)]
    logic2 = StatefulPhase5Logic()

    print("\n[TEST 2: Enforcing invariant for injection 'Source2 -> B']")
    assert_equivalent_propagation(
        agent_ids=agents,
        deliver_fn=logic2.deliver,
        initial_sender=injection2[0][0],
        initial_receiver=injection2[0][1],
        initial_message=injection2[0][2],
    )
    print("  ✅ SUCCESS: Invariant holds.")

    print("\n--- VERIFICATION COMPLETE ---")
    print("Structural invariant for MinimalRuntime is enforced and holds.")
