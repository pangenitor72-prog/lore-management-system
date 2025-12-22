# Content Pressure Doctrine — CP-3: Distributed Contradiction

## Purpose
This document defines the implementation and constraints for **Content Pressure Phase CP-3**, which proves that contradictions can propagate across multiple agents and topological hops without resolution or convergence.

## CP-3 Definition: Multi-Hop Propagation of Contradiction

CP-3 validates that the runtime can transport a composite payload of contradictory atoms through a multi-agent chain (e.g., A → B → C) while preserving its full contradictory state.

- **Distributed Contradiction:** The state where multiple agents in a chain hold and forward the *same* unresolved contradiction.
- **No Convergence:** Propagation does not imply consensus. Agent B does not resolve the conflict before passing it to Agent C.
- **Encoding:** CP-3 reuses the CP-2 string encoding pattern (e.g., `ATOM|topic=X|value=1
ATOM|topic=X|value=2`).

## Core Principle: Contradiction Stability

The engine's responsibility is to maintain the integrity of the contradictory payload across distance (topological hops). Distance does not degrade multiplicity.

## Explicit Prohibitions (CP-3)
- **No Collapse:** No agent in the chain may collapse the contradiction into a single truth.
- **No Degradation:** No atom may be lost during propagation steps.
- **No Reordering:** The internal ordering of atoms within the composite string must remain deterministic at every hop.
- **No Global State:** The contradiction exists only within the message passing chain of the current interaction.

## Enforcement Requirements
- The sanity check for CP-3 MUST assert that the full, unchanged composite string appears at every step of the propagation trace.
- The check MUST fail if any agent resolves, alters, or reorders the content atoms.
- Determinism must be verified by re-running the multi-hop sequence from a fresh session state.

This doctrine ensures that the runtime supports distributed ambiguity and does not force artificial consensus upon the simulation.
