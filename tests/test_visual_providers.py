# tests/test_visual_providers.py
"""
Tests for Visual Engine image providers.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Import the providers
from src.mantle.visual.providers import (
    GenerationResult,
    ImageProvider,
    select_provider,
)
from src.mantle.visual.providers.flux_provider import FluxProvider
from src.mantle.visual.providers.dalle_provider import DallE3Provider


class TestFluxProvider:
    """Tests for the FluxProvider."""

    def test_get_name(self):
        """Test provider name."""
        provider = FluxProvider()
        assert "Flux" in provider.get_name()
        assert "Schnell" in provider.get_name()

        provider_pro = FluxProvider(use_pro=True)
        assert "Pro" in provider_pro.get_name()

    def test_estimate_cost(self):
        """Test cost estimation."""
        provider = FluxProvider()

        # 1024x576 (16:9 scene)
        cost = provider.estimate_cost(1024, 576)
        assert cost > 0
        assert cost < 0.10  # Should be around $0.02

        # Pro model should cost more
        provider_pro = FluxProvider(use_pro=True)
        cost_pro = provider_pro.estimate_cost(1024, 576)
        assert cost_pro > cost

    @pytest.mark.asyncio
    async def test_is_available_without_key(self):
        """Test availability check without API key."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove FAL_KEY if it exists
            os.environ.pop("FAL_KEY", None)
            provider = FluxProvider()
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_key(self):
        """Test availability check with API key."""
        with patch.dict(os.environ, {"FAL_KEY": "test-key"}):
            provider = FluxProvider()
            assert await provider.is_available() is True


class TestDallE3Provider:
    """Tests for the DallE3Provider."""

    def test_get_name(self):
        """Test provider name."""
        provider = DallE3Provider()
        assert "DALL-E 3" in provider.get_name()
        assert "Standard" in provider.get_name()

        provider_hd = DallE3Provider(use_hd=True)
        assert "HD" in provider_hd.get_name()

    def test_estimate_cost(self):
        """Test cost estimation."""
        provider = DallE3Provider()
        cost = provider.estimate_cost(1024, 1024)
        assert cost == 0.04  # Standard price

        provider_hd = DallE3Provider(use_hd=True)
        cost_hd = provider_hd.estimate_cost(1024, 1024)
        assert cost_hd == 0.08  # HD price

    def test_get_closest_size(self):
        """Test size mapping to DALL-E 3 supported sizes."""
        provider = DallE3Provider()

        # Landscape (16:9)
        assert provider._get_closest_size(1024, 576) == "1792x1024"

        # Portrait (2:3)
        assert provider._get_closest_size(512, 768) == "1024x1792"

        # Square
        assert provider._get_closest_size(512, 512) == "1024x1024"

    @pytest.mark.asyncio
    async def test_is_available_without_key(self):
        """Test availability check without API key."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            provider = DallE3Provider()
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_key(self):
        """Test availability check with API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            provider = DallE3Provider()
            assert await provider.is_available() is True


class TestProviderSelection:
    """Tests for provider selection logic."""

    @pytest.mark.asyncio
    async def test_select_provider_prefers_flux(self):
        """Test that Flux is preferred when both are available."""
        with patch.dict(
            os.environ,
            {"FAL_KEY": "test-fal-key", "OPENAI_API_KEY": "test-openai-key"},
        ):
            provider = await select_provider()
            assert "Flux" in provider.get_name()

    @pytest.mark.asyncio
    async def test_select_provider_falls_back_to_dalle(self):
        """Test fallback to DALL-E when Flux unavailable."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}):
            os.environ.pop("FAL_KEY", None)
            provider = await select_provider()
            assert "DALL-E" in provider.get_name()

    @pytest.mark.asyncio
    async def test_select_provider_raises_when_none_available(self):
        """Test error when no provider is available."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("FAL_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(RuntimeError, match="No image provider available"):
                await select_provider()

    @pytest.mark.asyncio
    async def test_select_provider_respects_preference(self):
        """Test that VISUAL_PROVIDER_PREFERENCE is respected."""
        with patch.dict(
            os.environ,
            {
                "FAL_KEY": "test-fal-key",
                "OPENAI_API_KEY": "test-openai-key",
                "VISUAL_PROVIDER_PREFERENCE": "dalle",
            },
        ):
            provider = await select_provider()
            assert "DALL-E" in provider.get_name()


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_generation_result_defaults(self):
        """Test default values."""
        result = GenerationResult(url="https://example.com/image.png")
        assert result.url == "https://example.com/image.png"
        assert result.seed is None
        assert result.provider == ""
        assert result.model == ""
        assert result.generation_time_ms == 0
        assert result.cost_estimate == 0.0

    def test_generation_result_full(self):
        """Test with all values."""
        result = GenerationResult(
            url="https://example.com/image.png",
            seed=12345,
            provider="fal.ai",
            model="flux-schnell",
            generation_time_ms=3500,
            cost_estimate=0.02,
        )
        assert result.seed == 12345
        assert result.provider == "fal.ai"
        assert result.generation_time_ms == 3500
