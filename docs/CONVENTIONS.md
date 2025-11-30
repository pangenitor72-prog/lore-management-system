# LMS CODE CONVENTIONS
**Extracted from actual codebase - Last updated: 2025-11-25**

These conventions reflect the patterns actually used in the LMS codebase. Follow them to maintain consistency.

---

## CRITICAL PRINCIPLES

### 1. Gospel Principle (Highest Priority)
**"AI detects, humans decide"**
- NEVER let AI make canonical decisions automatically
- AI suggests, humans approve
- All canon decisions require explicit human confirmation
- Status changes must be logged with `updated_by` field

### 2. Async Architecture
- ALL I/O operations must be async or wrapped in `run_in_threadpool`
- Database calls use `run_in_threadpool` wrapper
- Never block the event loop with synchronous I/O

### 3. Type Safety
- Use Pydantic v2 models for all API input/output
- Use Enums for all categorical values
- Type hints required on all functions
- Explicit conversions between string and Enum values

---

## PYTHON CODE STYLE

### Imports Organization
```python
# Standard Library
import os
import json
from datetime import datetime, timezone
from typing import List, Optional

# Third Party
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

# Local Imports - organized by module
from .audit_log import AuditLogger
from .database import Database, get_db
from .models import EntityCreate, EntityResponse
```

**Rules:**
- Group imports: Standard → Third Party → Local
- Local imports organized by category (Audit, Database, Models, Agents, Services)
- Use absolute imports from package root (`from .module import`)

### Naming Conventions
```python
# Variables & Functions: snake_case
def create_entity(entity_data: EntityCreate) -> EntityResponse:
    canon_id = f"character-{uuid.uuid4().hex[:8]}"
    
# Classes: PascalCase
class EntityResponse(BaseModel):
    pass

# Constants: UPPER_SNAKE_CASE
DB_FILE_PATH = Path("data/lore.db")
BASE_DIR = Path(__file__).resolve().parent

# Enums: PascalCase with UPPER values
class EntityType(str, Enum):
    CHARACTER = "Character"
    LOCATION = "Location"
```

### Type Hints (Required)
```python
# Function signatures
async def get_entity(
    canon_id: str, 
    db: Neo4jDatabase = Depends(get_neo4j_db)
) -> EntityResponse:
    pass

# Variables when type is ambiguous
entity_ids: List[str] = []
data: Dict[str, Any] = {}

# Return types always specified
async def fetch_one(query: str) -> Optional[dict]:
    pass
```

---

## FASTAPI PATTERNS

### Route Structure
```python
@router.post("/entities", response_model=EntityResponse, status_code=201)
async def create_entity(
    entity_data: EntityCreate,
    db: Neo4jDatabase = Depends(get_neo4j_db)
) -> EntityResponse:
    """Creates a new entity in the graph database."""
    # Implementation
```

**Rules:**
- Async for all endpoints.
- Pydantic models for request/response validation.
- Explicit status codes for non-200 responses.
- Dependency injection for the database instance.
- Docstrings required on all routes.

### Dependency Injection Pattern
```python
# src/dependencies.py
async def get_neo4j_db(request: Request) -> Neo4jDatabase:
    return request.app.state.neo4j_db

# Usage in route
async def my_route(db: Neo4jDatabase = Depends(get_neo4j_db)):
    # db instance is managed by FastAPI's lifespan context
```

### Response Models
```python
# Always use Pydantic models, never raw dicts
return EntityResponse(**data)  # ✅ Good

return {"canon_id": "123", ...}  # ❌ Bad - no validation
```

### Error Handling
```python
# Standard pattern
from neo4j.exceptions import Neo4jError

try:
    result = await db.execute("CREATE (n:Thing {id: $id})", {"id": "123"})
except Neo4jError as e:
    await AuditLogger.log(f"Database error: {e.message}", level=logging.WARNING)
    if "already exists" in e.message: # Example check
        raise HTTPException(status_code=409, detail="Resource already exists")
    raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
except Exception as e:
    await AuditLogger.log(f"Unexpected error: {e}", level=logging.ERROR)
    raise HTTPException(status_code=500, detail=str(e))
```

