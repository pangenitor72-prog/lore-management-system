"""
Tests for genre assessment and resolution functionality.

Tests:
1. Genre assessment from text (keyword-based)
2. Genre resolver with world_id (curated and user-created)
3. Character creation respects world mechanics genre
4. Admin API for genre management
5. Backward compatibility with existing worlds
"""

import pytest
from src.mantle.agents.genre_assessment import (
    assess_genre_from_text,
    assess_genre_from_world_data,
    GenreAssessment,
    VALID_MECHANICS_GENRES,
)
from src.mantle.utils.genre_resolver import (
    resolve_mechanics_genre_sync,
    resolve_mechanics_genre,
)


class TestGenreAssessment:
    """Test genre assessment from lore text."""
    
    def test_fantasy_genre_detection(self):
        """Test that fantasy lore is correctly detected."""
        lore = """
        In the ancient kingdom of Eldoria, Queen Seraphina ruled with wisdom and grace.
        The castle of Thornhaven stood tall, protected by powerful magic and dragon fire.
        Wizards from the Arcane Academy served as her advisors, wielding spells of great power.
        """
        
        assessment = assess_genre_from_text(lore)
        assert assessment.mechanics_genre == "fantasy"
        assert "fantasy" in assessment.genre_hints
        assert assessment.confidence > 0.5
    
    def test_scifi_genre_detection(self):
        """Test that scifi lore is correctly detected."""
        lore = """
        Captain Rivera commanded the starship Endeavor across the galaxy.
        The crew consisted of humans, aliens, and androids working together.
        They traveled through hyperspace, exploring new planets and encountering hostile robots.
        The plasma cannons were ready as they approached the space station.
        """
        
        assessment = assess_genre_from_text(lore)
        assert assessment.mechanics_genre == "scifi"
        assert assessment.confidence > 0.5
    
    def test_horror_genre_detection(self):
        """Test that horror lore is correctly detected."""
        lore = """
        The village was cursed. Vampires and werewolves haunted the night.
        Demons whispered from the shadows, and zombies rose from their graves.
        The cult performed dark rituals in the abandoned church.
        No one was safe from the monsters that lurked in the darkness.
        """
        
        assessment = assess_genre_from_text(lore)
        assert assessment.mechanics_genre == "horror"
        assert assessment.confidence > 0.5
    
    def test_modern_genre_detection(self):
        """Test that modern/realistic lore is correctly detected."""
        lore = """
        Detective Sarah Martinez drove through the city streets in her car.
        She pulled out her phone to call the police station.
        The office building loomed ahead as she parked her vehicle.
        This case was realistic - no magic, just good old-fashioned detective work.
        """
        
        assessment = assess_genre_from_text(lore)
        assert assessment.mechanics_genre == "modern"
        assert assessment.confidence > 0.4
    
    def test_cyberpunk_genre_detection(self):
        """Test that cyberpunk lore is correctly detected."""
        lore = """
        The hacker jacked into the net, her neural interface glowing.
        Megacorps ruled the neon-lit streets where chrome and augments were everywhere.
        She navigated the cyberdeck through layers of corporate security.
        The netrunner's mission was clear: steal the data and get out.
        """
        
        assessment = assess_genre_from_text(lore)
        assert assessment.mechanics_genre == "cyberpunk"
        assert assessment.confidence > 0.5
    
    def test_short_text_defaults_to_fantasy(self):
        """Test that insufficient text defaults to fantasy with low confidence."""
        lore = "A short story."
        
        assessment = assess_genre_from_text(lore)
        assert assessment.mechanics_genre == "fantasy"
        assert assessment.confidence < 0.5
    
    def test_genre_from_world_data_with_mechanics_genre(self):
        """Test assess_genre_from_world_data when mechanics_genre is already set."""
        world_data = {
            "mechanics_genre": "scifi",
            "genre_hints": ["scifi", "mystery"],
            "genre_confidence": 0.9,
        }
        
        assessment = assess_genre_from_world_data(world_data)
        assert assessment.mechanics_genre == "scifi"
        assert assessment.genre_hints == ["scifi", "mystery"]
        assert assessment.confidence == 0.9
    
    def test_genre_from_world_data_legacy_genre_field(self):
        """Test backward compatibility with legacy 'genre' field."""
        world_data = {
            "genre": "fantasy",
            "genre_hints": ["fantasy", "drama"],
        }
        
        assessment = assess_genre_from_world_data(world_data)
        assert assessment.mechanics_genre == "fantasy"
        assert "fantasy" in assessment.genre_hints
    
    def test_genre_from_world_data_with_lore_content(self):
        """Test that lore_content triggers assessment."""
        world_data = {
            "lore_content": """
            The spaceship landed on a distant planet. Aliens greeted the crew.
            Advanced technology powered their civilization. Robots served the colonists.
            """,
        }
        
        assessment = assess_genre_from_world_data(world_data)
        assert assessment.mechanics_genre == "scifi"


