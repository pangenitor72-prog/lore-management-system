# tests/test_visual_cache.py
"""
Tests for Visual Engine cache manager.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.mantle.visual.cache_manager import (
    CachedImage,
    CacheManager,
    CacheMetadata,
)
from src.mantle.visual.types import VisualAssessment


class TestCacheManager:
    """Tests for the CacheManager."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """Create a cache manager with temp directory."""
        return CacheManager(cache_dir=temp_cache_dir)

    @pytest.fixture
    def sample_assessment_portrait(self):
        """Create a sample portrait assessment."""
        return VisualAssessment(
            image_type="portrait",
            visual_description="A grizzled dwarven blacksmith with a braided beard",
            mood="peaceful",
            lighting="warm forge light from below",
            key_elements=["dwarf", "beard", "apron", "hammer"],
            character_id="npc_thorin_blacksmith",
            character_description="A stout dwarf with coal-black eyes and burn scars on his arms",
        )

    @pytest.fixture
    def sample_assessment_location(self):
        """Create a sample location assessment."""
        return VisualAssessment(
            image_type="location_card",
            visual_description="A crumbling tower on a cliff overlooking a stormy sea",
            mood="eerie",
            lighting="lightning flashes illuminating dark stone",
            key_elements=["tower", "cliff", "sea", "storm"],
            location_id="loc_ravens_perch",
        )

    @pytest.fixture
    def sample_assessment_scene(self):
        """Create a sample scene assessment."""
        return VisualAssessment(
            image_type="scene",
            visual_description="The tavern common room, crowded with travelers",
            mood="joyful",
            lighting="warm candlelight and hearth glow",
            key_elements=["tavern", "crowd", "fire", "ale"],
        )

    @pytest.fixture
    def sample_assessment_moment(self):
        """Create a sample moment assessment."""
        return VisualAssessment(
            image_type="moment",
            visual_description="The dragon's eye snaps open, ancient and terrible",
            mood="dread",
            lighting="single shaft of light catching the golden iris",
            key_elements=["dragon", "eye", "awakening"],
        )

    def test_cache_dir_creation(self, cache_manager, temp_cache_dir):
        """Test that cache directories are created properly."""
        campaign_id = "test_campaign"
        type_dir = cache_manager._get_type_dir(campaign_id, "portrait")

        cache_manager._ensure_dir(type_dir)

        assert type_dir.exists()
        assert type_dir == temp_cache_dir / campaign_id / "portraits"

    def test_hash_prompt(self, cache_manager):
        """Test prompt hashing for scene caching."""
        prompt1 = "A dark forest with twisted trees"
        prompt2 = "A dark forest with twisted trees"
        prompt3 = "A bright meadow with flowers"

        hash1 = cache_manager._hash_prompt(prompt1)
        hash2 = cache_manager._hash_prompt(prompt2)
        hash3 = cache_manager._hash_prompt(prompt3)

        # Same prompt = same hash
        assert hash1 == hash2
        # Different prompt = different hash
        assert hash1 != hash3
        # Hash is 16 chars
        assert len(hash1) == 16

    @pytest.mark.asyncio
    async def test_get_portrait_not_found(self, cache_manager):
        """Test getting a portrait that doesn't exist."""
        result = await cache_manager.get_portrait(
            "campaign_1", "char_unknown", "neutral"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_location_not_found(self, cache_manager):
        """Test getting a location that doesn't exist."""
        result = await cache_manager.get_location("campaign_1", "loc_unknown")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, cache_manager):
        """Test getting an item that doesn't exist."""
        result = await cache_manager.get_item("campaign_1", "item_unknown")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_cache_portrait(
        self, cache_manager, temp_cache_dir, sample_assessment_portrait
    ):
        """Test cache check for portraits."""
        campaign_id = "test_campaign"

        # Create a fake cached portrait
        portraits_dir = temp_cache_dir / campaign_id / "portraits"
        portraits_dir.mkdir(parents=True)

        char_id = sample_assessment_portrait.character_id
        image_path = portraits_dir / f"{char_id}_neutral.webp"
        meta_path = portraits_dir / f"{char_id}_neutral.json"

        # Write fake image
        image_path.write_bytes(b"fake image data")

        # Write metadata
        metadata = {
            "prompt_used": "test prompt",
            "seed": 12345,
            "created_at": 1234567890,
            "expression": "neutral",
        }
        with open(meta_path, "w") as f:
            json.dump(metadata, f)

        # Check cache
        result = await cache_manager.check_cache(
            campaign_id, sample_assessment_portrait, "test prompt"
        )

        assert result is not None
        assert result.entity_id == char_id
        assert result.seed == 12345
        assert result.expression == "neutral"

    @pytest.mark.asyncio
    async def test_check_cache_location(
        self, cache_manager, temp_cache_dir, sample_assessment_location
    ):
        """Test cache check for locations."""
        campaign_id = "test_campaign"

        # Create a fake cached location
        locations_dir = temp_cache_dir / campaign_id / "locations"
        locations_dir.mkdir(parents=True)

        loc_id = sample_assessment_location.location_id
        image_path = locations_dir / f"{loc_id}.webp"
        image_path.write_bytes(b"fake image data")

        # Check cache
        result = await cache_manager.check_cache(
            campaign_id, sample_assessment_location, "test prompt"
        )

        assert result is not None
        assert result.entity_id == loc_id

    @pytest.mark.asyncio
    async def test_check_cache_moment_never_cached(
        self, cache_manager, sample_assessment_moment
    ):
        """Test that moments are never returned from cache."""
        result = await cache_manager.check_cache(
            "test_campaign", sample_assessment_moment, "test prompt"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_check_cache_scene_uses_location(
        self, cache_manager, temp_cache_dir
    ):
        """Test that scenes can reuse location cards."""
        campaign_id = "test_campaign"

        # Create assessment with location_id
        assessment = VisualAssessment(
            image_type="scene",
            visual_description="Inside the tower",
            mood="eerie",
            lighting="dim",
            key_elements=["tower"],
            location_id="loc_ravens_perch",
        )

        # Create a fake cached location
        locations_dir = temp_cache_dir / campaign_id / "locations"
        locations_dir.mkdir(parents=True)
        image_path = locations_dir / "loc_ravens_perch.webp"
        image_path.write_bytes(b"fake image data")

        # Scene check should find the location
        result = await cache_manager.check_cache(campaign_id, assessment, "test prompt")

        assert result is not None
        assert result.entity_id == "loc_ravens_perch"

    def test_get_cache_stats_empty(self, cache_manager):
        """Test cache stats for non-existent campaign."""
        stats = cache_manager.get_cache_stats("nonexistent_campaign")

        assert stats["exists"] is False
        assert stats["total_images"] == 0

    def test_get_cache_stats_with_images(self, cache_manager, temp_cache_dir):
        """Test cache stats with some cached images."""
        campaign_id = "test_campaign"

        # Create some fake cached images
        portraits_dir = temp_cache_dir / campaign_id / "portraits"
        locations_dir = temp_cache_dir / campaign_id / "locations"
        portraits_dir.mkdir(parents=True)
        locations_dir.mkdir(parents=True)

        # Add 2 portraits and 1 location
        (portraits_dir / "char1_neutral.webp").write_bytes(b"x" * 1000)
        (portraits_dir / "char2_neutral.webp").write_bytes(b"x" * 1500)
        (locations_dir / "loc1.webp").write_bytes(b"x" * 2000)

        stats = cache_manager.get_cache_stats(campaign_id)

        assert stats["exists"] is True
        assert stats["total_images"] == 3
        assert stats["total_size_bytes"] == 4500

    def test_clear_campaign_cache(self, cache_manager, temp_cache_dir):
        """Test clearing a campaign's cache."""
        campaign_id = "test_campaign"

        # Create some cached data
        campaign_dir = temp_cache_dir / campaign_id
        portraits_dir = campaign_dir / "portraits"
        portraits_dir.mkdir(parents=True)
        (portraits_dir / "test.webp").write_bytes(b"data")

        assert campaign_dir.exists()

        # Clear cache
        result = cache_manager.clear_campaign_cache(campaign_id)

        assert result is True
        assert not campaign_dir.exists()

    def test_clear_campaign_cache_not_found(self, cache_manager):
        """Test clearing a non-existent campaign cache."""
        result = cache_manager.clear_campaign_cache("nonexistent")
        assert result is False


class TestCacheMetadata:
    """Tests for CacheMetadata dataclass."""

    def test_cache_metadata_creation(self):
        """Test creating cache metadata."""
        metadata = CacheMetadata(
            prompt_used="test prompt",
            negative_prompt="bad things",
            seed=12345,
            provider="fal.ai",
            model="flux-schnell",
            width=1024,
            height=576,
            created_at=1234567890.0,
            image_type="scene",
            generation_time_ms=3500,
            cost_estimate=0.02,
        )

        assert metadata.prompt_used == "test prompt"
        assert metadata.seed == 12345
        assert metadata.width == 1024


class TestCachedImage:
    """Tests for CachedImage dataclass."""

    def test_cached_image_creation(self, tmp_path):
        """Test creating a cached image reference."""
        image_path = tmp_path / "test.webp"

        cached = CachedImage(
            url=str(image_path),
            local_path=image_path,
            prompt_used="test prompt",
            seed=12345,
            created_at=1234567890.0,
            image_type="portrait",
            entity_id="char_test",
            expression="neutral",
        )

        assert cached.entity_id == "char_test"
        assert cached.expression == "neutral"
        assert cached.image_type == "portrait"
