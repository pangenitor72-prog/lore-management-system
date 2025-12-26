# src/lms/orchestrator/sub_agents/adapters/__init__.py
"""
Adapter agents that wrap existing LMS agents.

These adapters allow the orchestrator to leverage existing agent
functionality (QueryAgent, AuditorAgent) through the sub-agent interface.
"""

from .query_adapter import QueryAgentAdapter
from .auditor_adapter import AuditorAgentAdapter

__all__ = [
    "QueryAgentAdapter",
    "AuditorAgentAdapter",
]
