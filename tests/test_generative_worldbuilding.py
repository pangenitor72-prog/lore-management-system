"""
Tests for Phase I-B: Generative Worldbuilding with Contradiction Checking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.lms.core.models import LoreConfidence, CONFIDENCE_RULES


class TestLoreConfidence:
    """Test LoreConfidence enum and rules."""
    
    def test_confidence_levels_exist(self):
        """Verify all confidence levels are defined."""
        assert LoreConfidence.HUMAN_APPROVED.value == "human_approved"
        assert LoreConfidence.AI_VERIFIED.value == "ai_verified"
        assert LoreConfidence.AI_GENERATED.value == "ai_generated"
        assert LoreConfidence.AI_FLAGGED.value == "ai_flagged"
    
    def test_confidence_rules_structure(self):
        """Verify confidence rules have required keys."""
        for level, rules in CONFIDENCE_RULES.items():
            assert "trust_score" in rules
            assert "can_be_contradicted" in rules
            assert "requires_review" in rules
    
    def test_human_approved_highest_trust(self):
        """Human-approved should have highest trust score."""
        assert CONFIDENCE_RULES["human_approved"]["trust_score"] == 1.0
        assert CONFIDENCE_RULES["human_approved"]["can_be_contradicted"] == False
    
    def test_ai_flagged_lowest_trust(self):
        """AI-flagged should have lowest trust and require review."""
        assert CONFIDENCE_RULES["ai_flagged"]["trust_score"] == 0.3
        assert CONFIDENCE_RULES["ai_flagged"]["requires_review"] == True


class TestAuditorEntityAudit:
    """Test AuditorAgent.audit_new_entity() method."""

    @pytest.fixture
    def mock_auditor(self):
        """Create a mock AuditorAgent."""
        from src.lms.agents.auditor_agent import AuditorAgent
        from src.lms.auditor.rule_based_auditor import RuleBasedAuditor
        from src.lms.auditor.semantic_auditor import SemanticAuditor

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=[])

        # Create mock instances of the required auditors
        mock_rule_auditor = MagicMock(spec=RuleBasedAuditor)
        mock_semantic_auditor = MagicMock(spec=SemanticAuditor)

        with patch('src.lms.agents.auditor_agent.genai'):
            auditor = AuditorAgent(
                mock_db,
                "fake-api-key",
                rule_based_auditor=mock_rule_auditor,
                semantic_auditor=mock_semantic_auditor,
            )

        return auditor, mock_db
    
    @pytest.mark.asyncio
    async def test_approve_new_entity(self, mock_auditor):
        """New entity with no conflicts should be approved."""
        auditor, mock_db = mock_auditor
        mock_db.execute.return_value = []  # No existing entity
        
        entity = {
            "name": "Test Tavern",
            "label": "Location",
            "properties": {"description": "A cozy tavern"}
        }
        
        result = await auditor.audit_new_entity(entity)
        
        assert result["approved"] == True
        assert result["action"] == "APPROVE"
        assert result["severity"] is None
        assert len(result["contradictions"]) == 0
    
    @pytest.mark.asyncio
    async def test_block_same_name_different_type(self, mock_auditor):
        """Same name with different type should be BLOCKED."""
        auditor, mock_db = mock_auditor

        # Existing entity is a Location (use entity_type to match query return)
        mock_db.execute.return_value = [{
            "name": "Thornhaven",
            "entity_type": "Location",
            "properties": {"description": "A fortified city"}
        }]

        # New entity tries to be a Character with same name
        entity = {
            "name": "Thornhaven",
            "label": "Character",
            "properties": {"description": "A brave warrior"}
        }

        result = await auditor.audit_new_entity(entity)

        assert result["approved"] == False
        assert result["action"] == "BLOCK"
        assert result["severity"] == "HIGH"
        assert len(result["contradictions"]) == 1
        assert result["contradictions"][0]["type"] == "same_name_different_type"

    @pytest.mark.asyncio
    async def test_flag_description_variation(self, mock_auditor):
        """Same name and type with different description should be FLAGGED."""
        auditor, mock_db = mock_auditor

        # Existing entity (use entity_type to match query return)
        mock_db.execute.return_value = [{
            "name": "The Red Dragon Inn",
            "entity_type": "Location",
            "properties": {"description": "A popular tavern"}
        }]

        # New entity with same name/type but different description
        entity = {
            "name": "The Red Dragon Inn",
            "label": "Location",
            "properties": {"description": "A seedy dive bar"}
        }

        result = await auditor.audit_new_entity(entity)

        assert result["approved"] == True  # Flagged but allowed
        assert result["action"] == "FLAG"
        assert result["severity"] in ["MEDIUM", "LOW"]


class TestDMAgentEntityExtraction:
    """Test DMAgent entity extraction from player input."""

    @pytest.fixture
    def mock_dm_agent(self):
        """Create a mock DMAgent."""
        from src.lms.agents.dm_agent import DMAgent

        mock_db = AsyncMock()
        mock_query_agent = MagicMock()
        mock_auditor_agent = MagicMock()

        with patch('src.lms.agents.dm_agent.genai') as mock_genai:
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model

            agent = DMAgent(
                mock_db,
                query_agent=mock_query_agent,
                auditor_agent=mock_auditor_agent,
                api_key="fake-api-key"
            )
            agent.model = mock_model

        return agent
    
    def test_parse_response_with_entities(self, mock_dm_agent):
        """Test parsing DM response that includes entity JSON."""
        response_text = """The bartender looks up from polishing a glass. "The Crimson Wastes? 
        Dangerous place, that. Full of sand wyrms and worse."
        
```json
{
  "new_entities": [
    {
      "name": "Crimson Wastes",
      "label": "Location",
      "properties": {
        "description": "A dangerous desert region full of sand wyrms"
      }
    }
  ]
}
```"""
        
        narrative, entities = mock_dm_agent._parse_response_with_entities(response_text)
        
        assert "The bartender looks up" in narrative
        assert "```json" not in narrative
        assert len(entities) == 1
        assert entities[0]["name"] == "Crimson Wastes"
        assert entities[0]["label"] == "Location"
    
    def test_parse_response_without_entities(self, mock_dm_agent):
        """Test parsing DM response with no entity JSON."""
        response_text = "The guard nods and lets you pass through the gate."
        
        narrative, entities = mock_dm_agent._parse_response_with_entities(response_text)
        
        assert narrative == response_text
        assert len(entities) == 0


class TestWorldbuildingRules:
    """Test worldbuilding rules loading."""
    
    def test_load_worldbuilding_rules(self):
        """Test that worldbuilding rules can be loaded."""
        from src.lms.agents.dm_agent import load_worldbuilding_rules
        
        rules = load_worldbuilding_rules()
        
        # Should return something (even if empty string when disabled)
        assert isinstance(rules, str)
    
    def test_rules_disabled_via_env(self):
        """Test that rules can be disabled via environment variable."""
        import os
        from src.lms.agents.dm_agent import load_worldbuilding_rules
        
        original = os.environ.get("ENABLE_WORLDBUILDING_RULES")
        
        try:
            os.environ["ENABLE_WORLDBUILDING_RULES"] = "false"
            rules = load_worldbuilding_rules()
            assert rules == ""
        finally:
            if original:
                os.environ["ENABLE_WORLDBUILDING_RULES"] = original
            else:
                os.environ.pop("ENABLE_WORLDBUILDING_RULES", None)

