# src/mantle/agents/relationship_agent.py
"""
Relationship Extraction Agent

Extracts relationship changes from player-NPC interactions in narrative.
Runs asynchronously after each DM response to update NPC impressions.

The agent analyzes:
- Player actions and their impact on NPCs
- NPC emotional responses
- Debts created or fulfilled
- Promises made or broken
- Trust/respect/fear/affection changes
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone

import google.generativeai as genai

from src.mantle.memory.models import (
    Impression, ImpressionValence, SalienceLevel
)
from src.mantle.memory.experiential import ExperientialMemory
from src.mantle.memory.formatting import format_npc_relationship_context

logger = logging.getLogger(__name__)


@dataclass
class RelationshipChange:
    """A detected change in an NPC's relationship with the player."""
    npc_id: str
    npc_name: str

    # Numeric changes (-1.0 to 1.0, added to current values)
    trust_delta: float = 0.0
    respect_delta: float = 0.0
    fear_delta: float = 0.0
    affection_delta: float = 0.0

    # Debt tracking
    debt_delta: float = 0.0  # Positive = they owe player more
    debt_reason: Optional[str] = None

    # Promises
    promise_made: Optional[str] = None  # NPC promised something
    promise_broken: Optional[str] = None  # Player broke a promise

    # Secret shared
    secret_shared: Optional[str] = None

    # New valence (if significant enough to change)
    new_valence: Optional[str] = None

    # Form of address change
    new_address: Optional[str] = None

    # Explanation for logging
    reason: str = ""

    # Salience of this interaction
    salience: str = "notable"


EXTRACTION_PROMPT = """You are analyzing a player-NPC interaction to extract relationship changes.

=== CONTEXT ===
Player Action: {player_action}
DM Narrative: {dm_narrative}
NPCs Present: {npcs_present}

=== YOUR TASK ===
Identify how this interaction affects the relationship between the player and each NPC.
Consider:
- Did the player help, harm, impress, frighten, or insult anyone?
- Did the player save someone, make a sacrifice, or show vulnerability?
- Did the player fulfill or break a promise?
- Did an NPC share a secret or make a promise?
- Did the player create a debt (someone owes them) or incur one (they owe someone)?

=== RATING SCALE ===
Changes are deltas from -0.3 to +0.3:
- +0.3: Major positive shift (saved their life, major sacrifice)
- +0.2: Significant positive (substantial help, defended them)
- +0.1: Minor positive (small kindness, polite, helpful)
- 0.0: No change
- -0.1: Minor negative (rude, dismissive, small slight)
- -0.2: Significant negative (threat, broken promise, harm)
- -0.3: Major negative (betrayal, violence against them/loved ones)

=== VALENCE OPTIONS ===
Only change valence for significant interactions:
- reverent: Awe, worship (rare - heroic deeds witnessed)
- grateful: Owes significant debt
- friendly: Warm relationship
- neutral: No strong feeling
- wary: Cautious, distrustful
- hostile: Antagonistic
- fearful: Afraid
- hateful: Deep enmity

=== OUTPUT FORMAT ===
Return JSON only:
{{
  "changes": [
    {{
      "npc_id": "canon_id or name if unknown",
      "npc_name": "Name as addressed in scene",
      "trust_delta": 0.0,
      "respect_delta": 0.0,
      "fear_delta": 0.0,
      "affection_delta": 0.0,
      "debt_delta": 0.0,
      "debt_reason": null or "reason",
      "promise_made": null or "what they promised",
      "promise_broken": null or "what promise was broken",
      "secret_shared": null or "the secret",
      "new_valence": null or "valence",
      "new_address": null or "how they now address player",
      "reason": "Brief explanation",
      "salience": "ordinary|notable|significant|legendary"
    }}
  ],
  "no_changes": false
}}

If no relationship changes occurred (mundane interaction), return:
{{"changes": [], "no_changes": true}}

Analyze the interaction now:"""


