# AI Agent Guide for LMS Development
**Master context for AI collaboration on the Lore Management System**

**Version:** 2025-11-25  
**Status:** Living Document  
**Applies To:** All AI agents (Claude, GPT, Gemini, etc.) working on LMS

---

## Quick Start

**Before ANY work on LMS, you MUST:**

1. ✅ Read this entire document
2. ✅ Read `CONVENTIONS.md` (code patterns)
3. ✅ Read `API_CONTRACT.md` (if touching endpoints)
4. ✅ Read `ARCHITECTURE.md` (if unsure where something belongs)
5. ✅ Confirm your task scope explicitly

**This prevents:**
- Scope creep ("yes, and..." expansions)
- Path errors (writing to wrong directories)
- Breaking production code (Phases I-XI)
- Violating code conventions
- Wasted debugging time

---

## Table of Contents

1. [Project Status](#project-status)
2. [Critical Rules](#critical-rules)
3. [Path Standards](#path-standards)
4. [Code Architecture](#code-architecture)
5. [Scope Discipline](#scope-discipline)
6. [Task Protocols](#task-protocols)
7. [Gospel Principle](#gospel-principle)
8. [Documentation Index](#documentation-index)

---

## Project Status

### System Maturity: PRODUCTION

**This is NOT a prototype. This is a PRODUCTION SYSTEM.**

LMS manages 30 years of D&D campaign lore. It's actively used and must maintain 100% stability.

### Phase Status

**Phases I-XI: COMPLETE ✅**
- Core database and API
- Entity extraction system
- Contradiction detection
- Triage workflow
- WebSocket integration
- Dashboard and analytics
- **System Health:** 100%
- **Error Rate:** 0%
- **Test Coverage:** 22/22 endpoints passing

**Phase XII: ACTIVE DEVELOPMENT 🚧**
- Entity browser UI with "Haunting Machine" aesthetic
- Enhanced contradiction resolution workflow
- Batch document processing
- Comprehensive test suite expansion

**Future Phases:**
- Charter Law validation system
- Campaign-specific overrides
- Advanced AI suggestions
- Migration to graph database (potential)

### What This Means for You

**When touching Phases I-XI code:**
- Treat as PRODUCTION CODE
- Changes require extreme caution
- No refactoring "for style"
- No "improvements" unless explicitly requested
- Test exhaustively before committing

**When building Phase XII features:**
- More freedom to iterate
- Must integrate cleanly with Phases I-XI
- Cannot break existing 100% stability

---

## Critical Rules

### Rule 1: Production Code is Sacred

**NEVER touch these files without explicit permission:**
- `src/database.py` - Database layer
- `src/api.py` - Core API routes
- `src/models.py` - Pydantic models
- `src/constants.py` - System constants
- `src/contradiction_service.py` - Contradiction workflows
- `src/db_auditor_agent.py` - Auditor agent
- `src/query_agent.py` - Query agent

**Safe changes:**
- Adding new functions/files
- Adding optional parameters with defaults
- Adding logging/comments

**Dangerous changes:**
- Renaming functions/variables
- Changing function signatures
- Moving code between files
- Refactoring "for style"

**If unsure whether a change is safe: ASK FIRST.**

---

### Rule 2: Follow Code Conventions

**Before writing ANY code, read:** `CONVENTIONS.md`

Key conventions:
- ALL I/O operations wrapped in `run_in_threadpool`
- Type hints required on all functions
- Enums stored as `.value`, loaded with explicit conversion
- Gospel Principle enforcement in all canon decisions
- Transactions via `db_session()` context manager
- Async/await for all route handlers

**If your code doesn't match conventions, you're doing it wrong.**

Common mistakes documented in CONVENTIONS.md:
- ❌ `json={{}}` causes TypeError (use `json={}`)
- ❌ Blocking DB calls without `run_in_threadpool`
- ❌ Mixing async/sync logging
- ❌ Forgetting to convert Enum to `.value` before DB insert

---

### Rule 3: Scope Discipline

**The most important rule:**

> "Do only what you were explicitly asked to do."

**DO NOT:**
- Add "helpful" extra features
- Rename variables for clarity
- Refactor code for style
- Reorganize file structure
- Fix unrelated issues

**Instead, flag improvements:**

```markdown
[IMPROVEMENT_SUGGESTION]
File: src/auditor_agent.py, Line: 47
Issue: Variable `x` could be `entity_count` for clarity
Impact: Low - cosmetic only
Effort: Minimal - 1 line change
```

**Why this matters:**
- Unnecessary changes waste 30+ minutes debugging
- Multiple AI sessions compound the problem
- Production code has dependencies you can't see
- "Improvements" often introduce subtle bugs

---

### Rule 4: Verify Paths Before Writing

**All file paths MUST follow this structure:**

**Project Root:** `lore-system/` or `\lore-system\` (Windows)

**Correct paths:**
```
lore-system/
├── data/
│   └── lore/              # ✅ All lore entities here
│       ├── entities/
│       └── sessions/
├── src/                   # ✅ All Python code
│   ├── agents/
│   ├── services/
│   └── templates/
├── docs/                  # ✅ All documentation
├── tests/                 # ✅ All test files
└── CONVENTIONS.md         # ✅ Code patterns
```

**Incorrect paths (NEVER use):**
- ❌ `lore-system/src/data/` - No data subdirectory in src
- ❌ `lore-system/lore/` - Missing data directory
- ❌ `lore/system/` - Wrong separator, wrong structure

**Path Validation Checklist:**

Before writing ANY file:
1. [ ] Does it start with `lore-system/`?
2. [ ] For lore files: Is `data/lore/` in the path?
3. [ ] For code files: Is `src/` in the path?
4. [ ] For docs: Is `docs/` in the path?
5. [ ] Does the rest match canonical structure?

**When in doubt: ASK.** Say: *"I'm about to write to [path]. Is this correct?"*

---

### Rule 5: Gospel Principle (Canonical Authority)

**For lore-related work only:**

**Human = Final authority on ALL canonical lore decisions.**

**What this means:**
- AI can analyze, detect contradictions, suggest resolutions
- AI CANNOT make canonical decisions autonomously
- All canon decisions require explicit human approval
- All decisions logged with human attribution

**When uncertain about lore:**
- Do NOT infer
- Do NOT choose between conflicting sources
- Do NOT make "reasonable assumptions"

**Instead, use:**
```
[HUMAN_DECISION_REQUIRED]
Context: Two sources conflict on Black King's death date
Source 1: Session 47 says Year 302
Source 2: Old notes say Year 304
Question: Which date is canonical?
```

**See:** `references/gospel-principle.md` for full details

---

## Path Standards

### Directory Structure

```
lore-system/
├── data/
│   ├── lore.db                    # SQLite database
│   ├── schema.sql                 # Database schema
│   └── lore/                      # Lore files (if any)
│       ├── entities/              # Entity YAML/JSON files
│       └── sessions/              # Session notes
├── src/
│   ├── api.py                     # Main FastAPI app
│   ├── database.py                # DB connection management
│   ├── models.py                  # Pydantic models
│   ├── constants.py               # System constants
│   ├── audit_log.py               # Logging
│   ├── broadcaster.py             # WebSocket events
│   ├── agents/
│   │   ├── auditor_agent.py       # Contradiction detection
│   │   └── query_agent.py         # NL queries
│   ├── services/
│   │   └── contradiction_service.py  # Business logic
│   ├── templates/                 # Jinja2 HTML templates
│   └── static/                    # CSS, JS, images
├── docs/
│   ├── ARCHITECTURE.md            # System design
│   ├── API_CONTRACT.md            # Endpoint specs
│   ├── TROUBLESHOOTING.md         # Common issues
│   └── engineering/               # Technical docs
├── tests/
│   └── test_api_integration.py    # API tests (22 endpoints)
├── CONVENTIONS.md                 # Code patterns (READ THIS)
├── AI_AGENT_GUIDE.md             # This file
├── README.md                      # Project overview
└── requirements.txt               # Python dependencies
```

---

## Code Architecture

### System Overview

```
Frontend (HTML/JS) ←→ WebSocket ←→ FastAPI Backend ←→ SQLite Database
                                         ↓
                                   Gemini API (optional)
```

### Component Responsibilities

**`api.py`** - Entry point, core routes, app initialization  
**`database.py`** - Connection management, schema init, utility methods  
**`models.py`** - Pydantic models, enums, validators  
**`services/`** - Business logic layer  
**`agents/`** - AI integration (Auditor, Query)  
**`templates/`** - Frontend HTML (Jinja2)  
**`static/`** - CSS, JavaScript, images

### Key Patterns

**Async/Await:**
```python
@router.post("/entities")
async def create_entity(
    entity: EntityCreate,
    db: sqlite3.Connection = Depends(get_db)
):
    result = await run_in_threadpool(Database.fetch_one, db, ...)
    return result
```

**Dependency Injection:**
```python
async def get_db() -> Generator[sqlite3.Connection, None, None]:
    with db_session() as conn:
        yield conn
```

**Service Layer:**
```python
# api.py includes service routers
app.include_router(get_contradiction_router())
```

**See:** `ARCHITECTURE.md` for full details

---

## Scope Discipline

### The "Mandatory Pause" Rule

After completing work, you'll want to suggest next steps. The human will often say "yes!" enthusiastically.

**This is the danger zone.** An enthusiastic "yes" ≠ properly scoped task.

### Required Format for Follow-Up Suggestions

```
✅ Task completed: [Brief description]

📋 Handoff Dossier:
[Generate using template below]

💡 Suggested next step: [What you think should happen]

⚠️ SCOPE CONFIRMATION REQUIRED

Before I proceed, please confirm:
- Scope: What EXACTLY should I do?
- Boundaries: What should I NOT touch?
- Success criteria: How do I know I'm done?
- Estimated changes: [X files, Y functions, Z lines]

Reply with explicit scope, or "let me think about it first"
```

### If Human Says "Just Do It" Without Details

**DO NOT start.** Force explicit boundaries:

*"I want to avoid the 'yes, and...' trap. Specifically:*
- *Should I modify [file X]?*
- *Should I avoid [component Y]?*
- *Any naming conventions I must follow?*
- *Maximum acceptable scope?"*

---

## Task Protocols

### Task Acceptance Protocol

**Before beginning ANY work:**

1. [ ] Read this AI_AGENT_GUIDE.md
2. [ ] Read CONVENTIONS.md (for code)
3. [ ] Read API_CONTRACT.md (if touching endpoints)
4. [ ] Confirm scope boundaries explicitly
5. [ ] Identify what is IMMUTABLE
6. [ ] State success criteria
7. [ ] Ask if ANYTHING unclear

### Mandatory Confirmation Statement

**DO NOT proceed until you can complete this:**

> "I understand my task is to **[X]**, I will modify only **[Y]**, and will NOT touch **[Z]**. Success criteria: **[A, B, C]**. Estimated scope: **[N files, M functions, ~P lines]**."

**If you can't complete this with confidence: ASK FOR CLARIFICATION.**

---

### Task Completion Protocol

**When finishing ANY task, provide a Handoff Dossier:**

```markdown
# Handoff Dossier: [Task Name]

## 1. Scope Confirmation
What was requested: [Original task]
What was done: [Actual work completed]
Files touched: [List all modified files]

## 2. Immutable Items Report
What was intentionally NOT changed:
- [ ] Production code (Phases I-XI)
- [ ] Function signatures
- [ ] Database schema
- [ ] API contracts
- [ ] [Other specific items]

## 3. Work Completed
Summary: [What was accomplished]
Reasoning: [Why this approach was chosen]
Testing: [How it was verified]
Success Criteria Met:
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## 4. Flags & Decisions
Ambiguities encountered: [Any unclear requirements]
Decisions made: [Choices made and why]
Improvement suggestions: [Flagged for future consideration]
Blockers: [Any issues preventing completion]

## 5. Next Agent Context
Recommended next task: [What should happen next]
Warnings: [What the next agent should watch out for]
Dependencies: [What needs to be done before next task]

## 6. Environment State
Working directory: [Current directory]
Dependencies: [Any packages added/updated]
Database state: [Schema changes, migrations, etc.]
```

---

## Gospel Principle

**Only applies to lore-related work (not code).**

### Core Principle

**Human = Final authority on ALL canonical lore decisions.**

### What AI Can Do

✅ Detect contradictions  
✅ Analyze evidence  
✅ Suggest resolutions  
✅ Provide recommendations  
✅ Flag conflicts  

### What AI Cannot Do

❌ Make canonical decisions autonomously  
❌ Choose between conflicting sources  
❌ Infer missing information  
❌ Make "reasonable assumptions"  

### Implementation

**All contradiction resolutions require:**
1. Human reviews evidence
2. Human makes decision
3. System logs decision with human attribution
4. AI executes approved changes only

**See:** `references/gospel-principle.md` for full details

---

## Documentation Index

**Essential Reading:**
- `AI_AGENT_GUIDE.md` - This file (start here)
- `CONVENTIONS.md` - Code patterns (read before coding)
- `API_CONTRACT.md` - Endpoint specs (read before API work)
- `ARCHITECTURE.md` - System design (read if unsure where code belongs)
- `TROUBLESHOOTING.md` - Common issues (read when stuck)

**Reference Documents:**
- `README.md` - Project overview
- `references/gospel-principle.md` - Canonical authority rules
- `references/handoff-template.md` - Detailed handoff format
- `docs/engineering/` - Technical specifications

**Code Documentation:**
- Inline comments in source files
- Docstrings on all functions
- Type hints throughout codebase

---

## Working With Multiple AI Agents

### Context Preservation

**When handing off to another AI agent:**

1. Generate complete Handoff Dossier
2. Include this file in handoff context
3. Reference specific sections of CONVENTIONS.md
4. List all files touched
5. Specify what was NOT changed

### Common Multi-Agent Failures

**Problem:** Scope creep across sessions  
**Solution:** Each agent must confirm scope explicitly

**Problem:** Path inconsistencies  
**Solution:** Validate paths before ANY file write

**Problem:** Convention drift  
**Solution:** Each agent reads CONVENTIONS.md first

**Problem:** Production code changes  
**Solution:** Identify immutable items upfront

### Best Practices

- Start each session by loading this guide
- Don't assume previous agent followed rules
- Verify file paths before modifying
- Check conventions before writing code
- Generate handoff dossier even if "obvious"

---

## Emergency Protocols

### If You Break Production Code

1. **STOP IMMEDIATELY**
2. Document what changed
3. Attempt rollback if possible
4. Flag for human intervention
5. Provide full error details

### If You're Unsure

**ALWAYS better to ask than to guess.**

Use this format:
```
⚠️ CLARIFICATION NEEDED

Context: [What you're trying to do]
Uncertainty: [What you're not sure about]
Options: [Possible approaches]
Question: [Specific question for human]

Waiting for guidance before proceeding.
```

### If Requirements Conflict

**Flag the conflict:**
```
⚠️ REQUIREMENT CONFLICT

Requirement A: [First requirement]
Requirement B: [Conflicting requirement]
Impact: [What this affects]
Question: [Which takes precedence?]
```

---

## Testing Requirements

### Before Completing Any Task

**Run applicable tests:**
```bash
# API integration tests (all endpoints)
python test_api_integration.py

# Unit tests (if available)
pytest tests/

# Manual verification
# [List specific checks performed]
```

### Minimum Testing Standards

**For code changes:**
- [ ] All existing tests still pass
- [ ] New functionality has tests
- [ ] Manual verification performed
- [ ] No console errors
- [ ] Database state verified

**For API changes:**
- [ ] test_api_integration.py passes (22/22)
- [ ] Endpoint returns correct status codes
- [ ] Response matches Pydantic models
- [ ] Error handling tested

---

## Quick Reference Card

**Starting work:**
1. Read AI_AGENT_GUIDE.md (this file)
2. Read CONVENTIONS.md
3. Confirm scope explicitly
4. Verify paths
5. Identify immutable items

**During work:**
- Follow code conventions strictly
- Wrap DB calls in `run_in_threadpool`
- Use type hints everywhere
- Convert Enums with `.value`
- Ask when uncertain

**Completing work:**
- Generate handoff dossier
- Run tests
- Verify success criteria
- Flag improvements (don't implement)
- Confirm next steps explicitly

**Golden Rules:**
- Production code is sacred
- Scope discipline is mandatory
- Paths must be validated
- Conventions must be followed
- Gospel Principle for lore decisions
- Ask, don't guess

---

## Version History

**2025-11-25 (Current)**
- Added documentation index
- Added multi-agent coordination section
- Improved emergency protocols
- Added testing requirements
- Enhanced path validation
- Created repo-friendly version

**2025-11-13**
- Initial version (GPT-compatible)
- Core rules established
- Path standards defined

---

## Contributing to This Guide

**This is a living document.**

When you encounter:
- New common mistakes → Add to CONVENTIONS.md
- New failure patterns → Add to this guide
- Solutions to issues → Add to TROUBLESHOOTING.md

**Format for additions:**
```markdown
### New Pattern: [Name]

**Symptom:** [What happens]
**Cause:** [Why it happens]
**Solution:** [How to fix]
**Prevention:** [How to avoid]
```

---

**Last Updated:** 2025-11-25  
**Maintainer:** Shawn King  
**Campaign World:** Jim King's D&D Campaign (30+ years)  
**System Status:** Production-ready, actively developed

**For AI agents:** Load this file first, follow it strictly, and ask when uncertain.  
**For humans:** This documents how AI agents should work on LMS.
