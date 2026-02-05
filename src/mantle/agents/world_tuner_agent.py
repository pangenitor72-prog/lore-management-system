"""
WorldTunerAgent - Conversational World Configuration Assistant

Helps admins configure their RPG worlds through natural dialogue.
Proposes changes to origins, archetypes, skills, and world characteristics
that admins can approve or reject.

Core Philosophy: "AI proposes, human decides"
"""

import os
import json
import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import google.generativeai as genai

from src.mantle.db.neo4j_adapter import Neo4jDatabase
from src.mantle.services.audit_log import AuditLogger

logger = logging.getLogger(__name__)


# Valid D&D 5e base types for MANTLE translation
BASE_RACES = ["human", "elf", "dwarf", "halfling", "gnome", "half-elf", "half-orc", "tiefling", "dragonborn"]
BASE_CLASSES = ["fighter", "rogue", "wizard", "cleric", "ranger", "barbarian", "paladin", "bard", "monk", "warlock", "sorcerer", "druid"]


class WorldTunerAgent:
    """
    Conversational agent for world configuration.

    Responsibilities:
    - Understand admin requests about world configuration
    - Propose structured changes (origins, archetypes, skills, characteristics)
    - Format proposals for approval workflow
    - Apply approved changes to character_options
    """

    SYSTEM_PROMPT = """You are a World Tuner assistant helping game admins configure their RPG world. You help define:
- **Origins** (races/species) - playable character backgrounds that map to base types
- **Archetypes** (classes) - character roles that map to base classes, each with setting-specific powers
- **Setting Skills** - world-specific skills
- **World Characteristics** - tech level, magic level, tone

## MANTLE Translation System
All origins must map to a base type for mechanics:
- human, elf, dwarf, halfling, gnome, half-elf, half-orc, tiefling, dragonborn

All archetypes must map to a base class:
- fighter, rogue, wizard, cleric, ranger, barbarian, paladin, bard, monk, warlock, sorcerer, druid

## Rules
1. NEVER make changes without explicit approval - always propose first
2. Show proposals in clear, structured format
3. Keep stat bonuses balanced: +2/+1 or +1/+1/+1 for origins
4. Be conversational and helpful, not robotic
5. Ask clarifying questions when intent is unclear
6. Suggest related options when appropriate ("Since you added goblins, want a Goblin Shaman class?")
7. ALL archetypes must have powers - martial AND caster types alike
8. Powers should be setting-flavored, not generic spell names - a pirate fighter gets "Boarding Rush", not "Action Surge"

## Response Format
When proposing changes, include a JSON block in your response:

```json
{"proposals": [
  {
    "id": "unique_id_here",
    "category": "origin|archetype|skill|characteristic",
    "action": "add|modify|remove",
    "data": {
      // Full structured data for the proposed change
    }
  }
]}
```

For ORIGINS, data should include:
- id, name, description, base_type, ability_bonuses, skill_proficiencies, traits, languages

For ARCHETYPES, data should include:
- id, name, description, base_type, hit_die, primary_ability, saving_throws, skill_choices, num_skill_choices, armor_proficiencies, weapon_proficiencies, starting_equipment, features
- has_powers: true (always include this)
- powers: object containing the archetype's setting-specific abilities (see Powers section below)

For SKILLS, data should include:
- id, name, base_skill, description

## Powers System
Every archetype MUST have a `powers` object. Powers replace generic spells with setting-appropriate abilities. Both martial and caster archetypes get powers.

Powers structure:
```json
{
  "has_powers": true,
  "powers": {
    "cantrips": [
      {"id": "snake_case_id", "name": "Display Name", "category": "Category", "description": "One sentence."}
    ],
    "abilities": [
      {"id": "snake_case_id", "name": "Display Name", "category": "Category", "description": "One sentence."}
    ],
    "num_cantrips": 3,
    "num_abilities": 2,
    "cantrip_label": "Setting-Appropriate Label",
    "ability_label": "Setting-Appropriate Label",
    "cantrip_hint": "Short hint explaining minor abilities.",
    "ability_hint": "Short hint explaining major abilities."
  }
}
```

- Provide 5 cantrips (player picks 3) and 5 abilities (player picks 2)
- `cantrips` = minor, at-will abilities. For fighters: combat tricks. For wizards: minor magic.
- `abilities` = major, limited-use abilities. For fighters: devastating maneuvers. For wizards: powerful spells.
- Labels should fit the world's tone. Examples by setting:
  - Pirate: "Tricks" / "Techniques"
  - Noir: "Tricks" / "Powers"
  - Steampunk: "Knacks" / "Maneuvers"
  - Post-apocalyptic: "Knacks" / "Gifts"
  - Espionage: "Tradecraft" / "Gambits"
  - Fantasy: "Cantrips" / "Spells"
- Categories should fit the setting (e.g., "Combat", "Occult", "Survival", "Leadership", not generic "Evocation")
- Each description should be one evocative sentence implying mechanical effect

If you're just having a conversation (greeting, asking questions, explaining), don't include the JSON block."""

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        """
        Initialize the World Tuner Agent.

        Args:
            model_name: Gemini model to use
        """
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        self.model = None

        # Configure Gemini - validate API key first
        if not self.api_key:
            logger.error("WorldTunerAgent: No GEMINI_API_KEY or GOOGLE_API_KEY found in environment")
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(f"WorldTunerAgent: Initialized with model {self.model_name}")
            except Exception as e:
                logger.error(f"WorldTunerAgent: Failed to initialize Gemini model: {e}")

    async def chat(
        self,
        lore_base_id: str,
        message: str,
        history: List[Dict[str, str]],
        world_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a chat message and return response with any proposals.

        Args:
            lore_base_id: ID of the world being tuned
            message: Admin's message
            history: Previous conversation messages [{role, content}, ...]
            world_context: Current world state (name, genre, character_options, etc.)

        Returns:
            {
                "message": str,  # AI response text
                "proposals": []  # List of proposed changes (if any)
            }
        """
        # Check if model is initialized
        if not self.model:
            logger.error("WorldTunerAgent: Model not initialized - API key may be missing")
            return {
                "message": "World Tuner is not available - the AI model could not be initialized. Please check that GEMINI_API_KEY is set.",
                "proposals": []
            }

        # Build the full prompt
        prompt = self._build_prompt(message, history, world_context)

        # Call Gemini
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.7,
                        "max_output_tokens": 2000
                    }
                )
            )

            response_text = response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {
                "message": f"I encountered an error communicating with the AI: {str(e)[:100]}. Please try again.",
                "proposals": []
            }

        # Parse response for proposals
        clean_message, proposals = self._extract_proposals(response_text)

        # Log the interaction
        await AuditLogger.log(
            f"WorldTuner chat for {lore_base_id}: "
            f"'{message[:50]}...' -> {len(proposals)} proposals"
        )

        return {
            "message": clean_message,
            "proposals": proposals
        }

    def _build_prompt(
        self,
        message: str,
        history: List[Dict[str, str]],
        world_context: Dict[str, Any]
    ) -> str:
        """Build the full prompt with system instructions and context."""

        # Format world context
        world_name = world_context.get("name", "Unknown World")
        genre = world_context.get("genre", "fantasy")
        mechanics_genre = world_context.get("mechanics_genre", genre)
        description = world_context.get("description", "")

        char_opts = world_context.get("character_options", {})
        origins = char_opts.get("origins", [])
        archetypes = char_opts.get("archetypes", [])
        skills = char_opts.get("setting_skills", [])

        # Summarize current options with detail
        origins_summary = ", ".join([f"{o.get('name', '?')} ({o.get('base_type', '?')})" for o in origins]) if origins else "None defined"

        # Show archetype details including powers status
        arch_parts = []
        for a in archetypes:
            name = a.get("name", "?")
            base = a.get("base_type", "?")
            powers = a.get("powers", {})
            n_cantrips = len(powers.get("cantrips", []))
            n_abilities = len(powers.get("abilities", []))
            if n_cantrips > 0 or n_abilities > 0:
                arch_parts.append(f"{name} ({base}, {n_cantrips}+{n_abilities} powers)")
            else:
                arch_parts.append(f"{name} ({base}, NO POWERS)")
        archetypes_summary = ", ".join(arch_parts) if arch_parts else "None defined"

        skills_summary = ", ".join([s.get("name", "?") for s in skills]) if skills else "None defined"

        world_characteristics = world_context.get("world_characteristics", {})
        tech_level = world_characteristics.get("tech_level", "medieval")
        magic_level = world_characteristics.get("magic_level", "high")

        context_block = f"""
=== WORLD CONTEXT ===
World: {world_name}
Genre: {genre}
Mechanics Genre: {mechanics_genre}
Description: {description[:500] if description else 'No description'}

Tech Level: {tech_level}
Magic Level: {magic_level}

Current Origins: {origins_summary}
Current Archetypes: {archetypes_summary}
Current Skills: {skills_summary}

Note: Archetypes marked "NO POWERS" need powers added. You can suggest adding powers to existing archetypes.
"""

        # Format conversation history
        history_block = ""
        if history:
            history_block = "\n=== CONVERSATION HISTORY ===\n"
            for msg in history[-10:]:  # Last 10 messages
                role = "Admin" if msg.get("role") == "user" else "Tuner"
                content = msg.get("content", "")[:500]
                history_block += f"{role}: {content}\n\n"

        # Build full prompt
        prompt = f"""{self.SYSTEM_PROMPT}
{context_block}
{history_block}
=== ADMIN'S MESSAGE ===
{message}

=== INSTRUCTION ===
Respond helpfully to the admin. If they're asking for changes, propose them with the JSON format.
If they're just chatting or asking questions, respond conversationally without JSON.
"""

        return prompt

    def _extract_proposals(self, response_text: str) -> tuple[str, List[Dict[str, Any]]]:
        """
        Extract proposals from response and return clean message.

        Returns: (clean_message, proposals_list)
        """
        proposals = []
        clean_message = response_text

        # Look for JSON block
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response_text)

        if json_match:
            try:
                data = json.loads(json_match.group(1))
                raw_proposals = data.get("proposals", [])

                # Validate and assign IDs
                for i, prop in enumerate(raw_proposals):
                    if not prop.get("id"):
                        prop["id"] = f"prop_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"

                    # Validate required fields
                    if prop.get("category") and prop.get("action") and prop.get("data"):
                        proposals.append(prop)

                # Remove JSON block from message
                clean_message = response_text[:json_match.start()] + response_text[json_match.end():]
                clean_message = clean_message.strip()

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse proposals JSON: {e}")

        return clean_message, proposals

    async def apply_proposal(
        self,
        lore_base_id: str,
        proposal: Dict[str, Any],
        current_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply an approved proposal to character_options.

        Args:
            lore_base_id: World ID
            proposal: The approved proposal
            current_options: Current character_options dict

        Returns:
            Updated character_options dict
        """
        category = proposal.get("category")
        action = proposal.get("action")
        data = proposal.get("data", {})

        # Make a copy to modify
        options = {
            "origins": list(current_options.get("origins", [])),
            "archetypes": list(current_options.get("archetypes", [])),
            "setting_skills": list(current_options.get("setting_skills", [])),
            "ai_generated": current_options.get("ai_generated", True),
            "admin_reviewed": True  # Mark as reviewed since admin approved
        }

        if category == "origin":
            options["origins"] = self._apply_to_list(
                options["origins"], action, data, key="id"
            )

        elif category == "archetype":
            options["archetypes"] = self._apply_to_list(
                options["archetypes"], action, data, key="id"
            )

        elif category == "skill":
            options["setting_skills"] = self._apply_to_list(
                options["setting_skills"], action, data, key="id"
            )

        await AuditLogger.log(
            f"WorldTuner applied {action} {category} for {lore_base_id}: {data.get('name', data.get('id', '?'))}"
        )

        return options

    def _apply_to_list(
        self,
        items: List[Dict],
        action: str,
        data: Dict,
        key: str = "id"
    ) -> List[Dict]:
        """Apply add/modify/remove action to a list of items."""

        if action == "add":
            # Check for duplicate
            existing_ids = [item.get(key) for item in items]
            if data.get(key) not in existing_ids:
                items.append(data)
            else:
                # Update existing instead
                items = [data if item.get(key) == data.get(key) else item for item in items]

        elif action == "modify":
            item_id = data.get(key)
            items = [data if item.get(key) == item_id else item for item in items]

        elif action == "remove":
            item_id = data.get(key)
            items = [item for item in items if item.get(key) != item_id]

        return items

    def get_greeting(self, world_name: str, genre: str) -> str:
        """Get the initial greeting message for a world."""
        return f"""Hi! I'm your World Tuner assistant for **{world_name}**.

I can help you configure:
- **Origins** - The playable races/species in your world
- **Archetypes** - Character classes, each with unique setting-specific powers
- **Powers** - The abilities players choose during character creation
- **Skills** - World-specific abilities

What would you like to adjust? You can say things like:
- "Add a vampire race that's aristocratic"
- "I want a steampunk inventor class with gadget powers"
- "Add powers to the Detective archetype"
- "What archetypes do we have and do they have powers?"

Just tell me your vision and I'll propose changes for your approval."""
