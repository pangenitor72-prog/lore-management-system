"""
Lore Parsing Agent

AI-powered agent that takes raw lore text and parses it into structured entities
with OCEAN personality profiles, relationships, and rich metadata for storage.

This agent uses Gemini to:
1. Extract entities (Characters, Locations, Factions, Items, Events)
2. Identify personality traits for characters
3. Generate OCEAN profiles from traits
4. Infer relationships between entities
5. Store everything in Neo4j
"""

import os
import re
import json
import uuid
import random
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Thread pool for blocking Gemini calls
_executor = ThreadPoolExecutor(max_workers=2)


def _slugify(text: str, max_length: int = 30) -> str:
    """Convert text to a URL-friendly slug."""
    # Lowercase and replace spaces/special chars with hyphens
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)  # Remove special chars
    slug = re.sub(r"[\s_]+", "-", slug)        # Spaces/underscores to hyphens
    slug = re.sub(r"-+", "-", slug)            # Multiple hyphens to single
    slug = slug.strip("-")                      # Remove leading/trailing hyphens
    return slug[:max_length]


def _generate_human_readable_id(
    name: str,
    entity_type: str,
    world_id: Optional[str] = None
) -> str:
    """
    Generate a human-readable entity ID.

    Format: {world}-{type_prefix}-{name_slug}-{short_random}
    Examples:
        - eldoria-chr-captain-varn-7f3a
        - city_of_night-loc-the-rack-a2c1
        - session-fac-thieves-guild-9d4e
    """
    # Type prefixes for brevity
    type_prefixes = {
        "Character": "chr",
        "Location": "loc",
        "Faction": "fac",
        "Item": "itm",
        "Event": "evt",
        "Concept": "con",
    }
    type_prefix = type_prefixes.get(entity_type, "ent")

    # Slugify the name
    name_slug = _slugify(name, max_length=20)
    if not name_slug:
        name_slug = "unnamed"

    # Short random suffix for uniqueness
    short_id = uuid.uuid4().hex[:4]

    # Build the ID
    if world_id:
        world_slug = _slugify(world_id, max_length=15)
        return f"{world_slug}-{type_prefix}-{name_slug}-{short_id}"
    else:
        return f"{type_prefix}-{name_slug}-{short_id}"


class ExtractedEntity(BaseModel):
    """Entity extracted from lore text."""
    name: str
    aliases: List[str] = Field(default_factory=list)  # Alternative names, titles, epithets
    entity_type: str  # Character, Location, Faction, Item, Event, Concept
    description: str
    traits: List[str] = Field(default_factory=list)  # Personality traits for characters
    tags: List[str] = Field(default_factory=list)  # Role tags like "merchant", "warrior"
    temporal_cues: List[str] = Field(default_factory=list)  # Time references
    verbatim_text: str = ""  # Original text about this entity
    # Character-specific deep fields
    goals: List[str] = Field(default_factory=list)  # What they want (stated or inferred)
    secrets: List[str] = Field(default_factory=list)  # What they're hiding
    fears: List[str] = Field(default_factory=list)  # What they're afraid of
    # Uncertainty flagging
    confidence: str = "high"  # high, medium, low - how confident the AI is
    uncertainties: List[str] = Field(default_factory=list)  # What the AI is unsure about


class ExtractedRelationship(BaseModel):
    """Relationship extracted from lore text."""
    source: str
    target: str
    relationship_type: str
    description: str = ""
    confidence: str = "high"  # high, medium, low
    uncertainty: Optional[str] = None  # What the AI is unsure about


class UncertaintyFlag(BaseModel):
    """A question or uncertainty the AI wants to flag for admin review."""
    category: str  # entity, relationship, world, timeline
    question: str  # The specific question
    context: str  # Relevant text or context
    suggestions: List[str] = Field(default_factory=list)  # Possible answers


class OCEANProfile(BaseModel):
    """OCEAN personality profile."""
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5


class ExtractedWorldCharacteristics(BaseModel):
    """World characteristics inferred from lore text."""
    primary_genre: Optional[str] = None
    sub_genres: List[str] = Field(default_factory=list)
    magic_level: Optional[str] = None
    technology_level: Optional[str] = None
    supernatural_presence: Optional[str] = None
    tone: Optional[str] = None
    narrative_style: List[str] = Field(default_factory=list)
    moral_complexity: Optional[str] = None
    lethality: Optional[str] = None
    themes: List[str] = Field(default_factory=list)
    social_structures: List[str] = Field(default_factory=list)
    power_scale: Optional[str] = None
    scope: Optional[str] = None
    world_constants: List[str] = Field(default_factory=list)
    sensory_palette: List[str] = Field(default_factory=list)


class PendingDuplicate(BaseModel):
    """An entity that may be a duplicate - needs admin review before ingestion."""
    new_entity: ExtractedEntity  # The entity from the new lore
    existing_entity_id: str  # canon_id of the potential match
    existing_entity_name: str
    existing_entity_type: str
    existing_description: str = ""
    existing_aliases: List[str] = Field(default_factory=list)
    similarity_score: float
    match_reason: str  # "exact_name", "similar_name", "alias_match"


class ParsedLoreResult(BaseModel):
    """Result of parsing lore text."""
    entities: List[ExtractedEntity]
    relationships: List[ExtractedRelationship]
    world_characteristics: Optional[ExtractedWorldCharacteristics] = None
    uncertainties: List[UncertaintyFlag] = Field(default_factory=list)  # Questions for admin
    pending_duplicates: List[PendingDuplicate] = Field(default_factory=list)  # Need admin review
    entities_stored: int = 0
    entities_auto_merged: int = 0  # Exact matches that were auto-merged
    relationships_stored: int = 0
    characters_with_ocean: int = 0


