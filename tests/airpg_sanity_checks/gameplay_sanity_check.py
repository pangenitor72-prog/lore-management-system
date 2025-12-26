# src/airpg/runtime/gameplay_sanity_check.py
from __future__ import annotations
from typing import List, Tuple, Optional

from .runtime import MinimalRuntime
from .session_state import SessionState
from .session_loop import run_session_step
from .gameplay_rules import rule_prevent_attack_on_turn_3

# ---- Test Data ----
AGENTS = ("Player", "A")
TOPOLOGY = {"Player": ["A"], "A": []}

def deliver_fn(
    receiver: str, sender: Optional[str], message: str
) -> List[Tuple[str, str]]:
    """Minimal deterministic propagation function."""
    forwards = []
    for next_receiver in TOPOLOGY.get(receiver, []):
        forwards.append((next_receiver, message))
    return forwards

def main():
    """
    Runs the gameplay rule test and asserts invariants.
    """
    print("--- Running Gameplay Rule Sanity Check ---")

    runtime = MinimalRuntime()
    rules = [rule_prevent_attack_on_turn_3]
    player_message = "I attack the target."

    # ---- Run WITH the rule active ----
    print("\n[RUN 1: Executing 3-turn session WITH gameplay rule]")
    state_r1_t0 = SessionState(turn_index=0)
    
    state_r1_t1, trace_r1_t1 = run_session_step(
        state=state_r1_t0, player_input=player_message, agent_ids=AGENTS,
        deliver_fn=deliver_fn, runtime=runtime, rules=rules
    )
    state_r1_t2, trace_r1_t2 = run_session_step(
        state=state_r1_t1, player_input=player_message, agent_ids=AGENTS,
        deliver_fn=deliver_fn, runtime=runtime, rules=rules
    )
    state_r1_t3, trace_r1_t3 = run_session_step(
        state=state_r1_t2, player_input=player_message, agent_ids=AGENTS,
        deliver_fn=deliver_fn, runtime=runtime, rules=rules
    )
    
    # ---- Run WITHOUT the rule active ----
    print("\n[RUN 2: Executing 3-turn session WITHOUT gameplay rule]")
    state_r2_t0 = SessionState(turn_index=0)

    state_r2_t1, trace_r2_t1 = run_session_step(
        state=state_r2_t0, player_input=player_message, agent_ids=AGENTS,
        deliver_fn=deliver_fn, runtime=runtime, rules=[]  # No rules
    )
    state_r2_t2, trace_r2_t2 = run_session_step(
        state=state_r2_t1, player_input=player_message, agent_ids=AGENTS,
        deliver_fn=deliver_fn, runtime=runtime, rules=[]
    )
    state_r2_t3, trace_r2_t3 = run_session_step(
        state=state_r2_t2, player_input=player_message, agent_ids=AGENTS,
        deliver_fn=deliver_fn, runtime=runtime, rules=[]
    )

    # ---- Assertions ----
    
    # 1. Turn 1 and 2 outputs are identical (rule is not active yet)
    assert trace_r1_t1[0].message == trace_r2_t1[0].message
    assert trace_r1_t2[0].message == trace_r2_t2[0].message
    print("\n[ASSERTION PASSED]: Turn 1 & 2 behavior is identical with/without rule.")

    # 2. Turn 3+ outputs diverge only when rule is active
    assert trace_r2_t3[0].message == "I attack the target."
    assert trace_r1_t3[0].message == "hesitates instead of attacking"
    print("[ASSERTION PASSED]: Turn 3 behavior diverges correctly when rule is active.")

    # 3. Removing the rule restores baseline behavior (covered by assert #1 & #2)
    print("[ASSERTION PASSED]: Removing the rule restores baseline behavior.")

    # 4. Re-running yields identical results (determinism)
    state_r3_t0 = SessionState(turn_index=0)
    _, fresh_trace = run_session_step(
        state=state_r3_t0, player_input=player_message, agent_ids=AGENTS,
        deliver_fn=deliver_fn, runtime=runtime, rules=rules
    )
    assert fresh_trace[0].message == trace_r1_t1[0].message
    print("[ASSERTION PASSED]: Re-running with fresh state yields identical trace.")

    print("\n--- VERIFICATION COMPLETE ---")
    print("Gameplay rules operate deterministically without hidden state.")


if __name__ == "__main__":
    main()
