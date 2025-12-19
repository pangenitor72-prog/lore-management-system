"""Phase 5C — Player Injection into Live Topology (Validation Artifact)
PROOF GOAL:
Demonstrate that a Player can be injected into the AIRPG
social-information system as a constrained source node,
without authority, privilege, memory, or special behavior.
The Player is treated identically to any other source.
All propagation, conflict resolution, and belief outcomes
are governed strictly by existing topology and personality rules.
NO MEMORY
NO TIME
NO RANDOMNESS
NO AUTHORITY
NO SPECIAL PLAYER LOGIC
"""
from typing import Dict, List

# ─────────────────────────────────────────────────────────────
# NPC PROFILES (STATIC)
# ─────────────────────────────────────────────────────────────
NPCS: Dict[str, Dict[str, float]] = {
    "A": {"O": 0.30, "C": 0.80, "E": 0.20, "A": 0.30, "N": 0.20},  # RETAIN
    "B": {"O": 0.85, "C": 0.20, "E": 0.20, "A": 0.20, "N": 0.20},  # TRANSFORM
    "C": {"O": 0.30, "C": 0.30, "E": 0.20, "A": 0.40, "N": 0.85},  # DUAL-HOLD
}
# ─────────────────────────────────────────────────────────────
# TOPOLOGY (PLAYER IS JUST A NODE)
# ─────────────────────────────────────────────────────────────
TOPOLOGY: Dict[str, List[str]] = {
    "SourceNPC": ["A"],
    "Player": ["B"],
    "A": ["C"],
    "B": ["C"],
    "C": [],
}
# ─────────────────────────────────────────────────────────────
# CLAIMS
# ─────────────────────────────────────────────────────────────
CLAIM_X = "The relic was destroyed."
CLAIM_Y = "The relic still exists."
CONFLICT_PAIRS = {
    (CLAIM_X, CLAIM_Y),
    (CLAIM_Y, CLAIM_X),
}
# ─────────────────────────────────────────────────────────────
# PERSONALITY → OUTCOME
# ─────────────────────────────────────────────────────────────
TRAIT_TO_OUTCOME = {
    "C": "RETAIN",
    "O": "TRANSFORM",
    "N": "DUAL-HOLD",
    "A": "REPLACE",
    "E": "REPLACE",
}
TIE_BREAK_ORDER = ["N", "C", "O", "A", "E"]
# ─────────────────────────────────────────────────────────────
# RUN-LOCAL STATE (NON-PERSISTENT)
# ─────────────────────────────────────────────────────────────
held_claims: Dict[str, List[str]] = {}
# ─────────────────────────────────────────────────────────────
# INLINE UTILITIES (NO HELPERS)
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
    if sender not in TOPOLOGY:
        return
    for receiver in sorted(TOPOLOGY[sender]):
        print(f"[PROPAGATION] {sender} → {receiver} : '{claim}'")
        if receiver not in held_claims:
            held_claims[receiver] = [claim]
            print(f"  [HOLD] {receiver} accepts initial claim.")
            propagate(receiver, claim)
            continue
        
        for existing in held_claims[receiver][:]:
            if conflicts(existing, claim):
                trait = dominant_trait(NPCS[receiver])
                outcome = TRAIT_TO_OUTCOME[trait]
                print(f"  [CONFLICT] {receiver}: '{existing}' vs '{claim}'")
                print(f"  [RESOLUTION] Dominant '{trait}' → {outcome}")
                if outcome == "RETAIN":
                    print(f"  [RESULT] {receiver} retains prior claim.")
                    return 
                if outcome == "REPLACE":
                    held_claims[receiver] = [claim]
                    print(f"  [RESULT] {receiver} replaces prior claim.")
                    propagate(receiver, claim)
                    return
                if outcome == "DUAL-HOLD":
                    if claim not in held_claims[receiver]:
                        held_claims[receiver].append(claim)
                    print(f"  [RESULT] {receiver} dual-holds.")
                    propagate(receiver, claim)
                    return
                if outcome == "TRANSFORM":
                    transformed = "Reports conflict about the relic."
                    held_claims[receiver] = [transformed]
                    print(f"  [RESULT] {receiver} transforms conflict.")
                    propagate(receiver, transformed)
                    return
        
        if claim not in held_claims[receiver]:
            held_claims[receiver].append(claim)
            print(f"  [HOLD] {receiver} accepts non-conflicting claim.")
            propagate(receiver, claim)

# ─────────────────────────────────────────────────────────────
# VALIDATION RUN
# ─────────────────────────────────────────────────────────────
def run():
    global held_claims
    held_claims = {}

    print("=== PHASE 5C VALIDATION RUN ===\n")
    print("NPC Profiles:")
    for n, p in NPCS.items():
        print(f"  {n}: {p}")
    print("\nTopology:")
    for k, v in TOPOLOGY.items():
        print(f"  {k} → {v}")
    print("\nClaims Injected (Deterministic Order):")
    print("  1) SourceNPC → Claim X")
    print("  2) Player → Claim Y\n")
    
    propagate("SourceNPC", CLAIM_X)
    propagate("Player", CLAIM_Y)

    print("\n=== FINAL HELD CLAIMS ===")
    for npc, claims in sorted(held_claims.items()):
        print(f"  {npc}: {claims}")

if __name__ == "__main__":
    run()
