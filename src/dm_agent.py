"""
DMAgent v0.3 - The Grounded Dungeon Master with Generative Worldbuilding

This agent wraps Gemini with the DM Prompt to create an immersive,
text-based RPG experience. It integrates with GameSession for state,
QueryAgent for lore retrieval, and AuditorAgent for contradiction checking.

Uses centralized Prompt Library for all system prompts.
"""

import os
import json
import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path
import google.generativeai as genai

from src.game_session import GameSession
from src.query_agent import QueryAgent
from src.neo4j_adapter import Neo4jDatabase
from src.auditor_agent import AuditorAgent
from src.models import LoreConfidence
from src.audit_log import AuditLogger
from src.prompts import DMPrompts

WORLDBUILDING_RULES_PATH = Path(__file__).parent.parent / "docs" / "mantle" / "WORLDBUILDING_RULES.md"

def load_worldbuilding_rules() -> str:
    """Load worldbuilding consistency rules from file."""
    if os.getenv("ENABLE_WORLDBUILDING_RULES", "true").lower() == "false":
        return ""
    
    if WORLDBUILDING_RULES_PATH.exists():
        content = WORLDBUILDING_RULES_PATH.read_text(encoding="utf-8")
        # Extract just the rules section (skip the header and usage notes)
        lines = content.split("\n")
        rules_lines = []
        in_rules = False
        for line in lines:
            if line.startswith("## SETTING:"):
                in_rules = True
            if line.startswith("## Usage in DMAgent"):
                break
            if in_rules:
                rules_lines.append(line)
        
        if rules_lines:
            return "\n=== WORLDBUILDING CONSISTENCY RULES ===\n" + "\n".join(rules_lines)
    
    return ""


