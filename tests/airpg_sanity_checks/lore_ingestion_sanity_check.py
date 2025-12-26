# src/airpg/runtime/lore_ingestion_sanity_check.py
from __future__ import annotations
from typing import List, Tuple, Optional

from .runtime import MinimalRuntime
from .session_state import SessionState
from .session_loop import run_session_step
from .lore_ingestion_stub import ingest_lore_as_pressure

# ---- Test Data & Stubs ----
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
    print("--- Running Lore Ingestion Sanity Check ---")

    runtime = MinimalRuntime()

    # ---- Test 1: Lore delivered verbatim with source marker ----
    print("\n[TEST 1: Lore delivered verbatim with source marker]")
    lore_text = "The ancient king was betrayed by his council."
    source_label = "myth"
    
    payload = ingest_lore_as_pressure(lore_text, source_label)
    
    assert isinstance(payload, str), "Payload must be a string."
    assert lore_text in payload, "Lore text must be preserved in payload."
    assert source_label in payload, "Source label must be preserved in payload."
    assert "CLAIM" in payload, "Payload must be marked as a CLAIM."
    print("  ✅ SUCCESS: Lore delivered verbatim with source marker.")

    # ---- Test 2: Lore remains a string at runtime boundaries ----
    print("\n[TEST 2: Lore remains a string at runtime boundaries]")
    initial_state = SessionState(turn_index=0)
    _, trace = run_session_step(
        state=initial_state,
        player_input=payload,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )
    
    assert trace, "Trace should not be empty."
    delivered_message = trace[1].message
    assert isinstance(delivered_message, str), "Delivered message must be a string."
    assert delivered_message == payload, "Payload must pass through unchanged."
    print("  ✅ SUCCESS: Lore remains a string at runtime boundaries.")

    # ---- Test 3: Lore does not alter determinism ----
    print("\n[TEST 3: Lore does not alter determinism]")
    _, trace2 = run_session_step(
        state=initial_state,
        player_input=payload,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )
    assert trace == trace2, "Determinism violated: identical runs produced different traces."
    print("  ✅ SUCCESS: Lore does not alter determinism.")

    # ---- Test 4: Re-running with identical inputs yields identical traces ----
    print("\n[TEST 4: Re-running with identical inputs yields identical traces]")
    # Test with different lore input
    lore_text_2 = "The tower fell on the third day."
    source_label_2 = "record"
    payload_2 = ingest_lore_as_pressure(lore_text_2, source_label_2)
    
    state_a = SessionState(turn_index=0)
    _, trace_a = run_session_step(
        state=state_a,
        player_input=payload_2,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )
    
    state_b = SessionState(turn_index=0)
    _, trace_b = run_session_step(
        state=state_b,
        player_input=payload_2,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )
    
    assert trace_a == trace_b, "Identical lore inputs must yield identical traces."
    print("  ✅ SUCCESS: Re-running with identical inputs yields identical traces.")

    # ---- Test 5: Removing the ingestion stub causes no runtime failure ----
    print("\n[TEST 5: Removing ingestion stub causes no runtime failure]")
    # Prove that the runtime works without the stub by injecting raw content
    raw_content = "Raw content without lore stub."
    state_raw = SessionState(turn_index=0)
    _, trace_raw = run_session_step(
        state=state_raw,
        player_input=raw_content,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
    )
    assert trace_raw, "Runtime must work without lore ingestion stub."
    assert trace_raw[1].message == raw_content, "Raw content must propagate unchanged."
    print("  ✅ SUCCESS: Removing ingestion stub causes no runtime failure.")

    print("\n--- VERIFICATION COMPLETE ---")
    print("Lore ingestion operates as stateless, non-authoritative pressure adapter.")


if __name__ == "__main__":
    main()
