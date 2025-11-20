# Database Migration Guide

This document outlines the strategy and best practices for safely evolving the SQLite database schema in the Lore Management System (LMS). Given SQLite's nature, direct `ALTER TABLE` operations can be complex for significant changes. This guide prioritizes safety, data integrity, and minimizing downtime.

## 1. Versioning Strategy

The database schema version is implicitly managed through the `data/schema.sql` file. Any change to the `schema.sql` should be considered a new schema version. There is currently no explicit version table in the database, but this could be a future enhancement.

## 2. General Principles

-   **Backwards-Compatibility:** Always strive for backwards-compatible schema changes. This means new columns should be nullable or have a sensible default. Existing columns should not be removed or renamed without a clear, multi-phase migration plan.
-   **Data Integrity:** Prioritize the integrity of existing data. Always back up the database before performing any migration on a production system.
-   **Atomic Changes:** Each migration step should be as small and atomic as possible to reduce the risk of failure and simplify rollback.
-   **Testing:** All migrations must be thoroughly tested in a development environment before deployment to production.

## 3. Recommended Migration Steps for Significant Changes

For complex schema changes (e.g., altering column types, renaming columns, splitting/merging tables, non-nullable new columns):

1.  **Backup the Database:**
    ```bash
    cp data/lore.db data/lore_backup_YYYYMMDD_HHMMSS.db
    ```
2.  **Create New Table with Desired Schema:**
    ```sql
    CREATE TABLE IF NOT EXISTS new_table_name (
        -- new schema definition
    );
    ```
3.  **Copy Data (with Transformations):**
    ```sql
    INSERT INTO new_table_name (new_column1, new_column2, ...)
    SELECT old_column1, old_column2, ...
    FROM old_table_name;
    ```
    -   Perform any necessary data transformations during this step (e.g., `CAST` types, `JSON_EXTRACT`, `COALESCE`).
    -   Handle new `NOT NULL` columns by providing defaults or deriving values.
4.  **Drop Original Table:**
    ```sql
    DROP TABLE old_table_name;
    ```
5.  **Rename New Table:**
    ```sql
    ALTER TABLE new_table_name RENAME TO old_table_name;
    ```
6.  **Recreate Indexes and Triggers:** If necessary, recreate any indexes, triggers, or views that were associated with the original table.
7.  **Update `schema.sql`:** Ensure `data/schema.sql` reflects the new canonical schema.

## 4. Simple Schema Changes

For simpler, backwards-compatible changes (e.g., adding a nullable column, adding a column with a default value):

1.  **Add Column:**
    ```sql
    ALTER TABLE table_name ADD COLUMN new_column_name TEXT;
    -- Or with a default:
    ALTER TABLE table_name ADD COLUMN new_column_name TEXT DEFAULT 'default_value';
    ```
2.  **Update `schema.sql`:** Ensure `data/schema.sql` reflects the new column definition.

## 5. Code Changes

-   **Update Pydantic Models:** Modify `src/models.py` to reflect any schema changes (new fields, updated types).
-   **Update Database Operations:** Adjust SQL queries in `src/database.py`, `src/api.py`, `src/auditor_agent.py`, `src/contradiction_service.py` to match the new schema.
-   **Testing:** Write or update tests to verify the migration process and the application's functionality with the new schema.

## 6. Important Considerations

-   **Deployment:** When deploying a migration, ensure that the application code expecting the *new* schema is deployed *after* the schema migration has completed successfully. For complex changes, a brief maintenance window may be required.
-   **Rollback Plan:** Always have a clear rollback plan. This typically involves restoring from the pre-migration database backup.
-   **Collaboration:** Communicate schema changes with all relevant team members and AI collaborators.
