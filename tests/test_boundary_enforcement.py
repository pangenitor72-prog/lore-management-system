"""Test boundary enforcement system."""

import pytest
from src.mantle.agents.boundary_enforcement import PlayerIntent, PlayerIntentType, AgencyOverride


@pytest.mark.asyncio
async def test_detect_declaration():
    """Test detection of player declarations."""
    
    # Should detect declarations
    assert await PlayerIntent.classify_intent(
        "There's a sword in the chest"
    ) == PlayerIntentType.DECLARATION
    
    assert await PlayerIntent.classify_intent(
        "The king is actually evil"
    ) == PlayerIntentType.DECLARATION
    
    assert await PlayerIntent.classify_intent(
        "This room has a secret door"
    ) == PlayerIntentType.DECLARATION


@pytest.mark.asyncio
async def test_detect_outcome_forcing():
    """Test detection of outcome forcing."""
    
    assert await PlayerIntent.classify_intent(
        "I successfully pick the lock"
    ) == PlayerIntentType.OUTCOME_FORCING
    
    assert await PlayerIntent.classify_intent(
        "I find the treasure"
    ) == PlayerIntentType.OUTCOME_FORCING
    
    assert await PlayerIntent.classify_intent(
        "I manage to convince the guard"
    ) == PlayerIntentType.OUTCOME_FORCING


@pytest.mark.asyncio
async def test_detect_meta_control():
    """Test detection of meta-control violations."""
    
    assert await PlayerIntent.classify_intent(
        "The guard lets me pass"
    ) == PlayerIntentType.META_CONTROL
    
    assert await PlayerIntent.classify_intent(
        "The merchant agrees to help"
    ) == PlayerIntentType.META_CONTROL


@pytest.mark.asyncio
async def test_valid_player_actions_not_flagged():
    """Test that valid inputs are classified correctly."""
    
    # Questions are valid
    assert await PlayerIntent.classify_intent(
        "Is there a library in this city?"
    ) == PlayerIntentType.QUESTION
    
    # Perception is valid
    assert await PlayerIntent.classify_intent(
        "I search the chest for treasure"
    ) == PlayerIntentType.PERCEPTION
    
    # Actions are valid
    assert await PlayerIntent.classify_intent(
        "I attack the goblin"
    ) == PlayerIntentType.ACTION
    
    # Dialogue is valid
    assert await PlayerIntent.classify_intent(
        "I ask the bartender about rumors"
    ) == PlayerIntentType.DIALOGUE


@pytest.mark.asyncio
async def test_attempts_are_valid():
    """Test that attempts (not declarations of success) are valid."""
    
    # These are attempts, not outcome forcing
    assert await PlayerIntent.classify_intent(
        "I try to pick the lock"
    ) == PlayerIntentType.ACTION
    
    assert await PlayerIntent.classify_intent(
        "I attempt to convince the guard"
    ) == PlayerIntentType.ACTION


def test_is_violation():
    """Test violation detection helper."""
    assert PlayerIntent.is_violation(PlayerIntentType.DECLARATION) == True
    assert PlayerIntent.is_violation(PlayerIntentType.OUTCOME_FORCING) == True
    assert PlayerIntent.is_violation(PlayerIntentType.META_CONTROL) == True
    
    assert PlayerIntent.is_violation(PlayerIntentType.ACTION) == False
    assert PlayerIntent.is_violation(PlayerIntentType.QUESTION) == False


def test_agency_override_validation():
    """Test agency override validation."""
    
    # Valid overrides
    assert AgencyOverride.can_override_agency("charm spell") == True
    assert AgencyOverride.can_override_agency("unconscious") == True
    assert AgencyOverride.can_override_agency("falling") == True
    assert AgencyOverride.can_override_agency("instant death") == True
    assert AgencyOverride.can_override_agency("eldritch horror") == True
    
    # Invalid overrides (no justification)
    assert AgencyOverride.can_override_agency("DM says so") == False
    assert AgencyOverride.can_override_agency("railroading") == False


def test_agency_override_formatting():
    """Test agency override message formatting."""
    
    message = AgencyOverride.format_override(
        "charm spell",
        "You feel compelled to trust the vampire"
    )
    
    assert "Agency Override" in message
    assert "Charm Spell" in message
    assert "trust the vampire" in message
    assert "Magical compulsion" in message


def test_get_violation_type_name():
    """Test human-readable violation names."""
    
    assert "declare what exists" in PlayerIntent.get_violation_type_name(
        PlayerIntentType.DECLARATION
    )
    assert "declare outcomes" in PlayerIntent.get_violation_type_name(
        PlayerIntentType.OUTCOME_FORCING
    )
    assert "control NPCs" in PlayerIntent.get_violation_type_name(
        PlayerIntentType.META_CONTROL
    )


def test_get_override_examples():
    """Test that override examples are returned."""
    examples = AgencyOverride.get_override_examples()
    
    assert len(examples) > 0
    assert "charm spell" in examples
    assert "unconscious" in examples
    assert "falling" in examples


@pytest.mark.asyncio
async def test_edge_case_mixed_content():
    """Test classification with edge case inputs."""
    
    # Valid action with "search" keyword
    result = await PlayerIntent.classify_intent("I carefully search the room")
    assert result == PlayerIntentType.PERCEPTION
    
    # Valid dialogue
    result = await PlayerIntent.classify_intent("I ask the innkeeper for a room")
    assert result == PlayerIntentType.DIALOGUE
    
    # Default to action for ambiguous input
    result = await PlayerIntent.classify_intent("I draw my sword")
    assert result == PlayerIntentType.ACTION


@pytest.mark.asyncio
async def test_case_insensitivity():
    """Test that classification is case-insensitive."""
    
    # Uppercase should still work
    result = await PlayerIntent.classify_intent("THERE IS A DOOR HERE")
    assert result == PlayerIntentType.DECLARATION
    
    # Mixed case
    result = await PlayerIntent.classify_intent("I Successfully Pick The Lock")
    assert result == PlayerIntentType.OUTCOME_FORCING
