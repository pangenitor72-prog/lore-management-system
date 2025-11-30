"""Test OCEAN personality system."""

import pytest
from src.agents.personality import (
    OCEANProfile, PersonalityArchetype, PersonalityTemplates,
    PersonalityGenerator
)


def test_ocean_profile_creation():
    """Test creating valid OCEAN profile."""
    profile = OCEANProfile(
        openness=0.7,
        conscientiousness=0.8,
        extraversion=0.5,
        agreeableness=0.6,
        neuroticism=0.3
    )
    
    assert profile.openness == 0.7
    assert profile.conscientiousness == 0.8


def test_ocean_profile_validation():
    """Test OCEAN profile validates trait ranges."""
    with pytest.raises(ValueError):
        OCEANProfile(
            openness=1.5,  # Invalid: > 1.0
            conscientiousness=0.5,
            extraversion=0.5,
            agreeableness=0.5,
            neuroticism=0.5
        )
    
    with pytest.raises(ValueError):
        OCEANProfile(
            openness=0.5,
            conscientiousness=-0.1,  # Invalid: < 0.0
            extraversion=0.5,
            agreeableness=0.5,
            neuroticism=0.5
        )


def test_ocean_to_dict():
    """Test converting OCEAN profile to dictionary."""
    profile = OCEANProfile(0.7, 0.6, 0.5, 0.8, 0.3)
    data = profile.to_dict()
    
    assert data['openness'] == 0.7
    assert data['agreeableness'] == 0.8


def test_ocean_from_dict():
    """Test creating OCEAN profile from dictionary."""
    data = {
        'openness': 0.7,
        'conscientiousness': 0.6,
        'extraversion': 0.5,
        'agreeableness': 0.8,
        'neuroticism': 0.3
    }
    
    profile = OCEANProfile.from_dict(data)
    assert profile.openness == 0.7
    assert profile.agreeableness == 0.8


def test_ocean_from_dict_defaults():
    """Test OCEAN profile uses defaults for missing values."""
    data = {'openness': 0.9}
    profile = OCEANProfile.from_dict(data)
    
    assert profile.openness == 0.9
    assert profile.conscientiousness == 0.5  # Default
    assert profile.extraversion == 0.5  # Default


def test_trait_descriptors():
    """Test trait descriptor generation."""
    profile = OCEANProfile(0.9, 0.2, 0.5, 0.1, 0.8)
    
    # High openness
    assert "creative" in profile.get_trait_descriptor('openness', 0.9).lower()
    
    # Low conscientiousness
    assert "spontaneous" in profile.get_trait_descriptor('conscientiousness', 0.2).lower()
    
    # High neuroticism
    assert "anxious" in profile.get_trait_descriptor('neuroticism', 0.8).lower()


def test_trait_descriptor_levels():
    """Test trait descriptors for different levels."""
    profile = OCEANProfile(0.5, 0.5, 0.5, 0.5, 0.5)
    
    # Low (< 0.3)
    low_desc = profile.get_trait_descriptor('openness', 0.2)
    assert "conventional" in low_desc.lower()
    
    # Moderate (0.3-0.7)
    moderate_desc = profile.get_trait_descriptor('openness', 0.5)
    assert "balanced" in moderate_desc.lower()
    
    # High (> 0.7)
    high_desc = profile.get_trait_descriptor('openness', 0.9)
    assert "creative" in high_desc.lower()


def test_behavioral_summary():
    """Test behavioral summary generation."""
    # Extreme traits only
    profile = OCEANProfile(0.9, 0.2, 0.5, 0.5, 0.8)
    summary = profile.get_behavioral_summary()
    
    assert "creative" in summary.lower() or "curious" in summary.lower()
    assert "spontaneous" in summary.lower() or "flexible" in summary.lower()
    assert "anxious" in summary.lower() or "sensitive" in summary.lower()


def test_behavioral_summary_balanced():
    """Test balanced profile produces appropriate summary."""
    profile = OCEANProfile(0.5, 0.5, 0.5, 0.5, 0.5)
    summary = profile.get_behavioral_summary()
    
    assert "balanced" in summary.lower()


def test_dialogue_style():
    """Test dialogue style generation."""
    # High extraversion, low agreeableness
    profile = OCEANProfile(0.5, 0.5, 0.9, 0.2, 0.5)
    style = profile.get_dialogue_style()
    
    assert "talkative" in style.lower() or "eager" in style.lower()
    assert "blunt" in style.lower() or "skeptical" in style.lower()


def test_dialogue_style_neutral():
    """Test neutral dialogue style for balanced profile."""
    profile = OCEANProfile(0.5, 0.5, 0.5, 0.5, 0.5)
    style = profile.get_dialogue_style()
    
    assert "neutral" in style.lower()


def test_personality_templates_exist():
    """Test all archetypes have templates."""
    for archetype in PersonalityArchetype:
        template = PersonalityTemplates.get_template(archetype)
        assert isinstance(template, OCEANProfile)


