# ============================================================
# routes.py — CLEAN, CORRECTED, FULL VERSION
# ============================================================

# --------------------------
# Standard Library
# --------------------------
import os
import asyncio
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import logging
from contextlib import asynccontextmanager

# --------------------------
# Third Party
# --------------------------
import uvicorn
from dotenv import load_dotenv
from fastapi import (
    FastAPI, HTTPException, Query, Body, Request,
    WebSocket, WebSocketDisconnect, status, APIRouter, Depends, File, UploadFile
)
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

# --------------------------
# Local Imports — Ingest / Services
# --------------------------
from src.lms.ingestion.ingestor import LoreIngestor
from src.lms.services.extraction_service import ExtractionService
from src.lms.services.embedding_service import EmbeddingService
from src.lms.services.contradiction_service import ContradictionService
from src.lms.services.audit_log import AuditLogger
from src.lms.services.broadcaster import broadcaster

# --------------------------
# Local Imports — Database
# --------------------------
from src.lms.db.neo4j_adapter import Neo4jDatabase
from src.lms.api.dependencies import get_neo4j_db

# --------------------------
# Local Imports — Models
# --------------------------
from src.lms.core.models import (
    EntityCreate, EntityResponse, RelationshipCreate,
    ErrorResponse, ContradictionResponse, ContradictionCreate,
    ContradictionStatus, RelationshipResponse, ContradictionSeverity,
    ContradictionWithAnalysis, TriageAnalysisCreate,
    TriageAnalysisResponse, ContradictionUpdateRequest,
    EntityType, ApprovalStatus, ConfidenceLevel, PartyKnowledge,
    GameSessionResponse, InstanceResponse
)

# --------------------------
# Local Imports — Agents
# --------------------------
from src.lms.agents.auditor_agent import AuditorAgent
from src.lms.auditor.rule_based_auditor import RuleBasedAuditor
from src.lms.auditor.semantic_auditor import SemanticAuditor
from src.lms.agents.query_agent import QueryAgent

# --------------------------
# Local Imports — Orchestrator
# --------------------------
from src.lms.orchestrator import Orchestrator

# --------------------------
# Local Imports — Memory System
# --------------------------
from src.lms.memory import MemoryManager, ExperientialMemory


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger.warning("[LMS] routes.py imported")


# ============================================================
# CONTRADICTION ROUTER (Corrected)
# ============================================================

def get_contradiction_router():
    """
    Router that uses ONLY the globally initialized auditor_agent.
    No duplicate agents, no incorrect dependency injection.
    """
    router = APIRouter()

    @router.get("/audit/full")
    async def run_full_audit(request: Request):
        auditor_agent = request.app.state.auditor

        if auditor_agent is None:
            raise HTTPException(
                status_code=503,
                detail="AuditorAgent not initialized (AI disabled or startup failure)"
            )

        try:
            result = await auditor_agent.run_full_audit()
            return {"contradictions": result}

        except Exception as e:
            logger.exception("Full audit failed")
            raise HTTPException(status_code=500, detail=f"Audit failed: {e}")

    return router


# ============================================================
# APP LIFESPAN — CLEANED & STABLE
# ============================================================

