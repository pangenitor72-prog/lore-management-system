# src/airpg/runtime/game_events.py
"""
Structured Game Events - For frontend notifications.

DMAgent emits these events separately from prose narrative,
allowing the frontend to display distinct notifications for
inventory changes, combat results, skill checks, etc.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class GameEventType(str, Enum):
    """Types of structured game events."""
    # Inventory
    ITEM_ADDED = "ITEM_ADDED"
    ITEM_REMOVED = "ITEM_REMOVED"
    ITEM_USED = "ITEM_USED"
    GOLD_CHANGED = "GOLD_CHANGED"

    # Combat
    DAMAGE_DEALT = "DAMAGE_DEALT"
    DAMAGE_TAKEN = "DAMAGE_TAKEN"
    COMBAT_STARTED = "COMBAT_STARTED"
    COMBAT_ENDED = "COMBAT_ENDED"

    # Checks
    SKILL_CHECK = "SKILL_CHECK"
    SAVING_THROW = "SAVING_THROW"
    ATTACK_ROLL = "ATTACK_ROLL"

    # Character
    HP_CHANGED = "HP_CHANGED"
    LEVEL_UP = "LEVEL_UP"
    CONDITION_ADDED = "CONDITION_ADDED"
    CONDITION_REMOVED = "CONDITION_REMOVED"

    # Story
    LOCATION_CHANGED = "LOCATION_CHANGED"
    NPC_MET = "NPC_MET"
    QUEST_STARTED = "QUEST_STARTED"
    QUEST_COMPLETED = "QUEST_COMPLETED"

    # Session
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_ENDED = "SESSION_ENDED"
    TURN_ADVANCED = "TURN_ADVANCED"


@dataclass
class GameEvent:
    """A structured game event for frontend consumption."""
    type: GameEventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    turn: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON transmission."""
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "turn": self.turn,
        }

    @classmethod
    def item_added(cls, item_name: str, quantity: int = 1, turn: int = 0) -> "GameEvent":
        """Create an ITEM_ADDED event."""
        return cls(
            type=GameEventType.ITEM_ADDED,
            data={"item": item_name, "quantity": quantity},
            turn=turn,
        )

    @classmethod
    def item_removed(cls, item_name: str, quantity: int = 1, turn: int = 0) -> "GameEvent":
        """Create an ITEM_REMOVED event."""
        return cls(
            type=GameEventType.ITEM_REMOVED,
            data={"item": item_name, "quantity": quantity},
            turn=turn,
        )

    @classmethod
    def gold_changed(cls, amount: int, new_total: int, turn: int = 0) -> "GameEvent":
        """Create a GOLD_CHANGED event."""
        return cls(
            type=GameEventType.GOLD_CHANGED,
            data={"amount": amount, "total": new_total},
            turn=turn,
        )

    @classmethod
    def skill_check(
        cls,
        skill: str,
        roll: int,
        modifier: int,
        dc: int,
        success: bool,
        turn: int = 0,
    ) -> "GameEvent":
        """Create a SKILL_CHECK event."""
        return cls(
            type=GameEventType.SKILL_CHECK,
            data={
                "skill": skill,
                "roll": roll,
                "modifier": modifier,
                "total": roll + modifier,
                "dc": dc,
                "success": success,
            },
            turn=turn,
        )

    @classmethod
    def damage_taken(
        cls,
        amount: int,
        damage_type: str,
        source: str,
        turn: int = 0,
    ) -> "GameEvent":
        """Create a DAMAGE_TAKEN event."""
        return cls(
            type=GameEventType.DAMAGE_TAKEN,
            data={"amount": amount, "type": damage_type, "source": source},
            turn=turn,
        )

    @classmethod
    def hp_changed(
        cls,
        current: int,
        maximum: int,
        change: int,
        turn: int = 0,
    ) -> "GameEvent":
        """Create an HP_CHANGED event."""
        return cls(
            type=GameEventType.HP_CHANGED,
            data={"current": current, "max": maximum, "change": change},
            turn=turn,
        )

    @classmethod
    def location_changed(cls, location: str, turn: int = 0) -> "GameEvent":
        """Create a LOCATION_CHANGED event."""
        return cls(
            type=GameEventType.LOCATION_CHANGED,
            data={"location": location},
            turn=turn,
        )


@dataclass
class Item:
    """An inventory item."""
    name: str
    quantity: int = 1
    item_type: str = "misc"  # weapon, armor, consumable, misc, quest
    description: str = ""
    weight: float = 0.0
    value: int = 0  # Value in gold pieces

    # Equipment properties
    equipped: bool = False
    damage: str = ""  # e.g., "1d8" for weapons
    armor_class: int = 0  # For armor

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "quantity": self.quantity,
            "type": self.item_type,
            "description": self.description,
            "weight": self.weight,
            "value": self.value,
            "equipped": self.equipped,
            "damage": self.damage,
            "armor_class": self.armor_class,
        }


