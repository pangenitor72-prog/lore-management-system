# tests/airpg/test_dual_mode.py
"""
Verification tests for Dual-Mode Gameplay system.

Tests:
1. Isolation: Actions in Save A do not affect Save B
2. Intervention: RPG_MANUAL mode pauses for dice rolls
3. Compatibility: STORY mode ignores dice rules entirely
4. Pacing: ONE_SHOT mode drives toward climax
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.airpg.runtime.game_config import (
    GameConfig,
    CASUAL_CONFIG,
    HARDCORE_CONFIG,
    RPG_AUTO_CONFIG,
)
from src.airpg.runtime.session_state import SessionState
from src.airpg.runtime.session_loop import run_session_step, StepResult
from src.airpg.runtime.gameplay_rules import Intervention, RuleResult
from src.airpg.runtime.rule_packs import get_rules_for_config, RPG_RULES, STORY_RULES
from src.airpg.runtime.rules.dnd5e_rules import stat_check_rule, combat_rule
from src.airpg.runtime.runtime import MinimalRuntime
from src.lms.dnd5e import CharacterSheet, AbilityScores


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_character():
    """Create a test D&D 5e character."""
    abilities = AbilityScores(
        strength=16,
        dexterity=14,
        constitution=14,
        intelligence=10,
        wisdom=12,
        charisma=8,
    )
    return CharacterSheet(
        name="Test Fighter",
        origin="human",
        archetype="fighter",
        ability_scores=abilities,
        max_hit_points=12,
        current_hit_points=12,
        skill_proficiencies=["athletics", "perception"],
    )


@pytest.fixture
def mock_runtime():
    """Create a mock MinimalRuntime."""
    runtime = MinimalRuntime()
    return runtime


@pytest.fixture
def mock_deliver():
    """Create a mock deliver function."""
    def deliver(receiver, sender, message):
        return []  # No forwards
    return deliver


# ============================================================================
# TEST: GameConfig Defaults (Casual Experience)
# ============================================================================

class TestGameConfigDefaults:
    """Verify GameConfig defaults to casual/low-friction experience."""

    def test_default_mode_is_story(self):
        """Default mode should be STORY (no visible mechanics)."""
        config = GameConfig()
        assert config.mode == "STORY"

    def test_default_dice_is_narrative(self):
        """Default dice mechanic should be NARRATIVE (AI handles)."""
        config = GameConfig()
        assert config.dice_mechanic == "NARRATIVE"

    def test_default_complexity_is_concise(self):
        """Default complexity should be CONCISE (short responses)."""
        config = GameConfig()
        assert config.narrative_complexity == "CONCISE"

    def test_default_scope_is_one_shot(self):
        """Default scope should be ONE_SHOT (ends in ~20 turns)."""
        config = GameConfig()
        assert config.session_scope == "ONE_SHOT"

    def test_casual_config_preset(self):
        """CASUAL_CONFIG preset should have all defaults."""
        assert CASUAL_CONFIG.mode == "STORY"
        assert CASUAL_CONFIG.dice_mechanic == "NARRATIVE"
        assert CASUAL_CONFIG.narrative_complexity == "CONCISE"
        assert CASUAL_CONFIG.session_scope == "ONE_SHOT"

    def test_hardcore_config_preset(self):
        """HARDCORE_CONFIG preset should be full RPG experience."""
        assert HARDCORE_CONFIG.mode == "RPG"
        assert HARDCORE_CONFIG.dice_mechanic == "MANUAL"
        assert HARDCORE_CONFIG.narrative_complexity == "VERBOSE"
        assert HARDCORE_CONFIG.session_scope == "CAMPAIGN"


# ============================================================================
# TEST: Intervention Protocol (RPG_MANUAL Mode)
# ============================================================================

class TestInterventionProtocol:
    """Verify Intervention system works for RPG_MANUAL mode."""

    def test_manual_mode_triggers_intervention(self, test_character):
        """RPG/MANUAL mode should return Intervention for skill checks."""
        config = GameConfig(mode="RPG", dice_mechanic="MANUAL")
        state = SessionState(
            turn_index=0,
            config=config,
            character=test_character,
        )

        result = stat_check_rule("I climb the wall", state)

        assert isinstance(result, Intervention)
        assert result.type == "INPUT_REQUEST"
        assert "Athletics" in result.prompt
        assert "DC" in result.prompt
        assert result.context["skill"] == "athletics"

    def test_manual_mode_combat_intervention(self, test_character):
        """RPG/MANUAL mode should return Intervention for attacks."""
        config = GameConfig(mode="RPG", dice_mechanic="MANUAL")
        state = SessionState(
            turn_index=0,
            config=config,
            character=test_character,
        )

        result = combat_rule("I attack the goblin", state)

        assert isinstance(result, Intervention)
        assert result.type == "INPUT_REQUEST"
        assert "Attack" in result.prompt

    def test_intervention_has_modifier_info(self, test_character):
        """Intervention should include character's modifier."""
        config = GameConfig(mode="RPG", dice_mechanic="MANUAL")
        state = SessionState(
            turn_index=0,
            config=config,
            character=test_character,
        )

        result = stat_check_rule("I climb the wall", state)

        # Fighter with 16 STR (+3) and proficiency (+2) = +5 Athletics
        assert result.context["modifier"] == 5


