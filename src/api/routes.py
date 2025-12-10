# Standard Library
import os
import asyncio
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
import logging
from contextlib import asynccontextmanager

# Third Party
import uvicorn
from dotenv import load_dotenv
from fastapi import (
    FastAPI, HTTPException, Query, Body, Request,
    WebSocket, WebSocketDisconnect, status, APIRouter, Depends, File, UploadFile
)
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.ingestion.ingestor import LoreIngestor
from src.services.extraction_service import ExtractionService
from src.services.embedding_service import EmbeddingService

# Local Imports - Audit
from src.services.contradiction_service import ContradictionService

from src.services.audit_log import AuditLogger
from src.services.broadcaster import broadcaster

# Local Imports - Database (New Neo4j adapter)
from src.db.neo4j_adapter import Neo4jDatabase
from src.db.mock_adapter import InMemoryMockDatabase
from src.api.dependencies import get_neo4j_db

# Local Imports - Models
from src.core.models import (
    EntityCreate, EntityResponse, RelationshipCreate,
    ErrorResponse, ContradictionResponse, ContradictionCreate,
    ContradictionStatus, RelationshipResponse, ContradictionSeverity,
    ContradictionWithAnalysis, TriageAnalysisCreate,
    TriageAnalysisResponse, ContradictionUpdateRequest,
    EntityType, ApprovalStatus, ConfidenceLevel, PartyKnowledge,
    GameSessionResponse, InstanceResponse
)

# Local Imports - Agents
from src.agents.auditor_agent import AuditorAgent
from src.auditor.rule_based_auditor import RuleBasedAuditor
from src.auditor.semantic_auditor import SemanticAuditor
from src.agents.query_agent import QueryAgent

def get_contradiction_router(neo4j_db = Depends(get_neo4j_db)):
    router = APIRouter()

    gemini_api_key = os.getenv("GEMINI_API_KEY") or ""
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

    # Rule-based auditor (DB only)
    rule_based = RuleBasedAuditor(neo4j_db)

    # Semantic auditor (DB + Gemini key)
    semantic = SemanticAuditor(neo4j_db, gemini_api_key)

    # AuditorAgent
    auditor_agent = AuditorAgent(
        neo4j_db=neo4j_db,
        gemini_api_key=gemini_api_key,
        rule_based_auditor=rule_based,
        semantic_auditor=semantic,
    )

    service = ContradictionService(auditor_agent)

    @router.get("/audit/full")
    async def run_full_audit():
        return await service.run_full_audit()

    return router


# Configure module logger
logger = logging.getLogger(__name__)
logger.warning("[GeminiWS] routes.py module imported")

# ============================================================
# APP LIFESPAN
# ============================================================


