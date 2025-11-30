"""Auditor Agent Prompts - Contradiction detection and severity classification."""

from dataclasses import dataclass

@dataclass
class PromptMetadata:
    version: str
    author: str
    date: str
    tested_with: str
    temperature: float

class AuditorPrompts:
    """All prompts for the Auditor Agent."""
    
    SYSTEM = """You are the Lore Auditor for the {campaign_name} campaign.
Your role is to detect contradictions in the canonical lore and classify their severity.

When analyzing entities:
- Check for direct contradictions (same name, different type)
- Check for temporal impossibilities (events before they happened)
- Check for logical inconsistencies
- Classify severity as CRITICAL, MINOR, or NONE

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

    SCORE_CONFIDENCE_TEMPLATE = """You are a confidence score analyst.
A "flash" model has detected the following contradiction:
ENTITY_A: {entity_a}
ENTITY_B: {entity_b}
DETECTED CONTRADICTION: {contradiction}
Your task is to analyze this contradiction and the evidence.
Return ONLY a JSON object with your analysis, like this:
{{"confidence": 0.85, "reasoning": "The flash model's reasoning is sound..."}}
Assign a confidence score from 0.0 (unlikely) to 1.0 (certain)."""

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

    DETECTION_PROMPT_TEMPLATE = """You are a lore consistency analyzer. Compare:

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
    def build_detection_prompt(entity_a: str, entity_b: str) -> str:
        return AuditorPrompts.DETECTION_PROMPT_TEMPLATE.format(entity_a=entity_a, entity_b=entity_b)

    @staticmethod
    def build_contradiction_check_prompt(graph_truth: str, new_text: str) -> str:
        return AuditorPrompts.CONTRADICTION_CHECK_TEMPLATE.format(graph_truth=graph_truth, new_text=new_text)

    @staticmethod
    def build_score_confidence_prompt(entity_a: str, entity_b: str, contradiction: str) -> str:
        return AuditorPrompts.SCORE_CONFIDENCE_TEMPLATE.format(entity_a=entity_a, entity_b=entity_b, contradiction=contradiction)

    @staticmethod
    def build_suggest_resolution_prompt(entity_a: str, entity_b: str, contradiction: str, confidence: float) -> str:
        return AuditorPrompts.SUGGEST_RESOLUTION_TEMPLATE.format(entity_a=entity_a, entity_b=entity_b, contradiction=contradiction, confidence=confidence)

