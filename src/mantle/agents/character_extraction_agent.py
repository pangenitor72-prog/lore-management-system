# src/mantle/agents/character_extraction_agent.py
"""
CharacterExtractionAgent - Extracts narrative elements from character descriptions

Takes rich character descriptions and extracts:
- Competencies (proven/untested/weak domains)
- Friction points (protects/lost/avoids/believes)
- Suggested mechanical mappings (origin, archetype, abilities)

Core Philosophy: "Description is truth" - the player's description defines who
their character is, and we extract structure from that, not the other way around.
"""

import os
import json
import re
import asyncio
import logging
from typing import Optional, Dict, Any, List
import google.generativeai as genai

from src.mantle.dnd5e.models.narrative import (
    Competency,
    FrictionPoint,
    CharacterExtraction,
    CompetenceLevel,
    FrictionPointCategory,
    CORE_DOMAINS,
)

logger = logging.getLogger(__name__)


class CharacterExtractionAgent:
    """
    Extracts narrative character elements from descriptions.

    Responsibilities:
    - Identify competencies (what they're proven/untested/weak at)
    - Find emotional friction points (what they protect/lost/avoid/believe)
    - Suggest origin and archetype mappings from world options
    - Infer ability score priorities from competencies
    - Suggest skills that fit the character concept
    """

    SYSTEM_PROMPT = """You are a character analyst helping extract meaningful narrative elements from character descriptions.

## Your Task
Read the character description carefully and extract:

1. **COMPETENCIES** - What domains is this character good/bad at?
   - PROVEN: Mastery. They succeed at this. "Legendary assassin" = proven combat.
   - UNTESTED: Capable but still learning. Failure teaches, doesn't punish.
   - WEAK: Struggles genuinely. Success is hard-won and meaningful.

   Core domains (assign level to each relevant one):
   - combat: Fighting, weapons, tactics
   - social: Persuasion, deception, intimidation, insight
   - stealth: Sneaking, infiltration, theft
   - magic: Spellcasting, arcane/divine knowledge
   - knowledge: Lore, history, investigation, medicine
   - survival: Nature, tracking, endurance, athletics

   You may also identify 1-2 CUSTOM domains that don't fit the core list
   (e.g., "court intrigue", "shipwright", "herbalism").

2. **FRICTION POINTS** - What matters to this character emotionally?
   - PROTECTS: Who/what would they sacrifice everything for?
   - LOST: What absence still haunts them?
   - AVOIDS: What truth do they refuse to face?
   - BELIEVES: What conviction shapes their actions?

   These are the places where narrative pressure produces response.

3. **CHARACTER IDENTITY** - If discernible from the description:
   - Name
   - Best matching origin from the world's options
   - Best matching archetype from the world's options

4. **MECHANICAL SUGGESTIONS** - Inferred from competencies:
   - Ability score priorities (which abilities matter most)
   - Skills that fit the character concept

## Response Format
Return a JSON object with your extraction:

```json
{
  "name": "Character name if mentioned",
  "origin_id": "best_matching_origin_id or null",
  "archetype_id": "best_matching_archetype_id or null",
  "competencies": [
    {
      "domain": "combat",
      "level": "proven",
      "evidence": "Quote or reference from description",
      "dm_guidance": "How DM should handle this in play",
      "is_custom": false
    }
  ],
  "friction_points": [
    {
      "category": "protects",
      "target": "Her younger sister",
      "intensity": "central",
      "narrative_hook": "Put the sister in danger to see what she'll sacrifice"
    }
  ],
  "ability_priorities": ["dexterity", "constitution", "wisdom"],
  "suggested_skills": ["stealth", "perception", "athletics"],
  "personality_traits": ["Speaks in short, clipped sentences", "Always sits facing the door"],
  "ideals": ["Everyone deserves a second chance"],
  "bonds": ["Her sister is all she has left"],
  "flaws": ["Trusts no one completely"],
  "backstory_summary": "A one-paragraph summary of the character's backstory",
  "extraction_confidence": 0.85
}
```

## Rules
1. Only include competencies that are clearly indicated or strongly implied
2. Include evidence (quotes) when possible to justify your extraction
3. Friction points should be specific, not generic
4. Intensity levels: "central" (defines them), "significant" (matters deeply), "minor" (present but not primary)
5. DM guidance should be actionable (what to do, not what to avoid)
6. If the description is minimal, extract what you can and note lower confidence
7. NEVER invent things not supported by the description
8. Custom domains should only be used for truly unique aspects that don't fit core domains"""

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        """
        Initialize the Character Extraction Agent.

        Args:
            model_name: Gemini model to use
        """
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        self.model = None

        if not self.api_key:
            logger.error("CharacterExtractionAgent: No GEMINI_API_KEY found")
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(f"CharacterExtractionAgent: Initialized with {self.model_name}")
            except Exception as e:
                logger.error(f"CharacterExtractionAgent: Failed to initialize: {e}")

    async def extract(
        self,
        description: str,
        world_context: Optional[Dict[str, Any]] = None,
        additional_prompts: Optional[Dict[str, str]] = None,
    ) -> CharacterExtraction:
        """
        Extract narrative elements from a character description.

        Args:
            description: The player's character description
            world_context: Optional world info including:
                - origins: List of available origins [{id, name, description}, ...]
                - archetypes: List of available archetypes [{id, name, description}, ...]
                - genre: The world's genre
                - name: The world's name
            additional_prompts: Optional player answers to deepening questions:
                - proven: What they've already proven they can do
                - untested: What they're capable of but still learning
                - weak: What they genuinely struggle with
                - protects: Who/what they'd sacrifice for
                - lost: What absence haunts them
                - avoids: What truth they refuse to face
                - believes: What conviction shapes them

        Returns:
            CharacterExtraction with competencies, friction points, and suggestions
        """
        if not self.model:
            logger.error("CharacterExtractionAgent: Model not initialized")
            return CharacterExtraction(extraction_confidence=0.0)

        prompt = self._build_prompt(description, world_context, additional_prompts)

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.3,  # Lower temp for more consistent extraction
                        "max_output_tokens": 2000
                    }
                )
            )

            return self._parse_response(response.text)

        except Exception as e:
            logger.error(f"CharacterExtractionAgent: Extraction failed: {e}")
            return CharacterExtraction(extraction_confidence=0.0)

    def _build_prompt(
        self,
        description: str,
        world_context: Optional[Dict[str, Any]],
        additional_prompts: Optional[Dict[str, str]],
    ) -> str:
        """Build the full extraction prompt."""
        parts = [self.SYSTEM_PROMPT]

        # Add world context if provided
        if world_context:
            parts.append("\n## WORLD CONTEXT")
            if world_context.get("name"):
                parts.append(f"World: {world_context['name']}")
            if world_context.get("genre"):
                parts.append(f"Genre: {world_context['genre']}")

            origins = world_context.get("origins", [])
            if origins:
                parts.append("\nAvailable Origins:")
                for origin in origins:
                    parts.append(f"- {origin.get('id', 'unknown')}: {origin.get('name', 'Unknown')} - {origin.get('description', '')[:100]}")

            archetypes = world_context.get("archetypes", [])
            if archetypes:
                parts.append("\nAvailable Archetypes:")
                for arch in archetypes:
                    parts.append(f"- {arch.get('id', 'unknown')}: {arch.get('name', 'Unknown')} - {arch.get('description', '')[:100]}")

        # Add the main description
        parts.append("\n## CHARACTER DESCRIPTION")
        parts.append(description)

        # Add additional prompts if provided
        if additional_prompts:
            parts.append("\n## PLAYER'S ADDITIONAL INPUT")
            if additional_prompts.get("proven"):
                parts.append(f"What they've proven: {additional_prompts['proven']}")
            if additional_prompts.get("untested"):
                parts.append(f"What they're learning: {additional_prompts['untested']}")
            if additional_prompts.get("weak"):
                parts.append(f"What they struggle with: {additional_prompts['weak']}")
            if additional_prompts.get("protects"):
                parts.append(f"What they protect: {additional_prompts['protects']}")
            if additional_prompts.get("lost"):
                parts.append(f"What they've lost: {additional_prompts['lost']}")
            if additional_prompts.get("avoids"):
                parts.append(f"What they avoid: {additional_prompts['avoids']}")
            if additional_prompts.get("believes"):
                parts.append(f"What they believe: {additional_prompts['believes']}")

        parts.append("\n## YOUR EXTRACTION")
        parts.append("Analyze the description and extract the narrative elements as JSON:")

        return "\n".join(parts)

    def _parse_response(self, response_text: str) -> CharacterExtraction:
        """Parse the AI response into a CharacterExtraction object."""
        try:
            # Find JSON block in response
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.warning("CharacterExtractionAgent: No JSON found in response")
                    return CharacterExtraction(extraction_confidence=0.0)

            data = json.loads(json_str)

            # Parse competencies
            competencies = []
            for comp_data in data.get("competencies", []):
                try:
                    level = CompetenceLevel(comp_data.get("level", "untested"))
                    competencies.append(Competency(
                        domain=comp_data.get("domain", "unknown"),
                        level=level,
                        evidence=comp_data.get("evidence", ""),
                        dm_guidance=comp_data.get("dm_guidance", ""),
                        is_custom=comp_data.get("is_custom", False),
                    ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid competency data: {e}")

            # Parse friction points
            friction_points = []
            for fp_data in data.get("friction_points", []):
                try:
                    category = FrictionPointCategory(fp_data.get("category", "believes"))
                    friction_points.append(FrictionPoint(
                        category=category,
                        target=fp_data.get("target", ""),
                        intensity=fp_data.get("intensity", "significant"),
                        narrative_hook=fp_data.get("narrative_hook", ""),
                    ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid friction point data: {e}")

            return CharacterExtraction(
                name=data.get("name"),
                origin_id=data.get("origin_id"),
                archetype_id=data.get("archetype_id"),
                competencies=competencies,
                friction_points=friction_points,
                ability_priorities=data.get("ability_priorities", []),
                suggested_skills=data.get("suggested_skills", []),
                personality_traits=data.get("personality_traits", []),
                ideals=data.get("ideals", []),
                bonds=data.get("bonds", []),
                flaws=data.get("flaws", []),
                backstory_summary=data.get("backstory_summary", ""),
                extraction_confidence=data.get("extraction_confidence", 0.5),
            )

        except json.JSONDecodeError as e:
            logger.error(f"CharacterExtractionAgent: JSON parse error: {e}")
            return CharacterExtraction(extraction_confidence=0.0)
        except Exception as e:
            logger.error(f"CharacterExtractionAgent: Parse error: {e}")
            return CharacterExtraction(extraction_confidence=0.0)

    def extraction_to_display(self, extraction: CharacterExtraction) -> Dict[str, Any]:
        """
        Convert extraction to a display-friendly format for the UI.

        Returns structured data for the "Character Reading" screen.
        """
        # Group competencies by level
        proven = [c for c in extraction.competencies if c.level == CompetenceLevel.PROVEN]
        untested = [c for c in extraction.competencies if c.level == CompetenceLevel.UNTESTED]
        weak = [c for c in extraction.competencies if c.level == CompetenceLevel.WEAK]

        # Format competencies with icons
        competency_display = []
        for c in proven:
            competency_display.append({
                "icon": "★",
                "domain": c.domain.upper(),
                "level": "proven",
                "label": "You succeed at this.",
                "evidence": c.evidence,
                "guidance": c.dm_guidance or c.get_default_guidance(),
            })
        for c in untested:
            competency_display.append({
                "icon": "◐",
                "domain": c.domain.upper(),
                "level": "untested",
                "label": "Capable but still learning.",
                "evidence": c.evidence,
                "guidance": c.dm_guidance or c.get_default_guidance(),
            })
        for c in weak:
            competency_display.append({
                "icon": "○",
                "domain": c.domain.upper(),
                "level": "weak",
                "label": "Success is hard-won.",
                "evidence": c.evidence,
                "guidance": c.dm_guidance or c.get_default_guidance(),
            })

        # Format friction points with icons
        friction_display = []
        category_icons = {
            FrictionPointCategory.PROTECTS: "♥",
            FrictionPointCategory.LOST: "💔",
            FrictionPointCategory.AVOIDS: "⚠",
            FrictionPointCategory.BELIEVES: "✦",
        }
        for fp in extraction.friction_points:
            friction_display.append({
                "icon": category_icons.get(fp.category, "·"),
                "category": fp.category.value.upper(),
                "target": fp.target,
                "intensity": fp.intensity,
                "hook": fp.narrative_hook or fp.get_default_hook(),
            })

        return {
            "name": extraction.name,
            "origin_id": extraction.origin_id,
            "archetype_id": extraction.archetype_id,
            "competencies": competency_display,
            "friction_points": friction_display,
            "ability_priorities": extraction.ability_priorities,
            "suggested_skills": extraction.suggested_skills,
            "personality": {
                "traits": extraction.personality_traits,
                "ideals": extraction.ideals,
                "bonds": extraction.bonds,
                "flaws": extraction.flaws,
            },
            "backstory": extraction.backstory_summary,
            "confidence": extraction.extraction_confidence,
        }
