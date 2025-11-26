# LMS Troubleshooting Guide
**Common Issues & Solutions**

**Last Updated:** 2025-11-25  
**Applies To:** LMS v1.0.0 (Phases I-XII)

---

## Table of Contents
1. [Quick Diagnostics](#quick-diagnostics)
2. [Database Issues](#database-issues)
3. [API Errors](#api-errors)
4. [Python/Syntax Errors](#pythonsyntax-errors)
5. [Async/Threading Issues](#asyncthreading-issues)
6. [Pydantic/Validation Errors](#pydanticvalidation-errors)
7. [Development Environment Issues](#development-environment-issues)
8. [AI Agent Issues](#ai-agent-issues)
9. [Frontend/WebSocket Issues](#frontendwebsocket-issues)
10. [Performance Issues](#performance-issues)
11. [Testing Issues](#testing-issues)

---

## Quick Diagnostics

### Is the server running?
```bash
# Check if process is running
ps aux | grep uvicorn

# Check if port is in use
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Expected: Should see uvicorn process on port 8000
```

### Quick health check
```bash
# Hit root endpoint
curl http://localhost:8000/

# Expected response:
# {"message": "Lore Management System API", "version": "1.0.0", "status": "operational"}
```

### Check logs
```bash
# Logs go to console when running uvicorn
# Look for errors, warnings, or stack traces

# Common log patterns:
# ✓ "Application startup..." - Server started
# ✓ "Schema initialized successfully" - Database ready
# ✗ "Failed to initialize schema" - Database problem
# ✗ "GEMINI_API_KEY missing" - API key not set (non-critical)
```

---

## Database Issues

### Error: `sqlite3.OperationalError: database is locked`

**Symptom:** Database operations fail with "database is locked"

**Cause:** Multiple connections trying to write simultaneously, or WAL mode not enabled

**Solution:**
```python
# 1. Verify WAL mode is enabled in connection
conn.execute("PRAGMA journal_mode=WAL;")

# 2. Ensure using db_session() context manager
with db_session() as conn:
    Database.execute(conn, "INSERT INTO ...")
    # Commits on exit

# 3. Check for long-running transactions
# Don't keep connections open across multiple requests
```

**Prevention:**
- Always use `db_session()` for transactions
- Use `Depends(get_db)` for route handlers
- Don't manually manage connections
- WAL mode is set automatically in `get_db_connection()`

---

### Error: `FOREIGN KEY constraint failed`

**Symptom:** Insert/update fails with foreign key violation

**Cause:** Trying to reference non-existent entity or relationship

**Solution:**
```python
# 1. Check that referenced entity exists
entity = Database.fetch_one(db, "SELECT * FROM entities WHERE canon_id = ?", (canon_id,))
if not entity:
    raise HTTPException(status_code=404, detail="Referenced entity not found")

# 2. Verify foreign keys are enabled
conn.execute("PRAGMA foreign_keys = ON;")  # This is set automatically

# 3. Check data integrity
# Make sure canon_id values match between tables
```

**Common Scenarios:**
- Adding alias for non-existent entity
- Creating relationship with invalid canon_id
- Linking contradiction to missing entity

---

### Error: Database file not found

**Symptom:** `sqlite3.OperationalError: unable to open database file`

**Cause:** Database path doesn't exist or permissions issue

**Solution:**
```bash
# 1. Check if data directory exists
ls -la data/

# 2. Create directory if missing
mkdir -p data

# 3. Verify file permissions
chmod 644 data/lore.db  # If file exists

# 4. Check DB_PATH in database.py
# Should be: Path(__file__).parent.parent / "data/lore.db"
```

**Prevention:**
- `Database.__init__()` creates directory automatically
- Don't move database file manually
- Use environment-based paths for different environments

---

### Schema initialization failed

**Symptom:** `CRITICAL: Failed to initialize schema`

**Cause:** Missing `data/schema.sql` or SQL syntax error

**Solution:**
```bash
# 1. Verify schema.sql exists
ls -la data/schema.sql

# 2. Check for SQL syntax errors
sqlite3 :memory: < data/schema.sql

# 3. If schema is corrupted, regenerate from backup
# Or restore from version control

# 4. Delete database and reinitialize
rm data/lore.db
# Restart server (schema auto-initializes)
```

---

### Database corruption

**Symptom:** Random errors, inconsistent data, WAL file issues

**Solution:**
```bash
# 1. Check database integrity
sqlite3 data/lore.db "PRAGMA integrity_check;"

# Expected output: "ok"

# 2. If corrupted, recover from backup
cp data/lore.db data/lore.db.backup
# Restore from last known good backup

# 3. If no backup, try to recover
sqlite3 data/lore.db ".dump" > recovery.sql
rm data/lore.db
sqlite3 data/lore.db < recovery.sql
```

**Prevention:**
- Regular backups (copy `data/lore.db`)
- Don't kill server process forcefully
- Use `db_session()` for transaction safety

---

## API Errors

### Error: `404 Not Found` on valid endpoint

**Symptom:** Endpoint exists but returns 404

**Cause:** Router not included in main app, or path prefix issue

**Solution:**
```python
# 1. Check router is included in api.py
app.include_router(router)  # Core routes
app.include_router(get_contradiction_router())  # Service routes

# 2. Check APIRouter prefix
router = APIRouter(prefix="/api")  # Adds /api to all routes

# 3. Verify full path
# If router has prefix="/api" and route is @router.get("/contradictions")
# Full path is: /api/contradictions

# 4. Check for typos in path
# "/entities" vs "/entity" - must match exactly
```

---

### Error: `422 Unprocessable Entity`

**Symptom:** Request fails validation

**Cause:** Invalid enum value, missing required field, or type mismatch

**Solution:**
```python
# Check response for validation details
{
  "detail": [
    {
      "loc": ["body", "entity_type"],
      "msg": "value is not a valid enumeration member",
      "type": "type_error.enum"
    }
  ]
}

# Common fixes:
# 1. Use exact enum values (case-sensitive)
"entity_type": "Character"  # ✓ Correct
"entity_type": "character"  # ✗ Wrong case

# 2. Check required fields in Pydantic model
class EntityCreate(BaseModel):
    entity_type: EntityType  # Required
    canonical_name: str = Field(min_length=1)  # Required
    aliases: List[str] = Field(default_factory=list)  # Optional

# 3. Verify data types
"confidence_level": "CONFIRMED"  # ✓ String
"confidence_level": 1  # ✗ Integer
```

---

### Error: `409 Conflict`

**Symptom:** Duplicate resource error

**Cause:** Attempting to create resource with existing unique identifier

**Solution:**
```python
# 1. Check for existing resource first
existing = Database.fetch_one(db, 
    "SELECT * FROM contradictions WHERE contradiction_id = ?", 
    (contradiction_id,)
)
if existing:
    raise HTTPException(status_code=409, detail="Already exists")

# 2. Generate unique IDs
contradiction_id = str(uuid.uuid4())  # Always unique

# 3. Handle duplicate gracefully in frontend
# Show message: "This resource already exists"
```

---

### Error: `500 Internal Server Error`

**Symptom:** Generic server error

**Cause:** Unhandled exception, database error, or logic bug

**Solution:**
```python
# 1. Check server logs for full traceback
# Look for actual error before HTTPException is raised

# 2. Add try/except around suspicious code
try:
    result = await operation()
except Exception as e:
    await AuditLogger.log(f"Error: {e}", level=logging.ERROR)
    raise HTTPException(status_code=500, detail=str(e))

# 3. Common causes:
# - Missing run_in_threadpool wrapper
# - Enum not converted to .value before DB insert
# - JSON decode error on invalid data
# - Database transaction not committed
```

---

## Python/Syntax Errors

### Error: `TypeError: unhashable type: 'dict'`

**Symptom:** Error when passing `json={{}}` to requests

**Cause:** Double braces create a set with a dict, which is unhashable

**Solution:**
```python
# ❌ Wrong
response = requests.post(url, json={{}})

# ✅ Correct
response = requests.post(url, json={})
```

**Where This Happens:**
- Test files using `requests` library
- Any code creating empty JSON body
- Mistaken syntax thinking `{{}}` means "empty object"

---

### Error: `AttributeError: 'str' object has no attribute 'value'`

**Symptom:** Trying to call `.value` on string

**Cause:** Variable is already a string, not an Enum

**Solution:**
```python
# Check type before calling .value
if isinstance(status, ContradictionStatus):
    status_str = status.value  # Enum → string
else:
    status_str = status  # Already string

# Better: Always use Enum types
status: ContradictionStatus = ContradictionStatus.PENDING
Database.execute(conn, "INSERT ... VALUES (?)", (status.value,))
```

---

### Error: `ValueError: 'invalid_value' is not a valid ContradictionStatus`

**Symptom:** Invalid string passed to Enum constructor

**Cause:** Database returned invalid status, or user input not validated

**Solution:**
```python
# Add validation before Enum conversion
try:
    status = ContradictionStatus(status_str)
except ValueError:
    await AuditLogger.log(f"Invalid status: {status_str}", level=logging.ERROR)
    # Use default or raise error
    status = ContradictionStatus.PENDING

# Or validate in Pydantic model
class ContradictionUpdate(BaseModel):
    status: ContradictionStatus  # Validates automatically
```

---

## Async/Threading Issues

### Error: Blocking operation in async function

**Symptom:** Performance degrades, or "Event loop is closed" error

**Cause:** Synchronous I/O in async function blocks event loop

**Solution:**
```python
# ❌ Wrong - blocks event loop
async def get_entity(canon_id: str, db = Depends(get_db)):
    entity = Database.fetch_one(db, "SELECT ...", (canon_id,))  # Blocking!
    return entity

# ✅ Correct - wrapped in threadpool
async def get_entity(canon_id: str, db = Depends(get_db)):
    entity = await run_in_threadpool(
        Database.fetch_one, db, "SELECT ...", (canon_id,)
    )
    return entity
```

**Rule of Thumb:**
- Any `Database.*` call → wrap in `run_in_threadpool`
- Any file I/O → wrap in `run_in_threadpool`
- Any network I/O → use async library or wrap
- CPU-bound work → wrap in `run_in_threadpool`

---

### Error: `RuntimeError: cannot reuse already awaited coroutine`

**Symptom:** Trying to await same coroutine twice

**Cause:** Storing coroutine result and trying to await again

**Solution:**
```python
# ❌ Wrong
result = some_async_function()  # Creates coroutine
value1 = await result  # Awaits coroutine
value2 = await result  # Error - already awaited!

# ✅ Correct
value = await some_async_function()  # Await immediately
# Use 'value' multiple times (not coroutine)
```

---

### Error: Mixing async and sync logging

**Symptom:** Logs not appearing or error about event loop

**Cause:** Using wrong logger method

**Solution:**
```python
# In async context (route handlers)
await AuditLogger.log("Message", level=logging.INFO)

# In sync context (helper functions, non-async code)
AuditLogger.log_sync("Message", level=logging.INFO)

# ❌ Wrong - sync method in async function
async def my_route():
    AuditLogger.log_sync("...")  # May cause issues

# ✅ Correct
async def my_route():
    await AuditLogger.log("...")
```

---

## Pydantic/Validation Errors

### Error: Field validation fails silently

**Symptom:** Invalid data passes through Pydantic model

**Cause:** Missing validation, or field is `Any` type

**Solution:**
```python
# Add explicit validators
class EntityCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=500)
    
    @field_validator('canonical_name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()
```

---

### Error: `ConfigDict` not recognized

**Symptom:** Pydantic v2 config not working

**Cause:** Using Pydantic v1 syntax in v2 environment

**Solution:**
```python
# ❌ Pydantic v1 syntax
class MyModel(BaseModel):
    class Config:
        orm_mode = True

# ✅ Pydantic v2 syntax
class MyModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```

---

### Error: JSON serialization fails

**Symptom:** `TypeError: Object of type X is not JSON serializable`

**Cause:** Non-serializable type (datetime, Enum) in response

**Solution:**
```python
# Pydantic handles this automatically in response models
# But for manual JSON:

import json
from datetime import datetime

# ❌ Wrong
data = {"created_at": datetime.now()}
json.dumps(data)  # Error!

# ✅ Correct - convert to string
data = {"created_at": datetime.now().isoformat()}
json.dumps(data)  # Works

# ✅ Better - use Pydantic
class MyResponse(BaseModel):
    created_at: datetime  # Pydantic handles serialization
```

---

## Development Environment Issues

### Error: `ModuleNotFoundError: No module named 'src'`

**Symptom:** Import fails when running from wrong directory

**Cause:** Not running from project root

**Solution:**
```bash
# Run from project root
cd /path/to/lore-system
python -m pytest  # ✓ Correct

# Don't run from subdirectory
cd /path/to/lore-system/src
python api.py  # ✗ Wrong - imports will fail
```

---

### Error: Port 8000 already in use

**Symptom:** `OSError: [Errno 48] Address already in use`

**Cause:** Another process using port 8000, or zombie uvicorn process

**Solution:**
```bash
# Find process using port
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process
kill -9 <PID>  # Mac/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port
uvicorn src.api:app --port 8001
```

---

### Error: `.env` file not loaded

**Symptom:** Environment variables not available

**Cause:** `.env` file missing or not in project root

**Solution:**
```bash
# 1. Create .env file in project root
cp .env.example .env

# 2. Add required variables
echo "GEMINI_API_KEY=your_key_here" >> .env
echo "ENV=development" >> .env

# 3. Verify loading in code
from dotenv import load_dotenv
load_dotenv()  # Must be called before accessing os.getenv()
```

---

### Error: Missing dependencies

**Symptom:** `ImportError: cannot import name 'X'`

**Cause:** Package not installed

**Solution:**
```bash
# Install all dependencies
pip install -r requirements.txt

# If specific package missing
pip install fastapi uvicorn pydantic

# Verify installation
pip list | grep fastapi
```

---

## AI Agent Issues

### Error: `GEMINI_API_KEY missing`

**Symptom:** Warning log about missing API key

**Cause:** `.env` file doesn't have valid key

**Impact:** Non-critical - system continues without AI features

**Solution:**
```bash
# 1. Get API key from Google AI Studio
# https://makersuite.google.com/app/apikey

# 2. Add to .env file
GEMINI_API_KEY=your_actual_key_here

# 3. Restart server
# uvicorn will reload .env on startup
```

**Note:** System is designed to work without Gemini API. AI features will be disabled but core functionality remains operational.

---

### Error: Agent returns empty/null results

**Symptom:** Contradiction detection or query returns no results

**Possible Causes:**
1. No actual contradictions in data (expected behavior)
2. Agent logic error
3. API rate limiting
4. Malformed prompts

**Debug Steps:**
```python
# 1. Check agent logs
await AuditLogger.log("Agent analysis starting...")

# 2. Verify input data
await AuditLogger.log(f"Analyzing {len(entities)} entities")

# 3. Test API connection separately
# Send simple test prompt to Gemini

# 4. Check rate limits in API response headers
```

---

## Frontend/WebSocket Issues

### Error: WebSocket connection fails

**Symptom:** `WebSocket connection to 'ws://localhost:8000/ws/auditor' failed`

**Cause:** Server not running, or endpoint not registered

**Solution:**
```javascript
// 1. Check server is running
// curl http://localhost:8000/

// 2. Verify WebSocket endpoint exists in api.py
@app.websocket("/ws/auditor")
async def websocket_auditor_endpoint(websocket: WebSocket):
    # ...

// 3. Check browser console for errors
// Look for CORS issues or connection refused

// 4. Test WebSocket with simple client
const ws = new WebSocket('ws://localhost:8000/ws/auditor');
ws.onopen = () => console.log('Connected');
ws.onerror = (e) => console.error('Error:', e);
```

---

### Error: Real-time updates not working

**Symptom:** UI doesn't update when contradiction created

**Cause:** WebSocket not connected, or events not broadcast

**Solution:**
```python
# 1. Verify broadcaster is publishing
from src.broadcaster import broadcaster
await broadcaster.publish("auditor_events", {
    "type": "contradiction_detected",
    "data": {...}
})

# 2. Check WebSocket handler is subscribed
queue = await broadcaster.subscribe("auditor_events")

# 3. Verify frontend is listening
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
    // Update UI here
};
```

---

### Error: Chart.js not rendering

**Symptom:** Dashboard shows empty space where chart should be

**Cause:** Chart.js not loaded, or canvas element missing

**Solution:**
```html
<!-- 1. Verify Chart.js is loaded -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<!-- 2. Check canvas element exists -->
<canvas id="myChart"></canvas>

<!-- 3. Verify data format -->
<script>
const ctx = document.getElementById('myChart').getContext('2d');
const chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: {{ labels | tojson }},  // From Jinja2
        datasets: [{
            data: {{ scores | tojson }}
        }]
    }
});
</script>
```

---

## Performance Issues

### Issue: Slow list endpoints

**Symptom:** `/entities` or `/contradictions` takes >1 second

**Cause:** N+1 query pattern - fetching related data in loop

**Solution:**
```python
# ❌ Bad - N+1 queries
entities = Database.fetch_all(db, "SELECT * FROM entities")
for entity in entities:
    # This runs a query for EACH entity!
    aliases = Database.fetch_all(db, 
        "SELECT * FROM aliases WHERE canon_id = ?", 
        (entity['canon_id'],)
    )

# ✅ Good - Single query with JOIN
query = """
    SELECT 
        e.*,
        GROUP_CONCAT(a.alias) AS aliases
    FROM entities e
    LEFT JOIN aliases a ON e.canon_id = a.canon_id
    GROUP BY e.canon_id
"""
entities = Database.fetch_all(db, query)
```

**Check For:**
- Multiple `fetch_all` calls in loops
- Separate queries for related data
- Missing JOIN clauses

---

### Issue: High memory usage

**Symptom:** Python process using excessive RAM

**Cause:** Large result sets loaded into memory, or connection leak

**Solution:**
```python
# 1. Limit query results
query += " LIMIT 100"  # Don't fetch entire table

# 2. Use pagination
@router.get("/entities")
async def list_entities(
    offset: int = 0,
    limit: int = 100
):
    query += " LIMIT ? OFFSET ?"
    return Database.fetch_all(db, query, (limit, offset))

# 3. Check for connection leaks
# Always use Depends(get_db) or db_session()
# Never create connections manually without cleanup
```

---

### Issue: Database file growing too large

**Symptom:** `lore.db` is multiple GB

**Cause:** No cleanup of old WAL files, or excessive logging

**Solution:**
```bash
# 1. Check WAL file size
ls -lh data/lore.db*

# 2. Checkpoint WAL to main database
sqlite3 data/lore.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 3. Vacuum database (reclaim space)
sqlite3 data/lore.db "VACUUM;"

# 4. Consider archiving old data
# Move resolved contradictions to archive table
```

---

## Testing Issues

### Error: Tests fail but API works

**Symptom:** `test_api_integration.py` fails but manual testing succeeds

**Cause:** Test expects different status code, or data format changed

**Solution:**
```python
# 1. Check expected vs actual status codes
passed, response = test_endpoint("POST", "/entities", expected_status=201)
# If fails, check what status was actually returned

# 2. Print response for debugging
print(f"Response: {response.json()}")

# 3. Update test expectations if API changed intentionally
# Don't change API to match tests - tests should match API

# 4. Check for test data conflicts
# Tests might create data that conflicts with existing data
```

---

### Error: Database locked during tests

**Symptom:** Tests fail with "database is locked"

**Cause:** Tests not cleaning up connections, or parallel execution

**Solution:**
```python
# 1. Use separate test database
DB_PATH = Path("data/test_lore.db")

# 2. Clean up between tests
import pytest

@pytest.fixture
def db():
    conn = get_db_connection()
    yield conn
    conn.close()

# 3. Don't run tests in parallel for SQLite
pytest -n 1  # Single process

# 4. Use transactions that rollback
@pytest.fixture
def db_transaction():
    with db_session() as conn:
        yield conn
        conn.rollback()  # Undo test changes
```

---

## Emergency Recovery Procedures

### Corrupted Database

```bash
# 1. Stop server immediately
kill <uvicorn_pid>

# 2. Backup current state (even if corrupted)
cp data/lore.db data/lore.db.corrupted.$(date +%Y%m%d)

# 3. Attempt integrity check
sqlite3 data/lore.db "PRAGMA integrity_check;"

# 4. If corrupted, dump and reload
sqlite3 data/lore.db ".dump" > dump.sql
rm data/lore.db
sqlite3 data/lore.db < dump.sql

# 5. If still broken, restore from backup
cp data/lore.db.backup data/lore.db

# 6. Restart server
uvicorn src.api:app --reload
```

---

### System Won't Start

```bash
# 1. Check Python version
python --version  # Must be 3.11+

# 2. Check dependencies
pip list | grep -E "fastapi|pydantic|uvicorn"

# 3. Check for syntax errors
python -m py_compile src/api.py

# 4. Check database
ls -la data/lore.db
sqlite3 data/lore.db "SELECT COUNT(*) FROM entities;"

# 5. Check logs for clues
# Look at full traceback in terminal

# 6. Nuclear option - fresh install
pip uninstall -y fastapi pydantic uvicorn
pip install -r requirements.txt
```

---

## Getting Help

### Before Asking for Help

1. **Check logs** - Full error message and stack trace
2. **Check this guide** - Search for error message
3. **Verify basics** - Server running? Database exists? Dependencies installed?
4. **Minimal reproduction** - Can you reproduce with curl/requests?
5. **Recent changes** - What changed since it last worked?

### Information to Include

```
- Error message (full traceback)
- LMS version (git commit hash)
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant log entries
- Recent changes to code
```

### Where to Get Help

- **Project documentation**: `docs/` directory
- **Code comments**: Search codebase for relevant function
- **Git history**: `git log` to see what changed
- **Test files**: See how features are tested

---

**Last Updated:** 2025-11-25  
**Maintainer:** Shawn King  
**Status:** Living document - add issues as you encounter them

**Contribution:** When you hit a new issue and solve it, add it here!
