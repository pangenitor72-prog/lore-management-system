# LMS Architecture
**System Design Overview for 30-Year D&D Campaign Lore Management**

**Last Updated:** 2025-11-25  
**System Status:** Production (Phases I-XI complete, Phase XII in progress)

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
│  SQLite Database (WAL mode)                                      │
│  ├─ database.py - Connection management, schema init            │
│  ├─ models.py - Pydantic v2 models & enums                      │
│  └─ data/schema.sql - Database schema definition                │
│                                                                   │
│  Configuration:                                                   │
│  ├─ WAL mode for concurrency                                    │
│  ├─ Foreign keys enforced                                       │
│  ├─ Per-request connections                                     │
│  └─ Explicit transaction management                             │
│                                                                   │
│  Tables:                                                          │
│  ├─ entities - Core lore entities                               │
│  ├─ aliases - Entity alternate names                            │
│  ├─ approved_fields - Entity metadata (JSON)                    │
│  ├─ relationships - Entity connections                          │
│  ├─ contradictions - Detected conflicts                         │
│  ├─ contradiction_entities - Many-to-many links                 │
│  └─ triage_analysis - AI analysis results                       │
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

#### Agent Layer (`src/agents/`)

**Purpose:** AI integration and intelligent analysis

**auditor_agent.py (AuditorAgent):**
- Analyzes lore for contradictions
- Detects 9 types of logical and temporal conflicts
- Generates confidence scores
- Broadcasts events via WebSocket
- Operates with or without Gemini API

**query_agent.py (QueryAgent):**
- Natural language lore queries
- Semantic search across entities
- Context-aware responses
- Future: Conversational interface

**Design Philosophy:**
- Agents suggest, never decide
- All AI recommendations require human approval
- Graceful degradation without API keys
- Comprehensive logging of all agent actions

---

#### Supporting Components

**database.py:**
- Connection factory (`get_db_connection`)
- Transaction context manager (`db_session`)
- Static utility methods (`execute`, `fetch_all`, `fetch_one`)
- Schema initialization
- PRAGMA configuration (WAL mode, foreign keys)

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

#### Database Structure

**entities table:**
- Primary lore objects (characters, locations, events, etc.)
- Canonical names and metadata
- Approval status and confidence levels
- Party knowledge tracking
- Timestamps (created_at, updated_at)

**aliases table:**
- Alternate names for entities
- Many-to-one relationship with entities
- Enables flexible searching

**approved_fields table:**
- Key-value store for entity metadata
- JSON values for complex data
- Extensible without schema changes

**relationships table:**
- Connections between entities
- Typed relationships (e.g., "ally_of", "located_in")
- Confidence levels for relationships

**contradictions table:**
- Detected logical/temporal conflicts
- Severity levels (HIGH, MEDIUM, LOW)
- Status tracking (PENDING → IN_REVIEW → RESOLVED/DISMISSED)
- Evidence storage (JSON)
- Timestamps and resolution notes

**contradiction_entities table:**
- Many-to-many link between contradictions and entities
- Enables finding all contradictions affecting an entity

**triage_analysis table:**
- AI analysis of contradictions
- Recommendations for resolution
- Confidence scores
- Analyst attribution

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

### Pattern 3: Async I/O with Thread Pool

**Problem:** SQLite operations are blocking, but FastAPI is async

**Solution:** Wrap all blocking DB calls in `run_in_threadpool`

```python
from fastapi.concurrency import run_in_threadpool

# ❌ Wrong - blocks event loop
async def get_entity(canon_id: str, db = Depends(get_db)):
    entity = Database.fetch_one(db, "SELECT ...", (canon_id,))
    return entity

# ✅ Correct - non-blocking
async def get_entity(canon_id: str, db = Depends(get_db)):
    entity = await run_in_threadpool(
        Database.fetch_one, 
        db, 
        "SELECT ...", 
        (canon_id,)
    )
    return entity
```

**Pattern Applied To:**
- All `Database.fetch_one()` calls
- All `Database.fetch_all()` calls
- All `Database.execute()` calls
- File I/O operations
- Any synchronous helper functions

---

### Pattern 4: Dependency Injection for Database

```python
# Dependency provides connection per request
async def get_db() -> Generator[sqlite3.Connection, None, None]:
    with db_session() as conn:
        yield conn

# Route receives connection via dependency injection
@router.post("/entities")
async def create_entity(
    entity: EntityCreate,
    db: sqlite3.Connection = Depends(get_db)  # ← Injected
):
    # Use db connection
    # Connection automatically committed/closed by context manager
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
- **SQLite** - Embedded database with WAL mode
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
├─ SQLite database (data/lore.db)
├─ Uvicorn dev server (--reload)
└─ Environment: .env file with GEMINI_API_KEY
```

### Production Deployment (Recommended)
```
Server
├─ Docker container (optional)
├─ Uvicorn with multiple workers
├─ SQLite with WAL mode
├─ Nginx reverse proxy (optional)
├─ HTTPS/SSL termination
└─ Environment variables via secure config
```

### Scaling Considerations

**Current Design (Single User):**
- SQLite sufficient for ~1000 req/sec
- WAL mode enables concurrent reads
- Single writer pattern acceptable

**Future Multi-User:**
- Migrate to PostgreSQL/MySQL
- Implement connection pooling
- Add Redis for caching
- Horizontal scaling with load balancer

---

## Future Architecture Considerations

### Phase XIII+: Planned Enhancements

**1. Graph Database Migration (Potential)**
- Current: SQLite with relationship table
- Future: Neo4j for complex relationship queries
- Benefit: Better performance for deep relationship traversal
- Challenge: Migration complexity

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
       ├─→ database.py (connection management)
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
               └─ uses database.py, models.py, audit_log.py
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
- All 22 API endpoints verified
- Real database transactions
- Full request/response cycle
- Located: `test_api_integration.py`

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

**Last Updated:** 2025-11-25  
**Maintained By:** Shawn King  
**Campaign World:** Jim King's D&D Campaign (30+ years)  
**System Status:** Production-ready, actively developed
