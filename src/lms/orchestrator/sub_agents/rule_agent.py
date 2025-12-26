# src/lms/orchestrator/sub_agents/rule_agent.py
"""
Rule-based sub-agent implementation.

Uses deterministic rules for tasks like validation, convention checking,
and template-based generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..models import Task, TaskResult, SubAgentContext, TaskStatus
from ..protocols import AgentBackend, SubAgentCapability
from .base import BaseSubAgent

logger = logging.getLogger(__name__)


# Type alias for rule functions
RuleCondition = Callable[[Task, SubAgentContext], bool]
RuleAction = Callable[[Task, SubAgentContext], Dict[str, Any]]


@dataclass
class Rule:
    """
    A single rule for the rule-based agent.

    Rules have a condition that determines if they apply,
    and an action that produces output.
    """

    name: str
    condition: RuleCondition
    action: RuleAction
    priority: int = 0
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def matches(self, task: Task, context: SubAgentContext) -> bool:
        """Check if this rule matches the given task and context."""
        try:
            return self.condition(task, context)
        except Exception as e:
            logger.warning(f"Rule '{self.name}' condition failed: {e}")
            return False

    def apply(self, task: Task, context: SubAgentContext) -> Dict[str, Any]:
        """Apply this rule and return the result."""
        return self.action(task, context)


class RuleBasedSubAgent(BaseSubAgent):
    """
    Sub-agent using deterministic rules.

    Used for:
    - File validation
    - Schema enforcement
    - Convention checking
    - Template-based generation
    - Simple transformations

    Rules are executed in priority order (highest first).
    """

    def __init__(
        self,
        capabilities: List[SubAgentCapability],
        rules: Optional[List[Rule]] = None,
        agent_id: Optional[str] = None,
        stop_on_first_match: bool = False,
    ):
        """
        Initialize the rule-based sub-agent.

        Args:
            capabilities: List of capabilities this agent provides
            rules: List of rules to apply
            agent_id: Optional custom agent ID
            stop_on_first_match: If True, stop after first matching rule
        """
        super().__init__(agent_id=agent_id, capabilities=capabilities)
        self._rules = sorted(rules or [], key=lambda r: -r.priority)
        self._stop_on_first_match = stop_on_first_match

    @property
    def backend_type(self) -> AgentBackend:
        """This is a rule-based agent."""
        return AgentBackend.RULE_BASED

    @property
    def rules(self) -> List[Rule]:
        """Get the list of rules."""
        return self._rules.copy()

    def add_rule(self, rule: Rule) -> None:
        """
        Add a new rule and re-sort by priority.

        Args:
            rule: The rule to add
        """
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)

    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a rule by name.

        Args:
            rule_name: Name of the rule to remove

        Returns:
            True if rule was found and removed
        """
        original_len = len(self._rules)
        self._rules = [r for r in self._rules if r.name != rule_name]
        return len(self._rules) < original_len

    async def _execute_impl(
        self, task: Task, context: SubAgentContext
    ) -> TaskResult:
        """Execute matching rules in priority order."""
        matched_rules: List[str] = []
        combined_output: Dict[str, Any] = {}
        warnings: List[str] = []
        artifacts: List[Dict[str, Any]] = []

        for rule in self._rules:
            try:
                if rule.matches(task, context):
                    matched_rules.append(rule.name)
                    result = rule.apply(task, context)

                    # Merge results
                    if isinstance(result, dict):
                        # Extract special keys
                        if "warnings" in result:
                            warnings.extend(result.pop("warnings"))
                        if "artifacts" in result:
                            artifacts.extend(result.pop("artifacts"))

                        combined_output.update(result)

                    if self._stop_on_first_match:
                        break

            except Exception as e:
                warning = f"Rule '{rule.name}' failed: {e}"
                logger.warning(warning)
                warnings.append(warning)

        if not matched_rules:
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=TaskStatus.COMPLETED,
                output={"message": "No matching rules found"},
                warnings=["No rules matched the task criteria"],
            )

        return TaskResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=TaskStatus.COMPLETED,
            output={
                "matched_rules": matched_rules,
                "results": combined_output,
            },
            artifacts=artifacts,
            warnings=warnings,
        )

    async def estimate_effort(self, task: Task) -> Dict[str, Any]:
        """
        Estimate effort for rule-based tasks.

        Rule-based agents are fast and deterministic.
        """
        return {
            "complexity": "low",
            "estimated_tokens": 0,  # No LLM tokens
            "dependencies": len(task.depends_on),
        }


# Utility functions for creating common rules


def create_file_extension_rule(
    name: str,
    extensions: List[str],
    action: RuleAction,
    priority: int = 0,
) -> Rule:
    """
    Create a rule that matches files with specific extensions.

    Args:
        name: Rule name
        extensions: List of file extensions (e.g., [".py", ".pyi"])
        action: Action to perform
        priority: Rule priority
    """

    def condition(task: Task, context: SubAgentContext) -> bool:
        for path in context.file_contents.keys():
            if any(path.endswith(ext) for ext in extensions):
                return True
        return False

    return Rule(
        name=name,
        condition=condition,
        action=action,
        priority=priority,
        tags=["file_extension"],
    )


def create_keyword_rule(
    name: str,
    keywords: List[str],
    action: RuleAction,
    priority: int = 0,
    case_sensitive: bool = False,
) -> Rule:
    """
    Create a rule that matches tasks containing specific keywords.

    Args:
        name: Rule name
        keywords: List of keywords to match in title or description
        action: Action to perform
        priority: Rule priority
        case_sensitive: Whether to match case-sensitively
    """

    def condition(task: Task, context: SubAgentContext) -> bool:
        text = f"{task.title} {task.description}"
        if not case_sensitive:
            text = text.lower()
            check_keywords = [k.lower() for k in keywords]
        else:
            check_keywords = keywords

        return any(kw in text for kw in check_keywords)

    return Rule(
        name=name,
        condition=condition,
        action=action,
        priority=priority,
        tags=["keyword"],
    )


def create_task_type_rule(
    name: str,
    task_types: List[str],
    action: RuleAction,
    priority: int = 0,
) -> Rule:
    """
    Create a rule that matches specific task types.

    Args:
        name: Rule name
        task_types: List of task type values to match
        action: Action to perform
        priority: Rule priority
    """

    def condition(task: Task, context: SubAgentContext) -> bool:
        return task.task_type.value in task_types

    return Rule(
        name=name,
        condition=condition,
        action=action,
        priority=priority,
        tags=["task_type"],
    )
