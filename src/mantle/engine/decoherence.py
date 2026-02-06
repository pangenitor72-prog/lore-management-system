# src/mantle/engine/decoherence.py
"""
Decoherence Engine - Lazy World Simulation

The world changes plausibly when the player is absent.
Changes are resolved when observed (lazy evaluation).

Philosophy: We don't continuously simulate the world. Instead:
1. Track when entities were last "observed" (appeared in scene)
2. When re-encountered, calculate elapsed time
3. Ask AI to generate what might have changed
4. Feed those hints to the DM for organic integration

This creates the illusion of a living world without expensive simulation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import google.generativeai as genai

logger = logging.getLogger(__name__)


@dataclass
class EntityObservation:
    """Records when an entity was last observed by the player."""
    entity_name: str
    entity_type: str  # Character, Location, Faction, etc.
    last_seen_turn: int
    last_seen_at: datetime
    interaction_count: int = 1
    context_notes: List[str] = field(default_factory=list)  # Brief notes about last interaction


@dataclass
class DecoherenceHint:
    """A hint about what might have changed for a stale entity."""
    entity_name: str
    turns_elapsed: int
    change_category: str  # "minor_drift", "notable_change", "major_shift"
    suggestion: str  # What the DM should consider
    confidence: float = 0.7  # How strongly to weight this hint


class DecoherenceEngine:
    """
    Tracks entity observations and generates decoherence hints.

    When the player hasn't seen an NPC or location for a while,
    this engine suggests plausible changes that occurred "off-screen".
    """

    # Thresholds for decoherence (in turns)
    MINOR_DRIFT_THRESHOLD = 10      # Small mood/detail changes
    NOTABLE_CHANGE_THRESHOLD = 25   # Significant developments
    MAJOR_SHIFT_THRESHOLD = 50      # World-altering changes possible

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.observations: Dict[str, EntityObservation] = {}
        self.model = None

        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                self.model = genai.GenerativeModel("gemini-2.0-flash")
                logger.info("DecoherenceEngine: AI model initialized")
            except Exception as e:
                logger.warning(f"DecoherenceEngine: Could not initialize AI model: {e}")

    def record_observation(
        self,
        entity_name: str,
        entity_type: str,
        current_turn: int,
        context_note: Optional[str] = None,
    ) -> None:
        """
        Record that an entity was observed in the current scene.

        Call this when:
        - An NPC appears in DM narration
        - Player enters a location
        - A faction is mentioned as present/active
        """
        key = self._normalize_key(entity_name)

        if key in self.observations:
            obs = self.observations[key]
            obs.last_seen_turn = current_turn
            obs.last_seen_at = datetime.now(timezone.utc)
            obs.interaction_count += 1
            if context_note:
                # Keep last 3 context notes
                obs.context_notes.append(context_note)
                obs.context_notes = obs.context_notes[-3:]
        else:
            self.observations[key] = EntityObservation(
                entity_name=entity_name,
                entity_type=entity_type,
                last_seen_turn=current_turn,
                last_seen_at=datetime.now(timezone.utc),
                context_notes=[context_note] if context_note else [],
            )

        logger.debug(f"DecoherenceEngine: Recorded observation of {entity_name} at turn {current_turn}")

    def get_staleness(self, entity_name: str, current_turn: int) -> Optional[int]:
        """
        Get how many turns since this entity was last observed.

        Returns None if entity has never been observed.
        """
        key = self._normalize_key(entity_name)
        if key not in self.observations:
            return None

        return current_turn - self.observations[key].last_seen_turn

    def get_stale_entities(self, current_turn: int, threshold: int = None) -> List[EntityObservation]:
        """Get all entities that haven't been seen for more than threshold turns."""
        threshold = threshold or self.MINOR_DRIFT_THRESHOLD

        stale = []
        for obs in self.observations.values():
            if current_turn - obs.last_seen_turn >= threshold:
                stale.append(obs)

        return sorted(stale, key=lambda o: current_turn - o.last_seen_turn, reverse=True)

    def generate_decoherence_hint(
        self,
        entity_name: str,
        entity_type: str,
        entity_context: str,  # What we know about this entity
        current_turn: int,
        world_context: Optional[str] = None,
    ) -> Optional[DecoherenceHint]:
        """
        Generate a hint about what might have changed for a stale entity.

        This is called when an entity is about to re-enter the scene after
        being absent for a while.
        """
        staleness = self.get_staleness(entity_name, current_turn)

        if staleness is None or staleness < self.MINOR_DRIFT_THRESHOLD:
            return None  # Entity is fresh, no decoherence needed

        # Determine change category based on staleness
        if staleness >= self.MAJOR_SHIFT_THRESHOLD:
            category = "major_shift"
            change_level = "significant, possibly dramatic"
        elif staleness >= self.NOTABLE_CHANGE_THRESHOLD:
            category = "notable_change"
            change_level = "noticeable, meaningful"
        else:
            category = "minor_drift"
            change_level = "subtle, minor"

        # Get previous context notes
        key = self._normalize_key(entity_name)
        obs = self.observations.get(key)
        last_context = " | ".join(obs.context_notes) if obs and obs.context_notes else "No specific notes"

        # If we have AI, generate a creative suggestion
        if self.model:
            suggestion = self._generate_ai_suggestion(
                entity_name=entity_name,
                entity_type=entity_type,
                entity_context=entity_context,
                staleness=staleness,
                change_level=change_level,
                last_context=last_context,
                world_context=world_context,
            )
        else:
            # Fallback to template-based suggestion
            suggestion = self._generate_template_suggestion(
                entity_name=entity_name,
                entity_type=entity_type,
                staleness=staleness,
                category=category,
            )

        return DecoherenceHint(
            entity_name=entity_name,
            turns_elapsed=staleness,
            change_category=category,
            suggestion=suggestion,
            confidence=0.8 if self.model else 0.5,
        )

    def get_dm_context_injection(
        self,
        current_turn: int,
        entities_in_scene: List[str],
        world_context: Optional[str] = None,
    ) -> str:
        """
        Generate context injection for the DM about decoherence.

        Call this before DM generates a response when stale entities
        are present in the scene.
        """
        hints = []

        for entity_name in entities_in_scene:
            staleness = self.get_staleness(entity_name, current_turn)
            if staleness and staleness >= self.MINOR_DRIFT_THRESHOLD:
                key = self._normalize_key(entity_name)
                obs = self.observations.get(key)
                if obs:
                    hint = self.generate_decoherence_hint(
                        entity_name=entity_name,
                        entity_type=obs.entity_type,
                        entity_context="",  # We don't have full context here
                        current_turn=current_turn,
                        world_context=world_context,
                    )
                    if hint:
                        hints.append(hint)

        if not hints:
            return ""

        lines = ["", "=== DECOHERENCE HINTS (world evolved while player was away) ==="]
        for hint in hints:
            turns_word = "turn" if hint.turns_elapsed == 1 else "turns"
            lines.append(
                f"- {hint.entity_name} ({hint.turns_elapsed} {turns_word} since last seen, {hint.change_category}):"
            )
            lines.append(f"  Consider: {hint.suggestion}")

        lines.append("")
        lines.append(
            "DECOHERENCE PRINCIPLE: The world doesn't freeze when the player leaves. "
            "Subtly reflect that time has passed - but don't info-dump. "
            "Let changes emerge naturally through dialogue and observation."
        )

        return "\n".join(lines)

    def _generate_ai_suggestion(
        self,
        entity_name: str,
        entity_type: str,
        entity_context: str,
        staleness: int,
        change_level: str,
        last_context: str,
        world_context: Optional[str],
    ) -> str:
        """Use AI to generate a creative decoherence suggestion."""
        prompt = f"""You are helping a fantasy RPG DM. An entity the player hasn't seen for a while is about to reappear.

Entity: {entity_name} ({entity_type})
Context: {entity_context or "General NPC/location"}
Turns since last seen: {staleness}
Expected change level: {change_level}
Last known context: {last_context}
World context: {world_context or "Standard fantasy setting"}

Generate ONE brief, specific suggestion for what might have changed while the player was away.
Keep it to 1-2 sentences. Focus on something that:
- Feels natural and organic
- Could be revealed through dialogue or observation
- Adds depth without derailing the story

Just output the suggestion, no preamble."""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"temperature": 0.8, "max_output_tokens": 100},
            )
            return response.text.strip()
        except Exception as e:
            logger.warning(f"DecoherenceEngine: AI generation failed: {e}")
            return self._generate_template_suggestion(
                entity_name, entity_type, staleness, "notable_change"
            )

    def _generate_template_suggestion(
        self,
        entity_name: str,
        entity_type: str,
        staleness: int,
        category: str,
    ) -> str:
        """Generate a template-based suggestion when AI isn't available."""
        templates = {
            "Character": {
                "minor_drift": [
                    "Their mood or demeanor might have shifted slightly.",
                    "They may have heard new rumors or gossip.",
                    "Small details in their appearance could have changed.",
                ],
                "notable_change": [
                    "Their circumstances or situation may have evolved.",
                    "New relationships or conflicts might have developed.",
                    "Their goals or priorities could have shifted.",
                ],
                "major_shift": [
                    "Their life situation may have dramatically changed.",
                    "Major events might have reshaped their worldview.",
                    "They could have new allegiances or enemies.",
                ],
            },
            "Location": {
                "minor_drift": [
                    "Minor repairs or changes to the environment.",
                    "Different NPCs might be present now.",
                    "The atmosphere or activity level may have shifted.",
                ],
                "notable_change": [
                    "New businesses or residents might have arrived.",
                    "Local events could have changed the area's character.",
                    "Power dynamics in the area may have shifted.",
                ],
                "major_shift": [
                    "The location might have been transformed by events.",
                    "Major construction, destruction, or change is possible.",
                    "The location's role in the world could be different.",
                ],
            },
            "Faction": {
                "minor_drift": [
                    "Internal politics may have shifted slightly.",
                    "Their public stance on issues might have evolved.",
                ],
                "notable_change": [
                    "Leadership or priorities may have changed.",
                    "New alliances or rivalries could have formed.",
                ],
                "major_shift": [
                    "The faction's power or influence may have dramatically changed.",
                    "Major schisms or transformations are possible.",
                ],
            },
        }

        # Get appropriate templates
        entity_templates = templates.get(entity_type, templates["Character"])
        category_templates = entity_templates.get(category, entity_templates["notable_change"])

        # Pick based on staleness as pseudo-random seed
        idx = staleness % len(category_templates)
        return category_templates[idx]

    def _normalize_key(self, entity_name: str) -> str:
        """Normalize entity name for consistent lookup."""
        return entity_name.lower().strip()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "observations": {
                key: {
                    "entity_name": obs.entity_name,
                    "entity_type": obs.entity_type,
                    "last_seen_turn": obs.last_seen_turn,
                    "last_seen_at": obs.last_seen_at.isoformat(),
                    "interaction_count": obs.interaction_count,
                    "context_notes": obs.context_notes,
                }
                for key, obs in self.observations.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], gemini_api_key: Optional[str] = None) -> "DecoherenceEngine":
        """Deserialize from persistence."""
        engine = cls(gemini_api_key=gemini_api_key)

        for key, obs_data in data.get("observations", {}).items():
            engine.observations[key] = EntityObservation(
                entity_name=obs_data["entity_name"],
                entity_type=obs_data["entity_type"],
                last_seen_turn=obs_data["last_seen_turn"],
                last_seen_at=datetime.fromisoformat(obs_data["last_seen_at"]),
                interaction_count=obs_data.get("interaction_count", 1),
                context_notes=obs_data.get("context_notes", []),
            )

        return engine
