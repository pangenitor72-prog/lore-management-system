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
    db: sqlite3.Connection = Depends(get_db)
) -> EntityResponse:
    pass

# Variables when type is ambiguous
entity_ids: List[str] = []
data: Dict[str, Any] = {}

# Return types always specified
def fetch_one(conn: sqlite3.Connection, query: str) -> Optional[dict]:
    pass
```

---

## FASTAPI PATTERNS

### Route Structure
```python
@router.post("/entities", response_model=EntityResponse, status_code=201)
async def create_entity(
    entity_data: EntityCreate,
    db: sqlite3.Connection = Depends(get_db)
) -> EntityResponse:
    """Creates a new entity in the database."""
    # Implementation
```

**Rules:**
- Async for all endpoints (even if mostly synchronous inside)
- Pydantic models for request/response
- Explicit status codes for non-200 responses
- Dependency injection for database connections
- Docstrings required on all routes

### Dependency Injection Pattern
```python
# Database connection dependency
async def get_db() -> Generator[sqlite3.Connection, None, None]:
    with db_session() as conn:
        yield conn

# Usage in route
async def my_route(db: sqlite3.Connection = Depends(get_db)):
    # db connection is managed by FastAPI
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
try:
    result = await operation(db)
except sqlite3.IntegrityError as e:
    await AuditLogger.log(f"Integrity error: {e}", level=logging.WARNING)
    if "UNIQUE constraint" in str(e):
        raise HTTPException(status_code=409, detail="Resource already exists")
    raise HTTPException(status_code=500, detail=f"Database error: {e}")
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
# NEVER manage connections manually in routes
# Use dependency injection
async def my_route(db: sqlite3.Connection = Depends(get_db)):
    # Connection automatically managed
```

### Transaction Pattern
```python
# Use db_session context manager for transactions
with db_session() as conn:
    Database.execute(conn, "INSERT INTO ...", params)
    Database.execute(conn, "UPDATE ...", params)
    # Commits on success, rolls back on exception
```

### Database Operations
```python
# Execute (with optional immediate commit)
cursor = Database.execute(
    conn, 
    "INSERT INTO entities (...) VALUES (?, ?)", 
    (value1, value2),
    commit=True  # Only if not in transaction
)

# Fetch one result
entity = await run_in_threadpool(
    Database.fetch_one, 
    db, 
    "SELECT * FROM entities WHERE canon_id = ?", 
    (canon_id,)
)

# Fetch multiple results
entities = await run_in_threadpool(
    Database.fetch_all,
    db,
    "SELECT * FROM entities WHERE type = ?",
    (entity_type,)
)
```

### Async Wrapper Pattern (Critical)
```python
# ALWAYS wrap blocking database calls in run_in_threadpool
from fastapi.concurrency import run_in_threadpool

# ✅ Correct
entity = await run_in_threadpool(
    Database.fetch_one, 
    db, 
    "SELECT * FROM entities WHERE id = ?", 
    (entity_id,)
)

# ❌ Wrong - blocks event loop
entity = Database.fetch_one(db, "SELECT * FROM entities WHERE id = ?", (entity_id,))
```

### Preventing N+1 Queries
```python
# ❌ Bad - N+1 query pattern
entities = fetch_all(db, "SELECT * FROM entities")
for entity in entities:
    aliases = fetch_all(db, "SELECT * FROM aliases WHERE canon_id = ?", (entity['canon_id'],))

# ✅ Good - Single query with JOIN or GROUP_CONCAT
query = """
    SELECT 
        e.*, 
        GROUP_CONCAT(a.alias) AS aliases
    FROM entities e
    LEFT JOIN aliases a ON e.canon_id = a.canon_id
    GROUP BY e.canon_id
"""
entities = fetch_all(db, query)
```

### SQLite Configuration (Always Set)
```python
conn.execute("PRAGMA foreign_keys = ON;")   # Enforce relationships
conn.execute("PRAGMA journal_mode=WAL;")    # Better concurrency
```

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
Database.execute(conn, "INSERT INTO entities (type) VALUES (?)", (entity.entity_type.value,))

# From DB: explicit conversion
entity_dict = Database.fetch_one(conn, "SELECT * FROM entities WHERE id = ?", (id,))
entity_type = EntityType(entity_dict['entity_type'])  # String → Enum
```

### JSON Field Handling
```python
# Storing JSON in SQLite
evidence_json = json.dumps(contradiction.evidence)
Database.execute(conn, "INSERT INTO contradictions (evidence) VALUES (?)", (evidence_json,))

# Loading JSON from SQLite
row = Database.fetch_one(conn, "SELECT evidence FROM contradictions WHERE id = ?", (id,))
evidence = json.loads(row['evidence']) if row['evidence'] else {}

# Pydantic automatically handles dict/JSON conversion
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
    db: sqlite3.Connection
) -> ContradictionResponse:
    """Fetch full contradiction data and return as ContradictionResponse."""
    contradiction_dict = await run_in_threadpool(
        Database.fetch_one, db,
        "SELECT * FROM contradictions WHERE contradiction_id = ?",
        (contradiction_id,)
    )
    
    if not contradiction_dict:
        raise HTTPException(status_code=404, detail=f"Not found: {contradiction_id}")
    
    # Build response
    return ContradictionResponse(**data)

# Called from routes
@router.post("/contradictions/{id}/resolve")
async def resolve_contradiction(id: str, db = Depends(get_db)):
    # ... logic ...
    return await get_contradiction_response(id, db)
```

