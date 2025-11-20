# Glossary

This glossary defines key terms and project-specific jargon used within the Lore Management System (LMS) codebase and documentation.

-   **Agent:** An AI-powered component designed to perform specific tasks within the LMS, such as detecting contradictions or querying lore.
-   **Approved Fields:** Canonical attributes of an Entity, stored as key-value pairs (often JSON) in the database.
-   **Auditor Agent (`AuditorAgent`):** An AI agent responsible for systematically checking the lore database for inconsistencies and contradictions, using both rule-based and AI-based methods.
-   **Canon ID (`canon_id`):** A unique, system-generated identifier for an Entity (e.g., `char-xyz123`).
-   **Canonical Name (`canonical_name`):** The definitive, primary name of an Entity within the lore.
-   **Confidence Level (`ConfidenceLevel` Enum):** An enumeration (`CONFIRMED`, `PROBABLE`, `SPECULATIVE`, `UNCERTAIN`) indicating the system's or an agent's certainty about a piece of information or a detected contradiction.
-   **Contradiction:** An inconsistency or conflict identified within the lore data, indicating a potential error or unresolved narrative element.
-   **Contradiction Status (`ContradictionStatus` Enum):** An enumeration (`PENDING`, `IN_REVIEW`, `RESOLVED`, `DISMISSED`) indicating the current stage of a detected contradiction within the triage workflow.
-   **Contradiction Severity (`ContradictionSeverity` Enum):** An enumeration (`HIGH`, `MEDIUM`, `LOW`) indicating the impact or importance of a detected contradiction.
-   **Database Session (`db_session`):** A context manager that provides an isolated `sqlite3.Connection` for a block of code, ensuring transactional integrity (commit on success, rollback on error) and proper connection closure.
-   **Dependency Injection (`Depends`):** A FastAPI mechanism used to provide external components (like database connections) to route handlers, promoting modularity and testability.
-   **DM (Dungeon Master):** Refers to the human user, particularly in the context of the tabletop role-playing game metaphor.
-   **Entity:** A fundamental piece of lore, representing a person, place, item, event, or concept.
-   **Entity Type (`EntityType` Enum):** An enumeration (`CHARACTER`, `LOCATION`, `FACTION`, `EVENT`, `ITEM`, `CONCEPT`) categorizing the nature of an Entity.
-   **FastAPI:** The Python web framework used to build the LMS API.
-   **Gospel Principle:** A core mandate for AI agents: they must only report on existing, canonical lore and avoid inventing new information.
-   **LLM (Large Language Model):** AI models (e.g., Gemini-Flash, Gemini-Pro) used by agents for tasks like contradiction detection, scoring, resolution suggestion, and natural language querying.
-   **Lore:** The body of canonical information, stories, and details within the fictional world managed by the system.
-   **N+1 Query Problem:** An inefficient database access pattern where a primary query fetches N records, and then N subsequent queries are executed to fetch related data for each of those N records.
-   **Party Knowledge (`PartyKnowledge` Enum):** An enumeration (`KNOWN`, `RUMORED`, `SECRET`, `FORGOTTEN`) indicating how widely known a piece of lore or entity is within the fictional world.
-   **Pydantic:** A Python library used for data validation and settings management, extensively used for defining API request/response models.
-   **Pytest:** The Python testing framework used for writing and running unit and integration tests.
-   **Query Agent (`QueryAgent`):** An AI agent responsible for answering natural language queries about the lore.
-   **Relationship:** A directed connection between two Entities, describing how they are linked (e.g., 'parent_of', 'located_in').
-   **`run_in_threadpool`:** A FastAPI utility that offloads a synchronous (blocking) function call to a separate thread, preventing it from blocking the main event loop of an `async def` endpoint.
-   **SQLite:** The lightweight, file-based relational database used by the LMS.
-   **Triage:** The process of reviewing, categorizing, and deciding the action to take on a detected Contradiction.
-   **Triage Analysis:** The detailed evaluation and recommended action for a contradiction, typically provided by an AI or human analyst.
