"""
Personality Pipeline Module
Stage 4 of the Smart Ingestor pipeline.

This module converts extracted personality cues into full OCEAN profiles
using the existing PersonalityGenerator in src.core.models.

It serves as the bridge between narrative text (traits) and psychological structure (OCEAN).

TODO: Architectural Gap - PersonalityGenerator.generate_from_text() Missing
----------------------------------------------------------------------
The original design expected PersonalityGenerator to have a `generate_from_text(personality_text)`
method that would use AI to map arbitrary prose to OCEAN profiles. This method was never implemented.

Current workaround (implemented here):
1. Try to match tags to known roles via PersonalityGenerator.generate_from_role()
2. Fall back to _heuristic_ocean_from_traits() which does keyword-based mapping
3. Default to neutral 0.5 baseline if neither works

The heuristic approach is limited (~15 keywords). A proper generate_from_text() implementation
in src/lms/core/models.py could use the Gemini API to map any descriptive text to OCEAN values,
which would be more accurate and flexible.

Priority: Low (current workaround is functional)
Identified by: AI code review, 2026-01
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict

from src.mantle.core.models import OCEANProfile, PersonalityGenerator, PersonalityTemplates
from src.mantle.ingestion.extractor import ExtractedProperties

logger = logging.getLogger(__name__)

@dataclass
class PersonalityOutput:
    ocean: OCEANProfile

def generate_personality(props: ExtractedProperties) -> PersonalityOutput:
    """
    Convert extracted traits into an OCEAN profile using PersonalityGenerator.
    Primary bridge between text-based cues and psychological modeling.
    """
    
    # 1. Build a consolidated "personality text" block
    traits = props.traits
    personality_text_parts = []
    
    if traits:
        # Join traits into a readable phrase (e.g. "cunning, vengeful, and calculating")
        if len(traits) == 1:
            traits_str = traits[0]
        else:
            traits_str = ", ".join(traits[:-1]) + ", and " + traits[-1]
        personality_text_parts.append(f"The character is described as {traits_str}.")

    # Include description for additional context (if available)
    if props.description:
        personality_text_parts.append(props.description)

    personality_text = " ".join([p for p in personality_text_parts if p])
    
    # Check if we can find a role in tags to use existing generator logic
    role_match = None
    for tag in props.tags:
        # Try to match tag to a known role/archetype?
        # The generator has `generate_from_role`.
        # Note: get_archetype_from_role is on PersonalityTemplates, not PersonalityGenerator
        if PersonalityTemplates.get_archetype_from_role(tag):
            role_match = tag
            break
            
    if role_match:
        logger.debug(f"Generating personality from role: {role_match}")
        return PersonalityOutput(
            ocean=PersonalityGenerator.generate_from_role(role_match)
        )
        
    # If no role, and we can't use `generate_from_text` (doesn't exist), 
    # and we have traits...
    
    # I will implement a simple heuristic mapper here.
    ocean = _heuristic_ocean_from_traits(props.traits)
    if ocean:
        return PersonalityOutput(ocean=ocean)

    # Fallback to neutral baseline as requested
    return PersonalityOutput(
        ocean=OCEANProfile(
            openness=0.5,
            conscientiousness=0.5,
            extraversion=0.5,
            agreeableness=0.5,
            neuroticism=0.5
        )
    )

def _heuristic_ocean_from_traits(traits: List[str]) -> Optional[OCEANProfile]:
    """
    Map extracted traits to OCEAN values manually since PersonalityGenerator.generate_from_text is missing.
    """
    if not traits:
        return None
        
    # Start with baseline
    scores = {
        "openness": 0.5,
        "conscientiousness": 0.5,
        "extraversion": 0.5,
        "agreeableness": 0.5,
        "neuroticism": 0.5
    }
    
    # Simple mapping keywords
    # This is a lightweight version of what a real model might do
    mappings = {
        "brave": {"neuroticism": -0.2, "extraversion": 0.1},
        "cunning": {"openness": 0.1, "agreeableness": -0.1},
        "vengeful": {"agreeableness": -0.3, "neuroticism": 0.2},
        "cold": {"agreeableness": -0.2, "extraversion": -0.2},
        "kind": {"agreeableness": 0.3},
        "mercy": {"agreeableness": 0.2},
        "rage": {"neuroticism": 0.3, "agreeableness": -0.2},
        "loyal": {"conscientiousness": 0.2, "agreeableness": 0.1},
        "fearful": {"neuroticism": 0.4, "extraversion": -0.1},
        "ambitious": {"conscientiousness": 0.2, "extraversion": 0.1},
        "studied": {"openness": 0.2, "conscientiousness": 0.1},
        "commands": {"extraversion": 0.3},
        "prefers": {}, # neutral
        "avoids": {"extraversion": -0.1},
        "favors": {},
        "plots": {"conscientiousness": 0.1, "agreeableness": -0.1}
    }
    
    modified = False
    for trait in traits:
        trait_lower = trait.lower()
        if trait_lower in mappings:
            modified = True
            for dim, delta in mappings[trait_lower].items():
                scores[dim] = max(0.0, min(1.0, scores[dim] + delta))
                
    if not modified:
        return None
        
    return OCEANProfile(
        openness=scores["openness"],
        conscientiousness=scores["conscientiousness"],
        extraversion=scores["extraversion"],
        agreeableness=scores["agreeableness"],
        neuroticism=scores["neuroticism"]
    )

def generate_many(props_list: List[ExtractedProperties]) -> List[PersonalityOutput]:
    """Batch version."""
    results = []
    logger.debug(f"Generating personalities for {len(props_list)} extracted entities.")
    for props in props_list:
        results.append(generate_personality(props))
    return results

