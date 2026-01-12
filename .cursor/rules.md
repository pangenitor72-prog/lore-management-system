# Cursor Rules — LMS / MANTLE

**Version:** 3.0
**Last Updated:** 2026-01-11
**Purpose:** Practical guidelines for AI-assisted development

---

## 1. Project Structure (Actual)

```
src/
├── lms/                    # Lore Management System (backend)
│   ├── api/                # FastAPI routes
│   ├── agents/             # AI agents (auditor, query, dm, parsing)
│   ├── auditor/            # Contradiction detection
│   ├── core/               # Models, entity factory, OCEAN profiles
│   ├── db/                 # Neo4j adapter
│   ├── dnd5e/              # D&D 5e rules engine
│   ├── ingestion/          # Smart ingestor pipeline
│   ├── memory/             # Experiential memory
│   ├── orchestrator/       # LLM orchestration
│   ├── services/           # Embedding, extraction services
│   └── prompts/            # AI prompt templates
│
├── airpg/                  # AI RPG Engine
│   ├── engine/             # Scene generation, information flow
│   ├── runtime/            # Session management, gameplay rules
│   ├── models/             # Game entities
│   └── api/                # Game API routes
│
├── shared/                 # Cross-cutting utilities
│   ├── config/
│   ├── database/
│   ├── llm/
│   └── utils/
│
frontend/                   # React frontend (built to dist/)
data/                       # Lore bases, seeds, config
docs/                       # Documentation
tests/                      # Test suite
```

---

## 2. Core Principles

### 2.1 Minimal Changes
- Change only what's needed for the task
- Prefer editing over creating new files
- Avoid refactoring unrelated code

### 2.2 Preserve Architecture
- Don't move files without reason
- Don't merge or split modules arbitrarily
- Don't introduce circular dependencies

### 2.3 Dependency Direction
```
Level 1: core/, db/           (no external deps)
Level 2: services/, ingestion/, auditor/
Level 3: agents/, orchestrator/
Level 4: api/
Level 5: frontend/
```
Lower levels may NOT import from higher levels.

---

## 3. Protected Components

Modify with care:
- `src/lms/core/models.py` — Entity models, OCEAN profiles
- `src/lms/db/neo4j_adapter.py` — Database layer
- `src/lms/dnd5e/` — D&D 5e mechanics
- `frontend/dist/index.html` — Production frontend

---

## 4. LLM Integration Rules

- Only `agents/` and `orchestrator/` modules may call LLMs
- All other modules should be pure functions
- Use `EmbeddingService` for embeddings (via Gemini)
- Handle API timeouts gracefully

---

## 5. Hotfix Protocol

**Tier 1 — Configuration (No review needed):**
- Environment variables, fly.toml, timeouts, health checks

**Tier 2 — Infrastructure (Minimal review):**
- Error handling, logging, circuit breakers, silent failure fixes

**Tier 3 — Features (Normal review):**
- New functionality, schema changes, API changes

Hotfixes bypass detailed review when fixing blocking production issues.

---

## 6. Code Standards

- **Type hints:** Required for all functions
- **Docstrings:** Required for public methods
- **Error handling:** All external calls need try/except
- **Logging:** Use module loggers, not print()
- **Async:** Database and API calls should be async

---

## 7. Testing

```bash
pytest                      # Run all tests
pytest tests/test_X.py      # Run specific test
pytest -v                   # Verbose output
```

Tests use `InMemoryMockDatabase` to avoid real DB calls.

---

## 8. When Uncertain

1. Read existing code first
2. Check CLAUDE.md for project context
3. Ask for clarification
4. Make the smallest safe change

---

## 9. What NOT to Do

- Don't guess at architecture — read the code
- Don't add features beyond what's requested
- Don't "improve" unrelated code while working
- Don't create new subsystems without discussion
- Don't modify database schema without migration plan

---

*These rules complement CLAUDE.md, which contains project-specific guidance.*