async def connect_neo4j_with_timeout(
    neo4j_db: Neo4jDatabase,
    timeout: int = 10
) -> bool:
    """Connect to Neo4j with timeout to prevent startup hang."""
    try:
        await asyncio.wait_for(neo4j_db.connect(), timeout=timeout)
        await AuditLogger.log("✅ Neo4j connected successfully")
        return True
    except asyncio.TimeoutError:
        await AuditLogger.log(
            f"❌ Neo4j connection timeout after {timeout}s",
            level=logging.ERROR
        )
        return False
    except Exception as e:
        await AuditLogger.log(
            f"❌ Neo4j connection failed during startup: {e}",
            level=logging.ERROR
        )
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):

    await AuditLogger.log("Application startup...")

    # ------------------------
    # 1. GEMINI KEY / AI FLAG
    # ------------------------
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key in ["YOUR_KEY_HERE", "your-key"]:
        await AuditLogger.log(
            "⚠️ GEMINI_API_KEY missing or invalid - AI features disabled; QueryAgent will not start",
            level=logging.WARNING
        )
        app.state.ai_enabled = False
    else:
        await AuditLogger.log("✅ Gemini API key loaded")
        app.state.ai_enabled = True

    # ------------------------
    # 2. INIT NEO4J
    # ------------------------
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    await AuditLogger.log(
        f"Neo4j config loaded: uri={'SET' if neo4j_uri else 'MISSING'}, user={neo4j_user}, password_set={bool(neo4j_password)}"
    )

    if not neo4j_uri:
        await AuditLogger.log(
            "❌ NEO4J_URI not set. Aborting startup to avoid connecting to the wrong database.",
            level=logging.ERROR,
        )
        raise RuntimeError("NEO4J_URI is required but not set.")

    app.state.neo4j_db = Neo4jDatabase(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )

    connected = await connect_neo4j_with_timeout(app.state.neo4j_db)
    if not connected:
        await AuditLogger.log(
            "❌ Neo4j unavailable - aborting startup (mock DB disabled)",
            level=logging.ERROR
        )
        raise RuntimeError("Neo4j connection failed; mock DB is disabled.")

    # ------------------------
    # 3. VECTOR INDEX
    # ------------------------
    try:
        if connected:
            indexes = await app.state.neo4j_db.list_indexes()
            has_vector = any(i.get("name") == "entity_embeddings" for i in indexes)

            if not has_vector:
                await AuditLogger.log("⚠️ Vector index missing - creating...")
                created = await app.state.neo4j_db.create_vector_index()
                app.state.vector_search_enabled = created
            else:
                app.state.vector_search_enabled = True
        else:
            app.state.vector_search_enabled = False
    except Exception as e:
        await AuditLogger.log(f"Vector index error: {e}", level=logging.ERROR)
        app.state.vector_search_enabled = False

    # ------------------------
    # 4. INIT AGENTS
    # ------------------------
    if app.state.ai_enabled and connected:
        try:
            rule_based_auditor = RuleBasedAuditor(app.state.neo4j_db)
            semantic_auditor = SemanticAuditor(app.state.neo4j_db, gemini_key)

            app.state.auditor = AuditorAgent(
                app.state.neo4j_db,
                gemini_key,
                rule_based_auditor=rule_based_auditor,
                semantic_auditor=semantic_auditor
            )

            app.state.query_agent = QueryAgent(
                app.state.neo4j_db,
                gemini_key,
                enable_vector_search=app.state.vector_search_enabled
            )

            await AuditLogger.log("✅ QueryAgent + Auditor initialized")
        except Exception as e:
            await AuditLogger.log(f"❌ Failed to initialize agents: {e}", level=logging.ERROR)
            app.state.query_agent = None
            app.state.auditor = None

    # ------------------------
    # 🌟 NOW THE ONE AND ONLY YIELD
    # ------------------------
    yield

    # ------------------------
    # SHUTDOWN
    # ------------------------
    try:
        await app.state.neo4j_db.close()
    except:
        pass

    await AuditLogger.log("Application shutdown...")

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
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Router
router = APIRouter()

# Path Configuration - Updated for new structure
BASE_DIR = Path(__file__).resolve().parent.parent  # Points to src/
templates = Jinja2Templates(directory=str(BASE_DIR / 'ui' / 'templates'))

# Mount Static Files - Updated for new structure
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "ui" / "static")),
    name="static"
)

# ============================================================
# WEBSOCKET ENDPOINTS
# ============================================================

