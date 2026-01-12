# LMS DASHBOARD DEVELOPMENT - GEMINI HANDOFF

## CONTEXT
Shawn is building a unified dashboard UI for his Lore Management System (LMS). The backend is fortified and ready. Jim (the end user) will upload text files containing 30 years of D&D campaign lore. The system needs to make ingestion frictionless.

## CURRENT STATE
- Base dashboard shell is complete (lms-dashboard.html in outputs folder)
- "Haunting Machine" aesthetic: dark (#0a0a0a bg), monospaced font (Courier New), minimal, purposeful
- 5 tabs: INTAKE (default), ENTITIES, CONTRADICTIONS, CANON, SYSTEM
- Upload zone functional (drag-drop, click-to-browse)
- Simulated queue/results display working
- File types: .txt and .md only

## PROJECT ARCHITECTURE
- Single dashboard.html with tab switching
- Backend API at `/api` endpoints (already built)
- Processing pipeline: Upload → Queue → Entity Extraction → Contradiction Detection → Results
- Gospel Principle: Humans make canon decisions, AI detects/flags issues

## INTAKE VIEW (CURRENT TAB)
Components:
1. Upload zone (drag-drop area)
2. Queue display (shows processing files)
3. Batch results (summary cards: files processed, entities found, contradictions detected)

## WHAT NEEDS TO BE BUILT NEXT

### PRIORITY 1: Wire Backend Integration
Replace simulated processing with actual API calls:
- POST `/api/upload` - Upload files to backend
- GET `/api/queue` - Check processing status
- GET `/api/batch-results/{batch_id}` - Get results after processing

### PRIORITY 2: Entity Browser (Phase XII)
Build the ENTITIES tab view:
- Search/filter bar
- Entity list (name, type, source file, confidence score)
- Entity detail panel (when clicked)
- "View source context" feature

### PRIORITY 3: Contradiction Review
Build the CONTRADICTIONS tab view:
- Use existing contradiction_card.html aesthetic
- List of detected contradictions
- Card UI showing: type, severity, conflicting entities, evidence
- Resolution workflow (mark as resolved, escalate to canon)

### PRIORITY 4: Canon Management
Build the CANON tab:
- Log of human authority decisions
- "Resolve contradiction" interface
- Audit trail (who decided what, when)

### PRIORITY 5: System Status
Build the SYSTEM tab:
- Backend health indicators
- Processing metrics
- Error logs
- Database stats

## STYLING GUIDELINES
- Background: #0a0a0a (main), #0f0f0f (cards), #111 (header)
- Text: #e0e0e0 (primary), #888 (secondary), #666 (tertiary)
- Borders: #333 (primary), #222 (subtle)
- Accents: #4a4 (success/active), #88a (processing), #a44 (warning)
- Font: 'Courier New', monospace
- Letter spacing: 0.1-0.2em for headers
- No rounded corners, minimal padding, purposeful negative space

## TECHNICAL NOTES
- File input accepts: .txt, .md
- Backend returns JSON responses
- All API calls should be async
- Show loading states during processing
- Update queue in real-time if possible
- Results cards have action buttons that switch tabs

## BACKEND API ENDPOINTS (ASSUMED)
```
POST   /api/upload           - Upload batch of files
GET    /api/queue            - Get current queue status
GET    /api/results/{id}     - Get batch results
GET    /api/entities         - List entities (with filters)
GET    /api/entities/{id}    - Get entity details
GET    /api/contradictions   - List contradictions
POST   /api/canon/resolve    - Submit canon decision
GET    /api/system/status    - System health
```

## CRITICAL: SAFETY CHECKPOINT FIRST
Before ANY work, create a safety checkpoint:

```bash
cd C:\Users\pange\Downloads\lore-system.tar\lore-system

# Check current state
git status

# Commit everything as-is (safety checkpoint)
git add .
git commit -m "CHECKPOINT: Pre-UI-integration safety commit"

# Push to preserve state
git push origin main

# Document current commit hash for rollback
git log -1 --oneline > CURRENT_COMMIT.txt
```

**If anything breaks**: `git reset --hard <commit-hash-from-CURRENT_COMMIT.txt>`

## ENDPOINT VERIFICATION (DO THIS FIRST)
Before wiring ANY UI to backend, verify endpoints exist and work:

### Step 0: Verify Server Configuration
```bash
# Find actual port and host configuration
cat run.py | grep -E "port|host|app.run"
# OR
grep -r "app.run\|port\|host" . --include="*.py" | head -5

# Document findings:
# Port: _____ (commonly 5000, 8000, 3000)
# Host: _____ (commonly localhost, 0.0.0.0, 127.0.0.1)
```

**STOP**: Tell Shawn what you found. Don't assume port number.

### Step 1: Start Backend Server
```bash
# Start server (adjust command if needed)
python run.py

# Should see output like:
# "Running on http://127.0.0.1:5000"
# "Press CTRL+C to quit"

# Keep this terminal open
# Open NEW terminal for testing
```

**If server won't start**: STOP. Tell Shawn the error. Don't proceed.

### Step 2: Clean Up Duplicate Templates
```bash
# From NEW terminal, in project root
find . -name "*dashboard*.html" -o -name "*card*.html" | grep -v node_modules

# Output example:
# ./src/templates/dashboard.html
# ./src/templates/old_dashboard.html
# ./templates/dashboard_backup.html
# ./contradiction_card.html
```

**MANDATORY**: Show Shawn this list. Ask which to keep. Wait for response.

**After Shawn confirms**, create backup before deleting:
```bash
mkdir -p backups/templates_$(date +%Y%m%d)
# Copy files to backup BEFORE deleting
cp <file-to-delete> backups/templates_$(date +%Y%m%d)/
# Then delete confirmed files
```

### Step 3: Install Dashboard Template
```bash
# Copy new dashboard to canonical location
cp /mnt/user-data/outputs/lms-dashboard.html src/templates/dashboard.html

# Verify it's there
ls -lh src/templates/dashboard.html
```

### Step 4: Check Backend API Routes
```bash
# Find all route definitions
cat src/api.py | grep -E "@app\.(route|get|post|put|delete)" -A 2

# Document ACTUAL routes found (example output):
# @app.route('/api/status', methods=['GET'])
# def status():
#     return jsonify({"status": "ok"})
```

**Create API inventory**: Document every route you find in `API_INVENTORY.md`

### Step 5: Test Each Endpoint Manually
Use the port/host from Step 0. Test ONE endpoint at a time.

**Example: Test status endpoint**
```bash
# Replace PORT with actual port from Step 0
curl http://localhost:PORT/api/status

# Expected: JSON response like {"status": "ok", "backend": "ready"}
# If you get: Connection refused -> Server not running (go back to Step 1)
# If you get: 404 -> Route doesn't exist (tell Shawn)
# If you get: 500 -> Server error (tell Shawn the error)
```

**Example: Test upload endpoint**
```bash
# Create test file first
echo "Test lore content" > test_upload.txt

# Test upload
curl -X POST -F "file=@test_upload.txt" http://localhost:PORT/api/upload

# Expected response examples:
# Success: {"batch_id": "abc123", "status": "queued"}
# Error: {"error": "Invalid file type"}
# 404: Route doesn't exist
```

**For EACH endpoint found in Step 4**:
1. Test with curl
2. Document the request format (query params? JSON body? form data?)
3. Document the response format (actual JSON structure)
4. Document error responses you see
5. If any endpoint fails or doesn't exist: STOP and tell Shawn

### Step 6: Document API Contract
Create `API_CONTRACT.md` with actual verified endpoints:

```markdown
# LMS API Contract (VERIFIED)

## GET /api/status
**Request**: None
**Response**: 
{
  "status": "ok",
  "backend": "ready",
  "version": "1.0.0"
}
**Errors**: None observed

## POST /api/upload
**Request**: multipart/form-data with "file" field
**Response**:
{
  "batch_id": "abc123",
  "files_queued": 5,
  "status": "processing"
}
**Errors**:
- 400: {"error": "No file provided"}
- 415: {"error": "Invalid file type"}

[Continue for each verified endpoint...]
```

**DO NOT ASSUME ENDPOINTS**. Only document what you've actually tested and seen work.

### Step 7: Write Integration Test Script
Create `test_api_integration.py` in project root:

```python
"""
API Integration Test
Run this BEFORE touching UI code.
"""
import requests
import sys

# UPDATE THIS with actual port from Step 0
BASE_URL = "http://localhost:5000"  # CHANGE PORT IF NEEDED

def test_endpoint(method, path, **kwargs):
    """Test a single endpoint and report results"""
    url = f"{BASE_URL}{path}"
    print(f"\n{'='*60}")
    print(f"Testing: {method} {path}")
    print(f"{'='*60}")
    
    try:
        if method == "GET":
            response = requests.get(url, **kwargs)
        elif method == "POST":
            response = requests.post(url, **kwargs)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")  # First 500 chars
        
        if response.status_code == 200:
            print("✓ SUCCESS")
            return True
        else:
            print("✗ FAILED")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ CONNECTION FAILED - Is server running?")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

# Test each endpoint
print("Starting API Integration Tests...")
print(f"Base URL: {BASE_URL}")

results = []

# Test status
results.append(test_endpoint("GET", "/api/status"))

# Test upload
with open("test_upload.txt", "w") as f:
    f.write("Test lore content for upload")
    
with open("test_upload.txt", "rb") as f:
    results.append(test_endpoint("POST", "/api/upload", 
                                 files={"file": f}))

# Add more tests as you discover endpoints...

# Summary
print(f"\n{'='*60}")
print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
print(f"{'='*60}")

if sum(results) == len(results):
    print("✓ All endpoints verified. Safe to wire UI.")
    sys.exit(0)
else:
    print("✗ Some endpoints failed. DO NOT WIRE UI YET.")
    print("Tell Shawn which endpoints failed.")
    sys.exit(1)
```

Run the test:
```bash
python test_api_integration.py
```

**If ANY test fails**: STOP. Tell Shawn what failed. Don't proceed to UI work.

### Step 8: Only Then Wire UI
Once ALL previous steps pass:

1. Open `src/templates/dashboard.html`
2. Find the `handleFiles()` function
3. Replace simulated processing with real API calls:

```javascript
async function handleFiles(files) {
    if (files.length === 0) return;
    
    queueDisplay.style.display = 'block';
    queueList.innerHTML = '';
    
    // Create FormData
    const formData = new FormData();
    Array.from(files).forEach(file => {
        formData.append('files', file);  // Match API expectation
    });
    
    try {
        // REAL API CALL (use verified endpoint from API_CONTRACT.md)
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Upload failed: ${response.status}`);
        }
        
        const result = await response.json();
        // Handle response according to API_CONTRACT.md
        
    } catch (error) {
        console.error('Upload error:', error);
        alert(`Upload failed: ${error.message}`);
    }
}
```

4. Test in browser BEFORE committing
5. Verify network tab shows correct requests
6. Commit only when working: `git commit -m "Wire upload to backend API"`

## CRITICAL CONTEXT PRESERVATION RULES

### When Asking Shawn Questions
Always include:
1. What step you're on
2. What you found/tested
3. Specific output/error messages
4. What you need clarified

**Example good question**:
"Step 5 complete. Found 3 endpoints in api.py:
- GET /api/status (works, returns {"status": "ok"})
- POST /api/upload (returns 404)
- GET /api/queue (works)

The upload endpoint returns 404. Should I:
A) Look for it elsewhere in the codebase?
B) Build it from scratch?
C) Use a different endpoint name?"

**Example bad question**:
"Upload doesn't work. What do I do?"

### Before Each Work Session
1. Check `CURRENT_COMMIT.txt` for last known good state
2. Run `git log -1` to see latest commit
3. Check `API_CONTRACT.md` for verified endpoints
4. Re-read GEMINI_HANDOFF.md sections relevant to current task

### When Switching Models/Instances
Create state snapshot:
```bash
# Create snapshot file
cat > SESSION_STATE.md << 'EOF'
# Current Session State
Date: $(date)
Last Commit: $(git log -1 --oneline)
Current Step: [Step number and description]
Completed Steps: [List]
Blocked On: [What's blocking progress]
Next Action: [What to do next]
EOF
```

### If You Get Lost
1. Check `git log -3` (last 3 commits)
2. Check `SESSION_STATE.md` if it exists
3. Check `API_CONTRACT.md` for what's verified
4. Ask Shawn: "I need context. Last commit was X. What should I work on?"

## ROLLBACK PROCEDURES

### If Something Breaks
```bash
# See what changed
git status
git diff

# Undo uncommitted changes
git restore <file>

# OR go back to safety checkpoint
git log --oneline | head -5  # Find checkpoint commit
git reset --hard <checkpoint-commit-hash>

# Tell Shawn what broke and what you rolled back to
```

### If You Delete Wrong Files
```bash
# Check backups folder
ls backups/templates_*/

# Restore from backup
cp backups/templates_YYYYMMDD/<file> src/templates/

# OR restore from git history
git checkout HEAD~1 -- <file-path>
```

## IMMEDIATE NEXT STEPS FOR GEMINI
1. **FIRST**: Run endpoint verification steps above
2. **SECOND**: Ask Shawn about any missing/mismatched endpoints
3. **THIRD**: Document actual API contract
4. **FOURTH**: Ask which priority to tackle first
5. **FIFTH**: Build with verified endpoints only
6. Maintain Haunting Machine aesthetic throughout

## FILES TO REFERENCE
- `src/api.py` - Backend API routes
- `src/templates/dashboard.html` - May have existing components
- `contradiction_card.html` - Styling reference for contradiction UI
- Current dashboard: `/mnt/user-data/outputs/lms-dashboard.html`

## CONSTRAINTS
- Single-page application (no page reloads)
- Tab switching only (no routing)
- Mobile-responsive (Shawn uses mobile app)
- Fast load times
- Clear visual feedback for all actions

## SHAWN'S PREFERENCES
- Direct and concise communication
- Lead with answers, elaborate when needed
- No speculation about next steps unless asked
- Natural conversational intelligence over commands
- Treat AI as cognitive partner, not tool

## GOSPEL PRINCIPLE REMINDER
AI detects and flags issues. Humans make canonical decisions. Never let the system auto-resolve contradictions or make lore decisions autonomously.

---

## QUICK START FOR GEMINI
1. Copy lms-dashboard.html from outputs to Shawn's project
2. Ask: "Which priority should I tackle first?"
3. Get necessary API details or design requirements
4. Build incrementally with frequent check-ins
5. Maintain aesthetic consistency

Good luck! 🖤
