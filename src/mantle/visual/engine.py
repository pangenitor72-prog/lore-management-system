# src/mantle/visual/engine.py
"""
Visual Engine Orchestrator.

Main entry point for the Visual Engine. Coordinates prompt building,
caching, and image generation to produce contextual images during gameplay.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .cache_manager import CachedImage, CacheManager
from .prompt_builder import PromptBuilder, load_style_profile
from .providers import GenerationResult, ImageProvider, select_provider
from .types import (
    StyleProfile,
    VisualAssessment,
    WorldDescriptors,
    WorldVisualIdentity,
)

logger = logging.getLogger(__name__)


@dataclass
class VisualEngineConfig:
    """Configuration for the Visual Engine."""

    enabled: bool = True
    cache_dir: Path = Path("./visual_cache")
    max_images_per_session: int = 30
    provider_preference: str = "flux"  # "flux" or "dalle"


@dataclass
class ImageResult:
    """Result of processing a visual assessment."""

    url: str
    from_cache: bool
    image_type: str
    generation_time_ms: int = 0
    cost_estimate: float = 0.0
    provider: str = ""
    seed: Optional[int] = None


class VisualEngine:
    """
    Main Visual Engine orchestrator.

    Coordinates:
    - PromptBuilder: Assembles prompts from style + world + assessment
    - CacheManager: Checks/stores cached images
    - ImageProvider: Generates new images via Flux or DALL-E

    Usage:
        engine = await VisualEngine.create(world_identity)
        result = await engine.process_assessment(assessment, campaign_id)
        # result.url contains the image URL (cached or freshly generated)
    """

    def __init__(
        self,
        prompt_builder: PromptBuilder,
        cache_manager: CacheManager,
        provider: ImageProvider,
        config: VisualEngineConfig,
    ):
        """
        Initialize the Visual Engine.

        Use VisualEngine.create() factory method instead of direct instantiation.
        """
        self.prompt_builder = prompt_builder
        self.cache_manager = cache_manager
        self.provider = provider
        self.config = config
        self._session_image_count = 0

    @classmethod
    async def create(
        cls,
        world_identity: WorldVisualIdentity,
        config: Optional[VisualEngineConfig] = None,
    ) -> "VisualEngine":
        """
        Factory method to create a VisualEngine instance.

        Args:
            world_identity: The world's visual identity (style + descriptors)
            config: Optional engine configuration

        Returns:
            Configured VisualEngine instance

        Raises:
            RuntimeError: If style profile not found or no provider available
        """
        if config is None:
            config = VisualEngineConfig(
                enabled=os.getenv("VISUAL_ENGINE_ENABLED", "true").lower() == "true",
                cache_dir=Path(os.getenv("VISUAL_CACHE_DIR", "./visual_cache")),
                max_images_per_session=int(
                    os.getenv("VISUAL_MAX_IMAGES_PER_SESSION", "30")
                ),
                provider_preference=os.getenv("VISUAL_PROVIDER_PREFERENCE", "flux"),
            )

        # Load the style profile
        style = load_style_profile(world_identity.style_profile_id)
        if not style:
            raise RuntimeError(
                f"Style profile not found: {world_identity.style_profile_id}"
            )

        # Create prompt builder
        prompt_builder = PromptBuilder(style, world_identity)

        # Create cache manager
        cache_manager = CacheManager(cache_dir=config.cache_dir)

        # Select image provider
        provider = await select_provider()

        logger.info(
            f"VisualEngine initialized: style={world_identity.style_profile_id}, "
            f"provider={provider.get_name()}"
        )

        return cls(prompt_builder, cache_manager, provider, config)

    @classmethod
    async def create_with_style_id(
        cls,
        style_id: str,
        world_descriptors: Optional[WorldDescriptors] = None,
        visual_exclusions: str = "",
        config: Optional[VisualEngineConfig] = None,
    ) -> "VisualEngine":
        """
        Convenience factory that creates a WorldVisualIdentity from components.

        Args:
            style_id: The style profile ID (e.g., "dark_fantasy_painterly")
            world_descriptors: Optional world-specific descriptors
            visual_exclusions: Things to exclude from all images
            config: Optional engine configuration

        Returns:
            Configured VisualEngine instance
        """
        world_identity = WorldVisualIdentity(
            style_profile_id=style_id,
            world_descriptors=world_descriptors or WorldDescriptors(),
            visual_exclusions=visual_exclusions,
        )
        return await cls.create(world_identity, config)

    async def process_assessment(
        self,
        assessment: VisualAssessment,
        campaign_id: str,
    ) -> ImageResult:
        """
        Process a visual assessment and return an image.

        This is the main entry point for generating images. It:
        1. Checks if the engine is enabled
        2. Checks session image limit
        3. Checks the cache for existing image
        4. If cache miss, builds prompt and generates new image
        5. Stores result in cache
        6. Returns the image URL

        Args:
            assessment: The visual assessment from Gemini
            campaign_id: The campaign ID for caching

        Returns:
            ImageResult with URL and metadata

        Raises:
            RuntimeError: If engine is disabled or limit exceeded
        """
        if not self.config.enabled:
            raise RuntimeError("Visual Engine is disabled")

        if self._session_image_count >= self.config.max_images_per_session:
            raise RuntimeError(
                f"Session image limit exceeded ({self.config.max_images_per_session})"
            )

        # Build the prompt first (needed for cache check on scenes)
        prompt_result = self.prompt_builder.build(assessment)

        # Check cache
        cached = await self.cache_manager.check_cache(
            campaign_id, assessment, prompt_result.prompt
        )

        if cached:
            logger.info(
                f"Cache hit for {assessment.image_type}: {cached.entity_id or 'scene'}"
            )
            return ImageResult(
                url=cached.url,
                from_cache=True,
                image_type=assessment.image_type,
                generation_time_ms=0,
                cost_estimate=0.0,
                provider="cache",
                seed=cached.seed,
            )

        # Cache miss - generate new image
        logger.info(
            f"Generating {assessment.image_type} image: {assessment.visual_description[:50]}..."
        )

        try:
            generation_result = await self.provider.generate(
                prompt=prompt_result.prompt,
                negative_prompt=prompt_result.negative_prompt,
                width=prompt_result.width,
                height=prompt_result.height,
            )

            # Store in cache
            cached_image = await self.cache_manager.store(
                campaign_id=campaign_id,
                assessment=assessment,
                image_url=generation_result.url,
                prompt_used=prompt_result.prompt,
                negative_prompt=prompt_result.negative_prompt,
                seed=generation_result.seed,
                provider=generation_result.provider,
                model=generation_result.model,
                width=prompt_result.width,
                height=prompt_result.height,
                generation_time_ms=generation_result.generation_time_ms,
                cost_estimate=generation_result.cost_estimate,
            )

            self._session_image_count += 1

            return ImageResult(
                url=cached_image.url,
                from_cache=False,
                image_type=assessment.image_type,
                generation_time_ms=generation_result.generation_time_ms,
                cost_estimate=generation_result.cost_estimate,
                provider=generation_result.provider,
                seed=generation_result.seed,
            )

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise

    async def process_assessment_safe(
        self,
        assessment: VisualAssessment,
        campaign_id: str,
    ) -> Optional[ImageResult]:
        """
        Process a visual assessment, returning None on failure.

        Use this when images are optional enhancement and shouldn't
        block the narrative flow.

        Args:
            assessment: The visual assessment from Gemini
            campaign_id: The campaign ID for caching

        Returns:
            ImageResult if successful, None if any error occurs
        """
        try:
            return await self.process_assessment(assessment, campaign_id)
        except Exception as e:
            logger.warning(f"Image generation failed (non-fatal): {e}")
            return None

    def get_session_stats(self) -> dict:
        """Get statistics for the current session."""
        return {
            "images_generated": self._session_image_count,
            "limit": self.config.max_images_per_session,
            "remaining": self.config.max_images_per_session - self._session_image_count,
            "provider": self.provider.get_name(),
            "enabled": self.config.enabled,
        }

    def reset_session(self) -> None:
        """Reset the session image counter."""
        self._session_image_count = 0
        logger.info("Visual Engine session reset")

    def get_cache_stats(self, campaign_id: str) -> dict:
        """Get cache statistics for a campaign."""
        return self.cache_manager.get_cache_stats(campaign_id)

    def build_prompt_preview(self, assessment: VisualAssessment) -> dict:
        """
        Build a prompt without generating an image.

        Useful for debugging and previewing what would be sent to the provider.

        Args:
            assessment: The visual assessment

        Returns:
            Dict with prompt, negative_prompt, width, height
        """
        result = self.prompt_builder.build(assessment)
        return {
            "prompt": result.prompt,
            "negative_prompt": result.negative_prompt,
            "width": result.width,
            "height": result.height,
            "estimated_cost": self.provider.estimate_cost(result.width, result.height),
        }


# Convenience function for quick engine creation
async def create_visual_engine(
    style_id: str = "dark_fantasy_painterly",
    world_descriptors: Optional[dict] = None,
    visual_exclusions: str = "",
) -> VisualEngine:
    """
    Quick factory function for creating a VisualEngine.

    Args:
        style_id: The style profile ID
        world_descriptors: Optional dict of world descriptors
        visual_exclusions: Things to exclude from images

    Returns:
        Configured VisualEngine
    """
    wd = WorldDescriptors()
    if world_descriptors:
        wd = WorldDescriptors(
            architecture=world_descriptors.get("architecture", ""),
            landscape=world_descriptors.get("landscape", ""),
            vegetation=world_descriptors.get("vegetation", ""),
            character_design=world_descriptors.get("character_design", ""),
            creatures=world_descriptors.get("creatures", ""),
            color_world=world_descriptors.get("color_world", ""),
            lighting_tendency=world_descriptors.get("lighting_tendency", ""),
            cultural_artifacts=world_descriptors.get("cultural_artifacts", ""),
        )

    return await VisualEngine.create_with_style_id(
        style_id=style_id,
        world_descriptors=wd,
        visual_exclusions=visual_exclusions,
    )
