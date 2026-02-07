# src/mantle/visual/providers/flux_provider.py
"""
Flux Image Generation Provider via fal.ai.

Primary provider for the Visual Engine - best cost/quality ratio.
~$0.02/image, 3-8 second generation.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


class FluxProvider:
    """
    Flux image generation via fal.ai API.

    Requires FAL_KEY environment variable to be set.
    """

    # Flux model on fal.ai
    MODEL_ID = "fal-ai/flux/schnell"  # Fast model, good quality
    MODEL_ID_PRO = "fal-ai/flux-pro"  # Higher quality, slower

    # Base cost estimate per megapixel
    COST_PER_MEGAPIXEL = 0.03

    def __init__(self, use_pro: bool = False):
        """
        Initialize the Flux provider.

        Args:
            use_pro: Use the pro model (slower but higher quality)
        """
        self.use_pro = use_pro
        self.model_id = self.MODEL_ID_PRO if use_pro else self.MODEL_ID
        self._fal_client = None

    def get_name(self) -> str:
        """Return the provider name."""
        return f"Flux ({'Pro' if self.use_pro else 'Schnell'}) via fal.ai"

    def estimate_cost(self, width: int, height: int) -> float:
        """
        Estimate cost for generating an image.

        Flux pricing is roughly based on resolution.
        Schnell: ~$0.02 for 1024x1024
        Pro: ~$0.05 for 1024x1024
        """
        megapixels = (width * height) / 1_000_000
        base_cost = megapixels * self.COST_PER_MEGAPIXEL
        if self.use_pro:
            base_cost *= 2.5
        return round(base_cost, 4)

    async def is_available(self) -> bool:
        """Check if FAL_KEY is configured."""
        api_key = os.getenv("FAL_KEY")
        if not api_key:
            logger.debug("FAL_KEY not set - Flux provider unavailable")
            return False
        return True

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
        Generate an image using Flux via fal.ai.

        Args:
            prompt: The positive prompt
            negative_prompt: Things to avoid (appended to prompt for Flux)
            width: Image width
            height: Image height
            seed: Optional seed for reproducibility
            guidance_scale: CFG scale (default 3.5 for Flux)
            num_inference_steps: Number of steps (default 4 for Schnell, 25 for Pro)

        Returns:
            GenerationResult with image URL and metadata
        """
        from . import GenerationResult

        api_key = os.getenv("FAL_KEY")
        if not api_key:
            raise RuntimeError("FAL_KEY environment variable not set")

        start_time = time.time()

        # Build the request
        # Flux handles negative prompts differently - we append them to the prompt
        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}. Avoid: {negative_prompt}"

        # Default inference steps based on model
        if num_inference_steps is None:
            num_inference_steps = 25 if self.use_pro else 4

        if guidance_scale is None:
            guidance_scale = 3.5

        request_data = {
            "prompt": full_prompt,
            "image_size": {
                "width": width,
                "height": height,
            },
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
            "num_images": 1,
            "enable_safety_checker": True,
        }

        if seed is not None:
            request_data["seed"] = seed

        try:
            # Use fal_client if available, otherwise use httpx directly
            try:
                import fal_client

                # Set the API key
                os.environ["FAL_KEY"] = api_key

                # Run the model
                result = await fal_client.subscribe_async(
                    self.model_id,
                    arguments=request_data,
                )

                # Extract the image URL
                if result and "images" in result and len(result["images"]) > 0:
                    image_data = result["images"][0]
                    image_url = image_data.get("url", "")
                    result_seed = result.get("seed")
                else:
                    raise RuntimeError("No images returned from Flux")

            except ImportError:
                # Fall back to httpx if fal_client not installed
                import httpx

                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"https://fal.run/{self.model_id}",
                        headers={
                            "Authorization": f"Key {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=request_data,
                    )
                    response.raise_for_status()
                    result = response.json()

                    if "images" in result and len(result["images"]) > 0:
                        image_url = result["images"][0].get("url", "")
                        result_seed = result.get("seed")
                    else:
                        raise RuntimeError("No images returned from Flux")

            generation_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Flux generated image in {generation_time_ms}ms: {image_url[:80]}..."
            )

            return GenerationResult(
                url=image_url,
                seed=result_seed,
                provider="fal.ai",
                model=self.model_id,
                generation_time_ms=generation_time_ms,
                cost_estimate=self.estimate_cost(width, height),
            )

        except Exception as e:
            logger.error(f"Flux generation failed: {e}")
            raise RuntimeError(f"Flux image generation failed: {e}") from e
