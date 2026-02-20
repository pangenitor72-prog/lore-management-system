# Neo4j Schema - Lore Management System

This document describes the Neo4j graph database schema used by the Lore Management System (LMS).

## Node Labels

### Character

Represents an NPC or significant character in the game world.

**Required Properties:**
- `name`: string - The character's name
- `description`: string - A brief description of the character
- `role`: string - The character's role/occupation in the world

**Optional Properties:**
- `species`/`race`: string - The character's species or race
- `age`: number - The character's age
- `alignment`: string - Moral alignment (e.g., "Neutral Good")
- `occupation`: string - Specific job or occupation
- `faction`: string - Primary faction affiliation
- `goals`: string - What the character wants to achieve
- `fears`: string - What the character is afraid of
- `secrets`: string - Hidden information about the character
- `background`: string - Character's history

**OCEAN Personality Traits (NEW):**
- `openness`: float (0.0-1.0) - Creative, curious vs conventional, traditional
- `conscientiousness`: float (0.0-1.0) - Organized, disciplined vs spontaneous, careless
- `extraversion`: float (0.0-1.0) - Outgoing, energetic vs reserved, withdrawn
- `agreeableness`: float (0.0-1.0) - Cooperative, compassionate vs competitive, skeptical
- `neuroticism`: float (0.0-1.0) - Anxious, sensitive vs confident, stable

**Personality Trait Interpretation:**
- 0.0-0.3: Low (e.g., reserved, conventional, anxious)
- 0.4-0.6: Moderate (balanced)
- 0.7-1.0: High (e.g., creative, organized, outgoing)

Personality traits enable consistent, psychologically-grounded NPC behavior across sessions.

**Example Character Node:**
```cypher
CREATE (c:Character {
    name: "Kaela Thornwick",
    description: "A herbalist merchant with a desperate secret",
    role: "Herbalist merchant",
    goals: "Find a cure for her daughter's Void Corruption",
    fears: "The Watch discovering her illegal specimens",
    secrets: "Experimenting with forbidden alchemy",
    openness: 0.6,
    conscientiousness: 0.8,
    extraversion: 0.5,
    agreeableness: 0.6,
    neuroticism: 0.7
})
```

### Location

Represents a place in the game world.

**Required Properties:**
- `name`: string - The location's name
- `description`: string - Description of the location
- `type`: string - Type of location (city, dungeon, forest, etc.)

**Optional Properties:**
- `geography`: string - Geographical features
- `climate`: string - Climate conditions
- `population`: number - Population count
- `government`: string - Type of government
- `notable_features`: string - Notable landmarks or features
- `dangers`: string - Known dangers
- `resources`: string - Available resources
- `history`: string - Historical significance
- `atmosphere`: string - Mood and atmosphere

### Faction

Represents an organization or group.

**Required Properties:**
- `name`: string - Faction name
- `description`: string - Description of the faction
- `motivation`: string - Core motivation/goal

**Optional Properties:**
- `leader`: string - Name of faction leader
- `base_of_operations`: string - Primary location
- `membership_size`: string - Approximate size
- `methods`: string - How they achieve their goals
- `enemies`: string - Known enemies
- `allies`: string - Known allies
- `secrets`: string - Hidden agenda
- `public_face`: string - Public perception

### Item

Represents a significant item or artifact.

**Required Properties:**
- `name`: string - Item name
- `description`: string - Item description
- `type`: string - Item type (weapon, armor, artifact, etc.)

**Optional Properties:**
- `power`: string - Magical or special abilities
- `drawback`: string - Costs or limitations
- `origin`: string - Creation story
- `creator`: string - Who made it
- `current_owner`: string - Current owner
- `material`: string - What it's made of
- `rarity`: string - How rare it is

### Event

Represents a historical or current event.

**Required Properties:**
- `name`: string - Event name
- `description`: string - What happened
- `timeframe`: string - When it occurred
- `participants`: string - Who was involved

**Optional Properties:**
- `location`: string - Where it happened
- `outcome`: string - Result of the event
- `consequences`: string - Long-term effects
- `significance`: string - Why it matters

