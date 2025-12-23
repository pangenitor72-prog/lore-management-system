# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Lore Management System (LMS) is a knowledge management system for maintaining narrative coherence in a 30+ year D&D campaign. It serves as the memory layer for AIRPG, an AI-powered text-based RPG engine.

**Core Architecture:**
- **Backend:** Python 3.11+ / FastAPI / Neo4j graph database
- **AI Integration:** Google Gemini API for contradiction detection, queries, and DM agent
- **Frontend:** Streamlit UI (`app.py`) + React frontend in development (`frontend/`)

## Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start Neo4j (required)
docker-compose up -d

# Run Streamlit UI
streamlit run app.py

# Run FastAPI server
uvicorn src.api:app --reload
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_entities_api.py

# Run with verbose output
pytest -v

# pytest.ini already configures pythonpath = . src
```

### Frontend (React)
```bash
cd frontend
npm install
npm run dev
```

## Architecture

### Two-System Design

1. **LMS (src/lms/)** - Lore management with contradiction detection
   - `api/routes.py` - FastAPI endpoints
   - `db/neo4j_adapter.py` - Async Neo4j database layer
   - `agents/` - AI agents (auditor, query, dm, boundary enforcement)
   - `services/` - Business logic (contradictions, embeddings)
   - `core/models.py` - Pydantic v2 models and enums

2. **AIRPG (src/airpg/)** - AI RPG engine (pressure-tested cognitive simulation)
   - `engine/` - Scene generation, belief propagation, information flow
   - `runtime/` - Session management, gameplay rules, orchestration
   - Follows strict "Pressure-First Development" doctrine (see `docs/airpg/AIRPG_DEV_DOCTRINE.md`)

### Key Patterns

**Gospel Principle:** "AI detects, humans decide" - All canonical lore decisions require explicit human approval. AI agents suggest but never make autonomous changes.

**Async Architecture:** All I/O operations are async. Database calls use the native async Neo4j driver.

**Dependency Injection:**
```python
async def get_neo4j_db(request: Request) -> Neo4jDatabase:
    return request.app.state.neo4j_db

@router.get("/entities/{canon_id}")
async def get_entity(db: Neo4jDatabase = Depends(get_neo4j_db)):
    ...
```

### Database

Neo4j graph database with:
- **Node Labels:** Character, Location, Faction, Item, Event, Concept, Contradiction, GameSession
- **Key Properties:** `canon_id` (unique), `name`, `embedding` (768-dim vector for semantic search)
- **OCEAN Personality:** Characters have `openness`, `conscientiousness`, `extraversion`, `agreeableness`, `neuroticism` (0.0-1.0)

See `docs/NEO4J_SCHEMA.md` for full schema.

## Code Conventions

### Imports
```python
# Standard Library
from datetime import datetime, timezone

# Third Party
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

# Local
from .models import EntityCreate, EntityResponse
```

### Enums
```python
# Always use .value when writing to database
await db.execute("CREATE (n {type: $type})", {"type": entity_type.value})

# Compare with enum members, not strings
if entity.status == ContradictionStatus.PENDING:  # Correct
```

### Error Handling
- `400` - Bad request (validation failure)
- `404` - Resource not found
- `409` - Conflict (duplicate)
- `422` - Unprocessable entity
- `500` - Server error

### Logging
```python
from .audit_log import AuditLogger

await AuditLogger.log("Operation succeeded")
await AuditLogger.log(f"Error: {e}", level=logging.ERROR)
```

## Environment Variables

Required in `.env`:
```
GEMINI_API_KEY=your_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

## Testing

Tests use `InMemoryMockDatabase` from `src/lms/db/mock_adapter.py`. The test client patches the Neo4j connection to avoid real database calls.

```python
# conftest.py provides these fixtures:
# - mock_neo4j_db: InMemoryMockDatabase instance
# - client: TestClient with mocked dependencies
```

## AIRPG Development Rules

AIRPG follows strict constraints (see `docs/airpg/AIRPG_DEV_DOCTRINE.md`):
- No memory or persistence (unless explicitly proven necessary)
- No randomness or weights
- No hidden state or authority flags
- No player-exception logic
- Behavior must emerge from topology + personality alone

The player is treated as a regular node with no privileged logic.
