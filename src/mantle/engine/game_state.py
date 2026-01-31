# src/mantle/engine/game_state.py
"""
GameState - Single source of truth for all game session state.

This class owns:
- Player character state (HP, conditions, etc.)
- Inventory (items, gold)
- Session state (turn count, history, phase)
- Combat state (combatants, initiative)
- World state (location, active NPCs)

All state mutations flow through this class, which:
1. Applies the change
2. Generates events for the frontend
3. Persists to disk
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..dnd5e.models.character_sheet import CharacterSheet
from .game_events import GameEvent, GameEventType, Inventory, Item, get_starting_inventory

logger = logging.getLogger(__name__)


@dataclass
class CombatantState:
    """Tracks an NPC or enemy during combat."""
    id: str
    name: str
    max_hp: int
    current_hp: int
    armor_class: int = 10
    initiative: int = 0
    conditions: List[str] = field(default_factory=list)
    is_player: bool = False

    def take_damage(self, amount: int) -> int:
        """Apply damage, return actual damage dealt."""
        actual = min(amount, self.current_hp)
        self.current_hp -= actual
        return actual

    def heal(self, amount: int) -> int:
        """Apply healing, return actual healing done."""
        actual = min(amount, self.max_hp - self.current_hp)
        self.current_hp += actual
        return actual

    def is_dead(self) -> bool:
        return self.current_hp <= 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "max_hp": self.max_hp,
            "current_hp": self.current_hp,
            "armor_class": self.armor_class,
            "initiative": self.initiative,
            "conditions": self.conditions,
            "is_player": self.is_player,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CombatantState":
        return cls(**data)


@dataclass
class CombatState:
    """Active combat encounter state."""
    active: bool = False
    round: int = 0
    turn_index: int = 0
    combatants: Dict[str, CombatantState] = field(default_factory=dict)
    initiative_order: List[str] = field(default_factory=list)

    def add_combatant(self, combatant: CombatantState):
        """Add a combatant to the encounter."""
        self.combatants[combatant.id] = combatant
        if combatant.id not in self.initiative_order:
            self.initiative_order.append(combatant.id)
            # Re-sort by initiative (highest first)
            self.initiative_order.sort(
                key=lambda cid: self.combatants[cid].initiative,
                reverse=True
            )

    def get_current_combatant(self) -> Optional[CombatantState]:
        """Get the combatant whose turn it is."""
        if not self.initiative_order:
            return None
        return self.combatants.get(self.initiative_order[self.turn_index])

    def next_turn(self):
        """Advance to the next combatant's turn."""
        if not self.initiative_order:
            return

        self.turn_index = (self.turn_index + 1) % len(self.initiative_order)
        if self.turn_index == 0:
            self.round += 1

    def remove_dead(self) -> List[str]:
        """Remove dead combatants from initiative. Returns removed IDs."""
        dead = [cid for cid, c in self.combatants.items() if c.is_dead() and not c.is_player]
        for cid in dead:
            if cid in self.initiative_order:
                idx = self.initiative_order.index(cid)
                self.initiative_order.remove(cid)
                # Adjust turn index if needed
                if idx < self.turn_index:
                    self.turn_index -= 1
        return dead

    def is_combat_over(self) -> bool:
        """Check if combat should end (only player left or no enemies)."""
        living_enemies = [
            c for c in self.combatants.values()
            if not c.is_player and not c.is_dead()
        ]
        return len(living_enemies) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "round": self.round,
            "turn_index": self.turn_index,
            "combatants": {k: v.to_dict() for k, v in self.combatants.items()},
            "initiative_order": self.initiative_order,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CombatState":
        state = cls(
            active=data.get("active", False),
            round=data.get("round", 0),
            turn_index=data.get("turn_index", 0),
            initiative_order=data.get("initiative_order", []),
        )
        for cid, cdata in data.get("combatants", {}).items():
            state.combatants[cid] = CombatantState.from_dict(cdata)
        return state


