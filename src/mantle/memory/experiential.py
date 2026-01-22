# src/lms/memory/experiential.py
"""
Experiential Memory Store

SQLite-backed persistence for the living memory of the world.
This is the third memory layer - what the world REMEMBERS.

Design principles:
- Durable: survives restarts, can be backed up
- Queryable: find beliefs, impressions, echoes by various criteria
- Observable: DM can inspect and override
- Temporal: tracks when things were learned/changed
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .models import (
    Echo, Whisper, AgentBelief, Impression, Legend, Thread,
    SalienceLevel, BeliefStrength, ImpressionValence,
    calculate_decay
)

logger = logging.getLogger(__name__)


class ExperientialMemory:
    """
    The living memory of the world.

    Stores:
    - Echoes: events that happened
    - Whispers: rumors spreading through the world
    - Beliefs: what agents think they know
    - Impressions: how NPCs perceive the player
    - Legends: player deeds that became mythology
    - Threads: unresolved narrative tensions
    """

    def __init__(self, db_path: str = "data/experiential_memory.db"):
        """Initialize the memory store."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"ExperientialMemory initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Create tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Echoes - events that happened
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS echoes (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    session_id TEXT,
                    location_id TEXT,
                    timestamp TEXT NOT NULL,
                    in_world_time TEXT,
                    participants TEXT,
                    witnesses TEXT,
                    player_involved INTEGER DEFAULT 0,
                    salience TEXT DEFAULT 'notable',
                    emotional_weight REAL DEFAULT 0.5,
                    narrative_weight REAL DEFAULT 0.5,
                    caused_by TEXT,
                    consequences TEXT,
                    related_entities TEXT,
                    tags TEXT,
                    arc_phase TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Whispers - rumors spreading
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whispers (
                    id TEXT PRIMARY KEY,
                    source_echo_id TEXT,
                    original_content TEXT NOT NULL,
                    current_content TEXT NOT NULL,
                    mutation TEXT DEFAULT 'preserved',
                    mutation_history TEXT,
                    truth_drift REAL DEFAULT 0.0,
                    origin_agent_id TEXT,
                    current_carriers TEXT,
                    spread_count INTEGER DEFAULT 1,
                    regions_reached TEXT,
                    factions_aware TEXT,
                    created_at TEXT NOT NULL,
                    last_spread TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    concerns_player INTEGER DEFAULT 0,
                    player_reputation_impact REAL DEFAULT 0.0,
                    FOREIGN KEY (source_echo_id) REFERENCES echoes(id)
                )
            """)

            # Agent Beliefs - what NPCs think they know
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_beliefs (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    subject_id TEXT,
                    subject_type TEXT DEFAULT 'general',
                    content TEXT NOT NULL,
                    is_true INTEGER,
                    strength TEXT DEFAULT 'confident',
                    confidence REAL DEFAULT 0.7,
                    emotional_investment REAL DEFAULT 0.5,
                    source_type TEXT DEFAULT 'direct',
                    source_agent_id TEXT,
                    source_echo_id TEXT,
                    source_whisper_id TEXT,
                    formed_at TEXT NOT NULL,
                    last_reinforced TEXT NOT NULL,
                    times_reinforced INTEGER DEFAULT 1,
                    last_challenged TEXT,
                    times_challenged INTEGER DEFAULT 0,
                    belief_category TEXT DEFAULT 'SINGLE_HELD',
                    FOREIGN KEY (source_echo_id) REFERENCES echoes(id),
                    FOREIGN KEY (source_whisper_id) REFERENCES whispers(id)
                )
            """)

            # Impressions - how NPCs see the player
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS impressions (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL UNIQUE,
                    valence TEXT DEFAULT 'neutral',
                    intensity REAL DEFAULT 0.5,
                    summary TEXT,
                    key_memories TEXT,
                    respect REAL DEFAULT 0.5,
                    trust REAL DEFAULT 0.5,
                    fear REAL DEFAULT 0.0,
                    affection REAL DEFAULT 0.5,
                    will_help INTEGER DEFAULT 1,
                    will_trade INTEGER DEFAULT 1,
                    will_share_secrets INTEGER DEFAULT 0,
                    will_betray INTEGER DEFAULT 0,
                    first_encounter TEXT NOT NULL,
                    last_interaction TEXT NOT NULL,
                    interaction_count INTEGER DEFAULT 1,
                    forms_of_address TEXT
                )
            """)

            # Legends - player mythology
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS legends (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    epithet TEXT NOT NULL,
                    narrative TEXT NOT NULL,
                    source_echo_ids TEXT,
                    seed_session_id TEXT,
                    is_public INTEGER DEFAULT 1,
                    known_by_factions TEXT,
                    known_in_regions TEXT,
                    accuracy REAL DEFAULT 1.0,
                    embellishment_level REAL DEFAULT 0.0,
                    reputation_modifier REAL DEFAULT 0.0,
                    fear_modifier REAL DEFAULT 0.0,
                    respect_modifier REAL DEFAULT 0.0,
                    salience TEXT DEFAULT 'legendary',
                    created_at TEXT NOT NULL,
                    hero_journey_stage TEXT,
                    common_phrases TEXT
                )
            """)

            # Threads - unresolved narrative tensions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    thread_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    stakes TEXT NOT NULL,
                    created_by_echo_id TEXT,
                    created_at TEXT NOT NULL,
                    created_session_id TEXT,
                    primary_entity_id TEXT,
                    secondary_entities TEXT,
                    player_obligation INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    urgency REAL DEFAULT 0.5,
                    times_referenced INTEGER DEFAULT 0,
                    last_referenced TEXT,
                    resolved INTEGER DEFAULT 0,
                    resolution_echo_id TEXT,
                    resolution_summary TEXT,
                    FOREIGN KEY (created_by_echo_id) REFERENCES echoes(id)
                )
            """)

            # Indices for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_echoes_session ON echoes(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_echoes_player ON echoes(player_involved)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_beliefs_agent ON agent_beliefs(agent_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_beliefs_subject ON agent_beliefs(subject_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_impressions_agent ON impressions(agent_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_whispers_active ON whispers(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_threads_active ON threads(is_active)")

    # ============================================================
    # ECHO OPERATIONS
    # ============================================================

    def record_echo(self, echo: Echo) -> str:
        """Record an event that happened."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO echoes (
                    id, event_type, description, summary, session_id, location_id,
                    timestamp, in_world_time, participants, witnesses, player_involved,
                    salience, emotional_weight, narrative_weight, caused_by,
                    consequences, related_entities, tags, arc_phase
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                echo.id, echo.event_type, echo.description, echo.summary,
                echo.session_id, echo.location_id, echo.timestamp.isoformat(),
                echo.in_world_time, json.dumps(echo.participants),
                json.dumps(echo.witnesses), int(echo.player_involved),
                echo.salience.value, echo.emotional_weight, echo.narrative_weight,
                echo.caused_by, json.dumps(echo.consequences),
                json.dumps(echo.related_entities), json.dumps(echo.tags), echo.arc_phase
            ))
            logger.info(f"Recorded echo: {echo.id} - {echo.summary}")
            return echo.id

    def get_echo(self, echo_id: str) -> Optional[Echo]:
        """Get a specific echo by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM echoes WHERE id = ?", (echo_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_echo(row)
        return None

    def get_echoes_for_session(self, session_id: str) -> List[Echo]:
        """Get all echoes from a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM echoes WHERE session_id = ? ORDER BY timestamp",
                (session_id,)
            )
            return [self._row_to_echo(row) for row in cursor.fetchall()]

    def get_player_echoes(self, limit: int = 50) -> List[Echo]:
        """Get echoes involving the player."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM echoes WHERE player_involved = 1 ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [self._row_to_echo(row) for row in cursor.fetchall()]

    def search_echoes(
        self,
        event_type: Optional[str] = None,
        location_id: Optional[str] = None,
        participant_id: Optional[str] = None,
        min_salience: Optional[SalienceLevel] = None,
        limit: int = 20
    ) -> List[Echo]:
        """Search echoes by various criteria."""
        query = "SELECT * FROM echoes WHERE 1=1"
        params = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if location_id:
            query += " AND location_id = ?"
            params.append(location_id)
        if participant_id:
            query += " AND participants LIKE ?"
            params.append(f'%"{participant_id}"%')
        if min_salience:
            salience_order = ['faded', 'ordinary', 'notable', 'significant', 'legendary']
            min_idx = salience_order.index(min_salience.value)
            allowed = salience_order[min_idx:]
            placeholders = ','.join('?' * len(allowed))
            query += f" AND salience IN ({placeholders})"
            params.extend(allowed)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_echo(row) for row in cursor.fetchall()]

    def _row_to_echo(self, row: sqlite3.Row) -> Echo:
        """Convert database row to Echo model."""
        return Echo(
            id=row['id'],
            event_type=row['event_type'],
            description=row['description'],
            summary=row['summary'],
            session_id=row['session_id'],
            location_id=row['location_id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            in_world_time=row['in_world_time'],
            participants=json.loads(row['participants'] or '[]'),
            witnesses=json.loads(row['witnesses'] or '[]'),
            player_involved=bool(row['player_involved']),
            salience=SalienceLevel(row['salience']),
            emotional_weight=row['emotional_weight'],
            narrative_weight=row['narrative_weight'],
            caused_by=row['caused_by'],
            consequences=json.loads(row['consequences'] or '[]'),
            related_entities=json.loads(row['related_entities'] or '[]'),
            tags=json.loads(row['tags'] or '[]'),
            arc_phase=row['arc_phase']
        )

    # ============================================================
    # WHISPER OPERATIONS
    # ============================================================

    def record_whisper(self, whisper: Whisper) -> str:
        """Record a rumor spreading through the world."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO whispers (
                    id, source_echo_id, original_content, current_content,
                    mutation, mutation_history, truth_drift, origin_agent_id,
                    current_carriers, spread_count, regions_reached, factions_aware,
                    created_at, last_spread, is_active, concerns_player,
                    player_reputation_impact
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                whisper.id, whisper.source_echo_id, whisper.original_content,
                whisper.current_content, whisper.mutation.value,
                json.dumps(whisper.mutation_history), whisper.truth_drift,
                whisper.origin_agent_id, json.dumps(whisper.current_carriers),
                whisper.spread_count, json.dumps(whisper.regions_reached),
                json.dumps(whisper.factions_aware), whisper.created_at.isoformat(),
                whisper.last_spread.isoformat(), int(whisper.is_active),
                int(whisper.concerns_player), whisper.player_reputation_impact
            ))
            logger.info(f"Recorded whisper: {whisper.current_content[:50]}...")
            return whisper.id

    def get_whisper(self, whisper_id: str) -> Optional[Whisper]:
        """Get a specific whisper by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM whispers WHERE id = ?", (whisper_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_whisper(row)
        return None

    def get_active_whispers(self) -> List[Whisper]:
        """Get all currently active rumors."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM whispers WHERE is_active = 1 ORDER BY last_spread DESC"
            )
            return [self._row_to_whisper(row) for row in cursor.fetchall()]

    def _row_to_whisper(self, row: sqlite3.Row) -> Whisper:
        """Convert database row to Whisper model."""
        return Whisper(
            id=row['id'],
            source_echo_id=row['source_echo_id'],
            original_content=row['original_content'],
            current_content=row['current_content'],
            mutation=WhisperMutation(row['mutation']),
            mutation_history=json.loads(row['mutation_history'] or '[]'),
            truth_drift=row['truth_drift'],
            origin_agent_id=row['origin_agent_id'],
            current_carriers=json.loads(row['current_carriers'] or '[]'),
            spread_count=row['spread_count'],
            regions_reached=json.loads(row['regions_reached'] or '[]'),
            factions_aware=json.loads(row['factions_aware'] or '[]'),
            created_at=datetime.fromisoformat(row['created_at']),
            last_spread=datetime.fromisoformat(row['last_spread']),
            is_active=bool(row['is_active']),
            concerns_player=bool(row['concerns_player']),
            player_reputation_impact=row['player_reputation_impact']
        )

    # ============================================================
    # BELIEF OPERATIONS
    # ============================================================

    def record_belief(self, belief: AgentBelief) -> str:
        """Record what an agent believes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO agent_beliefs (
                    id, agent_id, subject_id, subject_type, content, is_true,
                    strength, confidence, emotional_investment, source_type,
                    source_agent_id, source_echo_id, source_whisper_id,
                    formed_at, last_reinforced, times_reinforced,
                    last_challenged, times_challenged, belief_category
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                belief.id, belief.agent_id, belief.subject_id, belief.subject_type,
                belief.content, belief.is_true if belief.is_true is not None else None,
                belief.strength.value, belief.confidence, belief.emotional_investment,
                belief.source_type, belief.source_agent_id, belief.source_echo_id,
                belief.source_whisper_id, belief.formed_at.isoformat(),
                belief.last_reinforced.isoformat(), belief.times_reinforced,
                belief.last_challenged.isoformat() if belief.last_challenged else None,
                belief.times_challenged, belief.belief_category
            ))
            logger.debug(f"Recorded belief for agent {belief.agent_id}: {belief.content[:50]}...")
            return belief.id

    def get_agent_beliefs(self, agent_id: str) -> List[AgentBelief]:
        """Get all beliefs held by an agent."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM agent_beliefs WHERE agent_id = ?",
                (agent_id,)
            )
            return [self._row_to_belief(row) for row in cursor.fetchall()]

    def get_beliefs_about(self, subject_id: str) -> List[AgentBelief]:
        """Get what various agents believe about a subject."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM agent_beliefs WHERE subject_id = ?",
                (subject_id,)
            )
            return [self._row_to_belief(row) for row in cursor.fetchall()]

    def get_agent_belief_about(self, agent_id: str, subject_id: str) -> Optional[AgentBelief]:
        """Get what a specific agent believes about a specific subject."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM agent_beliefs WHERE agent_id = ? AND subject_id = ?",
                (agent_id, subject_id)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_belief(row)
        return None

    def reinforce_belief(self, belief_id: str) -> None:
        """Strengthen an existing belief."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE agent_beliefs
                SET times_reinforced = times_reinforced + 1,
                    last_reinforced = ?,
                    confidence = MIN(1.0, confidence + 0.1)
                WHERE id = ?
            """, (now, belief_id))

    def challenge_belief(self, belief_id: str) -> None:
        """Record that a belief was challenged."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE agent_beliefs
                SET times_challenged = times_challenged + 1,
                    last_challenged = ?,
                    confidence = MAX(0.0, confidence - 0.1)
                WHERE id = ?
            """, (now, belief_id))

    def _row_to_belief(self, row: sqlite3.Row) -> AgentBelief:
        """Convert database row to AgentBelief model."""
        return AgentBelief(
            id=row['id'],
            agent_id=row['agent_id'],
            subject_id=row['subject_id'],
            subject_type=row['subject_type'],
            content=row['content'],
            is_true=bool(row['is_true']) if row['is_true'] is not None else None,
            strength=BeliefStrength(row['strength']),
            confidence=row['confidence'],
            emotional_investment=row['emotional_investment'],
            source_type=row['source_type'],
            source_agent_id=row['source_agent_id'],
            source_echo_id=row['source_echo_id'],
            source_whisper_id=row['source_whisper_id'],
            formed_at=datetime.fromisoformat(row['formed_at']),
            last_reinforced=datetime.fromisoformat(row['last_reinforced']),
            times_reinforced=row['times_reinforced'],
            last_challenged=datetime.fromisoformat(row['last_challenged']) if row['last_challenged'] else None,
            times_challenged=row['times_challenged'],
            belief_category=row['belief_category']
        )

    # ============================================================
    # IMPRESSION OPERATIONS
    # ============================================================

    def record_impression(self, impression: Impression) -> str:
        """Record or update how an NPC sees the player."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO impressions (
                    id, agent_id, valence, intensity, summary, key_memories,
                    respect, trust, fear, affection, will_help, will_trade,
                    will_share_secrets, will_betray, first_encounter,
                    last_interaction, interaction_count, forms_of_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                impression.id, impression.agent_id, impression.valence.value,
                impression.intensity, impression.summary,
                json.dumps(impression.key_memories), impression.respect,
                impression.trust, impression.fear, impression.affection,
                int(impression.will_help), int(impression.will_trade),
                int(impression.will_share_secrets), int(impression.will_betray),
                impression.first_encounter.isoformat(),
                impression.last_interaction.isoformat(),
                impression.interaction_count, json.dumps(impression.forms_of_address)
            ))
            logger.info(f"Recorded impression from {impression.agent_id}: {impression.valence.value}")
            return impression.id

    def get_impression(self, agent_id: str) -> Optional[Impression]:
        """Get how an NPC sees the player."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM impressions WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_impression(row)
        return None

    def get_all_impressions(self) -> List[Impression]:
        """Get all NPC impressions of the player."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM impressions ORDER BY last_interaction DESC")
            return [self._row_to_impression(row) for row in cursor.fetchall()]

    def get_impressions_by_valence(self, valence: ImpressionValence) -> List[Impression]:
        """Get impressions filtered by emotional tone."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM impressions WHERE valence = ?",
                (valence.value,)
            )
            return [self._row_to_impression(row) for row in cursor.fetchall()]

    def _row_to_impression(self, row: sqlite3.Row) -> Impression:
        """Convert database row to Impression model."""
        return Impression(
            id=row['id'],
            agent_id=row['agent_id'],
            valence=ImpressionValence(row['valence']),
            intensity=row['intensity'],
            summary=row['summary'],
            key_memories=json.loads(row['key_memories'] or '[]'),
            respect=row['respect'],
            trust=row['trust'],
            fear=row['fear'],
            affection=row['affection'],
            will_help=bool(row['will_help']),
            will_trade=bool(row['will_trade']),
            will_share_secrets=bool(row['will_share_secrets']),
            will_betray=bool(row['will_betray']),
            first_encounter=datetime.fromisoformat(row['first_encounter']),
            last_interaction=datetime.fromisoformat(row['last_interaction']),
            interaction_count=row['interaction_count'],
            forms_of_address=json.loads(row['forms_of_address'] or '["stranger"]')
        )

    # ============================================================
    # LEGEND OPERATIONS
    # ============================================================

    def record_legend(self, legend: Legend) -> str:
        """Record a player deed that became legend."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO legends (
                    id, title, epithet, narrative, source_echo_ids,
                    seed_session_id, is_public, known_by_factions,
                    known_in_regions, accuracy, embellishment_level,
                    reputation_modifier, fear_modifier, respect_modifier,
                    salience, created_at, hero_journey_stage, common_phrases
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                legend.id, legend.title, legend.epithet, legend.narrative,
                json.dumps(legend.source_echo_ids), legend.seed_session_id,
                int(legend.is_public), json.dumps(legend.known_by_factions),
                json.dumps(legend.known_in_regions), legend.accuracy,
                legend.embellishment_level, legend.reputation_modifier,
                legend.fear_modifier, legend.respect_modifier,
                legend.salience.value, legend.created_at.isoformat(),
                legend.hero_journey_stage, json.dumps(legend.common_phrases)
            ))
            logger.info(f"Recorded legend: {legend.title}")
            return legend.id

    def get_legends(self) -> List[Legend]:
        """Get all player legends."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM legends ORDER BY created_at DESC")
            return [self._row_to_legend(row) for row in cursor.fetchall()]

    def get_public_legends(self) -> List[Legend]:
        """Get publicly known legends."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM legends WHERE is_public = 1")
            return [self._row_to_legend(row) for row in cursor.fetchall()]

    def _row_to_legend(self, row: sqlite3.Row) -> Legend:
        """Convert database row to Legend model."""
        return Legend(
            id=row['id'],
            title=row['title'],
            epithet=row['epithet'],
            narrative=row['narrative'],
            source_echo_ids=json.loads(row['source_echo_ids'] or '[]'),
            seed_session_id=row['seed_session_id'],
            is_public=bool(row['is_public']),
            known_by_factions=json.loads(row['known_by_factions'] or '[]'),
            known_in_regions=json.loads(row['known_in_regions'] or '[]'),
            accuracy=row['accuracy'],
            embellishment_level=row['embellishment_level'],
            reputation_modifier=row['reputation_modifier'],
            fear_modifier=row['fear_modifier'],
            respect_modifier=row['respect_modifier'],
            salience=SalienceLevel(row['salience']),
            created_at=datetime.fromisoformat(row['created_at']),
            hero_journey_stage=row['hero_journey_stage'],
            common_phrases=json.loads(row['common_phrases'] or '[]')
        )

    # ============================================================
    # THREAD OPERATIONS
    # ============================================================

    def record_thread(self, thread: Thread) -> str:
        """Record an unresolved narrative thread."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO threads (
                    id, thread_type, description, stakes, created_by_echo_id,
                    created_at, created_session_id, primary_entity_id,
                    secondary_entities, player_obligation, is_active, urgency,
                    times_referenced, last_referenced, resolved,
                    resolution_echo_id, resolution_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                thread.id, thread.thread_type, thread.description, thread.stakes,
                thread.created_by_echo_id, thread.created_at.isoformat(),
                thread.created_session_id, thread.primary_entity_id,
                json.dumps(thread.secondary_entities), int(thread.player_obligation),
                int(thread.is_active), thread.urgency, thread.times_referenced,
                thread.last_referenced.isoformat() if thread.last_referenced else None,
                int(thread.resolved), thread.resolution_echo_id, thread.resolution_summary
            ))
            logger.info(f"Recorded thread: {thread.description[:50]}...")
            return thread.id

    def get_active_threads(self) -> List[Thread]:
        """Get all unresolved narrative threads."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM threads WHERE is_active = 1 AND resolved = 0 ORDER BY urgency DESC"
            )
            return [self._row_to_thread(row) for row in cursor.fetchall()]

    def resolve_thread(self, thread_id: str, echo_id: str, summary: str) -> None:
        """Mark a thread as resolved."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE threads
                SET resolved = 1, resolution_echo_id = ?, resolution_summary = ?
                WHERE id = ?
            """, (echo_id, summary, thread_id))
            logger.info(f"Resolved thread {thread_id}: {summary}")

    def _row_to_thread(self, row: sqlite3.Row) -> Thread:
        """Convert database row to Thread model."""
        return Thread(
            id=row['id'],
            thread_type=row['thread_type'],
            description=row['description'],
            stakes=row['stakes'],
            created_by_echo_id=row['created_by_echo_id'],
            created_at=datetime.fromisoformat(row['created_at']),
            created_session_id=row['created_session_id'],
            primary_entity_id=row['primary_entity_id'],
            secondary_entities=json.loads(row['secondary_entities'] or '[]'),
            player_obligation=bool(row['player_obligation']),
            is_active=bool(row['is_active']),
            urgency=row['urgency'],
            times_referenced=row['times_referenced'],
            last_referenced=datetime.fromisoformat(row['last_referenced']) if row['last_referenced'] else None,
            resolved=bool(row['resolved']),
            resolution_echo_id=row['resolution_echo_id'],
            resolution_summary=row['resolution_summary']
        )

    # ============================================================
    # AGGREGATE QUERIES
    # ============================================================

    def get_world_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the world's memory state."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM echoes")
            echo_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM echoes WHERE player_involved = 1")
            player_echo_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM agent_beliefs")
            belief_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM impressions")
            impression_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM legends")
            legend_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM threads WHERE is_active = 1 AND resolved = 0")
            active_thread_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM whispers WHERE is_active = 1")
            active_whisper_count = cursor.fetchone()[0]

            return {
                "total_echoes": echo_count,
                "player_echoes": player_echo_count,
                "agent_beliefs": belief_count,
                "npc_impressions": impression_count,
                "player_legends": legend_count,
                "active_threads": active_thread_count,
                "active_whispers": active_whisper_count,
            }
