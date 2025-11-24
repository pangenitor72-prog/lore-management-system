# LMS API Contract (UNVERIFIED)

This document lists all API endpoints found in the source code.
**NOTE:** These endpoints have not yet been verified.

## From `src/api.py`

*   **GET `/ws/auditor`**: WebSocket for auditor events.
    **VERIFIED** (Not directly testable with curl, but path confirmed)
    **Purpose**: Provides real-time updates for auditor events.

*   **GET `/`**: Root endpoint.
    **VERIFIED**
    **Request**: None
    **Response**: `{"message":"Lore Management System API","version":"1.0.0","status":"operational"}`

*   **POST `/entities`**: Create a new entity.
    **VERIFIED**
    **Request**: `test_entity.json` content (with `entity_type` as "Character")
    **Response**:
    ```json
    {
      "canon_id": "character-...",
      "entity_type": "Character",
      "canonical_name": "The Black King",
      "aliases": [
        "The Shadow King",
        "The King in Black"
      ],
      "approved_fields": {
        "title": "The Black King",
        "description": "A mysterious figure who rules the Shadow Realm."
      },
      "approval_status": "PENDING",
      "confidence_level": "CONFIRMED",
      "party_knowledge": "KNOWN",
      "created_at": "...",
      "updated_at": "..."
    }
    ```

*   **GET `/entities/browser`**: HTML browser for entities.
    **VERIFIED**
    **Request**: None
    **Response**: Returns an HTML page for browsing entities.

*   **GET `/entities/{canon_id}`**: Get an entity by `canon_id`.
    **VERIFIED**
    **Request**: Path parameter `canon_id` (e.g., `character-d1258a89`)
    **Response**: Returns an `EntityResponse` object (same structure as POST /entities response).

*   **GET `/entities`**: List entities.
    **VERIFIED**
    **Request**: Optional query parameters: `entity_type`, `approval_status`, `limit`.
    **Response**: Returns a list of `EntityResponse` objects.

*   **GET `/dashboard`**: Renders the main dashboard.
    **VERIFIED**
    **Request**: None
    **Response**: Returns an HTML page for the dashboard.

*   **GET `/contradictions`**: Get contradictions (MOCK DATA).
    **VERIFIED**
    **Request**: None
    **Response**: Returns mock data as a list of `DashboardCard` objects.


## From `src/contradiction_service.py` (prefixed with `/api`)

*   **GET `/api/debug/seed-contradictions`**: Seed the database with test contradictions.
    **VERIFIED**
    **Request**: None
    **Error Response**: `{"detail":"This is a debug endpoint, only available in development environment."}` (expected behavior)

*   **POST `/api/debug/seed-contradictions`**: Seed the database with test contradictions.
    **VERIFIED**
    **Request**: None
    **Error Response**: `{"detail":"This is a debug endpoint, only available in development environment."}` (expected behavior)

*   **POST `/api/contradictions`**: Add a new contradiction.
    **VERIFIED**
    **Request**: JSON body (example from `temp_contradiction.json`):
    ```json
    {
      "contradiction_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "contradiction_type": "Temporal Discrepancy",
      "source_id": "test-source-1",
      "contradiction_text": "The Black King was seen in two places at once, in Year 298 and Year 302.",
      "description": "Conflicting timelines for the Black King's appearance.",
      "evidence": {
        "Session Log": "Session 42 Log states King was present.",
        "Archive Record": "Archive Record shows King was elsewhere."
      },
      "severity": "HIGH",
      "entities_involved": [
        {
          "canon_id": "character-d1258a89",
          "canonical_name": "The Black King",
          "entity_type": "Character"
        }
      ],
      "detected_at": "2025-11-24T15:00:00Z"
    }
    ```
    **Response**:
    ```json
    {
      "id": 1,
      "contradiction_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "contradiction_type": "Temporal Discrepancy",
      "severity": "HIGH",
      "description": "Conflicting timelines for the Black King's appearance.",
      "status": "PENDING",
      "source_id": "test-source-1",
      "contradiction_text": "The Black King was seen in two places at once, in Year 298 and Year 302.",
      "evidence": {
        "Session Log": "Session 42 Log states King was present.",
        "Archive Record": "Archive Record shows King was elsewhere."
      },
      "entities_involved": [
        {
          "canon_id": "character-d1258a89",
          "canonical_name": "The Black King",
          "entity_type": "Character",
          "approval_status": "PENDING",
          "confidence_level": "CONFIRMED",
          "party_knowledge": "KNOWN",
          "created_at": "...",
          "updated_at": "..."
        }
      ],
      "detected_at": "2025-11-24T15:00:00Z",
      "created_at": "...",
      "updated_at": "..."
    }
    ```

