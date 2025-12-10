"""
Lore Detector Module
Stage 2 of the Smart Ingestor pipeline.

This module analyzes cleaned text segments to determine WHAT they are about.
It uses deterministic, rule-based heuristics to identify:
- Entity Types (Character, Location, Item, Event, Faction)
- Relationships
- Temporal Cues
- Personality/Behavioral Cues

This module is NOT an AI model. It is a lightweight classification step.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

# --- Dataclasses ---

@dataclass
class DetectedEntity:
    type: str            # "character", "location", etc.
    name: Optional[str] = None  # if detected

@dataclass
class DetectedRelationship:
    source: Optional[str]      # entity acting (usually implicit in segment, or None)
    target: Optional[str]      # entity being referenced
    relationship_type: str     # e.g., "ally", "enemy", "serves", "member_of"

@dataclass
class TemporalCue:
    text: str
    cue_type: str              # "before", "after", "during", etc.

@dataclass
class TraitCue:
    text: str
    category: str              # e.g., "emotion", "behavior", "trait"

@dataclass
class LoreDetectionResult:
    segment: str
    entity: Optional[DetectedEntity]
    relationships: List[DetectedRelationship] = field(default_factory=list)
    temporal_cues: List[TemporalCue] = field(default_factory=list)
    trait_cues: List[TraitCue] = field(default_factory=list)

# --- Constants & Patterns ---

ENTITY_KEYWORDS = {
    "CHARACTER": [
        r"\bborn\b", r"\bson of\b", r"\bdaughter of\b", r"\bserveds? under\b", 
        r"\bhe\b", r"\bshe\b", r"\bhim\b", r"\bher\b", r"\bhis\b", r"\bhers\b"
    ],
    "LOCATION": [
        r"\bvillage of\b", r"\bcity of\b", r"\bthe ruins of\b", r"\bfortress\b", 
        r"\btower\b", r"\bforest of\b", r"\bkingdom\b", r"\bprovince\b"
    ],
    "ITEM": [
        r"\bartifact\b", r"\bblade\b", r"\brelic\b", r"\bamulet\b", 
        r"\btome\b", r"\bsword of\b", r"\bweapon\b", r"\bshield\b"
    ],
    "EVENT": [
        r"\bbattle of\b", r"\bsiege of\b", r"\brebellion\b", r"\buprising\b", 
        r"\byear \d+\b", r"\bwar of\b"
    ],
    "FACTION": [
        r"\bclan\b", r"\bhouse\b", r"\border of\b", r"\bguild\b", 
        r"\bfaction\b", r"\btribe\b"
    ]
}

RELATIONSHIP_PATTERNS = [
    (r"served under ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "served_under"),
    (r"allied with ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "ally"),
    (r"enemy of ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "enemy"),
    (r"member of (?:the )?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "member_of"),
    (r"belongs to (?:the )?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "member_of"),
    (r"sworn to ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "sworn_to"),
]

TEMPORAL_KEYWORDS = [
    (r"\bbefore\b", "before"),
    (r"\bafter\b", "after"),
    (r"\bduring\b", "during"),
    (r"\bat the time of\b", "concurrent"),
    (r"\bthree years later\b", "relative_future"), # broad match below
    (r"\byears? later\b", "relative_future"),
    (r"\byears? before\b", "relative_past"),
    (r"\bin the year\b", "absolute"),
    (r"\bwhen\b", "conditional")
]

TRAIT_KEYWORDS = {
    "trait": [
        r"\bbrave\b", r"\bcunning\b", r"\bvengeful\b", r"\bcold\b", 
        r"\bkind\b", r"\bmercy\b", r"\bloyal\b", r"\bfearful\b", r"\bambitious\b"
    ],
    "behavior": [
        r"\bstudied\b", r"\bcommands\b", r"\bprefers\b", r"\bavoids\b", 
        r"\bfavors\b", r"\bplots\b"
    ],
    "emotion": [
        r"\brage\b", r"\bfear\b", r"\bhate\b", r"\blove\b"
    ]
}

# --- Internal Helper Functions ---

def _detect_entity_type(segment: str) -> str:
    """
    Determine the primary entity type of the segment based on keyword frequency.
    Returns: "character", "location", "item", "event", "faction", or "unknown".
    """
    segment_lower = segment.lower()
    scores = {k: 0 for k in ENTITY_KEYWORDS}
    
    for category, patterns in ENTITY_KEYWORDS.items():
        for pattern in patterns:
            # Simple containment or regex check. Using regex for word boundaries.
            if re.search(pattern, segment_lower):
                scores[category] += 1
                
    # Determine winner
    # Logic: If max score is 0, return UNKNOWN.
    # If multiple have the same max score, prioritize specific order: 
    # EVENT > FACTION > LOCATION > ITEM > CHARACTER (Character is often a fallback with pronouns)
    # The prompt says: "Choose the most specific rule match." - this is subjective but strict ordering helps.
    
    max_score = 0
    best_category = "UNKNOWN"
    
    # Priority order for ties (reverse of checking order if we just use > max_score)
    # Let's iterate in priority order and update if strictly greater than current max? 
    # Or just iterate all and find absolute max.
    
    # Let's check pure counts first.
    if not any(scores.values()):
        return "unknown"

    # Sort categories by count (desc) then by priority (arbitrary logic for "specificity")
    # Let's define specificity weight: EVENT/LOCATION/ITEM/FACTION > CHARACTER (pronouns are noisy)
    
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    top_score = sorted_cats[0][1]
    candidates = [cat for cat, score in sorted_cats if score == top_score]
    
    if len(candidates) == 1:
        return candidates[0].lower()
    
    # Tie-breaking rules
    if "EVENT" in candidates: return "event"
    if "FACTION" in candidates: return "faction"
    if "LOCATION" in candidates: return "location"
    if "ITEM" in candidates: return "item"
    if "CHARACTER" in candidates: return "character"
    
    return "unknown"

def _extract_name_heuristic(segment: str, entity_type: str) -> Optional[str]:
    """
    Simple heuristic to guess a name based on entity type. 
    VERY rough, as Extractor is responsible for this. 
    Just trying to find a capitalized phrase near the start or near keywords if possible.
    """
    # For now, we won't implement complex name extraction as the prompt implies 
    # the Extractor does this. The prompt asks for "name (optional) # if detected".
    # We will leave it None for safety unless obvious pattern matches.
    # The prompt says "Do not attempt to resolve canonical entity names (Extractor does that later)."
    # However, DetectedEntity has a name field. We'll leave it None to avoid noise.
    return None

def _detect_relationships(segment: str) -> List[DetectedRelationship]:
    """
    Detect relationships using regex patterns.
    """
    relationships = []
    for pattern, rel_type in RELATIONSHIP_PATTERNS:
        matches = re.finditer(pattern, segment)
        for match in matches:
            target = match.group(1).strip()
            # Simple cleanup of target (remove trailing punctuation if captured)
            target = target.strip(".,;:!?")
            relationships.append(DetectedRelationship(
                source=None, # Source is usually the subject of the segment, detected later
                target=target,
                relationship_type=rel_type
            ))
    return relationships

def _detect_temporal_cues(segment: str) -> List[TemporalCue]:
    """
    Detect temporal cues using keywords.
    """
    cues = []
    segment_lower = segment.lower()
    for pattern, cue_type in TEMPORAL_KEYWORDS:
        # Find all matches
        matches = re.finditer(pattern, segment_lower)
        for match in matches:
            cues.append(TemporalCue(
                text=match.group(0),
                cue_type=cue_type
            ))
    return cues

def _detect_trait_cues(segment: str) -> List[TraitCue]:
    """
    Detect trait/personality cues using keywords.
    """
    cues = []
    segment_lower = segment.lower()
    for category, patterns in TRAIT_KEYWORDS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, segment_lower)
            for match in matches:
                cues.append(TraitCue(
                    text=match.group(0),
                    category=category
                ))
    return cues

# --- Main API ---

def detect_lore(segment: str) -> LoreDetectionResult:
    """
    Analyze a cleaned text segment and return structured detections:
    - entity type
    - name (optional)
    - relationships
    - temporal cues
    - trait cues
    """
    if not segment or not segment.strip():
        # Handle empty input
        return LoreDetectionResult(
            segment=segment,
            entity=DetectedEntity(type="unknown", name=None),
            relationships=[],
            temporal_cues=[],
            trait_cues=[]
        )

    # 1. Detect Entity Type
    e_type = _detect_entity_type(segment)
    # We generally don't extract name here as per instructions to leave resolution to Extractor
    # But if the prompt implies we should fill it if detected... 
    # Prompt says: "name: Optional[str] # if detected"
    # But later: "Do not attempt to resolve canonical entity names (Extractor does that later)."
    # I'll stick to type detection.
    entity = DetectedEntity(type=e_type, name=None)
    
    # 2. Detect Relationships
    relationships = _detect_relationships(segment)
    
    # 3. Detect Temporal Cues
    temporal_cues = _detect_temporal_cues(segment)
    
    # 4. Detect Trait Cues
    trait_cues = _detect_trait_cues(segment)
    
    return LoreDetectionResult(
        segment=segment,
        entity=entity,
        relationships=relationships,
        temporal_cues=temporal_cues,
        trait_cues=trait_cues
    )

def detect_many(segments: List[str]) -> List[LoreDetectionResult]:
    """Batch version."""
    results = []
    logger.debug(f"Detecting lore for {len(segments)} segments.")
    for seg in segments:
        results.append(detect_lore(seg))
    return results

