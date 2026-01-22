"""
Entity Repository - Centralized entity operations.

Consolidates common entity query patterns to reduce duplication
and provide a consistent interface for entity CRUD operations.
"""

from typing import List, Dict, Any, Optional
import logging

from src.mantle.db.neo4j_adapter import Neo4jDatabase

logger = logging.getLogger(__name__)


class EntityRepository:
    """Centralized entity operations for Neo4j."""

    def __init__(self, db: Neo4jDatabase):
        self.db = db

    async def get_by_id(self, canon_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by canon_id."""
        result = await self.db.execute(
            """
            MATCH (e:Entity {canon_id: $canon_id})
            RETURN e {.*} as entity
            """,
            {"canon_id": canon_id}
        )
        return result[0]["entity"] if result else None

    async def get_by_world(
        self,
        world_id: str,
        entity_type: Optional[str] = None,
        source_name: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Get entities for a world with optional filters."""
        conditions = ["e.world_id = $world_id OR e.curated_world_id = $world_id"]
        params = {"world_id": world_id, "limit": limit}

        if entity_type:
            conditions.append("e.entity_type = $entity_type")
            params["entity_type"] = entity_type

        if source_name:
            conditions.append("e.source_name = $source_name")
            params["source_name"] = source_name

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (e:Entity)
            WHERE {where_clause}
            RETURN e {{.*}} as entity
            ORDER BY e.name
            LIMIT $limit
        """

        result = await self.db.execute(query, params)
        return [r["entity"] for r in result]

    async def exists(self, canon_id: str) -> bool:
        """Check if entity exists."""
        result = await self.db.execute(
            "MATCH (e:Entity {canon_id: $canon_id}) RETURN count(e) > 0 as exists",
            {"canon_id": canon_id}
        )
        return result[0]["exists"] if result else False

    async def delete(self, canon_id: str) -> bool:
        """Delete entity by canon_id."""
        result = await self.db.execute(
            """
            MATCH (e:Entity {canon_id: $canon_id})
            DETACH DELETE e
            RETURN count(e) as deleted
            """,
            {"canon_id": canon_id}
        )
        return result[0]["deleted"] > 0 if result else False

    async def bulk_delete(self, canon_ids: List[str]) -> int:
        """Delete multiple entities by canon_id."""
        result = await self.db.execute(
            """
            MATCH (e:Entity)
            WHERE e.canon_id IN $canon_ids
            WITH e, e.canon_id as eid
            DETACH DELETE e
            RETURN count(eid) as deleted
            """,
            {"canon_ids": canon_ids}
        )
        return result[0]["deleted"] if result else 0

    async def update_properties(
        self, canon_id: str, properties: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update entity properties."""
        result = await self.db.execute(
            """
            MATCH (e:Entity {canon_id: $canon_id})
            SET e += $props
            RETURN e {.*} as entity
            """,
            {"canon_id": canon_id, "props": properties}
        )
        return result[0]["entity"] if result else None

    async def find_duplicates(
        self, world_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find potential duplicate entities by similar names."""
        params = {}
        where_clause = ""

        if world_id:
            where_clause = "WHERE e.world_id = $world_id OR e.curated_world_id = $world_id"
            params["world_id"] = world_id

        result = await self.db.execute(
            f"""
            MATCH (e:Entity)
            {where_clause}
            WITH toLower(e.name) as lowername, collect(e) as entities
            WHERE size(entities) > 1
            RETURN lowername as name, [e in entities | e {{.canon_id, .name, .entity_type, .world_id}}] as duplicates
            ORDER BY size(entities) DESC
            """,
            params
        )
        return [{"name": r["name"], "duplicates": r["duplicates"]} for r in result]

    async def merge_entities(
        self, target_id: str, source_ids: List[str], merged_properties: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Merge multiple entities into one.

        - Updates target entity with merged_properties
        - Transfers relationships from source entities to target
        - Deletes source entities
        """
        # Update target with merged properties
        await self.db.execute(
            """
            MATCH (target:Entity {canon_id: $target_id})
            SET target += $props
            """,
            {"target_id": target_id, "props": merged_properties}
        )

        # Transfer relationships from sources to target
        for source_id in source_ids:
            if source_id == target_id:
                continue

            # Transfer outgoing relationships
            await self.db.execute(
                """
                MATCH (source:Entity {canon_id: $source_id})-[r]->(other)
                MATCH (target:Entity {canon_id: $target_id})
                WHERE NOT (target)-[:SAME_AS|:MERGED_INTO]-(other)
                WITH target, other, type(r) as rel_type, properties(r) as rel_props
                CALL apoc.merge.relationship(target, rel_type, {}, rel_props, other, {}) YIELD rel
                RETURN count(rel) as transferred
                """,
                {"source_id": source_id, "target_id": target_id}
            )

            # Transfer incoming relationships
            await self.db.execute(
                """
                MATCH (other)-[r]->(source:Entity {canon_id: $source_id})
                MATCH (target:Entity {canon_id: $target_id})
                WHERE NOT (other)-[:SAME_AS|:MERGED_INTO]-(target)
                WITH target, other, type(r) as rel_type, properties(r) as rel_props
                CALL apoc.merge.relationship(other, rel_type, {}, rel_props, target, {}) YIELD rel
                RETURN count(rel) as transferred
                """,
                {"source_id": source_id, "target_id": target_id}
            )

        # Delete source entities
        await self.db.execute(
            """
            MATCH (e:Entity)
            WHERE e.canon_id IN $source_ids AND e.canon_id <> $target_id
            DETACH DELETE e
            """,
            {"source_ids": source_ids, "target_id": target_id}
        )

        return await self.get_by_id(target_id)

    async def add_director_note(self, canon_id: str, note: str) -> List[str]:
        """Add a director note to an entity."""
        result = await self.db.execute(
            """
            MATCH (e:Entity {canon_id: $canon_id})
            SET e.director_notes = COALESCE(e.director_notes, []) + [$note]
            RETURN e.director_notes as notes
            """,
            {"canon_id": canon_id, "note": note}
        )
        return result[0]["notes"] if result else []

    async def remove_director_note(self, canon_id: str, note_index: int) -> List[str]:
        """Remove a director note by index."""
        result = await self.db.execute(
            """
            MATCH (e:Entity {canon_id: $canon_id})
            WITH e, e.director_notes as notes
            WHERE notes IS NOT NULL AND size(notes) > $index
            SET e.director_notes = [i IN range(0, size(notes)-1) WHERE i <> $index | notes[i]]
            RETURN e.director_notes as notes
            """,
            {"canon_id": canon_id, "index": note_index}
        )
        return result[0]["notes"] if result else []

    async def get_director_notes(self, canon_id: str) -> List[str]:
        """Get all director notes for an entity."""
        result = await self.db.execute(
            """
            MATCH (e:Entity {canon_id: $canon_id})
            RETURN COALESCE(e.director_notes, []) as notes
            """,
            {"canon_id": canon_id}
        )
        return result[0]["notes"] if result else []
