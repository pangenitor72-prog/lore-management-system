# src/core/utils.py

"""
Core utility helpers for LMS / MANTLE / AIRPG.

These functions are intentionally:
- Pure (no side effects)
- Conservative (no surprise type coercion)
- Safe to call from agents, services, and API layers

They are meant to centralize common patterns:
- String sanitization and validation
- Property normalization
- Recursive null/empty pruning
- JSON-safe serialization
- Security input validation and environment variable checking
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, MutableMapping, Iterable, Union, Optional
import json
import re


def sanitize_string(value: Any) -> str:
    """
    Safely coerce a value to a clean string.

    Rules:
    - None -> ""
    - str  -> stripped
    - other types -> str(value), stripped

    This should be used for logging, IDs, and text fields where
    an empty string is safer than None.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def strip_nulls(obj: Any) -> Any:
    """
    Recursively remove keys with value None from dicts and
    strip None elements from lists/tuples.

    Does NOT:
    - Remove falsy but valid values (0, False, "", [], {}).
    - Mutate the original object (returns a new structure).

    This is a low-risk cleanup pass for data heading into
    Neo4j, JSON responses, or logs.
    """
    if isinstance(obj, Mapping):
        cleaned: Dict[Any, Any] = {}
        for k, v in obj.items():
            if v is None:
                continue
            cleaned_val = strip_nulls(v)
            cleaned[k] = cleaned_val
        return cleaned

    if isinstance(obj, (list, tuple)):
        return type(obj)(strip_nulls(v) for v in obj if v is not None)

    return obj


def deepclean_dict(data: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Higher-level dict cleaner.

    Operations:
    - Sanitizes string keys with sanitize_string
    - Leaves value types intact, but:
        - Recurses into nested dicts/lists
        - Strips None values via strip_nulls()

    This is safe to run before:
    - Writing to Neo4j
    - Returning API payloads
    - Logging structured events
    """
    if not isinstance(data, Mapping):
        raise TypeError("deepclean_dict expected a mapping")

    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        clean_key = sanitize_string(key)

        # Recurse into nested structures
        if isinstance(value, Mapping):
            cleaned[clean_key] = deepclean_dict(value)
        elif isinstance(value, (list, tuple)):
            cleaned[clean_key] = strip_nulls(
                [deepclean_dict(v) if isinstance(v, Mapping) else v for v in value]
            )
        else:
            cleaned[clean_key] = value

    # Final pass to drop Nones introduced deeper down
    return strip_nulls(cleaned)


def normalize_properties(props: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Normalize a generic property dict before persistence.

    Intended use:
    - Properties sent to Neo4j
    - Entity attribute maps
    - Outgoing response fragments

    Rules:
    - Keys: sanitized to strings via sanitize_string()
    - Values:
        - Strings stripped
        - Other types left intact
    - None values removed

    This is intentionally conservative to avoid changing domain semantics.
    """
    if not isinstance(props, Mapping):
        raise TypeError("normalize_properties expected a mapping")

    normalized: Dict[str, Any] = {}

    for key, value in props.items():
        clean_key = sanitize_string(key)

        if value is None:
            # Drop None properties entirely
            continue

        if isinstance(value, str):
            normalized[clean_key] = value.strip()
        elif isinstance(value, Mapping):
            normalized[clean_key] = normalize_properties(value)
        elif isinstance(value, (list, tuple)):
            # Normalize nested mappings inside collections; otherwise keep as-is
            normalized[clean_key] = [
                normalize_properties(v) if isinstance(v, Mapping) else v
                for v in value
            ]
        else:
            normalized[clean_key] = value

    return normalized


def safe_json(data: Any) -> str:
    """
    Safely serialize data to JSON for logging or debug output.

    - Uses default=str to avoid crashing on unserializable types
    - ensure_ascii=False to preserve Unicode
    - Never raises; falls back to a best-effort string representation
    """
    try:
        return json.dumps(data, default=str, ensure_ascii=False)
    except Exception:
        # Last-resort safeguard; do NOT raise from logging helpers
        try:
            return str(data)
        except Exception:
            return "<unserializable>"


# ============================================================
# SECURITY FUNCTIONS
# ============================================================


def sanitize_user_input(value: str, max_length: int = 500, allow_special: bool = False) -> str:
    """
    Sanitize user input strings to prevent injection attacks.
    
    This is a stricter version of sanitize_string for user-provided input
    that will be used in queries or displayed in responses.
    
    Args:
        value: The input string to sanitize
        max_length: Maximum allowed length (default: 500)
        allow_special: Whether to allow special characters beyond alphanumeric (default: False)
    
    Returns:
        Sanitized string
    
    Raises:
        ValueError: If input is too long or contains disallowed characters
    """
    if not value:
        return ""
    
    if not isinstance(value, str):
        value = str(value)
    
    value = value.strip()
    
    if not value:
        return ""
    
    if len(value) > max_length:
        raise ValueError(f"Input too long: maximum {max_length} characters")
    
    if not allow_special:
        # Allow alphanumeric, spaces, and basic punctuation only
        if not re.match(r'^[a-zA-Z0-9\s\-_.,!?()\'"]+$', value):
            raise ValueError("Input contains disallowed special characters")
    
    return value


def validate_canon_id(canon_id: str) -> str:
    """
    Validate and sanitize a canonical entity ID.
    
    Canon IDs should be safe for use in URLs, database queries, and file paths.
    
    Args:
        canon_id: The ID to validate
        
    Returns:
        Validated and sanitized ID
        
    Raises:
        ValueError: If ID format is invalid
    """
    if not canon_id or not isinstance(canon_id, str):
        raise ValueError("Canon ID must be a non-empty string")
    
    canon_id = canon_id.strip()
    
    if not canon_id:
        raise ValueError("Canon ID must be a non-empty string")
    
    # IDs should be alphanumeric with hyphens/underscores only
    if not re.match(r'^[a-zA-Z0-9\-_]+$', canon_id):
        raise ValueError("Canon ID contains invalid characters (only alphanumeric, hyphen, and underscore allowed)")
    
    if len(canon_id) > 100:
        raise ValueError("Canon ID too long (maximum 100 characters)")
    
    return canon_id


def validate_env_var(var_name: str, value: Optional[str], required: bool = True) -> Optional[str]:
    """
    Validate an environment variable.
    
    Args:
        var_name: Name of the environment variable (for error messages)
        value: The value to validate
        required: Whether this variable is required (default: True)
        
    Returns:
        The validated value (stripped of whitespace) or None if optional and not set
        
    Raises:
        ValueError: If a required variable is missing or invalid
    """
    if not value or not value.strip():
        if required:
            raise ValueError(f"Required environment variable {var_name} is not set or is empty")
        return None
    
    return value.strip()