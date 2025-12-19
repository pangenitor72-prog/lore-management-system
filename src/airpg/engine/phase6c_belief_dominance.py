# This file exists solely as a Phase 6C validation artifact and is not part of
# the runtime engine.

"""Phase 6C — Belief Dominance (Validation Artifact)
PROOF GOAL:
Demonstrate that repeated application of the same belief pressure
causes deterministic stabilization (dominance) of belief outcomes,
WITHOUT memory, counters, decay, timestamps, or persistence.
Each run is stateless.
Only an injected belief category label differs between runs.
NO MEMORY
NO TIME
NO RANDOMNESS
NO NEW PRIMITIVES
"""
from typing import Dict, List, Optional
# ─────────────────────────────────────────────────────────────
# NPC PROFILE (STATIC)
# ─────────────────────────────────────────────────────────────
NPCS: Dict[str, Dict[str, float]] = {
    "X": {"O": 0.45, "C": 0.45, "E": 0.20, "A": 0.40, "N": 0.45},  # tie-prone
}
# ─────────────────────────────────────────────────────────────
# TOPOLOGY (ISOLATED)
# ─────────────────────────────────────────────────────────────
TOPOLOGY = {
    "Source1": ["X"],
    "Source2": ["X"],
    "X": [],
}
# ─────────────────────────────────────────────────────────────
# CLAIMS
# ─────────────────────────────────────────────────────────────
CLAIM_A = "The tower collapsed."
CLAIM_B = "The tower still stands."
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
# BELIEF DOMINANCE BIAS (PHASE 6C ONLY)
# ─────────────────────────────────────────────────────────────
BELIEF_DOMINANCE_BIAS = {
    "CONFLICTED BELIEF": "TRANSFORM",
    "TRANSFORMED BELIEF": "TRANSFORM", # The spec says TRANSFORMED BELIEF biases toward TRANSFORM
}
# ─────────────────────────────────────────────────────────────
# RUN-LOCAL STATE
# ─────────────────────────────────────────────────────────────
held_claims: Dict[str, List[str]] = {}
prior_belief_category: Optional[str] = None
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
# PROPAGATION (WITH DOMINANCE PRESSURE)
# ─────────────────────────────────────────────────────────────
def propagate(sender: str, claim: str):
    global held_claims
    if sender not in TOPOLOGY:
        return
    for receiver in TOPOLOGY[sender]: # No need to sort, only one receiver "X"
        if receiver not in held_claims:
            held_claims[receiver] = [claim]
            return

        for existing in held_claims[receiver][:]:
            if conflicts(existing, claim):
                trait = dominant_trait(NPCS[receiver])
                outcome = TRAIT_TO_OUTCOME[trait]
                
                # Apply belief dominance pressure if prior_belief_category exists
                if prior_belief_category in BELIEF_DOMINANCE_BIAS:
                    outcome = BELIEF_DOMINANCE_BIAS[prior_belief_category]
                
                if outcome == "RETAIN":
                    return
                if outcome == "REPLACE":
                    held_claims[receiver] = [claim]
                    return
                if outcome == "DUAL-HOLD":
                    if claim not in held_claims[receiver]:
                        held_claims[receiver].append(claim)
                    return
                if outcome == "TRANSFORM":
                    held_claims[receiver] = ["Reports uncertainty about the tower."]
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
        if "Reports uncertainty" in claims[0]: # Check for transformed claim
            return "TRANSFORMED BELIEF"
        return "SINGLE-HELD BELIEF"
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if (claims[i], claims[j]) in CONFLICT_PAIRS:
                return "CONFLICTED BELIEF"
    raise RuntimeError("Invalid belief state") # Should not be reached with current setup
# ─────────────────────────────────────────────────────────────
# VALIDATION RUN
# ─────────────────────────────────────────────────────────────
def run(label: str, prior: Optional[str]) -> str:
    global held_claims, prior_belief_category
    held_claims = {}
    prior_belief_category = prior

    propagate("Source1", CLAIM_A)
    propagate("Source2", CLAIM_B)
    
    final_claims = held_claims.get("X", [])
    belief = classify_belief(final_claims)
    
    print(f"\nRUN: {label}")
    print(f"Injected Prior Belief: {prior or 'NONE'}")
    print(f"Final Held Claims for X: {final_claims}")
    print(f"Derived Belief Category: {belief}")
    return belief
# ─────────────────────────────────────────────────────────────
# EXECUTION
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # The NPC 'X' is designed to have a baseline DUAL-HOLD outcome without pressure.
    # N (0.45) > C (0.45) > O (0.45) -> N is dominant.
    # N -> DUAL-HOLD
    
    belief_1 = run("BASELINE", None)
    belief_2 = run("PRESSURE REAPPLIED", belief_1)
    belief_3 = run("PRESSURE REAPPLIED AGAIN", belief_2)
