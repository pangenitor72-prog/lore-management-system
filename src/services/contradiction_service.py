# src/services/contradiction_service.py

import logging
from typing import List, Dict, Any, Optional

from src.agents.auditor_agent import AuditorAgent
from src.core.models import Contradiction
from src.services.audit_log import AuditLogger
from src.services.broadcaster import broadcaster

logger = logging.getLogger(__name__)
BROADCAST_EVENTS = False  # TEMP: disable broadcaster during early dev


class ContradictionService:
    """
    High-level façade that coordinates contradiction detection and resolution
    across the RuleBasedAuditor and SemanticAuditor via the AuditorAgent.

    Responsibilities:
    - Trigger full audits
    - Trigger pairwise semantic contradiction checks
    - Format results for API/UI
    - Forward events to WebSocket broadcaster
    - Wrap AuditorAgent to keep API layer clean
    """

    def __init__(self, auditor_agent: AuditorAgent):
        self.auditor = auditor_agent
        AuditLogger.log_sync("ContradictionService initialized.")

    # ----------------------------------------------------------------------
    # FULL AUDIT (Rule-Based)
    # ----------------------------------------------------------------------
    async def run_full_audit(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run the rule-based audit, return the dictionary of categorized
        contradictions, and publish the result over WebSockets.
        """
        AuditLogger.log_sync("ContradictionService: Starting full audit.")
        results = await self.auditor.run_full_audit()

        # Broadcast summary to UI dashboard
        summary = self.auditor.rule_based_auditor.get_summary(results)
        if BROADCAST_EVENTS:
            await broadcaster.publish("auditor_events", {
                "type": "audit_complete",
                "summary": summary,
            })

        AuditLogger.log_sync("ContradictionService: Full audit complete.")
        return results

    # ----------------------------------------------------------------------
    # SEMANTIC CONTRADICTION CHECK
    # ----------------------------------------------------------------------
    async def check_entities_for_semantic_contradictions(
        self,
        entity_a: Dict[str, Any],
        entity_b: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Runs the AI semantic contradiction detector between two entities.

        Returns a list of contradiction dicts, NOT Contradiction objects,
        because UI/API expects JSON-serializable dicts.
        """
        a_name = entity_a.get("name", "?")
        b_name = entity_b.get("name", "?")

        AuditLogger.log_sync(
            f"ContradictionService: Checking semantic contradictions "
            f"between '{a_name}' and '{b_name}'."
        )

        contradictions = self.auditor.detect_contradictions(entity_a, entity_b)

        # Broadcast live update for dashboard (semantic scan)
        if contradictions and BROADCAST_EVENTS:
            await broadcaster.publish("auditor_events", {
                "type": "semantic_contradictions_found",
                "entity_a": a_name,
                "entity_b": b_name,
                "count": len(contradictions),
            })

        return contradictions

    # ----------------------------------------------------------------------
    # ENTITY CREATION AUDIT (PRE-CHECK)
    # ----------------------------------------------------------------------
    async def audit_new_entity_before_creation(
        self,
        entity_data: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Check contradictions BEFORE inserting a new entity into Neo4j.
        This enforces Gospel Principle constraints for world consistency.
        """
        name = entity_data.get("name", "Unknown")

        AuditLogger.log_sync(
            f"ContradictionService: Auditing new entity before creation: {name}"
        )

        result = await self.auditor.audit_new_entity(entity_data)

        # If blocked, queue for human review
        if not result["approved"]:
            await self.auditor.queue_blocked_entity(entity_data, result, session_id)

            if BROADCAST_EVENTS:
                await broadcaster.publish("auditor_events", {
                    "type": "entity_creation_blocked",
                    "entity": name,
                    "action": result["action"],
                    "reason": (
                        result["contradictions"][0]["conflict"]
                        if result["contradictions"]
                        else "Unknown"
                    ),
                })

        return result

    # ----------------------------------------------------------------------
    # REVIEW QUEUE OPERATIONS
    # ----------------------------------------------------------------------
    async def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Return all queued contradictions awaiting human review."""
        return await self.auditor.get_pending_reviews()

    async def approve_review(self, review_id: str, approver: str = "Human") -> bool:
        """Approve a contradiction resolution from the review queue."""
        AuditLogger.log_sync(f"ContradictionService: Approving review {review_id}.")
        result = await self.auditor.approve_queued_entity(review_id, approver)

        if result and BROADCAST_EVENTS:
            await broadcaster.publish("auditor_events", {
                "type": "review_approved",
                "review_id": review_id,
                "approved_by": approver,
            })

        return result

    async def reject_review(
        self,
        review_id: str,
        rejector: str = "Human",
        reason: str = ""
    ) -> bool:
        """Reject a queued contradiction resolution."""
        AuditLogger.log_sync(
            f"ContradictionService: Rejecting review {review_id} (reason: {reason})"
        )
        result = await self.auditor.reject_queued_entity(review_id, rejector, reason)

        if result and BROADCAST_EVENTS:
            await broadcaster.publish("auditor_events", {
                "type": "review_rejected",
                "review_id": review_id,
                "rejected_by": rejector,
                "reason": reason,
            })

        return result