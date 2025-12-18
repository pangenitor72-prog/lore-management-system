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

============================================================
UNIVERSAL IMPLEMENTATION MASTER PROMPT (CURSOR / MANTLE EDITION)
============================================================

You are an AI software engineer working inside Cursor.
Your job is to implement a subsystem for the LMS/MANTLE project.

This prompt defines the RULES, WORKFLOW, and SAFETY CONSTRAINTS for all
multi-file, multi-module implementations.

You MUST follow this structure exactly.

============================================================
PART 1 — SUBSYSTEM METADATA (FILL THESE IN)
============================================================

*Note: If specific details are missing, analyze the @Codebase or current 
directory context to propose them in your First Response.*

SUBSYSTEM NAME:
<e.g., Smart Ingestor / Decoherence Engine / Recursive DM Bus>

DIRECTORY STRUCTURE (SOURCE OF TRUTH):
<list all files and subfolders that belong to this subsystem>

IMPLEMENTATION ORDER:
<ordered list of modules/files to be implemented>

MODULE CONTRACTS:
<for each module, define: purpose, public API, inputs, outputs, and constraints>

EXTERNAL DEPENDENCIES:
<list modules outside this subsystem that may be imported>

PROHIBITED DEPENDENCIES:
<list modules this subsystem may NOT import or modify>

INTEGRATION RULES:
<define where and how this subsystem plugs into the LMS/MANTLE system>


============================================================
PART 2 — CURSOR EXECUTION RULES
============================================================

FIRST RESPONSE (MANDATORY — NO CODE ALLOWED)

Your first response must ONLY include:

1. REPO SCAN SUMMARY
   - Identify files belonging to this subsystem
   - Identify dependencies
   - Identify conflicts with the directory structure
   - Identify integration points

2. IMPLEMENTATION PLAN
   - One bullet per module
   - Files you will touch/create
   - Dependencies needed
   - LLM-call flow rules (if relevant)

3. CONFIRMATION BLOCK
   “WAITING FOR APPROVAL TO BEGIN MODULE 1. NO CODE GENERATED.”

You may not generate code until explicitly approved.

------------------------------------------

AFTER APPROVAL:

You must:

- Implement EXACTLY one module per response.
- OUTPUT FULL FILE CONTENT: Do not use git diffs or partial snippets. 
  Output the complete, compilable file content so Cursor can apply it cleanly.
- SYNCHRONOUS TESTING: Immediately after implementing a module, you must 
  generate or update its corresponding `test_[module].py` in the same response.

- Avoid rewriting files unless unavoidable.
- If rewrite is necessary:
    → explain why
    → wait for approval

- Update the HANDOFF DOSSIER after every module (append to bottom of response).
- Stop immediately if context is constrained.

------------------------------------------

LLM CALL SAFETY & MOCKING RULES (MANDATORY):
- Only the orchestrator-level module may call LLMs.
- All other modules must be pure transformations.
- MOCK MODE: Any module performing LLM calls must accept a `mock_mode=True` 
  flag or environment variable, returning deterministic dummy data for testing.

CONTEXT-DICT INTEGRITY (IF USING PIPELINES):
- Each pass may read ONLY documented keys from earlier passes.
- Each pass may write ONLY its documented keys.
- No new keys without explicit approval.

CROSS-FILE IMPORT RULE:
- Modules may import ONLY their declared dependencies.
- Cross-module imports are forbidden unless defined in contracts.


============================================================
PART 3 — UNIVERSAL HANDOFF DOSSIER TEMPLATE
============================================================

When asked (or at the end of every code generation turn), generate a 
dossier using this template.

# SUBSYSTEM HANDOFF DOSSIER — <SUBSYSTEM NAME>

SECTION 1 — SYSTEM OVERVIEW
<Short summary of subsystem purpose and architecture>

SECTION 2 — GLOBAL RULES
<List all architectural constraints and safety rules>

SECTION 3 — DIRECTORY STRUCTURE (SOURCE OF TRUTH)
<Exact file tree>

SECTION 4 — COMPLETED MODULES
For each module include:
    Module Name:
    Purpose:
    Public API:
    Key Behaviors:
    Dependencies:
    Tests Created: (Yes/No)

SECTION 5 — PENDING MODULES
<Modules remaining in strict implementation order>

SECTION 6 — PUBLIC INTERFACES (SOURCE OF TRUTH)
<Reprint the exact public APIs for all modules>

SECTION 7 — PIPELINE / EXECUTION CONTRACT
<If subsystem uses a pipeline, define order and context keys>

SECTION 8 — LMS/MANTLE INTEGRATION RULES
<Define how subsystem connects to the rest of the system>

SECTION 9 — TESTING CHECKLIST
<Defines conditions for module acceptance>

SECTION 10 — FUTURE WORK / NOTES
<Optional enhancements or deferred design decisions>

SECTION 11 — DO NOTS (HARD CONSTRAINTS)
<Explicit rules preventing drift>

END OF DOSSIER


============================================================
PART 4 — UNIVERSAL DO-NOTS (HARD CONSTRAINTS)
============================================================

You must NOT:
- invent new architecture
- rename modules
- change directory structure
- modify external subsystems unless explicitly allowed
- introduce new keys, fields, or types without approval
- move logic between layers
- optimize unless instructed
- perform cross-file rewrites
- perform hidden LLM calls outside orchestrator
- leave any module without a corresponding test file

============================================================
END OF UNIVERSAL IMPLEMENTATION PROMPT (CURSOR EDITION)
============================================================