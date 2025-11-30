# src/services/contradiction_service.py
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import json
import logging
import os
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.services.audit_log import AuditLogger
from src.db.neo4j_adapter import Neo4jDatabase
from src.api.dependencies import get_neo4j_db
from src.core.models import (
    ContradictionCreate, ContradictionResponse, TriageAnalysisCreate,
    TriageAnalysisResponse, ContradictionWithAnalysis, ContradictionStatus,
    ContradictionSeverity
)

router = APIRouter(prefix="/api")

BASE_DIR = Path(__file__).resolve().parent.parent  # Goes to src/
templates = Jinja2Templates(directory=str(BASE_DIR / 'ui' / 'templates'))

# --- HELPER: Parse Contradiction Record ---
def parse_contradiction_record(record) -> ContradictionResponse:
    """Convert Neo4j record to ContradictionResponse."""
    props = record['props']
    entity_ids = record.get('entity_ids', [])
    
    # Handle evidence JSON
    evidence = props.get('evidence', '{}')
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except:
            evidence = {}
    
    return ContradictionResponse(
        id=0, # Placeholder for backward compat if needed, or remove ID from model if possible
        contradiction_id=props['contradiction_id'],
        contradiction_type=props.get('type') or props.get('contradiction_type'),
        severity=ContradictionSeverity(props['severity']),
        description=props['description'],
        evidence=evidence,
        detected_at=datetime.fromisoformat(props['detected_at']),
        status=ContradictionStatus(props['status']),
        created_at=datetime.fromisoformat(props.get('created_at', props['detected_at'])),
        entity_ids=entity_ids
    )

# --- DEBUG: Seed Contradictions ---
@router.get("/debug/seed-contradictions")
@router.post("/debug/seed-contradictions")
async def seed_contradictions(db: Neo4jDatabase = Depends(get_neo4j_db)):
    """Insert a few fake contradictions for testing the dashboard. (DEBUG ONLY)"""
    if os.getenv("ENV") != "development":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Debug endpoint.")
    
    try:
        now = datetime.now(timezone.utc)
        for i in range(10):
            cid = f"test-{i}-{uuid4().hex[:6]}"
            query = """
            CREATE (c:Contradiction {
                contradiction_id: $cid,
                type: 'consistency',
                severity: $sev,
                description: $desc,
                evidence: '{}',
                detected_at: $det,
                status: $stat,
                created_at: $det
            })
            """
            await db.execute(query, {
                "cid": cid,
                "sev": ContradictionSeverity.LOW.value,
                "desc": f"Dummy contradiction {i}",
                "det": (now - datetime.timedelta(minutes=10 * i)).isoformat(),
                "stat": ContradictionStatus.PENDING.value
            })
        await AuditLogger.log("Inserted 10 test contradictions.")
        return {"status": "ok"}
    except Exception as e:
        await AuditLogger.log(f"Seeding error: {e}", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=str(e))

# --- TRIAGE QUEUE ENDPOINTS ---

@router.post("/contradictions", response_model=ContradictionResponse, status_code=201)
async def create_contradiction(contradiction_data: ContradictionCreate, db: Neo4jDatabase = Depends(get_neo4j_db)):
    """Add a new contradiction detected by the Auditor Agent to the queue."""
    query = """
    MERGE (c:Contradiction {contradiction_id: $cid})
    SET c.type = $type,
        c.severity = $severity,
        c.description = $desc,
        c.evidence = $evidence,
        c.detected_at = $detected,
        c.status = $status,
        c.created_at = $detected
    RETURN c
    """
    
    try:
        await db.execute(query, {
            "cid": contradiction_data.contradiction_id,
            "type": contradiction_data.contradiction_type,
            "severity": contradiction_data.severity.value,
            "desc": contradiction_data.description,
            "evidence": json.dumps(contradiction_data.evidence),
            "detected": contradiction_data.detected_at.isoformat(),
            "status": ContradictionStatus.PENDING.value
        })
        
        # Link Entities
        for eid in contradiction_data.entity_ids:
            link_query = """
            MATCH (c:Contradiction {contradiction_id: $cid})
            MATCH (e {canon_id: $eid})
            MERGE (c)-[:INVOLVES]->(e)
            """
            await db.execute(link_query, {
                "cid": contradiction_data.contradiction_id,
                "eid": eid
            })

        return await get_contradiction_details_internal(contradiction_data.contradiction_id, db)

    except Exception as e:
        await AuditLogger.log(f"Failed to create contradiction: {e}", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"Failed to create contradiction: {e}")