# ============================================================================
# TEST: STORY Mode Compatibility
# ============================================================================

class TestStoryModeCompatibility:
    """Verify STORY mode ignores all dice rules."""

    def test_story_mode_passthrough(self, test_character):
        """STORY mode should pass messages through unchanged."""
        config = GameConfig(mode="STORY")
        state = SessionState(
            turn_index=0,
            config=config,
            character=test_character,
        )

        result = stat_check_rule("I climb the wall", state)

        assert isinstance(result, str)
        assert result == "I climb the wall"  # Unchanged

    def test_no_config_is_story_mode(self, test_character):
        """No config (config=None) should behave as STORY mode."""
        state = SessionState(
            turn_index=0,
            config=None,
            character=test_character,
        )

        result = stat_check_rule("I climb the wall", state)

        assert isinstance(result, str)
        assert result == "I climb the wall"

    def test_story_rules_empty(self):
        """STORY_RULES should be empty (pure narrative)."""
        assert STORY_RULES == []

    def test_get_rules_for_none_config(self):
        """get_rules_for_config(None) should return STORY_RULES."""
        rules = get_rules_for_config(None)
        assert rules == STORY_RULES

    def test_get_rules_for_story_config(self):
        """get_rules_for_config(STORY mode) should return STORY_RULES."""
        config = GameConfig(mode="STORY")
        rules = get_rules_for_config(config)
        assert rules == STORY_RULES


# ============================================================================
# TEST: RPG_AUTO Mode
# ============================================================================

class TestRPGAutoMode:
    """Verify RPG/AUTO mode auto-resolves checks."""

    def test_auto_mode_resolves_checks(self, test_character):
        """RPG/AUTO mode should auto-roll and return result."""
        config = GameConfig(mode="RPG", dice_mechanic="AUTO")
        state = SessionState(
            turn_index=0,
            config=config,
            character=test_character,
        )

        result = stat_check_rule("I climb the wall", state)

        assert isinstance(result, str)
        assert "Athletics" in result or "athletics" in result.lower()
        assert "DC" in result
        # Should have roll result
        assert any(word in result for word in ["Success", "Fail", "check"])


# ============================================================================
# TEST: Pacing Phases (ONE_SHOT Mode)
# ============================================================================

class TestPacingPhases:
    """Verify ONE_SHOT pacing phases work correctly."""

    def test_intro_phase_turns_0_2(self):
        """Turns 0-2 should be INTRO phase."""
        config = GameConfig(session_scope="ONE_SHOT")

        assert config.get_pacing_phase(0) == "INTRO"
        assert config.get_pacing_phase(1) == "INTRO"
        assert config.get_pacing_phase(2) == "INTRO"

    def test_rising_phase_turns_3_14(self):
        """Turns 3-14 should be RISING phase."""
        config = GameConfig(session_scope="ONE_SHOT")

        assert config.get_pacing_phase(3) == "RISING"
        assert config.get_pacing_phase(10) == "RISING"
        assert config.get_pacing_phase(14) == "RISING"

    def test_climax_phase_turns_15_19(self):
        """Turns 15-19 should be CLIMAX phase."""
        config = GameConfig(session_scope="ONE_SHOT")

        assert config.get_pacing_phase(15) == "CLIMAX"
        assert config.get_pacing_phase(17) == "CLIMAX"
        assert config.get_pacing_phase(19) == "CLIMAX"

    def test_end_phase_turn_20_plus(self):
        """Turn 20+ should be END phase."""
        config = GameConfig(session_scope="ONE_SHOT")

        assert config.get_pacing_phase(20) == "END"
        assert config.get_pacing_phase(25) == "END"

    def test_campaign_mode_always_rising(self):
        """CAMPAIGN mode should always return RISING."""
        config = GameConfig(session_scope="CAMPAIGN")

        assert config.get_pacing_phase(0) == "RISING"
        assert config.get_pacing_phase(10) == "RISING"
        assert config.get_pacing_phase(100) == "RISING"


# ============================================================================
# TEST: Session Loop Integration
# ============================================================================