### Status Update Functions
```python
# Synchronous helpers for status updates (called via run_in_threadpool)
def set_resolved(contradiction_id: str, user: str, notes: str, db: sqlite3.Connection) -> bool:
    """Sets contradiction status to RESOLVED."""
    try:
        updated = Database.execute(
            db,
            "UPDATE contradictions SET status = ?, resolution_notes = ?, updated_by = ? WHERE contradiction_id = ?",
            (ContradictionStatus.RESOLVED.value, notes, user, contradiction_id),
            commit=True
        )
        if updated.rowcount == 0:
            AuditLogger.log_sync(f"Contradiction {contradiction_id} not found.", level=logging.WARNING)
            return False
        AuditLogger.log_sync(f"Contradiction {contradiction_id} resolved by {user}.")
        return True
    except Exception as e:
        AuditLogger.log_sync(f"Error: {e}", level=logging.ERROR)
        return False

# Called from async route
success = await run_in_threadpool(set_resolved, contradiction_id, user, notes, db)
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
  ├── database.py               # Database utilities, connection management
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
    query = "SELECT * FROM entities"
    params = []
    conditions = []
    
    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type.value)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " LIMIT ?"
    params.append(limit)
    
    return Database.fetch_all(db, query, tuple(params))
```

### Building Response with Nested Data
```python
# Fetch main entity
entity = Database.fetch_one(db, "SELECT * FROM entities WHERE canon_id = ?", (canon_id,))

# Fetch related data
aliases = Database.fetch_all(db, "SELECT alias FROM aliases WHERE canon_id = ?", (canon_id,))
fields = Database.fetch_all(db, "SELECT field_key, field_value FROM approved_fields WHERE canon_id = ?", (canon_id,))

# Parse JSON fields
approved_fields_parsed = {}
for f in fields:
    try:
        approved_fields_parsed[f['field_key']] = json.loads(f['field_value'])
    except (json.JSONDecodeError, TypeError):
        approved_fields_parsed[f['field_key']] = f['field_value']

# Build response
return EntityResponse(
    canon_id=entity['canon_id'],
    entity_type=EntityType(entity['entity_type']),
    aliases=[a['alias'] for a in aliases],
    approved_fields=approved_fields_parsed,
    # ... other fields
)
```

---

## TESTING PATTERNS

### Test File Organization
```
tests/
  ├── test_entities.py
  ├── test_contradictions.py
  └── test_database.py
```

### API Integration Tests
```python
import pytest
from fastapi.testclient import TestClient

def test_create_entity(client: TestClient):
    response = client.post("/entities", json={
        "entity_type": "Character",
        "canonical_name": "Test Character",
        "confidence_level": "CONFIRMED",
        "party_knowledge": "KNOWN"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data['canonical_name'] == "Test Character"
    assert 'canon_id' in data
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

### ❌ WRONG: Mixing Sync/Async
```python
async def my_route(db = Depends(get_db)):
    # Blocking call in async function
    entity = Database.fetch_one(db, "SELECT ...")  # Blocks event loop
```

### ✅ CORRECT: Wrap Blocking Calls
```python
async def my_route(db = Depends(get_db)):
    entity = await run_in_threadpool(Database.fetch_one, db, "SELECT ...")
```

### ❌ WRONG: Committing in Route
```python
@router.post("/entities")
async def create_entity(entity: EntityCreate, db = Depends(get_db)):
    Database.execute(db, "INSERT INTO entities ...", commit=True)  # Don't do this
```

### ✅ CORRECT: Use Transaction
```python
@router.post("/entities")
async def create_entity(entity: EntityCreate, db = Depends(get_db)):
    def _create_entity_db(conn):
        Database.execute(conn, "INSERT INTO entities ...")
        Database.execute(conn, "INSERT INTO aliases ...")
    
    await run_in_threadpool(_create_entity_db, db)  # Transaction handled by db_session
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
    
    gemini_key = os.getenv("GEMINI_API_KEY")
    app.state.auditor = AuditorAgent(get_db_connection, gemini_key)
    app.state.query_agent = QueryAgent(get_db_connection, gemini_key)
    
    # Initialize database schema
    _ = Database()
    
    yield
    
    # On shutdown
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
1. ✅ Use `db_session()` context manager for transactions
2. ✅ Use `Depends(get_db)` for route injection
3. ✅ Always wrap in `run_in_threadpool`
4. ✅ Set PRAGMA foreign_keys and journal_mode
5. ✅ Avoid N+1 queries with JOINs/GROUP_CONCAT

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
