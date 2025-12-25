# src/lms/api/game_routes.py
"""
Game Session API Routes

Endpoints for:
- Creating and managing game sessions
- Processing player actions through the DM
- Generating worlds from seed prompts
"""

from __future__ import annotations

import os
import uuid
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Request, status, Depends, File, UploadFile
from pydantic import BaseModel, Field

from src.lms.db.neo4j_adapter import Neo4jDatabase
from src.lms.api.dependencies import get_neo4j_db
from src.lms.agents.query_agent import QueryAgent
from src.lms.agents.auditor_agent import AuditorAgent
from src.lms.agents.lore_parsing_agent import LoreParsingAgent
from src.lms.guardrails.token_budget import TokenTracker, BudgetExceeded, RateLimitExceeded, estimate_tokens
from src.lms.guardrails.circuit_breaker import get_circuit_breaker, CircuitOpen

logger = logging.getLogger(__name__)

# Shared lore parsing agent for extracting entities from gameplay
_lore_parser: Optional[LoreParsingAgent] = None


def get_lore_parser() -> LoreParsingAgent:
    """Get or create the shared lore parsing agent."""
    global _lore_parser
    if _lore_parser is None:
        _lore_parser = LoreParsingAgent()
    return _lore_parser


async def extract_and_store_gameplay_lore(
    narrative: str,
    session_id: str,
    db: Optional[Neo4jDatabase],
) -> None:
    """
    Extract entities from gameplay narrative and store them in Neo4j.

    This runs asynchronously after the narrative is returned to the player,
    so it doesn't slow down the gameplay experience.
    """
    if not db:
        logger.debug("No database available for lore extraction")
        return

    if len(narrative) < 100:
        # Too short to contain meaningful entities
        return

    try:
        parser = get_lore_parser()

        # Parse the narrative for entities
        result = await parser.parse_and_store(
            text=narrative,
            db=db,
            source_name=f"session:{session_id}",
        )

        if result.entities_stored > 0:
            logger.info(
                f"[LORE] Extracted {result.entities_stored} entities from session {session_id} "
                f"({result.characters_with_ocean} with OCEAN profiles)"
            )
    except Exception as e:
        # Don't let extraction failures affect gameplay
        logger.warning(f"[LORE] Entity extraction failed for session {session_id}: {e}")

# Gemini configuration - same model as LoreParsingAgent
GEMINI_MODEL = "gemini-2.0-flash-exp"  # This works for lore parsing


def get_gemini_model():
    """Get a fresh Gemini model instance for each request."""
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)
    logger.info(f"Gemini model created: {GEMINI_MODEL}")
    return model

router = APIRouter(prefix="/game", tags=["Game"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class WorldSeedRequest(BaseModel):
    """Request to generate a world from a seed prompt."""
    seed_prompt: str = Field(
        ...,
        min_length=10,
        description="A brief description of the world to generate",
        examples=["A dark fantasy realm where magic corrupts its users"]
    )
    tone: Optional[str] = Field(
        default="dark fantasy",
        description="The narrative tone"
    )
    generate_entities: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of initial entities to generate"
    )


class WorldSeedResponse(BaseModel):
    """Response from world generation."""
    world_id: str
    name: str
    description: str
    entities_created: List[Dict[str, Any]]
    message: str


class SessionCreateRequest(BaseModel):
    """Request to create a new game session."""
    world_id: Optional[str] = None
    character_concept: Optional[str] = Field(
        default=None,
        description="Brief character concept for Session 0"
    )
    setting_preference: Optional[str] = None
    tone_preference: Optional[str] = None
    genre: Optional[str] = Field(
        default="fantasy",
        description="Story genre (fantasy, romance, mystery, horror, adventure, drama)"
    )
    storytelling_style: Optional[str] = Field(
        default="guided",
        description="How structured: guided, freeform, or collaborative"
    )


class SessionResponse(BaseModel):
    """Game session information."""
    session_id: str
    status: str
    phase: str  # "session_0" or "active_play"
    created_at: datetime
    arc_status: Optional[Dict[str, Any]] = None


class PlayerActionRequest(BaseModel):
    """Player action input."""
    action: str = Field(..., min_length=1, description="What the player does or says")


class DMResponse(BaseModel):
    """DM response to player action."""
    narrative: str
    session_id: str
    phase: str
    arc_context: Optional[Dict[str, Any]] = None
    suggested_actions: Optional[List[str]] = None
    episode_status: Optional[Dict[str, Any]] = None


# ============================================================
# IN-MEMORY SESSION STORE (for MVP - replace with Neo4j later)
# ============================================================

_active_sessions: Dict[str, Dict[str, Any]] = {}

# Global guardrails
_token_tracker = TokenTracker()
_gemini_breaker = get_circuit_breaker("gemini")
_executor = ThreadPoolExecutor(max_workers=4)


async def protected_ai_call(
    model,
    prompt: str,
    session_id: str,
    temperature: float = 0.85,
    max_output_tokens: int = 500,
) -> str:
    """
    Make an AI call with token budget and circuit breaker protection.

    Raises:
        HTTPException: If budget exceeded, rate limited, or circuit open
    """
    logger.info(f"[PROTECTED] Entering protected_ai_call for session {session_id}")

    # Estimate tokens
    input_tokens = estimate_tokens(prompt)
    output_tokens = max_output_tokens  # Conservative estimate
    logger.info(f"[PROTECTED] Estimated tokens: input={input_tokens}, output={output_tokens}")

    # Check budget
    logger.info(f"[PROTECTED] Checking token budget...")
    try:
        _token_tracker.check_budget(session_id, input_tokens, output_tokens)
        logger.info(f"[PROTECTED] Budget check passed")
    except BudgetExceeded as e:
        logger.warning(f"Budget exceeded for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Usage limit reached: {str(e)}. Please try again later."
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please slow down. Try again in {e.wait_seconds:.1f} seconds."
        )

    # Check circuit breaker
    logger.info(f"[PROTECTED] Checking circuit breaker...")
    try:
        _gemini_breaker.allow_request()
        logger.info(f"[PROTECTED] Circuit breaker check passed")
    except CircuitOpen as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service temporarily unavailable. Try again in {e.retry_after:.0f} seconds."
        )

    # Make the call in a thread pool to avoid blocking the event loop
    def _sync_generate():
        try:
            logger.info(f"[GEMINI] Starting generate_content for session {session_id}")
            logger.info(f"[GEMINI] Prompt length: {len(prompt)} chars")
            result = model.generate_content(
                prompt,
                generation_config={"temperature": temperature, "max_output_tokens": max_output_tokens}
            )
            logger.info(f"[GEMINI] Call completed for session {session_id}")
            return result
        except Exception as e:
            logger.error(f"[GEMINI] Sync call failed: {e}")
            raise

    try:
        logger.info(f"[GEMINI] Submitting to executor for session {session_id}")
        loop = asyncio.get_event_loop()
        # Add 45-second timeout to prevent infinite hangs
        response = await asyncio.wait_for(
            loop.run_in_executor(_executor, _sync_generate),
            timeout=45.0
        )
        logger.info(f"[GEMINI] Executor returned for session {session_id}")

        # Record success
        _gemini_breaker.record_success()

        # Record actual usage (estimate output tokens from response)
        actual_output = estimate_tokens(response.text)
        _token_tracker.record_usage(session_id, input_tokens, actual_output)

        return response.text

    except asyncio.TimeoutError:
        _gemini_breaker.record_failure()
        logger.error(f"AI call timed out for session {session_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Story generation timed out. Please try again."
        )
    except Exception as e:
        _gemini_breaker.record_failure()
        logger.error(f"AI call failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service error: {str(e)}"
        )