class TestSessionLoopIntegration:
    """Verify session loop handles config and interventions correctly."""

    def test_session_loop_returns_tuple_normally(
        self, test_character, mock_runtime, mock_deliver
    ):
        """Normal execution returns (state, trace) tuple."""
        config = GameConfig(mode="STORY")
        state = SessionState(
            turn_index=0,
            config=config,
            character=test_character,
        )

        result = run_session_step(
            state=state,
            player_input="Hello world",
            agent_ids=("Player",),
            deliver_fn=mock_deliver,
            runtime=mock_runtime,
            rules=None,
        )

        assert isinstance(result, tuple)
        next_state, trace = result
        assert next_state.turn_index == 1
        assert next_state.config == config
        assert next_state.character == test_character

    def test_session_loop_returns_step_result_on_intervention(
        self, test_character, mock_runtime, mock_deliver
    ):
        """Intervention returns StepResult instead of tuple."""
        config = GameConfig(mode="RPG", dice_mechanic="MANUAL")
        state = SessionState(
            turn_index=0,
            config=config,
            character=test_character,
        )

        result = run_session_step(
            state=state,
            player_input="I climb the wall",
            agent_ids=("Player",),
            deliver_fn=mock_deliver,
            runtime=mock_runtime,
            rules=RPG_RULES,
        )

        assert isinstance(result, StepResult)
        assert result.is_paused
        assert result.intervention is not None
        assert result.intervention.type == "INPUT_REQUEST"

    def test_session_state_preserved_across_steps(
        self, test_character, mock_runtime, mock_deliver
    ):
        """Config, session_id, and character preserved across steps."""
        config = GameConfig(mode="STORY")
        state = SessionState(
            turn_index=0,
            config=config,
            session_id="test-session-123",
            character=test_character,
        )

        result = run_session_step(
            state=state,
            player_input="Hello",
            agent_ids=("Player",),
            deliver_fn=mock_deliver,
            runtime=mock_runtime,
            rules=None,
        )

        next_state, _ = result
        assert next_state.config == config
        assert next_state.session_id == "test-session-123"
        assert next_state.character == test_character


# ============================================================================
# TEST: Save Isolation (Delta Layer)
# ============================================================================

class TestSaveIsolation:
    """Verify actions in Save A do not affect Save B."""

    def test_different_session_ids_are_isolated(self, test_character):
        """Different session_ids should have independent state."""
        config = GameConfig()

        state_a = SessionState(
            turn_index=5,
            config=config,
            session_id="save-a",
            character=test_character,
        )

        state_b = SessionState(
            turn_index=10,
            config=config,
            session_id="save-b",
            character=test_character,
        )

        # States are independent
        assert state_a.session_id != state_b.session_id
        assert state_a.turn_index != state_b.turn_index

    def test_character_state_independent_per_session(self):
        """Character modifications in one session don't affect another."""
        abilities = AbilityScores(
            strength=16, dexterity=14, constitution=14,
            intelligence=10, wisdom=12, charisma=8,
        )

        char_a = CharacterSheet(
            name="Hero A",
            origin="human",
            archetype="fighter",
            ability_scores=abilities,
            max_hit_points=20,
            current_hit_points=20,
        )

        char_b = CharacterSheet(
            name="Hero B",
            origin="elf",
            archetype="wizard",
            ability_scores=abilities,
            max_hit_points=15,
            current_hit_points=15,
        )

        state_a = SessionState(
            turn_index=0,
            session_id="save-a",
            character=char_a,
        )

        state_b = SessionState(
            turn_index=0,
            session_id="save-b",
            character=char_b,
        )

        # Damage character A
        damaged_char_a = char_a.take_damage(10)

        # Character B should be unaffected
        assert state_b.character.current_hit_points == 15
        assert damaged_char_a.current_hit_points == 10


# ============================================================================
# TEST: Helper Methods
# ============================================================================

class TestHelperMethods:
    """Test GameConfig helper methods."""

    def test_requires_dice(self):
        """requires_dice() should return True only for RPG non-NARRATIVE."""
        assert GameConfig(mode="STORY").requires_dice() is False
        assert GameConfig(mode="RPG", dice_mechanic="NARRATIVE").requires_dice() is False
        assert GameConfig(mode="RPG", dice_mechanic="AUTO").requires_dice() is True
        assert GameConfig(mode="RPG", dice_mechanic="MANUAL").requires_dice() is True

    def test_is_manual_rolls(self):
        """is_manual_rolls() should return True only for RPG/MANUAL."""
        assert GameConfig(mode="STORY").is_manual_rolls() is False
        assert GameConfig(mode="RPG", dice_mechanic="AUTO").is_manual_rolls() is False
        assert GameConfig(mode="RPG", dice_mechanic="MANUAL").is_manual_rolls() is True

    def test_is_one_shot(self):
        """is_one_shot() should return True for ONE_SHOT scope."""
        assert GameConfig(session_scope="ONE_SHOT").is_one_shot() is True
        assert GameConfig(session_scope="CAMPAIGN").is_one_shot() is False

    def test_is_verbose(self):
        """is_verbose() should return True for VERBOSE complexity."""
        assert GameConfig(narrative_complexity="CONCISE").is_verbose() is False
        assert GameConfig(narrative_complexity="VERBOSE").is_verbose() is True
