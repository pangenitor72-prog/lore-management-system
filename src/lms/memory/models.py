# src/lms/memory/models.py
"""
Memory Data Models

These structures capture the living memory of a world:
- Not just facts, but how facts are remembered
- Not just events, but how events echo through time
- Not just relationships, but how they're perceived
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


# ============================================================
# ENUMS
# ============================================================

class SalienceLevel(str, Enum):
    """How memorable/important something is."""
    LEGENDARY = "legendary"      # Never fades - world-shaping events
    SIGNIFICANT = "significant"  # Major events - slow decay
    NOTABLE = "notable"          # Worth remembering - moderate decay
    ORDINARY = "ordinary"        # Background noise - fast decay
    FADED = "faded"              # Nearly forgotten - may resurface


class BeliefStrength(str, Enum):
    """How strongly an agent holds a belief."""
    CERTAIN = "certain"          # Would stake their life on it
    CONFIDENT = "confident"      # Pretty sure
    UNCERTAIN = "uncertain"      # Heard it, not sure
    DOUBTFUL = "doubtful"        # Skeptical but aware
    REJECTED = "rejected"        # Actively disbelieves


class WhisperMutation(str, Enum):
    """How rumors transform as they spread."""
    PRESERVED = "preserved"      # Stayed accurate
    AMPLIFIED = "amplified"      # Exaggerated
    DIMINISHED = "diminished"    # Downplayed
    TWISTED = "twisted"          # Core meaning changed
    MYTHOLOGIZED = "mythologized"  # Became legend


class ImpressionValence(str, Enum):
    """Emotional tone of an impression."""
    REVERENT = "reverent"        # Awe, worship
    GRATEFUL = "grateful"        # Positive debt
    FRIENDLY = "friendly"        # Warm
    NEUTRAL = "neutral"          # No strong feeling
    WARY = "wary"                # Cautious
    HOSTILE = "hostile"          # Antagonistic
    FEARFUL = "fearful"          # Afraid
    HATEFUL = "hateful"          # Deep enmity


# ============================================================
# CORE MEMORY STRUCTURES
# ============================================================

class Echo(BaseModel):
    """
    An event that happened and reverberates through the world.

    Echoes are the raw material of memory - things that actually occurred.
    They can be witnessed, heard about, or discovered later.
    """
    id: str = Field(default_factory=lambda: f"echo_{uuid.uuid4().hex[:12]}")

    # What happened
    event_type: str                          # "combat", "dialogue", "discovery", "betrayal", etc.
    description: str                         # The narrative of what occurred
    summary: str                             # One-line version for quick reference

    # When and where
    session_id: Optional[str] = None         # Game session this occurred in
    location_id: Optional[str] = None        # Where it happened (canon_id)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    in_world_time: Optional[str] = None      # "Third day of the Harvest Moon"

    # Who was involved
    participants: List[str] = Field(default_factory=list)  # canon_ids of involved entities
    witnesses: List[str] = Field(default_factory=list)     # canon_ids of those who saw
    player_involved: bool = False            # Was the player part of this?

    # Significance
    salience: SalienceLevel = SalienceLevel.NOTABLE
    emotional_weight: float = 0.5            # 0.0-1.0, how emotionally charged
    narrative_weight: float = 0.5            # 0.0-1.0, story importance

    # Connections
    caused_by: Optional[str] = None          # Echo ID that led to this
    consequences: List[str] = Field(default_factory=list)  # Echo IDs this caused
    related_entities: List[str] = Field(default_factory=list)  # Affected canon_ids

    # Metadata
    tags: List[str] = Field(default_factory=list)
    arc_phase: Optional[str] = None          # Hero's Journey phase when this occurred


class Whisper(BaseModel):
    """
    A rumor or piece of information spreading through the world.

    Whispers mutate as they travel - growing, shrinking, or twisting.
    They connect Echoes (real events) to Beliefs (what agents think).
    """
    id: str = Field(default_factory=lambda: f"whisper_{uuid.uuid4().hex[:12]}")

    # Origin
    source_echo_id: Optional[str] = None     # The Echo this rumor is about (if any)
    original_content: str                    # What was originally said/happened
    current_content: str                     # How the rumor currently sounds

    # Mutation tracking
    mutation: WhisperMutation = WhisperMutation.PRESERVED
    mutation_history: List[Dict[str, Any]] = Field(default_factory=list)
    truth_drift: float = 0.0                 # -1.0 (opposite) to 1.0 (accurate)

    # Spread
    origin_agent_id: Optional[str] = None    # Who started this rumor
    current_carriers: List[str] = Field(default_factory=list)  # Who knows this now
    spread_count: int = 1                    # How many times it's been passed

    # Reach
    regions_reached: List[str] = Field(default_factory=list)  # Location canon_ids
    factions_aware: List[str] = Field(default_factory=list)   # Faction canon_ids

    # Vitality
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_spread: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True                   # Still spreading?

    # About the player?
    concerns_player: bool = False
    player_reputation_impact: float = 0.0    # -1.0 to 1.0


class AgentBelief(BaseModel):
    """
    What an agent believes about something.

    Beliefs are subjective - they may be true, false, or partially accurate.
    They're shaped by what the agent has witnessed, heard, or inferred.
    """
    id: str = Field(default_factory=lambda: f"belief_{uuid.uuid4().hex[:12]}")

    # Who believes what about what
    agent_id: str                            # canon_id of the believing agent
    subject_id: Optional[str] = None         # canon_id of what this is about
    subject_type: str = "general"            # "entity", "event", "claim", "relationship"

    # The belief itself
    content: str                             # What they believe
    is_true: Optional[bool] = None           # None = unknown, for DM reference

    # Strength and certainty
    strength: BeliefStrength = BeliefStrength.CONFIDENT
    confidence: float = 0.7                  # 0.0-1.0
    emotional_investment: float = 0.5        # How much they care

    # Sources
    source_type: str = "direct"              # "direct", "hearsay", "inference", "assumption"
    source_agent_id: Optional[str] = None    # Who told them (if hearsay)
    source_echo_id: Optional[str] = None     # What event formed this belief
    source_whisper_id: Optional[str] = None  # What rumor informed this

    # Temporal
    formed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_reinforced: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    times_reinforced: int = 1
    last_challenged: Optional[datetime] = None
    times_challenged: int = 0

    # For belief conflict resolution (AIRPG integration)
    belief_category: str = "SINGLE_HELD"     # SINGLE_HELD, CONFLICTED, TRANSFORMED


class Impression(BaseModel):
    """
    How an NPC perceives and remembers the player.

    Impressions shape how NPCs interact with the player:
    - A grateful innkeeper offers free rooms
    - A fearful guard looks the other way
    - A hateful rival plots revenge
    """
    id: str = Field(default_factory=lambda: f"impression_{uuid.uuid4().hex[:12]}")

    # Who holds this impression
    agent_id: str                            # canon_id of the NPC

    # The impression itself
    valence: ImpressionValence = ImpressionValence.NEUTRAL
    intensity: float = 0.5                   # 0.0-1.0, how strongly they feel

    # What shapes this impression
    summary: str                             # "Saved my daughter from bandits"
    key_memories: List[str] = Field(default_factory=list)  # Echo IDs that formed this

    # Reputation components
    respect: float = 0.5                     # 0.0-1.0
    trust: float = 0.5                       # 0.0-1.0
    fear: float = 0.0                        # 0.0-1.0
    affection: float = 0.5                   # 0.0-1.0

    # Behavioral impacts
    will_help: bool = True                   # Would they aid the player?
    will_trade: bool = True                  # Would they do business?
    will_share_secrets: bool = False         # Would they reveal hidden info?
    will_betray: bool = False                # Might they turn on the player?

    # Temporal
    first_encounter: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_interaction: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    interaction_count: int = 1

    # What they call the player (evolves with relationship)
    forms_of_address: List[str] = Field(default_factory=lambda: ["stranger", "traveler"])


class Legend(BaseModel):
    """
    A player deed that has become part of world mythology.

    Legends are the highest form of Echo - events so significant
    that they reshape how the world understands itself.

    "The one who slew the Dragon of Ashenmoor"
    "The betrayer of the Silver Compact"
    "The voice that silenced the Screaming Caves"
    """
    id: str = Field(default_factory=lambda: f"legend_{uuid.uuid4().hex[:12]}")

    # The legend itself
    title: str                               # "Dragonslayer of Ashenmoor"
    epithet: str                             # "The Dragonslayer"
    narrative: str                           # The story as it's told

    # Origin
    source_echo_ids: List[str] = Field(default_factory=list)  # Events that created this
    seed_session_id: Optional[str] = None    # When it began

    # How it's known
    is_public: bool = True                   # Common knowledge?
    known_by_factions: List[str] = Field(default_factory=list)
    known_in_regions: List[str] = Field(default_factory=list)

    # Truth and perception
    accuracy: float = 1.0                    # How true is the legend? (1.0 = accurate)
    embellishment_level: float = 0.0         # How much has it grown?

    # Impact
    reputation_modifier: float = 0.0         # -1.0 to 1.0, effect on meeting new NPCs
    fear_modifier: float = 0.0               # Do people fear the player?
    respect_modifier: float = 0.0            # Do people respect the player?

    # Narrative weight
    salience: SalienceLevel = SalienceLevel.LEGENDARY
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # How NPCs reference it
    common_phrases: List[str] = Field(default_factory=list)  # "Aren't you the one who..."

    # Arc integration
    hero_journey_stage: Optional[str] = None  # Which stage this fulfills


class Thread(BaseModel):
    """
    An unresolved narrative tension waiting for resolution.

    Threads are the open loops that make stories compelling:
    - Unanswered questions
    - Unpaid debts
    - Unfulfilled promises
    - Unresolved conflicts
    """
    id: str = Field(default_factory=lambda: f"thread_{uuid.uuid4().hex[:12]}")

    # What's unresolved
    thread_type: str                         # "mystery", "debt", "promise", "conflict", "prophecy"
    description: str                         # What needs resolution
    stakes: str                              # What happens if unresolved

    # Origin
    created_by_echo_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_session_id: Optional[str] = None

    # Involved parties
    primary_entity_id: Optional[str] = None  # Main NPC/faction involved
    secondary_entities: List[str] = Field(default_factory=list)
    player_obligation: bool = False          # Is the player expected to resolve?

    # Status
    is_active: bool = True
    urgency: float = 0.5                     # 0.0-1.0, how pressing
    times_referenced: int = 0                # How often has DM brought this up
    last_referenced: Optional[datetime] = None

    # Resolution
    resolved: bool = False
    resolution_echo_id: Optional[str] = None
    resolution_summary: Optional[str] = None


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calculate_decay(
    salience: SalienceLevel,
    days_elapsed: float,
    emotional_weight: float = 0.5
) -> float:
    """
    Calculate how much a memory has faded.

    Returns 0.0 (forgotten) to 1.0 (fully retained).
    """
    # Decay rates per salience level (half-life in days)
    half_lives = {
        SalienceLevel.LEGENDARY: float('inf'),   # Never fades
        SalienceLevel.SIGNIFICANT: 365,          # Year half-life
        SalienceLevel.NOTABLE: 90,               # Season half-life
        SalienceLevel.ORDINARY: 14,              # Two-week half-life
        SalienceLevel.FADED: 3,                  # Three-day half-life
    }

    half_life = half_lives.get(salience, 30)

    if half_life == float('inf'):
        return 1.0

    # Emotional weight slows decay
    adjusted_half_life = half_life * (1 + emotional_weight)

    # Exponential decay
    import math
    retention = math.pow(0.5, days_elapsed / adjusted_half_life)

    return max(0.0, min(1.0, retention))
