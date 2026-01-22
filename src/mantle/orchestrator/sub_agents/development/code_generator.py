# src/lms/orchestrator/sub_agents/development/code_generator.py
"""
Code Generator Sub-Agent.

LLM-powered agent specialized for generating Python code.
"""

from __future__ import annotations

from typing import List, Optional

from ...protocols import AgentBackend, SubAgentCapability
from ...prompts.sub_agent_prompts import SubAgentPrompts
from ..llm_agent import LLMSubAgent


class CodeGeneratorAgent(LLMSubAgent):
    """
    Specialized agent for code generation.

    Uses LLM to generate Python code following project conventions.
    """

    def __init__(
        self,
        gemini_api_key: str,
        agent_id: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize the code generator agent.

        Args:
            gemini_api_key: API key for Gemini
            agent_id: Optional custom agent ID
            temperature: Sampling temperature
        """
        super().__init__(
            gemini_api_key=gemini_api_key,
            capabilities=[
                SubAgentCapability.CODE_GENERATION,
                SubAgentCapability.CODE_REFACTORING,
                SubAgentCapability.BUG_FIXING,
            ],
            system_prompt=SubAgentPrompts.get_code_generator_prompt(),
            temperature=temperature,
            agent_id=agent_id,
        )

    @property
    def backend_type(self) -> AgentBackend:
        """This is an LLM-powered agent."""
        return AgentBackend.LLM
