# src/airpg/engine/phase5a1_belief_view.py
"""Phase 5A-1 — Belief as a Derived View (Validation Artifact)
PROOF GOAL:
Demonstrate that belief can be represented descriptively
as a pure view over Phase 5B outputs, without introducing
memory, persistence, state, or behavioral influence.
READ-ONLY
NO MEMORY
NO TIME
NO RANDOMNESS
NO FACTIONS
NO PERSISTENCE
"""
from typing import Dict, List

# ─────────────────────────────────────────────────────────────
# INPUT: FINAL OUTPUT FROM PHASE 5B (COPIED, NOT GENERATED)
# ─────────────────────────────────────────────────────────────
FINAL_HELD_CLAIMS: Dict[str, List[str]] = {
    # Original Scenario
    "A": ["The duke is dead."],
    "B": ["The duke is alive."],
    "C": ["The duke is dead.", "The duke is alive."],
    "D": ["The duke is dead.", "The duke is alive."],
    # Scenario 2: RETAIN
    "R": ["The duke is dead."],
    # Scenario 3: TRANSFORM
    "T": ["Reports conflict about the duke."],
    # Scenario 4: REPLACE
    "P": ["The duke is alive."],
}
# Explicit conflict pairs (must match Phase 5B)
CONFLICT_PAIRS = {
    ("The duke is dead.", "The duke is alive."),
    ("The duke is alive.", "The duke is dead."),
}

# ─────────────────────────────────────────────────────────────
# BELIEF CLASSIFICATION (DERIVED VIEW ONLY)
# ─────────────────────────────────────────────────────────────
def classify_belief(claims: List[str]) -> str:
    if not claims:
        return "NO BELIEF"
        
    if len(claims) == 1:
        if "conflict" in claims[0]:
            return "TRANSFORMED BELIEF"
        else:
            return "SINGLE-HELD BELIEF"

    # Check for explicit conflict if len > 1
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if (claims[i], claims[j]) in CONFLICT_PAIRS:
                return "CONFLICTED BELIEF"
    
    # Fallback for any other multi-claim non-conflicting case,
    # which shouldn't happen in this validation but is safe to have.
    # Per spec, this category is removed from primary logic.
    raise RuntimeError("Invalid belief state: non-conflicting multi-claim")

# ─────────────────────────────────────────────────────────────
# VALIDATION RUN
# ─────────────────────────────────────────────────────────────
def run():
    print("=== PHASE 5A-1 VALIDATION RUN (TIGHTENED) ===\n")
    print("Belief View (Derived, Non-Persistent):\n")
    for npc in sorted(FINAL_HELD_CLAIMS.keys()):
        claims = FINAL_HELD_CLAIMS[npc]
        belief_type = classify_belief(claims)
        print(f"NPC {npc}")
        print(f"  Belief Category: {belief_type}")
        print(f"  Derived From Claims:")
        for c in claims:
            print(f"    - {c}")
        print()
    print("=== VALIDATION NOTES ===")
    print("- Belief categories are computed after run termination.")
    print("- No belief data is stored or reused.")
    print("- Removing this file does not affect Phases 0–5B.")
    print("- Identical inputs will always produce identical belief views.")

if __name__ == "__main__":
    run()