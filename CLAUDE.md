# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Lore Management System (LMS) is a knowledge management system for maintaining narrative coherence in a 30+ year D&D campaign. It serves as the memory layer for AIRPG, an AI-powered text-based RPG engine.

**Core Architecture:**
- **Backend:** Python 3.11+ / FastAPI / Neo4j graph database
- **AI Integration:** Google Gemini API for contradiction detection, queries, and DM agent
- **Frontend:** React (served from `frontend/dist/index.html`)
- **Rules Engine:** D&D 5e mechanics with visibility scaling (Storyteller → Tactician)

## Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start Neo4j (required)
docker-compose up -d

# Run FastAPI server (serves React frontend at http://localhost:8000)
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

### System Architecture

1. **LMS (src/lms/)** - Lore management with contradiction detection
   - `api/` - FastAPI endpoints (routes.py, game_routes.py)
   - `db/neo4j_adapter.py` - Async Neo4j database layer
   - `agents/` - AI agents (auditor, query, dm, boundary enforcement)
   - `ingestion/` - Smart Ingestor pipeline (segment → detect → extract → personality → build → drift → embed → save)
   - `services/` - Business logic (contradictions, embeddings)
   - `core/models.py` - Pydantic v2 models and enums

2. **AIRPG (src/airpg/)** - AI RPG engine (pressure-tested cognitive simulation)
   - `engine/` - Scene generation, belief propagation, information flow
   - `runtime/` - Session management, gameplay rules, orchestration
   - Follows strict "Pressure-First Development" doctrine (see `docs/airpg/AIRPG_DEV_DOCTRINE.md`)

3. **Shared (src/shared/)** - Cross-cutting utilities
   - `config/` - Configuration management
   - `database/` - Database clients (neo4j_client.py)
   - `llm/` - LLM utilities
   - `utils/` - General utilities

4. **D&D 5e Rules (src/lms/dnd5e/)** - Mechanical rules layer
   - `models/` - Character sheets, abilities, races, classes, archetypes
   - `engine/` - Dice rolling, skill checks, combat resolution
   - `creation/` - Character creation flows (Concept, Guided, Classic)
   - `presentation/` - Visibility filtering (Storyteller → Tactician)

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

## UI/UX DESIGN SKILL
**Role:** You are an expert Frontend Engineer and UI Designer (Vercel/Linear style).
**Principles:**
1.  **"Juice" First:** Every interaction (click, roll, loot) must have visual feedback (toast, bounce, glow).
2.  **Mobile-First Pacing:** Interfaces must not be walls of text. Use Cards, Progress Bars, and Modals to break up content.
3.  **The "Tactical" Look:** Use borders, monospace fonts, and high-contrast accents to evoke a "Sci-Fi Terminal" or "RPG HUD" aesthetic.
4.  **Component Strategy:**
    *   Never put game logic in `App.jsx`. Use dedicated components (`GameClient`, `InventoryDrawer`).
    *   Use CSS Variables from `src/styles/tokens.css` for all colors.
    *   State management: Use React Context for global game state (Inventory, Turn Count).

**Visual Reference:**
*   **Colors:** Dark Slate (`#0f172a`), Neon Green (`#22c55e`), Warning Amber (`#f59e0b`).
*   **Typography:** Sans-serif for UI, Serif for Story, Monospace for Stats.
*   **Components:** Look at `AIRpg.css` for the "Card" and "Slot" styles. Mimic this density.
