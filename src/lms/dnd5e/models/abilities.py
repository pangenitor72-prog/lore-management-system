"""
Ability/Power definitions for the d20 rules engine.

Abilities are special powers characters can use - spells in fantasy,
tech abilities in sci-fi, special skills in modern settings.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AbilityType(str, Enum):
    """Types of abilities."""
    CANTRIP = "cantrip"      # At-will powers
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"
    PASSIVE = "passive"      # Always-on abilities
    ENCOUNTER = "encounter"  # Once per encounter/short rest
    DAILY = "daily"          # Once per long rest


class TargetType(str, Enum):
    """Who/what can be targeted."""
    SELF = "self"
    SINGLE = "single"
    AREA = "area"
    CONE = "cone"
    LINE = "line"


class AbilityData(BaseModel):
    """
    Ability/power definition.

    Generic base class for spells, tech abilities, special skills, etc.
    """
    id: str
    display_name: str
    description: str
    ability_type: AbilityType
    power_cost: int = 0  # Spell slot level or resource cost
    range_feet: int = 0  # 0 = self/touch
    target_type: TargetType = TargetType.SINGLE
    damage_dice: Optional[str] = None  # e.g., "1d8", "2d6"
    damage_type: Optional[str] = None  # e.g., "fire", "psychic", "kinetic"
    healing_dice: Optional[str] = None  # For healing abilities
    save_ability: Optional[str] = None  # What save to make
    duration: str = "instant"  # "instant", "1 minute", "concentration"
    requires_concentration: bool = False

    # Scaling
    scales_with_level: bool = False
    scaling_dice: Optional[str] = None

    # For character creation
    archetypes: List[str] = Field(default_factory=list)  # Which archetypes can learn this

    # Genre metadata
    genre: str = "generic"
    flavor_text: str = ""


# =============================================================================
# FANTASY ABILITIES (D&D Spells)
# =============================================================================

FANTASY_ABILITIES: Dict[str, AbilityData] = {
    # Cantrips
    "fire_bolt": AbilityData(
        id="fire_bolt",
        display_name="Fire Bolt",
        description="Hurl a mote of fire at a creature or object within range.",
        ability_type=AbilityType.CANTRIP,
        range_feet=120,
        target_type=TargetType.SINGLE,
        damage_dice="1d10",
        damage_type="fire",
        scales_with_level=True,
        scaling_dice="1d10",
        archetypes=["wizard"],
        genre="fantasy",
        flavor_text="A bolt of flame streaks toward your target.",
    ),
    "sacred_flame": AbilityData(
        id="sacred_flame",
        display_name="Sacred Flame",
        description="Flame-like radiance descends on a creature you can see.",
        ability_type=AbilityType.CANTRIP,
        range_feet=60,
        target_type=TargetType.SINGLE,
        damage_dice="1d8",
        damage_type="radiant",
        save_ability="dexterity",
        scales_with_level=True,
        archetypes=["cleric"],
        genre="fantasy",
        flavor_text="Divine light burns the wicked.",
    ),
    "light": AbilityData(
        id="light",
        display_name="Light",
        description="Touch an object to make it shed bright light.",
        ability_type=AbilityType.CANTRIP,
        range_feet=0,
        target_type=TargetType.SINGLE,
        duration="1 hour",
        archetypes=["cleric", "wizard"],
        genre="fantasy",
        flavor_text="The object glows with magical illumination.",
    ),
    # Level 1 Spells
    "magic_missile": AbilityData(
        id="magic_missile",
        display_name="Magic Missile",
        description="Create three darts of magical force that automatically hit.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=120,
        target_type=TargetType.SINGLE,
        damage_dice="3d4+3",
        damage_type="force",
        archetypes=["wizard"],
        genre="fantasy",
        flavor_text="Darts of magical force unerringly strike their targets.",
    ),
    "cure_wounds": AbilityData(
        id="cure_wounds",
        display_name="Cure Wounds",
        description="Touch a creature to restore hit points.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=0,
        target_type=TargetType.SINGLE,
        healing_dice="1d8",
        archetypes=["cleric"],
        genre="fantasy",
        flavor_text="Divine energy flows into the wounded creature.",
    ),
    "shield_of_faith": AbilityData(
        id="shield_of_faith",
        display_name="Shield of Faith",
        description="A shimmering field grants +2 AC to a creature.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=60,
        target_type=TargetType.SINGLE,
        duration="10 minutes",
        requires_concentration=True,
        archetypes=["cleric"],
        genre="fantasy",
        flavor_text="A protective shimmer surrounds the target.",
    ),
}


# =============================================================================
# SCI-FI ABILITIES (Tech Powers)
# =============================================================================

SCIFI_ABILITIES: Dict[str, AbilityData] = {
    # At-will tech
    "energy_bolt": AbilityData(
        id="energy_bolt",
        display_name="Energy Bolt",
        description="Fire a concentrated energy beam from your neural interface.",
        ability_type=AbilityType.CANTRIP,
        range_feet=100,
        target_type=TargetType.SINGLE,
        damage_dice="1d10",
        damage_type="energy",
        scales_with_level=True,
        archetypes=["hacker"],
        genre="scifi",
        flavor_text="Your cybernetics discharge a focused energy beam.",
    ),
    "scan": AbilityData(
        id="scan",
        display_name="Scan",
        description="Analyze a target to reveal its systems and weaknesses.",
        ability_type=AbilityType.CANTRIP,
        range_feet=60,
        target_type=TargetType.SINGLE,
        duration="instant",
        archetypes=["hacker", "medic"],
        genre="scifi",
        flavor_text="Your HUD highlights tactical information.",
    ),
    # Level 1 tech
    "system_shock": AbilityData(
        id="system_shock",
        display_name="System Shock",
        description="Overload a target's electronics with a neural spike.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=60,
        target_type=TargetType.SINGLE,
        damage_dice="3d4+3",
        damage_type="electric",
        archetypes=["hacker"],
        genre="scifi",
        flavor_text="Systems overload in a cascade of sparks.",
    ),
    "medpac": AbilityData(
        id="medpac",
        display_name="MedPac Injection",
        description="Administer emergency medical treatment to restore health.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=0,
        target_type=TargetType.SINGLE,
        healing_dice="1d8",
        archetypes=["medic"],
        genre="scifi",
        flavor_text="Nanobots begin repairing damaged tissue.",
    ),
    "shield_boost": AbilityData(
        id="shield_boost",
        display_name="Shield Boost",
        description="Temporarily enhance a target's personal shield.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=30,
        target_type=TargetType.SINGLE,
        duration="10 minutes",
        requires_concentration=True,
        archetypes=["medic", "hacker"],
        genre="scifi",
        flavor_text="Shield harmonics amplified.",
    ),
}


# =============================================================================
# MODERN/HORROR ABILITIES (Special Skills)
# =============================================================================

MODERN_ABILITIES: Dict[str, AbilityData] = {
    # Passive/at-will
    "keen_eye": AbilityData(
        id="keen_eye",
        display_name="Keen Eye",
        description="Your trained eye catches details others miss.",
        ability_type=AbilityType.PASSIVE,
        archetypes=["detective"],
        genre="modern",
        flavor_text="You notice what others overlook.",
    ),
    "first_aid": AbilityData(
        id="first_aid",
        display_name="First Aid",
        description="Apply emergency medical care to stabilize wounds.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=0,
        target_type=TargetType.SINGLE,
        healing_dice="1d6",
        archetypes=["doctor", "soldier"],
        genre="modern",
        flavor_text="You apply pressure and bandages quickly.",
    ),
    # Limited use
    "adrenaline_surge": AbilityData(
        id="adrenaline_surge",
        display_name="Adrenaline Surge",
        description="Push through pain and exhaustion for a burst of action.",
        ability_type=AbilityType.DAILY,
        power_cost=1,
        target_type=TargetType.SELF,
        duration="1 round",
        archetypes=["soldier"],
        genre="modern",
        flavor_text="Your heart pounds as everything sharpens.",
    ),
    "analyze_evidence": AbilityData(
        id="analyze_evidence",
        display_name="Analyze Evidence",
        description="Carefully examine evidence to reveal hidden information.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        target_type=TargetType.SINGLE,
        archetypes=["detective", "doctor"],
        genre="modern",
        flavor_text="The pieces start to come together.",
    ),
    "tactical_assessment": AbilityData(
        id="tactical_assessment",
        display_name="Tactical Assessment",
        description="Quickly analyze a combat situation to identify threats and opportunities.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        target_type=TargetType.SELF,
        archetypes=["soldier", "detective"],
        genre="modern",
        flavor_text="Training kicks in as you assess the battlefield.",
    ),
    "suppressing_fire": AbilityData(
        id="suppressing_fire",
        display_name="Suppressing Fire",
        description="Lay down a barrage of fire to force enemies into cover.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=60,
        target_type=TargetType.AREA,
        archetypes=["soldier"],
        genre="modern",
        flavor_text="Bullets crack overhead, forcing them down.",
    ),
}


# =============================================================================
# CYBERPUNK ABILITIES (Programs & Chrome)
# =============================================================================

CYBERPUNK_ABILITIES: Dict[str, AbilityData] = {
    # At-will programs
    "ping": AbilityData(
        id="ping",
        display_name="Ping",
        description="Scan the local network to reveal connected devices and their locations.",
        ability_type=AbilityType.CANTRIP,
        range_feet=100,
        target_type=TargetType.AREA,
        duration="instant",
        archetypes=["netrunner"],
        genre="cyberpunk",
        flavor_text="Network topology floods your vision.",
    ),
    "short_circuit": AbilityData(
        id="short_circuit",
        display_name="Short Circuit",
        description="Overload a target's cyberware with a quick hack, dealing electric damage.",
        ability_type=AbilityType.CANTRIP,
        range_feet=60,
        target_type=TargetType.SINGLE,
        damage_dice="1d8",
        damage_type="electric",
        scales_with_level=True,
        archetypes=["netrunner"],
        genre="cyberpunk",
        flavor_text="Sparks fly from their chrome.",
    ),
    # Level 1 programs
    "contagion": AbilityData(
        id="contagion",
        display_name="Contagion",
        description="Upload a spreading virus that jumps between connected enemies.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=60,
        target_type=TargetType.SINGLE,
        damage_dice="2d6",
        damage_type="electric",
        archetypes=["netrunner"],
        genre="cyberpunk",
        flavor_text="The virus spreads through the network.",
    ),
    "cyberware_malfunction": AbilityData(
        id="cyberware_malfunction",
        display_name="Cyberware Malfunction",
        description="Cause a target's cyberware to glitch, imposing disadvantage on their actions.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=60,
        target_type=TargetType.SINGLE,
        duration="1 minute",
        requires_concentration=True,
        save_ability="constitution",
        archetypes=["netrunner"],
        genre="cyberpunk",
        flavor_text="Their optics flicker and arms twitch.",
    ),
    "memory_wipe": AbilityData(
        id="memory_wipe",
        display_name="Memory Wipe",
        description="Erase the last few seconds from a target's memory.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=30,
        target_type=TargetType.SINGLE,
        save_ability="wisdom",
        archetypes=["netrunner"],
        genre="cyberpunk",
        flavor_text="What were we talking about?",
    ),
    # Techie abilities
    "jury_rig": AbilityData(
        id="jury_rig",
        display_name="Jury Rig",
        description="Quickly repair a piece of equipment or cyberware for temporary function.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=0,
        target_type=TargetType.SINGLE,
        archetypes=["techie"],
        genre="cyberpunk",
        flavor_text="It's not pretty, but it'll work.",
    ),
    "overclock": AbilityData(
        id="overclock",
        display_name="Overclock",
        description="Push a device beyond its limits for enhanced performance.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=0,
        target_type=TargetType.SINGLE,
        duration="1 minute",
        archetypes=["techie", "netrunner"],
        genre="cyberpunk",
        flavor_text="Warning lights flash, but performance soars.",
    ),
    # Combat stims
    "stim_boost": AbilityData(
        id="stim_boost",
        display_name="Stim Boost",
        description="Inject combat stims for a burst of enhanced reflexes and speed.",
        ability_type=AbilityType.DAILY,
        power_cost=1,
        target_type=TargetType.SELF,
        duration="1 minute",
        archetypes=["solo", "fixer"],
        genre="cyberpunk",
        flavor_text="The world slows down around you.",
    ),
}


# =============================================================================
# POST-APOCALYPTIC ABILITIES (Survival Tricks)
# =============================================================================

POSTAPOC_ABILITIES: Dict[str, AbilityData] = {
    # At-will survival skills
    "scavenge": AbilityData(
        id="scavenge",
        display_name="Scavenge",
        description="Search an area for useful supplies, parts, or hidden caches.",
        ability_type=AbilityType.CANTRIP,
        target_type=TargetType.AREA,
        archetypes=["scavenger", "survivor", "raider"],
        genre="postapoc",
        flavor_text="Your trained eye spots what others miss.",
    ),
    "read_the_wastes": AbilityData(
        id="read_the_wastes",
        display_name="Read the Wastes",
        description="Analyze tracks, weather, and environmental signs to predict danger.",
        ability_type=AbilityType.CANTRIP,
        target_type=TargetType.SELF,
        archetypes=["survivor", "scout"],
        genre="postapoc",
        flavor_text="The wasteland speaks to those who listen.",
    ),
    # Encounter abilities
    "field_medicine": AbilityData(
        id="field_medicine",
        display_name="Field Medicine",
        description="Use scavenged supplies to treat wounds in the field.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=0,
        target_type=TargetType.SINGLE,
        healing_dice="1d8",
        archetypes=["survivor", "medic", "scavenger"],
        genre="postapoc",
        flavor_text="Duct tape and prayer - wasteland medicine.",
    ),
    "improvised_trap": AbilityData(
        id="improvised_trap",
        display_name="Improvised Trap",
        description="Quickly set up a trap using scavenged materials.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=30,
        target_type=TargetType.AREA,
        damage_dice="2d6",
        damage_type="piercing",
        archetypes=["scavenger", "raider"],
        genre="postapoc",
        flavor_text="Tripwires and broken glass do the job.",
    ),
    "intimidating_presence": AbilityData(
        id="intimidating_presence",
        display_name="Intimidating Presence",
        description="Your reputation and demeanor make enemies think twice.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=30,
        target_type=TargetType.SINGLE,
        save_ability="wisdom",
        archetypes=["raider", "warlord"],
        genre="postapoc",
        flavor_text="They've heard stories about you.",
    ),
    # Daily abilities
    "last_resort": AbilityData(
        id="last_resort",
        display_name="Last Resort",
        description="When reduced to 0 HP, make one final attack before going down.",
        ability_type=AbilityType.DAILY,
        power_cost=1,
        target_type=TargetType.SELF,
        archetypes=["raider", "survivor", "warlord"],
        genre="postapoc",
        flavor_text="If you're going down, you're taking them with you.",
    ),
}


# =============================================================================
# HORROR ABILITIES (Occult & Survival)
# =============================================================================

HORROR_ABILITIES: Dict[str, AbilityData] = {
    # Investigation abilities
    "sense_the_unnatural": AbilityData(
        id="sense_the_unnatural",
        display_name="Sense the Unnatural",
        description="You can feel when something supernatural is nearby.",
        ability_type=AbilityType.CANTRIP,
        range_feet=60,
        target_type=TargetType.SELF,
        archetypes=["occultist", "psychic", "hunter"],
        genre="horror",
        flavor_text="The hair on your neck stands up.",
    ),
    "commune_with_spirits": AbilityData(
        id="commune_with_spirits",
        display_name="Commune with Spirits",
        description="Attempt to contact and question spirits of the dead.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        target_type=TargetType.SELF,
        duration="10 minutes",
        archetypes=["occultist", "psychic"],
        genre="horror",
        flavor_text="The veil between worlds grows thin.",
    ),
    "ward_against_evil": AbilityData(
        id="ward_against_evil",
        display_name="Ward Against Evil",
        description="Create a protective barrier against supernatural entities.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=30,
        target_type=TargetType.AREA,
        duration="1 hour",
        archetypes=["occultist", "exorcist"],
        genre="horror",
        flavor_text="Salt circles and spoken prayers create a sanctuary.",
    ),
    # Hunter abilities
    "monster_lore": AbilityData(
        id="monster_lore",
        display_name="Monster Lore",
        description="Recall knowledge about a supernatural creature's weaknesses.",
        ability_type=AbilityType.PASSIVE,
        target_type=TargetType.SELF,
        archetypes=["hunter", "exorcist", "occultist"],
        genre="horror",
        flavor_text="You've read the old books.",
    ),
    "silver_tongue": AbilityData(
        id="silver_tongue",
        display_name="Silver Tongue",
        description="Speak words of power that harm supernatural entities.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=30,
        target_type=TargetType.SINGLE,
        damage_dice="2d6",
        damage_type="radiant",
        archetypes=["exorcist"],
        genre="horror",
        flavor_text="The power of faith compels them.",
    ),
    # Psychic abilities
    "psychic_flash": AbilityData(
        id="psychic_flash",
        display_name="Psychic Flash",
        description="Touch an object to receive visions of its history.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=0,
        target_type=TargetType.SINGLE,
        archetypes=["psychic"],
        genre="horror",
        flavor_text="Images flood your mind unbidden.",
    ),
    "premonition": AbilityData(
        id="premonition",
        display_name="Premonition",
        description="You receive a brief glimpse of imminent danger.",
        ability_type=AbilityType.DAILY,
        power_cost=1,
        target_type=TargetType.SELF,
        archetypes=["psychic", "occultist"],
        genre="horror",
        flavor_text="Something terrible is about to happen.",
    ),
}


# =============================================================================
# WESTERN ABILITIES (Tricks & Grit)
# =============================================================================

WESTERN_ABILITIES: Dict[str, AbilityData] = {
    # Gunslinger abilities
    "fan_the_hammer": AbilityData(
        id="fan_the_hammer",
        display_name="Fan the Hammer",
        description="Fire multiple shots in rapid succession by fanning your revolver's hammer.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=30,
        target_type=TargetType.SINGLE,
        damage_dice="3d8",
        damage_type="piercing",
        archetypes=["gunslinger", "outlaw"],
        genre="western",
        flavor_text="Six shots before they can blink.",
    ),
    "dead_eye": AbilityData(
        id="dead_eye",
        display_name="Dead Eye",
        description="Time slows as you line up the perfect shot.",
        ability_type=AbilityType.DAILY,
        power_cost=1,
        range_feet=120,
        target_type=TargetType.SINGLE,
        archetypes=["gunslinger", "bounty_hunter"],
        genre="western",
        flavor_text="One shot. One kill.",
    ),
    "trick_shot": AbilityData(
        id="trick_shot",
        display_name="Trick Shot",
        description="Perform an impossible shot - ricochet, shoot objects from hands, etc.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=60,
        target_type=TargetType.SINGLE,
        archetypes=["gunslinger"],
        genre="western",
        flavor_text="You've practiced this a thousand times.",
    ),
    # Survival abilities
    "frontier_medicine": AbilityData(
        id="frontier_medicine",
        display_name="Frontier Medicine",
        description="Treat wounds with whiskey and a steady hand.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=0,
        target_type=TargetType.SINGLE,
        healing_dice="1d8",
        archetypes=["doc", "preacher", "pioneer"],
        genre="western",
        flavor_text="Bite down on this. It's gonna hurt.",
    ),
    "read_the_trail": AbilityData(
        id="read_the_trail",
        display_name="Read the Trail",
        description="Track a creature or person across any terrain.",
        ability_type=AbilityType.CANTRIP,
        target_type=TargetType.SELF,
        archetypes=["bounty_hunter", "pioneer", "lawman"],
        genre="western",
        flavor_text="These tracks tell a story.",
    ),
    # Social abilities
    "poker_face": AbilityData(
        id="poker_face",
        display_name="Poker Face",
        description="Your expression reveals nothing of your true intentions.",
        ability_type=AbilityType.PASSIVE,
        target_type=TargetType.SELF,
        archetypes=["gambler", "con_artist", "outlaw"],
        genre="western",
        flavor_text="Nobody can read you.",
    ),
    "reputation": AbilityData(
        id="reputation",
        display_name="Reputation",
        description="Your name precedes you - for better or worse.",
        ability_type=AbilityType.PASSIVE,
        target_type=TargetType.SELF,
        archetypes=["gunslinger", "outlaw", "lawman"],
        genre="western",
        flavor_text="They've heard of you.",
    ),
}


# =============================================================================
# WUXIA ABILITIES (Chi Techniques)
# =============================================================================

WUXIA_ABILITIES: Dict[str, AbilityData] = {
    # At-will techniques
    "iron_palm": AbilityData(
        id="iron_palm",
        display_name="Iron Palm",
        description="Channel chi into your strike for devastating impact.",
        ability_type=AbilityType.CANTRIP,
        range_feet=0,
        target_type=TargetType.SINGLE,
        damage_dice="1d8",
        damage_type="force",
        scales_with_level=True,
        archetypes=["martial_master", "wanderer", "guardian"],
        genre="wuxia",
        flavor_text="Your palm strikes like iron.",
    ),
    "lightness_skill": AbilityData(
        id="lightness_skill",
        display_name="Lightness Skill",
        description="Move with supernatural grace, running across water or up walls briefly.",
        ability_type=AbilityType.CANTRIP,
        target_type=TargetType.SELF,
        duration="1 round",
        archetypes=["wanderer", "assassin", "martial_master"],
        genre="wuxia",
        flavor_text="You move like a leaf on the wind.",
    ),
    # Chi techniques
    "pressure_point_strike": AbilityData(
        id="pressure_point_strike",
        display_name="Pressure Point Strike",
        description="Strike specific meridian points to disable or harm.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=0,
        target_type=TargetType.SINGLE,
        save_ability="constitution",
        archetypes=["martial_master", "assassin"],
        genre="wuxia",
        flavor_text="You strike the forbidden points.",
    ),
    "chi_healing": AbilityData(
        id="chi_healing",
        display_name="Chi Healing",
        description="Channel your internal energy to heal wounds.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=0,
        target_type=TargetType.SINGLE,
        healing_dice="2d8",
        archetypes=["healer", "martial_master"],
        genre="wuxia",
        flavor_text="Chi flows from your hands into the wounded.",
    ),
    "tiger_crane_stance": AbilityData(
        id="tiger_crane_stance",
        display_name="Tiger Crane Stance",
        description="Enter a powerful combat stance that enhances attack and defense.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        target_type=TargetType.SELF,
        duration="1 minute",
        archetypes=["martial_master", "guardian"],
        genre="wuxia",
        flavor_text="Fierce as the tiger, graceful as the crane.",
    ),
    # Advanced techniques
    "breaking_the_sky": AbilityData(
        id="breaking_the_sky",
        display_name="Breaking the Sky Palm",
        description="Release a wave of chi force that strikes all enemies in an area.",
        ability_type=AbilityType.LEVEL_2,
        power_cost=2,
        range_feet=30,
        target_type=TargetType.CONE,
        damage_dice="4d6",
        damage_type="force",
        save_ability="dexterity",
        archetypes=["martial_master"],
        genre="wuxia",
        flavor_text="Chi erupts from your palm like a thunderclap.",
    ),
    "flying_sword": AbilityData(
        id="flying_sword",
        display_name="Flying Sword",
        description="Throw your weapon with chi guidance, controlling it at a distance.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=60,
        target_type=TargetType.SINGLE,
        damage_dice="2d8",
        damage_type="slashing",
        archetypes=["swordsman", "wanderer"],
        genre="wuxia",
        flavor_text="Your blade dances through the air.",
    ),
}


# =============================================================================
# NOIR ABILITIES (Street Smarts & Grit)
# =============================================================================

NOIR_ABILITIES: Dict[str, AbilityData] = {
    # Investigation
    "read_the_room": AbilityData(
        id="read_the_room",
        display_name="Read the Room",
        description="Quickly assess a social situation, identifying threats and opportunities.",
        ability_type=AbilityType.CANTRIP,
        target_type=TargetType.SELF,
        archetypes=["private_eye", "grifter", "reporter"],
        genre="noir",
        flavor_text="You've seen this setup before.",
    ),
    "shake_down": AbilityData(
        id="shake_down",
        display_name="Shake Down",
        description="Intimidate or persuade someone into giving you information.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=5,
        target_type=TargetType.SINGLE,
        save_ability="wisdom",
        archetypes=["private_eye", "enforcer"],
        genre="noir",
        flavor_text="Everyone talks eventually.",
    ),
    "follow_the_money": AbilityData(
        id="follow_the_money",
        display_name="Follow the Money",
        description="Trace financial connections to uncover hidden relationships.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        target_type=TargetType.SELF,
        archetypes=["private_eye", "reporter"],
        genre="noir",
        flavor_text="Money always leaves a trail.",
    ),
    # Combat
    "dirty_fighting": AbilityData(
        id="dirty_fighting",
        display_name="Dirty Fighting",
        description="Fight without honor - sand in the eyes, low blows, whatever works.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=5,
        target_type=TargetType.SINGLE,
        damage_dice="2d6",
        damage_type="bludgeoning",
        archetypes=["enforcer", "private_eye"],
        genre="noir",
        flavor_text="There's no such thing as a fair fight.",
    ),
    "take_a_beating": AbilityData(
        id="take_a_beating",
        display_name="Take a Beating",
        description="You can take punishment that would drop most people.",
        ability_type=AbilityType.DAILY,
        power_cost=1,
        target_type=TargetType.SELF,
        archetypes=["enforcer", "private_eye"],
        genre="noir",
        flavor_text="They hit hard. You hit back harder.",
    ),
    # Social
    "femme_fatale": AbilityData(
        id="femme_fatale",
        display_name="Deadly Charm",
        description="Use your allure to manipulate and distract.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        range_feet=30,
        target_type=TargetType.SINGLE,
        save_ability="wisdom",
        archetypes=["grifter", "socialite"],
        genre="noir",
        flavor_text="They never see you coming.",
    ),
    "connections": AbilityData(
        id="connections",
        display_name="Connections",
        description="You know people. People who know things.",
        ability_type=AbilityType.DAILY,
        power_cost=1,
        target_type=TargetType.SELF,
        archetypes=["private_eye", "reporter", "grifter"],
        genre="noir",
        flavor_text="I know a guy who knows a guy.",
    ),
}


# =============================================================================
# URBAN FANTASY ABILITIES (Hidden Magic)
# =============================================================================

URBAN_FANTASY_ABILITIES: Dict[str, AbilityData] = {
    # Street magic
    "glamour": AbilityData(
        id="glamour",
        display_name="Glamour",
        description="Weave a minor illusion to disguise yourself or an object.",
        ability_type=AbilityType.CANTRIP,
        range_feet=0,
        target_type=TargetType.SELF,
        duration="1 hour",
        archetypes=["changeling", "street_mage", "fae_touched"],
        genre="urban_fantasy",
        flavor_text="The mundane see what you want them to see.",
    ),
    "veil": AbilityData(
        id="veil",
        display_name="Veil",
        description="Bend light and attention around yourself to avoid notice.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        target_type=TargetType.SELF,
        duration="10 minutes",
        requires_concentration=True,
        archetypes=["street_mage", "changeling"],
        genre="urban_fantasy",
        flavor_text="You step into the spaces between notice.",
    ),
    "hex": AbilityData(
        id="hex",
        display_name="Hex",
        description="Curse a target with misfortune, causing their efforts to fail.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=60,
        target_type=TargetType.SINGLE,
        duration="1 hour",
        save_ability="charisma",
        archetypes=["street_mage", "witch"],
        genre="urban_fantasy",
        flavor_text="Bad luck follows them like a shadow.",
    ),
    # Supernatural senses
    "see_through_the_masquerade": AbilityData(
        id="see_through_the_masquerade",
        display_name="True Sight",
        description="Pierce illusions and see supernatural creatures for what they are.",
        ability_type=AbilityType.ENCOUNTER,
        power_cost=0,
        target_type=TargetType.SELF,
        duration="1 minute",
        archetypes=["street_mage", "hunter", "fae_touched"],
        genre="urban_fantasy",
        flavor_text="The masks fall away.",
    ),
    "sense_magic": AbilityData(
        id="sense_magic",
        display_name="Sense Magic",
        description="Detect magical emanations and identify their source.",
        ability_type=AbilityType.CANTRIP,
        range_feet=60,
        target_type=TargetType.SELF,
        archetypes=["street_mage", "witch", "hunter"],
        genre="urban_fantasy",
        flavor_text="You feel the tingle of power.",
    ),
    # Combat magic
    "force_bolt": AbilityData(
        id="force_bolt",
        display_name="Force Bolt",
        description="Hurl a bolt of raw magical force at a target.",
        ability_type=AbilityType.CANTRIP,
        range_feet=120,
        target_type=TargetType.SINGLE,
        damage_dice="1d10",
        damage_type="force",
        scales_with_level=True,
        archetypes=["street_mage", "witch"],
        genre="urban_fantasy",
        flavor_text="Magic crackles from your fingertips.",
    ),
    "protective_circle": AbilityData(
        id="protective_circle",
        display_name="Protective Circle",
        description="Draw a circle that blocks supernatural entities.",
        ability_type=AbilityType.LEVEL_1,
        power_cost=1,
        range_feet=0,
        target_type=TargetType.AREA,
        duration="1 hour",
        archetypes=["street_mage", "witch", "hunter"],
        genre="urban_fantasy",
        flavor_text="Salt, silver, and will form the barrier.",
    ),
}


# =============================================================================
# ABILITY REGISTRY
# =============================================================================

ABILITIES_BY_GENRE: Dict[str, Dict[str, AbilityData]] = {
    "fantasy": FANTASY_ABILITIES,
    "scifi": SCIFI_ABILITIES,
    "modern": MODERN_ABILITIES,
    "cyberpunk": CYBERPUNK_ABILITIES,
    "postapoc": POSTAPOC_ABILITIES,
    "horror": HORROR_ABILITIES,
    "western": WESTERN_ABILITIES,
    "wuxia": WUXIA_ABILITIES,
    "noir": NOIR_ABILITIES,
    "urban_fantasy": URBAN_FANTASY_ABILITIES,
}


def get_ability(ability_id: str, genre: str = "fantasy") -> Optional[AbilityData]:
    """Get ability data by ID and genre."""
    genre_abilities = ABILITIES_BY_GENRE.get(genre, FANTASY_ABILITIES)
    return genre_abilities.get(ability_id)


def get_abilities_for_genre(genre: str = "fantasy") -> List[AbilityData]:
    """Get all available abilities for a genre."""
    genre_abilities = ABILITIES_BY_GENRE.get(genre, FANTASY_ABILITIES)
    return list(genre_abilities.values())


def get_abilities_for_archetype(archetype_id: str, genre: str = "fantasy") -> List[AbilityData]:
    """Get abilities available to a specific archetype."""
    genre_abilities = ABILITIES_BY_GENRE.get(genre, FANTASY_ABILITIES)
    return [
        ability for ability in genre_abilities.values()
        if archetype_id in ability.archetypes
    ]


def get_cantrips_for_archetype(archetype_id: str, genre: str = "fantasy") -> List[AbilityData]:
    """Get at-will abilities for an archetype."""
    return [
        ability for ability in get_abilities_for_archetype(archetype_id, genre)
        if ability.ability_type == AbilityType.CANTRIP
    ]


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

# Spell aliases for fantasy compatibility
Spell = AbilityData
SPELLS = FANTASY_ABILITIES


def get_spell(spell_id: str) -> Optional[AbilityData]:
    """Backward compatible: get spell by ID."""
    return FANTASY_ABILITIES.get(spell_id)


def get_all_spells() -> List[AbilityData]:
    """Backward compatible: get all fantasy spells."""
    return list(FANTASY_ABILITIES.values())
