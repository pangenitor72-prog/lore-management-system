# src/lms/memory/__init__.py
"""
Experiential Memory System

The third memory layer that makes worlds feel alive:
- Graph DB (Neo4j): Canonical truth - what IS
- Vector DB: Semantic connections - what RELATES
- Experiential Memory: Living memory - what is REMEMBERED

This module handles:
- Agent beliefs (what NPCs think they know)
- Salience (what matters, what fades)
- Echoes (events that ripple through time)
- Legends (player mythology emerging from deeds)
- Impressions (how the world sees the player)
"""

from .models import (
    Echo,
    Whisper,
    Impression,
    Legend,
    AgentBelief,
    Thread,
    SalienceLevel,
    BeliefStrength,
    ImpressionValence,
    WhisperMutation,
)
from .experiential import ExperientialMemory
from .manager import MemoryManager

__all__ = [
    "Echo",
    "Whisper",
    "Impression",
    "Legend",
    "AgentBelief",
    "Thread",
    "SalienceLevel",
    "BeliefStrength",
    "ImpressionValence",
    "WhisperMutation",
    "ExperientialMemory",
    "MemoryManager",
]
