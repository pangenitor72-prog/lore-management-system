# src/airpg/runtime/game_config.py
"""
Game configuration for dual-mode gameplay.

Supports two player archetypes:
- Casual (One-Shot): Quick, low-friction narrative experiences
- Hardcore (Campaign): Deep RPG with manual dice and persistent worlds

All defaults favor the Casual experience (low friction).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class GameConfig(BaseModel):
    """
    Configuration object that dictates simulation complexity.

    All defaults favor "Casual / One-Shot" experience:
    - STORY mode (no visible mechanics)
    - NARRATIVE dice (AI handles outcomes)
    - CONCISE text (action-focused, not literary)
    - ONE_SHOT scope (AI drives to climax in ~200 turns)
    """

    # MODE: Determines if we use strict rules or just story logic
    mode: Literal["STORY", "RPG"] = "STORY"

    # MECHANICS: How dice are handled (Hidden vs Manual)
    dice_mechanic: Literal["NARRATIVE", "AUTO", "MANUAL"] = "NARRATIVE"

    # COMPLEXITY: Text depth. CONCISE = short, action-focused. VERBOSE = immersive, literary
    narrative_complexity: Literal["CONCISE", "VERBOSE"] = "CONCISE"

    # SCOPE: Duration. ONE_SHOT = AI drives to climax (~200 turns). CAMPAIGN = endless open world
    session_scope: Literal["ONE_SHOT", "CAMPAIGN"] = "ONE_SHOT"

    # Pacing thresholds for ONE_SHOT mode
    climax_start_turn: int = 150
    max_turns: int = 200

    def requires_dice(self) -> bool:
        """Returns True if this config requires dice rolling."""
        return self.mode == "RPG" and self.dice_mechanic != "NARRATIVE"

    def is_manual_rolls(self) -> bool:
        """Returns True if player must provide dice roll values."""
        return self.mode == "RPG" and self.dice_mechanic == "MANUAL"

    def is_one_shot(self) -> bool:
        """Returns True if this is a time-limited one-shot session."""
        return self.session_scope == "ONE_SHOT"

    def is_verbose(self) -> bool:
        """Returns True if verbose/literary narrative is enabled."""
        return self.narrative_complexity == "VERBOSE"

    def get_pacing_phase(self, turn: int) -> Literal["INTRO", "RISING", "CLIMAX", "END"]:
        """
        Determine narrative pacing phase for ONE_SHOT mode.

        Args:
            turn: Current turn number (0-indexed)

        Returns:
            Pacing phase for DMAgent guidance
        """
        if not self.is_one_shot():
            return "RISING"  # Campaign mode is always open

        if turn < 3:
            return "INTRO"
        elif turn < self.climax_start_turn:
            return "RISING"
        elif turn < self.max_turns:
            return "CLIMAX"
        else:
            return "END"

    model_config = {"frozen": True}


# Preset configurations for easy selection
CASUAL_CONFIG = GameConfig()  # All defaults = casual one-shot

HARDCORE_CONFIG = GameConfig(
    mode="RPG",
    dice_mechanic="MANUAL",
    narrative_complexity="VERBOSE",
    session_scope="CAMPAIGN",
)

RPG_AUTO_CONFIG = GameConfig(
    mode="RPG",
    dice_mechanic="AUTO",
    narrative_complexity="CONCISE",
    session_scope="ONE_SHOT",
)
