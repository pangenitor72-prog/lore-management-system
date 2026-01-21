# Session Persistence and Save/Load Implementation

## Overview

This document describes the implementation of persistent game saves and session continuity for the Lore Management System, addressing the issue where users encountered "Session local-... not found" errors.

## Problem Statement

The user reported errors when sessions were not found, with the frontend generating fallback `local-*` session IDs. The system had basic save/load functionality but lacked proper:
- Session persistence across server restarts
- Character data restoration from saves
- Recovery mechanisms when sessions were cleared from memory
- Support for both anonymous (browser_id) and authenticated (user_id) saves

## Solution Architecture

### 1. Session Lifecycle

```
┌─────────────────┐
│  Session Create │
│  (POST /session)│
└────────┬────────┘
         │
         ├──────────────────┐
         │                  │
         v                  v
  ┌─────────────┐    ┌────────────────┐
  │ Memory      │    │ Neo4j          │
  │ _active_    │    │ :ActiveSession │
  │  sessions   │    │ :GameSession   │
  └─────────────┘    └────────────────┘
         │                  │
         v                  │
  ┌─────────────┐           │
  │ Player      │           │
  │  Action     │◄──────────┘
  └─────────────┘    (Recovery on miss)
         │
         v
  ┌─────────────┐
  │ Persist     │──────────► Neo4j
  │ to DB       │    (async task)
  └─────────────┘
         │
         v
  ┌─────────────┐
  │ Save Game   │──────────► :GameSave node
  │ (Manual)    │    (slots 1-10)
  └─────────────┘
```

### 2. Data Models

#### Neo4j Node Types

**ActiveSession Node** (Automatic persistence)
```cypher
(:ActiveSession {
  session_id: string,
  session_data: JSON string,  // Full session state
  updated_at: datetime,
  phase: string,
  character_concept: string,
  turn_count: integer
})
```

**GameSave Node** (Manual save slots)
```cypher
(:GameSave {
  // Scoping
  browser_id: string,  // Anonymous user scope
  user_id: string?,    // Optional authenticated user scope
  slot: integer,       // 1-10
  
  // Metadata
  session_id: string,
  session_name: string,
  character_concept: string,
  genre: string,
  phase: string,
  turn_count: integer,
  saved_at: datetime,
  world_name: string,
  character_id: string?,
  character_name: string?,
  rules_mode: string,
  session_status: string,
  
  // Full state
  save_data: JSON string  // Complete session data
})
```

**GameSession Node** (Analytics tracking)
```cypher
(:GameSession {
  session_id: string,
  world_id: string,
  session_world_id: string,
  phase: string,
  status: string,
  genre: string,
  character_name: string,
  tester: string,
  storytelling_style: string,
  is_curated_world: boolean,
  curated_world_name: string,
  turn_count: integer,
  created_at: datetime,
  last_activity: datetime
})
```

### 3. Key Functions

#### Session Persistence

**`_persist_session_to_db(session_id, session, db)`**
- Called automatically after each player action (async task)
- Serializes full session state including:
  - Basic metadata (phase, genre, etc.)
  - Conversation history
  - Character data (if present)
  - Arc Engine state
  - All datetime objects converted to ISO strings
- Stored in `:ActiveSession` node

**`_recover_session_from_db(session_id, db)`**
- Called when session not found in memory
- Deserializes session state from `:ActiveSession` node
- Restores:
  - Basic session data
  - Character objects to `_characters` dict
  - Arc Engine state
  - Converts ISO strings back to datetime objects

#### Save/Load Operations

**Save Game** (`POST /api/game/saves/{slot}`)
- Requires active session_id
- Stores complete snapshot in `:GameSave` node
- Supports both browser_id (anonymous) and user_id (authenticated) scoping
- Preserves character data for cross-restart persistence

**Load Game** (`GET /api/game/saves/{slot}/load`)
- Creates new session_id (not reusing old one)
- Two modes:
  - `continue`: Resume with full history
  - `new_chapter`: Summarized history, fresh arc
- Restores character data to `_characters` dict
- Returns session state to frontend

**List Saves** (`GET /api/game/saves`)
- Returns 10 slots (expandable on demand)
- Shows metadata: name, character, genre, turn count, etc.
- Properly scoped by browser_id or user_id

**Delete Save** (`DELETE /api/game/saves/{slot}`)
- Removes `:GameSave` node
- Scoped by browser_id or user_id

### 4. Frontend Changes

**Removed Local ID Fallbacks**
- Character creation: No longer generates `local-*` IDs
- Session creation: Throws error instead of fallback
- Load game: Uses server-provided session_id

**Error Handling**
- Shows user-friendly alerts when session creation fails
- Encourages retry or page refresh instead of silent fallback

### 5. Dual Scope Support

**Anonymous Users (browser_id)**
```javascript
// Frontend generates browser_id on first visit
const browserId = localStorage.getItem('browser_id') || generateBrowserId();

// Saves scoped to browser
POST /api/game/saves/1?session_id=...
{
  "browser_id": "browser-abc123",
  "slot": 1,
  ...
}
```

**Authenticated Users (user_id)**
```javascript
// After user logs in
const userId = auth.currentUser.id;

// Saves scoped to user account
POST /api/game/saves/1?session_id=...
{
  "browser_id": "browser-abc123",
  "user_id": "user-xyz789",  // Overrides browser scoping
  "slot": 1,
  ...
}
```