**Error Response Codes:**
- `400` - Bad request (validation failure)
- `404` - Resource not found
- `409` - Conflict (duplicate, integrity violation)
- `422` - Unprocessable entity (invalid enum, missing field)
- `500` - Server error (unexpected failure)

---

## DATABASE PATTERNS

### Connection Management
```python
# Connection is managed via FastAPI's lifespan and dependency injection.
# The `Neo4jDatabase` instance is created once and reused.
async def my_route(db: Neo4jDatabase = Depends(get_neo4j_db)):
    # The 'db' instance is ready to use.
    results = await db.execute("MATCH (n) RETURN count(n)")
```

### Transaction Pattern
```python
# The neo4j driver's `execute_query` method handles transactions automatically.
# For more complex, multi-statement transactions, you can use a transaction object.
async with db.driver.session() as session:
    async with session.begin_transaction() as tx:
        await tx.run("CREATE (:Entity {name: 'A'})")
        await tx.run("CREATE (:Entity {name: 'B'})")
        # Transaction is committed automatically on exit, or rolled back on exception.
```

### Database Operations
```python
# All database operations are async and should be awaited.
# No run_in_threadpool wrapper is needed.

# Execute a query (returns a list of records)
records = await db.execute(
    "CREATE (e:Entity {name: $name}) RETURN e",
    {"name": "New Entity"}
)

# Fetch one result
# (Note: `fetch_one` is not a method on the new adapter, you'd typically use `execute` and process the result)
records = await db.execute(
    "MATCH (e:Entity) WHERE e.name = $name RETURN e",
    {"name": "Test"}
)
entity = records[0] if records else None

# Fetch multiple results
entities = await db.execute(
    "MATCH (e:Entity) WHERE e.type = $type RETURN e",
    {"type": "Character"}
)
```

### Async Wrapper Pattern (Obsolete)
The `run_in_threadpool` pattern for database calls is no longer necessary, as the `neo4j` driver is natively asynchronous. All calls to the `Neo4jDatabase` adapter are `async` and should be `await`ed directly.

### Preventing N+1 Queries
```python
# The N+1 problem still exists in graph databases, but is solved differently.

# ❌ Bad - N+1 query pattern (separate queries for nodes and their relationships)
# entities = await db.execute("MATCH (e:Entity) RETURN e")
# for entity in entities:
#     rels = await db.execute("MATCH (e {name: $name})-[r]->(m) RETURN r, m", {"name": entity['e']['name']})

# ✅ Good - Single query with aggregation
query = """
    MATCH (e:Entity)
    OPTIONAL MATCH (e)-[r]->(m)
    RETURN e, collect({relationship: type(r), neighbor: m}) AS relationships
"""
results = await db.execute(query)
```

### Neo4j Configuration
Configuration (URI, user, password) is handled via environment variables at application startup. The `Neo4jDatabase` adapter manages the connection pool.

---

## PYDANTIC MODELS

### Model Structure
```python
class EntityCreate(BaseModel):
    """Model for creating a new entity."""
    entity_type: EntityType
    canonical_name: str = Field(min_length=1, max_length=500)
    aliases: List[str] = Field(default_factory=list)
    approved_fields: Dict[str, Any] = Field(default_factory=dict)
    confidence_level: ConfidenceLevel
    party_knowledge: PartyKnowledge

class EntityResponse(BaseModel):
    """Model for entity responses."""
    canon_id: str
    entity_type: EntityType
    canonical_name: str
    # ... other fields
    
    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode
```

**Rules:**
- Docstring required on all models
- Use `Field()` for validation and defaults
- `default_factory` for mutable defaults (list, dict)
- `ConfigDict(from_attributes=True)` for response models

### Enum Usage
```python
# Define as str Enum
class EntityType(str, Enum):
    CHARACTER = "Character"
    LOCATION = "Location"

# Use in models
class EntityCreate(BaseModel):
    entity_type: EntityType  # Validates against enum

# Convert to/from database
# To DB: use .value
await db.execute("CREATE (n:Entity {type: $type})", {"type": entity.entity_type.value})

# From DB: Pydantic handles conversion
# When you load data into a Pydantic model, it automatically
# converts the string from the database back into an Enum member.
record = await db.execute("MATCH (n:Entity) WHERE n.id = $id RETURN n", {"id": id})
response = EntityResponse(**record[0]['n']) # Pydantic validates and converts
```

