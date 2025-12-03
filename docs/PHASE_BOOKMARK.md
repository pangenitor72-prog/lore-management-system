⭐ PHASE BOOKMARK — LMS v2 CODEBASE AUDIT (Dec 2025)

Version: 1.0
Owner: Shawn
Purpose: Instant context restoration across chats


---

1. PROJECT IDENTITY

Project: Lore Management System (LMS) → evolving into MANTLE Runtime (AIRPG platform)

Architecture Level: v2 Subsystem Model (Smart Ingestor, Decoherence Engine, Query Engine, MANTLE Runtime)

Governance: .cursor/rules.md, UNIVERSAL_IMPLEMENTATION_PROMPT.md, per-subsystem contracts

Development Style: AI-assisted modular evolution with strict boundaries and diff-only updates



---

2. CURRENT WORK PHASE — FULL CODEBASE AUDIT

We are performing the LMS v2 Architectural Audit, goal:

> Assess the entire codebase subsystem-by-subsystem for correctness, safety, structure, drift, and upgrade readiness.



Rules:

No code changes unless they are trivial and safe

Subsystem-by-subsystem evaluation

Produce updates in three documents:

1. ARCHITECTURE_AUDIT_DOSSIER.md


2. IMPLEMENTATION_LOG.md


3. CHANGESET_SUMMARY.md





---

3. ACTIVE DOCUMENT STATES

3.1 ARCHITECTURE_AUDIT_DOSSIER.md (Current State)

Section 1 (Repo-level structure): PASS

Section 2 (Neo4j Adapter): FAIL

Missing TRY/EXCEPT around query execution

Silent failures due to swallowed exceptions

Vector index commands not confirmed via SHOW INDEXES

No driver cleanup guarantee in some failure paths

Sanitation functions too permissive

No explicit timeouts on driver operations


Pending sections:

Auditor subsystem

Query subsystem

API layer

Smart Ingestor

UI layer

DMAgent/AIRPG layer

Decoherence Engine placeholder

Deployment environment sanity check



3.2 IMPLEMENTATION_LOG.md (Current State)

Using Append-Only Block Model (AOBM)

Tracks:

Operations performed

Rationale

Side-effects

Subsystem affected


Next entry scheduled for the Neo4j adapter fixes (when implemented).


3.3 CHANGESET_SUMMARY.md (Current State)

Summarizes diffs applied per subsystem

Currently: no changes applied, pending code stabilization



---

4. DEVELOPMENT WORKFLOW

Audit Workflow

For each subsystem:
1. Identify boundaries
2. Classify concerns:
   - Architectural
   - Correctness
   - Performance
   - Security
   - Maintainability
3. Assign PASS / WARN / FAIL
4. Update audit dossier
5. Only implement immediate-safe fixes
6. Schedule deeper refactor into CHANGESET_SUMMARY

Subsystem Order

1. Repo topology ✔


2. Database Layer (Neo4j) ✔ FAIL


3. Auditor


4. Query Engine


5. API Layer


6. Smart Ingestor


7. UI Layer


8. DMAgent / Game Session


9. MANTLE Runtime / Decoherence placeholder


10. Deployment config (Docker + systemd + Nginx)




---

5. KEY ARCHITECTURAL RULES (V2)

Subsystems must have boundaries and orchestrators

Only orchestrators may call LLMs

Pure functions everywhere else

Dependency direction: low → high only

No drift allowed from CONTRACT or RULES

Governance documents serve as the canonical truth

Rollback is mandatory for each migration step



---

6. SPECIAL CONTEXT (SHOULD ALWAYS BE LOADED)

LMS is the canonical data layer for AIRPG

MANTLE Runtime will depend on:

Query Engine

Decoherence Engine

Smart Ingestor outputs

Canon graph in Neo4j


Major risk area: Decoherence Engine (novel architecture)

Smart Ingestor is the first subsystem to fully migrate to v2

We are currently only auditing, not refactoring



---

7. NEXT ACTION IN THE AUDIT

Continue with Subsystem 3: Auditor Layer

Tasks:

Scan src/agents/auditor_agent.py

Scan src/auditor/rule_based_auditor.py

Scan src/auditor/semantic_auditor.py

Identify architectural drift

Evaluate API shape for v2 compatibility

Update Dossier accordingly



---

8. LOADING INSTRUCTIONS

In any new chat, say:

“Load Phase Bookmark: LMS v2 Audit”
and paste this block.

I will automatically rehydrate:

State

Documents

Subsystem context

Audit flow

v2 architecture

All constraints and rules



---

9. CONFIRMATION

When loaded, I'll respond:

“Phase Bookmark Loaded: LMS v2 CODEBASE AUDIT is active.”