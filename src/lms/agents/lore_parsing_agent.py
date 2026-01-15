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


class ExtractedRelationship(BaseModel):
    """Relationship extracted from lore text."""
    source: str
    target: str
    relationship_type: str
    description: str = ""


class OCEANProfile(BaseModel):
    """OCEAN personality profile."""
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5


class ParsedLoreResult(BaseModel):
    """Result of parsing lore text."""
    entities: List[ExtractedEntity]
    relationships: List[ExtractedRelationship]
    entities_stored: int = 0
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

Your task: Extract EVERY entity and relationship from the lore text below. Be EXHAUSTIVE - missing entities breaks the game.

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

## ENTITY TYPES & IDENTIFICATION

| Type | Identify By | Examples |
|------|-------------|----------|
| CHARACTER | Named/titled individuals, people with agency | "Queen Seraphina", "the blacksmith Gorn", "a mysterious stranger" |
| LOCATION | Places, buildings, regions, realms, landmarks | "Thornhaven", "the Amber Plains", "Castle Dreadmoor" |
| FACTION | Groups, organizations, families, guilds, armies, cults | "House Blackwood", "the Thieves Guild", "the Iron Legion" |
| ITEM | Objects with narrative significance, artifacts, weapons | "the Crown of Shadows", "Varen's sword", "the ancient tome" |
| EVENT | Past/future occurrences, battles, ceremonies, disasters | "the Fall of Eldoria", "the Crimson Wedding", "the Great Flood" |
| CONCEPT | Magic systems, prophecies, religions, abstract forces | "blood magic", "the Prophecy of Ash", "the Old Ways" |

## CHARACTER PERSONALITY EXTRACTION

For EVERY Character, infer personality traits from:
- Direct descriptions ("she was cunning", "known for his kindness")
- Actions ("he betrayed his allies" → treacherous, cunning)
- Dialogue style ("spoke softly" → gentle, reserved)
- Reputation ("feared by all" → intimidating, powerful)
- Relationships ("beloved by the people" → charismatic, kind)

**Trait Vocabulary (use these exact words when applicable):**
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
            "tags": ["role1", "role2"],
            "temporal_cues": ["time reference 1", "time reference 2"],
            "verbatim_text": "Copy the EXACT sentences from the source that describe this entity"
        }}
    ],
    "relationships": [
        {{
            "source": "Entity Name",
            "target": "Other Entity Name",
            "relationship_type": "TYPE",
            "description": "How/why they are connected"
        }}
    ]
}}

## FIELD DEFINITIONS

| Field | Required | Description |
|-------|----------|-------------|
| name | Yes | Primary canonical name |
| aliases | Yes | Alternative names, titles, nicknames (empty array if none) |
| entity_type | Yes | One of: Character, Location, Faction, Item, Event, Concept |
| description | Yes | 2-3 sentences: who/what it is, why it matters to the narrative |
| traits | Characters only | Personality traits from vocabulary above (3-6 traits) |
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
3. **VERBATIM REQUIRED**: Always include the exact source text for each entity.
4. **INFER RELATIONSHIPS**: "the king's advisor" → SERVES relationship. "sworn enemies" → ENEMY_OF.
5. **CHARACTER TRAITS REQUIRED**: Every Character MUST have 3-6 personality traits inferred from text.
6. **HANDLE PRONOUNS**: Resolve "he", "she", "they" to actual entity names.
7. **EXTRACT NESTED ENTITIES**: "the ruins of Old Valdris" → Extract BOTH "ruins" (Location) AND "Old Valdris" (Faction/Location).

## EXAMPLE

Input: "Queen Mira the Wise ruled Thornhaven with an iron will but a kind heart. Her brother, Prince Caden, secretly plotted against her from his exile in the Shadowfen."

