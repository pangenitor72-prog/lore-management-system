# src/lms/arc/models.py
"""
Data models for the Arc Engine.

Based on Joseph Campbell's Hero's Journey (monomyth) structure with
adaptations for interactive storytelling and episodic delivery.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import uuid


class StoryAct(str, Enum):
    """
    The three major acts of the Hero's Journey.

    Maps to classical three-act structure:
    - ACT I (Departure): Setup, establishes ordinary world and call
    - ACT II (Initiation): Confrontation, tests and transformation
    - ACT III (Return): Resolution, hero returns changed
    """
    DEPARTURE = "departure"      # Act I: The hero leaves the ordinary world
    INITIATION = "initiation"    # Act II: The hero faces trials and transforms
    RETURN = "return"            # Act III: The hero returns with the elixir


class StoryPhase(str, Enum):
    """
    Campbell's 12 stages of the Hero's Journey.

    Each phase represents a distinct narrative beat with specific
    dramatic function and expected player/character experience.
    """
    # === ACT I: DEPARTURE ===
    ORDINARY_WORLD = "ordinary_world"
    # The hero's normal life before the adventure begins.
    # Function: Establish baseline, create empathy, show what's at stake.

    CALL_TO_ADVENTURE = "call_to_adventure"
    # The hero receives a challenge, quest, or problem.
    # Function: Disrupt equilibrium, present the central dramatic question.

    REFUSAL_OF_THE_CALL = "refusal_of_the_call"
    # The hero hesitates or expresses fear/reluctance.
    # Function: Humanize the hero, raise stakes, show the cost of action.

    MEETING_THE_MENTOR = "meeting_the_mentor"
    # The hero gains guidance, training, or a gift.
    # Function: Prepare for the journey, provide tools/knowledge.

    CROSSING_THE_THRESHOLD = "crossing_the_threshold"
    # The hero commits to the adventure and enters the special world.
    # Function: Point of no return, transition from known to unknown.

    # === ACT II: INITIATION ===
    TESTS_ALLIES_ENEMIES = "tests_allies_enemies"
    # The hero faces challenges and discovers who can be trusted.
    # Function: Build the world, test abilities, form alliances.

    APPROACH_TO_INMOST_CAVE = "approach_to_inmost_cave"
    # The hero prepares for the major challenge.
    # Function: Build tension, gather resources, plan the approach.

    ORDEAL = "ordeal"
    # The hero faces their greatest fear or challenge (the "death" moment).
    # Function: Climax of Act II, transformation through crisis.

    REWARD = "reward"
    # The hero achieves their goal and gains the prize.
    # Function: Celebrate victory, but hint at remaining complications.

    # === ACT III: RETURN ===
    THE_ROAD_BACK = "the_road_back"
    # The hero begins the journey home, often pursued.
    # Function: Renewed tension, consequences of the ordeal.

    RESURRECTION = "resurrection"
    # The hero faces a final test using everything learned.
    # Function: Climax of Act III, ultimate transformation.

    RETURN_WITH_ELIXIR = "return_with_elixir"
    # The hero returns home changed, bearing gifts or wisdom.
    # Function: Resolution, show transformation, close the loop.

    @property
    def act(self) -> StoryAct:
        """Get the act this phase belongs to."""
        departure_phases = {
            StoryPhase.ORDINARY_WORLD,
            StoryPhase.CALL_TO_ADVENTURE,
            StoryPhase.REFUSAL_OF_THE_CALL,
            StoryPhase.MEETING_THE_MENTOR,
            StoryPhase.CROSSING_THE_THRESHOLD,
        }
        initiation_phases = {
            StoryPhase.TESTS_ALLIES_ENEMIES,
            StoryPhase.APPROACH_TO_INMOST_CAVE,
            StoryPhase.ORDEAL,
            StoryPhase.REWARD,
        }
        # return_phases are the rest

        if self in departure_phases:
            return StoryAct.DEPARTURE
        elif self in initiation_phases:
            return StoryAct.INITIATION
        else:
            return StoryAct.RETURN

    @property
    def phase_index(self) -> int:
        """Get the 0-based index of this phase in the journey."""
        phases = list(StoryPhase)
        return phases.index(self)

    @property
    def description(self) -> str:
        """Get a brief description of this phase."""
        descriptions = {
            StoryPhase.ORDINARY_WORLD: "The hero's normal life before adventure",
            StoryPhase.CALL_TO_ADVENTURE: "A challenge disrupts the status quo",
            StoryPhase.REFUSAL_OF_THE_CALL: "The hero hesitates, showing fear or reluctance",
            StoryPhase.MEETING_THE_MENTOR: "Guidance and tools are provided",
            StoryPhase.CROSSING_THE_THRESHOLD: "The hero commits and enters the unknown",
            StoryPhase.TESTS_ALLIES_ENEMIES: "Challenges reveal friends and foes",
            StoryPhase.APPROACH_TO_INMOST_CAVE: "Preparation for the central ordeal",
            StoryPhase.ORDEAL: "The hero faces their greatest challenge",
            StoryPhase.REWARD: "Victory and the prize are claimed",
            StoryPhase.THE_ROAD_BACK: "The journey home begins, with new dangers",
            StoryPhase.RESURRECTION: "A final test demands everything learned",
            StoryPhase.RETURN_WITH_ELIXIR: "The hero returns transformed",
        }
        return descriptions.get(self, "Unknown phase")

    @property
    def expected_tension(self) -> float:
        """Get the expected tension level (0.0-1.0) for this phase."""
        tension_map = {
            StoryPhase.ORDINARY_WORLD: 0.2,
            StoryPhase.CALL_TO_ADVENTURE: 0.4,
            StoryPhase.REFUSAL_OF_THE_CALL: 0.3,
            StoryPhase.MEETING_THE_MENTOR: 0.35,
            StoryPhase.CROSSING_THE_THRESHOLD: 0.5,
            StoryPhase.TESTS_ALLIES_ENEMIES: 0.55,
            StoryPhase.APPROACH_TO_INMOST_CAVE: 0.7,
            StoryPhase.ORDEAL: 0.95,  # Peak tension
            StoryPhase.REWARD: 0.5,   # Relief
            StoryPhase.THE_ROAD_BACK: 0.6,
            StoryPhase.RESURRECTION: 0.9,  # Second peak
            StoryPhase.RETURN_WITH_ELIXIR: 0.2,  # Resolution
        }
        return tension_map.get(self, 0.5)


class TensionLevel(str, Enum):
    """
    Qualitative tension levels for narrative pacing.

    Used to communicate with the DM about when to escalate,
    maintain, or release tension.
    """
    CALM = "calm"           # 0.0-0.2: Peaceful, exploratory
    RISING = "rising"       # 0.2-0.4: Hints of conflict, building interest
    MODERATE = "moderate"   # 0.4-0.6: Active conflict, steady engagement
    HIGH = "high"           # 0.6-0.8: Intense conflict, high stakes
    PEAK = "peak"           # 0.8-1.0: Maximum tension, climactic moments
    FALLING = "falling"     # Transitional: Tension actively decreasing

    @classmethod
    def from_value(cls, value: float) -> "TensionLevel":
        """Convert a numeric tension value to a qualitative level."""
        if value < 0.2:
            return cls.CALM
        elif value < 0.4:
            return cls.RISING
        elif value < 0.6:
            return cls.MODERATE
        elif value < 0.8:
            return cls.HIGH
        else:
            return cls.PEAK


class BeatType(str, Enum):
    """Types of narrative beats the DM can deliver."""
    EXPOSITION = "exposition"          # World-building, backstory
    CHARACTER_MOMENT = "character_moment"  # NPC development, relationship building
    DISCOVERY = "discovery"            # Player learns something new
    OBSTACLE = "obstacle"              # Challenge or barrier
    COMBAT = "combat"                  # Physical conflict
    SOCIAL = "social"                  # Dialogue, negotiation
    PUZZLE = "puzzle"                  # Mental challenge
    CHOICE = "choice"                  # Meaningful decision point
    CONSEQUENCE = "consequence"        # Result of previous choice
    REVELATION = "revelation"          # Major plot twist or secret
    SETBACK = "setback"               # Things go wrong
    VICTORY = "victory"               # Achievement, success
    REST = "rest"                     # Downtime, recovery
    CLIFFHANGER = "cliffhanger"       # Tension-maintaining pause


class NarrativeBeat(BaseModel):
    """
    A suggested narrative beat for the DM.

    The Arc Engine generates these as hints/suggestions,
    not commands. The DM (and ultimately the player's actions)
    determine what actually happens.
    """
    beat_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    beat_type: BeatType
    description: str = Field(..., min_length=1)
    phase_alignment: StoryPhase
    tension_target: float = Field(ge=0.0, le=1.0)
    priority: float = Field(default=0.5, ge=0.0, le=1.0)

    # Optional guidance
    suggested_elements: List[str] = Field(default_factory=list)
    avoid_elements: List[str] = Field(default_factory=list)
    entity_hints: List[str] = Field(default_factory=list)  # Entity names to consider involving

    model_config = ConfigDict(frozen=True)


class EpisodeBoundary(BaseModel):
    """
    Represents a potential stopping point in the narrative.

    Used by the Episode Manager to identify natural breaks
    and generate session-ending moments.
    """
    boundary_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    boundary_type: str  # "natural_pause", "cliffhanger", "resolution"
    strength: float = Field(ge=0.0, le=1.0)  # How strong a stopping point this is
    description: str

    # For cliffhangers
    unresolved_tension: Optional[str] = None
    hook_for_next: Optional[str] = None

    # For recaps
    key_events_summary: List[str] = Field(default_factory=list)

    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ArcState(BaseModel):
    """
    Current state of the narrative arc.

    Tracks where we are in the Hero's Journey and provides
    context for narrative decisions.
    """
    arc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None

    # Current position in the journey
    current_phase: StoryPhase = StoryPhase.ORDINARY_WORLD
    phase_progress: float = Field(default=0.0, ge=0.0, le=1.0)  # Progress within phase

    # Tension state
    current_tension: float = Field(default=0.2, ge=0.0, le=1.0)
    tension_trend: str = "stable"  # "rising", "falling", "stable"

    # Episode tracking
    episode_number: int = Field(default=1, ge=1)
    beats_in_episode: int = Field(default=0, ge=0)
    episode_start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Journey tracking
    phases_completed: List[StoryPhase] = Field(default_factory=list)
    major_events: List[str] = Field(default_factory=list)  # Key story moments

    # Narrative elements encountered
    mentor_introduced: bool = False
    threshold_crossed: bool = False
    ordeal_faced: bool = False

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(validate_assignment=True)

    def get_act(self) -> StoryAct:
        """Get the current act based on phase."""
        return self.current_phase.act

    def get_tension_level(self) -> TensionLevel:
        """Get qualitative tension level."""
        return TensionLevel.from_value(self.current_tension)

    def get_journey_progress(self) -> float:
        """Get overall progress through the Hero's Journey (0.0-1.0)."""
        phase_index = self.current_phase.phase_index
        phase_count = len(StoryPhase)
        base_progress = phase_index / phase_count
        phase_contribution = self.phase_progress / phase_count
        return min(1.0, base_progress + phase_contribution)


class StoryContext(BaseModel):
    """
    Rich context for narrative generation.

    Combines arc state with session information to provide
    the DM with everything needed to generate phase-appropriate content.
    """
    arc_state: ArcState

    # From session
    player_character_name: Optional[str] = None
    player_goal: Optional[str] = None
    current_location: Optional[str] = None

    # Recent history
    recent_events: List[str] = Field(default_factory=list)
    unresolved_threads: List[str] = Field(default_factory=list)

    # Suggested direction
    suggested_beats: List[NarrativeBeat] = Field(default_factory=list)
    potential_boundaries: List[EpisodeBoundary] = Field(default_factory=list)

    # Guidance text for the DM
    phase_guidance: Optional[str] = None
    tension_guidance: Optional[str] = None
    pacing_note: Optional[str] = None

    model_config = ConfigDict(frozen=True)


# === PHASE TRANSITIONS ===

class PhaseTransition(BaseModel):
    """
    Represents a transition between story phases.

    Used to track and validate phase progression.
    """
    from_phase: StoryPhase
    to_phase: StoryPhase
    trigger: str  # What caused the transition
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


# Valid phase transitions (not all jumps make narrative sense)
VALID_TRANSITIONS: Dict[StoryPhase, List[StoryPhase]] = {
    StoryPhase.ORDINARY_WORLD: [StoryPhase.CALL_TO_ADVENTURE],
    StoryPhase.CALL_TO_ADVENTURE: [StoryPhase.REFUSAL_OF_THE_CALL, StoryPhase.MEETING_THE_MENTOR],
    StoryPhase.REFUSAL_OF_THE_CALL: [StoryPhase.MEETING_THE_MENTOR, StoryPhase.CALL_TO_ADVENTURE],
    StoryPhase.MEETING_THE_MENTOR: [StoryPhase.CROSSING_THE_THRESHOLD],
    StoryPhase.CROSSING_THE_THRESHOLD: [StoryPhase.TESTS_ALLIES_ENEMIES],
    StoryPhase.TESTS_ALLIES_ENEMIES: [StoryPhase.APPROACH_TO_INMOST_CAVE, StoryPhase.TESTS_ALLIES_ENEMIES],  # Can loop
    StoryPhase.APPROACH_TO_INMOST_CAVE: [StoryPhase.ORDEAL],
    StoryPhase.ORDEAL: [StoryPhase.REWARD],
    StoryPhase.REWARD: [StoryPhase.THE_ROAD_BACK],
    StoryPhase.THE_ROAD_BACK: [StoryPhase.RESURRECTION],
    StoryPhase.RESURRECTION: [StoryPhase.RETURN_WITH_ELIXIR],
    StoryPhase.RETURN_WITH_ELIXIR: [StoryPhase.ORDINARY_WORLD],  # New journey can begin
}


def is_valid_transition(from_phase: StoryPhase, to_phase: StoryPhase) -> bool:
    """Check if a phase transition is narratively valid."""
    valid_nexts = VALID_TRANSITIONS.get(from_phase, [])
    return to_phase in valid_nexts
