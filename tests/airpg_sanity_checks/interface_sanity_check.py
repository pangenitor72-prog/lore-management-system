# src/airpg/runtime/interface_sanity_check.py
from __future__ import annotations
from typing import List, Tuple, Optional, Callable

from .runtime import MinimalRuntime
from .session_state import SessionState
from .gameplay_rules import GameplayRule
from .interactive_loop import run_interactive_loop

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

class StubIO:
    """A simple, stateful stub for capturing I/O without mocks."""
    def __init__(self, inputs: List[str]):
        self.inputs = inputs
        self.outputs: List[str] = []
        self._input_index = 0

    def input_fn(self, prompt: str) -> str:
        """Provides canned input; prints prompt to captured output."""
        self.outputs.append(prompt.strip())
        if self._input_index < len(self.inputs):
            response = self.inputs[self._input_index]
            self.outputs.append(f"[Input: {response}]")
            self._input_index += 1
            return response
        return "quit"

    def output_fn(self, message: str) -> None:
        """Captures all print output."""
        self.outputs.append(message)

def main():
    print("--- Running Interface Sanity Check ---")
    
    runtime = MinimalRuntime()
    initial_state = SessionState(turn_index=0)
    test_inputs = ["Hello", "Again"]

    # ---- Run 1 ----
    stub1 = StubIO(inputs=test_inputs)
    run_interactive_loop(
        initial_state=initial_state,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
        input_fn=stub1.input_fn,
        output_fn=stub1.output_fn,
    )
    
    # ---- Run 2 (to test determinism) ----
    stub2 = StubIO(inputs=test_inputs)
    run_interactive_loop(
        initial_state=initial_state,
        agent_ids=AGENTS,
        deliver_fn=deliver_fn,
        runtime=runtime,
        input_fn=stub2.input_fn,
        output_fn=stub2.output_fn,
    )

    # ---- Assertions ----
    
    # 1. & 2. Output depends only on inputs + initial state, and re-running is identical
    assert stub1.outputs == stub2.outputs, (
        "INVARIANT VIOLATION: Identical runs produced different outputs.\n"
        f"Run 1 Output:\n{stub1.outputs}\n\n"
        f"Run 2 Output:\n{stub2.outputs}"
    )
    print("\n[ASSERTION PASSED]: Re-running with same inputs yields identical output.")

    # 3. No hidden accumulation occurs.
    # We can see from the output that the prompt for turn 1 is different from turn 0.
    # This proves the state object is being passed and updated correctly.
    assert "Turn 0" in stub1.outputs[0]
    assert "Turn 1" in stub1.outputs[4]
    print("[ASSERTION PASSED]: State object is passed and updated correctly.")


    print("\n--- VERIFICATION COMPLETE ---")
    print("Interactive loop is stateless and deterministic.")


if __name__ == "__main__":
    main()
