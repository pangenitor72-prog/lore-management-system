
"""
Image Generation Service for AIRpg/Mantle.

Handles generation of visual assets for entities using AI models (DALL-E 3, Imagen, or Mock).
"""

import os
import logging
import asyncio
import json
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)

class ImageProvider(str, Enum):
    MOCK = "mock"
    OPENAI = "openai"
    VERTEX = "vertex"

class ImageService:
    def __init__(self, provider: str = "mock", api_key: Optional[str] = None):
        self.provider = ImageProvider(provider.lower())
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        # Style presets
        self.styles = {
            "fantasy": "fantasy oil painting, detailed, atmospheric, cinematic lighting",
            "sci-fi": "sci-fi concept art, futuristic, neon details, unreal engine 5 render",
            "horror": "dark fantasy, grimdark, ominous atmosphere, detailed texture",
            "cyberpunk": "cyberpunk style, neon lights, rain, high tech low life, digital art",
            "noir": "film noir style, high contrast, black and white, dramatic shadows",
            "steampunk": "steampunk aesthetic, brass and steam, intricate gears, victorian style"
        }

    async def generate_image(
        self, 
        prompt: str, 
        entity_name: str, 
        entity_type: str,
        style_key: str = "fantasy"
    ) -> Optional[str]:
        """
        Generate an image for an entity.
        
        Args:
            prompt: Base description of the entity
            entity_name: Name of the entity
            entity_type: Type (Location, Character, etc.)
            style_key: Key for style preset (fantasy, sci-fi, etc.)
            
        Returns:
            URL of the generated image (or local path)
        """
        style_prompt = self.styles.get(style_key.lower(), self.styles["fantasy"])
        full_prompt = f"{entity_type} {entity_name}: {prompt}. {style_prompt}"
        
        # Truncate to avoid limit issues (e.g. 1000 chars for DALL-E 2, 4000 for DALL-E 3)
        full_prompt = full_prompt[:1000]

        logger.info(f"Generating image for {entity_name} ({self.provider}): {full_prompt[:50]}...")

        if self.provider == ImageProvider.MOCK:
            return await self._generate_mock(entity_name, entity_type)
        elif self.provider == ImageProvider.OPENAI:
            return await self._generate_openai(full_prompt)
        elif self.provider == ImageProvider.VERTEX:
            return await self._generate_vertex(full_prompt)
        
        return None

    async def _generate_mock(self, name: str, type: str) -> str:
        """Generate a deterministic placeholder URL."""
        # Use a reliable placeholder service
        # seed = sum(ord(c) for c in name)
        # return f"https://picsum.photos/seed/{seed}/512/512"
        
        # Or return a local placeholder path if frontend supports it
        # For now, return a placeholder API url that works in browser
        import hashlib
        hash_object = hashlib.md5(name.encode())
        hash_hex = hash_object.hexdigest()
        
        # RoboHash is great for characters/monsters
        if type.lower() in ["character", "creature", "npc"]:
            return f"https://robohash.org/{hash_hex}?set=set2&size=512x512"
        else:
            # Lorem Picsum for locations
            # We use the hash to get a consistent random image ID (0-1000)
            img_id = int(hash_hex, 16) % 1000
            return f"https://picsum.photos/id/{img_id}/512/512"

    async def _generate_openai(self, prompt: str) -> Optional[str]:
        """Generate using OpenAI DALL-E 3."""
        if not self.api_key:
            logger.warning("OpenAI API key not set for image generation")
            return None
            
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            
            response = await client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            return response.data[0].url
        except Exception as e:
            logger.error(f"OpenAI image generation failed: {e}")
            return None

    async def _generate_vertex(self, prompt: str) -> Optional[str]:
        """Generate using Google Vertex AI (Imagen)."""
        # Placeholder for Vertex AI implementation
        logger.warning("Vertex AI image generation not yet implemented")
        return None

# Singleton instance for easy import
# Default to MOCK to avoid costs during dev/testing
image_service = ImageService(provider=os.getenv("IMAGE_PROVIDER", "mock"))
