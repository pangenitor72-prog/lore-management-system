# src/airpg/engine/phase5b_conflict_resolution.py
"""Phase 5B — Conflicting Information Resolution (Validation Artifact)
PROOF GOAL:
Demonstrate deterministic resolution of conflicting information
using dominance-comparison personality rules, under existing
topology and propagation constraints.
NO MEMORY
NO TIME
NO RANDOMNESS
NO FACTIONS
NO PERSISTENCE
"""
from typing import Dict, List, Tuple

# ─────────────────────────────────────────────────────────────
# NPC DEFINITIONS (STATIC, DETERMINISTIC)
# ─────────────────────────────────────────────────────────────
NPCS: Dict[str, Dict[str, float]] = {
    "A": {"O": 0.80, "C": 0.40, "E": 0.50, "A": 0.50, "N": 0.20},
    "B": {"O": 0.20, "C": 0.85, "E": 0.40, "A": 0.30, "N": 0.25},
    "C": {"O": 0.35, "C": 0.40, "E": 0.30, "A": 0.55, "N": 0.75},
    "D": {"O": 0.50, "C": 0.50, "E": 0.50, "A": 0.50, "N": 0.50},
    # New NPCs for specific scenarios
    "R": {"O": 0.20, "C": 0.90, "E": 0.20, "A": 0.20, "N": 0.20}, # Retain
    "P": {"O": 0.20, "C": 0.20, "E": 0.20, "A": 0.90, "N": 0.20}, # Replace
    "T": {"O": 0.90, "C": 0.20, "E": 0.20, "A": 0.20, "N": 0.20}, # Transform
}
# ─────────────────────────────────────────────────────────────
# TOPOLOGY (PHASE 4A — WHO CAN HEAR)
# ─────────────────────────────────────────────────────────────
TOPOLOGY: Dict[str, List[str]] = {
    "Source1": ["A"],
    "Source2": ["B"],
    "A": ["C"],
    "B": ["C"],
    "C": ["D"],
    "D": [],
    # Topologies for new scenarios
    "SourceRetain": ["R"],
    "SourceReplace": ["P"],
    "SourceTransform": ["T"],
}
# ─────────────────────────────────────────────────────────────
# CLAIMS & CONFLICT PAIRS (EXPLICIT)
# ─────────────────────────────────────────────────────────────
CLAIM_X = "The duke is dead."
CLAIM_Y = "The duke is alive."
CONFLICT_PAIRS: List[Tuple[str, str]] = [
    (CLAIM_X, CLAIM_Y),
    (CLAIM_Y, CLAIM_X),
]
# ─────────────────────────────────────────────────────────────
# DOMINANCE → OUTCOME MAPPING (CANONICAL)
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
# STATE (RUN-LOCAL ONLY)
# ─────────────────────────────────────────────────────────────
held_claims: Dict[str, List[str]] = {}
# ─────────────────────────────────────────────────────────────
# UTILITY (INLINE — NO HELPERS)
# ─────────────────────────────────────────────────────────────
def dominant_trait(profile: Dict[str, float]) -> str:
    max_value = max(profile.values())
    tied = [t for t, v in profile.items() if v == max_value]
    for t in TIE_BREAK_ORDER:
        if t in tied:
            return t
    return tied[0]

def conflicts(existing: str, incoming: str) -> bool:
    return (existing, incoming) in CONFLICT_PAIRS
# ─────────────────────────────────────────────────────────────
# PROPAGATION (DETERMINISTIC ORDER)
# ─────────────────────────────────────────────────────────────
def propagate(sender: str, claim: str, topology: Dict[str, List[str]]):
    if sender not in topology:
        return
    for receiver in sorted(topology[sender]):
        print(f"[PROPAGATION] {sender} → {receiver} : '{claim}'")
        if receiver not in held_claims:
            held_claims[receiver] = [claim]
            print(f"  [HOLD] {receiver} accepts initial claim.")
            propagate(receiver, claim, topology)
            continue
        
        existing_claims = held_claims[receiver][:]
        is_conflicting = False
        for existing in existing_claims:
            if conflicts(existing, claim):
                is_conflicting = True
                print(f"  [CONFLICT] {receiver} detects conflict:")
                print(f"    Existing: '{existing}'")
                print(f"    Incoming: '{claim}'")
                trait = dominant_trait(NPCS[receiver])
                outcome = TRAIT_TO_OUTCOME[trait]
                print(
                    f"  [RESOLUTION] Dominant trait '{trait}' "
                    f"({NPCS[receiver][trait]}) → {outcome}"
                )
                if outcome == "RETAIN":
                    print(f"  [RESULT] {receiver} retains prior claim.")
                    # Do not propagate
                    break 
                if outcome == "REPLACE":
                    held_claims[receiver] = [claim]
                    print(f"  [RESULT] {receiver} replaces prior claim.")
                    propagate(receiver, claim, topology)
                    break
                if outcome == "DUAL-HOLD":
                    if claim not in held_claims[receiver]:
                        held_claims[receiver].append(claim)
                    print(f"  [RESULT] {receiver} dual-holds both claims.")
                    # Propagate both
                    for c in held_claims[receiver]:
                         propagate(receiver, c, topology)
                    break
                if outcome == "TRANSFORM":
                    transformed = "Reports conflict about the duke."
                    held_claims[receiver] = [transformed]
                    print(f"  [RESULT] {receiver} transforms conflict.")
                    propagate(receiver, transformed, topology)
                    break
        
        if not is_conflicting:
            if claim not in held_claims[receiver]:
                held_claims[receiver].append(claim)
                print(f"  [HOLD] {receiver} accepts non-conflicting claim.")
                propagate(receiver, claim, topology)

