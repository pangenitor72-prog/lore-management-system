# tests/test_visual_engine.py
"""
Tests for Visual Engine orchestrator.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mantle.visual.cache_manager import CachedImage, CacheManager
from src.mantle.visual.engine import (
    ImageResult,
    VisualEngine,
    VisualEngineConfig,
    create_visual_engine,
)
from src.mantle.visual.prompt_builder import PromptBuilder
from src.mantle.visual.providers import GenerationResult
from src.mantle.visual.types import (
    ImageSpecs,
    StyleProfile,
    VisualAssessment,
    WorldDescriptors,
    WorldVisualIdentity,
)


@pytest.fixture
def mock_style_profile():
    """Create a mock style profile."""
    return StyleProfile(
        style_profile_id="test_style",
        display_name="Test Style",
        prompt_prefix="test style prefix",
        prompt_suffix="test style suffix",
        negative_prompt="bad things",
        mood_modifiers={"tense": "dramatic lighting"},
        composition_templates={
            "scene": {"default": "wide shot"},
            "portrait": {"default": "head and shoulders"},
        },
        image_specs={
            "scene": ImageSpecs(aspect_ratio="16:9", width=1024, height=576),
            "portrait": ImageSpecs(aspect_ratio="2:3", width=512, height=768),
        },
    )


@pytest.fixture
def mock_world_identity():
    """Create a mock world identity."""
    return WorldVisualIdentity(
        style_profile_id="test_style",
        world_descriptors=WorldDescriptors(
            architecture="gothic stone",
            color_world="muted greys",
        ),
        visual_exclusions="modern elements",
    )


@pytest.fixture
def mock_provider():
    """Create a mock image provider."""
    provider = MagicMock()
    provider.get_name.return_value = "MockProvider"
    provider.estimate_cost.return_value = 0.02
    provider.generate = AsyncMock(
        return_value=GenerationResult(
            url="https://example.com/generated.webp",
            seed=12345,
            provider="mock",
            model="mock-model",
            generation_time_ms=3000,
            cost_estimate=0.02,
        )
    )
    return provider


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def visual_engine(mock_style_profile, mock_world_identity, mock_provider, temp_cache_dir):
    """Create a VisualEngine with mocked dependencies."""
    prompt_builder = PromptBuilder(mock_style_profile, mock_world_identity)
    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    config = VisualEngineConfig(
        enabled=True,
        cache_dir=temp_cache_dir,
        max_images_per_session=10,
    )

    return VisualEngine(
        prompt_builder=prompt_builder,
        cache_manager=cache_manager,
        provider=mock_provider,
        config=config,
    )


@pytest.fixture
def sample_scene_assessment():
    """Create a sample scene assessment."""
    return VisualAssessment(
        image_type="scene",
        visual_description="A dark forest clearing with ancient stones",
        mood="eerie",
        lighting="moonlight filtering through branches",
        key_elements=["forest", "stones", "moonlight"],
    )


@pytest.fixture
def sample_portrait_assessment():
    """Create a sample portrait assessment."""
    return VisualAssessment(
        image_type="portrait",
        visual_description="A grizzled warrior",
        mood="tense",
        lighting="firelight from below",
        key_elements=["warrior", "scars", "armor"],
        character_id="char_warrior_001",
        character_description="Battle-scarred veteran with grey beard",
    )


class TestVisualEngine:
    """Tests for the VisualEngine orchestrator."""

    @pytest.mark.asyncio
    async def test_process_assessment_generates_image(
        self, visual_engine, sample_scene_assessment, mock_provider
    ):
        """Test that process_assessment generates a new image on cache miss."""
        result = await visual_engine.process_assessment(
            sample_scene_assessment, "campaign_1"
        )

        assert result is not None
        assert result.from_cache is False
        assert result.image_type == "scene"
        assert result.generation_time_ms == 3000
        assert result.cost_estimate == 0.02
        mock_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_assessment_uses_cache(
        self, visual_engine, sample_portrait_assessment, mock_provider, temp_cache_dir
    ):
        """Test that process_assessment returns cached image when available."""
        # Pre-populate cache
        campaign_id = "campaign_1"
        char_id = sample_portrait_assessment.character_id
        portraits_dir = temp_cache_dir / campaign_id / "portraits"
        portraits_dir.mkdir(parents=True)
        (portraits_dir / f"{char_id}_neutral.webp").write_bytes(b"cached image")

        result = await visual_engine.process_assessment(
            sample_portrait_assessment, campaign_id
        )

        assert result is not None
        assert result.from_cache is True
        assert result.provider == "cache"
        # Provider should NOT be called for cache hit
        mock_provider.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_assessment_respects_session_limit(
        self, visual_engine, sample_scene_assessment
    ):
        """Test that session image limit is enforced."""
        visual_engine._session_image_count = 10  # At limit

        with pytest.raises(RuntimeError, match="Session image limit exceeded"):
            await visual_engine.process_assessment(
                sample_scene_assessment, "campaign_1"
            )

    @pytest.mark.asyncio
    async def test_process_assessment_disabled_engine(
        self, visual_engine, sample_scene_assessment
    ):
        """Test that disabled engine raises error."""
        visual_engine.config.enabled = False

        with pytest.raises(RuntimeError, match="Visual Engine is disabled"):
            await visual_engine.process_assessment(
                sample_scene_assessment, "campaign_1"
            )

    @pytest.mark.asyncio
    async def test_process_assessment_safe_returns_none_on_error(
        self, visual_engine, sample_scene_assessment
    ):
        """Test that process_assessment_safe returns None on error."""
        visual_engine.config.enabled = False

        result = await visual_engine.process_assessment_safe(
            sample_scene_assessment, "campaign_1"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_process_assessment_increments_counter(
        self, visual_engine, sample_scene_assessment
    ):
        """Test that session counter is incremented on generation."""
        assert visual_engine._session_image_count == 0

        await visual_engine.process_assessment(sample_scene_assessment, "campaign_1")

        assert visual_engine._session_image_count == 1

    @pytest.mark.asyncio
    async def test_process_assessment_no_increment_on_cache_hit(
        self, visual_engine, sample_portrait_assessment, temp_cache_dir
    ):
        """Test that session counter is NOT incremented on cache hit."""
        # Pre-populate cache
        campaign_id = "campaign_1"
        char_id = sample_portrait_assessment.character_id
        portraits_dir = temp_cache_dir / campaign_id / "portraits"
        portraits_dir.mkdir(parents=True)
        (portraits_dir / f"{char_id}_neutral.webp").write_bytes(b"cached")

        assert visual_engine._session_image_count == 0

        await visual_engine.process_assessment(sample_portrait_assessment, campaign_id)

        assert visual_engine._session_image_count == 0  # Still 0

    def test_get_session_stats(self, visual_engine):
        """Test session stats retrieval."""
        visual_engine._session_image_count = 5

        stats = visual_engine.get_session_stats()

        assert stats["images_generated"] == 5
        assert stats["limit"] == 10
        assert stats["remaining"] == 5
        assert stats["enabled"] is True

    def test_reset_session(self, visual_engine):
        """Test session reset."""
        visual_engine._session_image_count = 5

        visual_engine.reset_session()

        assert visual_engine._session_image_count == 0

    def test_build_prompt_preview(self, visual_engine, sample_scene_assessment):
        """Test prompt preview without generation."""
        preview = visual_engine.build_prompt_preview(sample_scene_assessment)

        assert "prompt" in preview
        assert "negative_prompt" in preview
        assert "width" in preview
        assert "height" in preview
        assert "estimated_cost" in preview
        assert preview["width"] == 1024
        assert preview["height"] == 576

    def test_get_cache_stats(self, visual_engine, temp_cache_dir):
        """Test cache stats retrieval."""
        # Create some cache data
        campaign_dir = temp_cache_dir / "campaign_1" / "portraits"
        campaign_dir.mkdir(parents=True)
        (campaign_dir / "test.webp").write_bytes(b"data")

        stats = visual_engine.get_cache_stats("campaign_1")

        assert stats["exists"] is True
        assert stats["total_images"] == 1


class TestVisualEngineConfig:
    """Tests for VisualEngineConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = VisualEngineConfig()

        assert config.enabled is True
        assert config.max_images_per_session == 30
        assert config.provider_preference == "flux"

    def test_custom_config(self):
        """Test custom configuration."""
        config = VisualEngineConfig(
            enabled=False,
            cache_dir=Path("/custom/cache"),
            max_images_per_session=50,
            provider_preference="dalle",
        )

        assert config.enabled is False
        assert config.cache_dir == Path("/custom/cache")
        assert config.max_images_per_session == 50
        assert config.provider_preference == "dalle"


