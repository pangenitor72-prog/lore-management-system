# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Mantle** (formerly Lore Management System) is an AI-powered narrative RPG platform. It combines:
- A knowledge management system for maintaining narrative coherence
- An AI Dungeon Master powered by Google Gemini
- D&D 5e mechanics with visibility scaling (Storyteller → Tactician)

**Live Site:** https://lore-management-system.fly.dev/

**Core Stack:**
- **Backend:** Python 3.11+ / FastAPI / Neo4j graph database
- **AI:** Google Gemini API for entity extraction, queries, and DM agent
- **Frontend:** Static HTML/CSS/JS (production) + React (development prototype)
- **Deployment:** Fly.io

## Project Tree

```
lore-management-system/
├── CLAUDE.md                    # This file - AI assistant guidance
├── app.py                       # Application entry point
├── fly.toml                     # Fly.io deployment config
├── requirements.txt             # Python dependencies
├── pytest.ini                   # Test configuration
│
├── data/
│   ├── deployed_version.txt     # Current deployed version
│   ├── invite_codes.json        # Beta tester invite codes
│   ├── email_signups.json       # Update notification signups
│   ├── feedback.json            # User feedback
│   ├── session_logs.json        # Runtime session data
│   └── lore_bases/
│       ├── example_world.json   # Sample world data
│       ├── test_world.json      # Test world data
│       └── seeds/               # 20+ curated world seeds by genre
│           ├── fantasy_seeds.json
│           ├── horror_seeds.json
│           ├── scifi_seeds.json
│           └── ...
│
├── frontend/
│   ├── README.md                # Frontend architecture docs
│   ├── vite.config.js           # Vite config (outputs to dist-react/)
│   ├── dist/                    # PRODUCTION UI (static)
│   │   ├── index.html           # Main app (~17k lines, self-contained)
│   │   ├── sw.js                # Service worker (PWA)
│   │   ├── manifest.json        # PWA manifest
│   │   ├── assets/              # Built JS/CSS assets
│   │   ├── images/
│   │   │   └── raven.png        # Mascot image
│   │   └── icons/               # PWA icons
│   └── src/                     # React prototype (NOT production)
│       ├── App.jsx
│       ├── main.jsx
│       ├── components/          # React components
│       └── styles/
│           └── globals.css      # Design tokens
│
├── src/
│   ├── mantle/                  # Main application (unified from LMS + AIRPG)
│   │   ├── api/                 # FastAPI routes
│   │   │   ├── routes.py        # Main app setup & core routes
│   │   │   ├── game_routes.py   # Game session routes (/api/game/*)
│   │   │   ├── world_tuner_routes.py  # World Tuner endpoints
│   │   │   ├── dnd_routes.py    # D&D mechanics routes
│   │   │   ├── memory_routes.py # Memory system routes
│   │   │   └── orchestrator_routes.py # Orchestrator routes
│   │   ├── agents/              # AI agents
│   │   │   ├── dm_agent.py      # AI Dungeon Master
│   │   │   ├── world_tuner_agent.py   # Conversational world config
│   │   │   ├── query_agent.py   # Knowledge queries
│   │   │   ├── auditor_agent.py # Contradiction detection
│   │   │   └── lore_parsing_agent.py  # Entity extraction
│   │   ├── engine/              # Game engine (from AIRPG runtime)
│   │   │   ├── world_integrity.py     # Canon truths & world state
│   │   │   ├── game_config.py         # Game configuration
│   │   │   └── game_events.py         # Game events & inventory
│   │   ├── core/                # Core models
│   │   │   ├── models.py        # Pydantic v2 models
│   │   │   └── entity_factory.py
│   │   ├── db/                  # Database layer
│   │   │   ├── neo4j_adapter.py # Async Neo4j driver
│   │   │   └── mock_adapter.py  # In-memory mock for tests
│   │   ├── dnd5e/               # D&D 5e rules engine
│   │   │   ├── models/          # Character sheets, classes, races
│   │   │   ├── engine/          # Dice, checks, combat
│   │   │   ├── creation/        # Character creation flows
│   │   │   └── presentation/    # Visibility filtering
│   │   ├── ingestion/           # Lore ingestion pipeline
│   │   ├── memory/              # Session memory (SQLite)
│   │   └── services/            # Business logic
│   │
│   ├── archive/                 # Archived/experimental code
│   │   └── airpg_experimental/  # Original AIRPG belief propagation
│   │
│   └── shared/                  # Cross-cutting utilities (unused)
│
├── docs/
│   ├── airpg/                   # AIRPG philosophy & architecture
│   │   ├── THE_NARROW_PATH.md   # Core design philosophy
│   │   ├── AIRPG_DEV_DOCTRINE.md
│   │   └── VISION.md
│   ├── engineering/             # Technical docs
│   │   ├── DB_SCHEMA.md
│   │   └── TESTING_GUIDE.md
│   ├── JIM_WORLD_CREATOR_GUIDE.md  # User guide for world creation
│   ├── NEO4J_SCHEMA.md          # Database schema
│   └── archive/                 # Historical docs
│
└── tests/                       # Pytest test suite
```