@router.get("/contradictions", response_model=List[ContradictionResponse])
async def list_contradictions(
    db: Neo4jDatabase = Depends(get_neo4j_db),
    status: Optional[ContradictionStatus] = None,
    severity: Optional[ContradictionSeverity] = None,
    limit: int = 50
):
    """List contradictions with filters."""
    query = "MATCH (c:Contradiction)"
    where = []
    params = {"limit": limit}
    
    if status:
        where.append("c.status = $status")
        params["status"] = status.value
    if severity:
        where.append("c.severity = $severity")
        params["severity"] = severity.value
        
    if where:
        query += " WHERE " + " AND ".join(where)
        
    query += """
    OPTIONAL MATCH (c)-[:INVOLVES]->(e)
    RETURN properties(c) AS props, collect(e.canon_id) AS entity_ids
    ORDER BY c.created_at DESC
    LIMIT $limit
    """
    
    records = await db.execute(query, params)
    return [parse_contradiction_record(r) for r in records]

@router.get("/contradictions/queue/next", response_model=ContradictionWithAnalysis)
async def get_next_pending_contradiction(db: Neo4jDatabase = Depends(get_neo4j_db)):
    """Get next pending contradiction ordered by severity (HIGH first), then created_at."""
    query = """
    MATCH (c:Contradiction {status: 'PENDING'})
    WITH c
    ORDER BY 
        CASE c.severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 END ASC,
        c.created_at ASC
    LIMIT 1
    OPTIONAL MATCH (c)-[:INVOLVES]->(e)
    RETURN properties(c) AS props, collect(e.canon_id) AS entity_ids
    """
    records = await db.execute(query)
    
    if not records:
        raise HTTPException(status_code=404, detail="The triage queue is empty.")
        
    contradiction = parse_contradiction_record(records[0])
    return ContradictionWithAnalysis(contradiction=contradiction, analysis=None)

@router.get("/contradictions/{contradiction_id}", response_model=ContradictionWithAnalysis)
async def get_contradiction_details(contradiction_id: str, db: Neo4jDatabase = Depends(get_neo4j_db)):
    """Get single contradiction with full details and analysis."""
    # Get Contradiction
    con_response = await get_contradiction_details_internal(contradiction_id, db)
    
    # Get Analysis
    query = """
    MATCH (c:Contradiction {contradiction_id: $cid})<-[:ANALYZES]-(a:TriageAnalysis)
    RETURN properties(a) AS props
    """
    records = await db.execute(query, {"cid": contradiction_id})
    analysis = None
    if records:
        props = records[0]['props']
        analysis = TriageAnalysisResponse(
            id=0,
            contradiction_id=contradiction_id,
            analyst=props['analyst'],
            analysis=props['analysis'],
            recommendation=props['recommendation'],
            confidence=ContradictionSeverity(props['confidence']),
            analyzed_at=datetime.fromisoformat(props['analyzed_at'])
        )
        
    return ContradictionWithAnalysis(contradiction=con_response, analysis=analysis)

# --- Helper for internal use ---
async def get_contradiction_details_internal(contradiction_id: str, db: Neo4jDatabase) -> ContradictionResponse:
    query = """
    MATCH (c:Contradiction {contradiction_id: $cid})
    OPTIONAL MATCH (c)-[:INVOLVES]->(e)
    RETURN properties(c) AS props, collect(e.canon_id) AS entity_ids
    """
    records = await db.execute(query, {"cid": contradiction_id})
    if not records:
        raise HTTPException(status_code=404, detail=f"Contradiction not found: {contradiction_id}")
    return parse_contradiction_record(records[0])

# --- TRIAGE ACTION ENDPOINTS ---

