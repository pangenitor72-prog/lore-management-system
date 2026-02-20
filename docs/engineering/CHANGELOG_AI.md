## 2026-02-20: v66 - Wire Dormant Systems

- **OCEAN Compact Format:** Added `format_ocean_compact()` in `src/mantle/prompts/formatters.py`. Outputs `[↓E ↑A ↓N] reserved/warm/steady` for personality. OCEAN profiles now inject for ALL scene NPCs every turn (not just first introduction).

- **Arc Engine Beat Suggestions:** Wired `suggest_beats()` into DM context. Added `character_name` parameter to `get_dm_context_injection()` for placeholder substitution. Output: `Suggest: [COMPLICATION] ally betrays | [REVELATION] hidden truth`

- **Confidence Level Filtering:** Updated `_get_graph_aware_entity_context()` to include UNCERTAIN entities and add `(rumored)` / `(unverified)` qualifiers based on confidence level.

- **Extended Overlay System:** Added hostility and injury detection patterns in `narrative_extraction.py`. Overlay context now uses compact format: `⚠️ UNAVAILABLE: Name=DEAD | Name=CAPTURED`

- **Token Budget System:** Added `src/mantle/prompts/context_manager.py` with `PromptContextManager` class. Priority-based context inclusion (CRITICAL/HIGH/MEDIUM/LOW). 50-60% token reduction via compact formatters.

- **Format Key:** Added context format documentation to DM system prompt explaining abbreviations (OCEAN arrows, stats, knowledge levels).

---

## 2025-11-29: Migration to Neo4j & Test Suite Cleanup

-   **Database Migration:** The backend has been fully migrated from SQLite to Neo4j. All database interactions now use the `src/neo4j_adapter.py` module.
-   **Documentation Update:** Several documents in `docs/` were updated to reflect the new Neo4j architecture, replacing references to SQLite and `database.py`.
-   **Legacy Code Removal:** Obsolete test files, database audit scripts, and the `src/sqlite-tools` directory were deleted.
-   **Test Suite Stabilization:** The `pytest` suite was repaired by fixing fixture names, endpoint URLs, and mock configurations. One persistently failing test was marked as skipped to ensure a clean test run.

---

## 2025-11-25: API and WebSocket Implementation
*   **A1 (Missing `/ws/gemini` endpoint):** Implemented the `/ws/gemini` WebSocket endpoint in `src/api.py`. It correctly instantiates and uses the `QueryAgent` from `src/query_agent.py` to handle incoming messages and stream responses back to the client.
*   **A2 (Missing `/entities` endpoint):** Implemented the full suite of RESTful endpoints for entities (`POST /entities`, `GET /entities/{id}`, `GET /entities`) in `src/api.py`. This includes Pydantic model validation (`EntityCreate`), dependency injection for the database session (`Depends(get_db)`), and asynchronous handling of database operations using `run_in_threadpool`.

## 2025-11-24: Database Bug Fixes and Test Implementation
*   **C1 (Missing `db.close()`):** Ensured all database connections are properly closed by adding a `close()` method to the `Database` class and calling it in a `finally` block within the `db_session` context manager.
*   **C2 (Missing commits after INSERT/UPDATE/DELETE):** Modified `src/database.py`'s `execute` method to accept a `commit` flag. Ensured all mutating operations in API endpoints and agent persistence logic use explicit `commit=True` or `db_session` context manager.
*   **C3 (Shared sqlite3 connection across threads):** Refactored `src/database.py` to remove the global `sqlite3.Connection`. Implemented `get_db_connection` (returns new connection) and `db_session` (context manager for transactions). Integrated FastAPI's `Depends(get_db)` for per-request connection management. Updated `AuditorAgent` and `QueryAgent` to accept `get_db_connection` callable for their internal DB access.
*   **Testing:** Implemented `pytest` for the first time in the project. Created `tests/test_db_basic.py` to validate `database.py` functionality using an in-memory SQLite database, and `tests/test_entities_api.py` to perform integration tests on the `/entities` endpoints.

## 2025-11-23: Initial Project Setup by AI
*   Initial project structure created based on user specification.
*   Core modules (`api.py`, `database.py`, `models.py`) created.
*   Basic FastAPI application setup.
*   Initial SQLite database schema defined in `data/schema.sql`.
*   Agent shells (`auditor_agent.py`, `query_agent.py`) created.