print("[GeminiWS] DEBUG: about to register @app.websocket('/ws/gemini')")
@app.websocket("/ws/gemini")
async def websocket_gemini_endpoint(websocket: WebSocket, client_id: str = Query(...)):
    """
    WebSocket endpoint for the Lore Oracle (Gemini-backed).
    - Always accepts the socket immediately (before any send).
    - Waits briefly for QueryAgent to be initialized.
    - Delegates the loop to QueryAgent.handle_websocket once ready.
    """

    logger.warning("[GeminiWS] ENTERED handler before accept()")
    # Accept immediately to avoid ASGI "websocket.send before accept" errors.
    try:
        await websocket.accept()
        await AuditLogger.log("[GeminiWS] ACCEPTED socket", level=logging.INFO)
    except Exception as e:
        await AuditLogger.log(f"[GeminiWS] accept failed: {e}", level=logging.ERROR)
        return

    try:
        await AuditLogger.log(
            f"[GeminiWS] query_agent exists? {hasattr(app.state, 'query_agent')}",
            level=logging.INFO,
        )

        # If QueryAgent is not yet initialized, wait a bit for startup to finish
        if not hasattr(app.state, "query_agent"):
            await AuditLogger.log("[GeminiWS] Entered initializing-wait loop", level=logging.INFO)
            await websocket.send_json({
                "status": "initializing",
                "message": "QueryAgent is still starting up…"
            })

            # Poll for up to 3 seconds (30 * 100ms) for QueryAgent to appear
            for _ in range(30):
                await asyncio.sleep(0.1)
                if hasattr(app.state, "query_agent"):
                    break

            if not hasattr(app.state, "query_agent"):
                # Still not ready. Keep the socket open but inform the client.
                await AuditLogger.log(
                    "[GeminiWS] query_agent still missing after wait → closing",
                    level=logging.WARNING,
                )
                await websocket.send_json({
                    "error": "QueryAgent is not available yet. Try again in a few seconds."
                })
                code = status.WS_1011_INTERNAL_ERROR
                await AuditLogger.log(f"[GeminiWS] Closing socket with code {code}", level=logging.WARNING)
                # Let the client decide to reconnect; close cleanly to avoid 1006.
                await websocket.close(code=code)
                return

        # At this point, QueryAgent should be ready; hand off control.
        await AuditLogger.log("[GeminiWS] Handing off to QueryAgent.handle_websocket", level=logging.INFO)
        await app.state.query_agent.handle_websocket(websocket, client_id)
    except Exception as e:
        await AuditLogger.log(f"[GeminiWS] Fatal exception in endpoint: {e}", level=logging.ERROR)
        try:
            await websocket.send_json({"error": "internal_error", "detail": str(e)})
            code = status.WS_1011_INTERNAL_ERROR
            await AuditLogger.log(f"[GeminiWS] Closing socket with code {code}", level=logging.WARNING)
            await websocket.close(code=code)
        except Exception:
            pass
print("[GeminiWS] DEBUG: websocket_gemini_endpoint function defined successfully")

@app.websocket("/ws/auditor")
async def websocket_auditor_endpoint(websocket: WebSocket):
    """WebSocket endpoint for auditor events (contradiction detection, etc.)."""
    await websocket.accept()
    await AuditLogger.log("Auditor WebSocket client connected.")
    queue = await broadcaster.subscribe("auditor_events")
    try:
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        await AuditLogger.log("Auditor WebSocket client disconnected.")
    except Exception as e:
        await AuditLogger.log(f"Auditor WebSocket error: {e}", level=logging.ERROR)
    finally:
        broadcaster.unsubscribe("auditor_events", queue)
        try:
            await websocket.close()
        except Exception:
            pass  # Connection may already be closed


# TEMP: /ws/events disabled (no broadcaster during early dev).
# @app.websocket("/ws/events")
# async def websocket_events_endpoint(websocket: WebSocket, channels: str = Query("query_events")):
#     """
#     Persistent websocket that stays open and streams events from the broadcaster.
#     Frontend subscribes to this for query logs, audit logs, ingestion logs, etc.
#     """
#     await websocket.accept()
#
#     channel_list = channels.split(",")
#
#     # Open subscriptions for each channel
#     async with broadcaster.subscribe(channel_list) as subscriber:
#         try:
#             async for event in subscriber:
#                 # Each event.value is already JSON-serializable
#                 await websocket.send_json(event.message)
#         except WebSocketDisconnect:
#             print("[EventsWS] Client disconnected")
#         except Exception as e:
#             print("[EventsWS] ERROR:", e)
#         finally:
#             await websocket.close()

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


