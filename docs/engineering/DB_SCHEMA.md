# Database Schema

This document outlines the current canonical SQLite database schema for the Lore Management System (LMS).

## Overview

The database is designed to store various lore entities, their attributes, relationships, and detected contradictions. Foreign key constraints are enforced to maintain data integrity.

## Tables

### 1. `entities`

Stores the core lore objects.

-   **`canon_id`** (`TEXT PRIMARY KEY`): Unique identifier for the entity (e.g., `char-xyz123`, `loc-abc456`).
-   **`entity_type`** (`TEXT NOT NULL`): Type of the entity (e.g., 'Character', 'Location', 'Faction', 'Event', 'Item', 'Concept').
-   **`canonical_name`** (`TEXT NOT NULL`): The primary, canonical name of the entity.
-   **`approval_status`** (`TEXT NOT NULL`): Current approval status ('APPROVED', 'PENDING', 'REJECTED').
-   **`confidence_level`** (`TEXT NOT NULL`): Confidence level of the entity data ('CONFIRMED', 'PROBABLE', 'SPECULATIVE', 'UNCERTAIN').
-   **`party_knowledge`** (`TEXT NOT NULL`): How widely known the entity is ('KNOWN', 'RUMORED', 'SECRET', 'FORGOTTEN').
-   **`created_at`** (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`): Timestamp of entity creation.
-   **`updated_at`** (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`): Timestamp of last update.

### 2. `approved_fields`

Stores canonical attributes for entities, allowing for flexible key-value pairs. `field_value` often contains JSON strings.

-   **`id`** (`INTEGER PRIMARY KEY AUTOINCREMENT`)
-   **`canon_id`** (`TEXT NOT NULL`): Foreign key referencing `entities.canon_id`.
-   **`field_key`** (`TEXT NOT NULL`): The name of the attribute (e.g., 'birthplace', 'race').
-   **`field_value`** (`TEXT NOT NULL`): The value of the attribute, often stored as a JSON string.
-   **`FOREIGN KEY (canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE`**

### 3. `aliases`

Stores alternative names or aliases for entities.

-   **`id`** (`INTEGER PRIMARY KEY AUTOINCREMENT`)
-   **`canon_id`** (`TEXT NOT NULL`): Foreign key referencing `entities.canon_id`.
-   **`alias`** (`TEXT NOT NULL`): An alternative name for the entity.
-   **`FOREIGN KEY (canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE`**

### 4. `relationships`

Stores directed relationships between two entities.

