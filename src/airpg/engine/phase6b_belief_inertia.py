"""Phase 6B — Belief Inertia (Validation Artifact)
PROOF GOAL:
Demonstrate that a prior belief category can exert deterministic inertia (resistance to update)
during future conflict resolution without introducing memory, time, randomness, or new primitives.
"""
from typing import Dict, List, Optional

# REQUIRED COMMENT (as per spec)
# This artifact demonstrates deterministic belief inertia that biases
# conflict resolution based on a prior belief category, without state.

# ─────────────────────────────────────────────────────────────
# NPC PROFILES (STATIC)
# ─────────────────────────────────────────────────────────────
NPCS: Dict[str, Dict[str, float]] = {
    # Tie-prone personality to show effect of bias
    "X": {"O": 0.9, "C": 0.9, "E": 0.20, "A": 0.40, "N": 0.9},
}
# ─────────────────────────────────────────────────────────────
# TOPOLOGY (ISOLATED)
# ─────────────────────────────────────────────────────────────
TOPOLOGY: Dict[str, List[str]] = {
    "Source1": ["X"],
    "Source2": ["X"],
    "X": [],
}
# ─────────────────────────────────────────────────────────────
# CLAIMS
# ─────────────────────────────────────────────────────────────
CLAIM_A = "The ritual succeeded."
CLAIM_B = "The ritual failed."
CONFLICT_PAIRS = {(CLAIM_A, CLAIM_B), (CLAIM_B, CLAIM_A)}
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
# BELIEF INERTIA RULE (PHASE 6B ONLY)
# ─────────────────────────────────────────────────────────────
BELIEF_INERTIA_BIAS = {
    "SINGLE-HELD BELIEF": "RETAIN",
    "CONFLICTED BELIEF": "DUAL-HOLD",
    "TRANSFORMED BELIEF": "TRANSFORM",
}
# ─────────────────────────────────────────────────────────────
# RUN-LOCAL STATE (CLEARED BETWEEN RUNS)
# ─────────────────────────────────────────────────────────────
held_claims: Dict[str, List[str]] = {}
prior_belief_category: Optional[str] = None
# ─────────────────────────────────────────────────────────────
# INLINE UTILITIES (NO NEW PRIMITIVES)
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

def classify_belief(claims: List[str]) -> str:
    if not claims:
        return "NO BELIEF"
    if len(claims) == 1:
        if "Reports conflict" in claims[0]:
            return "TRANSFORMED BELIEF"
        return "SINGLE-HELD BELIEF"
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if (claims[i], claims[j]) in CONFLICT_PAIRS:
                return "CONFLICTED BELIEF"
    raise RuntimeError("Invalid belief state: non-conflicting multi-claim")
# ─────────────────────────────────────────────────────────────
# PROPAGATION WITH BELIEF INERTIA
# ─────────────────────────────────────────────────────────────
def propagate(sender: str, claim: str):
    global held_claims
    if sender not in TOPOLOGY:
        return
    for receiver in sorted(TOPOLOGY[sender]):
        if receiver not in held_claims:
            held_claims[receiver] = [claim]
            return

        for existing in held_claims[receiver][:]:
            if conflicts(existing, claim):
                # Default outcome from personality
                trait = dominant_trait(NPCS[receiver])
                outcome = TRAIT_TO_OUTCOME[trait]
                
                # Belief Inertia Pressure
                if prior_belief_category in BELIEF_INERTIA_BIAS:
                    biased_outcome = BELIEF_INERTIA_BIAS[prior_belief_category]
                    outcome = biased_outcome
                
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
                    held_claims[receiver] = ["Reports conflict about the ritual."]
                    return

        if claim not in held_claims[receiver]:
            held_claims[receiver].append(claim)
# ─────────────────────────────────────────────────────────────
# VALIDATION RUNNER
# ─────────────────────────────────────────────────────────────
def run_scenario(label: str, prior: Optional[str]):
    global held_claims, prior_belief_category
    held_claims = {}
    prior_belief_category = prior

    print(f"\n--- RUN: {label} ---")
    print(f"Prior Belief Injected: {prior or 'NONE'}")
    
    propagate("Source1", CLAIM_A)
    propagate("Source2", CLAIM_B)
    
    final_claims = held_claims.get("X", [])
    final_belief = classify_belief(final_claims)
    
    print(f"\nFinal Held Claims for X: {final_claims}")
    print(f"Derived Belief Category: {final_belief}")
    print("-" * (len(label) + 10))

if __name__ == "__main__":
    print("====== PHASE 6B VALIDATION: BELIEF INERTIA ======")
    print("NPC 'X' is tie-prone (N, C, O all at 0.9).")
    print(f"Baseline dominant trait is '{dominant_trait(NPCS['X'])}' -> DUAL-HOLD.")
    
    run_scenario("Baseline", None)
    run_scenario("Inertia A", "SINGLE-HELD BELIEF")
    run_scenario("Inertia B", "CONFLICTED BELIEF")
    run_scenario("Inertia C", "TRANSFORMED BELIEF")
    
    print("\n====== VALIDATION COMPLETE ======")
    print("Proof: Different final beliefs for 'X' resulted from identical inputs,")
    print("       differing only by the injected prior belief category label.")