def get_dm_agent(request: Request):
    """Get or create DM agent from app state."""
    if not hasattr(request.app.state, "dm_agent") or request.app.state.dm_agent is None:
        return None
    return request.app.state.dm_agent


# ============================================================
# WORLD GENERATION
# ============================================================

@router.post("/world/seed", response_model=WorldSeedResponse)
async def seed_world(
    request: Request,
    seed: WorldSeedRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Generate a new world from a seed prompt.

    Creates initial entities, locations, and lore based on the seed description.
    """
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured"
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    world_id = str(uuid.uuid4())[:8]

    # Generate world details with rich character descriptions for OCEAN extraction
    world_prompt = f"""You are a world-builder for a tabletop RPG.

Given this seed concept: "{seed.seed_prompt}"
Tone: {seed.tone}

Generate a world with:
1. An evocative name (2-4 words)
2. A rich description (2-3 paragraphs)
3. {seed.generate_entities} initial entities (mix of locations, characters, factions)

IMPORTANT: For each CHARACTER entity, include personality traits in the description using words like:
brave, cunning, loyal, vengeful, kind, cold, ambitious, cautious, impulsive, patient, calculating,
warm, charismatic, fearful, aggressive, studious, curious, forgiving, strict, creative, methodical.

Example: "Lord Aldric is calculating and ambitious, known for his cold demeanor yet kind to scholars."

Return ONLY valid JSON in this exact format:
{{
    "name": "World Name",
    "description": "Full world description...",
    "entities": [
        {{
            "name": "Entity Name",
            "type": "Location|Character|Faction|Item|Concept",
            "description": "Entity description with personality traits for characters..."
        }}
    ]
}}
"""

    try:
        # Use protected AI call with guardrails
        text = await protected_ai_call(
            model,
            world_prompt,
            session_id=f"world_{world_id}",
            temperature=0.9,
            max_output_tokens=2000,
        )

        # Parse JSON from response
        import json
        import re
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)

        world_data = json.loads(text)

        # Build narrative text from all entity descriptions for LoreParsingAgent
        narrative_parts = [world_data.get("description", "")]
        for entity in world_data.get("entities", []):
            narrative_parts.append(f"{entity['name']} - {entity.get('description', '')}")

        full_narrative = "\n\n".join(narrative_parts)

        # Route through LoreParsingAgent for AI-powered OCEAN profile generation
        entities_created = []
        try:
            from src.lms.agents.lore_parsing_agent import LoreParsingAgent

            agent = LoreParsingAgent()
            logger.info(f"Processing world entities through LoreParsingAgent for OCEAN profiles")

            parse_result = await agent.parse_and_store(
                text=full_narrative,
                db=db,
                source_name=f"world:{world_id}",
            )

            # Map parsed entities back to response
            for entity in parse_result.entities:
                entities_created.append({
                    "canon_id": f"{world_id}_{entity.name.lower().replace(' ', '_')}",
                    "name": entity.name,
                    "type": entity.entity_type,
                })

            logger.info(
                f"LoreParsingAgent created {parse_result.entities_stored} entities, "
                f"{parse_result.characters_with_ocean} with OCEAN profiles"
            )

        except Exception as ingest_err:
            logger.warning(f"LoreParsingAgent failed, falling back to direct creation: {ingest_err}")

            # Fallback: Direct entity creation (without OCEAN profiles)
            for entity in world_data.get("entities", []):
                canon_id = f"{world_id}_{entity['name'].lower().replace(' ', '_')}"

                await db.execute("""
                    MERGE (e:Entity {canon_id: $canon_id})
                    SET e.name = $name,
                        e.entity_type = $type,
                        e.description = $description,
                        e.world_id = $world_id,
                        e.approval_status = 'PENDING',
                        e.confidence_level = 'AI_GENERATED',
                        e.created_at = datetime()
                    WITH e
                    CALL apoc.create.addLabels(e, [$type]) YIELD node
                    RETURN node
                """, {
                    "canon_id": canon_id,
                    "name": entity["name"],
                    "type": entity["type"],
                    "description": entity["description"],
                    "world_id": world_id,
                })

                entities_created.append({
                    "canon_id": canon_id,
                    "name": entity["name"],
                    "type": entity["type"],
                })

        # Store world metadata
        await db.execute("""
            MERGE (w:World {world_id: $world_id})
            SET w.name = $name,
                w.description = $description,
                w.seed_prompt = $seed_prompt,
                w.tone = $tone,
                w.created_at = datetime()
        """, {
            "world_id": world_id,
            "name": world_data["name"],
            "description": world_data["description"],
            "seed_prompt": seed.seed_prompt,
            "tone": seed.tone,
        })

        logger.info(f"Created world '{world_data['name']}' with {len(entities_created)} entities")

        return WorldSeedResponse(
            world_id=world_id,
            name=world_data["name"],
            description=world_data["description"],
            entities_created=entities_created,
            message=f"World '{world_data['name']}' created with {len(entities_created)} entities"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse world generation response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse generated world data"
        )
    except Exception as e:
        logger.error(f"World generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"World generation failed: {str(e)}"
        )


# ============================================================
# SESSION MANAGEMENT
# ============================================================

def get_optional_neo4j_db(request: Request):
    """Get Neo4j database if available, otherwise None."""
    return getattr(request.app.state, "neo4j_db", None)


@router.post("/session", response_model=SessionResponse)
async def create_session(
    request: Request,
    session_req: SessionCreateRequest,
):
    """
    Create a new game session.

    If no world_id is provided, starts in Session 0 mode to establish
    the setting collaboratively with the player.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Determine initial phase
    phase = "session_0" if not session_req.world_id else "active_play"

    session_data = {
        "session_id": session_id,
        "world_id": session_req.world_id,
        "character_concept": session_req.character_concept,
        "setting_preference": session_req.setting_preference,
        "tone_preference": session_req.tone_preference,
        "genre": session_req.genre or "fantasy",
        "storytelling_style": session_req.storytelling_style or "guided",
        "phase": phase,
        "status": "active",
        "created_at": now,
        "history": [],
        "session_0_answers": {},
    }

    _active_sessions[session_id] = session_data

    # Store in Neo4j for persistence (if available)
    db = get_optional_neo4j_db(request)
    if db:
        try:
            await db.execute("""
                CREATE (s:GameSession {
                    session_id: $session_id,
                    world_id: $world_id,
                    phase: $phase,
                    status: 'active',
                    created_at: datetime()
                })
            """, {
                "session_id": session_id,
                "world_id": session_req.world_id or "",
                "phase": phase,
            })
        except Exception as e:
            logger.warning(f"Failed to persist session to Neo4j: {e}")

    logger.info(f"Created session {session_id} in phase {phase}")

    return SessionResponse(
        session_id=session_id,
        status="active",
        phase=phase,
        created_at=now,
    )


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session status and information."""
    if session_id not in _active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    session = _active_sessions[session_id]

    return SessionResponse(
        session_id=session_id,
        status=session["status"],
        phase=session["phase"],
        created_at=session["created_at"],
    )


@router.post("/session/{session_id}/action", response_model=DMResponse)
async def process_action(
    request: Request,
    session_id: str,
    action: PlayerActionRequest,
):
    """
    Process a player action and return the DM's response.

    Handles both Session 0 (world-building) and active play.
    """
    logger.info(f"Action request received for session {session_id}")

    if session_id not in _active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    session = _active_sessions[session_id]
    model = get_gemini_model()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured"
        )

    logger.info(f"Processing action for session {session_id}: {action.action[:50]}...")

    # Get optional database
    db = get_optional_neo4j_db(request)

    # Add action to history
    session["history"].append({"role": "user", "content": action.action})

    # Handle Session 0 (collaborative world-building)
    if session["phase"] == "session_0":
        response_text, new_phase = await _handle_session_0(
            session, action.action, model, db
        )
        session["phase"] = new_phase
    else:
        # Active play - generate DM response
        response_text = await _handle_active_play(
            session, action.action, model, db
        )

    # Add response to history
    session["history"].append({"role": "assistant", "content": response_text})

    # Extract and store lore entities from the narrative (fire-and-forget)
    # This runs in the background so it doesn't slow down the response
    asyncio.create_task(
        extract_and_store_gameplay_lore(response_text, session_id, db)
    )

    return DMResponse(
        narrative=response_text,
        session_id=session_id,
        phase=session["phase"],
    )


async def _handle_session_0(
    session: Dict[str, Any],
    player_input: str,
    model,
    db: Neo4jDatabase,
) -> tuple[str, str]:
    """Handle Session 0 collaborative world-building."""
    answers = session.get("session_0_answers", {})

    # Check if UI already provided the answers via session creation
    # If so, skip the questions and generate the opening directly
    has_setting = session.get("setting_preference") or answers.get("setting")
    has_character = session.get("character_concept") or answers.get("character")
    has_tone = session.get("tone_preference") or answers.get("tone")

    # If we have all the info from the UI, generate opening immediately
    if has_setting or has_character or has_tone:
        # Populate answers from session data for the opening generator
        if not answers.get("setting") and session.get("setting_preference"):
            answers["setting"] = session["setting_preference"]
        if not answers.get("character") and session.get("character_concept"):
            answers["character"] = session["character_concept"]
        if not answers.get("tone") and session.get("tone_preference"):
            answers["tone"] = session["tone_preference"]
        session["session_0_answers"] = answers

        # Generate opening scene directly
        opening = await _generate_opening(session, model)
        return opening, "active_play"

    # Fallback: If no UI data, ask questions conversationally
    if "setting" not in answers:
        answers["setting"] = player_input
        session["session_0_answers"] = answers
        return (
            f"*The mists part to reveal {player_input}...*\n\n"
            "**Who are you in this world?**\n\n"
            "*A weathered soldier? A curious scholar? A desperate thief?*",
            "session_0"
        )

    elif "character" not in answers:
        answers["character"] = player_input
        session["session_0_answers"] = answers
        return (
            f"*{player_input}... the world takes shape around you.*\n\n"
            "**What kind of story shall we tell?**\n\n"
            "*A grim tale of survival? A mystery to unravel? An epic quest?*",
            "session_0"
        )

    elif "tone" not in answers:
        answers["tone"] = player_input
        session["session_0_answers"] = answers

        # Generate opening scene
        opening = await _generate_opening(session, model)

        return opening, "active_play"

    return "Session 0 complete. Begin your adventure.", "active_play"


def _get_genre_guidance(genre: str) -> Dict[str, str]:
    """Get narrative guidance specific to each genre."""
    guidance = {
        "fantasy": {
            "elements": "magic, ancient prophecies, mystical creatures, heroic quests",
            "hooks": "a mysterious letter, a strange mark appearing, an artifact calling to you",
            "voice": "evocative and wonderous, with a sense of destiny",
        },
        "romance": {
            "elements": "emotional tension, meaningful glances, past connections, unspoken feelings",
            "hooks": "an unexpected reunion, a letter from the past, a chance encounter that changes everything",
            "voice": "warm and intimate, focused on feelings and connections between people",
        },
        "mystery": {
            "elements": "clues, secrets, suspicious characters, hidden motives, puzzles",
            "hooks": "something that doesn't add up, a detail that nags at you, an unexpected discovery",
            "voice": "atmospheric and intriguing, building tension through details",
        },
        "horror": {
            "elements": "dread, the unknown, isolation, things not quite right, building unease",
            "hooks": "something watching, a sound that shouldn't be there, a memory that doesn't fit",
            "voice": "unsettling and atmospheric, letting imagination fill the shadows",
        },
        "adventure": {
            "elements": "exploration, discovery, challenges, exotic locations, bold action",
            "hooks": "a map to somewhere forgotten, news of something valuable, a call to action",
            "voice": "exciting and propulsive, full of momentum and possibility",
        },
        "drama": {
            "elements": "complex relationships, moral dilemmas, personal stakes, family secrets",
            "hooks": "a choice with no good answer, news that changes everything, a past catching up",
            "voice": "emotionally resonant, focused on human complexity and growth",
        },
    }
    return guidance.get(genre, guidance["fantasy"])


def _get_style_instructions(style: str) -> str:
    """Get storytelling instructions based on user's preferred style."""
    styles = {
        "guided": """
Provide clear narrative direction with vivid description. Help the reader feel
oriented in the world. End scenes at natural pause points, letting the reader
decide what to do next. NEVER suggest specific choices or ask questions.""",
        "freeform": """
Create a rich sandbox. Describe the environment with enough detail to spark
curiosity. Let the reader discover what catches their interest. End naturally
without prompting. NEVER suggest specific choices or ask questions.""",
        "collaborative": """
Build the story together through natural narrative flow. Describe the world
vividly and let moments breathe. End at natural pause points, trusting the
reader to respond. NEVER suggest specific choices or ask direct questions.""",
    }
    return styles.get(style, styles["guided"])


async def _generate_opening(session: Dict[str, Any], model) -> str:
    """Generate an opening that matches the user's genre, tone, and style."""
    logger.info(f"[OPENING] Starting _generate_opening for session {session.get('session_id', 'unknown')}")

    answers = session.get("session_0_answers", {})
    genre = session.get("genre", "fantasy")
    tone = session.get("tone_preference", answers.get("tone", "dramatic"))
    style = session.get("storytelling_style", "guided")
    setting = session.get("setting_preference", answers.get("setting", ""))
    character = session.get("character_concept", answers.get("character", ""))

    logger.info(f"[OPENING] genre={genre}, tone={tone}, style={style}")

    genre_info = _get_genre_guidance(genre)
    style_instructions = _get_style_instructions(style)

    prompt = f"""You are a master storyteller, welcoming someone into their personal mythology.

GENRE: {genre.upper()}
Genre elements to weave in: {genre_info['elements']}
Narrative voice: {genre_info['voice']}

TONE: {tone}
STORYTELLING STYLE: {style}
{style_instructions}

SETTING: {setting if setting else f"Create an evocative {genre} setting that immediately draws the reader in"}
CHARACTER: {character if character else "Introduce them gently - let them discover who they are through the scene"}

Write an opening that:
1. Begins IN THE MOMENT - no preamble, drop them right into a scene
2. Engages the senses - what do they see, hear, feel?
3. Creates immediate intrigue using: {genre_info['hooks']}
4. Makes them feel like they belong in this world
5. Ends at a natural pause - DO NOT suggest choices or ask questions

Length: 2-3 paragraphs. Write ONLY the narrative, no meta-commentary.
Make it feel personal - this is THEIR story beginning.
IMPORTANT: End the scene naturally. Do NOT list options, ask what they want to do, or suggest choices."""

    logger.info(f"[OPENING] Calling protected_ai_call with prompt of {len(prompt)} chars")

    # Use protected AI call with guardrails
    return await protected_ai_call(
        model,
        prompt,
        session_id=session.get("session_id", "unknown"),
        temperature=0.85,
        max_output_tokens=600,
    )


async def _handle_active_play(
    session: Dict[str, Any],
    player_input: str,
    model,
    db: Optional[Neo4jDatabase],
) -> str:
    """Handle active gameplay with genre-aware storytelling."""
    answers = session.get("session_0_answers", {})
    genre = session.get("genre", "fantasy")
    tone = session.get("tone_preference", answers.get("tone", "dramatic"))
    style = session.get("storytelling_style", "guided")
    setting = session.get("setting_preference", answers.get("setting", ""))
    character = session.get("character_concept", answers.get("character", ""))

    history = session.get("history", [])[-10:]  # Last 10 exchanges

    genre_info = _get_genre_guidance(genre)
    style_instructions = _get_style_instructions(style)

    # Format history for context
    history_text = "\n".join([
        f"{'Player' if h['role'] == 'user' else 'Narrator'}: {h['content'][:300]}"
        for h in history[:-1]  # Exclude current action
    ])

    # Query for relevant lore (if database available)
    lore_context = ""
    if db:
        try:
            results = await db.execute("""
                MATCH (e:Entity)
                WHERE e.world_id = $world_id OR e.world_id IS NULL
                RETURN e.name as name, e.description as description, e.entity_type as type
                LIMIT 5
            """, {"world_id": session.get("world_id", "")})

            if results:
                lore_context = "\n".join([
                    f"- {r['name']} ({r['type']}): {r['description'][:150]}"
                    for r in results if r.get('description')
                ])
        except Exception:
            pass

    prompt = f"""You are a master storyteller continuing someone's personal mythology.

GENRE: {genre.upper()}
Genre elements: {genre_info['elements']}
Narrative voice: {genre_info['voice']}

TONE: {tone}
STORYTELLING STYLE: {style}
{style_instructions}

SETTING: {setting if setting else 'an evocative world'}
PROTAGONIST: {character if character else 'the protagonist'}

STORY SO FAR:
{history_text if history_text else 'The story is just beginning.'}

WORLD KNOWLEDGE:
{lore_context if lore_context else 'Let the world reveal itself naturally.'}

PLAYER'S ACTION: {player_input}

Continue the narrative:
- React naturally to what the player did or said
- Use sensory details that fit the {genre} genre
- Maintain the {tone} tone throughout
- Never speak for the player or assume their thoughts
- If they're exploring, reward their curiosity with interesting details
- If they're taking action, show meaningful consequences
- Keep response 2-3 short paragraphs
- End at a natural pause point

IMPORTANT: Do NOT suggest choices, list options, or ask what they want to do.
Just describe what happens and let the scene breathe. Trust the reader to respond.

Write ONLY the narrative:"""

    # Use protected AI call with guardrails
    return await protected_ai_call(
        model,
        prompt,
        session_id=session.get("session_id", "unknown"),
        temperature=0.85,
        max_output_tokens=500,
    )


# ============================================================
# LORE BASES (Pre-made worlds)
# ============================================================

# Directory for lore base JSON files
LORE_BASES_DIR = Path(__file__).parent.parent.parent.parent / "data" / "lore_bases"


def _load_lore_bases_from_files() -> Dict[str, Dict[str, Any]]:
    """
    Load all lore bases from JSON files in data/lore_bases/.

    Each JSON file should contain:
    - id: unique identifier
    - name: display name
    - description: brief description for UI
    - genre_hints: list of genres
    - tone_hints: list of tone descriptors
    - seed_prompt: prompt used for AI generation
    - lore_content: full text to ingest for entities/NPCs (optional)
    """
    bases = {}

    if not LORE_BASES_DIR.exists():
        logger.warning(f"Lore bases directory not found: {LORE_BASES_DIR}")
        return bases

    for json_file in LORE_BASES_DIR.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            lore_id = data.get("id", json_file.stem)
            bases[lore_id] = {
                "id": lore_id,
                "name": data.get("name", lore_id.replace("_", " ").title()),
                "description": data.get("description", ""),
                "genre_hints": data.get("genre_hints", []),
                "tone_hints": data.get("tone_hints", []),
                "entities_count": 0,  # Updated after ingestion
                "seed_prompt": data.get("seed_prompt", ""),
                "lore_content": data.get("lore_content", ""),  # Full text for NPC/entity extraction
                "ingested": False,  # Track if lore has been processed
            }
            logger.info(f"Loaded lore base from file: {lore_id}")
        except Exception as e:
            logger.error(f"Failed to load lore base {json_file}: {e}")

    return bases


# Load from files, then add built-in defaults
_file_lore_bases = _load_lore_bases_from_files()

# Built-in lore bases (can be overridden by files)
LORE_BASES = {
    "shattered_kingdoms": {
        "id": "shattered_kingdoms",
        "name": "The Shattered Kingdoms",
        "description": "A realm fractured by an ancient war between divine forces. Noble houses vie for power while darker forces stir in the shadows.",
        "genre_hints": ["fantasy", "drama", "mystery"],
        "tone_hints": ["epic", "dark", "dramatic"],
        "entities_count": 0,
        "seed_prompt": "The Shattered Kingdoms - a fractured realm where noble houses compete for power amid ancient ruins and forgotten magic",
        "lore_content": "",
        "ingested": False,
    },
    "thornwood": {
        "id": "thornwood",
        "name": "Thornwood Chronicles",
        "description": "A mystical forest where fey courts hold sway. Ancient pacts, forbidden love, and the boundaries between worlds grow thin.",
        "genre_hints": ["fantasy", "romance", "horror"],
        "tone_hints": ["intimate", "whimsical", "dark"],
        "entities_count": 0,
        "seed_prompt": "Thornwood - a mystical forest where fey courts hold ancient pacts and the veil between worlds is thin",
        "lore_content": "",
        "ingested": False,
    },
    "empty": {
        "id": "empty",
        "name": "Fresh Canvas",
        "description": "Begin with nothing. Let the world emerge from your story.",
        "genre_hints": [],
        "tone_hints": [],
        "entities_count": 0,
        "seed_prompt": "",
        "lore_content": "",
        "ingested": True,  # Empty is always "ingested"
    },
}

# Merge file-loaded lore bases (they take precedence over built-ins)
LORE_BASES.update(_file_lore_bases)


class LoreBaseResponse(BaseModel):
    """Response for lore base information."""
    id: str
    name: str
    description: str
    genre_hints: List[str]
    tone_hints: List[str]
    entities_count: int
    seed_prompt: str


@router.get("/lore-bases", response_model=List[LoreBaseResponse])
async def list_lore_bases():
    """List all available pre-made lore bases."""
    return [LoreBaseResponse(**base) for base in LORE_BASES.values()]


@router.get("/lore-bases/{lore_id}", response_model=LoreBaseResponse)
async def get_lore_base(lore_id: str):
    """Get details of a specific lore base."""
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )
    return LoreBaseResponse(**LORE_BASES[lore_id])


