# AIRPG Development Roadmap

## Current Status: Phase XVI Complete

The system has evolved from a lore management tool into a full genre-agnostic AI RPG engine.

---

## Phase XII-XIII: Foundation (Complete)
- Neo4j graph database with vector embeddings
- AI ingestion pipeline (text → entities)
- Query agent with 4-tier retrieval
- AI Dungeon Master with MANTLE personality
- Save/Load system
- OCEAN personality model for NPCs

## Phase XIV: Genre & Rules (Complete)
- **16 Genre System** with mixing (up to 3 genres)
- **D&D 5e Rules Engine** running under the hood
- **Visibility Scaling** (Storyteller → Tactician)
- **Character Creation** (Concept, Guided, Classic modes)
- **Genre-Adapted Terminology** (Origin/Archetype)
- **Curated Seed Lore** per genre
- **React Frontend** as primary UI

## Phase XV: Polish (Current)
- [ ] Documentation consolidation
- [ ] Streamlit UI deprecation
- [ ] Test coverage expansion
- [ ] Performance optimization

---

## Future Phases

### Phase XVI: Multi-Modal
- Voice input/output (TTS/STT)
- Map image analysis
- Visual scene generation

### Phase XVII: Living World
- Faction turn simulation
- Background event generation
- Quest generation from loose ends

### Phase XVIII: Multiplayer
- Multiple player sessions
- Shared world state
- Async play support

### Phase XIX: VTT Integration
- Battle grid/map canvas
- Token positioning
- Line-of-sight calculations
- Integration with Roll20/Foundry

---

## Design Constraints

1. **Gospel Principle**: AI detects, humans decide
2. **Rules Always Run**: Mechanics consistent, only presentation scales
3. **Genre Agnostic**: Support any narrative genre
4. **Theater of Mind**: Text-first, VTT optional future
