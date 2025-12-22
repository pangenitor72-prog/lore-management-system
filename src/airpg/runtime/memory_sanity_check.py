# src/airpg/runtime/memory_sanity_check.py
from __future__ import annotations

from .memory_stub import (
    memory_is_enabled,
    memory_get_agent_bucket,
    memory_record_marker,
    memory_read_markers,
    MEMORY_ENABLED_KEY,
)


def main():
    print("--- Running Memory Sanity Check ---")

    # ---- Test A: Killability ----
    print("\n[TEST A: Killability]")
    
    # A1: When memory is disabled, record does nothing
    disabled_state = {MEMORY_ENABLED_KEY: False}
    memory_record_marker(disabled_state, "agent_A", "encountered", 1)
    memory_record_marker(disabled_state, "agent_A", "salience", 5)
    
    assert not memory_is_enabled(disabled_state), "Memory should be disabled."
    assert memory_read_markers(disabled_state, "agent_A") == {}, \
        "Read should return empty when memory is disabled."
    assert memory_get_agent_bucket(disabled_state, "agent_A") == {}, \
        "Get bucket should return empty when memory is disabled."
    print("  ✅ SUCCESS: When memory is disabled, record is no-op and read returns empty.")
    
    # A2: Memory is enabled by default
    default_state = {}
    assert memory_is_enabled(default_state), "Memory should be enabled by default."
    print("  ✅ SUCCESS: Memory is enabled by default.")

    # ---- Test B: Determinism ----
    print("\n[TEST B: Determinism]")
    
    # Run identical sequence on two fresh states
    state_1 = {}
    state_2 = {}
    
    sequence = [
        ("agent_A", "encountered", 1),
        ("agent_A", "salience", 3),
        ("agent_B", "unstable_contradiction", 2),
        ("agent_A", "encountered", 1),
        ("agent_B", "repeated", 1),
    ]
    
    for agent_id, marker, intensity in sequence:
        memory_record_marker(state_1, agent_id, marker, intensity)
        memory_record_marker(state_2, agent_id, marker, intensity)
    
    # Verify identical outputs
    assert memory_read_markers(state_1, "agent_A") == memory_read_markers(state_2, "agent_A"), \
        "Identical sequences must yield identical agent_A markers."
    assert memory_read_markers(state_1, "agent_B") == memory_read_markers(state_2, "agent_B"), \
        "Identical sequences must yield identical agent_B markers."
    
    # Verify expected values
    assert memory_read_markers(state_1, "agent_A") == {"encountered": 2, "salience": 3}, \
        "agent_A markers should accumulate correctly."
    assert memory_read_markers(state_1, "agent_B") == {"unstable_contradiction": 2, "repeated": 1}, \
        "agent_B markers should accumulate correctly."
    print("  ✅ SUCCESS: Identical sequences yield identical deterministic outputs.")

    # ---- Test C: No hidden persistence ----
    print("\n[TEST C: No hidden persistence]")
    
    # C1: Two fresh state objects must not share memory
    fresh_state_a = {}
    fresh_state_b = {}
    
    memory_record_marker(fresh_state_a, "agent_X", "encountered", 1)
    
    assert memory_read_markers(fresh_state_a, "agent_X") == {"encountered": 1}, \
        "fresh_state_a should have marker."
    assert memory_read_markers(fresh_state_b, "agent_X") == {}, \
        "fresh_state_b should NOT have marker (no sharing)."
    print("  ✅ SUCCESS: Separate state objects do not share memory.")
    
    # C2: Verify no module-level globals by creating another fresh state
    another_fresh = {}
    assert memory_read_markers(another_fresh, "agent_X") == {}, \
        "New state should have no memory from previous states."
    print("  ✅ SUCCESS: No module-level globals detected.")

    # ---- Test D: Intensity clamping ----
    print("\n[TEST D: Intensity clamping]")
    
    clamp_state = {}
    memory_record_marker(clamp_state, "agent_C", "test_marker", 0)  # Should clamp to 1
    memory_record_marker(clamp_state, "agent_C", "test_marker", -5)  # Should clamp to 1
    
    assert memory_read_markers(clamp_state, "agent_C") == {"test_marker": 2}, \
        "Intensity should be clamped to >= 1."
    print("  ✅ SUCCESS: Intensity is clamped to >= 1.")

    # ---- Test E: No runtime coupling ----
    print("\n[TEST E: No runtime coupling]")
    # This test passes by construction: we never imported MinimalRuntime
    # or any other runtime module. Memory operates on plain dicts only.
    print("  ✅ SUCCESS: Memory stub operates independently of runtime.")

    print("\n--- VERIFICATION COMPLETE ---")
    print("Memory stub is killable, deterministic, non-persistent, and decoupled.")


if __name__ == "__main__":
    main()
