# src/lms/orchestrator/sub_agents/lore/world_builder.py
"""
World Builder Sub-Agent.

LLM-powered agent for generating world-building content.
"""

from __future__ import annotations

from typing import Optional

from ...protocols import AgentBackend, SubAgentCapability
from ...prompts.sub_agent_prompts import SubAgentPrompts
from ..llm_agent import LLMSubAgent


class WorldBuilderAgent(LLMSubAgent):
    """
    Specialized agent for world building.

    Generates rich world content including locations, cultures,
    histories, and relationships.
    """

    def __init__(
        self,
        gemini_api_key: str,
        agent_id: Optional[str] = None,
        temperature: float = 0.8,  # Higher for creativity
    ):
        """
        Initialize the world builder agent.

        Args:
            gemini_api_key: API key for Gemini
            agent_id: Optional custom agent ID
            temperature: Sampling temperature (higher for more creative)
        """
        super().__init__(
            gemini_api_key=gemini_api_key,
            capabilities=[
                SubAgentCapability.WORLD_BUILDING,
                SubAgentCapability.ENTITY_CREATION,
                SubAgentCapability.RELATIONSHIP_MAPPING,
            ],
            system_prompt=SubAgentPrompts.get_world_builder_prompt(),
            temperature=temperature,
            agent_id=agent_id,
        )

    @property
    def backend_type(self) -> AgentBackend:
        """This is an LLM-powered agent."""
        return AgentBackend.LLM
