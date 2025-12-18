# src/core/utils.py

"""
Core utility helpers for LMS / MANTLE / AIRPG.

These functions are intentionally:
- Pure (no side effects)
- Conservative (no surprise type coercion)
- Safe to call from agents, services, and API layers

They are meant to centralize common patterns:
- String sanitization
- Property normalization
- Recursive null/empty pruning
- JSON-safe serialization
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, MutableMapping, Iterable, Union
import json


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