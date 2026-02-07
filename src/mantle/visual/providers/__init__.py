# src/mantle/visual/providers/__init__.py
"""
Image Generation Provider Abstraction.

Provides a unified interface for different image generation APIs
(Flux via fal.ai, DALL-E 3 via OpenAI).
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of image generation."""
    url: str
    seed: Optional[int] = None
    provider: str = ""
    model: str = ""
    generation_time_ms: int = 0
    cost_estimate: float = 0.0


class ImageProvider(ABC):
    """Abstract base class for image generation providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        seed: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        num_inference_steps: Optional[int] = None,
    ) -> GenerationResult:
        """
        Generate an image from a prompt.

        Args:
            prompt: The positive prompt describing what to generate
            negative_prompt: Things to avoid in the image
            width: Image width in pixels
            height: Image height in pixels
            seed: Optional seed for reproducibility
            guidance_scale: How closely to follow the prompt (provider-specific)
            num_inference_steps: Number of denoising steps (provider-specific)

        Returns:
            GenerationResult with image URL and metadata
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    def estimate_cost(self, width: int, height: int) -> float:
        """
        Estimate the cost in USD for generating an image at this resolution.

        Args:
            width: Image width
            height: Image height

        Returns:
            Estimated cost in USD
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this provider is configured and available."""
        pass


async def select_provider() -> ImageProvider:
    """
    Select the best available image provider.

    Priority:
    1. Flux (fal.ai) - best cost/quality ratio
    2. DALL-E 3 (OpenAI) - fallback

    Returns:
        The first available ImageProvider

    Raises:
        RuntimeError: If no provider is available
    """
    from .flux_provider import FluxProvider
    from .dalle_provider import DallE3Provider

    # Check preference from environment
    preference = os.getenv("VISUAL_PROVIDER_PREFERENCE", "flux").lower()

    providers = []
    if preference == "flux":
        providers = [FluxProvider(), DallE3Provider()]
    else:
        providers = [DallE3Provider(), FluxProvider()]

    for provider in providers:
        if await provider.is_available():
            logger.info(f"Selected image provider: {provider.get_name()}")
            return provider

    raise RuntimeError(
        "No image provider available. Set FAL_KEY or OPENAI_API_KEY environment variable."
    )


__all__ = [
    "GenerationResult",
    "ImageProvider",
    "select_provider",
]
