# AI Changelog

This document logs significant actions and changes performed by AI collaborators within the Lore Management System (LMS) repository.

---

**Date:** 2025-11-20
**Branch:** `feature/lms-audit-alignment`
**Summary:**
*   **Audit Fixes Implemented:**
    *   **C1 (Blocking DB & LLM calls inside async endpoints):** Implemented `run_in_threadpool` for all blocking database and LLM calls in `async def` API endpoints (`src/api.py`, `src/contradiction_service.py`) and agent WebSocket handlers (`src/query_agent.py`).
    *   **C2 (Missing commits after INSERT/UPDATE/DELETE):** Modified `src/database.py`'s `execute` method to accept a `commit` flag. Ensured all mutating operations in API endpoints and agent persistence logic use explicit `commit=True` or `db_session` context manager.
    *   **C3 (Shared sqlite3 connection across threads):** Refactored `src/database.py` to remove the global `sqlite3.Connection`. Implemented `get_db_connection` (returns new connection) and `db_session` (context manager for transactions). Integrated FastAPI's `Depends(get_db)` for per-request connection management. Updated `AuditorAgent` and `QueryAgent` to accept `get_db_connection` callable for their internal DB access.
    *   **C4 (Enum misuse when generating IDs):** Corrected `entity_data.entity_type.lower()` to `entity_data.entity_type.value.lower()` in `src/api.py`.
    *   **C5 & M8 (JSON fields stored/returned inconsistently & Type consistency):** Standardized JSON handling. `approved_fields` and `evidence` fields in `src/models.py` are now typed as `Dict[str, Any]`. Ensured `json.loads()` is applied on retrieval from DB for these fields in API responses.
    *   **M1 (Duplicated/inconsistent Pydantic models & Enums):** Consolidated and standardized all Pydantic models and Enums in `src/models.py`. Removed redundant constants from `src/constants.py`.
    *   **M3 (Enum/string conversion in responses):** Ensured explicit conversion of database string values to Enum types in Pydantic model construction where necessary (`src/api.py`, `src/contradiction_service.py`).
    *   **M4 (N+1 query patterns):** Refactored `list_entities` in `src/api.py` and `list_contradictions`, `get_next_pending_contradiction`, `get_contradiction_details` in `src/contradiction_service.py` to use optimized SQL JOINs or batched queries.
    *   **M5 (Unprotected debug or reset endpoints):** Added environment variable checks (`os.getenv("ENV") == "development"`) to guard `/debug/*` endpoints in `src/api.py` and `src/contradiction_service.py`.
    *   **M6 (Logging & error handling):** Configured central Python logging in `src/__init__.py` via `src/utils/logging_config.py`. Replaced all `print()` statements with `logger.info()`, `logger.error()`, `logger.warning()`, and `logger.debug()`. Enhanced error handling with `logger.exception()`.
    *   **M7 (Template/static path consistency):** Verified and standardized template/static file paths in `src/api.py` and `src/contradiction_service.py` using `Path(__file__).resolve().parent.parent`.

*   **Tests Added:**
    *   `tests/test_db_basic.py`: Basic connectivity, schema initialization, entity insert/fetch.
    *   `tests/test_entities_api.py`: CRUD operations for entity API endpoints.
    *   `tests/test_contradictions_api.py`: CRUD and status update operations for contradiction API endpoints.

*   **Docs Created:**
    *   `docs/engineering/PROJECT_CONVENTIONS.md`
    *   `docs/engineering/REPO_RULES.md`
    *   `docs/engineering/MASTER_AGENT_GUIDE.md` (this document)
    *   `docs/engineering/CHANGELOG_AI.md`
    *   `docs/engineering/ARCHITECTURE_OVERVIEW.md` (pending content)
    *   `docs/engineering/DB_SCHEMA.md` (pending content)
    *   `docs/engineering/MIGRATION_GUIDE.md` (pending content)
    *   `docs/engineering/TASKS_TODO.md` (pending content)
    *   `docs/engineering/TESTING_GUIDE.md` (pending content)
    *   `docs/engineering/GLOSSARY.md` (pending content)
