"""Character creation modes and rules visibility settings."""

from enum import Enum
from typing import Dict


class CreationMode(str, Enum):
    """
    Character creation modes with increasing complexity.

    CONCEPT: Player describes character in natural language, AI generates stats
    GUIDED: Step-by-step with explanations, simplified choices
    CLASSIC: Standard PHB-style creation
    EXPERT: Full control with point-buy, all options
    """
    CONCEPT = "concept"
    GUIDED = "guided"
    CLASSIC = "classic"
    EXPERT = "expert"


class RulesVisibility(str, Enum):
    """
    How much mechanical detail to show the player.

    STORYTELLER: Pure narrative, no numbers shown
    GUIDED: Light hints and context ("your training helped here")
    CLASSIC: Standard D&D presentation (rolls and DCs shown)
    TACTICIAN: Full mechanical breakdown
    """
    STORYTELLER = "storyteller"
    GUIDED = "guided"
    CLASSIC = "classic"
    TACTICIAN = "tactician"


# Smart defaults: creation mode pairs with visibility mode
DEFAULT_VISIBILITY: Dict[CreationMode, RulesVisibility] = {
    CreationMode.CONCEPT: RulesVisibility.STORYTELLER,
    CreationMode.GUIDED: RulesVisibility.GUIDED,
    CreationMode.CLASSIC: RulesVisibility.CLASSIC,
    CreationMode.EXPERT: RulesVisibility.TACTICIAN,
}


# XP thresholds for progressive unlock suggestions
UNLOCK_THRESHOLDS = {
    "sessions_played": {
        RulesVisibility.GUIDED: 3,    # After 3 sessions, suggest guided
        RulesVisibility.CLASSIC: 10,   # After 10 sessions, suggest classic
        RulesVisibility.TACTICIAN: 20, # After 20 sessions, suggest tactician
    },
    "combats_survived": {
        RulesVisibility.GUIDED: 5,
        RulesVisibility.CLASSIC: 15,
        RulesVisibility.TACTICIAN: 30,
    },
}


def get_mode_description(mode: CreationMode) -> Dict[str, str]:
    """Get user-friendly description of a creation mode."""
    descriptions = {
        CreationMode.CONCEPT: {
            "title": "Quick Start",
            "icon": "✨",
            "short": "Describe your character, we handle the rest",
            "long": "Simply describe your character concept in a few sentences, and "
                    "we'll generate a complete character sheet for you. Perfect for "
                    "new players or quick starts.",
        },
        CreationMode.GUIDED: {
            "title": "Guided",
            "icon": "📖",
            "short": "Step-by-step with explanations",
            "long": "Answer simple questions about your character and receive "
                    "recommendations. Each choice is explained in plain language, "
                    "making it easy to understand your options.",
        },
        CreationMode.CLASSIC: {
            "title": "Classic",
            "icon": "⚔️",
            "short": "Traditional character creation",
            "long": "Follow the standard D&D character creation process: choose "
                    "race, class, assign ability scores, select skills, and pick "
                    "equipment. Familiar to experienced players.",
        },
        CreationMode.EXPERT: {
            "title": "Expert",
            "icon": "🎯",
            "short": "Full control over every choice",
            "long": "Complete control with point-buy ability scores and access to "
                    "all options. For players who know exactly what they want to build.",
        },
    }
    return descriptions[mode]


def get_visibility_description(visibility: RulesVisibility) -> Dict[str, str]:
    """Get user-friendly description of a visibility mode."""
    descriptions = {
        RulesVisibility.STORYTELLER: {
            "title": "Storyteller",
            "icon": "📜",
            "short": "Pure narrative experience",
            "example": '"You narrowly avoid the trap, your quick reflexes saving you."',
        },
        RulesVisibility.GUIDED: {
            "title": "Guided",
            "icon": "💡",
            "short": "Narrative with helpful hints",
            "example": '"You avoid the trap (your Dexterity helped here)."',
        },
        RulesVisibility.CLASSIC: {
            "title": "Classic",
            "icon": "🎲",
            "short": "Show key rolls and results",
            "example": '"DEX save: 15 vs DC 14 - Success! You avoid the trap."',
        },
        RulesVisibility.TACTICIAN: {
            "title": "Tactician",
            "icon": "📊",
            "short": "Full mechanical breakdown",
            "example": '"DEX save: d20(12)+3=15 vs DC 14. Pass by 1. No damage taken."',
        },
    }
    return descriptions[visibility]


def should_suggest_unlock(
    current_visibility: RulesVisibility,
    sessions_played: int,
    combats_survived: int,
) -> RulesVisibility | None:
    """
    Check if player might be ready for a more detailed visibility mode.

    Returns the suggested mode, or None if no suggestion.
    """
    # Get ordered list of visibility modes
    order = [
        RulesVisibility.STORYTELLER,
        RulesVisibility.GUIDED,
        RulesVisibility.CLASSIC,
        RulesVisibility.TACTICIAN,
    ]

    current_idx = order.index(current_visibility)

    # Check if already at max
    if current_idx >= len(order) - 1:
        return None

    next_mode = order[current_idx + 1]

    # Check thresholds
    session_threshold = UNLOCK_THRESHOLDS["sessions_played"].get(next_mode, 999)
    combat_threshold = UNLOCK_THRESHOLDS["combats_survived"].get(next_mode, 999)

    if sessions_played >= session_threshold or combats_survived >= combat_threshold:
        return next_mode

    return None
