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

### Error: Connection Refused / Timeout

**Symptom:** The application fails to start, or API calls fail with a service unavailable error. Logs show `Connection refused` or a timeout error when trying to connect to Neo4j.

**Cause:**
1.  The Neo4j database is not running.
2.  The `NEO4J_URI`, `NEO4J_USER`, or `NEO4J_PASSWORD` in your `.env` file are incorrect.
3.  A firewall is blocking the connection to the Neo4j port (usually 7687).

**Solution:**
```bash
# 1. Check if the Neo4j Docker container is running
docker-compose ps

# 2. If not running, start it
docker-compose up -d

# 3. Verify your .env file credentials match your docker-compose.yml setup
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=password

# 4. Test the connection manually using cypher-shell
cypher-shell -a "bolt://localhost:7687" -u neo4j -p password
```

---

### Error: `Neo4jError: ConstraintValidationFailed`

**Symptom:** Creating a node fails with a constraint validation error.

**Cause:** You are trying to create a node that violates a uniqueness constraint (e.g., creating a node with a `canon_id` that already exists).

**Solution:**
- Ensure you are generating unique `canon_id` values for new entities.
- If you intend to update an existing entity, use `MERGE` instead of `CREATE` in your Cypher query.
- Example of a safe creation query: `MERGE (n:Entity {canon_id: $id}) ON CREATE SET n.name = $name ...`

---

### Error: Vector Index Creation Failed

**Symptom:** At startup, logs show `Vector index validation failed` or `Failed to create vector index`.

**Cause:**
1.  The version of Neo4j you are using does not support vector indexes.
2.  There is a syntax error in the `create_vector_index` method in `src/neo4j_adapter.py`.

**Solution:**
- Ensure you are using a compatible version of Neo4j (e.g., 5.11+).
- Check the Neo4j logs for more detailed error messages regarding the index creation.
- The system can run without vector search in a degraded mode, but semantic search features will be unavailable.

---

### Error: Inconsistent Graph State

**Symptom:** Queries return unexpected results, relationships are missing, or nodes have partial data.

**Cause:** A multi-step transaction was interrupted, or data was written incorrectly.

**Solution:**
- Use the Neo4j Browser (`http://localhost:7474`) to visually inspect the graph.
- Write Cypher queries to find the inconsistent data. For example, to find `Character` nodes without a `name` property:
  ```cypher
  MATCH (c:Character) WHERE c.name IS NULL RETURN c
  ```
- Use the `scripts/clear_db.py` script to wipe the database and start over from a clean state if the corruption is severe and you can re-ingest the data.


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
# 1. Use MERGE to handle this atomically in the database
# MERGE will find a node if it exists or create it if it doesn't.
# This avoids a separate SELECT call.
await db.execute(
    "MERGE (c:Contradiction {contradiction_id: $id}) ON CREATE SET c.is_new = true",
    {"id": contradiction_id}
)

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

### Error: Forgetting `await` on an async call

**Symptom:** `TypeError: 'coroutine' object is not subscriptable` or other unexpected errors.

**Cause:** Calling an `async` function without `await` returns a coroutine object, not the result.

**Solution:**
```python
# ❌ Wrong - doesn't wait for the query to finish
async def get_entity(canon_id: str, db: Neo4jDatabase = Depends(get_neo4j_db)):
    records = db.execute("MATCH (n) WHERE n.id = $id RETURN n", {"id": id})
    return records[0] # This will fail, `records` is a coroutine

# ✅ Correct - awaits the async database call
async def get_entity(canon_id: str, db: Neo4jDatabase = Depends(get_neo4j_db)):
    records = await db.execute("MATCH (n) WHERE n.id = $id RETURN n", {"id": id})
    return records[0]
```

**Rule of Thumb:**
- Any method on the `Neo4jDatabase` adapter is `async` and must be `await`ed.
- The `run_in_threadpool` wrapper is no longer needed for database calls.

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

### Issue: Slow Cypher Queries

**Symptom:** API endpoints are slow.

**Cause:** Inefficient Cypher query that isn't using an index or is performing a very large graph traversal.

**Solution:**
- Use the Neo4j Browser (`http://localhost:7474`) to `PROFILE` or `EXPLAIN` your query.
- Look for operations like `NodeByLabelScan` instead of `NodeIndexSeek`.
- Ensure you have indexes on the properties you are querying (e.g., `canon_id`, `name`).
- Rework the query to be more efficient, starting from indexed nodes and traversing as little of the graph as possible.
- Example: `CREATE INDEX entity_name_index IF NOT EXISTS FOR (n:Entity) ON (n.name);`

---

### Issue: High memory usage

**Symptom:** Python process or Neo4j server using excessive RAM.

**Cause:** A query is returning a huge number of nodes or relationships, which are then loaded into memory.

**Solution:**
- Always use `LIMIT` in your Cypher queries, especially for listing endpoints.
- Implement pagination using `SKIP` and `LIMIT`.
- Avoid returning entire nodes (`RETURN n`) when you only need a few properties (`RETURN n.name, n.canon_id`).

---

### Issue: Slow Vector Searches

**Symptom:** Semantic searches are slow.

**Cause:**
1.  A vector index does not exist or is not being used.
2.  The query is not selective enough.

**Solution:**
- Verify the vector index exists using `SHOW INDEXES` in Neo4j Browser.
- Use a higher `min_score` threshold in your `vector_search` call to return fewer, more relevant results.
- Combine vector search with other filters (e.g., on node labels or properties) to narrow down the search space.

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

### Error: Mock database not configured correctly

**Symptom:** Tests that interact with the database fail with `422 Unprocessable Entity`, `404 Not Found`, or other unexpected errors.

**Cause:** The `mock_neo4j_db` fixture from `conftest.py` is being used, but it has not been configured to provide the correct return values for the specific database calls made during the test.

**Solution:**
```python
# In your test function, configure the mock's side_effect
def test_my_api_call(client: TestClient, mock_neo4j_db: AsyncMock):
    # This test expects two db calls: a CREATE, then a GET
    mock_neo4j_db.execute.side_effect = [
        [],  # Return for the CREATE
        [{'canon_id': 'abc', ...}] # Return for the GET
    ]
    
    response = client.post("/my-endpoint", json={...})
    
    assert response.status_code == 201
```

**Rule of Thumb:**
- Every database call made within the code path your test is exercising needs a corresponding return value configured in your mock's `side_effect` list.
- Check the endpoint logic to see how many times `db.execute` (or similar) is called.

---

## Emergency Recovery Procedures

### Corrupted Database

```bash
# 1. Stop server and Neo4j
docker-compose down

# 2. Backup current state (even if corrupted)
# The data is typically in a volume managed by Docker. Find the volume name:
docker volume ls
# Then back it up (this can be complex, consult Docker/Neo4j docs)

# 3. If no backup, the simplest recovery is to reset and re-ingest
# WARNING: THIS DELETES ALL DATA
docker-compose down -v # The -v flag removes the volume
docker-compose up -d

# 4. Re-ingest your lore files using the Ingestion UI
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

# 4. Check database connection
docker-compose ps # Ensure neo4j container is running
cypher-shell -a "bolt://localhost:7687" -u neo4j -p yourpassword "MATCH (n) RETURN count(n);"

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
