# src/lms/orchestrator/orchestrator.py
"""
Main Orchestrator Agent.

Coordinates sub-agents to complete complex tasks by decomposing them
into subtasks and managing execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .models import (
    Task,
    TaskResult,
    TaskType,
    TaskStatus,
    TaskPriority,
    SubAgentContext,
    OrchestratorState,
)
from .protocols import SubAgentProtocol, SubAgentCapability, AgentBackend
from .task_manager import TaskManager
from .context_provider import ContextProvider
from .sub_agents.llm_agent import LLMSubAgent
from .sub_agents.rule_agent import RuleBasedSubAgent
from .prompts.orchestrator_prompts import OrchestratorPrompts

if TYPE_CHECKING:
    from src.mantle.db.neo4j_adapter import Neo4jDatabase

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main orchestrator agent that coordinates sub-agents.

    Responsibilities:
    - Parse high-level tasks into sub-tasks
    - Create and manage sub-agents dynamically
    - Assign tasks based on capabilities
    - Monitor progress and aggregate results
    - Handle failures and retries
    """

    def __init__(
        self,
        project_root: str,
        gemini_api_key: Optional[str] = None,
        neo4j_db: Optional["Neo4jDatabase"] = None,
        max_concurrent_agents: int = 5,
    ):
        """
        Initialize the orchestrator.

        Args:
            project_root: Root directory of the project
            gemini_api_key: API key for Gemini (optional for rule-based only)
            neo4j_db: Neo4j database connection (optional)
            max_concurrent_agents: Maximum concurrent agent executions
        """
        self._project_root = project_root
        self._gemini_api_key = gemini_api_key
        self._db = neo4j_db
        self._max_concurrent = max_concurrent_agents

        # Core components
        self._task_manager = TaskManager()
        self._context_provider = ContextProvider(project_root, neo4j_db)

        # Agent pool
        self._agents: Dict[str, SubAgentProtocol] = {}
        self._agent_semaphore = asyncio.Semaphore(max_concurrent_agents)

        # State
        self._state = OrchestratorState()
        self._running = False
        self._execution_task: Optional[asyncio.Task] = None

    @property
    def state(self) -> OrchestratorState:
        """Get the current orchestrator state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if the orchestrator is running."""
        return self._running

    async def submit_task(
        self,
        title: str,
        description: str,
        task_type: TaskType = TaskType.DEVELOPMENT,
        priority: TaskPriority = TaskPriority.MEDIUM,
        relevant_files: Optional[List[str]] = None,
        lore_entities: Optional[List[str]] = None,
        required_capabilities: Optional[List[str]] = None,
        auto_decompose: bool = True,
    ) -> str:
        """
        Submit a high-level task for execution.

        The orchestrator will optionally decompose it into subtasks
        and coordinate execution.

        Args:
            title: Task title
            description: Detailed task description
            task_type: Type of task (development, lore, etc.)
            priority: Task priority
            relevant_files: Hint about relevant files
            lore_entities: Hint about relevant lore entities
            required_capabilities: Required agent capabilities
            auto_decompose: Whether to automatically decompose complex tasks

        Returns:
            The task ID
        """
        task = Task(
            task_type=task_type,
            title=title,
            description=description,
            priority=priority,
            relevant_files=relevant_files or [],
            lore_entities=lore_entities or [],
            required_capabilities=required_capabilities or [],
        )

        logger.info(f"Orchestrator: Task submitted - {title}")

        # Optionally decompose complex tasks
        if auto_decompose and self._gemini_api_key:
            subtasks = await self._decompose_task(task)
            if subtasks:
                # Add parent task first
                parent_id = await self._task_manager.add_task(task)
                # Add subtasks
                await self._task_manager.add_subtasks(parent_id, subtasks)
                return parent_id

        # Add as single task
        return await self._task_manager.add_task(task)

    async def run(self) -> Dict[str, Any]:
        """
        Run the orchestrator until all tasks are complete.

        Returns:
            Summary of execution
        """
        if self._running:
            raise RuntimeError("Orchestrator is already running")

        self._running = True
        self._state.session_started_at = datetime.now(timezone.utc)
        logger.info("Orchestrator: Starting execution loop")

        try:
            while self._running:
                # Get next available task
                task = await self._task_manager.get_next_task()

                if not task:
                    # Check if there is still pending work
                    if not await self._task_manager.has_pending_work():
                        break

                    # Wait for running tasks
                    await asyncio.sleep(0.1)
                    continue

                # Execute task with concurrency control
                asyncio.create_task(self._execute_task(task))

            # Wait for any remaining tasks
            while await self._task_manager.get_running_count() > 0:
                await asyncio.sleep(0.1)

            return await self.get_status()

        finally:
            self._running = False
            await self._cleanup_agents()

    async def run_single_task(self, task_id: str) -> TaskResult:
        """
        Run a single task by ID.

        Args:
            task_id: The task ID to run

        Returns:
            The task result
        """
        task = await self._task_manager.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        await self._execute_task(task)
        result = await self._task_manager.get_result(task_id)

        if not result:
            raise RuntimeError(f"Task {task_id} did not produce a result")

        return result

    async def stop(self) -> None:
        """Stop the orchestrator gracefully."""
        logger.info("Orchestrator: Stopping")
        self._running = False

    async def get_status(self) -> Dict[str, Any]:
        """
        Get current orchestrator status.

        Returns:
            Status dict with queue info and statistics
        """
        queue_status = await self._task_manager.get_queue_status()

        return {
            "session_id": self._state.session_id,
            "is_running": self._running,
            "queue_status": queue_status,
            "agents_active": len(
                [a for a in self._agents.values() if hasattr(a, "is_active") and a.is_active]
            ),
            "agents_total": len(self._agents),
            "duration_seconds": (
                datetime.now(timezone.utc) - self._state.session_started_at
            ).total_seconds(),
            "total_tokens_used": self._state.total_tokens_used,
        }

    async def _execute_task(self, task: Task) -> None:
        """
        Execute a single task with an appropriate agent.

        Args:
            task: The task to execute
        """
        async with self._agent_semaphore:
            await self._task_manager.mark_running(task.task_id)

            try:
                # Get or create appropriate agent
                agent = await self._get_agent_for_task(task)

                if not agent:
                    result = TaskResult(
                        task_id=task.task_id,
                        agent_id="orchestrator",
                        status=TaskStatus.FAILED,
                        error_message="No suitable agent found for task",
                    )
                else:
                    # Build context
                    context = await self._context_provider.build_context(task)

                    # Execute
                    result = await agent.execute(task, context)

                    # Update token count
                    self._state.total_tokens_used += result.tokens_used

                await self._task_manager.complete_task(result)
                self._state.total_tasks_processed += 1

                # Handle suggested follow-up tasks
                if result.suggested_tasks:
                    await self._handle_suggested_tasks(task, result.suggested_tasks)

            except Exception as e:
                logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)
                await self._task_manager.fail_task(
                    task.task_id, str(e), can_retry=True
                )

    async def _decompose_task(self, task: Task) -> List[Task]:
        """
        Decompose a high-level task into subtasks.

        Uses LLM to analyze the task and create a plan.

        Args:
            task: The task to decompose

        Returns:
            List of subtasks, or empty list if decomposition not needed
        """
        # Simple tasks don't need decomposition
        if len(task.description) < 100:
            return []

        if not self._gemini_api_key:
            return []

        # Create decomposer agent
        decomposer = LLMSubAgent(
            gemini_api_key=self._gemini_api_key,
            capabilities=[SubAgentCapability.FILE_ANALYSIS],
            system_prompt=OrchestratorPrompts.get_decomposition_prompt(),
            temperature=0.3,
        )

        # Build minimal context for decomposition
        context = SubAgentContext(project_root=self._project_root)

        # Create decomposition task
        decompose_task = Task(
            task_type=TaskType.ANALYSIS,
            title="Decompose task",
            description=f"Decompose this task into subtasks:\n\n"
            f"Title: {task.title}\n"
            f"Description: {task.description}",
            input_data={"parent_task": task.model_dump()},
        )

        try:
            result = await decomposer.execute(decompose_task, context)

            if result.status != TaskStatus.COMPLETED:
                return []

            # Extract subtasks from result
            subtasks = []
            raw_subtasks = result.output.get("subtasks", [])

            for st_data in raw_subtasks:
                if not isinstance(st_data, dict):
                    continue

                subtask = Task(
                    task_type=task.task_type,
                    title=st_data.get("title", "Subtask"),
                    description=st_data.get("description", ""),
                    priority=self._parse_priority(st_data.get("priority", "medium")),
                    required_capabilities=st_data.get("capabilities", []),
                    relevant_files=st_data.get("files", []),
                )
                subtasks.append(subtask)

            logger.info(
                f"Decomposed task '{task.title}' into {len(subtasks)} subtasks"
            )
            return subtasks

        except Exception as e:
            logger.warning(f"Task decomposition failed: {e}")
            return []

    def _parse_priority(self, priority_str: str) -> TaskPriority:
        """Parse priority string to enum."""
        mapping = {
            "critical": TaskPriority.CRITICAL,
            "high": TaskPriority.HIGH,
            "medium": TaskPriority.MEDIUM,
            "low": TaskPriority.LOW,
        }
        return mapping.get(priority_str.lower(), TaskPriority.MEDIUM)

    async def _get_agent_for_task(
        self, task: Task
    ) -> Optional[SubAgentProtocol]:
        """
        Get or create an agent suitable for the task.

        Args:
            task: The task to find an agent for

        Returns:
            A suitable agent, or None if none available
        """
        # Check existing agents
        for agent in self._agents.values():
            if await agent.can_handle(task):
                return agent

        # Create new agent based on task
        agent = await self._create_agent_for_task(task)
        if agent:
            self._agents[agent.agent_id] = agent

        return agent

    async def _create_agent_for_task(
        self, task: Task
    ) -> Optional[SubAgentProtocol]:
        """
        Create a new agent based on task requirements.

        Args:
            task: The task to create an agent for

        Returns:
            A new agent, or None if creation fails
        """
        # Determine capabilities needed based on task
        title_lower = task.title.lower()
        desc_lower = task.description.lower()
        combined = f"{title_lower} {desc_lower}"

        # Check if LLM is available
        if not self._gemini_api_key:
            # Fall back to rule-based agent
            return RuleBasedSubAgent(
                capabilities=[SubAgentCapability.FILE_ANALYSIS],
            )

        # Development tasks
        if task.task_type == TaskType.DEVELOPMENT:
            if "test" in combined:
                capabilities = [SubAgentCapability.TEST_WRITING]
            elif "doc" in combined:
                capabilities = [SubAgentCapability.DOCUMENTATION]
            elif "refactor" in combined:
                capabilities = [SubAgentCapability.CODE_REFACTORING]
            elif "review" in combined:
                capabilities = [SubAgentCapability.CODE_REVIEW]
            elif "convention" in combined or "check" in combined:
                capabilities = [SubAgentCapability.CONVENTION_CHECKING]
            else:
                capabilities = [SubAgentCapability.CODE_GENERATION]

            return LLMSubAgent(
                gemini_api_key=self._gemini_api_key,
                capabilities=capabilities,
            )

        # Lore management tasks
        elif task.task_type == TaskType.LORE_MANAGEMENT:
            if "entity" in combined or "character" in combined:
                capabilities = [SubAgentCapability.ENTITY_CREATION]
            elif "contradiction" in combined:
                capabilities = [SubAgentCapability.CONTRADICTION_RESOLUTION]
            elif "relationship" in combined:
                capabilities = [SubAgentCapability.RELATIONSHIP_MAPPING]
            else:
                capabilities = [SubAgentCapability.WORLD_BUILDING]

            return LLMSubAgent(
                gemini_api_key=self._gemini_api_key,
                capabilities=capabilities,
            )

        # Analysis tasks
        elif task.task_type == TaskType.ANALYSIS:
            return LLMSubAgent(
                gemini_api_key=self._gemini_api_key,
                capabilities=[SubAgentCapability.FILE_ANALYSIS],
            )

        # Default
        return LLMSubAgent(
            gemini_api_key=self._gemini_api_key,
            capabilities=[SubAgentCapability.CODE_GENERATION],
        )

    async def _handle_suggested_tasks(
        self, parent: Task, suggestions: List[Dict[str, Any]]
    ) -> None:
        """
        Handle follow-up tasks suggested by agents.

        Args:
            parent: The parent task
            suggestions: List of suggested task dicts
        """
        for suggestion in suggestions[:3]:  # Limit to 3 suggestions
            if not isinstance(suggestion, dict):
                continue

            task = Task(
                task_type=parent.task_type,
                title=suggestion.get("title", "Follow-up task"),
                description=suggestion.get("description", ""),
                priority=TaskPriority.LOW,
                depends_on=[parent.task_id],
            )

            await self._task_manager.add_task(task)
            logger.info(f"Added suggested task: {task.title}")

    async def _cleanup_agents(self) -> None:
        """Cleanup all agents."""
        for agent in self._agents.values():
            try:
                await agent.cleanup()
            except Exception as e:
                logger.warning(f"Agent cleanup failed: {e}")
        self._agents.clear()

    # =========================================================================
    # Agent Registration (for advanced usage)
    # =========================================================================

    def register_agent(self, agent: SubAgentProtocol) -> None:
        """
        Register an external agent with the orchestrator.

        Args:
            agent: The agent to register
        """
        self._agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.agent_id}")

    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_id: The agent ID to unregister

        Returns:
            True if agent was found and unregistered
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
            return True
        return False