**Cypher Scope Logic**
```cypher
// List saves - anonymous
MATCH (s:GameSave {browser_id: $browser_id})
WHERE s.user_id IS NULL
RETURN s

// List saves - authenticated
MATCH (s:GameSave {user_id: $user_id})
RETURN s
```

### 6. Testing

**Test Coverage**
- `test_list_saves_empty`: Empty slots returned correctly
- `test_save_game_without_session`: Validation for missing sessions
- `test_save_and_load_game_flow`: End-to-end save/load cycle
- `test_session_recovery_from_db`: Recovery after memory clear
- `test_save_with_user_id`: Authenticated user saves
- `test_save_isolation_by_browser_id`: Browser isolation verification
- `test_delete_save`: Save deletion
- `test_load_with_new_chapter_mode`: New chapter mode
- `test_save_slot_validation`: Slot bounds validation

**Mock Database Extension**
- Extended `InMemoryMockDatabase` with:
  - `game_saves` dict for save slots
  - `active_sessions` dict for session persistence
  - `game_sessions` dict for analytics
  - Proper query pattern matching for MERGE, MATCH, DELETE

## API Reference

### Session Endpoints

**Create Session**
```
POST /api/game/session
Body: {
  "world_id": string?,
  "character_concept": string,
  "genre": string,
  "storytelling_style": "guided" | "freeform",
  "character_id": string?,
  "rules_mode": "narrative" | "dnd",
  "rules_visibility": "storyteller" | "guided" | "tactician"
}
Response: {
  "session_id": string,
  "status": "active",
  "phase": "session_0" | "active_play",
  "created_at": datetime,
  ...
}
```

**Get Session**
```
GET /api/game/session/{session_id}
Response: {
  "session_id": string,
  "status": string,
  "phase": string,
  ...
}
```

**Process Action**
```
POST /api/game/session/{session_id}/action
Body: {
  "action": string,
  "needs_guidance": boolean?,
  "adaptive_context": object?
}
Response: {
  "narrative": string,
  "session_id": string,
  "phase": string,
  "mechanical_result": object?,
  "suggested_actions": array?,
  ...
}
```

### Save/Load Endpoints

**List Saves**
```
GET /api/game/saves?browser_id={browser_id}&user_id={user_id}?
Response: [
  {
    "slot": 1,
    "is_empty": false,
    "session_name": "My Adventure",
    "character_concept": "Brave warrior",
    "genre": "fantasy",
    "phase": "active_play",
    "turn_count": 15,
    "saved_at": datetime,
    "world_name": "Test World",
    "character_id": string?,
    "character_name": string?,
    "rules_mode": "narrative",
    "session_status": "active",
    "suggested_mode": "continue"
  },
  ...
]
```

**Save Game**
```
POST /api/game/saves/{slot}?session_id={session_id}
Body: {
  "slot": 1,
  "session_name": "My Save",
  "browser_id": string,
  "user_id": string?,
  "inventory": array?
}
Response: {
  "success": true,
  "slot": 1,
  "session_id": string,
  "message": "Game saved to slot 1"
}
```

**Load Game**
```
GET /api/game/saves/{slot}/load?browser_id={browser_id}&mode={mode}&user_id={user_id}?
Query Params:
  - browser_id: string (required)
  - user_id: string (optional)
  - mode: "continue" | "new_chapter" (default: "continue")
Response: {
  "success": true,
  "session_id": string,  // New session ID
  "phase": string,
  "narrative": string,
  "message": string,
  "inventory": array,
  "character": object?,
  "continuation_mode": string,
  "session_summary": string?,
  "arc_context": object?,
  "turn_count": integer
}
```

**Delete Save**
```
DELETE /api/game/saves/{slot}?browser_id={browser_id}&user_id={user_id}?
Response: {
  "success": true,
  "message": "Save slot {slot} cleared"
}
```

## Logging

All save/load/recovery operations log at appropriate levels:

**Debug Level**
- Session persistence skipped (no DB)
- Character data persisted
- Session persisted with turn count

**Info Level**
- Session recovered from database
- Save created/loaded/deleted with scope
- Recovery attempts

**Error Level**
- Failed to persist session (with traceback)
- Failed to recover session (with traceback)
- Failed save/load/delete operations

## Migration Notes

**Backwards Compatibility**
- Existing code continues to work
- browser_id remains the default scoping mechanism
- user_id is optional and additive
- Frontend can adopt new session handling incrementally

**Database Migration**
No schema changes required:
- New node labels (`:ActiveSession`, `:GameSave`) are created on-demand
- Existing `:Session` nodes from old code coexist peacefully
- `:GameSession` nodes are created alongside for analytics

## Future Enhancements

1. **Session Expiry**: Add TTL to `:ActiveSession` nodes
2. **Save Slot Expansion**: Support more than 10 saves
3. **Cloud Saves**: Sync saves across devices for authenticated users
4. **Autosave**: Automatic save every N turns
5. **Save Thumbnails**: Screenshot or scene preview for each save
6. **Save Metadata**: More rich metadata (location, quest status, etc.)

## Conclusion

This implementation provides robust session persistence and save/load functionality with:
- ✅ Automatic session persistence across server restarts
- ✅ Manual save slots (1-10) with full state preservation
- ✅ Character data restoration
- ✅ Dual scope support (anonymous + authenticated)
- ✅ Recovery mechanisms for missing sessions
- ✅ Comprehensive error handling and logging
- ✅ Full test coverage (9/9 tests passing)
- ✅ Backwards compatible with existing code
