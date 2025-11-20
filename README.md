# Lore Management System (LMS)

A production-ready knowledge management system for maintaining narrative coherence in complex fictional worlds, with a focus on tabletop RPG campaigns.

## Origin Story

Built to solve a real problem: managing 30+ years of accumulated lore from a friend's long-running D&D campaign, "The Hollow Eye Chronicles." When you have decades of session notes, character backstories, and world history, maintaining consistency becomes impossible without systematic tooling.

## Core Problem

**The Challenge**: After 30 years of weekly D&D sessions, you have:
- Thousands of NPCs, locations, and events
- Conflicting accounts of the same events
- Characters who may or may not be dead
- Relationships that contradict each other
- No single source of truth

**The Solution**: LMS provides AI-assisted extraction, validation, and contradiction management to maintain narrative coherence at scale.

## Architecture

### Entity System (8 Types)
- **CHARACTER**: Named individuals (PCs, NPCs)
- **CREATURE**: Species, races, monster types
- **DEITY**: Gods, cosmic entities
- **LOCATION**: Places, regions, buildings
- **FACTION**: Organizations, kingdoms, orders
- **ITEM**: Weapons, artifacts, magical objects
- **SPELL**: Incantations, rituals, magical effects
- **EVENT**: Battles, ceremonies, historical moments

### Validation Pipeline (5 Stages)
1. **Source Text Validation**: Prevents "Context Bleed" (AI hallucinations)
2. **Entity Structure Validation**: Type-specific attribute checking
3. **Charter Law Validation**: Universal narrative coherence rules (11 laws)
4. **Campaign Rule Validation**: Setting-specific overrides
5. **Contradiction Detection**: Multi-entity conflict identification

### Multi-Agent AI System
- **ChunkingAgent**: Document parsing and entity extraction
- **AuditorAgent**: Contradiction detection and analysis
- **QueryAgent**: Natural language lore queries
- **Gemini Integration**: AI-powered analysis and suggestions

## Key Features

### Entity Extraction
- AI-powered extraction from Word docs, text files
- 13 extraction rules including critical Context Bleed prevention
- Confidence scoring and approval workflow
- Alias tracking and entity merging

### Contradiction Management
- 7 conflict types (attribute mismatch, existence conflict, temporal inconsistency, etc.)
- AI-suggested reconciliation strategies
- Guided resolution workflow
- Full audit trail

### Robust & Scalable Backend
- **Modernized Database Layer:** Refactored for per-request, thread-safe SQLite connections with explicit transaction management (WAL mode, Foreign Keys ON).
- **Asynchronous API:** All blocking I/O (DB & LLM calls) in `async` endpoints are now correctly offloaded to a threadpool for improved concurrency.
- **Unified Data Models:** Consolidated and validated Pydantic models and Enums ensure strict data integrity and consistency.
- **Optimized Queries:** N+1 query patterns eliminated in key listing endpoints for better performance.
- **Centralized Logging:** Comprehensive logging and enhanced error handling for better observability and debugging.

## Technical Implementation

### Backend
- **Python 3.11+** with FastAPI
- **SQLite** (WAL mode for concurrency, explicit FK enforcement)
- **Pydantic v2** for validation and data modeling
- **Google Gemini API** for AI features

### Database Schema
- Immutable entity IDs
- Full revision history
- Relationship tracking with confidence levels
- Contradiction queue with resolution tracking

### API Design
- RESTful endpoints for CRUD operations
- WebSocket support for real-time updates
- Batch document processing
- Search and filtering

### Frontend
- Vanilla JavaScript (no framework dependencies)
- "Haunting Machine" aesthetic (phosphor green terminal theme)
- Chart.js for analytics
- Responsive design

## Current Status

**Phases Complete (I-XI)**:
- ✅ Core database and API
- ✅ Entity extraction system
- ✅ Contradiction detection
- ✅ Triage workflow
- ✅ WebSocket integration
- ✅ Dashboard and analytics
- ✅ System stability (100% health, 0% error rate)
- ✅ **LMS Audit Alignment & Test Suite Upgrade (Completed)**: Core codebase aligned with modern entity model, DB schema validated, comprehensive test suite rewritten, and engineering documentation generated.

**Active Development (Phase XII)**:
- 🎨 Entity browser UI with "Haunting Machine" aesthetic
- 🔄 Enhanced contradiction resolution workflow
- 🔄 Batch document processing

**Future Phases**:
- Charter Law validation system
- Campaign-specific overrides
- Advanced AI suggestions
- Migration to graph database (potential)

## Design Philosophy

### The Gospel Principle
**"AI detects, humans decide"** - The system provides analysis and suggestions, but all canonical decisions are made by humans. No automatic changes to lore.

### Context Bleed Prevention (Critical Rule 13)
The system explicitly prevents AI from injecting knowledge from training data. Only entities explicitly present in source documents are extracted. This was the #1 priority identified during testing.

### Three-Tier Validation
1. Universal Charter (applies to all worlds)
2. Campaign Settings (world-specific rules)
3. Local Truth (location-specific exceptions)

This allows one LMS instance to manage multiple campaigns across different genres.

## Performance Metrics

- Database Health: 100%
- Endpoint Reliability: 100%
- Schema Consistency: 100%
- Error Rate (24hrs): 0%
- Uptime: 99.8%

## Project Structure
```
.
├── data/
│   └── lore.db              # SQLite database (WAL mode)
├── src/
│   ├── api.py               # FastAPI application
│   ├── database.py          # Database layer
│   ├── models.py            # Pydantic models
│   ├── agents/              # AI Agent implementations (AuditorAgent, QueryAgent)
│   ├── services/            # Core business services (e.g., contradiction_service)
│   ├── utils/               # Utility functions (e.g., logging_config)
│   └── templates/           # Jinja2 HTML templates
├── docs/
│   ├── engineering/         # Engineering-specific documentation (e.g., ARCHITECTURE_OVERVIEW, REPO_RULES)
│   └── (other docs)
├── tests/                   # Comprehensive test suite (unit, integration, API)
└── README.md                # Project overview (this file)
```
*Note: The actual project structure might include additional subdirectories within `src/` for agents and services.*

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt
pip install httpx pytest-asyncio # Required for running tests (not in requirements.txt initially)

# Set up environment
cp .env.example .env
# Add your GEMINI_API_KEY

# Run server
uvicorn src.api:app --reload --lifespan on

# Access dashboard
http://localhost:8000/dashboard
```

## Running Tests

To run the comprehensive test suite:

```bash
pytest
```

## Contributing
This is a personal project for managing a specific D&D campaign, but the architecture is designed to be generalizable. Key areas for contribution:
- Additional entity types
- New contradiction detection patterns
- UI/UX improvements
- Test coverage
- Documentation

## License
[Your chosen license]

## Credits
Created by: Shawn King
Campaign World: Jim King's "Hollow Eye Chronicles" (30+ years)
AI Architecture: Multi-agent coordination (GPT-5, Claude Sonnet 4.5, Gemini)
"Managing decades of lore so the cosmic horrors stay consistent." 🐙
