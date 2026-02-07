"""
DMAgent v0.4 - The Grounded Dungeon Master with Dual-Mode Support

This agent wraps Gemini with the DM Prompt to create an immersive,
text-based RPG experience. It integrates with GameSession for state,
QueryAgent for lore retrieval, and AuditorAgent for contradiction checking.

NEW in v0.4:
- Pacing Pressure for ONE_SHOT sessions (drives to climax in ~100 turns)
- GameConfig integration for narrative complexity
- Support for "THE END" state

Uses centralized Prompt Library for all system prompts.
"""

import os
import json
import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Literal, TYPE_CHECKING
from pathlib import Path
import google.generativeai as genai

from src.mantle.core.game_session import GameSession
from src.mantle.agents.query_agent import QueryAgent
from src.mantle.db.neo4j_adapter import Neo4jDatabase
from src.mantle.agents.auditor_agent import AuditorAgent
from src.mantle.core.models import LoreConfidence
from src.mantle.services.audit_log import AuditLogger
from src.mantle.core.entity_factory import EntityFactory, EntityType, EntityTemplate
from src.mantle.prompts import DMPrompts, BoundaryPrompts
from src.mantle.agents.boundary_enforcement import PlayerIntent, PlayerIntentType, AgencyOverride
from src.mantle.core.models import OCEANProfile, PersonalityGenerator, PersonalityTemplates

if TYPE_CHECKING:
    from src.mantle.engine.game_config import GameConfig
    from src.mantle.engine.world_integrity import CanonTruths
    from src.mantle.engine.game_events import GameEvent, Inventory

# Arc Engine for narrative structure (optional - graceful fallback if not available)
# Check environment variable to enable/disable Arc Engine
ARC_ENGINE_ENABLED = os.getenv("ENABLE_ARC_ENGINE", "true").lower() == "true"
ARC_ENGINE_AVAILABLE = False
ARC_ENGINE_IMPORT_ERROR = None
ArcEngine = None
StoryPhase = None
BeatType = None

if ARC_ENGINE_ENABLED:
    logging.info("[ARC ENGINE] Attempting to import Arc Engine (ENABLE_ARC_ENGINE=true)...")
    try:
        from src.mantle.arc import ArcEngine, StoryPhase, BeatType
        ARC_ENGINE_AVAILABLE = True
        logging.info("[ARC ENGINE] ✅ Arc Engine imported successfully")
        logging.info(f"[ARC ENGINE] Version: {getattr(ArcEngine, '__version__', 'unknown')}")
        logging.info(f"[ARC ENGINE] Available components: ArcEngine, StoryPhase, BeatType")
    except ImportError as e:
        ARC_ENGINE_AVAILABLE = False
        ARC_ENGINE_IMPORT_ERROR = str(e)
        logging.error(f"[ARC ENGINE] ❌ Import failed: {e}")
        logging.error(f"[ARC ENGINE] Import error details: {type(e).__name__}: {e}")
        
        # Log missing dependencies
        import sys
        missing_deps = []
        try:
            import pydantic
            logging.info(f"[ARC ENGINE] pydantic version: {pydantic.__version__}")
        except ImportError:
            missing_deps.append("pydantic")
            logging.error("[ARC ENGINE] Missing dependency: pydantic")
        
        if missing_deps:
            logging.error(f"[ARC ENGINE] Missing dependencies: {', '.join(missing_deps)}")
        
        # Check if arc module exists
        try:
            import src.mantle.arc.models
            logging.info("[ARC ENGINE] src.lms.arc.models is available")
        except ImportError as arc_err:
            logging.error(f"[ARC ENGINE] src.lms.arc.models not found: {arc_err}")
    except Exception as e:
        ARC_ENGINE_AVAILABLE = False
        ARC_ENGINE_IMPORT_ERROR = str(e)
        logging.error(f"[ARC ENGINE] ❌ Unexpected error during import: {e}")
        logging.error(f"[ARC ENGINE] Error type: {type(e).__name__}")
        import traceback
        logging.error(f"[ARC ENGINE] Traceback:\n{traceback.format_exc()}")
else:
    logging.info("[ARC ENGINE] Disabled via config (ENABLE_ARC_ENGINE=false)")

