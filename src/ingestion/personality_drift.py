# ===========================================
# SMART INGESTOR — PERSONALITY DRIFT ENGINE
# ===========================================
# File: src/ingestion/personality_drift.py
# NEW MODULE (safe to add)
# ===========================================

from typing import Dict, List, Optional
from dataclasses import dataclass
import math
import re

STRONG_LANGUAGE = [
    "always", "never", "known for", "defined by", "renowned for",
    "consistently", "in every circumstance", "his reputation",
    "her reputation", "their reputation"
]

# Mapping descriptive traits -> OCEAN influence
TRAIT_MAP = {
    "ruthless":      {"agreeableness": -0.10, "neuroticism": +0.02},
    "merciful":      {"agreeableness": +0.08},
    "cunning":       {"openness": +0.05, "conscientiousness": +0.05},
    "relentless":    {"conscientiousness": +0.08, "neuroticism": +0.02},
    "fearful":       {"neuroticism": +0.06},
    "calm":          {"neuroticism": -0.06},
    "ambitious":     {"openness": +0.05, "conscientiousness": +0.05},
    "paranoid":      {"neuroticism": +0.12},
    "brutal":        {"agreeableness": -0.10},
    "compassionate": {"agreeableness": +0.10},
}

@dataclass
class DriftResult:
    deltas: Dict[str, float]
    strong_language: bool
    count: int
    applied: bool

class PersonalityDriftEngine:
    """
    Implements MODERATE DRIFT MODEL (Option B).
    Personality changes occur only when stable patterns appear in descriptions.
    """

    def __init__(self):
        pass

    def detect_trait_terms(self, text: str) -> List[str]:
        text = text.lower()
        return [t for t in TRAIT_MAP if t in text]

    def strong_language_multiplier(self, text: str) -> float:
        text = text.lower()
        return 1.5 if any(s in text for s in STRONG_LANGUAGE) else 1.0

    def compute_drift(self, trait_terms: List[str], occurrences: int, text: str) -> DriftResult:
        """
        occurrences = how many times this trait (or cluster) appeared
        as tracked by SmartIngestor's memory system.
        """

        if occurrences < 2:
            return DriftResult({}, False, occurrences, False)  # no drift yet

        base_factor = 0.02 if occurrences == 2 else 0.05 if occurrences == 3 else 0.10
        strong = self.strong_language_multiplier(text)

        deltas = {}
        for term in trait_terms:
            for trait, amount in TRAIT_MAP[term].items():
                drift = amount * base_factor * strong
                deltas[trait] = deltas.get(trait, 0) + drift

        return DriftResult(deltas, strong > 1.0, occurrences, True)

    def apply_drift(self, ocean: Dict[str, float], deltas: Dict[str, float]):
        for trait, delta in deltas.items():
            current = ocean.get(trait, 0.5)
            # Ensure float conversion if stored as strings/decimals in DB
            if current is None: current = 0.5
            current = float(current)
            
            new_value = max(0.0, min(1.0, current + delta))
            ocean[trait] = new_value
        return ocean