class LoreBaseIngestResponse(BaseModel):
    """Response after ingesting a lore base."""
    lore_id: str
    entities_created: int
    relationships_created: int
    npcs_with_ocean: int
    message: str


@router.post("/lore-bases/{lore_id}/ingest", response_model=LoreBaseIngestResponse)
async def ingest_lore_base(
    lore_id: str,
    request: Request,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Ingest a lore base's content into the database.

    This processes the lore_content field through the smart ingestor pipeline:
    - Extracts entities (Characters, Locations, Factions, Items, etc.)
    - Generates OCEAN personality profiles for NPCs
    - Creates relationships between entities
    - Stores everything in Neo4j for the DM to use

    Call this once when setting up a new campaign with a lore base.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    lore_base = LORE_BASES[lore_id]

    # Check if already ingested
    if lore_base.get("ingested", False):
        return LoreBaseIngestResponse(
            lore_id=lore_id,
            entities_created=lore_base.get("entities_count", 0),
            relationships_created=0,
            npcs_with_ocean=0,
            message=f"Lore base '{lore_id}' was already ingested"
        )

    lore_content = lore_base.get("lore_content", "")
    if not lore_content or len(lore_content.strip()) < 50:
        # No substantial lore content to process
        LORE_BASES[lore_id]["ingested"] = True
        return LoreBaseIngestResponse(
            lore_id=lore_id,
            entities_created=0,
            relationships_created=0,
            npcs_with_ocean=0,
            message=f"Lore base '{lore_id}' has no lore content to ingest (use seed_prompt for generation instead)"
        )

    # Use the LoreParsingAgent for AI-powered extraction with OCEAN profiles
    try:
        from src.lms.agents.lore_parsing_agent import LoreParsingAgent

        agent = LoreParsingAgent()
        logger.info(f"Starting AI lore parsing for lore base: {lore_id}")

        result = await agent.parse_and_store(
            text=lore_content,
            db=db,
            source_name=f"lore_base:{lore_id}",
        )

        # Update lore base status
        LORE_BASES[lore_id]["ingested"] = True
        LORE_BASES[lore_id]["entities_count"] = result.entities_stored

        logger.info(
            f"Ingested lore base {lore_id}: {result.entities_stored} entities, "
            f"{result.relationships_stored} relationships, "
            f"{result.characters_with_ocean} with OCEAN profiles"
        )

        return LoreBaseIngestResponse(
            lore_id=lore_id,
            entities_created=result.entities_stored,
            relationships_created=result.relationships_stored,
            npcs_with_ocean=result.characters_with_ocean,
            message=f"Successfully ingested lore base '{lore_base['name']}' with AI parsing"
        )

    except Exception as e:
        logger.error(f"Failed to ingest lore base {lore_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest lore base: {str(e)}"
        )


class LoreBaseUploadRequest(BaseModel):
    """Request to create a new lore base."""
    id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=10, max_length=500)
    genre_hints: List[str] = Field(default_factory=list)
    tone_hints: List[str] = Field(default_factory=list)
    seed_prompt: str = Field(default="")
    lore_content: str = Field(default="", description="Full lore text for entity extraction")


