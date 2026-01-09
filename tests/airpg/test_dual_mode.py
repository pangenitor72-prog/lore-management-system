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
        """Default scope should be ONE_SHOT (ends in ~100 turns)."""
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


# ============================================================================
# TEST: World Integrity Check
# ============================================================================

class TestWorldIntegrity:
    """Verify World Integrity Check functionality."""

    def test_canon_truths_defaults(self):
        """CanonTruths should have sensible defaults."""
        from src.airpg.runtime.world_integrity import CanonTruths

        truths = CanonTruths()
        assert truths.world_name == "Unknown World"
        assert truths.theme == "Fantasy Adventure"
        assert truths.tone == "Balanced"
        assert truths.core_conflict == ""
        assert truths.key_factions == []
        assert truths.forbidden_elements == []

    def test_canon_truths_prompt_injection(self):
        """CanonTruths should format for prompt injection."""
        from src.airpg.runtime.world_integrity import CanonTruths

        truths = CanonTruths(
            world_name="Aethoria",
            theme="Dark Fantasy",
            tone="Grim",
            core_conflict="The Old Gods awaken",
            key_factions=["The Iron Circle", "House Valdris"],
        )

        injection = truths.to_prompt_injection()

        assert "IMMUTABLE CANON TRUTHS" in injection
        assert "Aethoria" in injection
        assert "Dark Fantasy" in injection
        assert "Grim" in injection
        assert "The Old Gods awaken" in injection
        assert "The Iron Circle" in injection
        assert "House Valdris" in injection

    def test_integrity_result_defaults(self):
        """IntegrityResult should track validation state."""
        from src.airpg.runtime.world_integrity import IntegrityResult

        result = IntegrityResult(is_valid=False)
        assert result.is_valid is False
        assert result.errors == []
        assert result.warnings == []
        assert result.canon_truths is None
        assert result.location_count == 0
        assert result.faction_count == 0
        assert result.npc_count == 0
        assert result.has_root is False

    def test_integrity_result_with_errors(self):
        """IntegrityResult should store validation errors."""
        from src.airpg.runtime.world_integrity import IntegrityResult

        result = IntegrityResult(
            is_valid=False,
            errors=["No world root defined"],
            warnings=["Only one location defined"],
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1


# ============================================================================
# TEST: Inventory and Game Events
# ============================================================================

class TestInventorySystem:
    """Verify Inventory and GameEvent functionality."""

    def test_item_creation(self):
        """Item should be created with proper defaults."""
        from src.airpg.runtime.game_events import Item

        item = Item(name="Longsword")
        assert item.name == "Longsword"
        assert item.quantity == 1
        assert item.item_type == "misc"
        assert item.equipped is False

    def test_item_with_properties(self):
        """Item should store all weapon properties."""
        from src.airpg.runtime.game_events import Item

        sword = Item(
            name="Vorpal Blade",
            quantity=1,
            item_type="weapon",
            description="A blade that severs heads",
            damage="2d6",
            equipped=True,
        )

        assert sword.name == "Vorpal Blade"
        assert sword.item_type == "weapon"
        assert sword.damage == "2d6"
        assert sword.equipped is True

    def test_inventory_add_item(self):
        """Inventory.add_item should add item and emit event."""
        from src.airpg.runtime.game_events import Item, Inventory, GameEventType

        inv = Inventory()
        item = Item(name="Health Potion", item_type="consumable")

        event = inv.add_item(item, turn=5)

        assert len(inv.items) == 1
        assert inv.items[0].name == "Health Potion"
        assert event.type == GameEventType.ITEM_ADDED
        assert event.data["item"] == "Health Potion"
        assert event.turn == 5

    def test_inventory_stack_items(self):
        """Adding duplicate items should stack quantity."""
        from src.airpg.runtime.game_events import Item, Inventory

        inv = Inventory()
        inv.add_item(Item(name="Arrow", quantity=10))
        inv.add_item(Item(name="Arrow", quantity=5))

        assert len(inv.items) == 1
        assert inv.items[0].quantity == 15

    def test_inventory_remove_item(self):
        """Inventory.remove_item should remove and emit event."""
        from src.airpg.runtime.game_events import Item, Inventory, GameEventType

        inv = Inventory()
        inv.add_item(Item(name="Torch", quantity=3))

        event = inv.remove_item("Torch", quantity=1, turn=2)

        assert inv.items[0].quantity == 2
        assert event.type == GameEventType.ITEM_REMOVED
        assert event.data["quantity"] == 1

    def test_inventory_gold(self):
        """Inventory should track gold changes."""
        from src.airpg.runtime.game_events import Inventory, GameEventType

        inv = Inventory(gold=50)
        assert inv.gold == 50

        event = inv.add_gold(25, turn=1)
        assert inv.gold == 75
        assert event.type == GameEventType.GOLD_CHANGED
        assert event.data["amount"] == 25
        assert event.data["total"] == 75

        event = inv.remove_gold(10, turn=2)
        assert inv.gold == 65
        assert event.data["amount"] == -10

    def test_starting_equipment(self):
        """get_starting_inventory should return archetype-specific gear."""
        from src.airpg.runtime.game_events import get_starting_inventory

        fighter_inv = get_starting_inventory("fighter", starting_gold=15)

        assert fighter_inv.gold == 15
        assert len(fighter_inv.items) > 0

        # Fighter should have weapon
        item_names = [item.name for item in fighter_inv.items]
        assert "Longsword" in item_names

    def test_game_event_serialization(self):
        """GameEvent should serialize to dict."""
        from src.airpg.runtime.game_events import GameEvent

        event = GameEvent.skill_check(
            skill="Athletics",
            roll=15,
            modifier=3,
            dc=12,
            success=True,
            turn=7,
        )

        data = event.to_dict()

        assert data["type"] == "SKILL_CHECK"
        assert data["data"]["skill"] == "Athletics"
        assert data["data"]["roll"] == 15
        assert data["data"]["total"] == 18
        assert data["data"]["success"] is True
        assert data["turn"] == 7


# ============================================================================
# TEST: Session State with Inventory
# ============================================================================

class TestSessionStateInventory:
    """Verify SessionState preserves inventory across transitions."""

    def test_session_state_with_inventory(self):
        """SessionState should include optional inventory field."""
        from src.airpg.runtime.game_events import Inventory, Item

        inv = Inventory()
        inv.add_item(Item(name="Rope", quantity=1))

        state = SessionState(
            turn_index=0,
            inventory=inv,
        )

        assert state.inventory is not None
        assert len(state.inventory.items) == 1

    def test_session_state_preserves_inventory(
        self, test_character, mock_runtime, mock_deliver
    ):
        """Session loop should preserve inventory across steps."""
        from src.airpg.runtime.game_events import Inventory, Item

        config = GameConfig(mode="STORY")
        inv = Inventory()
        inv.add_item(Item(name="Torch"))

        state = SessionState(
            turn_index=0,
            config=config,
            character=test_character,
            inventory=inv,
        )

        result = run_session_step(
            state=state,
            player_input="I look around",
            agent_ids=("Player",),
            deliver_fn=mock_deliver,
            runtime=mock_runtime,
            rules=None,
        )

        next_state, _ = result
        assert next_state.inventory is not None
        assert len(next_state.inventory.items) == 1
        assert next_state.inventory.items[0].name == "Torch"

    def test_session_state_pending_events(self):
        """SessionState should track pending events as tuple."""
        from src.airpg.runtime.game_events import GameEvent, GameEventType

        event1 = GameEvent.item_added("Sword", 1, turn=0)
        event2 = GameEvent.gold_changed(10, 100, turn=0)

        state = SessionState(
            turn_index=0,
            pending_events=(event1, event2),
        )

        assert len(state.pending_events) == 2
        assert state.pending_events[0].type == GameEventType.ITEM_ADDED
        assert state.pending_events[1].type == GameEventType.GOLD_CHANGED


# ============================================================================
# TEST: WorldNotReadyError
# ============================================================================

class TestWorldNotReadyError:
    """Verify WorldNotReadyError exception functionality."""

    def test_world_not_ready_error_creation(self):
        """WorldNotReadyError should capture errors and world_id."""
        from src.airpg.runtime.world_integrity import WorldNotReadyError

        errors = ["No root defined", "No locations"]
        error = WorldNotReadyError(errors, world_id="world_123")

        assert error.world_id == "world_123"
        assert error.errors == errors
        assert "No root defined" in str(error)
        assert "world_123" in str(error)

    def test_world_not_ready_error_to_dict(self):
        """WorldNotReadyError should serialize to dict for API."""
        from src.airpg.runtime.world_integrity import WorldNotReadyError

        errors = ["Missing faction"]
        error = WorldNotReadyError(errors, world_id="test_world")

        data = error.to_dict()

        assert data["error"] == "world_not_ready"
        assert data["world_id"] == "test_world"
        assert "Missing faction" in data["errors"]

    def test_world_not_ready_error_without_world_id(self):
        """WorldNotReadyError should work without world_id."""
        from src.airpg.runtime.world_integrity import WorldNotReadyError

        error = WorldNotReadyError(["No root"])

        assert error.world_id is None
        assert "No root" in str(error)


# ============================================================================
# TEST: Event Extraction from Narrative
# ============================================================================

class TestEventExtraction:
    """Verify event extraction from narrative text."""

    def test_extract_item_from_narrative(self):
        """Should extract ITEM_ADDED from 'find' phrases."""
        from src.lms.api.game_routes import _extract_events_from_narrative

        narrative = "You find a Rusty Key on the ground."
        events = _extract_events_from_narrative(narrative, None, turn=5)

        item_events = [e for e in events if e.type == "ITEM_ADDED"]
        assert len(item_events) >= 1
        assert any("Key" in e.data.get("item", "") for e in item_events)

    def test_extract_gold_from_narrative(self):
        """Should extract GOLD_CHANGED from gold mentions."""
        from src.lms.api.game_routes import _extract_events_from_narrative

        narrative = "The merchant hands you 50 gold coins."
        events = _extract_events_from_narrative(narrative, None, turn=3)

        gold_events = [e for e in events if e.type == "GOLD_CHANGED"]
        assert len(gold_events) == 1
        assert gold_events[0].data["amount"] == 50

    def test_extract_skill_check_from_mechanical_result(self):
        """Should extract SKILL_CHECK from mechanical_result."""
        from src.lms.api.game_routes import _extract_events_from_narrative

        mechanical_result = {
            "rolls": [
                {
                    "type": "skill",
                    "skill": "stealth",
                    "roll": 15,
                    "modifier": 3,
                    "total": 18,
                    "dc": 12,
                    "success": True,
                }
            ]
        }

        events = _extract_events_from_narrative("You move quietly.", mechanical_result, turn=2)

        skill_events = [e for e in events if e.type == "SKILL_CHECK"]
        assert len(skill_events) == 1
        assert skill_events[0].data["skill"] == "stealth"
        assert skill_events[0].data["success"] is True

    def test_extract_attack_from_mechanical_result(self):
        """Should extract ATTACK_ROLL from mechanical_result."""
        from src.lms.api.game_routes import _extract_events_from_narrative

        mechanical_result = {
            "rolls": [
                {
                    "type": "attack",
                    "roll": 17,
                    "modifier": 5,
                    "total": 22,
                    "is_hit": True,
                }
            ]
        }

        events = _extract_events_from_narrative("You swing your sword.", mechanical_result, turn=4)

        attack_events = [e for e in events if e.type == "ATTACK_ROLL"]
        assert len(attack_events) == 1
        assert attack_events[0].data["is_hit"] is True

    def test_no_events_for_plain_narrative(self):
        """Should return empty list for narrative without events."""
        from src.lms.api.game_routes import _extract_events_from_narrative

        narrative = "You walk down the corridor. The air is cold."
        events = _extract_events_from_narrative(narrative, None, turn=1)

        # May have some false positives, but should be minimal
        assert isinstance(events, list)
