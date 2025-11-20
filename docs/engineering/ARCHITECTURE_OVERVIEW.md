# Architecture Overview

This document provides a high-level overview of the Lore Management System (LMS) architecture, outlining its main components, data flow, and how core business logic is structured.

## 1. Main Modules and Their Responsibilities

The LMS is primarily a Python-based FastAPI application using SQLite as its persistent storage. It comprises the following key modules:

-   **`src/api.py`**:
    -   Serves as the main entry point for the FastAPI application.
    -   Defines and exposes RESTful API endpoints for managing entities, relationships, and contradictions.
    -   Handles request parsing, response serialization, and routes requests to appropriate handlers.
    -   Manages WebSocket connections for real-time interactions.
-   **`src/database.py`**:
    -   Manages all interactions with the SQLite database.
    -   Provides utility functions for establishing new, isolated database connections (`get_db_connection`).
    -   Includes a `db_session` context manager for transactional operations (ensuring ACID properties).
    -   Exposes static methods (`Database.execute`, `Database.fetch_one`, `Database.fetch_all`) for performing SQL operations given an active connection.
    -   Handles database schema initialization.
-   **`src/models.py`**:
    -   A centralized repository for all Pydantic models and Python Enums used throughout the application.
    -   Ensures strong typing, data validation, and consistent data structures for both API requests/responses and internal processing.
-   **`src/auditor_agent.py`**:
    -   Encapsulates the logic for contradiction detection and rule-based auditing.
    -   Utilizes both static SQL-based rules and AI (Gemini) models to identify inconsistencies in lore data.
    -   Persists detected contradictions into the database for triage.
    -   Manages its own database connections via a factory function provided during initialization.
-   **`src/query_agent.py`**:
    -   Provides AI-powered natural language querying capabilities over the canonical lore.
    -   Interacts with LLMs (Gemini) to process user questions and formulate responses based on available lore.
    -   Manages its own database connections (primarily for logging chat history) via a factory function provided during initialization.
-   **`src/contradiction_service.py`**:
    -   Defines API endpoints specifically for managing and triaging detected contradictions.
    -   Includes logic for creating, listing, retrieving details, updating status, and adding analysis to contradictions.
    -   Provides functions for setting contradiction statuses (e.g., `set_resolved`, `set_dismissed`) that are called by other parts of the system.
-   **`src/utils`**:
    -   Contains general utility functions, such as `logging_config.py` for centralized logging setup.
-   **`src/templates` / `src/static`**:
    -   Host Jinja2 templates and static assets (CSS, JS) for the web-based UI components (e.g., dashboard, entity browser, contradiction triage interface).

## 2. Data Flow

1.  **Client Request:** A client (web UI, another service) sends an HTTP request to a FastAPI endpoint defined in `src/api.py` or `src/contradiction_service.py`.
2.  **API Endpoint Processing:**
    *   FastAPI handles routing and Pydantic model validation of incoming data.
    *   A fresh `sqlite3.Connection` is injected into the endpoint using FastAPI's dependency injection (`Depends(get_db)`).
    *   For `async def` endpoints, any blocking I/O operations (database calls via `Database` static methods, LLM calls via agents) are offloaded to a thread pool using `await run_in_threadpool(...)` to prevent blocking the event loop.
    *   The endpoint might directly interact with the database using `Database.fetch_one`, `Database.fetch_all`, `Database.execute` (often within a `db_session` context for transactions).
    *   Alternatively, it might delegate complex logic to an agent (`AuditorAgent`, `QueryAgent`) or another service (`contradiction_service`).
3.  **Agent/Service Interaction:**
    *   Agents (`AuditorAgent`, `QueryAgent`) obtain their own database connections using the `get_db_connection` callable they were initialized with, ensuring isolation from the API's request-specific connection.
    *   Agents might perform further database queries or call external LLM APIs.
4.  **Database Operations:**
    *   SQL queries are executed against the SQLite database.
    *   Data is stored and retrieved in a structured manner, with JSON data being `json.dumps`ed on write and `json.loads`ed on read to maintain object integrity.
5.  **Response Generation:**
    *   Processed data is formatted back into Pydantic response models.
    *   HTTP responses (JSON, HTML) are sent back to the client.

## 3. Interaction Between Contradictions, Entities, and Relationships

-   **Entities:** Core lore elements (Characters, Locations, Items, etc.). They form the foundation of the lore database, stored in the `entities` table with associated `aliases` and `approved_fields`.
-   **Relationships:** Define connections and interactions between entities (e.g., "parent_of", "located_in", "member_of"). Stored in the `relationships` table.
-   **Contradictions:** Inconsistencies or conflicts detected within the entities and relationships.
    -   `AuditorAgent` identifies contradictions, which can be rule-based (SQL checks) or AI-based (LLM analysis).
    -   Detected contradictions are stored in the `contradictions` table, often linked to `contradiction_entities` (a many-to-many table).
    -   The `contradiction_service` module handles the lifecycle of these contradictions, allowing them to be triaged, analyzed, resolved, or dismissed, with analysis stored in `triage_analysis`.

## 4. Where Core Business Logic Lives

-   **Entity and Relationship Management:** Primarily within `src/api.py` for basic CRUD, interacting directly with `src/database.py`.
-   **Contradiction Detection:** Encapsulated within `src/auditor_agent.py` (both rule-based and AI-based logic).
-   **Contradiction Triage Workflow:** Handled by `src/contradiction_service.py`, which defines the API for managing contradiction statuses and associated analysis.
-   **Lore Querying:** Implemented in `src/query_agent.py` using LLMs.
-   **Data Modeling and Validation:** Centralized in `src/models.py`.
-   **Database Interactions:** Abstracted and managed by `src/database.py`.

This modular design aims to keep concerns separated, improve maintainability, and facilitate independent development and testing of different system components.
