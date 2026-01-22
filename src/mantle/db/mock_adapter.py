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
        self.game_saves = {}  # Maps (browser_id or user_id, slot) -> save_data
        self.active_sessions = {}  # Maps session_id -> session_data
        self.game_sessions = {}  # Maps session_id -> session metadata
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
        
        # =============================================
        # GAME SAVE PATTERNS
        # =============================================
        
        # MERGE GameSave (Save game)
        if "merge" in query_lower and "gamesave" in query_lower:
            browser_id = params.get("browser_id")
            user_id = params.get("user_id")
            slot = params.get("slot")
            
            if slot:
                key = (user_id, slot) if user_id else (browser_id, slot)
                save_data = {
                    "browser_id": browser_id,
                    "user_id": user_id,
                    "slot": slot,
                    "session_id": params.get("session_id"),
                    "session_name": params.get("session_name"),
                    "character_concept": params.get("character_concept"),
                    "genre": params.get("genre"),
                    "phase": params.get("phase"),
                    "turn_count": params.get("turn_count"),
                    "saved_at": datetime.now(timezone.utc),
                    "world_name": params.get("world_name"),
                    "character_id": params.get("character_id"),
                    "character_name": params.get("character_name"),
                    "rules_mode": params.get("rules_mode"),
                    "session_status": params.get("session_status"),
                    "save_data": params.get("save_data_json"),
                }
                self.game_saves[key] = save_data
            return []
        
        # DELETE GameSave (must come before MATCH GameSave to avoid matching MATCH in DELETE query)
        if "gamesave" in query_lower and ("delete" in query_lower or "detach delete" in query_lower):
            browser_id = params.get("browser_id")
            user_id = params.get("user_id")
            slot = params.get("slot")
            
            if slot:
                key = (user_id, slot) if user_id else (browser_id, slot)
                if key in self.game_saves:
                    del self.game_saves[key]
                    return [{"deleted": 1}]
            return [{"deleted": 0}]
        
        # MATCH GameSave (List saves)
        if "match" in query_lower and "gamesave" in query_lower and "return" in query_lower:
            browser_id = params.get("browser_id")
            user_id = params.get("user_id")
            
            results = []
            for key, save in self.game_saves.items():
                # Filter by scope
                if user_id:
                    if save.get("user_id") != user_id:
                        continue
                else:
                    if save.get("browser_id") != browser_id or save.get("user_id") is not None:
                        continue
                
                results.append({
                    "slot": save["slot"],
                    "session_name": save["session_name"],
                    "character_concept": save["character_concept"],
                    "genre": save["genre"],
                    "phase": save["phase"],
                    "turn_count": save["turn_count"],
                    "saved_at": save["saved_at"],
                    "world_name": save["world_name"],
                    "character_id": save["character_id"],
                    "character_name": save["character_name"],
                    "rules_mode": save["rules_mode"],
                    "session_status": save["session_status"],
                    "save_data_json": save.get("save_data"),
                })
            return sorted(results, key=lambda x: x["slot"])
        
        # =============================================
        # ACTIVE SESSION PATTERNS
        # =============================================
        
        # MERGE ActiveSession (Persist session)
        if "merge" in query_lower and "activesession" in query_lower:
            session_id = params.get("session_id")
            if session_id:
                self.active_sessions[session_id] = {
                    "session_id": session_id,
                    "session_data": params.get("session_json"),
                    "updated_at": datetime.now(timezone.utc),
                    "phase": params.get("phase"),
                    "character_concept": params.get("character_concept"),
                    "turn_count": params.get("turn_count"),
                }
            return []
        
        # MATCH ActiveSession (Recover session)
        if "match" in query_lower and "activesession" in query_lower and "return" in query_lower:
            session_id = params.get("session_id")
            if session_id and session_id in self.active_sessions:
                return [{"session_json": self.active_sessions[session_id]["session_data"]}]
            return []
        
        # =============================================
        # GAME SESSION METADATA PATTERNS
        # =============================================
        
        # CREATE GameSession (Metadata tracking)
        if "create" in query_lower and "gamesession" in query_lower:
            session_id = params.get("session_id")
            if session_id:
                self.game_sessions[session_id] = {
                    "session_id": session_id,
                    "world_id": params.get("world_id"),
                    "session_world_id": params.get("session_world_id"),
                    "phase": params.get("phase"),
                    "status": params.get("status", "active"),
                    "genre": params.get("genre"),
                    "character_name": params.get("character_name"),
                    "tester": params.get("tester"),
                    "storytelling_style": params.get("style"),
                    "is_curated_world": params.get("is_curated"),
                    "curated_world_name": params.get("curated_name"),
                    "turn_count": 0,
                    "created_at": datetime.now(timezone.utc),
                }
            return []
        
        # UPDATE GameSession turn count
        if "match" in query_lower and "gamesession" in query_lower and "set" in query_lower and "turn_count" in query_lower:
            session_id = params.get("session_id")
            if session_id and session_id in self.game_sessions:
                self.game_sessions[session_id]["turn_count"] = params.get("turn_count", 0)
                self.game_sessions[session_id]["status"] = params.get("status", "active")
                self.game_sessions[session_id]["last_activity"] = datetime.now(timezone.utc)
            return []
        
        return []
    
    async def connect(self):
        pass
    
    async def close(self):
        pass
    
    async def list_indexes(self):
        return [{"name": "entity_embeddings"}]
    
    async def create_vector_index(self):
        return True