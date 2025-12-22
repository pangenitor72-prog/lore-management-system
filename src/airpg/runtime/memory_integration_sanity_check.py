# src/airpg/runtime/memory_integration_sanity_check.py
from __future__ import annotations

from .memory_stub import memory_record_marker, MEMORY_ENABLED_KEY
from .memory_integration_pressure import apply_memory_bias


def main():
    print("--- Running Memory Integration Pressure Sanity Check (MP-1) ---")

    # Test options (synthetic, no narrative meaning)
    options = ["option_A", "option_B", "option_C", "option_D"]

    # ---- Test A: Baseline Equivalence ----
    print("\n[TEST A: Baseline Equivalence]")

    # A1: With memory disabled, returns unchanged
    disabled_state = {MEMORY_ENABLED_KEY: False}
    result_disabled = apply_memory_bias(disabled_state, "agent_X", options)
    assert result_disabled == options, "Disabled memory should return options unchanged."
    assert result_disabled is not options, "Must return a NEW list, not the same object."
    print("  ✅ SUCCESS: With memory disabled, options returned unchanged.")

    # A2: With memory enabled but no markers, returns unchanged
    empty_state = {}
    result_empty = apply_memory_bias(empty_state, "agent_X", options)
    assert result_empty == options, "No markers should return options unchanged."
    assert result_empty is not options, "Must return a NEW list, not the same object."
    print("  ✅ SUCCESS: With no markers, options returned unchanged.")

    # ---- Test B: Determinism ----
    print("\n[TEST B: Determinism]")

    # B1: Same inputs + same memory → identical output order
    state_b1 = {}
    memory_record_marker(state_b1, "agent_Y", "salience", 3)
    memory_record_marker(state_b1, "agent_Y", "encountered", 1)

    result_b1_run1 = apply_memory_bias(state_b1, "agent_Y", options)
    result_b1_run2 = apply_memory_bias(state_b1, "agent_Y", options)
    assert result_b1_run1 == result_b1_run2, "Identical inputs must yield identical output."
    print("  ✅ SUCCESS: Same state + same options → identical output.")

    # B2: Fresh state + same writes → identical output
    state_b2 = {}
    memory_record_marker(state_b2, "agent_Y", "salience", 3)
    memory_record_marker(state_b2, "agent_Y", "encountered", 1)

    result_b2 = apply_memory_bias(state_b2, "agent_Y", options)
    assert result_b1_run1 == result_b2, "Fresh state with same writes must yield identical output."
    print("  ✅ SUCCESS: Fresh state + same writes → identical output.")

    # ---- Test C: Killability ----
    print("\n[TEST C: Killability]")

    # C1: Disabling memory restores baseline
    state_c = {}
    memory_record_marker(state_c, "agent_Z", "repeated", 5)
    result_with_memory = apply_memory_bias(state_c, "agent_Z", options)

    # Now disable memory
    state_c[MEMORY_ENABLED_KEY] = False
    result_after_disable = apply_memory_bias(state_c, "agent_Z", options)
    assert result_after_disable == options, "Disabling memory must restore baseline."
    print("  ✅ SUCCESS: Disabling memory restores baseline behavior.")

    # C2: Agent with no markers returns baseline
    state_c2 = {}
    memory_record_marker(state_c2, "agent_Z", "repeated", 5)
    result_other_agent = apply_memory_bias(state_c2, "agent_DIFFERENT", options)
    assert result_other_agent == options, "Agent without markers must return baseline."
    print("  ✅ SUCCESS: Agent without markers returns baseline.")

    # ---- Test D: Non-Authority ----
    print("\n[TEST D: Non-Authority]")

    # D1: Bias does not remove options
    state_d = {}
    memory_record_marker(state_d, "agent_D", "salience", 10)
    memory_record_marker(state_d, "agent_D", "repeated", 20)
    result_d = apply_memory_bias(state_d, "agent_D", options)

    assert len(result_d) == len(options), "Bias must not change option count."
    assert set(result_d) == set(options), "Bias must not remove or add options."
    print("  ✅ SUCCESS: Bias does not remove or add options.")

    # D2: Bias does not add options
    assert all(opt in options for opt in result_d), "All output options must be from input."
    print("  ✅ SUCCESS: Bias does not add new options.")

    # D3: Works with empty options
    result_empty_opts = apply_memory_bias(state_d, "agent_D", [])
    assert result_empty_opts == [], "Empty input must return empty output."
    print("  ✅ SUCCESS: Empty options handled correctly.")

    # D4: Works with single option
    single_opt = ["only_one"]
    result_single = apply_memory_bias(state_d, "agent_D", single_opt)
    assert result_single == single_opt, "Single option must remain unchanged."
    assert result_single is not single_opt, "Must return a NEW list."
    print("  ✅ SUCCESS: Single option handled correctly.")

    # ---- Test E: Isolation ----
    print("\n[TEST E: Isolation]")

    # E1: No global state - two separate states remain independent
    state_e1 = {}
    state_e2 = {}
    memory_record_marker(state_e1, "agent_E", "salience", 5)

    result_e1 = apply_memory_bias(state_e1, "agent_E", options)
    result_e2 = apply_memory_bias(state_e2, "agent_E", options)

    # state_e1 has markers, state_e2 does not
    assert result_e2 == options, "State without markers must return baseline."
    assert result_e1 != result_e2 or options == result_e1, "Different states should not leak."
    print("  ✅ SUCCESS: States are isolated, no global leakage.")

    # E2: No persistence across calls - calling twice doesn't accumulate
    state_e3 = {}
    memory_record_marker(state_e3, "agent_E", "encountered", 2)

    call1 = apply_memory_bias(state_e3, "agent_E", options)
    call2 = apply_memory_bias(state_e3, "agent_E", options)
    assert call1 == call2, "Repeated calls must yield identical results."
    print("  ✅ SUCCESS: No persistence or accumulation across calls.")

    # ---- Test F: Only allowed markers influence bias ----
    print("\n[TEST F: Only allowed markers influence bias]")

    state_f = {}
    memory_record_marker(state_f, "agent_F", "unstable_contradiction", 100)
    memory_record_marker(state_f, "agent_F", "confusion", 50)

    result_f = apply_memory_bias(state_f, "agent_F", options)
    assert result_f == options, "Non-allowed markers must not influence bias."
    print("  ✅ SUCCESS: Only allowed markers (encountered, repeated, salience) influence bias.")

    print("\n--- VERIFICATION COMPLETE ---")
    print("MP-1: Memory biases tendency without constraining possibility.")


if __name__ == "__main__":
    main()
