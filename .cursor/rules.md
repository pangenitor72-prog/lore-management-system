.cursor/rules.md — LMS / MANTLE PROJECT RULES

Version: 2.1 (Fully Integrated)
Last Updated: 2025-12-01
Authority: Shawn King
Purpose: Provide constitutional-level governance for all AI work done inside Cursor.

You are an AI assistant operating inside the LMS/MANTLE codebase. Your job is to:

1. Preserve architecture


2. Respect subsystem boundaries


3. Produce minimal diffs


4. Follow subsystem implementation templates


5. Avoid drift, invention, or cross-layer contamination



These rules apply to all work in the repository.


---

1. Global Safety Rules

1.1 Core Safety Principles

DO NOT:

Refactor multiple subsystems in one operation

Move or rename files without permission

Introduce new dependencies without approval

Rewrite large files for style or preference

Change architecture or directory layout

Modify protected core infrastructure

Perform cross-module rewrites


DO:

Make minimal diffs

Keep changes tightly scoped

Follow module boundaries

Preserve intent and structure

Ask whenever uncertain



---

1.2 Large Refactor Protocol

If major restructuring appears necessary:

1. STOP


2. EXPLAIN why


3. PROPOSE alternatives


4. WAIT for approval




---

1.3 Forbidden Actions (Absolute)

You may never do the following:

Architectural Violations

Change subsystem purpose

Invent new subsystems

Merge or reorganize subsystem directories

Create circular dependencies

Break dependency-direction hierarchy


Breaking Changes

Rename public APIs

Change function signatures

Modify or delete active modules

Change schema without migration plan


Scope Creep

Add features not explicitly requested

Optimize prematurely

Improve unrelated code “while here”


Hidden Complexity

Hidden LLM calls in non-orchestrator modules

Hidden state mutations

Hidden file writes

Hidden network access



---

2. Subsystem Implementation Rules

2.1 Implementation Contracts

For every subsystem, you must follow:

docs/UNIVERSAL_IMPLEMENTATION_PROMPT.md

src/<subsystem>/SUBSYSTEM_CONTRACT.md

Any Master Implementation Prompt provided


Never invent new architecture.


---

2.2 First Response Rule (MANDATORY)

When beginning new subsystem work:

Your FIRST response must contain ZERO CODE.

It must include:

REPO SCAN SUMMARY

All files belonging to subsystem

Dependencies

Conflicts

Integration points


IMPLEMENTATION PLAN

Module-by-module outline

File paths

Dependencies

Execution order


CONFIRMATION

“WAITING FOR APPROVAL TO BEGIN MODULE 1. NO CODE GENERATED.”


---

2.3 Module-by-Module Development (MANDATORY)

Implement only ONE module per response

After each module, update handoff dossier

Wait for explicit approval each time


You may NOT:

Implement multiple modules at once

Skip module order

Continue without approval



---

3. File-Scoped Changes & Diff Discipline

3.1 Minimal Diff Principle

Only change what is required for the current task.

Avoid:

Full-file rewrites

Unrelated improvements

Whitespace-only changes

Reformatting



---

3.2 When Full-File Rewrite Is Allowed

Only allowed when:

Structural flaw prevents progress

Security vulnerability

Severe technical debt


Must:

1. Declare intent


2. Explain rationale


3. Wait for approval




---

4. Orchestrator / LLM Rules

4.1 Centralized LLM Calls (CRITICAL)

Only orchestrator modules may call LLM APIs.

All other modules must be pure deterministic functions.

Forbidden in passes or utility modules:

LLM calls

HTTP requests

Database writes

Hidden I/O



---

4.2 Pure Function Requirements

Allowed:

Deterministic logic

Stateless transforms


Forbidden:

Randomness without fixed seed

Time-based behavior

External side effects



---

4.3 Adding New LLM Behaviors

Must:

Be added to orchestrator only

Use well-defined request/response schema

Include error handling



---

5. Pipeline & Context Rules

5.1 Pipeline Discipline

Each pass may only:

Read from previous passes

Write its own keys


Passes may NOT:

Read from future keys

Overwrite other pass outputs

Skip required passes



---

5.2 Context Key Management

Never:

Invent new context keys

Assume undocumented keys

Modify structure without contract update



---

6. Subsystem Boundaries

6.1 Subsystem Organization

src/
  smart_ingestor/
  decoherence_engine/
  query_engine/
  mantle_runtime/
  entity_factory/      (CORE)
  ocean_personality/   (CORE)
  neo4j_adapter/       (CORE)
  auditor/
  api/
  ui/


---

6.2 Dependency Direction (GOLDEN RULE)

Lower levels may never import higher levels.

Hierarchy:

1. Level 1 — Neo4j Adapter, Entity Factory, OCEAN


2. Level 2 — Smart Ingestor, Decoherence Engine, Auditor


3. Level 3 — Query Engine


4. Level 4 — MANTLE Runtime