@router.post("/lore-bases", response_model=LoreBaseResponse)
async def create_lore_base(lore_base: LoreBaseUploadRequest):
    """
    Create a new lore base from JSON data.

    The lore_content field should contain narrative text describing:
    - Characters and their personalities/traits
    - Locations and their atmosphere
    - Factions and their relationships
    - Items and artifacts
    - Events and history

    Example lore_content for NPCs with OCEAN profiles:
    "Lord Aldric is a calculating and ambitious noble, known for his cold demeanor
    and strategic mind. He commands absolute loyalty from his guards yet shows
    surprising kindness to the common folk. His rival, Lady Seraphina, is warm and
    charismatic but hides a vengeful streak beneath her charming exterior..."

    After creation, call POST /game/lore-bases/{id}/ingest to process
    the content and create entities with OCEAN profiles.
    """
    if lore_base.id in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lore base '{lore_base.id}' already exists"
        )

    new_base = {
        "id": lore_base.id,
        "name": lore_base.name,
        "description": lore_base.description,
        "genre_hints": lore_base.genre_hints,
        "tone_hints": lore_base.tone_hints,
        "entities_count": 0,
        "seed_prompt": lore_base.seed_prompt,
        "lore_content": lore_base.lore_content,
        "ingested": False,
    }

    # Save to file for persistence
    LORE_BASES_DIR.mkdir(parents=True, exist_ok=True)
    file_path = LORE_BASES_DIR / f"{lore_base.id}.json"

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(new_base, f, indent=2)
        logger.info(f"Created lore base file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save lore base file: {e}")
        # Continue even if file save fails - keep in memory

    LORE_BASES[lore_base.id] = new_base

    return LoreBaseResponse(**new_base)


