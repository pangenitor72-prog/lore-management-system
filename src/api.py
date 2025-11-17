"""
FastAPI application for Lore Management System
Provides REST API endpoints for managing lore entities
"""
# === START: Replace lines 5-35 with this ===
from dotenv import load_dotenv
load_dotenv()

# --- Now your other imports can start ---
import uvicorn
from fastapi import FastAPI
from ai_service import generate_content

# ... (the rest of your app code) ...

from pathlib import Path
from fastapi import (
    FastAPI, HTTPException, Query, Body, status, 
    WebSocket, WebSocketDisconnect, Request
)
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List, Optional
from dotenv import load_dotenv
from datetime import datetime, timezone
import os
import json
import uuid
from enum import Enum

# --- Core Imports ---
from .database import Database
from . import models
from .models import (
    EntityCreate, EntityResponse, RelationshipCreate,
    ErrorResponse, ContradictionResponse, ContradictionCreate,
    ContradictionStatus, RelationshipResponse, ContradictionSeverity
)

# --- Agent Imports ---
from .auditor_agent import AuditorAgent
from .query_agent import QueryAgent
# Explicitly import debug routes
import src.contradiction_service

# ============================================================
# PHASE IX — DASHBOARD / WEBSOCKET LAYER
# ============================================================
from fastapi import WebSocket, WebSocketDisconnect
from typing import List
import json
import datetime
import json
from src.models import (
    ContradictionCreate, ContradictionResponse, TriageAnalysisCreate, 
    TriageAnalysisResponse, ContradictionWithAnalysis, ContradictionStatus, 
    ContradictionSeverity
)
from fastapi.staticfiles import StaticFiles
from pathlib import Path


app = FastAPI(
    title="Lore Management System API",
    description="API for managing canonical lore with Gospel Principle enforcement",
    version="1.0.0",
)



active_connections: List[WebSocket] = []

@app.websocket("/ws/agent-chat")
async def agent_chat_socket(websocket: WebSocket):
    """Live channel for dashboard status updates."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            now = datetime.now().strftime("%H:%M:%S")

            msg = {"time": now, "source": "LMS", "text": f"Echo: {data}"}
            await websocket.send_text(json.dumps(msg))
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# --- Initialize FastAPI App ---


# --- Template Configuration ---
# (You only need this defined once)
BASE_DIR = Path(__file__).resolve().parent.parent 
templates = Jinja2Templates(directory=str(BASE_DIR / 'src' / 'templates'))
# BASE_DIR should already exist in your file; re-use it instead of redefining if present.
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "src" / "static")),
    name="static",
)


# --- Initialization ---
load_dotenv()
gemini_key=os.getenv("GEMINI_API_KEY")

if not gemini_key or gemini_key == "YOUR_KEY_HERE":
    print("⚠️ WARNING: GEMINI_API_KEY missing — continuing without remote features.")
if not gemini_key:
    print("WARNING: GEMINI_API_KEY missing...")  

db = Database("data/lore.db") # This creates the 'db' object


# ✅ Initialize Agents
auditor = AuditorAgent(db, gemini_key)
query_agent = QueryAgent(db, gemini_key) 
print("[INIT] API: All agents wired")

from fastapi import APIRouter
router = APIRouter()

from uuid import uuid4

from fastapi import Request

@router.get("/entities/browser", response_class=HTMLResponse)
async def entities_browser(request: Request, canon_id: Optional[str] = None):
    """
    Entity Browser UI (Module 1)

    - If no canon_id: render the list browser (entities.html)
    - If canon_id provided: render the detail view (entity_detail.html)
    """
    context = {"request": request}
    template_name = "entities.html"

    if canon_id:
        template_name = "entity_detail.html"
        context["canon_id"] = canon_id

    return templates.TemplateResponse(template_name, context)

@router.get("/debug/seed-contradictions")
@router.post("/debug/seed-contradictions")
def seed_contradictions():
    """Insert a few fake contradictions for testing the dashboard."""
    from random import random
    from datetime import datetime, timedelta, timezone

    try:
        now = datetime.now(timezone.utc)
        for i in range(10):
            db.execute(
                """
                INSERT INTO contradictions (
                    contradiction_id,
                    contradiction_type,
                    severity,
                    description,
                    evidence,
                    detected_at,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"test-{i}-{uuid4().hex[:6]}",  # 🩵 unique ID
                    "consistency",
                    "LOW",
                    f"Dummy contradiction {i}",
                    "{}",
                    (now - timedelta(minutes=10 * i)).isoformat(),
                    "OPEN",
                ),
            )
        return {"status": "ok", "message": "Inserted 10 test contradictions"}
    except Exception as e:
        print("[DEBUG] Seeding error:", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_class=HTMLResponse)