WORLDBUILDING_RULES_PATH = Path(__file__).parent.parent.parent / "docs" / "mantle" / "WORLDBUILDING_RULES.md"

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
        model_name: str = "gemini-2.0-flash", 
        conversation_history: list = None,
        db: Optional[Neo4jDatabase] = None,
        query_agent: Optional[QueryAgent] = None,
        auditor_agent: Optional[AuditorAgent] = None,
        api_key: Optional[str] = None,
        prompt_version: str = "2.4"
    ):
        """
        Initialize the DM Agent.
        
        Args:
            db: Neo4jDatabase instance for database operations.
            query_agent: Instance of QueryAgent.
            auditor_agent: Instance of AuditorAgent.
            api_key: The Gemini API key (only for DMAgent's own LLM calls).
            model_name: The name of the Gemini model to use.
            prompt_version: The version of the DM prompt to use.
        """
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        
        # Injected Agents
        self.query_agent = query_agent
        self.auditor = auditor_agent
        
        # Load campaign context from config or rules
        self.history: List[Dict[str, str]] = []
        
        # Session 0 state
        self.session_0_complete = False
        self.session_0_answers: Dict[str, str] = {}
        
        # Track entities generated this session
        self.entities_generated: List[str] = []
        self.entities_blocked: List[Dict[str, Any]] = []

        # Campaign tracking
        self.campaign_id: Optional[str] = None
        self.campaign_metadata: Optional[Dict[str, Any]] = None

        # Session reference
        self.session: Optional[GameSession] = None

        # Prompt version
        self._prompt_version = prompt_version

        # Arc Engine for narrative structure and pacing
        self._arc_engine: Optional[ArcEngine] = None
        if ARC_ENGINE_AVAILABLE:
            self._arc_engine = ArcEngine()
            logging.info("[ARC ENGINE] Arc Engine initialized in DMAgent")

        # Dual-mode configuration (defaults to casual one-shot)
        self._game_config: Optional[GameConfig] = None
        self._session_ended = False  # Flag for THE END state

        # Canon truths injection (from world integrity check)
        self._canon_truths: Optional[CanonTruths] = None

        # Pending structured events for frontend
        self._pending_events: List[GameEvent] = []

        # Visual Engine integration
        self._visual_engine_enabled = os.getenv("VISUAL_ENGINE_ENABLED", "false").lower() == "true"
        self._last_visual_assessment: Optional[Dict[str, Any]] = None

    @property
    def arc_engine(self) -> Optional[ArcEngine]:
        """Get the Arc Engine instance (if available)."""
        return self._arc_engine

    def get_arc_context(self) -> str:
        """
        Get arc context for prompt injection.

        Returns empty string if Arc Engine not available.
        """
        if not self._arc_engine:
            logging.debug("[ARC ENGINE] get_arc_context() called but Arc Engine not available")
            return ""
        
        context = self._arc_engine.get_dm_context_injection()
        logging.debug(f"[ARC ENGINE] get_arc_context() returned context (length: {len(context)})")
        return context

    def get_arc_status(self) -> Optional[Dict[str, Any]]:
        """Get current arc status for external inspection."""
        if not self._arc_engine:
            return None
        return self._arc_engine.get_status()

    def set_game_config(self, config: "GameConfig") -> None:
        """Set the game configuration for dual-mode support."""
        self._game_config = config

    def set_canon_truths(self, truths: "CanonTruths") -> None:
        """Set the immutable canon truths for prompt injection."""
        self._canon_truths = truths

    @property
    def canon_truths(self) -> Optional["CanonTruths"]:
        """Get the current canon truths."""
        return self._canon_truths

    def get_canon_truths_context(self) -> str:
        """
        Get canon truths for prompt injection.

        Returns:
            Formatted canon truths for DM prompt injection
        """
        if not self._canon_truths:
            return ""
        return self._canon_truths.to_prompt_injection()

    def add_event(self, event: "GameEvent") -> None:
        """Add a structured game event for frontend notification."""
        self._pending_events.append(event)

    def flush_events(self) -> List["GameEvent"]:
        """Get and clear pending events."""
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events

    @property
    def is_session_ended(self) -> bool:
        """Check if the session has reached THE END."""
        return self._session_ended

    def get_pacing_context(self, turn: int) -> str:
        """
        Get pacing pressure context based on game mode.

        ONE_SHOT: Forces AI to drive toward climax in later turns.
        CAMPAIGN: Enforces slow buildup and grounded progression.

        Args:
            turn: Current turn number (0-indexed)

        Returns:
            Pacing instruction to inject into prompts
        """
        if not self._game_config:
            return ""

        if not self._game_config.is_one_shot():
            # CAMPAIGN MODE: Slow burn, earned status
            return """
=== PACING: CAMPAIGN MODE (LONG FORM) ===
- Do NOT rush the narrative. Allow scenes to breathe.
- The player is NOT a "Chosen One" or instantly special.
- Respect earned progression: status, power, and reputation must be built over time.
- Focus on small, grounded details and local consequences.
- Introduce mysteries that may not be solved for a long time.
"""

        # ONE_SHOT MODE logic (existing + reinforced urgency)
        phase = self._game_config.get_pacing_phase(turn)
        remaining = self._game_config.max_turns - turn

        pacing_instructions = {
            "INTRO": """
=== PACING: ONE-SHOT INTRO (Turns 1-3) ===
- Establish atmosphere QUICKLY.
- Introduce the central conflict immediately.
- Don't linger on travel or minor details.
""",
            "RISING": f"""
=== PACING: ONE-SHOT RISING ACTION (Turns 4-14) ===
- Escalate tension with EVERY response.
- Move the story forward aggressively.
- Remaining turns: {remaining}
""",
            "CLIMAX": f"""
=== PACING: ONE-SHOT CLIMAX (Turns 15-20) ===
⚠️ CRITICAL: Only {remaining} turns remaining!
- FORCE a confrontation or resolution now.
- No new mysteries. Solve the current one.
- Make consequences feel final.
""",
            "END": """
=== PACING: RESOLUTION ===
⚠️ THIS IS THE FINAL TURN.
- Deliver a satisfying conclusion.
- Resolve the central conflict.
- End with: "**THE END**"
- This session is complete.
""",
        }

        return pacing_instructions.get(phase, "")

    def get_complexity_context(self) -> str:
        """
        Get narrative complexity instructions based on config.

        Returns:
            Complexity instruction to inject into prompts
        """
        if not self._game_config:
            return ""

        if self._game_config.is_verbose():
            return """
=== NARRATIVE STYLE: VERBOSE ===
- Use rich, literary prose with sensory details
- Allow for longer, more immersive descriptions
- Include atmospheric and emotional depth
"""
        else:
            return """
=== NARRATIVE STYLE: CONCISE ===
- Keep responses short and action-focused
- Prioritize clarity over flourish
- Maximum 3-4 paragraphs per response
"""

    @property
    def system_prompt(self) -> str:
        """
        Get the DM system prompt with current campaign context.

        Dynamically generates the prompt based on Session 0 answers
        or uses defaults if Session 0 is not complete.
        """
        # Build context from session 0 answers or use defaults
        context = {
            "campaign_name": self.session_0_answers.get("setting", "Fantasy Campaign"),
            "world_tone": self.session_0_answers.get("tone", "High Adventure"),
            "setting_description": self.session_0_answers.get("setting", "A magical world of adventure"),
            "current_date": "Unknown Era",
            "naming_conventions": "Standard Fantasy (evocative but pronounceable)",
        }

        # Get base system prompt
        base_prompt = DMPrompts.get_system_prompt(version=self._prompt_version, context=context)

        # Append worldbuilding rules if available
        worldbuilding_rules = load_worldbuilding_rules()

        return base_prompt + worldbuilding_rules

    async def start_session(self, session_id: Optional[str] = None, player_id: str = "player_1"):
        """Initialize a new game session."""
        self.session = GameSession(self.db, session_id)
        await self.session.initialize(player_id)

        # Reset conversation state
        self.history = []
        self.session_0_complete = False
        self.session_0_answers = {}
        self.entities_generated = []
        self.entities_blocked = []

        # Initialize Arc Engine with session ID
        if ARC_ENGINE_AVAILABLE:
            self._arc_engine = ArcEngine(session_id=self.session.session_id)
            logging.info(f"[ARC ENGINE] Arc Engine re-initialized for session {self.session.session_id}")

        return self.session.session_id

    async def process_input(self, player_input: str) -> str:
        """
        Main entry point for player input.
        Routes to Session 0 or Active Play based on state.
        """
        if not self.session:
            raise RuntimeError("No active session. Call start_session() first.")

        # Check if session has ended (ONE_SHOT reached conclusion)
        if self._session_ended:
            return (
                "**THE END**\n\n"
                "*This story has concluded. Thank you for playing!*\n\n"
                "To start a new adventure, begin a new session."
            )

        # Log player input
        await self.session.add_event("PLAYER_ACTION", player_input)
        self.history.append({"role": "user", "content": player_input})

        # Route based on session state
        if not self.session_0_complete:
            response = await self._handle_session_0(player_input)
        else:
            response = await self._handle_active_play(player_input)

        # Check for THE END marker in response
        if "**THE END**" in response or "THE END" in response.upper():
            self._session_ended = True
            await AuditLogger.log("Session ended: ONE_SHOT reached conclusion")

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
            campaign_id, metadata = await self.session.create_campaign(
                name=self.session_0_answers.get("setting", "Unnamed Campaign"),
                description=self.session_0_answers.get("setting"),
                tone=self.session_0_answers.get("tone"),
                setting_theme=None,
            )

            self.campaign_id = campaign_id
            self.campaign_metadata = metadata

            
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
                lore_results = await self.query_agent.search_entities(setting, campaign_id=self.campaign_id)
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

