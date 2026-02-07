# tests/test_visual_gemini_integration.py
"""
Tests for Visual Engine integration with Gemini DM Agent.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.mantle.prompts.dm_prompts import DMPrompts


class TestDMPromptsVisual:
    """Tests for visual-related DM prompts."""

    def test_get_visual_direction(self):
        """Test visual direction prompt is returned."""
        direction = DMPrompts.get_visual_direction()

        assert "VISUAL DIRECTION" in direction
        assert "art director" in direction.lower()
        assert "visual_assessment" in direction
        assert "image" in direction.lower()

    def test_get_visual_schema(self):
        """Test visual assessment schema is returned."""
        schema = DMPrompts.get_visual_schema()

        assert "visual_assessment" in schema
        assert "image_type" in schema
        assert "visual_description" in schema
        assert "mood" in schema
        assert "lighting" in schema
        assert "key_elements" in schema
        # Check image types are listed
        assert "scene" in schema
        assert "portrait" in schema
        assert "location_card" in schema
        assert "item" in schema
        assert "moment" in schema

    def test_visual_direction_includes_guidelines(self):
        """Test that visual direction has proper guidelines."""
        direction = DMPrompts.get_visual_direction()

        # Should include when TO generate
        assert "new or significantly changed location" in direction.lower()
        assert "named npc for the first time" in direction.lower()
        assert "significant item" in direction.lower()

        # Should include when NOT to generate
        assert "routine dialogue" in direction.lower()
        assert "minor actions" in direction.lower()
        assert "mundane item" in direction.lower()


class TestVisualAssessmentParsing:
    """Tests for parsing visual assessments from DM responses."""

    def test_parse_response_with_visual_assessment(self):
        """Test parsing a response with visual_assessment."""
        from src.mantle.agents.dm_agent import DMAgent

        agent = DMAgent()

        response_text = '''The ancient door groans open, revealing a vast cathedral
with collapsed walls and centuries of decay.

```json
{
  "visual_summary": "Ruined cathedral with shattered stained glass and creeping vines",
  "new_entities": [],
  "visual_assessment": {
    "image_type": "location_card",
    "visual_description": "A vast gothic cathedral with its eastern wall collapsed, exposing the nave to grey sky. Broken pews scattered across dust-covered flagstones. Dark vines consume the stone saints.",
    "mood": "eerie",
    "lighting": "Pale diffused light through heavy clouds, one shaft illuminating the defaced altar",
    "key_elements": ["cathedral", "collapse", "vines", "altar", "dust"],
    "location_id": "loc_ruined_cathedral"
  }
}
```'''

        narrative, entities, summary, assessment = agent._parse_response_with_entities(
            response_text
        )

        assert "ancient door groans open" in narrative
        assert entities == []
        assert "Ruined cathedral" in summary

        # Check visual assessment
        assert assessment is not None
        assert assessment["image_type"] == "location_card"
        assert assessment["mood"] == "eerie"
        assert "gothic cathedral" in assessment["visual_description"]
        assert "cathedral" in assessment["key_elements"]
        assert assessment["location_id"] == "loc_ruined_cathedral"

    def test_parse_response_without_visual_assessment(self):
        """Test parsing a response without visual_assessment."""
        from src.mantle.agents.dm_agent import DMAgent

        agent = DMAgent()

        response_text = '''You continue walking down the corridor.

```json
{
  "visual_summary": "Dark stone corridor",
  "new_entities": []
}
```'''

        narrative, entities, summary, assessment = agent._parse_response_with_entities(
            response_text
        )

        assert "walking down the corridor" in narrative
        assert assessment is None

    def test_parse_portrait_assessment(self):
        """Test parsing a portrait-type assessment."""
        from src.mantle.agents.dm_agent import DMAgent

        agent = DMAgent()

        response_text = '''A grizzled dwarf looks up from his anvil, hammer pausing mid-swing.

```json
{
  "visual_summary": "Dwarven blacksmith at his forge",
  "new_entities": [],
  "visual_assessment": {
    "image_type": "portrait",
    "visual_description": "A stout dwarf with coal-black eyes and burn scars across his forearms. His braided beard is singed at the tips. Sweat glistens on his brow.",
    "mood": "peaceful",
    "lighting": "Warm forge light from below, casting deep shadows upward",
    "key_elements": ["dwarf", "beard", "scars", "sweat", "forge glow"],
    "character_id": "npc_thorin_smith",
    "character_description": "Middle-aged dwarf blacksmith with burn scars and a braided beard"
  }
}
```'''

        narrative, entities, summary, assessment = agent._parse_response_with_entities(
            response_text
        )

        assert assessment is not None
        assert assessment["image_type"] == "portrait"
        assert assessment["character_id"] == "npc_thorin_smith"
        assert "dwarf" in assessment["visual_description"].lower()

    def test_parse_moment_assessment(self):
        """Test parsing a climactic moment assessment."""
        from src.mantle.agents.dm_agent import DMAgent

        agent = DMAgent()

        response_text = '''The dragon's eye snaps open, ancient and terrible. The ground trembles.

```json
{
  "visual_summary": "Dragon awakening",
  "new_entities": [],
  "visual_assessment": {
    "image_type": "moment",
    "visual_description": "A massive amber eye, slitted pupil dilating as ancient intelligence stirs. Scales like tarnished gold frame the eye. Steam rises from between parted jaws.",
    "mood": "dread",
    "lighting": "Single shaft of light catching the golden iris, deep shadows everywhere else",
    "key_elements": ["dragon eye", "amber", "steam", "scales", "awakening"],
    "camera_angle": "close"
  }
}
```'''

        narrative, entities, summary, assessment = agent._parse_response_with_entities(
            response_text
        )

        assert assessment is not None
        assert assessment["image_type"] == "moment"
        assert assessment["mood"] == "dread"
        assert assessment["camera_angle"] == "close"

    def test_get_visual_assessment_for_engine(self):
        """Test converting assessment dict to VisualAssessment object."""
        from src.mantle.agents.dm_agent import DMAgent

        agent = DMAgent()
        agent._last_visual_assessment = {
            "image_type": "scene",
            "visual_description": "A dark forest clearing",
            "mood": "eerie",
            "lighting": "Moonlight through branches",
            "key_elements": ["forest", "clearing", "moonlight"],
        }

        assessment = agent.get_visual_assessment_for_engine()

        assert assessment is not None
        assert assessment.image_type == "scene"
        assert assessment.mood == "eerie"
        assert "forest" in assessment.key_elements

    def test_get_visual_assessment_when_none(self):
        """Test getting assessment when none exists."""
        from src.mantle.agents.dm_agent import DMAgent

        agent = DMAgent()
        agent._last_visual_assessment = None

        assessment = agent.get_visual_assessment_for_engine()
        assert assessment is None

    def test_clear_visual_assessment(self):
        """Test clearing the stored assessment."""
        from src.mantle.agents.dm_agent import DMAgent

        agent = DMAgent()
        agent._last_visual_assessment = {"image_type": "scene"}

        agent.clear_visual_assessment()

        assert agent._last_visual_assessment is None
        assert agent.get_last_visual_assessment() is None


class TestVisualEngineToggle:
    """Tests for visual engine enable/disable."""

    def test_visual_engine_disabled_by_default(self):
        """Test that visual engine is disabled by default."""
        import os
        from src.mantle.agents.dm_agent import DMAgent

        # Clear env var if set
        original = os.environ.pop("VISUAL_ENGINE_ENABLED", None)

        try:
            agent = DMAgent()
            assert agent._visual_engine_enabled is False
        finally:
            if original:
                os.environ["VISUAL_ENGINE_ENABLED"] = original

    def test_visual_engine_enabled_via_env(self):
        """Test enabling visual engine via environment variable."""
        import os
        from src.mantle.agents.dm_agent import DMAgent

        original = os.environ.get("VISUAL_ENGINE_ENABLED")
        os.environ["VISUAL_ENGINE_ENABLED"] = "true"

        try:
            agent = DMAgent()
            assert agent._visual_engine_enabled is True
        finally:
            if original:
                os.environ["VISUAL_ENGINE_ENABLED"] = original
            else:
                os.environ.pop("VISUAL_ENGINE_ENABLED", None)
