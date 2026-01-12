"""
Auditor Agent - Contradiction Detection System
Detects 9 types of logical and temporal contradictions in lore database (Rule-Based)
AND complex semantic contradictions (AI-Based).

Refactored to use Neo4j graph database instead of SQLite.
"""

from __future__ import annotations

from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import json
import re
import uuid
import logging
import asyncio

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from neo4j.exceptions import Neo4jError

from src.lms.services.audit_log import AuditLogger
from src.lms.db.neo4j_adapter import Neo4jDatabase
from src.lms.services.broadcaster import broadcaster
from src.lms.prompts import AuditorPrompts
from src.lms.core.models import OCEANProfile, Contradiction
from src.lms.auditor.rule_based_auditor import RuleBasedAuditor
from src.lms.auditor.semantic_auditor import SemanticAuditor


logger = logging.getLogger(__name__)
BROADCAST_EVENTS = False  # TEMP: disable broadcaster during early dev


class AuditorAgent:
    """Runs systematic audits for contradictions in Neo4j graph database."""

    # Severity classification rules for entity creation auditing
    CRITICAL_CONTRADICTION_TYPES = [
        "same_name_different_type",           # "Thornhaven" is both Location and Character
        "temporal_impossibility",             # Event referenced before it happened
        "resurrection_without_explanation",   # Dead character appears alive
        "location_inconsistency",             # Same entity in two places simultaneously
        "direct_negation",                    # "X is alive" vs "X is dead"
    ]

    MINOR_CONTRADICTION_TYPES = [
        "personality_inconsistency",          # Character acts out of character
        "description_variation",              # Minor detail differences
        "relationship_ambiguity",             # Unclear faction status
        "implicit_contradiction",             # Subtle inconsistency
    ]

    def __init__(
        self,
        neo4j_db: Neo4jDatabase,
        gemini_api_key: str,
        rule_based_auditor: RuleBasedAuditor,
        semantic_auditor: SemanticAuditor,
        campaign_context: Optional[Dict[str, Any]] = None,
    ):
        self.db = neo4j_db
        self.rule_based_auditor = rule_based_auditor
        self.semantic_auditor = semantic_auditor

        # Configure Gemini for personality / semantic helpers
        try:
            genai.configure(api_key=gemini_api_key)
            self.personality_model = genai.GenerativeModel("gemini-2.0-flash")
            AuditLogger.log_sync("AuditorAgent: Gemini model initialized for personality checks.")
        except Exception as e:
            self.personality_model = None
            AuditLogger.log_sync(f"AuditorAgent: Failed to initialize Gemini model: {e}")

        # Campaign context - configurable, defaults to Aethermoor for legacy support
        self.campaign_context = campaign_context or {"campaign_name": "Aethermoor"}
        self.system_prompt = AuditorPrompts.get_system_prompt(self.campaign_context)

        AuditLogger.log_sync("AuditorAgent: Initialized.")

    # ==========================================
    # INTERNAL HELPERS
    # ==========================================

    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        """
        Parse JSON from an AI response with robust error recovery.

        Mirrors the behavior used in ExtractionService so we don't explode
        on minor formatting drift.
        """
        if not text:
            return {}

        cleaned = text.strip()

        # Strip common markdown fences
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.strip()

        # Direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Regex fallback to "biggest JSON-looking block"
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Trailing comma fix
        fixed = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return {}

    def _classify_contradiction_severity(
        self,
        entity_new: Dict[str, Any],
        entity_existing: Dict[str, Any],
        contradiction_type: str,
    ) -> str:
        """Classify contradiction severity as HIGH / MEDIUM / LOW."""
        if contradiction_type in self.CRITICAL_CONTRADICTION_TYPES:
            return "HIGH"

        # Type mismatch between new and existing entity type is always serious
        if entity_new.get("entity_type") != entity_existing.get("entity_type"):
            return "HIGH"

        if contradiction_type in self.MINOR_CONTRADICTION_TYPES:
            return "MEDIUM"

        return "LOW"

    # ==========================================
    # TOP-LEVEL CONTRADICTION AUDIT
    # ==========================================

    def detect_contradictions(
        self,
        entity_a: Dict[str, Any],
        entity_b: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Delegates AI-based contradiction detection to the SemanticAuditor.

        Returns a list of contradiction dicts with at least:
        - type
        - severity
        - description
        - entity_ids (or names)
        """
        return self.semantic_auditor.detect_contradictions(entity_a, entity_b)

    async def run_full_audit(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Runs all RULE-BASED audit checks using Cypher queries via the injected RuleBasedAuditor.

        Returns:
            A dict keyed by audit category with lists of contradiction records.
        """
        try:
            results = await self.rule_based_auditor.run_full_audit()
        except (Neo4jError, Exception) as e:
            await AuditLogger.log(f"Rule-based audit failed: {e}", level=logging.ERROR)
            raise

        # Publish event for audit completion
        summary = self.rule_based_auditor.get_summary(results)
        if BROADCAST_EVENTS:
            await broadcaster.publish(
                "auditor_events",
                {
                    "type": "audit_progress",
                    "message": "Rule-based audit complete.",
                    "summary": summary,
                },
            )
        return results

    def review(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Placeholder review method for AuditorAgent.

        Currently resolves any contradiction that has "test" or "example" in its description.
        This is a stub and should be replaced with real human-in-the-loop review logic.
        """
        AuditLogger.log_sync(
            f"AuditorAgent reviewing contradiction: {record.get('contradiction_id')}"
        )
        description = record.get("description", "").lower()
        resolved = "test" in description or "example" in description
        AuditLogger.log_sync(f"Review decision -> resolved={resolved}")
        return {"resolved": resolved}

    # ==========================================
    # ENTITY CREATION AUDITING
    # ==========================================

    async def audit_new_entity(self, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audit a new entity BEFORE creation to check for contradictions.

        Expected entity_data keys (minimum):
        - name
        - entity_type OR label
        - properties (optional)
        """
        name = entity_data.get("name", "")
        new_type = (
            entity_data.get("entity_type")
            or entity_data.get("label")
            or "Entity"
        )

        await AuditLogger.log(
            f"Auditing new entity: {name} ({new_type})"
        )

        contradictions: List[Dict[str, Any]] = []
        max_severity: Optional[str] = None

        # Look for an existing entity with the same canonical name
        # Prefer the canonical schema (Entity + entity_type) but fall back if needed
        query = """
        MATCH (e)
        WHERE toLower(e.name) = toLower($name)
        RETURN 
            e.name AS name,
            coalesce(e.entity_type, labels(e)[0]) AS entity_type,
            properties(e) AS properties
        LIMIT 1
        """

        try:
            existing = await self.db.execute(query, {"name": name})
        except Exception as e:
            await AuditLogger.log(f"Error during entity existence check: {e}", level=logging.ERROR)
            existing = []

        if existing:
            record = existing[0]
            existing_entity = {
                "name": record.get("name"),
                "entity_type": record.get("entity_type"),
                "properties": record.get("properties", {}),
            }

            if existing_entity["entity_type"] != new_type:
                contradiction_type = "same_name_different_type"
            else:
                contradiction_type = "description_variation"

            severity = self._classify_contradiction_severity(
                {"name": name, "entity_type": new_type},
                existing_entity,
                contradiction_type,
            )

            contradictions.append(
                {
                    "type": contradiction_type,
                    "severity": severity,
                    "existing_entity": existing_entity["name"],
                    "existing_type": existing_entity["entity_type"],
                    "conflict": (
                        f"New {new_type} '{name}' conflicts with existing "
                        f"{existing_entity['entity_type']} of the same name."
                    ),
                }
            )

            max_severity = severity
            await AuditLogger.log(
                f"Contradiction found for '{name}': {contradiction_type} (severity: {severity})"
            )

        # Decide action based on max severity
        if max_severity == "HIGH":
            action = "BLOCK"
            approved = False
        elif max_severity in ["MEDIUM", "LOW"]:
            action = "FLAG"
            approved = True
        else:
            action = "APPROVE"
            approved = True

        result = {
            "approved": approved,
            "contradictions": contradictions,
            "severity": max_severity,
            "action": action,
        }

        await AuditLogger.log(f"Audit result for '{name}': {action} (approved={approved})")
        return result

    async def queue_blocked_entity(
        self,
        entity: Dict[str, Any],
        audit_result: Dict[str, Any],
        session_id: str,
    ) -> None:
        """Queue a blocked entity for human review."""
        await AuditLogger.log(
            f"Queuing blocked entity for review: {entity.get('name')}"
        )

        query = """
        CREATE (r:ReviewQueue {
            review_id: $review_id,
            entity_name: $entity_name,
            entity_type: $entity_type,
            proposed_properties: $properties,
            contradiction: $contradiction,
            severity: $severity,
            session_id: $session_id,
            status: 'PENDING',
            created_at: $created_at
        })
        RETURN r.review_id AS id
        """

        params = {
            "review_id": str(uuid.uuid4()),
            "entity_name": entity.get("name", "Unknown"),
            "entity_type": entity.get("entity_type") or entity.get("label", "Entity"),
            "properties": json.dumps(entity.get("properties", {})),
            "contradiction": (
                audit_result["contradictions"][0]["conflict"]
                if audit_result.get("contradictions")
                else "Unknown conflict"
            ),
            "severity": audit_result.get("severity", "HIGH"),
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.db.execute(query, params)

        if BROADCAST_EVENTS:
            await broadcaster.publish(
                "auditor_events",
                {
                    "type": "entity_blocked",
                    "entity_name": entity.get("name"),
                    "reason": params["contradiction"],
                },
            )

    async def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Get all entities pending human review."""
        query = """
        MATCH (r:ReviewQueue {status: 'PENDING'})
        RETURN r.review_id AS id,
               r.entity_name AS entity_name,
               r.entity_type AS entity_type,
               r.contradiction AS contradiction,
               r.severity AS severity,
               r.session_id AS session_id,
               r.created_at AS created_at
        ORDER BY r.created_at DESC
        """
        results = await self.db.execute(query)
        return [dict(r) for r in results] if results else []

    async def approve_queued_entity(
        self,
        review_id: str,
        approver: str = "Human",
    ) -> bool:
        """Approve a queued entity for creation."""
        await AuditLogger.log(
            f"Approving queued entity: {review_id} by {approver}"
        )

        query = """
        MATCH (r:ReviewQueue {review_id: $review_id})
        SET r.status = 'APPROVED',
            r.approved_by = $approver,
            r.approved_at = $now
        RETURN r.entity_name AS name,
               r.entity_type AS label,
               r.proposed_properties AS properties
        """
        result = await self.db.execute(
            query,
            {
                "review_id": review_id,
                "approver": approver,
                "now": datetime.now(timezone.utc).isoformat(),
            },
        )

        return bool(result)

    async def reject_queued_entity(
        self,
        review_id: str,
        rejector: str = "Human",
        reason: str = "",
    ) -> bool:
        """Reject a queued entity."""
        await AuditLogger.log(
            f"Rejecting queued entity: {review_id} by {rejector}"
        )

        query = """
        MATCH (r:ReviewQueue {review_id: $review_id})
        SET r.status = 'REJECTED',
            r.rejected_by = $rejector,
            r.rejection_reason = $reason,
            r.rejected_at = $now
        RETURN r.review_id AS id
        """
        result = await self.db.execute(
            query,
            {
                "review_id": review_id,
                "rejector": rejector,
                "reason": reason,
                "now": datetime.now(timezone.utc).isoformat(),
            },
        )

        return bool(result)

    # ==========================================
    # PERSONALITY CONSISTENCY CHECKING
    # ==========================================

    async def check_personality_consistency(
        self,
        entity_name: str,
        old_personality: OCEANProfile,
        new_behavior_description: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if new behavior is consistent with established personality.

        Returns a contradiction dict if inconsistent, otherwise None.
        """
        await AuditLogger.log(
            f"Checking personality consistency for: {entity_name}"
        )

        if not self.personality_model:
            await AuditLogger.log(
                "Personality model not initialized; skipping personality consistency check.",
                level=logging.WARNING,
            )
            return None

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
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.personality_model.generate_content(
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


    async def get_entity_personality(
        self,
        entity_name: str,
    ) -> Optional[OCEANProfile]:
        """Retrieve OCEAN personality profile for an entity from Neo4j."""
        query = """
        MATCH (e:Character)
        WHERE toLower(e.name) = toLower($name)
          AND e.openness IS NOT NULL
          AND e.conscientiousness IS NOT NULL
          AND e.extraversion IS NOT NULL
          AND e.agreeableness IS NOT NULL
          AND e.neuroticism IS NOT NULL
        RETURN e.openness AS openness,
               e.conscientiousness AS conscientiousness,
               e.extraversion AS extraversion,
               e.agreeableness AS agreeableness,
               e.neuroticism AS neuroticism
        LIMIT 1
        """

        try:
            result = await self.db.execute(query, {"name": entity_name})
        except Exception as e:
            await AuditLogger.log(
                f"Failed to fetch personality for {entity_name}: {e}",
                level=logging.ERROR,
            )
            return None

        if result:
            return OCEANProfile.from_dict(dict(result[0]))

        return None