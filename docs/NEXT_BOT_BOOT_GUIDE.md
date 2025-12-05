📘 NEXT_BOT_BOOT_GUIDE.md

AIRPG / LMS — ENGINEER BOOTSTRAP GUIDE (Hardening Phase Start)

Owner: Shawn
Author: Metis
Date: 2025-12-03
Purpose: Provide a complete startup brain for the next AI engineer.


---

🧭 1. PROJECT PURPOSE

You are working on LMS/MANTLE/AIRPG, a multi-agent storytelling engine built on:

Neo4j Knowledge Graph

Vector Search + Embeddings

Gemini AI (Flash + Pro)

DM Agent Runtime

Rule-Based + Semantic Contradiction Auditing


The system must support:

Dynamic world simulation

AI DM that enforces world coherence

Automatic contradiction detection

Future Decoherence Engine (Temporal resolution)

Smart Ingestor (multi-pass document ingestion)


You are currently entering the Hardening Phase, not the expansion phase.


---

🧱 2. CURRENT SYSTEM STATUS (as of last engineer)

✔️ Working & Stable

AuditorAgent

RuleBasedAuditor

SemanticAuditor (cleaned + corrected model handles)

ContradictionService

QueryAgent (now using VectorService)

Vector search now restored and functional

Merge conflicts fully resolved

Copilot audit passes with no critical warnings

System compiles


🟡 Partially Working / Needs Structure

Ingestor: legacy architecture

MANTLE runtime mixed with legacy agents

Architecture currently split across:

app.py (old Streamlit residue)

src/services/

src/api/

src/agents/



🔴 Critical Risk: Silent Failure

neo4j_adapter.py still returns [] on DB error with no exception.

This is the most dangerous bug in the system.


---

🔥 3. ABSOLUTE DO-NOT-TOUCH ZONES

The next engineer must not modify these without explicit permission from Shawn:

🚫 Entity Factory Templates

🚫 OCEAN personality model

🚫 Auditor architecture (Rule-based + Semantic split)

🚫 QueryAgent retrieval tiers (Agentic → Vector → Reverse → Keyword)

🚫 System-prompts under src/prompts/

These define AIRPG's behavior guarantees.


---

🎯 4. HARDENING PHASE: PRIMARY OBJECTIVES

This is the only work the next engineer should do.

Objective 1 — Fix Neo4j Silent Failure

File: src/db/neo4j_adapter.py

Required:

Add structured logging on exceptions

Re-raise exception

Never return empty lists on failure

Provide diagnostic context


This prevents invisible world corruption.


---

Objective 2 — Create Shared Utilities Module

Add:

src/core/utils.py

Populate with:

sanitize_string

normalize_properties

prune_nulls

deepclean_dict

safe_json


Replace repeated logic in services and auditors with imports from this file.


---

Objective 3 — Begin Architecture Unification

Move logic out of:

app.py

Into:

src/api/
src/services/
src/core/utils.py
src/mantle_runtime/  (create this folder if missing)

Do this gradually — small diffs only.


---

🔍 5. FILES THE NEXT BOT MUST REVIEW BEFORE TOUCHING ANYTHING

Mandatory reading:

AUDIT_DOSSIER.md

CHANGE_SET_SUMMARY.md

STARTUP_HANDOFF_BLOCK.md

This guide (NEXT_BOT_BOOT_GUIDE.md)

src/db/neo4j_adapter.py

src/services/contradiction_service.py

src/auditor/semantic_auditor.py

src/auditor/rule_based_auditor.py

src/agents/dm_agent.py

.cursor/rules.md



---

🧠 6. DEVELOPMENT RULES (Cursor / CLI)

Rule 1 — Minimal Diffs

Small, safe patches only.

Rule 2 — No Architecture Drift

Do not rename modules or move files without explicit instruction.

Rule 3 — No Unsolicited New Features

Hardening Phase ≠ Expansion Phase.

Rule 4 — Always Consider Async Boundaries

DM Agent and Auditor mix sync + async logging — changes must respect this.


---

🧩 7. NEXT TASK FOR THE NEXT ENGINEER

Task 1 (Required):

Fix silent failure in Neo4jDatabase.

Task 2 (Recommended):

Add logging, retry strategy, and exceptions where needed.

Task 3 (Secondary):

Create src/core/utils.py and refactor shared functions.

Task 4 (Optional After Above):

Start minor cleanup in app.py.


---

🚀 8. WHEN THE NEXT BOT CAN DECLARE SUCCESS

All of the following must be true:

DB exceptions propagate correctly

utils.py is created and used in at least one module

app.py has no world-logic

Sanity tests pass for:

QueryAgent

AuditorAgent

VectorService

neo4j_adapter



Only then may the next engineer move to expansion (Decoherence Engine, Smart Ingestor v2, etc.)


---

🧷 9. FINAL NOTES FOR THE NEXT AGENT

Shawn is experienced enough now that clarity matters more than simplicity.

Do not hide errors from him.

Do not auto-refactor.

Do not modify prompts without explicit permission.

Keep every change reversible and auditable.


You are here to stabilize a complex architecture, not rebuild it.


---

✅ End of NEXT_BOT_BOOT_GUIDE.md


---