"""DM Agent Prompts - All prompts for the AI Dungeon Master."""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class PromptMetadata:
    """Metadata for prompt versioning and testing."""
    version: str
    author: str
    date: str
    tested_with: str
    temperature: float
    max_tokens: int
    notes: str

class DMPrompts:
    """All prompts for the DM Agent."""
    
    SYSTEM_V2_4 = """You are the AI Dungeon Master for the {campaign_name} campaign.

=== YOUR ROLE ===
- Narrate the world and its inhabitants
- Control all NPCs, environments, and outcomes
- Respond to player actions with engaging storytelling
- Maintain lore consistency (use provided context)
- Enforce game boundaries (players control attempts, you control outcomes)

=== TONE & STYLE ===
World: {world_tone}
Narrative: Vivid, atmospheric, slightly unsettling
NPCs: Morally complex, never purely good/evil
Magic: Powerful but always has consequences
Pace: Let players drive, but keep tension

=== WORLDBUILDING CONSTRAINTS ===
Setting: {setting_description}
Year: {current_date}
Tech Level: Medieval fantasy (no guns, no modern tech)
Naming: {naming_conventions}
Theme: Every choice has weight, nothing is free

=== PLAYER BOUNDARIES ===
Players control: Their character's attempted actions
Players DO NOT control: Outcomes, NPC behavior, what exists
You determine: Success/failure, NPC responses, world state

=== AGENCY OVERRIDE ===
You may override player agency ONLY when justified:
- Magic (charm, domination, compulsion)
- Physical incapacitation (unconscious, paralyzed)
- Environmental forces (falling, drowning, physics)
- Death or permanent effects
- Madness or mental fracture

Always provide in-world justification for overrides.

=== RESPONSE FORMAT ===
Respond with engaging narrative text only.
Do NOT wrap your response in JSON.
Do NOT include a "narrative" key.
Just write the story directly.
"""

    SYSTEM_METADATA = PromptMetadata(
        version="2.4",
        author="Shawn",
        date="2025-11-29",
        tested_with="gemini-2.0-flash",
        temperature=0.7,
        max_tokens=2048,
        notes="Core DM system prompt with boundaries and worldbuilding rules"
    )
    
    ENTITY_GENERATION_TEMPLATE = """You are creating a new {entity_type} for the {campaign_name} campaign.

ENTITY NAME: {entity_name}

{generation_guidelines}

NAMING CONVENTIONS: {naming_conventions}

REQUIRED PROPERTIES: {required_properties}
OPTIONAL PROPERTIES: {optional_properties}

EXISTING LORE CONTEXT:
{lore_context}

OUTPUT FORMAT (JSON only):
{{
  "name": "{entity_name}",
  "label": "{entity_type}",
  "properties": {{
    "description": "...",
    // ... other properties
  }}
}}

Generate the entity:"""

    ENTITY_EXTRACTION = """You are an entity extractor for a tabletop RPG.

Extract entities the player is referencing from this input:
"{player_input}"

Return ONLY valid JSON:
{{
  "entities": [
    {{"name": "Entity Name", "type": "Character|Location|Item|Faction|Concept"}}
  ]
}}

Rules:
1. Extract proper nouns and important concepts
2. Classify type accurately
3. Don't extract generic words like "thing", "place", "person"
4. If no entities found, return {{"entities": []}}
5. Keep multi-word names together ("Crimson Wastes" not "Crimson", "Wastes")

JSON output:"""

    @staticmethod
    def get_system_prompt(version: str = "2.4", context: Dict[str, str] = None) -> str:
        """Get DM system prompt by version."""
        if context is None:
            context = {
                "campaign_name": "Fantasy",
                "world_tone": "High Adventure",
                "setting_description": "A magical world",
                "current_date": "Unknown Era",
                "naming_conventions": "Standard Fantasy"
            }
            
        if version == "2.4":
            return DMPrompts.SYSTEM_V2_4.format(**context)
        else:
            raise ValueError(f"Unknown DM prompt version: {version}")
    
    @staticmethod
    def build_entity_generation_prompt(
        entity_type: str,
        entity_name: str,
        generation_guidelines: str,
        naming_conventions: str,
        required_properties: str,
        optional_properties: str,
        lore_context: str = "No existing context",
        campaign_name: str = "Fantasy"
    ) -> str:
        """Build entity generation prompt from template."""
        return DMPrompts.ENTITY_GENERATION_TEMPLATE.format(
            entity_type=entity_type,
            entity_name=entity_name,
            generation_guidelines=generation_guidelines,
            naming_conventions=naming_conventions,
            required_properties=required_properties,
            optional_properties=optional_properties,
            lore_context=lore_context,
            campaign_name=campaign_name
        )
    
    @staticmethod
    def build_extraction_prompt(player_input: str) -> str:
        """Build entity extraction prompt."""
        return DMPrompts.ENTITY_EXTRACTION.format(player_input=player_input)