def dashboard(request: Request):
    """Render the Audit Dashboard with static snapshot data."""
    sql = """
    SELECT 
        detected_at,
        COALESCE(confidence, 0) AS confidence
    FROM contradictions
    WHERE detected_at IS NOT NULL
    ORDER BY detected_at DESC
    LIMIT 20
    """
    rows = db.fetch_all(sql)

    labels = [r["detected_at"] for r in rows]
    scores = [float(r["confidence"]) for r in rows]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "labels": labels[::-1],  # show oldest → newest
            "scores": scores[::-1],
        },
    )

@router.get("/api/contradiction-snapshot")
def contradiction_snapshot():
    """Return latest contradiction confidence scores for live chart refresh."""
    sql = """
        SELECT detected_at, confidence
        FROM contradictions
        WHERE confidence IS NOT NULL
        ORDER BY detected_at DESC
        LIMIT 20
    """
    rows = db.fetch_all(sql)
    labels = [r["detected_at"] for r in rows]
    scores = [float(r["confidence"]) for r in rows]
    return {"labels": labels[::-1], "scores": scores[::-1]}

# --- Core Endpoints (Stable) ---

@router.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Lore Management System API",
        "version": "1.0.0",
        "status": "operational"
    }

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serves the live audit dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.post("/entities", response_model=EntityResponse, status_code=201)
def create_entity(entity_data: EntityCreate):
    """Creates a new entity in the database."""
    canon_id = f"{entity_data.entity_type.lower()}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        # Wrap all database logic in a single transaction
        with db.transaction() as conn:
            # 1. Insert into the main entities table
            conn.execute("""
                INSERT INTO entities (canon_id, entity_type, canonical_name, 
                                      approval_status, confidence_level, 
                                      party_knowledge, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                canon_id,
                entity_data.entity_type.value,
                entity_data.canonical_name,
                entity_data.approval_status.value,
                entity_data.confidence_level.value,
                entity_data.party_knowledge.value,
                created_at,
                created_at
            ))

            # 2. Insert into the aliases table
            for alias in entity_data.aliases:
                conn.execute("""
                    INSERT INTO aliases (canon_id, alias) VALUES (?, ?)
                """, (canon_id, alias))

            # 3. Insert into the approved_fields table
            for key, value in entity_data.approved_fields.items():
                conn.execute("""
                    INSERT INTO approved_fields (canon_id, field_key, field_value) VALUES (?, ?, ?)
                """, (canon_id, key, json.dumps(value))) # Store value as JSON

        # Fetch the data *after* the transaction is committed
        # We use the get_entity function which already knows how to join these tables
        created_entity = get_entity(canon_id) 
        if not created_entity:
            raise HTTPException(status_code=500, detail="Failed to retrieve entity after creation.")

        return created_entity

    except Exception as e:
        # Print the full error to the server log for easier debugging
        print(f"Error in create_entity: {e}") 
        raise HTTPException(status_code=500, detail=f"Failed to create entity: {e}")
@router.get("/entities/{canon_id}", response_model=EntityResponse)
def get_entity(canon_id: str):
    # ...def get_entity(canon_id: str):
    """Get an entity by canon_id."""
    entity = db.fetch_one("SELECT * FROM entities WHERE canon_id = ?", (canon_id,))
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Entity not found: {canon_id}")
    
    aliases = db.fetch_all("SELECT alias FROM aliases WHERE canon_id = ?", (canon_id,))
    fields = db.fetch_all("SELECT field_key, field_value FROM approved_fields WHERE canon_id = ?", (canon_id,))
    
    return EntityResponse(
        canon_id=entity['canon_id'],
        entity_type=entity['entity_type'],
        canonical_name=entity['canonical_name'],
        aliases=[a['alias'] for a in aliases],
        approved_fields={f['field_key']: f['field_value'] for f in fields},
        approval_status=entity['approval_status'],
        confidence_level=entity['confidence_level'],
        party_knowledge=entity['party_knowledge'],
        created_at=entity['created_at'],
        updated_at=entity['updated_at']
    )

@router.get("/entities", response_model=List[EntityResponse])
def list_entities(
    entity_type: Optional[str] = None,
    approval_status: Optional[str] = None,
    limit: int = 100
):
    """List entities with optional filters."""
    query = "SELECT canon_id FROM entities WHERE 1=1"
    params = []
    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)
    if approval_status:
        query += " AND approval_status = ?"
        params.append(approval_status)
    query += f" LIMIT {limit}"
    
    canon_ids = db.fetch_all(query, tuple(params))
    return [get_entity(row['canon_id']) for row in canon_ids]

@router.post("/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_relationship(relationship: RelationshipCreate):
    """Create a relationship between entities."""
    from_entity = db.fetch_one("SELECT canon_id FROM entities WHERE canon_id = ?", (relationship.from_canon_id,))
    to_entity = db.fetch_one("SELECT canon_id FROM entities WHERE canon_id = ?", (relationship.to_canon_id,))
    
    if not from_entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"From entity not found: {relationship.from_canon_id}")
    if not to_entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"To entity not found: {relationship.to_canon_id}")
    
    try:
        with db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO relationships (
                    from_canon_id, relationship_type, to_canon_id, confidence_level
                ) VALUES (?, ?, ?, ?)
            """, (
                relationship.from_canon_id, relationship.relationship_type,
                relationship.to_canon_id, relationship.confidence_level.value
            ))
            relationship_id = cursor.lastrowid
        
        rel = db.fetch_one("SELECT * FROM relationships WHERE id = ?", (relationship_id,))
        return RelationshipResponse(**rel)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create relationship: {str(e)}")

