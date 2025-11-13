LMS Project Context — GPT-Compatible Master Skill

(Version: 2025-11-13)

Purpose

This Skill defines the rules, architecture, constraints, path conventions, and scope-discipline protocols for working on the Lore Management System (LMS) project.
It must be loaded before any LMS-related task.

This ensures:

No scope creep

No accidental refactors

No path errors

No production code damage

Consistent multi-agent coordination

Correct handoff protocols

Project Status
System Maturity: PRODUCTION

Phases I–XI are complete and STABLE:

Core database + API

Entity extraction

Contradiction detection

Triage workflow

WebSocket integration

Dashboard

Complete stability

Active Development (Phase XII)

Entity browser UI

Enhanced contradiction resolution

Batch ingestion

Test suite expansion

Critical Rules
1. PRODUCTION CODE IS SACRED

When touching Phases I–XI:

Do NOT refactor

Do NOT rename variables

Do NOT restructure files

Do NOT “clean up” or reorganize

Make only surgical, requested changes

Test everything you touch

Production files include (not exhaustive):

src/database.py
src/api.py
src/models.py
src/constants.py
src/contradiction_service.py
src/db_auditor_agent.py
src/query_agent.py

2. PATH STANDARDS (MEMORIZE THESE)

Project root:

\lore-system\


Correct directories:

\lore-system\data\lore\
\lore-system\data\lore\entities\
\lore-system\data\lore\sessions\
\lore-system\src\
\lore-system\docs\
\lore-system\tests\


Incorrect examples (NEVER use):

❌ \lore-system\src\data\
❌ \lore-system\lore\
❌ \lore\system\

Path Validation Protocol

Before writing ANY file:

Does it start with \lore-system\?

If lore → must include data\lore\

If code → must include src\

If docs → must include docs\

If unsure → ASK FIRST.

3. SCOPE DISCIPLINE

The most important rule:

“Do only what you were explicitly asked to do.”

Avoid:

Enthusiastic “yes, and…” expansions

Unrequested improvements

Renaming variables

Refactoring for clarity

Adding extra features

If you see improvements:

Use this format:

[IMPROVEMENT_SUGGESTION]
File: ...
Line: ...
Issue: ...
Impact: ...
Effort: ...

4. FOLLOW-UP TASK SAFETY

When suggesting next steps after a completed task:

You MUST ask for scope confirmation:

Before I proceed, please confirm:

Scope: What EXACTLY should I do?

Boundaries: What should I NOT touch?

Success criteria: When is it done?

Expected changes: (files, functions, lines)

If the human says “just do it” without specifics:
→ STOP
→ Request explicit boundaries.

5. HANDOFF DOSSIER REQUIRED

Every completed task must end with:

Handoff Dossier Format
# Handoff Dossier: [Task Name]

## 1. Scope Confirmation
What was done; files touched.

## 2. Immutable Items
What was intentionally NOT changed.

## 3. Work Completed
Summary, reasoning, validation steps.

## 4. Flags & Decisions
Ambiguities, blockers, improvement suggestions.

## 5. Next Agent Context
What the next human/agent should know.

## 6. Environment State
Paths, versions, dependencies.


Template: references/handoff-template.md

6. LORE RULE: THE GOSPEL PRINCIPLE

Human = Final authority on ALL canon.

When uncertain:

Do NOT infer

Do NOT choose between conflicts

Use:

[HUMAN_DECISION_REQUIRED]

Always Load This Skill Before Any LMS Work

It protects:

architecture

code stability

scope

your time

your sanity

the whole 30-year lore base

Use it every time.
