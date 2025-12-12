# Lore Management System (LMS)

A production-ready knowledge management system for maintaining narrative coherence in complex fictional worlds. Built as the **memory layer** for AIRPG - an AI-powered text-based RPG engine.

## The Vision

```
┌─────────────────────────────────────────────────────────────┐
│                        AIRPG                                │
│        (AI Dungeon Master - Text-Based RPG Game)            │
│                                                             │
│    Uses MANTLE engine for DM personality & rules            │
│    Uses LMS as its "memory" for canonical lore              │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│                      MANTLE ENGINE                          │
│    • Grounded DM personality (DM Prompt v2.3)               │
│    • PC Sanctity - Never controls player character          │
│    • Soft Corralling - Guides without blocking              │
│    • Modified Rule of Cool - Rewards audacity               │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│                    LMS (This Project)                       │
│    • Neo4j Graph Database for relationship-aware queries    │
│    • World Logic Charter (11 Laws of narrative coherence)   │
│    • Gospel Principle (AI detects, humans decide)           │
│    • Agentic Query System (natural language → lore)         │
└─────────────────────────────────────────────────────────────┘
```

## Origin Story

Built to solve a real problem: managing 30+ years of accumulated lore from a long-running D&D campaign. When you have decades of session notes, character backstories, and world history, maintaining consistency becomes impossible without systematic tooling.

**The Challenge**: After 30 years of weekly D&D sessions, you have:
- Thousands of NPCs, locations, and events
- Conflicting accounts of the same events
- Characters who may or may not be dead
- Relationships that contradict each other
- No single source of truth

**The Solution**: LMS provides AI-assisted extraction, validation, and contradiction management to maintain narrative coherence at scale - and eventually powers an AI DM that can run games in this world.

## Architecture

### Data Layer: Neo4j Graph Database
- **Nodes**: Entities (Characters, Factions, Locations, Items, Events, etc.)
- **Edges**: Relationships (ally_of, enemy_of, located_in, member_of, etc.)
- **Why Graph?**: Relationship traversal is natural - "Who are the Vulture Clan's allies?" is a simple graph query, not complex SQL JOINs.

### Entity System (8 Types)
- **CHARACTER**: Named individuals (PCs, NPCs)
- **CREATURE**: Species, races, monster types
- **DEITY**: Gods, cosmic entities
- **LOCATION**: Places, regions, buildings
- **FACTION**: Organizations, kingdoms, orders
- **ITEM**: Weapons, artifacts, magical objects
- **SPELL**: Incantations, rituals, magical effects
- **EVENT**: Battles, ceremonies, historical moments

### Multi-Agent AI System
- **Ingestor**: Extracts entities and relationships from text files using Gemini
- **QueryAgent**: RAG-powered natural language queries with agentic entity extraction
- **AuditorAgent**: Contradiction detection and semantic analysis
- **Gemini Integration**: AI-powered analysis and suggestions

### Agentic Query Retrieval (3-Tier Strategy)
1. **Agentic Extraction**: Gemini extracts entities from complex queries ("What happened when the dark one attacked?")
2. **Reverse Match**: Find nodes whose names appear in the user's message
3. **Keyword Search**: Traditional fallback for edge cases

## Key Features

### 🎮 AIRpg - Play Mode
- **AI Dungeon Master**: Grounded, ruleset-agnostic narrative DM
- **Session 0**: Collaborative world/character/tone creation
- **Save System**: 3 save slots + Continue button
- **Boundary Enforcement**: Educates players on agency rules
- **Entity Generation**: NPCs created during play are saved to the graph

### 🧠 NPC Personality (OCEAN Model)
- **Psychologically-grounded NPCs** using Five-Factor personality model
- **8 Archetypes**: Merchant, Guard, Scholar, Noble, Criminal, Priest, Warrior, Peasant
- **Consistent behavior** across sessions driven by personality traits
- **Dialogue style** adapts to personality (terse vs. talkative, warm vs. blunt)

### Entity Extraction
- AI-powered extraction from text files to Neo4j graph
- Automatic relationship detection
- Source file tracking for provenance

### Contradiction Management
- Semantic contradiction detection using Gemini
- AI-suggested reconciliation strategies
- Gospel Principle enforcement (humans decide canon)
- Full audit trail

### World Logic Charter (11 Laws)
Universal narrative coherence rules:
1. **Conservation of Consequence** - No deus ex machina without setup
2. **Limited Exception** - Magic has cost/consequence
3. **Local Truth** - Exceptions must be consistent within scope
4. **Reconcilable Conflict** - Contradictions resolvable via narrative
5. **Persistent Identity** - Can't be alive AND dead without explanation
6. **Temporal Ordering** - Cause before effect (usually)
7. **Bounded Knowledge** - Characters know only what they could learn
8. **Material Permanence** - Objects don't appear/vanish without mechanism
9. **Proportional Power** - Abilities match background/training
10. **Geographical Coherence** - Distance and travel time matter
11. **Social Consistency** - Cultures operate by internal logic

