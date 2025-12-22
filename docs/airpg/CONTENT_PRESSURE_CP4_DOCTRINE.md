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

## Player-Facing Canon Commit Warnings (Design)

This section defines the design contract for warning players when an action may write canon.

### When Warnings Are Required

The system MUST warn the player before any action that:
- Writes irreversible world-state (e.g., character death, faction destruction)
- Locks a previously ambiguous claim into canon
- Resolves a contradiction by selecting one version as real
- Commits a player choice that constrains future possibility

### Canon Commit Rules

- Canon writes are explicit and opt-in.
- Canon writes are savegame-scoped.
- Once written, canon constrains all future interactions within that savegame.
- Rewinding past a canon commit creates a new savegame branch, not an undo.

### Warning Requirements

- The warning MUST be clear and unambiguous.
- The player MUST explicitly confirm the commit.
- Declining the commit MUST preserve ambiguity; no canon is written.

## Lore Ingestion Interface Contract (Design)

This section defines the required properties that any lore ingestion system must satisfy to remain compatible with AIRPG's epistemic constraints.

### Claim Nature

- Lore MUST be ingested as claims, not facts.
- No ingestion path may assert objective truth.
- All lore enters as pressure, not authority.

### Source Attribution

- Lore MUST retain source context (e.g., myth, record, testimony).
- Source attribution is metadata; it does NOT imply authority or correctness.
- Source type does not affect propagation priority.

### Scope Declaration

- Lore MUST be explicitly scoped to the current savegame.
- No global lore is permitted.
- No cross-save lore is permitted.

### Canon Awareness

- Ingestion MUST respect existing savegame canon.
- Lore that contradicts canon MUST be routed through canon conflict handling.
- Lore ingestion MUST NOT write canon.
- Only explicit player confirmation may commit canon.

### Contradiction Tolerance

- Multiple incompatible lore entries MUST be allowed to coexist.
- No normalization is permitted.
- No reconciliation is permitted.
- No prioritization is permitted.

### Memory Separation

- Ingesting lore MUST NOT automatically write memory.
- Memory formation is optional and downstream.
- Lore and memory are distinct systems.

### Killability

- The engine MUST remain valid if all ingested lore is removed.
- Lore ingestion MUST NOT become structurally required.
- No lore entry may be load-bearing.
