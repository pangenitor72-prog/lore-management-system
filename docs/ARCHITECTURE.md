# LMS Architecture
**System Design Overview for 30-Year D&D Campaign Lore Management**

**Last Updated:** 2025-11-30  
**System Status:** Production (Phases I-XIII complete)

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Responsibilities](#component-responsibilities)
4. [Data Flow Patterns](#data-flow-patterns)
5. [Technology Stack](#technology-stack)
6. [Design Principles](#design-principles)
7. [Deployment Architecture](#deployment-architecture)
8. [Future Architecture Considerations](#future-architecture-considerations)

---

## System Overview

The Lore Management System (LMS) is a production-grade knowledge management system designed to maintain narrative coherence in a 30-year D&D campaign.

**Core Problem Solved:**
After 30 years of weekly sessions, maintaining consistency across thousands of NPCs, locations, events, and relationships becomes impossible without systematic tooling. LMS provides AI-assisted extraction, validation, and contradiction management while enforcing human authority over canonical decisions (Gospel Principle).

**System Maturity:** PRODUCTION
- ✅ 100% system health
- ✅ 0% error rate over 24 hours
- ✅ 22/22 API endpoints verified
- ✅ Comprehensive test coverage

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Web Browser                                                      │
│  ├─ HTML/CSS/JS (Vanilla)                                       │
│  ├─ "Haunting Machine" Aesthetic (phosphor green terminal)      │
│  └─ Chart.js for Analytics                                      │
│                                                                   │
│  Communication:                                                   │
│  ├─ HTTP/REST for CRUD operations                               │
│  └─ WebSocket for real-time auditor events                      │
│                                                                   │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ HTTP/WS
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  FastAPI Application (Python 3.11+)                              │
│  ├─ api.py - Core routes, app initialization                    │
│  ├─ services/ - Business logic layer                            │
│  │   └─ contradiction_service.py - Contradiction workflows      │
│  ├─ agents/ - AI Integration                                    │
│  │   ├─ auditor_agent.py - Contradiction detection             │
│  │   └─ query_agent.py - Natural language queries              │
│  ├─ broadcaster.py - WebSocket event distribution               │
│  └─ audit_log.py - Centralized logging                          │
│                                                                   │
│  Patterns:                                                        │
│  ├─ Async/await for all I/O                                     │
│  ├─ Dependency injection for DB connections                     │
│  ├─ Service layer for business logic                            │
│  └─ Gospel Principle enforcement                                │
│                                                                   │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ Thread-safe connections
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Neo4j Graph Database                                            │
│  ├─ neo4j_adapter.py - Async connection management & queries    │
│  ├─ models.py - Pydantic v2 models & enums                      │
│  └─ docs/NEO4J_SCHEMA.md - Graph schema documentation           │
│                                                                   │
│  Structure:                                                       │
│  ├─ Nodes (Entities): Character, Location, Faction, Item, etc.  │
│  ├─ Relationships: KNOWS, LOCATED_IN, MEMBER_OF, etc.           │
│  ├─ Properties on nodes and relationships                       │
│  └─ Vector Index for semantic search                            │
│                                                                   │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Google Gemini API                                               │
│  ├─ Used by: AuditorAgent, QueryAgent                           │
│  ├─ Purpose: AI-powered contradiction detection & analysis      │
│  └─ Note: System continues without it (degraded mode)           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### Frontend Layer (Client)

**Location:** `src/templates/`, `src/static/`

**Responsibilities:**
- Render UI for entity browsing, contradiction review, dashboard
- Handle user interactions (clicks, form submissions)
- Maintain WebSocket connection for real-time updates
- Display analytics and system health metrics

**Key Files:**
- `templates/dashboard.html` - Main analytics dashboard
- `templates/entities.html` - Entity browser interface
- `templates/entity_detail.html` - Single entity view
- `static/` - CSS, JavaScript, images

**Technology:**
- Vanilla JavaScript (no frameworks)
- Chart.js for data visualization
- Jinja2 templates for server-side rendering
- "Haunting Machine" aesthetic (phosphor green, terminal-style)

---

### Application Layer (Backend)

#### Core Application (`src/api.py`)

**Responsibilities:**
- Application initialization and lifespan management
- Core route definitions (root, entities, upload)
- Middleware configuration (CORS)
- Agent initialization (AuditorAgent, QueryAgent)
- Static file and template serving

**Key Patterns:**
- Async route handlers
- Dependency injection for database connections
- Response models via Pydantic
- Centralized error handling

**Startup Sequence:**
1. Load environment variables
2. Initialize AuditLogger
3. Check GEMINI_API_KEY availability
4. Initialize agents (AuditorAgent, QueryAgent)
5. Initialize database schema
6. Start FastAPI application

---

#### Service Layer (`src/services/`)

**Purpose:** Business logic separation from route handlers

**contradiction_service.py:**
- Contradiction CRUD operations
- Triage workflow management
- Status update operations (resolve, dismiss, review)
- Dashboard data aggregation
- Debug endpoints for testing

**Responsibilities:**
- Validate business rules
- Coordinate database transactions
- Enforce Gospel Principle (humans decide canon)
- Provide helper functions for common operations

**Pattern:**
```python
router = APIRouter(prefix="/api")

@router.post("/contradictions")
async def create_contradiction(...):
    # Business logic here
    pass

def get_router():
    return router
```

---

#### Agent Layer (`src/`)

**Purpose:** AI integration and intelligent analysis

**dm_agent.py (DMAgent):**
- AI Dungeon Master for AIRpg play mode
- Session 0 handling (world/character/tone setup)
- Grounded narrative generation
- Boundary enforcement integration
- Entity extraction and saving during play
- Personality-aware NPC dialogue generation

**auditor_agent.py (AuditorAgent):**
- Analyzes lore for contradictions
- Detects 9 types of logical and temporal conflicts
- Generates confidence scores
- Broadcasts events via WebSocket
- Personality consistency checking
- Operates with or without Gemini API

**query_agent.py (QueryAgent):**
- Natural language lore queries
- Semantic search across entities
- Context-aware responses

**boundary_enforcement.py:**
- Player intent classification (action, question, perception, dialogue)
- Violation detection (declaration, outcome forcing, meta-control)
- Agency override rules with in-world justifications
- Educational reframing of invalid inputs

**personality.py:**
- OCEAN (Five-Factor) personality model
- 8 preset archetypes (Merchant, Guard, Scholar, etc.)
- Personality generation from role with variation
- Behavioral summary and dialogue style guidance

**Design Philosophy:**
- Agents suggest, never decide (except DMAgent for narrative)
- All AI recommendations require human approval
- Graceful degradation without API keys
- Comprehensive logging of all agent actions

---

#### Supporting Components

**neo4j_adapter.py:**
- Async-first class (`Neo4jDatabase`) for connection pooling and queries.
- Executes Cypher queries asynchronously.
- Manages vector indexes for semantic search.
- Provides helper methods for storing and retrieving node data.

**models.py:**
- Pydantic v2 models for validation
- Enums for categorical values
- Request/response schemas
- Field validators
- ConfigDict for ORM mode

**audit_log.py:**
- Centralized logging facility
- Async logging (`AuditLogger.log`)
- Sync logging (`AuditLogger.log_sync`)
- Structured log format
- Multiple log levels support

**broadcaster.py:**
- WebSocket event distribution
- Pub/sub pattern for real-time updates
- Queue management for subscribers
- Event types: contradiction_detected, analysis_complete

---

### Data Layer

#### Graph Structure

The data layer is a property graph in Neo4j, consisting of nodes and relationships.

**Nodes:**
- **`Entity`:** A generic label for all lore objects. All entities also have a specific type label (e.g., `Character`, `Location`).
- **`Character`:** Represents NPCs and other individuals. Contains properties like `name`, `description`, and OCEAN personality scores.
- **`Location`:** Represents places in the world.
- **`Faction`:** Represents organizations and groups.
- **`Item`:** Represents significant objects.
- **`Event`:** Represents historical or ongoing events.
- **`Concept`:** Represents abstract ideas like magic systems.
- **`Contradiction`:** A node representing a detected conflict in the lore.
- **`TriageAnalysis`:** An AI-generated analysis of a `Contradiction`.
- **`GameSession`:** Stores the state and history of a play session in AIRpg mode.

**Relationships:**
- Relationships connect nodes to represent their interactions (e.g., `(:Character)-[:MEMBER_OF]->(:Faction)`).
- Common relationship types include `KNOWS`, `ALLIED_WITH`, `ENEMY_OF`, `LOCATED_IN`, `OWNS`, `PARTICIPATED_IN`, and `ANALYZES`.
- Relationships can also have properties, such as `confidence`.

**Key Properties:**
- **`canon_id`:** A unique ID for every `Entity` node.
- **`name`:** The human-readable name of an entity.
- **`embedding`:** A 768-dimension vector on `Entity` nodes used for semantic search.

For a complete and detailed schema, see `docs/NEO4J_SCHEMA.md`.

---

## Data Flow Patterns

### Pattern 1: Entity Creation

```
1. User submits entity data (Frontend)
   └─ POST /entities
      {
        "entity_type": "Character",
        "canonical_name": "The Black King",
        "confidence_level": "CONFIRMED",
        ...
      }

2. FastAPI route handler (api.py)
   └─ Validates with Pydantic (EntityCreate model)
   └─ Generates canon_id
   └─ Calls wrapped database function

3. Database transaction (via run_in_threadpool)
   └─ INSERT into entities table
   └─ INSERT into aliases table (for each alias)
   └─ INSERT into approved_fields table (for each field)
   └─ Commit transaction

4. Response construction
   └─ Fetch created entity with all related data
   └─ Convert to EntityResponse model
   └─ Return JSON (201 Created)

5. Frontend receives response
   └─ Updates UI
   └─ Shows success message
```

**Key Points:**
- All DB operations wrapped in `run_in_threadpool` (async safety)
- Transaction ensures atomicity (all or nothing)
- Pydantic validates input and output
- Enums converted to/from string values

---

### Pattern 2: Contradiction Detection & Resolution

```
1. Auditor Agent detects contradiction
   └─ Analyzes lore entities
   └─ Identifies temporal discrepancy
   └─ Generates evidence object

2. Agent creates contradiction record
   └─ POST /api/contradictions
   └─ Status: PENDING
   └─ Severity: HIGH/MEDIUM/LOW

3. WebSocket broadcast
   └─ Event published: "contradiction_detected"
   └─ All connected clients notified
   └─ Dashboard updates in real-time

4. AI Analysis (optional)
   └─ Agent analyzes contradiction context
   └─ POST /api/contradictions/{id}/analysis
   └─ Status changes to IN_REVIEW
   └─ Provides recommendation

5. Human Review (Gospel Principle)
   └─ User views contradiction details
   └─ Reviews AI analysis (if available)
   └─ Examines evidence and sources
   └─ Makes canonical decision

6. Resolution
   └─ POST /api/contradictions/{id}/resolve
   └─ Includes user name and notes
   └─ Status changes to RESOLVED
   └─ Logs decision in audit trail
   └─ Updates affected entities (if needed)
```

**Gospel Principle Enforcement:**
- AI can analyze, recommend, suggest
- Only human can resolve or dismiss
- All decisions logged with user attribution
- No automatic resolution ever occurs

---

### Pattern 3: Async-Native Database Operations

**Old Problem:** The previous SQLite driver was synchronous, requiring all database calls in async routes to be wrapped in `run_in_threadpool` to avoid blocking the event loop.

**New Solution:** The `neo4j` async driver and our `Neo4jDatabase` adapter are inherently asynchronous. No special wrappers are needed. All database methods are `async` and can be `await`ed directly in route handlers.

```python
# ✅ Correct: Direct await on the async method
@router.get("/entities/{canon_id}")
async def get_entity(canon_id: str, db: Neo4jDatabase = Depends(get_neo4j_db)):
    entity = await db.execute("MATCH (n:Entity {canon_id: $id}) RETURN n", {"id": canon_id})
    return entity
```

---

### Pattern 4: Dependency Injection for Database

The dependency injection pattern remains crucial, but is updated for the new adapter.

```python
# src/dependencies.py
# Dependency provides a single database instance for the app's lifespan
# (or per request, depending on the desired scoping)
async def get_neo4j_db(request: Request) -> Neo4jDatabase:
    return request.app.state.neo4j_db

# Route receives the database instance via dependency injection
@router.post("/entities")
async def create_entity(
    entity: EntityCreate,
    db: Neo4jDatabase = Depends(get_neo4j_db)  # ← Injected
):
    # Use the async db instance
    await db.execute("CREATE ...")
```

**Benefits:**
- No manual connection management in routes
- Automatic transaction handling
- Guaranteed connection cleanup
- Testable (can inject mock connections)

---

## Technology Stack

### Backend
- **Python 3.11+** - Modern async support, type hints
- **FastAPI** - High-performance async web framework
- **Pydantic v2** - Data validation and serialization
- **Neo4j** - Graph database for relationship-centric data
- **Uvicorn** - ASGI server

### Frontend
- **Vanilla JavaScript** - No framework dependencies
- **Jinja2** - Server-side templating
- **Chart.js** - Data visualization
- **WebSocket API** - Real-time updates

### AI Integration
- **Google Gemini API** - Natural language understanding
- **Custom agents** - Domain-specific logic

### Development Tools
- **pytest** - Testing framework
- **requests** - API testing
- **dotenv** - Environment management

---

## Design Principles

### 1. Gospel Principle (Highest Priority)
**"AI detects, humans decide"**

All canonical lore decisions require explicit human approval. The system provides analysis, evidence, and recommendations, but never makes autonomous changes to canonical truth.

**Implementation:**
- Contradiction status requires human action (resolve/dismiss)
- All decisions logged with user attribution
- AI analysis stored separately from decisions
- Status field tracks human vs. AI actions

---

### 2. Async-First Architecture

**All I/O operations are asynchronous or wrapped for async safety**

**Why:**
- Better scalability under load
- Non-blocking request handling
- Prepares for future WebSocket features
- Modern Python best practices

**Implementation:**
- Async route handlers
- `run_in_threadpool` for blocking operations
- Dependency injection pattern
- Context managers for resource cleanup

---

### 3. Separation of Concerns

**Clear boundaries between layers**

- **Routes** - HTTP handling, validation
- **Services** - Business logic
- **Agents** - AI integration
- **Database** - Data persistence

**Benefits:**
- Easier testing
- Clear responsibilities
- Simpler debugging
- Better maintainability

---

### 4. Type Safety

**Strong typing throughout the codebase**

- Pydantic models for all API input/output
- Type hints on all functions
- Enums for categorical values
- Explicit type conversions

**Benefits:**
- Catches errors at development time
- Self-documenting code
- Better IDE support
- Prevents runtime type errors

---

### 5. Explicit Over Implicit

**No magic, no assumptions**

- Explicit database connections (no globals)
- Explicit transactions (context managers)
- Explicit enum conversions (`.value` for DB)
- Explicit error handling

**Benefits:**
- Predictable behavior
- Easier debugging
- Clearer code flow
- No hidden state

---

### 6. Production-Ready from Start

**Not a prototype - built for real use**

- Comprehensive error handling
- Centralized logging
- Transaction safety
- Test coverage
- Performance optimization (N+1 query prevention)

---

## Deployment Architecture

### Development Environment
```
Local Machine
├─ Python 3.11+ with virtualenv
├─ Neo4j Graph Database (via Docker or local install)
├─ Uvicorn dev server (--reload)
└─ Environment: .env file with GEMINI_API_KEY & Neo4j credentials
```

### Production Deployment (Recommended)
```
Server
├─ Docker container (optional)
├─ Uvicorn with multiple workers
├─ Neo4j Graph Database (e.g., AuraDB)
├─ Nginx reverse proxy (optional)
├─ HTTPS/SSL termination
└─ Environment variables via secure config
```

### Scaling Considerations

**Current Design (Single User):**
- Neo4j is highly scalable and suitable for production use.
- The `neo4j` driver handles connection pooling automatically.

**Future Multi-User:**
- Neo4j can be clustered for high availability and horizontal scaling.
- Caching strategies can be implemented with Redis for frequently accessed query results.

---

## Future Architecture Considerations

### Phase XIII+: Planned Enhancements

**1. Graph Database Migration (Complete)**
- The system has been successfully migrated from SQLite to a Neo4j graph database.
- This provides significant performance benefits for relationship-heavy queries and enables semantic search capabilities.

**2. Charter Law Validation System**
- Universal lore rules (applies to all campaigns)
- Campaign-specific overrides
- Automated rule checking
- Hierarchical rule precedence

**3. Advanced AI Features**
- Multi-agent coordination
- Proactive contradiction detection
- Context-aware suggestions
- Natural language entity updates

**4. MANTLE Integration**
- LMS becomes lore source for AIRPG
- AI DM queries LMS for canonical truth
- Party knowledge filtering
- Real-time lore updates during gameplay

---

## Component Dependencies

```
┌─────────────┐
│   api.py    │ ← Entry point, imports everything
└──────┬──────┘
       │
       ├─→ neo4j_adapter.py (connection management)
       ├─→ models.py (Pydantic schemas)
       ├─→ audit_log.py (logging)
       ├─→ broadcaster.py (WebSocket)
       │
       ├─→ agents/
       │   ├─ auditor_agent.py
       │   └─ query_agent.py
       │
       └─→ services/
           └─ contradiction_service.py
               └─ uses neo4j_adapter.py, models.py, audit_log.py
```

**Key Insight:** `api.py` orchestrates all components but delegates responsibility. Each component is independently testable.

---

## Security Considerations

### Current (Single-User System)
- No authentication required
- CORS allows all origins
- Runs on localhost only
- SQLite file permissions for access control

### Production Recommendations
- Add authentication (Bearer tokens)
- Restrict CORS to known domains
- Use HTTPS for all communications
- Environment-based configuration
- Regular database backups
- Audit log retention policy

---

## Performance Characteristics

### Current Metrics (Phase I-XI)
- **System Health:** 100%
- **Error Rate:** 0% over 24 hours
- **Response Time:** <100ms for most endpoints
- **Database Size:** ~10MB (hundreds of entities)
- **Concurrent Requests:** ~50-100 req/sec (single worker)

### Optimization Techniques Used
- N+1 query prevention (GROUP_CONCAT, JOINs)
- Database indexing on primary lookups
- WAL mode for concurrent reads
- Async I/O for non-blocking operations
- Response model caching (future enhancement)

---

## Testing Strategy

### Integration Tests
- API tests are located in `tests/`.
- They use `pytest` and a mocked `Neo4jDatabase` instance to ensure isolation.
- Key endpoints for entities and contradictions are covered.
- A smoke test file (`test_smoke.py`) verifies basic application health.

### Future Test Coverage
- Unit tests for service functions
- Agent behavior tests
- WebSocket connection tests
- Load testing for concurrency
- Error scenario testing

---

## Documentation Structure

This document is part of a comprehensive documentation suite:

1. **ARCHITECTURE.md** (this file) - System design
2. **CONVENTIONS.md** - Code patterns and style
3. **API_CONTRACT.md** - Endpoint specifications
4. **README.md** - Project overview
5. **lms-project-context/** - AI agent context

---

**Last Updated:** 2025-11-30  
**Maintained By:** Shawn King  
**Campaign World:** Jim King's D&D Campaign (30+ years)  
**System Status:** Production (Phase XIII complete - AIRpg Play Mode)
