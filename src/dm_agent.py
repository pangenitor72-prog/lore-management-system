"""
DMAgent v0.1 - The Grounded Dungeon Master

This agent wraps Gemini with the DM Prompt v2.3 to create an immersive,
text-based RPG experience. It integrates with GameSession for state
and QueryAgent for lore retrieval.
"""

import os
import json
import re
from typing import Optional, Dict, Any, List
from pathlib import Path
import google.generativeai as genai

from src.game_session import GameSession
from src.query_agent import QueryAgent
from src.neo4j_adapter import Neo4jDatabase


# Load the DM Prompt from docs
DM_PROMPT_PATH = Path(__file__).parent.parent / "docs" / "mantle" / "DM PROMPT v2.3"

def load_system_prompt() -> str:
    """Load the DM system prompt from file."""
    if DM_PROMPT_PATH.exists():
        return DM_PROMPT_PATH.read_text(encoding="utf-8")
    else:
        # Fallback minimal prompt if file not found
        return """You are an AI Dungeon Master. Keep the player inside the fiction.
Never speak for the player. Describe the world and wait for their action."""


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
        model_name: str = "gemini-2.0-flash"
    ):
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        
        # Load system prompt
        self.system_prompt = load_system_prompt()
        
        # Session and Query Agent (initialized per-session)
        self.session: Optional[GameSession] = None
        self.query_agent: Optional[QueryAgent] = None
        
        # Conversation history for context window
        self.history: List[Dict[str, str]] = []
        
        # Session 0 state
        self.session_0_complete = False
        self.session_0_answers: Dict[str, str] = {}

    async def start_session(self, session_id: Optional[str] = None, player_id: str = "player_1"):
        """Initialize a new game session."""
        self.session = GameSession(self.db, session_id)
        await self.session.initialize(player_id)
        
        # Initialize QueryAgent for lore retrieval
        self.query_agent = QueryAgent(self.db, self.api_key)
        
        # Reset conversation state
        self.history = []
        self.session_0_complete = False
        self.session_0_answers = {}
        
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

