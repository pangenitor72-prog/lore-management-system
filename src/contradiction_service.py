# src/contradiction_service.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from jinja2 import Environment, FileSystemLoader
from src.database import Database
from src.models import *
from src.auditor_agent import AuditorAgent
from src.query_agent import QueryAgent
import json
import sqlite3
from fastapi import HTTPException
from src.models import (
    ContradictionCreate, ContradictionResponse, TriageAnalysisCreate, 
    TriageAnalysisResponse, ContradictionWithAnalysis, ContradictionStatus, 
    ContradictionSeverity
)

router = APIRouter()
db = Database("data/lore.db")
templates = Jinja2Templates(directory="src/templates")


# --- DEBUG: Seed Contradictions ---
@router.get("/debug/seed-contradictions")
@router.post("/debug/seed-contradictions")
def seed_contradictions():
    """Insert a few fake contradictions for testing the dashboard."""
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
                    f"test-{i}-{uuid4().hex[:6]}",
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
    # --- TRIAGE QUEUE ENDPOINTS ---

@router.post("/contradictions", response_model=ContradictionResponse, status_code=201)
def create_contradiction(contradiction_data: ContradictionCreate):
    """Add a new contradiction detected by the Auditor Agent to the queue."""
    try:
        with db.transaction() as conn:
            # Step 1: Insert into contradictions table
            cursor = conn.execute("""
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
                conn.execute("""
                    INSERT INTO contradiction_entities (contradiction_id, canon_id)
                    VALUES (?, ?)
                """, (contradiction_data.contradiction_id, entity_id))

        # Fetch the created contradiction to return it
        created = db.fetch_one("SELECT * FROM contradictions WHERE id = ?", (new_id,))
        if not created:
            raise HTTPException(status_code=500, detail="Failed to retrieve contradiction after creation.")

        response_data = dict(created)
        response_data['entity_ids'] = contradiction_data.entity_ids
        return ContradictionResponse(**response_data)

    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: contradictions.contradiction_id" in str(e):
            raise HTTPException(status_code=409, detail=f"Contradiction ID already exists: {contradiction_data.contradiction_id}")
        raise HTTPException(status_code=500, detail=f"Database integrity error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create contradiction: {e}")


@router.get("/contradictions", response_model=list[ContradictionResponse])
def list_contradictions(
    status: ContradictionStatus | None = None,
    severity: ContradictionSeverity | None = None,
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

    contradictions = db.fetch_all(query, tuple(params))
    
    # Attach entity IDs
    response_list = []
    for c in contradictions:
        entity_ids_rows = db.fetch_all(
            "SELECT canon_id FROM contradiction_entities WHERE contradiction_id = ?",
            (c['contradiction_id'],)
        )
        data = dict(c)
        data['entity_ids'] = [row['canon_id'] for row in entity_ids_rows]
        response_list.append(ContradictionResponse(**data))
        
    return response_list


@router.get("/contradictions/queue/next", response_model=ContradictionWithAnalysis)
def get_next_pending_contradiction():
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
    contradiction_dict = db.fetch_one(query)
    
    if not contradiction_dict:
        raise HTTPException(status_code=404, detail="The triage queue is empty (no PENDING contradictions).")

    # Fetch details
    contradiction_id = contradiction_dict['contradiction_id']
    entity_ids_rows = db.fetch_all(
        "SELECT canon_id FROM contradiction_entities WHERE contradiction_id = ?",
        (contradiction_id,)
    )
    data = dict(contradiction_dict)
    data['entity_ids'] = [row['canon_id'] for row in entity_ids_rows]
    contradiction = ContradictionResponse(**data)
    
    # Analysis will be None as status is PENDING
    return ContradictionWithAnalysis(contradiction=contradiction, analysis=None)


@router.get("/contradictions/{contradiction_id}", response_model=ContradictionWithAnalysis)
def get_contradiction_details(contradiction_id: str):
    """Get single contradiction with full details and analysis."""
    
    contradiction_dict = db.fetch_one("SELECT * FROM contradictions WHERE contradiction_id = ?", (contradiction_id,))
    if not contradiction_dict:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")

    entity_ids_rows = db.fetch_all(
        "SELECT canon_id FROM contradiction_entities WHERE contradiction_id = ?",
        (contradiction_id,)
    )
    data = dict(contradiction_dict)
    data['entity_ids'] = [row['canon_id'] for row in entity_ids_rows]
    contradiction = ContradictionResponse(**data)
    
    analysis_dict = db.fetch_one("SELECT * FROM triage_analysis WHERE contradiction_id = ?", (contradiction_id,))
    analysis = TriageAnalysisResponse(**analysis_dict) if analysis_dict else None
    
    return ContradictionWithAnalysis(contradiction=contradiction, analysis=analysis)


@router.patch("/contradictions/{contradiction_id}/status", response_model=ContradictionResponse)
def update_contradiction_status(contradiction_id: str, new_status_data: dict):
    """Update contradiction status."""
    if 'status' not in new_status_data:
        raise HTTPException(status_code=422, detail="Missing 'status' field in request body.")
        
    status_str = new_status_data['status']
    if status_str not in [e.value for e in ContradictionStatus]:
        raise HTTPException(status_code=422, detail=f"Invalid status value: {status_str}")

    db.execute("UPDATE contradictions SET status = ? WHERE contradiction_id = ?", (status_str, contradiction_id))
    
    updated_dict = db.fetch_one("SELECT * FROM contradictions WHERE contradiction_id = ?", (contradiction_id,))
    if not updated_dict:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")
    
    entity_ids_rows = db.fetch_all(
        "SELECT canon_id FROM contradiction_entities WHERE contradiction_id = ?",
        (contradiction_id,)
    )
    data = dict(updated_dict)
    data['entity_ids'] = [row['canon_id'] for row in entity_ids_rows]
    return ContradictionResponse(**data)


@router.post("/contradictions/{contradiction_id}/analysis", response_model=TriageAnalysisResponse, status_code=201)
def add_triage_analysis(contradiction_id: str, analysis_data: TriageAnalysisCreate):
    """Add Claude's triage analysis and update contradiction status to IN_REVIEW."""
    
    if not db.fetch_one("SELECT id FROM contradictions WHERE contradiction_id = ?", (contradiction_id,)):
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")
    
    try:
        with db.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO triage_analysis (contradiction_id, analyst, analysis, recommendation, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                contradiction_id,
                analysis_data.analyst,
                analysis_data.analysis,
                analysis_data.recommendation,
                analysis_data.confidence
            ))
            
            new_id = cursor.lastrowid
            
            conn.execute(
                "UPDATE contradictions SET status = ? WHERE contradiction_id = ?",
                (ContradictionStatus.IN_REVIEW.value, contradiction_id)
            )

        analysis_dict = db.fetch_one("SELECT * FROM triage_analysis WHERE id = ?", (new_id,))
        if not analysis_dict:
            raise HTTPException(status_code=500, detail="Failed to retrieve analysis after creation.")
            
        return TriageAnalysisResponse(**analysis_dict)
        
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: triage_analysis.contradiction_id" in str(e):
            raise HTTPException(status_code=409, detail=f"Analysis already exists for contradiction: {contradiction_id}")
        raise HTTPException(status_code=500, detail=f"Database integrity error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add analysis: {e}")


# --- Dashboard (HTML) ---
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """Render the Audit Dashboard with static snapshot data."""
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


# --- Router Accessor ---
def get_router():
    return router