## Current State (January 2026)

### Production Deployment
- **Environment:** DigitalOcean Ubuntu 22.04 LTS (Three-tier architecture)
- **Status:** Backend API & Neo4j 5.12 online; Frontend served via NGINX.
- **Pending:** SSL/HTTPS setup and UFW firewall lockdown.
- **Reference:** See `docs/DIGITAL_OCEAN_DEPLOYMENT.md` for the full handoff dossier.

### Design System: Obsidian & Gold
The production UI uses the **Obsidian & Gold** design system:
- **Colors:** Cooler blacks (#0f0f12, #16161a) with metallic gold (#D4AF37)
- **Typography:** Crimson Pro (narrative) + JetBrains Mono (UI)
- **Effects:** Noise texture overlay, inner depth shadows, subtle vignette
- **Radii:** Sharp corners (--radius-sharp: 4px, --radius-medium: 8px, --radius-soft: 12px)
- **Mascot:** Raven logo with oval gold frame

### Key Features
1. **World Creator** - Browse curated worlds or import your own lore
2. **File Explorer** - Drag & drop files/folders for lore import
3. **Human-in-the-Loop Entity Review** - AI extracts entities, humans approve
4. **Character Creation** - Guided flow with genre-specific options
5. **AI Dungeon Master** - Gemini-powered narrative generation
6. **Knowledge Graph** - Visual exploration of world entities

### Screens (in frontend/dist/index.html)
Search for `class="screen"` to find:
- `invite-code` - Beta access entry
- `playtester-welcome` - Welcome for testers
- `start` - Main landing with mode selection
- `world-builder` - World creation flow
- `ingest` - Lore import with file explorer
- `setup` - Story/character setup
- `story` - Main gameplay
- `graph` - Knowledge graph visualization
- `admin` - Admin panel

## Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start Neo4j (required for full functionality)
docker-compose up -d

# Run FastAPI server (serves at http://localhost:8000)
uvicorn src.mantle.api:app --reload --port 8000
```

### Testing
```bash
pytest                           # Run all tests
pytest tests/test_entities_api.py  # Specific test file
pytest -v                        # Verbose output
```

### Deployment
```bash
fly deploy                       # Deploy to Fly.io
```

**IMPORTANT: Local vs Deployed Changes**

When troubleshooting "why isn't this working?":
1. **First check:** Have the changes been deployed? File edits are LOCAL ONLY until committed and deployed.
2. **Local changes** = only visible on developer's machine (after server restart)
3. **Deployed changes** = visible to all users at https://lore-management-system.fly.dev/

**Workflow:**
```bash
# 1. Make changes to files
# 2. Commit changes
git add . && git commit -m "description"
# 3. Deploy to production
fly deploy
# 4. Update version tracker
# Edit data/deployed_version.txt with new version
```

**When user reports something isn't working after we made changes:**
→ Mention deployment status EARLY: "Those changes are local only - not deployed yet. Want me to deploy?"

## Frontend Architecture

**CRITICAL: Two Frontend Systems**

1. **Production UI (Static)** - `frontend/dist/index.html`
   - Self-contained ~17k line HTML file with inline CSS/JS
   - Features the raven logo landing page
   - **THIS IS WHAT USERS SEE**
   - Edit directly for production changes

2. **React App (Development)** - `frontend/src/`
   - For prototyping only
   - Builds to `frontend/dist-react/` (NOT dist/)
   - Does NOT affect production

```bash
cd frontend
npm run dev      # React dev server on port 3000
npm run build    # Builds to dist-react/ (safe)
```

**If the raven landing page disappears:**
```bash
git restore frontend/dist/
```

## Key Patterns

### Gospel Principle
"AI detects, humans decide" - All canonical lore decisions require explicit human approval. AI agents suggest but never make autonomous changes.

### Human-in-the-Loop Flow
1. User uploads/pastes lore content
2. AI extracts entities and relationships
3. User reviews in entity review panel (select/deselect, edit names)
4. Only approved entities are committed to the database

### Async Architecture
All I/O operations are async. Database calls use the native async Neo4j driver.

```python
async def get_neo4j_db(request: Request) -> Neo4jDatabase:
    return request.app.state.neo4j_db

@router.get("/entities/{canon_id}")
async def get_entity(db: Neo4jDatabase = Depends(get_neo4j_db)):
    ...
```

## Database

Neo4j graph database with:
- **Node Labels:** Character, Location, Faction, Item, Event, Concept
- **Key Properties:** `canon_id` (unique), `name`, `embedding` (768-dim vector)
- **OCEAN Personality:** Characters have openness, conscientiousness, extraversion, agreeableness, neuroticism (0.0-1.0)

## Environment Variables

Required in `.env`:
```
GEMINI_API_KEY=your_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
RESEND_API_KEY=your_resend_key  # For email notifications
```

## The Narrow Path (Core Philosophy)

**The system doesn't matter. What matters is that the player believes the system matters. The real product is the story.**

Players need to believe their choices create outcomes. The dice are a ritual that transfers ownership from the DM to the player. AI has absorbed millions of stories and understands the *shape* of human satisfaction without explicit rules.

The implementation is a **context-gathering system**, not a rules engine. Feed rich context about player investment to the AI and trust its pattern-matched intuition.

See `docs/airpg/THE_NARROW_PATH.md` for full philosophy.

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

### Error Codes
- `400` - Bad request (validation failure)
- `404` - Resource not found
- `409` - Conflict (duplicate)
- `422` - Unprocessable entity
- `500` - Server error

## Testing

Tests use `InMemoryMockDatabase` from `src/mantle/db/mock_adapter.py`:

```python
# conftest.py provides:
# - mock_neo4j_db: InMemoryMockDatabase instance
# - client: TestClient with mocked dependencies
```

## API Route Structure (IMPORTANT!)

**Router Prefixes:** Routers have their own prefixes that stack with mount prefixes:

```python
# game_routes.py has:
router = APIRouter(prefix="/game", tags=["Game"])  # <-- Router prefix

# routes.py mounts it:
app.include_router(game_router, prefix="/api")     # <-- Mount prefix

# Final path: /api/game/lore-bases (not /api/lore-bases!)
```

**Frontend API Calls:**
```javascript
const API_BASE = window.location.origin + '/api';

// CORRECT - game routes need /game/ prefix:
fetch(API_BASE + '/game/lore-bases')      // → /api/game/lore-bases

// Other routers without /game/ prefix:
fetch(API_BASE + '/orchestrator/status')  // → /api/orchestrator/status
fetch(API_BASE + '/memory/sessions')      // → /api/memory/sessions
```

**Router → Mount Mapping:**
| Router | Mount Prefix | Router Prefix | Example Endpoint |
|--------|-------------|---------------|------------------|
| game_router | /api | /game | /api/game/lore-bases |
| orchestrator_router | /api | (none) | /api/orchestrator/status |
| memory_router | /api | (none) | /api/memory/sessions |
| dnd_router | /api | (none) | /api/dnd/characters |

## Working with the User (Ben) - Session Notes

### Communication Preferences
- Be **explicit** about what changes have been made vs deployed
- When user asks "why isn't this working?", first check deployment status
- User values efficiency - use parallel tool calls when possible
- User appreciates when Claude mentions relevant context proactively

### Common Gotchas
1. **API Route Prefixes**: game_routes.py has `prefix="/game"` on the router itself
2. **Local vs Deployed**: Always clarify if changes need deployment
3. **Two Frontend Files**: Changes must go in BOTH `frontend/dist/index.html` AND `frontend/index.html`
4. **Version Tracking**: Update `data/deployed_version.txt` after deploys

### Testing Workflow
1. User often tests on live site (https://lore-management-system.fly.dev/)
2. Jim (collaborator) also does playtesting and reports issues
3. Feedback often comes mid-session - handle gracefully without losing context

### Character Creation System (MANTLE)
- **Origins** = Setting-specific races (map to D&D 5e base races)
- **Archetypes** = Setting-specific classes (map to D&D 5e base classes)
- **Seeds** = Pre-made world templates in `data/lore_bases/seeds/`
- Each seed has `character_options` with origins, archetypes, and setting_skills
- AI can extract character options from lore content

### World Tuner (Conversational World Config)
The World Tuner is an AI assistant that helps admins configure worlds through natural conversation.

**How it works:**
1. Admin opens World Tuner from World Manager (green "🎯 World Tuner" button)
2. Admin describes what they want ("Add a vampire race that's aristocratic")
3. AI proposes changes with structured data
4. Admin approves/rejects proposals in the side panel
5. Approved changes are applied to `character_options`

**Key Files:**
- **Agent**: `src/mantle/agents/world_tuner_agent.py`
- **API Endpoints**: `/api/game/admin/lore-bases/{id}/tuner/chat`, `/tuner/approve`, `/tuner/greeting`
- **Frontend**: Search "WORLD TUNER" in `frontend/dist/index.html`

**Proposal Structure:**
```json
{
  "id": "unique_id",
  "category": "origin|archetype|skill|characteristic",
  "action": "add|modify|remove",
  "data": { /* full structured data */ }
}
```

### Key Files for Common Tasks
- **Add new API endpoint**: `src/mantle/api/game_routes.py`
- **Modify DM behavior**: `src/mantle/agents/dm_agent.py`
- **World Tuner logic**: `src/mantle/agents/world_tuner_agent.py`
- **Character creation UI**: Search "Character Options" in `frontend/dist/index.html`
- **World Tuner UI**: Search "WORLD TUNER" in `frontend/dist/index.html`
- **World seeds**: `data/lore_bases/seeds/*.json`
- **Design tokens**: Search `:root {` in frontend files
- **Arc Engine**: `src/mantle/arc/` (narrative pacing, Hero's Journey phases, tension tracking)
- **Storytelling Preferences**: Search "storytelling-preferences" in frontend, `_build_storytelling_preferences_context` in game_routes.py

### TODO: Rules System Review
Revisit how the rules system (D&D 5e mechanics in `src/mantle/dnd5e/`) is implemented and how transparent it is with the user. Key questions:
- How visible are the mechanics to the player? (dice rolls, stat checks, HP changes)
- Should the visibility scaling (Storyteller → Tactician) be more prominent/configurable?
- Is the current implementation aligned with The Narrow Path philosophy?
- How do the rules interact with storytelling preferences (lethality, etc.)?
