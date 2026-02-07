# src/mantle/visual/types.py
"""
Type definitions for the Visual Engine.

These dataclasses mirror the JSON structures used in style profiles
and the visual_assessment blocks from Gemini responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

# Image type literals
ImageType = Literal["scene", "portrait", "location_card", "item", "moment"]

# Mood literals
Mood = Literal["tense", "joyful", "eerie", "epic", "peaceful", "melancholy", "awe", "dread"]

# Camera angle literals
CameraAngle = Literal["wide", "medium", "close", "low_angle", "overhead", "default"]


@dataclass
class ImageSpecs:
    """Specifications for a generated image."""
    aspect_ratio: str
    width: int
    height: int


@dataclass
class StyleProfile:
    """
    Defines the artistic medium for image generation.

    Loaded from JSON files in visual/styles/.
    """
    style_profile_id: str
    display_name: str

    prompt_prefix: str
    prompt_suffix: str
    negative_prompt: str

    mood_modifiers: Dict[str, str]
    composition_templates: Dict[str, Dict[str, str]]
    image_specs: Dict[str, ImageSpecs]

    @classmethod
    def from_dict(cls, data: Dict) -> "StyleProfile":
        """Create a StyleProfile from a dictionary (loaded from JSON)."""
        # Convert image_specs dicts to ImageSpecs objects
        image_specs = {}
        for img_type, specs in data.get("image_specs", {}).items():
            image_specs[img_type] = ImageSpecs(
                aspect_ratio=specs.get("aspect_ratio", "16:9"),
                width=specs.get("width", 1024),
                height=specs.get("height", 576),
            )

        return cls(
            style_profile_id=data.get("style_profile_id", "unknown"),
            display_name=data.get("display_name", "Unknown Style"),
            prompt_prefix=data.get("prompt_prefix", ""),
            prompt_suffix=data.get("prompt_suffix", ""),
            negative_prompt=data.get("negative_prompt", ""),
            mood_modifiers=data.get("mood_modifiers", {}),
            composition_templates=data.get("composition_templates", {}),
            image_specs=image_specs,
        )


@dataclass
class WorldDescriptors:
    """
    Content vocabulary for a specific world.

    Describes what things look like in this world (architecture, landscape, etc.)
    """
    architecture: str = ""
    landscape: str = ""
    vegetation: str = ""
    character_design: str = ""
    creatures: str = ""
    color_world: str = ""
    lighting_tendency: str = ""
    cultural_artifacts: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "WorldDescriptors":
        """Create WorldDescriptors from a dictionary."""
        return cls(
            architecture=data.get("architecture", ""),
            landscape=data.get("landscape", ""),
            vegetation=data.get("vegetation", ""),
            character_design=data.get("character_design", ""),
            creatures=data.get("creatures", ""),
            color_world=data.get("color_world", ""),
            lighting_tendency=data.get("lighting_tendency", ""),
            cultural_artifacts=data.get("cultural_artifacts", ""),
        )


@dataclass
class WorldVisualIdentity:
    """
    Visual identity for a seed world.

    Combines a style profile reference with world-specific descriptors.
    """
    style_profile_id: str
    world_descriptors: WorldDescriptors
    visual_exclusions: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "WorldVisualIdentity":
        """Create WorldVisualIdentity from a dictionary."""
        wd_data = data.get("world_descriptors", {})
        return cls(
            style_profile_id=data.get("style_profile_id", "dark_fantasy_painterly"),
            world_descriptors=WorldDescriptors.from_dict(wd_data),
            visual_exclusions=data.get("visual_exclusions", ""),
        )


@dataclass
class VisualAssessment:
    """
    Visual assessment from Gemini's response.

    Contains all the information needed to generate an image.
    """
    image_type: ImageType
    visual_description: str
    mood: Mood
    lighting: str
    key_elements: List[str] = field(default_factory=list)

    # Optional fields depending on image type
    camera_angle: Optional[CameraAngle] = None
    character_description: Optional[str] = None
    item_description: Optional[str] = None
    characters_visible: Optional[List[str]] = None

    # IDs for caching
    location_id: Optional[str] = None
    character_id: Optional[str] = None
    item_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "VisualAssessment":
        """Create VisualAssessment from a dictionary (from Gemini response)."""
        return cls(
            image_type=data.get("image_type", "scene"),
            visual_description=data.get("visual_description", ""),
            mood=data.get("mood", "tense"),
            lighting=data.get("lighting", ""),
            key_elements=data.get("key_elements", []),
            camera_angle=data.get("camera_angle"),
            character_description=data.get("character_description"),
            item_description=data.get("item_description"),
            characters_visible=data.get("characters_visible"),
            location_id=data.get("location_id"),
            character_id=data.get("character_id"),
            item_id=data.get("item_id"),
        )


@dataclass
class PromptResult:
    """Result of prompt assembly."""
    prompt: str
    negative_prompt: str
    width: int
    height: int


@dataclass
class GenerationResult:
    """Result of image generation."""
    url: str
    seed: Optional[int] = None
    provider: str = ""
    model: str = ""
    generation_time_ms: int = 0
    cost_estimate: float = 0.0
