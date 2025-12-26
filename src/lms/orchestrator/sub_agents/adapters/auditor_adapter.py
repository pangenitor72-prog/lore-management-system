# src/lms/orchestrator/sub_agents/adapters/auditor_adapter.py
"""
Adapter that wraps the existing AuditorAgent as a sub-agent.

This allows the orchestrator to leverage the AuditorAgent's
contradiction detection capabilities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ...models import Task, TaskResult, SubAgentContext, TaskStatus
from ...protocols import AgentBackend, SubAgentCapability
from ..base import BaseSubAgent

if TYPE_CHECKING:
    from src.lms.agents.auditor_agent import AuditorAgent


class AuditorAgentAdapter(BaseSubAgent):
    """
    Adapter that wraps AuditorAgent as a sub-agent.

    Enables the orchestrator to use the existing AuditorAgent for
    contradiction detection and lore auditing.
    """

    def __init__(
        self,
        auditor_agent: "AuditorAgent",
        agent_id: Optional[str] = None,
    ):
        """
        Initialize the adapter.

        Args:
            auditor_agent: The existing AuditorAgent to wrap
            agent_id: Optional custom agent ID
        """
        super().__init__(
            agent_id=agent_id,
            capabilities=[
                SubAgentCapability.CONTRADICTION_RESOLUTION,
                SubAgentCapability.FILE_ANALYSIS,
            ],
        )
        self._auditor_agent = auditor_agent

    @property
    def backend_type(self) -> AgentBackend:
        """AuditorAgent uses hybrid (rule-based + LLM)."""
        return AgentBackend.HYBRID

    async def _execute_impl(
        self, task: Task, context: SubAgentContext
    ) -> TaskResult:
        """
        Execute an audit task using the wrapped AuditorAgent.

        Supports:
        - Full audit (run_full_audit)
        - Entity-specific audit (audit_new_entity)
        - Personality consistency check
        """
        task_lower = f"{task.title} {task.description}".lower()

        try:
            # Determine which audit to run
            if "full" in task_lower or "all" in task_lower:
                # Run full audit
                contradictions = await self._auditor_agent.run_full_audit()
                return TaskResult(
                    task_id=task.task_id,
                    agent_id=self.agent_id,
                    status=TaskStatus.COMPLETED,
                    output={
                        "audit_type": "full",
                        "contradictions_found": len(contradictions),
                        "contradictions": [
                            self._format_contradiction(c) for c in contradictions
                        ],
                    },
                )

            elif "entity" in task_lower and task.lore_entities:
                # Audit specific entities
                results = []
                for entity_name in task.lore_entities:
                    # Get entity from context if available
                    entity_data = next(
                        (e for e in context.lore_entities if e.get("name") == entity_name),
                        {"name": entity_name},
                    )
                    audit_result = await self._auditor_agent.audit_new_entity(entity_data)
                    results.append({
                        "entity": entity_name,
                        "result": audit_result,
                    })

                return TaskResult(
                    task_id=task.task_id,
                    agent_id=self.agent_id,
                    status=TaskStatus.COMPLETED,
                    output={
                        "audit_type": "entity",
                        "entities_audited": len(results),
                        "results": results,
                    },
                )

            elif "pending" in task_lower or "review" in task_lower:
                # Get pending reviews
                pending = await self._auditor_agent.get_pending_reviews()
                return TaskResult(
                    task_id=task.task_id,
                    agent_id=self.agent_id,
                    status=TaskStatus.COMPLETED,
                    output={
                        "audit_type": "pending_reviews",
                        "pending_count": len(pending),
                        "pending": pending,
                    },
                )

            else:
                # Default: run full audit
                contradictions = await self._auditor_agent.run_full_audit()
                return TaskResult(
                    task_id=task.task_id,
                    agent_id=self.agent_id,
                    status=TaskStatus.COMPLETED,
                    output={
                        "audit_type": "full",
                        "contradictions_found": len(contradictions),
                        "contradictions": [
                            self._format_contradiction(c) for c in contradictions[:10]
                        ],
                    },
                )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=TaskStatus.FAILED,
                error_message=f"AuditorAgent failed: {e}",
            )

    def _format_contradiction(self, contradiction: Any) -> Dict[str, Any]:
        """Format a contradiction for output."""
        if hasattr(contradiction, "model_dump"):
            return contradiction.model_dump()
        elif isinstance(contradiction, dict):
            return contradiction
        else:
            return {"raw": str(contradiction)}

    async def can_handle(self, task: Task) -> bool:
        """
        Check if this adapter can handle the task.

        Handles tasks involving auditing, contradictions, or consistency checks.
        """
        if not await super().can_handle(task):
            return False

        audit_keywords = [
            "audit", "contradiction", "conflict", "inconsistent",
            "check", "validate", "verify", "review",
        ]
        combined = f"{task.title} {task.description}".lower()

        return any(kw in combined for kw in audit_keywords)

    async def estimate_effort(self, task: Task) -> Dict[str, Any]:
        """Estimate effort for an audit task."""
        task_lower = f"{task.title} {task.description}".lower()

        if "full" in task_lower:
            return {
                "complexity": "high",
                "estimated_tokens": 2000,
                "dependencies": 0,
            }
        else:
            return {
                "complexity": "medium",
                "estimated_tokens": 500,
                "dependencies": 0,
            }
