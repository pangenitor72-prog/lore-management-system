import json
from datetime import datetime, timezone

class InMemoryMockDatabase:
    """
    A mock database that stores entities in memory.
    Useful for testing and development without a running Neo4j instance.
    """
    def __init__(self):
        self.entities = {}
        self.contradictions = {}
        self.analyses = {}
        self.entity_contradiction_links = {}  # Maps contradiction_id -> [entity_ids]
        self.driver = None
    
    async def execute(self, query: str, params: dict = None):
        params = params or {}
        query_lower = query.lower()
        
        # Handle simple connectivity check (RETURN 1)
        if query_lower.strip() == "return 1":
            return [{"1": 1}]
        
        # =============================================
        # ANALYSIS PATTERNS
        # =============================================
        
        # Handle analysis creation
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
                self.contradictions[contradiction_id]["status"] = "IN_REVIEW"
                return [{"props": analysis_props}]
            return []
        
        # Handle analysis retrieval
        if "analyzes" in query_lower and "triageanalysis" in query_lower:
            contradiction_id = params.get("cid") or params.get("contradiction_id")
            if contradiction_id and contradiction_id in self.analyses:
                return [{"props": self.analyses[contradiction_id]}]
            return []
        
        # =============================================
        # ENTITY-CONTRADICTION LINKING
        # =============================================
        
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
        
        # Create Entity
        if "merge" in query_lower and "canon_id" in query_lower and "set" in query_lower:
            props = params.get("props", {})
            canon_id = props.get("canon_id") or params.get("canon_id")
            if canon_id:
                self.entities[canon_id] = props
            return []
        
        # Get Entity by ID
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
        
        # List Entities
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
        
        # Create Contradiction
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
        
        # Get Contradiction by ID
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
        
        # List Contradictions
        if "match" in query_lower and "c:contradiction" in query_lower and not params.get("cid"):
            results = []
            for cid, c in self.contradictions.items():
                entity_ids = self.entity_contradiction_links.get(cid, [])
                results.append({
                    "props": c,
                    "entity_ids": entity_ids
                })
            return results
        
        return []
    
    async def connect(self):
        pass
    
    async def close(self):
        pass
    
    async def list_indexes(self):
        return [{"name": "entity_embeddings"}]
    
    async def create_vector_index(self):
        return True