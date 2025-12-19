"""Phase 6A — Belief Persistence as Pressure (Validation Artifact)
PROOF GOAL:
Demonstrate that prior belief *category* can exert deterministic pressure
on future conflict resolution WITHOUT introducing:
- authority
- global memory
- time
- randomness
- new primitives
- personality override
Belief pressure may bias outcomes only when personality dominance allows it.
NO MEMORY (claims not stored)
LOCAL BELIEF CATEGORY ONLY
NO TIME
NO RANDOMNESS
NO PLAYER PRIVILEGE
"""
from typing import Dict, List, Optional
# ─────────────────────────────────────────────────────────────
# NPC PROFILES (STATIC, UNCHANGED)
# ─────────────────────────────────────────────────────────────
NPCS: Dict[str, Dict[str, float]] = {
    "X": {"O": 0.45, "C": 0.45, "E": 0.20, "A": 0.40, "N": 0.45},  # tie-prone
}
# ─────────────────────────────────────────────────────────────
# TOPOLOGY (SINGLE NODE FOR ISOLATION)
# ─────────────────────────────────────────────────────────────
TOPOLOGY = {
    "Source1": ["X"],
    "Source2": ["X"],
    "X": [],
}
# ─────────────────────────────────────────────────────────────
# CLAIMS
# ─────────────────────────────────────────────────────────────
CLAIM_A = "The gate was sealed."
CLAIM_B = "The gate remains open."
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
# BELIEF PRESSURE RULE (PHASE 6A ONLY)
# ─────────────────────────────────────────────────────────────
BELIEF_PRESSURE_BIAS = {
    "CONFLICTED BELIEF": "TRANSFORM",
    "TRANSFORMED BELIEF": "RETAIN",
}
# ─────────────────────────────────────────────────────────────
# RUN-LOCAL STATE (CLEARED BETWEEN RUNS)
# ─────────────────────────────────────────────────────────────
held_claims: Dict[str, List[str]] = {}
prior_belief_category: Optional[str] = None
# ─────────────────────────────────────────────────────────────
# INLINE UTILITIES (NO HELPERS, NO EXTENSIONS)
# ─────────────────────────────────────────────────────────────
def dominant_trait(profile: Dict[str, float]) -> str:
    max_val = max(profile.values())
    tied = [t for t, v in profile.items() if v == max_val]
    for t in TIE_BREAK_ORDER:
        if t in tied:
            return t
    return tied[0]

def conflicts(existing: str, incoming: str) -> bool:
    return (existing, incoming) in CONFLICT_PAIRS
# ─────────────────────────────────────────────────────────────
# PROPAGATION WITH BELIEF PRESSURE
# ─────────────────────────────────────────────────────────────
def propagate(sender: str, claim: str):
    global held_claims # Declare intent to modify global state
    if sender not in TOPOLOGY:
        return
    for receiver in sorted(TOPOLOGY[sender]):
        if receiver not in held_claims:
            held_claims[receiver] = [claim]
            return
        for existing in held_claims[receiver][:]:
            if conflicts(existing, claim):
                trait = dominant_trait(NPCS[receiver])
                outcome = TRAIT_TO_OUTCOME[trait]
                # Apply belief pressure ONLY if personality is tie-eligible
                # and prior belief category matches a pressure rule
                if trait in ["N", "C", "O", "A", "E"] and prior_belief_category in BELIEF_PRESSURE_BIAS:
                    outcome = BELIEF_PRESSURE_BIAS[prior_belief_category]
                
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
                    held_claims[receiver] = ["Reports conflict about the gate."]
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
        if "Reports conflict" in claims[0]: # Check for transformed claim
            return "TRANSFORMED BELIEF"
        return "SINGLE-HELD BELIEF"
    # If multiple claims, check for explicit conflict
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if (claims[i], claims[j]) in CONFLICT_PAIRS:
                return "CONFLICTED BELIEF"
    # Should not reach here in a well-defined system based on current specs
    raise RuntimeError("Invalid belief state: unhandled multi-claim scenario without explicit conflict.")
# ─────────────────────────────────────────────────────────────
# VALIDATION RUN
# ─────────────────────────────────────────────────────────────
def run(label: str, prior: Optional[str]):
    global held_claims, prior_belief_category
    held_claims = {}
    prior_belief_category = prior
    print(f"\n=== PHASE 6A RUN: {label} ===")
    if prior:
        print(f"Prior Belief Pressure: {prior}")
    else:
        print("Prior Belief Pressure: NONE")
    
    # Propagate CLAIMS, not just claim_A then claim_B
    propagate("Source1", CLAIM_A)
    propagate("Source2", CLAIM_B)
    
    final_belief_for_X = "NO BELIEF"
    if "X" in held_claims:
        final_belief_for_X = classify_belief(held_claims["X"])
        print(f"X: {held_claims['X']}")
        print(f"Derived Belief: {final_belief_for_X}")
    else:
        print("X: (No claims held)")
        print(f"Derived Belief: {final_belief_for_X}")

    return final_belief_for_X

if __name__ == "__main__":
    # Ensure a tie-prone NPC
    # O=0.45, C=0.45, E=0.20, A=0.40, N=0.45
    # Tied for dominant: N and C (both 0.45)
    # Tie break order: N > C, so N is dominant. Outcome: DUAL-HOLD
    print("NPC X for this artifact:")
    print(NPCS["X"])
    print(f"Dominant trait for X: {dominant_trait(NPCS['X'])}\n") # Should be N

    # Run 1: No belief pressure
    # X receives A then B. Initial dominant trait is N -> DUAL-HOLD
    belief_1 = run("BASELINE (No Pressure)", None)
    
    # Run 2: Apply belief pressure from belief_1.
    # If belief_1 was CONFLICTED, then pressure changes outcome to TRANSFORM
    # If belief_1 was TRANSFORMED, then pressure changes outcome to RETAIN
    belief_2 = run("PRESSURE APPLIED (Second Run)", belief_1)
    
