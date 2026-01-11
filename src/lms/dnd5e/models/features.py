"""
Class Features for the d20 rules engine.

Features are special abilities that come from your archetype (class).
Unlike spells/abilities which use power slots, features use their own
resource pools (Ki, Superiority Dice, Adrenaline, etc.) or are passive/per-rest.

This module provides genre-agnostic feature definitions with automatic
terminology translation based on the active genre.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class UseType(str, Enum):
    """How often a feature can be used."""
    PASSIVE = "passive"              # Always active
    AT_WILL = "at_will"              # No limit
    PER_SHORT_REST = "per_short_rest"  # Recharges on short rest
    PER_LONG_REST = "per_long_rest"    # Recharges on long rest
    RESOURCE = "resource"            # Uses a resource pool (Ki, Superiority, etc.)


class EffectType(str, Enum):
    """What the feature does."""
    DAMAGE = "damage"                # Deal extra damage
    HEALING = "healing"              # Restore HP
    BUFF = "buff"                    # Enhance self or ally
    DEBUFF = "debuff"                # Weaken enemy
    MOVEMENT = "movement"            # Enhanced mobility
    DEFENSE = "defense"              # Reduce damage or avoid attacks
    UTILITY = "utility"              # Non-combat benefit
    ACTION = "action"                # Extra actions
    REACTION = "reaction"            # Triggered response


class ResourcePool(str, Enum):
    """Types of resource pools that power features."""
    # Universal
    NONE = "none"                    # No resource needed

    # Martial resources
    SUPERIORITY = "superiority"      # Battlemaster dice
    KI = "ki"                        # Monk energy
    RAGE = "rage"                    # Barbarian fury

    # Other class resources
    SORCERY = "sorcery"              # Sorcery points
    BARDIC = "bardic"                # Inspiration dice
    CHANNEL = "channel"              # Channel Divinity

    # Genre-specific (translated from above)
    FOCUS = "focus"                  # Modern: mental focus
    RAM = "ram"                      # Cyberpunk: processing power
    CHI = "chi"                      # Wuxia: martial energy
    GRIT = "grit"                    # Western/Post-Apoc: determination
    COMPOSURE = "composure"          # Horror/Noir: mental stability
    ADRENALINE = "adrenaline"        # Action genres: fight response


# =============================================================================
# RESOURCE POOL DEFINITIONS
# =============================================================================

class ResourcePoolData(BaseModel):
    """Definition of a resource pool."""
    id: str
    display_name: str
    description: str
    base_amount: int                           # Starting amount at level 1
    scales_with: Optional[str] = None          # Ability score that adds to pool
    level_scaling: Dict[int, int] = Field(default_factory=dict)  # Level -> amount
    recharge: str = "short_rest"               # "short_rest" or "long_rest"
    die_size: Optional[str] = None             # For pools that use dice (d8, d10)


# Genre-specific resource pool mappings
RESOURCE_POOLS_BY_GENRE: Dict[str, Dict[str, ResourcePoolData]] = {
    "fantasy": {
        "ki": ResourcePoolData(
            id="ki",
            display_name="Ki Points",
            description="Your inner spiritual energy, honed through martial discipline.",
            base_amount=0,
            scales_with="wisdom",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},  # Equal to monk level
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Superiority Dice",
            description="Your tactical expertise, represented as combat maneuver dice.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "rage": ResourcePoolData(
            id="rage",
            display_name="Rages",
            description="The primal fury that fuels your battle frenzy.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
        "bardic": ResourcePoolData(
            id="bardic",
            display_name="Bardic Inspiration",
            description="Your ability to inspire allies through performance.",
            base_amount=0,
            scales_with="charisma",
            recharge="long_rest",  # Short rest at level 5
            die_size="d6",
        ),
        "channel": ResourcePoolData(
            id="channel",
            display_name="Channel Divinity",
            description="Your connection to divine power.",
            base_amount=1,
            level_scaling={6: 2, 18: 3},
            recharge="short_rest",
        ),
    },
    "modern": {
        "focus": ResourcePoolData(
            id="focus",
            display_name="Focus",
            description="Your mental stamina and concentration under pressure.",
            base_amount=0,
            scales_with="wisdom",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Tactical Dice",
            description="Your combat experience, expressed as tactical maneuvers.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "adrenaline": ResourcePoolData(
            id="adrenaline",
            display_name="Adrenaline",
            description="The fight-or-flight response that pushes you beyond normal limits.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
    "cyberpunk": {
        "ram": ResourcePoolData(
            id="ram",
            display_name="RAM",
            description="Your cyberdeck's available processing power for running programs.",
            base_amount=0,
            scales_with="intelligence",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Combat Subroutines",
            description="Pre-programmed combat algorithms in your reflex chips.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "chrome": ResourcePoolData(
            id="chrome",
            display_name="Chrome Strain",
            description="How much you can push your cyberware before it needs recalibration.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
    "postapoc": {
        "grit": ResourcePoolData(
            id="grit",
            display_name="Grit",
            description="Your determination to survive against all odds.",
            base_amount=0,
            scales_with="wisdom",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Survival Instincts",
            description="Hard-won combat knowledge from living in the wastes.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "resolve": ResourcePoolData(
            id="resolve",
            display_name="Resolve",
            description="The will to keep fighting when everything says stop.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
    "horror": {
        "composure": ResourcePoolData(
            id="composure",
            display_name="Composure",
            description="Your mental fortitude against the horrors you face.",
            base_amount=0,
            scales_with="wisdom",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Combat Training",
            description="Skills learned hunting things that hunt humans.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "willpower": ResourcePoolData(
            id="willpower",
            display_name="Willpower",
            description="The strength to face the darkness without breaking.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
    "wuxia": {
        "chi": ResourcePoolData(
            id="chi",
            display_name="Chi",
            description="Your internal energy, cultivated through martial training.",
            base_amount=0,
            scales_with="wisdom",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Martial Techniques",
            description="Advanced fighting forms passed down through your school.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "inner_fire": ResourcePoolData(
            id="inner_fire",
            display_name="Inner Fire",
            description="The burning passion that drives your martial path.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
    "western": {
        "grit": ResourcePoolData(
            id="grit",
            display_name="Grit",
            description="True grit - the determination that keeps you standing.",
            base_amount=0,
            scales_with="wisdom",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Gunfighter Tricks",
            description="Fancy shooting and dirty fighting learned on the frontier.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "luck": ResourcePoolData(
            id="luck",
            display_name="Luck",
            description="Sometimes, luck is all you've got.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
    "noir": {
        "composure": ResourcePoolData(
            id="composure",
            display_name="Composure",
            description="Keeping your cool when the heat is on.",
            base_amount=0,
            scales_with="wisdom",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Street Smarts",
            description="Tricks you've picked up in back alleys and smoky bars.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "luck": ResourcePoolData(
            id="luck",
            display_name="Luck",
            description="In this city, luck is a lady who doesn't stay long.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
    "scifi": {
        "psi": ResourcePoolData(
            id="psi",
            display_name="Psi Points",
            description="Your psychic potential, measured in mental energy units.",
            base_amount=0,
            scales_with="wisdom",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Tactical Protocols",
            description="Combat algorithms optimized through experience.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "surge": ResourcePoolData(
            id="surge",
            display_name="Power Surge",
            description="Emergency power reserves for critical moments.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
    "steampunk": {
        "pressure": ResourcePoolData(
            id="pressure",
            display_name="Steam Pressure",
            description="The pressure in your personal steam reservoirs.",
            base_amount=0,
            scales_with="intelligence",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Gentleman's Tricks",
            description="Refined combat techniques befitting your station.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "determination": ResourcePoolData(
            id="determination",
            display_name="British Determination",
            description="The stiff upper lip that carries you through.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
    "superhero": {
        "hero_points": ResourcePoolData(
            id="hero_points",
            display_name="Hero Points",
            description="The power of heroism that fuels your abilities.",
            base_amount=0,
            scales_with="charisma",
            level_scaling={2: 2, 3: 3, 4: 4, 5: 5},
            recharge="short_rest",
        ),
        "superiority": ResourcePoolData(
            id="superiority",
            display_name="Combat Moves",
            description="Signature moves that define your fighting style.",
            base_amount=4,
            level_scaling={7: 5, 15: 6},
            recharge="short_rest",
            die_size="d8",
        ),
        "willpower": ResourcePoolData(
            id="willpower",
            display_name="Willpower",
            description="The heroic resolve that lets you push beyond limits.",
            base_amount=2,
            level_scaling={3: 3, 6: 4, 12: 5, 17: 6},
            recharge="long_rest",
        ),
    },
}


# =============================================================================
# FEATURE DATA MODEL
# =============================================================================

class FeatureData(BaseModel):
    """
    A class feature - a special ability granted by your archetype.

    Features differ from abilities/spells in that they:
    - Come from your archetype, not learned separately
    - Often use resource pools (Ki, Superiority) instead of spell slots
    - Can be passive (always on) or active (requires use)
    """
    id: str
    display_name: str
    description: str

    # Usage
    use_type: UseType = UseType.PASSIVE
    uses_per_rest: Optional[int] = None        # For PER_SHORT_REST/PER_LONG_REST
    resource_pool: Optional[str] = None        # "ki", "superiority", etc.
    resource_cost: int = 0                     # How many points/dice to spend

    # Action economy
    action_type: str = "none"                  # "action", "bonus_action", "reaction", "none"
    trigger: Optional[str] = None              # For reactions: "when hit by attack"

    # Effect
    effect_type: EffectType = EffectType.UTILITY
    bonus_dice: Optional[str] = None           # "1d8", "2d6+STR"
    bonus_flat: Optional[int] = None           # +2, +5, etc.
    bonus_to: Optional[str] = None             # "damage", "attack", "ac", "speed"
    target: str = "self"                       # "self", "ally", "enemy", "all"
    duration: str = "instant"                  # "instant", "1 round", "1 minute"

    # Scaling
    level_gained: int = 1                      # What level you get this
    scales_at_level: Dict[int, Any] = Field(default_factory=dict)  # Level -> improvement

    # Prerequisites
    requires_feature: Optional[str] = None     # Must have another feature first
    archetype_restriction: List[str] = Field(default_factory=list)  # Only these archetypes

    # Genre translations (populated per-genre)
    genre: str = "generic"
    flavor_text: str = ""


# =============================================================================
# CORE FEATURES (Genre-Agnostic Base Definitions)
# =============================================================================

# These are the mechanical "souls" of features. Genre translations overlay these.

CORE_FEATURES: Dict[str, FeatureData] = {
    # -------------------------------------------------------------------------
    # FIGHTER FEATURES
    # -------------------------------------------------------------------------
    "second_wind": FeatureData(
        id="second_wind",
        display_name="Second Wind",
        description="You have a limited well of stamina that you can draw on to protect yourself from harm. On your turn, you can use a bonus action to regain hit points equal to 1d10 + your level.",
        use_type=UseType.PER_SHORT_REST,
        uses_per_rest=1,
        action_type="bonus_action",
        effect_type=EffectType.HEALING,
        bonus_dice="1d10",
        target="self",
        level_gained=1,
    ),
    "action_surge": FeatureData(
        id="action_surge",
        display_name="Action Surge",
        description="You can push yourself beyond your normal limits for a moment. On your turn, you can take one additional action.",
        use_type=UseType.PER_SHORT_REST,
        uses_per_rest=1,
        action_type="none",  # Grants an action, doesn't cost one
        effect_type=EffectType.ACTION,
        target="self",
        level_gained=2,
        scales_at_level={17: {"uses_per_rest": 2}},
    ),
    "extra_attack": FeatureData(
        id="extra_attack",
        display_name="Extra Attack",
        description="You can attack twice, instead of once, whenever you take the Attack action on your turn.",
        use_type=UseType.PASSIVE,
        effect_type=EffectType.BUFF,
        level_gained=5,
        scales_at_level={11: {"attacks": 3}, 20: {"attacks": 4}},
    ),
    "indomitable": FeatureData(
        id="indomitable",
        display_name="Indomitable",
        description="You can reroll a saving throw that you fail. If you do so, you must use the new roll.",
        use_type=UseType.PER_LONG_REST,
        uses_per_rest=1,
        action_type="none",
        effect_type=EffectType.DEFENSE,
        level_gained=9,
        scales_at_level={13: {"uses_per_rest": 2}, 17: {"uses_per_rest": 3}},
    ),

    # -------------------------------------------------------------------------
    # ROGUE FEATURES
    # -------------------------------------------------------------------------
    "sneak_attack": FeatureData(
        id="sneak_attack",
        display_name="Sneak Attack",
        description="Once per turn, you can deal extra damage to one creature you hit with an attack if you have advantage on the attack roll, or if another enemy of the target is within 5 feet of it.",
        use_type=UseType.PASSIVE,  # Once per turn, not resource-based
        effect_type=EffectType.DAMAGE,
        bonus_dice="1d6",
        bonus_to="damage",
        level_gained=1,
        scales_at_level={3: "2d6", 5: "3d6", 7: "4d6", 9: "5d6", 11: "6d6", 13: "7d6", 15: "8d6", 17: "9d6", 19: "10d6"},
    ),
    "cunning_action": FeatureData(
        id="cunning_action",
        display_name="Cunning Action",
        description="You can take a bonus action on each of your turns to Dash, Disengage, or Hide.",
        use_type=UseType.AT_WILL,
        action_type="bonus_action",
        effect_type=EffectType.MOVEMENT,
        level_gained=2,
    ),
    "uncanny_dodge": FeatureData(
        id="uncanny_dodge",
        display_name="Uncanny Dodge",
        description="When an attacker that you can see hits you with an attack, you can use your reaction to halve the attack's damage against you.",
        use_type=UseType.AT_WILL,
        action_type="reaction",
        trigger="when hit by an attack you can see",
        effect_type=EffectType.DEFENSE,
        level_gained=5,
    ),
    "evasion": FeatureData(
        id="evasion",
        display_name="Evasion",
        description="When you are subjected to an effect that allows you to make a Dexterity saving throw to take only half damage, you instead take no damage if you succeed, and half damage if you fail.",
        use_type=UseType.PASSIVE,
        effect_type=EffectType.DEFENSE,
        level_gained=7,
    ),

    # -------------------------------------------------------------------------
    # BARBARIAN FEATURES
    # -------------------------------------------------------------------------
    "rage": FeatureData(
        id="rage",
        display_name="Rage",
        description="In battle, you fight with primal ferocity. On your turn, you can enter a rage as a bonus action, gaining resistance to physical damage and bonus damage on strength attacks.",
        use_type=UseType.RESOURCE,
        resource_pool="rage",
        resource_cost=1,
        action_type="bonus_action",
        effect_type=EffectType.BUFF,
        bonus_flat=2,
        bonus_to="damage",
        duration="1 minute",
        level_gained=1,
        scales_at_level={9: {"bonus_flat": 3}, 16: {"bonus_flat": 4}},
    ),
    "unarmored_defense_barbarian": FeatureData(
        id="unarmored_defense_barbarian",
        display_name="Unarmored Defense",
        description="While not wearing armor, your AC equals 10 + your Dexterity modifier + your Constitution modifier.",
        use_type=UseType.PASSIVE,
        effect_type=EffectType.DEFENSE,
        level_gained=1,
    ),
    "reckless_attack": FeatureData(
        id="reckless_attack",
        display_name="Reckless Attack",
        description="You can throw aside all concern for defense to attack with fierce desperation. You gain advantage on attack rolls, but attacks against you have advantage until your next turn.",
        use_type=UseType.AT_WILL,
        action_type="none",  # Part of attack action
        effect_type=EffectType.BUFF,
        level_gained=2,
    ),
    "danger_sense": FeatureData(
        id="danger_sense",
        display_name="Danger Sense",
        description="You have advantage on Dexterity saving throws against effects that you can see, such as traps and spells.",
        use_type=UseType.PASSIVE,
        effect_type=EffectType.DEFENSE,
        level_gained=2,
    ),

    # -------------------------------------------------------------------------
    # MONK FEATURES
    # -------------------------------------------------------------------------
    "martial_arts": FeatureData(
        id="martial_arts",
        display_name="Martial Arts",
        description="Your practice of martial arts gives you mastery of combat styles that use unarmed strikes and monk weapons. You can use Dexterity for attacks and deal increased damage.",
        use_type=UseType.PASSIVE,
        effect_type=EffectType.BUFF,
        bonus_dice="1d4",
        level_gained=1,
        scales_at_level={5: "1d6", 11: "1d8", 17: "1d10"},
    ),
    "ki": FeatureData(
        id="ki",
        display_name="Ki",
        description="Your training allows you to harness the mystic energy of ki. You have a number of ki points equal to your level, which fuel various ki features.",
        use_type=UseType.PASSIVE,  # The pool itself is passive; features use it
        effect_type=EffectType.UTILITY,
        level_gained=2,
    ),
    "flurry_of_blows": FeatureData(
        id="flurry_of_blows",
        display_name="Flurry of Blows",
        description="Immediately after you take the Attack action, you can spend 1 ki point to make two unarmed strikes as a bonus action.",
        use_type=UseType.RESOURCE,
        resource_pool="ki",
        resource_cost=1,
        action_type="bonus_action",
        effect_type=EffectType.DAMAGE,
        level_gained=2,
    ),
    "patient_defense": FeatureData(
        id="patient_defense",
        display_name="Patient Defense",
        description="You can spend 1 ki point to take the Dodge action as a bonus action on your turn.",
        use_type=UseType.RESOURCE,
        resource_pool="ki",
        resource_cost=1,
        action_type="bonus_action",
        effect_type=EffectType.DEFENSE,
        level_gained=2,
    ),
    "step_of_the_wind": FeatureData(
        id="step_of_the_wind",
        display_name="Step of the Wind",
        description="You can spend 1 ki point to take the Disengage or Dash action as a bonus action, and your jump distance is doubled for the turn.",
        use_type=UseType.RESOURCE,
        resource_pool="ki",
        resource_cost=1,
        action_type="bonus_action",
        effect_type=EffectType.MOVEMENT,
        level_gained=2,
    ),
    "stunning_strike": FeatureData(
        id="stunning_strike",
        display_name="Stunning Strike",
        description="When you hit a creature with a melee weapon attack, you can spend 1 ki point to attempt a stunning strike. The target must succeed on a Constitution saving throw or be stunned.",
        use_type=UseType.RESOURCE,
        resource_pool="ki",
        resource_cost=1,
        action_type="none",  # Part of attack
        effect_type=EffectType.DEBUFF,
        level_gained=5,
    ),
    "unarmored_movement": FeatureData(
        id="unarmored_movement",
        display_name="Unarmored Movement",
        description="Your speed increases by 10 feet while you are not wearing armor or wielding a shield.",
        use_type=UseType.PASSIVE,
        effect_type=EffectType.MOVEMENT,
        bonus_flat=10,
        bonus_to="speed",
        level_gained=2,
        scales_at_level={6: 15, 10: 20, 14: 25, 18: 30},
    ),

    # -------------------------------------------------------------------------
    # BATTLEMASTER MANEUVERS (as features)
    # -------------------------------------------------------------------------
    "combat_superiority": FeatureData(
        id="combat_superiority",
        display_name="Combat Superiority",
        description="You have a set of superiority dice that fuel special combat maneuvers. You regain all expended superiority dice when you finish a short or long rest.",
        use_type=UseType.PASSIVE,
        effect_type=EffectType.UTILITY,
        level_gained=3,
        archetype_restriction=["battlemaster", "soldier", "solo", "gunslinger"],
    ),
    "maneuver_trip": FeatureData(
        id="maneuver_trip",
        display_name="Trip Attack",
        description="When you hit with a weapon attack, you can expend a superiority die to attempt to knock the target down, adding the die to damage and forcing a Strength save or fall prone.",
        use_type=UseType.RESOURCE,
        resource_pool="superiority",
        resource_cost=1,
        effect_type=EffectType.DEBUFF,
        bonus_dice="1d8",
        level_gained=3,
    ),
    "maneuver_riposte": FeatureData(
        id="maneuver_riposte",
        display_name="Riposte",
        description="When a creature misses you with a melee attack, you can use your reaction to make a melee attack against them, adding a superiority die to the damage.",
        use_type=UseType.RESOURCE,
        resource_pool="superiority",
        resource_cost=1,
        action_type="reaction",
        trigger="when a creature misses you with a melee attack",
        effect_type=EffectType.DAMAGE,
        bonus_dice="1d8",
        level_gained=3,
    ),
    "maneuver_precision": FeatureData(
        id="maneuver_precision",
        display_name="Precision Attack",
        description="When you make a weapon attack roll, you can expend a superiority die and add it to the roll, potentially turning a miss into a hit.",
        use_type=UseType.RESOURCE,
        resource_pool="superiority",
        resource_cost=1,
        effect_type=EffectType.BUFF,
        bonus_dice="1d8",
        bonus_to="attack",
        level_gained=3,
    ),
    "maneuver_disarm": FeatureData(
        id="maneuver_disarm",
        display_name="Disarming Attack",
        description="When you hit with a weapon attack, you can expend a superiority die to attempt to disarm the target, adding the die to damage and forcing them to drop an item.",
        use_type=UseType.RESOURCE,
        resource_pool="superiority",
        resource_cost=1,
        effect_type=EffectType.DEBUFF,
        bonus_dice="1d8",
        level_gained=3,
    ),
    "maneuver_menacing": FeatureData(
        id="maneuver_menacing",
        display_name="Menacing Attack",
        description="When you hit with a weapon attack, you can expend a superiority die to frighten the target, adding the die to damage.",
        use_type=UseType.RESOURCE,
        resource_pool="superiority",
        resource_cost=1,
        effect_type=EffectType.DEBUFF,
        bonus_dice="1d8",
        level_gained=3,
    ),
}


# =============================================================================
# GENRE FEATURE TRANSLATIONS
# =============================================================================

# Maps core feature IDs to genre-specific display names and flavor
FEATURE_TRANSLATIONS: Dict[str, Dict[str, Dict[str, str]]] = {
    "second_wind": {
        "fantasy": {"name": "Second Wind", "flavor": "You draw on your inner reserves of stamina."},
        "modern": {"name": "Catch Your Breath", "flavor": "Training kicks in as you push through the pain."},
        "cyberpunk": {"name": "Stim Injection", "flavor": "Your biomonitor triggers an emergency stim release."},
        "postapoc": {"name": "Dig Deep", "flavor": "You've survived worse. You'll survive this."},
        "horror": {"name": "Survival Instinct", "flavor": "Fear becomes fuel as your body refuses to quit."},
        "wuxia": {"name": "Breath of Recovery", "flavor": "You center your chi and let it mend your wounds."},
        "western": {"name": "Grit Your Teeth", "flavor": "You spit blood and keep fighting."},
        "noir": {"name": "Tough It Out", "flavor": "You've taken worse beatings than this."},
        "scifi": {"name": "Emergency Protocols", "flavor": "Your suit's medical systems activate."},
        "steampunk": {"name": "Stiff Upper Lip", "flavor": "A true gentleman never shows weakness."},
    },
    "action_surge": {
        "fantasy": {"name": "Action Surge", "flavor": "You push beyond your limits."},
        "modern": {"name": "Adrenaline Rush", "flavor": "Time seems to slow as you move."},
        "cyberpunk": {"name": "Sandevistan", "flavor": "Your reflex boosters overclock."},
        "postapoc": {"name": "Survival Rush", "flavor": "Your body remembers what it takes to live."},
        "horror": {"name": "Fight or Flight", "flavor": "Terror fuels impossible speed."},
        "wuxia": {"name": "Burst of Speed", "flavor": "Your chi explodes into action."},
        "western": {"name": "Quick Draw", "flavor": "Fastest in the West."},
        "noir": {"name": "Desperate Measure", "flavor": "When you've got nothing to lose."},
        "scifi": {"name": "Combat Override", "flavor": "Safety limiters disengaged."},
        "steampunk": {"name": "Full Steam Ahead", "flavor": "You release the pressure valves."},
    },
    "sneak_attack": {
        "fantasy": {"name": "Sneak Attack", "flavor": "You strike where it hurts most."},
        "modern": {"name": "Precision Strike", "flavor": "Training taught you exactly where to hit."},
        "cyberpunk": {"name": "Exploit Weakness", "flavor": "Your optics highlight vulnerable points."},
        "postapoc": {"name": "Scavenger's Strike", "flavor": "Years of survival taught you anatomy."},
        "horror": {"name": "Killing Blow", "flavor": "You know where monsters are vulnerable."},
        "wuxia": {"name": "Vital Point Strike", "flavor": "You target the meridian points."},
        "western": {"name": "Bushwhack", "flavor": "Ain't no fair fights out here."},
        "noir": {"name": "Sucker Punch", "flavor": "They never see it coming."},
        "scifi": {"name": "Targeted Strike", "flavor": "Weak point identified and exploited."},
        "steampunk": {"name": "Calculated Strike", "flavor": "Precision is everything."},
    },
    "rage": {
        "fantasy": {"name": "Rage", "flavor": "Primal fury consumes you."},
        "modern": {"name": "Combat Trance", "flavor": "Training takes over completely."},
        "cyberpunk": {"name": "Berserker Mode", "flavor": "Combat wetware overrides pain receptors."},
        "postapoc": {"name": "Survivor's Fury", "flavor": "The wasteland made you this way."},
        "horror": {"name": "Blood Rage", "flavor": "Something primal awakens within."},
        "wuxia": {"name": "Iron Body", "flavor": "Your chi hardens your body like steel."},
        "western": {"name": "Seeing Red", "flavor": "You don't feel the bullets anymore."},
        "noir": {"name": "Snap", "flavor": "Something inside breaks loose."},
        "scifi": {"name": "Combat Stimulant", "flavor": "Chemical override engaged."},
        "steampunk": {"name": "Steam-Powered Fury", "flavor": "Your augments pulse with power."},
    },
    "cunning_action": {
        "fantasy": {"name": "Cunning Action", "flavor": "Your quick thinking keeps you alive."},
        "modern": {"name": "Quick Reflexes", "flavor": "You move before they can react."},
        "cyberpunk": {"name": "Street Instincts", "flavor": "The streets taught you to move."},
        "postapoc": {"name": "Wasteland Agility", "flavor": "You didn't survive by standing still."},
        "horror": {"name": "Flight Response", "flavor": "Fear makes you fast."},
        "wuxia": {"name": "Lightfoot", "flavor": "Your movement flows like water."},
        "western": {"name": "Slippery", "flavor": "Hard to pin down."},
        "noir": {"name": "Street Smart", "flavor": "You know every exit."},
        "scifi": {"name": "Evasive Protocols", "flavor": "Threat assessment: relocate."},
        "steampunk": {"name": "Nimble", "flavor": "Graceful despite the circumstances."},
    },
    "flurry_of_blows": {
        "fantasy": {"name": "Flurry of Blows", "flavor": "A rapid series of strikes."},
        "modern": {"name": "Rapid Strikes", "flavor": "Combo training pays off."},
        "cyberpunk": {"name": "Mantis Flurry", "flavor": "Cyber-enhanced speed."},
        "postapoc": {"name": "Desperate Assault", "flavor": "Every hit counts."},
        "horror": {"name": "Frantic Blows", "flavor": "You strike again and again."},
        "wuxia": {"name": "Hundred Fists", "flavor": "Your hands become a blur."},
        "western": {"name": "Fan the Hammer", "flavor": "Rapid fire technique."},
        "noir": {"name": "Working Over", "flavor": "You don't let up."},
        "scifi": {"name": "Combat Burst", "flavor": "Accelerated attack pattern."},
        "steampunk": {"name": "Piston Strikes", "flavor": "Steam-assisted speed."},
    },
    "stunning_strike": {
        "fantasy": {"name": "Stunning Strike", "flavor": "Your ki disrupts their body."},
        "modern": {"name": "Nerve Strike", "flavor": "You hit a pressure point."},
        "cyberpunk": {"name": "Neural Disruptor", "flavor": "You short-circuit their nervous system."},
        "postapoc": {"name": "Stunning Blow", "flavor": "A strike to stun, not kill."},
        "horror": {"name": "Paralyzing Touch", "flavor": "They freeze in terror."},
        "wuxia": {"name": "Dim Mak", "flavor": "The death touch technique."},
        "western": {"name": "Rattlesnake Strike", "flavor": "Fast and paralyzing."},
        "noir": {"name": "Blackjack", "flavor": "Lights out."},
        "scifi": {"name": "Disruption Strike", "flavor": "Neural pathway interrupted."},
        "steampunk": {"name": "Shock Gauntlet", "flavor": "Electrical discharge stuns."},
    },
}


# =============================================================================
# FEATURE ACCESS FUNCTIONS
# =============================================================================

def get_feature(feature_id: str, genre: str = "fantasy") -> Optional[FeatureData]:
    """Get a feature with genre-appropriate translations applied."""
    base_feature = CORE_FEATURES.get(feature_id)
    if not base_feature:
        return None

    # Create a copy with genre translations
    feature_dict = base_feature.model_dump()

    # Apply genre translations if available
    translations = FEATURE_TRANSLATIONS.get(feature_id, {}).get(genre, {})
    if translations:
        feature_dict["display_name"] = translations.get("name", feature_dict["display_name"])
        feature_dict["flavor_text"] = translations.get("flavor", "")

    feature_dict["genre"] = genre
    return FeatureData(**feature_dict)


def get_features_for_archetype(
    archetype_id: str,
    level: int = 1,
    genre: str = "fantasy"
) -> List[FeatureData]:
    """
    Get all features available to an archetype at a given level.

    This checks archetype_restriction and level_gained to filter features.
    """
    features = []
    for feature_id, feature in CORE_FEATURES.items():
        # Check level requirement
        if feature.level_gained > level:
            continue

        # Check archetype restriction
        if feature.archetype_restriction and archetype_id not in feature.archetype_restriction:
            continue

        # Get genre-translated version
        translated = get_feature(feature_id, genre)
        if translated:
            features.append(translated)

    return features


def get_resource_pool(pool_id: str, genre: str = "fantasy") -> Optional[ResourcePoolData]:
    """Get a resource pool definition for a genre."""
    genre_pools = RESOURCE_POOLS_BY_GENRE.get(genre, RESOURCE_POOLS_BY_GENRE.get("fantasy", {}))
    return genre_pools.get(pool_id)


def get_all_resource_pools(genre: str = "fantasy") -> Dict[str, ResourcePoolData]:
    """Get all resource pools for a genre."""
    return RESOURCE_POOLS_BY_GENRE.get(genre, RESOURCE_POOLS_BY_GENRE.get("fantasy", {}))


def translate_resource_pool_name(pool_id: str, genre: str) -> str:
    """Get the display name for a resource pool in a specific genre."""
    pool = get_resource_pool(pool_id, genre)
    if pool:
        return pool.display_name

    # Fallback mappings for cross-genre translation
    mappings = {
        "ki": {"modern": "Focus", "cyberpunk": "RAM", "wuxia": "Chi", "postapoc": "Grit"},
        "rage": {"modern": "Adrenaline", "cyberpunk": "Chrome Strain", "postapoc": "Resolve"},
        "superiority": {"cyberpunk": "Combat Subroutines", "western": "Gunfighter Tricks"},
    }

    if pool_id in mappings and genre in mappings[pool_id]:
        return mappings[pool_id][genre]

    return pool_id.replace("_", " ").title()


# =============================================================================
# ARCHETYPE -> FEATURE MAPPINGS
# =============================================================================

# Maps archetype IDs to their features at each level.
# Format: {archetype_id: {level: [feature_ids]}}
# These are "universal" mappings - the features get translated per-genre.

ARCHETYPE_FEATURES: Dict[str, Dict[int, List[str]]] = {
    # -------------------------------------------------------------------------
    # FIGHTER-TYPE ARCHETYPES (combat specialists)
    # -------------------------------------------------------------------------
    "fighter": {
        1: ["second_wind"],
        2: ["action_surge"],
        5: ["extra_attack"],
        9: ["indomitable"],
    },
    "soldier": {  # Modern equivalent
        1: ["second_wind"],
        2: ["action_surge"],
        5: ["extra_attack"],
        9: ["indomitable"],
    },
    "solo": {  # Cyberpunk equivalent
        1: ["second_wind"],
        2: ["action_surge"],
        5: ["extra_attack"],
        9: ["indomitable"],
    },
    "warrior": {  # Generic combat type
        1: ["second_wind"],
        2: ["action_surge"],
        5: ["extra_attack"],
        9: ["indomitable"],
    },
    "gunslinger": {  # Western fighter
        1: ["second_wind"],
        2: ["action_surge"],
        5: ["extra_attack"],
        9: ["indomitable"],
    },
    "hunter": {  # Horror fighter
        1: ["second_wind"],
        2: ["action_surge"],
        5: ["extra_attack"],
        9: ["indomitable"],
    },

    # -------------------------------------------------------------------------
    # ROGUE-TYPE ARCHETYPES (skill specialists, sneaky)
    # -------------------------------------------------------------------------
    "rogue": {
        1: ["sneak_attack"],
        2: ["cunning_action"],
        5: ["uncanny_dodge"],
        7: ["evasion"],
    },
    "infiltrator": {  # Modern/Scifi equivalent
        1: ["sneak_attack"],
        2: ["cunning_action"],
        5: ["uncanny_dodge"],
        7: ["evasion"],
    },
    "detective": {  # Modern - uses some rogue features
        1: ["sneak_attack"],  # Precision Strike in modern
        2: ["cunning_action"],
        5: ["uncanny_dodge"],
    },
    "fixer": {  # Cyberpunk social rogue
        1: ["sneak_attack"],
        2: ["cunning_action"],
        5: ["uncanny_dodge"],
    },
    "thief": {  # Horror rogue
        1: ["sneak_attack"],
        2: ["cunning_action"],
        5: ["uncanny_dodge"],
        7: ["evasion"],
    },
    "outlaw": {  # Western rogue
        1: ["sneak_attack"],
        2: ["cunning_action"],
        5: ["uncanny_dodge"],
        7: ["evasion"],
    },

    # -------------------------------------------------------------------------
    # BARBARIAN-TYPE ARCHETYPES (rage/fury combat)
    # -------------------------------------------------------------------------
    "barbarian": {
        1: ["rage", "unarmored_defense_barbarian"],
        2: ["reckless_attack", "danger_sense"],
        5: ["extra_attack"],
    },
    "berserker": {  # Scifi/Horror equivalent
        1: ["rage", "unarmored_defense_barbarian"],
        2: ["reckless_attack", "danger_sense"],
        5: ["extra_attack"],
    },
    "bruiser": {  # Modern equivalent
        1: ["rage"],  # Combat Trance
        2: ["reckless_attack", "danger_sense"],
        5: ["extra_attack"],
    },
    "raider": {  # Post-apoc barbarian
        1: ["rage", "unarmored_defense_barbarian"],
        2: ["reckless_attack", "danger_sense"],
        5: ["extra_attack"],
    },

    # -------------------------------------------------------------------------
    # MONK-TYPE ARCHETYPES (martial arts, ki/focus)
    # -------------------------------------------------------------------------
    "monk": {
        1: ["martial_arts"],
        2: ["ki", "flurry_of_blows", "patient_defense", "step_of_the_wind", "unarmored_movement"],
        5: ["stunning_strike", "extra_attack"],
    },
    "martial_artist": {  # Modern equivalent
        1: ["martial_arts"],
        2: ["ki", "flurry_of_blows", "patient_defense", "step_of_the_wind", "unarmored_movement"],
        5: ["stunning_strike", "extra_attack"],
    },
    "operative": {  # Scifi equivalent
        1: ["martial_arts"],
        2: ["ki", "flurry_of_blows", "patient_defense", "step_of_the_wind", "unarmored_movement"],
        5: ["stunning_strike", "extra_attack"],
    },
    "wuxia_hero": {  # Wuxia martial artist
        1: ["martial_arts"],
        2: ["ki", "flurry_of_blows", "patient_defense", "step_of_the_wind", "unarmored_movement"],
        5: ["stunning_strike", "extra_attack"],
    },

    # -------------------------------------------------------------------------
    # BATTLEMASTER-TYPE ARCHETYPES (tactical combat, maneuvers)
    # -------------------------------------------------------------------------
    "battlemaster": {
        1: ["second_wind"],
        2: ["action_surge"],
        3: ["combat_superiority", "maneuver_trip", "maneuver_riposte", "maneuver_precision"],
        5: ["extra_attack"],
    },
    "tactician": {  # Modern battlemaster
        1: ["second_wind"],
        2: ["action_surge"],
        3: ["combat_superiority", "maneuver_trip", "maneuver_riposte", "maneuver_precision"],
        5: ["extra_attack"],
    },

    # -------------------------------------------------------------------------
    # TECH SPECIALISTS (use abilities, not features as much)
    # -------------------------------------------------------------------------
    "netrunner": {
        # Tech specialists rely more on abilities than features
        # But they get some utility features
        1: [],
        2: ["cunning_action"],  # Quick reflexes
    },
    "techie": {
        1: [],
        2: [],
    },
    "engineer": {
        1: [],
        2: [],
    },
    "doctor": {
        1: ["second_wind"],  # Self-treatment
        2: [],
    },
    "medic": {
        1: ["second_wind"],
        2: [],
    },
}


def get_features_for_archetype_at_level(
    archetype_id: str,
    level: int,
    genre: str = "fantasy"
) -> List[FeatureData]:
    """
    Get all features an archetype has at a given level.
    Returns features with genre-appropriate translations.
    """
    archetype_map = ARCHETYPE_FEATURES.get(archetype_id, {})
    feature_ids = []

    # Collect all features up to and including this level
    for lvl in range(1, level + 1):
        if lvl in archetype_map:
            feature_ids.extend(archetype_map[lvl])

    # Get translated features
    features = []
    for fid in feature_ids:
        feature = get_feature(fid, genre)
        if feature:
            features.append(feature)

    return features


def get_new_features_at_level(
    archetype_id: str,
    level: int,
    genre: str = "fantasy"
) -> List[FeatureData]:
    """
    Get features gained at exactly this level (not cumulative).
    Useful for level-up notifications.
    """
    archetype_map = ARCHETYPE_FEATURES.get(archetype_id, {})
    feature_ids = archetype_map.get(level, [])

    features = []
    for fid in feature_ids:
        feature = get_feature(fid, genre)
        if feature:
            features.append(feature)

    return features
