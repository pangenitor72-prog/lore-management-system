# src/airpg/runtime/content_injection.py
from __future__ import annotations
from typing import Dict, Any

def create_content_message(content: str) -> Dict[str, Any]:
    """
    Wraps a raw content string into a runtime message format.

    This function is a pure adapter. It adds NO metadata, NO identifiers,
    NO truth flags, and performs NO validation. It exists only to
    standardize the format of injected content.
    """
    # In this minimal implementation, the "message" is just the content.
    # A more complex system might wrap it in a dictionary, but for now,
    # the string itself is the message payload. This adheres to the
    # "no extra metadata" rule.
    return content

