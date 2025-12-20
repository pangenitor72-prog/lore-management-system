# Runtime Branch Governance (airpg-runtime-minimal)

This document outlines the strict governance rules for the `airpg-runtime-minimal` branch, ensuring architectural integrity and alignment with the proven `airpg-foundation` branch.

---

## 1. airpg-foundation: Proof-Only Archive

The `airpg-foundation` branch serves as a **LOCKED, proof-only archive**. It contains the validated, stateless, deterministic engine logic established through Phases 1–6D.

*   `airpg-foundation` **never** receives runtime-specific code or modifications from downstream branches.
*   Its content represents the immutable foundation of the AIRPG engine's proven capabilities.

## 2. airpg-runtime-minimal: Runtime Embodiment Layer

The `airpg-runtime-minimal` branch is the **active runtime embodiment layer**. It is where minimal, justified mechanisms (such as ephemeral memory) are introduced to enable a human-experiencable interaction, without corrupting the core proofs.

*   This branch may introduce new files and minimal runtime logic.
*   All runtime additions **MUST** adhere to the constraints and principles established in the `airpg-foundation` doctrine.

## 3. Explicit Merge Direction: Foundation → Runtime ONLY

To maintain the purity of the proof layer and the integrity of the runtime layer, merge operations are strictly unidirectional:

*   **Allowed:** Merges from `airpg-foundation` into `airpg-runtime-minimal`.
*   **Forbidden:** Merges from `airpg-runtime-minimal` into `airpg-foundation`.

This ensures that the proof foundation remains untainted by runtime-specific implementations.

## 4. Import Rule: Engine → Runtime Permitted; Runtime → Engine Forbidden

*   **Permitted:** Modules within the `airpg-runtime-minimal` branch **may import** modules from the `airpg-foundation` (engine) layer.
*   **Forbidden:** Modules within the `airpg-foundation` (engine) layer **may NEVER import** modules from the `airpg-runtime-minimal` branch.

This prevents runtime-specific dependencies from contaminating the core engine logic.

## 5. Structural Invariant: Mandatory Enforcement

The structural non-corruption invariant (`python -m src.airpg.runtime.sanity_check`) is **mandatory and authoritative** for this branch.

*   This invariant verifies that the `MinimalRuntime` wrapper does not alter the deterministic propagation behavior of the core engine.
*   Any change introduced to `airpg-runtime-minimal` that causes this invariant to fail is considered **invalid** and must be reverted or corrected.
*   Automated CI will enforce this invariant on all pushes and pull requests targeting this branch.

---

**This document is canonical for the `airpg-runtime-minimal` branch. No modifications that contradict these principles are permitted.**