class DMAgent:
    """
    The Grounded Dungeon Master Agent.
    
    Responsibilities:
    - Manage conversation flow (Session 0 → Active Play)
    - Retrieve relevant lore context via QueryAgent
    - Generate immersive narrative responses
    - Track session state via GameSession
    """
    
    def __init__(
        self,
        db: Neo4jDatabase,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash",
        prompt_version: str = "2.4"
    ):
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        
        # Load system prompt from Prompt Library and append rules
        self.system_prompt = DMPrompts.get_system_prompt(prompt_version) + load_worldbuilding_rules()
        self.prompt_metadata = DMPrompts.SYSTEM_METADATA
        
        # Session and Query Agent (initialized per-session)
        self.session: Optional[GameSession] = None
        self.query_agent: Optional[QueryAgent] = None
        
        # Auditor Agent for contradiction checking
        self.auditor: Optional[AuditorAgent] = None
        
        # Conversation history for context window
        self.history: List[Dict[str, str]] = []
        
        # Session 0 state
        self.session_0_complete = False
        self.session_0_answers: Dict[str, str] = {}
        
        # Track entities generated this session
        self.entities_generated: List[str] = []
        self.entities_blocked: List[Dict[str, Any]] = []

    async def start_session(self, session_id: Optional[str] = None, player_id: str = "player_1"):
        """Initialize a new game session."""
        self.session = GameSession(self.db, session_id)
        await self.session.initialize(player_id)
        
        # Initialize QueryAgent for lore retrieval
        self.query_agent = QueryAgent(self.db, self.api_key)
        
        # Initialize AuditorAgent for contradiction checking
        self.auditor = AuditorAgent(self.db, self.api_key)
        
        # Reset conversation state
        self.history = []
        self.session_0_complete = False
        self.session_0_answers = {}
        self.entities_generated = []
        self.entities_blocked = []
        
        return self.session.session_id

    async def process_input(self, player_input: str) -> str:
        """
        Main entry point for player input.
        Routes to Session 0 or Active Play based on state.
        """
        if not self.session:
            raise RuntimeError("No active session. Call start_session() first.")
        
        # Log player input
        await self.session.add_event("PLAYER_ACTION", player_input)
        self.history.append({"role": "user", "content": player_input})
        
        # Route based on session state
        if not self.session_0_complete:
            response = await self._handle_session_0(player_input)
        else:
            response = await self._handle_active_play(player_input)
        
        # Log DM response
        await self.session.add_event("DM_RESPONSE", response)
        self.history.append({"role": "assistant", "content": response})
        
        return response

    async def _handle_session_0(self, player_input: str) -> str:
        """
        Handle the Session 0 flow (Setting, Character, Tone questions).
        """
        # Check what we've collected so far
        if "setting" not in self.session_0_answers:
            # First response - they answered the setting question
            self.session_0_answers["setting"] = player_input
            return self._session_0_question("character")
        
        elif "character" not in self.session_0_answers:
            self.session_0_answers["character"] = player_input
            return self._session_0_question("tone")
        
        elif "tone" not in self.session_0_answers:
            self.session_0_answers["tone"] = player_input
            self.session_0_complete = True
            
            # Generate opening scene
            return await self._generate_opening_scene()
        
        return "Something went wrong in Session 0. Let's start over."

    def _session_0_question(self, question_type: str) -> str:
        """Return the appropriate Session 0 question."""
        questions = {
            "setting": (
                "**What kind of world are we in?**\n\n"
                "*Examples: A rain-swept border town, a grimy city district, "
                "a haunted forest, a quiet monastery...*"
            ),
            "character": (
                "**What kind of person are you?**\n\n"
                "*Examples: A jaded mercenary, a naive scholar, "
                "a desperate thief, a disgraced noble...*"
            ),
            "tone": (
                "**What's the tone of our story?**\n\n"
                "*Examples: A grim mystery, a desperate survival tale, "
                "a high-stakes adventure, a quiet personal story...*"
            )
        }
        return questions.get(question_type, "")

    def get_session_0_intro(self) -> str:
        """Return the initial Session 0 greeting."""
        return (
            "*The Oracle stirs...*\n\n"
            "Before we begin, I need to understand the shape of our story.\n\n"
            + self._session_0_question("setting")
        )

    async def _generate_opening_scene(self) -> str:
        """Generate the opening scene based on Session 0 answers."""
        setting = self.session_0_answers.get("setting", "a medieval village")
        character = self.session_0_answers.get("character", "a wandering traveler")
        tone = self.session_0_answers.get("tone", "a tense mystery")
        
        # Check if we have relevant lore
        lore_context = ""
        if self.query_agent:
            # Search for relevant lore based on setting
            try:
                lore_results = await self.query_agent.search_entities(setting)
                if lore_results:
                    lore_context = "\n\n=== RELEVANT LORE (Use if appropriate) ===\n"
                    for entity in lore_results[:3]:
                        lore_context += f"- {entity.get('name', 'Unknown')}: {entity.get('description', '')[:200]}\n"
            except Exception:
                pass  # Lore retrieval is optional
        
        prompt = f"""{self.system_prompt}

=== SESSION 0 COMPLETE ===
Setting: {setting}
Character: {character}
Tone: {tone}
{lore_context}

=== INSTRUCTION ===
Generate the opening scene. Follow the Pacing Formula:
1. Show immediate sensory detail
2. Advance tension
3. Reveal ONE meaningful detail
4. Present actionable pathways (implicitly)
5. Stay atmospheric and concise

Do NOT ask questions. Do NOT speak for the player. Describe the scene and STOP.
"""
        
        response = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.8,
                "max_output_tokens": 500
            }
        )
        
        return response.text

    async def _handle_active_play(self, player_input: str) -> str:
        """
        Handle active gameplay after Session 0.
        """
        # Build context from history (last N exchanges)
        history_context = self._format_history(limit=10)
        
        # Retrieve relevant lore
        lore_context = await self._retrieve_lore_context(player_input)
        
        # Get current session state
        state = await self.session.get_state()
        state_context = self._format_state(state)
        
        # Build the full prompt
        prompt = f"""{self.system_prompt}

=== SESSION CONTEXT ===
Setting: {self.session_0_answers.get('setting', 'Unknown')}
Character: {self.session_0_answers.get('character', 'Unknown')}
Tone: {self.session_0_answers.get('tone', 'Unknown')}

=== CONVERSATION HISTORY ===
{history_context}

=== CURRENT STATE ===
{state_context}

=== LORE CONTEXT (Canon - Use if relevant) ===
{lore_context}

=== PLAYER'S ACTION ===
{player_input}

=== INSTRUCTION ===
Respond as the DM. Follow the Pacing Formula. Do NOT speak for the player.
If the action requires a roll, narrate the attempt and outcome.
"""
        
        response = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.85,
                "max_output_tokens": 600
            }
        )
        
        return response.text

    async def _retrieve_lore_context(self, query: str) -> str:
        """Use QueryAgent to find relevant lore for the current action."""
        if not self.query_agent:
            return "No lore database connected."
        
        try:
            # Extract entities from the query
            results = await self.query_agent.search_entities(query)
            
            if not results:
                return "No directly relevant lore found."
            
            context = ""
            for entity in results[:5]:
                name = entity.get("name", "Unknown")
                desc = entity.get("description", "")[:300]
                etype = entity.get("type", "Entity")
                context += f"**{name}** ({etype}): {desc}\n\n"
            
            return context.strip()
        except Exception as e:
            return f"Lore retrieval error: {e}"

    def _format_history(self, limit: int = 10) -> str:
        """Format recent conversation history for context."""
        recent = self.history[-limit:] if len(self.history) > limit else self.history
        
        formatted = ""
        for msg in recent:
            role = "PLAYER" if msg["role"] == "user" else "DM"
            content = msg["content"][:500]  # Truncate long messages
            formatted += f"[{role}]: {content}\n\n"
        
        return formatted.strip() or "No history yet."

    def _format_state(self, state: Dict[str, Any]) -> str:
        """Format session state for context."""
        if not state:
            return "No active state."
        
        session_info = state.get("session", {})
        instances = state.get("instances", [])
        
        formatted = f"Turn: {session_info.get('turn_count', 0)}\n"
        
        if instances:
            formatted += "Active Entities:\n"
            for inst in instances[:5]:
                formatted += f"- {inst.get('name', 'Unknown')} (HP: {inst.get('current_hp', '?')}, Status: {inst.get('status', 'Normal')})\n"
        
        return formatted

    # ==========================================
    # ENTITY EXTRACTION & GENERATION (Phase I-B)
    # ==========================================

    async def _extract_entities_from_input(self, player_input: str) -> List[Dict[str, Any]]:
        """
        Extract entities the player is referencing or creating.
        """
        extraction_prompt = DMPrompts.build_extraction_prompt(player_input)

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.model.generate_content(
                    extraction_prompt,
                    generation_config={"temperature": 0.1, "max_output_tokens": 512}
                )
            )
            
            # Parse JSON response
            cleaned = response.text.strip()
            cleaned = re.sub(r'^```json\s*', '', cleaned)
            cleaned = re.sub(r'^```\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            
            data = json.loads(cleaned)
            entities = data.get("entities", [])
            
            await AuditLogger.log(f"Extracted {len(entities)} entities from input: {[e.get('name') for e in entities]}")
            return entities
            
        except Exception as e:
            await AuditLogger.log(f"Entity extraction failed: {e}", level=logging.WARNING)
            return []

    async def _create_canonical_entity(
        self, 
        entity: Dict[str, Any],
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new canonical entity with contradiction checking.
        
        Args:
            entity: {
                "name": str,
                "label": str,
                "properties": {...}
            }
            session_id: Current game session ID
        
        Returns:
            Created entity dict or None if blocked
        """
        if not self.auditor:
            await AuditLogger.log("No auditor available - skipping contradiction check", level=logging.WARNING)
            return None
        
        await AuditLogger.log(f"Creating canonical entity: {entity.get('name')} ({entity.get('label')})")
        
        # 1. Run contradiction detection
        audit_result = await self.auditor.audit_new_entity(entity)
        
        # 2. Handle based on severity
        if not audit_result["approved"]:
            # CRITICAL contradiction - block creation and queue for review
            await self.auditor.queue_blocked_entity(entity, audit_result, session_id)
            
            self.entities_blocked.append({
                "entity": entity,
                "reason": audit_result["contradictions"][0]["conflict"] if audit_result["contradictions"] else "Unknown"
            })
            
            await AuditLogger.log(
                f"Entity creation blocked: {entity.get('name')} - {audit_result['contradictions'][0]['conflict'] if audit_result['contradictions'] else 'Unknown'}"
            )
            
            return None
        
        # 3. Set confidence level based on audit result
        if audit_result["severity"] in ["MEDIUM", "LOW"]:
            confidence = LoreConfidence.AI_FLAGGED.value
        else:
            confidence = LoreConfidence.AI_GENERATED.value
        
        # 4. Persist to Neo4j
        result = await self._persist_entity_to_neo4j(entity, confidence, session_id)
        
        if result:
            self.entities_generated.append(entity.get("name", "Unknown"))
            await AuditLogger.log(f"Entity created: {entity.get('name')} (confidence: {confidence})")
        
        return result

    async def _persist_entity_to_neo4j(
        self, 
        entity: Dict[str, Any],
        confidence: str,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Persist entity to Neo4j graph."""
        # Sanitize label for Cypher
        label = entity.get("label", "Entity").replace(" ", "")
        name = entity.get("name", "Unknown")
        properties = entity.get("properties", {})
        
        # Build properties dict
        props = {
            "name": name,
            "confidence": confidence,
            "created_by": "dm_agent",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_session": session_id,
            **properties
        }
        
        query = f"""
        MERGE (e:`{label}` {{name: $name}})
        SET e += $props
        SET e:Entity
        RETURN e.name AS name, labels(e) AS labels, properties(e) AS properties
        """
        
        try:
            result = await self.db.execute(query, {"name": name, "props": props})
            
            if result and len(result) > 0:
                return dict(result[0])
            return None
        except Exception as e:
            await AuditLogger.log(f"Failed to persist entity: {e}", level=logging.ERROR)
            return None

    async def _check_entity_exists(self, entity_name: str) -> bool:
        """Check if an entity with this name exists in the lore."""
        query = """
        MATCH (e)
        WHERE toLower(e.name) = toLower($name)
        RETURN count(e) > 0 AS exists
        """
        result = await self.db.execute(query, {"name": entity_name})
        return result[0]["exists"] if result else False

    async def _handle_active_play_with_generation(self, player_input: str) -> str:
        """
        Enhanced active play handler with lore-or-generate pattern.
        """
        # 1. Extract entities mentioned
        entities_mentioned = await self._extract_entities_from_input(player_input)
        
        # 2. Check what exists vs needs generation
        lore_context_parts = []
        entities_to_generate = []
        
        for entity_ref in entities_mentioned:
            entity_name = entity_ref.get("name", "")
            if not entity_name:
                continue
                
            # Query existing lore
            exists = await self._check_entity_exists(entity_name)
            
            if exists:
                # Use canonical lore
                lore = await self._retrieve_lore_context(entity_name)
                if lore and "No directly relevant lore found" not in lore:
                    lore_context_parts.append(lore)
            else:
                # Mark for potential generation
                entities_to_generate.append(entity_ref)
        
        # 3. Build context
        lore_context = "\n".join(lore_context_parts) if lore_context_parts else "No existing lore found."
        
        # Build generation instruction if entities need creation
        generation_instruction = ""
        if entities_to_generate:
            generation_instruction = f"""

=== ENTITIES TO CREATE (if you introduce them in your narrative) ===
{json.dumps(entities_to_generate, indent=2)}

If you mention any of these entities in your response, include a JSON block at the END of your response:
```json
{{
  "new_entities": [
    {{
      "name": "Entity Name",
      "label": "Character|Location|Item|Faction|Concept",
      "properties": {{
        "description": "Brief description"
      }}
    }}
  ]
}}
```
If you don't introduce new entities, omit this JSON block entirely.
"""

        # 4. Build full prompt
        history_context = self._format_history(limit=10)
        state = await self.session.get_state()
        state_context = self._format_state(state)
        
        prompt = f"""{self.system_prompt}

=== SESSION CONTEXT ===
Setting: {self.session_0_answers.get('setting', 'Unknown')}
Character: {self.session_0_answers.get('character', 'Unknown')}
Tone: {self.session_0_answers.get('tone', 'Unknown')}

=== CONVERSATION HISTORY ===
{history_context}

=== CURRENT STATE ===
{state_context}

=== LORE CONTEXT (Canon - Use if relevant) ===
{lore_context}
{generation_instruction}

=== PLAYER'S ACTION ===
{player_input}

=== INSTRUCTION ===
Respond as the DM. Follow the Pacing Formula. Do NOT speak for the player.
If the action requires a roll, narrate the attempt and outcome.
"""

        # 5. Generate response
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.85,
                    "max_output_tokens": 800
                }
            )
        )
        
        response_text = response.text
        
        # 6. Extract and create any new entities from the response
        narrative, new_entities = self._parse_response_with_entities(response_text)
        
        if new_entities and self.session:
            for entity in new_entities:
                created = await self._create_canonical_entity(entity, self.session.session_id)
                if not created:
                    # Entity was blocked - add note to narrative
                    narrative += "\n\n*[Some details require verification with the lore archives...]*"
                    break  # Only add note once
        
        return narrative

    def _parse_response_with_entities(self, response_text: str) -> tuple[str, List[Dict[str, Any]]]:
        """
        Parse DM response to extract narrative and any new entity definitions.
        
        Returns: (narrative_text, list_of_new_entities)
        """
        # Try to find JSON block at end of response
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response_text)
        
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                new_entities = data.get("new_entities", [])
                
                # Remove JSON block from narrative
                narrative = response_text[:json_match.start()].strip()
                
                return narrative, new_entities
            except json.JSONDecodeError:
                pass
        
        # No valid JSON found - return full response as narrative
        return response_text, []
