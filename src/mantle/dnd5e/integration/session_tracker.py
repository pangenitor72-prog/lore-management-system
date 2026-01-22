"""Session state tracking for D&D 5e mechanics."""

import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from ..models.character_sheet import CharacterSheet
from ..engine.combat_resolver import CombatResolver

logger = logging.getLogger(__name__)


class CombatantState(BaseModel):
    """Tracks a combatant's state in combat."""
    entity_id: str
    name: str
    initiative: int
    current_hp: int
    max_hp: int
    armor_class: int
    is_player: bool = False
    conditions: List[str] = Field(default_factory=list)
    is_active: bool = True  # False if unconscious/dead


class CombatEncounter(BaseModel):
    """Tracks state of a combat encounter."""
    encounter_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    is_active: bool = True
    round_number: int = 1
    current_turn_index: int = 0
    initiative_order: List[str] = Field(default_factory=list)  # Entity IDs in initiative order
    combatants: Dict[str, CombatantState] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionTracker:
    """
    Tracks mechanical state across a game session.

    Manages:
    - Player character state
    - Combat encounters
    - Session statistics
    """

    def __init__(self, session_id: str):
        """
        Initialize the session tracker.

        Args:
            session_id: The game session ID
        """
        self.session_id = session_id
        self.characters: Dict[str, CharacterSheet] = {}
        self.current_combat: Optional[CombatEncounter] = None
        self.combat_history: List[CombatEncounter] = []

        # Session statistics
        self.stats = {
            "combats_started": 0,
            "combats_completed": 0,
            "attacks_made": 0,
            "attacks_hit": 0,
            "damage_dealt": 0,
            "damage_taken": 0,
            "checks_made": 0,
            "checks_succeeded": 0,
            "spells_cast": 0,
            "healing_done": 0,
        }

    def register_character(self, character: CharacterSheet) -> None:
        """Register a player character."""
        self.characters[character.character_id] = character
        logger.info(f"Session {self.session_id}: Registered {character.name}")

    def update_character(self, character: CharacterSheet) -> None:
        """Update a character's state."""
        self.characters[character.character_id] = character

    def get_character(self, character_id: str) -> Optional[CharacterSheet]:
        """Get a character by ID."""
        return self.characters.get(character_id)

    # Combat Management

    def start_combat(
        self,
        player_ids: List[str],
        enemy_data: List[Dict[str, Any]],
    ) -> CombatEncounter:
        """
        Start a new combat encounter.

        Args:
            player_ids: IDs of player characters involved
            enemy_data: List of enemy stats (name, hp, ac, initiative_mod)

        Returns:
            The new CombatEncounter
        """
        if self.current_combat and self.current_combat.is_active:
            logger.warning("Starting new combat while one is active")
            self._end_combat_internal()

        encounter = CombatEncounter()
        combatants = {}
        initiatives = []

        # Add players
        for pid in player_ids:
            char = self.characters.get(pid)
            if char:
                init_roll, _ = CombatResolver.roll_initiative(char)
                combatants[pid] = CombatantState(
                    entity_id=pid,
                    name=char.name,
                    initiative=init_roll,
                    current_hp=char.current_hit_points,
                    max_hp=char.max_hit_points,
                    armor_class=char.armor_class,
                    is_player=True,
                )
                initiatives.append((pid, init_roll))

        # Add enemies
        for i, enemy in enumerate(enemy_data):
            enemy_id = f"enemy_{i}_{uuid.uuid4().hex[:8]}"
            init_mod = enemy.get("initiative_mod", 0)
            init_roll = CombatResolver.roll_initiative(
                # Create a mock character for initiative
                type('obj', (object,), {'initiative_modifier': init_mod})()
            )[0]

            combatants[enemy_id] = CombatantState(
                entity_id=enemy_id,
                name=enemy.get("name", f"Enemy {i+1}"),
                initiative=init_roll,
                current_hp=enemy.get("hp", 10),
                max_hp=enemy.get("hp", 10),
                armor_class=enemy.get("ac", 12),
                is_player=False,
            )
            initiatives.append((enemy_id, init_roll))

        # Sort by initiative (highest first)
        initiatives.sort(key=lambda x: x[1], reverse=True)

        encounter.initiative_order = [eid for eid, _ in initiatives]
        encounter.combatants = combatants
        self.current_combat = encounter

        self.stats["combats_started"] += 1
        logger.info(f"Combat started: {len(player_ids)} players vs {len(enemy_data)} enemies")

        return encounter

    def get_current_combatant(self) -> Optional[CombatantState]:
        """Get the combatant whose turn it is."""
        if not self.current_combat or not self.current_combat.is_active:
            return None

        current_id = self.current_combat.initiative_order[
            self.current_combat.current_turn_index
        ]
        return self.current_combat.combatants.get(current_id)

    def next_turn(self) -> Optional[CombatantState]:
        """Advance to the next turn."""
        if not self.current_combat or not self.current_combat.is_active:
            return None

        # Skip unconscious/dead combatants
        attempts = 0
        max_attempts = len(self.current_combat.initiative_order)

        while attempts < max_attempts:
            self.current_combat.current_turn_index += 1

            # Check for new round
            if self.current_combat.current_turn_index >= len(self.current_combat.initiative_order):
                self.current_combat.current_turn_index = 0
                self.current_combat.round_number += 1
                logger.info(f"Combat round {self.current_combat.round_number}")

            current = self.get_current_combatant()
            if current and current.is_active:
                return current

            attempts += 1

        # All combatants inactive
        self.end_combat()
        return None

    def apply_combat_damage(
        self,
        target_id: str,
        damage: int,
    ) -> Optional[CombatantState]:
        """
        Apply damage to a combatant.

        Returns the updated combatant state.
        """
        if not self.current_combat:
            return None

        combatant = self.current_combat.combatants.get(target_id)
        if not combatant:
            return None

        combatant.current_hp = max(0, combatant.current_hp - damage)
        self.stats["damage_dealt"] += damage

        if combatant.current_hp <= 0:
            combatant.is_active = False
            logger.info(f"{combatant.name} is down!")

            # Check for combat end
            self._check_combat_end()

        # Update player character if applicable
        if combatant.is_player:
            char = self.characters.get(target_id)
            if char:
                self.characters[target_id] = char.take_damage(damage)
                self.stats["damage_taken"] += damage

        return combatant

    def apply_combat_healing(
        self,
        target_id: str,
        healing: int,
    ) -> Optional[CombatantState]:
        """Apply healing to a combatant."""
        if not self.current_combat:
            return None

        combatant = self.current_combat.combatants.get(target_id)
        if not combatant:
            return None

        old_hp = combatant.current_hp
        combatant.current_hp = min(combatant.max_hp, combatant.current_hp + healing)
        actual_healing = combatant.current_hp - old_hp

        self.stats["healing_done"] += actual_healing

        # Revive if was at 0
        if old_hp == 0 and combatant.current_hp > 0:
            combatant.is_active = True

        # Update player character
        if combatant.is_player:
            char = self.characters.get(target_id)
            if char:
                self.characters[target_id] = char.heal(healing)

        return combatant

    def _check_combat_end(self) -> bool:
        """Check if combat should end (one side defeated)."""
        if not self.current_combat:
            return True

        players_alive = any(
            c.is_active for c in self.current_combat.combatants.values()
            if c.is_player
        )
        enemies_alive = any(
            c.is_active for c in self.current_combat.combatants.values()
            if not c.is_player
        )

        if not players_alive or not enemies_alive:
            self.end_combat()
            return True

        return False

    def end_combat(self) -> Dict[str, Any]:
        """End the current combat and return summary."""
        if not self.current_combat:
            return {"error": "No active combat"}

        self.current_combat.is_active = False
        summary = {
            "rounds": self.current_combat.round_number,
            "players_standing": sum(
                1 for c in self.current_combat.combatants.values()
                if c.is_player and c.is_active
            ),
            "enemies_defeated": sum(
                1 for c in self.current_combat.combatants.values()
                if not c.is_player and not c.is_active
            ),
        }

        self.combat_history.append(self.current_combat)
        self.current_combat = None
        self.stats["combats_completed"] += 1

        logger.info(f"Combat ended: {summary}")
        return summary

    def _end_combat_internal(self) -> None:
        """Internal method to end combat without returning summary."""
        if self.current_combat:
            self.current_combat.is_active = False
            self.combat_history.append(self.current_combat)
            self.current_combat = None

    # Statistics

    def record_attack(self, hit: bool, damage: int = 0) -> None:
        """Record an attack for statistics."""
        self.stats["attacks_made"] += 1
        if hit:
            self.stats["attacks_hit"] += 1
            self.stats["damage_dealt"] += damage

    def record_check(self, success: bool) -> None:
        """Record a skill/ability check for statistics."""
        self.stats["checks_made"] += 1
        if success:
            self.stats["checks_succeeded"] += 1

    def record_spell(self) -> None:
        """Record a spell cast."""
        self.stats["spells_cast"] += 1

    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the session's mechanical events."""
        return {
            "session_id": self.session_id,
            "characters": [
                {
                    "name": c.name,
                    "class": c.character_class.value,
                    "level": c.level,
                    "hp": f"{c.current_hit_points}/{c.max_hit_points}",
                }
                for c in self.characters.values()
            ],
            "combats": self.stats["combats_completed"],
            "attacks": {
                "total": self.stats["attacks_made"],
                "hit_rate": (
                    self.stats["attacks_hit"] / self.stats["attacks_made"]
                    if self.stats["attacks_made"] > 0 else 0
                ),
            },
            "checks": {
                "total": self.stats["checks_made"],
                "success_rate": (
                    self.stats["checks_succeeded"] / self.stats["checks_made"]
                    if self.stats["checks_made"] > 0 else 0
                ),
            },
            "damage_dealt": self.stats["damage_dealt"],
            "damage_taken": self.stats["damage_taken"],
            "healing_done": self.stats["healing_done"],
            "spells_cast": self.stats["spells_cast"],
        }
