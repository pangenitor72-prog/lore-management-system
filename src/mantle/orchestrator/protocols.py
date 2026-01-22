# src/lms/orchestrator/protocols.py
"""
Protocols and interfaces for the Orchestrator Agent System.

Defines the contract that all sub-agents must implement.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Protocol, runtime_checkable

from .models import Task, TaskResult, SubAgentContext


class AgentBackend(str, Enum):
    """Backend type for sub-agents."""
    LLM = "llm"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"


class SubAgentCapability(str, Enum):
    """
    Capabilities that sub-agents can declare.

    The orchestrator uses these to match tasks to appropriate agents.
    """
    # Development capabilities
    CODE_GENERATION = "code_generation"
    CODE_REFACTORING = "code_refactoring"
    TEST_WRITING = "test_writing"
    DOCUMENTATION = "documentation"
    CODE_REVIEW = "code_review"
    BUG_FIXING = "bug_fixing"

    # Lore management capabilities
    ENTITY_CREATION = "entity_creation"
    CONTRADICTION_RESOLUTION = "contradiction_resolution"
    WORLD_BUILDING = "world_building"
    LORE_QUERY = "lore_query"
    RELATIONSHIP_MAPPING = "relationship_mapping"

    # Analysis capabilities
    FILE_ANALYSIS = "file_analysis"
    CODEBASE_EXPLORATION = "codebase_exploration"
    CONVENTION_CHECKING = "convention_checking"
    DEPENDENCY_ANALYSIS = "dependency_analysis"

    # Maintenance capabilities
    CLEANUP = "cleanup"
    MIGRATION = "migration"


@runtime_checkable
class SubAgentProtocol(Protocol):
    """
    Protocol defining the interface all sub-agents must implement.

    Sub-agents can be LLM-powered, rule-based, or hybrid. They must
    declare their capabilities and implement the execution interface.
    """

    @property
    def agent_id(self) -> str:
        """Unique identifier for this agent instance."""
        ...

    @property
    def capabilities(self) -> List[SubAgentCapability]:
        """List of capabilities this agent provides."""
        ...

    @property
    def backend_type(self) -> AgentBackend:
        """The backend type (LLM, rule-based, or hybrid)."""
        ...

    async def execute(self, task: Task, context: SubAgentContext) -> TaskResult:
        """
        Execute a task and return the result.

        Args:
            task: The task to execute
            context: Injected context (project files, lore, etc.)

        Returns:
            TaskResult with status, output, and any artifacts
        """
        ...

    async def can_handle(self, task: Task) -> bool:
        """
        Check if this agent can handle the given task.

        Args:
            task: The task to evaluate

        Returns:
            True if this agent can handle the task
        """
        ...

    async def estimate_effort(self, task: Task) -> Dict[str, Any]:
        """
        Estimate the effort required for a task.

        Returns:
            Dict with 'complexity', 'estimated_tokens', 'dependencies'
        """
        ...

    async def cleanup(self) -> None:
        """Cleanup resources after task completion."""
        ...


class OrchestratorProtocol(Protocol):
    """
    Protocol for the main orchestrator.

    Defines the interface for submitting and managing tasks.
    """

    async def submit_task(
        self,
        title: str,
        description: str,
        **kwargs: Any,
    ) -> str:
        """Submit a task and return its ID."""
        ...

    async def run(self) -> Dict[str, Any]:
        """Run the orchestrator until all tasks complete."""
        ...

    async def stop(self) -> None:
        """Stop the orchestrator gracefully."""
        ...

    async def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status."""
        ...
