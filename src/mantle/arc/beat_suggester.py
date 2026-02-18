# src/lms/arc/beat_suggester.py
"""
Beat Suggester - Recommends narrative beats for the DM.

Generates phase-appropriate narrative suggestions based on
current story state, tension, and Campbell structure.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
import uuid

from .models import (
    StoryPhase,
    TensionLevel,
    BeatType,
    NarrativeBeat,
    ArcState,
)

logger = logging.getLogger(__name__)


# Beat templates for each phase
PHASE_BEAT_TEMPLATES: Dict[StoryPhase, List[Dict[str, Any]]] = {
    StoryPhase.ORDINARY_WORLD: [
        {
            "type": BeatType.EXPOSITION,
            "template": "Show {character}'s daily routine and what matters to them",
            "tension_target": 0.15,
            "priority": 0.8,
        },
        {
            "type": BeatType.CHARACTER_MOMENT,
            "template": "Reveal an internal desire or flaw through small interactions",
            "tension_target": 0.2,
            "priority": 0.7,
        },
        {
            "type": BeatType.SOCIAL,
            "template": "Establish key relationships that will be tested later",
            "tension_target": 0.2,
            "priority": 0.6,
        },
    ],
    StoryPhase.CALL_TO_ADVENTURE: [
        {
            "type": BeatType.DISCOVERY,
            "template": "Present the inciting incident that disrupts normal life",
            "tension_target": 0.4,
            "priority": 0.9,
        },
        {
            "type": BeatType.CHOICE,
            "template": "Offer a clear call that demands a response",
            "tension_target": 0.45,
            "priority": 0.8,
        },
        {
            "type": BeatType.REVELATION,
            "template": "Reveal why {character} is uniquely suited for this challenge",
            "tension_target": 0.35,
            "priority": 0.6,
        },
    ],
    StoryPhase.REFUSAL_OF_THE_CALL: [
        {
            "type": BeatType.CHARACTER_MOMENT,
            "template": "Express fear, doubt, or reluctance about the journey",
            "tension_target": 0.3,
            "priority": 0.8,
        },
        {
            "type": BeatType.OBSTACLE,
            "template": "Present practical reasons why the quest seems impossible",
            "tension_target": 0.35,
            "priority": 0.7,
        },
        {
            "type": BeatType.CONSEQUENCE,
            "template": "Show the cost of both action and inaction",
            "tension_target": 0.4,
            "priority": 0.6,
        },
    ],
    StoryPhase.MEETING_THE_MENTOR: [
        {
            "type": BeatType.CHARACTER_MOMENT,
            "template": "Introduce the mentor figure with earned wisdom",
            "tension_target": 0.3,
            "priority": 0.9,
        },
        {
            "type": BeatType.DISCOVERY,
            "template": "Provide crucial knowledge or training",
            "tension_target": 0.35,
            "priority": 0.8,
        },
        {
            "type": BeatType.EXPOSITION,
            "template": "Gift a significant object, weapon, or magical aid",
            "tension_target": 0.35,
            "priority": 0.7,
        },
    ],
    StoryPhase.CROSSING_THE_THRESHOLD: [
        {
            "type": BeatType.CHOICE,
            "template": "Commit fully to the adventure - point of no return",
            "tension_target": 0.5,
            "priority": 0.9,
        },
        {
            "type": BeatType.OBSTACLE,
            "template": "Encounter threshold guardians who test resolve",
            "tension_target": 0.55,
            "priority": 0.7,
        },
        {
            "type": BeatType.DISCOVERY,
            "template": "Enter the unfamiliar world of the adventure",
            "tension_target": 0.5,
            "priority": 0.8,
        },
    ],
    StoryPhase.TESTS_ALLIES_ENEMIES: [
        {
            "type": BeatType.OBSTACLE,
            "template": "Face a test that reveals character strengths or weaknesses",
            "tension_target": 0.55,
            "priority": 0.8,
        },
        {
            "type": BeatType.SOCIAL,
            "template": "Encounter a potential ally who must be won over",
            "tension_target": 0.5,
            "priority": 0.7,
        },
        {
            "type": BeatType.COMBAT,
            "template": "Clash with enemies who represent the antagonist's power",
            "tension_target": 0.6,
            "priority": 0.7,
        },
        {
            "type": BeatType.SETBACK,
            "template": "Suffer a betrayal or unexpected complication",
            "tension_target": 0.65,
            "priority": 0.6,
        },
    ],
    StoryPhase.APPROACH_TO_INMOST_CAVE: [
        {
            "type": BeatType.EXPOSITION,
            "template": "Reveal the nature of the central challenge ahead",
            "tension_target": 0.7,
            "priority": 0.8,
        },
        {
            "type": BeatType.SOCIAL,
            "template": "Final bonding moment with allies before the ordeal",
            "tension_target": 0.65,
            "priority": 0.7,
        },
        {
            "type": BeatType.REST,
            "template": "Brief calm before the storm - preparation and dread",
            "tension_target": 0.6,
            "priority": 0.6,
        },
    ],
    StoryPhase.ORDEAL: [
        {
            "type": BeatType.COMBAT,
            "template": "Face the supreme challenge - everything at stake",
            "tension_target": 0.95,
            "priority": 0.95,
        },
        {
            "type": BeatType.SETBACK,
            "template": "Experience apparent defeat or death moment",
            "tension_target": 0.9,
            "priority": 0.8,
        },
        {
            "type": BeatType.REVELATION,
            "template": "Discover hidden truth that changes everything",
            "tension_target": 0.85,
            "priority": 0.7,
        },
        {
            "type": BeatType.CHOICE,
            "template": "Make the crucial decision that defines the hero",
            "tension_target": 0.9,
            "priority": 0.85,
        },
    ],
    StoryPhase.REWARD: [
        {
            "type": BeatType.VICTORY,
            "template": "Claim the treasure, knowledge, or reconciliation sought",
            "tension_target": 0.5,
            "priority": 0.9,
        },
        {
            "type": BeatType.CHARACTER_MOMENT,
            "template": "Moment of celebration or relief after survival",
            "tension_target": 0.45,
            "priority": 0.7,
        },
        {
            "type": BeatType.DISCOVERY,
            "template": "Recognize the transformation that has occurred",
            "tension_target": 0.5,
            "priority": 0.6,
        },
    ],
    StoryPhase.THE_ROAD_BACK: [
        {
            "type": BeatType.OBSTACLE,
            "template": "Face pursuit or consequences of claiming the reward",
            "tension_target": 0.65,
            "priority": 0.8,
        },
        {
            "type": BeatType.CHOICE,
            "template": "Recommit to the return despite new complications",
            "tension_target": 0.6,
            "priority": 0.7,
        },
        {
            "type": BeatType.CONSEQUENCE,
            "template": "Deal with the aftermath of the ordeal",
            "tension_target": 0.55,
            "priority": 0.6,
        },
    ],
    StoryPhase.RESURRECTION: [
        {
            "type": BeatType.COMBAT,
            "template": "Final confrontation using all lessons learned",
            "tension_target": 0.9,
            "priority": 0.95,
        },
        {
            "type": BeatType.CHOICE,
            "template": "Make the ultimate sacrifice or defining choice",
            "tension_target": 0.85,
            "priority": 0.85,
        },
        {
            "type": BeatType.REVELATION,
            "template": "Complete transformation - death of the old self",
            "tension_target": 0.8,
            "priority": 0.7,
        },
    ],
    StoryPhase.RETURN_WITH_ELIXIR: [
        {
            "type": BeatType.VICTORY,
            "template": "Return home transformed, bearing the elixir",
            "tension_target": 0.25,
            "priority": 0.9,
        },
        {
            "type": BeatType.SOCIAL,
            "template": "Share the wisdom or gift with the community",
            "tension_target": 0.2,
            "priority": 0.8,
        },
        {
            "type": BeatType.CHARACTER_MOMENT,
            "template": "Demonstrate how the journey has changed the hero",
            "tension_target": 0.2,
            "priority": 0.7,
        },
    ],
}


class BeatSuggester:
    """
    Generates narrative beat suggestions for the DM.

    Uses the current story phase and tension state to recommend
    appropriate narrative beats while respecting player agency.

    Supports genre-specific beat templates for non-heroic arcs.
    """

    def __init__(self):
        """Initialize the beat suggester."""
        self._recent_beat_types: List[BeatType] = []
        self._max_recent = 5

    def suggest_beats(
        self,
        phase,  # StoryPhase or GenrePhase
        current_tension: float,
        count: int = 3,
        avoid_types: Optional[List[BeatType]] = None,
        genre_arc: Optional[str] = None,
    ) -> List[NarrativeBeat]:
        """
        Generate beat suggestions for the current narrative moment.

        Args:
            phase: Current story phase (StoryPhase or GenrePhase)
            current_tension: Current tension level (0.0-1.0)
            count: Number of suggestions to return
            avoid_types: Beat types to avoid (for variety)
            genre_arc: Optional genre arc type for genre-specific templates

        Returns:
            List of suggested narrative beats, sorted by priority
        """
        avoid_types = avoid_types or []

        # Get phase ID as string (works for both StoryPhase and GenrePhase)
        phase_id = phase.id if hasattr(phase, 'id') else phase.value

        # Get templates - prefer genre-specific if available
        templates = []
        if genre_arc and genre_arc != "heroic":
            from .genre_arcs import GenreArcType, get_beat_templates_for_phase
            try:
                arc_type = GenreArcType(genre_arc)
                templates = get_beat_templates_for_phase(arc_type, phase_id)
            except (ValueError, KeyError):
                pass  # Fall back to default templates

        # Fall back to Campbell templates if no genre templates found
        if not templates:
            templates = PHASE_BEAT_TEMPLATES.get(phase, [])

        # Score and filter templates
        scored_beats = []
        for template in templates:
            # Handle beat type as either BeatType enum or string
            beat_type = template["type"]
            if isinstance(beat_type, str):
                try:
                    beat_type = BeatType(beat_type.lower())
                except ValueError:
                    continue  # Skip invalid beat types

            if beat_type in avoid_types:
                continue

            # Avoid repeating recent beat types
            if beat_type in self._recent_beat_types[-2:]:
                continue

            # Calculate score based on tension alignment and priority
            tension_diff = abs(template["tension_target"] - current_tension)
            tension_score = 1.0 - (tension_diff * 0.5)  # Penalize tension mismatch
            total_score = template["priority"] * tension_score

            beat = NarrativeBeat(
                beat_type=beat_type,
                description=template["template"],
                phase_alignment=phase_id,
                tension_target=template["tension_target"],
                priority=total_score,
            )
            scored_beats.append((total_score, beat))

        # Sort by score and return top suggestions
        scored_beats.sort(key=lambda x: x[0], reverse=True)
        return [beat for _, beat in scored_beats[:count]]

    def record_beat_used(self, beat_type: BeatType) -> None:
        """Record that a beat type was used (for variety tracking)."""
        self._recent_beat_types.append(beat_type)
        if len(self._recent_beat_types) > self._max_recent:
            self._recent_beat_types.pop(0)

    def suggest_tension_adjustment_beat(
        self,
        current_tension: float,
        target_tension: float,
        phase,  # StoryPhase or GenrePhase
    ) -> Optional[NarrativeBeat]:
        """
        Suggest a beat specifically to adjust tension toward target.

        Args:
            current_tension: Current tension level
            target_tension: Desired tension level
            phase: Current story phase (StoryPhase or GenrePhase)

        Returns:
            A beat suggestion designed to move tension in the right direction
        """
        # Get phase ID as string
        phase_id = phase.id if hasattr(phase, 'id') else phase.value

        needs_increase = target_tension > current_tension + 0.1
        needs_decrease = target_tension < current_tension - 0.1

        if needs_increase:
            escalating_types = [
                BeatType.COMBAT,
                BeatType.OBSTACLE,
                BeatType.SETBACK,
                BeatType.REVELATION,
                BeatType.CLIFFHANGER,
            ]
            for template in PHASE_BEAT_TEMPLATES.get(phase, []):
                if template["type"] in escalating_types:
                    return NarrativeBeat(
                        beat_type=template["type"],
                        description=f"[Escalate] {template['template']}",
                        phase_alignment=phase_id,
                        tension_target=target_tension,
                        priority=0.9,
                    )
            # Generic escalation
            return NarrativeBeat(
                beat_type=BeatType.OBSTACLE,
                description="Introduce an unexpected complication or danger",
                phase_alignment=phase_id,
                tension_target=target_tension,
                priority=0.8,
            )

        elif needs_decrease:
            calming_types = [
                BeatType.REST,
                BeatType.VICTORY,
                BeatType.CHARACTER_MOMENT,
                BeatType.SOCIAL,
            ]
            for template in PHASE_BEAT_TEMPLATES.get(phase, []):
                if template["type"] in calming_types:
                    return NarrativeBeat(
                        beat_type=template["type"],
                        description=f"[Release] {template['template']}",
                        phase_alignment=phase_id,
                        tension_target=target_tension,
                        priority=0.9,
                    )
            # Generic de-escalation
            return NarrativeBeat(
                beat_type=BeatType.REST,
                description="Allow a moment of calm or reflection",
                phase_alignment=phase_id,
                tension_target=target_tension,
                priority=0.8,
            )

        return None

    def suggest_cliffhanger(self, phase) -> NarrativeBeat:
        """
        Suggest a cliffhanger beat for ending an episode.

        Args:
            phase: Current story phase (StoryPhase or GenrePhase)

        Returns:
            A cliffhanger beat appropriate for the phase
        """
        # Get phase ID as string
        phase_id = phase.id if hasattr(phase, 'id') else phase.value

        # Campbell cliffhangers for heroic arcs
        heroic_cliffhangers = {
            "ordinary_world": "A mysterious stranger arrives with urgent news",
            "call_to_adventure": "The full scope of the threat is revealed",
            "refusal_of_the_call": "The cost of refusal becomes tragically clear",
            "meeting_the_mentor": "The mentor reveals a dark secret about the quest",
            "crossing_the_threshold": "The first true danger of the new world appears",
            "tests_allies_enemies": "An ally's loyalty comes into question",
            "approach_to_inmost_cave": "The true nature of the ordeal is glimpsed",
            "ordeal": "At the moment of crisis, an unexpected twist",
            "reward": "The victory is revealed to have a terrible price",
            "the_road_back": "The enemy was not truly defeated",
            "resurrection": "The final choice presents itself",
            "return_with_elixir": "Seeds of a new adventure are planted",
        }

        # Genre-specific cliffhangers
        genre_cliffhangers = {
            # Horror
            "normalcy": "Something is wrong with the familiar",
            "intrusion": "The horror reveals itself briefly",
            "investigation": "A terrible truth emerges",
            "descent": "Escape routes close off one by one",
            "confrontation": "The horror shows its true nature",
            "cost": "Someone must make an impossible choice",
            "survival": "The nightmare seems to end... but does it?",
            "aftermath": "Seeds of future dread are planted",
            # Mystery
            "crime": "The crime is worse than it first appeared",
            "scene": "A vital clue points in an unexpected direction",
            "suspects": "The prime suspect has an alibi... or do they?",
            "complications": "A new crime changes everything",
            "breakthrough": "The key evidence comes with a cost",
            "resolution": "Justice comes, but questions remain",
            # Heist
            "opportunity": "The score is bigger than imagined",
            "assembly": "A crucial team member has secrets",
            "planning": "A flaw in the plan is discovered",
            "preparation": "Someone is watching",
            "execution": "Everything goes wrong at once",
            "complication": "The real threat reveals itself",
            "escape": "Freedom is within reach... but at what cost?",
        }

        # Combine both dictionaries
        all_cliffhangers = {**heroic_cliffhangers, **genre_cliffhangers}
        description = all_cliffhangers.get(phase_id, "End on an unresolved moment of tension")

        return NarrativeBeat(
            beat_type=BeatType.CLIFFHANGER,
            description=description,
            phase_alignment=phase_id,
            tension_target=0.75,
            priority=1.0,
        )

    def get_beat_guidance(self, beat: NarrativeBeat) -> str:
        """
        Get detailed guidance for executing a beat.

        Args:
            beat: The narrative beat to elaborate on

        Returns:
            Detailed guidance text for the DM
        """
        type_guidance = {
            BeatType.EXPOSITION: (
                "Weave world-building naturally into the scene. Show, don't tell. "
                "Use sensory details and character reactions to convey information."
            ),
            BeatType.CHARACTER_MOMENT: (
                "Focus on revealing character through action and dialogue. "
                "Small choices reveal personality. Let NPCs have their own agendas."
            ),
            BeatType.DISCOVERY: (
                "Create a moment of revelation that changes understanding. "
                "Let the player piece things together rather than info-dumping."
            ),
            BeatType.OBSTACLE: (
                "Present a challenge that requires choice or sacrifice. "
                "Multiple solutions should exist. Failure should be meaningful."
            ),
            BeatType.COMBAT: (
                "Describe the stakes clearly. Use the environment. "
                "Combat should reveal character and advance the story."
            ),
            BeatType.SOCIAL: (
                "NPCs have their own goals and knowledge. "
                "Dialogue should feel like negotiation, not exposition."
            ),
            BeatType.PUZZLE: (
                "Clues should be fair but not obvious. "
                "Multiple approaches should work. Reward clever thinking."
            ),
            BeatType.CHOICE: (
                "Present meaningful alternatives with real consequences. "
                "No choice should be obviously 'correct'. Honor the player's decision."
            ),
            BeatType.CONSEQUENCE: (
                "Show how past choices ripple forward. "
                "Consequences should feel earned, not punitive."
            ),
            BeatType.REVELATION: (
                "Build to the moment. Let it land. "
                "The revelation should recontextualize what came before."
            ),
            BeatType.SETBACK: (
                "Failure should open new paths, not close them. "
                "Setbacks test resolve and force growth."
            ),
            BeatType.VICTORY: (
                "Celebrate the achievement. Let the player feel powerful. "
                "Then hint at what comes next."
            ),
            BeatType.REST: (
                "Quiet moments build anticipation. "
                "Use downtime for character development and foreshadowing."
            ),
            BeatType.CLIFFHANGER: (
                "End at the moment of maximum uncertainty. "
                "The question should be 'what happens next?' not 'what happened?'"
            ),
        }

        return type_guidance.get(beat.beat_type, "Execute this beat with attention to pacing.")

    def to_dict(self) -> Dict[str, Any]:
        """Export state for persistence."""
        return {
            "recent_beat_types": [bt.value for bt in self._recent_beat_types],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeatSuggester":
        """Restore from dictionary."""
        suggester = cls()
        suggester._recent_beat_types = [
            BeatType(bt) for bt in data.get("recent_beat_types", [])
        ]
        return suggester
