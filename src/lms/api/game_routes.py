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

from fastapi import APIRouter, HTTPException, Request, status, Depends, File, UploadFile, Query
from pydantic import BaseModel, Field

from src.lms.db.neo4j_adapter import Neo4jDatabase
from src.lms.api.dependencies import get_neo4j_db
from src.lms.agents.query_agent import QueryAgent
from src.lms.agents.auditor_agent import AuditorAgent
from src.lms.agents.lore_parsing_agent import LoreParsingAgent
from src.lms.guardrails.token_budget import TokenTracker, BudgetExceeded, RateLimitExceeded, estimate_tokens
from src.lms.guardrails.circuit_breaker import get_circuit_breaker, CircuitOpen

# D&D Rules Integration
from src.lms.api.dnd_routes import _characters, CharacterSheet
from src.lms.dnd5e.engine.checks import CheckEngine, SKILL_TO_ABILITY
from src.lms.dnd5e.engine.combat_resolver import CombatResolver
from src.lms.dnd5e.presentation.visibility import VisibilityFilter
from src.lms.dnd5e.creation.modes import RulesVisibility

# World Integrity Check
from src.airpg.runtime.world_integrity import (
    WorldNotReadyError,
    require_valid_world,
    validate_world_before_session,
)

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
    world_id: Optional[str] = None,
) -> None:
    """
    Extract entities from gameplay narrative and store them in Neo4j.

    This runs asynchronously after the narrative is returned to the player,
    so it doesn't slow down the gameplay experience.

    Args:
        narrative: The narrative text to extract entities from
        session_id: The session ID for source tracking
        db: Neo4j database instance
        world_id: The world/lore base ID to associate entities with
    """
    if not db:
        logger.debug("No database available for lore extraction")
        return

    if len(narrative) < 100:
        # Too short to contain meaningful entities
        return

    try:
        parser = get_lore_parser()

        # Parse the narrative for entities, associating with the session's world
        result = await parser.parse_and_store(
            text=narrative,
            db=db,
            source_name=f"session:{session_id}",
            world_id=world_id,
        )

        if result.entities_stored > 0:
            logger.info(
                f"[LORE] Extracted {result.entities_stored} entities from session {session_id} "
                f"(world: {world_id or 'none'}, {result.characters_with_ocean} with OCEAN profiles)"
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
# INVITE CODE SYSTEM (for controlled alpha testing)
# ============================================================

# Path to invite codes configuration
INVITE_CODES_FILE = Path(__file__).parent.parent.parent.parent / "data" / "invite_codes.json"

# In-memory cache of invite codes (loaded from file)
_invite_codes_cache: Optional[Dict[str, Any]] = None


def _load_invite_codes() -> Dict[str, Any]:
    """Load invite codes from file."""
    global _invite_codes_cache
    if _invite_codes_cache is None:
        try:
            if INVITE_CODES_FILE.exists():
                with open(INVITE_CODES_FILE, "r", encoding="utf-8") as f:
                    _invite_codes_cache = json.load(f)
            else:
                _invite_codes_cache = {"max_testers": 20, "codes": []}
        except Exception as e:
            logger.error(f"Failed to load invite codes: {e}")
            _invite_codes_cache = {"max_testers": 20, "codes": []}
    return _invite_codes_cache


def _save_invite_codes() -> None:
    """Save invite codes to file."""
    if _invite_codes_cache:
        try:
            INVITE_CODES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(INVITE_CODES_FILE, "w", encoding="utf-8") as f:
                json.dump(_invite_codes_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save invite codes: {e}")


class InviteCodeRequest(BaseModel):
    """Request to validate an invite code."""
    code: str = Field(..., min_length=5, max_length=50, description="The invite code to validate")


class InviteCodeResponse(BaseModel):
    """Response from invite code validation."""
    valid: bool
    message: str
    tester_name: Optional[str] = None
    testers_remaining: Optional[int] = None


@router.post("/invite/validate", response_model=InviteCodeResponse)
async def validate_invite_code(request: InviteCodeRequest):
    """
    Validate an invite code for alpha testing access.

    Returns success if the code is valid and not yet at max capacity.
    Codes are single-use per tester slot.
    """
    codes_data = _load_invite_codes()
    max_testers = codes_data.get("max_testers", 20)
    codes = codes_data.get("codes", [])

    # Count active testers
    active_count = sum(1 for c in codes if c.get("activated", False))

    # Check if at capacity
    if active_count >= max_testers:
        return InviteCodeResponse(
            valid=False,
            message="Sorry, we've reached capacity for alpha testers. Please check back later!",
            testers_remaining=0
        )

    # Find the code
    code_upper = request.code.strip().upper()
    for code_entry in codes:
        if code_entry.get("code", "").upper() == code_upper:
            if code_entry.get("activated", False):
                # Already activated - still valid (same tester returning)
                return InviteCodeResponse(
                    valid=True,
                    message=f"Welcome back, {code_entry.get('name', 'Tester')}!",
                    tester_name=code_entry.get("name"),
                    testers_remaining=max_testers - active_count
                )
            else:
                # Activate the code
                code_entry["activated"] = True
                code_entry["activated_at"] = datetime.now(timezone.utc).isoformat()
                _save_invite_codes()

                logger.info(f"Invite code activated: {code_entry.get('name', 'unknown')}")

                return InviteCodeResponse(
                    valid=True,
                    message=f"Welcome to the alpha test, {code_entry.get('name', 'Tester')}!",
                    tester_name=code_entry.get("name"),
                    testers_remaining=max_testers - active_count - 1
                )

    # Code not found
    return InviteCodeResponse(
        valid=False,
        message="Invalid invite code. Please check your code and try again.",
        testers_remaining=max_testers - active_count
    )


@router.get("/invite/status")
async def get_invite_status():
    """
    Get current alpha testing status.

    Returns capacity information for display.
    """
    codes_data = _load_invite_codes()
    max_testers = codes_data.get("max_testers", 20)
    codes = codes_data.get("codes", [])

    active_count = sum(1 for c in codes if c.get("activated", False))

    return {
        "accepting_testers": active_count < max_testers,
        "testers_active": active_count,
        "testers_max": max_testers,
        "testers_remaining": max_testers - active_count
    }


# ============================================================
# ANALYTICS DASHBOARD
# ============================================================

def _load_session_logs() -> List[Dict[str, Any]]:
    """Load session logs from file."""
    try:
        log_file = Path(__file__).parent.parent.parent.parent / "data" / "session_logs.json"
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Failed to load session logs: {e}")
        return []


@router.get("/analytics")
async def get_analytics():
    """
    Get comprehensive analytics for the admin dashboard.
    Shows tester engagement, session activity, and usage patterns.
    """
    # Load invite codes
    codes_data = _load_invite_codes()
    codes = codes_data.get("codes", [])

    # Load session logs
    session_logs = _load_session_logs()

    # === TESTER ANALYTICS ===
    activated_testers = [c for c in codes if c.get("activated", False)]
    testers = []
    for tester in activated_testers:
        tester_name = tester.get("name", "Unknown")
        tester_code = tester.get("code", "")
        activated_at = tester.get("activated_at")

        # Find this tester's sessions
        tester_sessions = [log for log in session_logs if log.get("tester") == tester_name]
        tester_actions = [log for log in tester_sessions if log.get("event_type") == "player_action"]

        # Get unique session IDs
        unique_sessions = set(log.get("session_id") for log in tester_sessions if log.get("session_id"))

        # Find last activity
        last_activity = None
        if tester_sessions:
            timestamps = [log.get("received_at") or log.get("timestamp") for log in tester_sessions]
            timestamps = [t for t in timestamps if t]
            if timestamps:
                last_activity = max(timestamps)

        testers.append({
            "name": tester_name,
            "code": tester_code,
            "activated_at": activated_at,
            "last_activity": last_activity,
            "total_sessions": len(unique_sessions),
            "total_actions": len(tester_actions),
        })

    # Sort by last activity (most recent first)
    testers.sort(key=lambda x: x.get("last_activity") or "", reverse=True)

    # === SESSION ANALYTICS ===
    all_sessions = {}
    for log in session_logs:
        sid = log.get("session_id")
        if not sid:
            continue
        if sid not in all_sessions:
            all_sessions[sid] = {
                "session_id": sid,
                "tester": log.get("tester"),
                "events": [],
                "started_at": None,
                "last_event": None,
            }
        all_sessions[sid]["events"].append(log)

        timestamp = log.get("received_at") or log.get("timestamp")
        if timestamp:
            if not all_sessions[sid]["started_at"] or timestamp < all_sessions[sid]["started_at"]:
                all_sessions[sid]["started_at"] = timestamp
            if not all_sessions[sid]["last_event"] or timestamp > all_sessions[sid]["last_event"]:
                all_sessions[sid]["last_event"] = timestamp

    # Calculate session stats
    sessions_list = []
    for sid, session in all_sessions.items():
        events = session["events"]
        action_count = sum(1 for e in events if e.get("event_type") == "player_action")
        screen_views = [e for e in events if e.get("event_type") == "screen_view"]

        sessions_list.append({
            "session_id": sid[:8] + "...",
            "tester": session["tester"],
            "started_at": session["started_at"],
            "last_event": session["last_event"],
            "event_count": len(events),
            "action_count": action_count,
            "screens_visited": len(set(e.get("data", {}).get("screen") for e in screen_views if e.get("data"))),
        })

    # Sort by start time (most recent first)
    sessions_list.sort(key=lambda x: x.get("started_at") or "", reverse=True)

    # === AGGREGATE STATS ===
    total_actions = sum(1 for log in session_logs if log.get("event_type") == "player_action")
    total_sessions = len(all_sessions)

    # Event type breakdown
    event_types = {}
    for log in session_logs:
        evt = log.get("event_type", "unknown")
        event_types[evt] = event_types.get(evt, 0) + 1

    # Activity by date (last 7 days)
    from collections import defaultdict
    activity_by_date = defaultdict(int)
    for log in session_logs:
        timestamp = log.get("received_at") or log.get("timestamp")
        if timestamp:
            try:
                date = timestamp[:10]  # YYYY-MM-DD
                activity_by_date[date] += 1
            except:
                pass

    return {
        "summary": {
            "testers_activated": len(activated_testers),
            "testers_max": codes_data.get("max_testers", 30),
            "total_sessions": total_sessions,
            "total_events": len(session_logs),
            "total_actions": total_actions,
        },
        "testers": testers[:20],  # Top 20 most recent
        "recent_sessions": sessions_list[:15],  # Last 15 sessions
        "event_breakdown": event_types,
        "activity_by_date": dict(sorted(activity_by_date.items())[-7:]),  # Last 7 days
    }


# ============================================================
# FEEDBACK SYSTEM (for playtester feedback collection)
# ============================================================

FEEDBACK_FILE = Path(__file__).parent.parent.parent.parent / "data" / "feedback.json"


def _load_feedback() -> List[Dict[str, Any]]:
    """Load feedback from file."""
    try:
        if FEEDBACK_FILE.exists():
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Failed to load feedback: {e}")
        return []


def _save_feedback(feedback_list: List[Dict[str, Any]]) -> None:
    """Save feedback to file."""
    try:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(feedback_list, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")


class FeedbackRequest(BaseModel):
    """Feedback submission from playtesters."""
    category: Optional[str] = Field(None, description="Feedback category: confused, frustrated, delighted, bug, idea, other")
    text: Optional[str] = Field(None, max_length=5000, description="Detailed feedback text")
    context: Optional[Dict[str, Any]] = Field(None, description="Context about what was happening")


class FeedbackResponse(BaseModel):
    """Response from feedback submission."""
    success: bool
    message: str
    feedback_id: str


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """
    Submit feedback from a playtester.

    Stores feedback with context for later review.
    """
    if not request.category and not request.text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a category or feedback text"
        )

    feedback_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()

    feedback_entry = {
        "id": feedback_id,
        "timestamp": timestamp,
        "category": request.category,
        "text": request.text,
        "context": request.context or {}
    }

    # Load existing feedback, append new entry, save
    feedback_list = _load_feedback()
    feedback_list.append(feedback_entry)
    _save_feedback(feedback_list)

    # Log for visibility
    tester = request.context.get("tester", "anonymous") if request.context else "anonymous"
    logger.info(f"Feedback received from {tester}: [{request.category}] {(request.text or '')[:100]}")

    return FeedbackResponse(
        success=True,
        message="Thank you for your feedback!",
        feedback_id=feedback_id
    )


@router.get("/feedback")
async def get_all_feedback():
    """
    Get all submitted feedback (for admin review).

    Returns list of all feedback entries.
    """
    feedback_list = _load_feedback()
    return {
        "count": len(feedback_list),
        "feedback": feedback_list
    }


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
    genres: Optional[List[str]] = Field(
        default=None,
        description="Multiple genres for blending (e.g., ['romance', 'mystery'])"
    )
    storytelling_style: Optional[str] = Field(
        default="guided",
        description="How structured: guided, freeform, or collaborative"
    )
    # D&D Rules Integration
    character_id: Optional[str] = Field(
        default=None,
        description="D&D character ID for rules-based play"
    )
    rules_mode: Optional[str] = Field(
        default="narrative",
        description="'narrative' for story-only, 'dnd' for d20 rules"
    )
    rules_visibility: Optional[str] = Field(
        default="guided",
        description="How much mechanical info to show: storyteller, guided, classic, tactician"
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
    action: str = Field(..., min_length=1, max_length=2000, description="What the player does or says")
    needs_guidance: bool = Field(default=False, description="Whether player needs subtle story direction hints")
    adaptive_context: Optional[str] = Field(default=None, description="AI adaptation hints based on learned player preferences")


class GameEventData(BaseModel):
    """Structured game event for frontend notifications."""
    type: str  # ITEM_ADDED, DAMAGE_TAKEN, SKILL_CHECK, etc.
    data: Dict[str, Any] = {}
    turn: int = 0


class DMResponse(BaseModel):
    """DM response to player action."""
    narrative: str
    session_id: str
    phase: str
    arc_context: Optional[Dict[str, Any]] = None
    suggested_actions: Optional[List[str]] = None
    episode_status: Optional[Dict[str, Any]] = None
    # D&D Rules Integration
    mechanical_result: Optional[Dict[str, Any]] = None  # Roll results, damage, etc.
    character_update: Optional[Dict[str, Any]] = None  # HP changes, conditions, etc.
    # Structured Events for frontend notifications
    events: Optional[List[GameEventData]] = None  # ITEM_ADDED, GOLD_CHANGED, etc.
    # Session state flags
    session_ended: bool = False  # True when ONE_SHOT reaches THE END


# ============================================================
# SESSION STORE (in-memory + Neo4j persistence for continuity)
# ============================================================

_active_sessions: Dict[str, Dict[str, Any]] = {}


async def _persist_session_to_db(session_id: str, session: Dict[str, Any], db) -> bool:
    """
    Persist active session to Neo4j for continuity across server restarts.

    Stores the full session state as JSON so it can be recovered.
    """
    if not db:
        return False

    try:
        # Convert datetime to ISO string for JSON serialization
        created_at = session.get("created_at")
        if hasattr(created_at, 'isoformat'):
            created_at_str = created_at.isoformat()
        else:
            created_at_str = str(created_at) if created_at else None

        session_copy = {**session, "created_at": created_at_str}

        await db.execute("""
            MERGE (s:ActiveSession {session_id: $session_id})
            SET s.session_data = $session_json,
                s.updated_at = datetime(),
                s.phase = $phase,
                s.character_concept = $character_concept
        """, {
            "session_id": session_id,
            "session_json": json.dumps(session_copy),
            "phase": session.get("phase", "active_play"),
            "character_concept": session.get("character_concept", ""),
        })
        return True
    except Exception as e:
        logger.warning(f"Failed to persist session {session_id} to Neo4j: {e}")
        return False


async def _recover_session_from_db(session_id: str, db) -> Optional[Dict[str, Any]]:
    """
    Recover a session from Neo4j if it's not in memory.

    Returns the session dict if found, None otherwise.
    """
    if not db:
        return None

    try:
        results = await db.execute("""
            MATCH (s:ActiveSession {session_id: $session_id})
            RETURN s.session_data as session_json
        """, {"session_id": session_id})

        if not results:
            return None

        session_data = json.loads(results[0]["session_json"])

        # Convert ISO string back to datetime
        if session_data.get("created_at"):
            try:
                session_data["created_at"] = datetime.fromisoformat(session_data["created_at"])
            except (ValueError, TypeError):
                session_data["created_at"] = datetime.now(timezone.utc)

        logger.info(f"Recovered session {session_id} from Neo4j database")
        return session_data

    except Exception as e:
        logger.warning(f"Failed to recover session {session_id} from Neo4j: {e}")
        return None


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
# D&D RULES INTEGRATION
# ============================================================

# Action keywords for detecting mechanical intent
ATTACK_KEYWORDS = ["attack", "strike", "hit", "slash", "stab", "shoot", "punch", "kick", "swing at", "fire at"]
SKILL_KEYWORDS = {
    "stealth": ["sneak", "hide", "stealth", "creep", "silently", "quietly"],
    "perception": ["look", "search", "notice", "spot", "see", "watch", "observe", "listen"],
    "athletics": ["climb", "jump", "swim", "push", "pull", "lift", "run", "sprint"],
    "acrobatics": ["flip", "tumble", "balance", "dodge", "roll"],
    "persuasion": ["convince", "persuade", "charm", "negotiate", "talk", "reason with"],
    "deception": ["lie", "bluff", "deceive", "trick", "mislead"],
    "intimidation": ["threaten", "intimidate", "scare", "frighten", "menace"],
    "insight": ["read", "sense motive", "tell if", "detect lie", "understand intention"],
    "investigation": ["investigate", "examine", "analyze", "deduce", "figure out", "search for clues"],
    "arcana": ["identify magic", "recall arcane", "recognize spell"],
    "history": ["remember", "recall history", "know about"],
    "nature": ["identify plant", "track", "forage", "identify animal"],
    "medicine": ["heal", "stabilize", "diagnose", "treat wound"],
    "survival": ["track", "hunt", "find food", "navigate", "make camp"],
}


def detect_mechanical_action(action: str) -> Optional[Dict[str, Any]]:
    """
    Detect if player action requires mechanical resolution.

    Returns:
        Dict with action_type and details, or None if purely narrative
    """
    action_lower = action.lower()

    # Check for attack intent
    for keyword in ATTACK_KEYWORDS:
        if keyword in action_lower:
            return {
                "action_type": "attack",
                "keyword": keyword,
                "raw_action": action,
            }

    # Check for skill check intent
    for skill, keywords in SKILL_KEYWORDS.items():
        for keyword in keywords:
            if keyword in action_lower:
                return {
                    "action_type": "skill_check",
                    "skill": skill,
                    "keyword": keyword,
                    "raw_action": action,
                }

    return None


def resolve_mechanical_action(
    action_info: Dict[str, Any],
    character,
    visibility: RulesVisibility,
) -> Dict[str, Any]:
    """
    Resolve a mechanical action using the D&D 5e engine.

    Returns:
        Dict with roll result, narrative description, and any state changes
    """
    result = {
        "action_type": action_info["action_type"],
        "rolls": [],
        "narrative_hint": "",
        "character_update": None,
    }

    if action_info["action_type"] == "attack":
        # Resolve attack against default AC (will be refined with actual targets)
        target_ac = 13  # Default moderate difficulty
        attack = CombatResolver.resolve_attack(character, target_ac)
        filtered = VisibilityFilter.filter_attack_result(attack, visibility)

        result["rolls"].append({
            "type": "attack",
            "roll": attack.attack_roll,
            "modifier": attack.attack_modifier,
            "total": attack.attack_total,
            "is_hit": attack.is_hit,
            "is_critical": attack.is_critical,
            "display": filtered.get("display", ""),
        })

        if attack.is_hit and attack.damage_roll:
            result["rolls"].append({
                "type": "damage",
                "damage": attack.damage_total,
                "damage_type": attack.damage_type,
            })

        result["narrative_hint"] = filtered.get("description", attack.narrative_outcome)

    elif action_info["action_type"] == "skill_check":
        skill = action_info["skill"]
        dc = 15  # Default moderate difficulty

        check = CheckEngine.skill_check(character, skill, dc)
        filtered = VisibilityFilter.filter_check_result(check, visibility)

        result["rolls"].append({
            "type": "skill",
            "skill": skill,
            "roll": check.roll,
            "modifier": check.modifier,
            "total": check.total,
            "dc": dc,
            "success": check.success,
            "display": filtered.get("display", ""),
        })

        result["narrative_hint"] = filtered.get("description", check.narrative_outcome)

    return result


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
                world_id=world_id,
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

    Validates world integrity before starting active_play sessions.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Determine initial phase
    phase = "session_0" if not session_req.world_id else "active_play"

    # World Integrity Check: Validate world before active_play
    # For Session 0 (no world_id), we allow empty world since we're building it
    db = get_optional_neo4j_db(request)
    if session_req.world_id and db:
        try:
            # Validate that the world has required elements
            await require_valid_world(
                db,
                world_id=session_req.world_id,
                allow_empty=False,  # Existing worlds must be complete
            )
        except WorldNotReadyError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=e.to_dict(),
            )

    # Build genre blend string for storytelling
    genre_blend = session_req.genre or "fantasy"
    if session_req.genres and len(session_req.genres) > 1:
        genre_blend = " + ".join(session_req.genres)

    # Fetch lore_content from selected world (if any)
    world_lore_content = ""
    world_name = ""
    if session_req.world_id:
        # Use the global LORE_BASES dict (loaded at startup from seed files)
        if session_req.world_id in LORE_BASES:
            world_data = LORE_BASES[session_req.world_id]
            world_lore_content = world_data.get("lore_content", "")
            world_name = world_data.get("name", "")
            logger.info(f"Loaded lore_content for world '{session_req.world_id}': {len(world_lore_content)} chars")

    # Create a unique session-scoped world ID for entity isolation
    # This ensures each game has its own lore space, even if using the same base world
    base_world_id = session_req.world_id or "custom"
    session_world_id = f"{base_world_id}_{session_id[:8]}"

    session_data = {
        "session_id": session_id,
        "world_id": session_req.world_id,  # Original lore base ID (for loading seed lore)
        "session_world_id": session_world_id,  # Unique ID for this session's entities
        "world_name": world_name,
        "world_lore_content": world_lore_content,  # Store the full lore content!
        "character_concept": session_req.character_concept,
        "setting_preference": session_req.setting_preference,
        "tone_preference": session_req.tone_preference,
        "genre": session_req.genre or "fantasy",
        "genres": session_req.genres or [session_req.genre or "fantasy"],
        "genre_blend": genre_blend,
        "storytelling_style": session_req.storytelling_style or "guided",
        "phase": phase,
        "status": "active",
        "created_at": now,
        "history": [],
        "session_0_answers": {},
        # D&D Rules Integration
        "character_id": session_req.character_id,
        "rules_mode": session_req.rules_mode or "narrative",
        "rules_visibility": session_req.rules_visibility or "guided",
    }

    _active_sessions[session_id] = session_data

    # Store in Neo4j for persistence (if available)
    # This ensures story continuity even if server restarts
    db = get_optional_neo4j_db(request)
    if db:
        # Persist full session data for recovery
        await _persist_session_to_db(session_id, session_data, db)

        # Also create minimal GameSession node for querying
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
            logger.warning(f"Failed to create GameSession node: {e}")

    logger.info(f"Created session {session_id} in phase {phase}")

    return SessionResponse(
        session_id=session_id,
        status="active",
        phase=phase,
        created_at=now,
    )


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(request: Request, session_id: str):
    """Get session status and information. Recovers from database if needed."""
    session = _active_sessions.get(session_id)

    if not session:
        # Try to recover from database
        db = get_optional_neo4j_db(request)
        session = await _recover_session_from_db(session_id, db)

        if session:
            _active_sessions[session_id] = session
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

    return SessionResponse(
        session_id=session_id,
        status=session.get("status", "active"),
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
    Integrates D&D 5e rules when a character is present.

    Session Recovery: If session is not in memory (e.g., after server restart),
    attempts to recover from Neo4j database to maintain story continuity.
    """
    logger.info(f"Action request received for session {session_id}")

    # Get database connection first (needed for session recovery)
    db = get_optional_neo4j_db(request)

    # Try to get session from memory, or recover from database
    session = _active_sessions.get(session_id)

    if not session:
        # Session not in memory - try to recover from Neo4j
        logger.info(f"Session {session_id} not in memory, attempting recovery from database...")
        session = await _recover_session_from_db(session_id, db)

        if session:
            # Successfully recovered - restore to memory
            _active_sessions[session_id] = session
            logger.info(f"Session {session_id} recovered successfully - story continuity maintained")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found. Please start a new story or load a saved game."
            )

    model = get_gemini_model()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured"
        )

    logger.info(f"Processing action for session {session_id}: {action.action[:50]}...")

    # D&D Rules Integration - detect and resolve mechanical actions
    mechanical_result = None
    character_update = None
    mechanical_context = ""

    if session.get("rules_mode") == "dnd" and session.get("character_id"):
        character = _characters.get(session["character_id"])
        if character:
            # Detect mechanical action
            action_info = detect_mechanical_action(action.action)
            if action_info:
                try:
                    visibility = RulesVisibility(session.get("rules_visibility", "guided"))
                    mechanical_result = resolve_mechanical_action(action_info, character, visibility)

                    # Build context for AI narrative
                    if mechanical_result.get("rolls"):
                        roll = mechanical_result["rolls"][0]
                        if roll.get("type") == "attack":
                            if roll.get("is_hit"):
                                dmg = mechanical_result["rolls"][1]["damage"] if len(mechanical_result["rolls"]) > 1 else 0
                                mechanical_context = f"[MECHANICAL: Attack HIT for {dmg} damage. Incorporate this success into your narrative.]"
                            else:
                                mechanical_context = "[MECHANICAL: Attack MISSED. Describe the miss narratively.]"
                        elif roll.get("type") == "skill":
                            if roll.get("success"):
                                mechanical_context = f"[MECHANICAL: {roll['skill'].title()} check SUCCEEDED. The character accomplishes their goal.]"
                            else:
                                mechanical_context = f"[MECHANICAL: {roll['skill'].title()} check FAILED. Describe a complication or setback.]"

                    logger.info(f"Mechanical action resolved: {mechanical_result['action_type']}")
                except Exception as e:
                    logger.warning(f"Failed to resolve mechanical action: {e}")

    # Add action to history
    session["history"].append({"role": "user", "content": action.action})

    # Handle Session 0 (collaborative world-building)
    if session["phase"] == "session_0":
        response_text, new_phase = await _handle_session_0(
            session, action.action, model, db
        )
        session["phase"] = new_phase
    else:
        # Active play - generate DM response (with mechanical context if applicable)
        response_text = await _handle_active_play(
            session, action.action, model, db, mechanical_context,
            needs_guidance=action.needs_guidance,
            adaptive_context=action.adaptive_context
        )

    # Add response to history
    session["history"].append({"role": "assistant", "content": response_text})

    # Extract and store lore entities from the narrative (fire-and-forget)
    # Use session_world_id for isolation - each game gets its own entity space
    asyncio.create_task(
        extract_and_store_gameplay_lore(
            response_text,
            session_id,
            db,
            world_id=session.get("session_world_id"),  # Session-scoped, not shared!
        )
    )

    # Generate suggested actions for guided mode
    suggested_actions = _generate_suggested_actions(
        response_text,
        session.get("genre", "fantasy"),
        session.get("storytelling_style", "guided"),
    )

    # Extract structured events from narrative for frontend
    turn_count = len(session.get("history", [])) // 2
    events = _extract_events_from_narrative(response_text, mechanical_result, turn_count)

    # Detect session ending (THE END marker for ONE_SHOT mode)
    session_ended = "**THE END**" in response_text or "THE END" in response_text.upper()
    if session_ended:
        session["status"] = "ended"

    # Persist session to database for continuity across server restarts
    # This ensures the story is never lost
    asyncio.create_task(_persist_session_to_db(session_id, session, db))

    return DMResponse(
        narrative=response_text,
        session_id=session_id,
        phase=session["phase"],
        mechanical_result=mechanical_result,
        character_update=character_update,
        suggested_actions=suggested_actions,
        events=events if events else None,
        session_ended=session_ended,
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


def _extract_events_from_narrative(
    narrative: str,
    mechanical_result: Optional[Dict[str, Any]],
    turn: int,
) -> List[GameEventData]:
    """
    Extract structured game events from narrative text and mechanical results.

    Detects:
    - Item acquisitions (finds, picks up, receives)
    - Gold changes (coins, gold, money)
    - Skill checks (from mechanical_result)
    - Damage (from mechanical_result)

    Returns:
        List of GameEventData for frontend rendering
    """
    import re
    events = []

    # Patterns for item acquisition
    item_patterns = [
        r"(?:find|pick up|receive|acquire|discover|obtain|grab|take)s?\s+(?:a|an|the|some)?\s*([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)",
        r"(?:a|an|the)\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)\s+(?:is now yours|added to your inventory)",
    ]

    for pattern in item_patterns:
        matches = re.findall(pattern, narrative, re.IGNORECASE)
        for item_name in matches:
            # Filter out common false positives
            if item_name.lower() not in ["the", "a", "an", "you", "your", "they", "their"]:
                events.append(GameEventData(
                    type="ITEM_ADDED",
                    data={"item": item_name.strip(), "quantity": 1},
                    turn=turn,
                ))

    # Extract gold/coins from narrative
    gold_pattern = r"(\d+)\s*(?:gold|coins?|gp|gold pieces)"
    gold_matches = re.findall(gold_pattern, narrative, re.IGNORECASE)
    for amount_str in gold_matches:
        try:
            amount = int(amount_str)
            events.append(GameEventData(
                type="GOLD_CHANGED",
                data={"amount": amount},
                turn=turn,
            ))
        except ValueError:
            pass

    # Extract events from mechanical results
    if mechanical_result and mechanical_result.get("rolls"):
        for roll in mechanical_result["rolls"]:
            if roll.get("type") == "skill":
                events.append(GameEventData(
                    type="SKILL_CHECK",
                    data={
                        "skill": roll.get("skill", "unknown"),
                        "roll": roll.get("roll", 0),
                        "modifier": roll.get("modifier", 0),
                        "total": roll.get("total", 0),
                        "dc": roll.get("dc", 0),
                        "success": roll.get("success", False),
                    },
                    turn=turn,
                ))
            elif roll.get("type") == "attack":
                events.append(GameEventData(
                    type="ATTACK_ROLL",
                    data={
                        "roll": roll.get("roll", 0),
                        "modifier": roll.get("modifier", 0),
                        "total": roll.get("total", 0),
                        "is_hit": roll.get("is_hit", False),
                    },
                    turn=turn,
                ))
            elif roll.get("type") == "damage":
                events.append(GameEventData(
                    type="DAMAGE_DEALT",
                    data={
                        "damage": roll.get("damage", 0),
                        "damage_type": roll.get("damage_type", "unknown"),
                    },
                    turn=turn,
                ))

    return events


def _generate_suggested_actions(
    narrative: str,
    genre: str,
    style: str,
) -> Optional[List[str]]:
    """
    Generate contextual action suggestions based on narrative and genre.

    Returns 3 suggested actions for 'guided' style, None for other styles.
    """
    if style != "guided":
        return None

    # Genre-specific action templates
    genre_actions = {
        "fantasy": [
            "Look for magical signs",
            "Speak with a local",
            "Examine my surroundings",
            "Draw my weapon",
            "Search for clues",
            "Ask about the legends",
        ],
        "romance": [
            "Make eye contact",
            "Start a conversation",
            "Ask about their day",
            "Offer to help",
            "Share something personal",
            "Take a deep breath",
        ],
        "mystery": [
            "Search for clues",
            "Question a witness",
            "Examine the evidence",
            "Follow the lead",
            "Check my notes",
            "Look for something out of place",
        ],
        "horror": [
            "Listen carefully",
            "Check behind me",
            "Look for an exit",
            "Investigate cautiously",
            "Stay calm",
            "Find a light source",
        ],
        "adventure": [
            "Explore further",
            "Check my equipment",
            "Look for a path",
            "Ask the guide",
            "Take point",
            "Search for supplies",
        ],
        "drama": [
            "Speak my mind",
            "Listen quietly",
            "Ask what happened",
            "Offer support",
            "Walk away",
            "Take a moment",
        ],
        "scifi": [
            "Scan the area",
            "Check the systems",
            "Hail the station",
            "Analyze the data",
            "Prepare for departure",
            "Access the terminal",
        ],
    }

    # Get genre-specific actions or default
    base_actions = genre_actions.get(genre, [
        "Look around",
        "Talk to someone nearby",
        "Investigate further",
        "Wait and observe",
        "Move cautiously",
        "Ask a question",
    ])

    # Context-aware suggestions based on narrative keywords
    suggestions = []

    narrative_lower = narrative.lower()

    # Add contextual suggestions
    if any(word in narrative_lower for word in ["person", "figure", "man", "woman", "stranger"]):
        suggestions.append("Approach and introduce myself")
    if any(word in narrative_lower for word in ["door", "entrance", "gate"]):
        suggestions.append("Try the door")
    if any(word in narrative_lower for word in ["letter", "note", "paper", "book"]):
        suggestions.append("Read it carefully")
    if any(word in narrative_lower for word in ["sound", "noise", "voice"]):
        suggestions.append("Listen more closely")
    if any(word in narrative_lower for word in ["dark", "shadow", "night"]):
        suggestions.append("Look for a light source")

    # Fill remaining slots with genre actions
    import random
    while len(suggestions) < 3:
        action = random.choice(base_actions)
        if action not in suggestions:
            suggestions.append(action)

    return suggestions[:3]


def _get_genre_guidance(genre: str) -> Dict[str, str]:
    """Get narrative guidance specific to each genre."""
    guidance = {
        "fantasy": {
            "elements": "magic, ancient prophecies, mystical creatures, heroic quests",
            "hooks": "something unexpected that demands attention - a person, an event, a discovery, or a problem",
            "voice": "evocative and wonderous, with a sense of destiny",
        },
        "romance": {
            "elements": "emotional tension, meaningful glances, past connections, unspoken feelings",
            "hooks": "a moment of connection or tension with another person",
            "voice": "warm and intimate, focused on feelings and connections between people",
        },
        "mystery": {
            "elements": "clues, secrets, suspicious characters, hidden motives, puzzles",
            "hooks": "something that feels wrong or out of place",
            "voice": "atmospheric and intriguing, building tension through details",
        },
        "horror": {
            "elements": "dread, the unknown, isolation, things not quite right, building unease",
            "hooks": "a subtle wrongness that grows more unsettling",
            "voice": "unsettling and atmospheric, letting imagination fill the shadows",
        },
        "adventure": {
            "elements": "exploration, discovery, challenges, exotic locations, bold action",
            "hooks": "an opportunity or challenge that beckons",
            "voice": "exciting and propulsive, full of momentum and possibility",
        },
        "drama": {
            "elements": "complex relationships, moral dilemmas, personal stakes, family secrets",
            "hooks": "a moment of emotional weight or decision",
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


def _get_guidance_instruction(needs_guidance: bool) -> str:
    """Get optional story guidance instruction when player seems stuck."""
    if needs_guidance:
        return """
GUIDANCE MODE: The player seems uncertain about what to do next. Without railroading:
- Weave a subtle hint into the narrative about possible directions
- Have an NPC mention something relevant, or describe an environmental detail that suggests action
- Keep it natural - the player should feel they discovered the option, not that it was handed to them
Example: Instead of "You should go to the tavern", use "The distant sound of laughter drifts from the tavern's open windows"
"""
    return ""


async def _generate_opening(session: Dict[str, Any], model) -> str:
    """Generate an opening that matches the user's genre, tone, and style."""
    logger.info(f"[OPENING] Starting _generate_opening for session {session.get('session_id', 'unknown')}")

    answers = session.get("session_0_answers", {})
    genre = session.get("genre", "fantasy")
    tone = session.get("tone_preference", answers.get("tone", "dramatic"))
    style = session.get("storytelling_style", "guided")
    setting = session.get("setting_preference", answers.get("setting", ""))
    character = session.get("character_concept", answers.get("character", ""))
    world_lore = session.get("world_lore_content", "")
    world_name = session.get("world_name", "")

    logger.info(f"[OPENING] genre={genre}, tone={tone}, style={style}, world_lore_len={len(world_lore)}")

    genre_info = _get_genre_guidance(genre)
    style_instructions = _get_style_instructions(style)

    # Build world context from lore_content if available
    world_context = ""
    if world_lore:
        # Truncate if too long, but include substantial context
        lore_excerpt = world_lore[:3000] if len(world_lore) > 3000 else world_lore
        world_context = f"""
WORLD: {world_name}
The following is the established lore for this world. Use these characters, locations, and details:

{lore_excerpt}

IMPORTANT: Stay true to these characters and this setting. The player is entering THIS world with THESE people."""

    prompt = f"""You are a master storyteller, welcoming someone into their personal mythology.

GENRE: {genre.upper()}
Genre elements to weave in: {genre_info['elements']}
Narrative voice: {genre_info['voice']}

TONE: {tone}
STORYTELLING STYLE: {style}
{style_instructions}
{world_context}

SETTING: {setting if setting else f"Use the world lore above, or create an evocative {genre} setting"}
CHARACTER: {character if character else "Introduce the player gently - let them discover who they are through the scene"}

Write an opening that:
1. Begins IN THE MOMENT - no preamble, drop them right into a scene
2. Uses characters and locations from the world lore above (if provided)
3. Engages the senses - what do they see, hear, feel?
4. Creates intrigue through {genre_info['hooks']} (be creative and varied - avoid clichés like mysterious letters or marks appearing)
5. Makes them feel like they belong in this world
6. Ends at a natural pause - DO NOT suggest choices or ask questions

Length: 2-3 paragraphs. Write ONLY the narrative, no meta-commentary.
Make it feel personal - this is THEIR story beginning.
IMPORTANT: End the scene naturally. Do NOT list options, ask what they want to do, or suggest choices.
CRITICAL: Always complete your thoughts. Never end mid-sentence. If approaching your response limit, wrap up naturally rather than cutting off abruptly."""

    logger.info(f"[OPENING] Calling protected_ai_call with prompt of {len(prompt)} chars")

    # Use protected AI call with guardrails
    # 1400 tokens for opening to allow rich scene-setting without truncation
    return await protected_ai_call(
        model,
        prompt,
        session_id=session.get("session_id", "unknown"),
        temperature=0.85,
        max_output_tokens=1400,
    )


async def _handle_active_play(
    session: Dict[str, Any],
    player_input: str,
    model,
    db: Optional[Neo4jDatabase],
    mechanical_context: str = "",
    needs_guidance: bool = False,
    adaptive_context: Optional[str] = None,
) -> str:
    """Handle active gameplay with genre-aware storytelling."""
    answers = session.get("session_0_answers", {})
    genre = session.get("genre", "fantasy")
    tone = session.get("tone_preference", answers.get("tone", "dramatic"))
    style = session.get("storytelling_style", "guided")
    setting = session.get("setting_preference", answers.get("setting", ""))
    character = session.get("character_concept", answers.get("character", ""))
    world_lore = session.get("world_lore_content", "")
    world_name = session.get("world_name", "")

    history = session.get("history", [])[-20:]  # Last 20 messages for better continuity

    genre_info = _get_genre_guidance(genre)
    style_instructions = _get_style_instructions(style)

    # Format history for context with tiered detail:
    # - Most recent exchanges get full context (crucial for continuity)
    # - Middle exchanges get moderate detail
    # - Older exchanges get abbreviated summaries
    history_lines = []
    recent_history = history[:-1] if history else []  # Exclude current action
    history_len = len(recent_history)

    for i, h in enumerate(recent_history):
        role_label = "Player" if h["role"] == "user" else "Narrator"
        content = h.get("content", "")

        # Tiered context: more recent = more detail
        if i >= history_len - 4:
            # Last 4 messages: full context (up to 1000 chars) for tight continuity
            excerpt = content[:1000] if len(content) > 1000 else content
        elif i >= history_len - 10:
            # Middle 6 messages: moderate detail (600 chars)
            excerpt = content[:600] if len(content) > 600 else content
        else:
            # Older messages: abbreviated (300 chars)
            excerpt = content[:300] if len(content) > 300 else content

        history_lines.append(f"{role_label}: {excerpt}")

    history_text = "\n\n".join(history_lines)

    # Get the MOST RECENT DM response (untruncated) for immediate context
    # This ensures the AI always knows exactly what scene the player is responding to
    last_dm_response = ""
    for entry in reversed(history):
        if entry.get("role") == "assistant":
            last_dm_response = entry.get("content", "")
            break

    # Build world lore context (primary source of truth)
    world_context = ""
    if world_lore:
        # Include substantial lore for consistency
        lore_excerpt = world_lore[:2500] if len(world_lore) > 2500 else world_lore
        world_context = f"""
WORLD: {world_name}
ESTABLISHED LORE (stay true to these characters and details):
{lore_excerpt}
"""

    # Query for additional entities from database (supplementary)
    # Use session_world_id for isolation - only get entities from THIS game
    db_context = ""
    if db:
        try:
            results = await db.execute("""
                MATCH (e:Entity)
                WHERE e.world_id = $session_world_id
                RETURN e.name as name, e.description as description, e.entity_type as type
                LIMIT 5
            """, {"session_world_id": session.get("session_world_id", "")})

            if results:
                db_context = "\nAdditional discovered lore:\n" + "\n".join([
                    f"- {r['name']} ({r['type']}): {r['description'][:100]}"
                    for r in results if r.get('description')
                ])
        except Exception:
            pass

    # Build character context if D&D character exists
    char_context = ""
    if session.get("character_id"):
        dnd_char = _characters.get(session["character_id"])
        if dnd_char:
            char_context = f"""
CHARACTER: {dnd_char.name}, a {dnd_char.race} {dnd_char.character_class}
- Level {dnd_char.level}, {dnd_char.current_hit_points}/{dnd_char.max_hit_points} HP
- Skills: {', '.join(dnd_char.skill_proficiencies[:4])}"""

    # Handle genre blending
    genre_display = session.get("genre_blend", genre)

    prompt = f"""You are a master storyteller continuing someone's personal mythology.

GENRE: {genre_display.upper()}
Genre elements: {genre_info['elements']}
Narrative voice: {genre_info['voice']}

TONE: {tone}
STORYTELLING STYLE: {style}
{style_instructions}
{world_context}
{db_context}

SETTING: {setting if setting else 'the world described above'}
PROTAGONIST: {character if character else 'the protagonist'}
{char_context}

STORY SO FAR:
{history_text if history_text else 'The story is just beginning.'}

CURRENT SCENE (what just happened - the player is responding to THIS):
{last_dm_response if last_dm_response else 'The story is just beginning.'}

PLAYER'S ACTION: {player_input}
{mechanical_context}
{_get_guidance_instruction(needs_guidance)}
{f'''
STORYTELLING ADJUSTMENT (based on player preferences - apply subtly):
{adaptive_context}
''' if adaptive_context else ''}
Continue the narrative:
- CRITICAL: Pick up EXACTLY where the last scene left off. If the Narrator just described a location, characters, or situation - respond to the player's action within THAT scene.
- React naturally and immediately to what the player did or said
- Maintain the same characters, location, and situation from the previous exchange - do NOT jump to a new scene
- USE THE CHARACTERS AND LOCATIONS FROM THE WORLD LORE ABOVE - stay consistent!
- Use sensory details that fit the {genre_display} genre
- Maintain the {tone} tone throughout
- Never speak for the player or assume their thoughts
- If they're exploring, reward their curiosity with interesting details
- If they're taking action, show meaningful consequences
- Keep response 2-3 short paragraphs
- End at a natural pause point

IMPORTANT: Do NOT suggest choices, list options, or ask what they want to do.
Just describe what happens and let the scene breathe. Trust the reader to respond.
Do NOT introduce new scenes or locations unless the player's action explicitly moves them there.
CRITICAL: Always complete your thoughts. Never end mid-sentence. If approaching your response limit, wrap up naturally rather than cutting off abruptly.

Write ONLY the narrative:"""

    # Use protected AI call with guardrails
    # 1200 tokens allows for complete responses without truncation
    return await protected_ai_call(
        model,
        prompt,
        session_id=session.get("session_id", "unknown"),
        temperature=0.85,
        max_output_tokens=1200,
    )


# ============================================================
# LORE BASES (Pre-made worlds)
# ============================================================

# Directory for lore base JSON files
LORE_BASES_DIR = Path(__file__).parent.parent.parent.parent / "data" / "lore_bases"
SEEDS_DIR = LORE_BASES_DIR / "seeds"


def _load_lore_bases_from_files() -> Dict[str, Dict[str, Any]]:
    """
    Load all lore bases from JSON files in data/lore_bases/ and data/lore_bases/seeds/.

    Each JSON file should contain:
    - id: unique identifier
    - name: display name
    - description: brief description for UI
    - genre_hints: list of genres (or 'genre' for single genre)
    - tone_hints: list of tone descriptors
    - seed_prompt: prompt used for AI generation
    - lore_content: full text to ingest for entities/NPCs (optional)
    """
    bases = {}

    # Load from main directory
    if LORE_BASES_DIR.exists():
        for json_file in LORE_BASES_DIR.glob("*.json"):
            _load_single_lore_file(json_file, bases)

    # Load from seeds directory (curated genre-specific lore)
    if SEEDS_DIR.exists():
        for json_file in SEEDS_DIR.glob("*.json"):
            _load_single_lore_file(json_file, bases, is_seed=True)

    return bases


def _load_single_lore_file(json_file: Path, bases: Dict, is_seed: bool = False) -> None:
    """Load a single lore base JSON file."""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        lore_id = data.get("id", json_file.stem)

        # Handle both 'genre' (single) and 'genre_hints' (list)
        genre_hints = data.get("genre_hints", [])
        if not genre_hints and data.get("genre"):
            genre_hints = [data.get("genre")]

        bases[lore_id] = {
            "id": lore_id,
            "name": data.get("name", lore_id.replace("_", " ").title()),
            "description": data.get("description", ""),
            "genre": data.get("genre", genre_hints[0] if genre_hints else "fantasy"),
            "genre_hints": genre_hints,
            "tone_hints": data.get("tone_hints", []),
            "entities_count": 0,
            "seed_prompt": data.get("seed_prompt", ""),
            "lore_content": data.get("lore_content", ""),
            "ingested": False,
            "is_seed": is_seed,  # Mark as curated seed lore
        }
        logger.info(f"Loaded {'seed' if is_seed else 'lore base'} from file: {lore_id}")
    except Exception as e:
        logger.error(f"Failed to load lore file {json_file}: {e}")


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

# Log all loaded lore bases at startup for debugging
logger.info(f"Loaded {len(LORE_BASES)} total lore bases at startup:")
for base_id, base_data in LORE_BASES.items():
    is_seed = base_data.get("is_seed", False)
    logger.info(f"  - {base_id}: {base_data.get('name', 'unnamed')} (seed={is_seed})")


class LoreBaseResponse(BaseModel):
    """Response for lore base information."""
    id: str
    name: str
    description: str
    genre: Optional[str] = None
    genre_hints: List[str]
    tone_hints: List[str]
    entities_count: int
    seed_prompt: str
    is_seed: bool = False


@router.get("/lore-bases", response_model=List[LoreBaseResponse])
async def list_lore_bases(genre: Optional[str] = None):
    """
    List all available pre-made lore bases.

    Args:
        genre: Optional filter to show only lore bases matching this genre
    """
    bases = []
    for base in LORE_BASES.values():
        # Filter by genre if specified
        if genre:
            base_genre = base.get("genre", "")
            base_genres = base.get("genre_hints", [])
            if genre.lower() != base_genre.lower() and genre.lower() not in [g.lower() for g in base_genres]:
                continue

        bases.append(LoreBaseResponse(
            id=base["id"],
            name=base["name"],
            description=base["description"],
            genre=base.get("genre"),
            genre_hints=base.get("genre_hints", []),
            tone_hints=base.get("tone_hints", []),
            entities_count=base.get("entities_count", 0),
            seed_prompt=base.get("seed_prompt", ""),
            is_seed=base.get("is_seed", False),
        ))

    return bases


@router.get("/lore-bases/by-genre/{genre}", response_model=List[LoreBaseResponse])
async def get_lore_bases_for_genre(genre: str):
    """Get curated lore bases for a specific genre."""
    return await list_lore_bases(genre=genre)


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
            world_id=lore_id,  # Use lore base ID as the world_id
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
# SAVE/LOAD SYSTEM (Neo4j persistent, browser-isolated)
# ============================================================

# Max saves per browser (generous limit)
MAX_SAVES_PER_BROWSER = 50


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
    world_name: Optional[str] = None


class InventoryItem(BaseModel):
    """An item in the player's inventory."""
    name: str
    description: Optional[str] = ""
    icon: Optional[str] = "📦"
    quantity: int = 1


class SaveGameRequest(BaseModel):
    """Request to save a game to a slot."""
    slot: int = Field(..., ge=1, le=MAX_SAVES_PER_BROWSER)
    session_name: Optional[str] = Field(default=None, max_length=50)
    inventory: Optional[List[dict]] = Field(default_factory=list)
    browser_id: str = Field(..., min_length=1, max_length=100)


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
    inventory: List[dict] = Field(default_factory=list)
    character: Optional[dict] = None  # Full character data for restoration


@router.get("/saves", response_model=List[SaveSlotInfo])
async def list_save_slots(
    request: Request,
    browser_id: str = Query(..., min_length=1, description="Unique browser identifier"),
):
    """
    List all save slots for a specific browser.

    Each browser has its own isolated save slots - saves from one browser
    are completely invisible to other browsers.
    """
    db = get_optional_neo4j_db(request)
    slots = []

    if db:
        try:
            # Query Neo4j for this browser's saves
            results = await db.execute("""
                MATCH (s:GameSave {browser_id: $browser_id})
                RETURN s.slot as slot, s.session_name as session_name,
                       s.character_concept as character_concept, s.genre as genre,
                       s.phase as phase, s.turn_count as turn_count,
                       s.saved_at as saved_at, s.world_name as world_name
                ORDER BY s.slot
            """, {"browser_id": browser_id})

            # Build a map of existing saves
            existing_saves = {}
            for record in results:
                existing_saves[record["slot"]] = record

            # Return slots 1-10 (show first 10, more created on demand)
            for slot_num in range(1, 11):
                if slot_num in existing_saves:
                    save = existing_saves[slot_num]
                    slots.append(SaveSlotInfo(
                        slot=slot_num,
                        is_empty=False,
                        session_name=save["session_name"],
                        character_concept=save["character_concept"],
                        genre=save["genre"],
                        phase=save["phase"],
                        turn_count=save["turn_count"],
                        saved_at=save["saved_at"],
                        world_name=save["world_name"],
                    ))
                else:
                    slots.append(SaveSlotInfo(slot=slot_num, is_empty=True))

        except Exception as e:
            logger.error(f"Failed to list saves from Neo4j: {e}")
            # Return empty slots on error
            for slot_num in range(1, 11):
                slots.append(SaveSlotInfo(slot=slot_num, is_empty=True))
    else:
        # No database - return empty slots
        for slot_num in range(1, 11):
            slots.append(SaveSlotInfo(slot=slot_num, is_empty=True))

    return slots


@router.post("/saves/{slot}", response_model=SaveGameResponse)
async def save_game(
    request: Request,
    slot: int,
    session_id: str,
    save_req: SaveGameRequest,
):
    """
    Save a game session to a slot.

    Saves are isolated by browser_id - each browser has its own save slots.
    All session state including history, preferences, and phase is persisted to Neo4j.
    """
    if slot < 1 or slot > MAX_SAVES_PER_BROWSER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVES_PER_BROWSER}"
        )

    if session_id not in _active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    session = _active_sessions[session_id]
    browser_id = save_req.browser_id
    now = datetime.now(timezone.utc)

    # Create save data - include everything needed for full session isolation
    save_data = {
        "session_id": session_id,
        "session_name": save_req.session_name or f"Save {slot}",
        "character_concept": session.get("character_concept"),
        "genre": session.get("genre"),
        "genres": session.get("genres"),
        "genre_blend": session.get("genre_blend"),
        "tone_preference": session.get("tone_preference"),
        "setting_preference": session.get("setting_preference"),
        "storytelling_style": session.get("storytelling_style"),
        "phase": session.get("phase"),
        "history": session.get("history", []),
        "session_0_answers": session.get("session_0_answers", {}),
        "world_id": session.get("world_id"),
        "session_world_id": session.get("session_world_id"),
        "world_name": session.get("world_name"),
        "world_lore_content": session.get("world_lore_content"),
        "inventory": save_req.inventory or [],
        "saved_at": now.isoformat(),
        "created_at": session.get("created_at").isoformat() if session.get("created_at") else now.isoformat(),
        # D&D state
        "character_id": session.get("character_id"),
        "rules_mode": session.get("rules_mode"),
        "rules_visibility": session.get("rules_visibility"),
        "character_data": None,  # Will be populated below
    }

    # Include full character data in save (not just ID) for persistence across server restarts
    char_id = session.get("character_id")
    if char_id:
        char = _characters.get(char_id)
        if char:
            save_data["character_data"] = char.model_dump()

    db = get_optional_neo4j_db(request)
    if db:
        try:
            # Store the full save data as JSON in Neo4j
            # MERGE to update existing or create new
            await db.execute("""
                MERGE (s:GameSave {browser_id: $browser_id, slot: $slot})
                SET s.session_id = $session_id,
                    s.session_name = $session_name,
                    s.character_concept = $character_concept,
                    s.genre = $genre,
                    s.phase = $phase,
                    s.turn_count = $turn_count,
                    s.saved_at = datetime(),
                    s.world_name = $world_name,
                    s.save_data = $save_data_json
            """, {
                "browser_id": browser_id,
                "slot": slot,
                "session_id": session_id,
                "session_name": save_data["session_name"],
                "character_concept": save_data.get("character_concept", ""),
                "genre": save_data.get("genre", "fantasy"),
                "phase": save_data.get("phase", "active_play"),
                "turn_count": len(save_data.get("history", [])) // 2,
                "world_name": save_data.get("world_name", ""),
                "save_data_json": json.dumps(save_data),
            })
            logger.info(f"Saved session {session_id} to Neo4j slot {slot} for browser {browser_id[:8]}...")
        except Exception as e:
            logger.error(f"Failed to save to Neo4j: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save game to database"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available for saving"
        )

    return SaveGameResponse(
        success=True,
        slot=slot,
        session_id=session_id,
        message=f"Game saved to slot {slot}"
    )


@router.get("/saves/{slot}/load", response_model=LoadGameResponse)
async def load_game(
    request: Request,
    slot: int,
    browser_id: str = Query(..., min_length=1, description="Unique browser identifier"),
):
    """
    Load a game from a save slot.

    Restores the session and returns the last narrative.
    Only loads saves belonging to the specified browser_id.
    """
    if slot < 1 or slot > MAX_SAVES_PER_BROWSER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVES_PER_BROWSER}"
        )

    db = get_optional_neo4j_db(request)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )

    try:
        # Load save from Neo4j
        results = await db.execute("""
            MATCH (s:GameSave {browser_id: $browser_id, slot: $slot})
            RETURN s.save_data as save_data_json
        """, {"browser_id": browser_id, "slot": slot})

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No save found in slot {slot}"
            )

        save_data = json.loads(results[0]["save_data_json"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load from Neo4j: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load game from database"
        )

    # Create a new session ID for the loaded game
    new_session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Restore session data with all isolation and context fields
    session_data = {
        "session_id": new_session_id,
        "world_id": save_data.get("world_id"),
        "session_world_id": save_data.get("session_world_id"),
        "world_name": save_data.get("world_name"),
        "world_lore_content": save_data.get("world_lore_content"),
        "character_concept": save_data.get("character_concept"),
        "setting_preference": save_data.get("setting_preference"),
        "tone_preference": save_data.get("tone_preference"),
        "genre": save_data.get("genre", "fantasy"),
        "genres": save_data.get("genres"),
        "genre_blend": save_data.get("genre_blend"),
        "storytelling_style": save_data.get("storytelling_style", "guided"),
        "phase": save_data.get("phase", "active_play"),
        "status": "active",
        "created_at": now,
        "history": save_data.get("history", []),
        "session_0_answers": save_data.get("session_0_answers", {}),
        # D&D 5e state
        "character_id": save_data.get("character_id"),
        "rules_mode": save_data.get("rules_mode"),
        "rules_visibility": save_data.get("rules_visibility"),
    }

    _active_sessions[new_session_id] = session_data

    # Restore character from save data (not just ID reference)
    char_data = save_data.get("character_data")
    char_id = save_data.get("character_id")
    if char_data:
        # Full character data available in save
        try:
            character = CharacterSheet.model_validate(char_data)
            _characters[character.character_id] = character
            logger.info(f"Restored character '{character.name}' from save data")
        except Exception as e:
            logger.error(f"Failed to restore character from save: {e}")
    elif char_id and char_id not in _characters:
        # Legacy save without character_data - log warning
        logger.warning(f"Save has character_id {char_id} but no character_data - character may not be available")

    # Get the last narrative to show the player where they left off
    history = save_data.get("history", [])
    last_narrative = "Your adventure continues..."
    for entry in reversed(history):
        if entry.get("role") == "assistant":
            last_narrative = entry.get("content", last_narrative)
            break

    logger.info(f"Loaded save from slot {slot} for browser {browser_id[:8]}... as session {new_session_id}")

    return LoadGameResponse(
        success=True,
        session_id=new_session_id,
        phase=session_data["phase"],
        narrative=last_narrative,
        message=f"Game loaded from slot {slot}",
        inventory=save_data.get("inventory", []),
        character=save_data.get("character_data")  # Include full character for frontend restoration
    )


@router.delete("/saves/{slot}")
async def delete_save(
    request: Request,
    slot: int,
    browser_id: str = Query(..., min_length=1, description="Unique browser identifier"),
):
    """Delete a save from a slot. Only deletes saves belonging to the specified browser_id."""
    if slot < 1 or slot > MAX_SAVES_PER_BROWSER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVES_PER_BROWSER}"
        )

    db = get_optional_neo4j_db(request)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )

    try:
        # Delete from Neo4j - only if it belongs to this browser
        result = await db.execute("""
            MATCH (s:GameSave {browser_id: $browser_id, slot: $slot})
            DELETE s
            RETURN count(*) as deleted
        """, {"browser_id": browser_id, "slot": slot})

        if not result or result[0]["deleted"] == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No save found in slot {slot}"
            )

        logger.info(f"Deleted save from slot {slot} for browser {browser_id[:8]}...")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete from Neo4j: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete save from database"
        )

    return {"success": True, "message": f"Save slot {slot} cleared"}


