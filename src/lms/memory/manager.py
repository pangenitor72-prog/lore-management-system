# src/lms/memory/manager.py
"""
Memory Manager - Orchestrator for the Three Memory Systems

The unified interface for:
1. Graph DB (Neo4j) - Canonical truth, entities, relationships
2. Vector DB - Semantic similarity, embeddings
3. Experiential Memory - Living memory, beliefs, impressions

This is where the world comes alive.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .models import (
    Echo, Whisper, AgentBelief, Impression, Legend, Thread,
    SalienceLevel, BeliefStrength, ImpressionValence, WhisperMutation
)
from .experiential import ExperientialMemory

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    The unified memory interface for the AI DM.

    Combines:
    - Neo4j: What IS true (canonical facts)
    - Vectors: What RELATES (semantic similarity)
    - Experiential: What is REMEMBERED (beliefs, impressions, echoes)

    Usage:
        memory = MemoryManager(neo4j_db, experiential_memory)

        # Record what happened
        memory.record_event(...)

        # Query what an NPC believes
        beliefs = memory.get_npc_beliefs(npc_id)

        # Get context for DM response
        context = memory.get_narrative_context(session_id, location_id)
    """

    def __init__(
        self,
        neo4j_db=None,
        experiential: Optional[ExperientialMemory] = None,
        embedding_service=None,
    ):
        """Initialize the memory manager with available backends."""
        self.neo4j = neo4j_db
        self.experiential = experiential or ExperientialMemory()
        self.embeddings = embedding_service
        logger.info("MemoryManager initialized")

    # ============================================================
    # EVENT RECORDING - When things happen in the game
    # ============================================================

    async def record_event(
        self,
        event_type: str,
        description: str,
        summary: str,
        session_id: Optional[str] = None,
        location_id: Optional[str] = None,
        participants: Optional[List[str]] = None,
        witnesses: Optional[List[str]] = None,
        player_involved: bool = False,
        salience: SalienceLevel = SalienceLevel.NOTABLE,
        emotional_weight: float = 0.5,
        narrative_weight: float = 0.5,
        arc_phase: Optional[str] = None,
        caused_by: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Echo:
        """
        Record something that happened in the game world.

        This creates an Echo - the fundamental unit of memory.
        Echoes can trigger:
        - Whisper creation (rumors spreading)
        - Belief updates (NPCs learning things)
        - Impression changes (how NPCs see the player)
        - Legend formation (if significant enough)

        Returns the created Echo.
        """
        echo = Echo(
            event_type=event_type,
            description=description,
            summary=summary,
            session_id=session_id,
            location_id=location_id,
            participants=participants or [],
            witnesses=witnesses or [],
            player_involved=player_involved,
            salience=salience,
            emotional_weight=emotional_weight,
            narrative_weight=narrative_weight,
            arc_phase=arc_phase,
            caused_by=caused_by,
            tags=tags or [],
        )

        self.experiential.record_echo(echo)

        # If player was involved and event is significant, update impressions
        if player_involved and salience in [SalienceLevel.SIGNIFICANT, SalienceLevel.LEGENDARY]:
            await self._update_witness_impressions(echo)

        # If notable enough, start rumors spreading
        if salience != SalienceLevel.ORDINARY and witnesses:
            await self._create_whisper_from_echo(echo)

        logger.info(f"Recorded event: {summary} (salience: {salience.value})")
        return echo

    async def _update_witness_impressions(self, echo: Echo) -> None:
        """Update impressions of witnesses based on event."""
        for witness_id in echo.witnesses:
            impression = self.experiential.get_impression(witness_id)

            if impression:
                # Update existing impression
                impression.key_memories.append(echo.id)
                impression.last_interaction = datetime.now(timezone.utc)
                impression.interaction_count += 1

                # Adjust based on event type
                if echo.event_type in ["rescue", "help", "gift"]:
                    impression.trust = min(1.0, impression.trust + 0.1)
                    impression.affection = min(1.0, impression.affection + 0.1)
                    if impression.valence == ImpressionValence.NEUTRAL:
                        impression.valence = ImpressionValence.FRIENDLY
                elif echo.event_type in ["threat", "attack", "betrayal"]:
                    impression.trust = max(0.0, impression.trust - 0.2)
                    impression.fear = min(1.0, impression.fear + 0.2)
                    impression.valence = ImpressionValence.FEARFUL
                elif echo.event_type in ["heroic", "legendary_deed"]:
                    impression.respect = min(1.0, impression.respect + 0.2)
                    impression.valence = ImpressionValence.REVERENT

                self.experiential.record_impression(impression)
            else:
                # Create new impression
                valence = ImpressionValence.NEUTRAL
                if echo.event_type in ["rescue", "help"]:
                    valence = ImpressionValence.GRATEFUL
                elif echo.event_type in ["threat", "attack"]:
                    valence = ImpressionValence.FEARFUL

                new_impression = Impression(
                    agent_id=witness_id,
                    valence=valence,
                    summary=f"Witnessed: {echo.summary}",
                    key_memories=[echo.id],
                )
                self.experiential.record_impression(new_impression)

    async def _create_whisper_from_echo(self, echo: Echo) -> Optional[Whisper]:
        """Create a whisper (rumor) from a significant event."""
        if not echo.witnesses:
            return None

        whisper = Whisper(
            source_echo_id=echo.id,
            original_content=echo.summary,
            current_content=echo.summary,
            origin_agent_id=echo.witnesses[0] if echo.witnesses else None,
            current_carriers=echo.witnesses[:3],  # First few witnesses carry it
            concerns_player=echo.player_involved,
        )

        # TODO: Record whisper to experiential store
        # self.experiential.record_whisper(whisper)

        logger.debug(f"Created whisper from echo: {echo.id}")
        return whisper

    # ============================================================
    # BELIEF MANAGEMENT - What NPCs think they know
    # ============================================================

    async def record_npc_belief(
        self,
        npc_id: str,
        content: str,
        subject_id: Optional[str] = None,
        subject_type: str = "general",
        source_type: str = "direct",
        source_agent_id: Optional[str] = None,
        confidence: float = 0.7,
        is_true: Optional[bool] = None,
    ) -> AgentBelief:
        """
        Record what an NPC believes about something.

        Beliefs are subjective - they may or may not be true.
        The DM can set is_true to track accuracy.
        """
        # Check if NPC already has a belief about this subject
        existing = None
        if subject_id:
            existing = self.experiential.get_agent_belief_about(npc_id, subject_id)

        if existing:
            # Update existing belief - either reinforce or create conflict
            if existing.content == content:
                self.experiential.reinforce_belief(existing.id)
                return existing
            else:
                # Conflicting belief - record challenge
                self.experiential.challenge_belief(existing.id)
                # Create new belief marked as conflicted
                belief_category = "CONFLICTED"
        else:
            belief_category = "SINGLE_HELD"

        belief = AgentBelief(
            agent_id=npc_id,
            subject_id=subject_id,
            subject_type=subject_type,
            content=content,
            is_true=is_true,
            source_type=source_type,
            source_agent_id=source_agent_id,
            confidence=confidence,
            belief_category=belief_category,
        )

        self.experiential.record_belief(belief)
        logger.debug(f"Recorded belief for {npc_id}: {content[:50]}...")
        return belief

    def get_npc_beliefs(self, npc_id: str) -> List[AgentBelief]:
        """Get all beliefs held by an NPC."""
        return self.experiential.get_agent_beliefs(npc_id)

    def get_npc_belief_about(self, npc_id: str, subject_id: str) -> Optional[AgentBelief]:
        """Get what an NPC believes about a specific subject."""
        return self.experiential.get_agent_belief_about(npc_id, subject_id)

    def get_world_beliefs_about(self, subject_id: str) -> List[AgentBelief]:
        """Get what various NPCs believe about something."""
        return self.experiential.get_beliefs_about(subject_id)

    # ============================================================
    # IMPRESSION MANAGEMENT - How NPCs see the player
    # ============================================================

    def get_npc_impression(self, npc_id: str) -> Optional[Impression]:
        """Get how an NPC sees the player."""
        return self.experiential.get_impression(npc_id)

    def get_all_impressions(self) -> List[Impression]:
        """Get all NPC impressions of the player."""
        return self.experiential.get_all_impressions()

    def get_friendly_npcs(self) -> List[Impression]:
        """Get NPCs who view the player positively."""
        positive = []
        for valence in [ImpressionValence.FRIENDLY, ImpressionValence.GRATEFUL, ImpressionValence.REVERENT]:
            positive.extend(self.experiential.get_impressions_by_valence(valence))
        return positive

    def get_hostile_npcs(self) -> List[Impression]:
        """Get NPCs who view the player negatively."""
        negative = []
        for valence in [ImpressionValence.HOSTILE, ImpressionValence.HATEFUL, ImpressionValence.WARY]:
            negative.extend(self.experiential.get_impressions_by_valence(valence))
        return negative

    # ============================================================
    # LEGEND MANAGEMENT - Player mythology
    # ============================================================

    async def create_legend(
        self,
        title: str,
        epithet: str,
        narrative: str,
        source_echo_ids: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        is_public: bool = True,
        hero_journey_stage: Optional[str] = None,
    ) -> Legend:
        """
        Create a legend from player deeds.

        Legends are the highest form of memory - they reshape
        how the world understands itself and the player.
        """
        legend = Legend(
            title=title,
            epithet=epithet,
            narrative=narrative,
            source_echo_ids=source_echo_ids or [],
            seed_session_id=session_id,
            is_public=is_public,
            hero_journey_stage=hero_journey_stage,
            common_phrases=[f"Aren't you {epithet}?", f"I've heard of {title}..."],
        )

        self.experiential.record_legend(legend)
        logger.info(f"Created legend: {title}")
        return legend

    def get_player_legends(self) -> List[Legend]:
        """Get all legends about the player."""
        return self.experiential.get_legends()

    def get_public_legends(self) -> List[Legend]:
        """Get publicly known legends."""
        return self.experiential.get_public_legends()

    # ============================================================
    # THREAD MANAGEMENT - Narrative tensions
    # ============================================================

    async def create_thread(
        self,
        thread_type: str,
        description: str,
        stakes: str,
        primary_entity_id: Optional[str] = None,
        player_obligation: bool = False,
        urgency: float = 0.5,
        session_id: Optional[str] = None,
        source_echo_id: Optional[str] = None,
    ) -> Thread:
        """
        Create an unresolved narrative thread.

        Threads are open loops - questions, debts, promises,
        conflicts that await resolution.
        """
        thread = Thread(
            thread_type=thread_type,
            description=description,
            stakes=stakes,
            primary_entity_id=primary_entity_id,
            player_obligation=player_obligation,
            urgency=urgency,
            created_session_id=session_id,
            created_by_echo_id=source_echo_id,
        )

        self.experiential.record_thread(thread)
        logger.info(f"Created thread: {description[:50]}...")
        return thread

    def get_active_threads(self) -> List[Thread]:
        """Get all unresolved narrative threads."""
        return self.experiential.get_active_threads()

    async def resolve_thread(self, thread_id: str, resolution_summary: str, echo_id: Optional[str] = None) -> None:
        """Mark a thread as resolved."""
        self.experiential.resolve_thread(thread_id, echo_id or "", resolution_summary)

    # ============================================================
    # CONTEXT BUILDING - For DM responses
    # ============================================================

    async def get_narrative_context(
        self,
        session_id: Optional[str] = None,
        location_id: Optional[str] = None,
        npc_ids: Optional[List[str]] = None,
        include_legends: bool = True,
        include_threads: bool = True,
    ) -> Dict[str, Any]:
        """
        Build context for the DM to generate responses.

        Combines:
        - Recent events (echoes)
        - NPC beliefs and impressions
        - Active legends
        - Unresolved threads
        - Canonical facts from Neo4j
        """
        context = {
            "recent_echoes": [],
            "npc_impressions": {},
            "npc_beliefs": {},
            "player_legends": [],
            "active_threads": [],
            "canonical_facts": {},
        }

        # Get recent echoes
        if session_id:
            context["recent_echoes"] = [
                {"summary": e.summary, "type": e.event_type, "salience": e.salience.value}
                for e in self.experiential.get_echoes_for_session(session_id)[-10:]
            ]

        # Get NPC context
        if npc_ids:
            for npc_id in npc_ids:
                impression = self.get_npc_impression(npc_id)
                if impression:
                    context["npc_impressions"][npc_id] = {
                        "valence": impression.valence.value,
                        "trust": impression.trust,
                        "respect": impression.respect,
                        "will_help": impression.will_help,
                        "forms_of_address": impression.forms_of_address,
                    }

                beliefs = self.get_npc_beliefs(npc_id)
                if beliefs:
                    context["npc_beliefs"][npc_id] = [
                        {"content": b.content, "confidence": b.confidence}
                        for b in beliefs[:5]  # Top 5 beliefs
                    ]

        # Get legends
        if include_legends:
            legends = self.get_public_legends()
            context["player_legends"] = [
                {"title": l.title, "epithet": l.epithet}
                for l in legends
            ]

        # Get threads
        if include_threads:
            threads = self.get_active_threads()
            context["active_threads"] = [
                {"type": t.thread_type, "description": t.description, "urgency": t.urgency}
                for t in threads[:5]  # Top 5 by urgency
            ]

        # Get canonical facts from Neo4j if available
        if self.neo4j and location_id:
            try:
                result = await self.neo4j.execute("""
                    MATCH (l:Location {canon_id: $location_id})
                    OPTIONAL MATCH (l)<-[:LOCATED_IN]-(e:Entity)
                    RETURN l.name as location_name, l.description as location_desc,
                           collect(e.name) as entities_present
                """, {"location_id": location_id})

                if result:
                    context["canonical_facts"]["location"] = result[0] if result else {}
            except Exception as e:
                logger.warning(f"Failed to get canonical facts: {e}")

        return context

    # ============================================================
    # STATS AND OVERVIEW
    # ============================================================

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get a summary of the world's memory state."""
        return self.experiential.get_world_state_summary()

    async def get_player_reputation_summary(self) -> Dict[str, Any]:
        """Get a summary of how the world sees the player."""
        impressions = self.get_all_impressions()
        legends = self.get_player_legends()

        # Calculate averages
        if impressions:
            avg_trust = sum(i.trust for i in impressions) / len(impressions)
            avg_respect = sum(i.respect for i in impressions) / len(impressions)
            avg_fear = sum(i.fear for i in impressions) / len(impressions)
        else:
            avg_trust = avg_respect = avg_fear = 0.5

        # Count valences
        valence_counts = {}
        for imp in impressions:
            valence_counts[imp.valence.value] = valence_counts.get(imp.valence.value, 0) + 1

        return {
            "npcs_met": len(impressions),
            "average_trust": round(avg_trust, 2),
            "average_respect": round(avg_respect, 2),
            "average_fear": round(avg_fear, 2),
            "valence_distribution": valence_counts,
            "legend_count": len(legends),
            "epithets": [l.epithet for l in legends],
        }
