# src/lms/arc/arc_engine.py
"""
Arc Engine - Unified narrative structure and pacing system.

Combines story phase tracking, tension management, beat suggestions,
and episode pacing into a single coherent interface for the DM.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from typing import Union

from .models import (
    StoryPhase,
    StoryAct,
    TensionLevel,
    ArcState,
    NarrativeBeat,
    EpisodeBoundary,
    StoryContext,
    BeatType,
)
from .story_phase import StoryPhaseManager
from .tension_tracker import TensionTracker
from .beat_suggester import BeatSuggester
from .episode_manager import EpisodeManager, EpisodeConfig
from .preference_adapter import (
    get_adapted_description,
    get_adapted_guidance,
    get_adapted_tension_target,
    get_adapted_pacing_guidance,
)
from .genre_arcs import (
    GenreArcType,
    GenrePhase,
    get_arc_type_for_genre,
)

logger = logging.getLogger(__name__)


class ArcEngine:
    """
    Main interface for the narrative arc system.

    Integrates:
    - Story Phase Manager (Campbell's 12 stages or genre-specific arcs)
    - Tension Tracker (rising/falling action)
    - Beat Suggester (narrative guidance)
    - Episode Manager (pacing and boundaries)

    The Arc Engine whispers to the DM - it suggests, never commands.
    Player agency and DM creativity remain paramount.

    Supports genre-specific arc variants:
    - HEROIC: Campbell's Hero's Journey (fantasy, mythology, adventure)
    - HORROR: Descent → Confrontation → Survival/Loss
    - MYSTERY: Setup → Investigation → Revelation
    - HEIST: Assembly → Planning → Execution → Escape
    - ROMANCE: Meeting → Tension → Crisis → Union
    - SURVIVAL: Collapse → Scarcity → Community → Hope
    - WESTERN: Arrival → Conflict → Showdown → Departure
    - CYBERPUNK: Awakening → Resistance → Confrontation → Change
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        genre: str = "fantasy",
        episode_config: Optional[EpisodeConfig] = None,
    ):
        """
        Initialize the Arc Engine.

        Args:
            session_id: Optional session ID for tracking
            genre: World genre (determines arc type). Defaults to "fantasy" (heroic arc).
            episode_config: Optional episode configuration
        """
        self._session_id = session_id

        # Determine arc type from genre
        self._genre = genre
        self._genre_arc = get_arc_type_for_genre(genre)

        # Initialize components with genre awareness
        self._phase_manager = StoryPhaseManager(genre_arc=self._genre_arc)
        self._tension_tracker = TensionTracker()
        self._beat_suggester = BeatSuggester()
        self._episode_manager = EpisodeManager(config=episode_config)

        # Link session ID to arc state
        if session_id:
            self._phase_manager._state.session_id = session_id

        logger.info(
            f"ArcEngine initialized for session {session_id or 'anonymous'} "
            f"with {self._genre_arc.value} arc (genre: {genre})"
        )

    # === PROPERTIES ===

    @property
    def genre_arc(self) -> GenreArcType:
        """Get the genre arc type."""
        return self._genre_arc

    @property
    def current_phase(self) -> Union[StoryPhase, GenrePhase]:
        """Get current story phase (StoryPhase for heroic, GenrePhase for others)."""
        return self._phase_manager.current_phase

    @property
    def current_phase_id(self) -> str:
        """Get current phase ID as string (works for both phase types)."""
        return self._phase_manager.current_phase_id

    @property
    def current_act(self) -> str:
        """Get current act (Departure/Initiation/Return or genre-specific act)."""
        return self._phase_manager.current_act

    @property
    def current_tension(self) -> float:
        """Get current tension level (0.0-1.0)."""
        return self._tension_tracker.current_tension

    @property
    def tension_level(self) -> TensionLevel:
        """Get qualitative tension level."""
        return self._tension_tracker.tension_level

    @property
    def episode_number(self) -> int:
        """Get current episode number."""
        return self._episode_manager.episode_number

    @property
    def journey_progress(self) -> float:
        """Get overall progress through the Hero's Journey (0.0-1.0)."""
        return self._phase_manager.state.get_journey_progress()

    # === MAIN INTERFACE ===

    def process_narrative(
        self,
        narrative_text: str,
        player_action: Optional[str] = None,
        preferences: Optional[Dict[str, str]] = None,
    ) -> StoryContext:
        """
        Process a narrative segment and return updated context.

        This is the main method called after each DM response.
        It analyzes the narrative, updates state, and generates
        suggestions for the next beat.

        Args:
            narrative_text: The DM's narrative response
            player_action: Optional player action that preceded it
            preferences: Optional storytelling preferences dict with keys:
                         protagonist_arc, lethality, moral_complexity

        Returns:
            Updated StoryContext with suggestions
        """
        # Analyze and update tension
        self._tension_tracker.apply_text_analysis(narrative_text)

        # Check for phase transition signals
        transition = self._phase_manager.suggest_transition(narrative_text)
        if transition:
            phase, confidence, reason = transition
            if confidence > 0.5:
                self._phase_manager.transition_to(phase, reason, confidence)
        else:
            # Advance progress within current phase
            self._phase_manager.advance_progress(0.1)

        # Align tension toward phase expectation (gentle pull)
        # Use lethality-adjusted tension target when preferences are available
        lethality = preferences.get("lethality") if preferences else None
        tension_target = get_adapted_tension_target(self.current_phase, lethality)
        self._tension_tracker.align_to_phase(
            self.current_phase, strength=0.1, tension_override=tension_target
        )

        # Detect episode boundary opportunities
        boundary = self._episode_manager.detect_boundary(
            current_phase=self.current_phase,
            current_tension=self.current_tension,
        )

        # Generate beat suggestions with genre awareness
        suggested_beats = self._beat_suggester.suggest_beats(
            phase=self.current_phase,
            current_tension=self.current_tension,
            count=3,
            genre_arc=self._genre_arc.value,
        )

        # Build and return context
        return StoryContext(
            arc_state=self._phase_manager.state,
            recent_events=self._episode_manager._key_events[-3:],
            suggested_beats=suggested_beats,
            potential_boundaries=[boundary] if boundary else [],
            phase_guidance=self._phase_manager.get_phase_guidance(),
            tension_guidance=self._tension_tracker.get_pacing_guidance(self.current_phase),
            pacing_note=self._get_pacing_note(),
        )

    def record_beat(
        self,
        beat_type: BeatType,
        description: str,
    ) -> None:
        """
        Record that a narrative beat occurred.

        Call this after significant story moments to track pacing.

        Args:
            beat_type: Type of beat that occurred
            description: Brief description
        """
        self._beat_suggester.record_beat_used(beat_type)
        self._episode_manager.record_beat(
            beat_type=beat_type,
            description=description,
            tension_after=self.current_tension,
        )

    def force_phase_transition(
        self,
        target_phase: StoryPhase,
        reason: str = "Manual transition",
    ) -> bool:
        """
        Force a transition to a specific phase.

        Use sparingly - prefer letting transitions happen naturally.

        Args:
            target_phase: Phase to transition to
            reason: Why the transition is happening

        Returns:
            True if transition succeeded
        """
        success, error = self._phase_manager.transition_to(
            target_phase,
            trigger=reason,
            force=True,
        )
        return success

    def set_tension(self, value: float) -> None:
        """
        Manually set tension to a specific value.

        Args:
            value: Tension level (0.0-1.0)
        """
        self._tension_tracker.set_tension(value)

    # === EPISODE MANAGEMENT ===

    def check_episode_boundary(self) -> Optional[EpisodeBoundary]:
        """
        Check if we're at a good episode boundary.

        Returns:
            EpisodeBoundary if a stopping point is detected
        """
        return self._episode_manager.detect_boundary(
            current_phase=self.current_phase,
            current_tension=self.current_tension,
        )

    def end_episode(self) -> Dict[str, Any]:
        """
        End the current episode and prepare for the next.

        Returns:
            Episode summary including recap
        """
        recap = self._episode_manager.generate_recap()
        pacing = self._episode_manager.get_pacing_status()

        summary = {
            "episode_number": self.episode_number,
            "recap": recap,
            "pacing": pacing,
            "phase_at_end": self.current_phase_id,
            "tension_at_end": self.current_tension,
        }

        self._episode_manager.start_new_episode()

        return summary

    def get_cliffhanger_prompt(self) -> str:
        """Get guidance for creating a cliffhanger ending."""
        return self._episode_manager.generate_cliffhanger_prompt(self.current_phase)

    def get_recap(self) -> str:
        """Get a recap of the current episode so far."""
        return self._episode_manager.generate_recap()

    # === DM GUIDANCE ===

    def get_dm_context_injection(
        self,
        subtle: bool = False,
        compact: bool = True,
        preferences: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Get text to inject into the DM's prompt for arc awareness.

        Args:
            subtle: If True, provide gentle guidance without explicit phase names.
                   Use for campaigns where structure should emerge naturally.
            compact: If True, use token-efficient format (default).
            preferences: Optional storytelling preferences dict with keys:
                         protagonist_arc, lethality, moral_complexity.
                         When provided, adapts all language to match the player's
                         chosen arc and lethality.

        Returns:
            Context string for prompt injection
        """
        phase = self.current_phase
        tension = self.current_tension
        trend = self._tension_tracker.trend
        is_heroic = self._genre_arc == GenreArcType.HEROIC

        # Get phase name and act
        if isinstance(phase, GenrePhase):
            phase_name = phase.name
            phase_act = phase.act.title()
            phase_description = phase.description
        else:
            phase_name = phase.value.replace('_', ' ').title()
            phase_act = phase.act.value.title()
            # Get arc-adapted description for heroic phases
            arc_type = preferences.get("protagonist_arc") if preferences else None
            phase_description = get_adapted_description(phase, arc_type)

        lethality = preferences.get("lethality") if preferences else None

        if subtle:
            # For campaigns: guidance without explicit structure
            tension_word = "calm" if tension < 0.3 else "building" if tension < 0.6 else "high"
            # Get a single beat suggestion for gentle guidance
            beats = self._beat_suggester.suggest_beats(
                phase=phase,
                current_tension=tension,
                count=1,
                genre_arc=self._genre_arc.value,
            )
            beat_hint = f" | Opportunity: {beats[0].description}" if beats else ""
            if compact:
                # Compact subtle: single line
                return f"ARC: {tension_word}, {trend} | {phase_description[:60]}{beat_hint}"
            return f"""
Narrative energy: {tension_word}, {trend}
{phase_description}{beat_hint}"""

        # For finite stories: more explicit structure helps pacing
        if compact:
            # Compact format: ARC: Phase | Tension: X% (level, trend) | Progress: Y%
            # Suggest: [TYPE] description | [TYPE] description
            progress_pct = int(self.journey_progress * 100)
            parts = [
                f"ARC: {phase_name}",
                f"Tension: {tension:.0%} ({self.tension_level.value}, {trend})",
                f"Progress: {progress_pct}%",
            ]
            result = " | ".join(parts)

            # Add focus (truncated)
            if phase_description:
                short_focus = phase_description[:80]
                if len(phase_description) > 80:
                    short_focus = short_focus.rsplit(' ', 1)[0] + "..."
                result += f"\nFocus: {short_focus}"

            # Add beat suggestions (compact)
            beats = self._beat_suggester.suggest_beats(
                phase=phase,
                current_tension=tension,
                count=2,
                genre_arc=self._genre_arc.value,
            )
            if beats:
                beat_parts = [f"[{b.beat_type.value.upper()}] {b.description[:40]}" for b in beats]
                result += f"\nSuggest: {' | '.join(beat_parts)}"

            return result

        # Verbose format (legacy)
        arc_label = f"{self._genre_arc.value.upper()} ARC" if not is_heroic else "NARRATIVE ARC"
        lines = [
            f"\n=== {arc_label} ===",
            f"Phase: {phase_name} ({phase_act})",
            f"Tension: {tension:.0%} ({self.tension_level.value}), {trend}",
        ]

        # Add phase description
        if phase_description:
            lines.append(f"Focus: {phase_description}")

        # Add pacing guidance — prefer lethality-adapted version, fall back to default
        if is_heroic:
            lethality_pacing = get_adapted_pacing_guidance(phase, lethality)
            if lethality_pacing:
                lines.append(f"Pacing: {lethality_pacing}")
            else:
                pacing_note = self._tension_tracker.get_pacing_guidance(phase, lethality=lethality)
                if pacing_note:
                    lines.append(f"Pacing: {pacing_note}")

        # Add beat suggestions for narrative direction
        beats = self._beat_suggester.suggest_beats(
            phase=phase,
            current_tension=tension,
            count=2,  # Top 2 suggestions to avoid prompt bloat
            genre_arc=self._genre_arc.value,
        )
        if beats:
            lines.append("Consider:")
            for beat in beats:
                # Format: "- [COMBAT] Face the supreme challenge - everything at stake"
                lines.append(f"  - [{beat.beat_type.value.upper()}] {beat.description}")

        return "\n".join(lines)

    def get_next_beat_suggestions(self, count: int = 3) -> List[NarrativeBeat]:
        """
        Get suggested next beats.

        Args:
            count: Number of suggestions to return

        Returns:
            List of suggested narrative beats
        """
        return self._beat_suggester.suggest_beats(
            phase=self.current_phase,
            current_tension=self.current_tension,
            count=count,
            genre_arc=self._genre_arc.value,
        )

    # === INTERNAL HELPERS ===

    def _get_pacing_note(self) -> str:
        """Generate a brief pacing note for the context."""
        status = self._episode_manager.get_pacing_status()
        beats = status["beats_count"]
        min_beats = self._episode_manager.config.min_beats_per_episode
        max_beats = self._episode_manager.config.max_beats_per_episode

        if beats < min_beats:
            return f"Episode building ({beats}/{min_beats} beats minimum)"
        elif beats < max_beats:
            return f"Episode in progress ({beats} beats) - watch for natural pauses"
        else:
            return f"Episode at maximum ({beats} beats) - find a stopping point"

    # === PERSISTENCE ===

    def to_dict(self) -> Dict[str, Any]:
        """Export full state for persistence."""
        return {
            "session_id": self._session_id,
            "genre": self._genre,
            "genre_arc": self._genre_arc.value,
            "phase_manager": self._phase_manager.to_dict(),
            "tension_tracker": self._tension_tracker.to_dict(),
            "beat_suggester": self._beat_suggester.to_dict(),
            "episode_manager": self._episode_manager.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArcEngine":
        """Restore from dictionary."""
        genre = data.get("genre", "fantasy")
        engine = cls(session_id=data.get("session_id"), genre=genre)
        engine._phase_manager = StoryPhaseManager.from_dict(
            data.get("phase_manager", {})
        )
        engine._tension_tracker = TensionTracker.from_dict(
            data.get("tension_tracker", {})
        )
        engine._beat_suggester = BeatSuggester.from_dict(
            data.get("beat_suggester", {})
        )
        engine._episode_manager = EpisodeManager.from_dict(
            data.get("episode_manager", {})
        )
        return engine

    # === STATUS ===

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the arc engine."""
        phase = self.current_phase

        # Get expected tension (works for both phase types)
        if isinstance(phase, GenrePhase):
            expected_tension = phase.expected_tension
            phase_value = phase.id
        else:
            expected_tension = phase.expected_tension
            phase_value = phase.value

        return {
            "session_id": self._session_id,
            "genre": self._genre,
            "genre_arc": self._genre_arc.value,
            "phase": {
                "current": phase_value,
                "act": self.current_act,
                "progress": self._phase_manager.state.phase_progress,
                "journey_progress": self.journey_progress,
            },
            "tension": {
                "value": self.current_tension,
                "level": self.tension_level.value,
                "trend": self._tension_tracker.trend,
                "expected_for_phase": expected_tension,
            },
            "episode": self._episode_manager.get_pacing_status(),
            "milestones": {
                "mentor_introduced": self._phase_manager.state.mentor_introduced,
                "threshold_crossed": self._phase_manager.state.threshold_crossed,
                "ordeal_faced": self._phase_manager.state.ordeal_faced,
            },
        }
