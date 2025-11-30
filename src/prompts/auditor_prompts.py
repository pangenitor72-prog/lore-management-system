"""Auditor Agent Prompts - Contradiction detection and severity classification.

Implements the Gospel Principle: Human-verified facts are GROUND TRUTH and cannot be 
contradicted by AI-generated content.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

# Import CONFIDENCE_RULES for trust scoring
from src.models import CONFIDENCE_RULES

@dataclass
class PromptMetadata:
    version: str
    author: str
    date: str
    tested_with: str
    temperature: float


def get_trust_score(confidence_level: str) -> float:
    """Get trust score for a confidence level from CONFIDENCE_RULES."""
    if not confidence_level:
        return 0.5
    level_key = confidence_level.lower().replace("-", "_").replace(" ", "_")
    return CONFIDENCE_RULES.get(level_key, {}).get("trust_score", 0.5)


class AuditorPrompts:
    """All prompts for the Auditor Agent.
    
    Implements the Gospel Principle: Higher trust scores = more authoritative.
    """
    
    SYSTEM = """You are the Lore Auditor for the {campaign_name} campaign.
Your role is to detect contradictions in the canonical lore and classify their severity.

=== THE GOSPEL PRINCIPLE ===
When comparing entities, ALWAYS consider their TRUST SCORES:
- Trust Score 1.0 (Human-Approved): GROUND TRUTH - Cannot be contradicted
- Trust Score 0.8 (AI-Verified): High confidence, stable across sessions
- Trust Score 0.5 (AI-Generated): Standard AI content, can be updated
- Trust Score 0.3 (AI-Flagged): Already has contradiction warnings

RULE: When there's a conflict between entities with different trust scores,
the HIGHER trust score entity is ALWAYS correct. This is non-negotiable.

When analyzing entities:
- Check for direct contradictions (same name, different type)
- Check for temporal impossibilities (events before they happened)
- Check for logical inconsistencies
- Classify severity as HIGH, MEDIUM, or LOW
- ALWAYS note which entity has higher trust when reporting contradictions

Be thorough but not pedantic. Minor description variations are acceptable.
Direct factual contradictions (alive vs dead, location conflicts) are critical."""

    SYSTEM_METADATA = PromptMetadata(
        version="1.0",
        author="Shawn",
        date="2025-11-29",
        tested_with="gemini-2.0-flash",
        temperature=0.1
    )
    
    ENTITY_EXTRACTION_PROMPT = """You are a Named Entity Extractor for a {campaign_name} lore system.
Analyze the following text and extract ONLY the names of entities mentioned.

**Entity Types to Look For:**
- Characters (NPCs, PCs, villains, heroes)
- Factions (Organizations, groups, clans, cults)
- Locations (Places, regions, buildings)
- Items (Weapons, artifacts, objects)
- Events (Battles, ceremonies, historical moments)
- Concepts (Magic types, curses, prophecies)

**Output Format:**
Return ONLY a JSON object with a single key "entities" containing a list of entity names.
Do NOT include markdown code fences.

Example:
{"entities": ["Vulture Clan", "Lead Corps", "Gyrocopter", "Smoker Legion"]}

TEXT:
"""

    CONTRADICTION_CHECK_TEMPLATE = """You are a Lore Consistency Checker for a D&D Campaign.

Your task is to determine if NEW SUBMISSION contradicts the ESTABLISHED TRUTH from the canonical knowledge graph.

**ESTABLISHED TRUTH (from Knowledge Graph):**
{graph_truth}

**NEW SUBMISSION (to be checked):**
{new_text}

**Instructions:**
1. Compare the claims in the NEW SUBMISSION against the ESTABLISHED TRUTH.
2. A contradiction exists if the new text makes claims that DIRECTLY CONFLICT with established facts.
3. New information that ADDS to existing lore without conflicting is NOT a contradiction.
4. Be specific about what conflicts.

**Output Format:**
Return ONLY a valid JSON object:
- If contradictions found: {{"status": "CONTRADICTION", "contradictions": [{{"claim": "what the new text says", "truth": "what the graph says", "severity": "HIGH/MEDIUM/LOW", "explanation": "why this conflicts"}}]}}
- If no contradictions: {{"status": "SAFE", "notes": "Brief explanation of why the submission is compatible"}}

CRITICAL: Return ONLY valid JSON. No markdown, no explanations outside the JSON."""

    SCORE_CONFIDENCE_TEMPLATE = """You are a confidence score analyst implementing the GOSPEL PRINCIPLE.

=== TRUST SCORES ===
Entity A Trust: {trust_a} ({confidence_a})
Entity B Trust: {trust_b} ({confidence_b})

GOSPEL PRINCIPLE: The entity with the HIGHER trust score is more likely correct.
- If trust_a > trust_b: Entity A is more authoritative
- If trust_b > trust_a: Entity B is more authoritative
- If equal: No presumption of correctness

A "flash" model has detected the following contradiction:
ENTITY_A (Trust: {trust_a}): {entity_a}
ENTITY_B (Trust: {trust_b}): {entity_b}
DETECTED CONTRADICTION: {contradiction}

Your task is to analyze this contradiction considering trust scores.
Return ONLY a JSON object with your analysis:
{{"confidence": 0.85, 
  "reasoning": "Explanation...",
  "favored_entity": "A or B based on trust",
  "trust_differential": {trust_a} - {trust_b}}}
