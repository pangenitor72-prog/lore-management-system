# Cross-World Entity Linking Fix

## Summary

This PR fixes a critical bug where relationships were being created across different worlds when entities share the same name during lore ingestion. It also adds an admin workflow to promote session-created entities into canon.

## Problem Statement

### The Bug
During lore ingestion (both admin uploads to canon and AI DM generated entities during sessions), relationships were being created across worlds when entities shared the same name. The root cause was in `src/lms/agents/lore_parsing_agent.py`: relationship storage used Cypher matching by `{name: $source}` / `{name: $target}` with no `world_id`/`curated_world_id` scoping, allowing matching to bind to entities in different worlds.

This caused cross-world relationships, contaminating the graph and potentially bleeding lore between sessions/worlds.

### Example Scenario
```
World A: Captain Varn (pirate captain)
World B: Captain Varn (military officer)

When ingesting "Captain Varn commands the ship" into World A:
BUG: Could create relationship to World B's Captain Varn
FIX: Now creates relationship only to World A's Captain Varn
```

## Solution

### 1. Relationship Storage Fix (lore_parsing_agent.py)

**Key Changes:**
- Maintain `entity_name_to_canon_id` mapping during entity ingestion scope
- Resolve relationships using canon_id with the following priority:
  1. **Priority 1**: Use canon_id from current ingestion scope (mapping)
  2. **Priority 2**: World-scoped name lookup if entity not in current batch
  3. **Fallback**: Skip relationship with warning if resolution fails

**Code Flow:**
```python
# Build mapping during entity storage
entity_name_to_canon_id[entity.name.lower()] = canon_id
for alias in entity.aliases:
    entity_name_to_canon_id[alias.lower()] = canon_id

# Use mapping for relationship resolution
source_canon_id = entity_name_to_canon_id.get(rel.source.lower())
target_canon_id = entity_name_to_canon_id.get(rel.target.lower())

# Fallback to world-scoped lookup if not in mapping
if not source_canon_id:
    result = await db.execute("""
        MATCH (e:Entity)
        WHERE (toLower(e.name) = toLower($name) OR ...)
          AND (e.world_id = $world_id OR e.curated_world_id = $world_id)
        RETURN e.canon_id
    """, {"name": rel.source, "world_id": world_id})
    source_canon_id = result[0]["canon_id"] if result else None

# Skip if can't resolve
if not source_canon_id or not target_canon_id:
    logger.warning(f"Skipping relationship: could not resolve to canon_id")
    relationships_skipped += 1
    continue

# Create using canon_ids (world-safe)
await db.execute(f"""
    MATCH (a:Entity {{canon_id: $source_id}})
    MATCH (b:Entity {{canon_id: $target_id}})
    MERGE (a)-[r:`{rel_type}`]->(b)
    SET r.description = $description
""", {"source_id": source_canon_id, "target_id": target_canon_id, ...})
```

### 2. Admin API Endpoints (game_routes.py)

#### Promote Entities to Canon
**Endpoint:** `POST /api/game/admin/entities/promote`

Promotes session-created entities (e.g., NPCs created during gameplay) into canon.

**Request:**
```json
{
  "entity_ids": ["session123-chr-npc-0001", "session123-loc-tavern-0002"],
  "target_world_id": "my_world",
  "promote_relationships": true,
  "keep_session_entity": false
}
```

**Response:**
```json
{
  "success": true,
  "promoted_count": 2,
  "promoted_entities": [
    {
      "session_canon_id": "session123-chr-npc-0001",
      "new_canon_id": "my_world-chr-npc-0001",
      "name": "NPC the First",
      "entity_type": "Character"
    }
  ],
  "relationships_promoted": 1,
  "message": "Successfully promoted 2 entities to 'my_world'"
}
```

**Features:**
- Bulk promotion of multiple entities
- Optional relationship promotion (only promotes relationships between promoted entities)
- Tracks promotion metadata (`promoted_from_canon_id`, `origin_session_id`)
- Can keep or delete session entities
- Copies all properties (OCEAN personality, goals, secrets, fears, etc.)

#### Detect Cross-World Relationships
**Endpoint:** `GET /api/game/admin/relationships/cross-world?limit=100`

Detects existing cross-world relationships (damage from the bug).

**Response:**
```json
{
  "total_relationships": 1000,
  "cross_world_relationships": 5,
  "relationships": [
    {
      "rel_id": 12345,
      "rel_type": "KNOWS",
      "source_canon_id": "world1-chr-john-0001",
      "source_name": "John",
      "source_world_id": "world1",
      "target_canon_id": "world2-chr-jane-0002",
      "target_name": "Jane",
      "target_world_id": "world2"
    }
  ]
}
```

