# src/mantle/api/save_routes.py
"""
Save/Load System API Routes

Endpoints for game save management:
- List save slots
- Save game to slot
- Load game from slot
- Delete save from slot

All saves are browser-isolated and persisted to Neo4j.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from src.mantle.api.session_state import (
    active_sessions,
    MAX_SAVES_PER_BROWSER,
)
from src.mantle.api.dnd_routes import _characters, CharacterSheet

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saves", tags=["Saves"])


# ============================================================
# HELPERS
# ============================================================

def get_optional_neo4j_db(request: Request):
    """Get Neo4j database if available, otherwise None."""
    return getattr(request.app.state, "neo4j_db", None)


def get_gemini_model():
    """Get Gemini model for AI summarization."""
    # Import here to avoid circular imports
    try:
        from src.mantle.api.game_routes import get_gemini_model as _get_model
        return _get_model()
    except ImportError:
        return None


# Try to import Arc Engine
try:
    from src.mantle.arc import ArcEngine
    ARC_ENGINE_AVAILABLE = True
except ImportError:
    ARC_ENGINE_AVAILABLE = False
    ArcEngine = None


# ============================================================
# MODELS
# ============================================================

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
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    rules_mode: Optional[str] = None
    session_status: Optional[str] = None
    suggested_mode: Optional[str] = None


class SaveGameRequest(BaseModel):
    """Request to save a game to a slot."""
    slot: int = Field(..., ge=1, le=MAX_SAVES_PER_BROWSER)
    session_name: Optional[str] = Field(default=None, max_length=50)
    inventory: Optional[List[dict]] = Field(default_factory=list)
    browser_id: str = Field(..., min_length=1, max_length=100)
    user_id: Optional[str] = Field(default=None, max_length=100)


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
    character: Optional[dict] = None
    continuation_mode: str = "continue"
    session_summary: Optional[str] = None
    arc_context: Optional[Dict[str, Any]] = None
    turn_count: int = 0


# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def _generate_session_summary(
    history: List[Dict[str, str]],
    save_data: Dict[str, Any],
    db: Optional[Any],
) -> str:
    """
    Generate a narrative summary of the previous session for New Chapter mode.
    """
    if not history:
        return "A new chapter begins..."

    character_name = save_data.get("character_name", "the hero")
    world_name = save_data.get("world_name", "the realm")
    genre = save_data.get("genre", "fantasy")

    recent_history = history[-20:] if len(history) > 20 else history

    conversation_text = ""
    for entry in recent_history:
        role = "Player" if entry.get("role") == "user" else "Narrator"
        content = entry.get("content", "")[:500]
        conversation_text += f"{role}: {content}\n\n"

    model = get_gemini_model()
    if model:
        try:
            summary_prompt = f"""You are summarizing a {genre} roleplaying story for a player returning after a break.

CHARACTER: {character_name}
WORLD: {world_name}

RECENT STORY EVENTS:
{conversation_text}

Write a brief "Previously, in your adventure..." summary (2-3 short paragraphs) that:
1. Reminds the player what happened
2. Mentions any key characters, locations, or items
3. Sets up anticipation for what comes next
4. Uses second person ("You...")
5. Matches the {genre} tone