### JSON Field Handling
```python
# Storing JSON in Neo4j
# The python neo4j driver handles dicts automatically.
await db.execute(
    "CREATE (c:Contradiction {evidence: $evidence})",
    {"evidence": contradiction.evidence}
)

# Loading JSON from Neo4j
# The driver also deserializes automatically when fetching.
record = await db.execute("MATCH (c:Contradiction) WHERE c.id = $id RETURN c.evidence", {"id": id})
evidence = record[0]['c.evidence']
```

### Validators
```python
class EntityResponse(BaseModel):
    canonical_name: str
    
    @field_validator('canonical_name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure canonical name is not empty after stripping."""
        if not v.strip():
            raise ValueError("Canonical name cannot be empty")
        return v.strip()
```

---

## SERVICE LAYER PATTERNS

### Service Organization
```python
# Services in separate files: src/services/[resource]_service.py
# Export router via get_router() function

# In contradiction_service.py
router = APIRouter(prefix="/api")

@router.post("/contradictions")
async def create_contradiction(...):
    pass

def get_router():
    return router

# In api.py
from .contradiction_service import get_router as get_contradiction_router
app.include_router(get_contradiction_router())
```

### Helper Functions Pattern
```python
# Helper functions in service file, outside routes
async def get_contradiction_response(
    contradiction_id: str, 
    db: Neo4jDatabase
) -> ContradictionResponse:
    """Fetch full contradiction data and return as ContradictionResponse."""
    records = await db.execute(
        "MATCH (c:Contradiction {contradiction_id: $id}) RETURN c",
        {"id": contradiction_id}
    )
    
    if not records:
        raise HTTPException(status_code=404, detail=f"Not found: {contradiction_id}")
    
    # Build response from graph properties
    return ContradictionResponse(**records[0]['c'])
```

### Status Update Functions
```python
# Async helpers for status updates
async def set_resolved(contradiction_id: str, user: str, notes: str, db: Neo4jDatabase) -> bool:
    """Sets contradiction status to RESOLVED."""
    try:
        result = await db.execute(
            "MATCH (c:Contradiction {contradiction_id: $id}) SET c.status = $status, c.resolution_notes = $notes, c.updated_by = $user RETURN c",
            {
                "id": contradiction_id,
                "status": ContradictionStatus.RESOLVED.value,
                "notes": notes,
                "user": user
            }
        )
        if not result:
            AuditLogger.log_sync(f"Contradiction {contradiction_id} not found.", level=logging.WARNING)
            return False
        AuditLogger.log_sync(f"Contradiction {contradiction_id} resolved by {user}.")
        return True
    except Exception as e:
        await AuditLogger.log(f"Error: {e}", level=logging.ERROR)
        return False
```

---

## LOGGING PATTERNS

### Async Logging (Route Handlers)
```python
from .audit_log import AuditLogger
import logging

# In async contexts
await AuditLogger.log("Operation succeeded.")
await AuditLogger.log(f"Error: {e}", level=logging.ERROR)
await AuditLogger.log("Processing...", level=logging.INFO)
```

### Sync Logging (Helper Functions)
```python
# In synchronous helper functions
AuditLogger.log_sync("Status updated.", level=logging.INFO)
AuditLogger.log_sync(f"Warning: {issue}", level=logging.WARNING)
```

### Log Levels
```python
logging.DEBUG     # Detailed debugging (queries, row counts)
logging.INFO      # Normal operations (entity created, status changed)
logging.WARNING   # Unexpected but handled (not found, constraint violation)
logging.ERROR     # Recoverable errors (DB error, invalid input)
logging.CRITICAL  # System failures (schema init failed, config missing)
```

### What to Log
```python
# ✅ Log these
- Entity/contradiction creation
- Status changes (with user)
- Errors with context
- Database operations (DEBUG level)
- API endpoint hits (INFO level)

# ❌ Don't log these
- Successful validation
- Normal flow operations
- Sensitive data (API keys, passwords)
```

---

## WEBSOCKET PATTERNS

