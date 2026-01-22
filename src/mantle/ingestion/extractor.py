"""
Property Extractor Module
Stage 3 of the Smart Ingestor pipeline.

This module takes a LoreDetectionResult and extracts structured entity properties.
It transforms detected features into canonical properties that feed:
- EntityFactory
- PersonalityPipeline
- Neo4jMapper

This module is deterministic and rule-based.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from src.mantle.ingestion.detector import LoreDetectionResult, DetectedEntity, DetectedRelationship

logger = logging.getLogger(__name__)

# --- Dataclasses ---

@dataclass
class ExtractedProperties:
    name: Optional[str]
    aliases: List[str]
    description: str             # cleaned descriptive text
    entity_type: Optional[str]
    tags: List[str]
    traits: List[str]            # behavioral or adjective cues
    temporal_cues: List[Dict[str, Any]]    # raw cues preserved for timeline modeling
    relationship_candidates: List[Dict[str, Any]]   # unresolved relationship edges

# --- Constants & Heuristics ---

ROLE_KEYWORDS = {
    "commander", "mage", "scholar", "hunter", "warrior", "assassin", "guard",
    "king", "queen", "prince", "princess", "lord", "lady", "captain", "lieutenant",
    "priest", "monk", "thief", "spy", "merchant", "blacksmith", "alchemist"
}

FACTION_KEYWORDS = {
    "order", "house", "clan", "guild", "faction", "tribe", "legion", "empire",
    "kingdom", "alliance", "cult", "coven"
}

MAGIC_KEYWORDS = {
    "arcane", "ritual", "seer", "necromantic", "spell", "magic", "sorcery",
    "enchanted", "divine", "cursed", "holy", "unholy"
}

# Titles to strip from name if found at start
TITLES = [
    "Commander", "Lord", "Lady", "Master", "Captain", "King", "Queen", "Prince", 
    "Princess", "Sir", "Dame", "General", "Emperor", "Empress", "High Priest", 
    "Archmage"
]

LEADERSHIP_PATTERNS = [
    (r"led by ([A-Z][a-z\-]+(?: [A-Z][a-z\-]+)*)", "LEADS"),
    (r"commanded by ([A-Z][a-z\-]+(?: [A-Z][a-z\-]+)*)", "COMMANDS"),
    (r"ruled by ([A-Z][a-z\-]+(?: [A-Z][a-z\-]+)*)", "LEADS"),
    (r"under the command of ([A-Z][a-z\-]+(?: [A-Z][a-z\-]+)*)", "COMMANDS"),
    (r"([A-Z][a-z\-]+(?: [A-Z][a-z\-]+)*) leads (?:the )?", "LEADS"),
    (r"([A-Z][a-z\-]+(?: [A-Z][a-z\-]+)*) commands (?:the )?", "COMMANDS"),
]

OFFICER_TITLES = [
    "Commander", "Captain", "General", "Brigadier", "Lieutenant", "Admiral", "Colonel", "Major"
]

# --- Helper Functions ---

def _extract_leadership_entities(segment: str, faction_name: str) -> List[ExtractedProperties]:
    """
    Extract leadership figures from a faction segment.
    """
    leadership_entities = []
    seen_names = set()
    
    # 1. Regex Extraction (Explicit relationships)
    for pattern, rel_type in LEADERSHIP_PATTERNS:
        matches = re.finditer(pattern, segment)
        for match in matches:
            char_name = match.group(1).strip()
            
            if char_name in ["The", "A", "He", "She", "It", "They"]: continue
            if faction_name and char_name == faction_name: continue
            if char_name in seen_names: continue
            
            # Check for title to refine relationship
            has_title = any(t in char_name for t in OFFICER_TITLES)
            final_rel = "COMMANDS" if has_title else rel_type
            
            props = ExtractedProperties(
                name=char_name,
                aliases=[],
                description=f"Leader within {faction_name or 'the faction'}.",
                entity_type="character",
                tags=["leader"] + (["officer"] if has_title else []),
                traits=[],
                temporal_cues=[],
                relationship_candidates=[{
                    "source": char_name,
                    "target": faction_name,
                    "relationship_type": final_rel,
                    "is_explicit": True
                }]
            )
            leadership_entities.append(props)
            seen_names.add(char_name)
            
    # 2. Title-based extraction (Implicit/Fallback)
    for title in OFFICER_TITLES:
        # Pattern: Title Name (e.g. Captain Remington)
        pattern = r"\b" + title + r" ([A-Z][a-z\-]+)\b"
        matches = re.finditer(pattern, segment)
        for match in matches:
            char_name = f"{title} {match.group(1)}"
            
            if char_name in seen_names: continue
            if faction_name and char_name == faction_name: continue
            
            props = ExtractedProperties(
                name=char_name,
                aliases=[],
                description=f"{title} of {faction_name or 'the faction'}.",
                entity_type="character",
                tags=[title.lower(), "officer"],
                traits=[],
                temporal_cues=[],
                relationship_candidates=[{
                    "source": char_name,
                    "target": faction_name,
                    "relationship_type": "COMMANDS",
                    "is_explicit": True
                }]
            )
            leadership_entities.append(props)
            seen_names.add(char_name)

    return leadership_entities

def _extract_name(result: LoreDetectionResult) -> Optional[str]:
    """
    Extract entity name using heuristics.
    """
    # 1. Use detected name if available (though currently detector mostly leaves it None)
    if result.entity and result.entity.name:
        return result.entity.name
        
    segment = result.segment.strip()
    if not segment:
        return None
        
    lines = segment.split('\n')
    first_line = lines[0].strip()
    
    # 2. Heuristic: Check for capitalized token sequence at start of first line
    # Matches "Name Name" or "The Name Name" etc.
    # We stop at punctuation or lowercase (except specific particles like 'of'/'the' inside name? simpler to stick to capitalization)
    
    # Simple regex for initial capital sequence:
    # Starts with Capital, allows spaces followed by Capitals.
    # e.g. "Aldric Varn", "The Iron Spire"
    # match = re.match(r'^((?:[A-Z][a-z]+(?:\s+(?:of|the|de|van)\s+)?)+[A-Z][a-z]*)', first_line)
    
    # Improved regex to capture names like "The Dark Tower" (ALL CAPS) or "Aldric Varn"
    # Must start with a word character.
    # If the whole line is short and uppercase, take it.
    if len(first_line) < 60 and first_line.isupper():
        return first_line

    # Standard Capitalized Name regex
    # We relax the regex slightly to catch names at start of string even if followed by punctuation
    match = re.match(r'^((?:[A-Z][a-z]+(?:\s+(?:of|the|de|van)\s+)?)+[A-Z][a-z]*)', first_line)
    
    if match:
        name_candidate = match.group(1).strip()
        # Filter out if it's just a common word that happens to be capitalized at start of sentence
        # (Hard to distinguish perfectly without POS tagging, but let's assume valid for now)
        
        # If the candidate name covers most of the first line, use it.
        # e.g. "Aldric Varn (the Iron Wolf)..." -> "Aldric Varn" is good.
        # "He was born..." -> "He" is bad.
        if name_candidate in ["He", "She", "It", "They"]:
             return None

        return name_candidate

    return None

def _extract_aliases(segment: str) -> List[str]:
    """
    Extract aliases using patterns like "also called", "known as", etc.
    """
    aliases = []
    
    # Patterns
    patterns = [
        r"also called (?:the )?([A-Z][a-zA-Z\s\-\']+)",
        r"known as (?:the )?([A-Z][a-zA-Z\s\-\']+)",
        r"called (?:the )?([A-Z][a-zA-Z\s\-\']+)",
        r"\((?:the )?([A-Z][a-zA-Z\s\-\']+)\)" # Parentheses with capitalized content
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, segment)
        for match in matches:
            alias = match.group(1).strip()
            # Basic validation: ignore if too long or looks like a full sentence
            if len(alias.split()) < 6 and len(alias) > 2:
                # Remove trailing punctuation
                alias = alias.strip(".,;:!?")
                aliases.append(alias)
                
    return list(set(aliases))

def _extract_description(segment: str, name: Optional[str], relationships: List[DetectedRelationship], temporal_cues: List[Dict]) -> str:
    """
    Clean description by removing name mentions (if start of sentence), relationship lines, etc.
    This is a "best effort" cleanup.
    """
    # For now, we mainly return the full segment but maybe stripped of the exact name line if it's a heading-only segment?
    # Prompt: "Everything EXCEPT: extracted name, relationship lines, pure temporal statements"
    
    # Actually, simpler approach: Return the full text, but let downstream handle advanced filtering.
    # However, prompt specifically asks to "Remove leading titles... but keep meaningful descriptors in the description field."
    
    # Let's try to remove the name if it appears at the very start to make it more "description-like".
    # e.g. "Aldric Varn is a warrior." -> "is a warrior." (maybe too aggressive?)
    # Usually description fields in databases prefer the full text or at least the text explaining the entity.
    
    # If the segment IS just the name (heading), description is empty?
    if name and segment.strip() == name:
        return ""
        
    desc = segment
    
    # If name is at start, maybe we don't remove it?
    # "Aldric Varn (the Iron Wolf), commander of..."
    # The user wants "description: cleaned descriptive text".
    # Often it's better to keep the context.
    
    # Prompt says: "Remove leading titles like... but keep meaningful descriptors in the description field."
    # This might refer to when we are extracting tags? No, it says under "3. DESCRIPTION".
    
    # Let's just return the segment as is for now, maybe stripping the Name if it's a heading-style segment (Name\nDescription).
    lines = segment.split('\n')
    filtered_lines = []
    
    for line in lines:
        sline = line.strip()
        if name and sline == name:
            continue
        # If line is purely a relationship? Hard to tell for sure without overlaps.
        # If line is purely temporal?
        
        filtered_lines.append(line)
        
    return "\n".join(filtered_lines).strip()

def _extract_tags(segment: str) -> List[str]:
    """
    Extract tags from text: roles, factions, combat, magic.
    """
    tags = set()
    text_lower = segment.lower()
    
    # Check simple keywords
    all_keywords = ROLE_KEYWORDS | FACTION_KEYWORDS | MAGIC_KEYWORDS
    
    # Regex to find words
    words = set(re.findall(r'\b\w+\b', text_lower))
    
    for word in words:
        if word in all_keywords:
            tags.add(word)
            
    # Also check multi-word heuristics if needed?
    # For now single word lookup is robust enough for "commander", "mage", etc.
    
    return sorted(list(tags))

def _extract_traits(trait_cues: List[Any]) -> List[str]:
    """
    Convert TraitCue objects to list of strings.
    """
    return [cue.text.lower() for cue in trait_cues]

# --- Main API ---

def extract_properties(result: LoreDetectionResult) -> List[ExtractedProperties]:
    """
    Convert a LoreDetectionResult into a list of canonical properties for EntityBuilder.
    Returns a list because faction modules may yield multiple entities.
    """
    
    # 1. Name Extraction
    name = _extract_name(result)
    
    # 2. Aliases
    aliases = _extract_aliases(result.segment)
    
    # 7. Temporal Cues (Pass through)
    temporal_cues_dicts = []
    for cue in result.temporal_cues:
        temporal_cues_dicts.append({
            "text": cue.text,
            "cue_type": cue.cue_type
        })
        
    # 8. Relationship Candidates
    relationship_candidates = []
    for rel in result.relationships:
        relationship_candidates.append({
            "source": rel.source, # Likely None
            "target": rel.target,
            "relationship_type": rel.relationship_type
        })
    
    # 3. Description
    description = _extract_description(result.segment, name, result.relationships, temporal_cues_dicts)
    
    # 4. Entity Type
    entity_type = result.entity.type if result.entity else None
    
    # 5. Tags
    tags = _extract_tags(result.segment)
    
    # 6. Traits
    traits = _extract_traits(result.trait_cues)
    
    main_entity = ExtractedProperties(
        name=name,
        aliases=aliases,
        description=description,
        entity_type=entity_type,
        tags=tags,
        traits=traits,
        temporal_cues=temporal_cues_dicts,
        relationship_candidates=relationship_candidates
    )
    
    entities = [main_entity]
    
    # If Faction, attempt to extract leadership figures
    if entity_type and entity_type.lower() == "faction":
        # We need the faction name to link them
        faction_name = name
        # If no name detected for faction, use alias? Or skip?
        if faction_name:
            leadership = _extract_leadership_entities(result.segment, faction_name)
            entities.extend(leadership)
            
    return entities

def extract_many(results: List[LoreDetectionResult]) -> List[ExtractedProperties]:
    """Batch version."""
    extracted = []
    logger.debug(f"Extracting properties for {len(results)} detection results.")
    for res in results:
        props_list = extract_properties(res)
        extracted.extend(props_list)
    return extracted

