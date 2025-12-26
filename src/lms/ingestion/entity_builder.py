"""
Entity Builder Module
Stage 5 of the Smart Ingestor pipeline.

This module is responsible for assembling canonical EntityCreate objects
from ExtractedProperties and PersonalityOutput. It serves as the final
assembly step before persistence.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from src.lms.core.models import (
    EntityCreate, EntityType, OCEANProfile, 
    ApprovalStatus, ConfidenceLevel, PartyKnowledge
)
from .extractor import ExtractedProperties
from .personality_pipeline import PersonalityOutput

logger = logging.getLogger(__name__)

@dataclass
class BuiltEntity:
    entity: EntityCreate
    relationship_candidates: List[Dict[str, Any]]

def _map_entity_type(raw_type: Optional[str]) -> EntityType:
    """
    Map raw entity type string to EntityType enum.
    """
    if not raw_type:
        return EntityType.CONCEPT # Fallback
        
    raw_lower = raw_type.lower()
    
    if "character" in raw_lower:
        return EntityType.CHARACTER
    elif "location" in raw_lower:
        return EntityType.LOCATION
    elif "faction" in raw_lower:
        return EntityType.FACTION
    elif "event" in raw_lower:
        return EntityType.EVENT
    elif "item" in raw_lower:
        return EntityType.ITEM
    elif "concept" in raw_lower:
        return EntityType.CONCEPT
        
    return EntityType.CONCEPT # Safe default

def build_entity(
    props: ExtractedProperties,
    personality: PersonalityOutput
) -> BuiltEntity:
    """
    Assemble a single EntityCreate instance and associated relationship candidates
    from extracted properties and a generated personality profile.
    """
    
    # 1. Determine Name
    name = props.name
    if not name:
        # Fallback to alias if available
        if props.aliases:
            name = props.aliases[0]
        else:
            # Fallback to truncated description (very rough)
            # Or just "Unknown Entity"
            if props.description:
                # Take first few words
                words = props.description.split()
                name = " ".join(words[:5]) + "..." if words else "Unknown Entity"
            else:
                name = "Unknown Entity"
                
    # 2. Determine Entity Type
    entity_type = _map_entity_type(props.entity_type)
    
    # 3. Prepare Approved Fields
    # The EntityCreate model has `approved_fields: Dict[str, Any]`.
    # We can put extra data there, or maybe 'description' goes there if it's not a top-level field?
    # Checking src/core/models.py:
    # EntityCreate has:
    # - entity_type: EntityType
    # - canonical_name: str
    # - aliases: List[str]
    # - approved_fields: Dict[str, Any]
    # - approval_status: ApprovalStatus
    # - confidence_level: ConfidenceLevel
    # - party_knowledge: PartyKnowledge
    
    # It DOES NOT have 'description', 'tags', 'traits' at top level!
    # So we must put them in `approved_fields`.
    
    approved_fields = {
        "description": props.description,
        "tags": props.tags,
        "traits": props.traits,
        "temporal_cues": props.temporal_cues
    }
    
    # Add personality if it exists and entity type supports it (Characters)
    if entity_type == EntityType.CHARACTER and personality.ocean:
        approved_fields["ocean_profile"] = personality.ocean
        # Note: We store the object itself. The Pydantic model uses Dict[str, Any] so it should be fine,
        # but serialization might need care later.
    
    # 4. Construct EntityCreate
    entity = EntityCreate(
        entity_type=entity_type,
        canonical_name=name,
        aliases=props.aliases,
        approved_fields=approved_fields,
        approval_status=ApprovalStatus.PENDING,
        confidence_level=ConfidenceLevel.UNCERTAIN, # Ingested data is uncertain by default
        party_knowledge=PartyKnowledge.RUMORED # Default for new ingestion
    )
    
    logger.debug(f"Built entity: {name} ({entity_type})")
    
    return BuiltEntity(
        entity=entity,
        relationship_candidates=props.relationship_candidates
    )

def build_many(
    props_list: List[ExtractedProperties],
    personalities: List[PersonalityOutput]
) -> List[BuiltEntity]:
    """
    Batch builder. Pairwise zips props_list and personalities by index.
    """
    built_entities = []
    
    # Zip and ignore mismatches
    for props, person in zip(props_list, personalities):
        built_entities.append(build_entity(props, person))
        
    return built_entities

