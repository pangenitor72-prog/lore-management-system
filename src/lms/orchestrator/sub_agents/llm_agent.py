# src/lms/orchestrator/sub_agents/llm_agent.py
"""
LLM-powered sub-agent implementation.

Uses Google Gemini API for complex reasoning tasks like code generation,
documentation, and lore creation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from ..models import Task, TaskResult, SubAgentContext, TaskStatus
from ..protocols import AgentBackend, SubAgentCapability
from .base import BaseSubAgent

logger = logging.getLogger(__name__)

# Gemini import with graceful fallback
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


class LLMSubAgent(BaseSubAgent):
    """
    Sub-agent powered by Google Gemini LLM.

    Used for complex reasoning tasks that require natural language
    understanding and generation.
    """

    DEFAULT_MODEL = "gemini-2.0-flash"
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self,
        gemini_api_key: str,
        capabilities: List[SubAgentCapability],
        model_name: str = DEFAULT_MODEL,
        system_prompt: Optional[str] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        agent_id: Optional[str] = None,
    ):
        """
        Initialize the LLM sub-agent.

        Args:
            gemini_api_key: API key for Google Gemini
            capabilities: List of capabilities this agent provides
            model_name: Gemini model to use
            system_prompt: System prompt for the model
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            agent_id: Optional custom agent ID
        """
        super().__init__(agent_id=agent_id, capabilities=capabilities)

        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            )

        genai.configure(api_key=gemini_api_key)
        self._model = genai.GenerativeModel(model_name)
        self._model_name = model_name
        self._system_prompt = system_prompt or self._default_system_prompt()
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def backend_type(self) -> AgentBackend:
        """This is an LLM-powered agent."""
        return AgentBackend.LLM

    def _default_system_prompt(self) -> str:
        """Default system prompt for the agent."""
        return """You are a specialized sub-agent in the Lore Management System.
Your role is to complete assigned tasks accurately and thoroughly.

Guidelines:
- Follow project conventions and patterns
- Return structured JSON responses when requested
- If you encounter issues, describe them clearly
- Be concise but complete in your responses

When returning structured output, use this JSON format:
{
    "status": "success" | "failure",
    "output": { ... task-specific output ... },
    "artifacts": [ ... any files or entities created ... ],
    "warnings": [ ... any warnings or concerns ... ],
    "suggested_tasks": [ ... follow-up tasks if any ... ]
}"""

    async def _execute_impl(
        self, task: Task, context: SubAgentContext
    ) -> TaskResult:
        """Execute task using Gemini LLM."""
        # Build the prompt with context
        prompt = self._build_prompt(task, context)

        try:
            # Run LLM call in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": self._temperature,
                        "max_output_tokens": self._max_tokens,
                    },
                ),
            )

            # Extract response text
            response_text = response.text

            # Parse the response
            result_data = self._parse_response(response_text, task)

            # Determine status from response
            status = TaskStatus.COMPLETED
            if result_data.get("status") == "failure":
                status = TaskStatus.FAILED

            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=status,
                output=result_data.get("output", result_data),
                artifacts=result_data.get("artifacts", []),
                warnings=result_data.get("warnings", []),
                suggested_tasks=result_data.get("suggested_tasks", []),
                tokens_used=self._estimate_tokens(prompt, response_text),
            )

        except Exception as e:
            logger.error(f"LLM execution failed: {e}", exc_info=True)
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=TaskStatus.FAILED,
                error_message=str(e),
            )

    def _build_prompt(self, task: Task, context: SubAgentContext) -> str:
        """
        Build a comprehensive prompt with context.

        Includes system prompt, project context, relevant files,
        lore context, and task details.
        """
        parts = [self._system_prompt]

        # Add project context
        if context.claude_md_content:
            parts.append(
                f"\n=== PROJECT GUIDELINES (CLAUDE.md) ===\n"
                f"{context.claude_md_content[:3000]}"  # Truncate if too long
            )

        # Add architecture docs
        if context.architecture_docs:
            parts.append("\n=== ARCHITECTURE DOCUMENTATION ===")
            for doc_path, content in list(context.architecture_docs.items())[:3]:
                # Truncate each doc
                parts.append(f"\n--- {doc_path} ---\n{content[:1500]}")

        # Add relevant file contents
        if context.file_contents:
            parts.append("\n=== RELEVANT FILES ===")
            for path, content in context.file_contents.items():
                # Truncate each file
                truncated = content[:2000]
                if len(content) > 2000:
                    truncated += "\n... (truncated)"
                parts.append(f"\n--- {path} ---\n{truncated}")

        # Add lore context if applicable
        if context.lore_entities:
            parts.append("\n=== LORE CONTEXT ===")
            for entity in context.lore_entities[:5]:  # Limit to 5 entities
                name = entity.get("name", "Unknown")
                etype = entity.get("type", "Entity")
                desc = entity.get("description", "")[:200]
                parts.append(f"- [{etype}] {name}: {desc}")

        # Add task details
        parts.append(
            f"\n=== TASK ===\n"
            f"Title: {task.title}\n"
            f"Type: {task.task_type.value}\n"
            f"Description: {task.description}"
        )

        if task.input_data:
            parts.append(
                f"\nInput Data:\n{json.dumps(task.input_data, indent=2)}"
            )

        # Add output instructions
        parts.append(
            "\n=== OUTPUT INSTRUCTIONS ===\n"
            "Complete the task and return a JSON response with:\n"
            '{"status": "success/failure", "output": {...}, '
            '"artifacts": [...], "warnings": [...]}'
        )

        return "\n".join(parts)

    def _parse_response(self, text: str, task: Task) -> Dict[str, Any]:
        """
        Parse LLM response, extracting JSON if present.

        Tries multiple strategies to extract structured data.
        """
        # Strategy 1: Try to find JSON in markdown code block
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 2: Try to find any JSON block
        json_match = re.search(r"```\s*([\{\[].*?[\}\]])\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3: Try direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 4: Try to find JSON object in text
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback: Return as raw text
        return {
            "status": "success",
            "output": {"raw_response": text},
            "warnings": ["Could not parse structured response"],
        }

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """
        Rough token estimation.

        Uses a simple character-based heuristic.
        """
        return (len(prompt) + len(response)) // 4

    async def estimate_effort(self, task: Task) -> Dict[str, Any]:
        """Estimate effort for LLM tasks."""
        # Estimate based on description length and complexity indicators
        desc_length = len(task.description)
        complexity = "low"

        if desc_length > 500 or "refactor" in task.description.lower():
            complexity = "high"
        elif desc_length > 200:
            complexity = "medium"

        estimated_tokens = min(
            self._max_tokens,
            1000 + (desc_length // 2),
        )

        return {
            "complexity": complexity,
            "estimated_tokens": estimated_tokens,
            "dependencies": len(task.depends_on),
        }