=== CRITICAL AGENCY RULE ===
You MUST NOT describe the player character's internal thoughts, feelings, or spoken words.
You MUST NOT decide what the player does next.
Describe the scene and the immediate situation, then STOP and wait for the player.
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
        Handle active gameplay after Session 0 with boundary enforcement.
        
        Flow:
        1. Classify player intent
        2. If boundary violation → educate and reframe
        3. If valid → process normally
        """
        # 1. Classify intent for boundary violations
        intent = await PlayerIntent.classify_intent(player_input)
        
        # 2. Check for boundary violations
        if PlayerIntent.is_violation(intent):
            # Log violation (for metrics/learning)
            await AuditLogger.log(
                f"Player boundary violation: {intent.value} - '{player_input}'",
                level=logging.INFO
            )
            
            # Get appropriate educational reminder
            violation_type = intent.value.replace("_", " ")
            reminder = BoundaryPrompts.get_reminder(violation_type)
            
            # Reframe as valid player action
            reframed_response = await self._reframe_invalid_input(
                player_input,
                PlayerIntent.get_violation_type_name(intent)
            )
            
            # Return educational message + reframed response
            return f"""{reminder}

I'll interpret your intent as a question:

{reframed_response}"""
        
        # 3. Valid intent - proceed with entity-aware generation
        return await self._handle_active_play_with_generation(player_input)

    async def _reframe_invalid_input(
        self,
        player_input: str,
        violation_type: str
    ) -> str:
        """
        Reframe boundary violation as valid player action.
        
        Uses Gemini to gracefully convert invalid input into valid question/action.
        
        Args:
            player_input: Original invalid input
            violation_type: Type of violation (for context)
            
        Returns:
            DM response to reframed valid action
        """
        # Build reframing prompt
        reframe_prompt = BoundaryPrompts.build_reframe_prompt(
            player_input,
            violation_type
        )
        
        # Call Gemini to reframe and respond
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.model.generate_content(
                reframe_prompt,
                generation_config={"temperature": 0.7, "max_output_tokens": 500}
            )
        )
        
        return response.text

    async def _generate_normal_response(self, player_input: str) -> str:
        """
        Generate normal DM response (no boundary violations).

        This is the standard entity extraction + generation logic.
        Integrates with Arc Engine for narrative structure awareness.
        """
        # Build context from history (last N exchanges)
        history_context = self._format_history(limit=10)

        # Retrieve relevant lore
        lore_context = await self._retrieve_lore_context(player_input)

        # Get current session state
        state = await self.session.get_state()
        state_context = self._format_state(state)

        # Get arc context for narrative structure (if available)
        arc_context = self.get_arc_context()

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
=== INSTRUCTION ===
Respond as the DM. Follow the Pacing Formula.
You determine all outcomes based on narrative logic, character capabilities, and circumstances.
Do NOT ask for dice rolls or reference game mechanics unless a ruleset is specified.

=== CRITICAL AGENCY RULE ===
You MUST NOT describe the player character's internal thoughts, feelings, or spoken words.
You MUST NOT auto-complete the player's intended actions.
Only describe the immediate outcome and the world's reaction.
Stop and wait for the player's response.
"""

        response = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.85,
                "max_output_tokens": 600
            }
        )

        response_text = response.text

        # Process response through Arc Engine for state updates
        if self._arc_engine:
            logging.info(f"[ARC ENGINE] Processing narrative through Arc Engine (player_action length: {len(player_input)})")
            try:
                self._arc_engine.process_narrative(
                    narrative_text=response_text,
                    player_action=player_input,
                )
                logging.info(f"[ARC ENGINE] Narrative processed - Phase: {self._arc_engine.current_phase.value if hasattr(self._arc_engine, 'current_phase') else 'unknown'}, Tension: {self._arc_engine.tension_level.value if hasattr(self._arc_engine, 'tension_level') else 'unknown'}")
            except Exception as e:
                logging.error(f"[ARC ENGINE] Error processing narrative: {e}")
                import traceback
                logging.error(f"[ARC ENGINE] Traceback:\n{traceback.format_exc()}")

        return response_text

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
                saved = dict(result[0])

                # Link entity to campaign if active
                if self.campaign_id:
                    try:
                        await self.db.execute(
                            """
                            MATCH (e:Entity {name: $name})
                            MATCH (c:Campaign {campaign_id: $campaign_id})
                            MERGE (e)-[:BELONGS_TO]->(c)
                            """,
                            {"name": saved.get("name"), "campaign_id": self.campaign_id}
                        )
                    except Exception as e:
                        await AuditLogger.log(
                            f"Failed to link entity to campaign: {e}",
                            level=logging.ERROR
                        )

                return saved

            return None
        except Exception as e:
            await AuditLogger.log(f"Failed to persist entity: {e}", level=logging.ERROR)
            return None

    async def _check_entity_exists(self, entity_name: str) -> bool:
            if self.campaign_id:
                cypher = """
                MATCH (e:Entity {name: $name})-[:BELONGS_TO]->(:Campaign {campaign_id: $campaign_id})
                RETURN count(e) > 0 AS exists
                """
                params = {"name": entity_name, "campaign_id": self.campaign_id}
            else:
                cypher = """
                MATCH (e:Entity {name: $name})
                RETURN count(e) > 0 AS exists
                """
                params = {"name": entity_name}

            records = await self.db.execute(cypher, params)
            return records[0]["exists"] if records else False


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
            generation_instruction = "\n\n=== ENTITIES TO CREATE (if you introduce them in your narrative) ===\n"
            
            for entity in entities_to_generate:
                # Map extracted type to EntityType
                raw_type = entity.get("type", "Concept")
                try:
                    e_type = EntityType(raw_type)
                except ValueError:
                    e_type = EntityType.CONCEPT
                
                # Get template and guidelines
                template = EntityFactory.get_template(e_type)
                
                generation_instruction += f"""
ENTITY: {entity.get("name")} ({e_type.value})
GUIDELINES:
{template.generation_guidelines}
NAMING: {template.naming_conventions}
"""

        # Build JSON instruction with optional visual assessment
        visual_schema = ""
        if self._visual_engine_enabled:
            visual_schema = DMPrompts.get_visual_schema()

        json_instruction = f"""
=== OUTPUT FORMAT ===
At the end of your response, you MUST include a JSON block for system use:
```json
{{
  "visual_summary": "Evocative visual description of the current scene (max 30 words) suitable for image generation.",
  "new_entities": [
    // Include definitions for any NEW entities you introduced based on the guidelines above.
    // If no new entities, leave this list empty.
  ]
}}
```
{visual_schema}
"""

        # 4. Build full prompt
        history_context = self._format_history(limit=10)
        state = await self.session.get_state()
        state_context = self._format_state(state)

        # Get turn number for pacing
        session_info = state.get("session", {}) if state else {}
        turn_count = session_info.get("turn_count", len(self.history) // 2)

        # Get pacing and complexity contexts
        pacing_context = self.get_pacing_context(turn_count)
        complexity_context = self.get_complexity_context()

        # Get canon truths for consistency enforcement
        canon_truths_context = self.get_canon_truths_context()

        # Get visual direction if visual engine is enabled
        visual_direction = ""
        if self._visual_engine_enabled:
            visual_direction = DMPrompts.get_visual_direction()

        prompt = f"""{self.system_prompt}
{canon_truths_context}
=== SESSION CONTEXT ===
Setting: {self.session_0_answers.get('setting', 'Unknown')}
Character: {self.session_0_answers.get('character', 'Unknown')}
Tone: {self.session_0_answers.get('tone', 'Unknown')}
Turn: {turn_count}

=== CONVERSATION HISTORY ===
{history_context}

=== CURRENT STATE ===
{state_context}

=== LORE CONTEXT (Canon - Use if relevant) ===
{lore_context}
{generation_instruction}
{json_instruction}
{pacing_context}
{complexity_context}
{visual_direction}
=== PLAYER'S ACTION ===
{player_input}

=== INSTRUCTION ===
Respond as the DM. Follow the Pacing Formula. Do NOT speak for the player.
You determine all outcomes based on narrative logic, character capabilities, and circumstances.
Do NOT ask for dice rolls or reference game mechanics unless a ruleset is specified.
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
        narrative, new_entities, visual_summary, visual_assessment = self._parse_response_with_entities(response_text)

        if visual_summary and self.session:
            await self.session.add_event("VISUAL_SCENE", visual_summary)
            logging.info(f"[VISUAL] Generated scene: {visual_summary}")

        if visual_assessment and self.session:
            await self.session.add_event("VISUAL_ASSESSMENT", json.dumps(visual_assessment))
            logging.info(f"[VISUAL] Assessment: type={visual_assessment.get('image_type')}, mood={visual_assessment.get('mood')}")

        if new_entities and self.session:
            for entity in new_entities:
                # Use factory skeleton as base to ensure structure
                try:
                    e_type = EntityType(entity.get("label", "Concept"))
                except ValueError:
                    e_type = EntityType.CONCEPT
                    
                # Validate roughly (optional, as we are creating it now)
                # EntityFactory.validate_entity(entity, EntityFactory.get_template(e_type))
                
                created = await self._create_canonical_entity(entity, self.session.session_id)
                if not created:
                    # Entity was blocked - add note to narrative
                    narrative += "\n\n*[Some details require verification with the lore archives...]*"
                    break  # Only add note once
        
        return narrative

    def _parse_response_with_entities(self, response_text: str) -> tuple[str, List[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]]]:
        """
        Parse DM response to extract narrative, entities, and visual assessment.

        Returns: (narrative_text, list_of_new_entities, visual_summary, visual_assessment)
        """
        # Try to find JSON block at end of response
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response_text)

        if json_match:
            try:
                data = json.loads(json_match.group(1))
                new_entities = data.get("new_entities", [])
                visual_summary = data.get("visual_summary")
                visual_assessment = data.get("visual_assessment")

                # Store visual assessment for later retrieval
                if visual_assessment:
                    self._last_visual_assessment = visual_assessment
                    logging.info(f"[VISUAL] Assessment extracted: {visual_assessment.get('image_type')} - {visual_assessment.get('mood')}")

                # Remove JSON block from narrative
                narrative = response_text[:json_match.start()].strip()

                return narrative, new_entities, visual_summary, visual_assessment
            except json.JSONDecodeError:
                pass

        # No valid JSON found - return full response as narrative
        return response_text, [], None, None

    def get_last_visual_assessment(self) -> Optional[Dict[str, Any]]:
        """Get the most recent visual assessment from the last response."""
        return self._last_visual_assessment

    def clear_visual_assessment(self) -> None:
        """Clear the stored visual assessment after it's been processed."""
        self._last_visual_assessment = None

    def get_visual_assessment_for_engine(self) -> Optional["VisualAssessment"]:
        """
        Get the last visual assessment as a VisualAssessment object for the Visual Engine.

        Returns:
            VisualAssessment object or None if no assessment available
        """
        if not self._last_visual_assessment:
            return None

        try:
            from src.mantle.visual.types import VisualAssessment
            return VisualAssessment.from_dict(self._last_visual_assessment)
        except ImportError:
            logging.warning("[VISUAL] Visual engine types not available")
            return None
        except Exception as e:
            logging.error(f"[VISUAL] Failed to convert assessment: {e}")
            return None

    # ==========================================
    # PERSONALITY-AWARE GENERATION (OCEAN Model)
    # ==========================================

    async def _generate_entity_with_personality(
        self,
        entity_name: str,
        entity_type: EntityType,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate entity with personality profile (for Characters).
        
        Args:
            entity_name: Name of the entity to generate
            entity_type: Type of entity (Character, Location, etc.)
            context: Additional context including inferred_role, lore_context
            
        Returns:
            Generated entity data with OCEAN traits (for Characters)
        """
        # Get template
        template = EntityFactory.get_template(entity_type)
        
        # For Characters, generate OCEAN profile
        personality_context = ""
        if entity_type == EntityType.CHARACTER:
            # Infer role from context or use default
            role = context.get('inferred_role', 'commoner')
            
            # Generate personality from role
            personality = PersonalityGenerator.generate_from_role(role)
            
            # Add personality to context for prompt
            personality_context = f"""

PERSONALITY PROFILE (OCEAN):
- Openness: {personality.openness:.1f} ({personality.get_trait_descriptor('openness', personality.openness)})
- Conscientiousness: {personality.conscientiousness:.1f} ({personality.get_trait_descriptor('conscientiousness', personality.conscientiousness)})
- Extraversion: {personality.extraversion:.1f} ({personality.get_trait_descriptor('extraversion', personality.extraversion)})
- Agreeableness: {personality.agreeableness:.1f} ({personality.get_trait_descriptor('agreeableness', personality.agreeableness)})
- Neuroticism: {personality.neuroticism:.1f} ({personality.get_trait_descriptor('neuroticism', personality.neuroticism)})

Behavioral Summary: {personality.get_behavioral_summary()}
Dialogue Style: {personality.get_dialogue_style()}

Include these OCEAN values in the entity properties:
- openness: {personality.openness:.2f}
- conscientiousness: {personality.conscientiousness:.2f}
- extraversion: {personality.extraversion:.2f}
- agreeableness: {personality.agreeableness:.2f}
- neuroticism: {personality.neuroticism:.2f}
"""
        
        # Build prompt
        prompt = DMPrompts.build_entity_generation_prompt(
            entity_type=entity_type.value,
            entity_name=entity_name,
            generation_guidelines=template.generation_guidelines,
            naming_conventions=template.naming_conventions,
            required_properties=", ".join(template.required_properties),
            optional_properties=", ".join(template.optional_properties),
            lore_context=context.get('lore_context', 'No existing context') + personality_context
        )
        
        # Generate entity
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.model.generate_content(
                prompt,
                generation_config={"temperature": 0.7, "max_output_tokens": 800}
            )
        )
        
        # Parse response
        try:
            cleaned = response.text.strip()
            cleaned = re.sub(r'^```json\s*', '', cleaned)
            cleaned = re.sub(r'^```\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            
            entity_data = json.loads(cleaned)
            await AuditLogger.log(f"Generated entity with personality: {entity_name}")
            return entity_data
        except Exception as e:
            await AuditLogger.log(f"Entity generation failed: {e}", level=logging.WARNING)
            return {}

    async def _generate_npc_dialogue(
        self,
        npc_name: str,
        npc_data: Dict[str, Any],
        player_input: str
    ) -> str:
        """
        Generate NPC dialogue using personality profile.
        
        Args:
            npc_name: NPC name
            npc_data: NPC entity data (including OCEAN traits)
            player_input: What player said/did
            
        Returns:
            NPC's response in character
        """
        # Extract personality if present
        properties = npc_data.get('properties', {})
        
        personality_guidance = ""
        ocean_traits = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
        
        if all(k in properties for k in ocean_traits):
            personality = OCEANProfile.from_dict(properties)
            
            personality_guidance = f"""
{npc_name}'s Personality Profile:
- Behavioral traits: {personality.get_behavioral_summary()}
- Dialogue style: {personality.get_dialogue_style()}

Respond as {npc_name} would, staying true to their personality.
Keep responses consistent with their OCEAN profile.
"""
        
        prompt = f"""
You are roleplaying as {npc_name}.

Description: {properties.get('description', 'An NPC in the world')}
Role: {properties.get('role', 'Unknown')}
{personality_guidance}

Player action: {player_input}

Respond in character as {npc_name}. Keep the response concise and in-character.
Do NOT break character or provide meta-commentary.
"""
        
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.model.generate_content(
                prompt,
                generation_config={"temperature": 0.8, "max_output_tokens": 400}
            )
        )
        
        return response.text

    def _add_personality_to_entity(
        self,
        entity: Dict[str, Any],
        role: str = "commoner"
    ) -> Dict[str, Any]:
        """
        Add OCEAN personality traits to a Character entity.
        
        Args:
            entity: Entity dict with properties
            role: Role/occupation for personality inference
            
        Returns:
            Entity dict with OCEAN traits added to properties
        """
        if entity.get("label") != "Character":
            return entity
        
        # Generate personality from role
        personality = PersonalityGenerator.generate_from_role(role)
        
        # Add to properties
        if "properties" not in entity:
            entity["properties"] = {}
        
        entity["properties"].update(personality.to_dict())
        
        return entity