Keep it under 200 words. Be evocative but concise."""

            response = model.generate_content(summary_prompt)
            if response and response.text:
                summary = response.text.strip()
                logger.info(f"Generated session summary ({len(summary)} chars)")
                return summary
        except Exception as e:
            logger.warning(f"Failed to generate AI summary: {e}")

    last_narrator_text = ""
    for entry in reversed(history):
        if entry.get("role") == "assistant":
            last_narrator_text = entry.get("content", "")
            break

    if last_narrator_text:
        sentences = last_narrator_text.split(". ")[:3]
        context = ". ".join(sentences)
        if not context.endswith("."):
            context += "."
        return f"*Previously, in {world_name}...*\n\n{context}\n\nA new chapter begins for {character_name}."

    return f"*A new chapter begins in {world_name}...*\n\nYour adventure continues, {character_name}. The path ahead is yours to forge."


# ============================================================
# ROUTES
# ============================================================

@router.get("", response_model=List[SaveSlotInfo])
async def list_save_slots(
    request: Request,
    browser_id: str = Query(..., min_length=1, description="Unique browser identifier"),
    user_id: Optional[str] = Query(None, description="Optional user/account ID"),
):
    """List all save slots for a specific browser or user."""
    db = get_optional_neo4j_db(request)
    slots = []

    if db:
        try:
            if user_id:
                query = """
                    MATCH (s:GameSave {user_id: $user_id})
                    RETURN s.slot as slot, s.session_name as session_name,
                           s.character_concept as character_concept, s.genre as genre,
                           s.phase as phase, s.turn_count as turn_count,
                           s.saved_at as saved_at, s.world_name as world_name,
                           s.character_id as character_id, s.character_name as character_name,
                           s.rules_mode as rules_mode, s.session_status as session_status
                    ORDER BY s.slot
                """
                params = {"user_id": user_id}
            else:
                query = """
                    MATCH (s:GameSave {browser_id: $browser_id})
                    WHERE s.user_id IS NULL
                    RETURN s.slot as slot, s.session_name as session_name,
                           s.character_concept as character_concept, s.genre as genre,
                           s.phase as phase, s.turn_count as turn_count,
                           s.saved_at as saved_at, s.world_name as world_name,
                           s.character_id as character_id, s.character_name as character_name,
                           s.rules_mode as rules_mode, s.session_status as session_status
                    ORDER BY s.slot
                """
                params = {"browser_id": browser_id}

            results = await db.execute(query, params)

            existing_saves = {}
            for record in results:
                existing_saves[record["slot"]] = record

            for slot_num in range(1, 11):
                if slot_num in existing_saves:
                    save = existing_saves[slot_num]
                    turn_count = save["turn_count"] or 0
                    session_status = save.get("session_status", "active")

                    if turn_count == 0:
                        suggested_mode = "continue"
                    elif session_status == "ended":
                        suggested_mode = "new_chapter"
                    else:
                        suggested_mode = "continue"

                    slots.append(SaveSlotInfo(
                        slot=slot_num,
                        is_empty=False,
                        session_name=save["session_name"],
                        character_concept=save["character_concept"],
                        genre=save["genre"],
                        phase=save["phase"],
                        turn_count=turn_count,
                        saved_at=save["saved_at"],
                        world_name=save["world_name"],
                        character_id=save.get("character_id"),
                        character_name=save.get("character_name"),
                        rules_mode=save.get("rules_mode"),
                        session_status=session_status,
                        suggested_mode=suggested_mode,
                    ))
                else:
                    slots.append(SaveSlotInfo(slot=slot_num, is_empty=True))

        except Exception as e:
            logger.error(f"Failed to list saves from Neo4j: {e}")
            for slot_num in range(1, 11):
                slots.append(SaveSlotInfo(slot=slot_num, is_empty=True))
    else:
        for slot_num in range(1, 11):
            slots.append(SaveSlotInfo(slot=slot_num, is_empty=True))

    return slots


@router.post("/{slot}", response_model=SaveGameResponse)
async def save_game(
    request: Request,
    slot: int,
    session_id: str,
    save_req: SaveGameRequest,
):
    """Save a game session to a slot."""
    if slot < 1 or slot > MAX_SAVES_PER_BROWSER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVES_PER_BROWSER}"
        )

    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    session = active_sessions[session_id]
    browser_id = save_req.browser_id
    user_id = save_req.user_id
    now = datetime.now(timezone.utc)

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
        "character_id": session.get("character_id"),
        "rules_mode": session.get("rules_mode"),
        "rules_visibility": session.get("rules_visibility"),
        "protagonist_arc": session.get("protagonist_arc"),
        "lethality_preference": session.get("lethality_preference"),
        "moral_complexity_preference": session.get("moral_complexity_preference"),
        "character_data": None,
    }

    char_id = session.get("character_id")
    if char_id:
        char = _characters.get(char_id)
        if char:
            save_data["character_data"] = char.model_dump()
            save_data["character_name"] = char.name

    db = get_optional_neo4j_db(request)
    if db:
        try:
            session_status = session.get("status", "active")

            if user_id:
                query = """
                    MERGE (s:GameSave {user_id: $user_id, slot: $slot})
                    SET s.session_id = $session_id,
                        s.browser_id = $browser_id,
                        s.session_name = $session_name,
                        s.character_concept = $character_concept,
                        s.genre = $genre,
                        s.phase = $phase,
                        s.turn_count = $turn_count,
                        s.saved_at = datetime(),
                        s.world_name = $world_name,
                        s.character_id = $character_id,
                        s.character_name = $character_name,
                        s.rules_mode = $rules_mode,
                        s.session_status = $session_status,
                        s.save_data = $save_data_json
                """
                params = {"user_id": user_id, "browser_id": browser_id}
            else:
                query = """
                    MERGE (s:GameSave {browser_id: $browser_id, slot: $slot})
                    SET s.session_id = $session_id,
                        s.session_name = $session_name,
                        s.character_concept = $character_concept,
                        s.genre = $genre,
                        s.phase = $phase,
                        s.turn_count = $turn_count,
                        s.saved_at = datetime(),
                        s.world_name = $world_name,
                        s.character_id = $character_id,
                        s.character_name = $character_name,
                        s.rules_mode = $rules_mode,
                        s.session_status = $session_status,
                        s.save_data = $save_data_json
                """
                params = {"browser_id": browser_id}

            params.update({
                "slot": slot,
                "session_id": session_id,
                "session_name": save_data["session_name"],
                "character_concept": save_data.get("character_concept", ""),
                "genre": save_data.get("genre", "fantasy"),
                "phase": save_data.get("phase", "active_play"),
                "turn_count": len(save_data.get("history", [])) // 2,
                "world_name": save_data.get("world_name", ""),
                "character_id": save_data.get("character_id"),
                "character_name": save_data.get("character_name") or save_data.get("character", {}).get("name"),
                "rules_mode": save_data.get("rules_mode", "narrative"),
                "session_status": session_status,
                "save_data_json": json.dumps(save_data),
            })

            await db.execute(query, params)
            logger.info(f"Saved session {session_id} to slot {slot}")
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


@router.get("/{slot}/load", response_model=LoadGameResponse)
async def load_game(
    request: Request,
    slot: int,
    browser_id: str = Query(..., min_length=1),
    mode: str = Query("continue", description="'continue' or 'new_chapter'"),
    user_id: Optional[str] = Query(None),
):
    """Load a game from a save slot with optional continuation mode."""
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
        if user_id:
            query = """
                MATCH (s:GameSave {user_id: $user_id, slot: $slot})
                RETURN s.save_data as save_data_json
            """
            params = {"user_id": user_id, "slot": slot}
        else:
            query = """
                MATCH (s:GameSave {browser_id: $browser_id, slot: $slot})
                WHERE s.user_id IS NULL
                RETURN s.save_data as save_data_json
            """
            params = {"browser_id": browser_id, "slot": slot}

        results = await db.execute(query, params)

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

    new_session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

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
        "character_id": save_data.get("character_id"),
        "rules_mode": save_data.get("rules_mode"),
        "rules_visibility": save_data.get("rules_visibility"),
        "protagonist_arc": save_data.get("protagonist_arc"),
        "lethality_preference": save_data.get("lethality_preference"),
        "moral_complexity_preference": save_data.get("moral_complexity_preference"),
    }

    active_sessions[new_session_id] = session_data

    char_data = save_data.get("character_data")
    char_id = save_data.get("character_id")
    if char_data:
        try:
            character = CharacterSheet.model_validate(char_data)
            _characters[character.character_id] = character
            logger.info(f"Restored character '{character.name}' from save data")
        except Exception as e:
            logger.error(f"Failed to restore character from save: {e}")
    elif char_id and char_id not in _characters:
        logger.warning(f"Save has character_id {char_id} but no character_data")

    history = save_data.get("history", [])
    turn_count = len(history) // 2

    arc_context = None
    if ARC_ENGINE_AVAILABLE:
        arc_state = save_data.get("arc_engine_state")
        if arc_state:
            try:
                arc_engine = ArcEngine.from_dict(arc_state)
                session_data["arc_engine"] = arc_engine
                arc_context = {
                    "current_phase": arc_engine.current_phase.value,
                    "phase_display": arc_engine.current_phase.value.replace("_", " ").title(),
                    "tension_level": arc_engine.tension_level.value,
                    "journey_progress": arc_engine.journey_progress,
                }
            except Exception as e:
                logger.warning(f"Failed to restore Arc Engine: {e}")

    if mode == "new_chapter":
        session_summary = await _generate_session_summary(history, save_data, db)

        session_data["history"] = [
            {"role": "system", "content": f"PREVIOUS CHAPTER SUMMARY:\n{session_summary}"}
        ]

        if ARC_ENGINE_AVAILABLE:
            new_arc = ArcEngine()
            session_data["arc_engine"] = new_arc
            arc_context = {
                "current_phase": "CALL_TO_ADVENTURE",
                "phase_display": "Call To Adventure",
                "tension_level": "low",
                "journey_progress": 0.0,
            }

        narrative = session_summary
        message = f"Starting new chapter in {save_data.get('world_name', 'your world')}"
        logger.info(f"Loaded save from slot {slot} as NEW CHAPTER")

    else:
        last_narrative = "Your adventure continues..."
        for entry in reversed(history):
            if entry.get("role") == "assistant":
                last_narrative = entry.get("content", last_narrative)
                break

        narrative = last_narrative
        message = f"Game loaded from slot {slot}"
        logger.info(f"Loaded save from slot {slot} as session {new_session_id}")

    return LoadGameResponse(
        success=True,
        session_id=new_session_id,
        phase=session_data["phase"],
        narrative=narrative,
        message=message,
        inventory=save_data.get("inventory", []),
        character=save_data.get("character_data"),
        continuation_mode=mode,
        session_summary=narrative if mode == "new_chapter" else None,
        arc_context=arc_context,
        turn_count=turn_count,
    )


@router.delete("/{slot}")
async def delete_save(
    request: Request,
    slot: int,
    browser_id: str = Query(..., min_length=1),
    user_id: Optional[str] = Query(None),
):
    """Delete a save from a slot."""
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
        if user_id:
            query = """
                MATCH (s:GameSave {user_id: $user_id, slot: $slot})
                DELETE s
                RETURN count(*) as deleted
            """
            params = {"user_id": user_id, "slot": slot}
        else:
            query = """
                MATCH (s:GameSave {browser_id: $browser_id, slot: $slot})
                WHERE s.user_id IS NULL
                DELETE s
                RETURN count(*) as deleted
            """
            params = {"browser_id": browser_id, "slot": slot}

        result = await db.execute(query, params)

        if not result or result[0]["deleted"] == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No save found in slot {slot}"
            )

        logger.info(f"Deleted save from slot {slot}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete from Neo4j: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete save from database"
        )

    return {"success": True, "message": f"Save slot {slot} cleared"}
