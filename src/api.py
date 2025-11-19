"""
FastAPI application for Lore Management System
Provides REST API endpoints for managing lore entities
"""

# ============================================================
# IMPORTS
# ============================================================

# Standard Library
import os
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum

# Third Party
import uvicorn
from dotenv import load_dotenv
from fastapi import (
    FastAPI, HTTPException, Query, Body, Request,
    WebSocket, WebSocketDisconnect, status, APIRouter
)
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Local Imports - Database
from .database import Database

# Local Imports - Models
from .models import (
    EntityCreate, EntityResponse, RelationshipCreate,
    ErrorResponse, ContradictionResponse, ContradictionCreate,
    ContradictionStatus, RelationshipResponse, ContradictionSeverity,
    ContradictionWithAnalysis, TriageAnalysisCreate, 
    TriageAnalysisResponse, ContradictionUpdateRequest
)

# Local Imports - Agents
from .auditor_agent import AuditorAgent
from .query_agent import QueryAgent

# Local Imports - Services
from .contradiction_service import get_router as get_contradiction_router
from .constants import STATUS_RESOLVED, STATUS_DISMISSED, STATUS_IN_REVIEW

# ============================================================
# CONFIGURATION & INITIALIZATION
# ============================================================

# Load environment variables
load_dotenv()

# Initialize FastAPI App
app = FastAPI(
    title="Lore Management System API",
    description="API for managing canonical lore with Gospel Principle enforcement",
    version="1.0.0",
)

# Initialize Router
router = APIRouter()

# Path Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / 'src' / 'templates'))

# Mount Static Files
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "src" / "static")),
    name="static",
)

# Database Initialization
db = Database("data/lore.db")

# API Key Configuration
gemini_key = os.getenv("GEMINI_API_KEY")
if not gemini_key or gemini_key == "YOUR_KEY_HERE":
    print("⚠️ WARNING: GEMINI_API_KEY missing — continuing without remote features.")

# Agent Initialization
auditor = AuditorAgent(db, gemini_key)
query_agent = QueryAgent(db, gemini_key)
print("[INIT] API: All agents wired")

# WebSocket Connection Management
active_connections: List[WebSocket] = []

# ============================================================
# ROOT & INFO ENDPOINTS
# ============================================================

@router.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Lore Management System API",
        "version": "1.0.0",
        "status": "operational"
    }

# ============================================================
# ENTITY ENDPOINTS
# ============================================================

@router.post("/entities", response_model=EntityResponse, status_code=201)
def create_entity(entity_data: EntityCreate):
    """Creates a new entity in the database."""
    canon_id = f"{entity_data.entity_type.lower()}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        with db.transaction() as conn:
            # Insert into entities table
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

            # Insert aliases
            for alias in entity_data.aliases:
                conn.execute("""
                    INSERT INTO aliases (canon_id, alias) VALUES (?, ?)
                """, (canon_id, alias))

            # Insert approved fields
            for key, value in entity_data.approved_fields.items():
                conn.execute("""
                    INSERT INTO approved_fields (canon_id, field_key, field_value) 
                    VALUES (?, ?, ?)
                """, (canon_id, key, json.dumps(value)))

        created_entity = get_entity(canon_id)
        if not created_entity:
            raise HTTPException(
                status_code=500, 
                detail="Failed to retrieve entity after creation."
            )

        return created_entity

    except Exception as e:
        print(f"Error in create_entity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create entity: {e}")


@router.get("/entities/{canon_id}", response_model=EntityResponse)
def get_entity(canon_id: str):
    """Get an entity by canon_id."""
    entity = db.fetch_one("SELECT * FROM entities WHERE canon_id = ?", (canon_id,))
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Entity not found: {canon_id}"
        )

    aliases = db.fetch_all("SELECT alias FROM aliases WHERE canon_id = ?", (canon_id,))
    fields = db.fetch_all(
        "SELECT field_key, field_value FROM approved_fields WHERE canon_id = ?", 
        (canon_id,)
    )

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


