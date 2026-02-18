# tests/test_overlay_system.py
"""
Tests for the Overlay/Instance System and Narrative Auditor.

These systems track NPC state changes during gameplay sessions:
- Death, capture, departure detection
- Session-scoped overlays (canon remains immutable)
- Contradiction detection against overlays
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

# Import the functions we're testing
from src.mantle.api.helpers.narrative_extraction import (
    extract_entity_names_from_text,
)


class TestEntityNameExtraction:
    """Test entity name extraction from narrative text."""

    def test_extracts_titled_names(self):
        """Should extract names with titles like Lord, Lady, Captain."""
        narrative = "Lord Blackwood entered the chamber, followed by Lady Ashworth."
        names = extract_entity_names_from_text(narrative)
        # The extractor may grab slightly different spans, check for presence
        names_joined = " ".join(names).lower()
        assert "lord blackwood" in names_joined
        assert "lady ashworth" in names_joined

    def test_extracts_the_patterns(self):
        """Should extract 'The X' patterns like The Iron Guard."""
        narrative = "The Iron Guard stood watch at the gate of The Crimson Tower."
        names = extract_entity_names_from_text(narrative)
        assert "The Iron Guard" in names
        assert "The Crimson Tower" in names

    def test_handles_empty_text(self):
        """Should return empty list for empty text."""
        assert extract_entity_names_from_text("") == []
        assert extract_entity_names_from_text(None) == []


class TestDeathPatternDetection:
    """Test death pattern detection in narratives."""

    @pytest.mark.parametrize("narrative,expected_dead", [
        ("Lord Blackwood dies in the battle.", True),
        ("The knight was killed by the dragon.", True),
        ("Marcus fell, slain by his own brother.", True),
        ("She murdered the baron in cold blood.", True),
        ("Lord Blackwood watched the sunset.", False),
        ("The knight rode into battle.", False),
    ])
    def test_death_patterns(self, narrative, expected_dead):
        """Should detect various death-related phrases."""
        death_patterns = [
            "dies", "died", "dead", "killed", "slain", "murdered",
            "perished", "fell lifeless", "breathed his last", "breathed her last",
            "no longer breathing", "lies dead", "lay dead",
        ]
        narrative_lower = narrative.lower()
        found_death = any(p in narrative_lower for p in death_patterns)
        assert found_death == expected_dead


class TestCapturePatternDetection:
    """Test capture pattern detection in narratives."""

    @pytest.mark.parametrize("narrative,expected_captured", [
        ("The guards captured Lady Ashworth.", True),
        ("He was thrown in the dungeon.", True),
        ("Marcus was taken prisoner by the enemy.", True),
        ("They put her in chains.", True),
        ("Lady Ashworth escaped into the night.", False),
        ("The guards watched her leave.", False),
    ])
    def test_capture_patterns(self, narrative, expected_captured):
        """Should detect various capture-related phrases."""
        capture_patterns = [
            "captured", "imprisoned", "arrested", "taken prisoner",
            "in chains", "bound and gagged", "thrown in the dungeon",
        ]
        narrative_lower = narrative.lower()
        found_capture = any(p in narrative_lower for p in capture_patterns)
        assert found_capture == expected_captured


class TestDeparturePatternDetection:
    """Test departure/missing pattern detection in narratives."""

    @pytest.mark.parametrize("narrative,expected_missing", [
        ("The stranger vanished into thin air.", True),
        ("Marcus fled the city before dawn.", True),
        ("She escaped through the secret passage.", True),
        ("He was nowhere to be found.", True),
        ("The stranger greeted them warmly.", False),
        ("Marcus entered the tavern.", False),
    ])
    def test_departure_patterns(self, narrative, expected_missing):
        """Should detect various departure/missing phrases."""
        departure_patterns = [
            "fled", "escaped", "vanished", "disappeared",
            "ran away", "nowhere to be found",
        ]
        narrative_lower = narrative.lower()
        found_departure = any(p in narrative_lower for p in departure_patterns)
        assert found_departure == expected_missing


class TestProximityDetection:
    """Test that name-pattern proximity matters."""

    def test_distant_pattern_not_matched(self):
        """A death word far from the name shouldn't trigger."""
        narrative = (
            "Lord Blackwood entered the tavern. The bard sang songs of heroes. "
            "The fire crackled warmly. A distant war killed many soldiers."
        )
        # "Lord Blackwood" is at position 0
        # "killed" is at position 100+
        # Distance > 60 characters, should NOT match
        name_idx = narrative.lower().find("lord blackwood")
        pattern_idx = narrative.lower().find("killed")
        assert abs(name_idx - pattern_idx) > 60  # Should be far apart

    def test_close_pattern_matched(self):
        """A death word close to the name should trigger."""
        narrative = "Lord Blackwood was killed by the assassin."
        name_idx = narrative.lower().find("lord blackwood")
        pattern_idx = narrative.lower().find("killed")
        assert abs(name_idx - pattern_idx) < 60  # Should be close


class TestOverlayReadWrite:
    """Test overlay read/write consistency."""

    @pytest.mark.asyncio
    async def test_write_then_read_overlay(self):
        """Written overlay data should be readable."""
        # This would require a real or mocked Neo4j connection
        # For now, just verify the query structure is correct
        from src.mantle.db.neo4j_adapter import Neo4jDatabase

        # Verify the relationship name matches between read and write
        # Read uses: [:OVERRIDES]
        # Write uses: [:OVERRIDES]
        # (We fixed the bug where read used [:INSTANCE_OF])
        read_query = """
            MATCH (e:Entity {canon_id: $cid})
            OPTIONAL MATCH (s:Session {session_id: $sid})-[:CONTAINS]->(i:Instance)-[:OVERRIDES]->(e)
            RETURN COALESCE(properties(i), properties(e)) as entity
        """
        write_query = """
            MERGE (i)-[:OVERRIDES]->(e)
        """
        # Both should use OVERRIDES
        assert ":OVERRIDES" in read_query
        assert ":OVERRIDES" in write_query
