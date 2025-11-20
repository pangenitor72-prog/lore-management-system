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
import logging

# Third Party
import uvicorn
from dotenv import load_dotenv
from fastapi import (
    FastAPI, HTTPException, Query, Body, Request,
    WebSocket, WebSocketDisconnect, status, APIRouter, Depends
)
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.concurrency import run_in_threadpool

# Local Imports - Database
from .database import Database, get_db

# Local Imports - Models
from .models import (
    EntityCreate, EntityResponse, RelationshipCreate,
    ErrorResponse, ContradictionResponse, ContradictionCreate,
    ContradictionStatus, RelationshipResponse, ContradictionSeverity,
    ContradictionWithAnalysis, TriageAnalysisCreate,
    TriageAnalysisResponse, ContradictionUpdateRequest,
    EntityType, ApprovalStatus, ConfidenceLevel, PartyKnowledge # Added canonical Enums
)

# Local Imports - Agents
from .auditor_agent import AuditorAgent
from .query_agent import QueryAgent

# Local Imports - Services
from .contradiction_service import get_router as get_contradiction_router
# Removed redundant constants import from .constants as they are now Enums in models.py

logger = logging.getLogger("lms_api")

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

# API Key Configuration
gemini_key = os.getenv("GEMINI_API_KEY")
if not gemini_key or gemini_key == "YOUR_KEY_HERE":
    logger.warning("GEMINI_API_KEY missing — continuing without remote features.")

# Agent Initialization
auditor = AuditorAgent(get_db_connection, gemini_key)
query_agent = QueryAgent(get_db_connection, gemini_key)
logger.info("API: All agents wired.")

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
async def create_entity(entity_data: EntityCreate, db: sqlite3.Connection = Depends(get_db)):
    """Creates a new entity in the database."""
    canon_id = f"{entity_data.entity_type.value.lower()}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        with db_session() as conn: # Use the new db_session context manager
            # Insert into entities table
            Database.execute(conn, """
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
                Database.execute(conn, """
                    INSERT INTO aliases (canon_id, alias) VALUES (?, ?)
                """, (canon_id, alias))

            # Insert approved fields
            for key, value in entity_data.approved_fields.items():
                Database.execute(conn, """
                    INSERT INTO approved_fields (canon_id, field_key, field_value)
                    VALUES (?, ?, ?)
                """, (canon_id, key, json.dumps(value)))

        created_entity = await run_in_threadpool(get_entity, canon_id, db) # get_entity will also be async

        if not created_entity:
            logger.error(f"Failed to retrieve entity after creation for canon_id: {canon_id}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve entity after creation."
            )

        return created_entity

    except Exception as e:
        logger.exception(f"Error in create_entity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create entity: {e}")


@router.get("/entities/{canon_id}", response_model=EntityResponse)
async def get_entity(canon_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Get an entity by canon_id."""
    entity = await run_in_threadpool(Database.fetch_one, db, "SELECT * FROM entities WHERE canon_id = ?", (canon_id,))
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {canon_id}"
        )

    aliases = await run_in_threadpool(Database.fetch_all, db, "SELECT alias FROM aliases WHERE canon_id = ?", (canon_id,))
    fields = await run_in_threadpool(Database.fetch_all, db,
        "SELECT field_key, field_value FROM approved_fields WHERE canon_id = ?",
        (canon_id,)
    )

    # Correctly parse JSON fields (C5, M8)
    approved_fields_parsed = {}
    for f in fields:
        try:
            approved_fields_parsed[f['field_key']] = json.loads(f['field_value'])
        except json.JSONDecodeError:
            approved_fields_parsed[f['field_key']] = f['field_value'] # Fallback if not valid JSON

    return EntityResponse(
        canon_id=entity['canon_id'],
        entity_type=EntityType(entity['entity_type']), # Explicitly convert to Enum (M3)
        canonical_name=entity['canonical_name'],
        aliases=[a['alias'] for a in aliases],
        approved_fields=approved_fields_parsed,
        approval_status=ApprovalStatus(entity['approval_status']), # Explicitly convert to Enum (M3)
        confidence_level=ConfidenceLevel(entity['confidence_level']), # Explicitly convert to Enum (M3)
        party_knowledge=PartyKnowledge(entity['party_knowledge']), # Explicitly convert to Enum (M3)
        created_at=entity['created_at'],
        updated_at=entity['updated_at']
    )


