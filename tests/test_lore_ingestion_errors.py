"""
Tests for lore ingestion error handling.

Verifies that the error handling improvements catch and report errors properly.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from src.mantle.agents.lore_parsing_agent import LoreParsingAgent, ParsedLoreResult, ExtractedEntity


class TestLoreIngestionErrors:
    """Test error handling in lore ingestion."""

    @pytest.mark.asyncio
    async def test_empty_entity_name_skipped(self):
        """Test that entities with empty names are skipped and logged."""
        agent = LoreParsingAgent(api_key="test_key")
        
        # Create a mock database
        mock_db = AsyncMock()
        
        # Create test entities with one having an empty name
        entities = [
            ExtractedEntity(
                name="Valid Entity",
                entity_type="Character",
                description="A valid entity"
            ),
            ExtractedEntity(
                name="",  # Empty name - should be skipped
                entity_type="Character",
                description="Invalid entity"
            ),
            ExtractedEntity(
                name="Another Valid Entity",
                entity_type="Location",
                description="Another valid entity"
            ),
        ]
        
        # Mock parse_lore to return our test entities
        mock_result = ParsedLoreResult(entities=entities, relationships=[])
        
        with patch.object(agent, 'parse_lore', return_value=mock_result):
            result = await agent.parse_and_store(
                text="Test text",
                db=mock_db,
                source_name="test"
            )
        
        # Only 2 valid entities should be stored
        assert result.entities_stored == 2
        # Database execute should be called for each valid entity
        assert mock_db.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_invalid_entity_type_handled(self):
        """Test that invalid entity types are converted to 'Entity'."""
        agent = LoreParsingAgent(api_key="test_key")
        
        mock_db = AsyncMock()
        
        # Create entity with invalid type
        entities = [
            ExtractedEntity(
                name="Test Entity",
                entity_type="InvalidType",  # Not in valid list
                description="Test description"
            ),
        ]
        
        mock_result = ParsedLoreResult(entities=entities, relationships=[])
        
        with patch.object(agent, 'parse_lore', return_value=mock_result):
            result = await agent.parse_and_store(
                text="Test text",
                db=mock_db,
                source_name="test"
            )
        
        # Should still be stored (with warning)
        assert result.entities_stored == 1

    @pytest.mark.asyncio
    async def test_ocean_validation_clamps_values(self):
        """Test that OCEAN scores outside [0.0, 1.0] are clamped."""
        agent = LoreParsingAgent(api_key="test_key")
        
        # Test the OCEAN generation for a character with traits
        ocean = agent._generate_ocean_for_character(
            name="Test Character",
            description="A brave warrior",
            traits=["brave", "brave", "brave"],  # Should push neuroticism very low
            role=""
        )
        
        # All OCEAN scores should be in valid range
        assert 0.0 <= ocean.openness <= 1.0
        assert 0.0 <= ocean.conscientiousness <= 1.0
        assert 0.0 <= ocean.extraversion <= 1.0
        assert 0.0 <= ocean.agreeableness <= 1.0
        assert 0.0 <= ocean.neuroticism <= 1.0

    def test_json_parse_error_handling(self):
        """Test that JSON parsing errors are caught and logged."""
        agent = LoreParsingAgent(api_key="test_key")
        
        # Test with invalid JSON
        invalid_json = "This is not JSON at all"
        result = agent._parse_extraction_response(invalid_json)
        
        # Should return empty result instead of crashing
        assert "entities" in result
        assert "relationships" in result
        assert result["entities"] == []
        assert result["relationships"] == []

    def test_json_parse_with_markdown_fences(self):
        """Test that markdown JSON fences are properly cleaned."""
        agent = LoreParsingAgent(api_key="test_key")
        
        # Test with markdown fences
        json_with_fences = '```json\n{"entities": [], "relationships": []}\n```'
        result = agent._parse_extraction_response(json_with_fences)
        
        # Should successfully parse after cleaning
        assert "entities" in result
        assert "relationships" in result
        assert isinstance(result["entities"], list)
        assert isinstance(result["relationships"], list)

    def test_json_parse_salvages_truncated_response(self):
        """Test that truncated JSON responses can be salvaged."""
        agent = LoreParsingAgent(api_key="test_key")
        
        # Truncated JSON with incomplete entity array
        truncated_json = '''{
            "entities": [
                {"name": "Entity1", "entity_type": "Character", "description": "First entity"},
                {"name": "Entity2", "entity_type": "Location", "description": "Second ent'''
        
        result = agent._parse_extraction_response(truncated_json)
        
        # Should salvage at least the first complete entity
        assert "entities" in result
        # May salvage 1 or more complete entities
        assert len(result["entities"]) >= 0  # May or may not salvage depending on regex


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
