"""
SemanticAuditor

AI-based semantic contradiction detection and personality consistency checks
using Gemini models.

Responsibilities:
- Compare two entity records (dicts) and propose contradictions
- Apply Gospel Principle via confidence/trust weighting
- Score each contradiction's reliability
- Suggest possible resolutions when confidence is high enough
- Check personality consistency for NPC behaviors using OCEAN profiles

NOTE:
- This class does NOT directly touch Neo4j; it just uses the db reference
  for potential future extensions and consistency with the rest of the
  architecture.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import json
import re
import logging
import asyncio

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

from src.mantle.db.neo4j_adapter import Neo4jDatabase
from src.mantle.services.audit_log import AuditLogger
from src.mantle.prompts import AuditorPrompts
from src.mantle.core.models import OCEANProfile, Contradiction

logger = logging.getLogger(__name__)


class SemanticAuditor:
    """
    Performs AI-based semantic contradiction detection using Gemini.
    """

    def __init__(self, db: Neo4jDatabase, gemini_api_key: str):
        self.db = db
        genai.configure(api_key=gemini_api_key)

        # Explicit model handles for clarity
        self.flash_model = genai.GenerativeModel("gemini-2.0-flash")
        self.pro_model = genai.GenerativeModel("gemini-exp-1206")

    # ============================================================
    # PUBLIC API — CONTRADICTION DETECTION
    # ============================================================

    def detect_contradictions(
        self,
        entity_a: Dict[str, Any],
        entity_b: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Finds, scores, and suggests resolutions for AI-detected contradictions
        between two entities.

        Returns:
            List[Dict[str, Any]] — each dict is a contradiction record with:
              - type
              - severity
              - description
              - entity_ids
              - evidence
              - confidence
              - scoring_reasoning
              - possible_resolutions
              - resolution_reasoning
        """
        a_name = entity_a.get("name", "?")
        b_name = entity_b.get("name", "?")

        # Extract confidence levels for Gospel Principle (trust scoring)
        confidence_a = (
            entity_a.get("confidence_level")
            or entity_a.get("confidence")
            or entity_a.get("properties", {}).get("confidence_level")
            or "ai_generated"
        )
        confidence_b = (
            entity_b.get("confidence_level")
            or entity_b.get("confidence")
            or entity_b.get("properties", {}).get("confidence_level")
            or "ai_generated"
        )

        AuditLogger.log_sync(
            f"AI-DETECT: Comparing {a_name} (trust: {confidence_a}) "
            f"vs {b_name} (trust: {confidence_b})"
        )

        # Build detection prompt with trust scores (Gospel Principle)
        prompt = AuditorPrompts.build_detection_prompt(
            json.dumps(entity_a, indent=2),
            json.dumps(entity_b, indent=2),
            confidence_a=confidence_a,
            confidence_b=confidence_b,
        )

        try:
            resp = self.flash_model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "max_output_tokens": 4096,
                },
            )
            raw_text = getattr(resp, "text", "") or ""
            contradictions = self._parse_json_array(raw_text)

            final_contradictions: List[Dict[str, Any]] = []
            for raw_con in contradictions:
                # Normalize structure
                normalized = self._normalize_contradiction(
                    raw_con, entity_a, entity_b
                )

                scored_con = self._score_contradiction_confidence(
                    normalized, entity_a, entity_b
                )
                resolved_con = self._suggest_resolutions(
                    scored_con, entity_a, entity_b
                )
                final_contradictions.append(resolved_con)

            return final_contradictions

        except GoogleAPIError as e:
            AuditLogger.log_sync(
                f"AI detection Gemini API error: {e}",
                level=logging.ERROR,
            )
            return []
        except json.JSONDecodeError as e:
            AuditLogger.log_sync(
                f"AI detection JSON parsing error: {e}",
                level=logging.ERROR,
            )
            return []
        except Exception as e:
            AuditLogger.log_sync(
                f"AI detection unexpected error: {e}",
                level=logging.ERROR,
            )
            return []

    # ============================================================
    # INTERNAL HELPERS — CONTRADICTION PIPELINE
    # ============================================================

    def _parse_json_array(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse a JSON array from the LLM response.

        Accepts:
        - A top-level JSON array
        - A top-level JSON object with key "contradictions": [...]
        - Otherwise returns []
        """
        if not text:
            return []

        # Try to find a JSON array first
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            snippet = m.group()
            try:
                data = json.loads(snippet)
                if isinstance(data, list):
                    return data
                return []
            except json.JSONDecodeError:
                AuditLogger.log_sync(
                    "Failed to parse list from LLM response for contradictions."
                )
                return []

        # Fallback: try to interpret a dict with "contradictions" key
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return []

        try:
            obj = json.loads(m.group())
        except json.JSONDecodeError:
            AuditLogger.log_sync(
                "Failed to parse dict from LLM response for contradictions."
            )
            return []

        if isinstance(obj, dict) and "contradictions" in obj:
            arr = obj["contradictions"]
            return arr if isinstance(arr, list) else []

        return []

    def _normalize_contradiction(
        self,
        raw: Dict[str, Any],
        entity_a: Dict[str, Any],
        entity_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Normalize the raw LLM contradiction into a consistent shape.
        Does NOT turn it into a Contradiction model yet—stays as a dict.
        """
        # Try to infer involved entity canon_ids if present
        entity_ids = raw.get("entity_ids")
        if not isinstance(entity_ids, list):
            entity_ids = []

        # Ensure required keys exist with safe defaults
        normalized: Dict[str, Any] = {
            "type": raw.get("type")
            or raw.get("contradiction_type")
            or "SEMANTIC_CONTRADICTION",
            "severity": raw.get("severity") or "MEDIUM",
            "description": raw.get("description")
            or raw.get("message")
            or "Semantic contradiction detected by LLM.",
            "entity_ids": entity_ids,
            "evidence": raw.get("evidence") or raw.get("details") or {},
        }

        # Preserve any other fields the model produced
        for k, v in raw.items():
            if k not in normalized:
                normalized[k] = v

        # If entity_ids is empty, fall back to names/ids (for debugging)
        if not normalized["entity_ids"]:
            a_id = entity_a.get("canon_id") or entity_a.get("id")
            b_id = entity_b.get("canon_id") or entity_b.get("id")
            ids = [x for x in (a_id, b_id) if x]
            normalized["entity_ids"] = ids

        return normalized

    def _score_contradiction_confidence(
        self,
        contradiction: Dict[str, Any],
        entity_a: Dict[str, Any],
        entity_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Use gemini-2.5-pro to assign a confidence score to the contradiction.

        Implements the Gospel Principle by passing trust scores into the prompt.
        """
        desc_preview = contradiction.get("description", "N/A")[:80]
        AuditLogger.log_sync(f"AI-SCORE: Scoring contradiction: {desc_preview}...")

        # Extract confidence levels again (defensive; we don't assume prior state)
        confidence_a = (
            entity_a.get("confidence_level")
            or entity_a.get("confidence")
            or entity_a.get("properties", {}).get("confidence_level")
            or "ai_generated"
        )
        confidence_b = (
            entity_b.get("confidence_level")
            or entity_b.get("confidence")
            or entity_b.get("properties", {}).get("confidence_level")
            or "ai_generated"
        )

        prompt = AuditorPrompts.build_score_confidence_prompt(
            json.dumps(entity_a, indent=2),
            json.dumps(entity_b, indent=2),
            json.dumps(contradiction, indent=2),
            confidence_a=confidence_a,
            confidence_b=confidence_b,
        )

        try:
            resp = self.pro_model.generate_content(
                prompt,
                generation_config={"temperature": 0.0},
            )
            raw_text = getattr(resp, "text", "") or ""

            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                score_data = json.loads(match.group())
                contradiction["confidence"] = float(score_data.get("confidence", 0.0))
                contradiction["scoring_reasoning"] = score_data.get(
                    "reasoning", "No reasoning provided."
                )
            else:
                contradiction["confidence"] = 0.0
                contradiction["scoring_reasoning"] = (
                    "Failed to parse pro-model scoring response."
                )

        except GoogleAPIError as e:
            AuditLogger.log_sync(
                f"AI scoring Gemini API error: {e}",
                level=logging.ERROR,
            )
            contradiction["confidence"] = 0.0
            contradiction["scoring_reasoning"] = (
                f"Gemini API error during scoring: {e}"
            )
        except json.JSONDecodeError as e:
            AuditLogger.log_sync(
                f"AI scoring JSON parsing error: {e}",
                level=logging.ERROR,
            )
            contradiction["confidence"] = 0.0
            contradiction["scoring_reasoning"] = (
                f"JSON parsing error during scoring: {e}"
            )
        except Exception as e:
            AuditLogger.log_sync(
                f"AI scoring unexpected error: {e}",
                level=logging.ERROR,
            )
            contradiction["confidence"] = 0.0
            contradiction["scoring_reasoning"] = (
                f"Unexpected error during scoring: {e}"
            )

        return contradiction

    def _suggest_resolutions(
        self,
        contradiction: Dict[str, Any],
        entity_a: Dict[str, Any],
        entity_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Use gemini-2.5-pro to suggest resolutions for high-confidence contradictions.
        """
        confidence = float(contradiction.get("confidence", 0.0))

        if confidence < 0.7:
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = (
                "Confidence score too low to suggest resolution."
            )
            return contradiction

        desc_preview = contradiction.get("description", "N/A")[:80]
        AuditLogger.log_sync(
            f"AI-RESOLVE: Suggesting resolutions for: {desc_preview}..."
        )

        prompt = AuditorPrompts.build_suggest_resolution_prompt(
            json.dumps(entity_a, indent=2),
            json.dumps(entity_b, indent=2),
            json.dumps(contradiction, indent=2),
            confidence,
        )

        try:
            resp = self.pro_model.generate_content(
                prompt,
                generation_config={"temperature": 0.2},
            )
            raw_text = getattr(resp, "text", "") or ""
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)

            if match:
                res_data = json.loads(match.group())
                contradiction["possible_resolutions"] = res_data.get(
                    "possible_resolutions", []
                )
                contradiction["resolution_reasoning"] = res_data.get(
                    "reasoning", "No reasoning provided."
                )
            else:
                contradiction["possible_resolutions"] = []
                contradiction["resolution_reasoning"] = (
                    "Failed to parse pro-model resolution response."
                )

        except GoogleAPIError as e:
            AuditLogger.log_sync(
                f"AI resolution Gemini API error: {e}",
                level=logging.ERROR,
            )
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = (
                f"Gemini API error during resolution suggestion: {e}"
            )
        except json.JSONDecodeError as e:
            AuditLogger.log_sync(
                f"AI resolution JSON parsing error: {e}",
                level=logging.ERROR,
            )
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = (
                f"JSON parsing error during resolution suggestion: {e}"
            )
        except Exception as e:
            AuditLogger.log_sync(
                f"AI resolution unexpected error: {e}",
                level=logging.ERROR,
            )
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = (
                f"Unexpected error during resolution suggestion: {e}"
            )

        return contradiction

    # ============================================================
    # SHARED JSON HELPER
    # ============================================================

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        Parses JSON from a string, handling Markdown code blocks.
        Returns {} on failure.
        """
        if not text:
            return {}

        # Try to find JSON block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return {}

        return {}

    # ============================================================
    # PERSONALITY CONSISTENCY CHECK (ASYNC)
    # ============================================================

    async def check_personality_consistency(
        self,
        entity_name: str,
        old_personality: OCEANProfile,
        new_behavior_description: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if new behavior is consistent with established personality.

        Returns a contradiction-like dict if inconsistent, otherwise None.
        """
        # Use async logger for async method
        await AuditLogger.log(
            f"Checking personality consistency for: {entity_name}"
        )

        prompt = f"""
An NPC named {entity_name} has an established personality profile:
- Openness: {old_personality.openness:.1f}
- Conscientiousness: {old_personality.conscientiousness:.1f}
- Extraversion: {old_personality.extraversion:.1f}
- Agreeableness: {old_personality.agreeableness:.1f}
- Neuroticism: {old_personality.neuroticism:.1f}

Behavioral Summary: {old_personality.get_behavioral_summary()}

New behavior observed: {new_behavior_description}

Is this behavior consistent with their established personality?
Consider that people can act out of character under stress, but extreme contradictions 
(reserved person suddenly very chatty, organized person suddenly chaotic) are inconsistent.

Return ONLY valid JSON:
{{
  "consistent": true/false,
  "explanation": "Why this is/isn't consistent"
}}
"""

        try:
            # Run pro_model call in a thread so we don't block the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.pro_model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.1},
                ),
            )

            result = self._parse_json_response(getattr(response, "text", "") or "")

            if not result.get("consistent", True):
                await AuditLogger.log(
                    f"Personality inconsistency detected for {entity_name}"
                )
                return {
                    "type": "personality_inconsistency",
                    "severity": "MEDIUM",
                    "description": (
                        f"{entity_name}: "
                        f"{result.get('explanation', 'Personality inconsistency detected')}"
                    ),
                    "entity": entity_name,
                }

        except GoogleAPIError as e:
            await AuditLogger.log(
                f"Personality consistency Gemini API error: {e}",
                level=logging.ERROR,
            )
        except json.JSONDecodeError as e:
            await AuditLogger.log(
                f"Personality consistency JSON parsing error: {e}",
                level=logging.ERROR,
            )
        except Exception as e:
            await AuditLogger.log(
                f"Personality consistency unexpected error: {e}",
                level=logging.ERROR,
            )

        return None