# Lore Management System (LMS) + AIRPG

A production-ready knowledge management system for maintaining narrative coherence in complex fictional worlds, with an integrated **AI-powered RPG engine** supporting any genre.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     AIRPG RUNTIME                           │
│     Genre-Agnostic AI RPG Engine (16+ Genres)               │
│     React Frontend • FastAPI Backend • Neo4j Graph          │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│                   D&D 5e RULES ENGINE                       │
│     • Runs under the hood (always consistent)               │
│     • Visibility scales: Storyteller → Tactician            │
│     • Genre-adapted terminology                             │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│                 LMS (Lore Management)                       │
│     • Neo4j Graph Database (relationships + vectors)        │
│     • Gospel Principle (AI detects, humans decide)          │
│     • Contradiction detection & resolution                  │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### Genre System (16 Genres)
Mix up to 3 genres for unique narrative blends:

| Category | Genres |
|----------|--------|
| **Adventure** | Fantasy, Sci-Fi, Western, Superhero |
| **Tension** | Horror, Mystery, Thriller, Post-Apocalyptic |
| **Drama** | Romance, Drama, Historical, Steampunk |
| **Speculative** | Cosmic Horror, Wuxia, Cyberpunk, Urban Fantasy |

Each genre has curated seed lore for immediate play.

### Character Creation (3 Modes)
- **Concept Mode**: Describe your character, AI generates the sheet
- **Guided Mode**: Step-by-step with plain language explanations
- **Classic Mode**: Full PHB-style manual control

### Rules Visibility (4 Levels)
The D&D 5e engine always runs, but presentation scales:

| Mode | Example Attack |
|------|----------------|
| **Storyteller** | "You strike true, your blade finding its mark." |
| **Guided** | "You strike true (your training paid off here)." |
| **Classic** | "You hit! [18 vs AC 15]" |
| **Tactician** | "Hit! d20(14) + 4 = 18 vs AC 15. Damage: 2d6+3 = 11 slashing" |

### AI Dungeon Master
- MANTLE personality engine (grounded, consistent DM behavior)
- Boundary enforcement (PC Sanctity - never controls player character)
- Entity generation (NPCs created during play saved to graph)
- OCEAN personality model for psychologically-grounded NPCs

### Lore Management
- Neo4j graph database with 768-dim vector embeddings
- Contradiction detection (semantic + rule-based)
- Agentic query retrieval (natural language → lore)
- World Logic Charter (11 laws of narrative coherence)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start Neo4j
docker-compose up -d

# Configure environment
cp .env.example .env
# Add: GEMINI_API_KEY, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# Run the server
uvicorn src.api:app --reload

# Open browser to http://localhost:8000
```

## Project Structure

```
src/
├── lms/                    # Lore Management System
│   ├── api/                # FastAPI routes
│   │   ├── routes.py       # Main API + frontend serving
│   │   ├── game_routes.py  # Game session endpoints
│   │   └── dnd_routes.py   # Character creation API
│   ├── agents/             # AI agents (DM, Query, Auditor)
│   ├── dnd5e/              # D&D 5e rules engine
│   │   ├── models/         # Character sheets, abilities, etc.
│   │   ├── engine/         # Dice, checks, combat resolution
│   │   ├── creation/       # Character creation flows
│   │   └── presentation/   # Visibility filtering
│   ├── db/                 # Neo4j database layer
│   └── services/           # Business logic
├── airpg/                  # AI RPG engine
│   ├── engine/             # Scene generation, belief propagation
│   └── runtime/            # Session management, orchestration
frontend/
├── dist/                   # Production React build
│   └── index.html          # Single-page app
data/
└── lore_bases/
    └── seeds/              # Curated genre lore (16 genres)
```

## Technical Stack

- **Backend**: Python 3.11+ / FastAPI / Pydantic v2
- **Database**: Neo4j (graph + vector search)
- **AI**: Google Gemini API
- **Frontend**: React (dist/index.html)
- **Theme**: "Haunting Machine" (phosphor green terminal aesthetic)

## Development

```bash
# Run tests
pytest

# Run with verbose output
pytest -v

# Frontend development (if modifying React source)
cd frontend && npm run dev
```

## Documentation

- `CLAUDE.md` - AI assistant guidance
- `docs/airpg/` - AIRPG architecture and doctrine
- `docs/engineering/` - Technical guides
- `docs/API_CONTRACT.md` - API documentation

## Design Principles

### Gospel Principle
**"AI detects, humans decide"** - All canonical lore decisions require explicit human approval.

### Rules Always Run
D&D 5e mechanics resolve every action consistently. Only the *presentation* changes based on visibility mode.

### Genre Agnostic
The rules engine uses genre-adapted terminology (Origin/Archetype vs Race/Class) to support any narrative genre.

## Credits

Created by: **Shawn King**
Campaign World: **Jim King's D&D Campaign** (30+ years)
AI Architecture: Multi-agent coordination (Claude, Gemini)

## License

MIT License