# ─────────────────────────────────────────────────────────────
# VALIDATION RUN SCENARIOS
# ─────────────────────────────────────────────────────────────
def run_scenario_1_dual_hold():
    global held_claims
    held_claims = {}
    
    topology = {
        "Source1": ["A"], "Source2": ["B"],
        "A": ["C"], "B": ["C"], "C": ["D"], "D": [],
    }

    print("="*20 + " SCENARIO 1: DUAL-HOLD " + "="*20)
    print("\nInitial NPC Profiles:")
    for n in ["A", "B", "C", "D"]:
        print(f"  {n}: {NPCS[n]}")
    print("\nTopology:")
    for k, v in topology.items():
        print(f"  {k} → {v}")
    print("\nClaims Injected (Deterministic Order):")
    print("  1) Source1 → Claim X")
    print("  2) Source2 → Claim Y\n")
    
    propagate("Source1", CLAIM_X, topology)
    propagate("Source2", CLAIM_Y, topology)
    
    print("\n--- FINAL HELD CLAIMS (SCENARIO 1) ---")
    for npc, claims in sorted(held_claims.items()):
        print(f"  {npc}: {claims}")
    print("\n")

def run_scenario_2_retain():
    global held_claims
    held_claims = {}
    
    topology = {"Source1": ["R"], "Source2": ["R"], "R": []}
    
    print("="*20 + " SCENARIO 2: RETAIN " + "="*20)
    print("\nNPC Profile:")
    print(f"  R: {NPCS['R']}")
    
    print("\nClaims Injected:")
    print("  1) Source1 → Claim X")
    print("  2) Source2 → Claim Y\n")
    
    propagate("Source1", CLAIM_X, topology)
    propagate("Source2", CLAIM_Y, topology)

    print("\n--- FINAL HELD CLAIMS (SCENARIO 2) ---")
    for npc, claims in sorted(held_claims.items()):
        print(f"  {npc}: {claims}")
    print("\n")

def run_scenario_3_transform():
    global held_claims
    held_claims = {}

    topology = {"Source1": ["T"], "Source2": ["T"], "T": []}

    print("="*20 + " SCENARIO 3: TRANSFORM " + "="*20)
    print("\nNPC Profile:")
    print(f"  T: {NPCS['T']}")
    
    print("\nClaims Injected:")
    print("  1) Source1 → Claim X")
    print("  2) Source2 → Claim Y\n")
    
    propagate("Source1", CLAIM_X, topology)
    propagate("Source2", CLAIM_Y, topology)

    print("\n--- FINAL HELD CLAIMS (SCENARIO 3) ---")
    for npc, claims in sorted(held_claims.items()):
        print(f"  {npc}: {claims}")
    print("\n")

def run_scenario_4_replace():
    global held_claims
    held_claims = {}

    topology = {"Source1": ["P"], "Source2": ["P"], "P": []}
    
    print("="*20 + " SCENARIO 4: REPLACE " + "="*20)
    print("\nNPC Profile:")
    print(f"  P: {NPCS['P']}")
    
    print("\nClaims Injected:")
    print("  1) Source1 → Claim X")
    print("  2) Source2 → Claim Y\n")

    propagate("Source1", CLAIM_X, topology)
    propagate("Source2", CLAIM_Y, topology)
    
    print("\n--- FINAL HELD CLAIMS (SCENARIO 4) ---")
    for npc, claims in sorted(held_claims.items()):
        print(f"  {npc}: {claims}")
    print("\n")

def run_all():
    print("=== PHASE 5B VALIDATION RUN ===\n")
    run_scenario_1_dual_hold()
    run_scenario_2_retain()
    run_scenario_3_transform()
    run_scenario_4_replace()
    print("=== ALL SCENARIOS COMPLETE ===")

if __name__ == "__main__":
    run_all()