class RelationshipExtractionAgent:
    """
    Extracts relationship changes from narrative interactions.

    Designed to run asynchronously after DM responses without
    blocking the main game loop.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        experiential: Optional[ExperientialMemory] = None,
        model_name: str = "gemini-2.0-flash",
    ):
        """Initialize the relationship extraction agent."""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

        self.experiential = experiential or ExperientialMemory()
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name) if self.api_key else None

        logger.info(f"RelationshipExtractionAgent initialized with {model_name}")

    async def extract_relationship_changes(
        self,
        player_action: str,
        dm_narrative: str,
        npcs_present: List[Dict[str, Any]],
        session_id: Optional[str] = None,
    ) -> List[RelationshipChange]:
        """
        Extract relationship changes from a player-NPC interaction.

        Args:
            player_action: What the player did/said
            dm_narrative: The DM's response narrative
            npcs_present: List of NPCs in the scene with their IDs and names
            session_id: Current session ID for context

        Returns:
            List of RelationshipChange objects
        """
        if not self.model:
            logger.warning("No Gemini API key - skipping relationship extraction")
            return []

        if not npcs_present:
            logger.debug("No NPCs present - skipping relationship extraction")
            return []

        # Format NPCs for prompt
        npc_list = ", ".join([
            f"{npc.get('name', 'Unknown')} (ID: {npc.get('canon_id', 'unknown')})"
            for npc in npcs_present
        ])

        prompt = EXTRACTION_PROMPT.format(
            player_action=player_action,
            dm_narrative=dm_narrative,
            npcs_present=npc_list,
        )

        try:
            response = await self._call_gemini(prompt)
            changes = self._parse_response(response)

            if changes:
                logger.info(f"Extracted {len(changes)} relationship changes")
                for change in changes:
                    logger.debug(f"  {change.npc_name}: {change.reason}")

            return changes

        except Exception as e:
            logger.error(f"Relationship extraction failed: {e}")
            return []

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API with the extraction prompt."""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,  # Low temperature for consistent extraction
                    max_output_tokens=1024,
                ),
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise

    def _parse_response(self, response_text: str) -> List[RelationshipChange]:
        """Parse Gemini response into RelationshipChange objects."""
        # Extract JSON from response
        json_match = None
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_match = response_text[start:end].strip()
        elif "{" in response_text:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            json_match = response_text[start:end].strip()

        if not json_match:
            logger.warning("No JSON found in relationship extraction response")
            return []

        try:
            data = json.loads(json_match)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse relationship JSON: {e}")
            return []

        if data.get("no_changes", False):
            return []

        changes = []
        for item in data.get("changes", []):
            change = RelationshipChange(
                npc_id=item.get("npc_id", ""),
                npc_name=item.get("npc_name", ""),
                trust_delta=float(item.get("trust_delta", 0.0)),
                respect_delta=float(item.get("respect_delta", 0.0)),
                fear_delta=float(item.get("fear_delta", 0.0)),
                affection_delta=float(item.get("affection_delta", 0.0)),
                debt_delta=float(item.get("debt_delta", 0.0)),
                debt_reason=item.get("debt_reason"),
                promise_made=item.get("promise_made"),
                promise_broken=item.get("promise_broken"),
                secret_shared=item.get("secret_shared"),
                new_valence=item.get("new_valence"),
                new_address=item.get("new_address"),
                reason=item.get("reason", ""),
                salience=item.get("salience", "notable"),
            )
            changes.append(change)

        return changes

    async def apply_relationship_changes(
        self,
        changes: List[RelationshipChange],
        session_id: Optional[str] = None,
    ) -> None:
        """
        Apply extracted relationship changes to the experiential memory.

        Updates or creates Impression records for each NPC.
        """
        for change in changes:
            await self._apply_single_change(change, session_id)

    async def _apply_single_change(
        self,
        change: RelationshipChange,
        session_id: Optional[str] = None,
    ) -> None:
        """Apply a single relationship change to an NPC's impression."""
        # Get existing impression or create new one
        impression = self.experiential.get_impression(change.npc_id)

        if impression:
            # Update existing impression
            impression.trust = max(0.0, min(1.0, impression.trust + change.trust_delta))
            impression.respect = max(0.0, min(1.0, impression.respect + change.respect_delta))
            impression.fear = max(0.0, min(1.0, impression.fear + change.fear_delta))
            impression.affection = max(0.0, min(1.0, impression.affection + change.affection_delta))
            impression.debt_to_player = max(-1.0, min(1.0, impression.debt_to_player + change.debt_delta))

            if change.debt_reason:
                impression.debt_reason = change.debt_reason

            if change.promise_made:
                impression.promises_made.append(change.promise_made)

            if change.promise_broken:
                impression.promises_broken.append(change.promise_broken)

            if change.secret_shared:
                impression.shared_secrets.append(change.secret_shared)
                impression.will_share_secrets = True

            if change.new_valence:
                try:
                    impression.valence = ImpressionValence(change.new_valence)
                except ValueError:
                    pass  # Invalid valence, skip

            if change.new_address:
                if change.new_address not in impression.forms_of_address:
                    impression.forms_of_address.insert(0, change.new_address)

            impression.last_interaction = datetime.now(timezone.utc)
            impression.interaction_count += 1

            # Update behavioral flags based on trust/fear
            impression.will_help = impression.trust > 0.4 and impression.affection > 0.3
            impression.will_trade = impression.trust > 0.3
            impression.will_betray = impression.trust < 0.2 and impression.fear < 0.5

        else:
            # Create new impression
            valence = ImpressionValence.NEUTRAL
            if change.new_valence:
                try:
                    valence = ImpressionValence(change.new_valence)
                except ValueError:
                    pass

            impression = Impression(
                agent_id=change.npc_id,
                valence=valence,
                summary=change.reason,
                trust=0.5 + change.trust_delta,
                respect=0.5 + change.respect_delta,
                fear=change.fear_delta if change.fear_delta > 0 else 0.0,
                affection=0.5 + change.affection_delta,
                debt_to_player=change.debt_delta,
                debt_reason=change.debt_reason,
                forms_of_address=[change.new_address] if change.new_address else ["stranger", "traveler"],
            )

            if change.promise_made:
                impression.promises_made.append(change.promise_made)
            if change.secret_shared:
                impression.shared_secrets.append(change.secret_shared)
                impression.will_share_secrets = True

        # Save the impression
        self.experiential.record_impression(impression)

        logger.info(
            f"Updated impression for {change.npc_name} ({change.npc_id}): "
            f"trust={impression.trust:.2f}, respect={impression.respect:.2f}, "
            f"debt={impression.debt_to_player:.2f}"
        )