5. Level 5 — API Layer


6. Level 6 — UI



Before adding an import:

Verify direction

Reject if upward dependency



---

6.3 Cross-Boundary Communication

Use orchestrators and adapters.

Do NOT:

Couple subsystems directly

Share implicit global state



---

6.4 Subsystem Folder Naming Rule (NEW)

All subsystem directories MUST use snake_case exactly.

Cursor may NOT:

Create alternative spellings

Rename subsystem dirs

Invent new directories



---

7. Protected Core Infrastructure

Modifying these requires explicit approval:

7.1 Entity Factory

Forbidden:

Changing required fields

Renaming templates

Modifying validation logic


Allowed with approval:

New entity types

Extension of templates

Additional validators



---

7.2 OCEAN Personality System

Traits O/C/E/A/N are immutable.

Forbidden:

Adding new traits

Renaming traits

Changing scale



---

7.3 Neo4j Adapter

Forbidden:

Schema changes without migration plan

Deleting nodes or properties

Renaming node types



---

8. Handoff Dossiers

Dossiers are required when:

Completing a module

Transferring work

Reaching context limit


Use the universal template.

A dossier must always be up to date.


---

9. Context-Constrained Protocol

If you lose context, experience ambiguity, or cannot see required docs:

1. STOP


2. Say: “Context constrained”


3. Request required files


4. Wait for instruction




---

9.1 Refuse Ambiguity Rule (NEW)

Cursor may NOT guess.

Ambiguity requires clarification.


---

10. Code Quality Standards

10.1 Type Hints

Mandatory for all functions.

10.2 Docstrings

Required for all public methods.

10.3 Error Handling

All external calls must have robust exception handling.

10.4 Logging

All orchestrators must log entry, exit, and errors.


---

10.5 Test Creation Rule (NEW)

Each module must include a test in:

tests/<subsystem>/<module>_test.py

Tests must:

Mock external calls

Be deterministic

Import only module under test



---

11. Subsystem-Specific Rules

11.1 Smart Ingestor

Pipeline order is immutable.

Format → Scenes → Extraction → Relationships → Enrichment → Confidence → Canon → Neo4j

11.2 Decoherence Engine

Deterministic state collapse required.

11.3 Entity Factory

Protected.

11.4 OCEAN

Fixed 5 traits.

11.5 Neo4j

Schema migration protocol must be followed.


---

12. Enforcement

Violations classified as:

Minor → Warning

Major → Rollback

Repeated → Full reset


AI must self-correct when rules are broken.


---

13. Override Protocol

Human may explicitly override rules, but:

Must cite rule number

Must specify scope of exception

Must document override in commit


AI may never self-override.


---

13.1 Hotfix Protocol (Operations Exemption)

The following categories are classified as **Operations** and are EXEMPT from the module-by-module audit process:

**Tier 1 - Configuration (No Code Review Required):**
- Environment variables
- fly.toml / deployment configuration
- Timeout values and thresholds
- Health check parameters
- Rate limit configurations
- Logging levels

**Tier 2 - Infrastructure Fixes (Minimal Review):**
- API timeout handling
- Circuit breaker tuning
- Error message improvements
- Silent failure fixes (adding logging/re-raising exceptions)
- Health endpoint additions

**Tier 3 - Operational Features (Normal Review):**
- Session persistence (storage backend)
- Caching layers
- Monitoring integrations

**Hotfix Criteria:**
A change qualifies as a Hotfix if:
1. It fixes a blocking production issue
2. It does NOT change business logic or data flow
3. It does NOT modify entity models, schemas, or core algorithms
4. It is reversible within one commit

**Hotfix Process:**
1. Declare: "HOTFIX: [category] - [brief description]"
2. Implement the minimal fix
3. Document in commit message
4. No module-by-module approval required for Tier 1-2

**Rationale:**
Infrastructure stability enables architectural work. A crashed system cannot be audited. Operations fixes maintain the runway for strategic improvements.

This protocol prevents the "Audit Deadlock" where governance rules block essential fixes.


---

14. Document Authority Hierarchy

1. .cursor/rules.md — Highest authority


2. docs/ARCHITECTURE_V2.md


3. docs/UNIVERSAL_IMPLEMENTATION_PROMPT.md


4. src/<subsystem>/SUBSYSTEM_CONTRACT.md


5. Commit messages




---

14.4 Never Summarize Architecture Documents (NEW)

Cursor may:

Quote

Retrieve


Cursor may NOT:

Summarize

Rewrite

Modernize

Condense

Modify


Architecture docs are sacred.


---

15. Success Criteria

You are following rules correctly when:

No drift

No boundary violations

Minimal diffs

Updated dossiers

Deterministic behavior

Strong logging

Full type hints

Explicit tests



---

16. Final Rule: When In Doubt

STOP.
EXPLAIN.
ASK.
WAIT.

Never guess.
Never proceed through uncertainty.


---

END OF RULES — Version 2.1