class LoreParsingAgent:
    """
    AI-powered agent for parsing raw lore into structured entities.

    Uses Gemini to intelligently extract:
    - Characters with personality traits → OCEAN profiles
    - Locations with atmosphere and significance
    - Factions with goals and relationships
    - Items with properties and history
    - Events with participants and consequences
    """

    EXTRACTION_PROMPT = """You are an expert Lore Extraction Agent for a narrative RPG knowledge graph system.

Your task: Extract EVERY entity and relationship from the lore text below. Be EXHAUSTIVE - missing entities breaks the game. Also infer the world's characteristics from the narrative.

## EXTRACTION STRATEGY (Follow This Order)

**STEP 1: Scan for Named Entities**
Look for these patterns:
- Capitalized names (people, places, organizations)
- Titles + names ("King Aldric", "The Obsidian Tower", "Order of the Flame")
- Pronouns with antecedents ("she" refers to whom?)
- Epithets ("the Mad King", "the Silent One")

**STEP 2: Scan for Unnamed but Significant Entities**
- Roles mentioned without names ("the innkeeper", "a traveling merchant") → Create placeholder names like "The Innkeeper of [Location]"
- Locations without proper names ("the old ruins", "a hidden cave") → Name them contextually
- Items of significance ("the ancient sword", "a mysterious amulet")

**STEP 3: Extract Implicit Entities**
- If someone "leads a rebellion" → Extract the rebellion as a Faction/Event
- If a battle is mentioned → Extract it as an Event
- If a magic system is described → Extract it as a Concept
- If a family/house is mentioned → Extract it as a Faction

**STEP 4: Map All Relationships**
- Explicit: "X is Y's brother" → FAMILY_OF
- Implicit: "X serves Y" → SERVES
- Spatial: "X lives in Y" → LOCATED_IN
- Temporal: "X happened during Y" → DURING
- Causal: "X caused Y" → CAUSED

**STEP 5: Infer World Characteristics**
Analyze the text to determine the world's nature:
- Genre signals: magic systems, technology, supernatural elements
- Tone signals: descriptions of violence/peace, hope/despair, moral clarity
- Themes: recurring topics (power, betrayal, redemption, etc.)
- Social structures: mentions of governance, class, religion

## ENTITY TYPES & IDENTIFICATION

| Type | Identify By | Examples |
|------|-------------|----------|
| CHARACTER | Named/titled individuals, people with agency | "Queen Seraphina", "the blacksmith Gorn", "a mysterious stranger" |
| LOCATION | Places, buildings, regions, realms, landmarks | "Thornhaven", "the Amber Plains", "Castle Dreadmoor" |
| FACTION | Groups, organizations, families, guilds, armies, cults | "House Blackwood", "the Thieves Guild", "the Iron Legion" |
| ITEM | Objects with narrative significance, artifacts, weapons | "the Crown of Shadows", "Varen's sword", "the ancient tome" |
| EVENT | Past/future occurrences, battles, ceremonies, disasters | "the Fall of Eldoria", "the Crimson Wedding", "the Great Flood" |
| CONCEPT | Magic systems, prophecies, religions, abstract forces | "blood magic", "the Prophecy of Ash", "the Old Ways" |

## CHARACTER DEEP EXTRACTION

For EVERY Character, extract:

**Personality Traits** (3-6 traits from vocabulary below):
- Direct descriptions ("she was cunning", "known for his kindness")
- Actions ("he betrayed his allies" → treacherous, cunning)
- Dialogue style ("spoke softly" → gentle, reserved)
- Reputation ("feared by all" → intimidating, powerful)

**Goals** - What does this character want? Infer from:
- Stated objectives ("seeks to reclaim the throne")
- Actions that imply desire ("he gathered an army" → wants power/revenge)
- Role expectations (a merchant wants profit, a knight wants honor)

**Secrets** - What are they hiding? Infer from:
- Explicit secrets ("unknown to all, she was...")
- Contradictions between public and private actions
- Hidden identities, loyalties, or knowledge

**Fears** - What are they afraid of? Infer from:
- Stated fears or anxieties
- Protective behaviors ("never spoke of his past" → fears exposure)
- Weaknesses that could be exploited

**Trait Vocabulary:**
```
OPENNESS: curious, creative, imaginative, wise, studious, traditional, practical, inventive, philosophical, artistic
CONSCIENTIOUSNESS: methodical, disciplined, loyal, patient, calculating, ambitious, organized, careful, reckless, impulsive, scattered, lazy
EXTRAVERSION: charismatic, bold, commanding, warm, outgoing, reserved, cold, quiet, shy, gregarious, assertive, withdrawn
AGREEABLENESS: kind, forgiving, gentle, compassionate, ruthless, vengeful, cunning, aggressive, trusting, suspicious, generous, selfish
NEUROTICISM: brave, calm, stoic, fearful, anxious, paranoid, confident, nervous, stable, volatile, serene, tormented
```

## OUTPUT FORMAT (JSON only, no markdown fences)

{{
    "entities": [
        {{
            "name": "Canonical Name",
            "aliases": ["Nick Name", "Title", "Epithet"],
            "entity_type": "Character|Location|Faction|Item|Event|Concept",
            "description": "2-3 sentence summary capturing essence and narrative role",
            "traits": ["trait1", "trait2", "trait3"],
            "goals": ["primary goal", "secondary goal"],
            "secrets": ["what they hide"],
            "fears": ["what they fear"],
            "tags": ["role1", "role2"],
            "temporal_cues": ["time reference 1", "time reference 2"],
            "verbatim_text": "Copy the EXACT sentences from the source that describe this entity",
            "confidence": "high|medium|low",
            "uncertainties": ["What I'm unsure about regarding this entity"]
        }}
    ],
    "relationships": [
        {{
            "source": "Entity Name",
            "target": "Other Entity Name",
            "relationship_type": "TYPE",
            "description": "How/why they are connected",
            "confidence": "high|medium|low",
            "uncertainty": "What I'm unsure about (or null)"
        }}
    ],
    "uncertainties": [
        {{
            "category": "entity|relationship|world|timeline",
            "question": "The specific question for the admin",
            "context": "Relevant text or reasoning",
            "suggestions": ["Possible answer 1", "Possible answer 2"]
        }}
    ],
    "world_characteristics": {{
        "primary_genre": "Fantasy|Sci-Fi|Horror|Modern|Historical|etc or null",
        "sub_genres": ["High Fantasy", "Grimdark", "etc"],
        "magic_level": "None|Rare & Mythic|Low & Costly|Common|Pervasive or null",
        "technology_level": "Primitive|Ancient|Medieval|Renaissance|Industrial|Modern|Near-Future|Far-Future|Magitech or null",
        "supernatural_presence": "None|Hidden/Secretive|Known but Rare|Common|Dominant or null",
        "tone": "Hopeful|Optimistic|Neutral|Serious|Melancholic|Dark|Grimdark|Whimsical|Campy|Satirical or null",
        "narrative_style": ["Epic/Sweeping", "Intimate/Character-driven", "Action-packed", "Slow-burn", "Pulpy/Fun", "Literary/Poetic", "Cinematic", "etc"],
        "moral_complexity": "Clear Good vs Evil|Mostly Clear|Gray Areas|Morally Ambiguous|No Clear Morality or null",
        "lethality": "Plot Armor|Forgiving|Balanced|Dangerous|Brutal or null",
        "themes": ["Political Intrigue", "Betrayal", "Redemption", "etc"],
        "social_structures": ["Feudal", "Monarchic", "etc"],
        "power_scale": "Street-level|Local/Regional|Kingdom/National|Continental|World-shaping|Cosmic or null",
        "scope": "Intimate/Personal|Local Community|Regional|Continental|Global|Interplanetary|Cosmic or null",
        "world_constants": ["Hard rules inferred: 'Magic requires blood sacrifice'", "etc"],
        "sensory_palette": ["Recurring sensory details: 'perpetual twilight', 'smell of decay'"]
    }}
}}

## FIELD DEFINITIONS

| Field | Required | Description |
|-------|----------|-------------|
| name | Yes | Primary canonical name |
| aliases | Yes | Alternative names, titles, nicknames (empty array if none) |
| entity_type | Yes | One of: Character, Location, Faction, Item, Event, Concept |
| description | Yes | 2-3 sentences: who/what it is, why it matters to the narrative |
| traits | Characters only | Personality traits from vocabulary above (3-6 traits) |
| goals | Characters/Factions | What they want (1-3 goals, inferred if not stated) |
| secrets | Characters/Factions | What they hide (can be empty if truly open) |
| fears | Characters/Factions | What they fear/vulnerabilities (can be empty if none) |
| tags | Yes | Role/category tags: ["warrior", "noble", "haunted", "ancient", "criminal"] |
| temporal_cues | If present | Time references: ["during the war", "500 years ago", "before the fall"] |
| verbatim_text | Yes | EXACT quote from source text (for citation/verification) |

## RELATIONSHIP TYPES

**Interpersonal:** FAMILY_OF, MARRIED_TO, PARENT_OF, CHILD_OF, SIBLING_OF, LOVES, HATES, FRIENDS_WITH, RIVALS, MENTORS, SERVES, EMPLOYS, BETRAYED
**Organizational:** LEADS, MEMBER_OF, FOUNDED, ALLIED_WITH, ENEMY_OF, FACTION_OF, CONTROLS
**Spatial:** LOCATED_IN, RULES, BORDERS, CONTAINS, ORIGINATES_FROM, RESIDES_IN, HEADQUARTERS_AT
**Object:** OWNS, CREATED, WIELDS, GUARDS, SEEKS, POSSESSES
**Temporal/Causal:** CAUSED, PARTICIPATED_IN, WITNESSED, DURING, BEFORE, AFTER, RESULTED_IN
**Conceptual:** BELIEVES_IN, PRACTICES, PROPHECY_ABOUT, CURSED_BY, BLESSED_BY

## CRITICAL RULES

1. **EXHAUSTIVE EXTRACTION**: If in doubt, extract it. A minor character mentioned once is still an entity.
2. **NO INVENTED CONTENT**: Only extract what's in the text. Don't invent details not present.
3. **INFER GOALS/SECRETS/FEARS**: For characters, you MAY infer these from context if not stated explicitly. Use narrative logic.
4. **VERBATIM REQUIRED**: Always include the exact source text for each entity.
5. **INFER RELATIONSHIPS**: "the king's advisor" → SERVES relationship. "sworn enemies" → ENEMY_OF.
6. **CHARACTER TRAITS REQUIRED**: Every Character MUST have 3-6 personality traits inferred from text.
7. **HANDLE PRONOUNS**: Resolve "he", "she", "they" to actual entity names.
8. **EXTRACT NESTED ENTITIES**: "the ruins of Old Valdris" → Extract BOTH "ruins" (Location) AND "Old Valdris" (Faction/Location).
9. **WORLD CHARACTERISTICS**: Always include world_characteristics. Use null for fields you cannot determine. Include only what the text supports.
10. **FLAG UNCERTAINTIES**: When you're unsure about something, flag it!
    - Mark entities/relationships with confidence: "low" or "medium" if uncertain
    - Add specific uncertainties to the entity's "uncertainties" array
    - Add major questions to the top-level "uncertainties" array
    - Examples of things to flag:
      * "Is this person alive or dead?"
      * "Is this the same character mentioned earlier under a different name?"
      * "Is this relationship romantic or familial?"
      * "Is this location part of the larger region mentioned?"
      * "Does 'the war' refer to a specific known event?"

## EXAMPLE

Input: "Queen Mira the Wise ruled Thornhaven with an iron will but a kind heart. Her brother, Prince Caden, secretly plotted against her from his exile in the Shadowfen, nursing old wounds and gathering dark allies."

Output:
{{
    "entities": [
        {{
            "name": "Queen Mira",
            "aliases": ["Mira the Wise", "The Queen"],
            "entity_type": "Character",
            "description": "Ruler of Thornhaven known for her wisdom. Governs with strict authority but genuine compassion for her people.",
            "traits": ["wise", "disciplined", "kind", "authoritative", "compassionate"],
            "goals": ["Maintain peace and prosperity in Thornhaven", "Protect her realm from threats"],
            "secrets": [],
            "fears": ["Her brother's treachery succeeding", "Being forced to harm family"],
            "tags": ["royalty", "ruler", "queen"],
            "temporal_cues": [],
            "verbatim_text": "Queen Mira the Wise ruled Thornhaven with an iron will but a kind heart.",
            "confidence": "high",
            "uncertainties": []
        }},
        {{
            "name": "Prince Caden",
            "aliases": ["The Exiled Prince"],
            "entity_type": "Character",
            "description": "Queen Mira's brother, living in exile. Harbors treasonous ambitions against his sister's throne.",
            "traits": ["cunning", "ambitious", "treacherous", "secretive", "resentful"],
            "goals": ["Reclaim what he believes is rightfully his", "Overthrow Queen Mira"],
            "secrets": ["The true nature of his dark allies", "The extent of his network"],
            "fears": ["Dying in obscurity", "Being forgotten", "His sister's forgiveness"],
            "tags": ["royalty", "exile", "conspirator"],
            "temporal_cues": [],
            "verbatim_text": "Her brother, Prince Caden, secretly plotted against her from his exile in the Shadowfen, nursing old wounds and gathering dark allies.",
            "confidence": "high",
            "uncertainties": ["What are his 'old wounds'? Possibly related to succession or past conflict"]
        }},
        {{
            "name": "Thornhaven",
            "aliases": [],
            "entity_type": "Location",
            "description": "A realm or city ruled by Queen Mira. The seat of royal power.",
            "traits": [],
            "goals": [],
            "secrets": [],
            "fears": [],
            "tags": ["kingdom", "capital", "ruled"],
            "temporal_cues": [],
            "verbatim_text": "Queen Mira the Wise ruled Thornhaven"
        }},
        {{
            "name": "Shadowfen",
            "aliases": [],
            "entity_type": "Location",
            "description": "A remote, likely dangerous region where exiles and dark forces gather.",
            "traits": [],
            "goals": [],
            "secrets": [],
            "fears": [],
            "tags": ["exile location", "remote", "frontier", "dark"],
            "temporal_cues": [],
            "verbatim_text": "from his exile in the Shadowfen"
        }}
    ],
    "relationships": [
        {{"source": "Queen Mira", "target": "Thornhaven", "relationship_type": "RULES", "description": "Mira is the ruling queen of Thornhaven"}},
        {{"source": "Prince Caden", "target": "Queen Mira", "relationship_type": "SIBLING_OF", "description": "Caden is Mira's brother"}},
        {{"source": "Prince Caden", "target": "Queen Mira", "relationship_type": "ENEMY_OF", "description": "Caden secretly plots against his sister"}},
        {{"source": "Prince Caden", "target": "Shadowfen", "relationship_type": "RESIDES_IN", "description": "Caden lives in exile in the Shadowfen"}}
    ],
    "world_characteristics": {{
        "primary_genre": "Fantasy",
        "sub_genres": ["High Fantasy"],
        "magic_level": null,
        "technology_level": "Medieval",
        "supernatural_presence": null,
        "tone": "Serious",
        "narrative_style": ["Intimate/Character-driven", "Slow-burn"],
        "moral_complexity": "Gray Areas",
        "lethality": null,
        "themes": ["Political Intrigue", "Betrayal", "Family Conflict"],
        "social_structures": ["Monarchic"],
        "power_scale": "Kingdom/National",
        "scope": "Regional",
        "world_constants": [],
        "sensory_palette": ["dark allies suggest shadow/ominous atmosphere"]
    }}
}}

---

TEXT TO ANALYZE:
{text}
"""

    # OCEAN trait mappings - comprehensive vocabulary for AI extraction
    # Values are deltas applied to baseline 0.5 for each dimension
    TRAIT_TO_OCEAN = {
        # === OPENNESS ===
        # High Openness (curious, creative, open to new experiences)
        "curious": {"openness": 0.15},
        "creative": {"openness": 0.15},
        "imaginative": {"openness": 0.15},
        "inventive": {"openness": 0.15},
        "artistic": {"openness": 0.15, "extraversion": 0.05},
        "philosophical": {"openness": 0.15, "conscientiousness": 0.05},
        "wise": {"openness": 0.1, "conscientiousness": 0.05},
        "studious": {"openness": 0.1, "conscientiousness": 0.1},
        "intellectual": {"openness": 0.15},
        "visionary": {"openness": 0.15, "extraversion": 0.05},
        # Low Openness (traditional, practical, conventional)
        "traditional": {"openness": -0.1},
        "practical": {"openness": -0.1, "conscientiousness": 0.05},
        "conventional": {"openness": -0.1},
        "conservative": {"openness": -0.1},

        # === CONSCIENTIOUSNESS ===
        # High Conscientiousness (organized, disciplined, goal-oriented)
        "methodical": {"conscientiousness": 0.15},
        "disciplined": {"conscientiousness": 0.15},
        "organized": {"conscientiousness": 0.15},
        "careful": {"conscientiousness": 0.1, "neuroticism": -0.05},
        "diligent": {"conscientiousness": 0.15},
        "loyal": {"conscientiousness": 0.1, "agreeableness": 0.1},
        "patient": {"conscientiousness": 0.1, "neuroticism": -0.1},
        "calculating": {"conscientiousness": 0.1, "agreeableness": -0.1},
        "ambitious": {"conscientiousness": 0.1, "extraversion": 0.05},
        "determined": {"conscientiousness": 0.1, "neuroticism": -0.05},
        "reliable": {"conscientiousness": 0.15, "agreeableness": 0.05},
        "dutiful": {"conscientiousness": 0.15},
        # Low Conscientiousness (impulsive, careless, spontaneous)
        "impulsive": {"conscientiousness": -0.15, "neuroticism": 0.05},
        "reckless": {"conscientiousness": -0.15, "neuroticism": -0.05},
        "scattered": {"conscientiousness": -0.15},
        "lazy": {"conscientiousness": -0.2},
        "careless": {"conscientiousness": -0.15},
        "spontaneous": {"conscientiousness": -0.1, "openness": 0.05},

        # === EXTRAVERSION ===
        # High Extraversion (outgoing, energetic, assertive)
        "charismatic": {"extraversion": 0.15, "agreeableness": 0.05},
        "bold": {"extraversion": 0.15, "neuroticism": -0.1},
        "commanding": {"extraversion": 0.15},
        "warm": {"extraversion": 0.1, "agreeableness": 0.1},
        "outgoing": {"extraversion": 0.15},
        "gregarious": {"extraversion": 0.15, "agreeableness": 0.05},
        "assertive": {"extraversion": 0.15, "conscientiousness": 0.05},
        "confident": {"extraversion": 0.1, "neuroticism": -0.15},
        "enthusiastic": {"extraversion": 0.15, "openness": 0.05},
        "dominant": {"extraversion": 0.15, "agreeableness": -0.1},
        "flamboyant": {"extraversion": 0.2, "openness": 0.1},
        # Low Extraversion (reserved, quiet, introverted)
        "reserved": {"extraversion": -0.1},
        "cold": {"extraversion": -0.15, "agreeableness": -0.1},
        "quiet": {"extraversion": -0.1},
        "shy": {"extraversion": -0.15, "neuroticism": 0.05},
        "withdrawn": {"extraversion": -0.15},
        "secretive": {"extraversion": -0.1, "openness": -0.05},
        "aloof": {"extraversion": -0.1, "agreeableness": -0.05},
        "introverted": {"extraversion": -0.15},

        # === AGREEABLENESS ===
        # High Agreeableness (kind, cooperative, trusting)
        "kind": {"agreeableness": 0.2},
        "forgiving": {"agreeableness": 0.15, "neuroticism": -0.05},
        "gentle": {"agreeableness": 0.15, "extraversion": -0.05},
        "compassionate": {"agreeableness": 0.15},
        "trusting": {"agreeableness": 0.15, "neuroticism": -0.05},
        "generous": {"agreeableness": 0.15},
        "empathetic": {"agreeableness": 0.15, "openness": 0.05},
        "altruistic": {"agreeableness": 0.2},
        "humble": {"agreeableness": 0.1, "extraversion": -0.05},
        "cooperative": {"agreeableness": 0.15, "conscientiousness": 0.05},
        "nurturing": {"agreeableness": 0.15},
        # Low Agreeableness (competitive, suspicious, antagonistic)
        "ruthless": {"agreeableness": -0.2},
        "vengeful": {"agreeableness": -0.2, "neuroticism": 0.1},
        "cunning": {"agreeableness": -0.1, "openness": 0.05},
        "aggressive": {"agreeableness": -0.15, "extraversion": 0.1},
        "suspicious": {"agreeableness": -0.15, "neuroticism": 0.1},
        "selfish": {"agreeableness": -0.2},
        "manipulative": {"agreeableness": -0.2, "openness": 0.05},
        "treacherous": {"agreeableness": -0.2, "conscientiousness": -0.1},
        "cruel": {"agreeableness": -0.25},
        "hostile": {"agreeableness": -0.2, "neuroticism": 0.1},
        "arrogant": {"agreeableness": -0.15, "extraversion": 0.1},
        "proud": {"agreeableness": -0.1, "extraversion": 0.05},

        # === NEUROTICISM ===
        # Low Neuroticism (stable, confident, resilient)
        "brave": {"neuroticism": -0.15, "extraversion": 0.05},
        "calm": {"neuroticism": -0.15},
        "stoic": {"neuroticism": -0.15, "extraversion": -0.05},
        "stable": {"neuroticism": -0.15},
        "serene": {"neuroticism": -0.15, "agreeableness": 0.05},
        "composed": {"neuroticism": -0.15},
        "resilient": {"neuroticism": -0.15, "conscientiousness": 0.05},
        "fearless": {"neuroticism": -0.2, "extraversion": 0.1},
        # High Neuroticism (anxious, emotional, volatile)
        "fearful": {"neuroticism": 0.2, "extraversion": -0.1},
        "anxious": {"neuroticism": 0.15},
        "paranoid": {"neuroticism": 0.2, "agreeableness": -0.1},
        "nervous": {"neuroticism": 0.15, "extraversion": -0.05},
        "volatile": {"neuroticism": 0.2, "conscientiousness": -0.1},
        "tormented": {"neuroticism": 0.2},
        "insecure": {"neuroticism": 0.15, "extraversion": -0.1},
        "moody": {"neuroticism": 0.15},
        "melancholic": {"neuroticism": 0.1, "extraversion": -0.1},
        "resentful": {"neuroticism": 0.15, "agreeableness": -0.1},

        # === COMPOUND/SPECIAL TRAITS ===
        "authoritative": {"extraversion": 0.1, "conscientiousness": 0.1},
        "mysterious": {"extraversion": -0.1, "openness": 0.1},
        "intimidating": {"extraversion": 0.1, "agreeableness": -0.1, "neuroticism": -0.1},
        "enigmatic": {"extraversion": -0.1, "openness": 0.15},
        "heroic": {"neuroticism": -0.1, "extraversion": 0.1, "agreeableness": 0.1},
        "villainous": {"agreeableness": -0.2, "neuroticism": 0.05},
        "noble": {"conscientiousness": 0.1, "agreeableness": 0.1},
        "devout": {"conscientiousness": 0.1, "openness": -0.05},
        "fanatical": {"conscientiousness": 0.15, "openness": -0.1, "neuroticism": 0.1},
        "mercenary": {"agreeableness": -0.1, "conscientiousness": 0.05},
        "honorable": {"conscientiousness": 0.15, "agreeableness": 0.1},
        "corrupt": {"agreeableness": -0.15, "conscientiousness": -0.1},
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the agent with Gemini API."""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = None

        if self.api_key:
            import google.generativeai as genai
            from google.generativeai.types import HarmCategory, HarmBlockThreshold

            genai.configure(api_key=self.api_key)

            # Safety settings for fiction/RPG content (war, violence in lore is OK)
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            self.model = genai.GenerativeModel(
                "gemini-2.0-flash-exp",
                safety_settings=safety_settings,
            )
            logger.info("LoreParsingAgent initialized with Gemini (fiction-safe settings)")
        else:
            logger.warning("LoreParsingAgent: No API key, will use fallback parsing")

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return LoreParsingAgent._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    @staticmethod
    def _name_similarity(name1: str, name2: str) -> float:
        """Calculate similarity between two names (0.0 to 1.0)."""
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()

        if n1 == n2:
            return 1.0

        # Check if one is substring of another
        if n1 in n2 or n2 in n1:
            return 0.85

        # Levenshtein-based similarity
        max_len = max(len(n1), len(n2))
        if max_len == 0:
            return 1.0

        distance = LoreParsingAgent._levenshtein_distance(n1, n2)
        return 1.0 - (distance / max_len)

    async def _find_existing_entity(
        self,
        entity: 'ExtractedEntity',
        world_id: str,
        db
    ) -> Optional[Dict[str, Any]]:
        """
        Check if an entity already exists in the given world.

        Returns a dict with match info if found:
        {
            "canon_id": str,
            "name": str,
            "entity_type": str,
            "description": str,
            "aliases": list,
            "similarity": float,
            "match_type": "exact" | "similar" | "alias"
        }
        Returns None if no match found.
        """
        entity_name = entity.name.lower().strip()
        entity_type = entity.entity_type

        # Query existing entities in this world of the same type
        result = await db.execute("""
            MATCH (e:Entity)
            WHERE (e.curated_world_id = $world_id OR e.world_id = $world_id)
              AND e.entity_type = $entity_type
            RETURN e.canon_id AS canon_id,
                   e.name AS name,
                   e.entity_type AS entity_type,
                   e.description AS description,
                   e.aliases AS aliases
        """, {"world_id": world_id, "entity_type": entity_type})

        best_match = None
        best_score = 0.0

        for row in result:
            existing_name = (row.get("name") or "").lower().strip()
            existing_aliases = [a.lower().strip() for a in (row.get("aliases") or [])]

            # Check for exact name match
            if entity_name == existing_name:
                return {
                    "canon_id": row["canon_id"],
                    "name": row.get("name", ""),
                    "entity_type": row.get("entity_type", ""),
                    "description": row.get("description", ""),
                    "aliases": row.get("aliases") or [],
                    "similarity": 1.0,
                    "match_type": "exact"
                }

            # Check if new entity name is in existing aliases
            if entity_name in existing_aliases:
                return {
                    "canon_id": row["canon_id"],
                    "name": row.get("name", ""),
                    "entity_type": row.get("entity_type", ""),
                    "description": row.get("description", ""),
                    "aliases": row.get("aliases") or [],
                    "similarity": 0.95,
                    "match_type": "alias"
                }

            # Check if existing name is in new entity's aliases
            new_aliases = [a.lower().strip() for a in (entity.aliases or [])]
            if existing_name in new_aliases:
                return {
                    "canon_id": row["canon_id"],
                    "name": row.get("name", ""),
                    "entity_type": row.get("entity_type", ""),
                    "description": row.get("description", ""),
                    "aliases": row.get("aliases") or [],
                    "similarity": 0.95,
                    "match_type": "alias"
                }

            # Check for similar names (fuzzy match)
            similarity = self._name_similarity(entity_name, existing_name)
            if similarity > best_score and similarity >= 0.75:
                best_score = similarity
                best_match = {
                    "canon_id": row["canon_id"],
                    "name": row.get("name", ""),
                    "entity_type": row.get("entity_type", ""),
                    "description": row.get("description", ""),
                    "aliases": row.get("aliases") or [],
                    "similarity": similarity,
                    "match_type": "similar"
                }

        return best_match

    def _generate_ocean_from_traits(self, traits: List[str]) -> OCEANProfile:
        """Convert personality traits to OCEAN profile."""
        scores = {
            "openness": 0.5,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.5,
        }

        for trait in traits:
            trait_lower = trait.lower().strip()
            if trait_lower in self.TRAIT_TO_OCEAN:
                for dimension, delta in self.TRAIT_TO_OCEAN[trait_lower].items():
                    scores[dimension] = max(0.0, min(1.0, scores[dimension] + delta))

        return OCEANProfile(**scores)

    # Role/archetype to OCEAN tendencies for narrative-driven generation
    ROLE_OCEAN_HINTS = {
        # Leaders & Authority
        "king": {"extraversion": 0.7, "conscientiousness": 0.7, "openness": 0.5},
        "queen": {"extraversion": 0.6, "conscientiousness": 0.7, "agreeableness": 0.5},
        "lord": {"extraversion": 0.6, "conscientiousness": 0.6, "neuroticism": 0.4},
        "captain": {"extraversion": 0.7, "conscientiousness": 0.8, "neuroticism": 0.3},
        "commander": {"extraversion": 0.7, "conscientiousness": 0.8, "agreeableness": 0.4},
        "chief": {"extraversion": 0.7, "conscientiousness": 0.6, "openness": 0.5},

        # Scholars & Mystics
        "wizard": {"openness": 0.9, "conscientiousness": 0.6, "extraversion": 0.3},
        "mage": {"openness": 0.85, "conscientiousness": 0.5, "extraversion": 0.4},
        "sage": {"openness": 0.9, "conscientiousness": 0.7, "agreeableness": 0.6},
        "scholar": {"openness": 0.85, "conscientiousness": 0.8, "extraversion": 0.3},
        "priest": {"conscientiousness": 0.7, "agreeableness": 0.7, "openness": 0.5},
        "oracle": {"openness": 0.9, "neuroticism": 0.6, "extraversion": 0.3},

        # Rogues & Shadows
        "assassin": {"conscientiousness": 0.7, "extraversion": 0.2, "agreeableness": 0.2},
        "thief": {"openness": 0.6, "conscientiousness": 0.4, "agreeableness": 0.3},
        "spy": {"openness": 0.7, "conscientiousness": 0.7, "extraversion": 0.5},
        "rogue": {"openness": 0.6, "conscientiousness": 0.3, "agreeableness": 0.4},

        # Warriors & Fighters
        "warrior": {"conscientiousness": 0.6, "extraversion": 0.6, "neuroticism": 0.4},
        "knight": {"conscientiousness": 0.8, "agreeableness": 0.6, "extraversion": 0.5},
        "soldier": {"conscientiousness": 0.7, "extraversion": 0.5, "openness": 0.4},
        "mercenary": {"conscientiousness": 0.5, "agreeableness": 0.3, "openness": 0.5},
        "barbarian": {"extraversion": 0.7, "conscientiousness": 0.3, "openness": 0.4},
        "guard": {"conscientiousness": 0.7, "extraversion": 0.4, "agreeableness": 0.5},

        # Common Folk & Services
        "merchant": {"extraversion": 0.7, "conscientiousness": 0.6, "agreeableness": 0.5},
        "innkeeper": {"extraversion": 0.8, "agreeableness": 0.7, "openness": 0.5},
        "bartender": {"extraversion": 0.7, "agreeableness": 0.6, "openness": 0.6},
        "farmer": {"conscientiousness": 0.7, "agreeableness": 0.6, "openness": 0.3},
        "blacksmith": {"conscientiousness": 0.8, "extraversion": 0.4, "openness": 0.4},
        "healer": {"agreeableness": 0.8, "conscientiousness": 0.7, "openness": 0.6},

        # Outcasts & Mysterious
        "hermit": {"extraversion": 0.1, "openness": 0.7, "agreeableness": 0.4},
        "wanderer": {"openness": 0.8, "extraversion": 0.4, "conscientiousness": 0.3},
        "stranger": {"extraversion": 0.3, "openness": 0.6, "neuroticism": 0.5},
        "exile": {"neuroticism": 0.6, "agreeableness": 0.4, "extraversion": 0.3},

        # Villains & Antagonists
        "villain": {"agreeableness": 0.2, "neuroticism": 0.6, "openness": 0.5},
        "tyrant": {"agreeableness": 0.1, "extraversion": 0.7, "conscientiousness": 0.6},
        "cultist": {"openness": 0.7, "conscientiousness": 0.6, "agreeableness": 0.3},
    }

    # Description keywords that hint at personality
    DESCRIPTION_OCEAN_HINTS = {
        # High Openness
        "curious": {"openness": 0.2}, "creative": {"openness": 0.2}, "imaginative": {"openness": 0.2},
        "mysterious": {"openness": 0.15}, "eccentric": {"openness": 0.2}, "unconventional": {"openness": 0.15},
        # Low Openness
        "traditional": {"openness": -0.15}, "practical": {"openness": -0.1}, "conventional": {"openness": -0.15},

        # High Conscientiousness
        "disciplined": {"conscientiousness": 0.2}, "meticulous": {"conscientiousness": 0.2},
        "organized": {"conscientiousness": 0.15}, "dutiful": {"conscientiousness": 0.15},
        # Low Conscientiousness
        "chaotic": {"conscientiousness": -0.2}, "impulsive": {"conscientiousness": -0.15},
        "reckless": {"conscientiousness": -0.2}, "carefree": {"conscientiousness": -0.1},

        # High Extraversion
        "outgoing": {"extraversion": 0.2}, "charismatic": {"extraversion": 0.2},
        "loud": {"extraversion": 0.15}, "gregarious": {"extraversion": 0.2}, "boisterous": {"extraversion": 0.15},
        # Low Extraversion
        "quiet": {"extraversion": -0.15}, "reserved": {"extraversion": -0.15},
        "solitary": {"extraversion": -0.2}, "withdrawn": {"extraversion": -0.2}, "shy": {"extraversion": -0.15},

        # High Agreeableness
        "kind": {"agreeableness": 0.2}, "gentle": {"agreeableness": 0.15}, "compassionate": {"agreeableness": 0.2},
        "trusting": {"agreeableness": 0.15}, "helpful": {"agreeableness": 0.15}, "generous": {"agreeableness": 0.15},
        # Low Agreeableness
        "ruthless": {"agreeableness": -0.2}, "cold": {"agreeableness": -0.15}, "cruel": {"agreeableness": -0.2},
        "suspicious": {"agreeableness": -0.15}, "selfish": {"agreeableness": -0.15}, "harsh": {"agreeableness": -0.1},

        # High Neuroticism
        "anxious": {"neuroticism": 0.2}, "paranoid": {"neuroticism": 0.2}, "fearful": {"neuroticism": 0.15},
        "troubled": {"neuroticism": 0.15}, "tormented": {"neuroticism": 0.2}, "unstable": {"neuroticism": 0.2},
        # Low Neuroticism
        "calm": {"neuroticism": -0.15}, "stoic": {"neuroticism": -0.2}, "unflappable": {"neuroticism": -0.2},
        "confident": {"neuroticism": -0.15}, "serene": {"neuroticism": -0.15}, "composed": {"neuroticism": -0.15},
    }

    def _generate_ocean_for_character(
        self,
        name: str,
        description: str = "",
        traits: List[str] = None,
        role: str = ""
    ) -> OCEANProfile:
        """
        Generate OCEAN profile for ANY character.

        Priority:
        1. Use explicit traits if available (most reliable)
        2. Infer from role/title keywords
        3. Infer from description keywords
        4. Add narrative randomness to avoid bland 0.5 defaults

        The result is always interesting - never just (0.5, 0.5, 0.5, 0.5, 0.5).
        """
        # Start with slight random variation around 0.5 (not flat)
        scores = {
            "openness": 0.5 + random.uniform(-0.15, 0.15),
            "conscientiousness": 0.5 + random.uniform(-0.15, 0.15),
            "extraversion": 0.5 + random.uniform(-0.15, 0.15),
            "agreeableness": 0.5 + random.uniform(-0.15, 0.15),
            "neuroticism": 0.5 + random.uniform(-0.15, 0.15),
        }

        hints_applied = 0

        # 1. If we have explicit traits, use them (strongest signal)
        if traits:
            for trait in traits:
                trait_lower = trait.lower().strip()
                if trait_lower in self.TRAIT_TO_OCEAN:
                    for dimension, delta in self.TRAIT_TO_OCEAN[trait_lower].items():
                        scores[dimension] += delta
                        hints_applied += 1

        # 2. Check name/role for archetype hints
        text_to_check = f"{name} {role}".lower()
        for role_keyword, role_scores in self.ROLE_OCEAN_HINTS.items():
            if role_keyword in text_to_check:
                for dimension, value in role_scores.items():
                    # Blend toward the archetype value
                    scores[dimension] = scores[dimension] * 0.5 + value * 0.5
                    hints_applied += 1
                break  # Only apply one role archetype

        # 3. Check description for personality hints
        if description:
            desc_lower = description.lower()
            for keyword, deltas in self.DESCRIPTION_OCEAN_HINTS.items():
                if keyword in desc_lower:
                    for dimension, delta in deltas.items():
                        scores[dimension] += delta
                        hints_applied += 1

        # 4. If we still have no strong signal, add more dramatic randomness
        # This ensures every character is interesting, not bland
        if hints_applied < 2:
            # Pick 1-2 dimensions to make more extreme
            dimensions = list(scores.keys())
            extreme_dims = random.sample(dimensions, k=random.randint(1, 2))
            for dim in extreme_dims:
                # Push toward high or low
                if random.random() > 0.5:
                    scores[dim] = random.uniform(0.65, 0.85)  # High
                else:
                    scores[dim] = random.uniform(0.15, 0.35)  # Low

        # Clamp all values to valid range
        for dim in scores:
            scores[dim] = max(0.0, min(1.0, scores[dim]))

        return OCEANProfile(**scores)

    def _clean_json_response(self, text: str) -> str:
        """Clean markdown fences from LLM response."""
        cleaned = text.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _parse_extraction_response(self, text: str) -> Dict[str, Any]:
        """Parse Gemini's extraction response with robust error handling."""
        cleaned = self._clean_json_response(text)

        # Try direct parse first
        try:
            data = json.loads(cleaned)
            logger.debug(f"[JSON PARSE] Successfully parsed JSON directly ({len(cleaned)} chars)")
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"[JSON PARSE] Direct JSON parse failed at position {e.pos}: {e.msg}")
            logger.debug(f"[JSON PARSE] Failed text sample (first 200 chars): {cleaned[:200]}")

        # Try to extract JSON object from response
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            json_str = match.group()
            logger.debug(f"[JSON PARSE] Extracted JSON object from text ({len(json_str)} chars)")
            try:
                data = json.loads(json_str)
                logger.debug(f"[JSON PARSE] Successfully parsed extracted JSON")
                return data
            except json.JSONDecodeError as e:
                logger.warning(f"[JSON PARSE] Extracted JSON parse failed at position {e.pos}: {e.msg}")

                # Try to repair truncated JSON (common with large outputs)
                # Find where entities array ends and try to salvage
                try:
                    logger.debug(f"[JSON PARSE] Attempting to salvage entities from malformed JSON")
                    # Look for the last complete entity
                    entities_match = re.search(r'"entities"\s*:\s*\[([\s\S]*)', json_str)
                    if entities_match:
                        entities_content = entities_match.group(1)
                        # Find all complete entity objects
                        entity_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                        entities = re.findall(entity_pattern, entities_content)

                        if entities:
                            logger.info(f"[JSON PARSE] Salvaged {len(entities)} entities from truncated response")
                            salvaged_entities = []
                            for ent_str in entities:
                                try:
                                    ent = json.loads(ent_str)
                                    if "name" in ent:  # Valid entity
                                        salvaged_entities.append(ent)
                                except Exception as entity_err:
                                    logger.debug(f"[JSON PARSE] Failed to parse salvaged entity: {entity_err}")
                                    continue

                            if salvaged_entities:
                                logger.info(f"[JSON PARSE] Successfully salvaged {len(salvaged_entities)} valid entities")
                                return {"entities": salvaged_entities, "relationships": []}

                except Exception as repair_err:
                    logger.warning(f"[JSON PARSE] JSON repair attempt failed: {repair_err}")

        # Log a sample of what we got for debugging
        logger.error(f"[JSON PARSE] FAILED to parse extraction response")
        logger.error(f"[JSON PARSE] First 500 chars: {cleaned[:500]}")
        logger.error(f"[JSON PARSE] Last 500 chars: {cleaned[-500:]}")
        logger.error(f"[JSON PARSE] Total length: {len(cleaned)} chars")
        return {"entities": [], "relationships": []}

    async def parse_lore(self, text: str) -> ParsedLoreResult:
        """
        Parse raw lore text into structured entities and relationships.

        Args:
            text: Raw lore text to parse

        Returns:
            ParsedLoreResult with extracted entities and relationships
        """
        if not text or len(text.strip()) < 20:
            return ParsedLoreResult(entities=[], relationships=[])

        if not self.model:
            logger.warning("No Gemini model available, using fallback")
            return await self._fallback_parse(text)

        prompt = self.EXTRACTION_PROMPT.format(text=text)

        # Check document size - warn for very large docs
        word_count = len(text.split())
        logger.info(f"LoreParsingAgent: Processing {word_count} words, {len(text)} chars")

        if word_count > 5000:
            logger.warning(f"Large document detected ({word_count} words). May require chunking.")

        try:
            loop = asyncio.get_event_loop()

            def _sync_generate():
                return self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.1,  # Lower temp for more consistent extraction
                        "max_output_tokens": 8192,  # More tokens for exhaustive extraction
                    }
                )

            # Generous timeout - only admins use this, let it cook
            timeout_seconds = 600.0  # 10 minutes - take your time, Gemini
            logger.info(f"LoreParsingAgent: Using {timeout_seconds}s timeout")

            response = await asyncio.wait_for(
                loop.run_in_executor(_executor, _sync_generate),
                timeout=timeout_seconds
            )

            logger.info(f"LoreParsingAgent: Gemini returned {len(response.text)} chars")

            parsed = self._parse_extraction_response(response.text)

            if not parsed.get("entities"):
                logger.error("Gemini returned no entities - may have failed silently")
                # Return empty result with error indicator instead of garbage fallback
                return ParsedLoreResult(
                    entities=[ExtractedEntity(
                        name="EXTRACTION_FAILED",
                        entity_type="Concept",
                        description="The AI extraction returned no entities. The document may be too large or malformed. Try with a smaller section.",
                        traits=[],
                        tags=["error"],
                        verbatim_text="",
                    )],
                    relationships=[],
                )

            entities = []
            for e in parsed.get("entities", []):
                entities.append(ExtractedEntity(
                    name=e.get("name", "Unknown"),
                    aliases=e.get("aliases", []),
                    entity_type=e.get("entity_type", "Concept"),
                    description=e.get("description", ""),
                    traits=e.get("traits", []),
                    tags=e.get("tags", []),
                    temporal_cues=e.get("temporal_cues", []),
                    verbatim_text=e.get("verbatim_text", ""),
                    goals=e.get("goals", []),
                    secrets=e.get("secrets", []),
                    fears=e.get("fears", []),
                    confidence=e.get("confidence", "high"),
                    uncertainties=e.get("uncertainties", []),
                ))

            relationships = []
            for r in parsed.get("relationships", []):
                relationships.append(ExtractedRelationship(
                    source=r.get("source", ""),
                    target=r.get("target", ""),
                    relationship_type=r.get("relationship_type", "RELATED_TO"),
                    description=r.get("description", ""),
                    confidence=r.get("confidence", "high"),
                    uncertainty=r.get("uncertainty"),
                ))

            # Parse top-level uncertainties (questions for admin review)
            uncertainties = []
            for u in parsed.get("uncertainties", []):
                uncertainties.append(UncertaintyFlag(
                    category=u.get("category", "entity"),
                    question=u.get("question", ""),
                    context=u.get("context", ""),
                    suggestions=u.get("suggestions", []),
                ))

            # Parse world characteristics if present
            world_chars = None
            wc_data = parsed.get("world_characteristics")
            if wc_data and isinstance(wc_data, dict):
                world_chars = ExtractedWorldCharacteristics(
                    primary_genre=wc_data.get("primary_genre"),
                    sub_genres=wc_data.get("sub_genres", []),
                    magic_level=wc_data.get("magic_level"),
                    technology_level=wc_data.get("technology_level"),
                    supernatural_presence=wc_data.get("supernatural_presence"),
                    tone=wc_data.get("tone"),
                    narrative_style=wc_data.get("narrative_style", []),
                    moral_complexity=wc_data.get("moral_complexity"),
                    lethality=wc_data.get("lethality"),
                    themes=wc_data.get("themes", []),
                    social_structures=wc_data.get("social_structures", []),
                    power_scale=wc_data.get("power_scale"),
                    scope=wc_data.get("scope"),
                    world_constants=wc_data.get("world_constants", []),
                    sensory_palette=wc_data.get("sensory_palette", []),
                )
                logger.info(f"LoreParsingAgent inferred world characteristics: genre={world_chars.primary_genre}, tone={world_chars.tone}")

            logger.info(f"LoreParsingAgent extracted {len(entities)} entities, {len(relationships)} relationships, {len(uncertainties)} uncertainties")

            return ParsedLoreResult(
                entities=entities,
                relationships=relationships,
                world_characteristics=world_chars,
                uncertainties=uncertainties,
            )

        except asyncio.TimeoutError:
            logger.error(f"Gemini extraction timed out after {timeout_seconds}s for {word_count} word document")
            # Return clear error instead of garbage fallback
            return ParsedLoreResult(
                entities=[ExtractedEntity(
                    name="TIMEOUT_ERROR",
                    entity_type="Concept",
                    description=f"Extraction timed out after {timeout_seconds} seconds. The document ({word_count} words) may be too large. Try splitting it into smaller sections.",
                    traits=[],
                    tags=["error"],
                    verbatim_text="",
                )],
                relationships=[],
            )
        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            # Return clear error instead of garbage fallback
            return ParsedLoreResult(
                entities=[ExtractedEntity(
                    name="EXTRACTION_ERROR",
                    entity_type="Concept",
                    description=f"Extraction failed with error: {str(e)}. Please try again or use a smaller document.",
                    traits=[],
                    tags=["error"],
                    verbatim_text="",
                )],
                relationships=[],
            )

    async def _fallback_parse(self, text: str) -> ParsedLoreResult:
        """Simple regex-based fallback when Gemini is unavailable."""
        entities = []

        # Look for capitalized names (simple heuristic)
        name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
        names = set(re.findall(name_pattern, text))

        for name in names:
            if len(name) > 2:
                entities.append(ExtractedEntity(
                    name=name,
                    entity_type="Concept",
                    description=f"Extracted from lore text",
                    traits=[],
                    tags=[],
                    verbatim_text="",
                ))

        return ParsedLoreResult(entities=entities[:20], relationships=[])

    async def parse_and_store(
        self,
        text: str,
        db,  # Neo4jDatabase
        source_name: str = "lore_upload",
        world_id: str = None,
        curated_world_id: str = None,
        genre: str = None,
        session_id: str = None,
    ) -> ParsedLoreResult:
        """
        Parse lore text and store entities in Neo4j with OCEAN profiles.

        Args:
            text: Raw lore text
            db: Neo4j database instance
            source_name: Source identifier for tracking
            world_id: Session-scoped world ID for entity isolation
            curated_world_id: Original curated world ID (e.g., "eldoria") for filtering
            genre: Genre to tag entities with (fantasy, sci_fi, horror, etc.)
            session_id: Session ID for gameplay tracking

        Returns:
            ParsedLoreResult with storage counts
        """
        logger.info(f"[LORE INGESTION] Starting parse_and_store: source='{source_name}', world_id='{world_id}', curated='{curated_world_id}'")
        logger.info(f"[LORE INGESTION] Text length: {len(text)} chars, {len(text.split())} words")
        
        try:
            result = await self.parse_lore(text)
            logger.info(f"[LORE INGESTION] Parse completed: {len(result.entities)} entities extracted")
        except Exception as e:
            logger.error(f"[LORE INGESTION] Parse failed: {type(e).__name__}: {str(e)}", exc_info=True)
            raise

        if not result.entities:
            logger.info("[LORE INGESTION] No entities extracted, returning empty result")
            return result

        timestamp = datetime.now(timezone.utc).isoformat()
        entities_stored = 0
        characters_with_ocean = 0

        # Build mapping of entity names to canon_ids for relationship resolution
        # This prevents cross-world linking by keeping track of entities in THIS ingestion scope
        entity_name_to_canon_id: Dict[str, str] = {}

        logger.info(f"[LORE INGESTION] Beginning storage phase: {len(result.entities)} entities, {len(result.relationships)} relationships")

        # Ensure LoreBase node exists if we have a curated world
        if curated_world_id:
            logger.info(f"[LORE INGESTION] Creating/updating LoreBase node for '{curated_world_id}'")
            try:
                await db.execute("""
                    MERGE (lb:LoreBase {lore_id: $lore_id})
                    ON CREATE SET lb.created_at = $timestamp,
                                  lb.name = $lore_id,
                                  lb.entity_type = 'World',
                                  lb.world_id = $lore_id,
                                  lb.curated_world_id = $lore_id
                    SET lb.last_ingested = $timestamp
                """, {"lore_id": curated_world_id, "timestamp": timestamp})
                logger.info(f"Ensured LoreBase node exists for {curated_world_id}")
            except Exception as e:
                logger.warning(f"Failed to create LoreBase node: {e}")

        # Extract world_id from source if not provided
        if not world_id and source_name:
            if source_name.startswith("lore_base:"):
                world_id = source_name.split("lore_base:")[1]
            elif source_name.startswith("session:"):
                # For sessions, world_id should be passed explicitly
                world_id = None

        id_world = curated_world_id or world_id
        pending_duplicates = []
        entities_auto_merged = 0

        # Store entities with smart duplicate detection
        logger.info(f"[LORE INGESTION] Storing {len(result.entities)} entities...")
        for idx, entity in enumerate(result.entities, 1):
            logger.debug(f"[LORE INGESTION] Processing entity {idx}/{len(result.entities)}: '{entity.name}' ({entity.entity_type})")

            # Validate entity before storage
            try:
                # Check required fields
                if not entity.name or not entity.name.strip():
                    logger.error(f"[LORE INGESTION] Entity {idx} has empty name, skipping")
                    continue

                if not entity.entity_type or not entity.entity_type.strip():
                    logger.error(f"[LORE INGESTION] Entity '{entity.name}' has empty entity_type, skipping")
                    continue

                if not entity.description or not entity.description.strip():
                    logger.warning(f"[LORE INGESTION] Entity '{entity.name}' has empty description (will store anyway)")

                # Validate entity type is in valid list
                valid_types = ["Character", "Location", "Faction", "Item", "Event", "Concept"]
                if entity.entity_type not in valid_types:
                    logger.warning(f"[LORE INGESTION] Entity '{entity.name}' has invalid type '{entity.entity_type}', will be treated as Entity")

            except Exception as ve:
                logger.error(f"[LORE INGESTION] Validation failed for entity {idx}: {ve}", exc_info=True)
                continue

            # Check for existing entity in this world BEFORE creating (duplicate detection)
            existing = None
            if id_world:
                try:
                    existing = await self._find_existing_entity(entity, id_world, db)
                except Exception as e:
                    logger.warning(f"Duplicate check failed for {entity.name}: {e}")

            # Handle duplicates
            if existing:
                if existing["match_type"] == "exact" or existing["similarity"] >= 0.95:
                    # EXACT MATCH or ALIAS MATCH - Auto-merge into existing entity
                    logger.info(f"Auto-merging '{entity.name}' into existing entity '{existing['name']}' (match_type={existing['match_type']})")

                    # Update existing entity with any new info
                    update_props = {"updated_at": timestamp}

                    # Merge aliases (add new entity's name and aliases if not present)
                    existing_aliases = list(existing.get("aliases") or [])
                    if entity.name not in existing_aliases and entity.name.lower() != existing["name"].lower():
                        existing_aliases.append(entity.name)
                    for alias in (entity.aliases or []):
                        if alias not in existing_aliases:
                            existing_aliases.append(alias)
                    update_props["aliases"] = existing_aliases

                    # Update description if new one is longer/more detailed
                    if entity.description and len(entity.description) > len(existing.get("description") or ""):
                        update_props["description"] = entity.description

                    # Merge goals, secrets, fears for characters and factions
                    if entity.entity_type in ["Character", "Faction"]:
                        for field in ["goals", "secrets", "fears"]:
                            existing_vals = getattr(entity, field, []) or []
                            if existing_vals:
                                update_props[field] = existing_vals

                    await db.execute("""
                        MATCH (e:Entity {canon_id: $canon_id})
                        SET e += $props
                    """, {"canon_id": existing["canon_id"], "props": update_props})

                    # Add to mapping for relationship resolution
                    entity_name_to_canon_id[entity.name.lower()] = existing["canon_id"]
                    # Also map any aliases
                    for alias in (entity.aliases or []):
                        entity_name_to_canon_id[alias.lower()] = existing["canon_id"]

                    entities_auto_merged += 1
                    if entity.entity_type == "Character":
                        characters_with_ocean += 1  # Count for stats
                    continue  # Skip to next entity

                else:
                    # PROBABLE MATCH - Flag for admin review, don't create
                    logger.info(f"Flagging '{entity.name}' as potential duplicate of '{existing['name']}' (similarity={existing['similarity']:.0%})")

                    pending_duplicates.append(PendingDuplicate(
                        new_entity=entity,
                        existing_entity_id=existing["canon_id"],
                        existing_entity_name=existing["name"],
                        existing_entity_type=existing["entity_type"],
                        existing_description=existing.get("description", ""),
                        existing_aliases=existing.get("aliases") or [],
                        similarity_score=existing["similarity"],
                        match_reason=existing["match_type"],
                    ))
                    continue  # Skip to next entity - don't create until admin approves

            # NO MATCH - Create new entity
            try:
                canon_id = _generate_human_readable_id(
                    name=entity.name,
                    entity_type=entity.entity_type,
                    world_id=id_world
                )
                logger.debug(f"[LORE INGESTION] Generated canon_id: {canon_id}")
            except Exception as id_err:
                logger.error(f"[LORE INGESTION] Failed to generate canon_id for '{entity.name}': {id_err}", exc_info=True)
                continue

            props = {
                "canon_id": canon_id,
                "name": entity.name,
                "aliases": entity.aliases,
                "entity_type": entity.entity_type,
                "description": entity.description,
                "content": entity.verbatim_text or entity.description,
                "source": source_name,
                "world_id": world_id,  # Session-scoped world ID for isolation
                "curated_world_id": curated_world_id,  # Original curated world ID for filtering
                "genre": genre,  # Genre for filtering
                "session_id": session_id,  # Session tracking
                "confidence_level": "AI_GENERATED",
                "approval_status": "PENDING",
                "created_at": timestamp,
                "tags": entity.tags,
                "temporal_cues": entity.temporal_cues,
            }

            # Generate OCEAN profile for ALL characters
            # Uses traits if available, otherwise infers from name/description/role
            # Never defaults to bland 0.5 across the board - always narratively interesting
            if entity.entity_type == "Character":
                try:
                    logger.debug(f"[LORE INGESTION] Generating OCEAN profile for character '{entity.name}'")
                    ocean = self._generate_ocean_for_character(
                        name=entity.name,
                        description=entity.description or "",
                        traits=entity.traits,
                        role=""  # Could extract role from name/description in future
                    )
                    
                    # Validate OCEAN scores
                    for key in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
                        value = getattr(ocean, key, 0.5)
                        if not isinstance(value, (int, float)):
                            logger.error(f"[LORE INGESTION] OCEAN {key} for '{entity.name}' is not numeric: {type(value)}")
                            value = 0.5
                        if value < 0.0 or value > 1.0:
                            logger.warning(f"[LORE INGESTION] OCEAN {key} for '{entity.name}' out of range ({value}), clamping to [0.0, 1.0]")
                            value = max(0.0, min(1.0, value))
                        props[key] = value
                    
                    if entity.traits:
                        props["personality_traits"] = entity.traits
                    # Store goals, secrets, fears for richer character data
                    if entity.goals:
                        props["goals"] = entity.goals
                    if entity.secrets:
                        props["secrets"] = entity.secrets
                    if entity.fears:
                        props["fears"] = entity.fears
                    characters_with_ocean += 1
                    logger.debug(f"[LORE INGESTION] OCEAN profile generated successfully for '{entity.name}'")
                except Exception as ocean_err:
                    logger.error(f"[LORE INGESTION] OCEAN generation failed for '{entity.name}': {ocean_err}", exc_info=True)
                    # Continue without OCEAN profile rather than failing the entire entity

            # Store goals, secrets, fears for Factions (collective motivations)
            elif entity.entity_type == "Faction":
                if entity.goals:
                    props["goals"] = entity.goals
                if entity.secrets:
                    props["secrets"] = entity.secrets
                if entity.fears:
                    props["fears"] = entity.fears
                logger.debug(f"[LORE INGESTION] Added faction motivations for '{entity.name}'")

            try:
                # Use parameterized label (safe because we control entity_type values)
                label = entity.entity_type.replace(" ", "_")
                if label not in ["Character", "Location", "Faction", "Item", "Event", "Concept"]:
                    logger.warning(f"[LORE INGESTION] Invalid label '{label}' for '{entity.name}', using 'Entity'")
                    label = "Entity"

                # Create new entity (duplicates handled by _find_existing_entity above)
                query = f"""
                    CREATE (e:`{label}` $props)
                    SET e:Entity
                """
                logger.debug(f"[LORE INGESTION] Executing Neo4j CREATE for '{entity.name}'")

                try:
                    await db.execute(query, {"props": props})
                    logger.debug(f"[LORE INGESTION] Successfully stored '{entity.name}' in Neo4j")
                except Exception as db_err:
                    logger.error(
                        f"[LORE INGESTION] Neo4j CREATE failed for '{entity.name}': {type(db_err).__name__}: {str(db_err)}\n"
                        f"Query: {query[:200]}...\n"
                        f"Params: props keys={list(props.keys())}",
                        exc_info=True
                    )
                    raise  # Re-raise to be caught by outer try-catch

                # Create EXISTS_IN relationship to LoreBase for graph connectivity
                if curated_world_id:
                    try:
                        await db.execute("""
                            MATCH (e:Entity {canon_id: $canon_id})
                            MATCH (lb:LoreBase {lore_id: $world_id})
                            MERGE (e)-[:EXISTS_IN]->(lb)
                        """, {"canon_id": canon_id, "world_id": curated_world_id})
                        logger.debug(f"[LORE INGESTION] Created EXISTS_IN relationship for '{entity.name}'")
                    except Exception as rel_err:
                        logger.warning(f"[LORE INGESTION] Failed to create EXISTS_IN relationship for '{entity.name}': {rel_err}")

                # Add to mapping for relationship resolution
                entity_name_to_canon_id[entity.name.lower()] = canon_id
                # Also map any aliases
                for alias in (entity.aliases or []):
                    entity_name_to_canon_id[alias.lower()] = canon_id

                entities_stored += 1

            except Exception as e:
                logger.error(f"[LORE INGESTION] Failed to store entity '{entity.name}': {type(e).__name__}: {str(e)}", exc_info=True)

        # Store relationships using canon_id mapping with world-scoped fallback
        relationships_stored = 0
        relationships_skipped = 0
        logger.info(f"[LORE INGESTION] Storing {len(result.relationships)} relationships...")
        logger.debug(f"[LORE INGESTION] Entity name to canon_id mapping has {len(entity_name_to_canon_id)} entries")
        
        for idx, rel in enumerate(result.relationships, 1):
            try:
                logger.debug(f"[LORE INGESTION] Processing relationship {idx}/{len(result.relationships)}: '{rel.source}' -> '{rel.target}' ({rel.relationship_type})")
                
                # Validate relationship
                if not rel.source or not rel.target:
                    logger.warning(f"[LORE INGESTION] Relationship {idx} has empty source or target, skipping")
                    relationships_skipped += 1
                    continue
                
                # Validate and sanitize relationship type to prevent injection
                rel_type = rel.relationship_type.upper().replace(" ", "_")
                # Security: Only allow alphanumeric and underscore (safe for Cypher)
                if not re.match(r"^[A-Z_]+$", rel_type):
                    logger.warning(f"[LORE INGESTION] Invalid relationship type '{rel.relationship_type}', using RELATED_TO")
                    rel_type = "RELATED_TO"

                # Resolve source and target to canon_ids
                # Priority 1: Use canon_id mapping from this ingestion scope
                source_canon_id = entity_name_to_canon_id.get(rel.source.lower())
                target_canon_id = entity_name_to_canon_id.get(rel.target.lower())

                # Priority 2: If not in mapping, try world-scoped name lookup
                # This handles cases where we're referring to existing entities in the world
                if not source_canon_id and id_world:
                    try:
                        source_result = await db.execute("""
                            MATCH (e:Entity)
                            WHERE (toLower(e.name) = toLower($name) OR toLower($name) IN [alias IN e.aliases | toLower(alias)])
                              AND (e.world_id = $world_id OR e.curated_world_id = $world_id)
                            RETURN e.canon_id AS canon_id
                            LIMIT 1
                        """, {"name": rel.source, "world_id": id_world})
                        if source_result:
                            source_canon_id = source_result[0]["canon_id"]
                            logger.debug(f"[LORE INGESTION] Resolved source '{rel.source}' to existing entity {source_canon_id} in world {id_world}")
                    except Exception as lookup_err:
                        logger.warning(f"[LORE INGESTION] Failed to lookup source entity '{rel.source}': {lookup_err}")

                if not target_canon_id and id_world:
                    try:
                        target_result = await db.execute("""
                            MATCH (e:Entity)
                            WHERE (toLower(e.name) = toLower($name) OR toLower($name) IN [alias IN e.aliases | toLower(alias)])
                              AND (e.world_id = $world_id OR e.curated_world_id = $world_id)
                            RETURN e.canon_id AS canon_id
                            LIMIT 1
                        """, {"name": rel.target, "world_id": id_world})
                        if target_result:
                            target_canon_id = target_result[0]["canon_id"]
                            logger.debug(f"[LORE INGESTION] Resolved target '{rel.target}' to existing entity {target_canon_id} in world {id_world}")
                    except Exception as lookup_err:
                        logger.warning(f"[LORE INGESTION] Failed to lookup target entity '{rel.target}': {lookup_err}")

                # If we still can't resolve both endpoints, skip this relationship with a warning
                if not source_canon_id or not target_canon_id:
                    missing = []
                    if not source_canon_id:
                        missing.append(f"source '{rel.source}'")
                    if not target_canon_id:
                        missing.append(f"target '{rel.target}'")
                    logger.warning(
                        f"[LORE INGESTION] Skipping relationship '{rel.source}' --[{rel.relationship_type}]--> '{rel.target}': "
                        f"Could not resolve {', '.join(missing)} to canon_id in scope (world={id_world}). "
                        f"This prevents cross-world linking."
                    )
                    relationships_skipped += 1
                    continue

                # Create relationship using canon_ids (world-safe)
                query = f"""
                    MATCH (a:Entity {{canon_id: $source_id}})
                    MATCH (b:Entity {{canon_id: $target_id}})
                    MERGE (a)-[r:`{rel_type}`]->(b)
                    SET r.description = $description,
                        r.source = $source_name,
                        r.created_at = $timestamp
                """
                params = {
                    "source_id": source_canon_id,
                    "target_id": target_canon_id,
                    "description": rel.description,
                    "source_name": source_name,
                    "timestamp": timestamp,
                }
                
                try:
                    await db.execute(query, params)
                    logger.debug(f"[LORE INGESTION] Stored relationship {source_canon_id} --[{rel_type}]--> {target_canon_id}")
                    relationships_stored += 1
                except Exception as db_err:
                    logger.error(
                        f"[LORE INGESTION] Neo4j relationship storage failed: {type(db_err).__name__}: {str(db_err)}\n"
                        f"Query: {query[:200]}...\n"
                        f"Params: {params}",
                        exc_info=True
                    )
                    relationships_skipped += 1

            except Exception as e:
                logger.error(f"[LORE INGESTION] Failed to process relationship '{rel.source}' -> '{rel.target}': {type(e).__name__}: {str(e)}", exc_info=True)
                relationships_skipped += 1

        result.entities_stored = entities_stored
        result.entities_auto_merged = entities_auto_merged
        result.relationships_stored = relationships_stored
        result.characters_with_ocean = characters_with_ocean
        result.pending_duplicates = pending_duplicates

        # Store inferred world characteristics on LoreBase (if not already set by admin)
        if curated_world_id and result.world_characteristics:
            try:
                wc = result.world_characteristics
                wc_json = json.dumps({
                    "primary_genre": wc.primary_genre,
                    "sub_genres": wc.sub_genres,
                    "magic_level": wc.magic_level,
                    "technology_level": wc.technology_level,
                    "supernatural_presence": wc.supernatural_presence,
                    "tone": wc.tone,
                    "narrative_style": wc.narrative_style,
                    "moral_complexity": wc.moral_complexity,
                    "lethality": wc.lethality,
                    "themes": wc.themes,
                    "social_structures": wc.social_structures,
                    "power_scale": wc.power_scale,
                    "scope": wc.scope,
                    "world_constants": wc.world_constants,
                    "sensory_palette": wc.sensory_palette,
                })
                # Only set if not already present (admin-set values take precedence)
                await db.execute("""
                    MATCH (lb:LoreBase {lore_id: $lore_id})
                    WHERE lb.world_characteristics_json IS NULL
                    SET lb.world_characteristics_json = $wc_json,
                        lb.world_characteristics_source = 'AI_INFERRED'
                """, {"lore_id": curated_world_id, "wc_json": wc_json})
                logger.info(f"Stored inferred world characteristics for {curated_world_id}")
            except Exception as e:
                logger.warning(f"Failed to store world characteristics: {e}")

        logger.info(
            f"LoreParsingAgent: {entities_stored} new entities, "
            f"{entities_auto_merged} auto-merged, "
            f"{len(pending_duplicates)} pending review, "
            f"{relationships_stored} relationships stored, "
            f"{relationships_skipped} relationships skipped (could not resolve to canon_id), "
            f"{characters_with_ocean} characters with OCEAN"
        )

        return result