class TestGenreResolver:
    """Test centralized genre resolution."""
    
    def test_resolve_with_curated_world(self):
        """Test resolution when world_id points to curated world."""
        lore_bases = {
            "test_world": {
                "mechanics_genre": "scifi",
                "genre_hints": ["scifi", "mystery"],
            }
        }
        
        mechanics, flavors = resolve_mechanics_genre_sync(
            world_id="test_world",
            user_genre="fantasy",
            lore_bases=lore_bases,
        )
        
        assert mechanics == "scifi"  # World genre dominates
        assert "scifi" in flavors
        assert "fantasy" in flavors  # User genre becomes flavor
    
    def test_resolve_with_legacy_genre_field(self):
        """Test backward compatibility with legacy genre field."""
        lore_bases = {
            "legacy_world": {
                "genre": "horror",
                "genre_hints": ["horror", "gothic"],
            }
        }
        
        mechanics, flavors = resolve_mechanics_genre_sync(
            world_id="legacy_world",
            user_genre="fantasy",
            lore_bases=lore_bases,
        )
        
        assert mechanics == "horror"  # Legacy genre field works
        assert "horror" in flavors
    
    def test_resolve_without_world_uses_user_genre(self):
        """Test that user genre is used when no world_id."""
        mechanics, flavors = resolve_mechanics_genre_sync(
            world_id=None,
            user_genre="cyberpunk",
            lore_bases={},
        )
        
        assert mechanics == "cyberpunk"
        assert flavors == ["cyberpunk"]
    
    def test_resolve_with_invalid_world_uses_user_genre(self):
        """Test that invalid world_id falls back to user genre."""
        lore_bases = {
            "real_world": {
                "mechanics_genre": "modern",
            }
        }
        
        mechanics, flavors = resolve_mechanics_genre_sync(
            world_id="nonexistent_world",
            user_genre="fantasy",
            lore_bases=lore_bases,
        )
        
        assert mechanics == "fantasy"
        assert flavors == ["fantasy"]
    
    def test_resolve_defaults_to_fantasy(self):
        """Test that ultimate fallback is fantasy."""
        mechanics, flavors = resolve_mechanics_genre_sync(
            world_id=None,
            user_genre=None,
            lore_bases={},
        )
        
        assert mechanics == "fantasy"
        assert flavors == ["fantasy"]
    
    def test_resolve_same_genre_no_duplicate_flavor(self):
        """Test that when user genre matches world genre, no duplicate in flavors."""
        lore_bases = {
            "test_world": {
                "mechanics_genre": "scifi",
                "genre_hints": ["scifi"],
            }
        }
        
        mechanics, flavors = resolve_mechanics_genre_sync(
            world_id="test_world",
            user_genre="scifi",
            lore_bases=lore_bases,
        )
        
        assert mechanics == "scifi"
        assert flavors.count("scifi") == 1  # No duplicate


class TestCharacterCreationGenre:
    """Test character creation respects world mechanics genre."""
    
    def test_concept_generator_uses_mechanics_genre(self):
        """Test that ConceptGenerator respects genre parameter."""
        from src.mantle.dnd5e.creation.concept_generator import ConceptGenerator
        
        # Test with scifi genre
        generator = ConceptGenerator(genre="scifi")
        assert generator.genre == "scifi"
        
        # Test with modern genre
        generator = ConceptGenerator(genre="modern")
        assert generator.genre == "modern"
    
    def test_concept_character_has_genre_appropriate_equipment(self):
        """Test that concept-generated characters have genre-appropriate starting equipment."""
        from src.mantle.dnd5e.creation.concept_generator import ConceptGenerator
        
        # Generate a modern character
        generator = ConceptGenerator(genre="modern")
        character = generator.generate_from_concept_sync(
            "A detective investigating a murder case",
            player_id="test_player"
        )
        
        # Check equipment is modern, not fantasy
        equipment_str = " ".join(character.equipment).lower()
        
        # Should NOT have fantasy equipment
        assert "chainmail" not in equipment_str
        assert "longsword" not in equipment_str
        assert "wizard" not in equipment_str
        
        # Genre should be modern
        assert character.genre == "modern"


class TestBackwardCompatibility:
    """Test that existing worlds without mechanics_genre still work."""
    
    def test_legacy_world_with_only_genre_field(self):
        """Test that worlds with only 'genre' field work correctly."""
        world_data = {
            "id": "old_world",
            "name": "Old World",
            "genre": "fantasy",
            "genre_hints": [],
        }
        
        assessment = assess_genre_from_world_data(world_data)
        assert assessment.mechanics_genre == "fantasy"
    
    def test_legacy_world_with_genre_hints(self):
        """Test that worlds with genre_hints but no mechanics_genre work."""
        world_data = {
            "id": "old_world",
            "name": "Old World",
            "genre_hints": ["scifi", "mystery"],
        }
        
        assessment = assess_genre_from_world_data(world_data)
        # Should use first genre_hint as mechanics_genre
        assert assessment.mechanics_genre == "scifi"
        assert "scifi" in assessment.genre_hints


class TestValidGenres:
    """Test that valid genres are correctly defined and used."""
    
    def test_all_valid_genres_defined(self):
        """Test that VALID_MECHANICS_GENRES contains expected genres."""
        expected_genres = {
            "fantasy", "scifi", "modern", "horror", "western",
            "cyberpunk", "steampunk", "postapoc", "superhero",
            "mythology", "noir", "wuxia", "pirate", "dark_fantasy",
            "space_opera", "generic"
        }
        
        assert VALID_MECHANICS_GENRES == expected_genres
    
    def test_genre_assessment_produces_valid_genre(self):
        """Test that assessment always produces a valid mechanics_genre."""
        test_texts = [
            "Magic and dragons in a medieval kingdom",
            "Spaceships and aliens in the future",
            "Modern city with realistic crime",
            "Vampires and monsters in a cursed town",
        ]
        
        for text in test_texts:
            assessment = assess_genre_from_text(text)
            assert assessment.mechanics_genre in VALID_MECHANICS_GENRES
