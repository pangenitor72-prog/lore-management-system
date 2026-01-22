# src/airpg/runtime/gameplay_rules.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Literal, Optional, Union

from .session_state import SessionState


@dataclass(frozen=True)
class Intervention:
    """
    Pauses the session loop to request external input from the player.

    Used for RPG/MANUAL mode to request dice rolls, confirmations, or choices.

    Attributes:
        type: The kind of intervention needed
            - INPUT_REQUEST: Need a value (e.g., dice roll result)
            - CONFIRMATION: Yes/No decision
            - CHOICE: Select from options
        prompt: Human-readable prompt to show the player
        context: Additional data for the intervention (DC, skill, options, etc.)
        resume_key: Identifier for matching response to intervention
    """
    type: Literal["INPUT_REQUEST", "CONFIRMATION", "CHOICE"]
    prompt: str
    context: Dict[str, any] = field(default_factory=dict)
    resume_key: str = ""


# Rule return types:
# - str: Transformed message, continue processing
# - None: Block the message entirely
# - Intervention: Pause loop and request external input
RuleResult = Union[str, None, Intervention]

# A GameplayRule is a pure function that takes a message and the current
# session state, and returns either a transformed message, None to block,
# or an Intervention to pause and request input.
GameplayRule = Callable[[str, SessionState], RuleResult]

# This function will be implemented in Task C
def rule_prevent_attack_on_turn_3(
    message: str, state: SessionState
) -> Optional[str]:
    """
    Example gameplay rule: If the turn index is 2 or more and the message
    contains "attack", transform it. Otherwise, allow it.
    """
    if state.turn_index >= 2 and "attack" in message.lower():
        return "hesitates instead of attacking"
    return message