Output:
{{
    "entities": [
        {{
            "name": "Queen Mira",
            "aliases": ["Mira the Wise", "The Queen"],
            "entity_type": "Character",
            "description": "Ruler of Thornhaven known for her wisdom. Governs with strict authority but genuine compassion for her people.",
            "traits": ["wise", "disciplined", "kind", "authoritative", "compassionate"],
            "tags": ["royalty", "ruler", "queen"],
            "temporal_cues": [],
            "verbatim_text": "Queen Mira the Wise ruled Thornhaven with an iron will but a kind heart."
        }},
        {{
            "name": "Prince Caden",
            "aliases": ["The Exiled Prince"],
            "entity_type": "Character",
            "description": "Queen Mira's brother, living in exile. Harbors treasonous ambitions against his sister's throne.",
            "traits": ["cunning", "ambitious", "treacherous", "secretive", "resentful"],
            "tags": ["royalty", "exile", "conspirator"],
            "temporal_cues": [],
            "verbatim_text": "Her brother, Prince Caden, secretly plotted against her from his exile in the Shadowfen."
        }},
        {{
            "name": "Thornhaven",
            "aliases": [],
            "entity_type": "Location",
            "description": "A realm or city ruled by Queen Mira. The seat of royal power.",
            "traits": [],
            "tags": ["kingdom", "capital", "ruled"],
            "temporal_cues": [],
            "verbatim_text": "Queen Mira the Wise ruled Thornhaven"
        }},
        {{
            "name": "Shadowfen",
            "aliases": [],
            "entity_type": "Location",
            "description": "A remote region where Prince Caden lives in exile. Likely a frontier or lawless area.",
            "traits": [],
            "tags": ["exile location", "remote", "frontier"],
            "temporal_cues": [],
            "verbatim_text": "from his exile in the Shadowfen"
        }}
    ],
    "relationships": [
        {{"source": "Queen Mira", "target": "Thornhaven", "relationship_type": "RULES", "description": "Mira is the ruling queen of Thornhaven"}},
        {{"source": "Prince Caden", "target": "Queen Mira", "relationship_type": "SIBLING_OF", "description": "Caden is Mira's brother"}},
        {{"source": "Prince Caden", "target": "Queen Mira", "relationship_type": "ENEMY_OF", "description": "Caden secretly plots against his sister"}},
        {{"source": "Prince Caden", "target": "Shadowfen", "relationship_type": "RESIDES_IN", "description": "Caden lives in exile in the Shadowfen"}}
    ]
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
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash-exp")
            logger.info("LoreParsingAgent initialized with Gemini")
        else:
            logger.warning("LoreParsingAgent: No API key, will use fallback parsing")

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

    def _clean_json_response(self, text: str) -> str:
        """Clean markdown fences from LLM response."""
        cleaned = text.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _parse_extraction_response(self, text: str) -> Dict[str, Any]:
        """Parse Gemini's extraction response."""
        cleaned = self._clean_json_response(text)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        logger.error("Failed to parse extraction response")
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

            response = await asyncio.wait_for(
                loop.run_in_executor(_executor, _sync_generate),
                timeout=120.0  # More time for thorough extraction
            )

            parsed = self._parse_extraction_response(response.text)

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
                ))

            relationships = []
            for r in parsed.get("relationships", []):
                relationships.append(ExtractedRelationship(
                    source=r.get("source", ""),
                    target=r.get("target", ""),
                    relationship_type=r.get("relationship_type", "RELATED_TO"),
                    description=r.get("description", ""),
                ))

            logger.info(f"LoreParsingAgent extracted {len(entities)} entities, {len(relationships)} relationships")

            return ParsedLoreResult(
                entities=entities,
                relationships=relationships,
            )

        except asyncio.TimeoutError:
            logger.error("Gemini extraction timed out")
            return await self._fallback_parse(text)
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return await self._fallback_parse(text)

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
        result = await self.parse_lore(text)

        if not result.entities:
            return result

        timestamp = datetime.now(timezone.utc).isoformat()
        entities_stored = 0
        characters_with_ocean = 0

        # Extract world_id from source if not provided
        if not world_id and source_name:
            if source_name.startswith("lore_base:"):
                world_id = source_name.split("lore_base:")[1]
            elif source_name.startswith("session:"):
                # For sessions, world_id should be passed explicitly
                world_id = None

        # Store entities
        for entity in result.entities:
            # Generate human-readable ID: {world}-{type}-{name}-{short_random}
            # e.g., "eldoria-chr-captain-varn-7f3a"
            id_world = curated_world_id or world_id
            canon_id = _generate_human_readable_id(
                name=entity.name,
                entity_type=entity.entity_type,
                world_id=id_world
            )

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

            # Generate OCEAN profile for characters
            if entity.entity_type == "Character" and entity.traits:
                ocean = self._generate_ocean_from_traits(entity.traits)
                props["openness"] = ocean.openness
                props["conscientiousness"] = ocean.conscientiousness
                props["extraversion"] = ocean.extraversion
                props["agreeableness"] = ocean.agreeableness
                props["neuroticism"] = ocean.neuroticism
                props["personality_traits"] = entity.traits
                characters_with_ocean += 1

            try:
                # Use parameterized label (safe because we control entity_type values)
                label = entity.entity_type.replace(" ", "_")
                if label not in ["Character", "Location", "Faction", "Item", "Event", "Concept"]:
                    label = "Entity"

                await db.execute(f"""
                    MERGE (e:`{label}` {{name: $name}})
                    SET e += $props
                    SET e:Entity
                """, {"name": entity.name, "props": props})

                entities_stored += 1

            except Exception as e:
                logger.error(f"Failed to store entity {entity.name}: {e}")

        # Store relationships
        relationships_stored = 0
        for rel in result.relationships:
            try:
                rel_type = rel.relationship_type.upper().replace(" ", "_")
                if not re.match(r"^[A-Z_]+$", rel_type):
                    rel_type = "RELATED_TO"

                await db.execute(f"""
                    MATCH (a {{name: $source}})
                    MATCH (b {{name: $target}})
                    MERGE (a)-[r:`{rel_type}`]->(b)
                    SET r.description = $description
                    SET r.source = $source_name
                """, {
                    "source": rel.source,
                    "target": rel.target,
                    "description": rel.description,
                    "source_name": source_name,
                })

                relationships_stored += 1

            except Exception as e:
                logger.error(f"Failed to store relationship {rel.source} -> {rel.target}: {e}")

        result.entities_stored = entities_stored
        result.relationships_stored = relationships_stored
        result.characters_with_ocean = characters_with_ocean

        logger.info(
            f"LoreParsingAgent stored {entities_stored} entities, "
            f"{relationships_stored} relationships, "
            f"{characters_with_ocean} characters with OCEAN profiles"
        )

        return result