# --- Phase VI: Audit Endpoints (AI & Rule-Based) ---

@router.post("/audit/compare-entities") # <-- Fixed: Added @router.post
def compare_entities(entity_a_id: str, entity_b_id: str):
    """Runs a pairwise AI contradiction check."""
    a=db.fetch_one("SELECT * FROM entities WHERE canon_id=?",(entity_a_id,))
    b=db.fetch_one("SELECT * FROM entities WHERE canon_id=?",(entity_b_id,))
    
    if not a or not b:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    result=auditor.detect_contradictions(a,b)
    
    return {
        "entity_a":a.get("name"),"entity_b":b.get("name"),
        "count":len(result),"contradictions":result,
        "timestamp": datetime.now(timezone.utc).isoformat() # <-- Fixed: Added .isoformat()
    }

@router.post("/audit/detect-all-contradictions")
def detect_all_contradictions(limit: Optional[int] = None):
    """Runs a full AI batch analysis and persists findings."""
    count = auditor.analyze_all_entities(limit)
    
    return {
        "contradictions_found": count,
        "detail": f"Batch analysis complete. {count} contradictions were found and persisted to the database.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.post("/audit/run-rule-based-audit")
def run_rule_based_audit():
    """Triggers the AuditorAgent's full SQL-based audit."""
    print("[AUDIT] Received request for rule-based audit.")
    results = auditor.run_full_audit()
    summary = auditor.get_summary(results)
    
    return {
        "audit_type": "rule-based",
        "timestamp": datetime.now(timezone.utc).isoformat(), # <-- Fixed: Uses timezone.utc
        "summary": summary,
        "details": results
    }

# --- Phase VI: AI Chat WebSocket ---

@app.websocket("/ws/agent-chat/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Hosts the AI-powered QueryAgent chat."""
    await websocket.accept()
    sender = client_id
    print(f"[WS] Client '{sender}' connected.")
    if sender == "dashboard":
        print("[WS] 📊 Dashboard connection established (Phase IX).")

    
    try:
        while True:
            msg = await websocket.receive_text()
            timestamp = datetime.now(timezone.utc).isoformat()
            
            await db.execute(
                ("INSERT INTO agent_chat_log (sender, message, timestamp) "
                 "VALUES (?, ?, ?)"),
                (sender, msg, timestamp)
            )
            
            reply = query_agent.ask(msg) # <-- NEW AI LOGIC
            reply_timestamp = datetime.now(timezone.utc).isoformat()

            await db.execute(
                ("INSERT INTO agent_chat_log (sender, message, timestamp) "
                 "VALUES (?, ?, ?)"),
                ("QueryAgent", reply, reply_timestamp)
            )
            await websocket.send_text(reply)
            
    except Exception as e:
        print(f"[WS] WebSocket Closed for '{sender}': {e}")
    try:
            await websocket.close()
    except:
            pass # Ignore errors if already closed

# --- Phase VII: Triage Loop API Endpoints ---

# === Phase VIII: Contradiction API (Service-Based) ===
from src.contradiction_service import get_router
app.include_router(get_router())
app.include_router(router)
from src.models import ContradictionUpdateRequest
from src.constants import STATUS_RESOLVED, STATUS_DISMISSED, STATUS_IN_REVIEW



@router.get("/contradictions/{contradiction_id}", tags=["Contradictions"])
async def get_single_contradiction(contradiction_id: str):
    contradiction = contradiction_service.get_contradiction(contradiction_id)
    if not contradiction:
        raise HTTPException(status_code=404, detail="Contradiction not found")
    return contradiction

@router.post("/contradictions/{contradiction_id}/resolve", tags=["Contradictions"])
async def resolve_contradiction(contradiction_id: str, payload: ContradictionUpdateRequest):
    success = contradiction_service.resolve_contradiction(contradiction_id, payload.user, payload.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Contradiction not found or update failed")
    return {"status": "success", "new_status": STATUS_RESOLVED, "contradiction_id": contradiction_id}

@router.post("/contradictions/{contradiction_id}/dismiss", tags=["Contradictions"])
async def dismiss_contradiction(contradiction_id: str, payload: ContradictionUpdateRequest):
    success = contradiction_service.dismiss_contradiction(contradiction_id, payload.user, payload.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Contradiction not found or update failed")
    return {"status": "success", "new_status": STATUS_DISMISSED, "contradiction_id": contradiction_id}

@router.post("/contradictions/{contradiction_id}/review", tags=["Contradictions"])
async def set_contradiction_in_review(contradiction_id: str):
    success = contradiction_service.set_in_review(contradiction_id, user="System")
    if not success:
        raise HTTPException(status_code=404, detail="Contradiction not found or update failed")
    return {"status": "success", "new_status": STATUS_IN_REVIEW, "contradiction_id": contradiction_id}
# ============================================================
# 🧭 Phase IX – Dashboard Data Endpoint
# ============================================================
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

@app.get("/dashboard/data", response_class=JSONResponse)
async def dashboard_data():
    """
    Returns contradiction metrics for the Phase IX dashboard.
    Pulls status + confidence + timestamps from the Contradictions table.
    """
    try:
        rows = db.fetch_all("""
        SELECT id, status, confidence, created_at
        FROM contradictions
        ORDER BY created_at DESC
        LIMIT 100
        """)


        data = []
        for r in rows:
            data.append({
                "id": r["id"],
                "status": r["status"],
                "confidence": (
                    float(r["confidence"])
                    if r["confidence"] is not None
                    else 0.0
                ),
                "created_at": (
                    r["created_at"]
                    if isinstance(r["created_at"], str)
                    else r["created_at"].isoformat()
                ),
            })

        return JSONResponse(content=data)

    except Exception as e:
        print(f"[Dashboard] Error fetching data: {e}")
        return JSONResponse(
            content={"error": "Failed to retrieve dashboard data."},
            status_code=500,
        )


from src.contradiction_service import get_router
app.include_router(get_router())

# src/api.py
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List  # <-- **ADD THIS IMPORT**
from fastapi.responses import JSONResponse  # <-- **ADD THIS IMPORT**

# Import your local modules
from . import database  # <-- **ADD THIS IMPORT**
from . import models    # <-- **ADD THIS IMPORT**
from .auditor_agent import AuditorAgent
from .query_agent import QueryAgent




# --- PHASE IX: DASHBOARD API ---

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_page(request: Request):
    """
    Serves the main monitoring dashboard.
    """
    # This renders src/templates/dashboard.html
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/dashboard/data", response_model=List[models.Contradiction])
async def get_dashboard():
    """
    Returns all contradiction data for chart population.
    """
    try:
        # Use the 'db' object and its 'fetch_all' method, which
        # is already defined in your api.py file.
        contradictions = db.fetch_all(
            "SELECT detected_at, confidence FROM contradictions WHERE detected_at IS NOT NULL ORDER BY detected_at DESC LIMIT 20"
)
        # Your fetch_all method already returns a list of dicts,
        # so we can return it directly.
        return contradictions
        
    except Exception as e:
        print(f"Error fetching dashboard data: {e}")
        return JSONResponse(status_code=500, content={"message": "Error fetching data"})
@app.websocket("/ws/agent-chat/{client_id}")
async def agent_chat_websocket(websocket: WebSocket, client_id: str):
    """
    Handles the live WebSocket chat connection for the QueryAgent.
    """
    try:
        # This assumes your query_agent has a 'handle_websocket' method
        await query_agent.handle_websocket(websocket, client_id)
    except WebSocketDisconnect:
        print(f"Client {client_id} disconnected.")
    except Exception as e:
        print(f"Error in WebSocket for {client_id}: {e}")
        await websocket.close(code=1011, reason="Internal error")
# === END OF NEW FUNCTION ===



@router.get("/debug/reset-contradictions", response_model=dict)
async def debug_reset_contradictions():
    """
    (Optional) Clears the contradictions table for easy testing.
    """
    try:
        # Use the 'db' object and its 'execute' method
        db.execute("DELETE FROM contradictions")
        # Reset auto-increment sequence for SQLite
        db.execute("DELETE FROM sqlite_sequence WHERE name='contradictions'")
        
        return {"status": "success", "message": "Contradictions table reset."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
    # expose router to api.py
def get_router():
    return router
def get_router():
    return router
