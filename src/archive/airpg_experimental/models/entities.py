# src/airpg/models/entities.py
"""
Pydantic V2 models for core AIRpg entities.
These models define the data structure for entities within the AIRpg engine,
based on the canonical schema defined in docs/airpg/DATABASE_SCHEMA.md.
"""

from typing import Optional, List
from pydantic import BaseModel, Field

class Faction(BaseModel):
    """A group or organization within the world."""
    id: str
    name: str
    description: Optional[str] = None

class OCEANProfile(BaseModel):
    """
    Represents the OCEAN personality traits of an NPC.
    Values are typically floats between 0.0 and 1.0.
    """
    id: str
    npc_id: str
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float

class NPC(BaseModel):
    """A non-player character in the world."""
    id: str
    name: str
    description: Optional[str] = None
    faction_id: Optional[str] = None
    ocean_profile_id: Optional[str] = None

class Location(BaseModel):
    """A place in the world."""
    id: str
    name: str
    description: Optional[str] = None

class StoryThread(BaseModel):
    """A narrative arc or quest line."""
    id: str
    name: str
    description: Optional[str] = None
    is_active: bool
