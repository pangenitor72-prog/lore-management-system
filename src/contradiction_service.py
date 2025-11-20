# src/contradiction_service.py
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json
import sqlite3
import logging
import os # For M5 environment check

from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.concurrency import run_in_threadpool

from src.database import Database, get_db, db_session, get_db_connection
from src.models import (
    ContradictionCreate, ContradictionResponse, TriageAnalysisCreate,
    TriageAnalysisResponse, ContradictionWithAnalysis, ContradictionStatus,
    ContradictionSeverity
)

logger = logging.getLogger("lms_contradiction_service")

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / 'src' / 'templates')) # M7: Standardize template path



# --- DEBUG: Seed Contradictions ---
@router.get("/debug/seed-contradictions")
@router.post("/debug/seed-contradictions")
async def seed_contradictions(db: sqlite3.Connection = Depends(get_db)):
    """Insert a few fake contradictions for testing the dashboard. (DEBUG ONLY)"""
    if os.getenv("ENV") != "development":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is a debug endpoint, only available in development environment.")
    try:
        now = datetime.now(timezone.utc)
        for i in range(10):
            from datetime import timedelta # This import should be at the top or within function
            await run_in_threadpool(
                Database.execute, db,
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
                    f"test-{i}-{uuid4().hex[:6]}",
                    "consistency",
                    ContradictionSeverity.LOW.value, # Use Enum value
                    f"Dummy contradiction {i}",
                    "{}",
                    (now - timedelta(minutes=10 * i)).isoformat(),
                    ContradictionStatus.PENDING.value, # Use Enum value
                ),
                commit=True
            )
        logger.info("Inserted 10 test contradictions.")
        return {"status": "ok", "message": "Inserted 10 test contradictions"}
    except Exception as e:
        logger.error(f"Seeding error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    # --- TRIAGE QUEUE ENDPOINTS ---

@router.post("/contradictions", response_model=ContradictionResponse, status_code=201)
async def create_contradiction(contradiction_data: ContradictionCreate, db: sqlite3.Connection = Depends(get_db)):
    """Add a new contradiction detected by the Auditor Agent to the queue."""
    try:
        with db_session() as conn:
            # Step 1: Insert into contradictions table
            cursor = Database.execute(conn, """
                INSERT INTO contradictions (contradiction_id, contradiction_type, severity, description, evidence, detected_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                contradiction_data.contradiction_id,
                contradiction_data.contradiction_type,
                contradiction_data.severity.value,
                contradiction_data.description,
                json.dumps(contradiction_data.evidence),
                contradiction_data.detected_at,
                ContradictionStatus.PENDING.value
            ))
            
            new_id = cursor.lastrowid
            
            # Step 2: Insert into contradiction_entities (many-to-many)
            for entity_id in contradiction_data.entity_ids:
                Database.execute(conn, """
                    INSERT INTO contradiction_entities (contradiction_id, canon_id)
                    VALUES (?, ?)
                """, (contradiction_data.contradiction_id, entity_id))

        # Fetch the created contradiction to return it
        created = await run_in_threadpool(Database.fetch_one, db, "SELECT * FROM contradictions WHERE id = ?", (new_id,))
        if not created:
            logger.error(f"Failed to retrieve contradiction after creation for ID: {new_id}")
            raise HTTPException(status_code=500, detail="Failed to retrieve contradiction after creation.")

        response_data = dict(created)
        response_data['entity_ids'] = contradiction_data.entity_ids
        return ContradictionResponse(**response_data)

    except sqlite3.IntegrityError as e:
        logger.warning(f"Database integrity error when creating contradiction: {e}", exc_info=True)
        if "UNIQUE constraint failed: contradictions.contradiction_id" in str(e):
            raise HTTPException(status_code=409, detail=f"Contradiction ID already exists: {contradiction_data.contradiction_id}")
        raise HTTPException(status_code=500, detail=f"Database integrity error: {e}")
    except Exception as e:
        logger.exception(f"Failed to create contradiction: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create contradiction: {e}")


@router.get("/contradictions", response_model=list[ContradictionResponse])
async def list_contradictions(
    db: sqlite3.Connection = Depends(get_db),
    status: Optional[ContradictionStatus] = None, # Use Enum for filter
    severity: Optional[ContradictionSeverity] = None, # Use Enum for filter
    limit: int = 50
):
    """List contradictions with filters."""
    query = "SELECT * FROM contradictions"
    params = []
    conditions = []

    if status:
        conditions.append("status = ?")
        params.append(status.value)
    if severity:
        conditions.append("severity = ?")
        params.append(severity.value)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    contradictions_data = await run_in_threadpool(Database.fetch_all, db, query, tuple(params))
    
    # Fetch all contradiction_entities in one go to avoid N+1
    contradiction_ids = [c['contradiction_id'] for c in contradictions_data]
    
    all_entity_links = {}
    if contradiction_ids:
        # Construct placeholders for IN clause
        placeholders = ','.join('?' * len(contradiction_ids))
        entity_links_query = f"SELECT contradiction_id, canon_id FROM contradiction_entities WHERE contradiction_id IN ({placeholders})"
        entity_links_rows = await run_in_threadpool(Database.fetch_all, db, entity_links_query, tuple(contradiction_ids))
        
        for link in entity_links_rows:
            all_entity_links.setdefault(link['contradiction_id'], []).append(link['canon_id'])

    response_list = []
    for c in contradictions_data:
        data = dict(c)
        data['evidence'] = json.loads(data['evidence']) if data['evidence'] else {} # Ensure evidence is dict (C5, M8)
        data['entity_ids'] = all_entity_links.get(c['contradiction_id'], [])
        response_list.append(ContradictionResponse(**data))
        
    return response_list


@router.get("/contradictions/queue/next", response_model=ContradictionWithAnalysis)
async def get_next_pending_contradiction(db: sqlite3.Connection = Depends(get_db)):
    """Get next pending contradiction ordered by severity (HIGH first), then created_at."""
    query = """
        SELECT * FROM contradictions
        WHERE status = 'PENDING'
        ORDER BY
            CASE severity
                WHEN 'HIGH' THEN 1
                WHEN 'MEDIUM' THEN 2
                WHEN 'LOW' THEN 3
            END,
            created_at ASC
        LIMIT 1
    """
    contradiction_dict = await run_in_threadpool(Database.fetch_one, db, query)
    
    if not contradiction_dict:
        raise HTTPException(status_code=404, detail="The triage queue is empty (no PENDING contradictions).")

    # Fetch details
    contradiction_id = contradiction_dict['contradiction_id']
    entity_ids_rows = await run_in_threadpool(Database.fetch_all, db,
        "SELECT canon_id FROM contradiction_entities WHERE contradiction_id = ?",
        (contradiction_id,)
    )
    data = dict(contradiction_dict)
    data['evidence'] = json.loads(data['evidence']) if data['evidence'] else {} # Ensure evidence is dict (C5, M8)
    data['entity_ids'] = [row['canon_id'] for row in entity_ids_rows]
    contradiction = ContradictionResponse(**data)
    
    # Analysis will be None as status is PENDING
    return ContradictionWithAnalysis(contradiction=contradiction, analysis=None)


@router.get("/contradictions/{contradiction_id}", response_model=ContradictionWithAnalysis)
async def get_contradiction_details(contradiction_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Get single contradiction with full details and analysis."""
    
    contradiction_dict = await run_in_threadpool(Database.fetch_one, db, "SELECT * FROM contradictions WHERE contradiction_id = ?", (contradiction_id,))
    if not contradiction_dict:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")

    entity_ids_rows = await run_in_threadpool(Database.fetch_all, db,
        "SELECT canon_id FROM contradiction_entities WHERE contradiction_id = ?",
        (contradiction_id,)
    )
    data = dict(contradiction_dict)
    data['evidence'] = json.loads(data['evidence']) if data['evidence'] else {} # Ensure evidence is dict (C5, M8)
    data['entity_ids'] = [row['canon_id'] for row in entity_ids_rows]
    contradiction = ContradictionResponse(**data)
    
    analysis_dict = await run_in_threadpool(Database.fetch_one, db, "SELECT * FROM triage_analysis WHERE contradiction_id = ?", (contradiction_id,))
    analysis = None
    if analysis_dict:
        # Explicitly convert confidence string to Enum for TriageAnalysisResponse (M3)
        analysis_data = dict(analysis_dict)
        analysis_data['confidence'] = ContradictionSeverity(analysis_data['confidence']) 
        analysis = TriageAnalysisResponse(**analysis_data)
    
    return ContradictionWithAnalysis(contradiction=contradiction, analysis=analysis)


@router.patch("/contradictions/{contradiction_id}/status", response_model=ContradictionResponse)
async def update_contradiction_status(contradiction_id: str, new_status_data: dict, db: sqlite3.Connection = Depends(get_db)):
    """Update contradiction status."""
    if 'status' not in new_status_data:
        raise HTTPException(status_code=422, detail="Missing 'status' field in request body.")
        
    status_str = new_status_data['status']
    try:
        # Validate status_str against ContradictionStatus Enum
        new_contradiction_status = ContradictionStatus(status_str)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status value: {status_str}")

    await run_in_threadpool(Database.execute, db, "UPDATE contradictions SET status = ? WHERE contradiction_id = ?", (new_contradiction_status.value, contradiction_id), commit=True)
    
    updated_dict = await run_in_threadpool(Database.fetch_one, db, "SELECT * FROM contradictions WHERE contradiction_id = ?", (contradiction_id,))
    if not updated_dict:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")
    
    entity_ids_rows = await run_in_threadpool(Database.fetch_all, db,
        "SELECT canon_id FROM contradiction_entities WHERE contradiction_id = ?",
        (contradiction_id,)
    )
    data = dict(updated_dict)
    data['evidence'] = json.loads(data['evidence']) if data['evidence'] else {} # Ensure evidence is dict (C5, M8)
    data['entity_ids'] = [row['canon_id'] for row in entity_ids_rows]
    return ContradictionResponse(**data)


@router.post("/contradictions/{contradiction_id}/analysis", response_model=TriageAnalysisResponse, status_code=201)
async def add_triage_analysis(contradiction_id: str, analysis_data: TriageAnalysisCreate, db: sqlite3.Connection = Depends(get_db)):
    """Add Claude's triage analysis and update contradiction status to IN_REVIEW."""
    
    contradiction_exists = await run_in_threadpool(Database.fetch_one, db, "SELECT id FROM contradictions WHERE contradiction_id = ?", (contradiction_id,))
    if not contradiction_exists:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")
    
    try:
        with db_session() as conn:
            cursor = Database.execute(conn, """
                INSERT INTO triage_analysis (contradiction_id, analyst, analysis, recommendation, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                contradiction_id,
                analysis_data.analyst,
                analysis_data.analysis,
                analysis_data.recommendation,
                analysis_data.confidence.value # Use .value for Enum
            ))
            
            new_id = cursor.lastrowid
            
            Database.execute(conn,
                "UPDATE contradictions SET status = ? WHERE contradiction_id = ?",
                (ContradictionStatus.IN_REVIEW.value, contradiction_id)
            )

        analysis_dict = await run_in_threadpool(Database.fetch_one, db, "SELECT * FROM triage_analysis WHERE id = ?", (new_id,))
        if not analysis_dict:
            logger.error(f"Failed to retrieve analysis after creation for ID: {new_id}")
            raise HTTPException(status_code=500, detail="Failed to retrieve analysis after creation.")
        
        # Explicitly convert confidence string to Enum for TriageAnalysisResponse (M3)
        analysis_data_response = dict(analysis_dict)
        analysis_data_response['confidence'] = ContradictionSeverity(analysis_data_response['confidence'])
        return TriageAnalysisResponse(**analysis_data_response)
        
    except sqlite3.IntegrityError as e:
        logger.warning(f"Database integrity error when adding triage analysis: {e}", exc_info=True)
        if "UNIQUE constraint failed: triage_analysis.contradiction_id" in str(e):
            raise HTTPException(status_code=409, detail=f"Analysis already exists for contradiction: {contradiction_id}")
        raise HTTPException(status_code=500, detail=f"Database integrity error: {e}")
    except Exception as e:
        logger.exception(f"Failed to add analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add analysis: {e}")


# --- Dashboard (HTML) ---
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Render the Audit Dashboard with static snapshot data."""
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
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "labels": labels[::-1],  # oldest → newest
            "scores": scores[::-1],
        },
    )


# --- API: Contradiction Snapshot ---
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

# --- Contradiction Status Update Functions (called from api.py) ---
def set_in_review(contradiction_id: str, user: str, db: sqlite3.Connection) -> bool:
    """Sets contradiction status to IN_REVIEW."""
    try:
        updated = Database.execute(
            db,
            "UPDATE contradictions SET status = ?, updated_by = ? WHERE contradiction_id = ?",
            (ContradictionStatus.IN_REVIEW.value, user, contradiction_id),
            commit=True
        )
        if updated.rowcount == 0:
            logger.warning(f"Contradiction {contradiction_id} not found for 'in_review' update.")
            return False
        logger.info(f"Contradiction {contradiction_id} set to IN_REVIEW by {user}.")
        return True
    except Exception as e:
        logger.exception(f"Error setting contradiction {contradiction_id} to IN_REVIEW: {e}")
        return False

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
            logger.warning(f"Contradiction {contradiction_id} not found for 'resolved' update.")
            return False
        logger.info(f"Contradiction {contradiction_id} set to RESOLVED by {user}. Notes: {notes}")
        return True
    except Exception as e:
        logger.exception(f"Error setting contradiction {contradiction_id} to RESOLVED: {e}")
        return False

def set_dismissed(contradiction_id: str, user: str, notes: str, db: sqlite3.Connection) -> bool:
    """Sets contradiction status to DISMISSED."""
    try:
        updated = Database.execute(
            db,
            "UPDATE contradictions SET status = ?, resolution_notes = ?, updated_by = ? WHERE contradiction_id = ?",
            (ContradictionStatus.DISMISSED.value, notes, user, contradiction_id),
            commit=True
        )
        if updated.rowcount == 0:
            logger.warning(f"Contradiction {contradiction_id} not found for 'dismissed' update.")
            return False
        logger.info(f"Contradiction {contradiction_id} set to DISMISSED by {user}. Notes: {notes}")
        return True
    except Exception as e:
        logger.exception(f"Error setting contradiction {contradiction_id} to DISMISSED: {e}")
        return False


# --- Router Accessor ---
def get_router():
    return router
