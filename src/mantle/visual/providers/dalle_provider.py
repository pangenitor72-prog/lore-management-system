# src/mantle/visual/providers/dalle_provider.py
"""
DALL-E 3 Image Generation Provider via OpenAI.

Fallback provider for the Visual Engine.
Superior prompt comprehension, no negative prompt support.
~$0.04-0.08/image, 5-15 second generation.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


class DallE3Provider:
    """
    DALL-E 3 image generation via OpenAI API.

    Requires OPENAI_API_KEY environment variable to be set.
    """

    # DALL-E 3 only supports specific sizes
    SUPPORTED_SIZES = {
        "1024x1024": "1024x1024",
        "1792x1024": "1792x1024",  # Landscape
        "1024x1792": "1024x1792",  # Portrait
    }

    # Pricing per image
    COST_STANDARD = 0.04  # Standard quality
    COST_HD = 0.08  # HD quality

    def __init__(self, use_hd: bool = False):
        """
        Initialize the DALL-E 3 provider.

        Args:
            use_hd: Use HD quality (slower, more expensive)
        """
        self.use_hd = use_hd
        self.quality = "hd" if use_hd else "standard"

    def get_name(self) -> str:
        """Return the provider name."""
        return f"DALL-E 3 ({'HD' if self.use_hd else 'Standard'}) via OpenAI"

    def estimate_cost(self, width: int, height: int) -> float:
        """
        Estimate cost for generating an image.

        DALL-E 3 has fixed pricing based on quality, not resolution.
        """
        return self.COST_HD if self.use_hd else self.COST_STANDARD

    async def is_available(self) -> bool:
        """Check if OPENAI_API_KEY is configured."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.debug("OPENAI_API_KEY not set - DALL-E 3 provider unavailable")
            return False
        return True

    def _get_closest_size(self, width: int, height: int) -> str:
        """
        Get the closest supported DALL-E 3 size.

        DALL-E 3 only supports 1024x1024, 1792x1024, and 1024x1792.
        """
        aspect_ratio = width / height

        if aspect_ratio > 1.3:
            # Landscape
            return "1792x1024"
        elif aspect_ratio < 0.77:
            # Portrait
            return "1024x1792"
        else:
            # Square-ish
            return "1024x1024"

    async def generate(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        seed: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        num_inference_steps: Optional[int] = None,
    ):
        """
        Generate an image using DALL-E 3 via OpenAI.

        Note: DALL-E 3 does not support:
        - Negative prompts (we append exclusions to the main prompt)
        - Seed control (seed parameter is ignored)
        - guidance_scale / num_inference_steps

        Args:
            prompt: The positive prompt
            negative_prompt: Things to avoid (appended to prompt)
            width: Requested width (mapped to closest supported size)
            height: Requested height (mapped to closest supported size)
            seed: Ignored - DALL-E 3 doesn't support seeds
            guidance_scale: Ignored
            num_inference_steps: Ignored

        Returns:
            GenerationResult with image URL and metadata
        """
        from . import GenerationResult

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable not set")

        start_time = time.time()

        # Build the prompt (include negative as exclusions)
        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}. Do not include: {negative_prompt}"

        # Get closest supported size
        size = self._get_closest_size(width, height)

        try:
            # Try to use the openai library if available
            try:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(api_key=api_key)

                response = await client.images.generate(
                    model="dall-e-3",
                    prompt=full_prompt,
                    size=size,
                    quality=self.quality,
                    n=1,
                )

                image_url = response.data[0].url
                revised_prompt = response.data[0].revised_prompt

                if revised_prompt:
                    logger.debug(f"DALL-E 3 revised prompt: {revised_prompt[:100]}...")

            except ImportError:
                # Fall back to httpx if openai library not installed
                import httpx

                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/images/generations",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "dall-e-3",
                            "prompt": full_prompt,
                            "size": size,
                            "quality": self.quality,
                            "n": 1,
                        },
                    )
                    response.raise_for_status()
                    result = response.json()

                    if "data" in result and len(result["data"]) > 0:
                        image_url = result["data"][0].get("url", "")
                    else:
                        raise RuntimeError("No images returned from DALL-E 3")

            generation_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"DALL-E 3 generated image in {generation_time_ms}ms: {image_url[:80]}..."
            )

            return GenerationResult(
                url=image_url,
                seed=None,  # DALL-E 3 doesn't provide seeds
                provider="openai",
                model="dall-e-3",
                generation_time_ms=generation_time_ms,
                cost_estimate=self.estimate_cost(width, height),
            )

        except Exception as e:
            logger.error(f"DALL-E 3 generation failed: {e}")
            raise RuntimeError(f"DALL-E 3 image generation failed: {e}") from e