def test_merchant_archetype():
    """Test merchant archetype has expected traits."""
    merchant = PersonalityTemplates.get_template(PersonalityArchetype.MERCHANT)
    
    # Merchants should be conscientious (organized)
    assert merchant.conscientiousness > 0.6
    
    # Moderately extraverted (friendly)
    assert 0.4 <= merchant.extraversion <= 0.7


def test_guard_archetype():
    """Test guard archetype has expected traits."""
    guard = PersonalityTemplates.get_template(PersonalityArchetype.GUARD)
    
    # Guards should be conscientious (disciplined)
    assert guard.conscientiousness > 0.7
    
    # Low openness (follows rules)
    assert guard.openness < 0.4


def test_scholar_archetype():
    """Test scholar archetype has expected traits."""
    scholar = PersonalityTemplates.get_template(PersonalityArchetype.SCHOLAR)
    
    # Scholars should be high openness (curious)
    assert scholar.openness > 0.7
    
    # High conscientiousness (meticulous)
    assert scholar.conscientiousness > 0.6


def test_criminal_archetype():
    """Test criminal archetype has expected traits."""
    criminal = PersonalityTemplates.get_template(PersonalityArchetype.CRIMINAL)
    
    # Criminals should be low conscientiousness (flexible morals)
    assert criminal.conscientiousness < 0.4
    
    # Low agreeableness (self-interested)
    assert criminal.agreeableness < 0.4


def test_archetype_inference_from_role():
    """Test inferring archetype from role description."""
    assert PersonalityTemplates.get_archetype_from_role("merchant") == PersonalityArchetype.MERCHANT
    assert PersonalityTemplates.get_archetype_from_role("City Guard") == PersonalityArchetype.GUARD
    assert PersonalityTemplates.get_archetype_from_role("scholarly researcher") == PersonalityArchetype.SCHOLAR
    assert PersonalityTemplates.get_archetype_from_role("noble lord") == PersonalityArchetype.NOBLE
    assert PersonalityTemplates.get_archetype_from_role("thief") == PersonalityArchetype.CRIMINAL
    
    # Unknown role returns None
    assert PersonalityTemplates.get_archetype_from_role("dragon") is None


def test_archetype_inference_case_insensitive():
    """Test archetype inference is case-insensitive."""
    assert PersonalityTemplates.get_archetype_from_role("MERCHANT") == PersonalityArchetype.MERCHANT
    assert PersonalityTemplates.get_archetype_from_role("Guard") == PersonalityArchetype.GUARD


def test_personality_generation_from_archetype():
    """Test generating personality with variation."""
    base = PersonalityTemplates.get_template(PersonalityArchetype.MERCHANT)
    varied = PersonalityGenerator.generate_from_archetype(PersonalityArchetype.MERCHANT, variation=0.1)
    
    # Should be similar but not necessarily identical
    assert abs(varied.openness - base.openness) <= 0.15
    assert abs(varied.conscientiousness - base.conscientiousness) <= 0.15


def test_personality_generation_from_role():
    """Test generating personality from role string."""
    personality = PersonalityGenerator.generate_from_role("merchant")
    
    # Should be merchant-like (high conscientiousness)
    assert personality.conscientiousness > 0.5


def test_personality_generation_fallback():
    """Test fallback to balanced profile for unknown role."""
    personality = PersonalityGenerator.generate_from_role("unknown_fantasy_role")
    
    # Should be balanced (all traits around 0.5)
    assert 0.4 <= personality.openness <= 0.6
    assert 0.4 <= personality.conscientiousness <= 0.6


def test_personality_generation_random():
    """Test random personality generation has extreme traits."""
    # Generate several profiles to test randomness
    profiles = [PersonalityGenerator.generate_random() for _ in range(10)]
    
    # At least some profiles should have extreme traits
    has_extreme = False
    for profile in profiles:
        traits = [profile.openness, profile.conscientiousness, profile.extraversion,
                  profile.agreeableness, profile.neuroticism]
        if any(t < 0.3 or t > 0.7 for t in traits):
            has_extreme = True
            break
    
    assert has_extreme, "Random generation should produce some extreme traits"


def test_personality_values_clamped():
    """Test that generated personalities stay within bounds."""
    # Generate many profiles with high variation
    for _ in range(20):
        profile = PersonalityGenerator.generate_from_archetype(
            PersonalityArchetype.MERCHANT, 
            variation=0.3
        )
        
        assert 0.0 <= profile.openness <= 1.0
        assert 0.0 <= profile.conscientiousness <= 1.0
        assert 0.0 <= profile.extraversion <= 1.0
        assert 0.0 <= profile.agreeableness <= 1.0
        assert 0.0 <= profile.neuroticism <= 1.0


def test_all_archetypes_have_valid_profiles():
    """Test all archetype templates have valid trait values."""
    for archetype in PersonalityArchetype:
        profile = PersonalityTemplates.get_template(archetype)
        
        # All traits should be in valid range
        assert 0.0 <= profile.openness <= 1.0
        assert 0.0 <= profile.conscientiousness <= 1.0
        assert 0.0 <= profile.extraversion <= 1.0
        assert 0.0 <= profile.agreeableness <= 1.0
        assert 0.0 <= profile.neuroticism <= 1.0
