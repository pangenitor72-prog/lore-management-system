"""
Auditor Scoring Module
Calculates deterministic confidence scores for contradiction triage based on:
- Trust score differential between entities (Gospel Principle)
- Contradiction severity (High/Medium/Low)
- Evidence richness
- Entity confidence levels
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union

from src.core.models import CONFIDENCE_RULES, ContradictionSeverity, LoreConfidence

# Configure module logger
logger = logging.getLogger(__name__)

# Severity score multipliers (higher severity = lower confidence in correctness)
SEVERITY_WEIGHTS = {
    "HIGH": 0.3,      # High severity contradictions significantly reduce confidence
    "MEDIUM": 0.6,    # Medium severity has moderate impact
    "LOW": 0.8,       # Low severity has minimal impact
}

# Default trust score for unknown confidence levels
DEFAULT_TRUST_SCORE = 0.5


class AuditorScoring:
    """
    Deterministic scoring system for contradiction triage.
    
    Implements the "Gospel Principle": Human-verified facts always win over 
    AI-generated content when there's a conflict.
    """
    
    def __init__(self, weight_factors: Optional[Dict[str, float]] = None):
        """
        Initialize the scoring system.
        
        Args:
            weight_factors: Optional custom weights for scoring components
                - trust_mismatch: Weight for trust score differential (default: 0.4)
                - severity: Weight for contradiction severity (default: 0.3)
                - evidence: Weight for evidence richness (default: 0.2)
                - history: Weight for prior resolution patterns (default: 0.1)
        """
        self.weights = weight_factors or {
            "trust_mismatch": 0.4,
            "severity": 0.3,
            "evidence": 0.2,
            "history": 0.1
        }
    
    @staticmethod
    def get_trust_score(confidence_level: str) -> float:
        """
        Get the trust score for a given confidence level.
        
        Args:
            confidence_level: The entity's confidence level (e.g., "human_approved", "ai_generated")
            
        Returns:
            Trust score between 0.0 and 1.0
        """
        if not confidence_level:
            return DEFAULT_TRUST_SCORE
        
        # Normalize to lowercase for lookup
        level_key = confidence_level.lower().replace("-", "_").replace(" ", "_")
        
        # Look up in CONFIDENCE_RULES
        if level_key in CONFIDENCE_RULES:
            return CONFIDENCE_RULES[level_key].get("trust_score", DEFAULT_TRUST_SCORE)
        
        # Handle legacy/alternative naming
        legacy_mappings = {
            "confirmed": "human_approved",
            "probable": "ai_verified", 
            "speculative": "ai_generated",
            "uncertain": "ai_flagged",
        }
        
        if level_key in legacy_mappings:
            mapped_key = legacy_mappings[level_key]
            return CONFIDENCE_RULES.get(mapped_key, {}).get("trust_score", DEFAULT_TRUST_SCORE)
        
        logger.debug(f"Unknown confidence level '{confidence_level}', using default trust score")
        return DEFAULT_TRUST_SCORE
    
    def compute_trust_mismatch_score(
        self, 
        entity_a_confidence: str, 
        entity_b_confidence: str
    ) -> float:
        """
        Compute a score based on the trust differential between two entities.
        
        The Gospel Principle: When there's a large trust mismatch, we're more
        confident about which entity is correct (the higher-trust one wins).
        
        Args:
            entity_a_confidence: Confidence level of first entity
            entity_b_confidence: Confidence level of second entity
            
        Returns:
            Score between 0.0 (no mismatch, uncertain) and 1.0 (clear winner)
        """
        trust_a = self.get_trust_score(entity_a_confidence)
        trust_b = self.get_trust_score(entity_b_confidence)
        
        # Calculate absolute differential
        mismatch = abs(trust_a - trust_b)
        
        # Higher mismatch = more confidence in resolution direction
        return mismatch
    
    def compute_severity_score(self, severity: Union[str, ContradictionSeverity]) -> float:
        """
        Compute a score based on contradiction severity.
        
        Higher severity contradictions are harder to automatically resolve,
        so they get lower confidence scores (need human review).
        
        Args:
            severity: The contradiction severity level
            
        Returns:
            Score between 0.0 and 1.0
        """
        if isinstance(severity, ContradictionSeverity):
            severity_key = severity.value
        else:
            severity_key = str(severity).upper()
        
        return SEVERITY_WEIGHTS.get(severity_key, 0.5)
    
    def compute_evidence_score(self, evidence: Optional[Dict[str, Any]]) -> float:
        """
        Compute a score based on evidence richness.
        
        More detailed evidence = higher confidence in the contradiction detection.
        
        Args:
            evidence: Evidence dictionary from the contradiction
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not evidence:
            return 0.3  # Minimal evidence
        
        score = 0.3  # Base score for having any evidence
        
        # Check for key evidence components
        evidence_factors = [
            ("source_text", 0.15),      # Original text that caused detection
            ("entity_a", 0.1),           # First entity details
            ("entity_b", 0.1),           # Second entity details
            ("field_name", 0.1),         # Which field conflicts
            ("conflicting_values", 0.15),# The actual conflicting values
            ("detection_method", 0.05),  # How it was detected
            ("context", 0.05),           # Additional context
        ]
        
        for key, weight in evidence_factors:
            if key in evidence and evidence[key]:
                score += weight
        
        return min(score, 1.0)
    
    def compute_confidence(
        self, 
        contradiction: Union[Dict[str, Any], Any],
        entity_confidences: Optional[List[str]] = None
    ) -> float:
        """
        Compute a deterministic confidence score for a contradiction.
        
        This is the main scoring method that combines all factors:
        - Trust mismatch between entities (Gospel Principle)
        - Severity of the contradiction
        - Evidence richness
        
        Args:
            contradiction: The contradiction object (dict or model)
            entity_confidences: Optional list of confidence levels for involved entities
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Extract fields from dict or object
        def get_field(obj, field, default=None):
            if isinstance(obj, dict):
                return obj.get(field, default)
            return getattr(obj, field, default)
        
        # Get contradiction details
        severity = get_field(contradiction, "severity", "MEDIUM")
        evidence = get_field(contradiction, "evidence", {})
        description = get_field(contradiction, "description", "")
        
        # Extract entity confidences from evidence if not provided
        if not entity_confidences and evidence:
            entity_a = evidence.get("entity_a", {}) if isinstance(evidence, dict) else {}
            entity_b = evidence.get("entity_b", {}) if isinstance(evidence, dict) else {}
            
            conf_a = entity_a.get("confidence_level", "ai_generated") if isinstance(entity_a, dict) else "ai_generated"
            conf_b = entity_b.get("confidence_level", "ai_generated") if isinstance(entity_b, dict) else "ai_generated"
            
            entity_confidences = [conf_a, conf_b]
        
        # Calculate component scores
        scores = {}
        
        # 1. Trust mismatch score (Gospel Principle)
        if entity_confidences and len(entity_confidences) >= 2:
            scores["trust_mismatch"] = self.compute_trust_mismatch_score(
                entity_confidences[0], 
                entity_confidences[1]
            )
        else:
            scores["trust_mismatch"] = 0.5  # Unknown, use neutral score
        
        # 2. Severity score
        scores["severity"] = self.compute_severity_score(severity)
        
        # 3. Evidence score
        scores["evidence"] = self.compute_evidence_score(evidence)
        
        # 4. Description bonus (having a description helps)
        scores["history"] = 0.5 + (0.2 if description else 0.0)
        
        # Compute weighted average
        total_weight = sum(self.weights.values())
        weighted_sum = sum(
            scores.get(key, 0.5) * weight 
            for key, weight in self.weights.items()
        )
        
        confidence = weighted_sum / total_weight if total_weight > 0 else 0.5
        
        logger.debug(
            f"Confidence computed: {confidence:.3f} "
            f"(trust_mismatch={scores.get('trust_mismatch', 0):.2f}, "
            f"severity={scores.get('severity', 0):.2f}, "
            f"evidence={scores.get('evidence', 0):.2f})"
        )
        
        return round(confidence, 3)
    
    def get_resolution_recommendation(
        self, 
        contradiction: Union[Dict[str, Any], Any],
        entity_confidences: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get a resolution recommendation based on the Gospel Principle.
        
        Args:
            contradiction: The contradiction object
            entity_confidences: Confidence levels of involved entities
            
        Returns:
            Dict with recommendation, winner, and reasoning
        """
        def get_field(obj, field, default=None):
            if isinstance(obj, dict):
                return obj.get(field, default)
            return getattr(obj, field, default)
        
        evidence = get_field(contradiction, "evidence", {})
        
        # Extract entity info
        if not entity_confidences and evidence:
            entity_a = evidence.get("entity_a", {}) if isinstance(evidence, dict) else {}
            entity_b = evidence.get("entity_b", {}) if isinstance(evidence, dict) else {}
            
            conf_a = entity_a.get("confidence_level", "ai_generated") if isinstance(entity_a, dict) else "ai_generated"
            conf_b = entity_b.get("confidence_level", "ai_generated") if isinstance(entity_b, dict) else "ai_generated"
        else:
            conf_a = entity_confidences[0] if entity_confidences else "ai_generated"
            conf_b = entity_confidences[1] if entity_confidences and len(entity_confidences) > 1 else "ai_generated"
        
        trust_a = self.get_trust_score(conf_a)
        trust_b = self.get_trust_score(conf_b)
        
        confidence = self.compute_confidence(contradiction, [conf_a, conf_b])
        
        # Determine recommendation based on trust differential
        if abs(trust_a - trust_b) < 0.1:
            # Similar trust levels - requires human review
            return {
                "recommendation": "REQUIRES_REVIEW",
                "confidence": confidence,
                "winner": None,
                "reasoning": f"Both entities have similar trust levels ({conf_a}: {trust_a}, {conf_b}: {trust_b}). Human review required."
            }
        elif trust_a > trust_b:
            # Entity A has higher trust (Gospel Principle: it wins)
            return {
                "recommendation": "FAVOR_ENTITY_A",
                "confidence": confidence,
                "winner": "entity_a",
                "reasoning": f"Entity A ({conf_a}, trust={trust_a}) has higher trust than Entity B ({conf_b}, trust={trust_b}). Per Gospel Principle, higher-trust entity wins."
            }
        else:
            # Entity B has higher trust
            return {
                "recommendation": "FAVOR_ENTITY_B", 
                "confidence": confidence,
                "winner": "entity_b",
                "reasoning": f"Entity B ({conf_b}, trust={trust_b}) has higher trust than Entity A ({conf_a}, trust={trust_a}). Per Gospel Principle, higher-trust entity wins."
            }
    
    def generate_review_record(
        self, 
        contradiction_id: str, 
        confidence: float,
        recommendation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a review record for audit trail.
        
        Args:
            contradiction_id: ID of the contradiction
            confidence: Computed confidence score
            recommendation: Optional resolution recommendation
            
        Returns:
            Review record dictionary
        """
        record = {
            "contradiction_id": contradiction_id,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scoring_version": "2.0",  # Deterministic scoring version
            "weights_used": self.weights.copy()
        }
        
        if recommendation:
            record["recommendation"] = recommendation.get("recommendation")
            record["reasoning"] = recommendation.get("reasoning")
        
        return record