async def connect_neo4j_with_timeout(neo4j_db: Neo4jDatabase, timeout: int = 10):
    try:
        await asyncio.wait_for(neo4j_db.connect(), timeout=timeout)
        await AuditLogger.log("✅ Neo4j connected successfully")
        return True
    except Exception as e:
        await AuditLogger.log(f"❌ Neo4j connection failed: {e}", level=logging.ERROR)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):

    await AuditLogger.log("Application startup…")

    # -------------------------
    # GEMINI KEY
    # -------------------------
    gemini_key = os.getenv("GEMINI_API_KEY")
    app.state.ai_enabled = bool(gemini_key)

    # -------------------------
    # INIT NEO4J
    # -------------------------
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    # Default to None to prevent AttributeError in endpoints
    app.state.neo4j_db = None
    connected = False

    if not neo4j_uri:
        logger.error("NEO4J_URI missing — application cannot start fully")
    else:
        app.state.neo4j_db = Neo4jDatabase(neo4j_uri, neo4j_user, neo4j_password)
        connected = await connect_neo4j_with_timeout(app.state.neo4j_db)
        if not connected:
            logger.error("Neo4j connection failed — application starting in degraded mode")

    # -------------------------
    # VECTOR INDEX
    # -------------------------
    if connected:
        try:
            indexes = await app.state.neo4j_db.list_indexes()
            has_vector = any(i.get("name") == "entity_embeddings" for i in indexes)

            if not has_vector:
                created = await app.state.neo4j_db.create_vector_index()
                app.state.vector_search_enabled = created
            else:
                app.state.vector_search_enabled = True

        except Exception as e:
            await AuditLogger.log(f"Vector index error: {e}", level=logging.ERROR)
            app.state.vector_search_enabled = False
    else:
        app.state.vector_search_enabled = False

    # -------------------------
    # INIT AGENTS
    # -------------------------
    if app.state.ai_enabled and connected:
        try:
            rule = RuleBasedAuditor(app.state.neo4j_db)
            semantic = SemanticAuditor(app.state.neo4j_db, gemini_key)

            app.state.auditor = AuditorAgent(
                app.state.neo4j_db,
                gemini_key,
                rule_based_auditor=rule,
                semantic_auditor=semantic
            )

            app.state.query_agent = QueryAgent(
                app.state.neo4j_db,
                gemini_key,
                enable_vector_search=app.state.vector_search_enabled,
            )

            await AuditLogger.log("✅ QueryAgent + Auditor initialized")
        except Exception as e:
            await AuditLogger.log(f"❌ Failed to initialize agents: {e}", level=logging.ERROR)
            app.state.auditor = None
            app.state.query_agent = None

    # -------------------------
    # INIT ORCHESTRATOR
    # -------------------------
    try:
        project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
        app.state.orchestrator = Orchestrator(
            project_root=project_root,
            gemini_api_key=gemini_key,
            neo4j_db=app.state.neo4j_db if connected else None,
        )
        await AuditLogger.log("✅ Orchestrator initialized")
    except Exception as e:
        await AuditLogger.log(f"❌ Failed to initialize Orchestrator: {e}", level=logging.ERROR)
        app.state.orchestrator = None

    # -------------------------
    # INIT MEMORY SYSTEM
    # -------------------------
    try:
        experiential = ExperientialMemory(db_path="data/experiential_memory.db")
        app.state.memory_manager = MemoryManager(
            neo4j_db=app.state.neo4j_db if connected else None,
            experiential=experiential,
        )
        await AuditLogger.log("✅ Memory System initialized (Experiential Memory active)")
    except Exception as e:
        await AuditLogger.log(f"❌ Failed to initialize Memory System: {e}", level=logging.ERROR)
        app.state.memory_manager = None

    # -------------------------
    # YIELD
    # -------------------------
    yield

    # -------------------------
    # SHUTDOWN
    # -------------------------
    try:
        await app.state.neo4j_db.close()
    except:
        pass

    await AuditLogger.log("Application shutdown…")


# ============================================================
# APP CONFIG
# ============================================================

load_dotenv()

app = FastAPI(
    title="Lore Management System API",
    description="Canonical lore engine with Gospel enforcement",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://lore-management-system.fly.dev"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Frontend assets mount (built React app)
frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "assets").exists():
    logger.info(f"Mounting frontend assets from {frontend_dist / 'assets'}")
    app.mount(
        "/assets",
        StaticFiles(directory=str(frontend_dist / "assets")),
        name="frontend-assets"
    )
else:
    logger.warning(f"Frontend assets NOT found at {frontend_dist / 'assets'}. UI may be broken.")

# Mount Static Files - Updated for new structure
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "ui" / "static")),
    name="static"
)


# ============================================================
# WEBSOCKET — GEMINI QUERY
# ============================================================