class TestImageResult:
    """Tests for ImageResult dataclass."""

    def test_image_result_creation(self):
        """Test creating an image result."""
        result = ImageResult(
            url="https://example.com/image.webp",
            from_cache=False,
            image_type="scene",
            generation_time_ms=3000,
            cost_estimate=0.02,
            provider="fal.ai",
            seed=12345,
        )

        assert result.url == "https://example.com/image.webp"
        assert result.from_cache is False
        assert result.seed == 12345

    def test_image_result_defaults(self):
        """Test default values."""
        result = ImageResult(
            url="https://example.com/image.webp",
            from_cache=True,
            image_type="portrait",
        )

        assert result.generation_time_ms == 0
        assert result.cost_estimate == 0.0
        assert result.provider == ""
        assert result.seed is None


class TestVisualEngineFactory:
    """Tests for factory methods."""

    @pytest.mark.asyncio
    async def test_create_with_style_id(self):
        """Test create_with_style_id factory method."""
        with patch(
            "src.mantle.visual.engine.load_style_profile"
        ) as mock_load, patch(
            "src.mantle.visual.engine.select_provider"
        ) as mock_select:
            # Setup mocks
            mock_load.return_value = StyleProfile(
                style_profile_id="dark_fantasy_painterly",
                display_name="Dark Fantasy",
                prompt_prefix="dark fantasy",
                prompt_suffix="quality",
                negative_prompt="bad",
                mood_modifiers={},
                composition_templates={},
                image_specs={},
            )
            mock_provider = MagicMock()
            mock_provider.get_name.return_value = "MockProvider"
            mock_select.return_value = mock_provider

            engine = await VisualEngine.create_with_style_id(
                style_id="dark_fantasy_painterly",
                world_descriptors=WorldDescriptors(architecture="gothic"),
                visual_exclusions="modern",
            )

            assert engine is not None
            mock_load.assert_called_once_with("dark_fantasy_painterly")

    @pytest.mark.asyncio
    async def test_create_raises_on_missing_style(self):
        """Test that create raises when style not found."""
        with patch(
            "src.mantle.visual.engine.load_style_profile"
        ) as mock_load:
            mock_load.return_value = None

            world_identity = WorldVisualIdentity(
                style_profile_id="nonexistent_style",
                world_descriptors=WorldDescriptors(),
            )

            with pytest.raises(RuntimeError, match="Style profile not found"):
                await VisualEngine.create(world_identity)


class TestCreateVisualEngineFunction:
    """Tests for the convenience factory function."""

    @pytest.mark.asyncio
    async def test_create_visual_engine_basic(self):
        """Test basic factory function usage."""
        with patch(
            "src.mantle.visual.engine.VisualEngine.create_with_style_id"
        ) as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            engine = await create_visual_engine(
                style_id="pixel_art_16bit",
                world_descriptors={"architecture": "retro"},
            )

            assert engine == mock_engine
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_visual_engine_defaults(self):
        """Test factory function with defaults."""
        with patch(
            "src.mantle.visual.engine.VisualEngine.create_with_style_id"
        ) as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            engine = await create_visual_engine()

            # Should use dark_fantasy_painterly as default
            call_args = mock_create.call_args
            assert call_args.kwargs["style_id"] == "dark_fantasy_painterly"