@router.post("/lore-bases/upload")
async def upload_lore_base_file(file: UploadFile = File(...)):
    """
    Upload a lore base JSON file.

    The file should be a JSON file with the structure:
    {
        "id": "my_world",
        "name": "My World Name",
        "description": "A brief description",
        "genre_hints": ["fantasy"],
        "tone_hints": ["epic"],
        "seed_prompt": "Seed prompt for AI",
        "lore_content": "Full narrative text with NPCs, locations, etc..."
    }
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .json file"
        )

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {str(e)}"
        )

    lore_id = data.get("id", file.filename.replace(".json", ""))

    if lore_id in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lore base '{lore_id}' already exists"
        )

    new_base = {
        "id": lore_id,
        "name": data.get("name", lore_id.replace("_", " ").title()),
        "description": data.get("description", ""),
        "genre_hints": data.get("genre_hints", []),
        "tone_hints": data.get("tone_hints", []),
        "entities_count": 0,
        "seed_prompt": data.get("seed_prompt", ""),
        "lore_content": data.get("lore_content", ""),
        "ingested": False,
    }

    # Save to file
    LORE_BASES_DIR.mkdir(parents=True, exist_ok=True)
    file_path = LORE_BASES_DIR / f"{lore_id}.json"

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(new_base, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save uploaded lore base: {e}")

    LORE_BASES[lore_id] = new_base

    return {
        "message": f"Lore base '{lore_id}' uploaded successfully",
        "lore_id": lore_id,
        "name": new_base["name"],
        "has_lore_content": bool(new_base["lore_content"]),
        "next_step": f"Call POST /api/game/lore-bases/{lore_id}/ingest to process entities"
    }


# ============================================================
# SESSION LISTING
# ============================================================

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all active sessions."""
    return [
        SessionResponse(
            session_id=sid,
            status=data["status"],
            phase=data["phase"],
            created_at=data["created_at"],
        )
        for sid, data in _active_sessions.items()
    ]


