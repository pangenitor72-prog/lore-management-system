# src/lms/orchestrator/sub_agents/base.py
"""
Base class for sub-agents.

Provides common functionality while allowing subclasses to implement
specific execution logic.
"""

from __future__ import annotations

import logging
import traceback
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import Task, TaskResult, SubAgentContext, TaskStatus
from ..protocols import AgentBackend, SubAgentCapability

logger = logging.getLogger(__name__)


class BaseSubAgent(ABC):
    """
    Abstract base class for sub-agents.

    Uses the template method pattern to handle common pre/post processing
    while delegating core execution logic to subclasses.

    Subclasses must implement:
    - backend_type property
    - _execute_impl method
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        capabilities: Optional[List[SubAgentCapability]] = None,
    ):
        """
        Initialize the sub-agent.

        Args:
            agent_id: Unique identifier. Auto-generated if not provided.
            capabilities: List of capabilities this agent provides.
        """
        self._agent_id = agent_id or f"{self.__class__.__name__}_{uuid.uuid4().hex[:8]}"
        self._capabilities = capabilities or []
        self._is_active = False
        self._current_task_id: Optional[str] = None

    @property
    def agent_id(self) -> str:
        """Unique identifier for this agent instance."""
        return self._agent_id

    @property
    def capabilities(self) -> List[SubAgentCapability]:
        """List of capabilities this agent provides."""
        return self._capabilities

    @property
    def is_active(self) -> bool:
        """Whether the agent is currently executing a task."""
        return self._is_active

    @property
    @abstractmethod
    def backend_type(self) -> AgentBackend:
        """
        The backend type (LLM, rule-based, or hybrid).

        Subclasses must override this property.
        """
        ...

    async def execute(self, task: Task, context: SubAgentContext) -> TaskResult:
        """
        Execute a task and return the result.

        This is the template method that handles common pre/post processing.
        Subclasses should override _execute_impl for custom logic.

        Args:
            task: The task to execute
            context: Injected context (project files, lore, etc.)

        Returns:
            TaskResult with status, output, and any artifacts
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"Agent {self.agent_id} starting task {task.task_id}: {task.title}")

        self._is_active = True
        self._current_task_id = task.task_id

        try:
            # Pre-execution validation
            if not await self.can_handle(task):
                return TaskResult(
                    task_id=task.task_id,
                    agent_id=self.agent_id,
                    status=TaskStatus.FAILED,
                    error_message=f"Agent {self.agent_id} cannot handle this task type",
                )

            # Execute the task
            result = await self._execute_impl(task, context)

            # Calculate execution time
            end_time = datetime.now(timezone.utc)
            result.execution_time_ms = int(
                (end_time - start_time).total_seconds() * 1000
            )

            logger.info(
                f"Agent {self.agent_id} completed task {task.task_id}: "
                f"{result.status.value} in {result.execution_time_ms}ms"
            )
            return result

        except Exception as e:
            logger.error(
                f"Agent {self.agent_id} failed on task {task.task_id}: {e}",
                exc_info=True,
            )
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=TaskStatus.FAILED,
                error_message=str(e),
                error_traceback=traceback.format_exc(),
            )

        finally:
            self._is_active = False
            self._current_task_id = None

    @abstractmethod
    async def _execute_impl(
        self, task: Task, context: SubAgentContext
    ) -> TaskResult:
        """
        Implement the actual task execution logic.

        Subclasses must override this method.

        Args:
            task: The task to execute
            context: Injected context

        Returns:
            TaskResult with execution results
        """
        ...

    async def can_handle(self, task: Task) -> bool:
        """
        Check if this agent can handle the given task.

        Default implementation checks if any required capabilities match.

        Args:
            task: The task to evaluate

        Returns:
            True if this agent can handle the task
        """
        if not task.required_capabilities:
            # No specific capabilities required
            return True

        my_caps = {c.value for c in self._capabilities}
        return any(cap in my_caps for cap in task.required_capabilities)

    async def estimate_effort(self, task: Task) -> Dict[str, Any]:
        """
        Estimate the effort required for a task.

        Default implementation returns medium complexity.
        Subclasses can override for more accurate estimates.

        Args:
            task: The task to estimate

        Returns:
            Dict with complexity, estimated_tokens, dependencies
        """
        return {
            "complexity": "medium",
            "estimated_tokens": 1000,
            "dependencies": len(task.depends_on),
        }

    async def cleanup(self) -> None:
        """
        Cleanup resources after task completion.

        Subclasses can override to cleanup LLM sessions, connections, etc.
        """
        pass

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"agent_id={self.agent_id!r}, "
            f"backend={self.backend_type.value}, "
            f"capabilities={[c.value for c in self._capabilities]}"
            f")"
        )