### Concept

Represents abstract concepts like magic systems, religions, etc.

**Required Properties:**
- `name`: string - Concept name
- `description`: string - Explanation
- `type`: string - Category (magic, religion, etc.)

**Optional Properties:**
- `manifestation`: string - How it appears in the world
- `origin`: string - Where it comes from
- `practitioners`: string - Who uses/follows it
- `dangers`: string - Associated risks
- `limitations`: string - What it can't do

## Relationship Types

### Character Relationships
- `KNOWS` - Characters who know each other
- `ALLIED_WITH` - Alliance relationship
- `ENEMY_OF` - Hostile relationship
- `MEMBER_OF` - Faction membership
- `PRIMARY_MEMBER_OF` - Primary faction affiliation
- `BORN_IN` - Birthplace connection
- `LOCATED_IN` - Current location

### Location Relationships
- `CONNECTED_TO` - Physical connections between locations
- `BORDERS` - Adjacent territories
- `PART_OF` - Hierarchical location relationship

### Faction Relationships
- `ALLIED_WITH` - Faction alliance
- `ENEMY_OF` - Faction rivalry
- `CONTROLS` - Territory or resource control

### Item Relationships
- `OWNED_BY` - Current ownership
- `CREATED_BY` - Creator relationship
- `LOCATED_IN` - Where the item is

## Metadata Properties

All nodes may have these metadata properties:

- `canon_id`: string - Unique identifier
- `confidence`: string - Lore confidence level (CONFIRMED, AI_GENERATED, AI_FLAGGED, SPECULATIVE)
- `created_at`: datetime - When the entity was created
- `created_by`: string - Who/what created it (dm_agent, human, etc.)
- `source_session`: string - Game session where entity originated
- `source_file`: string - Source file if ingested

## Review Queue

Nodes pending human review for contradictions.

**Properties:**
- `review_id`: string - Unique review ID
- `entity_name`: string - Name of proposed entity
- `entity_type`: string - Type of proposed entity
- `proposed_properties`: string (JSON) - Proposed property values
- `contradiction`: string - Description of the conflict
- `severity`: string - HIGH, MEDIUM, or LOW
- `session_id`: string - Originating session
- `status`: string - PENDING, APPROVED, or REJECTED
- `created_at`: datetime - When queued
- `approved_by`/`rejected_by`: string - Who resolved it
- `approved_at`/`rejected_at`: datetime - When resolved

## Contradiction Nodes

Detected contradictions in the lore.

**Properties:**
- `contradiction_id`: string - Unique ID
- `detected_at`: datetime - When detected
- `entity_a_id`: string - First entity involved
- `entity_b_id`: string - Second entity involved
- `contradiction_type`: string - Type of contradiction
- `severity`: string - HIGH, MEDIUM, or LOW
- `description`: string - What the contradiction is
- `evidence`: string (JSON) - Supporting evidence
- `confidence`: float - AI confidence score
- `possible_resolutions`: string (JSON) - Suggested fixes

## Indexes

Recommended indexes for performance:

```cypher
CREATE INDEX character_name IF NOT EXISTS FOR (c:Character) ON (c.name);
CREATE INDEX location_name IF NOT EXISTS FOR (l:Location) ON (l.name);
CREATE INDEX faction_name IF NOT EXISTS FOR (f:Faction) ON (f.name);
CREATE INDEX entity_canon_id IF NOT EXISTS FOR (n) ON (n.canon_id);
CREATE INDEX review_status IF NOT EXISTS FOR (r:ReviewQueue) ON (r.status);
```

## OCEAN Personality System

The OCEAN (Five-Factor) model provides psychologically-grounded personality profiles for NPCs:

| Trait | Low (0.0-0.3) | High (0.7-1.0) |
|-------|---------------|----------------|
| **O**penness | Conventional, practical | Creative, curious |
| **C**onscientiousness | Spontaneous, flexible | Disciplined, organized |
| **E**xtraversion | Reserved, withdrawn | Outgoing, energetic |
| **A**greeableness | Skeptical, competitive | Compassionate, trusting |
| **N**euroticism | Confident, stable | Anxious, sensitive |