## Technical Stack

### Backend
- **Python 3.11+** with FastAPI
- **Neo4j** Graph Database (relationship-aware queries)
- **Pydantic v2** for validation
- **Google Gemini API** for AI features

### Frontend Options
- **Streamlit** UI (functional, basic)
- **React** UI (in development)
- "Haunting Machine" aesthetic (phosphor green terminal theme)

## Project Structure
```
.
├── src/
│   ├── api/
│   │   └── routes.py        # FastAPI application (main entry point)
│   ├── db/
│   │   └── neo4j_adapter.py # Neo4j database layer
│   ├── agents/
│   │   ├── dm_agent.py      # AI Dungeon Master agent
│   │   ├── query_agent.py   # RAG-powered query agent
│   │   └── auditor_agent.py # Contradiction detection
│   ├── ingestion/
│   │   └── ingestor.py      # Entity extraction to Neo4j
│   ├── services/            # Business logic services
│   ├── core/
│   │   ├── models.py        # Pydantic models
│   │   ├── entity_factory.py # Entity generation templates
│   │   └── utils.py         # Security and validation utilities
│   └── prompts/             # AI prompt library
│       ├── dm_prompts.py    # DM system prompts
│       ├── boundary_prompts.py  # Reframe prompts
│       └── auditor_prompts.py   # Auditor prompts
├── docs/
│   ├── NEO4J_SCHEMA.md      # Graph database schema
│   ├── PLAYER_DM_CONTRACT.md  # Agency rules documentation
│   ├── ARCHITECTURE.md      # System architecture
│   ├── SECURITY.md          # Security best practices
│   └── ...                  # Other documentation
├── lore/                    # Source lore files
├── tests/                   # Test suite
├── backups/                 # Legacy/backup files
│   └── app.py.legacy        # Old Streamlit UI (deprecated)
└── docker-compose.yml       # Neo4j container setup
```

## Getting Started

### Prerequisites
- Python 3.11+
- Neo4j (via Docker or local install)
- Google Gemini API key

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start Neo4j (via Docker)
docker-compose up -d

# Set up environment
cp .env.production.template .env
# Edit .env and replace ALL placeholder values with your actual credentials:
#   - NEO4J_URI (e.g., bolt://localhost:7687 or neo4j+s://your-aura-instance)
#   - NEO4J_USER (default: neo4j)
#   - NEO4J_PASSWORD (your secure password)
#   - GEMINI_API_KEY (your Google Gemini API key)

# Run FastAPI server (main application entry point)
uvicorn src.api.routes:app --reload --host 0.0.0.0 --port 8000
```

**Important**: The application entry point is `src/api/routes.py`. The old `app.py` Streamlit UI has been deprecated and moved to `backups/app.py.legacy`.

## Current Status

### Complete ✅
- Fully migrated to a pure Neo4j graph database backend.
- Legacy SQLite code and obsolete files removed.
- Test suite stabilized and passing (74 passed, 1 skipped).
- Neo4j graph integration with entity relationships
- Entity extraction pipeline (text → graph)
- Agentic query retrieval (3-tier strategy)
- Contradiction detection (rule-based + semantic)
- WebSocket integration for real-time updates
- **AIRpg Play Mode** with AI Dungeon Master
- **Session 0** collaborative world setup
- **Save/Load System** with 3 slots + Continue
- **Boundary Enforcement** for player agency
- **OCEAN Personality System** for NPCs
- **Entity Generation** during gameplay
- "Haunting Machine" Streamlit UI

### In Progress 🚧
- React frontend wiring
- Party knowledge filtering
- Rules/mechanics integration (optional rulesets)

### Roadmap 📋
See `ROADMAP.md` for full development plan:
- **Phase XIII**: Session state management ✅
- **Phase XIV**: Multi-modal (voice, maps)
- **Phase XV**: Living world simulation

## Design Philosophy

### The Gospel Principle
**"AI detects, humans decide"** - The system provides analysis and suggestions, but all canonical decisions are made by humans. No automatic changes to lore.

### Context Bleed Prevention
The system explicitly prevents AI from injecting knowledge from training data. Only entities explicitly present in source documents are extracted.

### Three-Tier Validation
1. **Universal Charter** (applies to all worlds)
2. **Campaign Settings** (world-specific rules)
3. **Local Truth** (location-specific exceptions)

## Credits

Created by: **Shawn King**  
Campaign World: **Jim King's D&D Campaign** (30+ years)  
AI Architecture: Multi-agent coordination (Claude, Gemini)

*"Managing decades of lore so the cosmic horrors stay consistent."* 🐙

## License
[MIT License]