@app.websocket("/ws/gemini")
async def websocket_gemini_endpoint(websocket: WebSocket, client_id: str = Query(...)):
    await websocket.accept()

    # Wait for agent to initialize (during startup)
    for _ in range(30):
        if getattr(app.state, "query_agent", None):
            break
        await websocket.send_json({"status": "initializing"})
        await asyncio.sleep(0.1)

    if not getattr(app.state, "query_agent", None):
        await websocket.send_json({"error": "QueryAgent unavailable"})
        await websocket.close()
        return

    try:
        await app.state.query_agent.handle_websocket(websocket, client_id)
    except Exception as e:
        logger.exception("[WS] QueryAgent error")
        try:
            await websocket.send_json({"error": str(e)})
        finally:
            try:
                await websocket.close()
            except:
                pass


# ============================================================
# WEBSOCKET — AUDITOR EVENTS
# ============================================================

@app.websocket("/ws/auditor")
async def websocket_auditor_endpoint(websocket: WebSocket):
    await websocket.accept()
    queue = await broadcaster.subscribe("auditor_events")

    try:
        while True:
            try:
                # Wait for message with timeout to send keepalive
                msg = await asyncio.wait_for(queue.get(), timeout=25.0)
                await websocket.send_json(msg)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        pass

    finally:
        broadcaster.unsubscribe("auditor_events", queue)
        try:
            await websocket.close()
        except:
            pass


# ============================================================
# ROOT & DIAGNOSTICS
# ============================================================

@router.get("/")
def root():
    """Serve frontend index if built; fallback to API JSON."""
    frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    index_path = frontend_dist / "index.html"
    
    if index_path.exists():
        return FileResponse(str(index_path))
    
    logger.warning(f"Frontend index not found at {index_path}. Serving API status.")
    return {
        "message": "Lore Management System API",
        "version": "1.0.0",
        "status": "operational"
    }


@router.get("/health")
async def health_check(request: Request):
    out = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "features": {}
    }

    # Neo4j check - use getattr for resilience
    db = getattr(request.app.state, "neo4j_db", None)
    if db is None:
        out["checks"]["neo4j"] = "not_configured"
        out["status"] = "degraded"
    else:
        try:
            await db.execute("RETURN 1")
            out["checks"]["neo4j"] = "connected"
        except Exception as e:
            out["checks"]["neo4j"] = f"error: {str(e)[:50]}"
            out["status"] = "degraded"

        # Vector index check
        try:
            indexes = await db.list_indexes()
            has_vec = any(i.get("name") == "entity_embeddings" for i in indexes)
            out["checks"]["vector_index"] = "exists" if has_vec else "missing"
        except Exception as e:
            out["checks"]["vector_index"] = f"error: {str(e)[:50]}"

    # Agent checks - use getattr for resilience
    out["checks"]["query_agent"] = "ready" if getattr(request.app.state, "query_agent", None) else "not_ready"
    out["checks"]["auditor"] = "ready" if getattr(request.app.state, "auditor", None) else "not_ready"
    out["checks"]["orchestrator"] = "ready" if getattr(request.app.state, "orchestrator", None) else "not_ready"

    out["features"]["ai_enabled"] = getattr(request.app.state, "ai_enabled", False)
    out["features"]["vector_search"] = getattr(request.app.state, "vector_search_enabled", False)

    return out


@router.get("/debug/status")
async def debug_status(request: Request):
    try:
        neo4j_ok = request.app.state.neo4j_db.test_connection()
    except:
        neo4j_ok = False

    return {
        "environment": os.getenv("APP_ENV", "development"),
        "ai_enabled": getattr(request.app.state, "ai_enabled", False),
        "gemini_key_present": bool(os.getenv("GEMINI_API_KEY")),
        "neo4j_connected": neo4j_ok,
    }


# ============================================================
# ENTITY ENDPOINTS
# ============================================================

