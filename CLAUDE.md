# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Lore Management System (LMS) is a knowledge management system for maintaining narrative coherence in a 30+ year D&D campaign. It serves as the memory layer for AIRPG, an AI-powered text-based RPG engine.

**Core Architecture:**
- **Backend:** Python 3.11+ / FastAPI / Neo4j graph database
- **AI Integration:** Google Gemini API for contradiction detection, queries, and DM agent
- **Frontend:** React (served from `frontend/dist/index.html`)
- **Rules Engine:** D&D 5e mechanics with visibility scaling (Storyteller → Tactician)

## The Narrow Path (Core Philosophy)

**The system doesn't matter. What matters is that the player believes the system matters. The real product is the story.**

### Why This Matters

Players need to believe their choices create outcomes. If they know the DM always makes it work out, success feels hollow. But if they believe:
- Their choices (stats, abilities, skills) created an advantage
- The system could have said no
- And it said YES

Then that success belongs to *them*. The dice are a ritual that transfers ownership from the DM to the player.

### The Narrow Path Problem

Every DM walks a tightrope:
- **Too much control** → Players feel like passengers. Victories are hollow.
- **Too much chaos** → Story falls apart. Deaths feel arbitrary. Investment gets punished.

Human DMs fudge dice, adjust HP, have enemies miss at dramatic moments. They lie constantly to maintain the illusion. This is hard. Even experienced DMs struggle with it.

### AI's Advantage

AI has absorbed millions of stories, player feedback, DM advice, narrative theory. It knows the *shape* of human satisfaction without explicit rules. It doesn't need a flowchart for "when to let the player win" - it understands what earned victories feel like.

### How To Leverage This

The implementation is a **context-gathering system**, not a rules engine:

| Signal | What It Reveals |
|--------|-----------------|
| Character choices | What fantasy they want |
| Actions taken | What they pursue |
| Questions asked | What they want to know more about |
| Things named | What they've claimed as theirs |
| Time lingered | What scenes they care about |

Feed this context to the AI with the goal: *"Honor their choices. Maintain tension. Make outcomes feel earned. Never get caught."*

Don't code rules for the narrow path. Give the AI rich context about player investment and trust its pattern-matched intuition.

### Working With The Project Creator

The creator thinks in intuitions, not specifications. They know when something is right by feel. When they struggle to articulate something, your job is to:
1. Read their signals (words, project context, priorities)
2. Synthesize into something coherent
3. Reflect it back: "Is this what you mean?"

They will recognize truth when they see it reflected back. This is the same capability the AI DM uses for players.

**See also:** `docs/airpg/THE_NARROW_PATH.md` for full philosophy, `docs/airpg/SESSION_INSIGHT_2026-01-13.md` for the conversation that led to these insights.

## Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start Neo4j (required)
docker-compose up -d

# Run FastAPI server (serves React frontend at http://localhost:8000)
uvicorn src.lms.api:app --reload
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
   - `api/` - FastAPI endpoints (routes.py, game_routes.py, dnd_routes.py, memory_routes.py)
   - `agents/` - AI agents (auditor, query, dm, boundary enforcement)
   - `arc/` - Story arc management (tension tracking, beat suggestions, episode management)
   - `auditor/` - Contradiction detection (rule-based + semantic auditors)
   - `core/` - Pydantic v2 models, enums, entity factory, OCEAN profiles, normalization
   - `db/` - Async Neo4j database layer (neo4j_adapter.py)
   - `dnd5e/` - D&D 5e rules engine (see below)
   - `guardrails/` - Circuit breaker, token budget management
   - `ingestion/` - Smart Ingestor pipeline (segment → detect → extract → personality → build → drift → embed → save)
   - `memory/` - Experiential memory (SQLite-backed session memory)
   - `orchestrator/` - LLM orchestration and CLI tools
   - `prompts/` - AI prompt templates (auditor, query, DM)
   - `services/` - Business logic (contradictions, embeddings, vector search, audit logging)
   - `suggestions/` - Action suggestion engine
   - `templates/` - HTML templates
   - `ui/` - UI utilities and API client

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
   - `data/` - Static game data (spells, equipment, backgrounds)

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
    *   Use CSS Variables from `frontend/src/styles/globals.css` for all colors.
    *   State management: Use React Context for global game state (Inventory, Turn Count).

**Visual Reference:**
*   **Colors:** Dark Slate (`#0f172a`), Neon Green (`#22c55e`), Warning Amber (`#f59e0b`).
*   **Typography:** Sans-serif for UI, Serif for Story, Monospace for Stats.
*   **Components:** Look at `AIRpg.css` for the "Card" and "Slot" styles. Mimic this density.
