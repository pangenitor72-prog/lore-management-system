# src/lms/arc/tension_tracker.py
"""
Tension Tracker - Monitors narrative tension and pacing.

Tracks rising/falling action and provides guidance on when to
escalate, maintain, or release dramatic tension.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Deque

from .models import TensionLevel, StoryPhase, ArcState

logger = logging.getLogger(__name__)


# Keywords that suggest tension changes
TENSION_MODIFIERS: Dict[str, float] = {
    # Escalating keywords (+)
    "danger": 0.15,
    "attack": 0.2,
    "threat": 0.15,
    "fight": 0.2,
    "battle": 0.25,
    "death": 0.2,
    "dying": 0.2,
    "kill": 0.15,
    "scream": 0.1,
    "fear": 0.1,
    "terror": 0.15,
    "chase": 0.15,
    "flee": 0.1,
    "urgent": 0.1,
    "hurry": 0.1,
    "enemy": 0.1,
    "trap": 0.15,
    "ambush": 0.2,
    "betrayal": 0.2,
    "confront": 0.15,
    "showdown": 0.2,

    # De-escalating keywords (-)
    "rest": -0.15,
    "sleep": -0.1,
    "calm": -0.15,
    "peaceful": -0.2,
    "safe": -0.15,
    "relax": -0.1,
    "friend": -0.05,
    "ally": -0.05,
    "help": -0.05,
    "heal": -0.1,
    "recover": -0.1,
    "sanctuary": -0.15,
    "haven": -0.15,
    "home": -0.1,
    "victory": -0.1,  # Brief relief after success
    "succeeded": -0.1,
    "laugh": -0.1,
    "smile": -0.05,
    "celebrate": -0.1,
}


class TensionTracker:
    """
    Tracks and manages narrative tension levels.

    Responsibilities:
    - Monitor current tension level (0.0-1.0)
    - Track tension history for trend analysis
    - Detect tension changes in narrative text
    - Provide pacing guidance to the DM
    """

    def __init__(
        self,
        initial_tension: float = 0.2,
        history_size: int = 20,
    ):
        """
        Initialize the tension tracker.

        Args:
            initial_tension: Starting tension level (0.0-1.0)
            history_size: How many tension readings to keep for trend analysis
        """
        self._current_tension = max(0.0, min(1.0, initial_tension))
        self._history: Deque[float] = deque(maxlen=history_size)
        self._history.append(self._current_tension)
        self._last_update = datetime.now(timezone.utc)

    @property
    def current_tension(self) -> float:
        """Get the current tension level (0.0-1.0)."""
        return self._current_tension

    @property
    def tension_level(self) -> TensionLevel:
        """Get qualitative tension level."""
        return TensionLevel.from_value(self._current_tension)

    @property
    def trend(self) -> str:
        """Get the current tension trend: 'rising', 'falling', or 'stable'."""
        if len(self._history) < 3:
            return "stable"

        recent = list(self._history)[-5:]
        if len(recent) < 2:
            return "stable"

        # Calculate average change
        changes = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        avg_change = sum(changes) / len(changes)

        if avg_change > 0.02:
            return "rising"
        elif avg_change < -0.02:
            return "falling"
        else:
            return "stable"

    def set_tension(self, value: float) -> None:
        """
        Set tension to an absolute value.

        Args:
            value: New tension level (0.0-1.0)
        """
        self._current_tension = max(0.0, min(1.0, value))
        self._history.append(self._current_tension)
        self._last_update = datetime.now(timezone.utc)

    def adjust_tension(self, delta: float) -> float:
        """
        Adjust tension by a relative amount.

        Args:
            delta: Amount to change tension by (can be negative)

        Returns:
            New tension level
        """
        self._current_tension = max(0.0, min(1.0, self._current_tension + delta))
        self._history.append(self._current_tension)
        self._last_update = datetime.now(timezone.utc)
        return self._current_tension

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze narrative text for tension modifiers.

        Args:
            text: Narrative text to analyze

        Returns:
            Dict with analysis results including suggested tension change
        """
        text_lower = text.lower()
        escalators = []
        de_escalators = []
        total_modifier = 0.0

        for keyword, modifier in TENSION_MODIFIERS.items():
            if keyword in text_lower:
                total_modifier += modifier
                if modifier > 0:
                    escalators.append(keyword)
                else:
                    de_escalators.append(keyword)

        # Dampen extreme swings
        total_modifier = max(-0.3, min(0.3, total_modifier))

        return {
            "suggested_change": total_modifier,
            "escalators": escalators,
            "de_escalators": de_escalators,
            "current_tension": self._current_tension,
            "projected_tension": max(0.0, min(1.0, self._current_tension + total_modifier)),
        }

    def apply_text_analysis(self, text: str) -> float:
        """
        Analyze text and apply the suggested tension change.

        Args:
            text: Narrative text to analyze

        Returns:
            New tension level
        """
        analysis = self.analyze_text(text)
        if abs(analysis["suggested_change"]) > 0.01:
            self.adjust_tension(analysis["suggested_change"])
            logger.debug(
                f"Tension adjusted by {analysis['suggested_change']:.2f} "
                f"to {self._current_tension:.2f}"
            )
        return self._current_tension

    def align_to_phase(
        self,
        phase: StoryPhase,
        strength: float = 0.3,
        tension_override: Optional[float] = None,
    ) -> float:
        """
        Gradually align tension toward the expected level for a phase.

        Args:
            phase: The current story phase
            strength: How strongly to pull toward expected tension (0.0-1.0)
            tension_override: Optional override for expected tension (e.g. from lethality preference)

        Returns:
            New tension level
        """
        expected = tension_override if tension_override is not None else phase.expected_tension
        current = self._current_tension
        delta = (expected - current) * strength
        return self.adjust_tension(delta)

    def get_pacing_guidance(
        self,
        phase: StoryPhase,
        lethality: Optional[str] = None,
    ) -> str:
        """
        Get pacing guidance based on current tension vs. expected.

        Args:
            phase: Current story phase
            lethality: Optional lethality preference to adjust expected tension
                       and phase-specific language

        Returns:
            Guidance text for the DM
        """
        # Use lethality-adjusted tension target when available
        if lethality:
            from .preference_adapter import get_adapted_tension_target
            expected = get_adapted_tension_target(phase, lethality)
        else:
            expected = phase.expected_tension

        current = self._current_tension
        diff = current - expected

        if diff > 0.2:
            # Tension too high for this phase
            if phase == StoryPhase.ORDINARY_WORLD:
                return "Tension is unusually high for the Ordinary World. Consider a calming scene."
            elif phase == StoryPhase.REWARD:
                return "Allow more celebration and relief after the Ordeal before introducing new tension."
            else:
                return f"Tension ({current:.1%}) is above expected ({expected:.1%}). Consider a breathing moment."

        elif diff < -0.2:
            # Tension too low for this phase
            if phase == StoryPhase.ORDEAL:
                # Adapt language based on lethality
                if lethality == "plot_armor":
                    return "The Ordeal should feel emotionally overwhelming. Raise the personal stakes."
                elif lethality == "brutal":
                    return "The Ordeal should feel genuinely lethal. This could be the end. Escalate ruthlessly."
                else:
                    return "The Ordeal should feel like everything is at stake. Escalate dramatically."
            elif phase == StoryPhase.APPROACH_TO_INMOST_CAVE:
                return "Build more dread as you approach the central challenge."
            else:
                return f"Tension ({current:.1%}) is below expected ({expected:.1%}). Consider raising stakes."

        else:
            # Tension is appropriate
            trend = self.trend
            if trend == "rising" and expected < 0.5:
                return "Tension is rising appropriately. Watch for natural peaks."
            elif trend == "falling" and expected > 0.7:
                return "Maintain high tension through this critical phase."
            else:
                return "Pacing feels appropriate for this story phase."

    def should_suggest_break(self) -> bool:
        """
        Determine if this is a good time to suggest a session break.

        Returns True if tension has just peaked and is now falling,
        or if there's been sustained high tension that needs relief.
        """
        if len(self._history) < 5:
            return False

        recent = list(self._history)[-5:]

        # Check for post-peak falloff
        peak_then_fall = (
            recent[-3] < recent[-2]  # Was rising
            and recent[-2] > recent[-1]  # Now falling
            and recent[-2] > 0.7  # Peak was significant
        )

        # Check for sustained high tension needing relief
        sustained_high = all(t > 0.7 for t in recent[-4:])

        return peak_then_fall or sustained_high

    def get_tension_curve(self) -> List[float]:
        """Get the recent tension history as a list."""
        return list(self._history)

    def to_dict(self) -> Dict[str, Any]:
        """Export state for persistence."""
        return {
            "current_tension": self._current_tension,
            "history": list(self._history),
            "last_update": self._last_update.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TensionTracker":
        """Restore from dictionary."""
        tracker = cls(initial_tension=data.get("current_tension", 0.2))
        tracker._history = deque(
            data.get("history", []),
            maxlen=tracker._history.maxlen,
        )
        return tracker