@router.post("/entities", response_model=EntityResponse, status_code=201)
async def create_entity(entity_data: EntityCreate, db: Neo4jDatabase = Depends(get_neo4j_db)):

    canon_id = f"{entity_data.entity_type.value.lower()}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    props = {
        "canon_id": canon_id,
        "entity_type": entity_data.entity_type.value,
        "name": entity_data.canonical_name,
        "canonical_name": entity_data.canonical_name,
        "approval_status": entity_data.approval_status.value,
        "confidence_level": entity_data.confidence_level.value,
        "party_knowledge": entity_data.party_knowledge.value,
        "created_at": now,
        "updated_at": now,
        "aliases": entity_data.aliases,
    }

    # Add approved fields
    for key, value in entity_data.approved_fields.items():
        if isinstance(value, (dict, list)):
            props[key] = json.dumps(value)
        else:
            props[key] = value

    safe_label = "".join([c for c in entity_data.entity_type.value if c.isalnum()])

    query = f"""
    MERGE (n:`{safe_label}` {{canon_id: $canon_id}})
    SET n += $props
    SET n:Entity
    RETURN n
    """

    try:
        await db.execute(query, {"canon_id": canon_id, "props": props})
        return await get_entity(canon_id, db=db)
    except Exception as e:
        await AuditLogger.log(f"Error in create_entity: {e}", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"Failed to create entity: {e}")


