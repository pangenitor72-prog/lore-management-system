"""
Neo4j Mapper — Stage 6 of Smart Ingestor.

Responsible for converting BuiltEntity instances into
Neo4j nodes and placeholder relationship edges using the safe driver wrapper.
"""

import logging
import uuid
import json
from typing import List, Dict, Any, Optional

from src.lms.db.neo4j_adapter import Neo4jDatabase
from src.lms.ingestion.entity_builder import BuiltEntity
from src.lms.core.models import OCEANProfile
from src.lms.core.normalization import normalize_entity_name

logger = logging.getLogger(__name__)

async def save_entity(neo4j_db: Neo4jDatabase, built: BuiltEntity) -> str:
    """
    Persist a single BuiltEntity to Neo4j.
    Returns the canonical entity ID.
    
    PHASE 1: Only saves the Entity node itself.
    Relationships are handled in Phase 2 via save_relationships.
    """
    entity = built.entity
    
    # Generate ID if not present
    name = entity.canonical_name
    entity_type = entity.entity_type.value
    
    # CANON RESOLUTION PHASE
    # Normalize name to prevent duplicates (e.g. "Lead Corps" vs "LeadCorps")
    normalized_name = normalize_entity_name(name)
    
    # 1. Check for existing entity by (type, normalized_name)
    existing_norm = await neo4j_db.execute(
        """
        MATCH (e:Entity {entity_type: $entity_type, normalized_name: $normalized_name})
        RETURN e.canon_id as canon_id
        LIMIT 1
        """,
        {"entity_type": entity_type, "normalized_name": normalized_name}
    )
    
    if existing_norm and len(existing_norm) > 0 and existing_norm[0].get("canon_id"):
        canon_id = existing_norm[0]["canon_id"]
        logger.info(f"Resolved existing canonical entity by normalized name: {name} -> {normalized_name} ({canon_id})")
    else:
        # 2. Legacy Fallback: Check by exact name if not found by normalized (handle pre-migration data)
        # This ensures we don't create a duplicate if the node exists but lacks 'normalized_name' property
        existing_legacy = await neo4j_db.execute(
            "MATCH (e:Entity {name: $name}) RETURN e.canon_id as canon_id LIMIT 1",
            {"name": name}
        )
        
        if existing_legacy and len(existing_legacy) > 0 and existing_legacy[0].get("canon_id"):
            canon_id = existing_legacy[0]["canon_id"]
            logger.info(f"Resolved existing canonical entity by legacy name match: {name} ({canon_id})")
        else:
            canon_id = str(uuid.uuid4())
    
    # Prepare properties
    description = entity.approved_fields.get("description", "")
    tags = entity.approved_fields.get("tags", [])
    aliases = entity.aliases
    
    # OCEAN Profile
    ocean_profile: OCEANProfile = entity.approved_fields.get("ocean_profile")
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
        ocean_props = {
            "openness": None,
            "conscientiousness": None,
            "extraversion": None,
            "agreeableness": None,
            "neuroticism": None
        }

    # Sanitize label
    safe_label = entity_type if entity_type.isalnum() else "Entity"
    
    query = f"""
    MERGE (e:Entity {{canon_id: $canon_id}})
    SET e:{safe_label}
    SET
        e.name = $name,
        e.normalized_name = $normalized_name,
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
    RETURN e.canon_id
    """
    
    params = {
        "canon_id": canon_id,
        "name": name,
        "normalized_name": normalized_name,
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
        logger.debug(f"Saved entity: {name} ({entity_type}) -> {canon_id}")
    except Exception as e:
        logger.error(f"Failed to save entity {name}: {e}")
        raise e
            
    return canon_id

async def resolve_target_canon_id(neo4j_db: Neo4jDatabase, target_name: str, name_map: Dict[str, str]) -> Optional[str]:
    """
    Resolve a target entity's canon_id.
    1. Check local batch map (name -> canon_id)
    2. Check Neo4j DB (Normalized -> Name)
    3. If missing, create placeholder and return new canon_id
    """
    # 1. Local batch lookup
    if target_name in name_map:
        return name_map[target_name]
        
    # 2. Database lookup
    normalized_target = normalize_entity_name(target_name)
    
    # Check by normalized_name
    query = "MATCH (e:Entity {normalized_name: $normalized_name}) RETURN e.canon_id as canon_id LIMIT 1"
    result = await neo4j_db.execute(query, {"normalized_name": normalized_target})
    if result and result[0].get("canon_id"):
        return result[0]["canon_id"]

    # Legacy Fallback: Check by exact name
    query_legacy = "MATCH (e:Entity {name: $name}) RETURN e.canon_id as canon_id LIMIT 1"
    result_legacy = await neo4j_db.execute(query_legacy, {"name": target_name})
    if result_legacy and result_legacy[0].get("canon_id"):
        return result_legacy[0]["canon_id"]
        
    # 3. Create placeholder
    # Ensure we use normalized_name in creation to prevent future duplicates
    new_canon_id = str(uuid.uuid4())
    create_query = """
    MERGE (e:Entity {normalized_name: $normalized_name})
    ON CREATE SET 
        e.name = $name,
        e.entity_type = 'unknown', 
        e.canon_id = $canon_id,
        e.created_at = datetime()
    RETURN e.canon_id
    """
    try:
        await neo4j_db.execute(create_query, {
            "name": target_name, 
            "normalized_name": normalized_target,
            "canon_id": new_canon_id
        })
        logger.debug(f"Created placeholder target: {target_name} ({new_canon_id})")
        return new_canon_id
    except Exception as e:
        logger.error(f"Failed to create placeholder for {target_name}: {e}")
        return None

async def save_relationships(
    neo4j_db: Neo4jDatabase, 
    built: BuiltEntity, 
    source_canon_id: str,
    name_map: Dict[str, str]
):
    """
    PHASE 2: Persist relationships for an entity.
    """
    if not built.relationship_candidates:
        return

    explicit_rels = []
    candidates = []
    
    for rc in built.relationship_candidates:
        if rc.get("is_explicit"):
            explicit_rels.append(rc)
        else:
            candidates.append(rc)
            
    # 1. Save Relationship Candidates (Unverified edges)
    if candidates:
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
        
        formatted_rels = []
        for rc in candidates:
            formatted_rels.append({
                "source": rc.get("source"),
                "target": rc.get("target"),
                "type": rc.get("relationship_type")
            })
            
        try:
            await neo4j_db.execute(rel_query, {"origin_id": source_canon_id, "rels": formatted_rels})
            logger.debug(f"Saved {len(formatted_rels)} relationship candidates for {source_canon_id}")
        except Exception as e:
            logger.error(f"Failed to save relationship candidates for {source_canon_id}: {e}")

    # 2. Save Explicit Relationships (Verified edges)
    # Uses MATCH on source and target canon_id to ensure clean graph
    for rel in explicit_rels:
        rel_type = rel.get("relationship_type")
        target_name = rel.get("target")
        
        # Sanitize rel_type
        if not rel_type or not rel_type.replace("_", "").isalnum():
            continue
            
        target_canon_id = await resolve_target_canon_id(neo4j_db, target_name, name_map)
        if not target_canon_id:
            logger.warning(f"Skipping relationship {rel_type} to {target_name}: Could not resolve target ID")
            continue
            
        query = f"""
        MATCH (source:Entity {{canon_id: $source_canon_id}})
        MATCH (target:Entity {{canon_id: $target_canon_id}})
        MERGE (source)-[:{rel_type}]->(target)
        """
        
        try:
            await neo4j_db.execute(query, {
                "source_canon_id": source_canon_id,
                "target_canon_id": target_canon_id
            })
            logger.debug(f"Created explicit relationship {rel_type} -> {target_name} ({target_canon_id})")
        except Exception as e:
            logger.error(f"Failed to create explicit relationship {rel_type}: {e}")

async def save_many(neo4j_db: Neo4jDatabase, entities: List[BuiltEntity]) -> List[str]:
    """
    Persist multiple BuiltEntity objects in two phases.
    Phase 1: Save all entities nodes.
    Phase 2: Save all relationships (linking standard entities).
    """
    ids = []
    # Map entity name -> canon_id for this batch
    batch_name_map: Dict[str, str] = {}
    
    # --- Phase 1: Entities ---
    logger.info("Starting Phase 1: Entity Persistence")
    for built in entities:
        try:
            eid = await save_entity(neo4j_db, built)
            ids.append(eid)
            # Store name mapping for Phase 2
            batch_name_map[built.entity.canonical_name] = eid
            for alias in built.entity.aliases:
                batch_name_map[alias] = eid
        except Exception as e:
            logger.error(f"Error in save_many Phase 1: {e}")
            continue
            
    # --- Phase 2: Relationships ---
    logger.info("Starting Phase 2: Relationship Persistence")
    for built in entities:
        try:
            # We need the source canon_id
            # It should be in our map (unless save failed)
            source_name = built.entity.canonical_name
            if source_name not in batch_name_map:
                continue
                
            source_canon_id = batch_name_map[source_name]
            await save_relationships(neo4j_db, built, source_canon_id, batch_name_map)
            
        except Exception as e:
            logger.error(f"Error in save_many Phase 2: {e}")
            continue

    return ids