@router.get("/health")
async def health_check(request: Request):
    """System health check with feature flags."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "features": {}
    }

    try:
        await request.app.state.neo4j_db.execute("RETURN 1")
        health_status["checks"]["neo4j"] = "connected"
    except Exception as e:
        health_status["checks"]["neo4j"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    try:
        indexes = await request.app.state.neo4j_db.list_indexes()
        has_vector_index = any(idx.get("name") == "entity_embeddings" for idx in indexes)
        health_status["checks"]["vector_index"] = "exists" if has_vector_index else "missing"
        if not has_vector_index:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["vector_index"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    health_status["checks"]["query_agent"] = "ready" if hasattr(request.app.state, "query_agent") else "not_initialized"
    health_status["checks"]["auditor"] = "ready" if hasattr(request.app.state, "auditor") else "not_initialized"

    health_status["features"]["ai_enabled"] = getattr(request.app.state, "ai_enabled", False)
    health_status["features"]["vector_search"] = getattr(request.app.state, "vector_search_enabled", False)

    return health_status


@app.get("/debug/status")
async def debug_status(request: Request):
    import os
    from urllib.parse import urlparse

    neo4j_uri = os.getenv("NEO4J_URI", "NOT SET")
    parsed = urlparse(neo4j_uri) if neo4j_uri != "NOT SET" else None

    # Test Neo4j connection
    neo4j_ok = False
    try:
        if hasattr(request.app.state, "neo4j_db"):
            neo4j_ok = request.app.state.neo4j_db.test_connection()
    except Exception:
        pass

    return {
        "environment": os.getenv("APP_ENV", "development"),
        "ai_enabled": getattr(request.app.state, "ai_enabled", False),
        "gemini_key_present": bool(os.getenv("GEMINI_API_KEY")),
        "neo4j_uri_host": parsed.hostname if parsed else "NOT SET",
        "neo4j_uri_scheme": parsed.scheme if parsed else "NOT SET",
        "neo4j_uses_ssl": neo4j_uri.startswith("neo4j+s://") if neo4j_uri else False,
        "neo4j_connected": neo4j_ok,
    }


@app.get("/debug/neo4j-stats")
async def neo4j_stats():
    """Temporary endpoint to check what's in Neo4j"""
    try:
        db = app.state.query_agent.db

        counts = await db.execute("""
            MATCH (n) 
            RETURN labels(n)[0] AS type, count(*) AS count 
            ORDER BY count DESC
        """)

        samples = await db.execute("""
            MATCH (n) 
            WHERE n.name IS NOT NULL 
            RETURN labels(n)[0] AS type, n.name AS name 
            LIMIT 20
        """)

        return {"counts": counts, "samples": samples}
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/neo4j-stats")
async def neo4j_stats():
    """Temporary endpoint to check what's in Neo4j"""
    try:
        db = app.state.query_agent.db

        counts = await db.execute("""
            MATCH (n) 
            RETURN labels(n)[0] AS type, count(*) AS count 
            ORDER BY count DESC
        """)

        samples = await db.execute("""
            MATCH (n) 
            WHERE n.name IS NOT NULL 
            RETURN labels(n)[0] AS type, n.name AS name 
            LIMIT 20
        """)

        return {"counts": counts, "samples": samples}
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# INGESTION ENDPOINTS
# ============================================================

