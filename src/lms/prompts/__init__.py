"""
Prompt Library - Centralized AI prompt management.

All prompts used across the LMS/AIRpg system.
Versioned, testable, and easily iterable.
"""

from .dm_prompts import DMPrompts
from .query_prompts import QueryPrompts
from .auditor_prompts import AuditorPrompts
from .boundary_prompts import BoundaryPrompts

__all__ = [
    'DMPrompts',
    'QueryPrompts',
    'AuditorPrompts',
    'BoundaryPrompts'
]

PROMPT_VERSION = "2.4.0"
LAST_UPDATED = "2025-11-29"

