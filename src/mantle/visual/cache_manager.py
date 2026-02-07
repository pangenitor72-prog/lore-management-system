# src/mantle/visual/cache_manager.py
"""
Cache Manager for the Visual Engine.

Handles filesystem-based caching of generated images by campaign.
Images are cached by type (portrait, location, item, scene, moment)
with metadata stored alongside for debugging and regeneration.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import httpx

from .types import ImageType, VisualAssessment

logger = logging.getLogger(__name__)

# Default cache directory
DEFAULT_CACHE_DIR = Path("./visual_cache")


@dataclass
class CachedImage:
    """Represents a cached image with its metadata."""

    url: str  # Local file path or original URL
    local_path: Path  # Path to the cached file
    prompt_used: str
    seed: Optional[int]
    created_at: float
    image_type: ImageType
    entity_id: Optional[str] = None  # character_id, location_id, item_id
    expression: Optional[str] = None  # For portraits


@dataclass
class CacheMetadata:
    """Metadata stored alongside cached images."""

    prompt_used: str
    negative_prompt: str
    seed: Optional[int]
    provider: str
    model: str
    width: int
    height: int
    created_at: float
    image_type: str
    entity_id: Optional[str] = None
    expression: Optional[str] = None
    generation_time_ms: int = 0
    cost_estimate: float = 0.0


class CacheManager:
    """
    Manages the visual cache for a campaign.

    Cache structure:
    /visual_cache/{campaign_id}/
        /portraits/{character_id}_{expression}.webp
        /locations/{location_id}.webp
        /items/{item_id}.webp
        /scenes/{content_hash}.webp
        /moments/{timestamp}.webp
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Base directory for cache. Defaults to ./visual_cache
        """
        self.cache_dir = cache_dir or Path(
            os.getenv("VISUAL_CACHE_DIR", DEFAULT_CACHE_DIR)
        )

    def _get_campaign_dir(self, campaign_id: str) -> Path:
        """Get the cache directory for a campaign."""
        return self.cache_dir / campaign_id

    def _get_type_dir(self, campaign_id: str, image_type: ImageType) -> Path:
        """Get the directory for a specific image type within a campaign."""
        type_dirs = {
            "portrait": "portraits",
            "location_card": "locations",
            "item": "items",
            "scene": "scenes",
            "moment": "moments",
        }
        return self._get_campaign_dir(campaign_id) / type_dirs.get(image_type, "other")

    def _ensure_dir(self, path: Path) -> None:
        """Ensure a directory exists."""
        path.mkdir(parents=True, exist_ok=True)

    def _hash_prompt(self, prompt: str) -> str:
        """Create a short hash of a prompt for scene caching."""
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    async def get_portrait(
        self,
        campaign_id: str,
        character_id: str,
        expression: str = "neutral",
    ) -> Optional[CachedImage]:
        """
        Get a cached portrait for a character.

        Args:
            campaign_id: The campaign ID
            character_id: The character's unique ID
            expression: The expression (neutral, angry, fearful, smiling)

        Returns:
            CachedImage if found, None otherwise
        """
        type_dir = self._get_type_dir(campaign_id, "portrait")
        filename = f"{character_id}_{expression}"
        return await self._get_cached(type_dir, filename, "portrait", character_id)

    async def get_location(
        self,
        campaign_id: str,
        location_id: str,
    ) -> Optional[CachedImage]:
        """
        Get a cached location card.

        Args:
            campaign_id: The campaign ID
            location_id: The location's unique ID

        Returns:
            CachedImage if found, None otherwise
        """
        type_dir = self._get_type_dir(campaign_id, "location_card")
        return await self._get_cached(type_dir, location_id, "location_card", location_id)

    async def get_item(
        self,
        campaign_id: str,
        item_id: str,
    ) -> Optional[CachedImage]:
        """
        Get a cached item illustration.

        Args:
            campaign_id: The campaign ID
            item_id: The item's unique ID

        Returns:
            CachedImage if found, None otherwise
        """
        type_dir = self._get_type_dir(campaign_id, "item")
        return await self._get_cached(type_dir, item_id, "item", item_id)

    async def get_scene(
        self,
        campaign_id: str,
        prompt: str,
    ) -> Optional[CachedImage]:
        """
        Get a cached scene image by prompt hash.

        Scenes use a looser cache - same prompt = same image.

        Args:
            campaign_id: The campaign ID
            prompt: The full prompt used for generation

        Returns:
            CachedImage if found, None otherwise
        """
        type_dir = self._get_type_dir(campaign_id, "scene")
        content_hash = self._hash_prompt(prompt)
        return await self._get_cached(type_dir, content_hash, "scene")

    async def _get_cached(
        self,
        type_dir: Path,
        filename: str,
        image_type: ImageType,
        entity_id: Optional[str] = None,
    ) -> Optional[CachedImage]:
        """
        Get a cached image by filename.

        Args:
            type_dir: Directory containing the image type
            filename: Base filename (without extension)
            image_type: The type of image
            entity_id: Optional entity ID

        Returns:
            CachedImage if found, None otherwise
        """
        # Check for common image extensions
        for ext in [".webp", ".png", ".jpg"]:
            image_path = type_dir / f"{filename}{ext}"
            meta_path = type_dir / f"{filename}.json"

            if image_path.exists():
                # Load metadata if available
                metadata = None
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception as e:
                        logger.warning(f"Failed to load cache metadata: {e}")

                return CachedImage(
                    url=str(image_path),
                    local_path=image_path,
                    prompt_used=metadata.get("prompt_used", "") if metadata else "",
                    seed=metadata.get("seed") if metadata else None,
                    created_at=metadata.get("created_at", 0) if metadata else 0,
                    image_type=image_type,
                    entity_id=entity_id,
                    expression=metadata.get("expression") if metadata else None,
                )

        return None

    async def store(
        self,
        campaign_id: str,
        assessment: VisualAssessment,
        image_url: str,
        prompt_used: str,
        negative_prompt: str,
        seed: Optional[int],
        provider: str,
        model: str,
        width: int,
        height: int,
        generation_time_ms: int = 0,
        cost_estimate: float = 0.0,
    ) -> CachedImage:
        """
        Store an image in the cache.

        Downloads the image from URL and stores locally with metadata.

        Args:
            campaign_id: The campaign ID
            assessment: The visual assessment that triggered generation
            image_url: URL of the generated image
            prompt_used: The prompt used for generation
            negative_prompt: The negative prompt used
            seed: The seed used (if available)
            provider: Provider name (e.g., "fal.ai")
            model: Model name
            width: Image width
            height: Image height
            generation_time_ms: Time to generate
            cost_estimate: Estimated cost

        Returns:
            CachedImage with local path
        """
        type_dir = self._get_type_dir(campaign_id, assessment.image_type)
        self._ensure_dir(type_dir)

        # Determine filename based on image type
        entity_id = None
        expression = None

        if assessment.image_type == "portrait" and assessment.character_id:
            entity_id = assessment.character_id
            expression = "neutral"  # Default expression
            filename = f"{entity_id}_{expression}"
        elif assessment.image_type == "location_card" and assessment.location_id:
            entity_id = assessment.location_id
            filename = entity_id
        elif assessment.image_type == "item" and assessment.item_id:
            entity_id = assessment.item_id
            filename = entity_id
        elif assessment.image_type == "moment":
            # Moments use timestamp - never cached for reuse
            filename = str(int(time.time() * 1000))
        else:
            # Scenes use prompt hash
            filename = self._hash_prompt(prompt_used)

        # Download the image
        image_path = type_dir / f"{filename}.webp"
        meta_path = type_dir / f"{filename}.json"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url)
                response.raise_for_status()

                # Save image
                with open(image_path, "wb") as f:
                    f.write(response.content)

                logger.info(f"Cached image: {image_path}")

        except Exception as e:
            logger.error(f"Failed to download and cache image: {e}")
            # Return with original URL if download fails
            return CachedImage(
                url=image_url,
                local_path=image_path,
                prompt_used=prompt_used,
                seed=seed,
                created_at=time.time(),
                image_type=assessment.image_type,
                entity_id=entity_id,
                expression=expression,
            )

        # Save metadata
        metadata = CacheMetadata(
            prompt_used=prompt_used,
            negative_prompt=negative_prompt,
            seed=seed,
            provider=provider,
            model=model,
            width=width,
            height=height,
            created_at=time.time(),
            image_type=assessment.image_type,
            entity_id=entity_id,
            expression=expression,
            generation_time_ms=generation_time_ms,
            cost_estimate=cost_estimate,
        )

        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(asdict(metadata), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")

        return CachedImage(
            url=str(image_path),
            local_path=image_path,
            prompt_used=prompt_used,
            seed=seed,
            created_at=time.time(),
            image_type=assessment.image_type,
            entity_id=entity_id,
            expression=expression,
        )

    async def check_cache(
        self,
        campaign_id: str,
        assessment: VisualAssessment,
        prompt: str,
    ) -> Optional[CachedImage]:
        """
        Check if an image is already cached based on assessment.

        Args:
            campaign_id: The campaign ID
            assessment: The visual assessment
            prompt: The assembled prompt (for scene hashing)

        Returns:
            CachedImage if found, None otherwise
        """
        if assessment.image_type == "portrait" and assessment.character_id:
            return await self.get_portrait(
                campaign_id, assessment.character_id, "neutral"
            )

        elif assessment.image_type == "location_card" and assessment.location_id:
            return await self.get_location(campaign_id, assessment.location_id)

        elif assessment.image_type == "item" and assessment.item_id:
            return await self.get_item(campaign_id, assessment.item_id)

        elif assessment.image_type == "scene":
            # Try location cache first (reuse location card as scene)
            if assessment.location_id:
                cached = await self.get_location(campaign_id, assessment.location_id)
                if cached:
                    return cached
            # Then try scene cache by prompt
            return await self.get_scene(campaign_id, prompt)

        elif assessment.image_type == "moment":
            # Moments are never cached - always generate fresh
            return None

        return None

    def get_cache_stats(self, campaign_id: str) -> dict:
        """
        Get statistics about the cache for a campaign.

        Args:
            campaign_id: The campaign ID

        Returns:
            Dict with cache statistics
        """
        campaign_dir = self._get_campaign_dir(campaign_id)

        if not campaign_dir.exists():
            return {
                "campaign_id": campaign_id,
                "exists": False,
                "total_images": 0,
                "total_size_mb": 0,
            }

        stats = {
            "campaign_id": campaign_id,
            "exists": True,
            "portraits": 0,
            "locations": 0,
            "items": 0,
            "scenes": 0,
            "moments": 0,
            "total_images": 0,
            "total_size_bytes": 0,
        }

        for type_name in ["portraits", "locations", "items", "scenes", "moments"]:
            type_dir = campaign_dir / type_name
            if type_dir.exists():
                images = list(type_dir.glob("*.webp")) + list(type_dir.glob("*.png"))
                stats[type_name.rstrip("s") if type_name != "moments" else "moments"] = len(images)
                stats["total_images"] += len(images)
                for img in images:
                    stats["total_size_bytes"] += img.stat().st_size

        stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)
        return stats

    def clear_campaign_cache(self, campaign_id: str) -> bool:
        """
        Clear all cached images for a campaign.

        Args:
            campaign_id: The campaign ID

        Returns:
            True if cleared, False if campaign not found
        """
        import shutil

        campaign_dir = self._get_campaign_dir(campaign_id)

        if not campaign_dir.exists():
            return False

        try:
            shutil.rmtree(campaign_dir)
            logger.info(f"Cleared cache for campaign: {campaign_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
