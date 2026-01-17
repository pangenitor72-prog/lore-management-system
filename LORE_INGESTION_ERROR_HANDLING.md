# Lore Ingestion Error Handling

## Overview

This document describes the comprehensive error handling system added to the lore ingestion pipeline to help users understand and fix ingestion failures.

## Problem Statement

Users were experiencing generic "object error" messages when lore ingestion failed, with no context about what went wrong or how to fix it. The system lacked:
- Detailed error logging for debugging
- Validation of data before storage
- Structured error responses
- Graceful handling of partial failures

## Solution

### 1. Comprehensive Logging

All ingestion operations now log detailed information at each step:

```python
logger.info(f"[LORE INGESTION] Starting parse_and_store: source='{source_name}'")
logger.debug(f"[LORE INGESTION] Processing entity {idx}/{total}: '{name}' ({type})")
logger.error(f"[LORE INGESTION] Neo4j MERGE failed: {error}\nQuery: {query}\nParams: {params}")
```

**Log Markers:**
- `[LORE INGESTION]` - Main ingestion flow
- `[JSON PARSE]` - JSON parsing operations
- `[PROTECTED]` - Budget/rate limiting checks

### 2. Data Validation

Before storing entities, the system validates:

#### Required Fields
- Entity name must be non-empty
- Entity type must be non-empty
- Description should be present (warning if missing)

#### Entity Types
- Must be one of: Character, Location, Faction, Item, Event, Concept
- Invalid types converted to "Entity" with warning

#### OCEAN Scores (for Characters)
- Must be numeric (int or float)
- Must be in range [0.0, 1.0]
- Out-of-range values are clamped with warning

### 3. Structured Error Responses

All ingestion endpoints return structured error objects:

```json
{
  "error_type": "json_parse_error",
  "message": "The AI returned an improperly formatted response. Please try again.",
  "details": "Failed to parse AI response as JSON: Expecting property name enclosed in double quotes: line 15 column 5 (char 234)",
  "step_failed": "parsing"
}
```

**Error Types:**
- `json_parse_error` - AI response JSON parsing failed
- `validation_error` - Data validation failed
- `neo4j_error` - Database operation failed
- `encoding_error` - File encoding issues
- `extraction_error` / `import_error` - Other extraction errors

**Steps:**
- `file_reading` - Failed to read file
- `extraction` - AI extraction failed
- `parsing` - JSON parsing failed
- `validation` - Data validation failed
- `storage` - Database storage failed

### 4. Graceful Degradation

The system handles partial failures gracefully:

- **Invalid entities skipped:** Entities with missing required fields are logged and skipped, allowing valid entities to be stored
- **OCEAN generation failures:** If OCEAN profile generation fails for a character, the entity is still stored without personality data
- **Relationship failures:** Failed relationships are logged but don't stop entity storage
- **JSON salvage:** For truncated JSON responses, the system attempts to salvage complete entities

### 5. Error Context Preservation

For file imports, error metadata is preserved:

```json
{
  "status": "failed",
  "import_result": {
    "error": "Failed to parse AI response as JSON",
    "error_type": "json_parse_error"
  }
}
```

## API Error Responses

### POST /ingest
Ingests text content directly.

**Success Response (200):**
```json
{
  "status": "success",
  "source_name": "direct_input",
  "nodes_created": 15,
  "relationships_created": 23,
  "entities": [...],
  "relationships": [...]
}
```

**Error Response (500):**
```json
{
  "error_type": "json_parse_error",
  "message": "The AI returned an improperly formatted response. Please try again.",
  "details": "JSONDecodeError: Expecting property name...",
  "step_failed": "parsing"
}
```

### POST /ingest/preview
Previews extraction without storing.

**Error Response (500):**
```json
{
  "error_type": "extraction_error",
  "message": "Preview failed: timeout",
  "details": "TimeoutError: Gemini extraction timed out after 600 seconds",
  "step_failed": "extraction"
}
```

### POST /admin/lore/import/{file_id}
Imports a previously uploaded file.

**Additional Error Types:**
- `encoding_error` (400) - File is not valid UTF-8 text

## Server Logs

Server logs now contain full context for debugging:

```
2026-01-17 12:34:56 [INFO] [LORE INGESTION] Starting parse_and_store: source='myworld.txt', world_id='myworld', curated='None'
2026-01-17 12:34:56 [INFO] [LORE INGESTION] Text length: 5432 chars, 892 words
2026-01-17 12:34:57 [INFO] [LORE INGESTION] Parse completed: 8 entities extracted
2026-01-17 12:34:57 [INFO] [LORE INGESTION] Beginning storage phase: 8 entities, 12 relationships
2026-01-17 12:34:57 [DEBUG] [LORE INGESTION] Processing entity 1/8: 'Captain Varn' (Character)
2026-01-17 12:34:57 [ERROR] [LORE INGESTION] Entity 2 has empty name, skipping
2026-01-17 12:34:58 [DEBUG] [LORE INGESTION] Generating OCEAN profile for character 'Captain Varn'
2026-01-17 12:34:58 [DEBUG] [LORE INGESTION] Generated canon_id: myworld-chr-captain-varn-7f3a
2026-01-17 12:34:58 [ERROR] [LORE INGESTION] Neo4j MERGE failed for 'Captain Varn': ConstraintError: Node already exists
Query: MERGE (e:`Character` {canon_id: $canon_id})...
Params: canon_id=myworld-chr-captain-varn-7f3a, props keys=['name', 'description', ...]
```

## Testing

Comprehensive test suite verifies error handling:

```bash
pytest tests/test_lore_ingestion_errors.py -v
```

**Tests:**
- `test_empty_entity_name_skipped` - Empty names are skipped
- `test_invalid_entity_type_handled` - Invalid types converted to Entity
- `test_ocean_validation_clamps_values` - OCEAN scores stay in [0.0, 1.0]
- `test_json_parse_error_handling` - JSON errors return empty result
- `test_json_parse_with_markdown_fences` - Markdown fences cleaned
- `test_json_parse_salvages_truncated_response` - Partial recovery works

## Developer Guide

### Adding New Validation

To add new validation to entity storage:

1. Add validation in `parse_and_store()` before storage:
```python
# Validate new field
if entity.my_field and not isinstance(entity.my_field, str):
    logger.error(f"[LORE INGESTION] Entity '{entity.name}' has invalid my_field type")
    continue  # Skip this entity
```

2. Add test in `test_lore_ingestion_errors.py`:
```python
@pytest.mark.asyncio
async def test_my_field_validation(self):
    agent = LoreParsingAgent(api_key="test_key")
    # Test validation logic
```

### Adding New Error Types

To add a new error type:

1. Add to error response in routes.py:
```python
except MyCustomError as e:
    raise HTTPException(
        status_code=400,
        detail={
            "error_type": "my_custom_error",
            "message": "User-friendly message",
            "details": str(e),
            "step_failed": "custom_step"
        }
    )
```

2. Document in this file under "Error Types" section

### Debugging Ingestion Failures

1. **Check server logs** for `[LORE INGESTION]` markers
2. **Look for the specific error** - entity validation, JSON parse, Neo4j error
3. **Check the raw data** - logs include samples of problematic content
4. **Verify database state** - check if partial data was stored
5. **Test with smaller input** - isolate the problematic content

## Future Enhancements

Potential improvements:
- Frontend error display with error_type-specific UI
- "Download Error Log" button for technical users
- Automatic retry with exponential backoff
- Entity preview with validation warnings before commit
- Batch processing with progress tracking
