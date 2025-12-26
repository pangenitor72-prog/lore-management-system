# src/lms/api/memory_routes.py
"""
Memory API Routes

Endpoints for the Experiential Memory system:
- Recording events (echoes)
- Managing NPC beliefs and impressions
- Player legends and reputation
- Narrative threads
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel, Field

from src.lms.memory import (
    MemoryManager,
    Echo, Whisper, AgentBelief, Impression, Legend, Thread,
    SalienceLevel, BeliefStrength, ImpressionValence,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])


# ============================================================
# DEPENDENCY
# ============================================================

def get_memory_manager(request: Request) -> MemoryManager:
    """Get the memory manager from app state."""
    manager = getattr(request.app.state, "memory_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory system not initialized"
        )
    return manager


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class RecordEventRequest(BaseModel):
    """Request to record an event (echo)."""
    event_type: str = Field(..., description="Type: combat, dialogue, discovery, betrayal, etc.")
    description: str = Field(..., description="Full narrative of what occurred")
    summary: str = Field(..., description="One-line summary")
    session_id: Optional[str] = None
    location_id: Optional[str] = None
    participants: Optional[List[str]] = None
    witnesses: Optional[List[str]] = None
    player_involved: bool = False
    salience: str = "notable"  # legendary, significant, notable, ordinary
    emotional_weight: float = 0.5
    narrative_weight: float = 0.5
    arc_phase: Optional[str] = None
    tags: Optional[List[str]] = None


class RecordBeliefRequest(BaseModel):
    """Request to record an NPC belief."""
    npc_id: str = Field(..., description="canon_id of the NPC")
    content: str = Field(..., description="What they believe")
    subject_id: Optional[str] = None
    subject_type: str = "general"
    source_type: str = "direct"  # direct, hearsay, inference
    source_agent_id: Optional[str] = None
    confidence: float = 0.7
    is_true: Optional[bool] = None


class UpdateImpressionRequest(BaseModel):
    """Request to update NPC impression of player."""
    npc_id: str
    valence: Optional[str] = None  # reverent, grateful, friendly, neutral, wary, hostile, fearful, hateful
    summary: Optional[str] = None
    trust_delta: float = 0.0
    respect_delta: float = 0.0
    fear_delta: float = 0.0
    affection_delta: float = 0.0


class CreateLegendRequest(BaseModel):
    """Request to create a player legend."""
    title: str = Field(..., description="The Dragonslayer of Ashenmoor")
    epithet: str = Field(..., description="The Dragonslayer")
    narrative: str = Field(..., description="The story as it's told")
    source_echo_ids: Optional[List[str]] = None
    session_id: Optional[str] = None
    is_public: bool = True
    hero_journey_stage: Optional[str] = None


class CreateThreadRequest(BaseModel):
    """Request to create a narrative thread."""
    thread_type: str = Field(..., description="mystery, debt, promise, conflict, prophecy")
    description: str
    stakes: str
    primary_entity_id: Optional[str] = None
    player_obligation: bool = False
    urgency: float = 0.5


class ResolveThreadRequest(BaseModel):
    """Request to resolve a thread."""
    resolution_summary: str
    echo_id: Optional[str] = None


# ============================================================
# EVENT ENDPOINTS
# ============================================================

@router.post("/events")
async def record_event(
    request: Request,
    event_req: RecordEventRequest,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """
    Record something that happened in the game world.

    Creates an Echo - the fundamental unit of memory.
    """
    try:
        salience = SalienceLevel(event_req.salience)
    except ValueError:
        salience = SalienceLevel.NOTABLE

    echo = await memory.record_event(
        event_type=event_req.event_type,
        description=event_req.description,
        summary=event_req.summary,
        session_id=event_req.session_id,
        location_id=event_req.location_id,
        participants=event_req.participants,
        witnesses=event_req.witnesses,
        player_involved=event_req.player_involved,
        salience=salience,
        emotional_weight=event_req.emotional_weight,
        narrative_weight=event_req.narrative_weight,
        arc_phase=event_req.arc_phase,
        tags=event_req.tags,
    )

    return {
        "status": "recorded",
        "echo_id": echo.id,
        "summary": echo.summary,
        "salience": echo.salience.value,
    }


@router.get("/events")
async def get_events(
    request: Request,
    session_id: Optional[str] = None,
    player_only: bool = False,
    limit: int = 20,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get recorded events (echoes)."""
    if session_id:
        echoes = memory.experiential.get_echoes_for_session(session_id)
    elif player_only:
        echoes = memory.experiential.get_player_echoes(limit=limit)
    else:
        echoes = memory.experiential.search_echoes(limit=limit)

    return {
        "count": len(echoes),
        "events": [
            {
                "id": e.id,
                "type": e.event_type,
                "summary": e.summary,
                "salience": e.salience.value,
                "player_involved": e.player_involved,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in echoes
        ]
    }


# ============================================================
# BELIEF ENDPOINTS
# ============================================================

@router.post("/beliefs")
async def record_belief(
    request: Request,
    belief_req: RecordBeliefRequest,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Record what an NPC believes."""
    belief = await memory.record_npc_belief(
        npc_id=belief_req.npc_id,
        content=belief_req.content,
        subject_id=belief_req.subject_id,
        subject_type=belief_req.subject_type,
        source_type=belief_req.source_type,
        source_agent_id=belief_req.source_agent_id,
        confidence=belief_req.confidence,
        is_true=belief_req.is_true,
    )

    return {
        "status": "recorded",
        "belief_id": belief.id,
        "npc_id": belief.agent_id,
        "content": belief.content,
        "confidence": belief.confidence,
    }


@router.get("/beliefs/{npc_id}")
async def get_npc_beliefs(
    request: Request,
    npc_id: str,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get all beliefs held by an NPC."""
    beliefs = memory.get_npc_beliefs(npc_id)

    return {
        "npc_id": npc_id,
        "count": len(beliefs),
        "beliefs": [
            {
                "id": b.id,
                "content": b.content,
                "subject_id": b.subject_id,
                "confidence": b.confidence,
                "strength": b.strength.value,
                "source_type": b.source_type,
                "is_true": b.is_true,
            }
            for b in beliefs
        ]
    }


@router.get("/beliefs/about/{subject_id}")
async def get_beliefs_about(
    request: Request,
    subject_id: str,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get what various NPCs believe about a subject."""
    beliefs = memory.get_world_beliefs_about(subject_id)

    return {
        "subject_id": subject_id,
        "count": len(beliefs),
        "believers": [
            {
                "npc_id": b.agent_id,
                "content": b.content,
                "confidence": b.confidence,
            }
            for b in beliefs
        ]
    }


# ============================================================
# IMPRESSION ENDPOINTS
# ============================================================

@router.get("/impressions")
async def get_all_impressions(
    request: Request,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get how all NPCs see the player."""
    impressions = memory.get_all_impressions()

    return {
        "count": len(impressions),
        "impressions": [
            {
                "npc_id": i.agent_id,
                "valence": i.valence.value,
                "intensity": i.intensity,
                "trust": i.trust,
                "respect": i.respect,
                "fear": i.fear,
                "summary": i.summary,
                "forms_of_address": i.forms_of_address,
            }
            for i in impressions
        ]
    }


@router.get("/impressions/{npc_id}")
async def get_impression(
    request: Request,
    npc_id: str,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get how a specific NPC sees the player."""
    impression = memory.get_npc_impression(npc_id)

    if not impression:
        return {"npc_id": npc_id, "impression": None, "message": "No impression recorded"}

    return {
        "npc_id": npc_id,
        "impression": {
            "valence": impression.valence.value,
            "intensity": impression.intensity,
            "summary": impression.summary,
            "trust": impression.trust,
            "respect": impression.respect,
            "fear": impression.fear,
            "affection": impression.affection,
            "will_help": impression.will_help,
            "will_trade": impression.will_trade,
            "will_share_secrets": impression.will_share_secrets,
            "forms_of_address": impression.forms_of_address,
            "interaction_count": impression.interaction_count,
        }
    }


@router.put("/impressions/{npc_id}")
async def update_impression(
    request: Request,
    npc_id: str,
    update_req: UpdateImpressionRequest,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Update an NPC's impression of the player."""
    impression = memory.get_npc_impression(npc_id)

    if not impression:
        # Create new impression
        impression = Impression(
            agent_id=npc_id,
            summary=update_req.summary or "Met the player",
        )

    # Apply deltas
    impression.trust = max(0.0, min(1.0, impression.trust + update_req.trust_delta))
    impression.respect = max(0.0, min(1.0, impression.respect + update_req.respect_delta))
    impression.fear = max(0.0, min(1.0, impression.fear + update_req.fear_delta))
    impression.affection = max(0.0, min(1.0, impression.affection + update_req.affection_delta))

    if update_req.valence:
        try:
            impression.valence = ImpressionValence(update_req.valence)
        except ValueError:
            pass

    if update_req.summary:
        impression.summary = update_req.summary

    impression.last_interaction = datetime.now(timezone.utc)
    impression.interaction_count += 1

    memory.experiential.record_impression(impression)

    return {
        "status": "updated",
        "npc_id": npc_id,
        "valence": impression.valence.value,
        "trust": impression.trust,
        "respect": impression.respect,
    }


# ============================================================
# LEGEND ENDPOINTS
# ============================================================

@router.post("/legends")
async def create_legend(
    request: Request,
    legend_req: CreateLegendRequest,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Create a new player legend."""
    legend = await memory.create_legend(
        title=legend_req.title,
        epithet=legend_req.epithet,
        narrative=legend_req.narrative,
        source_echo_ids=legend_req.source_echo_ids,
        session_id=legend_req.session_id,
        is_public=legend_req.is_public,
        hero_journey_stage=legend_req.hero_journey_stage,
    )

    return {
        "status": "created",
        "legend_id": legend.id,
        "title": legend.title,
        "epithet": legend.epithet,
    }


@router.get("/legends")
async def get_legends(
    request: Request,
    public_only: bool = False,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get player legends."""
    if public_only:
        legends = memory.get_public_legends()
    else:
        legends = memory.get_player_legends()

    return {
        "count": len(legends),
        "legends": [
            {
                "id": l.id,
                "title": l.title,
                "epithet": l.epithet,
                "narrative": l.narrative,
                "is_public": l.is_public,
                "reputation_modifier": l.reputation_modifier,
            }
            for l in legends
        ]
    }


# ============================================================
# THREAD ENDPOINTS
# ============================================================

@router.post("/threads")
async def create_thread(
    request: Request,
    thread_req: CreateThreadRequest,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Create a new narrative thread."""
    thread = await memory.create_thread(
        thread_type=thread_req.thread_type,
        description=thread_req.description,
        stakes=thread_req.stakes,
        primary_entity_id=thread_req.primary_entity_id,
        player_obligation=thread_req.player_obligation,
        urgency=thread_req.urgency,
    )

    return {
        "status": "created",
        "thread_id": thread.id,
        "type": thread.thread_type,
        "description": thread.description,
    }


@router.get("/threads")
async def get_threads(
    request: Request,
    active_only: bool = True,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get narrative threads."""
    if active_only:
        threads = memory.get_active_threads()
    else:
        threads = memory.experiential.get_active_threads()  # TODO: Add get_all_threads

    return {
        "count": len(threads),
        "threads": [
            {
                "id": t.id,
                "type": t.thread_type,
                "description": t.description,
                "stakes": t.stakes,
                "urgency": t.urgency,
                "player_obligation": t.player_obligation,
                "resolved": t.resolved,
            }
            for t in threads
        ]
    }


@router.post("/threads/{thread_id}/resolve")
async def resolve_thread(
    request: Request,
    thread_id: str,
    resolve_req: ResolveThreadRequest,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Mark a thread as resolved."""
    await memory.resolve_thread(
        thread_id=thread_id,
        resolution_summary=resolve_req.resolution_summary,
        echo_id=resolve_req.echo_id,
    )

    return {
        "status": "resolved",
        "thread_id": thread_id,
        "resolution": resolve_req.resolution_summary,
    }


# ============================================================
# SUMMARY ENDPOINTS
# ============================================================

@router.get("/summary")
async def get_memory_summary(
    request: Request,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get overall memory system statistics."""
    return memory.get_memory_summary()


@router.get("/reputation")
async def get_player_reputation(
    request: Request,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get summary of how the world sees the player."""
    return await memory.get_player_reputation_summary()


@router.get("/context")
async def get_narrative_context(
    request: Request,
    session_id: Optional[str] = None,
    location_id: Optional[str] = None,
    npc_ids: Optional[str] = None,  # Comma-separated
    memory: MemoryManager = Depends(get_memory_manager),
):
    """
    Get narrative context for DM response generation.

    Combines recent events, NPC impressions, beliefs, legends, and threads.
    """
    npc_list = npc_ids.split(",") if npc_ids else None

    context = await memory.get_narrative_context(
        session_id=session_id,
        location_id=location_id,
        npc_ids=npc_list,
        include_legends=True,
        include_threads=True,
    )

    return context
