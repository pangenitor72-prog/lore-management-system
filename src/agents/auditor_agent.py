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
from src.services.audit_log import AuditLogger
import logging
import asyncio
from src.db.neo4j_adapter import Neo4jDatabase
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError # Added for specific error handling
from neo4j.exceptions import Neo4jError # Added for specific error handling
from src.services.broadcaster import broadcaster
from src.prompts import AuditorPrompts
from src.core.models import OCEANProfile, Contradiction # Corrected import for OCEANProfile, added Contradiction
from src.auditor.rule_based_auditor import RuleBasedAuditor # Import new RuleBasedAuditor
from src.auditor.semantic_auditor import SemanticAuditor # Import new SemanticAuditor


class AuditorAgent:
    """Runs systematic audits for contradictions in Neo4j graph database."""

    # Severity classification rules for entity creation auditing
    CRITICAL_CONTRADICTION_TYPES = [
        "same_name_different_type",           # "Thornhaven" is both Location and Character
        "temporal_impossibility",              # Event referenced before it happened
        "resurrection_without_explanation",    # Dead character appears alive
        "location_inconsistency",             # Same entity in two places simultaneously
        "direct_negation"                     # "X is alive" vs "X is dead"
    ]
    
    MINOR_CONTRADICTION_TYPES = [
        "personality_inconsistency",          # Character acts out of character
        "description_variation",              # Minor detail differences
        "relationship_ambiguity",             # Unclear faction status
        "implicit_contradiction"              # Subtle inconsistency
    ]

    def __init__(self, neo4j_db: Neo4jDatabase, gemini_api_key: str, rule_based_auditor: RuleBasedAuditor, semantic_auditor: SemanticAuditor):
        self.db = neo4j_db
        self.rule_based_auditor = rule_based_auditor
        self.semantic_auditor = semantic_auditor
        AuditLogger.log_sync("AuditorAgent: Initialized.")
        
        # Load campaign context (placeholder for now, ideally from config)
        self.campaign_context = {"campaign_name": "Aethermoor"} 
        self.system_prompt = AuditorPrompts.get_system_prompt(self.campaign_context)

    def detect_contradictions(self, entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Delegates AI-based contradiction detection to the SemanticAuditor."""
        return self.semantic_auditor.detect_contradictions(entity_a, entity_b)

    async def run_full_audit(self) -> Dict[str, List[Dict]]:
        """Runs all RULE-BASED audit checks using Cypher queries via the injected RuleBasedAuditor."""
        # Delegate to the injected RuleBasedAuditor
        results = await self.rule_based_auditor.run_full_audit()
        
        # Publish event for audit completion
        summary = self.rule_based_auditor.get_summary(results) # Get summary from rule-based auditor
        await broadcaster.publish("auditor_events", {
            "type": "audit_progress",
            "message": "Rule-based audit complete.",
            "summary": summary
        })
        return results

    def review(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Placeholder review method for AuditorAgent.
        This method is a stand-in for a more complex review process.
        It currently resolves any contradiction that has "test" or "example" in its description.
        """
        AuditLogger.log_sync(f"AuditorAgent reviewing contradiction: {record.get('contradiction_id')}")
        description = record.get("description", "").lower()
        resolved = "test" in description or "example" in description
        AuditLogger.log_sync(f"Review decision -> resolved={resolved}")
        return {"resolved": resolved}

    # ==========================================
    # ENTITY CREATION AUDITING
    # ==========================================

    def _classify_contradiction_severity(
        self, 
        entity_new: Dict[str, Any], 
        entity_existing: Dict[str, Any],
        contradiction_type: str
    ) -> str:
        """Classify contradiction severity as CRITICAL or MINOR."""
        if contradiction_type in self.CRITICAL_CONTRADICTION_TYPES:
            return "HIGH"
        
        if entity_new.get("label") != entity_existing.get("label"):
            return "HIGH"
        
        if contradiction_type in self.MINOR_CONTRADICTION_TYPES:
            return "MEDIUM"
        
        return "LOW"

    async def audit_new_entity(self, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Audit a new entity BEFORE creation to check for contradictions."""
        await AuditLogger.log(f"Auditing new entity: {entity_data.get('name')} ({entity_data.get('label')})")
        
        contradictions = []
        max_severity = None
        
        existing = await self.db.execute("""
            MATCH (e)
            WHERE toLower(e.name) = toLower($name)
            RETURN e.name AS name,
                   labels(e)[0] AS label,
                   properties(e) AS properties
            LIMIT 1
        """, {"name": entity_data.get("name", "")})
        
        if existing and len(existing) > 0:
            existing_entity = existing[0]
            
            if existing_entity["label"] != entity_data.get("label"):
                contradiction_type = "same_name_different_type"
            else:
                contradiction_type = "description_variation"
            
            severity = self._classify_contradiction_severity(
                entity_data,
                dict(existing_entity),
                contradiction_type
            )
            
            contradictions.append({
                "type": contradiction_type,
                "severity": severity,
                "existing_entity": existing_entity["name"],
                "existing_label": existing_entity["label"],
                "conflict": f"New {entity_data.get('label')} '{entity_data.get('name')}' conflicts with existing {existing_entity['label']}"
            })
            
            max_severity = severity
            await AuditLogger.log(f"Contradiction found: {contradiction_type} (severity: {severity})")
        
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
            "action": action
        }
        
        await AuditLogger.log(f"Audit result: {action} (approved={approved})")
        return result

    async def queue_blocked_entity(
        self,
        entity: Dict[str, Any],
        audit_result: Dict[str, Any],
        session_id: str
    ) -> None:
        """Queue a blocked entity for human review."""
        await AuditLogger.log(f"Queuing blocked entity for review: {entity.get('name')}")
        
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
            "entity_type": entity.get("label", "Entity"),
            "properties": json.dumps(entity.get("properties", {})),
            "contradiction": audit_result["contradictions"][0]["conflict"] if audit_result["contradictions"] else "Unknown conflict",
            "severity": audit_result.get("severity", "HIGH"),
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.db.execute(query, params)
        
        await broadcaster.publish("auditor_events", {
            "type": "entity_blocked",
            "entity_name": entity.get("name"),
            "reason": audit_result["contradictions"][0]["conflict"] if audit_result["contradictions"] else "Unknown"
        })

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

    async def approve_queued_entity(self, review_id: str, approver: str = "Human") -> bool:
        """Approve a queued entity for creation."""
        await AuditLogger.log(f"Approving queued entity: {review_id} by {approver}")
        
        query = """
        MATCH (r:ReviewQueue {review_id: $review_id})
        SET r.status = 'APPROVED',
            r.approved_by = $approver,
            r.approved_at = $now
        RETURN r.entity_name AS name, 
               r.entity_type AS label,
               r.proposed_properties AS properties
        """
        result = await self.db.execute(query, {
            "review_id": review_id,
            "approver": approver,
            "now": datetime.now(timezone.utc).isoformat()
        })
        
        if result and len(result) > 0:
            return True
        return False

    async def reject_queued_entity(self, review_id: str, rejector: str = "Human", reason: str = "") -> bool:
        """Reject a queued entity."""
        await AuditLogger.log(f"Rejecting queued entity: {review_id} by {rejector}")
        
        query = """
        MATCH (r:ReviewQueue {review_id: $review_id})
        SET r.status = 'REJECTED',
            r.rejected_by = $rejector,
            r.rejection_reason = $reason,
            r.rejected_at = $now
        RETURN r.review_id
        """
        result = await self.db.execute(query, {
            "review_id": review_id,
            "rejector": rejector,
            "reason": reason,
            "now": datetime.now(timezone.utc).isoformat()
        })
        
        return result is not None and len(result) > 0

    # ==========================================
    # PERSONALITY CONSISTENCY CHECKING
    # ==========================================

    async def check_personality_consistency(
        self,
        entity_name: str,
        old_personality: OCEANProfile,
        new_behavior_description: str
    ) -> Optional[Dict[str, Any]]:
        """Check if new behavior is consistent with established personality."""
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
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.flash.generate_content(
                    prompt,
                    generation_config={"temperature": 0.1}
                )
            )
            
            result = self._parse_json_response(response.text)
            
            if not result.get('consistent', True):
                await AuditLogger.log(f"Personality inconsistency detected for {entity_name}")
                return {
                    "type": "personality_inconsistency",
                    "severity": "MINOR",
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

    async def get_entity_personality(self, entity_name: str) -> Optional[OCEANProfile]:
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
        
        result = await self.db.execute(query, {"name": entity_name})
        
        if result and len(result) > 0:
            return OCEANProfile.from_dict(dict(result[0]))
        
        return None