```python
from .broadcaster import broadcaster

@app.websocket("/ws/auditor")
async def websocket_auditor_endpoint(websocket: WebSocket):
    await websocket.accept()
    queue = await broadcaster.subscribe("auditor_events")
    
    try:
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        await AuditLogger.log("Client disconnected.")
    except Exception as e:
        await AuditLogger.log(f"WebSocket error: {e}", level=logging.ERROR)
    finally:
        broadcaster.unsubscribe("auditor_events", queue)
        await websocket.close()
```

---

## FILE ORGANIZATION

### Project Structure
```
src/
  ├── api.py                    # Main FastAPI app, core routes
  ├── neo4j_adapter.py          # Database utilities, connection management
  ├── models.py                 # Pydantic models and Enums
  ├── audit_log.py              # Logging utilities
  ├── broadcaster.py            # WebSocket event broadcaster
  ├── agents/
  │   ├── auditor_agent.py      # Contradiction detection
  │   └── query_agent.py        # Natural language queries
  ├── services/
  │   └── contradiction_service.py  # Contradiction routes & logic
  ├── templates/
  │   ├── dashboard.html
  │   ├── entities.html
  │   └── entity_detail.html
  └── static/                   # CSS, JS, images
```

### File Naming
- Python files: `snake_case.py`
- Templates: `snake_case.html`
- Services: `[resource]_service.py`
- Agents: `[name]_agent.py`

---

## COMMON PATTERNS & IDIOMS

### UUID Generation
```python
import uuid

# Canon ID with prefix
canon_id = f"{entity_type.value.lower()}-{uuid.uuid4().hex[:8]}"
# Result: "character-a3f9bc21"

# Contradiction ID
contradiction_id = f"test-{i}-{uuid4().hex[:6]}"
# Result: "test-0-d4e8ac"
```

### Timestamp Pattern
```python
from datetime import datetime, timezone

# Always use timezone-aware timestamps
created_at = datetime.now(timezone.utc).isoformat()
# Result: "2025-11-25T14:30:00+00:00"
```

### Optional Query Parameters
```python
@router.get("/entities")
async def list_entities(
    entity_type: Optional[EntityType] = None,
    approval_status: Optional[ApprovalStatus] = None,
    limit: int = 100
):
    # Build a dynamic Cypher query
    query = "MATCH (n:Entity)"
    where_clauses = []
    params = {"limit": limit}
    
    if entity_type:
        where_clauses.append("n.entity_type = $type")
        params["type"] = entity_type.value
    
    if approval_status:
        where_clauses.append("n.approval_status = $status")
        params["status"] = approval_status.value
        
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    query += " RETURN n LIMIT $limit"
    
    return await db.execute(query, params)
```

### Building Response with Nested Data
```python
# With a graph database, fetching nested data is done with a single query
query = """
    MATCH (e:Entity {canon_id: $canon_id})
    OPTIONAL MATCH (e)-[r]->(m)
    RETURN e, collect({relationship: type(r), neighbor: m}) AS relationships
"""
result = await db.execute(query, {"canon_id": canon_id})

if not result:
    raise HTTPException(404)

entity_props = result[0]['e']
relationships = result[0]['relationships']

# Pydantic can then be used to build the final response model
# (often requiring custom parsing logic to shape the graph result)
return EntityResponseWithRelationships(**entity_props, relationships=relationships)
```

---

## TESTING PATTERNS

### Test File Organization
```
tests/
  ├── conftest.py              # Core fixtures (mock_neo4j_db, client)
  ├── test_smoke.py            # Basic application health tests
  ├── test_entities_api.py     # Integration tests for entity endpoints
  └── test_contradictions_api.py # Integration tests for contradiction endpoints
```

### API Integration Tests
```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

def test_create_entity(client: TestClient, mock_neo4j_db: AsyncMock):
    # Configure mock DB for the test
    mock_neo4j_db.execute.side_effect = [
        [], # Mock CREATE call
        [{ "canon_id": "char-123", "canonical_name": "Test Character", ... }] # Mock GET call
    ]

    response = client.post("/entities", json={
        "entity_type": "Character",
        "canonical_name": "Test Character",
        "confidence_level": "CONFIRMED",
        "party_knowledge": "KNOWN"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data['canonical_name'] == "Test Character"
    assert data['canon_id'] == "char-123"
```

---

## COMMON MISTAKES TO AVOID

