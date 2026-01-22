"""
World Tuner Routes - Conversational World Configuration

Extracted from game_routes.py for cleaner organization.
Provides API endpoints for the World Tuner feature.
"""

import json
import logging
from fastapi import APIRouter, HTTPException, Request, status

from src.lms.agents.world_tuner_agent import WorldTunerAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game/admin/lore-bases", tags=["World Tuner"])


def get_lore_bases():
    """Import LORE_BASES from game_routes to avoid circular imports."""
    from src.lms.api.game_routes import LORE_BASES
    return LORE_BASES


@router.post("/{lore_id}/tuner/chat")
async def world_tuner_chat(
    lore_id: str,
    http_request: Request,
):
    """
    Send a message to the World Tuner agent for conversational world configuration.

    The agent helps admins configure origins, archetypes, skills, and world
    characteristics through natural dialogue, proposing changes for approval.
    """
    LORE_BASES = get_lore_bases()

    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    body = await http_request.json()
    message = body.get("message", "").strip()
    history = body.get("history", [])

    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is required"
        )

    # Build world context
    base = LORE_BASES[lore_id]
    world_context = {
        "id": lore_id,
        "name": base.get("name", lore_id),
        "genre": base.get("genre", "fantasy"),
        "description": base.get("description", ""),
        "character_options": base.get("character_options", {}),
        "world_characteristics": base.get("world_characteristics", {})
    }

    # Create agent and chat
    agent = WorldTunerAgent()
    result = await agent.chat(lore_id, message, history, world_context)

    return {
        "success": True,
        "message": result.get("message", ""),
        "proposals": result.get("proposals", []),
        "world_id": lore_id
    }


@router.post("/{lore_id}/tuner/approve")
async def world_tuner_approve(
    lore_id: str,
    http_request: Request,
):
    """
    Approve and apply a proposed change from the World Tuner.

    Takes a proposal object and applies it to the world's character_options.
    """
    LORE_BASES = get_lore_bases()

    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    body = await http_request.json()
    proposal = body.get("proposal")

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposal is required"
        )

    base = LORE_BASES[lore_id]
    current_options = base.get("character_options", {})

    # Apply the proposal
    agent = WorldTunerAgent()
    updated_options = await agent.apply_proposal(lore_id, proposal, current_options)

    # Store the updated options
    LORE_BASES[lore_id]["character_options"] = updated_options

    # Persist to Neo4j
    db = getattr(http_request.app.state, "neo4j_db", None)
    if db:
        try:
            await db.execute("""
                MATCH (lb:LoreBase {lore_id: $lore_id})
                SET lb.character_options = $options
            """, {
                "lore_id": lore_id,
                "options": json.dumps(updated_options)
            })
        except Exception as e:
            logger.warning(f"Failed to persist character options to Neo4j: {e}")

    return {
        "success": True,
        "lore_id": lore_id,
        "proposal_id": proposal.get("id"),
        "action": proposal.get("action"),
        "category": proposal.get("category"),
        "character_options": updated_options,
        "message": f"Applied {proposal.get('action')} to {proposal.get('category')}"
    }


@router.get("/{lore_id}/tuner/greeting")
async def world_tuner_greeting(
    lore_id: str,
    http_request: Request,
):
    """Get the initial greeting message for the World Tuner."""
    LORE_BASES = get_lore_bases()

    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    base = LORE_BASES[lore_id]
    agent = WorldTunerAgent()

    return {
        "success": True,
        "greeting": agent.get_greeting(
            base.get("name", lore_id),
            base.get("genre", "fantasy")
        ),
        "world_id": lore_id,
        "world_name": base.get("name", lore_id)
    }
