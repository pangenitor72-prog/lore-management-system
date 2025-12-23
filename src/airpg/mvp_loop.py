# src/airpg/mvp_loop.py
"""
MVP Loop — Minimal Playable Demonstration

This script demonstrates:
- player input → world response
- visible use of existing pressures
- traceable decision logic

Consumes existing systems only. Does not modify MinimalRuntime.
Does not introduce persistence. Does not write canon.
Deterministic.
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple

# Consume existing systems
from .runtime.memory_stub import (
    memory_is_enabled,
    memory_read_markers,
    MEMORY_KEY,
    MEMORY_ENABLED_KEY,
)
from .runtime.memory_integration_pressure import apply_memory_bias

# ─────────────────────────────────────────────────────────────
# PERSONALITY LOGIC (COPIED FROM EXISTING ENGINE — READ-ONLY)
# ─────────────────────────────────────────────────────────────
TRAIT_TO_OUTCOME = {
    "N": "DUAL-HOLD",
    "C": "RETAIN",
    "O": "TRANSFORM",
    "A": "REPLACE",
    "E": "REPLACE",
}
TIE_BREAK_ORDER = ["N", "C", "O", "A", "E"]


def dominant_trait(profile: Dict[str, float]) -> str:
    """Returns the dominant OCEAN trait using tie-break order."""
    max_val = max(profile.values())
    tied = [t for t, v in profile.items() if v == max_val]
    for t in TIE_BREAK_ORDER:
        if t in tied:
            return t
    return tied[0]


# ─────────────────────────────────────────────────────────────
# DEFAULT AGENT PROFILE (STATIC)
# ─────────────────────────────────────────────────────────────
DEFAULT_AGENT_ID = "world"
DEFAULT_AGENT_PROFILE: Dict[str, float] = {
    "O": 0.50,  # Openness
    "C": 0.60,  # Conscientiousness (slightly dominant)
    "E": 0.40,  # Extraversion
    "A": 0.50,  # Agreeableness
    "N": 0.30,  # Neuroticism
}


# ─────────────────────────────────────────────────────────────
# OPTION GENERATION (DETERMINISTIC)
# ─────────────────────────────────────────────────────────────
def generate_options(player_input: str) -> List[str]:
    """
    Generates exactly 3 opaque options from player input.

    Options are deterministic tokens based on input hash.
    No narrative meaning required.
    """
    # Deterministic hash of input
    h = hash(player_input) % 1000

    return [
        f"OPT_A_{h}",
        f"OPT_B_{h}",
        f"OPT_C_{h}",
    ]


# ─────────────────────────────────────────────────────────────
# PERSONALITY CONSTRAINT (PRESSURE 1)
# ─────────────────────────────────────────────────────────────
def apply_personality_constraint(
    options: List[str],
    profile: Dict[str, float],
) -> Tuple[List[str], str]:
    """
    Applies personality-based ordering to options.

    Returns: (reordered_options, trace_message)

    Personality affects preference ordering, not legality.
    All options remain available.
    """
    trait = dominant_trait(profile)
    outcome = TRAIT_TO_OUTCOME[trait]

    # Deterministic reordering based on trait
    # Higher C (conscientiousness) → prefer first option
    # Higher O (openness) → prefer last option (novel)
    # Higher N (neuroticism) → keep all, no preference
    result = list(options)

    if trait == "O":
        # Openness prefers novel → rotate to put last first
        result = result[-1:] + result[:-1]
    elif trait in ("A", "E"):
        # Agreeable/Extraverted → prefer second option (social)
        if len(result) >= 2:
            result[0], result[1] = result[1], result[0]
    # C and N keep original order

    trace = f"personality={trait} outcome={outcome}"
    return result, trace


# ─────────────────────────────────────────────────────────────
# CANON LEGALITY CHECK (PRESSURE 3 — STUB)
# ─────────────────────────────────────────────────────────────
def check_canon_legality(
    options: List[str],
    state: Dict[str, Any],
) -> Tuple[List[str], str]:
    """
    Checks options against canon.

    READ-ONLY stub. Returns all options as legal.
    Does not write canon.
    """
    # Stub: all options are legal
    # In future, this would read canon and filter
    return list(options), "canon_check=STUB all_legal=True"


# ─────────────────────────────────────────────────────────────
# MVP LOOP CORE
# ─────────────────────────────────────────────────────────────
def run_loop(
    player_input: str,
    state: Dict[str, Any],
    agent_id: str = DEFAULT_AGENT_ID,
    profile: Dict[str, float] = None,
) -> Dict[str, Any]:
    """
    Runs one iteration of the MVP loop.

    Args:
        player_input: The player's input string.
        state: Session state dict (contains memory if enabled).
        agent_id: The agent making the decision.
        profile: OCEAN personality profile (uses default if None).

    Returns:
        Dict with:
        - player_input
        - available_options
        - selected_option
        - trace (list of pressure influences)
        - would_write_memory (marker that WOULD be written, not persisted)
    """
    if profile is None:
        profile = DEFAULT_AGENT_PROFILE

    trace: List[str] = []

    # Step A: Generate options from input
    options = generate_options(player_input)
    trace.append(f"generated={len(options)} options")

    # Step B1: Apply personality constraint
    options, personality_trace = apply_personality_constraint(options, profile)
    trace.append(personality_trace)

    # Step B2: Apply memory bias (MP-1) if enabled
    memory_enabled = memory_is_enabled(state)
    options_before_memory = list(options)
    options = apply_memory_bias(state, agent_id, options)

    if memory_enabled:
        markers = memory_read_markers(state, agent_id)
        if options != options_before_memory:
            trace.append(f"memory_bias=APPLIED markers={markers}")
        else:
            trace.append(f"memory_bias=NO_EFFECT markers={markers}")
    else:
        trace.append("memory_bias=DISABLED")

    # Step B3: Canon legality check (read-only stub)
    options, canon_trace = check_canon_legality(options, state)
    trace.append(canon_trace)

    # Step C: Select first option (deterministic)
    selected = options[0] if options else None
    trace.append(f"selection=FIRST_LEGAL")

    # Step D: Determine what memory marker WOULD be written
    # (Do NOT persist — just report)
    would_write = {
        "agent_id": agent_id,
        "marker": "encountered",
        "value": f"input:{player_input[:32]}",
        "persisted": False,
    }

    return {
        "player_input": player_input,
        "available_options": options,
        "selected_option": selected,
        "trace": trace,
        "would_write_memory": would_write,
    }


# ─────────────────────────────────────────────────────────────
# CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────
def main():
    """Command-line entrypoint for MVP loop demonstration."""
    print("=" * 60)
    print("AIRPG MVP LOOP — Minimal Playable Demonstration")
    print("=" * 60)
    print()

    # Create minimal state with memory enabled
    state: Dict[str, Any] = {
        MEMORY_ENABLED_KEY: True,
        MEMORY_KEY: {
            DEFAULT_AGENT_ID: {
                "encountered": 1,
                "salience": 2,
            }
        },
    }

    # Hardcoded player input for deterministic demonstration
    player_input = "I search the tavern for clues"

    print(f"Player Input: \"{player_input}\"")
    print(f"Agent: {DEFAULT_AGENT_ID}")
    print(f"Profile: {DEFAULT_AGENT_PROFILE}")
    print(f"Memory Enabled: {memory_is_enabled(state)}")
    print(f"Memory Markers: {memory_read_markers(state, DEFAULT_AGENT_ID)}")
    print()

    # Run the loop
    result = run_loop(player_input, state)

    # Output results
    print("-" * 60)
    print("RESULTS")
    print("-" * 60)
    print(f"Available Options: {result['available_options']}")
    print(f"Selected Option:   {result['selected_option']}")
    print()
    print("TRACE:")
    for i, t in enumerate(result["trace"], 1):
        print(f"  {i}. {t}")
    print()
    print("WOULD WRITE MEMORY (not persisted):")
    for k, v in result["would_write_memory"].items():
        print(f"  {k}: {v}")
    print()
    print("=" * 60)
    print("DETERMINISM CHECK: Re-running with same input...")
    print("=" * 60)

    # Re-run to prove determinism
    result2 = run_loop(player_input, state)

    if result == result2:
        print("✓ DETERMINISM VERIFIED: Identical results")
    else:
        print("✗ DETERMINISM FAILED: Results differ")

    print()

    # Interactive mode (optional)
    print("-" * 60)
    print("INTERACTIVE MODE (type 'quit' to exit)")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nPlayer> ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("Exiting MVP loop.")
                break
            if not user_input:
                continue

            result = run_loop(user_input, state)
            print(f"\nOptions: {result['available_options']}")
            print(f"Selected: {result['selected_option']}")
            print(f"Trace: {result['trace']}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting MVP loop.")
            break


if __name__ == "__main__":
    main()
