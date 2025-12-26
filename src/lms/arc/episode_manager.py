# src/lms/arc/episode_manager.py
"""
Episode Manager - Handles narrative pacing and session boundaries.

Manages episode length, detects natural stopping points, generates
cliffhangers and recaps, and adapts to user attention patterns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .models import (
    StoryPhase,
    TensionLevel,
    EpisodeBoundary,
    ArcState,
    NarrativeBeat,
    BeatType,
)

logger = logging.getLogger(__name__)


class EpisodeConfig:
    """Configuration for episode management."""

    def __init__(
        self,
        target_duration_minutes: int = 30,
        min_beats_per_episode: int = 5,
        max_beats_per_episode: int = 15,
        cliffhanger_probability: float = 0.7,
        natural_pause_threshold: float = 0.3,  # Tension below this is a pause
    ):
        self.target_duration_minutes = target_duration_minutes
        self.min_beats_per_episode = min_beats_per_episode
        self.max_beats_per_episode = max_beats_per_episode
        self.cliffhanger_probability = cliffhanger_probability
        self.natural_pause_threshold = natural_pause_threshold


class EpisodeManager:
    """
    Manages episode pacing and boundaries.

    Responsibilities:
    - Track episode progress (beats, time, tension curve)
    - Detect natural stopping points
    - Generate session-ending cliffhangers
    - Create episode recaps for continuity
    - Adapt to user engagement patterns
    """

    def __init__(
        self,
        config: Optional[EpisodeConfig] = None,
        episode_number: int = 1,
    ):
        """
        Initialize the episode manager.

        Args:
            config: Episode configuration
            episode_number: Starting episode number
        """
        self.config = config or EpisodeConfig()
        self._episode_number = episode_number
        self._episode_start_time = datetime.now(timezone.utc)
        self._beats_in_episode: List[Dict[str, Any]] = []
        self._tension_samples: List[float] = []
        self._key_events: List[str] = []
        self._detected_boundaries: List[EpisodeBoundary] = []

    @property
    def episode_number(self) -> int:
        """Get current episode number."""
        return self._episode_number

    @property
    def episode_duration(self) -> timedelta:
        """Get duration of current episode."""
        return datetime.now(timezone.utc) - self._episode_start_time

    @property
    def beats_count(self) -> int:
        """Get number of beats in current episode."""
        return len(self._beats_in_episode)

    def record_beat(
        self,
        beat_type: BeatType,
        description: str,
        tension_after: float,
    ) -> None:
        """
        Record a narrative beat that occurred.

        Args:
            beat_type: Type of beat
            description: Brief description of what happened
            tension_after: Tension level after the beat
        """
        self._beats_in_episode.append({
            "type": beat_type.value,
            "description": description,
            "tension": tension_after,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._tension_samples.append(tension_after)

        # Track key events for recap
        if beat_type in [BeatType.REVELATION, BeatType.CHOICE, BeatType.VICTORY, BeatType.SETBACK]:
            self._key_events.append(description)

    def sample_tension(self, tension: float) -> None:
        """Record a tension sample for pacing analysis."""
        self._tension_samples.append(tension)

    def detect_boundary(
        self,
        current_phase: StoryPhase,
        current_tension: float,
        recent_beat: Optional[BeatType] = None,
    ) -> Optional[EpisodeBoundary]:
        """
        Detect if we're at a natural episode boundary.

        Args:
            current_phase: Current story phase
            current_tension: Current tension level
            recent_beat: Most recent beat type (if any)

        Returns:
            EpisodeBoundary if a good stopping point is detected, else None
        """
        # Check if we have minimum beats
        if self.beats_count < self.config.min_beats_per_episode:
            return None

        # Check for maximum beats (force consideration)
        force_check = self.beats_count >= self.config.max_beats_per_episode

        # Natural pause: tension dropped below threshold after being high
        is_tension_drop = (
            len(self._tension_samples) >= 3
            and self._tension_samples[-3] > 0.5
            and current_tension < self.config.natural_pause_threshold
        )

        # Resolution point: just completed a significant beat
        is_resolution = recent_beat in [
            BeatType.VICTORY,
            BeatType.REST,
            BeatType.CONSEQUENCE,
        ]

        # Cliffhanger opportunity: tension is rising and we hit a revelation
        is_cliffhanger_moment = (
            current_tension > 0.6
            and recent_beat in [BeatType.REVELATION, BeatType.SETBACK, BeatType.DISCOVERY]
        )

        # Phase transition is natural break
        is_phase_appropriate = current_phase in [
            StoryPhase.CROSSING_THE_THRESHOLD,  # End of Act I
            StoryPhase.REWARD,  # End of Ordeal sequence
            StoryPhase.RETURN_WITH_ELIXIR,  # Journey complete
        ]

        # Determine boundary type
        if is_cliffhanger_moment or (force_check and current_tension > 0.5):
            boundary = EpisodeBoundary(
                boundary_type="cliffhanger",
                strength=min(1.0, current_tension + 0.2),
                description="High-tension moment - perfect for cliffhanger",
                unresolved_tension=self._key_events[-1] if self._key_events else "Danger looms",
                hook_for_next="What happens next?",
                key_events_summary=self._key_events[-5:],
            )
            self._detected_boundaries.append(boundary)
            return boundary

        elif is_tension_drop or is_resolution:
            boundary = EpisodeBoundary(
                boundary_type="natural_pause",
                strength=0.6,
                description="Natural pause after tension release",
                key_events_summary=self._key_events[-5:],
            )
            self._detected_boundaries.append(boundary)
            return boundary

        elif is_phase_appropriate and self.beats_count >= self.config.min_beats_per_episode:
            boundary = EpisodeBoundary(
                boundary_type="phase_transition",
                strength=0.7,
                description=f"End of {current_phase.value} phase",
                key_events_summary=self._key_events[-5:],
            )
            self._detected_boundaries.append(boundary)
            return boundary

        elif force_check:
            boundary = EpisodeBoundary(
                boundary_type="soft_break",
                strength=0.4,
                description="Episode reaching maximum length",
                key_events_summary=self._key_events[-5:],
            )
            self._detected_boundaries.append(boundary)
            return boundary

        return None

    def generate_recap(self) -> str:
        """
        Generate a recap of the current episode.

        Returns:
            A narrative summary suitable for "Previously, on..."
        """
        if not self._key_events:
            return "The adventure continues..."

        # Get the most significant events
        events = self._key_events[-5:]

        if len(events) == 1:
            return f"Previously: {events[0]}"

        recap_lines = ["Previously, in our adventure:"]
        for event in events:
            recap_lines.append(f"  - {event}")

        return "\n".join(recap_lines)

    def generate_cliffhanger_prompt(self, current_phase: StoryPhase) -> str:
        """
        Generate a prompt to help the DM create a cliffhanger.

        Args:
            current_phase: Current story phase

        Returns:
            Guidance text for creating a cliffhanger
        """
        phase_cliffhangers = {
            StoryPhase.ORDINARY_WORLD: (
                "End with the first sign that something is wrong - "
                "a distant thunder, a messenger's arrival, a troubling dream."
            ),
            StoryPhase.CALL_TO_ADVENTURE: (
                "End at the moment the stakes become clear - "
                "reveal the true scope of the threat or the personal cost of refusal."
            ),
            StoryPhase.REFUSAL_OF_THE_CALL: (
                "End with an event that makes refusal impossible - "
                "the danger comes home, or someone they love is threatened."
            ),
            StoryPhase.MEETING_THE_MENTOR: (
                "End with the mentor's warning or a glimpse of what's to come - "
                "the journey will be harder than expected."
            ),
            StoryPhase.CROSSING_THE_THRESHOLD: (
                "End as they step into the unknown - "
                "the door closes behind them, the bridge burns, there's no going back."
            ),
            StoryPhase.TESTS_ALLIES_ENEMIES: (
                "End with a betrayal revealed or a new enemy unmasked - "
                "trust is called into question."
            ),
            StoryPhase.APPROACH_TO_INMOST_CAVE: (
                "End with the first glimpse of the true challenge - "
                "the dragon stirs, the fortress gates loom."
            ),
            StoryPhase.ORDEAL: (
                "End at the moment of apparent defeat - "
                "all seems lost, but we don't see how the hero survives."
            ),
            StoryPhase.REWARD: (
                "End with the discovery that victory has a price - "
                "the treasure is cursed, the enemy wasn't truly defeated."
            ),
            StoryPhase.THE_ROAD_BACK: (
                "End with the pursuit closing in - "
                "escape seems impossible, a sacrifice may be required."
            ),
            StoryPhase.RESURRECTION: (
                "End at the moment of final choice - "
                "the hero must decide who they truly are."
            ),
            StoryPhase.RETURN_WITH_ELIXIR: (
                "End with seeds of a new adventure - "
                "peace is restored, but change is on the horizon."
            ),
        }

        return phase_cliffhangers.get(
            current_phase,
            "End on a moment of unresolved tension or revelation."
        )

    def start_new_episode(self) -> int:
        """
        Start a new episode, resetting tracking.

        Returns:
            The new episode number
        """
        self._episode_number += 1
        self._episode_start_time = datetime.now(timezone.utc)
        self._beats_in_episode = []
        self._tension_samples = []
        self._key_events = []
        self._detected_boundaries = []

        logger.info(f"Starting Episode {self._episode_number}")
        return self._episode_number

    def get_pacing_status(self) -> Dict[str, Any]:
        """
        Get current pacing status for the episode.

        Returns:
            Dict with pacing metrics and recommendations
        """
        duration_minutes = self.episode_duration.total_seconds() / 60
        beat_pace = self.beats_count / max(1, duration_minutes)

        # Calculate tension arc
        avg_tension = (
            sum(self._tension_samples) / len(self._tension_samples)
            if self._tension_samples
            else 0.5
        )

        # Determine pacing recommendation
        if self.beats_count < self.config.min_beats_per_episode / 2:
            recommendation = "Episode is just beginning - establish the situation"
        elif self.beats_count < self.config.min_beats_per_episode:
            recommendation = "Building toward the first potential boundary"
        elif self.beats_count < self.config.max_beats_per_episode:
            recommendation = "In the sweet spot - look for natural stopping points"
        else:
            recommendation = "Episode running long - find a boundary soon"

        return {
            "episode_number": self._episode_number,
            "beats_count": self.beats_count,
            "duration_minutes": round(duration_minutes, 1),
            "beat_pace_per_minute": round(beat_pace, 2),
            "average_tension": round(avg_tension, 2),
            "key_events_count": len(self._key_events),
            "boundaries_detected": len(self._detected_boundaries),
            "recommendation": recommendation,
        }

    def should_suggest_break(self) -> bool:
        """Check if we should suggest a break to the player."""
        # Time-based check
        if self.episode_duration > timedelta(minutes=self.config.target_duration_minutes * 1.5):
            return True

        # Beat-based check
        if self.beats_count >= self.config.max_beats_per_episode:
            return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Export state for persistence."""
        return {
            "episode_number": self._episode_number,
            "episode_start_time": self._episode_start_time.isoformat(),
            "beats_in_episode": self._beats_in_episode,
            "tension_samples": self._tension_samples,
            "key_events": self._key_events,
            "config": {
                "target_duration_minutes": self.config.target_duration_minutes,
                "min_beats_per_episode": self.config.min_beats_per_episode,
                "max_beats_per_episode": self.config.max_beats_per_episode,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodeManager":
        """Restore from dictionary."""
        config_data = data.get("config", {})
        config = EpisodeConfig(
            target_duration_minutes=config_data.get("target_duration_minutes", 30),
            min_beats_per_episode=config_data.get("min_beats_per_episode", 5),
            max_beats_per_episode=config_data.get("max_beats_per_episode", 15),
        )
        manager = cls(
            config=config,
            episode_number=data.get("episode_number", 1),
        )
        manager._beats_in_episode = data.get("beats_in_episode", [])
        manager._tension_samples = data.get("tension_samples", [])
        manager._key_events = data.get("key_events", [])
        if "episode_start_time" in data:
            manager._episode_start_time = datetime.fromisoformat(data["episode_start_time"])
        return manager
