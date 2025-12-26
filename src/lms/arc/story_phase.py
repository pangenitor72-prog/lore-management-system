# src/lms/arc/story_phase.py
"""
Story Phase Manager - State machine for Campbell's Hero's Journey.

Tracks the current phase of the narrative and manages transitions
based on story events and player actions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from .models import (
    StoryPhase,
    StoryAct,
    ArcState,
    PhaseTransition,
    VALID_TRANSITIONS,
    is_valid_transition,
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
    Manages the Hero's Journey phase state machine.

    Responsibilities:
    - Track current phase
    - Validate and execute phase transitions
    - Detect phase-relevant content in narrative
    - Provide phase-appropriate guidance
    """

    def __init__(self, initial_state: Optional[ArcState] = None):
        """
        Initialize the phase manager.

        Args:
            initial_state: Optional existing arc state to resume from
        """
        self._state = initial_state or ArcState()
        self._transition_history: List[PhaseTransition] = []

    @property
    def current_phase(self) -> StoryPhase:
        """Get the current story phase."""
        return self._state.current_phase

    @property
    def current_act(self) -> StoryAct:
        """Get the current act based on phase."""
        return self._state.get_act()

    @property
    def state(self) -> ArcState:
        """Get the full arc state."""
        return self._state

    def get_valid_next_phases(self) -> List[StoryPhase]:
        """Get list of valid phases we can transition to."""
        return VALID_TRANSITIONS.get(self.current_phase, [])

    def can_transition_to(self, target_phase: StoryPhase) -> bool:
        """Check if we can transition to the target phase."""
        return is_valid_transition(self.current_phase, target_phase)

    def transition_to(
        self,
        target_phase: StoryPhase,
        trigger: str,
        confidence: float = 0.8,
        force: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Attempt to transition to a new phase.

        Args:
            target_phase: The phase to transition to
            trigger: Description of what caused the transition
            confidence: How confident we are in this transition (0.0-1.0)
            force: If True, allow non-standard transitions

        Returns:
            Tuple of (success, error_message)
        """
        if not force and not self.can_transition_to(target_phase):
            return False, f"Invalid transition from {self.current_phase.value} to {target_phase.value}"

        # Record the transition
        transition = PhaseTransition(
            from_phase=self.current_phase,
            to_phase=target_phase,
            trigger=trigger,
            confidence=confidence,
        )
        self._transition_history.append(transition)

        # Update state
        old_phase = self.current_phase
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

    def detect_phase_signals(self, text: str) -> Dict[StoryPhase, float]:
        """
        Analyze text for phase transition signals.

        Returns a dict of phases to confidence scores based on
        keyword matching. This is a simple heuristic - the LLM
        should make final phase decisions.

        Args:
            text: Narrative text to analyze

        Returns:
            Dict mapping phases to confidence scores (0.0-1.0)
        """
        text_lower = text.lower()
        scores: Dict[StoryPhase, float] = {}

        for phase, keywords in PHASE_INDICATORS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches > 0:
                # Normalize by number of keywords for this phase
                score = min(1.0, matches / (len(keywords) * 0.3))
                scores[phase] = score

        return scores

    def suggest_transition(self, text: str) -> Optional[Tuple[StoryPhase, float, str]]:
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

        # Only consider valid next phases
        valid_signals = {
            phase: score
            for phase, score in signals.items()
            if self.can_transition_to(phase)
        }

        if not valid_signals:
            return None

        # Find the strongest signal
        best_phase = max(valid_signals, key=valid_signals.get)
        confidence = valid_signals[best_phase]

        # Only suggest if confidence is above threshold
        if confidence < 0.3:
            return None

        reason = f"Detected {PHASE_INDICATORS[best_phase][0]!r} narrative elements"
        return best_phase, confidence, reason

    def get_phase_guidance(self) -> str:
        """
        Get narrative guidance for the current phase.

        Returns text that can be injected into the DM prompt
        to encourage phase-appropriate storytelling.
        """
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
        return guidance.get(self.current_phase, "Continue the narrative.")

    def get_expected_beats(self) -> List[str]:
        """
        Get expected narrative beats for the current phase.

        Returns a list of story elements that typically appear in this phase.
        """
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
        return beats.get(self.current_phase, [])

    def to_dict(self) -> Dict[str, Any]:
        """Export state as dictionary for persistence."""
        return {
            "arc_state": self._state.model_dump(),
            "transition_history": [t.model_dump() for t in self._transition_history],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryPhaseManager":
        """Restore from dictionary."""
        state = ArcState(**data.get("arc_state", {}))
        manager = cls(initial_state=state)
        manager._transition_history = [
            PhaseTransition(**t) for t in data.get("transition_history", [])
        ]
        return manager
