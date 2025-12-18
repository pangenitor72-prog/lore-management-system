"""
Personality Pipeline Module
Stage 4 of the Smart Ingestor pipeline.

This module converts extracted personality cues into full OCEAN profiles
using the existing PersonalityGenerator in src.core.models.

It serves as the bridge between narrative text (traits) and psychological structure (OCEAN).
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict

from src.core.models import OCEANProfile, PersonalityGenerator, PersonalityTemplates
from src.ingestion.extractor import ExtractedProperties

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
        # Join traits into a readable phrase
        # e.g. "cunning, vengeful, and calculating"
        if len(traits) == 1:
            traits_str = traits[0]
        else:
            traits_str = ", ".join(traits[:-1]) + ", and " + traits[-1]
        
        personality_text_parts.append(f"The character is described as {traits_str}.")
        
    # Lightly include description if available, to give more context
    if props.description:
        # Truncate description to avoid noise if it's very long? 
        # For now, just include it. The generator (if it used LLM) would benefit.
        # But wait, PersonalityGenerator in src.core.models seems to be rule-based/random/archetype-based 
        # and doesn't actually have a `generate_from_text` method!
        
        # Checking src/core/models.py content from previous read_file...
        # It has `generate_random`, `generate_from_archetype`, `generate_from_role`.
        # It DOES NOT have `generate_from_text`.
        
        # The prompt says:
        # "Use: ocean: OCEANProfile = PersonalityGenerator.generate_from_text(personality_text)"
        
        # But the code I read in src/core/models.py DOES NOT HAVE THIS METHOD.
        # It only has:
        # - generate_random
        # - generate_from_archetype
        # - generate_from_role
        
        # I MUST implementing `generate_from_text`? 
        # The prompt says "Operate ONLY on: src/ingestion/personality_pipeline.py"
        # "Do NOT modify any other files."
        
        # This implies I cannot add `generate_from_text` to `PersonalityGenerator` in `src/core/models.py`.
        
        # However, the prompt might be assuming it exists or I should simulate it here?
        # "Use: ocean: OCEANProfile = PersonalityGenerator.generate_from_text(personality_text)"
        
        # If I strictly follow the prompt, I will get an AttributeError.
        
        # OPTION A: Implementing `generate_from_text` LOCALLY in this file as a helper or subclass?
        # OPTION B: Use `generate_from_role` if tags contain roles?
        
        # The prompt says: "This module MUST use: ... PersonalityGenerator... This ensures: No architectural drift"
        
        # The prompt seems to hallucinate that `generate_from_text` exists or expects me to map text to roles/archetypes.
        
        # Let's look at `ExtractedProperties`. It has `tags`. `tags` include roles.
        # `PersonalityGenerator.generate_from_role` exists.
        
        # If I cannot modify `src/core/models.py`, I must implement the logic here, possibly extending or just using available methods.
        
        # WAIT. The prompt says: "Use: ocean: OCEANProfile = PersonalityGenerator.generate_from_text(personality_text)"
        # Maybe I should just write the code as requested, and if it fails, I'll know?
        # But I see the file content, it's definitely missing.
        
        # Maybe the user *thinks* it exists?
        # Or maybe I am supposed to implement a local adaptation.
        
        # Let's try to infer OCEAN from traits mapping locally if `generate_from_text` is missing.
        # But the instructions are specific about using `PersonalityGenerator.generate_from_text`.
        
        # I will implement a local helper `_generate_from_text_heuristic` and call it, 
        # pretending it's the intended logic, or I can monkey-patch it? No, that's bad.
        
        # The safest bet is to implement the logic that *would* be in `generate_from_text` right here,
        # or map traits to roles if possible.
        
        # Actually, let's look at the "TRAIT_KEYWORDS" in detector.py again.
        # They map to "trait", "behavior", "emotion".
        
        # If I look at `PersonalityGenerator`, it is random or archetype based.
        
        # I will implement a local mapping function `_map_text_to_ocean` that mimics what `generate_from_text` would do,
        # utilizing `PersonalityGenerator` for the final object creation (validation etc).
        
        # BUT the prompt explicitly says: "Use: ocean: OCEANProfile = PersonalityGenerator.generate_from_text(personality_text)"
        
        # This is a dilemma. I will implement a valid workaround that respects the *intent*:
        # Convert text cues to OCEAN.
        
        # I'll define `generate_from_text` as a standalone function in this module if I can't add it to the class.
        pass

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