Assign a confidence score from 0.0 (unlikely contradiction) to 1.0 (certain contradiction).
Higher trust differential = more confidence in which entity is correct."""

    SUGGEST_RESOLUTION_TEMPLATE = """You are a "Lore Arbiter's Assistant."
A highly confident contradiction has been detected:
ENTITY_A: {entity_a}
ENTITY_B: {entity_b}
DETECTED CONTRADICTION (Confidence: {confidence}):
{contradiction}

Your task is to suggest 1-3 possible resolutions for the human arbiter (the DM).
NEVER decide the "truth." Only present options. Adhere to the Gospel Principle.
Example: "Verify the 'death_date' of Entity A from Source X."

Return ONLY a JSON object like this:
{{"reasoning": "The core conflict is a temporal paradox.",
  "possible_resolutions": ["SUGGESTION 1: ..."]
}}"""

    DETECTION_PROMPT_TEMPLATE = """You are a lore consistency analyzer implementing the GOSPEL PRINCIPLE.

=== TRUST SCORES (The Gospel Principle) ===
Entity A Trust Score: {trust_a} ({confidence_a})
Entity B Trust Score: {trust_b} ({confidence_b})

CRITICAL RULE: The entity with the HIGHER trust score is GROUND TRUTH.
- If trust scores differ significantly (>0.2), the higher-trust entity is CORRECT.
- If one entity is "human_approved" (trust=1.0), it CANNOT be wrong.
- When flagging contradictions, always indicate which entity should be updated.

=== ENTITY A (Trust: {trust_a}) ===
{entity_a}

=== ENTITY B (Trust: {trust_b}) ===
{entity_b}

Identify contradictions (attribute, relationship, temporal, geographic, narrative).
Return ONLY a JSON array like:
[{{"type":"temporal","severity":"HIGH","description":"...",
"evidence_a":"...","evidence_b":"...","confidence":0.9,
"reasoning":"...","favored_entity":"A or B (based on trust)",
"entity_to_update":"A or B (the lower-trust one)",
"possible_resolutions":["..."]}}]
If none, return []."""

    # Legacy template without trust scores (for backwards compatibility)
    DETECTION_PROMPT_TEMPLATE_LEGACY = """You are a lore consistency analyzer. Compare:

ENTITY_A:
{entity_a}

ENTITY_B:
{entity_b}

Identify contradictions (attribute, relationship, temporal, geographic, narrative).
Return ONLY a JSON array like:
[{{"type":"temporal","severity":"HIGH","description":"...",
"evidence_a":"...","evidence_b":"...","confidence":0.9,
"reasoning":"...","possible_resolutions":["..."]}}]
If none, return []."""

    @staticmethod
    def get_system_prompt(context: dict = None) -> str:
        if context is None:
            context = {"campaign_name": "Fantasy"}
        return AuditorPrompts.SYSTEM.format(**context)

    @staticmethod
    def build_detection_prompt(
        entity_a: str, 
        entity_b: str,
        confidence_a: str = "ai_generated",
        confidence_b: str = "ai_generated"
    ) -> str:
        """
        Build detection prompt with trust scores for Gospel Principle compliance.
        
        Args:
            entity_a: JSON string of first entity
            entity_b: JSON string of second entity
            confidence_a: Confidence level of entity A (e.g., "human_approved", "ai_generated")
            confidence_b: Confidence level of entity B
            
        Returns:
            Formatted prompt with trust score context
        """
        trust_a = get_trust_score(confidence_a)
        trust_b = get_trust_score(confidence_b)
        
        return AuditorPrompts.DETECTION_PROMPT_TEMPLATE.format(
            entity_a=entity_a, 
            entity_b=entity_b,
            trust_a=trust_a,
            trust_b=trust_b,
            confidence_a=confidence_a,
            confidence_b=confidence_b
        )

    @staticmethod
    def build_contradiction_check_prompt(graph_truth: str, new_text: str) -> str:
        return AuditorPrompts.CONTRADICTION_CHECK_TEMPLATE.format(graph_truth=graph_truth, new_text=new_text)

    @staticmethod
    def build_score_confidence_prompt(
        entity_a: str, 
        entity_b: str, 
        contradiction: str,
        confidence_a: str = "ai_generated",
        confidence_b: str = "ai_generated"
    ) -> str:
        """
        Build scoring prompt with trust scores for Gospel Principle compliance.
        
        Args:
            entity_a: JSON string of first entity
            entity_b: JSON string of second entity
            contradiction: JSON string of detected contradiction
            confidence_a: Confidence level of entity A
            confidence_b: Confidence level of entity B
            
        Returns:
            Formatted prompt with trust score context
        """
        trust_a = get_trust_score(confidence_a)
        trust_b = get_trust_score(confidence_b)
        
        return AuditorPrompts.SCORE_CONFIDENCE_TEMPLATE.format(
            entity_a=entity_a, 
            entity_b=entity_b, 
            contradiction=contradiction,
            trust_a=trust_a,
            trust_b=trust_b,
            confidence_a=confidence_a,
            confidence_b=confidence_b
        )

    @staticmethod
    def build_suggest_resolution_prompt(entity_a: str, entity_b: str, contradiction: str, confidence: float) -> str:
        return AuditorPrompts.SUGGEST_RESOLUTION_TEMPLATE.format(entity_a=entity_a, entity_b=entity_b, contradiction=contradiction, confidence=confidence)