# ============================================================
# GRAPH VISUALIZATION
# ============================================================

@router.get("/graph")
async def get_graph_data(
    request: Request,
    world_id: Optional[str] = None,
    limit: int = 100,
):
    """
    Get graph data for visualization.

    Returns nodes and edges in a format suitable for vis.js or similar libraries.

    Args:
        world_id: Optional filter to show only entities from a specific world/lore base
        limit: Maximum number of nodes to return
    """
    db = get_optional_neo4j_db(request)
    if not db:
        return {"nodes": [], "edges": []}

    try:
        # Build world filter clause
        world_filter = ""
        params = {"limit": limit}
        if world_id:
            world_filter = "AND n.world_id = $world_id"
            params["world_id"] = world_id

        # Get all entities (nodes)
        node_query = f"""
        MATCH (n)
        WHERE (n.canon_id IS NOT NULL OR n.name IS NOT NULL)
        {world_filter}
        RETURN
            COALESCE(n.canon_id, id(n)) AS id,
            COALESCE(n.name, n.canonical_name, 'Unknown') AS label,
            labels(n)[0] AS type,
            n.entity_type AS entity_type,
            n.openness AS openness,
            n.description AS description,
            n.world_id AS world_id
        LIMIT $limit
        """
        nodes_result = await db.execute(node_query, params)

        # Build edge world filter
        edge_world_filter = ""
        edge_params = {"limit": limit * 2}
        if world_id:
            edge_world_filter = "AND (a.world_id = $world_id OR b.world_id = $world_id)"
            edge_params["world_id"] = world_id

        # Get all relationships (edges)
        edge_query = f"""
        MATCH (a)-[r]->(b)
        WHERE (a.canon_id IS NOT NULL OR a.name IS NOT NULL)
          AND (b.canon_id IS NOT NULL OR b.name IS NOT NULL)
        {edge_world_filter}
        RETURN
            COALESCE(a.canon_id, id(a)) AS from,
            COALESCE(b.canon_id, id(b)) AS to,
            type(r) AS label
        LIMIT $limit
        """
        edges_result = await db.execute(edge_query, edge_params)

        # Format for vis.js
        nodes = []
        for row in nodes_result:
            node_type = row.get("entity_type") or row.get("type") or "Entity"

            # Color by type
            colors = {
                "Character": "#c98b8b",
                "Location": "#8ba88b",
                "Faction": "#a08bc9",
                "Item": "#e8c47c",
                "Event": "#8b9fc9",
                "Concept": "#d4a574",
            }
            color = colors.get(node_type, "#b8a99a")

            nodes.append({
                "id": row["id"],
                "label": row["label"],
                "group": node_type,
                "color": color,
                "title": row.get("description", "")[:200] if row.get("description") else node_type,
            })

        edges = []
        for row in edges_result:
            edges.append({
                "from": row["from"],
                "to": row["to"],
                "label": row["label"],
                "arrows": "to",
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
            }
        }

    except Exception as e:
        logger.error(f"Graph query failed: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}


@router.get("/graph/node/{node_id}")
async def get_node_details(
    request: Request,
    node_id: str,
):
    """
    Get full details for a specific node in the graph.

    Returns all properties stored on the node, including OCEAN personality
    traits for characters, goals, fears, secrets, etc.
    """
    db = get_optional_neo4j_db(request)
    if not db:
        return {"error": "Database not available", "node_id": node_id}

    try:
        # Fetch all properties for the node
        query = """
        MATCH (n)
        WHERE n.canon_id = $node_id OR n.name = $node_id OR id(n) = toInteger($node_id)
        RETURN
            COALESCE(n.canon_id, toString(id(n))) AS id,
            labels(n) AS labels,
            properties(n) AS props
        LIMIT 1
        """
        result = await db.execute(query, {"node_id": node_id})

        if not result:
            return {"error": "Node not found", "node_id": node_id}

        row = result[0]
        node_labels = row.get("labels", [])
        props = row.get("props", {})

        # Determine entity type from labels or props
        entity_type = props.get("entity_type") or (node_labels[0] if node_labels else "Unknown")

        # Extract OCEAN personality traits
        ocean = {}
        ocean_keys = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
        for key in ocean_keys:
            if key in props:
                ocean[key] = props[key]

        # Extract relationships
        rel_query = """
        MATCH (n)-[r]-(other)
        WHERE n.canon_id = $node_id OR n.name = $node_id OR id(n) = toInteger($node_id)
        RETURN
            type(r) AS rel_type,
            CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END AS direction,
            COALESCE(other.name, other.canonical_name, 'Unknown') AS other_name,
            labels(other)[0] AS other_type
        LIMIT 20
        """
        rel_result = await db.execute(rel_query, {"node_id": node_id})

        relationships = []
        for rel_row in rel_result:
            relationships.append({
                "type": rel_row["rel_type"],
                "direction": rel_row["direction"],
                "target_name": rel_row["other_name"],
                "target_type": rel_row["other_type"],
            })

        return {
            "id": row["id"],
            "labels": node_labels,
            "entity_type": entity_type,
            "name": props.get("name") or props.get("canonical_name") or "Unknown",
            "description": props.get("description", ""),
            "properties": props,
            "ocean": ocean if ocean else None,
            "relationships": relationships,
        }

    except Exception as e:
        logger.error(f"Node detail query failed: {e}")
        return {"error": str(e), "node_id": node_id}
