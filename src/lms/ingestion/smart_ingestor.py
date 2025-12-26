"""
Smart Ingestor Orchestrator — Stage 7 of LMS/MANTLE ingestion pipeline.

Coordinates all stages:
segment -> detect -> extract -> personality -> build -> write
"""

import logging
import os
from typing import Dict, Any, List

from src.lms.db.neo4j_adapter import Neo4jDatabase

from .segmenter import segment_text
from .detector import detect_many
from .extractor import extract_many
from .personality_pipeline import generate_many
from .entity_builder import build_many
from .neo4j_mapper import save_many
from src.lms.ingestion.personality_drift import PersonalityDriftEngine
from src.lms.ingestion.relationship_inference import RelationshipInferenceEngine

logger = logging.getLogger(__name__)

async def ingest_text(raw_text: str, neo4j_db: Neo4jDatabase) -> Dict[str, Any]:
    """
    Full ingestion pipeline for raw text.
    Returns structured debug info:
    - segments
    - detected entities
    - extracted properties
    - IDs of created entities
    """
    if not raw_text or not raw_text.strip():
        logger.warning("Empty text provided to ingest_text.")
        return {
            "segments": [],
            "detected": [],
            "extracted": [],
            "entity_ids": []
        }
        
    logger.info("Starting ingestion pipeline.")
    
    # 1. Segment
    segments = segment_text(raw_text)
    logger.debug(f"Stage 1: Segmented into {len(segments)} blocks.")
    
    # 2. Detect
    detection_results = detect_many(segments)
    logger.debug(f"Stage 2: Detected lore in {len(detection_results)} blocks.")
    
    # 3. Extract
    extracted = extract_many(detection_results)
    logger.debug(f"Stage 3: Extracted properties for {len(extracted)} entities.")
    
    # 4. Personality
    personalities = generate_many(extracted)
    logger.debug(f"Stage 4: Generated personality profiles.")
    
    # 5. Build Entities
    built_entities = build_many(extracted, personalities)
    logger.debug(f"Stage 5: Built {len(built_entities)} canonical entities.")

    # Apply Personality Drift
    drift_engine = PersonalityDriftEngine()
    # Note: In a real system, trait_occurrences would be fetched from a persistent memory store.
    # For now, we simulate tracking within this batch or initialize empty.
    trait_occurrences = {}
    
    # Initialize Relationship Inference Engine
    rel_engine = RelationshipInferenceEngine()

    for built in built_entities:
        entity = built.entity
        # Check if it has personality data
        if "ocean_profile" in entity.approved_fields:
            ocean_profile = entity.approved_fields["ocean_profile"]
            
            # Detect traits in description
            description = entity.approved_fields.get("description", "")
            trait_terms = drift_engine.detect_trait_terms(description)
            
            if trait_terms:
                # Update local occurrences (simulation)
                for t in trait_terms:
                    trait_occurrences[t] = trait_occurrences.get(t, 0) + 1
                    
                drift = drift_engine.compute_drift(
                    trait_terms,
                    occurrences=max([trait_occurrences[t] for t in trait_terms]),
                    text=description
                )
                
                if drift.applied:
                    # Convert OCEAN object to dict for modification (or modify object directly if mutable)
                    # OCEANProfile is Pydantic, so it has dict-like access or fields
                    # We need to map OCEANProfile to the Dict[str, float] expected by apply_drift
                    ocean_dict = {
                        "openness": ocean_profile.openness,
                        "conscientiousness": ocean_profile.conscientiousness,
                        "extraversion": ocean_profile.extraversion,
                        "agreeableness": ocean_profile.agreeableness,
                        "neuroticism": ocean_profile.neuroticism
                    }
                    
                    updated_ocean_dict = drift_engine.apply_drift(ocean_dict, drift.deltas)
                    
                    # Update the profile
                    entity.approved_fields["ocean_profile"] = ocean_profile.model_copy(update=updated_ocean_dict)
                    logger.debug(f"Applied personality drift to {entity.canonical_name}: {drift.deltas}")

        # Relationship Inference Integration
        # We need an ID for the entity to associate relationships.
        # However, save_entity generates the ID later.
        # The prompt implies we have an ID or generates one.
        # But 'built.entity' is EntityCreate, it doesn't have an ID yet.
        # The prompt says: "origin_entity_id=current_entity['id']"
        
        # NOTE: The provided snippet assumes we have an ID.
        # In our current pipeline, IDs are generated in `neo4j_mapper.save_entity`.
        # To make this work, we should probably generate UUIDs earlier in `entity_builder` 
        # OR run inference *inside* `save_many` or `save_entity`.
        
        # BUT the prompt instructs to modify `smart_ingestor.py`.
        # AND it says: "Then inside your entity-parsing block... add..."
        
        # To support this properly without breaking the existing flow where ID is generated at save:
        # We should generate the ID *here* (or in builder) and attach it to the entity object 
        # so we can use it for relationship inference immediately.
        
        # EntityCreate doesn't have an 'id' field.
        # But we can stash it in `approved_fields` or similar? Or just hold it in a parallel list?
        # Or, we modify `BuiltEntity` to include `temp_id`?
        
        # Let's generate a temporary ID here if one isn't available, and assume `save_entity` will use/respect it 
        # if we pass it, or we rely on `neo4j_mapper` to handle the final write.
        
        # Actually, the snippet:
        # self.neo4j.create_relationship_candidate(...)
        # implies we are calling the DB directly here?
        # But `smart_ingestor` is async and `save_many` handles DB writes.
        # The prompt says: "Store as RelationshipCandidate nodes in Neo4j" via "self.neo4j.create_relationship_candidate"
        
        # Wait, the prompt assumes `self.neo4j` exists on `SmartIngestor` class?
        # But `ingest_text` is a standalone function, not a class method in my implementation!
        # My `ingest_text` takes `neo4j_db` as arg.
        
        # Also, `save_many` is where Neo4j writes happen.
        # If I infer relationships here, I should add them to `built.relationship_candidates`.
        # That keeps the architecture clean (Builder -> Mapper).
        
        # The prompt says: "Store as RelationshipCandidate nodes in Neo4j self.neo4j.create_relationship_candidate(...)"
        # This conflicts slightly with my "Task 6" `save_many` pattern which batch saves.
        # However, I can ADAPT the snippet to fit my architecture:
        # 1. Infer relationships.
        # 2. Add them to `built.relationship_candidates`.
        # 3. Let `save_many` persist them as before.
        
        # This is safer and cleaner than adding direct DB calls in the middle of the ingestor logic.
        
        description = entity.approved_fields.get("description", "")
        if description:
            # We don't have a permanent ID yet. 
            # But `BuiltEntity` separates entity creation from relationship creation.
            # `save_entity` in `neo4j_mapper` generates the ID.
            
            # If I add to `built.relationship_candidates`, `save_entity` will process them.
            # `save_entity` uses `entity_id` (generated there) as `origin_entity_id`.
            # So I don't need the ID here! I just need to pass the candidate.
            
            inferred_rels = rel_engine.infer(
                description, 
                origin_entity_name=entity.canonical_name,
                origin_entity_id="PENDING" # Placeholder, ignored by save_entity which uses actual ID
            )
            
            for rel in inferred_rels:
                # Add to the built entity's candidates list
                built.relationship_candidates.append({
                    "source": None, # Implicit source
                    "target": rel.target_name,
                    "relationship_type": rel.relationship_type,
                    "confidence": rel.confidence,
                    "sentence": rel.sentence
                })

    # 6. Save to Neo4j
    ids = await save_many(neo4j_db, built_entities)
    logger.info(f"Stage 6: Persisted {len(ids)} entities to Neo4j.")
    
    return {
        "segments": segments,
        "detected": detection_results,
        "extracted": extracted,
        "entity_ids": ids
    }

async def ingest_file(file_path: str, neo4j_db: Neo4jDatabase) -> Dict[str, Any]:
    """
    Load a file from disk (.txt, .md, .pdf if already converted),
    then call ingest_text.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {}
        
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw_text = f.read()
            
        logger.info(f"Read file {file_path}, size: {len(raw_text)} chars.")
        return await ingest_text(raw_text, neo4j_db)
        
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        return {}

