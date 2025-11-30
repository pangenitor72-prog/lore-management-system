"""Test prompt library structure and functionality."""

import pytest
from src.prompts import DMPrompts, QueryPrompts, AuditorPrompts, BoundaryPrompts

def test_dm_prompt_metadata_exists():
    """Verify DM prompts have metadata."""
    assert DMPrompts.SYSTEM_METADATA.version == "2.4"
    assert DMPrompts.SYSTEM_METADATA.tested_with == "gemini-2.0-flash"

def test_dm_system_prompt_complete():
    """Verify DM system prompt contains key sections."""
    prompt = DMPrompts.SYSTEM_V2_4
    assert "YOUR ROLE" in prompt
    assert "TONE & STYLE" in prompt
    assert "PLAYER BOUNDARIES" in prompt
    assert "AGENCY OVERRIDE" in prompt

def test_dm_prompt_no_todos():
    """Ensure prompts don't have placeholder text."""
    prompt = DMPrompts.SYSTEM_V2_4
    assert "TODO" not in prompt
    assert "PLACEHOLDER" not in prompt

def test_entity_generation_template_has_fields():
    """Verify entity generation template has all required fields."""
    template = DMPrompts.ENTITY_GENERATION_TEMPLATE
    required_fields = [
        "{entity_type}",
        "{entity_name}",
        "{generation_guidelines}",
        "{naming_conventions}",
        "{required_properties}",
        "{optional_properties}",
        "{lore_context}"
    ]
    for field in required_fields:
        assert field in template, f"Missing field: {field}"

def test_entity_generation_builds_without_error():
    """Test that entity generation prompt builder works."""
    prompt = DMPrompts.build_entity_generation_prompt(
        entity_type="Character",
        entity_name="Test NPC",
        generation_guidelines="Test guidelines",
        naming_conventions="Celtic",
        required_properties="name, description",
        optional_properties="age, race",
        lore_context="Test context"
    )
    assert "Test NPC" in prompt
    assert "Character" in prompt
    assert "Celtic" in prompt

def test_extraction_prompt_builds():
    """Test entity extraction prompt builder."""
    prompt = DMPrompts.build_extraction_prompt("Find the sword")
    assert "Find the sword" in prompt

def test_query_prompts_exist():
    """Verify query agent prompts are defined."""
    assert QueryPrompts.SYSTEM is not None
    assert len(QueryPrompts.SYSTEM) > 0

def test_boundary_reminders_exist():
    """Verify boundary enforcement reminders are defined."""
    assert BoundaryPrompts.DECLARATION_REMINDER is not None
    assert BoundaryPrompts.OUTCOME_FORCING_REMINDER is not None
    assert "cannot declare" in BoundaryPrompts.DECLARATION_REMINDER.lower()

def test_boundary_get_reminder():
    """Test boundary reminder retrieval."""
    reminder = BoundaryPrompts.get_reminder("declaration")
    assert "cannot declare" in reminder.lower()