@router.get("/entities/browser", response_class=HTMLResponse)
async def entities_browser(request: Request, canon_id: Optional[str] = None):
    """
    Entity Browser UI
    - No canon_id: render list browser (entities.html)
    - With canon_id: render detail view (entity_detail.html)
    """
    context = {"request": request}
    template_name = "entities.html"

    if canon_id:
        template_name = "entity_detail.html"
        context["canon_id"] = canon_id

    return templates.TemplateResponse(template_name, context)

# ============================================================
# RELATIONSHIP ENDPOINTS
# ============================================================

@router.post("/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_relationship(relationship: RelationshipCreate):
    """Create a relationship between entities."""
    from_entity = db.fetch_one(
        "SELECT canon_id FROM entities WHERE canon_id = ?", 
        (relationship.from_canon_id,)
    )
    to_entity = db.fetch_one(
        "SELECT canon_id FROM entities WHERE canon_id = ?", 
        (relationship.to_canon_id,)
    )

    if not from_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"From entity not found: {relationship.from_canon_id}"
        )
    if not to_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"To entity not found: {relationship.to_canon_id}"
        )

    try:
        with db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO relationships (
                    from_canon_id, relationship_type, to_canon_id, confidence_level
                ) VALUES (?, ?, ?, ?)
            """, (
                relationship.from_canon_id, 
                relationship.relationship_type,
                relationship.to_canon_id, 
                relationship.confidence_level.value
            ))
            relationship_id = cursor.lastrowid

        rel = db.fetch_one("SELECT * FROM relationships WHERE id = ?", (relationship_id,))
        return RelationshipResponse(**rel)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to create relationship: {str(e)}"
        )

# ============================================================
# AUDIT ENDPOINTS
# ============================================================

@router.post("/audit/compare-entities")
def compare_entities(entity_a_id: str, entity_b_id: str):
    """Runs a pairwise AI contradiction check."""
    a = db.fetch_one("SELECT * FROM entities WHERE canon_id = ?", (entity_a_id,))
    b = db.fetch_one("SELECT * FROM entities WHERE canon_id = ?", (entity_b_id,))

    if not a or not b:
        raise HTTPException(status_code=404, detail="Entity not found")

    result = auditor.detect_contradictions(a, b)

    return {
        "entity_a": a.get("name"),
        "entity_b": b.get("name"),
        "count": len(result),
        "contradictions": result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/audit/detect-all-contradictions")
def detect_all_contradictions(limit: Optional[int] = None):
    """Runs a full AI batch analysis and persists findings."""
    count = auditor.analyze_all_entities(limit)

    return {
        "contradictions_found": count,
        "detail": f"Batch analysis complete. {count} contradictions found and persisted.",
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "details": results
    }

# ============================================================
# CONTRADICTION ENDPOINTS
# ============================================================

@router.get("/api/contradictions", response_class=JSONResponse, tags=["Contradictions"])
def list_contradictions():
    """
    Returns all contradictions for the Module 2 UI.
    """
    rows = db.fetch_all("""
        SELECT 
            contradiction_id,
            contradiction_type,
            severity,
            status,
            description,
            evidence,
            detected_at,
            created_at
        FROM contradictions
        ORDER BY detected_at DESC
    """)

    results = []
    for r in rows:
        results.append({
            "contradiction_id": r["contradiction_id"],
            "contradiction_type": r["contradiction_type"],
            "severity": r["severity"],
            "status": r["status"],
            "description": r["description"],
            "evidence": json.loads(r["evidence"]) if r["evidence"] else {},
            "detected_at": r["detected_at"],
            "created_at": r["created_at"],
            "entity_ids": []  # Your DB doesn’t store entity_ids yet, this keeps UI happy
        })

    return JSONResponse(content=results)
    
@router.get("/contradictions/{contradiction_id}", tags=["Contradictions"])
async def get_single_contradiction(contradiction_id: str):
    """Get a single contradiction by ID."""
    from . import contradiction_service
    
    contradiction = contradiction_service.get_contradiction(contradiction_id)
    if not contradiction:
        raise HTTPException(status_code=404, detail="Contradiction not found")
    return contradiction


@router.post("/contradictions/{contradiction_id}/resolve", tags=["Contradictions"])
async def resolve_contradiction(contradiction_id: str, payload: ContradictionUpdateRequest):
    """Mark a contradiction as resolved."""
    from . import contradiction_service
    
    success = contradiction_service.resolve_contradiction(
        contradiction_id, 
        payload.user, 
        payload.notes
    )
    if not success:
        raise HTTPException(
            status_code=404, 
            detail="Contradiction not found or update failed"
        )
    return {
        "status": "success", 
        "new_status": STATUS_RESOLVED, 
        "contradiction_id": contradiction_id
    }


@router.post("/contradictions/{contradiction_id}/dismiss", tags=["Contradictions"])
async def dismiss_contradiction(contradiction_id: str, payload: ContradictionUpdateRequest):
    """Dismiss a contradiction."""
    from . import contradiction_service
    
    success = contradiction_service.dismiss_contradiction(
        contradiction_id, 
        payload.user, 
        payload.notes
    )
    if not success:
        raise HTTPException(
            status_code=404, 
            detail="Contradiction not found or update failed"
        )
    return {
        "status": "success", 
        "new_status": STATUS_DISMISSED, 
        "contradiction_id": contradiction_id
    }


@router.post("/contradictions/{contradiction_id}/review", tags=["Contradictions"])
async def set_contradiction_in_review(contradiction_id: str):
    """Set a contradiction to in-review status."""
    from . import contradiction_service
    
    success = contradiction_service.set_in_review(contradiction_id, user="System")
    if not success:
        raise HTTPException(
            status_code=404, 
            detail="Contradiction not found or update failed"
        )
    return {
        "status": "success", 
        "new_status": STATUS_IN_REVIEW, 
        "contradiction_id": contradiction_id
    }

# ============================================================
# DASHBOARD ENDPOINTS
# ============================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Render the Audit Dashboard."""
    sql = """
        SELECT detected_at, COALESCE(confidence, 0) AS confidence
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
            "labels": labels[::-1],
            "scores": scores[::-1],
        },
    )


@router.get("/dashboard/data")
async def dashboard_data():
    """Returns contradiction metrics for dashboard."""
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
                "confidence": float(r["confidence"]) if r["confidence"] is not None else 0.0,
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

# ============================================================
# WEBSOCKET ENDPOINTS
# ============================================================

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


@app.websocket("/ws/agent-chat/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Hosts the AI-powered QueryAgent chat."""
    await websocket.accept()
    sender = client_id
    print(f"[WS] Client '{sender}' connected.")
    
    if sender == "dashboard":
        print("[WS] 📊 Dashboard connection established.")

    try:
        while True:
            msg = await websocket.receive_text()
            timestamp = datetime.now(timezone.utc).isoformat()

            await db.execute(
                "INSERT INTO agent_chat_log (sender, message, timestamp) VALUES (?, ?, ?)",
                (sender, msg, timestamp)
            )

            reply = query_agent.ask(msg)
            reply_timestamp = datetime.now(timezone.utc).isoformat()

            await db.execute(
                "INSERT INTO agent_chat_log (sender, message, timestamp) VALUES (?, ?, ?)",
                ("QueryAgent", reply, reply_timestamp)
            )
            
            await websocket.send_text(reply)

    except Exception as e:
        print(f"[WS] WebSocket Closed for '{sender}': {e}")
        try:
            await websocket.close()
        except:
            pass

# ============================================================
# DEBUG ENDPOINTS
# ============================================================

@router.get("/debug/seed-contradictions")
@router.post("/debug/seed-contradictions")
def seed_contradictions():
    """Insert test contradictions for dashboard testing."""
    try:
        now = datetime.now(timezone.utc)
        for i in range(10):
            from datetime import timedelta
            db.execute(
                """
                INSERT INTO contradictions (
                    contradiction_id, contradiction_type, severity,
                    description, evidence, detected_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"test-{i}-{uuid.uuid4().hex[:6]}",
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


@router.get("/debug/reset-contradictions")
async def debug_reset_contradictions():
    """Clears the contradictions table for testing."""
    try:
        db.execute("DELETE FROM contradictions")
        db.execute("DELETE FROM sqlite_sequence WHERE name='contradictions'")
        return {"status": "success", "message": "Contradictions table reset."}
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

# ============================================================
# ROUTER REGISTRATION
# ============================================================

app.include_router(router)
app.include_router(get_contradiction_router())

# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
