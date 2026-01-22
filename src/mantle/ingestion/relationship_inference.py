# ===========================================
# SMART INGESTOR — RELATIONSHIP INFERENCE ENGINE
# ===========================================
# File: src/ingestion/relationship_inference.py
# NEW MODULE (safe to add)
# ===========================================

from dataclasses import dataclass
from typing import List, Dict, Optional
import re

# Relationship patterns — RELIABLE ONLY
RELATION_PATTERNS = {
    "served_under": [
        r"served under ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
        r"in service to ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
        r"sworn to ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
    ],
    "member_of": [
        r"member of the ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
        r"belonged to the ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
        r"of the ([A-Z][a-zA-Z]+ Guild|Order|Legion|House)",
    ],
    "enemy_of": [
        r"enemy of ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
        r"feuded with ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
        r"at war with ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
    ],
    "ally_of": [
        r"ally of ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
        r"allied with ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
        r"in alliance with ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
    ],
    "loyal_to": [
        r"loyal to ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
        r"devoted to ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*)",
    ],
    # Family patterns can be added later if desired
}

@dataclass
class InferredRelationship:
    origin_id: str
    target_name: str
    relationship_type: str
    confidence: float
    sentence: str


class RelationshipInferenceEngine:
    """
    Extracts RELIABLE relationship candidates from input text using
    carefully curated pattern-matching and contextual verification.
    """

    def __init__(self):
        pass

    def infer(self, text: str, origin_entity_name: str, origin_entity_id: str) -> List[InferredRelationship]:
        results = []
        lowered = text.lower()

        for relation_type, patterns in RELATION_PATTERNS.items():
            for pattern in patterns:
                m = re.search(pattern, text)
                if not m:
                    continue

                target = m.group(1).strip()

                # Block pronoun references
                if target.lower() in ["him", "her", "them", "he", "she", "they"]:
                    continue

                confidence = 0.8  # default moderate confidence

                # Boost confidence for strong wording
                if any(word in lowered for word in ["sworn", "loyal", "enemy", "allied", "member"]):
                    confidence += 0.1

                result = InferredRelationship(
                    origin_id=origin_entity_id,
                    target_name=target,
                    relationship_type=relation_type,
                    confidence=min(confidence, 1.0),
                    sentence=text
                )
                results.append(result)

        return results