# ============================================================
# SAVE/LOAD SYSTEM (5 slots)
# ============================================================

# In-memory save slots (replace with persistent storage for production)
_save_slots: Dict[int, Dict[str, Any]] = {}
MAX_SAVE_SLOTS = 5


class SaveSlotInfo(BaseModel):
    """Information about a save slot."""
    slot: int
    is_empty: bool
    session_name: Optional[str] = None
    character_concept: Optional[str] = None
    genre: Optional[str] = None
    phase: Optional[str] = None
    turn_count: Optional[int] = None
    saved_at: Optional[datetime] = None


class SaveGameRequest(BaseModel):
    """Request to save a game to a slot."""
    slot: int = Field(..., ge=1, le=MAX_SAVE_SLOTS)
    session_name: Optional[str] = Field(default=None, max_length=50)


class SaveGameResponse(BaseModel):
    """Response after saving a game."""
    success: bool
    slot: int
    session_id: str
    message: str


class LoadGameResponse(BaseModel):
    """Response after loading a game."""
    success: bool
    session_id: str
    phase: str
    narrative: str
    message: str


@router.get("/saves", response_model=List[SaveSlotInfo])
async def list_save_slots():
    """List all save slots and their contents."""
    slots = []
    for slot_num in range(1, MAX_SAVE_SLOTS + 1):
        if slot_num in _save_slots:
            save_data = _save_slots[slot_num]
            slots.append(SaveSlotInfo(
                slot=slot_num,
                is_empty=False,
                session_name=save_data.get("session_name", f"Save {slot_num}"),
                character_concept=save_data.get("character_concept"),
                genre=save_data.get("genre"),
                phase=save_data.get("phase"),
                turn_count=len(save_data.get("history", [])) // 2,
                saved_at=save_data.get("saved_at"),
            ))
        else:
            slots.append(SaveSlotInfo(
                slot=slot_num,
                is_empty=True,
            ))
    return slots


