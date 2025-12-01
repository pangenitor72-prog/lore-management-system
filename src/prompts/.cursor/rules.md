# Cursor Project Rules – LMS / MANTLE

You are an AI assistant working inside Cursor on the LMS / MANTLE codebase.

Your primary goals:

1. Preserve the existing architecture.
2. Respect subsystem boundaries.
3. Implement changes in small, explicit diffs.
4. Follow the project’s subsystem implementation templates.

This file defines **global rules** for ALL work in this repo.

---

## 1. Global Safety Rules

- Do NOT refactor multiple subsystems in a single operation.
- Do NOT move files or rename modules unless explicitly instructed.
- Do NOT introduce new external dependencies without explicit approval.
- Do NOT rewrite large files unless it is absolutely necessary and clearly justified.
- Prefer **minimal diffs** over full-file rewrites.

If you believe a large refactor is needed:
- Explain why in plain language.
- Wait for explicit approval before proceeding.

---

## 2. Subsystem Implementation Rules

For any subsystem (e.g., Smart Ingestor, Decoherence Engine, Query Layer):

- Look for its implementation contract in:

  - `docs/UNIVERSAL_IMPLEMENTATION_PROMPT.md`, or  
  - `<subsystem>/SUBSYSTEM_CONTRACT.md`, or  
  - `docs/<subsystem>_DESIGN.md`

- Follow:
  - The defined directory structure
  - The module implementation order
  - The public API contracts
  - The integration rules

If a **Master Implementation Prompt** is provided (like for Smart Ingestor):

- Treat that as **law** for that subsystem.
- Do NOT invent new architecture or cross boundaries.

---

## 3. File-Scoped Changes & Diff Discipline

- When editing a file, only change what is needed for the current task.
- Do NOT edit unrelated functions “while you are there”.
- DO keep behavior-preserving cleanups small and localized.
- Prefer:
  - Adding new functions instead of reorganizing entire files.
  - Adding new modules instead of merging modules together.

All changes should be expressed as **minimal diffs**.

If you must rewrite an entire file:
- State: “This requires a full-file rewrite.”
- Explain why.
- Wait for confirmation.

---

## 4. Orchestrator / LLM Call Rules

For subsystems that use LLMs (e.g., Smart Ingestor, Decoherence Engine):

- Only the **orchestrator** module may call LLMs.
- All other modules must be **pure functions**:
  - No network calls
  - No filesystem writes
  - No logging beyond simple debug if already present

If you need new LLM behavior:
- Add it to the orchestrator layer.
- Use clearly defined request/response data structures.

---

## 5. Context / Pipeline Rules

For pipeline-based subsystems (e.g., passes that operate on a `context` dict):

- Each pass may only:
  - Read keys documented as outputs from earlier passes.
  - Write keys documented as its own outputs.
- Do NOT invent new context keys without updating the subsystem contract.
- Do NOT overwrite keys owned by other passes.

When in doubt, update the subsystem’s contract doc first.

---

## 6. Subsystem Boundaries

You must respect these kinds of boundaries:

- `src/smart_ingestor/` – Smart Ingestor only
- `src/decoherence_engine/` – Time / state resolution only
- `src/auditor/` – Contradiction / validation only
- `src/api/` – API layer only
- `src/ui/` or `src/templates/` – Presentation layer only

Do NOT:
- Import from a subsystem that is higher-level than your current one.
- Push domain logic down into generic layers (e.g., database adapters).

Follow the principle: **higher-level modules depend on lower-level, not vice versa**.

---

## 7. LoreIngestor / EntityFactory / OCEAN Protection

Unless explicitly instructed:

- Do NOT modify:
  - `EntityFactory` templates
  - OCEAN / Personality modules
  - Canonical LoreIngestor behavior beyond designated extension points

If a subsystem needs to integrate with these:

- Use adapter modules, not direct modification.
- Respect their existing public APIs.

---

## 8. Handoff Dossiers

For large tasks or subsystems:

- If you are asked to create or update a **Handoff Dossier**, use the template stored in:
  - `docs/UNIVERSAL_IMPLEMENTATION_PROMPT.md` (or equivalent)
- The dossier must summarize:
  - Architecture
  - Completed modules
  - Pending modules
  - Public APIs
  - Integration points
  - Do-nots / constraints

This dossier allows other AI instances (or humans) to continue safely.

---

## 9. When Context Is Constrained

If you lose context or are unsure:

- Do NOT guess.
- Ask to:
  - Re-open the relevant design doc or contract.
  - Rebuild a Handoff Dossier.
- If you cannot see the design, assume you are NOT allowed to alter architecture.

---

## 10. Final Rule

When in doubt:
- Preserve structure.
- Preserve contracts.
- Preserve intent.
- Make the smallest, safest change that solves the current task.