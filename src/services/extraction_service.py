import asyncio
import json
import re
import logging
from typing import Dict, Any

import google.generativeai as genai

from src.services.audit_log import AuditLogger

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    A dedicated service for interacting with the Google Gemini API to extract
    structured data (nodes and relationships) from text chunks.
    This service encapsulates the non-deterministic LLM call, separating it
    from the main ingestion pipeline logic.
    """

    EXTRACTION_PROMPT = """You are a Knowledge Graph Extractor for a D&D Campaign.
Analyze the following text and extract entities and relationships.

**Entities to Extract (Labels):**
- Character (NPCs, PCs, villains)
- Location (Places, regions, buildings)
- Item (Weapons, artifacts, objects)
- Faction (Organizations, groups, cults)
- Event (Battles, ceremonies, historical moments)
- Concept (Abstract ideas, magic types, prophecies, curses)

**Output Format:**
Return ONLY a valid JSON object with two keys: "nodes" and "relationships".
Do NOT include markdown code fences or any other text.

Example:
{"nodes": [{"id": "Kael", "label": "Character", "properties": {"class": "Paladin", "description": "A sworn protector"}}, {"id": "Void Corruption", "label": "Concept", "properties": {"type": "Curse"}}], "relationships": [{"source": "Kael", "target": "Void Corruption", "type": "VULNERABLE_TO"}]}

**Rules:**
1. Use consistent, simple IDs (e.g., "Kael" not "Kael the Paladin").
2. Always include a "description" in properties when possible.
3. Extract relationship types like: LOCATED_IN, MEMBER_OF, OWNS, CREATED, DEFEATED, ALLIED_WITH, ENEMY_OF, KNOWS, WIELDS, etc.
4. If no entities found, return: {"nodes": [], "relationships": []}
5. CRITICAL: Return ONLY valid JSON. No markdown, no explanations."""

    def __init__(self, api_key: str):
        """
        Initializes the ExtractionService and configures the Gemini model.
        Args:
            api_key: The API key for the Google Gemini service.
        """
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from AI response with robust error recovery."""
        cleaned = text.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Regex fallback
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Fallback for trailing commas
        fixed = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        return {"nodes": [], "relationships": []}

    async def extract_graph_from_chunk(self, chunk: str, index: int) -> Dict[str, Any]:
        """
        Extracts entities and relationships from a single text chunk using Gemini.
        The actual model call is run in an executor to avoid blocking the event loop.
        Args:
            chunk: The text chunk to process.
            index: The index of the chunk, for logging purposes.
        Returns:
            A dictionary containing the extracted 'nodes' and 'relationships'.
        """
        loop = asyncio.get_event_loop()
        try:
            full_prompt = self.EXTRACTION_PROMPT + "\n\nTEXT:\n" + chunk
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    full_prompt,
                    generation_config={"temperature": 0.1}
                )
            )
            return self._parse_json_response(response.text)
        except Exception as e:
            await AuditLogger.log(f"Chunk {index + 1} extraction failed: {str(e)}", level=logging.ERROR)
            return {"nodes": [], "relationships": []}
