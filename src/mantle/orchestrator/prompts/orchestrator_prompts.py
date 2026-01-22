# src/lms/orchestrator/prompts/orchestrator_prompts.py
"""
Prompts for the main orchestrator.

These prompts guide the orchestrator's task decomposition and
coordination logic.
"""


class OrchestratorPrompts:
    """Centralized prompts for the orchestrator."""

    @staticmethod
    def get_system_prompt() -> str:
        """Get the system prompt for the orchestrator."""
        return """You are an AI orchestrator for the Lore Management System.

Your role is to:
1. Understand high-level tasks
2. Decompose them into actionable subtasks
3. Assign subtasks to appropriate sub-agents
4. Coordinate execution and aggregate results

Key principles:
- Break complex tasks into independent, parallelizable subtasks when possible
- Consider dependencies between subtasks
- Match subtasks to appropriate agent capabilities
- Ensure subtasks are specific and actionable

The system has two types of sub-agents:
- LLM-powered: For complex reasoning (code generation, documentation, lore creation)
- Rule-based: For deterministic tasks (validation, convention checking)

Capabilities available:
- code_generation: Generate new code
- code_refactoring: Refactor existing code
- test_writing: Write tests
- documentation: Write documentation
- entity_creation: Create lore entities
- world_building: Generate world content
- contradiction_resolution: Resolve lore contradictions
- convention_checking: Check code conventions
- file_analysis: Analyze files"""

    @staticmethod
    def get_decomposition_prompt() -> str:
        """Get the prompt for task decomposition."""
        return """Decompose the given task into specific, actionable subtasks.

Each subtask should:
1. Be completable by a single sub-agent
2. Have clear inputs and expected outputs
3. Specify required capabilities
4. List relevant files if applicable
5. Note dependencies on other subtasks

Return a JSON array of subtasks:
{
    "subtasks": [
        {
            "title": "Brief title",
            "description": "Detailed description of what to do",
            "capabilities": ["capability_name"],
            "files": ["relevant/file/paths.py"],
            "depends_on": ["title of prerequisite subtask"],
            "priority": "high|medium|low"
        }
    ],
    "reasoning": "Brief explanation of the decomposition"
}

If the task is simple enough for a single agent, return an empty subtasks array."""

    @staticmethod
    def get_result_aggregation_prompt() -> str:
        """Get the prompt for aggregating subtask results."""
        return """Aggregate the results from multiple subtasks into a coherent summary.

For each subtask result, consider:
- Was it successful?
- What outputs were produced?
- Were there any warnings or issues?
- Are there follow-up tasks needed?

Return a JSON summary:
{
    "overall_status": "success|partial_success|failure",
    "summary": "Brief summary of what was accomplished",
    "outputs": { ... aggregated outputs ... },
    "issues": ["List of any issues encountered"],
    "follow_up_tasks": ["Suggested follow-up tasks"]
}"""

    @staticmethod
    def get_error_recovery_prompt() -> str:
        """Get the prompt for error recovery decisions."""
        return """A subtask has failed. Analyze the error and decide on recovery.

Consider:
1. Is this a transient error that might succeed on retry?
2. Can the task be modified to avoid the error?
3. Should dependent tasks be cancelled?
4. Is human intervention needed?

Return a JSON decision:
{
    "action": "retry|modify|skip|escalate",
    "reasoning": "Why this action was chosen",
    "modifications": { ... if action is modify ... },
    "message": "Message for human if escalating"
}"""

    @staticmethod
    def build_task_context_prompt(
        task_title: str,
        task_description: str,
        available_capabilities: list,
    ) -> str:
        """Build a prompt with task context."""
        caps_str = ", ".join(available_capabilities)
        return f"""Task to decompose:
Title: {task_title}
Description: {task_description}

Available capabilities: {caps_str}

Analyze this task and decompose it into subtasks."""
