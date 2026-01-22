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
from src.mantle.ingestion.ingestor import LoreIngestor
from src.mantle.services.extraction_service import ExtractionService
from src.mantle.services.embedding_service import EmbeddingService
from src.mantle.services.contradiction_service import ContradictionService
from src.mantle.services.audit_log import AuditLogger
from src.mantle.services.broadcaster import broadcaster

# --------------------------
# Local Imports — Database
# --------------------------
from src.mantle.db.neo4j_adapter import Neo4jDatabase
from src.mantle.api.dependencies import get_neo4j_db

# --------------------------
# Local Imports — Models
# --------------------------
from src.mantle.core.models import (
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
from src.mantle.agents.auditor_agent import AuditorAgent
from src.mantle.auditor.rule_based_auditor import RuleBasedAuditor
from src.mantle.auditor.semantic_auditor import SemanticAuditor
from src.mantle.agents.query_agent import QueryAgent

# --------------------------
# Local Imports — Orchestrator
# --------------------------
from src.mantle.orchestrator import Orchestrator

# --------------------------
# Local Imports — Memory System
# --------------------------
from src.mantle.memory import MemoryManager, ExperientialMemory


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
    # LOAD ADMIN-CREATED LORE BASES FROM NEO4J
    # -------------------------
    if connected:
        try:
            from src.mantle.api.game_routes import load_lore_bases_from_neo4j
            neo4j_count = await load_lore_bases_from_neo4j(app.state.neo4j_db)
            if neo4j_count > 0:
                await AuditLogger.log(f"✅ Loaded {neo4j_count} admin-created lore bases from Neo4j")
        except Exception as e:
            logger.error(f"Failed to load lore bases from Neo4j: {e}")

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
    except Exception:
        pass  # Graceful shutdown - ignore close errors

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
        "http://localhost:8000",
        "http://localhost:9000",
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

# PWA files (manifest, service worker, icons)
if frontend_dist.exists():
    # Mount icons directory
    if (frontend_dist / "icons").exists():
        app.mount(
            "/icons",
            StaticFiles(directory=str(frontend_dist / "icons")),
            name="pwa-icons"
        )

    # Mount images directory (raven mascot, etc.)
    if (frontend_dist / "images").exists():
        app.mount(
            "/images",
            StaticFiles(directory=str(frontend_dist / "images")),
            name="frontend-images"
        )

    # Serve manifest.json
    @app.get("/manifest.json")
    async def get_manifest():
        from fastapi.responses import FileResponse
        manifest_path = frontend_dist / "manifest.json"
        if manifest_path.exists():
            return FileResponse(manifest_path, media_type="application/manifest+json")
        return {"error": "manifest not found"}

    # Serve service worker (with no-cache to ensure updates propagate)
    @app.get("/sw.js")
    async def get_service_worker():
        from fastapi.responses import FileResponse
        sw_path = frontend_dist / "sw.js"
        if sw_path.exists():
            return FileResponse(
                sw_path,
                media_type="application/javascript",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        return {"error": "service worker not found"}

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
            except Exception:
                pass  # Already closed or disconnected


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
        except Exception:
            pass  # Already closed or disconnected


# ============================================================
# ROOT & DIAGNOSTICS
# ============================================================

@router.get("/")
def root():
    """Serve frontend index if built; fallback to API JSON."""
    frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    index_path = frontend_dist / "index.html"

    if index_path.exists():
        # Add no-cache headers to ensure users always get latest version
        return FileResponse(
            str(index_path),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    
    logger.warning(f"Frontend index not found at {index_path}. Serving API status.")
    return {
        "message": "Lore Management System API",
        "version": "1.0.0",
        "status": "operational"
    }


@router.get("/api/version")
def get_app_version():
    """Return current app version for frontend update checking."""
    version_file = Path(__file__).parent.parent.parent.parent / "data" / "deployed_version.txt"
    try:
        if version_file.exists():
            version = version_file.read_text().strip()
            return {"version": version, "status": "ok"}
    except Exception as e:
        logger.error(f"Failed to read version: {e}")
    return {"version": "unknown", "status": "error"}


@router.get("/health")
async def health_check(request: Request):
    # Read version from file
    version_file = Path("data/deployed_version.txt")
    version = "unknown"
    if version_file.exists():
        try:
            version = version_file.read_text().strip()
        except Exception:
            version = "error_reading_version"
    
    out = {
        "status": "healthy",
        "version": version,
        "deployed_at": version,  # For backwards compatibility
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

    # Arc Engine check
    try:
        from src.mantle.agents.dm_agent import ARC_ENGINE_ENABLED, ARC_ENGINE_AVAILABLE, ARC_ENGINE_IMPORT_ERROR
        
        if not ARC_ENGINE_ENABLED:
            out["checks"]["arc_engine"] = "disabled"
        elif ARC_ENGINE_AVAILABLE:
            out["checks"]["arc_engine"] = "available"
        else:
            out["checks"]["arc_engine"] = "error"
        
        out["features"]["arc_engine_enabled"] = ARC_ENGINE_ENABLED and ARC_ENGINE_AVAILABLE
    except Exception as e:
        out["checks"]["arc_engine"] = f"check_failed: {str(e)[:50]}"
        out["features"]["arc_engine_enabled"] = False

    return out


@router.get("/debug/status")
async def debug_status(request: Request):
    try:
        neo4j_ok = request.app.state.neo4j_db.test_connection()
    except Exception:
        neo4j_ok = False

    return {
        "environment": os.getenv("APP_ENV", "development"),
        "ai_enabled": getattr(request.app.state, "ai_enabled", False),
        "gemini_key_present": bool(os.getenv("GEMINI_API_KEY")),
        "neo4j_connected": neo4j_ok,
    }


# ============================================================
# ARC ENGINE DIAGNOSTIC ENDPOINTS
# ============================================================

@router.get("/arc/status")
async def get_arc_status():
    """
    Get Arc Engine status and diagnostic information.
    
    Returns detailed information about whether the Arc Engine is:
    - Enabled via configuration
    - Successfully imported
    - Available for use
    - Any import errors encountered
    """
    from src.mantle.agents.dm_agent import (
        ARC_ENGINE_ENABLED,
        ARC_ENGINE_AVAILABLE,
        ARC_ENGINE_IMPORT_ERROR
    )
    
    response = {
        "enabled": ARC_ENGINE_ENABLED,
        "available": ARC_ENGINE_AVAILABLE,
        "import_error": ARC_ENGINE_IMPORT_ERROR,
        "dependencies_checked": {}
    }
    
    # Determine reason
    if not ARC_ENGINE_ENABLED:
        response["reason"] = "Disabled via config (ENABLE_ARC_ENGINE=false)"
    elif ARC_ENGINE_AVAILABLE:
        response["reason"] = "Import successful"
    else:
        if ARC_ENGINE_IMPORT_ERROR:
            response["reason"] = f"Import failed: {ARC_ENGINE_IMPORT_ERROR}"
        else:
            response["reason"] = "Import failed: Unknown error"
    
    # Check dependencies
    try:
        import pydantic
        response["dependencies_checked"]["pydantic"] = pydantic.__version__
    except ImportError:
        response["dependencies_checked"]["pydantic"] = "missing"
    
    try:
        import src.mantle.arc.models
        response["dependencies_checked"]["src.lms.arc.models"] = "available"
    except ImportError as e:
        response["dependencies_checked"]["src.lms.arc.models"] = f"missing: {str(e)}"
    
    return response


@router.get("/arc/session/{session_id}")
async def get_arc_session_status(session_id: str):
    """
    Get Arc Engine state for a specific game session.
    
    Returns detailed information about the narrative arc state including:
    - Current phase (e.g., CALL_TO_ADVENTURE)
    - Current act (DEPARTURE/INITIATION/RETURN)
    - Tension level and value
    - Journey progress
    - Episode information
    - Phase and tension guidance
    """
    from src.mantle.agents.dm_agent import ARC_ENGINE_AVAILABLE, ARC_ENGINE_ENABLED
    
    if not ARC_ENGINE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Arc Engine is disabled via configuration (ENABLE_ARC_ENGINE=false)"
        )
    
    if not ARC_ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Arc Engine is not available (import failed)"
        )
    
    # Try to get session from game_routes
    try:
        from src.mantle.api.game_routes import _active_sessions
        
        if session_id not in _active_sessions:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        session_data = _active_sessions[session_id]
        arc_engine = session_data.get("arc_engine")
        
        if not arc_engine:
            return {
                "session_id": session_id,
                "arc_engine_state": "not_initialized",
                "message": "Arc Engine not initialized for this session"
            }
        
        # Get arc state
        try:
            response = {
                "session_id": session_id,
                "current_phase": arc_engine.current_phase.value if hasattr(arc_engine, 'current_phase') else "unknown",
                "current_act": arc_engine.current_act.value if hasattr(arc_engine, 'current_act') else "unknown",
                "tension_level": arc_engine.tension_level.value if hasattr(arc_engine, 'tension_level') else "unknown",
                "tension_value": float(arc_engine.current_tension) if hasattr(arc_engine, 'current_tension') else 0.0,
                "journey_progress": float(arc_engine.journey_progress) if hasattr(arc_engine, 'journey_progress') else 0.0,
                "episode_number": arc_engine.episode_number if hasattr(arc_engine, 'episode_number') else 1,
            }
            
            # Try to get status dict if available
            if hasattr(arc_engine, 'get_status'):
                status = arc_engine.get_status()
                if status:
                    response.update(status)
            
            # Add guidance based on phase
            phase_guidance = {
                "ORDINARY_WORLD": "Establish the hero's normal life and comfort zone",
                "CALL_TO_ADVENTURE": "Present the challenge or quest that disrupts normalcy",
                "REFUSAL_OF_CALL": "Show hesitation and the stakes of refusing",
                "MEETING_MENTOR": "Introduce guidance, wisdom, or magical aid",
                "CROSSING_THRESHOLD": "Hero commits to the journey and enters the unknown",
                "TESTS_ALLIES_ENEMIES": "Face challenges, make friends and enemies",
                "APPROACH_INNERMOST_CAVE": "Prepare for the major challenge ahead",
                "ORDEAL": "Face the greatest fear or challenge",
                "REWARD": "Gain the treasure, knowledge, or victory",
                "ROAD_BACK": "Begin the return journey with new challenges",
                "RESURRECTION": "Face final test using all lessons learned",
                "RETURN_WITH_ELIXIR": "Return home transformed with gifts for others"
            }
            
            response["phase_guidance"] = phase_guidance.get(
                response["current_phase"],
                "Unknown phase"
            )
            
            # Add tension guidance
            tension_level = response["tension_level"]
            tension_guidance = {
                "CALM": "Peaceful moment, good for character development and world building",
                "BUILDING": "Tension is rising, introduce complications or foreshadowing",
                "HIGH": "Action and conflict should be prominent, stakes are clear",
                "CLIMACTIC": "Peak moment of confrontation or revelation",
                "RELEASE": "Resolution phase, consequences play out, breathing room"
            }
            
            response["tension_guidance"] = tension_guidance.get(
                tension_level,
                "Monitor and adjust tension as needed"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting arc state: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error reading arc state: {str(e)}"
            )
    
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Game routes module not available"
        )


# ============================================================
# ENTITY ENDPOINTS
# ============================================================

def _slugify_name(name: str, max_length: int = 20) -> str:
    """Convert name to URL-friendly slug for human-readable IDs."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_length] or "unnamed"


@router.post("/entities", response_model=EntityResponse, status_code=201)
async def create_entity(entity_data: EntityCreate, db: Neo4jDatabase = Depends(get_neo4j_db)):
    # Human-readable ID: {type}-{name_slug}-{short_random}
    # e.g., "character-lord-aldric-7f3a"
    type_slug = entity_data.entity_type.value.lower()
    name_slug = _slugify_name(entity_data.canonical_name)
    short_id = uuid.uuid4().hex[:4]
    canon_id = f"{type_slug}-{name_slug}-{short_id}"
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


# ============================================================
# ENTITY MANAGEMENT ENDPOINTS
# ============================================================

from difflib import SequenceMatcher

def calculate_name_similarity(name1: str, name2: str) -> float:
    """Calculate string similarity ratio between two names."""
    return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()


@router.get("/entities/manage")
async def get_entities_for_management(
    db: Neo4jDatabase = Depends(get_neo4j_db),
    world_id: Optional[str] = Query(default=None, description="Filter by world/lore base ID"),
    entity_type: Optional[EntityType] = Query(default=None, description="Filter by entity type"),
    confidence_level: Optional[ConfidenceLevel] = Query(default=None, description="Filter by confidence level"),
    search: Optional[str] = Query(default=None, description="Search by name or alias"),
):
    """
    Get all entities for the management view.
    Returns entities sorted by confidence level (least to most confident).
    Confidence order: UNCERTAIN → SPECULATIVE → PROBABLE → AI_GENERATED → CONFIRMED
    """
    # Validate database connection
    if db is None:
        logger.error("Database connection is None when fetching entities for management")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    try:
        logger.info(f"Fetching entities for management - world_id: {world_id}, type: {entity_type}, confidence: {confidence_level}, search: {search}")
        
        query = "MATCH (n:Entity)"
        where = []
        params = {}

        if world_id:
            where.append("n.world_id = $world_id")
            params["world_id"] = world_id

        if entity_type:
            where.append("n.entity_type = $type")
            params["type"] = entity_type.value

        if confidence_level:
            where.append("n.confidence_level = $confidence")
            params["confidence"] = confidence_level.value

        if search:
            where.append("(toLower(n.canonical_name) CONTAINS toLower($search) OR any(alias IN n.aliases WHERE toLower(alias) CONTAINS toLower($search)))")
            params["search"] = search

        if where:
            query += " WHERE " + " AND ".join(where)

        # Custom ORDER BY to sort by confidence level (least to most confident)
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
               properties(n) AS all_props,
               size((n)-[]->()) + size((n)<-[]-()) AS relationship_count
        ORDER BY 
            CASE n.confidence_level
                WHEN 'UNCERTAIN' THEN 1
                WHEN 'SPECULATIVE' THEN 2
                WHEN 'PROBABLE' THEN 3
                WHEN 'AI_GENERATED' THEN 4
                WHEN 'CONFIRMED' THEN 5
                ELSE 0
            END ASC,
            n.canonical_name ASC
        """

        rows = await db.execute(query, params)

        reserved = {
            "canon_id", "entity_type", "canonical_name", "aliases",
            "approval_status", "confidence_level", "party_knowledge",
            "created_at", "updated_at", "name", "embedding",
        }

        # Handle date parsing - may be ISO string or Neo4j datetime
        def parse_date(val):
            if val is None:
                return datetime.now(timezone.utc)
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace('Z', '+00:00'))
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val / 1000, tz=timezone.utc)
            return datetime.now(timezone.utc)

        out = []
        for row in rows:
            all_props = row["all_props"]
            approved_fields = {}

            for k, v in all_props.items():
                if k not in reserved:
                    try:
                        approved_fields[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        approved_fields[k] = v

            entity_dict = {
                "canon_id": row["canon_id"],
                "entity_type": row["entity_type"],
                "canonical_name": row["canonical_name"] or "Unknown",
                "aliases": row["aliases"] or [],
                "approved_fields": approved_fields,
                "approval_status": row["approval_status"],
                "confidence_level": row["confidence_level"],
                "party_knowledge": row.get("party_knowledge") or "KNOWN",
                "created_at": parse_date(row.get("created_at")),
                "updated_at": parse_date(row.get("updated_at")),
                "relationship_count": row.get("relationship_count", 0)
            }
            out.append(entity_dict)

        logger.info(f"Successfully fetched {len(out)} entities for management")
        return out
        
    except Exception as e:
        logger.error(f"Failed to get entities for management: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entities: {str(e)}"
        )


@router.get("/entities/duplicates")
async def find_duplicate_entities(
    db: Neo4jDatabase = Depends(get_neo4j_db),
    world_id: Optional[str] = Query(default=None, description="Filter by world/lore base ID"),
    similarity_threshold: float = Query(default=0.8, ge=0.0, le=1.0, description="Similarity threshold (0.0 to 1.0)"),
):
    """
    Find potential duplicate entities based on name similarity, type, and aliases.
    Returns groups of entities that might be duplicates.
    """
    # Get all entities
    query = "MATCH (n:Entity)"
    params = {}
    
    if world_id:
        query += " WHERE n.world_id = $world_id"
        params["world_id"] = world_id
    
    query += """
    RETURN n.canon_id AS canon_id,
           n.entity_type AS entity_type,
           COALESCE(n.canonical_name, n.name) AS canonical_name,
           COALESCE(n.aliases, []) AS aliases,
           n.confidence_level AS confidence_level
    """
    
    rows = await db.execute(query, params)
    
    # Group entities by type first
    entities_by_type = {}
    for row in rows:
        entity_type = row["entity_type"]
        if entity_type not in entities_by_type:
            entities_by_type[entity_type] = []
        entities_by_type[entity_type].append({
            "canon_id": row["canon_id"],
            "entity_type": entity_type,
            "canonical_name": row["canonical_name"],
            "aliases": row["aliases"] or [],
            "confidence_level": row.get("confidence_level", "AI_GENERATED")
        })
    
    # Find duplicates within each type
    duplicate_groups = []
    
    for entity_type, entities in entities_by_type.items():
        seen = set()
        
        for i, entity1 in enumerate(entities):
            if entity1["canon_id"] in seen:
                continue
                
            potential_duplicates = [entity1]
            seen.add(entity1["canon_id"])
            
            for j, entity2 in enumerate(entities):
                if i >= j or entity2["canon_id"] in seen:
                    continue
                
                # Calculate name similarity
                name_similarity = calculate_name_similarity(
                    entity1["canonical_name"],
                    entity2["canonical_name"]
                )
                
                # Check for overlapping aliases
                aliases1 = set([a.lower() for a in entity1["aliases"]])
                aliases2 = set([a.lower() for a in entity2["aliases"]])
                alias_overlap = len(aliases1 & aliases2) > 0
                
                # Consider them duplicates if name similarity is high or they share aliases
                if name_similarity >= similarity_threshold or alias_overlap:
                    potential_duplicates.append(entity2)
                    seen.add(entity2["canon_id"])
            
            # Only add groups with 2+ entities
            if len(potential_duplicates) >= 2:
                # Calculate similarity scores for the group
                group_with_scores = []
                for entity in potential_duplicates:
                    max_similarity = max(
                        calculate_name_similarity(entity["canonical_name"], other["canonical_name"])
                        for other in potential_duplicates if other["canon_id"] != entity["canon_id"]
                    )
                    group_with_scores.append({
                        **entity,
                        "similarity_score": round(max_similarity, 2)
                    })
                
                duplicate_groups.append({
                    "entity_type": entity_type,
                    "entities": group_with_scores
                })
    
    return {
        "duplicate_groups": duplicate_groups,
        "total_groups": len(duplicate_groups)
    }


class EntityMergeRequest(BaseModel):
    """Request model for merging entities."""
    entity_ids: List[str] = Field(min_length=2, description="List of entity IDs to merge (minimum 2)")
    target_canonical_name: str = Field(min_length=1, description="Canonical name for merged entity")
    target_aliases: List[str] = Field(default_factory=list, description="Aliases for merged entity")
    target_confidence_level: ConfidenceLevel = Field(description="Confidence level for merged entity")


@router.post("/entities/merge")
async def merge_entities(
    merge_request: EntityMergeRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Merge multiple entities into one.
    - Combines all properties intelligently
    - Preserves all source references
    - Updates relationships to point to the merged entity
    - Keeps the highest confidence level
    - Maintains audit trail
    """
    if len(merge_request.entity_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 entities required for merge")
    
    # Fetch all entities to merge
    query = """
    MATCH (n:Entity)
    WHERE n.canon_id IN $entity_ids
    RETURN n.canon_id AS canon_id,
           n.entity_type AS entity_type,
           n.canonical_name AS canonical_name,
           n.aliases AS aliases,
           n.confidence_level AS confidence_level,
           n.approval_status AS approval_status,
           n.party_knowledge AS party_knowledge,
           properties(n) AS all_props
    """
    
    entities = await db.execute(query, {"entity_ids": merge_request.entity_ids})
    
    if len(entities) != len(merge_request.entity_ids):
        raise HTTPException(status_code=404, detail="Some entities not found")
    
    # Ensure all entities are the same type
    entity_types = set(e["entity_type"] for e in entities)
    if len(entity_types) > 1:
        raise HTTPException(status_code=400, detail=f"Cannot merge entities of different types: {entity_types}")
    
    entity_type = entities[0]["entity_type"]
    
    # Determine the target entity (use the first one or create new ID)
    target_canon_id = entities[0]["canon_id"]
    
    # Combine aliases from all entities
    combined_aliases = set(merge_request.target_aliases)
    for entity in entities:
        combined_aliases.update(entity.get("aliases") or [])
        # Add canonical names as aliases (except the target name)
        if entity["canonical_name"] and entity["canonical_name"] != merge_request.target_canonical_name:
            combined_aliases.add(entity["canonical_name"])
    
    # Remove target canonical name from aliases
    combined_aliases.discard(merge_request.target_canonical_name)
    
    # Merge approved_fields
    reserved = {
        "canon_id", "entity_type", "canonical_name", "aliases",
        "approval_status", "confidence_level", "party_knowledge",
        "created_at", "updated_at", "name", "embedding",
    }
    
    merged_fields = {}
    for entity in entities:
        all_props = entity["all_props"]
        for k, v in all_props.items():
            if k not in reserved and v is not None:
                # If key exists, prefer non-empty values
                if k not in merged_fields or (not merged_fields[k] and v):
                    merged_fields[k] = v
    
    # Update the target entity
    update_query = """
    MATCH (target:Entity {canon_id: $target_id})
    SET target.canonical_name = $canonical_name,
        target.aliases = $aliases,
        target.confidence_level = $confidence_level,
        target.updated_at = datetime().epochMillis
    """
    
    # Add merged fields to the update
    for key, value in merged_fields.items():
        update_query += f"\nSET target.{key} = ${key}"
    
    update_params = {
        "target_id": target_canon_id,
        "canonical_name": merge_request.target_canonical_name,
        "aliases": list(combined_aliases),
        "confidence_level": merge_request.target_confidence_level.value,
        **merged_fields
    }
    
    await db.execute(update_query, update_params)
    
    # Redirect all relationships from source entities to target
    source_ids = [e["canon_id"] for e in entities if e["canon_id"] != target_canon_id]
    
    if source_ids:
        # Redirect outgoing relationships
        redirect_out_query = """
        MATCH (source:Entity)-[r]->(other)
        WHERE source.canon_id IN $source_ids
        WITH source, r, other, type(r) AS rel_type, properties(r) AS rel_props
        MATCH (target:Entity {canon_id: $target_id})
        WHERE NOT (target)-[]->(other)  // Avoid duplicate relationships
        CREATE (target)-[new_r:RELATED_TO]->(other)
        SET new_r = rel_props
        DELETE r
        """
        
        await db.execute(redirect_out_query, {
            "source_ids": source_ids,
            "target_id": target_canon_id
        })
        
        # Redirect incoming relationships
        redirect_in_query = """
        MATCH (other)-[r]->(source:Entity)
        WHERE source.canon_id IN $source_ids
        WITH source, r, other, type(r) AS rel_type, properties(r) AS rel_props
        MATCH (target:Entity {canon_id: $target_id})
        WHERE NOT (other)-[]->(target)  // Avoid duplicate relationships
        CREATE (other)-[new_r:RELATED_TO]->(target)
        SET new_r = rel_props
        DELETE r
        """
        
        await db.execute(redirect_in_query, {
            "source_ids": source_ids,
            "target_id": target_canon_id
        })
        
        # Delete source entities
        delete_query = """
        MATCH (n:Entity)
        WHERE n.canon_id IN $source_ids
        DELETE n
        """
        
        await db.execute(delete_query, {"source_ids": source_ids})
    
    await AuditLogger.log(
        f"Merged entities {merge_request.entity_ids} into {target_canon_id}",
        level=logging.INFO
    )
    
    # Return the merged entity
    return await get_entity(target_canon_id, db=db)


class EntityBulkDeleteRequest(BaseModel):
    """Request model for bulk entity deletion."""
    entity_ids: List[str] = Field(min_length=1, description="List of entity IDs to delete")
    delete_orphaned_relationships: bool = Field(default=True, description="Whether to delete orphaned relationships")


@router.delete("/entities/bulk")
async def bulk_delete_entities(
    delete_request: EntityBulkDeleteRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Bulk delete entities.
    - Deletes multiple entities at once
    - Optionally deletes orphaned relationships
    - Returns count of deleted entities
    """
    if not delete_request.entity_ids:
        raise HTTPException(status_code=400, detail="No entity IDs provided")
    
    # Check if entities exist and get relationship counts
    check_query = """
    MATCH (n:Entity)
    WHERE n.canon_id IN $entity_ids
    RETURN n.canon_id AS canon_id,
           n.canonical_name AS canonical_name,
           size((n)-[]->()) + size((n)<-[]-()) AS relationship_count
    """
    
    entities = await db.execute(check_query, {"entity_ids": delete_request.entity_ids})
    
    if not entities:
        raise HTTPException(status_code=404, detail="No entities found with provided IDs")
    
    # Count entities before deletion
    entities_to_delete = len(entities)
    
    # Delete relationships first
    if delete_request.delete_orphaned_relationships:
        delete_rels_query = """
        MATCH (n:Entity)-[r]-()
        WHERE n.canon_id IN $entity_ids
        DELETE r
        """
        await db.execute(delete_rels_query, {"entity_ids": delete_request.entity_ids})
    
    # Delete entities
    delete_query = """
    MATCH (n:Entity)
    WHERE n.canon_id IN $entity_ids
    DELETE n
    """
    
    await db.execute(delete_query, {"entity_ids": delete_request.entity_ids})
    
    await AuditLogger.log(
        f"Bulk deleted {entities_to_delete} entities: {delete_request.entity_ids}",
        level=logging.INFO
    )
    
    return {
        "deleted_count": entities_to_delete,
        "entity_ids": delete_request.entity_ids,
        "entities": [{"canon_id": e["canon_id"], "canonical_name": e["canonical_name"], "relationship_count": e.get("relationship_count", 0)} for e in entities]
    }


@router.patch("/entities/{canon_id}")
async def update_entity_patch(
    canon_id: str,
    updates: Dict[str, Any] = Body(...),
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Update specific properties of an entity.
    Allows partial updates to entity fields.
    """
    # First check if entity exists
    check_query = "MATCH (n:Entity {canon_id: $canon_id}) RETURN n.canon_id AS canon_id"
    result = await db.execute(check_query, {"canon_id": canon_id})
    
    if not result:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Build update query
    allowed_fields = {
        "canonical_name", "aliases", "confidence_level", "approval_status",
        "party_knowledge", "approved_fields", "description", "entity_type",
        "openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"
    }
    
    set_clauses = ["n.updated_at = datetime().epochMillis"]
    params = {"canon_id": canon_id}
    
    for key, value in updates.items():
        if key in allowed_fields:
            if key == "approved_fields" and isinstance(value, dict):
                # Handle approved_fields specially - merge with existing
                for field_key, field_value in value.items():
                    if not field_key.startswith("_"):  # Skip internal fields
                        set_clauses.append(f"n.{field_key} = ${field_key}")
                        params[field_key] = json.dumps(field_value) if isinstance(field_value, (dict, list)) else field_value
            else:
                set_clauses.append(f"n.{key} = ${key}")
                params[key] = value
    
    if len(set_clauses) == 1:  # Only the updated_at clause
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    update_query = f"""
    MATCH (n:Entity {{canon_id: $canon_id}})
    SET {', '.join(set_clauses)}
    RETURN n
    """
    
    await db.execute(update_query, params)
    
    await AuditLogger.log(
        f"Updated entity {canon_id} with fields: {list(updates.keys())}",
        level=logging.INFO
    )
    
    # Return updated entity
    return await get_entity(canon_id, db=db)


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
            except (json.JSONDecodeError, TypeError, ValueError):
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
    limit: int = Query(default=100, le=10000, description="Max entities to return (up to 10000)"),
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
                except (json.JSONDecodeError, TypeError, ValueError):
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
    from src.mantle.agents.lore_parsing_agent import LoreParsingAgent

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured (GEMINI_API_KEY missing)"
        )

    try:
        await AuditLogger.log(f"Text ingestion started: {len(ingest_req.content)} chars from source '{ingest_req.source_name}'")
        
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

        await AuditLogger.log(
            f"Text ingestion completed: {result.entities_stored} entities, "
            f"{result.relationships_stored} relationships stored"
        )

        return IngestTextResponse(
            status="success",
            source_name=source_name,
            nodes_created=result.entities_stored,
            relationships_created=result.relationships_stored,
            entities=entities,
            relationships=relationships,
        )

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse AI response as JSON: {str(e)}"
        await AuditLogger.log(f"Ingestion JSON error: {error_msg}", level=logging.ERROR)
        logger.error(f"JSON parsing error in ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "json_parse_error",
                "message": "The AI returned an improperly formatted response. Please try again.",
                "details": error_msg,
                "step_failed": "parsing"
            }
        )
    except ValueError as e:
        # Validation errors
        error_msg = f"Data validation failed: {str(e)}"
        await AuditLogger.log(f"Ingestion validation error: {error_msg}", level=logging.ERROR)
        logger.error(f"Validation error in ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_type": "validation_error",
                "message": "The extracted data failed validation checks.",
                "details": error_msg,
                "step_failed": "validation"
            }
        )
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        await AuditLogger.log(f"Text ingestion failed: {error_type}: {error_msg}", level=logging.ERROR)
        logger.error(f"Text ingestion failed: {e}", exc_info=True)
        
        # Check for database errors
        if "neo4j" in error_msg.lower() or "database" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_type": "neo4j_error",
                    "message": "Failed to save data to the database. Please try again.",
                    "details": f"{error_type}: {error_msg}",
                    "step_failed": "storage"
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_type": "unknown_error",
                    "message": f"Ingestion failed: {error_msg}",
                    "details": f"{error_type}: {error_msg}",
                    "step_failed": "extraction"
                }
            )


class PreviewResponse(BaseModel):
    """Response for preview extraction (no storage)."""
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    summary: Dict[str, int]


@router.post("/ingest/preview", response_model=PreviewResponse)
async def preview_extraction(
    request: Request,
    ingest_req: IngestTextRequest,
):
    """
    Preview entity extraction WITHOUT storing to database.

    This allows users to review what will be extracted before committing.
    Returns extracted entities, relationships, and a summary.
    """
    from src.mantle.agents.lore_parsing_agent import LoreParsingAgent

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured (GEMINI_API_KEY missing)"
        )

    try:
        await AuditLogger.log(f"Preview extraction started: {len(ingest_req.content)} chars")
        
        agent = LoreParsingAgent(api_key=gemini_key)

        # Parse WITHOUT storing - just extract
        result = await agent.parse_lore(ingest_req.content)

        # Format entities for preview
        entities = []
        type_counts = {}
        for entity in result.entities:
            entity_type = entity.entity_type
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

            # Generate OCEAN profile for characters
            ocean = None
            if entity_type == "Character" and entity.traits:
                ocean = agent._calculate_ocean_from_traits(entity.traits)

            entities.append({
                "name": entity.name,
                "type": entity_type,
                "description": entity.description,
                "traits": entity.traits,
                "aliases": entity.aliases if entity.aliases else [],
                "tags": entity.tags,
                "temporal_cues": entity.temporal_cues if entity.temporal_cues else [],
                "verbatim_text": entity.verbatim_text,
                "ocean": ocean,
            })

        # Format relationships for preview
        relationships = []
        for rel in result.relationships:
            relationships.append({
                "source": rel.source,
                "target": rel.target,
                "type": rel.relationship_type,
                "description": rel.description,
            })

        await AuditLogger.log(f"Preview extraction completed: {len(entities)} entities, {len(relationships)} relationships")

        return PreviewResponse(
            entities=entities,
            relationships=relationships,
            summary={
                "total_entities": len(entities),
                "total_relationships": len(relationships),
                **type_counts,
            }
        )

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse AI response as JSON: {str(e)}"
        await AuditLogger.log(f"Preview JSON error: {error_msg}", level=logging.ERROR)
        logger.error(f"JSON parsing error in preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "json_parse_error",
                "message": "The AI returned an improperly formatted response. Please try again.",
                "details": error_msg,
                "step_failed": "parsing"
            }
        )
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        await AuditLogger.log(f"Preview extraction failed: {error_type}: {error_msg}", level=logging.ERROR)
        logger.error(f"Preview extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "extraction_error",
                "message": f"Preview failed: {error_msg}",
                "details": f"{error_type}: {error_msg}",
                "step_failed": "extraction"
            }
        )


class CommitEntitiesRequest(BaseModel):
    """Request to commit approved entities."""
    source_name: str
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]


@router.post("/ingest/commit")
async def commit_entities(
    request: Request,
    commit_req: CommitEntitiesRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Commit previously previewed entities to the database.

    Takes the approved entities from preview and stores them.
    """
    from src.mantle.agents.lore_parsing_agent import LoreParsingAgent

    gemini_key = os.getenv("GEMINI_API_KEY")
    agent = LoreParsingAgent(api_key=gemini_key) if gemini_key else None

    try:
        entities_stored = 0
        relationships_stored = 0

        for entity_data in commit_req.entities:
            # Generate human-readable ID
            from src.mantle.agents.lore_parsing_agent import _generate_human_readable_id
            canon_id = _generate_human_readable_id(
                entity_data["name"],
                entity_data["type"],
                commit_req.source_name
            )

            # Build OCEAN properties if present
            ocean_props = {}
            if entity_data.get("ocean"):
                ocean = entity_data["ocean"]
                ocean_props = {
                    "openness": ocean.get("openness", 0.5),
                    "conscientiousness": ocean.get("conscientiousness", 0.5),
                    "extraversion": ocean.get("extraversion", 0.5),
                    "agreeableness": ocean.get("agreeableness", 0.5),
                    "neuroticism": ocean.get("neuroticism", 0.5),
                }

            # Store entity in Neo4j
            await db.execute(
                f"""
                MERGE (e:{entity_data['type']} {{canon_id: $canon_id}})
                SET e.name = $name,
                    e.description = $description,
                    e.traits = $traits,
                    e.tags = $tags,
                    e.source = $source,
                    e.world_id = $world_id,
                    e.confidence = 'USER_APPROVED',
                    e.created_at = datetime(),
                    e += $ocean_props
                """,
                {
                    "canon_id": canon_id,
                    "name": entity_data["name"],
                    "description": entity_data.get("description", ""),
                    "traits": entity_data.get("traits", []),
                    "tags": entity_data.get("tags", []),
                    "source": commit_req.source_name,
                    "world_id": commit_req.source_name,
                    "ocean_props": ocean_props,
                }
            )
            entities_stored += 1

        # Store relationships
        for rel in commit_req.relationships:
            await db.execute(
                f"""
                MATCH (a {{name: $source}})
                MATCH (b {{name: $target}})
                MERGE (a)-[r:{rel['type']}]->(b)
                SET r.description = $description,
                    r.source = $rel_source,
                    r.created_at = datetime()
                """,
                {
                    "source": rel["source"],
                    "target": rel["target"],
                    "description": rel.get("description", ""),
                    "rel_source": commit_req.source_name,
                }
            )
            relationships_stored += 1

        return {
            "status": "success",
            "entities_stored": entities_stored,
            "relationships_stored": relationships_stored,
            "source_name": commit_req.source_name,
        }

    except Exception as e:
        logger.error(f"Entity commit failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Commit failed: {str(e)}"
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
# ANNOUNCEMENTS SYSTEM
# ============================================================

# In-memory announcement storage (persists until server restart)
# For production, you'd want to store this in a file or database
_current_announcement = {
    "id": "update-2026-01-02",
    "type": "success",  # info, warning, success, maintenance
    "icon": "🎉",
    "message": """<strong>Character Creation Overhaul!</strong> The new 5e-style character creation is now live. Pick your race, class, and abilities step-by-step — no more wrong equipment!
<br><br>
<strong>What's New:</strong>
<ul style="margin: 8px 0 0 20px; padding: 0; text-align: left;">
<li><strong>Standard Creation Mode</strong> — Choose race, class, assign abilities, pick skills</li>
<li><strong>All 12 D&D Classes</strong> — Barbarian, Bard, Druid, Monk, Paladin, Ranger, Sorcerer, Warlock added</li>
<li><strong>Starting Equipment Preview</strong> — See exactly what gear you'll get before starting</li>
<li><strong>Proper Ability Scores</strong> — Standard array (15,14,13,12,10,8) with auto-assign option</li>
</ul>""",
    "dismissible": True,
    "persistent": False,
    "active": True
}


@app.get("/api/announcement")
async def get_announcement():
    """Get current announcement for display in the app."""
    if not _current_announcement or not _current_announcement.get("active"):
        return {"announcement": None}
    return {"announcement": _current_announcement}


class AnnouncementUpdate(BaseModel):
    id: str
    type: str = "info"  # info, warning, success, maintenance
    icon: str = "📢"
    message: str
    dismissible: bool = True
    persistent: bool = False
    active: bool = True


@app.post("/api/announcement")
async def set_announcement(announcement: AnnouncementUpdate, pin: str = Query(...)):
    """Set or update the current announcement (requires admin PIN)."""
    global _current_announcement

    # Verify admin PIN
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Invalid admin PIN")

    _current_announcement = announcement.model_dump()
    logger.info(f"Announcement updated: {announcement.id}")
    return {"status": "success", "announcement": _current_announcement}


@app.delete("/api/announcement")
async def clear_announcement(pin: str = Query(...)):
    """Clear the current announcement (requires admin PIN)."""
    global _current_announcement

    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Invalid admin PIN")

    _current_announcement = None
    logger.info("Announcement cleared")
    return {"status": "success", "message": "Announcement cleared"}


# ============================================================
# LORE FILE MANAGER ENDPOINTS
# ============================================================

# Storage directory for lore uploads
LORE_UPLOADS_DIR = Path("data/lore_uploads")
LORE_METADATA_FILE = LORE_UPLOADS_DIR / "metadata.json"


def _ensure_lore_dir():
    """Ensure lore uploads directory exists."""
    LORE_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not LORE_METADATA_FILE.exists():
        LORE_METADATA_FILE.write_text("[]", encoding="utf-8")


def _load_lore_metadata() -> List[Dict[str, Any]]:
    """Load lore file metadata."""
    _ensure_lore_dir()
    try:
        return json.loads(LORE_METADATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_lore_metadata(metadata: List[Dict[str, Any]]):
    """Save lore file metadata."""
    _ensure_lore_dir()
    LORE_METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


class LoreFileResponse(BaseModel):
    """Response for a lore file."""
    id: str
    filename: str
    size: int
    uploaded_at: str
    status: str  # pending, imported, failed
    import_result: Optional[Dict[str, Any]] = None

    @property
    def name(self) -> str:
        """Alias for filename (frontend compatibility)."""
        return self.filename

    def model_dump(self, **kwargs):
        """Include 'name' alias in serialization."""
        data = super().model_dump(**kwargs)
        data["name"] = self.filename
        return data


@app.post("/admin/lore/upload")
async def upload_lore_files(
    files: List[UploadFile] = File(...),
):
    """
    Upload lore files to the staging area.

    Supported formats: .txt, .md, .json, .pdf
    Files are stored for later review and import.
    """
    _ensure_lore_dir()
    uploaded = []
    metadata = _load_lore_metadata()

    allowed_extensions = {".txt", ".md", ".json", ".pdf"}

    for file in files:
        # Check file extension
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed_extensions:
            logger.warning(f"Rejected file with extension {ext}: {file.filename}")
            continue

        # Generate unique ID
        file_id = f"lore-{uuid.uuid4().hex[:8]}"

        # Save file
        try:
            content = await file.read()
            file_path = LORE_UPLOADS_DIR / f"{file_id}{ext}"
            await run_in_threadpool(file_path.write_bytes, content)

            # Add metadata entry
            file_meta = {
                "id": file_id,
                "filename": file.filename,
                "stored_as": f"{file_id}{ext}",
                "size": len(content),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
                "import_result": None,
            }
            metadata.append(file_meta)
            uploaded.append(file_meta)

            logger.info(f"Lore file uploaded: {file.filename} as {file_id}")

        except Exception as e:
            logger.error(f"Failed to save lore file {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save {file.filename}")

    # Save updated metadata
    _save_lore_metadata(metadata)

    return {
        "status": "success",
        "files_uploaded": len(uploaded),
        "files": uploaded
    }


@app.get("/admin/lore/files")
async def list_lore_files():
    """List all uploaded lore files."""
    metadata = _load_lore_metadata()
    return {"files": [LoreFileResponse(**m).model_dump() for m in metadata]}


@app.get("/admin/lore/files/{file_id}")
async def get_lore_file(file_id: str):
    """Get contents of a lore file."""
    metadata = _load_lore_metadata()

    file_meta = next((m for m in metadata if m["id"] == file_id), None)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = LORE_UPLOADS_DIR / file_meta["stored_as"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File data not found")

    # Read file content
    try:
        if file_path.suffix == ".pdf":
            # For PDF, return info that it needs special handling
            return {
                "id": file_id,
                "filename": file_meta["filename"],
                "name": file_meta["filename"],  # Alias for frontend compatibility
                "type": "pdf",
                "content": "[PDF files cannot be displayed as text. Use import to process.]",
                "size": file_meta["size"],
            }
        else:
            content = file_path.read_text(encoding="utf-8")
            return {
                "id": file_id,
                "filename": file_meta["filename"],
                "name": file_meta["filename"],  # Alias for frontend compatibility
                "type": file_path.suffix[1:],  # Remove leading dot
                "content": content,
                "size": file_meta["size"],
            }
    except UnicodeDecodeError:
        return {
            "id": file_id,
            "filename": file_meta["filename"],
            "name": file_meta["filename"],  # Alias for frontend compatibility
            "type": file_path.suffix[1:],
            "content": "[Binary file - cannot display as text]",
            "size": file_meta["size"],
        }


@app.post("/admin/lore/import/{file_id}")
async def import_lore_file(
    file_id: str,
    request: Request,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Import a lore file into the database.

    Uses the LoreParsingAgent for AI-powered entity extraction.
    """
    from src.mantle.agents.lore_parsing_agent import LoreParsingAgent

    metadata = _load_lore_metadata()
    file_meta = next((m for m in metadata if m["id"] == file_id), None)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = LORE_UPLOADS_DIR / file_meta["stored_as"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File data not found")

    # Check if AI is available
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured (GEMINI_API_KEY missing)"
        )

    try:
        await AuditLogger.log(f"Lore file import started: {file_meta['filename']} (file_id={file_id})")
        
        # Read file content
        if file_path.suffix == ".pdf":
            try:
                from pypdf import PdfReader
                # Run PDF extraction in threadpool to avoid blocking
                def _extract_pdf(path):
                    reader = PdfReader(str(path))
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    return text

                content = await run_in_threadpool(_extract_pdf, file_path)
                logger.info(f"Extracted {len(content)} chars from PDF {file_meta['filename']}")

            except ImportError:
                raise HTTPException(
                    status_code=501,
                    detail="PDF support not available (pypdf not installed)"
                )
            except Exception as e:
                logger.error(f"PDF parsing failed: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse PDF: {str(e)}"
                )
        else:
            content = file_path.read_text(encoding="utf-8")
        logger.info(f"Read file {file_meta['filename']}: {len(content)} chars")

        # Use LoreParsingAgent for extraction
        agent = LoreParsingAgent(api_key=gemini_key)
        source_name = file_meta["filename"]

        result = await agent.parse_and_store(
            text=content,
            db=db,
            source_name=source_name,
            world_id=source_name,
        )

        # Update metadata with import result
        import_result = {
            "entities_stored": result.entities_stored,
            "relationships_stored": result.relationships_stored,
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }

        for m in metadata:
            if m["id"] == file_id:
                m["status"] = "imported"
                m["import_result"] = import_result
                break

        _save_lore_metadata(metadata)

        await AuditLogger.log(f"Lore file imported successfully: {file_meta['filename']} - {result.entities_stored} entities, {result.relationships_stored} relationships")

        return {
            "status": "success",
            "file_id": file_id,
            "filename": file_meta["filename"],
            "entities_stored": result.entities_stored,
            "entities_created": result.entities_stored,  # Alias for frontend compatibility
            "relationships_stored": result.relationships_stored,
        }

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse AI response as JSON: {str(e)}"
        await AuditLogger.log(f"Import JSON error for {file_meta['filename']}: {error_msg}", level=logging.ERROR)
        logger.error(f"JSON parsing error in import: {e}", exc_info=True)
        
        # Update metadata with failure
        for m in metadata:
            if m["id"] == file_id:
                m["status"] = "failed"
                m["import_result"] = {
                    "error": error_msg,
                    "error_type": "json_parse_error"
                }
                break
        _save_lore_metadata(metadata)
        
        raise HTTPException(
            status_code=500, 
            detail={
                "error_type": "json_parse_error",
                "message": "The AI returned an improperly formatted response. Please try again.",
                "details": error_msg,
                "step_failed": "parsing"
            }
        )
    except UnicodeDecodeError as e:
        error_msg = f"Failed to read file as text: {str(e)}"
        await AuditLogger.log(f"Import file encoding error for {file_meta['filename']}: {error_msg}", level=logging.ERROR)
        
        # Update metadata with failure
        for m in metadata:
            if m["id"] == file_id:
                m["status"] = "failed"
                m["import_result"] = {
                    "error": error_msg,
                    "error_type": "encoding_error"
                }
                break
        _save_lore_metadata(metadata)
        
        raise HTTPException(
            status_code=400,
            detail={
                "error_type": "encoding_error",
                "message": "File could not be read as text. Please ensure it's a valid text file.",
                "details": error_msg,
                "step_failed": "file_reading"
            }
        )
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        await AuditLogger.log(f"Import failed for {file_meta['filename']}: {error_type}: {error_msg}", level=logging.ERROR)
        logger.error(f"Import failed: {e}", exc_info=True)

        # Update metadata with failure
        for m in metadata:
            if m["id"] == file_id:
                m["status"] = "failed"
                m["import_result"] = {
                    "error": error_msg,
                    "error_type": error_type
                }
                break
        _save_lore_metadata(metadata)

        # Check for database errors
        if "neo4j" in error_msg.lower() or "database" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail={
                    "error_type": "neo4j_error",
                    "message": "Failed to save data to the database. Please try again.",
                    "details": f"{error_type}: {error_msg}",
                    "step_failed": "storage"
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_type": "import_error",
                    "message": f"Import failed: {error_msg}",
                    "details": f"{error_type}: {error_msg}",
                    "step_failed": "extraction"
                }
            )


@app.delete("/admin/lore/files/{file_id}")
async def delete_lore_file(file_id: str):
    """Delete a lore file from the staging area."""
    metadata = _load_lore_metadata()

    file_meta = next((m for m in metadata if m["id"] == file_id), None)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete the actual file
    file_path = LORE_UPLOADS_DIR / file_meta["stored_as"]
    if file_path.exists():
        file_path.unlink()

    # Remove from metadata
    metadata = [m for m in metadata if m["id"] != file_id]
    _save_lore_metadata(metadata)

    logger.info(f"Lore file deleted: {file_meta['filename']}")

    return {"status": "success", "message": f"Deleted {file_meta['filename']}"}


# ============================================================
# ROUTER REGISTRATION
# ============================================================

app.include_router(router)
app.include_router(get_contradiction_router())

# Orchestrator routes
from src.mantle.api.orchestrator_routes import router as orchestrator_router
app.include_router(orchestrator_router, prefix="/api")

# Game session routes
from src.mantle.api.game_routes import router as game_router
app.include_router(game_router, prefix="/api")

# World Tuner routes (conversational world config)
from src.mantle.api.world_tuner_routes import router as world_tuner_router
app.include_router(world_tuner_router, prefix="/api")

# Memory system routes
from src.mantle.api.memory_routes import router as memory_router
app.include_router(memory_router, prefix="/api")

# D&D 5e rules system routes
from src.mantle.api.dnd_routes import router as dnd_router
app.include_router(dnd_router, prefix="/api")


# ============================================================
# FEEDBACK SYSTEM (for playtester feedback collection)
# ============================================================

FEEDBACK_FILE = Path(__file__).parent.parent.parent.parent / "data" / "feedback.json"


def _load_feedback() -> List[Dict[str, Any]]:
    """Load feedback from file."""
    try:
        if FEEDBACK_FILE.exists():
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Failed to load feedback: {e}")
        return []


def _save_feedback(feedback_list: List[Dict[str, Any]]) -> None:
    """Save feedback to file."""
    try:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(feedback_list, f, indent=2)
        logging.info(f"Saved {len(feedback_list)} feedback entries to {FEEDBACK_FILE}")
    except Exception as e:
        logging.error(f"Failed to save feedback to {FEEDBACK_FILE}: {e}")
        raise  # Re-raise so the API can return an error


class FeedbackRequest(BaseModel):
    """Feedback submission from playtesters."""
    category: Optional[str] = Field(None, description="Feedback category")
    text: Optional[str] = Field(None, max_length=5000, description="Detailed feedback text")
    context: Optional[Dict[str, Any]] = Field(None, description="Context about what was happening")


@app.post("/api/feedback")
async def submit_feedback(request: Request, feedback: FeedbackRequest):
    """Submit feedback from a playtester. Stores in Neo4j for persistence."""
    if not feedback.category and not feedback.text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a category or feedback text"
        )

    feedback_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()
    tester = feedback.context.get("tester", "anonymous") if feedback.context else "anonymous"
    session_id = feedback.context.get("session_id", "") if feedback.context else ""

    # Store in Neo4j for persistence across deploys
    db = getattr(request.app.state, "neo4j_db", None)
    if db:
        try:
            await db.execute("""
                CREATE (f:Feedback {
                    feedback_id: $feedback_id,
                    timestamp: $timestamp,
                    category: $category,
                    text: $text,
                    tester: $tester,
                    session_id: $session_id,
                    screen: $screen,
                    world_id: $world_id
                })
            """, {
                "feedback_id": feedback_id,
                "timestamp": timestamp,
                "category": feedback.category or "",
                "text": feedback.text or "",
                "tester": tester,
                "session_id": session_id,
                "screen": feedback.context.get("screen", "") if feedback.context else "",
                "world_id": feedback.context.get("world_id", "") if feedback.context else "",
            })
            logging.info(f"Feedback stored in Neo4j from {tester}: [{feedback.category}]")
        except Exception as e:
            logging.error(f"Failed to store feedback in Neo4j: {e}")
    else:
        logging.warning("No Neo4j connection - feedback not persisted")

    await AuditLogger.log(f"Feedback from {tester}: [{feedback.category}] {(feedback.text or '')[:100]}")

    return {"success": True, "message": "Thank you for your feedback!", "feedback_id": feedback_id}


@app.get("/api/feedback")
async def get_all_feedback(request: Request):
    """Get all submitted feedback from Neo4j (for admin review)."""
    db = getattr(request.app.state, "neo4j_db", None)
    if not db:
        return {"count": 0, "feedback": []}

    try:
        result = await db.execute("""
            MATCH (f:Feedback)
            RETURN f.feedback_id AS id,
                   f.timestamp AS timestamp,
                   f.category AS category,
                   f.text AS text,
                   f.tester AS tester,
                   f.session_id AS session_id,
                   f.screen AS screen,
                   f.world_id AS world_id
            ORDER BY f.timestamp DESC
            LIMIT 100
        """, {})

        feedback_list = []
        for record in result:
            feedback_list.append({
                "id": record.get("id"),
                "timestamp": record.get("timestamp"),
                "category": record.get("category"),
                "text": record.get("text"),
                "context": {
                    "tester": record.get("tester"),
                    "session_id": record.get("session_id"),
                    "screen": record.get("screen"),
                    "world_id": record.get("world_id"),
                }
            })

        return {"count": len(feedback_list), "feedback": feedback_list}
    except Exception as e:
        logging.error(f"Failed to load feedback from Neo4j: {e}")
        return {"count": 0, "feedback": []}


# ============================================================
# SESSION LOGGING (for playtester analytics)
# ============================================================

SESSION_LOG_FILE = Path(__file__).parent.parent.parent.parent / "data" / "session_logs.json"


def _load_session_logs() -> List[Dict[str, Any]]:
    """Load session logs from file."""
    try:
        if SESSION_LOG_FILE.exists():
            with open(SESSION_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Failed to load session logs: {e}")
        return []


def _save_session_logs(logs: List[Dict[str, Any]]) -> None:
    """Save session logs to file."""
    try:
        SESSION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save session logs: {e}")


class SessionLogRequest(BaseModel):
    """Session log submission."""
    session_id: str
    tester: Optional[str] = None
    events: List[Dict[str, Any]] = Field(default_factory=list)


@app.post("/api/session-log")
async def log_session_events(request: SessionLogRequest):
    """Log session events from playtesters."""
    if not request.events:
        return {"success": True, "logged": 0}

    logs = _load_session_logs()

    # Add each event with session context
    for event in request.events:
        logs.append({
            "session_id": request.session_id,
            "tester": request.tester,
            "received_at": datetime.now(timezone.utc).isoformat(),
            **event
        })

    _save_session_logs(logs)

    return {"success": True, "logged": len(request.events)}


@app.get("/api/session-log")
async def get_session_logs():
    """Get all session logs (for admin review)."""
    logs = _load_session_logs()
    return {"count": len(logs), "logs": logs}


# ============================================================
# EMAIL SIGNUP (for update notifications)
# ============================================================

EMAIL_SIGNUPS_FILE = Path(__file__).parent.parent.parent.parent / "data" / "email_signups.json"


def _load_email_signups() -> Dict[str, Any]:
    """Load email signups from file."""
    try:
        if EMAIL_SIGNUPS_FILE.exists():
            with open(EMAIL_SIGNUPS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"signups": []}
    except Exception as e:
        logging.error(f"Failed to load email signups: {e}")
        return {"signups": []}


def _save_email_signups(data: Dict[str, Any]) -> None:
    """Save email signups to file."""
    try:
        EMAIL_SIGNUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EMAIL_SIGNUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save email signups: {e}")


class EmailSignupRequest(BaseModel):
    """Email signup submission."""
    email: str = Field(..., min_length=5, max_length=254)


@app.post("/api/email-signup")
async def submit_email_signup(request: EmailSignupRequest):
    """Submit email for update notifications."""
    import re

    # Basic email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a valid email address"
        )

    data = _load_email_signups()

    # Check for duplicate
    existing_emails = [s.get("email", "").lower() for s in data.get("signups", [])]
    if request.email.lower() in existing_emails:
        return {"success": True, "message": "You're already signed up for updates!"}

    # Add new signup
    data["signups"].append({
        "email": request.email,
        "signed_up_at": datetime.now(timezone.utc).isoformat(),
    })

    _save_email_signups(data)

    await AuditLogger.log(f"Email signup: {request.email[:3]}***@***")

    return {"success": True, "message": "Thanks! We'll keep you posted on updates."}


@app.get("/api/email-signup")
async def get_email_signups():
    """Get all email signups (for admin review)."""
    data = _load_email_signups()
    return {"count": len(data.get("signups", [])), "signups": data.get("signups", [])}


# ============================================================
# EMAIL NOTIFICATIONS (via Resend)
# ============================================================

VERSION_FILE = Path(__file__).parent.parent.parent.parent / "data" / "deployed_version.txt"
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# Get current version from sw.js
def _get_current_version() -> str:
    """Read current version from service worker."""
    try:
        sw_path = Path(__file__).parent.parent.parent.parent / "frontend" / "dist" / "sw.js"
        if sw_path.exists():
            content = sw_path.read_text()
            # Extract version from: const CACHE_VERSION = '2026-01-10-v16';
            import re
            match = re.search(r"CACHE_VERSION\s*=\s*['\"]([^'\"]+)['\"]", content)
            if match:
                return match.group(1)
    except Exception as e:
        logging.error(f"Failed to read version: {e}")
    return "unknown"


def _get_last_deployed_version() -> str:
    """Get the last deployed version we notified about."""
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text().strip()
    except Exception:
        pass
    return ""


def _save_deployed_version(version: str) -> None:
    """Save the current version as last deployed."""
    try:
        VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.write_text(version)
    except Exception as e:
        logging.error(f"Failed to save version: {e}")


async def send_update_notification(subject: str, message: str) -> dict:
    """Send update notification to all subscribers via Resend."""
    if not RESEND_API_KEY:
        logging.warning("RESEND_API_KEY not set - skipping email notification")
        return {"success": False, "error": "API key not configured"}

    try:
        import resend
        resend.api_key = RESEND_API_KEY

        data = _load_email_signups()
        subscribers = data.get("signups", [])

        if not subscribers:
            logging.info("No subscribers to notify")
            return {"success": True, "sent": 0, "message": "No subscribers"}

        emails = [s.get("email") for s in subscribers if s.get("email")]

        if not emails:
            return {"success": True, "sent": 0, "message": "No valid emails"}

        # Send email (Resend supports batch sending)
        # Using their onboarding domain for testing, replace with your verified domain
        from_email = os.getenv("RESEND_FROM_EMAIL", "Mantle <onboarding@resend.dev>")

        html_content = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #e8c47c;">Mantle Update</h2>
            <div style="color: #333; line-height: 1.6;">
                {message}
            </div>
            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
            <p style="color: #888; font-size: 12px;">
                You're receiving this because you signed up for Mantle updates.<br>
                <a href="https://lore-management-system.fly.dev" style="color: #e8c47c;">Play Mantle</a>
            </p>
        </div>
        """

        # Send to each subscriber (Resend free tier: 100/day)
        sent_count = 0
        errors = []

        for email in emails[:100]:  # Limit to 100 per send
            try:
                resend.Emails.send({
                    "from": from_email,
                    "to": [email],
                    "subject": subject,
                    "html": html_content
                })
                sent_count += 1
                logging.info(f"Sent update email to {email[:3]}***")
            except Exception as e:
                errors.append(f"{email[:3]}***: {str(e)}")
                logging.error(f"Failed to send to {email}: {e}")

        return {
            "success": True,
            "sent": sent_count,
            "total_subscribers": len(emails),
            "errors": errors if errors else None
        }

    except ImportError:
        logging.error("Resend package not installed")
        return {"success": False, "error": "Resend package not installed"}
    except Exception as e:
        logging.error(f"Failed to send notifications: {e}")
        return {"success": False, "error": str(e)}


class UpdateNotificationRequest(BaseModel):
    """Manual update notification request."""
    subject: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=10, max_length=5000)


@app.post("/api/admin/send-update")
async def send_manual_update(request: UpdateNotificationRequest):
    """Send a manual update notification to all subscribers (admin only)."""
    result = await send_update_notification(request.subject, request.message)
    return result


# Auto-notify on deploy (called during startup)
async def check_and_notify_deploy():
    """Check if version changed and send notification."""
    current_version = _get_current_version()
    last_version = _get_last_deployed_version()

    logging.info(f"Version check: current={current_version}, last={last_version}")

    if current_version and current_version != last_version and current_version != "unknown":
        logging.info(f"New version detected: {current_version}")

        # Save version first to prevent duplicate notifications
        _save_deployed_version(current_version)

        # Send notification
        result = await send_update_notification(
            subject=f"Mantle Updated - {current_version}",
            message=f"""
            <p>A new version of Mantle has been deployed!</p>
            <p><strong>Version:</strong> {current_version}</p>
            <p>Check out the latest features and improvements at
            <a href="https://lore-management-system.fly.dev" style="color: #e8c47c;">lore-management-system.fly.dev</a></p>
            """
        )
        logging.info(f"Deploy notification result: {result}")
    else:
        logging.info("No version change detected, skipping notification")


# Register startup event to check for deploy
@app.on_event("startup")
async def startup_deploy_check():
    """Check for new deploy on startup."""
    # Run after a short delay to let other startup tasks complete
    await asyncio.sleep(5)
    await check_and_notify_deploy()


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
        # Add no-cache headers to ensure users always get latest version
        return FileResponse(
            str(index_path),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

    raise HTTPException(status_code=404, detail="Not Found")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)