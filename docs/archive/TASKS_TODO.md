# Remaining / Follow-up Tasks

This document outlines follow-up tasks, potential refactorings, test expansions, performance work, and documentation deepenings identified during the recent audit and refactoring effort. These tasks are suitable for future development sprints or AI collaboration.

## 1. Further Refactors

-   **Refine `Neo4jDatabase` Adapter:** The `Neo4jDatabase` class provides a good abstraction. Future work could involve adding more helper methods for common query patterns to further simplify the service and agent layers.
-   **Agent Initialization in `api.py`:** Review the global initialization of `AuditorAgent` and `QueryAgent` in `src/api.py`. While it now passes a callable for `get_db_connection`, consider if a more explicit dependency injection pattern for these agents directly into routes (e.g., using a custom FastAPI `Depends` for agents) might be cleaner for managing their lifecycle or dynamic configuration.
-   **Centralized Error Handling Middleware:** Implement a FastAPI exception handler or middleware for consistent, application-wide error responses, rather than `try-except` blocks in every endpoint.
-   **Configuration Management:** Use a dedicated configuration library (e.g., `Dynaconf`, `Pydantic-Settings`) instead of `os.getenv` for more structured settings management.
-   **Remove `from . import contradiction_service`:** In `src/api.py`, the `resolve_contradiction_unified` endpoint uses `from . import contradiction_service`. While it works, it might indicate a circular import if not carefully managed. Reassess if this function should be part of `api.py` or if a cleaner import path exists.

## 2. Test Expansions

-   **Auditor Agent Tests:** Add comprehensive unit tests for `AuditorAgent`'s various `check_*` methods and `detect_contradictions` logic. Mock LLM calls and database interactions.
-   **Query Agent Tests:** Add unit tests for `QueryAgent`'s `ask` method, mocking LLM responses.
-   **WebSocket Tests:** Implement integration tests for WebSocket endpoints to ensure correct real-time communication.
-   **Error Handling Tests:** Add tests to verify that API endpoints return appropriate HTTP status codes and error messages for invalid input, missing resources, and server errors.
-   **Edge Case Tests:** Expand test coverage for edge cases, such as empty lists, invalid IDs, and boundary conditions for filters.
-   **Performance Tests:** Introduce basic performance tests for N+1 query fixes and large data sets.

## 3. Performance Work

-   **Database Indexing Review:** Regularly review Cypher query performance and add or optimize database indexes on node properties to improve query speed.
-   **Database Connection Pooling:** The `neo4j` driver handles connection pooling automatically. Monitor performance under load to ensure the pool is configured optimally for the application's needs.
-   **LLM Caching:** Implement caching for LLM responses to reduce latency and API costs for repetitive queries.

## 4. Documentation Deepenings

-   **API Reference:** Generate a more detailed API reference (e.g., using Sphinx or extending OpenAPI spec) to document all endpoints, request/response models, and error codes.
-   **Graph Schema Visualization:** Create a visualization of the graph schema (nodes, relationships, properties) to provide a clear visual reference.
-   **Deployment Guide:** Document the steps required to deploy the LMS application to various environments (e.g., Docker, Kubernetes, cloud platforms).
-   **Security Hardening:** Document security considerations, best practices, and any implemented security features (e.g., authentication, authorization).
-   **Design Decisions:** Document specific design choices and their justifications.

## 5. Feature Enhancements

-   **Authentication and Authorization:** Implement robust user authentication and role-based authorization for API endpoints.
-   **LLM API Cost Monitoring:** Integrate tools to monitor and manage LLM API usage and costs.
-   **Advanced Search:** Implement more sophisticated search capabilities for entities and contradictions.
-   **UI Improvements:** Enhance the existing web UI with richer features and a more intuitive user experience.
-   **Asynchronous LLM Calls:** If the `genai` library supports it, consider making LLM calls truly asynchronous to further optimize performance in `AuditorAgent` and `QueryAgent`.

This list serves as a living document to guide future development and continuous improvement of the LMS.