class Inventory:
    """
    Character inventory manager.

    Tracks items and emits events for changes.
    """

    def __init__(self, items: Optional[List[Item]] = None, gold: int = 0):
        self._items: List[Item] = items or []
        self._gold = gold
        self._pending_events: List[GameEvent] = []

    @property
    def items(self) -> List[Item]:
        """Get all items."""
        return self._items.copy()

    @property
    def gold(self) -> int:
        """Get current gold."""
        return self._gold

    def add_item(self, item: Item, turn: int = 0) -> GameEvent:
        """Add an item and emit event."""
        # Check if item already exists (stack)
        for existing in self._items:
            if existing.name == item.name and existing.item_type == item.item_type:
                existing.quantity += item.quantity
                event = GameEvent.item_added(item.name, item.quantity, turn)
                self._pending_events.append(event)
                return event

        # New item
        self._items.append(item)
        event = GameEvent.item_added(item.name, item.quantity, turn)
        self._pending_events.append(event)
        return event

    def remove_item(self, item_name: str, quantity: int = 1, turn: int = 0) -> Optional[GameEvent]:
        """Remove an item and emit event."""
        for i, item in enumerate(self._items):
            if item.name == item_name:
                if item.quantity <= quantity:
                    self._items.pop(i)
                else:
                    item.quantity -= quantity
                event = GameEvent.item_removed(item_name, quantity, turn)
                self._pending_events.append(event)
                return event
        return None

    def add_gold(self, amount: int, turn: int = 0) -> GameEvent:
        """Add gold and emit event."""
        self._gold += amount
        event = GameEvent.gold_changed(amount, self._gold, turn)
        self._pending_events.append(event)
        return event

    def remove_gold(self, amount: int, turn: int = 0) -> Optional[GameEvent]:
        """Remove gold if sufficient funds."""
        if self._gold >= amount:
            self._gold -= amount
            event = GameEvent.gold_changed(-amount, self._gold, turn)
            self._pending_events.append(event)
            return event
        return None

    def get_equipped(self) -> List[Item]:
        """Get equipped items."""
        return [item for item in self._items if item.equipped]

    def flush_events(self) -> List[GameEvent]:
        """Get and clear pending events."""
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events

    def to_dict(self) -> Dict[str, Any]:
        """Serialize inventory."""
        return {
            "items": [item.to_dict() for item in self._items],
            "gold": self._gold,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Inventory":
        """Deserialize inventory."""
        items = [
            Item(
                name=i["name"],
                quantity=i.get("quantity", 1),
                item_type=i.get("type", "misc"),
                description=i.get("description", ""),
                weight=i.get("weight", 0.0),
                value=i.get("value", 0),
                equipped=i.get("equipped", False),
                damage=i.get("damage", ""),
                armor_class=i.get("armor_class", 0),
            )
            for i in data.get("items", [])
        ]
        return cls(items=items, gold=data.get("gold", 0))


# Starting equipment by archetype (D&D 5e inspired)
STARTING_EQUIPMENT = {
    "fighter": [
        Item("Longsword", 1, "weapon", "A versatile martial weapon", 3.0, 15, True, "1d8"),
        Item("Chain Mail", 1, "armor", "Heavy armor (AC 16)", 55.0, 75, True, "", 16),
        Item("Shield", 1, "armor", "+2 AC when equipped", 6.0, 10, True, "", 2),
        Item("Dungeoneer's Pack", 1, "misc", "Basic adventuring supplies", 12.0, 12),
    ],
    "wizard": [
        Item("Quarterstaff", 1, "weapon", "A simple weapon", 4.0, 1, True, "1d6"),
        Item("Spellbook", 1, "misc", "Contains your known spells", 3.0, 50, True),
        Item("Component Pouch", 1, "misc", "Spell components", 2.0, 25, True),
        Item("Scholar's Pack", 1, "misc", "Books and writing supplies", 10.0, 40),
    ],
    "rogue": [
        Item("Shortsword", 1, "weapon", "A finesse weapon", 2.0, 10, True, "1d6"),
        Item("Dagger", 2, "weapon", "Light, finesse, thrown", 1.0, 2, True, "1d4"),
        Item("Leather Armor", 1, "armor", "Light armor (AC 11 + DEX)", 10.0, 10, True, "", 11),
        Item("Thieves' Tools", 1, "misc", "For picking locks", 1.0, 25, True),
        Item("Burglar's Pack", 1, "misc", "Rope, caltrops, and more", 11.0, 16),
    ],
    "cleric": [
        Item("Mace", 1, "weapon", "A simple weapon", 4.0, 5, True, "1d6"),
        Item("Scale Mail", 1, "armor", "Medium armor (AC 14 + DEX)", 45.0, 50, True, "", 14),
        Item("Shield", 1, "armor", "+2 AC when equipped", 6.0, 10, True, "", 2),
        Item("Holy Symbol", 1, "misc", "Divine focus for spells", 0.5, 5, True),
        Item("Priest's Pack", 1, "misc", "Religious supplies", 10.0, 19),
    ],
    "default": [
        Item("Dagger", 1, "weapon", "A simple weapon", 1.0, 2, True, "1d4"),
        Item("Traveler's Clothes", 1, "armor", "Simple clothing", 4.0, 2, True),
        Item("Backpack", 1, "misc", "For carrying equipment", 5.0, 2),
    ],
}


def get_starting_inventory(archetype: str, starting_gold: int = 10) -> Inventory:
    """
    Get starting inventory for a character archetype.

    Args:
        archetype: Character class/archetype (fighter, wizard, etc.)
        starting_gold: Starting gold pieces

    Returns:
        Populated Inventory
    """
    archetype_lower = archetype.lower()
    items = STARTING_EQUIPMENT.get(archetype_lower, STARTING_EQUIPMENT["default"])
    return Inventory(items=[Item(**item.__dict__) for item in items], gold=starting_gold)