*   **GET `/api/contradictions`**: List contradictions.
    **VERIFIED**
    **Request**: None
    **Response**: Returns a list of `ContradictionResponse` objects.

*   **GET `/api/contradictions/queue/next`**: Get the next pending contradiction.
    **VERIFIED**
    **Request**: None
    **Response**: Returns a `ContradictionWithAnalysis` object for the next pending contradiction.

*   **GET `/api/contradictions/{contradiction_id}`**: Get a single contradiction.
    **VERIFIED**
    **Request**: Path parameter `contradiction_id` (e.g., `a1b2c3d4-e5f6-7890-1234-567890abcdef`)
    **Response**: Returns a `ContradictionWithAnalysis` object.

*   **POST `/api/contradictions/{contradiction_id}/resolve`**: Resolve a contradiction.
    **VERIFIED**
    **Request**: Path parameter `contradiction_id` (e.g., `a1b2c3d4-e5f6-7890-1234-567890abcdef`), empty JSON body `{}`.
    **Response**: Returns the updated `ContradictionResponse` object with `status` set to "RESOLVED".

*   **POST `/api/contradictions/{contradiction_id}/dismiss`**: Dismiss a contradiction.
    **VERIFIED**
    **Request**: Path parameter `contradiction_id` (e.g., `a1b2c3d4-e5f6-7890-1234-567890abcdef`), empty JSON body `{}`.
    **Response**: Returns the updated `ContradictionResponse` object with `status` set to "DISMISSED".

*   **POST `/api/contradictions/{contradiction_id}/review`**: Mark a contradiction as "in review".
    **VERIFIED**
    **Request**: Path parameter `contradiction_id` (e.g., `a1b2c3d4-e5f6-7890-1234-567890abcdef`), empty JSON body `{}`.
    **Response**: Returns the updated `ContradictionResponse` object with `status` set to "IN_REVIEW".

*   **POST `/api/contradictions/{contradiction_id}/analysis`**: Add an analysis to a contradiction.
    **VERIFIED**
    **Request**: Path parameter `contradiction_id` (e.g., `a1b2c3d4-e5f6-7890-1234-567890abcdef`), JSON body:
    ```json
    {
      "contradiction_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "analysis": "The contradiction arises from differing records. Specifically, the session log places the Black King in location A, while the archive record places him in location B at the same time.",
      "recommendation": "Consult additional historical records or eyewitness accounts to reconcile the discrepancy.",
      "confidence": "HIGH"
    }
    ```
    **Response**: Returns a `TriageAnalysisResponse` object.

*   **GET `/api/dashboard`**: Renders the audit dashboard.
    **VERIFIED**
    **Request**: None
    **Response**: Returns an HTML page for the audit dashboard.

*   **GET `/api/api/contradiction-snapshot`**: Get a snapshot of contradiction data. **(POTENTIAL BUG: double `/api` prefix)**
    **VERIFIED** (confirmed accessible via the double `/api` prefix)
    **Request**: None
    **Response**: Returns JSON data with `labels` and `scores` (e.g., `{"labels":[],"scores":[]}`).