-   **`id`** (`INTEGER PRIMARY KEY AUTOINCREMENT`)
-   **`from_canon_id`** (`TEXT NOT NULL`): Foreign key referencing the source `entities.canon_id`.
-   **`relationship_type`** (`TEXT NOT NULL`): The type of relationship (e.g., 'parent_of', 'located_in').
-   **`to_canon_id`** (`TEXT NOT NULL`): Foreign key referencing the target `entities.canon_id`.
-   **`confidence_level`** (`TEXT NOT NULL`): Confidence level of the relationship ('CONFIRMED', 'PROBABLE', 'SPECULATIVE', 'UNCERTAIN').
-   **`created_at`** (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`): Timestamp of relationship creation.
-   **`FOREIGN KEY (from_canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE`**
-   **`FOREIGN KEY (to_canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE`**

### 5. `revisions`

Stores historical changes made to entity fields, acting as an audit log.

-   **`id`** (`INTEGER PRIMARY KEY AUTOINCREMENT`)
-   **`canon_id`** (`TEXT NOT NULL`): Foreign key referencing `entities.canon_id`.
-   **`field_name`** (`TEXT NOT NULL`): The name of the field that was changed.
-   **`old_value`** (`TEXT`): The value of the field before the change.
-   **`new_value`** (`TEXT`): The value of the field after the change.
-   **`changed_at`** (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`): Timestamp of the change.
-   **`changed_by`** (`TEXT`): Identifier for who (or what process) made the change.
-   **`FOREIGN KEY (canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE`**

### 6. `contradictions`

Stores detected inconsistencies or conflicts in the lore, whether identified by rules or AI.

-   **`id`** (`INTEGER PRIMARY KEY AUTOINCREMENT`)
-   **`contradiction_id`** (`TEXT UNIQUE NOT NULL`): A unique identifier (UUID) for the contradiction.
-   **`status`** (`TEXT NOT NULL DEFAULT 'PENDING'`): Current triage status ('PENDING', 'IN_REVIEW', 'RESOLVED', 'DISMISSED').
-   **`detected_at`** (`TEXT NOT NULL`): Timestamp when the contradiction was first detected.
-   **`entity_a_id`** (`TEXT`): Optional, foreign key to the first involved entity (`entities.canon_id`).
-   **`entity_b_id`** (`TEXT`): Optional, foreign key to the second involved entity (`entities.canon_id`).
-   **`contradiction_type`** (`TEXT NOT NULL`): Categorization of the contradiction (e.g., 'consistency', 'temporal').
-   **`severity`** (`TEXT NOT NULL`): Impact level ('HIGH', 'MEDIUM', 'LOW').
-   **`description`** (`TEXT NOT NULL`): Detailed explanation of the contradiction.
-   **`evidence`** (`TEXT NOT NULL`): JSON string containing evidence supporting the contradiction.
-   **`confidence`** (`REAL`): AI-assigned confidence score (0.0 to 1.0).
-   **`scoring_reasoning`** (`TEXT`): AI's reasoning for the confidence score.
-   **`possible_resolutions`** (`TEXT`): JSON string of AI-suggested resolutions.
-   **`created_at`** (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`): Timestamp of record creation.
-   **`resolution_notes`** (`TEXT`): Notes on how the contradiction was resolved or dismissed.
-   **`updated_by`** (`TEXT`): Identifier for who updated the contradiction status.
-   **`FOREIGN KEY (entity_a_id) REFERENCES entities (canon_id) ON DELETE CASCADE`**
-   **`FOREIGN KEY (entity_b_id) REFERENCES entities (canon_id) ON DELETE CASCADE`**

### 7. `contradiction_entities`

A many-to-many junction table linking contradictions to all involved entities. This allows a single contradiction to involve more than two entities.

-   **`id`** (`INTEGER PRIMARY KEY AUTOINCREMENT`)
-   **`contradiction_id`** (`TEXT NOT NULL`): Foreign key referencing `contradictions.contradiction_id`.
-   **`canon_id`** (`TEXT NOT NULL`): Foreign key referencing `entities.canon_id`.
-   **`FOREIGN KEY (contradiction_id) REFERENCES contradictions(contradiction_id) ON DELETE CASCADE`**
-   **`FOREIGN KEY (canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE`**

### 8. `triage_analysis`

Stores detailed analysis provided during the contradiction triage process (e.g., by "Claude").

-   **`id`** (`INTEGER PRIMARY KEY AUTOINCREMENT`)
-   **`contradiction_id`** (`TEXT UNIQUE NOT NULL`): Foreign key referencing `contradictions.contradiction_id` (ensuring one analysis per contradiction).
-   **`analyst`** (`TEXT NOT NULL`): Identifier of the analyst (e.g., 'CLAUDE', 'Human Reviewer').
-   **`analysis`** (`TEXT NOT NULL`): The detailed analysis of the contradiction.
-   **`recommendation`** (`TEXT NOT NULL`): Recommendation for resolving or handling the contradiction.
-   **`confidence`** (`TEXT NOT NULL`): Confidence level of the analysis ('HIGH', 'MEDIUM', 'LOW').
-   **`analyzed_at`** (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`): Timestamp of the analysis.
-   **`FOREIGN KEY (contradiction_id) REFERENCES contradictions(contradiction_id) ON DELETE CASCADE`**

### 9. `agent_chat_log`

Logs interactions with the query agent.

-   **`id`** (`INTEGER PRIMARY KEY AUTOINCREMENT`)
-   **`sender`** (`TEXT NOT NULL`): Who sent the message (e.g., 'user', 'QueryAgent').
-   **`message`** (`TEXT NOT NULL`): The content of the message.
-   **`timestamp`** (`TEXT NOT NULL`): Timestamp of the message.

## Indexes

-   `idx_entities_type` ON `entities(entity_type)`
-   `idx_entities_status` ON `entities(approval_status)`
-   `idx_approved_fields_canon` ON `approved_fields(canon_id)`
-   `idx_approved_fields_key` ON `approved_fields(field_key)`
-   `idx_aliases_canon` ON `aliases(canon_id)`
-   `idx_relationships_from` ON `relationships(from_canon_id)`
-   `idx_relationships_to` ON `relationships(to_canon_id)`
-   `idx_revisions_canon` ON `revisions(canon_id)`
-   `idx_contradictions_status` ON `contradictions(status)`
-   `idx_contradictions_severity` ON `contradictions(severity)`
-   `idx_contradiction_entities_canon` ON `contradiction_entities(canon_id)`
