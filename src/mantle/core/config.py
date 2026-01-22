"""
Core application configuration settings.
"""

# Confidence rules for entity trust scoring
CONFIDENCE_RULES = {
    "human_approved": {
        "trust_score": 1.0,
        "can_be_contradicted": False,
        "requires_review": False
    },
    "ai_verified": {
        "trust_score": 0.8,
        "can_be_contradicted": True,
        "requires_review": False,
        "auto_promote_after_sessions": 5
    },
    "ai_generated": {
        "trust_score": 0.5,
        "can_be_contradicted": True,
        "requires_review": False
    },
    "ai_flagged": {
        "trust_score": 0.3,
        "can_be_contradicted": True,
        "requires_review": True,
        "blocks_promotion": True
    }
}
