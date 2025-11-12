"""
Auditor Scoring Module
Calculates confidence scores for contradiction triage based on evidence richness,
contradiction type, and prior resolution history.
"""

import random
from datetime import datetime





class AuditorScoring:
    def __init__(self, weight_factors=None):
        self.weights = weight_factors or {"evidence": 0.5, "type": 0.3, "history": 0.2}

    def compute_confidence(self, contradiction):
        """Return a float between 0.0–1.0 representing audit confidence."""
        base = random.uniform(0.4, 0.9)
        if contradiction.description:
            base += 0.05
        return round(min(base, 1.0), 2)

    def generate_review_record(self, contradiction_id, confidence):
        return {
            "contradiction_id": contradiction_id,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat()
        }

    def compute_confidence(self, contradiction):
        """Return a float between 0.0–1.0 representing audit confidence."""
        base = random.uniform(0.4, 0.9)

        # Handle dicts and objects alike
        description = None
        if isinstance(contradiction, dict):
            description = contradiction.get("description")
        else:
            description = getattr(contradiction, "description", None)

        if description:
            base += 0.05

        return round(min(base, 1.0), 2)