@router.post("/saves/{slot}", response_model=SaveGameResponse)
async def save_game(
    slot: int,
    session_id: str,
    save_req: SaveGameRequest,
):
    """
    Save a game session to a slot.

    Saves all session state including history, preferences, and phase.
    """
    if slot < 1 or slot > MAX_SAVE_SLOTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVE_SLOTS}"
        )

    if session_id not in _active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    session = _active_sessions[session_id]

    # Create save data
    save_data = {
        "session_id": session_id,
        "session_name": save_req.session_name or f"Save {slot}",
        "character_concept": session.get("character_concept"),
        "genre": session.get("genre"),
        "tone_preference": session.get("tone_preference"),
        "setting_preference": session.get("setting_preference"),
        "storytelling_style": session.get("storytelling_style"),
        "phase": session.get("phase"),
        "history": session.get("history", []),
        "session_0_answers": session.get("session_0_answers", {}),
        "world_id": session.get("world_id"),
        "saved_at": datetime.now(timezone.utc),
        "created_at": session.get("created_at"),
    }

    _save_slots[slot] = save_data

    logger.info(f"Saved session {session_id} to slot {slot}")

    return SaveGameResponse(
        success=True,
        slot=slot,
        session_id=session_id,
        message=f"Game saved to slot {slot}"
    )


