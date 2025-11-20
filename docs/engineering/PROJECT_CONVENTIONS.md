# Project Conventions

This document outlines the conventions and best practices for developing within the Lore Management System (LMS) repository. Adhering to these guidelines ensures consistency, maintainability, and facilitates collaboration.

## 1. Folder Structure and Responsibilities

- **`/` (Project Root):** Contains top-level configuration files (`pytest.ini`, `README.md`, `.gitignore`), and entry points (`run.py`, `ai_service.py`).
- **`/data`:** Database schema (`schema.sql`) and potentially other data files.
- **`/docs`:** Project documentation.
    - **`/docs/audit`:** Reports and findings from system audits.
    - **`/docs/engineering`:** Engineering-specific documentation (this suite).
    - **`/docs/lms`:** General LMS-related documentation.
- **`/src`:** Core application source code.
    - **`/src/api.py`:** Main FastAPI application entry point, API router definitions, and endpoint implementations.
    - **`/src/auditor_agent.py`:** Logic for the Auditor Agent (contradiction detection, rule-based audits).
    - **`/src/contradiction_service.py`:** Endpoints and logic related to contradiction management (triage, status updates).
    - **`/src/database.py`:** Database connection management, schema initialization, and core CRUD operations.
    - **`/src/models.py`:** Pydantic models for data validation and serialization/deserialization, and Python Enums.
    - **`/src/query_agent.py`:** Logic for the Query Agent (AI-powered lore querying).
    - **`/src/utils`:** General utility functions (e.g., logging configuration).
    - **`/src/static`:** Static files (CSS, JS) for frontend components.
    - **`/src/templates`:** Jinja2 HTML templates for UI rendering.
- **`/tests`:** Unit and integration tests.

## 2. API → Service → DB Flow

- **API Layer (`src/api.py`, `src/contradiction_service.py` routers):**
    - Handles HTTP requests and responses.
    - Performs input validation using Pydantic models.
    - Orchestrates calls to agents or direct database operations.
    - Utilizes FastAPI's Dependency Injection for database connections (`Depends(get_db)`).
    - Ensures all blocking I/O (database calls, LLM calls) within `async def` endpoints are offloaded using `await run_in_threadpool(...)`.
- **Service Layer (e.g., `src/auditor_agent.py`, `src/query_agent.py`):**
    - Encapsulates business logic specific to a domain (e.g., auditing, querying).
    - Interacts with the database via `Database` static methods or directly manipulates data.
    - Should be designed to be testable independently of the API layer.
- **Database Layer (`src/database.py`):**
    - Provides low-level access to the SQLite database.
    - Manages connection lifecycle (opening, closing, transactions).
    - Exposes static methods (`Database.execute`, `Database.fetch_one`, `Database.fetch_all`) that require an explicit `sqlite3.Connection` object.
    - `db_session` context manager is used for transactional operations.

## 3. Conventions for Naming, Imports, Logging, Error Handling

- **Naming:**
    - Python variables, functions: `snake_case`.
    - Python classes: `CamelCase`.
    - Constants: `SCREAMING_SNAKE_CASE`.
    - FastAPI endpoints: `snake_case`.
    - Database column names: `snake_case`.
- **Imports:**
    - Group imports into standard library, third-party, and local.
    - Alphabetize imports within each group.
    - Use absolute imports for local modules (`from src.module import ...`).
- **Logging:**
    - Use Python's standard `logging` module.
    - `logger = logging.getLogger("lms_module_name")` in each module.
    - Replace `print()` statements with `logger.info()`, `logger.warning()`, `logger.error()`, `logger.debug()` as appropriate.
    - For exceptions, use `logger.exception("Error message", exc_info=True)` to log stack traces.
- **Error Handling:**
    - FastAPI endpoints should raise `HTTPException` for client-side errors (4xx) and well-handled server errors (5xx with informative `detail`).
    - Catch specific exceptions where possible; avoid bare `except Exception:`.
    - Always log exceptions.

## 4. JSON Encoding/Decoding Rules (C5, M8)

- **Storage to DB:** When storing JSON-like data (e.g., `approved_fields`, `evidence`) into a `TEXT` column in SQLite, always use `json.dumps()` to serialize the Python dictionary/list into a JSON string.
- **Retrieval from DB:** When retrieving JSON-like data from the database, always use `json.loads()` to deserialize the JSON string back into a Python dictionary/list *before* passing it to Pydantic models or returning in API responses.
- **Pydantic Models:** JSON-like fields in Pydantic models should be typed as `Dict[str, Any]` (or `List[Any]`, etc.) to accurately reflect their deserialized state.

## 5. How Enums and Models are Organized (M1, M3)

- **Canonical Source:** All Enums and Pydantic models are centrally defined in `src/models.py`. This is the single source of truth for data structures.
- **Usage:** Always import and use Enums directly from `src/models.py` (e.g., `from src.models import EntityType`). Avoid duplicating string constants for Enum values.
- **DB to Model Conversion:** When retrieving data from the database that corresponds to an Enum field in a Pydantic model, explicitly convert the string value from the database to the Enum type (e.g., `EntityType(db_row['entity_type'])`). This adds robustness against potential mismatches or invalid data.

## 6. Important Patterns Introduced During this Run

- **Database Dependency Injection:** FastAPI endpoints now receive a `sqlite3.Connection` via `Depends(get_db)`. This ensures isolated, per-request database sessions.
- **Blocking Call Offloading:** All blocking I/O operations within `async def` functions are wrapped with `await run_in_threadpool(...)` to prevent blocking the FastAPI event loop.
- **Database Context Manager:** The `db_session` context manager in `src/database.py` simplifies transaction management (commit on success, rollback on error, close connection).
- **Explicit Commits:** For single-statement mutations outside a `db_session` block, `Database.execute()` now accepts `commit=True`.
- **N+1 Query Resolution:** List endpoints have been refactored to use SQL JOINs or batched queries to avoid fetching data in a loop.
- **Secured Debug Endpoints:** Debug-only endpoints (`/debug/*`) are now protected by environment variable checks (`os.getenv("ENV") == "development"`) to prevent accidental exposure in production.
