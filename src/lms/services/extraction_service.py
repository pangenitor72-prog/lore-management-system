import asyncio
import json
import re
import logging
from typing import Dict, Any, List

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

from src.lms.services.audit_log import AuditLogger

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    Service responsible for extracting structured nodes and relationships
    from raw lore text chunks using Gemini.

    This version is hardened, deterministic, async-safe, and guaranteed to
    return a valid extraction structure.
    """

    MODEL_NAME = "gemini-2.0-flash-exp"

    EXTRACTION_PROMPT = (
        "You are a Knowledge Graph Extractor for a D&D Campaign.\n"
        "Analyze the following text and extract ENTITIES and RELATIONSHIPS.\n\n"
        "**Entity Labels:** Character, Location, Item, Faction, Event, Concept\n\n"
        "**Output Format:**\n"
        "Return ONLY valid JSON with exactly two keys:\n"
        "{\"nodes\": [...], \"relationships\": [...]}.\n"
        "No markdown. No explanation. No commentary.\n\n"
        "**Rules:**\n"
        "1. IDs must be short and simple (e.g., \"Kael\").\n"
        "2. Every entity MUST have a 'content' field containing the VERBATIM narrative text that describes it.\n"
        "   - Do not summarize. Copy the exact sentences from the text.\n"
        "   - If an entity is mentioned but has no narrative text, do NOT create it.\n"
        "3. Include a 'description' property (summary) if possible, but 'content' is mandatory.\n"
        "4. Relationship types may include: LOCATED_IN, MEMBER_OF, OWNS, CREATED,\n"
        "   DEFEATED, ALLIED_WITH, ENEMY_OF, KNOWS, WIELDS, etc.\n"
        "5. If nothing is found, return: {\"nodes\": [], \"relationships\": []}\n"
        "6. CRITICAL: Output MUST be valid JSON.\n"
    )

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.MODEL_NAME)
        AuditLogger.log_sync(f"ExtractionService initialized with {self.MODEL_NAME}")

    # ------------------------------
    # JSON Parsing & Validation
    # ------------------------------

    def _clean_llm_text(self, text: str) -> str:
        """Remove markdown fences and extract only JSON-looking content."""
        cleaned = text.strip()

        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        return cleaned.strip()

    def _force_valid_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure nodes/relationships exist and are lists."""
        if not isinstance(data, dict):
            return {"nodes": [], "relationships": []}

        nodes = data.get("nodes", [])
        relationships = data.get("relationships", [])

        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(relationships, list):
            relationships = []

        # Sanitize nodes
        clean_nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue

            nid = node.get("id")
            label = node.get("label")
            
            # Check properties dict
            props = node.get("properties", {})
            if not isinstance(props, dict):
                props = {}

            # Look for 'content' in top-level node OR properties
            content = node.get("content") or props.get("content")
            
            if not isinstance(nid, str) or not nid.strip():
                continue
            if not isinstance(label, str) or not label.strip():
                continue
                
            # STRICT: Content is mandatory
            if not content or not isinstance(content, str) or not content.strip():
                 continue

            # Ensure content is in properties
            props["content"] = content.strip()

            clean_nodes.append({"id": nid.strip(), "label": label.strip(), "properties": props})

        # Sanitize relationships
        clean_rels = []
        for rel in relationships:
            if not isinstance(rel, dict):
                continue

            s = rel.get("source")
            t = rel.get("target")
            rtype = rel.get("type")

            if not all(isinstance(x, str) and x.strip() for x in [s, t, rtype]):
                continue

            clean_rels.append({"source": s.strip(), "target": t.strip(), "type": rtype.strip()})

        return {"nodes": clean_nodes, "relationships": clean_rels}

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM response into valid extraction JSON."""
        cleaned = self._clean_llm_text(text)

        # Try direct JSON load
        try:
            data = json.loads(cleaned)
            return self._force_valid_structure(data)
        except json.JSONDecodeError:
            pass

        # Regex fallback
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                data = json.loads(match.group())
                return self._force_valid_structure(data)
            except json.JSONDecodeError:
                pass

        # Nothing worked → return empty
        AuditLogger.log_sync("ExtractionService: Failed to parse JSON from Gemini", level=logging.ERROR)
        return {"nodes": [], "relationships": []}

    # ------------------------------
    # Extraction
    # ------------------------------

    async def extract_graph_from_chunk(self, chunk: str, index: int) -> Dict[str, Any]:
        """
        Extract entities and relationships from a single text chunk.
        Uses thread pool to avoid blocking FastAPI's event loop.
        """
        logger.info(f"[EXTRACT] Starting extraction for chunk {index}, length={len(chunk)}")

        prompt = f"{self.EXTRACTION_PROMPT}\n\nTEXT:\n{chunk}"

        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "max_output_tokens": 2048
                    },
                )
            )

            logger.info(f"[EXTRACT] Gemini response for chunk {index}: {response.text}")
            return self._parse_json_response(response.text)

        except GoogleAPIError as e:
            await AuditLogger.log(f"Extraction chunk {index} Gemini API error: {e}", level=logging.ERROR)
            return {"nodes": [], "relationships": []}

        except Exception as e:
            await AuditLogger.log(f"Extraction chunk {index} unexpected error: {e}", level=logging.ERROR)
            return {"nodes": [], "relationships": []}