"""Test Entity Factory templates and validation."""

import pytest
from src.lms.core.entity_factory import EntityFactory, EntityTemplate
from src.lms.core.models import EntityType

def test_all_entity_types_have_templates():
    """Verify all entity types have templates defined."""
    for entity_type in EntityType:
        assert entity_type in EntityFactory.TEMPLATES

def test_character_template_structure():
    """Verify Character template has required structure."""
    template = EntityFactory.get_template(EntityType.CHARACTER)
    
    assert "name" in template.required_properties
    assert "description" in template.required_properties
    assert len(template.generation_guidelines) > 0
    assert len(template.naming_conventions) > 0

def test_templates_are_setting_agnostic():
    """Ensure templates don't hardcode specific settings."""
    forbidden_terms = [
        "Aethermoor",
        "Celtic",
        "Gaelic", 
        "Third Age",
        "Year 1247",
        "dark fairy tale"
    ]
    
    for entity_type, template in EntityFactory.TEMPLATES.items():
        guidelines = template.generation_guidelines.lower()
        naming = template.naming_conventions.lower()
        
        for term in forbidden_terms:
            assert term.lower() not in guidelines, \
                f"{entity_type} template contains hardcoded setting term: {term}"
            assert term.lower() not in naming, \
                f"{entity_type} naming contains hardcoded setting term: {term}"

def test_validate_entity_with_all_required():
    """Test validation passes with all required properties."""
    template = EntityFactory.get_template(EntityType.CHARACTER)
    
    entity = {
        "name": "Test Character",
        "properties": {
            "name": "Test Character",
            "description": "A test character",
            "role": "Tester"
        }
    }
    
    assert EntityFactory.validate_entity(entity, template) == True

def test_validate_entity_missing_required():
    """Test validation fails with missing required properties."""
    template = EntityFactory.get_template(EntityType.CHARACTER)
    
    entity = {
        "name": "Test Character",
        "properties": {
            "name": "Test Character"
            # Missing description and role
        }
    }
    
    with pytest.raises(ValueError) as excinfo:
        EntityFactory.validate_entity(entity, template)
    
    assert "missing required properties" in str(excinfo.value).lower()

def test_create_entity_skeleton():
    """Test entity skeleton creation."""
    skeleton = EntityFactory.create_entity_skeleton(
        EntityType.CHARACTER,
        "Test NPC"
    )
    
    assert skeleton["name"] == "Test NPC"
    assert skeleton["label"] == "Character"
    assert "name" in skeleton["properties"]
    assert "description" in skeleton["properties"]
    assert "role" in skeleton["properties"]

def test_all_templates_have_required_fields():
    """Verify all templates have necessary structure."""
    for entity_type, template in EntityFactory.TEMPLATES.items():
        assert len(template.required_properties) > 0, \
            f"{entity_type} has no required properties"
        assert len(template.generation_guidelines) > 100, \
            f"{entity_type} has insufficient guidelines"
        assert "naming" in template.naming_conventions.lower(), \
            f"{entity_type} missing naming convention guidance"

