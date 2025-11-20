# Testing Guide

This document provides a guide to the testing framework and strategy employed in the Lore Management System (LMS). It covers how to run tests, recommended structures for new tests, and a summary of current test coverage.

## 1. How to Run the Tests

The LMS uses `pytest` as its primary testing framework. All tests are located in the `tests/` directory.

To run all tests from the project root directory:

```bash
pytest
```

To run a specific test file:

```bash
pytest tests/path/to/your_test_file.py
```

To run tests with verbose output:

```bash
pytest -v
```

To run tests and see print statements/log messages (useful for debugging):

```bash
pytest -s
```

## 2. Recommended Structure for Future Tests

### a. `tests/test_db_*.py` (Unit Tests for Database Layer)

-   **Purpose:** Verify the functionality of `src/database.py`'s core methods (connection handling, schema initialization, `execute`, `fetch_one`, `fetch_all`).
-   **Approach:**
    -   Use `pytest.fixture` to set up an isolated in-memory SQLite database (`":memory:"`) for each test function or test class.
    -   Directly interact with `src/database.py` functions and static methods.
    -   Ensure schema is initialized for the in-memory database within the fixture.
-   **Example:** See `tests/test_db_basic.py`.

### b. `tests/test_*_api.py` (Integration Tests for API Endpoints)

-   **Purpose:** Verify that FastAPI endpoints correctly handle requests, interact with the database, and return appropriate responses.
-   **Approach:**
    -   Use `httpx.AsyncClient` to make requests to the FastAPI application.
    -   Use `pytest.fixture` to set up an in-memory database and override FastAPI's `get_db` dependency to point to this test database. This ensures isolated tests for API endpoints.
    -   Mock external dependencies (e.g., LLM calls in agents) if they are not the primary focus of the test.
    -   Test request/response validation, status codes, and the correctness of the data returned/modified.
-   **Example:** See `tests/test_entities_api.py`, `tests/test_contradictions_api.py`.

### c. `tests/test_*_agent.py` (Unit Tests for Agents)

-   **Purpose:** Verify the business logic within agents (`src/auditor_agent.py`, `src/query_agent.py`).
-   **Approach:**
    -   Mock database interactions using `unittest.mock` or a lightweight mock database object.
    -   Mock external API calls (e.g., Gemini LLM calls) to ensure tests are fast and deterministic, and do not incur external costs.
    -   Focus on the logic of the agent, not the underlying dependencies.

## 3. Current Test Coverage Summary

Following the recent audit and refactoring, the following basic test coverage has been established:

-   **`tests/test_db_basic.py`**:
    -   Verification of in-memory database connection.
    -   Confirmation of database schema initialization.
    -   Basic entity insertion and retrieval.
    -   Entity insertion with aliases and approved fields, including JSON field handling verification.
-   **`tests/test_entities_api.py`**:
    -   Successful creation of entities via `POST /entities`.
    -   Retrieval of a specific entity via `GET /entities/{canon_id}`.
    -   Listing of entities via `GET /entities`, including filtering by `approval_status`.
    -   Verification of correct JSON field parsing in API responses.
-   **`tests/test_contradictions_api.py`**:
    -   Creation of new contradictions via `POST /contradictions`.
    -   Listing of contradictions via `GET /contradictions`, including filtering by `status`.
    -   Retrieval of contradiction details via `GET /contradictions/{contradiction_id}`.
    -   Updating contradiction status via `PATCH /contradictions/{contradiction_id}/status`.
    -   Adding triage analysis to a contradiction via `POST /contradictions/{contradiction_id}/analysis`.
    -   Verification of contradiction status updates after analysis.

## 4. What is Covered Now vs. What is Not

-   **Covered:** Core CRUD operations for entities and contradictions, basic database functionality, API endpoint integration with the database, and some aspects of JSON field handling and Enum usage.
-   **Not Covered (yet):**
    -   Comprehensive unit tests for the complex logic within `AuditorAgent` (e.g., specific rule-based checks, AI detection logic).
    -   Unit tests for `QueryAgent`'s LLM interaction logic.
    -   Error handling paths for all API endpoints (e.g., invalid input, missing required fields, database errors).
    -   Tests for relationship CRUD operations.
    -   Negative test cases (e.g., creating entity with invalid data, querying non-existent entities).
    -   Performance or load testing.
    -   WebSocket communication beyond basic connection.

This guide should serve as a foundation for expanding the test suite to achieve higher coverage and robustness in future development.
