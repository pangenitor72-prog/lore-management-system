import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from src.api.routes import app
from src.db.neo4j_adapter import Neo4jDatabase
from src.api.dependencies import get_neo4j_db


class InMemoryMockDatabase:
    """
    A mock database that stores entities in memory for testing.
    This simulates the Neo4j database behavior for entity CRUD operations.
    """
    def __init__(self):
        self.entities = {}
        self.contradictions = {}
        self.analyses = {}
        self.entity_contradiction_links = {}  # Maps contradiction_id -> [entity_ids]
        self.driver = None  # Mock driver for tests that need it
    
    async def execute(self, query: str, params: dict = None):
        params = params or {}
        query_lower = query.lower()
        
        # Handle simple connectivity check (RETURN 1)
        if query_lower.strip() == "return 1":
            return [{"1": 1}]
        
        # =============================================
        # ANALYSIS PATTERNS (must come before contradiction patterns!)
        # These queries contain "contradiction" but are about analysis
        # =============================================
        
        # Handle analysis creation (CREATE TriageAnalysis with ANALYZES relationship)
        # Query: MATCH (c:Contradiction...) CREATE (a:TriageAnalysis...) MERGE (a)-[:ANALYZES]->(c)
        if "create" in query_lower and "triageanalysis" in query_lower:
            contradiction_id = params.get("cid")
            if contradiction_id and contradiction_id in self.contradictions:
                now = params.get("now", datetime.now(timezone.utc).isoformat())
                analysis_props = {
                    "analyst": params.get("analyst"),
                    "analysis": params.get("analysis"),
                    "recommendation": params.get("rec"),
                    "confidence": params.get("conf"),
                    "analyzed_at": now
                }
                self.analyses[contradiction_id] = analysis_props
                # Update contradiction status to IN_REVIEW
                self.contradictions[contradiction_id]["status"] = "IN_REVIEW"
                return [{"props": analysis_props}]
            # Contradiction not found
            return []
        
        # Handle analysis retrieval (ANALYZES relationship query)
        # Query: MATCH (c:Contradiction...)<-[:ANALYZES]-(a:TriageAnalysis)
        if "analyzes" in query_lower and "triageanalysis" in query_lower:
            contradiction_id = params.get("cid") or params.get("contradiction_id")
            if contradiction_id and contradiction_id in self.analyses:
                return [{"props": self.analyses[contradiction_id]}]
            return []
        
        # =============================================
        # ENTITY-CONTRADICTION LINKING
        # =============================================
        
        # Handle entity-contradiction linking (MATCH...MATCH...MERGE pattern for INVOLVES)
        if "involves" in query_lower and "merge" in query_lower:
            cid = params.get("cid")
            eid = params.get("eid")
            if cid and eid:
                if cid not in self.entity_contradiction_links:
                    self.entity_contradiction_links[cid] = []
                if eid not in self.entity_contradiction_links[cid]:
                    self.entity_contradiction_links[cid].append(eid)
            return []
        
        # =============================================
        # ENTITY PATTERNS
        # =============================================
        
        # Handle entity creation (MERGE with label like Character, Location, etc.)
        if "merge" in query_lower and "canon_id" in query_lower and "set" in query_lower:
            props = params.get("props", {})
            canon_id = props.get("canon_id") or params.get("canon_id")
            if canon_id:
                self.entities[canon_id] = props
            return []
        
        # Handle entity retrieval by canon_id (specific query with $canon_id param)
        if "match" in query_lower and "n:entity" in query_lower and "canon_id" in query_lower and params.get("canon_id"):
            canon_id = params.get("canon_id")
            if canon_id and canon_id in self.entities:
                entity = self.entities[canon_id]
                return [{
                    "canon_id": entity.get("canon_id"),
                    "entity_type": entity.get("entity_type"),
                    "canonical_name": entity.get("canonical_name"),
                    "aliases": entity.get("aliases", []),
                    "approval_status": entity.get("approval_status"),
                    "confidence_level": entity.get("confidence_level"),
                    "party_knowledge": entity.get("party_knowledge"),
                    "created_at": entity.get("created_at"),
                    "updated_at": entity.get("updated_at"),
                    "all_props": entity
                }]
            return []
        
        # Handle list entities (no specific canon_id param)
        if "match" in query_lower and "n:entity" in query_lower and "return" in query_lower and not params.get("canon_id"):
            results = []
            for canon_id, entity in self.entities.items():
                results.append({
                    "canon_id": entity.get("canon_id"),
                    "entity_type": entity.get("entity_type"),
                    "canonical_name": entity.get("canonical_name"),
                    "aliases": entity.get("aliases", []),
                    "approval_status": entity.get("approval_status"),
                    "confidence_level": entity.get("confidence_level"),
                    "party_knowledge": entity.get("party_knowledge"),
                    "created_at": entity.get("created_at"),
                    "updated_at": entity.get("updated_at"),
                    "all_props": entity
                })
            return results
        
        # =============================================
        # CONTRADICTION PATTERNS
        # =============================================
        
        # Handle contradiction creation (MERGE c:Contradiction with SET)
        if "merge" in query_lower and "contradiction" in query_lower and "set" in query_lower:
            contradiction_id = params.get("cid") or params.get("contradiction_id")
            if contradiction_id:
                props = {
                    "contradiction_id": contradiction_id,
                    "type": params.get("type"),
                    "contradiction_type": params.get("type"),
                    "severity": params.get("severity"),
                    "description": params.get("desc") or params.get("description"),
                    "evidence": params.get("evidence", "{}"),
                    "detected_at": params.get("detected") or datetime.now(timezone.utc).isoformat(),
                    "status": params.get("status", "PENDING"),
                    "created_at": params.get("detected") or datetime.now(timezone.utc).isoformat(),
                }
                self.contradictions[contradiction_id] = props
            return []
        
        # Handle contradiction retrieval by ID (with cid param, but NOT analyzes queries)
        if "match" in query_lower and "contradiction" in query_lower and params.get("cid") and "analyzes" not in query_lower:
            contradiction_id = params.get("cid")
            if contradiction_id and contradiction_id in self.contradictions:
                c = self.contradictions[contradiction_id]
                entity_ids = self.entity_contradiction_links.get(contradiction_id, [])
                return [{
                    "props": c,
                    "entity_ids": entity_ids
                }]
            return []
        
        # Handle list contradictions (no specific cid param)
        if "match" in query_lower and "c:contradiction" in query_lower and not params.get("cid"):
            results = []
            for cid, c in self.contradictions.items():
                entity_ids = self.entity_contradiction_links.get(cid, [])
                results.append({
                    "props": c,
                    "entity_ids": entity_ids
                })
            return results
        
        # Default: return empty
        return []
    
    async def connect(self):
        pass
    
    async def close(self):
        pass
    
    async def list_indexes(self):
        return [{"name": "entity_embeddings"}]


# Mock Neo4j Database
@pytest.fixture
def mock_neo4j_db():
    return InMemoryMockDatabase()


# Override dependency and lifespan for testing
@pytest.fixture
def client(mock_neo4j_db):
    # Patch the get_neo4j_db dependency to return our mock
    app.dependency_overrides[get_neo4j_db] = lambda: mock_neo4j_db

    # Patch the connect_neo4j_with_timeout within src.api.routes to avoid real connection attempts
    # Also patch Neo4jDatabase to prevent any real database instantiation
    with patch("src.api.routes.connect_neo4j_with_timeout", AsyncMock(return_value=True)), \
         patch("src.api.routes.Neo4jDatabase", return_value=mock_neo4j_db):
        # Pre-set all app.state attributes that the lifespan would normally set
        # This ensures health checks pass even if lifespan partially runs
        app.state.neo4j_db = mock_neo4j_db
        app.state.query_agent = AsyncMock()
        app.state.auditor = AsyncMock()
        app.state.ai_enabled = False  # Disable AI features for faster tests
        app.state.vector_search_enabled = True  # Pretend vector index exists

        with TestClient(app) as c:
            yield c
    
    # Clean up overrides after test
    app.dependency_overrides = {}
