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


class ExtractedEntity(BaseModel):
    """Entity extracted from lore text."""
    name: str
    entity_type: str  # Character, Location, Faction, Item, Event, Concept
    description: str
    traits: List[str] = Field(default_factory=list)  # Personality traits for characters
    tags: List[str] = Field(default_factory=list)  # Role tags like "merchant", "warrior"
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

    EXTRACTION_PROMPT = """You are a Lore Extraction Agent for a narrative RPG system.

Analyze the following lore text and extract ALL entities and relationships.

**Entity Types:**
- Character: People, NPCs, named individuals
- Location: Places, buildings, regions, landmarks
- Faction: Groups, organizations, families, guilds
- Item: Objects, artifacts, weapons, treasures
- Event: Historical events, battles, ceremonies
- Concept: Abstract ideas, magic systems, prophecies

**For CHARACTERS, you MUST extract personality traits using these keywords:**
Positive: brave, loyal, kind, wise, patient, calm, creative, curious, charismatic, warm, forgiving, studious, methodical, ambitious, bold
Negative: cunning, cold, vengeful, fearful, aggressive, impulsive, anxious, calculating, ruthless, paranoid, reckless

**Output Format (JSON only, no markdown):**
{{
    "entities": [
        {{
            "name": "Entity Name",
            "entity_type": "Character|Location|Faction|Item|Event|Concept",
            "description": "A 1-2 sentence summary",
            "traits": ["brave", "loyal", "cold"],  // Only for Characters
            "tags": ["warrior", "noble", "merchant"],  // Role/category tags
            "verbatim_text": "Copy the exact sentences from the text that describe this entity"
        }}
    ],
    "relationships": [
        {{
            "source": "Entity Name",
            "target": "Other Entity Name",
            "relationship_type": "LEADS|ALLIED_WITH|ENEMY_OF|LOCATED_IN|MEMBER_OF|OWNS|KNOWS|RIVALS",
            "description": "Brief description of the relationship"
        }}
    ]
}}

**Rules:**
1. Extract ALL named entities, even minor ones
2. For Characters, ALWAYS include personality traits based on descriptive words in the text
3. Include the verbatim_text - copy exact sentences that describe each entity
4. Infer relationships from context (e.g., "his rival" → RIVALS relationship)
5. If no entities found, return: {{"entities": [], "relationships": []}}

TEXT TO ANALYZE:
{text}
"""

    # OCEAN trait mappings
    TRAIT_TO_OCEAN = {
        # High Openness
        "curious": {"openness": 0.15},
        "creative": {"openness": 0.15},
        "studious": {"openness": 0.1, "conscientiousness": 0.05},
        "wise": {"openness": 0.1},
        "imaginative": {"openness": 0.15},

        # Low Openness
        "traditional": {"openness": -0.1},
        "practical": {"openness": -0.05},

        # High Conscientiousness
        "methodical": {"conscientiousness": 0.15},
        "loyal": {"conscientiousness": 0.1, "agreeableness": 0.05},
        "disciplined": {"conscientiousness": 0.15},
        "patient": {"conscientiousness": 0.1, "neuroticism": -0.05},
        "calculating": {"conscientiousness": 0.1, "agreeableness": -0.1},
        "ambitious": {"conscientiousness": 0.1, "extraversion": 0.05},

        # Low Conscientiousness
        "impulsive": {"conscientiousness": -0.15, "neuroticism": 0.05},
        "reckless": {"conscientiousness": -0.15, "neuroticism": -0.05},
        "scattered": {"conscientiousness": -0.1},

        # High Extraversion
        "charismatic": {"extraversion": 0.15},
        "warm": {"extraversion": 0.1, "agreeableness": 0.1},
        "bold": {"extraversion": 0.1, "neuroticism": -0.05},
        "commanding": {"extraversion": 0.15},

        # Low Extraversion
        "cold": {"extraversion": -0.15, "agreeableness": -0.1},
        "reserved": {"extraversion": -0.1},
        "quiet": {"extraversion": -0.1},

        # High Agreeableness
        "kind": {"agreeableness": 0.2},
        "forgiving": {"agreeableness": 0.15},
        "gentle": {"agreeableness": 0.15},
        "compassionate": {"agreeableness": 0.15},

        # Low Agreeableness
        "vengeful": {"agreeableness": -0.2, "neuroticism": 0.1},
        "ruthless": {"agreeableness": -0.2},
        "cunning": {"agreeableness": -0.1, "openness": 0.05},
        "aggressive": {"agreeableness": -0.15, "extraversion": 0.05},

        # High Neuroticism
        "fearful": {"neuroticism": 0.2, "extraversion": -0.05},
        "anxious": {"neuroticism": 0.15},
        "paranoid": {"neuroticism": 0.15},

        # Low Neuroticism
        "brave": {"neuroticism": -0.15, "extraversion": 0.05},
        "calm": {"neuroticism": -0.15},
        "stoic": {"neuroticism": -0.1, "extraversion": -0.05},
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
                        "temperature": 0.2,
                        "max_output_tokens": 4096,
                    }
                )

            response = await asyncio.wait_for(
                loop.run_in_executor(_executor, _sync_generate),
                timeout=60.0
            )

            parsed = self._parse_extraction_response(response.text)

            entities = []
            for e in parsed.get("entities", []):
                entities.append(ExtractedEntity(
                    name=e.get("name", "Unknown"),
                    entity_type=e.get("entity_type", "Concept"),
                    description=e.get("description", ""),
                    traits=e.get("traits", []),
                    tags=e.get("tags", []),
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
    ) -> ParsedLoreResult:
        """
        Parse lore text and store entities in Neo4j with OCEAN profiles.

        Args:
            text: Raw lore text
            db: Neo4j database instance
            source_name: Source identifier for tracking
            world_id: World/lore base ID for separation (extracted from source if not provided)

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
            canon_id = f"lore-{uuid.uuid4().hex[:12]}"

            props = {
                "canon_id": canon_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "description": entity.description,
                "content": entity.verbatim_text or entity.description,
                "source": source_name,
                "world_id": world_id,  # Explicit world association
                "confidence_level": "AI_GENERATED",
                "approval_status": "PENDING",
                "created_at": timestamp,
                "tags": entity.tags,
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