@router.post("/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    process_immediately: bool = True,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Accepts a batch of files for processing, saves them to a unique
    batch directory, and optionally processes them immediately.
    """
    batch_id = f"batch-{uuid.uuid4().hex}"
    upload_dir = Path("uploads") / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)  # Create the batch-specific directory

    saved_files: List[str] = []
    processing_results: List[dict] = []

    # Initialize Ingestor if processing is requested and AI is enabled
    ingestor: Optional[LoreIngestor] = None
    if process_immediately:
        try:
            gemini_key = os.getenv("GEMINI_API_KEY")
            print(f"[UPLOAD] process_immediately={process_immediately}", flush=True)
            print(f"[UPLOAD] gemini_key present={bool(os.getenv('GEMINI_API_KEY'))}", flush=True)
            print(f"[UPLOAD] ai_enabled={request.app.state.ai_enabled}", flush=True)
            if not gemini_key or not request.app.state.ai_enabled:
                print(f"[UPLOAD] SKIPPED: gemini_key={bool(gemini_key)}, ai_enabled={request.app.state.ai_enabled}", flush=True)
                await AuditLogger.log(
                    "Skipping processing: AI features disabled or GEMINI_API_KEY missing",
                    level=logging.WARNING
                )
            else:
                print("[UPLOAD] Creating ingestor...", flush=True)
                # 1. Instantiate services
                extraction_service = ExtractionService(api_key=gemini_key)
                embedding_service = EmbeddingService(api_key=gemini_key)

                # 2. Instantiate ingestor with services (use injected Neo4j adapter)
                ingestor = LoreIngestor(
                    db=db,
                    extraction_service=extraction_service,
                    embedding_service=embedding_service,
                )
        except Exception as e:
            print(f"[UPLOAD] EXCEPTION creating ingestor: {e}", flush=True)
            import traceback
            traceback.print_exc()
            await AuditLogger.log(f"Failed to initialize ingestor or its services: {e}", level=logging.ERROR)
            ingestor = None

    print(f"[UPLOAD] ingestor is None: {ingestor is None}", flush=True)

    for file in files:
        try:
            print("[UPLOAD] Received file:", file.filename, flush=True)
            file_path = upload_dir / file.filename

            # Use run_in_threadpool for the blocking I/O operation
            content = await file.read()
            await run_in_threadpool(file_path.write_bytes, content)

            saved_files.append(file.filename)

            # Process immediately if requested and ingestor is ready
            if process_immediately and ingestor:
                try:
                    print("[UPLOAD] Calling ingestor", flush=True)
                    # Decode content for processing
                    text_content = content.decode("utf-8")

                    # 1. Process (Extract)
                    result_data = await ingestor.process_file_content(file.filename, text_content)

                    # 2. Save to Neo4j
                    save_stats = await ingestor.save_to_neo4j(result_data["data"], file.filename)
                    print("[UPLOAD] Ingestor returned:", save_stats, flush=True)

                    processing_results.append({
                        "filename": file.filename,
                        "status": "processed",
                        "nodes_created": save_stats["nodes_saved"],
                        "relationships_created": save_stats["rels_saved"],
                    })

                    await AuditLogger.log(f"Processed {file.filename}: {save_stats}")

                except UnicodeDecodeError:
                    await AuditLogger.log(
                        f"Skipping processing for binary file: {file.filename}",
                        level=logging.WARNING
                    )
                    processing_results.append({"filename": file.filename, "status": "skipped_binary"})
                except Exception as proc_e:
                    await AuditLogger.log(
                        f"Processing failed for {file.filename}: {proc_e}",
                        level=logging.ERROR
                    )
                    processing_results.append(
                        {
                            "filename": file.filename,
                            "status": "failed",
                            "error": str(proc_e),
                        }
                    )

        except Exception as e:
            # Log the error
            await AuditLogger.log(f"Error saving file {file.filename}: {e}", level=logging.ERROR)
            raise HTTPException(
                status_code=500,
                detail=f"Could not save file: {file.filename}",
            )

    return {
        "batch_id": batch_id,
        "files_queued": len(saved_files),
        "status": "completed" if process_immediately else "queued",
        "filenames": saved_files,
        "processing_results": processing_results if process_immediately else [],
    }


# ============================================================
# ENTITY ENDPOINTS
# ============================================================

@router.post("/entities", response_model=EntityResponse, status_code=201)
async def create_entity(entity_data: EntityCreate, db: Neo4jDatabase = Depends(get_neo4j_db)):
    """Creates a new entity in the Neo4j graph."""
    canon_id = f"{entity_data.entity_type.value.lower()}-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    # Prepare properties map
    props = {
        "canon_id": canon_id,
        "entity_type": entity_data.entity_type.value,
        "name": entity_data.canonical_name,  # Standardize on 'name' for graph
        "canonical_name": entity_data.canonical_name,
        "approval_status": entity_data.approval_status.value,
        "confidence_level": entity_data.confidence_level.value,
        "party_knowledge": entity_data.party_knowledge.value,
        "created_at": created_at,
        "updated_at": created_at,
        "aliases": entity_data.aliases,
    }

    # Add approved fields to properties
    for key, value in entity_data.approved_fields.items():
        # Neo4j properties must be primitives
        if isinstance(value, (dict, list)) and key != "aliases":
            props[key] = json.dumps(value)
        else:
            props[key] = value

    label = entity_data.entity_type.value
    # Sanitize label
    safe_label = "".join([c for c in label if c.isalnum()])

    query = f"""
    MERGE (n:`{safe_label}` {{canon_id: $canon_id}})
    SET n += $props
    SET n:Entity
    RETURN n
    """

    try:
        await db.execute(query, {"canon_id": canon_id, "props": props})

        # Verify creation and return formatted response
        created_entity = await get_entity(canon_id, db=db)
        return created_entity

    except Exception as e:
        await AuditLogger.log(f"Error in create_entity: {e}", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"Failed to create entity: {e}")


@router.get("/entities/browser", response_class=HTMLResponse)
async def entities_browser(request: Request, canon_id: Optional[str] = None):
    context = {"request": request}
    template_name = "entities.html"
    if canon_id:
        template_name = "entity_detail.html"
        context["canon_id"] = canon_id
    return templates.TemplateResponse(template_name, context)


@router.get("/entities/{canon_id}", response_model=EntityResponse)
async def get_entity(canon_id: str, db: Neo4jDatabase = Depends(get_neo4j_db)):
    """Get an entity by canon_id from Neo4j."""
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
    results = await db.execute(query, {"canon_id": canon_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {canon_id}"
        )

    record = results[0]

    # Extract extra fields from properties
    all_props = record["all_props"]
    reserved_keys = {
        "canon_id", "entity_type", "canonical_name", "aliases",
        "approval_status", "confidence_level", "party_knowledge",
        "created_at", "updated_at", "name", "embedding",
    }

    approved_fields = {}
    for k, v in all_props.items():
        if k not in reserved_keys:
            try:
                approved_fields[k] = json.loads(v)
            except Exception:
                approved_fields[k] = v

    return EntityResponse(
        canon_id=record["canon_id"],
        entity_type=EntityType(record["entity_type"]),
        canonical_name=record["canonical_name"],
        aliases=record["aliases"] if record["aliases"] else [],
        approved_fields=approved_fields,
        approval_status=ApprovalStatus(record["approval_status"]),
        confidence_level=ConfidenceLevel(record["confidence_level"]),
        party_knowledge=PartyKnowledge(record["party_knowledge"]),
        created_at=datetime.fromisoformat(record["created_at"]) if record["created_at"] else datetime.now(),
        updated_at=datetime.fromisoformat(record["updated_at"]) if record["updated_at"] else datetime.now(),
    )


@router.get("/entities", response_model=List[EntityResponse])
async def list_entities(
    db: Neo4jDatabase = Depends(get_neo4j_db),
    entity_type: Optional[EntityType] = None,
    approval_status: Optional[ApprovalStatus] = None,
    limit: int = 100,
):
    """List entities with optional filters using Neo4j."""
    query = "MATCH (n:Entity)"
    where_clauses = []
    params: dict = {"limit": limit}

    if entity_type:
        where_clauses.append("n.entity_type = $type")
        params["type"] = entity_type.value

    if approval_status:
        where_clauses.append("n.approval_status = $status")
        params["status"] = approval_status.value

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += """
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
    ORDER BY n.created_at DESC
    LIMIT $limit
    """

    records = await db.execute(query, params)

    result_entities: List[EntityResponse] = []
    reserved_keys = {
        "canon_id", "entity_type", "canonical_name", "aliases",
        "approval_status", "confidence_level", "party_knowledge",
        "created_at", "updated_at", "name", "embedding",
    }

    for record in records:
        try:
            # Extract extra fields
            all_props = record["all_props"]
            approved_fields = {}
            for k, v in all_props.items():
                if k not in reserved_keys:
                    try:
                        approved_fields[k] = json.loads(v)
                    except Exception:
                        approved_fields[k] = v

            result_entities.append(
                EntityResponse(
                    canon_id=record["canon_id"],
                    entity_type=EntityType(record["entity_type"]),
                    canonical_name=record["canonical_name"],
                    aliases=record["aliases"] if record["aliases"] else [],
                    approved_fields=approved_fields,
                    approval_status=ApprovalStatus(record["approval_status"]),
                    confidence_level=ConfidenceLevel(record["confidence_level"]),
                    party_knowledge=PartyKnowledge(record["party_knowledge"]),
                    created_at=datetime.fromisoformat(record["created_at"]) if record["created_at"] else datetime.now(),
                    updated_at=datetime.fromisoformat(record["updated_at"]) if record["updated_at"] else datetime.now(),
                )
            )
        except Exception as e:
            await AuditLogger.log(
                f"Error parsing entity row {record.get('canon_id')}: {e}",
                level=logging.WARNING
            )
            continue

    return result_entities


# ============================================================
# DASHBOARD ROUTES
# ============================================================

class DashboardCard(BaseModel):
    id: int
    title: str
    description: str | None = None
    severity: str
    source: str


@router.get("/dashboard")
async def read_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/contradictions", response_model=List[DashboardCard])
async def get_contradictions():
    # MOCK DATA FOR UI TESTING
    return [
        DashboardCard(
            id=101, title="Timeline Fracture: The Black King",
            description="Player claimed to kill the Black King in Year 298, but Archive shows he appears in Year 302.",
            severity="CRITICAL", source="Session 42 Log"
        ),
        DashboardCard(
            id=102, title="Inventory Mismatch: Sun Blade",
            description="Party sheet lists Sun Blade as sold; Jim's notes say 'Stolen by Kobolds'.",
            severity="MINOR", source="Inventory Audit"
        ),
        DashboardCard(
            id=103, title="NPC Status: Lady Vengeance",
            description="Status flag is DEAD, but she is currently giving a quest in the Waterdeep module.",
            severity="CRITICAL", source="NPC Tracker"
        ),
    ]


# ============================================================
# ROUTER REGISTRATION
# ============================================================

def _debug_log_gemini_route(app_instance):
    from fastapi.routing import APIRoute
    try:
        from fastapi.routing import WebSocketRoute
    except ImportError:
        from starlette.routing import WebSocketRoute
    print("[GeminiWS] DEBUG: scanning app.router.routes for /ws/gemini …")
    for route in app_instance.router.routes:
        path = getattr(route, "path", None)
        if path == "/ws/gemini":
            endpoint = getattr(route, "endpoint", None)
            module = getattr(endpoint, "__module__", None)
            qualname = getattr(endpoint, "__qualname__", None)
            print(
                "[GeminiWS] DEBUG: FOUND /ws/gemini route →",
                "type:", type(route).__name__,
                "module:", module,
                "qualname:", qualname,
            )

app.include_router(router)
logger.warning("[GeminiWS] routes.py: router included into app")
app.include_router(get_contradiction_router())
_debug_log_gemini_route(app)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)