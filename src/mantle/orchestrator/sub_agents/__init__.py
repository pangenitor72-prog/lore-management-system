# src/lms/orchestrator/sub_agents/__init__.py
"""
Sub-Agent Framework

Provides base classes and implementations for sub-agents that can be
orchestrated to complete tasks.

Sub-agent types:
- LLMSubAgent: Uses Gemini for complex reasoning tasks
- RuleBasedSubAgent: Uses deterministic rules for validation/checking
- Adapters: Wrap existing LMS agents (QueryAgent, AuditorAgent)
"""

from .base import BaseSubAgent
from .llm_agent import LLMSubAgent
from .rule_agent import RuleBasedSubAgent, Rule
from .adapters import QueryAgentAdapter, AuditorAgentAdapter

__all__ = [
    "BaseSubAgent",
    "LLMSubAgent",
    "RuleBasedSubAgent",
    "Rule",
    "QueryAgentAdapter",
    "AuditorAgentAdapter",
]