@router.post("/contradictions/{contradiction_id}/resolve", response_model=ContradictionResponse)
async def resolve_contradiction(
    contradiction_id: str,
    body: dict,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """Mark contradiction as RESOLVED with user notes."""
    user = body.get("user", "Unknown")
    notes = body.get("notes", "")
    
    query = """
    MATCH (c:Contradiction {contradiction_id: $cid})
    SET c.status = $status,
        c.resolution_notes = $notes,
        c.updated_by = $user,
        c.updated_at = $now
    RETURN c
    """
    await db.execute(query, {
        "cid": contradiction_id,
        "status": ContradictionStatus.RESOLVED.value,
        "notes": notes,
        "user": user,
        "now": datetime.now(timezone.utc).isoformat()
    })
    
    return await get_contradiction_details_internal(contradiction_id, db)

@router.post("/contradictions/{contradiction_id}/dismiss", response_model=ContradictionResponse)
async def dismiss_contradiction(
    contradiction_id: str,
    body: dict,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """Mark contradiction as DISMISSED with user notes."""
    user = body.get("user", "Unknown")
    notes = body.get("notes", "")
    
    query = """
    MATCH (c:Contradiction {contradiction_id: $cid})
    SET c.status = $status,
        c.resolution_notes = $notes,
        c.updated_by = $user,
        c.updated_at = $now
    RETURN c
    """
    await db.execute(query, {
        "cid": contradiction_id,
        "status": ContradictionStatus.DISMISSED.value,
        "notes": notes,
        "user": user,
        "now": datetime.now(timezone.utc).isoformat()
    })
    
    return await get_contradiction_details_internal(contradiction_id, db)

@router.post("/contradictions/{contradiction_id}/review", response_model=ContradictionResponse)
async def mark_in_review(
    contradiction_id: str,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """Mark contradiction as IN_REVIEW."""
    query = """
    MATCH (c:Contradiction {contradiction_id: $cid})
    SET c.status = $status,
        c.updated_at = $now
    RETURN c
    """
    await db.execute(query, {
        "cid": contradiction_id,
        "status": ContradictionStatus.IN_REVIEW.value,
        "now": datetime.now(timezone.utc).isoformat()
    })
    return await get_contradiction_details_internal(contradiction_id, db)

@router.patch("/contradictions/{contradiction_id}/status", response_model=ContradictionResponse)
async def update_contradiction_status(
    contradiction_id: str, 
    new_status_data: dict, 
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """Update contradiction status."""
    status_str = new_status_data.get('status')
    try:
        new_status = ContradictionStatus(status_str)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status: {status_str}")
        
    query = """
    MATCH (c:Contradiction {contradiction_id: $cid})
    SET c.status = $status,
        c.updated_at = $now
    RETURN c
    """
    await db.execute(query, {
        "cid": contradiction_id,
        "status": new_status.value,
        "now": datetime.now(timezone.utc).isoformat()
    })
    return await get_contradiction_details_internal(contradiction_id, db)

@router.post("/contradictions/{contradiction_id}/analysis", response_model=TriageAnalysisResponse, status_code=201)
async def add_triage_analysis(
    contradiction_id: str, 
    analysis_data: TriageAnalysisCreate, 
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """Add Claude's triage analysis and update contradiction status."""
    
    # Create Analysis Node and Link
    query = """
    MATCH (c:Contradiction {contradiction_id: $cid})
    CREATE (a:TriageAnalysis {
        analyst: $analyst,
        analysis: $analysis,
        recommendation: $rec,
        confidence: $conf,
        analyzed_at: $now
    })
    MERGE (a)-[:ANALYZES]->(c)
    SET c.status = $status
    RETURN properties(a) AS props
    """
    
    now = datetime.now(timezone.utc).isoformat()
    records = await db.execute(query, {
        "cid": contradiction_id,
        "analyst": analysis_data.analyst,
        "analysis": analysis_data.analysis,
        "rec": analysis_data.recommendation,
        "conf": analysis_data.confidence.value,
        "now": now,
        "status": ContradictionStatus.IN_REVIEW.value
    })
    
    if not records:
        raise HTTPException(status_code=404, detail="Contradiction not found or failed to create analysis.")
        
    props = records[0]['props']
    return TriageAnalysisResponse(
        id=0,
        contradiction_id=contradiction_id,
        analyst=props['analyst'],
        analysis=props['analysis'],
        recommendation=props['recommendation'],
        confidence=ContradictionSeverity(props['confidence']),
        analyzed_at=datetime.fromisoformat(props['analyzed_at'])
    )

# --- DASHBOARD & SNAPSHOT ---

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Neo4jDatabase = Depends(get_neo4j_db)):
    """Render the Audit Dashboard."""
    query = """
    MATCH (c:Contradiction)
    WHERE c.confidence IS NOT NULL
    RETURN c.detected_at AS detected_at, c.confidence AS confidence
    ORDER BY c.detected_at DESC
    LIMIT 20
    """
    records = await db.execute(query)
    labels = [r["detected_at"] for r in records]
    scores = [float(r["confidence"]) for r in records]
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "labels": labels[::-1],
            "scores": scores[::-1],
        },
    )

@router.get("/api/contradiction-snapshot")
async def contradiction_snapshot(db: Neo4jDatabase = Depends(get_neo4j_db)):
    """Return latest contradiction confidence scores."""
    query = """
    MATCH (c:Contradiction)
    WHERE c.confidence IS NOT NULL
    RETURN c.detected_at AS detected_at, c.confidence AS confidence
    ORDER BY c.detected_at DESC
    LIMIT 20
    """
    records = await db.execute(query)
    labels = [r["detected_at"] for r in records]
    scores = [float(r["confidence"]) for r in records]
    return {"labels": labels[::-1], "scores": scores[::-1]}

def get_router():
    return router