#### Cleanup Cross-World Relationships
**Endpoint:** `DELETE /api/game/admin/relationships/cross-world?dry_run=true`

Removes cross-world relationships.

**Dry Run Response:**
```json
{
  "dry_run": true,
  "would_delete": 5,
  "message": "Dry run complete. 5 cross-world relationships found. Set dry_run=false to delete."
}
```

**Actual Delete Response:**
```json
{
  "dry_run": false,
  "deleted": 5,
  "message": "Successfully deleted 5 cross-world relationships"
}
```

**Safety Features:**
- Dry run mode for preview
- Only deletes relationships spanning different worlds
- Preserves within-world relationships
- Can be run repeatedly safely

### 3. Security

All Cypher queries using f-string interpolation have been secured:
- **Entity labels**: Whitelist validation against `["Character", "Location", "Faction", "Item", "Event", "Concept"]`
- **Relationship types**: Regex validation `^[A-Z_a-z0-9]+$` (alphanumeric + underscore only)
- **Security comments**: Document validation approach in code
- **Fallback to safe defaults**: Use safe values when validation fails

### 4. Testing

Added comprehensive tests in `tests/test_cross_world_linking.py`:
- ✅ Test relationship creation doesn't link across worlds with same names
- ✅ Test canon_id mapping within ingestion scope
- ✅ Test entity promotion workflow
- ✅ Test OCEAN personality and relationship promotion
- ✅ Test cross-world relationship detection
- ✅ Test cross-world relationship cleanup (dry_run and actual)

## Usage

### For Admins: Cleanup Existing Damage

1. **Detect cross-world relationships:**
   ```bash
   GET /api/game/admin/relationships/cross-world
   ```

2. **Preview cleanup (dry run):**
   ```bash
   DELETE /api/game/admin/relationships/cross-world?dry_run=true
   ```

3. **Actually cleanup:**
   ```bash
   DELETE /api/game/admin/relationships/cross-world?dry_run=false
   ```

### For DMs: Promote Session Entities

When a DM creates entities during gameplay that should become canon:

1. **Note the session entity canon_ids**

2. **Promote to canon:**
   ```bash
   POST /api/game/admin/entities/promote
   {
     "entity_ids": ["session_chr_npc_001"],
     "target_world_id": "my_world",
     "promote_relationships": true,
     "keep_session_entity": false
   }
   ```

## Technical Details

### World Scoping

Two types of world identifiers are used:
- **`curated_world_id`**: Original curated world (e.g., "eldoria", "city_of_night")
- **`world_id`**: Session-scoped world (e.g., "eldoria_session123")

Relationships now respect both:
```cypher
WHERE (e.world_id = $scope OR e.curated_world_id = $scope)
```

### Relationship Resolution Priority

1. **Current ingestion scope** (entity_name_to_canon_id mapping)
   - Fastest, most accurate
   - Entities just created in this batch

2. **World-scoped database lookup** (fallback for existing entities)
   - Matches by name/alias within the same world
   - Prevents cross-world linking

3. **Skip with warning** (if resolution fails)
   - Better to skip than create wrong relationship
   - Logged with context for debugging

### Promotion Metadata

Canon entities promoted from sessions include:
- `promoted_from_canon_id`: Points to original session entity
- `origin_session_id`: Tracks which session created it
- `confidence_level`: Set to "ADMIN_PROMOTED"
- `approval_status`: Set to "APPROVED"

Session entities can optionally keep a link:
- `promoted_to_canon_id`: Points to canon entity
- `promoted_at`: Timestamp of promotion

## Backward Compatibility

- Existing entities unaffected
- Existing valid relationships preserved
- Only cross-world relationships are flagged/cleaned
- New ingestion uses safer canon_id matching
- Fallback to name matching still works for existing entities

## Performance

- Minimal performance impact: O(n) mapping lookup
- World-scoped queries use existing indexes
- Bulk promotion efficient for multiple entities

## Future Improvements

1. **Automatic promotion suggestions**: Detect high-value session entities for promotion
2. **Relationship review UI**: Admin interface to review/approve relationships
3. **World merge tool**: Safely merge two curated worlds with deduplication
4. **Lore consistency checker**: Detect contradictions across worlds

## References

- **Issue**: Cross-world entity linking during ingestion
- **Root Cause**: Name-based matching without world scoping
- **Fix PR**: #[PR_NUMBER]
- **Related**: Genre assessment PR #25
