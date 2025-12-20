# This file exists solely as a Phase 6D validation artifact
# and is not part of the runtime engine.
"""Phase 6D — Source Credibility Pressure (Validation Artifact)
PROOF GOAL:
Demonstrate that the identity of a source node can deterministically
bias belief outcomes during conflict resolution WITHOUT introducing:
- trust scores
- credibility weights
- authority flags
- memory
- time
- randomness
- new primitives
Source credibility must emerge ONLY from:
(source personality) × (receiver personality) × (existing rules)
NO MEMORY
NO TIME
NO RANDOMNESS
NO NEW PRIMITIVES
"""
from typing import Dict, List

# ─────────────────────────────────────────────────────────────
# NPC PROFILES (STATIC)
# ─────────────────────────────────────────────────────────────
NPCS: Dict[str, Dict[str, float]] = {
    # Receiver (tie-prone)
    "X": {"O": 0.45, "C": 0.45, "E": 0.20, "A": 0.40, "N": 0.45},
    # Source 1 — methodical / careful
    "S1": {"O": 0.20, "C": 0.90, "E": 0.20, "A": 0.30, "N": 0.20},
    # Source 2 — exploratory / interpretive
    "S2": {"O": 0.90, "C": 0.20, "E": 0.20, "A": 0.30, "N": 0.20},
}
# ─────────────────────────────────────────────────────────────
# TOPOLOGY (SOURCES ARE JUST NODES)
# ─────────────────────────────────────────────────────────────
TOPOLOGY = {
    "S1": ["X"],
    "S2": ["X"],
    "X": [],
}
# ─────────────────────────────────────────────────────────────
# CLAIMS
# ─────────────────────────────────────────────────────────────
CLAIM_A = "The vault was sealed."
CLAIM_B = "The vault remains open."
CONFLICT_PAIRS = {
    (CLAIM_A, CLAIM_B),
    (CLAIM_B, CLAIM_A),
}
# ─────────────────────────────────────────────────────────────
# PERSONALITY → OUTCOME (UNCHANGED)
# ─────────────────────────────────────────────────────────────
TRAIT_TO_OUTCOME = {
    "N": "DUAL-HOLD",
    "C": "RETAIN",
    "O": "TRANSFORM",
    "A": "REPLACE",
    "E": "REPLACE",
}
TIE_BREAK_ORDER = ["N", "C", "O", "A", "E"]
# ─────────────────────────────────────────────────────────────
# RUN-LOCAL STATE
# ─────────────────────────────────────────────────────────────
held_claims: Dict[str, List[str]] = {}
# ─────────────────────────────────────────────────────────────
# INLINE UTILITIES
# ─────────────────────────────────────────────────────────────
def dominant_trait(profile: Dict[str, float]) -> str:
    max_val = max(profile.values())
    tied = [t for t, v in profile.items() if v == max_val]
    for t in TIE_BREAK_ORDER:
        if t in tied:
            return t
    return tied[0]

def conflicts(a: str, b: str) -> bool:
    return (a, b) in CONFLICT_PAIRS
# ─────────────────────────────────────────────────────────────
# PROPAGATION (UNCHANGED RULES)
# ─────────────────────────────────────────────────────────────
def propagate(sender: str, claim: str):
    global held_claims
    if sender not in TOPOLOGY:
        return
    for receiver in TOPOLOGY[sender]: # Only "X" will be receiver here
        if receiver not in held_claims:
            held_claims[receiver] = [claim]
            return

        for existing_claim in held_claims[receiver][:]:
            if conflicts(existing_claim, claim):
                receiver_dominant = dominant_trait(NPCS[receiver])
                outcome = TRAIT_TO_OUTCOME[receiver_dominant]

                if outcome == "RETAIN":
                    return # Retains prior claim, propagation halts for this branch
                if outcome == "REPLACE":
                    held_claims[receiver] = [claim]
                    return
                if outcome == "DUAL-HOLD":
                    if claim not in held_claims[receiver]:
                        held_claims[receiver].append(claim)
                    return
                if outcome == "TRANSFORM":
                    held_claims[receiver] = ["Reports uncertainty about the vault."]
                    return

        if claim not in held_claims[receiver]:
            held_claims[receiver].append(claim)
# ─────────────────────────────────────────────────────────────
# BELIEF CLASSIFICATION (READ-ONLY)
# ─────────────────────────────────────────────────────────────
def classify_belief(claims: List[str]) -> str:
    if not claims:
        return "NO BELIEF"
    if len(claims) == 1:
        if "Reports uncertainty" in claims[0]:
            return "TRANSFORMED BELIEF"
        return "SINGLE-HELD BELIEF"
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if (claims[i], claims[j]) in CONFLICT_PAIRS:
                return "CONFLICTED BELIEF"
    raise RuntimeError("Invalid belief state")
# ─────────────────────────────────────────────────────────────
# VALIDATION RUN
# ─────────────────────────────────────────────────────────────
def run(label: str, first_source: str, second_source: str):
    global held_claims
    held_claims = {}

    # Reset held_claims and propagate
    propagate(first_source, CLAIM_A) # Source of first claim
    propagate(second_source, CLAIM_B) # Source of second (conflicting) claim

    final_claims = held_claims.get("X", [])
    belief = classify_belief(final_claims)
    
    print(f"\nRUN: {label}")
    print(f"Receiver X Personality: {NPCS['X']}")
    print(f"Source 1 Personality ({first_source}): {NPCS[first_source]}")
    print(f"Source 2 Personality ({second_source}): {NPCS[second_source]}")
    print(f"Final Held Claims for X: {final_claims}")
    print(f"Derived Belief Category: {belief}")
# ─────────────────────────────────────────────────────────────
# EXECUTION
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Injected order determines which claim is "existing" and which is "incoming"
    # S1 (C-dominant) sends A, then S2 (O-dominant) sends B
    run("S1 THEN S2 (C-dom first, O-dom second)", "S1", "S2") 
    
    # S2 (O-dominant) sends A, then S1 (C-dominant) sends B
    run("S2 THEN S1 (O-dom first, C-dom second)", "S2", "S1")