### ❌ WRONG: `json={{}}`
```python
# This causes TypeError: unhashable type: 'dict'
passed, _ = test_endpoint("POST", "/resolve", json={{}})
```

### ✅ CORRECT: `json={}`
```python
passed, _ = test_endpoint("POST", "/resolve", json={})
```

### ❌ WRONG: Forgetting `await`
```python
async def my_route(db: Neo4jDatabase = Depends(get_neo4j_db)):
    # This does not wait for the query to finish and will cause errors
    records = db.execute("MATCH (n) RETURN n")
```

### ✅ CORRECT: Use `await`
```python
async def my_route(db: Neo4jDatabase = Depends(get_neo4j_db)):
    # Always await calls to the async database adapter
    records = await db.execute("MATCH (n) RETURN n")
```

### ❌ WRONG: Forgetting Enum Conversion
```python
# Storing enum directly
Database.execute(conn, "INSERT INTO entities (type) VALUES (?)", (entity.entity_type,))
```

### ✅ CORRECT: Use .value
```python
Database.execute(conn, "INSERT INTO entities (type) VALUES (?)", (entity.entity_type.value,))
```

### ❌ WRONG: String Comparison with Enum
```python
if entity.status == "PENDING":  # Wrong - comparing Enum to string
```

### ✅ CORRECT: Enum Comparison
```python
if entity.status == ContradictionStatus.PENDING:  # Correct
```

---

## ENVIRONMENT CONFIGURATION

### Required Environment Variables
```bash
GEMINI_API_KEY=your_api_key_here
ENV=development  # or production
```

### Loading Configuration
```python
from dotenv import load_dotenv
import os

load_dotenv()

gemini_key = os.getenv("GEMINI_API_KEY")
if not gemini_key or gemini_key == "YOUR_KEY_HERE":
    await AuditLogger.log("GEMINI_API_KEY missing — continuing without remote features.", level=logging.WARNING)
```

---

## LIFESPAN MANAGEMENT

### App Startup/Shutdown
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup
    await AuditLogger.log("Application startup...")
    
    # Initialize Neo4j Database
    app.state.neo4j_db = Neo4jDatabase(...)
    await app.state.neo4j_db.connect()
    
    # Initialize agents with the database instance
    gemini_key = os.getenv("GEMINI_API_KEY")
    app.state.auditor = AuditorAgent(app.state.neo4j_db, gemini_key)
    app.state.query_agent = QueryAgent(app.state.neo4j_db, gemini_key)
    
    yield
    
    # On shutdown
    await app.state.neo4j_db.close()
    await AuditLogger.log("Application shutdown...")

app = FastAPI(lifespan=lifespan)
```

---

## STATIC FILES & TEMPLATES

### Configuration
```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
```

### Template Response
```python
from fastapi.responses import HTMLResponse
from fastapi import Request

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
```

---

## CORS CONFIGURATION

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## SUMMARY: QUICK REFERENCE

**When adding a new endpoint:**
1. ✅ Use async function signature
2. ✅ Pydantic model for request/response
3. ✅ Dependency injection for DB connection
4. ✅ Wrap database calls in `run_in_threadpool`
5. ✅ Use Enum.value when writing to DB
6. ✅ Convert strings to Enum when reading from DB
7. ✅ Log errors with AuditLogger
8. ✅ Return appropriate HTTP status codes
9. ✅ Add docstring
10. ✅ Handle exceptions with HTTPException

**When working with database:**
1. ✅ Use `Depends(get_neo4j_db)` for route injection.
2. ✅ `await` all database calls.
3. ✅ No `run_in_threadpool` needed for the native async driver.
4. ✅ Build graph-aware queries to prevent N+1 style problems.
5. ✅ Use Cypher query parameters to prevent injection.

**When using Enums:**
1. ✅ Store: `enum_value.value`
2. ✅ Load: `EnumType(string_value)`
3. ✅ Compare: `value == EnumType.MEMBER`
4. ✅ Never compare enum to string directly

**Gospel Principle enforcement:**
- ✅ AI agents suggest, never decide
- ✅ All canon decisions require human approval
- ✅ Log who made the decision
- ✅ Status updates must include `updated_by`

---

**Last Updated:** 2025-11-25
**Based on:** Actual LMS codebase (api.py, database.py, models.py, contradiction_service.py)
