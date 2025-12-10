"""
Neo4j Mapper — Stage 6 of Smart Ingestor.

Responsible for converting BuiltEntity instances into
Neo4j nodes and placeholder relationship edges using the safe driver wrapper.
"""

import logging
import uuid
import json
from typing import List, Dict, Any

from src.db.neo4j_adapter import Neo4jDatabase
from src.ingestion.entity_builder import BuiltEntity
from src.core.models import OCEANProfile

logger = logging.getLogger(__name__)

async def save_entity(neo4j_db: Neo4jDatabase, built: BuiltEntity) -> str:
    """
    Persist a single BuiltEntity to Neo4j.
    Returns the canonical entity ID.
    """
    entity = built.entity
    
    # Generate ID if not present (EntityCreate usually doesn't have an ID field, EntityResponse does)
    # The prompt implies we generate it here if needed.
    # We will use this ID for the node.
    entity_id = str(uuid.uuid4())
    
    # Prepare properties
    # Extract fields from EntityCreate and its approved_fields
    
    # Base fields
    name = entity.canonical_name
    entity_type = entity.entity_type.value
    
    # Fields from approved_fields
    description = entity.approved_fields.get("description", "")
    tags = entity.approved_fields.get("tags", [])
    aliases = entity.aliases
    
    # OCEAN Profile
    ocean_profile: OCEANProfile = entity.approved_fields.get("ocean_profile")
    
    # Flatten OCEAN if present
    ocean_props = {}
    if ocean_profile:
        ocean_props = {
            "openness": float(ocean_profile.openness),
            "conscientiousness": float(ocean_profile.conscientiousness),
            "extraversion": float(ocean_profile.extraversion),
            "agreeableness": float(ocean_profile.agreeableness),
            "neuroticism": float(ocean_profile.neuroticism)
        }
    else:
        # Default nulls? Or just don't set them?
        # Cypher MERGE with defaults is cleaner if we want consistent schema, 
        # but let's leave them null if not applicable (e.g. Items)
        ocean_props = {
            "openness": None,
            "conscientiousness": None,
            "extraversion": None,
            "agreeableness": None,
            "neuroticism": None
        }

    # Construct Cypher
    # Note: We use dynamic labels carefully or just a generic :Entity label + type property?
    # Prompt says: "MERGE (e:Entity {id: $id}) ... e.entity_type = $entity_type"
    # It also says: "entity_type -> must become a label or property depending on your schema"
    # Using specific labels is better for Neo4j performance, but :Entity generic label is safer for generalized code.
    # Let's add BOTH: :Entity AND the specific type label (sanitized).
    
    # Sanitize label from entity_type (e.g. "Character" -> :Character)
    # EntityType enum values are PascalCase usually ("Character", "Location")
    safe_label = entity_type if entity_type.isalnum() else "Entity"
    
    query = f"""
    MERGE (e:Entity {{id: $id}})
    SET e:{safe_label}
    SET
        e.name = $name,
        e.description = $description,
        e.entity_type = $entity_type,
        e.tags = $tags,
        e.aliases = $aliases,
        e.approval_status = $approval_status,
        e.confidence_level = $confidence_level,
        e.party_knowledge = $party_knowledge,
        e.last_updated = datetime(),
        e.openness = $openness,
        e.conscientiousness = $conscientiousness,
        e.extraversion = $extraversion,
        e.agreeableness = $agreeableness,
        e.neuroticism = $neuroticism
    RETURN e.id
    """
    
    params = {
        "id": entity_id,
        "name": name,
        "description": description,
        "entity_type": entity_type,
        "tags": tags,
        "aliases": aliases,
        "approval_status": entity.approval_status.value,
        "confidence_level": entity.confidence_level.value,
        "party_knowledge": entity.party_knowledge.value,
        **ocean_props
    }
    
    try:
        await neo4j_db.execute(query, params)
        logger.debug(f"Saved entity: {name} ({entity_type}) -> {entity_id}")
    except Exception as e:
        logger.error(f"Failed to save entity {name}: {e}")
        # Re-raise? Or return None? Prompt says "safe async adapter", implies robustness.
        # But if we fail to save the entity, we can't save relationships attached to it properly.
        raise e

    # Handle Relationship Candidates
    # "Do NOT attempt entity resolution — only create placeholder edges."
    # "MERGE (r:RelationshipCandidate ...)"
    
    if built.relationship_candidates:
        rel_query = """
        UNWIND $rels AS rel
        MERGE (r:RelationshipCandidate {
            origin_entity_id: $origin_id,
            target_name: rel.target,
            relationship_type: rel.type
        })
        SET 
            r.source_name = rel.source,
            r.created_at = datetime()
        """
        
        # Prepare rel params
        # built.relationship_candidates is List[Dict] with keys: source, target, relationship_type
        # We need to map them to the structure expected by UNWIND or loop.
        
        formatted_rels = []
        for rc in built.relationship_candidates:
            # Flatten/Clean
            formatted_rels.append({
                "source": rc.get("source"), # Might be None
                "target": rc.get("target"),
                "type": rc.get("relationship_type")
            })
            
        rel_params = {
            "origin_id": entity_id,
            "rels": formatted_rels
        }
        
        try:
            await neo4j_db.execute(rel_query, rel_params)
            logger.debug(f"Saved {len(formatted_rels)} relationship candidates for {entity_id}")
        except Exception as e:
            logger.error(f"Failed to save relationship candidates for {entity_id}: {e}")
            # Don't fail the whole entity save just for candidates
            pass
            
    return entity_id

async def save_many(neo4j_db: Neo4jDatabase, entities: List[BuiltEntity]) -> List[str]:
    """
    Persist multiple BuiltEntity objects, returning a list of IDs.
    """
    ids = []
    for built in entities:
        try:
            eid = await save_entity(neo4j_db, built)
            ids.append(eid)
        except Exception as e:
            logger.error(f"Error in save_many loop: {e}")
            # Continue to next
            continue
            
    return ids

