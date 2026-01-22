# src/lms/orchestrator/sub_agents/lore/entity_creator.py
"""
Entity Creator Sub-Agent.

Hybrid agent for creating lore entities with LLM generation
and rule-based validation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...models import Task, TaskResult, SubAgentContext, TaskStatus
from ...protocols import AgentBackend, SubAgentCapability
from ...prompts.sub_agent_prompts import SubAgentPrompts
from ..llm_agent import LLMSubAgent


class EntityCreatorAgent(LLMSubAgent):
    """
    Specialized agent for creating lore entities.

    Uses LLM for entity generation and applies validation rules
    for consistency checking.
    """

    # Valid entity types
    ENTITY_TYPES = {
        "CHARACTER",
        "CREATURE",
        "DEITY",
        "LOCATION",
        "FACTION",
        "ITEM",
        "SPELL",
        "EVENT",
    }

    # OCEAN traits for characters
    OCEAN_TRAITS = [
        "openness",
        "conscientiousness",
        "extraversion",
        "agreeableness",
        "neuroticism",
    ]

    def __init__(
        self,
        gemini_api_key: str,
        agent_id: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize the entity creator agent.

        Args:
            gemini_api_key: API key for Gemini
            agent_id: Optional custom agent ID
            temperature: Sampling temperature for creativity
        """
        super().__init__(
            gemini_api_key=gemini_api_key,
            capabilities=[
                SubAgentCapability.ENTITY_CREATION,
                SubAgentCapability.WORLD_BUILDING,
            ],
            system_prompt=SubAgentPrompts.get_entity_creator_prompt(),
            temperature=temperature,
            agent_id=agent_id,
        )

    @property
    def backend_type(self) -> AgentBackend:
        """This is a hybrid agent (LLM + validation)."""
        return AgentBackend.HYBRID

    async def _execute_impl(
        self, task: Task, context: SubAgentContext
    ) -> TaskResult:
        """Execute entity creation with validation."""
        # First, run LLM to generate the entity
        result = await super()._execute_impl(task, context)

        if result.status != TaskStatus.COMPLETED:
            return result

        # Validate the generated entity
        entity_data = result.output.get("entity", result.output)
        validation_warnings = self._validate_entity(entity_data, context)

        # Merge warnings
        all_warnings = list(result.warnings) + validation_warnings

        # Update result with validation warnings
        return TaskResult(
            task_id=result.task_id,
            agent_id=result.agent_id,
            status=result.status,
            output=result.output,
            artifacts=result.artifacts,
            warnings=all_warnings,
            suggested_tasks=result.suggested_tasks,
            tokens_used=result.tokens_used,
            execution_time_ms=result.execution_time_ms,
        )

    def _validate_entity(
        self, entity_data: Dict[str, Any], context: SubAgentContext
    ) -> List[str]:
        """
        Validate the generated entity.

        Args:
            entity_data: The entity data from LLM
            context: The context with existing entities

        Returns:
            List of validation warnings
        """
        warnings = []

        # Check entity type
        entity_type = entity_data.get("entity_type", "").upper()
        if entity_type and entity_type not in self.ENTITY_TYPES:
            warnings.append(
                f"Invalid entity type '{entity_type}'. "
                f"Valid types: {', '.join(self.ENTITY_TYPES)}"
            )

        # Check for name conflicts
        name = entity_data.get("name", "")
        if name and context.lore_entities:
            existing_names = {
                e.get("name", "").lower() for e in context.lore_entities
            }
            if name.lower() in existing_names:
                warnings.append(
                    f"Entity name '{name}' already exists in the lore. "
                    "Consider a unique name or check for duplicates."
                )

        # Validate OCEAN traits for characters
        if entity_type == "CHARACTER":
            properties = entity_data.get("properties", {})
            for trait in self.OCEAN_TRAITS:
                value = properties.get(trait)
                if value is not None:
                    try:
                        float_val = float(value)
                        if not (0.0 <= float_val <= 1.0):
                            warnings.append(
                                f"OCEAN trait '{trait}' value {value} "
                                "should be between 0.0 and 1.0"
                            )
                    except (ValueError, TypeError):
                        warnings.append(
                            f"OCEAN trait '{trait}' has invalid value: {value}"
                        )

        # Check description length
        description = entity_data.get("description", "")
        if len(description) < 20:
            warnings.append(
                "Entity description is very short. "
                "Consider adding more detail for richness."
            )

        # Check for required fields
        if not name:
            warnings.append("Entity is missing a name.")
        if not entity_type:
            warnings.append("Entity is missing an entity_type.")

        return warnings
