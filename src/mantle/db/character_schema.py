# src/mantle/db/character_schema.py
"""
Neo4j schema for character creation system.

This module defines the persistent storage for world-specific character options:
- Origins (races/species)
- Archetypes (classes)
- Skills
- Equipment Templates

Schema Overview:
    World -[HAS_ORIGIN]-> Origin
    World -[HAS_ARCHETYPE]-> Archetype
    Archetype -[GRANTS_SKILL_CHOICE]-> Skill
    Archetype -[STARTS_WITH]-> EquipmentTemplate
    Origin -[GRANTS_ABILITY_BONUS]-> AbilityBonus (embedded)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class OriginSchema:
    """A playable origin (race/species) for a world."""
    id: str
    world_id: str
    name: str
    description: str = ""

    # Mechanical properties
    ability_bonuses: Dict[str, int] = field(default_factory=dict)  # {"strength": 2, "dexterity": 1}
    speed: int = 30
    size: str = "Medium"
    traits: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    skill_proficiencies: List[str] = field(default_factory=list)

    # Mapping to base D&D mechanics (for rules engine)
    base_type: str = "human"  # D&D race for mechanical fallback

    # UI/Creation hints
    personality_hint: str = ""
    suggested_archetypes: List[str] = field(default_factory=list)

    # Metadata
    ai_generated: bool = False
    admin_reviewed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "world_id": self.world_id,
            "name": self.name,
            "description": self.description,
            "ability_bonuses": self.ability_bonuses,
            "speed": self.speed,
            "size": self.size,
            "traits": self.traits,
            "languages": self.languages,
            "skill_proficiencies": self.skill_proficiencies,
            "base_type": self.base_type,
            "personality_hint": self.personality_hint,
            "suggested_archetypes": self.suggested_archetypes,
            "ai_generated": self.ai_generated,
            "admin_reviewed": self.admin_reviewed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OriginSchema":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif not isinstance(created_at, datetime):
            created_at = datetime.now(timezone.utc)

        return cls(
            id=data.get("id", str(uuid4())),
            world_id=data.get("world_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            ability_bonuses=data.get("ability_bonuses", {}),
            speed=data.get("speed", 30),
            size=data.get("size", "Medium"),
            traits=data.get("traits", []),
            languages=data.get("languages", []),
            skill_proficiencies=data.get("skill_proficiencies", []),
            base_type=data.get("base_type", "human"),
            personality_hint=data.get("personality_hint", ""),
            suggested_archetypes=data.get("suggested_archetypes", []),
            ai_generated=data.get("ai_generated", False),
            admin_reviewed=data.get("admin_reviewed", False),
            created_at=created_at,
        )


@dataclass
class ArchetypeSchema:
    """A playable archetype (class) for a world."""
    id: str
    world_id: str
    name: str
    description: str = ""

    # Core mechanics
    hit_die: str = "d8"  # d6, d8, d10, d12
    primary_ability: str = "strength"
    saving_throws: List[str] = field(default_factory=list)

    # Proficiencies
    armor_proficiencies: List[str] = field(default_factory=list)
    weapon_proficiencies: List[str] = field(default_factory=list)
    skill_choices: List[str] = field(default_factory=list)
    num_skill_choices: int = 2

    # Starting equipment (list of EquipmentTemplate IDs or item names)
    starting_equipment: List[str] = field(default_factory=list)
    starting_gold: int = 10

    # Features at level 1
    features: List[Dict[str, str]] = field(default_factory=list)  # [{"name": "...", "description": "..."}]

    # Powers/Spellcasting
    has_powers: bool = False
    power_ability: Optional[str] = None
    cantrips_known: int = 0
    powers_known: int = 0

    # Mapping to base D&D mechanics
    base_type: str = "fighter"  # D&D class for mechanical fallback

    # UI hints
    playstyle_hint: str = ""
    suggested_origins: List[str] = field(default_factory=list)

    # Metadata
    ai_generated: bool = False
    admin_reviewed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "world_id": self.world_id,
            "name": self.name,
            "description": self.description,
            "hit_die": self.hit_die,
            "primary_ability": self.primary_ability,
            "saving_throws": self.saving_throws,
            "armor_proficiencies": self.armor_proficiencies,
            "weapon_proficiencies": self.weapon_proficiencies,
            "skill_choices": self.skill_choices,
            "num_skill_choices": self.num_skill_choices,
            "starting_equipment": self.starting_equipment,
            "starting_gold": self.starting_gold,
            "features": self.features,
            "has_powers": self.has_powers,
            "power_ability": self.power_ability,
            "cantrips_known": self.cantrips_known,
            "powers_known": self.powers_known,
            "base_type": self.base_type,
            "playstyle_hint": self.playstyle_hint,
            "suggested_origins": self.suggested_origins,
            "ai_generated": self.ai_generated,
            "admin_reviewed": self.admin_reviewed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArchetypeSchema":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif not isinstance(created_at, datetime):
            created_at = datetime.now(timezone.utc)

        return cls(
            id=data.get("id", str(uuid4())),
            world_id=data.get("world_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            hit_die=data.get("hit_die", "d8"),
            primary_ability=data.get("primary_ability", "strength"),
            saving_throws=data.get("saving_throws", []),
            armor_proficiencies=data.get("armor_proficiencies", []),
            weapon_proficiencies=data.get("weapon_proficiencies", []),
            skill_choices=data.get("skill_choices", []),
            num_skill_choices=data.get("num_skill_choices", 2),
            starting_equipment=data.get("starting_equipment", []),
            starting_gold=data.get("starting_gold", 10),
            features=data.get("features", []),
            has_powers=data.get("has_powers", False),
            power_ability=data.get("power_ability"),
            cantrips_known=data.get("cantrips_known", 0),
            powers_known=data.get("powers_known", 0),
            base_type=data.get("base_type", "fighter"),
            playstyle_hint=data.get("playstyle_hint", ""),
            suggested_origins=data.get("suggested_origins", []),
            ai_generated=data.get("ai_generated", False),
            admin_reviewed=data.get("admin_reviewed", False),
            created_at=created_at,
        )


@dataclass
class EquipmentTemplateSchema:
    """A template for starting equipment items."""
    id: str
    world_id: str
    name: str
    description: str = ""

    # Item properties (mirrors game_events.Item)
    item_type: str = "misc"  # weapon, armor, consumable, misc, quest
    rarity: str = "common"
    equipment_slot: str = "none"

    # Stats
    damage: str = ""  # "1d8", "2d6", etc.
    armor_class: int = 0
    weight: float = 0.0
    value: int = 0  # Base value in gold

    # Properties
    properties: List[str] = field(default_factory=list)  # ["finesse", "light", "two-handed"]
    requires_attunement: bool = False

    # Metadata
    ai_generated: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "world_id": self.world_id,
            "name": self.name,
            "description": self.description,
            "item_type": self.item_type,
            "rarity": self.rarity,
            "equipment_slot": self.equipment_slot,
            "damage": self.damage,
            "armor_class": self.armor_class,
            "weight": self.weight,
            "value": self.value,
            "properties": self.properties,
            "requires_attunement": self.requires_attunement,
            "ai_generated": self.ai_generated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EquipmentTemplateSchema":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif not isinstance(created_at, datetime):
            created_at = datetime.now(timezone.utc)

        return cls(
            id=data.get("id", str(uuid4())),
            world_id=data.get("world_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            item_type=data.get("item_type", "misc"),
            rarity=data.get("rarity", "common"),
            equipment_slot=data.get("equipment_slot", "none"),
            damage=data.get("damage", ""),
            armor_class=data.get("armor_class", 0),
            weight=data.get("weight", 0.0),
            value=data.get("value", 0),
            properties=data.get("properties", []),
            requires_attunement=data.get("requires_attunement", False),
            ai_generated=data.get("ai_generated", False),
            created_at=created_at,
        )


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

class CharacterSchemaDB:
    """Database operations for character creation schema."""

    def __init__(self, db):
        """Initialize with a Neo4jDatabase instance."""
        self.db = db

    # -------------------------------------------------------------------------
    # ORIGIN OPERATIONS
    # -------------------------------------------------------------------------

    async def create_origin(self, origin: OriginSchema) -> OriginSchema:
        """Create a new origin in the database."""
        await self.db.execute(
            """
            MERGE (w:World {world_id: $world_id})
            CREATE (o:Origin {
                id: $id,
                world_id: $world_id,
                name: $name,
                description: $description,
                ability_bonuses: $ability_bonuses,
                speed: $speed,
                size: $size,
                traits: $traits,
                languages: $languages,
                skill_proficiencies: $skill_proficiencies,
                base_type: $base_type,
                personality_hint: $personality_hint,
                suggested_archetypes: $suggested_archetypes,
                ai_generated: $ai_generated,
                admin_reviewed: $admin_reviewed,
                created_at: datetime()
            })
            MERGE (w)-[:HAS_ORIGIN]->(o)
            RETURN o
            """,
            {
                "id": origin.id,
                "world_id": origin.world_id,
                "name": origin.name,
                "description": origin.description,
                "ability_bonuses": str(origin.ability_bonuses),  # Neo4j doesn't support nested maps well
                "speed": origin.speed,
                "size": origin.size,
                "traits": origin.traits,
                "languages": origin.languages,
                "skill_proficiencies": origin.skill_proficiencies,
                "base_type": origin.base_type,
                "personality_hint": origin.personality_hint,
                "suggested_archetypes": origin.suggested_archetypes,
                "ai_generated": origin.ai_generated,
                "admin_reviewed": origin.admin_reviewed,
            }
        )
        logger.info(f"Created origin: {origin.name} for world {origin.world_id}")
        return origin

    async def get_origins_for_world(self, world_id: str) -> List[OriginSchema]:
        """Get all origins for a world."""
        result = await self.db.execute(
            """
            MATCH (w:World {world_id: $world_id})-[:HAS_ORIGIN]->(o:Origin)
            RETURN o
            ORDER BY o.name
            """,
            {"world_id": world_id}
        )

        origins = []
        for record in result:
            data = dict(record.get("o", {}))
            # Parse ability_bonuses back from string
            if isinstance(data.get("ability_bonuses"), str):
                try:
                    import ast
                    data["ability_bonuses"] = ast.literal_eval(data["ability_bonuses"])
                except (ValueError, SyntaxError):
                    data["ability_bonuses"] = {}
            origins.append(OriginSchema.from_dict(data))

        return origins

    async def update_origin(self, origin: OriginSchema) -> OriginSchema:
        """Update an existing origin."""
        await self.db.execute(
            """
            MATCH (o:Origin {id: $id, world_id: $world_id})
            SET o.name = $name,
                o.description = $description,
                o.ability_bonuses = $ability_bonuses,
                o.speed = $speed,
                o.size = $size,
                o.traits = $traits,
                o.languages = $languages,
                o.skill_proficiencies = $skill_proficiencies,
                o.base_type = $base_type,
                o.personality_hint = $personality_hint,
                o.suggested_archetypes = $suggested_archetypes,
                o.admin_reviewed = $admin_reviewed
            RETURN o
            """,
            {
                "id": origin.id,
                "world_id": origin.world_id,
                "name": origin.name,
                "description": origin.description,
                "ability_bonuses": str(origin.ability_bonuses),
                "speed": origin.speed,
                "size": origin.size,
                "traits": origin.traits,
                "languages": origin.languages,
                "skill_proficiencies": origin.skill_proficiencies,
                "base_type": origin.base_type,
                "personality_hint": origin.personality_hint,
                "suggested_archetypes": origin.suggested_archetypes,
                "admin_reviewed": origin.admin_reviewed,
            }
        )
        logger.info(f"Updated origin: {origin.name}")
        return origin

    async def delete_origin(self, origin_id: str, world_id: str) -> bool:
        """Delete an origin."""
        result = await self.db.execute(
            """
            MATCH (o:Origin {id: $id, world_id: $world_id})
            DETACH DELETE o
            RETURN count(o) as deleted
            """,
            {"id": origin_id, "world_id": world_id}
        )
        deleted = result[0].get("deleted", 0) if result else 0
        return deleted > 0

    # -------------------------------------------------------------------------
    # ARCHETYPE OPERATIONS
    # -------------------------------------------------------------------------

    async def create_archetype(self, archetype: ArchetypeSchema) -> ArchetypeSchema:
        """Create a new archetype in the database."""
        import json
        await self.db.execute(
            """
            MERGE (w:World {world_id: $world_id})
            CREATE (a:Archetype {
                id: $id,
                world_id: $world_id,
                name: $name,
                description: $description,
                hit_die: $hit_die,
                primary_ability: $primary_ability,
                saving_throws: $saving_throws,
                armor_proficiencies: $armor_proficiencies,
                weapon_proficiencies: $weapon_proficiencies,
                skill_choices: $skill_choices,
                num_skill_choices: $num_skill_choices,
                starting_equipment: $starting_equipment,
                starting_gold: $starting_gold,
                features: $features,
                has_powers: $has_powers,
                power_ability: $power_ability,
                cantrips_known: $cantrips_known,
                powers_known: $powers_known,
                base_type: $base_type,
                playstyle_hint: $playstyle_hint,
                suggested_origins: $suggested_origins,
                ai_generated: $ai_generated,
                admin_reviewed: $admin_reviewed,
                created_at: datetime()
            })
            MERGE (w)-[:HAS_ARCHETYPE]->(a)
            RETURN a
            """,
            {
                "id": archetype.id,
                "world_id": archetype.world_id,
                "name": archetype.name,
                "description": archetype.description,
                "hit_die": archetype.hit_die,
                "primary_ability": archetype.primary_ability,
                "saving_throws": archetype.saving_throws,
                "armor_proficiencies": archetype.armor_proficiencies,
                "weapon_proficiencies": archetype.weapon_proficiencies,
                "skill_choices": archetype.skill_choices,
                "num_skill_choices": archetype.num_skill_choices,
                "starting_equipment": archetype.starting_equipment,
                "starting_gold": archetype.starting_gold,
                "features": json.dumps(archetype.features),  # Store as JSON string
                "has_powers": archetype.has_powers,
                "power_ability": archetype.power_ability or "",
                "cantrips_known": archetype.cantrips_known,
                "powers_known": archetype.powers_known,
                "base_type": archetype.base_type,
                "playstyle_hint": archetype.playstyle_hint,
                "suggested_origins": archetype.suggested_origins,
                "ai_generated": archetype.ai_generated,
                "admin_reviewed": archetype.admin_reviewed,
            }
        )
        logger.info(f"Created archetype: {archetype.name} for world {archetype.world_id}")
        return archetype

    async def get_archetypes_for_world(self, world_id: str) -> List[ArchetypeSchema]:
        """Get all archetypes for a world."""
        import json
        result = await self.db.execute(
            """
            MATCH (w:World {world_id: $world_id})-[:HAS_ARCHETYPE]->(a:Archetype)
            RETURN a
            ORDER BY a.name
            """,
            {"world_id": world_id}
        )

        archetypes = []
        for record in result:
            data = dict(record.get("a", {}))
            # Parse features back from JSON string
            if isinstance(data.get("features"), str):
                try:
                    data["features"] = json.loads(data["features"])
                except json.JSONDecodeError:
                    data["features"] = []
            archetypes.append(ArchetypeSchema.from_dict(data))

        return archetypes

    async def update_archetype(self, archetype: ArchetypeSchema) -> ArchetypeSchema:
        """Update an existing archetype."""
        import json
        await self.db.execute(
            """
            MATCH (a:Archetype {id: $id, world_id: $world_id})
            SET a.name = $name,
                a.description = $description,
                a.hit_die = $hit_die,
                a.primary_ability = $primary_ability,
                a.saving_throws = $saving_throws,
                a.armor_proficiencies = $armor_proficiencies,
                a.weapon_proficiencies = $weapon_proficiencies,
                a.skill_choices = $skill_choices,
                a.num_skill_choices = $num_skill_choices,
                a.starting_equipment = $starting_equipment,
                a.starting_gold = $starting_gold,
                a.features = $features,
                a.has_powers = $has_powers,
                a.power_ability = $power_ability,
                a.cantrips_known = $cantrips_known,
                a.powers_known = $powers_known,
                a.base_type = $base_type,
                a.playstyle_hint = $playstyle_hint,
                a.suggested_origins = $suggested_origins,
                a.admin_reviewed = $admin_reviewed
            RETURN a
            """,
            {
                "id": archetype.id,
                "world_id": archetype.world_id,
                "name": archetype.name,
                "description": archetype.description,
                "hit_die": archetype.hit_die,
                "primary_ability": archetype.primary_ability,
                "saving_throws": archetype.saving_throws,
                "armor_proficiencies": archetype.armor_proficiencies,
                "weapon_proficiencies": archetype.weapon_proficiencies,
                "skill_choices": archetype.skill_choices,
                "num_skill_choices": archetype.num_skill_choices,
                "starting_equipment": archetype.starting_equipment,
                "starting_gold": archetype.starting_gold,
                "features": json.dumps(archetype.features),
                "has_powers": archetype.has_powers,
                "power_ability": archetype.power_ability or "",
                "cantrips_known": archetype.cantrips_known,
                "powers_known": archetype.powers_known,
                "base_type": archetype.base_type,
                "playstyle_hint": archetype.playstyle_hint,
                "suggested_origins": archetype.suggested_origins,
                "admin_reviewed": archetype.admin_reviewed,
            }
        )
        logger.info(f"Updated archetype: {archetype.name}")
        return archetype

    async def delete_archetype(self, archetype_id: str, world_id: str) -> bool:
        """Delete an archetype."""
        result = await self.db.execute(
            """
            MATCH (a:Archetype {id: $id, world_id: $world_id})
            DETACH DELETE a
            RETURN count(a) as deleted
            """,
            {"id": archetype_id, "world_id": world_id}
        )
        deleted = result[0].get("deleted", 0) if result else 0
        return deleted > 0

    # -------------------------------------------------------------------------
    # BULK OPERATIONS
    # -------------------------------------------------------------------------

    async def save_character_options(
        self,
        world_id: str,
        origins: List[Dict[str, Any]],
        archetypes: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Save all character options for a world (replaces existing).

        Used by World Tuner to persist AI-generated or admin-edited options.
        """
        # Delete existing options
        await self.db.execute(
            """
            MATCH (w:World {world_id: $world_id})-[:HAS_ORIGIN]->(o:Origin)
            DETACH DELETE o
            """,
            {"world_id": world_id}
        )
        await self.db.execute(
            """
            MATCH (w:World {world_id: $world_id})-[:HAS_ARCHETYPE]->(a:Archetype)
            DETACH DELETE a
            """,
            {"world_id": world_id}
        )

        # Create new options
        origins_created = 0
        for origin_data in origins:
            origin_data["world_id"] = world_id
            if not origin_data.get("id"):
                origin_data["id"] = str(uuid4())
            origin = OriginSchema.from_dict(origin_data)
            await self.create_origin(origin)
            origins_created += 1

        archetypes_created = 0
        for arch_data in archetypes:
            arch_data["world_id"] = world_id
            if not arch_data.get("id"):
                arch_data["id"] = str(uuid4())
            archetype = ArchetypeSchema.from_dict(arch_data)
            await self.create_archetype(archetype)
            archetypes_created += 1

        logger.info(
            f"Saved character options for world {world_id}: "
            f"{origins_created} origins, {archetypes_created} archetypes"
        )

        return {
            "origins_created": origins_created,
            "archetypes_created": archetypes_created,
        }

    async def get_character_options(self, world_id: str) -> Dict[str, Any]:
        """
        Get all character options for a world.

        Returns format compatible with LORE_BASES character_options.
        """
        origins = await self.get_origins_for_world(world_id)
        archetypes = await self.get_archetypes_for_world(world_id)

        return {
            "origins": [o.to_dict() for o in origins],
            "archetypes": [a.to_dict() for a in archetypes],
            "source": "neo4j",
        }

    # -------------------------------------------------------------------------
    # SCHEMA INITIALIZATION
    # -------------------------------------------------------------------------

    async def ensure_indexes(self):
        """Create indexes for character schema nodes."""
        indexes = [
            "CREATE INDEX origin_id IF NOT EXISTS FOR (o:Origin) ON (o.id)",
            "CREATE INDEX origin_world IF NOT EXISTS FOR (o:Origin) ON (o.world_id)",
            "CREATE INDEX archetype_id IF NOT EXISTS FOR (a:Archetype) ON (a.id)",
            "CREATE INDEX archetype_world IF NOT EXISTS FOR (a:Archetype) ON (a.world_id)",
            "CREATE INDEX world_id IF NOT EXISTS FOR (w:World) ON (w.world_id)",
        ]

        for index_query in indexes:
            try:
                await self.db.execute(index_query)
            except Exception as e:
                # Index might already exist
                logger.debug(f"Index creation note: {e}")

        logger.info("Character schema indexes ensured")