### Personality Archetypes

Pre-defined profiles for common NPC types:

| Archetype | O | C | E | A | N |
|-----------|---|---|---|---|---|
| Merchant | 0.5 | 0.7 | 0.6 | 0.5 | 0.4 |
| Guard | 0.3 | 0.8 | 0.4 | 0.5 | 0.3 |
| Scholar | 0.8 | 0.7 | 0.4 | 0.6 | 0.5 |
| Noble | 0.6 | 0.6 | 0.7 | 0.4 | 0.3 |
| Criminal | 0.6 | 0.3 | 0.5 | 0.3 | 0.6 |
| Priest | 0.5 | 0.7 | 0.6 | 0.8 | 0.4 |
| Warrior | 0.4 | 0.6 | 0.6 | 0.4 | 0.3 |
| Peasant | 0.4 | 0.6 | 0.5 | 0.7 | 0.6 |

These profiles drive consistent NPC behavior across all game sessions.

## Character Creation Schema (v22+)

The character creation system uses additional node types to store world-specific playable options.

### World

Represents a game world configuration.

**Properties:**
- `world_id`: string - Unique identifier (same as lore_id)
- `name`: string - Display name

### Origin

Represents a playable race/species for a world.

**Required Properties:**
- `id`: string - Unique identifier
- `world_id`: string - Parent world
- `name`: string - Display name (e.g., "Space Marine", "Street Urchin")
- `base_type`: string - D&D mechanical base (human, elf, dwarf, etc.)

**Optional Properties:**
- `description`: string - Flavor text
- `ability_bonuses`: string (JSON) - e.g., '{"strength": 2, "dexterity": 1}'
- `speed`: integer - Movement speed (default 30)
- `size`: string - Size category (Medium, Small, etc.)
- `traits`: list[string] - Racial traits
- `languages`: list[string] - Languages known
- `skill_proficiencies`: list[string] - Granted skills
- `personality_hint`: string - Creation hints
- `suggested_archetypes`: list[string] - Recommended classes
- `ai_generated`: boolean - True if AI-generated
- `admin_reviewed`: boolean - True if admin approved

**Relationships:**
- `(World)-[:HAS_ORIGIN]->(Origin)`

### Archetype

Represents a playable class for a world.

**Required Properties:**
- `id`: string - Unique identifier
- `world_id`: string - Parent world
- `name`: string - Display name (e.g., "Netrunner", "Void Knight")
- `base_type`: string - D&D mechanical base (fighter, wizard, rogue, etc.)

**Optional Properties:**
- `description`: string - Flavor text
- `hit_die`: string - Hit die (d6, d8, d10, d12)
- `primary_ability`: string - Main ability score
- `saving_throws`: list[string] - Proficient saves
- `armor_proficiencies`: list[string] - Armor proficiencies
- `weapon_proficiencies`: list[string] - Weapon proficiencies
- `skill_choices`: list[string] - Available skill picks
- `num_skill_choices`: integer - Number of skills to choose
- `starting_equipment`: list[string] - Starting gear
- `starting_gold`: integer - Starting gold
- `features`: string (JSON) - Level 1 features
- `has_powers`: boolean - Spellcaster flag
- `power_ability`: string - Spellcasting ability
- `cantrips_known`: integer - Starting cantrips
- `powers_known`: integer - Starting powers
- `playstyle_hint`: string - How the class plays
- `suggested_origins`: list[string] - Recommended races
- `ai_generated`: boolean - True if AI-generated
- `admin_reviewed`: boolean - True if admin approved

**Relationships:**
- `(World)-[:HAS_ARCHETYPE]->(Archetype)`

### EquipmentTemplate

Represents a template for starting equipment items.

