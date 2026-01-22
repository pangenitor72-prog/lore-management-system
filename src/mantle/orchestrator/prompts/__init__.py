# src/lms/orchestrator/prompts/__init__.py
"""
Orchestrator Prompts

Centralized prompt library for the orchestrator and sub-agents.
"""

from .orchestrator_prompts import OrchestratorPrompts
from .sub_agent_prompts import SubAgentPrompts

__all__ = [
    "OrchestratorPrompts",
    "SubAgentPrompts",
]

PROMPT_VERSION = "1.0.0"
