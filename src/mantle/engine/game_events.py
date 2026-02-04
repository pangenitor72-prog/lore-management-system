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


class ItemRarity(str, Enum):
    """Item rarity tiers - affects value, availability, and visual presentation."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"
    ARTIFACT = "artifact"


class EquipmentSlot(str, Enum):
    """Equipment slots for worn/wielded items."""
    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    TWO_HAND = "two_hand"  # Uses both hand slots
    HEAD = "head"
    BODY = "body"
    HANDS = "hands"
    FEET = "feet"
    NECK = "neck"
    RING_1 = "ring_1"
    RING_2 = "ring_2"
    ACCESSORY = "accessory"
    NONE = "none"  # Not equippable


class GameEventType(str, Enum):
    """Types of structured game events."""
    # Inventory
    ITEM_ADDED = "ITEM_ADDED"
    ITEM_REMOVED = "ITEM_REMOVED"
    ITEM_USED = "ITEM_USED"
    ITEM_EQUIPPED = "ITEM_EQUIPPED"
    ITEM_UNEQUIPPED = "ITEM_UNEQUIPPED"
    GOLD_CHANGED = "GOLD_CHANGED"
    CURRENCY_CHANGED = "CURRENCY_CHANGED"  # For multi-currency (silver, copper, credits)

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
    DISCOVERY = "DISCOVERY"  # Narrative discoveries (clues, lore, secrets)

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
    """An inventory item with rarity and equipment slot support."""
    name: str
    quantity: int = 1
    item_type: str = "misc"  # weapon, armor, consumable, misc, quest
    description: str = ""
    weight: float = 0.0
    value: int = 0  # Value in gold pieces (base currency)

    # Rarity - affects value multiplier and visual presentation
    rarity: str = "common"  # ItemRarity value

    # Equipment properties
    equipped: bool = False
    equipment_slot: str = "none"  # EquipmentSlot value
    damage: str = ""  # e.g., "1d8" for weapons
    armor_class: int = 0  # For armor

    # Additional properties for special items
    properties: Optional[List[str]] = None  # ["finesse", "light", "thrown"]
    requires_attunement: bool = False
    attuned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "quantity": self.quantity,
            "type": self.item_type,
            "description": self.description,
            "weight": self.weight,
            "value": self.value,
            "rarity": self.rarity,
            "equipped": self.equipped,
            "equipment_slot": self.equipment_slot,
            "damage": self.damage,
            "armor_class": self.armor_class,
            "properties": self.properties or [],
            "requires_attunement": self.requires_attunement,
            "attuned": self.attuned,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Item":
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            quantity=data.get("quantity", 1),
            item_type=data.get("type", data.get("item_type", "misc")),
            description=data.get("description", ""),
            weight=data.get("weight", 0.0),
            value=data.get("value", 0),
            rarity=data.get("rarity", "common"),
            equipped=data.get("equipped", False),
            equipment_slot=data.get("equipment_slot", "none"),
            damage=data.get("damage", ""),
            armor_class=data.get("armor_class", 0),
            properties=data.get("properties"),
            requires_attunement=data.get("requires_attunement", False),
            attuned=data.get("attuned", False),
        )

    def get_value_with_rarity(self) -> int:
        """Get item value adjusted by rarity multiplier."""
        multipliers = {
            "common": 1,
            "uncommon": 2,
            "rare": 5,
            "very_rare": 25,
            "legendary": 100,
            "artifact": 500,
        }
        return self.value * multipliers.get(self.rarity, 1)

    def can_equip_to(self, slot: str) -> bool:
        """Check if item can be equipped to the given slot."""
        if self.equipment_slot == "none":
            return False
        if self.equipment_slot == slot:
            return True
        # Two-hand weapons can go in main_hand but occupy both
        if self.equipment_slot == "two_hand" and slot == "main_hand":
            return True
        return False


class Inventory:
    """
    Character inventory manager with multi-currency and equipment slots.

    Tracks items, currency, and equipped gear. Emits events for all changes.
    """

    def __init__(
        self,
        items: Optional[List[Item]] = None,
        gold: int = 0,
        silver: int = 0,
        copper: int = 0,
    ):
        self._items: List[Item] = items or []
        # Multi-currency support (fantasy: gold/silver/copper, sci-fi: credits/chips)
        self._currency: Dict[str, int] = {
            "gold": gold,
            "silver": silver,
            "copper": copper,
        }
        self._pending_events: List[GameEvent] = []
        # Equipment slots - maps slot to item index in _items
        self._equipped_slots: Dict[str, Optional[int]] = {
            slot.value: None for slot in EquipmentSlot if slot != EquipmentSlot.NONE
        }

    @property
    def items(self) -> List[Item]:
        """Get all items."""
        return self._items.copy()

    @property
    def gold(self) -> int:
        """Get current gold (primary currency for backwards compat)."""
        return self._currency.get("gold", 0)

    @property
    def silver(self) -> int:
        """Get current silver."""
        return self._currency.get("silver", 0)

    @property
    def copper(self) -> int:
        """Get current copper."""
        return self._currency.get("copper", 0)

    @property
    def currency(self) -> Dict[str, int]:
        """Get all currency."""
        return self._currency.copy()

    def get_total_value_in_gold(self) -> float:
        """Get total currency value in gold pieces (10 silver = 1 gold, 10 copper = 1 silver)."""
        return (
            self._currency.get("gold", 0)
            + self._currency.get("silver", 0) / 10
            + self._currency.get("copper", 0) / 100
        )

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
        self._currency["gold"] = self._currency.get("gold", 0) + amount
        event = GameEvent.gold_changed(amount, self._currency["gold"], turn)
        self._pending_events.append(event)
        return event

    def remove_gold(self, amount: int, turn: int = 0) -> Optional[GameEvent]:
        """Remove gold if sufficient funds."""
        current = self._currency.get("gold", 0)
        if current >= amount:
            self._currency["gold"] = current - amount
            event = GameEvent.gold_changed(-amount, self._currency["gold"], turn)
            self._pending_events.append(event)
            return event
        return None

    def add_currency(self, currency_type: str, amount: int, turn: int = 0) -> GameEvent:
        """Add any currency type (gold, silver, copper, credits, etc.)."""
        self._currency[currency_type] = self._currency.get(currency_type, 0) + amount
        event = GameEvent(
            type=GameEventType.CURRENCY_CHANGED,
            data={
                "currency": currency_type,
                "amount": amount,
                "total": self._currency[currency_type],
            },
            turn=turn,
        )
        self._pending_events.append(event)
        return event

    def remove_currency(self, currency_type: str, amount: int, turn: int = 0) -> Optional[GameEvent]:
        """Remove currency if sufficient funds."""
        current = self._currency.get(currency_type, 0)
        if current >= amount:
            self._currency[currency_type] = current - amount
            event = GameEvent(
                type=GameEventType.CURRENCY_CHANGED,
                data={
                    "currency": currency_type,
                    "amount": -amount,
                    "total": self._currency[currency_type],
                },
                turn=turn,
            )
            self._pending_events.append(event)
            return event
        return None

    def get_equipped(self) -> List[Item]:
        """Get equipped items."""
        return [item for item in self._items if item.equipped]

    def get_equipped_in_slot(self, slot: str) -> Optional[Item]:
        """Get the item equipped in a specific slot."""
        idx = self._equipped_slots.get(slot)
        if idx is not None and 0 <= idx < len(self._items):
            return self._items[idx]
        return None

    def equip_item(self, item_name: str, slot: str, turn: int = 0) -> Optional[GameEvent]:
        """Equip an item to a slot. Returns event or None if failed."""
        # Find the item
        item_idx = None
        for i, item in enumerate(self._items):
            if item.name.lower() == item_name.lower():
                item_idx = i
                break

        if item_idx is None:
            return None  # Item not found

        item = self._items[item_idx]
        if not item.can_equip_to(slot):
            return None  # Can't equip to this slot

        # Unequip current item in slot if any
        current_idx = self._equipped_slots.get(slot)
        if current_idx is not None and current_idx < len(self._items):
            self._items[current_idx].equipped = False

        # For two-hand weapons, also clear off-hand
        if item.equipment_slot == "two_hand":
            off_hand_idx = self._equipped_slots.get("off_hand")
            if off_hand_idx is not None and off_hand_idx < len(self._items):
                self._items[off_hand_idx].equipped = False
            self._equipped_slots["off_hand"] = None

        # Equip the new item
        item.equipped = True
        self._equipped_slots[slot] = item_idx

        event = GameEvent(
            type=GameEventType.ITEM_EQUIPPED,
            data={"item": item.name, "slot": slot, "rarity": item.rarity},
            turn=turn,
        )
        self._pending_events.append(event)
        return event

    def unequip_item(self, slot: str, turn: int = 0) -> Optional[GameEvent]:
        """Unequip item from a slot."""
        idx = self._equipped_slots.get(slot)
        if idx is None or idx >= len(self._items):
            return None

        item = self._items[idx]
        item.equipped = False
        self._equipped_slots[slot] = None

        event = GameEvent(
            type=GameEventType.ITEM_UNEQUIPPED,
            data={"item": item.name, "slot": slot},
            turn=turn,
        )
        self._pending_events.append(event)
        return event

    def flush_events(self) -> List[GameEvent]:
        """Get and clear pending events."""
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events

    def to_dict(self) -> Dict[str, Any]:
        """Serialize inventory."""
        # Build equipped map: slot -> item name for display
        equipped_display = {}
        for slot, idx in self._equipped_slots.items():
            if idx is not None and 0 <= idx < len(self._items):
                equipped_display[slot] = self._items[idx].name

        return {
            "items": [item.to_dict() for item in self._items],
            "currency": self._currency,
            "gold": self._currency.get("gold", 0),  # Backwards compat
            "silver": self._currency.get("silver", 0),
            "copper": self._currency.get("copper", 0),
            "equipped_slots": self._equipped_slots,  # Internal: slot -> index
            "equipped": equipped_display,  # API: slot -> item name
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Inventory":
        """Deserialize inventory."""
        items = [Item.from_dict(i) for i in data.get("items", [])]

        # Handle both old format (gold only) and new format (currency dict)
        currency = data.get("currency", {})
        if not currency and "gold" in data:
            currency = {"gold": data.get("gold", 0), "silver": 0, "copper": 0}

        inv = cls(
            items=items,
            gold=currency.get("gold", 0),
            silver=currency.get("silver", 0),
            copper=currency.get("copper", 0),
        )

        # Restore any additional currency types (credits, chips, etc.)
        for key, value in currency.items():
            if key not in ("gold", "silver", "copper"):
                inv._currency[key] = value

        # Restore equipped slots
        equipped = data.get("equipped_slots", {})
        for slot, idx in equipped.items():
            if idx is not None and slot in inv._equipped_slots:
                inv._equipped_slots[slot] = idx

        return inv


# Starting equipment by archetype (D&D 5e inspired) with rarity and equipment slots
STARTING_EQUIPMENT: Dict[str, List[Item]] = {
    "fighter": [
        Item("Longsword", 1, "weapon", "A versatile martial weapon", 3.0, 15,
             rarity="common", equipped=True, equipment_slot="main_hand", damage="1d8",
             properties=["versatile"]),
        Item("Chain Mail", 1, "armor", "Heavy armor (AC 16)", 55.0, 75,
             rarity="common", equipped=True, equipment_slot="body", armor_class=16),
        Item("Shield", 1, "armor", "+2 AC when equipped", 6.0, 10,
             rarity="common", equipped=True, equipment_slot="off_hand", armor_class=2),
        Item("Dungeoneer's Pack", 1, "misc", "Basic adventuring supplies", 12.0, 12),
    ],
    "wizard": [
        Item("Quarterstaff", 1, "weapon", "A simple weapon", 4.0, 1,
             rarity="common", equipped=True, equipment_slot="two_hand", damage="1d6"),
        Item("Spellbook", 1, "misc", "Contains your known spells", 3.0, 50,
             rarity="uncommon", equipped=True),
        Item("Component Pouch", 1, "misc", "Spell components", 2.0, 25),
        Item("Scholar's Pack", 1, "misc", "Books and writing supplies", 10.0, 40),
    ],
    "rogue": [
        Item("Shortsword", 1, "weapon", "A finesse weapon", 2.0, 10,
             rarity="common", equipped=True, equipment_slot="main_hand", damage="1d6",
             properties=["finesse", "light"]),
        Item("Dagger", 2, "weapon", "Light, finesse, thrown", 1.0, 2,
             rarity="common", equipment_slot="off_hand", damage="1d4",
             properties=["finesse", "light", "thrown"]),
        Item("Leather Armor", 1, "armor", "Light armor (AC 11 + DEX)", 10.0, 10,
             rarity="common", equipped=True, equipment_slot="body", armor_class=11),
        Item("Thieves' Tools", 1, "misc", "For picking locks", 1.0, 25),
        Item("Burglar's Pack", 1, "misc", "Rope, caltrops, and more", 11.0, 16),
    ],
    "cleric": [
        Item("Mace", 1, "weapon", "A simple weapon", 4.0, 5,
             rarity="common", equipped=True, equipment_slot="main_hand", damage="1d6"),
        Item("Scale Mail", 1, "armor", "Medium armor (AC 14 + DEX)", 45.0, 50,
             rarity="common", equipped=True, equipment_slot="body", armor_class=14),
        Item("Shield", 1, "armor", "+2 AC when equipped", 6.0, 10,
             rarity="common", equipped=True, equipment_slot="off_hand", armor_class=2),
        Item("Holy Symbol", 1, "misc", "Divine focus for spells", 0.5, 5,
             rarity="uncommon", equipped=True, equipment_slot="neck"),
        Item("Priest's Pack", 1, "misc", "Religious supplies", 10.0, 19),
    ],
    "barbarian": [
        Item("Greataxe", 1, "weapon", "A brutal two-handed weapon", 7.0, 30,
             rarity="common", equipped=True, equipment_slot="two_hand", damage="1d12",
             properties=["heavy", "two-handed"]),
        Item("Handaxe", 2, "weapon", "Light throwing axes", 2.0, 5,
             rarity="common", damage="1d6", properties=["light", "thrown"]),
        Item("Explorer's Pack", 1, "misc", "Outdoor adventuring gear", 10.0, 10),
    ],
    "ranger": [
        Item("Longbow", 1, "weapon", "A ranged martial weapon", 2.0, 50,
             rarity="common", equipped=True, equipment_slot="two_hand", damage="1d8",
             properties=["ammunition", "heavy", "two-handed"]),
        Item("Shortsword", 2, "weapon", "Dual-wielding finesse weapons", 2.0, 10,
             rarity="common", equipment_slot="main_hand", damage="1d6",
             properties=["finesse", "light"]),
        Item("Leather Armor", 1, "armor", "Light armor (AC 11 + DEX)", 10.0, 10,
             rarity="common", equipped=True, equipment_slot="body", armor_class=11),
        Item("Quiver", 1, "misc", "Holds 20 arrows", 1.0, 1),
        Item("Arrows", 20, "consumable", "Ammunition for bows", 0.05, 0),
    ],
    "default": [
        Item("Dagger", 1, "weapon", "A simple weapon", 1.0, 2,
             rarity="common", equipped=True, equipment_slot="main_hand", damage="1d4",
             properties=["finesse", "light", "thrown"]),
        Item("Traveler's Clothes", 1, "armor", "Simple clothing", 4.0, 2,
             rarity="common", equipped=True, equipment_slot="body"),
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
        Populated Inventory with equipped items in proper slots
    """
    archetype_lower = archetype.lower()
    template_items = STARTING_EQUIPMENT.get(archetype_lower, STARTING_EQUIPMENT["default"])

    # Deep copy items to avoid mutating templates
    items = [Item.from_dict(item.to_dict()) for item in template_items]

    inv = Inventory(items=items, gold=starting_gold)

    # Set up equipped slots based on item states
    for i, item in enumerate(inv._items):
        if item.equipped and item.equipment_slot != "none":
            slot = item.equipment_slot
            if slot in inv._equipped_slots:
                inv._equipped_slots[slot] = i

    return inv