@router.get("/saves/{slot}/load", response_model=LoadGameResponse)
async def load_game(slot: int):
    """
    Load a game from a save slot.

    Restores the session and returns the last narrative.
    """
    if slot < 1 or slot > MAX_SAVE_SLOTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVE_SLOTS}"
        )

    if slot not in _save_slots:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No save found in slot {slot}"
        )

    save_data = _save_slots[slot]

    # Create a new session ID for the loaded game
    new_session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Restore session data
    session_data = {
        "session_id": new_session_id,
        "world_id": save_data.get("world_id"),
        "character_concept": save_data.get("character_concept"),
        "setting_preference": save_data.get("setting_preference"),
        "tone_preference": save_data.get("tone_preference"),
        "genre": save_data.get("genre", "fantasy"),
        "storytelling_style": save_data.get("storytelling_style", "guided"),
        "phase": save_data.get("phase", "active_play"),
        "status": "active",
        "created_at": now,
        "history": save_data.get("history", []),
        "session_0_answers": save_data.get("session_0_answers", {}),
    }

    _active_sessions[new_session_id] = session_data

    # Get the last narrative to show the player where they left off
    history = save_data.get("history", [])
    last_narrative = "Your adventure continues..."
    for entry in reversed(history):
        if entry.get("role") == "assistant":
            last_narrative = entry.get("content", last_narrative)
            break

    logger.info(f"Loaded save from slot {slot} as new session {new_session_id}")

    return LoadGameResponse(
        success=True,
        session_id=new_session_id,
        phase=session_data["phase"],
        narrative=last_narrative,
        message=f"Game loaded from slot {slot}"
    )


@router.delete("/saves/{slot}")
async def delete_save(slot: int):
    """Delete a save from a slot."""
    if slot < 1 or slot > MAX_SAVE_SLOTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVE_SLOTS}"
        )

    if slot not in _save_slots:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No save found in slot {slot}"
        )

    del _save_slots[slot]

    return {"success": True, "message": f"Save slot {slot} cleared"}
