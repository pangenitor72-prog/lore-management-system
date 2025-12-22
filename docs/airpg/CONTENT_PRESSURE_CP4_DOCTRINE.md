# Content Pressure Doctrine — CP-4: Topological Divergence

## Purpose
This document defines the implementation and constraints for **Content Pressure Phase CP-4**, which proves that topology and personality-driven halting can create asymmetric exposure to contradictory pressure without requiring resolution or fallback logic.

## CP-4 Definition: Topological Filtering

CP-4 validates that the runtime can selectively propagate a composite contradictory payload through a branching topology (e.g., a diamond shape) where some paths forward and others halt.

- **Asymmetric Exposure:** Different agents may receive the same contradictory payload via different paths, or not at all.
- **Halting as Logic:** A node's refusal to forward is a valid, deterministic outcome. It is not an error and triggers no fallback.
- **No Compensation:** The system does not "try other routes" if a path is blocked. Propagation is strictly topological.

## Core Principle: Divergence Without Resolution

The engine's responsibility is to respect the topological and personality constraints of each node. If Agent C halts, Agent D does not receive the message from C. If Agent B forwards, Agent D receives it from B. The contradiction arrives intact via the successful path.

## Explicit Prohibitions (CP-4)
- **No Fallback Routing:** If a path is blocked, the message stops on that branch.
- **No Merging:** If D receives from B but not C, it holds the state from B. It does not "know" about the missing C message.
- **No Resolution:** The contradiction within the payload remains unresolved regardless of the path taken.
- **No Global Knowledge:** Agent D does not know why C halted.

## Enforcement Requirements
- The sanity check for CP-4 MUST implement a diamond topology (A->B, A->C, B->D, C->D).
- It MUST configure Agent C to halt propagation.
- It MUST assert that Agent D receives the payload ONLY from Agent B.
- It MUST assert that the payload remains identical to the injection.
- Determinism must be verified by re-running the scenario.

This doctrine ensures that information flow is shaped by the graph and the agents, not by a desire to ensure global saturation.
