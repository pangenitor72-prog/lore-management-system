import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from src.lms.db.neo4j_adapter import Neo4jDatabase
from src.lms.services.audit_log import AuditLogger

class GameSession:
    """
    Manages the lifecycle of an AIRpg session.
    Handles session creation, state persistence, and instance management.
    """
    
    def __init__(self, db: Neo4jDatabase, session_id: Optional[str] = None):
        self.db = db
        self.session_id = session_id or str(uuid.uuid4())
        self.is_new = session_id is None

    async def initialize(self, player_id: str = "player_1"):
        """Create a new session node in Neo4j if it doesn't exist."""
        if not self.is_new:
            return # Already exists
            
        query = """
        CREATE (s:Session {
            session_id: $sid,
            created_at: $now,
            updated_at: $now,
            player_id: $pid,
            status: 'ACTIVE',
            turn_count: 0,
            summary: ''
        })
        RETURN s.session_id
        """
        await self.db.execute(query, {
            "sid": self.session_id,
            "now": datetime.now(timezone.utc).isoformat(),
            "pid": player_id
        })
        await AuditLogger.log(f"GameSession: Started new session {self.session_id}")

    async def create_campaign(self, name: str, description: str = None, tone: str = None, setting_theme: str = None):
        campaign_id = str(uuid.uuid4())
        metadata = {
            "campaign_id": campaign_id,
            "name": name,
            "description": description,
            "tone": tone,
            "setting_theme": setting_theme,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        await self.db.execute(
            """
            MERGE (c:Campaign {campaign_id: $campaign_id})
            SET c += $metadata
            """,
            {"campaign_id": campaign_id, "metadata": metadata}
        )

        self.campaign_id = campaign_id
        self.campaign_metadata = metadata
        return campaign_id, metadata


    async def load_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent chat/action history for this session."""
        query = """
        MATCH (s:Session {session_id: $sid})-[:HAS_EVENT]->(e:Event)
        RETURN e.type AS type, e.content AS content, e.timestamp AS timestamp
        ORDER BY e.timestamp ASC
        LIMIT $limit
        """
        results = await self.db.execute(query, {"sid": self.session_id, "limit": limit})
        return [dict(r) for r in results]

    async def add_event(self, event_type: str, content: str):
        """Log a player action or DM response to the session history."""
        query = """
        MATCH (s:Session {session_id: $sid})
        CREATE (e:Event {
            type: $type,
            content: $content,
            timestamp: $now
        })
        MERGE (s)-[:HAS_EVENT]->(e)
        SET s.updated_at = $now, s.turn_count = s.turn_count + 1
        """
        await self.db.execute(query, {
            "sid": self.session_id,
            "type": event_type,
            "content": content,
            "now": datetime.now(timezone.utc).isoformat()
        })

    async def instantiate_entity(self, canon_id: str) -> Optional[str]:
        """
        Create a mutable Instance of a canonical Entity for this session.
        Returns the instance_id.
        """
        # Check if instance already exists
        check_query = """
        MATCH (s:Session {session_id: $sid})-[:CONTAINS]->(i:Instance)-[:INSTANCE_OF]->(e:Entity {canon_id: $cid})
        RETURN i.instance_id AS iid
        """
        existing = await self.db.execute(check_query, {"sid": self.session_id, "cid": canon_id})
        if existing:
            return existing[0]["iid"]

        # Create new instance
        instance_id = f"inst-{uuid.uuid4().hex[:8]}"
        copy_query = """
        MATCH (s:Session {session_id: $sid})
        MATCH (e:Entity {canon_id: $cid})
        CREATE (i:Instance {
            instance_id: $iid,
            session_id: $sid,
            name: e.name,
            current_hp: 100,  // Placeholder default
            status: 'Normal'
        })
        MERGE (s)-[:CONTAINS]->(i)
        MERGE (i)-[:INSTANCE_OF]->(e)
        RETURN i.instance_id
        """
        await self.db.execute(copy_query, {
            "sid": self.session_id,
            "cid": canon_id,
            "iid": instance_id
        })
        return instance_id

    async def get_state(self) -> Dict[str, Any]:
        """Retrieve current session state (active instances, location, etc)."""
        query = """
        MATCH (s:Session {session_id: $sid})
        OPTIONAL MATCH (s)-[:CONTAINS]->(i:Instance)
        RETURN s, collect(properties(i)) as instances
        """
        res = await self.db.execute(query, {"sid": self.session_id})
        if not res:
            return {}
        
        row = res[0]
        return {
            "session": dict(row['s']),
            "instances": [dict(i) for i in row['instances']]
        }
