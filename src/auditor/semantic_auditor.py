from typing import List, Dict, Any, Optional
import json
import re
import logging
import asyncio
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from neo4j.exceptions import Neo4jError

from src.db.neo4j_adapter import Neo4jDatabase
from src.services.audit_log import AuditLogger
from src.prompts import AuditorPrompts
from src.core.models import Contradiction, OCEANProfile

logger = logging.getLogger(__name__)

class SemanticAuditor:
    """
    Performs AI-based semantic contradiction detection.
    """

    def __init__(self, db: Neo4jDatabase, gemini_api_key: str):
        self.db = db
        genai.configure(api_key=gemini_api_key)
        self.flash = genai.GenerativeModel("gemini-2.5-flash")
        self.pro = genai.GenerativeModel("gemini-2.5-pro")

    def detect_contradictions(self, entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Finds, Scores, and suggests Resolutions for AI-detected contradictions.
        
        Implements the Gospel Principle: Extracts trust scores from entities
        and passes them to the prompt so the LLM knows which entity is more authoritative.
        """
        a_name, b_name = entity_a.get("name","?"), entity_b.get("name","?")
        
        # Extract confidence levels for Gospel Principle (trust scoring)
        # Check multiple possible property names for confidence level
        confidence_a = (
            entity_a.get("confidence_level") or 
            entity_a.get("confidence") or 
            entity_a.get("properties", {}).get("confidence_level") or
            "ai_generated"
        )
        confidence_b = (
            entity_b.get("confidence_level") or 
            entity_b.get("confidence") or 
            entity_b.get("properties", {}).get("confidence_level") or
            "ai_generated"
        )
        
        AuditLogger.log_sync(
            f"AI-DETECT: Comparing {a_name} (trust: {confidence_a}) vs {b_name} (trust: {confidence_b})"
        )
        
        # Build prompt with trust scores for Gospel Principle compliance
        prompt = AuditorPrompts.build_detection_prompt(
            json.dumps(entity_a, indent=2),
            json.dumps(entity_b, indent=2),
            confidence_a=confidence_a,
            confidence_b=confidence_b
        )
        
        try:
            resp = self.flash.generate_content(
                prompt,
                generation_config={"temperature":0.1,"top_p":0.95,"max_output_tokens":4096}
            )
            contradictions = self._parse_json_array(resp.text)
            
            final_contradictions = []
            for con in contradictions:
                scored_con = self._score_contradiction_confidence(con, entity_a, entity_b)
                resolved_con = self._suggest_resolutions(scored_con, entity_a, entity_b)
                final_contradictions.append(resolved_con)

            return final_contradictions
            
        except GoogleAPIError as e:
            AuditLogger.log_sync(f"AI detection Gemini API error: {e}", level=logging.ERROR)
            return []
        except json.JSONDecodeError as e:
            AuditLogger.log_sync(f"AI detection JSON parsing error: {e}", level=logging.ERROR)
            return []
        except Exception as e: # Catch any other unexpected errors
            AuditLogger.log_sync(f"AI detection unexpected error: {e}", level=logging.ERROR)
            return []

    def _parse_json_array(self,text:str)->List[Dict[str,Any]]:
        """Parses the JSON array from the AI's response."""
        if not text: return []
        m=re.search(r"\[.*\]",text,re.DOTALL)
        if not m:
            m=re.search(r"\{.*\}",text,re.DOTALL)
            if m:
                try:
                    d=json.loads(m.group())
                    if isinstance(d,dict) and "contradictions" in d:
                        arr=d["contradictions"]
                        return arr if isinstance(arr,list) else []
                except json.JSONDecodeError:
                    AuditLogger.log_sync("Failed to parse dict from LLM response for contradictions.")
                    return []
            return []
        try:
            arr=json.loads(m.group())
            return arr if isinstance(arr,list) else []
        except json.JSONDecodeError:
            AuditLogger.log_sync("Failed to parse list from LLM response for contradictions.")
            return []

    def _score_contradiction_confidence(self, contradiction: Dict[str, Any], entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses gemini-1.5-pro to assign a confidence score.
        
        Implements the Gospel Principle by passing trust scores to the scoring prompt.
        """
        AuditLogger.log_sync(f"AI-SCORE: Scoring contradiction: {contradiction.get('description', 'N/A')[:50]}...")
        
        # Extract confidence levels for Gospel Principle
        confidence_a = (
            entity_a.get("confidence_level") or 
            entity_a.get("confidence") or 
            entity_a.get("properties", {}).get("confidence_level") or
            "ai_generated"
        )
        confidence_b = (
            entity_b.get("confidence_level") or 
            entity_b.get("confidence") or 
            entity_b.get("properties", {}).get("confidence_level") or
            "ai_generated"
        )
        
        prompt = AuditorPrompts.build_score_confidence_prompt(
            json.dumps(entity_a, indent=2),
            json.dumps(entity_b, indent=2),
            json.dumps(contradiction, indent=2),
            confidence_a=confidence_a,
            confidence_b=confidence_b
        )
        
        try:
            resp = self.pro.generate_content(
                prompt,
                generation_config={"temperature": 0.0}
            )
            match = re.search(r"\{.*\}", resp.text, re.DOTALL)
            if match:
                score_data = json.loads(match.group())
                contradiction["confidence"] = score_data.get("confidence", 0.0)
                contradiction["scoring_reasoning"] = score_data.get("reasoning", "No reasoning provided.")
            else:
                contradiction["confidence"] = 0.0
                contradiction["scoring_reasoning"] = "Failed to parse pro-model scoring response."
        except GoogleAPIError as e:
            AuditLogger.log_sync(f"AI scoring Gemini API error: {e}", level=logging.ERROR)
            contradiction["confidence"] = 0.0
            contradiction["scoring_reasoning"] = f"Gemini API error during scoring: {e}"
        except json.JSONDecodeError as e:
            AuditLogger.log_sync(f"AI scoring JSON parsing error: {e}", level=logging.ERROR)
            contradiction["confidence"] = 0.0
            contradiction["scoring_reasoning"] = f"JSON parsing error during scoring: {e}"
        except Exception as e:
            AuditLogger.log_sync(f"AI scoring unexpected error: {e}", level=logging.ERROR)
            contradiction["confidence"] = 0.0
            contradiction["scoring_reasoning"] = f"Unexpected error during scoring: {e}"
        return contradiction

    def _suggest_resolutions(self, contradiction: Dict[str, Any], entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> Dict[str, Any]:
        """Uses gemini-1.5-pro to suggest resolutions."""
        if contradiction.get("confidence", 0.0) < 0.7:
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = "Confidence score too low to suggest resolution."
            return contradiction

        AuditLogger.log_sync(f"AI-RESOLVE: Suggesting resolutions for: {contradiction.get('description', 'N/A')[:50]}...")
        
        prompt = AuditorPrompts.build_suggest_resolution_prompt(
            json.dumps(entity_a, indent=2),
            json.dumps(entity_b, indent=2),
            json.dumps(contradiction, indent=2),
            contradiction.get('confidence', 0.0)
        )
        
        try:
            resp = self.pro.generate_content(
                prompt,
                generation_config={"temperature": 0.2}
            )
            match = re.search(r"\{.*\}", resp.text, re.DOTALL)
            if match:
                res_data = json.loads(match.group())
                contradiction["possible_resolutions"] = res_data.get("possible_resolutions", [])
                contradiction["resolution_reasoning"] = res_data.get("reasoning", "No reasoning provided.")
            else:
                contradiction["possible_resolutions"] = []
                contradiction["resolution_reasoning"] = "Failed to parse pro-model resolution response."
        except GoogleAPIError as e:
            AuditLogger.log_sync(f"AI resolution Gemini API error: {e}", level=logging.ERROR)
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = f"Gemini API error during resolution suggestion: {e}"
        except json.JSONDecodeError as e:
            AuditLogger.log_sync(f"AI resolution JSON parsing error: {e}", level=logging.ERROR)
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = f"JSON parsing error during resolution suggestion: {e}"
        except Exception as e:
            AuditLogger.log_sync(f"AI resolution unexpected error: {e}", level=logging.ERROR)
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = f"Unexpected error during resolution suggestion: {e}"
        return contradiction

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parses JSON from a string, handling Markdown code blocks."""
        if not text: return {}
        # Try to find JSON block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}

    async def check_personality_consistency(
        self,
        entity_name: str,
        old_personality: OCEANProfile,
        new_behavior_description: str
    ) -> Optional[Dict[str, Any]]:
        """Check if new behavior is consistent with established personality."""
        # Use await AuditLogger.log for async method, even if class uses log_sync elsewhere
        await AuditLogger.log(f"Checking personality consistency for: {entity_name}")
        
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
            # Use self.pro as requested (pro_model)
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.pro.generate_content(
                    prompt,
                    generation_config={"temperature": 0.1}
                )
            )
            
            result = self._parse_json_response(response.text)
            
            if not result.get('consistent', True):
                await AuditLogger.log(f"Personality inconsistency detected for {entity_name}")
                return {
                    "type": "personality_inconsistency",
                    "severity": "MEDIUM",
                    "description": f"{entity_name}: {result.get('explanation', 'Personality inconsistency detected')}",
                    "entity": entity_name
                }
        except GoogleAPIError as e:
            await AuditLogger.log(f"Personality consistency Gemini API error: {e}", level=logging.ERROR)
        except json.JSONDecodeError as e:
            await AuditLogger.log(f"Personality consistency JSON parsing error: {e}", level=logging.ERROR)
        except Exception as e:
            await AuditLogger.log(f"Personality consistency unexpected error: {e}", level=logging.ERROR)
        
        return None
