# LMS API Contract
**Complete API endpoint documentation with real request/response examples**

**Base URL:** `http://localhost:8000`

**Last Verified:** 2025-11-25 (All 22 endpoint tests passing)

**Test Status:** ✅ Production-ready (100% system health, 0% error rate)

---

## Table of Contents
1. [Root Endpoints](#root-endpoints)
2. [Entity Endpoints](#entity-endpoints)
3. [Contradiction Endpoints](#contradiction-endpoints)
4. [Dashboard Endpoints](#dashboard-endpoints)
5. [WebSocket Endpoints](#websocket-endpoints)
6. [Common Response Codes](#common-response-codes)
7. [Data Models](#data-models)

---

## Root Endpoints

### GET /
**Description:** Root endpoint, health check

**Request:** None

**Response (200):**
```json
{
  "message": "Lore Management System API",
  "version": "1.0.0",
  "status": "operational"
}
```

---

## Entity Endpoints

### POST /entities
**Description:** Create a new lore entity

**Request Body:**
```json
{
  "entity_type": "Character",
  "canonical_name": "The Black King",
  "aliases": ["Shadow King", "The King in Black"],
  "approved_fields": {
    "title": "Ruler of the Shadow Realm",
    "description": "A mysterious figure who rules from darkness."
  },
  "confidence_level": "CONFIRMED",
  "party_knowledge": "KNOWN"
}
```

**Response (201):**
```json
{
  "canon_id": "character-a3f9bc21",
  "entity_type": "Character",
  "canonical_name": "The Black King",
  "aliases": ["Shadow King", "The King in Black"],
  "approved_fields": {
    "title": "Ruler of the Shadow Realm",
    "description": "A mysterious figure who rules from darkness."
  },
  "approval_status": "PENDING",
  "confidence_level": "CONFIRMED",
  "party_knowledge": "KNOWN",
  "created_at": "2025-11-25T14:30:00+00:00",
  "updated_at": "2025-11-25T14:30:00+00:00"
}
```

**Errors:**
- `422` - Invalid enum value (entity_type, confidence_level, party_knowledge)
- `500` - Database error

**Valid Enum Values:**
- `entity_type`: `Character`, `Location`, `Faction`, `Event`, `Item`, `Concept`
- `confidence_level`: `CONFIRMED`, `PROBABLE`, `SPECULATIVE`, `UNCERTAIN`
- `party_knowledge`: `KNOWN`, `RUMORED`, `SECRET`, `FORGOTTEN`

---

### GET /entities/{canon_id}
**Description:** Get a single entity by canon_id

**Path Parameters:**
- `canon_id` (string, required) - Entity's canonical identifier (e.g., "character-a3f9bc21")

**Request:** None

**Response (200):**
```json
{
  "canon_id": "character-a3f9bc21",
  "entity_type": "Character",
  "canonical_name": "The Black King",
  "aliases": ["Shadow King", "The King in Black"],
  "approved_fields": {
    "title": "Ruler of the Shadow Realm",
    "description": "A mysterious figure who rules from darkness."
  },
  "approval_status": "PENDING",
  "confidence_level": "CONFIRMED",
  "party_knowledge": "KNOWN",
  "created_at": "2025-11-25T14:30:00+00:00",
  "updated_at": "2025-11-25T14:30:00+00:00"
}
```

**Errors:**
- `404` - Entity not found

---

### GET /entities
**Description:** List all entities with optional filters

**Query Parameters:**
- `entity_type` (string, optional) - Filter by entity type
- `approval_status` (string, optional) - Filter by approval status
- `limit` (integer, optional, default=100) - Maximum results to return

**Request:** None

**Response (200):**
```json
[
  {
    "canon_id": "character-a3f9bc21",
    "entity_type": "Character",
    "canonical_name": "The Black King",
    "aliases": ["Shadow King"],
    "approved_fields": {...},
    "approval_status": "PENDING",
    "confidence_level": "CONFIRMED",
    "party_knowledge": "KNOWN",
    "created_at": "2025-11-25T14:30:00+00:00",
    "updated_at": "2025-11-25T14:30:00+00:00"
  },
  ...
]
```

**Example Requests:**
```
GET /entities?entity_type=Character&limit=50
GET /entities?approval_status=APPROVED
GET /entities?entity_type=Location&approval_status=PENDING
```

---

### GET /entities/browser
**Description:** HTML page for browsing entities (UI endpoint)

**Query Parameters:**
- `canon_id` (string, optional) - If provided, shows entity detail view

**Request:** None

**Response (200):** HTML page

---

## Contradiction Endpoints

### POST /api/contradictions
**Description:** Create a new contradiction (typically called by Auditor Agent)

**Request Body:**
```json
{
  "contradiction_id": "c3f9bc21-a8d7-4e2f-9b1c-8d7e3f9bc210",
  "contradiction_type": "Temporal Discrepancy",
  "source_id": "auditor-agent",
  "contradiction_text": "Conflicting dates for siege",
  "description": "Session 47 says Year 302, old notes say Year 304",
  "evidence": {
    "source_1": "session_47.txt - 'siege began 302'",
    "source_2": "old_notes.txt - 'siege started 304'"
  },
  "severity": "HIGH",
  "entities_involved": [
    {
      "canon_id": "event-siege-shadow",
      "canonical_name": "Shadow Realm Siege",
      "entity_type": "Event"
    }
  ],
  "detected_at": "2025-11-25T14:30:00+00:00"
}
```

**Response (201):**
```json
{
  "id": 42,
  "contradiction_id": "c3f9bc21-a8d7-4e2f-9b1c-8d7e3f9bc210",
  "contradiction_type": "Temporal Discrepancy",
  "severity": "HIGH",
  "description": "Session 47 says Year 302, old notes say Year 304",
  "evidence": {
    "source_1": "session_47.txt - 'siege began 302'",
    "source_2": "old_notes.txt - 'siege started 304'"
  },
  "detected_at": "2025-11-25T14:30:00+00:00",
  "status": "PENDING",
  "created_at": "2025-11-25T14:30:00+00:00",
  "entity_ids": ["event-siege-shadow"]
}
```

**Errors:**
- `409` - Contradiction ID already exists
- `422` - Invalid severity value
- `500` - Database error

**Valid Severity Values:** `HIGH`, `MEDIUM`, `LOW`

---

### GET /api/contradictions
**Description:** List contradictions with optional filters

**Query Parameters:**
- `status` (string, optional) - Filter by status
- `severity` (string, optional) - Filter by severity
- `limit` (integer, optional, default=50) - Maximum results

**Request:** None

**Response (200):**
```json
[
  {
    "id": 42,
    "contradiction_id": "c3f9bc21-...",
    "contradiction_type": "Temporal Discrepancy",
    "severity": "HIGH",
    "description": "Conflicting dates",
    "evidence": {...},
    "detected_at": "2025-11-25T14:30:00+00:00",
    "status": "PENDING",
    "created_at": "2025-11-25T14:30:00+00:00",
    "entity_ids": ["event-siege-shadow"]
  },
  ...
]
```

**Valid Status Values:** `PENDING`, `IN_REVIEW`, `RESOLVED`, `DISMISSED`

---

### GET /api/contradictions/queue/next
**Description:** Get next pending contradiction ordered by severity (HIGH first)

**Request:** None

**Response (200):**
```json
{
  "contradiction": {
    "id": 42,
    "contradiction_id": "c3f9bc21-...",
    "contradiction_type": "Temporal Discrepancy",
    "severity": "HIGH",
    "description": "Conflicting dates",
    "evidence": {...},
    "detected_at": "2025-11-25T14:30:00+00:00",
    "status": "PENDING",
    "created_at": "2025-11-25T14:30:00+00:00",
    "entity_ids": ["event-siege-shadow"]
  },
  "analysis": null
}
```

**Errors:**
- `404` - Queue is empty (no pending contradictions)

---

### GET /api/contradictions/{contradiction_id}
**Description:** Get single contradiction with full details and analysis

**Path Parameters:**
- `contradiction_id` (string, required) - UUID of contradiction

**Request:** None

**Response (200):**
```json
{
  "contradiction": {
    "id": 42,
    "contradiction_id": "c3f9bc21-...",
    "contradiction_type": "Temporal Discrepancy",
    "severity": "HIGH",
    "description": "Conflicting dates",
    "evidence": {...},
    "detected_at": "2025-11-25T14:30:00+00:00",
    "status": "IN_REVIEW",
    "created_at": "2025-11-25T14:30:00+00:00",
    "entity_ids": ["event-siege-shadow"]
  },
  "analysis": {
    "id": 12,
    "contradiction_id": "c3f9bc21-...",
    "analyst": "CLAUDE",
    "analysis": "Both sources are credible. Session 47 is more recent.",
    "recommendation": "Trust session 47 date (302)",
    "confidence": "HIGH",
    "analyzed_at": "2025-11-25T14:35:00+00:00"
  }
}
```

**Errors:**
- `404` - Contradiction not found

---

### POST /api/contradictions/{contradiction_id}/resolve
**Description:** Mark contradiction as RESOLVED (Gospel Principle: human decision)

**Path Parameters:**
- `contradiction_id` (string, required)

**Request Body:**
```json
{
  "user": "Jim King",
  "notes": "Confirmed Year 302 with original session notes"
}
```

**Response (200):**
```json
{
  "id": 42,
  "contradiction_id": "c3f9bc21-...",
  "contradiction_type": "Temporal Discrepancy",
  "severity": "HIGH",
  "description": "Conflicting dates",
  "evidence": {...},
  "detected_at": "2025-11-25T14:30:00+00:00",
  "status": "RESOLVED",
  "created_at": "2025-11-25T14:30:00+00:00",
  "entity_ids": ["event-siege-shadow"]
}
```

**Errors:**
- `404` - Contradiction not found

---

### POST /api/contradictions/{contradiction_id}/dismiss
**Description:** Mark contradiction as DISMISSED (not a real issue)

**Path Parameters:**
- `contradiction_id` (string, required)

**Request Body:**
```json
{
  "user": "Jim King",
  "notes": "Not actually contradictory - different sieges"
}
```

**Response (200):** Same as resolve endpoint, with `status: "DISMISSED"`

**Errors:**
- `404` - Contradiction not found

---

### POST /api/contradictions/{contradiction_id}/review
**Description:** Mark contradiction as IN_REVIEW

**Path Parameters:**
- `contradiction_id` (string, required)

**Request Body:** `{}` (empty object)

**Response (200):** Same as resolve endpoint, with `status: "IN_REVIEW"`

**Errors:**
- `404` - Contradiction not found

---

### POST /api/contradictions/{contradiction_id}/analysis
**Description:** Add AI triage analysis and update status to IN_REVIEW

**Path Parameters:**
- `contradiction_id` (string, required)

**Request Body:**
```json
{
  "contradiction_id": "c3f9bc21-...",
  "analysis": "Both sources credible. Session 47 more recent and detailed.",
  "recommendation": "Accept Year 302 as canonical, update entity timeline.",
  "confidence": "HIGH"
}
```

**Response (201):**
```json
{
  "id": 12,
  "contradiction_id": "c3f9bc21-...",
  "analyst": "CLAUDE",
  "analysis": "Both sources credible. Session 47 more recent and detailed.",
  "recommendation": "Accept Year 302 as canonical, update entity timeline.",
  "confidence": "HIGH",
  "analyzed_at": "2025-11-25T14:35:00+00:00"
}
```

**Errors:**
- `404` - Contradiction not found
- `409` - Analysis already exists for this contradiction

---

## Dashboard Endpoints

### GET /dashboard
**Description:** HTML dashboard page (UI endpoint)

**Request:** None

**Response (200):** HTML page with contradiction analytics

---

### GET /contradictions
**Description:** Mock data endpoint for dashboard UI testing

**Request:** None

**Response (200):**
```json
[
  {
    "id": 101,
    "title": "Timeline Fracture: The Black King",
    "description": "Player claimed to kill the Black King in Year 298...",
    "severity": "CRITICAL",
    "source": "Session 42 Log"
  },
  ...
]
```

**Note:** This returns mock data for UI development. Use `/api/contradictions` for real data.

---

### GET /api/dashboard
**Description:** Dashboard statistics and metrics

**Request:** None

**Response (200):**
```json
{
  "total_entities": 347,
  "confirmed_entities": 289,
  "pending_contradictions": 12,
  "resolved_contradictions": 45,
  "system_health": 100
}
```

---

### GET /api/api/contradiction-snapshot
**Description:** Latest contradiction confidence scores for live chart

**Request:** None

**Response (200):**
```json
{
  "labels": [
    "2025-11-25T10:00:00Z",
    "2025-11-25T11:00:00Z",
    "2025-11-25T12:00:00Z"
  ],
  "scores": [0.85, 0.92, 0.78]
}
```

---

## WebSocket Endpoints

### WS /ws/auditor
**Description:** WebSocket for real-time auditor events

**Protocol:** WebSocket

**Connection:** 
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/auditor');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Auditor event:', message);
};
```

**Events Received:**
```json
{
  "type": "contradiction_detected",
  "contradiction_id": "c3f9bc21-...",
  "severity": "HIGH",
  "description": "..."
}
```

**Note:** Broadcasts contradiction detection and analysis events to connected clients.

---

## Debug Endpoints (Development Only)

### GET /api/debug/seed-contradictions
### POST /api/debug/seed-contradictions
**Description:** Insert test contradictions for UI development

**Environment:** Development only (ENV=development)

**Response (403):** 
```json
{
  "detail": "This is a debug endpoint, only available in development environment."
}
```

**Response (200) in development:**
```json
{
  "status": "ok",
  "message": "Inserted 10 test contradictions"
}
```

---

## Common Response Codes

### Success Codes
- `200 OK` - Request succeeded
- `201 Created` - Resource created successfully

### Client Error Codes
- `400 Bad Request` - Invalid request format
- `404 Not Found` - Resource doesn't exist
- `409 Conflict` - Resource already exists (duplicate)
- `422 Unprocessable Entity` - Invalid enum value or field validation failure

### Server Error Codes
- `500 Internal Server Error` - Unexpected server error (check logs)

### Error Response Format
```json
{
  "detail": "Specific error message describing what went wrong"
}
```

---

## Data Models

### EntityType Enum
- `Character`
- `Location`
- `Faction`
- `Event`
- `Item`
- `Concept`

### ApprovalStatus Enum
- `APPROVED`
- `PENDING`
- `REJECTED`

### ConfidenceLevel Enum
- `CONFIRMED` - Verified by primary source
- `PROBABLE` - Likely true based on evidence
- `SPECULATIVE` - Possible but uncertain
- `UNCERTAIN` - Contradictory or weak evidence

### PartyKnowledge Enum
- `KNOWN` - Party has learned this information
- `RUMORED` - Party has heard rumors
- `SECRET` - Information exists but party doesn't know
- `FORGOTTEN` - Previously known but lost/forgotten

### ContradictionSeverity Enum
- `HIGH` - Critical inconsistency affecting major lore
- `MEDIUM` - Notable inconsistency, should be resolved
- `LOW` - Minor discrepancy, low priority

### ContradictionStatus Enum
- `PENDING` - Awaiting review
- `IN_REVIEW` - Being analyzed
- `RESOLVED` - Human decision made, contradiction closed
- `DISMISSED` - Determined not to be a real contradiction

---

## Authentication

Currently: No authentication required (single-user system)

Future: When multi-user features added, will use Bearer token authentication.

---

## Rate Limiting

Currently: No rate limits

Production: Consider implementing rate limits for API endpoints if exposed publicly.

---

## CORS Configuration

Currently: All origins allowed (`allow_origins=["*"]`)

**Headers allowed:** All
**Methods allowed:** All
**Credentials:** Enabled

**Production:** Restrict `allow_origins` to specific domains.

---

## Testing This Contract

Run the integration test suite to verify all endpoints:

```bash
python test_api_integration.py
```

Expected output: `22/22 tests passed`

---

**Last Updated:** 2025-11-25  
**Verified Against:** LMS v1.0.0 (Phases I-XI complete, Phase XII in progress)  
**Test Coverage:** 22 endpoints, 100% passing
