# src/lms/orchestrator/sub_agents/adapters/query_adapter.py
"""
Adapter that wraps the existing QueryAgent as a sub-agent.

This allows the orchestrator to leverage the QueryAgent's RAG
capabilities for lore queries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ...models import Task, TaskResult, SubAgentContext, TaskStatus
from ...protocols import AgentBackend, SubAgentCapability
from ..base import BaseSubAgent

if TYPE_CHECKING:
    from src.mantle.agents.query_agent import QueryAgent


class QueryAgentAdapter(BaseSubAgent):
    """
    Adapter that wraps QueryAgent as a sub-agent.

    Enables the orchestrator to use the existing QueryAgent for
    lore queries without duplicating its functionality.
    """

    def __init__(
        self,
        query_agent: "QueryAgent",
        agent_id: Optional[str] = None,
    ):
        """
        Initialize the adapter.

        Args:
            query_agent: The existing QueryAgent to wrap
            agent_id: Optional custom agent ID
        """
        super().__init__(
            agent_id=agent_id,
            capabilities=[
                SubAgentCapability.LORE_QUERY,
                SubAgentCapability.CODEBASE_EXPLORATION,
            ],
        )
        self._query_agent = query_agent

    @property
    def backend_type(self) -> AgentBackend:
        """QueryAgent uses LLM (Gemini)."""
        return AgentBackend.LLM

    async def _execute_impl(
        self, task: Task, context: SubAgentContext
    ) -> TaskResult:
        """
        Execute a query using the wrapped QueryAgent.

        Expects task.description to contain the query.
        """
        query = task.description

        # Add any context hints to the query
        if task.lore_entities:
            entities_hint = ", ".join(task.lore_entities)
            query = f"{query}\n\nRelevant entities: {entities_hint}"

        try:
            # Use the QueryAgent's ask method
            answer = await self._query_agent.ask(query)

            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=TaskStatus.COMPLETED,
                output={
                    "query": task.description,
                    "answer": answer,
                    "source": "QueryAgent",
                },
            )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=TaskStatus.FAILED,
                error_message=f"QueryAgent failed: {e}",
            )

    async def can_handle(self, task: Task) -> bool:
        """
        Check if this adapter can handle the task.

        Handles tasks that involve querying lore or asking questions.
        """
        # Check capabilities first
        if not await super().can_handle(task):
            return False

        # Also match on keywords
        query_keywords = ["query", "ask", "find", "search", "what", "who", "where", "when", "how"]
        combined = f"{task.title} {task.description}".lower()

        return any(kw in combined for kw in query_keywords)

    async def estimate_effort(self, task: Task) -> Dict[str, Any]:
        """Estimate effort for a query task."""
        return {
            "complexity": "low",
            "estimated_tokens": 500,
            "dependencies": 0,
        }
