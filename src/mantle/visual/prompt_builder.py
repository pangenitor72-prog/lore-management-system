# src/mantle/visual/prompt_builder.py
"""
Prompt Builder for the Visual Engine.

Assembles image generation prompts from multiple layers:
1. Style prefix (artistic medium)
2. World descriptors (content vocabulary)
3. Composition template
4. Visual description (from Gemini)
5. Mood modifier
6. Lighting
7. Style suffix
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from .types import (
    ImageType,
    PromptResult,
    StyleProfile,
    VisualAssessment,
    WorldDescriptors,
    WorldVisualIdentity,
)

logger = logging.getLogger(__name__)

# Path to style profile JSON files
STYLES_DIR = Path(__file__).parent / "styles"


class PromptBuilder:
    """
    Builds image generation prompts from style profiles and visual assessments.

    Combines:
    - Style profile (artistic medium, mood modifiers, composition templates)
    - World visual identity (content vocabulary, exclusions)
    - Visual assessment from Gemini (scene description, mood, lighting)
    """

    def __init__(self, style: StyleProfile, world_identity: WorldVisualIdentity):
        """
        Initialize the PromptBuilder.

        Args:
            style: The style profile defining artistic medium
            world_identity: The world's visual identity with content vocabulary
        """
        self.style = style
        self.world_identity = world_identity

    def build(self, assessment: VisualAssessment) -> PromptResult:
        """
        Build a complete prompt from a visual assessment.

        Args:
            assessment: The visual assessment from Gemini

        Returns:
            PromptResult with prompt, negative_prompt, and image dimensions
        """
        parts: list[str] = []

        # Layer 1: Style prefix (artistic medium)
        if self.style.prompt_prefix:
            parts.append(self.style.prompt_prefix)

        # Layer 2: World descriptors (content vocabulary) - select relevant ones
        world_desc = self._get_relevant_world_descriptors(assessment)
        if world_desc:
            parts.append(world_desc)

        # Layer 3: Composition template
        composition = self._get_composition(assessment)
        if composition:
            parts.append(composition)

        # Layer 4: Gemini's visual description (the actual scene content)
        if assessment.visual_description:
            parts.append(assessment.visual_description)

        # Layer 5: Character or item description if applicable
        if assessment.image_type == "portrait" and assessment.character_description:
            parts.append(assessment.character_description)
        if assessment.image_type == "item" and assessment.item_description:
            parts.append(assessment.item_description)

        # Layer 6: Mood modifier
        mood_mod = self.style.mood_modifiers.get(assessment.mood, "")
        if mood_mod:
            parts.append(mood_mod)

        # Layer 7: Lighting
        if assessment.lighting:
            parts.append(assessment.lighting)

        # Layer 8: Style suffix (quality/exclusion keywords)
        if self.style.prompt_suffix:
            parts.append(self.style.prompt_suffix)

        # Build negative prompt
        neg_parts = []
        if self.style.negative_prompt:
            neg_parts.append(self.style.negative_prompt)
        if self.world_identity.visual_exclusions:
            neg_parts.append(self.world_identity.visual_exclusions)

        # Get image specs for this type
        specs = self.style.image_specs.get(assessment.image_type)
        if specs:
            width = specs.width
            height = specs.height
        else:
            # Default to scene specs
            width = 1024
            height = 576

        return PromptResult(
            prompt=", ".join(filter(None, parts)),
            negative_prompt=", ".join(filter(None, neg_parts)),
            width=width,
            height=height,
        )

    def _get_composition(self, assessment: VisualAssessment) -> str:
        """Get the appropriate composition template."""
        composition_set = self.style.composition_templates.get(assessment.image_type, {})

        # Try to get the specific camera angle, fall back to default
        camera = assessment.camera_angle or "default"
        composition = composition_set.get(camera) or composition_set.get("default", "")

        return composition

    def _get_relevant_world_descriptors(self, assessment: VisualAssessment) -> str:
        """
        Get world descriptors relevant to the image type.

        Different image types need different descriptors:
        - Scenes/locations: architecture, landscape, vegetation
        - Portraits: character_design, cultural_artifacts
        - Items: cultural_artifacts
        - Moments: everything (they're cinematic)
        """
        wd = self.world_identity.world_descriptors
        relevant: list[str] = []

        # Always include color and lighting tendency
        if wd.color_world:
            relevant.append(wd.color_world)
        if wd.lighting_tendency:
            relevant.append(wd.lighting_tendency)

        # Include type-specific descriptors
        if assessment.image_type in ("scene", "location_card"):
            if wd.architecture:
                relevant.append(wd.architecture)
            if wd.landscape:
                relevant.append(wd.landscape)
            if wd.vegetation:
                relevant.append(wd.vegetation)

        elif assessment.image_type == "portrait":
            if wd.character_design:
                relevant.append(wd.character_design)
            if wd.cultural_artifacts:
                relevant.append(wd.cultural_artifacts)

        elif assessment.image_type == "item":
            if wd.cultural_artifacts:
                relevant.append(wd.cultural_artifacts)

        elif assessment.image_type == "moment":
            # Moments get everything - they're cinematic
            for value in [
                wd.architecture,
                wd.landscape,
                wd.vegetation,
                wd.character_design,
                wd.creatures,
                wd.cultural_artifacts,
            ]:
                if value:
                    relevant.append(value)

        return ", ".join(relevant)


def load_style_profile(style_id: str) -> Optional[StyleProfile]:
    """
    Load a style profile from JSON file.

    Args:
        style_id: The style profile ID (e.g., "dark_fantasy_painterly")

    Returns:
        StyleProfile or None if not found
    """
    style_path = STYLES_DIR / f"{style_id}.json"

    if not style_path.exists():
        logger.warning(f"Style profile not found: {style_path}")
        return None

    try:
        with open(style_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return StyleProfile.from_dict(data)
    except Exception as e:
        logger.error(f"Failed to load style profile {style_id}: {e}")
        return None


def load_all_style_profiles() -> Dict[str, StyleProfile]:
    """
    Load all style profiles from the styles directory.

    Returns:
        Dictionary mapping style_profile_id to StyleProfile
    """
    profiles = {}

    if not STYLES_DIR.exists():
        logger.warning(f"Styles directory not found: {STYLES_DIR}")
        return profiles

    for style_file in STYLES_DIR.glob("*.json"):
        try:
            with open(style_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            profile = StyleProfile.from_dict(data)
            profiles[profile.style_profile_id] = profile
            logger.debug(f"Loaded style profile: {profile.style_profile_id}")
        except Exception as e:
            logger.error(f"Failed to load style profile {style_file}: {e}")

    logger.info(f"Loaded {len(profiles)} style profiles")
    return profiles


def create_prompt_builder(
    style_id: str,
    world_identity: Optional[WorldVisualIdentity] = None,
) -> Optional[PromptBuilder]:
    """
    Create a PromptBuilder for a given style and world.

    Args:
        style_id: The style profile ID
        world_identity: Optional world visual identity (uses empty if not provided)

    Returns:
        PromptBuilder or None if style not found
    """
    style = load_style_profile(style_id)
    if not style:
        return None

    # Use empty world identity if none provided
    if world_identity is None:
        world_identity = WorldVisualIdentity(
            style_profile_id=style_id,
            world_descriptors=WorldDescriptors(),
            visual_exclusions="",
        )

    return PromptBuilder(style, world_identity)
