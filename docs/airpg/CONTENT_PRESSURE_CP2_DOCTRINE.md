# Content Pressure Doctrine — CP-2: Local Contradiction

## Purpose
This document defines the implementation and constraints for **Content Pressure Phase CP-2**, which introduces local, coexisting contradictions into the AIRPG runtime.

## CP-2 Definition: Contradiction via String Encoding

CP-2 proves that the runtime can process multiple, contradictory content atoms within a single interaction without violating core engine principles. This is achieved by encoding multiple atoms into a single, opaque string payload.

- **Contradiction:** A state where two or more atoms share the same `topic` but have different `values`.
- **Encoding:** Atoms are textually encoded into one string (e.g., using a delimiter like `ATOM|`). This string is the `initial_message` for `MinimalRuntime`.
- **Runtime Behavior:** The runtime treats the composite string as a single, indivisible message. It does not parse, interpret, or resolve the atoms within.

## Core Principle: Preservation of Multiplicity

The engine's responsibility is to propagate the *entire composite string* without alteration. The existence of contradictions is a form of pressure; it is not a problem for the engine to solve.

## Explicit Prohibitions (CP-2)
- **No Resolution:** The runtime MUST NOT resolve, merge, or select a "winner" from contradictory atoms.
- **No Priority:** No atom has higher priority. Order is preserved but not interpreted.
- **No Authority:** The runtime MUST NOT assign authority to any atom.
- **No Persistence:** The composite message MUST NOT persist across interactions unless explicitly re-injected by an orchestrator.

## Enforcement Requirements
- The sanity check for CP-2 MUST parse the output string to verify that all original, contradictory atoms are present and unaltered.
- The check MUST fail if any atom is dropped, merged, or transformed based on its contradictory nature.
- Deterministic ordering of atoms within the composite string must be maintained.
- Contradictions MUST coexist only at the local interaction level and have no global or persistent meaning.

This doctrine ensures that contradiction is handled as a runtime pressure that tests personality and emergent behavior, not as a data problem that requires resolution logic.