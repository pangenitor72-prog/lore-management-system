# src/lms/arc/story_phase.py
"""
Story Phase Manager - State machine for narrative arcs.

Tracks the current phase of the narrative and manages transitions
based on story events and player actions. Supports both Campbell's
Hero's Journey (default) and genre-specific arc variants.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple, Union

from .models import (
    StoryPhase,
    StoryAct,
    ArcState,
    PhaseTransition,
    VALID_TRANSITIONS,
    is_valid_transition,
)
from .genre_arcs import (
    GenreArcType,
    GenrePhase,
    get_arc_type_for_genre,
    get_phases_for_arc,
    GENRE_TRANSITIONS,
    GENRE_PHASE_INDICATORS,
)

logger = logging.getLogger(__name__)


# Keywords/patterns that suggest a phase transition
PHASE_INDICATORS: Dict[StoryPhase, List[str]] = {
    StoryPhase.ORDINARY_WORLD: [
        "daily life", "routine", "normal", "peaceful", "home",
        "before everything changed", "used to be",
    ],
    StoryPhase.CALL_TO_ADVENTURE: [
        "quest", "mission", "summoned", "discovered", "messenger",
        "urgent", "need your help", "only you can", "chosen",
        "strange occurrence", "disruption", "calling",
    ],
    StoryPhase.REFUSAL_OF_THE_CALL: [
        "not ready", "can't do this", "impossible", "afraid",
        "why me", "someone else", "refuse", "hesitate",
        "doubt", "too dangerous",
    ],
    StoryPhase.MEETING_THE_MENTOR: [
        "wise", "teacher", "training", "gift", "weapon", "knowledge",
        "learn", "prepare", "guide", "master", "sage",
        "ancient wisdom", "teaching",
    ],
    StoryPhase.CROSSING_THE_THRESHOLD: [
        "no turning back", "point of no return", "committed",
        "leaving home", "entering", "crossing", "beyond",
        "unknown territory", "first step",
    ],
    StoryPhase.TESTS_ALLIES_ENEMIES: [
        "challenge", "trial", "test", "ally", "friend", "enemy",
        "betrayal", "trust", "prove", "join forces",
        "new companion", "rival",
    ],
    StoryPhase.APPROACH_TO_INMOST_CAVE: [
        "preparing", "gathering", "planning", "approaching",
        "final preparation", "before the battle", "on the eve",
        "the lair", "heart of", "fortress",
    ],
    StoryPhase.ORDEAL: [
        "greatest fear", "death", "dying", "sacrifice",
        "ultimate challenge", "final battle", "confrontation",
        "darkest hour", "all is lost", "supreme test",
    ],
    StoryPhase.REWARD: [
        "victory", "treasure", "prize", "achieved", "won",
        "reward", "gained", "mastered", "claimed",
        "the sword", "the secret",
    ],
    StoryPhase.THE_ROAD_BACK: [
        "returning", "pursued", "escape", "fleeing",
        "journey home", "heading back", "consequences",
        "chase", "hunted",
    ],
    StoryPhase.RESURRECTION: [
        "final test", "last chance", "everything learned",
        "transformation", "reborn", "new self",
        "ultimate sacrifice", "choosing",
    ],
    StoryPhase.RETURN_WITH_ELIXIR: [
        "home", "returned", "changed", "wisdom", "gift",
        "new beginning", "peace", "balance restored",
        "sharing", "hero",
    ],
}


class StoryPhaseManager:
    """
    Manages the narrative phase state machine.

    Supports both Campbell's Hero's Journey (for heroic genres) and
    genre-specific arc variants (horror, mystery, heist, romance, etc.).

    Responsibilities:
    - Track current phase
    - Validate and execute phase transitions
    - Detect phase-relevant content in narrative
    - Provide phase-appropriate guidance
    """

    def __init__(
        self,
        initial_state: Optional[ArcState] = None,
        genre_arc: Union[GenreArcType, str] = GenreArcType.HEROIC,
    ):
        """
        Initialize the phase manager.

        Args:
            initial_state: Optional existing arc state to resume from
            genre_arc: The arc type to use (GenreArcType enum or string)
        """
        self._state = initial_state or ArcState()
        self._transition_history: List[PhaseTransition] = []

        # Resolve genre arc type
        if isinstance(genre_arc, str):
            try:
                self._genre_arc = GenreArcType(genre_arc)
            except ValueError:
                self._genre_arc = get_arc_type_for_genre(genre_arc)
        else:
            self._genre_arc = genre_arc

        # Cache genre-specific data
        self._is_heroic = self._genre_arc == GenreArcType.HEROIC
        if not self._is_heroic:
            self._genre_phases = get_phases_for_arc(self._genre_arc)
            self._genre_transitions = GENRE_TRANSITIONS.get(self._genre_arc, {})
            self._genre_phase_indicators = GENRE_PHASE_INDICATORS.get(self._genre_arc, {})
            # Track current genre phase index
            self._current_genre_phase_index = 0
        else:
            self._genre_phases = []
            self._genre_transitions = {}
            self._genre_phase_indicators = {}

    @property
    def genre_arc(self) -> GenreArcType:
        """Get the genre arc type."""
        return self._genre_arc

    @property
    def current_phase(self) -> Union[StoryPhase, GenrePhase]:
        """Get the current story phase."""
        if self._is_heroic:
            return self._state.current_phase
        else:
            # Return the current genre phase
            if self._genre_phases:
                return self._genre_phases[self._current_genre_phase_index]
            return self._state.current_phase

    @property
    def current_phase_id(self) -> str:
        """Get the current phase ID (works for both StoryPhase and GenrePhase)."""
        phase = self.current_phase
        if isinstance(phase, GenrePhase):
            return phase.id
        return phase.value

    @property
    def current_act(self) -> str:
        """Get the current act based on phase."""
        if self._is_heroic:
            return self._state.get_act().value
        else:
            phase = self.current_phase
            if isinstance(phase, GenrePhase):
                return phase.act
            return "confrontation"

    @property
    def state(self) -> ArcState:
        """Get the full arc state."""
        return self._state

    def get_valid_next_phases(self) -> List[Union[StoryPhase, GenrePhase]]:
        """Get list of valid phases we can transition to."""
        if self._is_heroic:
            return VALID_TRANSITIONS.get(self._state.current_phase, [])
        else:
            current_id = self.current_phase_id
            valid_ids = self._genre_transitions.get(current_id, [])
            # Return GenrePhase objects for valid transitions
            return [p for p in self._genre_phases if p.id in valid_ids]

    def can_transition_to(self, target_phase: Union[StoryPhase, GenrePhase, str]) -> bool:
        """Check if we can transition to the target phase."""
        if self._is_heroic:
            if isinstance(target_phase, StoryPhase):
                return is_valid_transition(self._state.current_phase, target_phase)
            return False
        else:
            # Get target phase ID
            if isinstance(target_phase, GenrePhase):
                target_id = target_phase.id
            elif isinstance(target_phase, str):
                target_id = target_phase
            else:
                return False
            valid_ids = self._genre_transitions.get(self.current_phase_id, [])
            return target_id in valid_ids

    def transition_to(
        self,
        target_phase: Union[StoryPhase, GenrePhase, str],
        trigger: str,
        confidence: float = 0.8,
        force: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Attempt to transition to a new phase.

        Args:
            target_phase: The phase to transition to (StoryPhase, GenrePhase, or phase ID)
            trigger: Description of what caused the transition
            confidence: How confident we are in this transition (0.0-1.0)
            force: If True, allow non-standard transitions

        Returns:
            Tuple of (success, error_message)
        """
        # Get phase IDs for logging
        old_phase_id = self.current_phase_id

        if isinstance(target_phase, str):
            target_id = target_phase
        elif isinstance(target_phase, GenrePhase):
            target_id = target_phase.id
        else:
            target_id = target_phase.value

        if not force and not self.can_transition_to(target_phase):
            return False, f"Invalid transition from {old_phase_id} to {target_id}"

        # Record the transition (store phase IDs for serialization)
        transition = PhaseTransition(
            from_phase=self._state.current_phase,  # Always use StoryPhase for serialization
            to_phase=self._state.current_phase,  # Will be updated below for heroic
            trigger=trigger,
            confidence=confidence,
        )

        if self._is_heroic:
            if isinstance(target_phase, StoryPhase):
                transition = PhaseTransition(
                    from_phase=self._state.current_phase,
                    to_phase=target_phase,
                    trigger=trigger,
                    confidence=confidence,
                )
                self._transition_history.append(transition)

                # Update state
                old_phase = self._state.current_phase
                self._state.phases_completed.append(old_phase)
                self._state.current_phase = target_phase
                self._state.phase_progress = 0.0
                self._state.updated_at = datetime.now(timezone.utc)

                # Track special transitions
                if target_phase == StoryPhase.MEETING_THE_MENTOR:
                    self._state.mentor_introduced = True
                elif target_phase == StoryPhase.CROSSING_THE_THRESHOLD:
                    self._state.threshold_crossed = True
                elif target_phase == StoryPhase.ORDEAL:
                    self._state.ordeal_faced = True

                logger.info(f"Phase transition: {old_phase.value} -> {target_phase.value} ({trigger})")
            else:
                return False, f"Expected StoryPhase for heroic arc, got {type(target_phase)}"
        else:
            # Genre-specific arc transition
            self._transition_history.append(transition)

            # Find target phase index
            target_index = None
            for i, phase in enumerate(self._genre_phases):
                if phase.id == target_id:
                    target_index = i
                    break

            if target_index is None:
                return False, f"Unknown phase: {target_id}"

            self._current_genre_phase_index = target_index
            self._state.phase_progress = 0.0
            self._state.updated_at = datetime.now(timezone.utc)

            logger.info(f"Genre phase transition ({self._genre_arc.value}): {old_phase_id} -> {target_id} ({trigger})")

        return True, None

    def advance_progress(self, amount: float = 0.1) -> None:
        """
        Advance progress within the current phase.

        Args:
            amount: Amount to advance (0.0-1.0)
        """
        new_progress = min(1.0, self._state.phase_progress + amount)
        self._state.phase_progress = new_progress
        self._state.updated_at = datetime.now(timezone.utc)

    def detect_phase_signals(self, text: str) -> Dict[str, float]:
        """
        Analyze text for phase transition signals.

        Returns a dict of phase IDs to confidence scores based on
        keyword matching. This is a simple heuristic - the LLM
        should make final phase decisions.

        Args:
            text: Narrative text to analyze

        Returns:
            Dict mapping phase IDs to confidence scores (0.0-1.0)
        """
        text_lower = text.lower()
        scores: Dict[str, float] = {}

        if self._is_heroic:
            # Use Campbell's Hero's Journey indicators
            for phase, keywords in PHASE_INDICATORS.items():
                matches = sum(1 for kw in keywords if kw in text_lower)
                if matches > 0:
                    # Normalize by number of keywords for this phase
                    score = min(1.0, matches / (len(keywords) * 0.3))
                    scores[phase.value] = score
        else:
            # Use genre-specific indicators
            for phase_id, keywords in self._genre_phase_indicators.items():
                matches = sum(1 for kw in keywords if kw in text_lower)
                if matches > 0:
                    score = min(1.0, matches / (len(keywords) * 0.3))
                    scores[phase_id] = score

        return scores

    def suggest_transition(
        self, text: str
    ) -> Optional[Tuple[Union[StoryPhase, GenrePhase], float, str]]:
        """
        Suggest a phase transition based on narrative content.

        Args:
            text: Recent narrative text

        Returns:
            Optional tuple of (suggested_phase, confidence, reason)
            Returns None if no transition is suggested
        """
        signals = self.detect_phase_signals(text)

        if not signals:
            return None

        # Get valid next phase IDs
        valid_next = self.get_valid_next_phases()
        valid_ids = set()
        for phase in valid_next:
            if isinstance(phase, GenrePhase):
                valid_ids.add(phase.id)
            else:
                valid_ids.add(phase.value)

        # Only consider valid next phases
        valid_signals = {
            phase_id: score
            for phase_id, score in signals.items()
            if phase_id in valid_ids
        }

        if not valid_signals:
            return None

        # Find the strongest signal
        best_phase_id = max(valid_signals, key=valid_signals.get)
        confidence = valid_signals[best_phase_id]

        # Only suggest if confidence is above threshold
        if confidence < 0.3:
            return None

        # Get the actual phase object
        if self._is_heroic:
            best_phase = StoryPhase(best_phase_id)
            indicators = PHASE_INDICATORS.get(best_phase, [])
            first_indicator = indicators[0] if indicators else best_phase_id
        else:
            best_phase = next(
                (p for p in self._genre_phases if p.id == best_phase_id), None
            )
            if best_phase is None:
                return None
            indicators = self._genre_phase_indicators.get(best_phase_id, [])
            first_indicator = indicators[0] if indicators else best_phase_id

        reason = f"Detected {first_indicator!r} narrative elements"
        return best_phase, confidence, reason

    def get_phase_guidance(self) -> str:
        """
        Get narrative guidance for the current phase.

        Returns text that can be injected into the DM prompt
        to encourage phase-appropriate storytelling.
        """
        if self._is_heroic:
            guidance = {
                StoryPhase.ORDINARY_WORLD: (
                    "Establish the protagonist's normal world. Show their daily life, "
                    "relationships, and what they have to lose. Create empathy and baseline."
                ),
                StoryPhase.CALL_TO_ADVENTURE: (
                    "Present a challenge that disrupts the status quo. This could be a quest, "
                    "a mystery, a threat, or an opportunity. Make it compelling but allow hesitation."
                ),
                StoryPhase.REFUSAL_OF_THE_CALL: (
                    "Allow the protagonist to express doubt or fear. This humanizes them "
                    "and raises the stakes. The refusal can be internal or voiced."
                ),
                StoryPhase.MEETING_THE_MENTOR: (
                    "Introduce a guide figure who provides wisdom, tools, or training. "
                    "This prepares the protagonist for the challenges ahead."
                ),
                StoryPhase.CROSSING_THE_THRESHOLD: (
                    "Mark the point of no return. The protagonist commits to the adventure "
                    "and leaves the familiar world behind. This should feel significant."
                ),
                StoryPhase.TESTS_ALLIES_ENEMIES: (
                    "Present a series of challenges that reveal allies and enemies. "
                    "Build the world of the adventure and test the protagonist's abilities."
                ),
                StoryPhase.APPROACH_TO_INMOST_CAVE: (
                    "Build tension as the protagonist approaches the central challenge. "
                    "This is the calm before the storm - a time for preparation and dread."
                ),
                StoryPhase.ORDEAL: (
                    "Confront the protagonist with their greatest fear or challenge. "
                    "This should feel like a death-and-rebirth moment. Maximum stakes."
                ),
                StoryPhase.REWARD: (
                    "Celebrate the victory and claim the prize. But hint at complications - "
                    "the journey isn't over yet. Allow a moment of triumph."
                ),
                StoryPhase.THE_ROAD_BACK: (
                    "Begin the return journey with renewed urgency. The protagonist may be "
                    "pursued or face consequences of the ordeal. Tension rises again."
                ),
                StoryPhase.RESURRECTION: (
                    "Present a final test that requires everything learned on the journey. "
                    "This is the true transformation moment - choosing who to become."
                ),
                StoryPhase.RETURN_WITH_ELIXIR: (
                    "Bring the journey full circle. The protagonist returns changed, "
                    "bearing wisdom or gifts for their community. Close the narrative loop."
                ),
            }
            return guidance.get(self._state.current_phase, "Continue the narrative.")
        else:
            # Return the genre phase description as guidance
            phase = self.current_phase
            if isinstance(phase, GenrePhase):
                return phase.description
            return "Continue the narrative."

    def get_expected_beats(self) -> List[str]:
        """
        Get expected narrative beats for the current phase.

        Returns a list of story elements that typically appear in this phase.
        """
        if self._is_heroic:
            beats = {
                StoryPhase.ORDINARY_WORLD: [
                    "Establish protagonist's daily routine",
                    "Show important relationships",
                    "Hint at internal desire or flaw",
                    "Demonstrate what's at stake",
                ],
                StoryPhase.CALL_TO_ADVENTURE: [
                    "Present the inciting incident",
                    "Introduce the central dramatic question",
                    "Show why the protagonist is needed",
                    "Create urgency",
                ],
                StoryPhase.REFUSAL_OF_THE_CALL: [
                    "Express fear or self-doubt",
                    "Show the cost of action",
                    "Provide reasons to stay in ordinary world",
                    "Create internal conflict",
                ],
                StoryPhase.MEETING_THE_MENTOR: [
                    "Introduce the mentor figure",
                    "Provide training or knowledge",
                    "Give a significant gift or tool",
                    "Offer wisdom about the journey ahead",
                ],
                StoryPhase.CROSSING_THE_THRESHOLD: [
                    "Commit to the adventure",
                    "Leave the ordinary world",
                    "Enter unknown territory",
                    "Encounter threshold guardians",
                ],
                StoryPhase.TESTS_ALLIES_ENEMIES: [
                    "Face a series of challenges",
                    "Make new allies",
                    "Identify enemies",
                    "Learn the rules of the new world",
                ],
                StoryPhase.APPROACH_TO_INMOST_CAVE: [
                    "Prepare for the central ordeal",
                    "Gather resources and allies",
                    "Build tension and dread",
                    "Plan the approach",
                ],
                StoryPhase.ORDEAL: [
                    "Face the greatest fear",
                    "Experience a death-like moment",
                    "Confront the shadow/antagonist",
                    "Transform through crisis",
                ],
                StoryPhase.REWARD: [
                    "Claim the prize/treasure",
                    "Celebrate victory",
                    "Gain new knowledge or power",
                    "Experience brief relief",
                ],
                StoryPhase.THE_ROAD_BACK: [
                    "Begin the return journey",
                    "Face pursuit or consequences",
                    "Recommit to the return",
                    "Deal with aftermath of ordeal",
                ],
                StoryPhase.RESURRECTION: [
                    "Face final test",
                    "Use all lessons learned",
                    "Complete transformation",
                    "Make ultimate sacrifice or choice",
                ],
                StoryPhase.RETURN_WITH_ELIXIR: [
                    "Return to ordinary world",
                    "Share the elixir/wisdom",
                    "Show how protagonist changed",
                    "Establish new equilibrium",
                ],
            }
            return beats.get(self._state.current_phase, [])
        else:
            # For genre phases, use the beat templates from genre_arcs
            from .genre_arcs import get_beat_templates_for_phase

            phase_id = self.current_phase_id
            templates = get_beat_templates_for_phase(self._genre_arc, phase_id)
            return [t.get("template", "") for t in templates[:4]]

    def to_dict(self) -> Dict[str, Any]:
        """Export state as dictionary for persistence."""
        return {
            "arc_state": self._state.model_dump(),
            "transition_history": [t.model_dump() for t in self._transition_history],
            "genre_arc": self._genre_arc.value,
            "current_genre_phase_index": self._current_genre_phase_index if not self._is_heroic else 0,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryPhaseManager":
        """Restore from dictionary."""
        state = ArcState(**data.get("arc_state", {}))
        genre_arc = data.get("genre_arc", "heroic")
        manager = cls(initial_state=state, genre_arc=genre_arc)
        manager._transition_history = [
            PhaseTransition(**t) for t in data.get("transition_history", [])
        ]
        # Restore genre phase index
        if not manager._is_heroic:
            manager._current_genre_phase_index = data.get("current_genre_phase_index", 0)
        return manager
