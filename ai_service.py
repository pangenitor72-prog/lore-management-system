"""Compatibility wrapper for legacy imports.

Tests and production code import `ai_service` from the repository root,
but the actual implementation lives in `code/ai_service.py`. Importing
the symbols here keeps the public module path stable without duplicating
logic.
"""

from code.ai_service import *  # noqa: F401,F403
