"""
Boundary Enforcement - Player agency and DM authority management.

Implements the social contract of tabletop RPGs:
- Players control their character's ATTEMPTS
- DM controls OUTCOMES, NPC behavior, and what exists
- DM can override agency only with in-world justification

Detects violations and educates players without being punitive.
"""

import re
from enum import Enum
from typing import Dict, Any, Optional, List
import asyncio


class PlayerIntentType(str, Enum):
    """Classification of player input by intent."""
    
    # Valid player intents
    ACTION = "action"              # "I attack the goblin"
    QUESTION = "question"          # "Is there a library here?"
    PERCEPTION = "perception"      # "I search for traps"
    DIALOGUE = "dialogue"          # "I ask the bartender about rumors"
    
    # Boundary violations
    DECLARATION = "declaration"    # "There's a sword in the chest" (player declaring what exists)
    OUTCOME_FORCING = "outcome_forcing"  # "I successfully pick the lock" (player declaring success)
    META_CONTROL = "meta_control"  # "The guard lets me pass" (player controlling NPCs)


class PlayerIntent:
    """Analyzes and validates player input against game boundaries."""
    
    # Patterns that indicate declarations (player stating what exists)
    DECLARATION_PATTERNS = [
        r'^there(\'s| is| are| was| were)',
        r'^the .+ (is|are|has|have)',
        r'^this .+ (is|are|has|have)',
        r'\bactually\b',
        r'^.+ exists?$',
        r'\bturns? out\b'
    ]
    
    # Patterns that indicate outcome forcing (player declaring success)
    OUTCOME_FORCING_PATTERNS = [
        r'\bi succeed',
        r'\bi manage to\b',
        r'\bi successfully\b',
        r'\bit works\b',
        r'\bi win\b',
        r'\bi kill\b',
        r'\bi find\b',
        r'\bi discover\b'
    ]
    
    # Patterns that indicate meta-control (player controlling NPCs/world)
    META_CONTROL_PATTERNS = [
        r'^the .+ (lets?|allows?|agrees?|decides?)',
        r'^they (let|allow|agree|decide)',
        r'^he (lets?|allows?|agrees?|decides?)',
        r'^she (lets?|allows?|agrees?|decides?)'
    ]
    
    @staticmethod
    async def classify_intent(player_input: str) -> PlayerIntentType:
        """
        Classify player intent to detect boundary violations.
        
        Args:
            player_input: Raw player input
            
        Returns:
            PlayerIntentType classification
        """
        lower_input = player_input.lower().strip()
        
        # Check for declarations (player dictating reality)
        for pattern in PlayerIntent.DECLARATION_PATTERNS:
            if re.search(pattern, lower_input):
                return PlayerIntentType.DECLARATION
        
        # Check for outcome forcing (declaring success)
        for pattern in PlayerIntent.OUTCOME_FORCING_PATTERNS:
            if re.search(pattern, lower_input):
                return PlayerIntentType.OUTCOME_FORCING
        
        # Check for meta-control (controlling NPCs)
        for pattern in PlayerIntent.META_CONTROL_PATTERNS:
            if re.search(pattern, lower_input):
                return PlayerIntentType.META_CONTROL
        
        # Check for questions (valid)
        if lower_input.startswith(("is there", "are there", "does", "can i", "could i", "may i")):
            return PlayerIntentType.QUESTION
        
        # Check for perception (valid)
        if any(word in lower_input for word in ["search", "look", "examine", "inspect", "check"]):
            return PlayerIntentType.PERCEPTION
        
        # Check for dialogue (valid)
        if any(word in lower_input for word in ["ask", "tell", "say", "speak", "talk"]):
            return PlayerIntentType.DIALOGUE
        
        # Default: assume action (valid)
        return PlayerIntentType.ACTION
    
    @staticmethod
    def is_violation(intent_type: PlayerIntentType) -> bool:
        """Check if intent type is a boundary violation."""
        return intent_type in [
            PlayerIntentType.DECLARATION,
            PlayerIntentType.OUTCOME_FORCING,
            PlayerIntentType.META_CONTROL
        ]
    
    @staticmethod
    def get_violation_type_name(intent_type: PlayerIntentType) -> str:
        """Get human-readable violation type name."""
        type_names = {
            PlayerIntentType.DECLARATION: "declare what exists",
            PlayerIntentType.OUTCOME_FORCING: "declare outcomes",
            PlayerIntentType.META_CONTROL: "control NPCs"
        }
        return type_names.get(intent_type, "unknown violation")


class AgencyOverride:
    """Manages when DM can legitimately override player agency."""
    
    VALID_OVERRIDE_REASONS = {
        "magic": {
            "examples": ["charm spell", "domination", "suggestion", "mind control"],
            "justification": "Magical compulsion overrides free will"
        },
        "injury": {
            "examples": ["unconscious", "paralyzed", "stunned", "petrified"],
            "justification": "Physical incapacitation prevents action"
        },
        "environmental": {
            "examples": ["falling", "drowning", "burning", "crushed"],
            "justification": "Physics and environment dictate outcome"
        },
        "death": {
            "examples": ["instant death", "disintegration", "soul destruction"],
            "justification": "Death ends agency"
        },
        "madness": {
            "examples": ["eldritch horror", "insanity", "psychic break"],
            "justification": "Mental fracture causes involuntary actions"
        }
    }
    
    @staticmethod
    def can_override_agency(reason: str) -> bool:
        """
        Check if DM can legitimately override player agency.
        
        Args:
            reason: Reason for override (e.g., "charm spell")
            
        Returns:
            True if override is valid
        """
        reason_lower = reason.lower()
        
        for category, data in AgencyOverride.VALID_OVERRIDE_REASONS.items():
            if any(example in reason_lower for example in data["examples"]):
                return True
        
        return False
    
    @staticmethod
    def format_override(reason: str, effect: str) -> str:
        """
        Format agency override with justification.
        
        Args:
            reason: Reason for override (e.g., "charm spell")
            effect: What happens (e.g., "trust the vampire")
            
        Returns:
            Formatted override message with justification
        """
        reason_lower = reason.lower()
        category = "environmental"
        
        # Find matching category
        for cat, data in AgencyOverride.VALID_OVERRIDE_REASONS.items():
            if any(example in reason_lower for example in data["examples"]):
                category = cat
                break
        
        justification = AgencyOverride.VALID_OVERRIDE_REASONS[category]["justification"]
        
        return f"""⚡ **Agency Override**: {reason.title()}

{effect}

*({justification})*"""
    
    @staticmethod
    def get_override_examples() -> List[str]:
        """Get list of valid override examples for documentation."""
        examples = []
        for category, data in AgencyOverride.VALID_OVERRIDE_REASONS.items():
            examples.extend(data["examples"])
        return examples
