# Entity Manager Embedded in World Manager

## Overview

This document describes the Entity Manager that has been embedded directly into each world within the World Manager section of the admin panel.

## Changes Made

### 1. Backend Error Handling Improvements

**File:** `src/lms/api/game_routes.py`

Enhanced the `/api/game/lore-bases/{lore_id}/entities` endpoint with:
- Added debug logging for query execution
- Better error handling with specific exception types
- Graceful handling of malformed entity records
- More informative error messages
- Re-raises HTTP exceptions correctly

### 2. Frontend: Embedded Entity Manager

**File:** `frontend/dist/index.html`

Replaced the old source-based entity view with a full-featured Entity Manager embedded in each world card.

#### Key Features:

**Entity Display:**
- Entities are now grouped by TYPE (Character, Location, Faction, etc.) instead of source
- Each entity type group is collapsible
- Entity cards show: name, type badge, description, source, and confidence level
- Click entity card to expand and see full details (ID, type, created date)

**Selection & Bulk Operations:**
- Checkbox on each entity card for multi-select
- "Select All" / "Deselect All" buttons
- Selected count displayed in header
- Selected entities highlighted with gold border
- Selection state tracked per world

**Filtering:**
- Dropdown filter to show only specific entity types
- Filter is applied to display without losing selection state

**Edit Functionality:**
- Pencil icon (✏️) button on each entity
- Click to edit entity name inline
- Uses PATCH `/entities/{canon_id}` endpoint
- Shows status feedback on success/error

**Merge Functionality:**
- "Merge Selected" button appears when 2+ entities of SAME TYPE are selected
- Prevents merging entities of different types
- Shows list of entities being merged
- Prompts for canonical name for merged entity
- Uses POST `/game/entities/merge` endpoint
- Merges descriptions, aliases, and traits
- Automatically refreshes after merge

**Bulk Delete:**
- "Delete Selected" button appears when any entities are selected
- Shows count of entities to be deleted
- Confirmation dialog with count
- Uses DELETE `/entities/bulk` endpoint
- Clears selection after successful delete
- Automatically refreshes world data

## UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ World Name  [Edit] world_id           [Entity Count Badge]      │
│ Description                                                      │
│ [Genre Tags] [Edit]                                              │
│                                                                   │
│ ▼ Expanded Content:                                              │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │ 📋 Entity Manager                    [Type Filter ▼]      │ │
│   │ 150 entities | 3 selected    [✓ Select All] [Deselect]   │ │
│   │                           [🔗 Merge (3)] [🗑️ Delete (3)]  │ │
│   ├───────────────────────────────────────────────────────────┤ │
│   │ ▶ Character (45 entities)                                 │ │
│   │   ☐ Aldric the Wise [Character]                          │ │
│   │      A veteran mage with knowledge of...                  │ │
│   │      Source: eldoria_main.txt                       ✏️ ✕  │ │
│   │                                                            │ │
│   │   ☑ Lyra Moonwhisper [Character]                         │ │
│   │      Elven ranger with a mysterious past...               │ │
│   │      Source: eldoria_characters.txt                 ✏️ ✕  │ │
│   │                                                            │ │
│   │ ▶ Location (38 entities)                                  │ │
│   │ ▶ Faction (12 entities)                                   │ │
│   │ ▶ Item (25 entities)                                      │ │
│   │ ▶ Event (18 entities)                                     │ │
│   │ ▶ Concept (12 entities)                                   │ │
│   └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Technical Implementation

### Selection State Management

```javascript
// Track selected entities per world
let selectedEntities = {}; // { worldId: Set<entityId> }
```

### Key Functions Added

1. **`toggleEntitySelection(worldId, entityId)`** - Toggle entity checkbox
2. **`selectAllEntities(worldId)`** - Select all visible entities (respects filter)
3. **`deselectAllEntities(worldId)`** - Clear all selections
4. **`filterEntitiesByType(worldId)`** - Filter display by entity type
5. **`toggleEntityDetails(worldId, entityId)`** - Expand/collapse entity details
6. **`editEntityInline(worldId, entityId)`** - Edit entity name
7. **`bulkDeleteEntities(worldId)`** - Delete all selected entities
8. **`openMergeModal(worldId)`** - Merge selected entities (2 at a time)
9. **`toggleTypeExpand(worldId, typeId)`** - Expand/collapse type groups

### API Endpoints Used

- **GET** `/api/game/lore-bases/{lore_id}/entities` - Load entities for world
- **PATCH** `/entities/{canon_id}` - Update entity properties
- **POST** `/game/entities/merge` - Merge two entities
- **DELETE** `/entities/bulk` - Bulk delete entities

## User Workflow Examples

### Merging Duplicate Entities

1. Expand a world in World Manager
2. Use type filter to show only "Character" entities
3. Select 2+ characters that are duplicates (e.g., "Jon Snow" and "John Snow")
4. Click "Merge Selected" button
5. Enter canonical name in prompt
6. System merges entities, combines aliases and descriptions
7. View refreshes automatically

### Bulk Deleting Test Entities

1. Expand a world
2. Click "Select All" to select all entities
3. Click "Delete Selected" button
4. Confirm deletion
5. All entities removed from database
6. View refreshes

### Editing Entity Names

1. Find entity in list
2. Click pencil icon (✏️)
3. Enter new name in prompt
4. Entity name updated in database
5. View refreshes

## Testing Notes

- Tested with mock data structure
- Error handling verified for failed API calls
- Selection state properly isolated per world
- Type filtering works with selection state
- Merge validation prevents merging different types
- Bulk delete includes confirmation dialog

## Future Enhancements

- More sophisticated entity editor (modal with all fields)
- Merge preview showing what will be combined
- Undo functionality for merges and deletes
- Export/import entity data
- Entity relationship visualization
- Advanced filtering (by source, confidence, date range)
- Keyboard shortcuts for common operations