**Properties:**
- `id`: string - Unique identifier
- `world_id`: string - Parent world
- `name`: string - Item name
- `description`: string - Item description
- `item_type`: string - weapon, armor, consumable, misc, quest
- `rarity`: string - common, uncommon, rare, very_rare, legendary, artifact
- `equipment_slot`: string - main_hand, off_hand, body, etc.
- `damage`: string - Damage dice (e.g., "1d8")
- `armor_class`: integer - AC bonus
- `weight`: float - Item weight
- `value`: integer - Base value in gold
- `properties`: list[string] - Item properties
- `requires_attunement`: boolean - Attunement required

### Character Creation Indexes

```cypher
CREATE INDEX origin_id IF NOT EXISTS FOR (o:Origin) ON (o.id);
CREATE INDEX origin_world IF NOT EXISTS FOR (o:Origin) ON (o.world_id);
CREATE INDEX archetype_id IF NOT EXISTS FOR (a:Archetype) ON (a.id);
CREATE INDEX archetype_world IF NOT EXISTS FOR (a:Archetype) ON (a.world_id);
CREATE INDEX world_id IF NOT EXISTS FOR (w:World) ON (w.world_id);
```

### Example: Creating World with Character Options

```cypher
// Create world
CREATE (w:World {world_id: 'neon_shadows', name: 'Neon Shadows'})

// Create origin
CREATE (o:Origin {
    id: 'netrunner',
    world_id: 'neon_shadows',
    name: 'Netrunner',
    base_type: 'human',
    description: 'A hacker who interfaces directly with cyberspace',
    ability_bonuses: '{"intelligence": 2, "dexterity": 1}',
    traits: ['Neural Interface', 'Code Mastery']
})
MERGE (w)-[:HAS_ORIGIN]->(o)

// Create archetype
CREATE (a:Archetype {
    id: 'street_samurai',
    world_id: 'neon_shadows',
    name: 'Street Samurai',
    base_type: 'fighter',
    description: 'A cybernetically enhanced warrior',
    hit_die: 'd10',
    primary_ability: 'strength'
})
MERGE (w)-[:HAS_ARCHETYPE]->(a)
```

## Session Overlay System (v66)

The overlay system allows session-scoped mutations to entities without modifying canon data.

### Session Node

Represents a gameplay session.

**Properties:**
- `session_id`: string - Unique session identifier
- `created_at`: datetime - When the session started

### Instance Node

Represents a session-scoped overlay of an Entity. Stores delta properties that override the canon Entity for this session only.

**Properties:**
- `canon_id`: string - Links to the original Entity
- `created_at`: datetime - When the overlay was created
- `updated_at`: datetime - Last modification time
- `is_dead`: boolean - NPC died during this session
- `is_captured`: boolean - NPC was captured/imprisoned
- `is_missing`: boolean - NPC fled/vanished
- `is_hostile`: boolean - NPC turned hostile toward player
- `is_injured`: boolean - NPC was injured
- `disposition`: string - Current disposition (e.g., "hostile", "friendly")
- `status`: string - General status description

### Relationships

```cypher
// Session contains Instance overlays
(s:Session)-[:CONTAINS]->(i:Instance)

// Instance overrides canonical Entity
(i:Instance)-[:OVERRIDES]->(e:Entity)
```

### Example: NPC Death Overlay

```cypher
// When an NPC dies during a session:
MATCH (s:Session {session_id: $sid})
MATCH (e:Entity {canon_id: $cid})
MERGE (s)-[:CONTAINS]->(i:Instance {canon_id: $cid})
ON CREATE SET i.created_at = datetime()
MERGE (i)-[:OVERRIDES]->(e)
SET i.is_dead = true, i.status = 'dead', i.updated_at = datetime()

// Reading with overlay coalesce:
MATCH (e:Entity {canon_id: $cid})
OPTIONAL MATCH (s:Session {session_id: $sid})-[:CONTAINS]->(i:Instance)-[:OVERRIDES]->(e)
RETURN COALESCE(properties(i), properties(e)) as entity
```

Canon entities remain immutable. All session-specific changes are stored in Instance overlays and automatically coalesced during reads.