@dataclass
class GameState:
    """
    Single source of truth for all game session state.

    This is THE authoritative state object. When the DM says "you take 5 damage",
    this class is where that damage actually gets applied.
    """

    session_id: str
    world_id: str

    # Player state
    character: Optional[CharacterSheet] = None
    inventory: Inventory = field(default_factory=Inventory)

    # Session state
    turn_count: int = 0
    phase: str = "active"  # session_0, active, combat, ended
    history: List[Dict[str, str]] = field(default_factory=list)

    # World state
    location: str = "Unknown"
    active_npcs: Dict[str, CombatantState] = field(default_factory=dict)

    # Combat state
    combat: CombatState = field(default_factory=CombatState)

    # Events this turn (for frontend notifications)
    pending_events: List[GameEvent] = field(default_factory=list)

    # =========================================================================
    # STATE MUTATION METHODS - These are the ONLY way to change state
    # =========================================================================

    def apply_damage_to_player(self, amount: int, source: str = "unknown") -> GameEvent:
        """
        Apply damage to player character.

        This is the canonical way to hurt the player. Call this after dice
        determine damage, and the HP will actually change.
        """
        if not self.character:
            raise ValueError("No character in session")

        old_hp = self.character.current_hit_points
        self.character = self.character.take_damage(amount)
        actual_damage = old_hp - self.character.current_hit_points

        event = GameEvent(
            type=GameEventType.DAMAGE_TAKEN,
            turn=self.turn_count,
            data={
                "amount": actual_damage,
                "source": source,
                "new_hp": self.character.current_hit_points,
                "max_hp": self.character.max_hit_points,
            }
        )
        self.pending_events.append(event)

        logger.info(
            f"[GameState] Player took {actual_damage} damage from {source}. "
            f"HP: {self.character.current_hit_points}/{self.character.max_hit_points}"
        )

        return event

    def apply_damage_to_npc(self, npc_id: str, amount: int, source: str = "player") -> GameEvent:
        """Apply damage to an NPC or enemy."""
        npc = self.active_npcs.get(npc_id) or self.combat.combatants.get(npc_id)
        if not npc:
            # Try to find by name
            for n in list(self.active_npcs.values()) + list(self.combat.combatants.values()):
                if n.name.lower() == npc_id.lower():
                    npc = n
                    break

        if not npc:
            raise ValueError(f"NPC '{npc_id}' not found")

        actual = npc.take_damage(amount)

        event = GameEvent(
            type=GameEventType.DAMAGE_DEALT,
            turn=self.turn_count,
            data={
                "target": npc.name,
                "target_id": npc.id,
                "amount": actual,
                "new_hp": npc.current_hp,
                "max_hp": npc.max_hp,
                "is_dead": npc.is_dead(),
            }
        )
        self.pending_events.append(event)

        logger.info(
            f"[GameState] {npc.name} took {actual} damage from {source}. "
            f"HP: {npc.current_hp}/{npc.max_hp}"
        )

        return event

    def heal_player(self, amount: int, source: str = "unknown") -> GameEvent:
        """Heal the player character."""
        if not self.character:
            raise ValueError("No character in session")

        old_hp = self.character.current_hit_points
        self.character = self.character.heal(amount)
        actual_healing = self.character.current_hit_points - old_hp

        event = GameEvent(
            type=GameEventType.HP_CHANGED,
            turn=self.turn_count,
            data={
                "change": actual_healing,
                "source": source,
                "current": self.character.current_hit_points,
                "max": self.character.max_hit_points,
            }
        )
        self.pending_events.append(event)

        logger.info(
            f"[GameState] Player healed {actual_healing} HP from {source}. "
            f"HP: {self.character.current_hit_points}/{self.character.max_hit_points}"
        )

        return event

    def add_item(self, item: Item) -> GameEvent:
        """Add an item to the player's inventory."""
        event = self.inventory.add_item(item, self.turn_count)
        self.pending_events.append(event)
        logger.info(f"[GameState] Added item: {item.name} x{item.quantity}")
        return event

    def add_item_by_name(self, name: str, quantity: int = 1) -> GameEvent:
        """Add an item by name (creates a basic Item)."""
        item = Item(name=name, quantity=quantity)
        return self.add_item(item)

    def remove_item(self, item_name: str, quantity: int = 1) -> Optional[GameEvent]:
        """Remove an item from inventory."""
        event = self.inventory.remove_item(item_name, quantity, self.turn_count)
        if event:
            self.pending_events.append(event)
            logger.info(f"[GameState] Removed item: {item_name} x{quantity}")
        return event

    def add_gold(self, amount: int) -> GameEvent:
        """Add gold to the player's inventory."""
        event = self.inventory.add_gold(amount, self.turn_count)
        self.pending_events.append(event)
        logger.info(f"[GameState] Added {amount} gold. Total: {self.inventory.gold}")
        return event

    def remove_gold(self, amount: int) -> Optional[GameEvent]:
        """Remove gold from inventory (if sufficient funds)."""
        event = self.inventory.remove_gold(amount, self.turn_count)
        if event:
            self.pending_events.append(event)
            logger.info(f"[GameState] Removed {amount} gold. Total: {self.inventory.gold}")
        return event

    def add_condition(self, condition: str) -> GameEvent:
        """Add a condition to the player (poisoned, stunned, etc.)."""
        if not self.character:
            raise ValueError("No character in session")

        if condition not in self.character.conditions:
            new_conditions = self.character.conditions + [condition]
            self.character = self.character.model_copy(update={"conditions": new_conditions})

        event = GameEvent(
            type=GameEventType.CONDITION_ADDED,
            turn=self.turn_count,
            data={"condition": condition}
        )
        self.pending_events.append(event)
        logger.info(f"[GameState] Added condition: {condition}")
        return event

    def remove_condition(self, condition: str) -> Optional[GameEvent]:
        """Remove a condition from the player."""
        if not self.character or condition not in self.character.conditions:
            return None

        new_conditions = [c for c in self.character.conditions if c != condition]
        self.character = self.character.model_copy(update={"conditions": new_conditions})

        event = GameEvent(
            type=GameEventType.CONDITION_REMOVED,
            turn=self.turn_count,
            data={"condition": condition}
        )
        self.pending_events.append(event)
        logger.info(f"[GameState] Removed condition: {condition}")
        return event

    def use_spell_slot(self, level: int) -> bool:
        """Use a spell slot. Returns True if successful."""
        if not self.character:
            return False

        updated = self.character.use_power_slot(level)
        if updated:
            self.character = updated
            logger.info(f"[GameState] Used spell slot level {level}")
            return True
        return False

    def change_location(self, new_location: str) -> GameEvent:
        """Change the player's current location."""
        old_location = self.location
        self.location = new_location

        event = GameEvent(
            type=GameEventType.LOCATION_CHANGED,
            turn=self.turn_count,
            data={"location": new_location, "previous": old_location}
        )
        self.pending_events.append(event)
        logger.info(f"[GameState] Location changed: {old_location} -> {new_location}")
        return event

    def add_npc(self, npc: CombatantState):
        """Add an NPC to the active scene."""
        self.active_npcs[npc.id] = npc
        logger.info(f"[GameState] Added NPC: {npc.name}")

    def remove_npc(self, npc_id: str):
        """Remove an NPC from the active scene."""
        if npc_id in self.active_npcs:
            npc = self.active_npcs.pop(npc_id)
            logger.info(f"[GameState] Removed NPC: {npc.name}")

    # =========================================================================
    # COMBAT MANAGEMENT
    # =========================================================================

    def start_combat(self, enemies: List[CombatantState]) -> GameEvent:
        """Start a combat encounter with the given enemies."""
        self.combat = CombatState(active=True, round=1)
        self.phase = "combat"

        # Add player
        if self.character:
            player_combatant = CombatantState(
                id=self.character.character_id,
                name=self.character.name,
                max_hp=self.character.max_hit_points,
                current_hp=self.character.current_hit_points,
                armor_class=self.character.armor_class,
                initiative=self.character.initiative_modifier + 10,  # Roll would go here
                is_player=True,
            )
            self.combat.add_combatant(player_combatant)

        # Add enemies
        for enemy in enemies:
            self.combat.add_combatant(enemy)

        event = GameEvent(
            type=GameEventType.COMBAT_STARTED,
            turn=self.turn_count,
            data={
                "enemies": [e.name for e in enemies],
                "initiative_order": [
                    self.combat.combatants[cid].name
                    for cid in self.combat.initiative_order
                ]
            }
        )
        self.pending_events.append(event)
        logger.info(f"[GameState] Combat started with {len(enemies)} enemies")
        return event

    def end_combat(self) -> GameEvent:
        """End the current combat encounter."""
        self.combat.active = False
        self.phase = "active"

        # Sync player HP back from combat state
        if self.character:
            player_combat = self.combat.combatants.get(self.character.character_id)
            if player_combat:
                self.character = self.character.model_copy(
                    update={"current_hit_points": player_combat.current_hp}
                )

        event = GameEvent(
            type=GameEventType.COMBAT_ENDED,
            turn=self.turn_count,
            data={"rounds": self.combat.round}
        )
        self.pending_events.append(event)
        logger.info(f"[GameState] Combat ended after {self.combat.round} rounds")
        return event

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def advance_turn(self) -> GameEvent:
        """Advance to the next turn."""
        self.turn_count += 1
        event = GameEvent(
            type=GameEventType.TURN_ADVANCED,
            turn=self.turn_count,
            data={"turn": self.turn_count}
        )
        self.pending_events.append(event)
        return event

    def add_to_history(self, role: str, content: str):
        """Add a message to conversation history."""
        self.history.append({"role": role, "content": content})

    def flush_events(self) -> List[GameEvent]:
        """Get and clear all pending events."""
        events = self.pending_events.copy()
        self.pending_events.clear()
        # Also get inventory events (in case any were added directly)
        events.extend(self.inventory.flush_events())
        return events

    # =========================================================================
    # CONTEXT FOR DM AGENT
    # =========================================================================

    def get_dm_context(self) -> str:
        """
        Generate context string for the DM agent.

        This is injected into every DM prompt so the AI knows the actual
        state of the game - HP, inventory, conditions, etc.
        """
        lines = []

        # Player character state
        if self.character:
            lines.append("=== PLAYER CHARACTER STATE ===")
            lines.append(f"Name: {self.character.name}")
            lines.append(f"Class: {self.character.archetype} (Level {self.character.level})")
            lines.append(f"HP: {self.character.current_hit_points}/{self.character.max_hit_points}")

            # Health status description
            hp_pct = self.character.current_hit_points / self.character.max_hit_points
            if hp_pct <= 0:
                lines.append("Status: UNCONSCIOUS/DYING")
            elif hp_pct <= 0.25:
                lines.append("Status: Badly wounded (critical)")
            elif hp_pct <= 0.5:
                lines.append("Status: Wounded")
            elif hp_pct < 1.0:
                lines.append("Status: Lightly wounded")
            else:
                lines.append("Status: Healthy")

            if self.character.temporary_hit_points > 0:
                lines.append(f"Temp HP: {self.character.temporary_hit_points}")

            lines.append(f"AC: {self.character.armor_class}")

            if self.character.conditions:
                lines.append(f"Conditions: {', '.join(self.character.conditions)}")

            # Character identity (personality, backstory) — drives roleplay
            personality_context = self.character.get_personality_context()
            if personality_context:
                lines.append("")
                lines.append("=== CHARACTER IDENTITY ===")
                lines.append(personality_context)

            # Spell/power slots
            if self.character.power_slots_max:
                slots = []
                for level, max_slots in sorted(self.character.power_slots_max.items()):
                    used = self.character.power_slots_used.get(level, 0)
                    remaining = max_slots - used
                    if remaining > 0:
                        slots.append(f"L{level}: {remaining}/{max_slots}")
                if slots:
                    lines.append(f"Spell Slots: {', '.join(slots)}")

        # Inventory
        lines.append("")
        lines.append("=== INVENTORY ===")
        items = self.inventory.items
        if items:
            for item in items[:10]:
                qty_str = f" (x{item.quantity})" if item.quantity > 1 else ""
                equipped_str = " [equipped]" if item.equipped else ""
                lines.append(f"- {item.name}{qty_str}{equipped_str}")
            if len(items) > 10:
                lines.append(f"  ... and {len(items) - 10} more items")
        else:
            lines.append("(empty)")
        lines.append(f"Gold: {self.inventory.gold}")

        # Current scene
        lines.append("")
        lines.append("=== CURRENT SCENE ===")
        lines.append(f"Location: {self.location}")
        lines.append(f"Turn: {self.turn_count}")

        if self.active_npcs:
            lines.append("NPCs present:")
            for npc in self.active_npcs.values():
                status = "dead" if npc.is_dead() else f"HP {npc.current_hp}/{npc.max_hp}"
                lines.append(f"  - {npc.name} ({status})")

        # Combat state
        if self.combat.active:
            lines.append("")
            lines.append("=== ACTIVE COMBAT ===")
            lines.append(f"Round: {self.combat.round}")
            current = self.combat.get_current_combatant()
            if current:
                lines.append(f"Current turn: {current.name}")

            lines.append("Initiative order:")
            for cid in self.combat.initiative_order:
                c = self.combat.combatants.get(cid)
                if c:
                    status = "DEAD" if c.is_dead() else f"HP {c.current_hp}/{c.max_hp}"
                    marker = " <-- CURRENT" if c == current else ""
                    player_marker = " (PLAYER)" if c.is_player else ""
                    lines.append(f"  {c.initiative}: {c.name}{player_marker} ({status}){marker}")

        return "\n".join(lines)

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for persistence."""
        return {
            "session_id": self.session_id,
            "world_id": self.world_id,
            "character": self.character.model_dump() if self.character else None,
            "inventory": self.inventory.to_dict(),
            "turn_count": self.turn_count,
            "phase": self.phase,
            "history": self.history,
            "location": self.location,
            "active_npcs": {k: v.to_dict() for k, v in self.active_npcs.items()},
            "combat": self.combat.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameState":
        """Deserialize state from persistence."""
        state = cls(
            session_id=data["session_id"],
            world_id=data["world_id"],
            turn_count=data.get("turn_count", 0),
            phase=data.get("phase", "active"),
            history=data.get("history", []),
            location=data.get("location", "Unknown"),
        )

        # Restore character
        if data.get("character"):
            state.character = CharacterSheet(**data["character"])

        # Restore inventory
        if data.get("inventory"):
            state.inventory = Inventory.from_dict(data["inventory"])

        # Restore NPCs
        for npc_id, npc_data in data.get("active_npcs", {}).items():
            state.active_npcs[npc_id] = CombatantState.from_dict(npc_data)

        # Restore combat
        if data.get("combat"):
            state.combat = CombatState.from_dict(data["combat"])

        return state

    def save(self, base_path: str = "data/sessions") -> str:
        """
        Save state to JSON file.

        Returns the path to the saved file.
        """
        path = Path(base_path)
        path.mkdir(parents=True, exist_ok=True)

        file_path = path / f"{self.session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

        logger.info(f"[GameState] Saved session {self.session_id} to {file_path}")
        return str(file_path)

    @classmethod
    def load(cls, session_id: str, base_path: str = "data/sessions") -> Optional["GameState"]:
        """
        Load state from JSON file.

        Returns None if file doesn't exist.
        """
        file_path = Path(base_path) / f"{session_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        state = cls.from_dict(data)
        logger.info(f"[GameState] Loaded session {session_id} from {file_path}")
        return state

    @classmethod
    def create_new(
        cls,
        session_id: str,
        world_id: str,
        character: Optional[CharacterSheet] = None,
        starting_gold: int = 10,
    ) -> "GameState":
        """
        Create a new game state with proper initialization.

        Sets up inventory based on character archetype.
        """
        state = cls(
            session_id=session_id,
            world_id=world_id,
            character=character,
            phase="session_0" if not character else "active",
        )

        # Initialize inventory from character archetype
        if character:
            archetype = character.archetype.lower()
            state.inventory = get_starting_inventory(archetype, starting_gold)
            logger.info(
                f"[GameState] Created new session {session_id} for {character.name} "
                f"({archetype}) with {len(state.inventory.items)} starting items"
            )
        else:
            state.inventory = Inventory(gold=starting_gold)
            logger.info(f"[GameState] Created new session {session_id} (no character yet)")

        return state