@router.get("/entities", response_model=List[EntityResponse])
async def list_entities(
    db: sqlite3.Connection = Depends(get_db),
    entity_type: Optional[EntityType] = None, # Use Enum for filtering
    approval_status: Optional[ApprovalStatus] = None, # Use Enum for filtering
    limit: int = 100
):
    """List entities with optional filters."""
    query = """
        SELECT
            e.canon_id, e.entity_type, e.canonical_name, e.approval_status,
            e.confidence_level, e.party_knowledge, e.created_at, e.updated_at,
            GROUP_CONCAT(DISTINCT a.alias) AS aliases,
            GROUP_CONCAT(af.field_key || ':::' || af.field_value) AS approved_fields
        FROM entities e
        LEFT JOIN aliases a ON e.canon_id = a.canon_id
        LEFT JOIN approved_fields af ON e.canon_id = af.canon_id
    """
    params = []
    conditions = []

    if entity_type:
        conditions.append("e.entity_type = ?")
        params.append(entity_type.value)
    if approval_status:
        conditions.append("e.approval_status = ?")
        params.append(approval_status.value)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " GROUP BY e.canon_id ORDER BY e.created_at DESC LIMIT ?"
    params.append(limit)

    rows = await run_in_threadpool(Database.fetch_all, db, query, tuple(params))

    result_entities = []
    for row in rows:
        aliases_list = []
        if row['aliases']:
            aliases_list = row['aliases'].split(',')

        approved_fields_dict = {}
        if row['approved_fields']:
            for item in row['approved_fields'].split(','):
                try:
                    key, value = item.split(':::', 1) # Split only on the first occurrence
                    approved_fields_dict[key] = json.loads(value) # JSON parsing
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning(f"Failed to parse approved_field item '{item}': {e}")
                    # Handle cases where value might not be valid JSON if needed
                    # For now, store as raw string if parsing fails
                    key, value = item.split(':::', 1)
                    approved_fields_dict[key] = value

        result_entities.append(EntityResponse(
            canon_id=row['canon_id'],
            entity_type=EntityType(row['entity_type']),
            canonical_name=row['canonical_name'],
            aliases=aliases_list,
            approved_fields=approved_fields_dict,
            approval_status=ApprovalStatus(row['approval_status']),
            confidence_level=ConfidenceLevel(row['confidence_level']),
            party_knowledge=PartyKnowledge(row['party_knowledge']),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        ))
    return result_entities


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
async def create_relationship(relationship: RelationshipCreate, db: sqlite3.Connection = Depends(get_db)):
    """Create a relationship between entities."""
    from_entity = await run_in_threadpool(
        Database.fetch_one, db, "SELECT canon_id FROM entities WHERE canon_id = ?",
        (relationship.from_canon_id,)
    )
    to_entity = await run_in_threadpool(
        Database.fetch_one, db, "SELECT canon_id FROM entities WHERE canon_id = ?",
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
        with db_session() as conn:
            cursor = Database.execute(conn, """
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

        rel = await run_in_threadpool(Database.fetch_one, db, "SELECT * FROM relationships WHERE id = ?", (relationship_id,))
        return RelationshipResponse(**rel)

    except Exception as e:
        logger.exception(f"Failed to create relationship: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create relationship: {str(e)}"
        )

# ============================================================
# AUDIT ENDPOINTS
# ============================================================

@router.post("/audit/compare-entities")
async def compare_entities(entity_a_id: str, entity_b_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Runs a pairwise AI contradiction check."""
    a = await run_in_threadpool(Database.fetch_one, db, "SELECT * FROM entities WHERE canon_id = ?", (entity_a_id,))
    b = await run_in_threadpool(Database.fetch_one, db, "SELECT * FROM entities WHERE canon_id = ?", (entity_b_id,))

    if not a or not b:
        raise HTTPException(status_code=404, detail="Entity not found")

    result = await run_in_threadpool(auditor.detect_contradictions, a, b)

    return {
        "entity_a": a.get("canonical_name"), # Using canonical_name as 'name' might not exist
        "entity_b": b.get("canonical_name"), # Using canonical_name as 'name' might not exist
        "count": len(result),
        "contradictions": result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/audit/detect-all-contradictions")
async def detect_all_contradictions(limit: Optional[int] = None, db: sqlite3.Connection = Depends(get_db)): # db added for consistency
    """Runs a full AI batch analysis and persists findings."""
    count = await run_in_threadpool(auditor.analyze_all_entities, limit)

    return {
        "contradictions_found": count,
        "detail": f"Batch analysis complete. {count} contradictions found and persisted.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/audit/run-rule-based-audit")
async def run_rule_based_audit(db: sqlite3.Connection = Depends(get_db)): # db added for consistency
    """Triggers the AuditorAgent's full SQL-based audit."""
    logger.info("Received request for rule-based audit.")
    results = await run_in_threadpool(auditor.run_full_audit)
    summary = await run_in_threadpool(auditor.get_summary, results)

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
async def list_contradictions(db: sqlite3.Connection = Depends(get_db)):
    """
    Returns all contradictions for the Module 2 UI.
    """
    rows = await run_in_threadpool(Database.fetch_all, db, """
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
            "entity_ids": []  # placeholder until we wire entity links
        })

    return JSONResponse(content=results)




@router.post("/api/contradictions/{contradiction_id}/resolve", tags=["Contradictions"])
async def resolve_contradiction_unified(contradiction_id: str, action_data: dict = Body(...), db: sqlite3.Connection = Depends(get_db)): # db added for consistency
    """
    Unified triage endpoint for Module 2 UI.
    Handles: resolve, dismiss, in_review actions.
    """
    from . import contradiction_service
    
    action = action_data.get("action")  # "resolve", "dismiss", "in_review"
    user = action_data.get("user", "System")
    notes = action_data.get("notes", "")
    
    if action == "in_review":
        success = await run_in_threadpool(contradiction_service.set_in_review, contradiction_id, user=user)
        new_status = "IN_REVIEW"
    elif action == "resolve":
        success = await run_in_threadpool(contradiction_service.set_resolved, contradiction_id, user=user, notes=notes)
        new_status = "RESOLVED"
    elif action == "dismiss":
        success = await run_in_threadpool(contradiction_service.set_dismissed, contradiction_id, user=user, notes=notes)
        new_status = "DISMISSED"
    else:
        logger.warning(f"Invalid action '{action}' provided for contradiction {contradiction_id}.")
        raise HTTPException(status_code=400, detail="Invalid action. Use: resolve, dismiss, or in_review")
    
    if not success:
        logger.error(f"Contradiction {contradiction_id} not found or update failed for action {action}.")
        raise HTTPException(
            status_code=404, 
            detail="Contradiction not found or update failed"
        )
    
    logger.info(f"Contradiction {contradiction_id} successfully updated to status: {new_status} by {user}.")
    return {
        "status": "success", 
        "new_status": new_status, 
        "contradiction_id": contradiction_id,
        "user": user,
        "notes": notes
    }


@router.get("/contradictions/browser", response_class=HTMLResponse)
async def contradiction_browser(request: Request):
    """Serves the contradiction triage/resolution interface"""
    return templates.TemplateResponse("contradictions.html", {"request": request})

# ============================================================
# DASHBOARD ENDPOINTS
# ============================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Render the Audit Dashboard."""
    sql = """
        SELECT detected_at, COALESCE(confidence, 0) AS confidence
        FROM contradictions
        WHERE detected_at IS NOT NULL
        ORDER BY detected_at DESC
        LIMIT 20
    """
    rows = await run_in_threadpool(Database.fetch_all, db, sql)

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
async def dashboard_data(db: sqlite3.Connection = Depends(get_db)):
    """Returns contradiction metrics for dashboard."""
    try:
        rows = await run_in_threadpool(Database.fetch_all, db, """
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
        logger.exception(f"Error fetching dashboard data: {e}")
        return JSONResponse(
            content={"error": "Failed to retrieve dashboard data."},
            status_code=500,
        )


@router.get("/api/contradiction-snapshot")
async def contradiction_snapshot(db: sqlite3.Connection = Depends(get_db)):
    """Return latest contradiction confidence scores for live chart refresh."""
    sql = """
        SELECT detected_at, confidence
        FROM contradictions
        WHERE confidence IS NOT NULL
        ORDER BY detected_at DESC
        LIMIT 20
    """
    rows = await run_in_threadpool(Database.fetch_all, db, sql)
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
    logger.info(f"WebSocket client connected: {websocket.client}")
    
    try:
        while True:
            data = await websocket.receive_text()
            now = datetime.now().strftime("%H:%M:%S")
            msg = {"time": now, "source": "LMS", "text": f"Echo: {data}"}
            await websocket.send_text(json.dumps(msg))
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket error in agent_chat_socket: {e}", exc_info=True)


@app.websocket("/ws/agent-chat/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Hosts the AI-powered QueryAgent chat."""
    await websocket.accept()
    sender = client_id
    logger.info(f"WebSocket client '{sender}' connected.")
    
    if sender == "dashboard":
        logger.info("📊 Dashboard connection established.")

    try:
        while True:
            msg = await websocket.receive_text()
            timestamp = datetime.now(timezone.utc).isoformat()

            # Record user message
            await run_in_threadpool(
                Database.execute, db,
                "INSERT INTO agent_chat_log (sender, message, timestamp) VALUES (?, ?, ?)",
                (sender, msg, timestamp),
                commit=True
            )

            # Get AI response (blocking call, offload to threadpool)
            reply = await run_in_threadpool(query_agent.ask, msg)
            reply_timestamp = datetime.now(timezone.utc).isoformat()

            # Record AI response
            await run_in_threadpool(
                Database.execute, db,
                "INSERT INTO agent_chat_log (sender, message, timestamp) VALUES (?, ?, ?)",
                ("QueryAgent", reply, reply_timestamp),
                commit=True
            )
            
            await websocket.send_text(reply)

    except WebSocketDisconnect:
        logger.info(f"WebSocket Closed for '{sender}': Client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error for '{sender}': {e}", exc_info=True)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
        except RuntimeError: # Already disconnected
            pass

# ============================================================
# DEBUG ENDPOINTS
# ============================================================

@router.get("/debug/seed-contradictions")
@router.post("/debug/seed-contradictions")
async def seed_contradictions(db: sqlite3.Connection = Depends(get_db)):
    """Insert test contradictions for dashboard testing. (DEBUG ONLY)"""
    if os.getenv("ENV") != "development":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is a debug endpoint, only available in development environment.")

    try:
        now = datetime.now(timezone.utc)
        for i in range(10):
            from datetime import timedelta
            await run_in_threadpool(
                Database.execute, db,
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
                    ContradictionStatus.PENDING.value, # Using Enum value
                ),
                commit=True
            )
        logger.info("Inserted 10 test contradictions.")
        return {"status": "ok", "message": "Inserted 10 test contradictions"}
        
    except Exception as e:
        logger.error(f"Seeding error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/reset-contradictions")
async def debug_reset_contradictions(db: sqlite3.Connection = Depends(get_db)):
    """Clears the contradictions table for testing. (DEBUG ONLY)"""
    if os.getenv("ENV") != "development":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is a debug endpoint, only available in development environment.")

    try:
        await run_in_threadpool(Database.execute, db, "DELETE FROM contradictions", commit=True)
        await run_in_threadpool(Database.execute, db, "DELETE FROM sqlite_sequence WHERE name='contradictions'", commit=True)
        logger.info("Contradictions table reset.")
        return {"status": "success", "message": "Contradictions table reset."}
        
    except Exception as e:
        logger.error(f"Error resetting contradictions table: {e}", exc_info=True)
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
