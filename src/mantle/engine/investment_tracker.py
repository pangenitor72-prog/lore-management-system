# src/mantle/engine/investment_tracker.py
"""
Investment Signal Tracker - What Does the Player Care About?

Philosophy from THE_NARROW_PATH.md:
"Track what player invests energy in"
"The system should detect what the player cares about"

This module aggregates multiple signals to determine player investment:
1. Discovery heat - entities they've explicitly connected with
2. Interaction frequency - entities mentioned in their actions
3. Memory salience - emotionally weighted events involving entities
4. Return visits - entities they keep coming back to

The investment score helps the DM:
- Make invested entities feel more consequential
- Create more satisfying moments of payoff
- Avoid wasting narrative energy on things player doesn't care about
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from collections import Counter
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class EntityInvestment:
    """Tracks player investment in a specific entity."""
    entity_name: str
    entity_type: str  # Character, Location, Faction, etc.

    # Signal components
    discovery_count: int = 0          # How many discoveries mention this entity
    discovery_heat_sum: float = 0.0   # Sum of discovery heat values (hot=1.0, warm=0.5, cold=0.1)
    action_mention_count: int = 0     # How many player actions mention this entity
    turn_first_seen: int = 0          # When did player first encounter
    turn_last_seen: int = 0           # When did player last interact

    # Computed
    investment_score: float = 0.0     # 0.0-1.0 normalized investment

    def recalculate_score(self, current_turn: int) -> float:
        """
        Calculate investment score from signals.

        Factors:
        - Discovery engagement (high weight - explicit interest)
        - Action mentions (medium weight - active engagement)
        - Recency (decay for stale entities)
        """
        # Base score from discoveries (most explicit signal)
        discovery_score = min(1.0, self.discovery_heat_sum / 3.0)  # Cap at 3 hot discoveries

        # Score from action mentions (player actively engaging)
        mention_score = min(1.0, self.action_mention_count / 10.0)  # Cap at 10 mentions

        # Recency factor (decay over time if not mentioned)
        turns_since_seen = current_turn - self.turn_last_seen
        if turns_since_seen <= 5:
            recency = 1.0
        elif turns_since_seen <= 15:
            recency = 0.7
        elif turns_since_seen <= 30:
            recency = 0.4
        else:
            recency = 0.2

        # Weighted combination
        # Discoveries are most important (40%), mentions matter (35%), recency adjusts (25%)
        raw_score = (
            discovery_score * 0.40 +
            mention_score * 0.35 +
            recency * 0.25
        )

        self.investment_score = min(1.0, max(0.0, raw_score))
        return self.investment_score


class InvestmentTracker:
    """
    Tracks player investment signals across entities.

    Feed this tracker with:
    - Player actions (to detect entity mentions)
    - Discoveries (explicit interest markers)
    - Game state changes

    It produces:
    - Ranked list of invested entities
    - Investment context for DM prompts
    """

    def __init__(self):
        self.investments: Dict[str, EntityInvestment] = {}
        self.action_history: List[Tuple[int, str]] = []  # (turn, action_text)

    def record_player_action(self, action: str, turn: int) -> None:
        """
        Record a player action and extract entity mentions.

        Called every time the player takes an action.
        """
        self.action_history.append((turn, action))

        # Keep history manageable
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]

        # Extract entity mentions from action
        entities = self._extract_entities_from_action(action)

        for entity_name in entities:
            key = self._normalize_key(entity_name)

            if key in self.investments:
                inv = self.investments[key]
                inv.action_mention_count += 1
                inv.turn_last_seen = turn
            else:
                # New entity - create minimal tracking
                self.investments[key] = EntityInvestment(
                    entity_name=entity_name,
                    entity_type="Unknown",  # Will be updated if discovered
                    action_mention_count=1,
                    turn_first_seen=turn,
                    turn_last_seen=turn,
                )

    def record_discovery(
        self,
        entity_name: str,
        entity_type: str,
        heat: str,  # "hot", "warm", "cold"
        turn: int,
    ) -> None:
        """
        Record a discovery about an entity.

        Discoveries are the strongest signal of player investment.
        """
        heat_values = {"hot": 1.0, "warm": 0.5, "cold": 0.1}
        heat_value = heat_values.get(heat, 0.1)

        key = self._normalize_key(entity_name)

        if key in self.investments:
            inv = self.investments[key]
            inv.discovery_count += 1
            inv.discovery_heat_sum += heat_value
            inv.turn_last_seen = turn
            if entity_type and entity_type != "Unknown":
                inv.entity_type = entity_type
        else:
            self.investments[key] = EntityInvestment(
                entity_name=entity_name,
                entity_type=entity_type or "Unknown",
                discovery_count=1,
                discovery_heat_sum=heat_value,
                turn_first_seen=turn,
                turn_last_seen=turn,
            )

        logger.debug(f"[INVESTMENT] Discovery recorded: {entity_name} ({heat})")

    def get_top_investments(self, current_turn: int, limit: int = 5) -> List[EntityInvestment]:
        """Get the entities the player is most invested in."""
        # Recalculate all scores
        for inv in self.investments.values():
            inv.recalculate_score(current_turn)

        # Sort by investment score
        sorted_investments = sorted(
            self.investments.values(),
            key=lambda i: i.investment_score,
            reverse=True,
        )

        return sorted_investments[:limit]

    def get_dm_context_injection(self, current_turn: int) -> str:
        """
        Generate context injection for the DM about player investment.

        This helps the DM:
        - Emphasize entities the player cares about
        - Create payoff moments for invested storylines
        - Avoid wasting time on entities player doesn't care about
        """
        top = self.get_top_investments(current_turn, limit=5)

        if not top:
            return ""

        # Only include entities with meaningful investment
        invested = [i for i in top if i.investment_score >= 0.2]

        if not invested:
            return ""

        lines = ["", "=== PLAYER INVESTMENT SIGNALS ==="]
        lines.append("(Entities the player has shown interest in - make these feel consequential)")

        for inv in invested:
            # Describe investment level
            if inv.investment_score >= 0.7:
                level = "HIGH INVESTMENT"
            elif inv.investment_score >= 0.4:
                level = "MODERATE INTEREST"
            else:
                level = "SOME INTEREST"

            notes = []
            if inv.discovery_count > 0:
                notes.append(f"{inv.discovery_count} discovery/discoveries")
            if inv.action_mention_count > 0:
                notes.append(f"mentioned {inv.action_mention_count}x in actions")

            note_str = f" ({', '.join(notes)})" if notes else ""
            lines.append(f"- {inv.entity_name} [{level}]{note_str}")

        lines.append("")
        lines.append(
            "INVESTMENT PRINCIPLE: When invested entities appear, "
            "make interactions feel meaningful. Callbacks, payoffs, "
            "and consequences should feel satisfying - this is what the player cares about."
        )

        return "\n".join(lines)

    def _extract_entities_from_action(self, action: str) -> List[str]:
        """
        Extract potential entity names from player action text.

        Uses heuristics to find:
        - Named NPCs (proper nouns)
        - Mentioned locations
        - Referenced factions
        """
        if not action:
            return []

        entities = set()

        # Pattern 1: Titles + Names
        title_pattern = re.compile(
            r'\b(Lord|Lady|King|Queen|Captain|Master|Elder|Chief)\s+([A-Z][a-z]+)',
            re.IGNORECASE
        )
        for match in title_pattern.finditer(action):
            entities.add(match.group(0).strip())

        # Pattern 2: Direct address ("I talk to Marcus", "I ask the innkeeper")
        talk_pattern = re.compile(
            r'\b(?:talk|speak|ask|tell|question|approach|greet)\s+(?:to\s+)?(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            re.IGNORECASE
        )
        for match in talk_pattern.finditer(action):
            name = match.group(1).strip()
            if name.lower() not in ("the", "a", "an", "him", "her", "them", "it"):
                entities.add(name)

        # Pattern 3: Going to places ("I go to the Rusty Tankard", "I head to Blackwood")
        place_pattern = re.compile(
            r'\b(?:go|head|travel|walk|run|return)\s+(?:to|toward|towards)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            re.IGNORECASE
        )
        for match in place_pattern.finditer(action):
            entities.add(match.group(1).strip())

        # Pattern 4: Looking for or asking about
        about_pattern = re.compile(
            r'\b(?:looking for|searching for|ask about|asking about|investigate|find)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            re.IGNORECASE
        )
        for match in about_pattern.finditer(action):
            entities.add(match.group(1).strip())

        return list(entities)[:10]  # Limit to prevent noise

    def _normalize_key(self, entity_name: str) -> str:
        """Normalize entity name for consistent lookup."""
        return entity_name.lower().strip()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "investments": {
                key: {
                    "entity_name": inv.entity_name,
                    "entity_type": inv.entity_type,
                    "discovery_count": inv.discovery_count,
                    "discovery_heat_sum": inv.discovery_heat_sum,
                    "action_mention_count": inv.action_mention_count,
                    "turn_first_seen": inv.turn_first_seen,
                    "turn_last_seen": inv.turn_last_seen,
                    "investment_score": inv.investment_score,
                }
                for key, inv in self.investments.items()
            },
            "action_history": self.action_history[-50:],  # Keep last 50
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InvestmentTracker":
        """Deserialize from persistence."""
        tracker = cls()

        for key, inv_data in data.get("investments", {}).items():
            tracker.investments[key] = EntityInvestment(
                entity_name=inv_data["entity_name"],
                entity_type=inv_data.get("entity_type", "Unknown"),
                discovery_count=inv_data.get("discovery_count", 0),
                discovery_heat_sum=inv_data.get("discovery_heat_sum", 0.0),
                action_mention_count=inv_data.get("action_mention_count", 0),
                turn_first_seen=inv_data.get("turn_first_seen", 0),
                turn_last_seen=inv_data.get("turn_last_seen", 0),
                investment_score=inv_data.get("investment_score", 0.0),
            )

        tracker.action_history = data.get("action_history", [])

        return tracker