@router.get("/entities/{canon_id}", response_model=EntityResponse)
async def get_entity(canon_id: str, db: Neo4jDatabase = Depends(get_neo4j_db)):

    query = """
    MATCH (n:Entity {canon_id: $canon_id})
    RETURN n.canon_id AS canon_id,
           n.entity_type AS entity_type,
           n.canonical_name AS canonical_name,
           n.aliases AS aliases,
           n.approval_status AS approval_status,
           n.confidence_level AS confidence_level,
           n.party_knowledge AS party_knowledge,
           n.created_at AS created_at,
           n.updated_at AS updated_at,
           properties(n) AS all_props
    """

    rows = await db.execute(query, {"canon_id": canon_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Entity not found")

    row = rows[0]
    all_props = row["all_props"]

    reserved = {
        "canon_id", "entity_type", "canonical_name", "aliases",
        "approval_status", "confidence_level", "party_knowledge",
        "created_at", "updated_at", "name", "embedding",
    }

    approved_fields = {}
    for k, v in all_props.items():
        if k not in reserved:
            try:
                approved_fields[k] = json.loads(v)
            except:
                approved_fields[k] = v

    return EntityResponse(
        canon_id=row["canon_id"],
        entity_type=EntityType(row["entity_type"]),
        canonical_name=row["canonical_name"],
        aliases=row["aliases"] or [],
        approved_fields=approved_fields,
        approval_status=ApprovalStatus(row["approval_status"]),
        confidence_level=ConfidenceLevel(row["confidence_level"]),
        party_knowledge=PartyKnowledge(row["party_knowledge"]) if row.get("party_knowledge") else PartyKnowledge.KNOWN,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


@router.get("/entities", response_model=List[EntityResponse])
async def list_entities(
    db: Neo4jDatabase = Depends(get_neo4j_db),
    entity_type: Optional[EntityType] = None,
    approval_status: Optional[ApprovalStatus] = None,
    world_id: Optional[str] = Query(default=None, description="Filter by world/lore base ID"),
    limit: int = 100,
):

    query = "MATCH (n:Entity)"
    where = []
    params = {"limit": limit}

    if entity_type:
        where.append("n.entity_type = $type")
        params["type"] = entity_type.value

    if approval_status:
        where.append("n.approval_status = $status")
        params["status"] = approval_status.value

    if world_id:
        where.append("n.world_id = $world_id")
        params["world_id"] = world_id

    if where:
        query += " WHERE " + " AND ".join(where)

    query += """
    RETURN n.canon_id AS canon_id,
           n.entity_type AS entity_type,
           COALESCE(n.canonical_name, n.name) AS canonical_name,
           COALESCE(n.aliases, []) AS aliases,
           COALESCE(n.approval_status, 'PENDING') AS approval_status,
           COALESCE(n.confidence_level, 'AI_GENERATED') AS confidence_level,
           n.party_knowledge AS party_knowledge,
           COALESCE(n.created_at, datetime().epochMillis) AS created_at,
           COALESCE(n.updated_at, n.created_at, datetime().epochMillis) AS updated_at,
           properties(n) AS all_props
    ORDER BY n.created_at DESC
    LIMIT $limit
    """

    rows = await db.execute(query, params)

    reserved = {
        "canon_id", "entity_type", "canonical_name", "aliases",
        "approval_status", "confidence_level", "party_knowledge",
        "created_at", "updated_at", "name", "embedding",
    }

    out = []
    for row in rows:
        all_props = row["all_props"]
        approved_fields = {}

        for k, v in all_props.items():
            if k not in reserved:
                try:
                    approved_fields[k] = json.loads(v)
                except:
                    approved_fields[k] = v

        # Handle date parsing - may be ISO string or Neo4j datetime
        def parse_date(val):
            if val is None:
                return datetime.now(timezone.utc)
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace('Z', '+00:00'))
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val / 1000, tz=timezone.utc)
            return datetime.now(timezone.utc)

        out.append(
            EntityResponse(
                canon_id=row["canon_id"],
                entity_type=EntityType(row["entity_type"]),
                canonical_name=row["canonical_name"] or "Unknown",
                aliases=row["aliases"] or [],
                approved_fields=approved_fields,
                approval_status=ApprovalStatus(row["approval_status"]),
                confidence_level=ConfidenceLevel(row["confidence_level"]),
                party_knowledge=PartyKnowledge(row["party_knowledge"]) if row.get("party_knowledge") else PartyKnowledge.KNOWN,
                created_at=parse_date(row.get("created_at")),
                updated_at=parse_date(row.get("updated_at")),
            )
        )

    return out


# ============================================================
# INGESTION ENDPOINT
# ============================================================

@router.post("/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    process_immediately: bool = True,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    batch_id = f"batch-{uuid.uuid4().hex}"
    upload_dir = Path("uploads") / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    processing_results = []

    ingestor = None

    if process_immediately:
        try:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if gemini_key and request.app.state.ai_enabled:
                extraction = ExtractionService(api_key=gemini_key)
                embedding = EmbeddingService(api_key=gemini_key)
                ingestor = LoreIngestor(db=db, extraction_service=extraction, embedding_service=embedding)
        except Exception as e:
            await AuditLogger.log(f"Ingestor init error: {e}", level=logging.ERROR)

    for file in files:
        try:
            content = await file.read()
            filepath = upload_dir / file.filename
            await run_in_threadpool(filepath.write_bytes, content)
            saved_files.append(file.filename)

            if process_immediately and ingestor:
                try:
                    text = content.decode("utf-8")
                    data = await ingestor.process_file_content(file.filename, text)
                    result = await ingestor.save_to_neo4j(data["data"], file.filename)
                    processing_results.append({
                        "filename": file.filename,
                        "status": "processed",
                        "nodes_created": result["nodes_saved"],
                        "relationships_created": result["relationships_saved"],
                    })
                except UnicodeDecodeError:
                    processing_results.append({"filename": file.filename, "status": "skipped_binary"})
                except Exception as e:
                    processing_results.append({"filename": file.filename, "status": "failed", "error": str(e)})

        except Exception as e:
            await AuditLogger.log(f"Error saving file {file.filename}: {e}", level=logging.ERROR)
            raise HTTPException(500, f"Could not save file: {file.filename}")

    return {
        "batch_id": batch_id,
        "files_queued": len(saved_files),
        "status": "completed" if process_immediately else "queued",
        "filenames": saved_files,
        "processing_results": processing_results if process_immediately else [],
    }


class IngestTextRequest(BaseModel):
    """Request to ingest text content directly."""
    content: str = Field(..., min_length=10, description="Lore text to ingest")
    source_name: Optional[str] = Field(default="direct_input", description="Source identifier")


class IngestTextResponse(BaseModel):
    """Response from text ingestion."""
    status: str
    source_name: str
    nodes_created: int
    relationships_created: int
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]


class AdminResetRequest(BaseModel):
    """Request to reset database."""
    confirm: str


class AdminPinRequest(BaseModel):
    """Request to verify admin PIN."""
    pin: str


class AdminStatsResponse(BaseModel):
    """Database statistics."""
    total_nodes: int
    total_relationships: int
    characters: int
    locations: int
    factions: int
    items: int
    events: int
    concepts: int


@router.post("/ingest", response_model=IngestTextResponse)
async def ingest_text_endpoint(
    request: Request,
    ingest_req: IngestTextRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Ingest lore text directly without file upload.

    Uses the LoreParsingAgent which includes:
    - AI-powered entity extraction (Character, Location, Faction, Item, Event, Concept)
    - Personality trait detection for characters
    - OCEAN personality profile generation
    - Relationship inference
    - Neo4j persistence with proper labels
    """
    from src.lms.agents.lore_parsing_agent import LoreParsingAgent

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured (GEMINI_API_KEY missing)"
        )

    try:
        # Use LoreParsingAgent for proper AI-based entity extraction
        agent = LoreParsingAgent(api_key=gemini_key)
        source_name = ingest_req.source_name or "direct_input"

        result = await agent.parse_and_store(
            text=ingest_req.content,
            db=db,
            source_name=source_name,
            world_id=source_name,  # Use source name as world_id for filtering
        )

        # Format entities for response
        entities = []
        for entity in result.entities:
            entities.append({
                "name": entity.name,
                "type": entity.entity_type,
                "content": entity.description[:200] if entity.description else ""
            })

        # Format relationships for response
        relationships = []
        for rel in result.relationships:
            relationships.append({
                "source": rel.source,
                "target": rel.target,
                "type": rel.relationship_type
            })

        return IngestTextResponse(
            status="success",
            source_name=source_name,
            nodes_created=result.entities_stored,
            relationships_created=result.relationships_stored,
            entities=entities,
            relationships=relationships,
        )

    except Exception as e:
        logger.error(f"Text ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )


# ============================================================
# ENTITY BROWSER UI
# ============================================================

@router.get("/entities/browser", response_class=HTMLResponse)
async def entities_browser(request: Request, canon_id: Optional[str] = None):
    context = {"request": request}
    template = "entity_detail.html" if canon_id else "entities.html"
    if canon_id:
        context["canon_id"] = canon_id
    return templates.TemplateResponse(template, context)


# ============================================================
# DASHBOARD (Mock)
# ============================================================

class DashboardCard(BaseModel):
    id: int
    title: str
    description: Optional[str]
    severity: str
    source: str


@router.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/contradictions", response_model=List[DashboardCard])
async def get_contradictions_mock():
    return [
        DashboardCard(
            id=101,
            title="Timeline Fracture",
            description="NPC appears alive after recorded death.",
            severity="CRITICAL",
            source="Session Log"
        )
    ]


# ============================================================
# ADMIN ENDPOINTS
# ============================================================

# Default admin PIN - can be overridden via ADMIN_PIN environment variable
ADMIN_PIN = os.getenv("ADMIN_PIN", "1234")

# Server-side rate limiting for PIN attempts
_pin_attempts: Dict[str, list] = {}  # IP -> list of attempt timestamps
MAX_PIN_ATTEMPTS = 5
PIN_LOCKOUT_SECONDS = 300  # 5 minutes


@app.post("/admin/verify-pin")
async def verify_admin_pin(pin_req: AdminPinRequest, request: Request):
    """
    Verify admin PIN for access to admin panel.

    The PIN is read from the ADMIN_PIN environment variable.
    Default PIN is "1234" if not configured.

    Rate limited: 5 attempts per 5 minutes per IP.
    """
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit
    now = datetime.now(timezone.utc).timestamp()
    if client_ip in _pin_attempts:
        # Clean old attempts
        _pin_attempts[client_ip] = [
            t for t in _pin_attempts[client_ip]
            if now - t < PIN_LOCKOUT_SECONDS
        ]

        if len(_pin_attempts[client_ip]) >= MAX_PIN_ATTEMPTS:
            logger.warning(f"Admin PIN rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Try again later."
            )

    # Verify PIN
    if pin_req.pin == ADMIN_PIN:
        # Clear attempts on success
        _pin_attempts.pop(client_ip, None)
        logger.info(f"Admin access granted from IP: {client_ip}")
        return {"status": "success", "message": "PIN verified"}
    else:
        # Record failed attempt
        if client_ip not in _pin_attempts:
            _pin_attempts[client_ip] = []
        _pin_attempts[client_ip].append(now)

        remaining = MAX_PIN_ATTEMPTS - len(_pin_attempts[client_ip])
        logger.warning(f"Failed admin PIN attempt from IP: {client_ip} ({remaining} remaining)")

        raise HTTPException(
            status_code=401,
            detail="Invalid PIN"
        )


@app.get("/admin/stats", response_model=AdminStatsResponse)
async def get_admin_stats(db: Neo4jDatabase = Depends(get_neo4j_db)):
    """Get database statistics for admin panel."""
    try:
        # Get total node count
        total_result = await db.execute("MATCH (n) RETURN count(n) as total")
        total_nodes = total_result[0]["total"] if total_result else 0

        # Get total relationship count
        rel_result = await db.execute("MATCH ()-[r]->() RETURN count(r) as total")
        total_relationships = rel_result[0]["total"] if rel_result else 0

        # Get counts by entity type
        type_result = await db.execute("""
            MATCH (n)
            WHERE n.entity_type IS NOT NULL
            RETURN n.entity_type as type, count(n) as count
        """)

        type_counts = {row["type"]: row["count"] for row in type_result}

        return AdminStatsResponse(
            total_nodes=total_nodes,
            total_relationships=total_relationships,
            characters=type_counts.get("Character", 0),
            locations=type_counts.get("Location", 0),
            factions=type_counts.get("Faction", 0),
            items=type_counts.get("Item", 0),
            events=type_counts.get("Event", 0),
            concepts=type_counts.get("Concept", 0),
        )
    except Exception as e:
        logger.error(f"Failed to get admin stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/reset-database")
async def reset_database(
    reset_req: AdminResetRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Reset the database by deleting all nodes and relationships.

    DANGER: This is a destructive operation that cannot be undone.
    Requires confirm="RESET" in the request body.
    """
    if reset_req.confirm != "RESET":
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Send confirm='RESET' to proceed."
        )

    try:
        # Get count before deletion
        count_result = await db.execute("MATCH (n) RETURN count(n) as total")
        node_count = count_result[0]["total"] if count_result else 0

        # Delete all nodes and relationships
        await db.execute("MATCH (n) DETACH DELETE n")

        logger.warning(f"Database reset by admin. Deleted {node_count} nodes.")

        return {
            "status": "success",
            "message": f"Deleted {node_count} nodes and all relationships.",
            "nodes_deleted": node_count
        }
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


# ============================================================
# ROUTER REGISTRATION
# ============================================================

app.include_router(router)
app.include_router(get_contradiction_router())

# Orchestrator routes
from src.lms.api.orchestrator_routes import router as orchestrator_router
app.include_router(orchestrator_router, prefix="/api")

# Game session routes
from src.lms.api.game_routes import router as game_router
app.include_router(game_router, prefix="/api")

# Memory system routes
from src.lms.api.memory_routes import router as memory_router
app.include_router(memory_router, prefix="/api")

# D&D 5e rules system routes
from src.lms.api.dnd_routes import router as dnd_router
app.include_router(dnd_router, prefix="/api")


# ============================================================
# CATCH-ALL FOR SPA (must be registered LAST)
# ============================================================

@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    """
    Catch-all route for SPA client-side routing.
    Returns index.html for any path not matched by other routes.
    """
    frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    index_path = frontend_dist / "index.html"

    if index_path.exists():
        return FileResponse(str(index_path))

    raise HTTPException(status_code=404, detail="Not Found")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)