"""
Genre-Specific Arc Variants

Provides alternative narrative arc structures for different genres.
Each genre has its own phases, tension curves, beat templates, and transitions.

The default is HEROIC (Campbell's 12-stage Hero's Journey).
Genre-specific arcs provide more appropriate narrative guidance for:
- Horror: Descent into darkness
- Mystery: Investigation and revelation
- Heist: Planning and execution
- Romance: Emotional connection
- Survival: Endurance and community
- Western: Frontier justice
- Cyberpunk: System vs individual
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


class GenreArcType(str, Enum):
    """Arc structure variants for different genres."""
    HEROIC = "heroic"        # Campbell's 12-stage Hero's Journey (default)
    HORROR = "horror"        # Descent → Confrontation → Survival/Loss
    MYSTERY = "mystery"      # Setup → Investigation → Revelation
    HEIST = "heist"          # Assembly → Planning → Execution → Escape
    ROMANCE = "romance"      # Meeting → Tension → Crisis → Union
    SURVIVAL = "survival"    # Collapse → Scarcity → Community → Hope
    WESTERN = "western"      # Arrival → Conflict → Showdown → Departure
    CYBERPUNK = "cyberpunk"  # Awakening → Resistance → Confrontation → Change


# Map world genres to arc types (from 51 deployed seeds)
GENRE_TO_ARC: Dict[str, GenreArcType] = {
    # HEROIC - Campbell's Journey
    "fantasy": GenreArcType.HEROIC,
    "mythology": GenreArcType.HEROIC,
    "superhero": GenreArcType.HEROIC,
    "adventure": GenreArcType.HEROIC,
    "fairy_tale": GenreArcType.HEROIC,
    "wuxia": GenreArcType.HEROIC,
    "samurai": GenreArcType.HEROIC,
    "norse": GenreArcType.HEROIC,
    "mythic_india": GenreArcType.HEROIC,
    "historical": GenreArcType.HEROIC,
    "urban_fantasy": GenreArcType.HEROIC,
    "supernatural_80s": GenreArcType.HEROIC,

    # HORROR - Descent into Darkness
    "horror": GenreArcType.HORROR,
    "survival_horror": GenreArcType.HORROR,
    "folk_horror": GenreArcType.HORROR,
    "gothic": GenreArcType.HORROR,
    "dark_fantasy": GenreArcType.HORROR,
    "pirate_horror": GenreArcType.HORROR,
    "weird_western": GenreArcType.HORROR,
    "thornwood": GenreArcType.HORROR,

    # MYSTERY - Investigation Arc
    "mystery": GenreArcType.MYSTERY,
    "thriller": GenreArcType.MYSTERY,
    "noir": GenreArcType.MYSTERY,
    "scifi_noir": GenreArcType.MYSTERY,
    "historical_crime": GenreArcType.MYSTERY,
    "true_crime": GenreArcType.MYSTERY,
    "whitechapel": GenreArcType.MYSTERY,
    "superhero_noir": GenreArcType.MYSTERY,

    # HEIST - Planning & Execution
    "heist": GenreArcType.HEIST,
    "clockwork_spies": GenreArcType.HEIST,
    "modern_underworld": GenreArcType.HEIST,

    # ROMANCE - Emotional Connection
    "romance": GenreArcType.ROMANCE,
    "gothic_romance": GenreArcType.ROMANCE,
    "adventure_romance": GenreArcType.ROMANCE,
    "postapoc_romance": GenreArcType.ROMANCE,
    "drama": GenreArcType.ROMANCE,
    "modern": GenreArcType.ROMANCE,

    # SURVIVAL - Endurance Arc
    "postapoc": GenreArcType.SURVIVAL,
    "mundane_collapse": GenreArcType.SURVIVAL,
    "fallen_capes": GenreArcType.SURVIVAL,

    # WESTERN - Frontier Justice
    "western": GenreArcType.WESTERN,
    "space_western": GenreArcType.WESTERN,
    "pirate": GenreArcType.WESTERN,
    "steampunk": GenreArcType.WESTERN,
    "sky_pirate": GenreArcType.WESTERN,
    "political_fantasy": GenreArcType.WESTERN,

    # CYBERPUNK - System vs Individual
    "cyberpunk": GenreArcType.CYBERPUNK,
    "scifi": GenreArcType.CYBERPUNK,
    "solarpunk": GenreArcType.CYBERPUNK,
    "afrofuturism": GenreArcType.CYBERPUNK,
    "cyberpunk_wuxia": GenreArcType.CYBERPUNK,
}


@dataclass
class GenrePhase:
    """A phase in a genre-specific arc."""
    id: str
    name: str
    description: str
    expected_tension: float
    act: str  # "setup", "confrontation", "resolution"
    phase_index: int

    @property
    def value(self) -> str:
        """Compatibility with StoryPhase.value."""
        return self.id


# Phase definitions for each genre arc
GENRE_ARC_PHASES: Dict[GenreArcType, List[GenrePhase]] = {
    GenreArcType.HORROR: [
        GenrePhase("normalcy", "Normalcy", "Ordinary life with creeping unease", 0.15, "setup", 0),
        GenrePhase("intrusion", "Intrusion", "Something wrong enters the world", 0.35, "setup", 1),
        GenrePhase("investigation", "Investigation", "Seeking answers makes things worse", 0.50, "confrontation", 2),
        GenrePhase("descent", "Descent", "Reality unravels, escape seems impossible", 0.70, "confrontation", 3),
        GenrePhase("confrontation", "Confrontation", "Face the horror directly", 0.90, "confrontation", 4),
        GenrePhase("cost", "Cost", "Victory demands sacrifice", 0.75, "resolution", 5),
        GenrePhase("survival", "Survival", "Escape, but changed forever", 0.40, "resolution", 6),
        GenrePhase("aftermath", "Aftermath", "Living with what was learned", 0.30, "resolution", 7),
    ],
    GenreArcType.MYSTERY: [
        GenrePhase("crime", "Crime", "The inciting incident that demands answers", 0.40, "setup", 0),
        GenrePhase("scene", "Scene", "Gathering initial evidence and witnesses", 0.35, "setup", 1),
        GenrePhase("suspects", "Suspects", "Multiple theories emerge", 0.50, "confrontation", 2),
        GenrePhase("complications", "Complications", "False leads, new crimes, danger", 0.60, "confrontation", 3),
        GenrePhase("breakthrough", "Breakthrough", "Key evidence or confession obtained", 0.70, "confrontation", 4),
        GenrePhase("confrontation", "Confrontation", "Face the guilty party", 0.80, "resolution", 5),
        GenrePhase("resolution", "Resolution", "Justice served, loose ends tied", 0.25, "resolution", 6),
    ],
    GenreArcType.HEIST: [
        GenrePhase("opportunity", "Opportunity", "The score is identified", 0.30, "setup", 0),
        GenrePhase("assembly", "Assembly", "Recruiting the crew", 0.35, "setup", 1),
        GenrePhase("planning", "Planning", "Casing the target, building the plan", 0.45, "setup", 2),
        GenrePhase("preparation", "Preparation", "Acquiring tools, rehearsing", 0.55, "confrontation", 3),
        GenrePhase("execution", "Execution", "The heist itself", 0.85, "confrontation", 4),
        GenrePhase("complication", "Complication", "Something goes wrong", 0.95, "confrontation", 5),
        GenrePhase("escape", "Escape", "Getting out with the prize", 0.75, "resolution", 6),
        GenrePhase("aftermath", "Aftermath", "Splitting the take, consequences", 0.35, "resolution", 7),
    ],
    GenreArcType.ROMANCE: [
        GenrePhase("meeting", "Meeting", "First encounter, spark of connection", 0.30, "setup", 0),
        GenrePhase("attraction", "Attraction", "Growing feelings, obstacles appear", 0.45, "setup", 1),
        GenrePhase("deepening", "Deepening", "Vulnerability shared, trust built", 0.55, "confrontation", 2),
        GenrePhase("crisis", "Crisis", "Misunderstanding or external threat", 0.80, "confrontation", 3),
        GenrePhase("separation", "Separation", "Apparent loss of the relationship", 0.70, "confrontation", 4),
        GenrePhase("reconciliation", "Reconciliation", "Realizing what matters", 0.60, "resolution", 5),
        GenrePhase("union", "Union", "Commitment, happily ever after", 0.25, "resolution", 6),
    ],
    GenreArcType.SURVIVAL: [
        GenrePhase("collapse", "Collapse", "The world falls apart", 0.60, "setup", 0),
        GenrePhase("scarcity", "Scarcity", "Resources dwindle, desperation grows", 0.70, "setup", 1),
        GenrePhase("conflict", "Conflict", "Competition turns violent", 0.80, "confrontation", 2),
        GenrePhase("community", "Community", "Finding or building a group", 0.55, "confrontation", 3),
        GenrePhase("threat", "Threat", "External danger to the group", 0.90, "confrontation", 4),
        GenrePhase("hope", "Hope", "Glimpse of a sustainable future", 0.40, "resolution", 5),
    ],
    GenreArcType.WESTERN: [
        GenrePhase("arrival", "Arrival", "Stranger comes to town", 0.30, "setup", 0),
        GenrePhase("discovery", "Discovery", "Learning the lay of the land", 0.45, "setup", 1),
        GenrePhase("escalation", "Escalation", "Conflict builds toward violence", 0.65, "confrontation", 2),
        GenrePhase("showdown", "Showdown", "The climactic confrontation", 0.90, "confrontation", 3),
        GenrePhase("aftermath", "Aftermath", "Consequences of the showdown", 0.50, "resolution", 4),
        GenrePhase("departure", "Departure", "Riding off into the sunset", 0.25, "resolution", 5),
    ],
    GenreArcType.CYBERPUNK: [
        GenrePhase("awakening", "Awakening", "Seeing the system's true nature", 0.35, "setup", 0),
        GenrePhase("contact", "Contact", "Finding others who resist", 0.45, "setup", 1),
        GenrePhase("mission", "Mission", "First strike against the system", 0.60, "confrontation", 2),
        GenrePhase("escalation", "Escalation", "The system strikes back", 0.75, "confrontation", 3),
        GenrePhase("sacrifice", "Sacrifice", "What must be given up", 0.85, "confrontation", 4),
        GenrePhase("confrontation", "Confrontation", "Facing the heart of power", 0.95, "resolution", 5),
        GenrePhase("change", "Change", "The world shifts, for better or worse", 0.40, "resolution", 6),
    ],
}


# Beat templates for each genre arc and phase
GENRE_BEAT_TEMPLATES: Dict[GenreArcType, Dict[str, List[Dict[str, Any]]]] = {
    GenreArcType.HORROR: {
        "normalcy": [
            {"type": "EXPOSITION", "template": "Establish routine with subtle wrongness beneath", "tension_target": 0.15, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "Show what the protagonist values and fears to lose", "tension_target": 0.20, "priority": 0.7},
            {"type": "DISCOVERY", "template": "Hint at something not quite right in the environment", "tension_target": 0.25, "priority": 0.6},
        ],
        "intrusion": [
            {"type": "REVELATION", "template": "Something impossible or terrifying manifests", "tension_target": 0.40, "priority": 0.9},
            {"type": "SETBACK", "template": "First attempt to rationalize or escape fails", "tension_target": 0.35, "priority": 0.8},
            {"type": "OBSTACLE", "template": "Normal solutions prove useless against the threat", "tension_target": 0.40, "priority": 0.7},
        ],
        "investigation": [
            {"type": "DISCOVERY", "template": "Uncover disturbing history or forbidden knowledge", "tension_target": 0.50, "priority": 0.8},
            {"type": "CONSEQUENCE", "template": "Knowledge comes at a psychological cost", "tension_target": 0.55, "priority": 0.7},
            {"type": "SOCIAL", "template": "Others dismiss warnings or are already compromised", "tension_target": 0.45, "priority": 0.6},
        ],
        "descent": [
            {"type": "SETBACK", "template": "Reality bends in impossible ways", "tension_target": 0.70, "priority": 0.9},
            {"type": "REVELATION", "template": "The true nature of the horror becomes clear", "tension_target": 0.75, "priority": 0.8},
            {"type": "OBSTACLE", "template": "Escape routes close one by one", "tension_target": 0.70, "priority": 0.7},
        ],
        "confrontation": [
            {"type": "COMBAT", "template": "Face the horror with whatever weapons remain", "tension_target": 0.90, "priority": 0.9},
            {"type": "CHOICE", "template": "Choose between survival and saving others", "tension_target": 0.95, "priority": 0.85},
            {"type": "REVELATION", "template": "Final truth about the horror or oneself", "tension_target": 0.85, "priority": 0.7},
        ],
        "cost": [
            {"type": "CONSEQUENCE", "template": "Victory extracts its terrible price", "tension_target": 0.75, "priority": 0.9},
            {"type": "SETBACK", "template": "Something precious is lost forever", "tension_target": 0.70, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "Process the trauma of what was faced", "tension_target": 0.65, "priority": 0.7},
        ],
        "survival": [
            {"type": "VICTORY", "template": "Escape or destroy the immediate threat", "tension_target": 0.45, "priority": 0.8},
            {"type": "REST", "template": "Brief respite to process survival", "tension_target": 0.35, "priority": 0.7},
            {"type": "REVELATION", "template": "Realize how the experience has changed you", "tension_target": 0.40, "priority": 0.6},
        ],
        "aftermath": [
            {"type": "CHARACTER_MOMENT", "template": "Attempt to return to normal life", "tension_target": 0.30, "priority": 0.8},
            {"type": "CLIFFHANGER", "template": "Hint that the horror may not be truly gone", "tension_target": 0.35, "priority": 0.7},
            {"type": "EXPOSITION", "template": "Show the lasting scars of the experience", "tension_target": 0.25, "priority": 0.6},
        ],
    },
    GenreArcType.MYSTERY: {
        "crime": [
            {"type": "REVELATION", "template": "The crime is discovered in shocking fashion", "tension_target": 0.45, "priority": 0.9},
            {"type": "EXPOSITION", "template": "Establish the stakes and why it matters", "tension_target": 0.35, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "The investigator commits to solving the case", "tension_target": 0.40, "priority": 0.7},
        ],
        "scene": [
            {"type": "DISCOVERY", "template": "Examine evidence and note anomalies", "tension_target": 0.35, "priority": 0.9},
            {"type": "SOCIAL", "template": "Interview witnesses with varying reliability", "tension_target": 0.35, "priority": 0.8},
            {"type": "PUZZLE", "template": "Piece together the timeline of events", "tension_target": 0.40, "priority": 0.7},
        ],
        "suspects": [
            {"type": "SOCIAL", "template": "Interrogate suspects, each with motive and alibi", "tension_target": 0.50, "priority": 0.9},
            {"type": "REVELATION", "template": "Uncover secrets that complicate the case", "tension_target": 0.55, "priority": 0.8},
            {"type": "OBSTACLE", "template": "Powerful interests obstruct the investigation", "tension_target": 0.50, "priority": 0.7},
        ],
        "complications": [
            {"type": "SETBACK", "template": "Prime suspect has an airtight alibi", "tension_target": 0.60, "priority": 0.8},
            {"type": "REVELATION", "template": "New crime connects to the first", "tension_target": 0.65, "priority": 0.9},
            {"type": "OBSTACLE", "template": "Investigator is threatened or compromised", "tension_target": 0.60, "priority": 0.7},
        ],
        "breakthrough": [
            {"type": "DISCOVERY", "template": "Key evidence points to the true culprit", "tension_target": 0.70, "priority": 0.9},
            {"type": "REVELATION", "template": "The motive finally becomes clear", "tension_target": 0.75, "priority": 0.85},
            {"type": "PUZZLE", "template": "All the pieces fall into place", "tension_target": 0.70, "priority": 0.7},
        ],
        "confrontation": [
            {"type": "SOCIAL", "template": "Confront the culprit with the evidence", "tension_target": 0.80, "priority": 0.9},
            {"type": "CHOICE", "template": "Decide between justice and mercy", "tension_target": 0.75, "priority": 0.8},
            {"type": "COMBAT", "template": "Culprit attempts desperate escape", "tension_target": 0.85, "priority": 0.7},
        ],
        "resolution": [
            {"type": "VICTORY", "template": "Justice is served in some form", "tension_target": 0.30, "priority": 0.9},
            {"type": "EXPOSITION", "template": "Loose ends are tied up", "tension_target": 0.25, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "Reflect on what the case revealed", "tension_target": 0.25, "priority": 0.7},
        ],
    },
    GenreArcType.HEIST: {
        "opportunity": [
            {"type": "REVELATION", "template": "The perfect score presents itself", "tension_target": 0.30, "priority": 0.9},
            {"type": "EXPOSITION", "template": "Establish what makes this target irresistible", "tension_target": 0.25, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "Why does the mastermind need this job?", "tension_target": 0.30, "priority": 0.7},
        ],
        "assembly": [
            {"type": "SOCIAL", "template": "Recruit a specialist with a unique skill", "tension_target": 0.35, "priority": 0.9},
            {"type": "CHARACTER_MOMENT", "template": "Old grudges or debts complicate recruitment", "tension_target": 0.40, "priority": 0.8},
            {"type": "EXPOSITION", "template": "Each crew member brings baggage", "tension_target": 0.35, "priority": 0.7},
        ],
        "planning": [
            {"type": "PUZZLE", "template": "Map the security and identify weaknesses", "tension_target": 0.45, "priority": 0.9},
            {"type": "DISCOVERY", "template": "Insider information reveals opportunity", "tension_target": 0.50, "priority": 0.8},
            {"type": "OBSTACLE", "template": "An unexpected security measure complicates plans", "tension_target": 0.50, "priority": 0.7},
        ],
        "preparation": [
            {"type": "EXPOSITION", "template": "Acquire specialized equipment", "tension_target": 0.55, "priority": 0.8},
            {"type": "SOCIAL", "template": "Rehearse roles and contingencies", "tension_target": 0.50, "priority": 0.7},
            {"type": "OBSTACLE", "template": "Last-minute complication requires adaptation", "tension_target": 0.60, "priority": 0.8},
        ],
        "execution": [
            {"type": "PUZZLE", "template": "Each phase of the plan unfolds", "tension_target": 0.85, "priority": 0.9},
            {"type": "OBSTACLE", "template": "Security is tighter than expected", "tension_target": 0.90, "priority": 0.85},
            {"type": "CHOICE", "template": "Improvise when the plan goes sideways", "tension_target": 0.85, "priority": 0.8},
        ],
        "complication": [
            {"type": "SETBACK", "template": "Everything that can go wrong does", "tension_target": 0.95, "priority": 0.95},
            {"type": "REVELATION", "template": "Betrayal or unexpected twist", "tension_target": 0.95, "priority": 0.9},
            {"type": "COMBAT", "template": "Confrontation becomes unavoidable", "tension_target": 0.90, "priority": 0.8},
        ],
        "escape": [
            {"type": "OBSTACLE", "template": "Race against pursuit or countdown", "tension_target": 0.75, "priority": 0.9},
            {"type": "CHOICE", "template": "Sacrifice something to get out clean", "tension_target": 0.70, "priority": 0.8},
            {"type": "VICTORY", "template": "Clean getaway with the prize", "tension_target": 0.60, "priority": 0.7},
        ],
        "aftermath": [
            {"type": "SOCIAL", "template": "Divide the spoils fairly or not", "tension_target": 0.40, "priority": 0.8},
            {"type": "CONSEQUENCE", "template": "Long-term implications of the job", "tension_target": 0.35, "priority": 0.7},
            {"type": "CHARACTER_MOMENT", "template": "What was it all really for?", "tension_target": 0.30, "priority": 0.6},
        ],
    },
    GenreArcType.ROMANCE: {
        "meeting": [
            {"type": "SOCIAL", "template": "First encounter creates unexpected spark", "tension_target": 0.30, "priority": 0.9},
            {"type": "CHARACTER_MOMENT", "template": "Initial impressions may be wrong", "tension_target": 0.25, "priority": 0.8},
            {"type": "EXPOSITION", "template": "Circumstances bring them together", "tension_target": 0.30, "priority": 0.7},
        ],
        "attraction": [
            {"type": "SOCIAL", "template": "Forced proximity reveals compatibility", "tension_target": 0.45, "priority": 0.9},
            {"type": "OBSTACLE", "template": "External circumstances keep them apart", "tension_target": 0.50, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "Denial of growing feelings", "tension_target": 0.40, "priority": 0.7},
        ],
        "deepening": [
            {"type": "REVELATION", "template": "Vulnerable moment creates intimacy", "tension_target": 0.55, "priority": 0.9},
            {"type": "SOCIAL", "template": "Trust is built through shared experience", "tension_target": 0.50, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "Acknowledge the depth of feeling", "tension_target": 0.55, "priority": 0.7},
        ],
        "crisis": [
            {"type": "SETBACK", "template": "Misunderstanding threatens everything", "tension_target": 0.80, "priority": 0.9},
            {"type": "REVELATION", "template": "Secret or past complicates the relationship", "tension_target": 0.85, "priority": 0.85},
            {"type": "OBSTACLE", "template": "External force drives them apart", "tension_target": 0.75, "priority": 0.8},
        ],
        "separation": [
            {"type": "CONSEQUENCE", "template": "Apart, both realize what they've lost", "tension_target": 0.70, "priority": 0.9},
            {"type": "CHARACTER_MOMENT", "template": "Growth that was needed for the relationship", "tension_target": 0.65, "priority": 0.8},
            {"type": "SETBACK", "template": "Attempts to move on fail", "tension_target": 0.70, "priority": 0.7},
        ],
        "reconciliation": [
            {"type": "CHOICE", "template": "Grand gesture or humble admission", "tension_target": 0.60, "priority": 0.9},
            {"type": "SOCIAL", "template": "Honest conversation resolves misunderstanding", "tension_target": 0.55, "priority": 0.8},
            {"type": "REVELATION", "template": "True feelings finally spoken", "tension_target": 0.60, "priority": 0.85},
        ],
        "union": [
            {"type": "VICTORY", "template": "Commitment to a shared future", "tension_target": 0.25, "priority": 0.9},
            {"type": "REST", "template": "Peaceful resolution of external conflicts", "tension_target": 0.20, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "Both transformed by love", "tension_target": 0.25, "priority": 0.7},
        ],
    },
    GenreArcType.SURVIVAL: {
        "collapse": [
            {"type": "REVELATION", "template": "The world as known ends catastrophically", "tension_target": 0.65, "priority": 0.9},
            {"type": "SETBACK", "template": "Everything familiar is lost", "tension_target": 0.60, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "Shock gives way to survival instinct", "tension_target": 0.55, "priority": 0.7},
        ],
        "scarcity": [
            {"type": "OBSTACLE", "template": "Essential resources run dangerously low", "tension_target": 0.70, "priority": 0.9},
            {"type": "CHOICE", "template": "Hard decisions about rationing", "tension_target": 0.75, "priority": 0.8},
            {"type": "DISCOVERY", "template": "Find a cache of supplies", "tension_target": 0.65, "priority": 0.7},
        ],
        "conflict": [
            {"type": "COMBAT", "template": "Others compete violently for resources", "tension_target": 0.85, "priority": 0.9},
            {"type": "SETBACK", "template": "Betrayal by someone trusted", "tension_target": 0.80, "priority": 0.8},
            {"type": "CHOICE", "template": "Mercy vs survival", "tension_target": 0.80, "priority": 0.7},
        ],
        "community": [
            {"type": "SOCIAL", "template": "Find or build a group of survivors", "tension_target": 0.55, "priority": 0.9},
            {"type": "CHARACTER_MOMENT", "template": "Establish roles and rules", "tension_target": 0.50, "priority": 0.8},
            {"type": "REST", "template": "Brief moment of normalcy", "tension_target": 0.45, "priority": 0.7},
        ],
        "threat": [
            {"type": "COMBAT", "template": "External force threatens the community", "tension_target": 0.90, "priority": 0.95},
            {"type": "CHOICE", "template": "Stand and fight or flee again", "tension_target": 0.85, "priority": 0.85},
            {"type": "SETBACK", "template": "Losses are suffered defending what matters", "tension_target": 0.90, "priority": 0.8},
        ],
        "hope": [
            {"type": "VICTORY", "template": "Threat is overcome through unity", "tension_target": 0.45, "priority": 0.9},
            {"type": "DISCOVERY", "template": "Path to sustainable future revealed", "tension_target": 0.40, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "What was preserved makes it worthwhile", "tension_target": 0.35, "priority": 0.7},
        ],
    },
    GenreArcType.WESTERN: {
        "arrival": [
            {"type": "EXPOSITION", "template": "Stranger rides into town with a past", "tension_target": 0.30, "priority": 0.9},
            {"type": "SOCIAL", "template": "Initial impressions cut both ways", "tension_target": 0.30, "priority": 0.8},
            {"type": "CHARACTER_MOMENT", "template": "Why is the stranger really here?", "tension_target": 0.35, "priority": 0.7},
        ],
        "discovery": [
            {"type": "DISCOVERY", "template": "Learn who holds power and who suffers", "tension_target": 0.45, "priority": 0.9},
            {"type": "SOCIAL", "template": "Form alliances and make enemies", "tension_target": 0.45, "priority": 0.8},
            {"type": "REVELATION", "template": "The town's dark secret emerges", "tension_target": 0.50, "priority": 0.7},
        ],
        "escalation": [
            {"type": "OBSTACLE", "template": "Intimidation and violence increase", "tension_target": 0.65, "priority": 0.9},
            {"type": "CHOICE", "template": "Get involved or stay out of it", "tension_target": 0.60, "priority": 0.8},
            {"type": "SETBACK", "template": "Someone innocent pays the price", "tension_target": 0.70, "priority": 0.7},
        ],
        "showdown": [
            {"type": "COMBAT", "template": "Face the villain in decisive confrontation", "tension_target": 0.95, "priority": 0.95},
            {"type": "CHOICE", "template": "Kill or show mercy", "tension_target": 0.90, "priority": 0.85},
            {"type": "REVELATION", "template": "Truth about the past comes out", "tension_target": 0.85, "priority": 0.7},
        ],
        "aftermath": [
            {"type": "CONSEQUENCE", "template": "The town deals with what happened", "tension_target": 0.50, "priority": 0.8},
            {"type": "SOCIAL", "template": "Gratitude or resentment from survivors", "tension_target": 0.45, "priority": 0.7},
            {"type": "CHARACTER_MOMENT", "template": "What justice actually looks like", "tension_target": 0.50, "priority": 0.6},
        ],
        "departure": [
            {"type": "CHARACTER_MOMENT", "template": "The stranger moves on", "tension_target": 0.25, "priority": 0.9},
            {"type": "REST", "template": "Peace settles over the town", "tension_target": 0.20, "priority": 0.8},
            {"type": "CLIFFHANGER", "template": "But the past isn't finished yet", "tension_target": 0.30, "priority": 0.6},
        ],
    },
    GenreArcType.CYBERPUNK: {
        "awakening": [
            {"type": "REVELATION", "template": "See the system's corruption clearly", "tension_target": 0.40, "priority": 0.9},
            {"type": "CHARACTER_MOMENT", "template": "Can't unsee what was revealed", "tension_target": 0.35, "priority": 0.8},
            {"type": "SETBACK", "template": "Old life becomes impossible", "tension_target": 0.40, "priority": 0.7},
        ],
        "contact": [
            {"type": "SOCIAL", "template": "Find others who fight the system", "tension_target": 0.45, "priority": 0.9},
            {"type": "DISCOVERY", "template": "Learn the resistance's methods", "tension_target": 0.45, "priority": 0.8},
            {"type": "OBSTACLE", "template": "Trust must be earned in dangerous times", "tension_target": 0.50, "priority": 0.7},
        ],
        "mission": [
            {"type": "PUZZLE", "template": "Plan a strike against corporate power", "tension_target": 0.60, "priority": 0.9},
            {"type": "COMBAT", "template": "Execute the operation", "tension_target": 0.70, "priority": 0.85},
            {"type": "VICTORY", "template": "First taste of fighting back", "tension_target": 0.55, "priority": 0.7},
        ],
        "escalation": [
            {"type": "SETBACK", "template": "The system's retaliation is overwhelming", "tension_target": 0.80, "priority": 0.9},
            {"type": "REVELATION", "template": "Learn how deep the corruption goes", "tension_target": 0.75, "priority": 0.85},
            {"type": "OBSTACLE", "template": "Resources and allies dwindle", "tension_target": 0.75, "priority": 0.7},
        ],
        "sacrifice": [
            {"type": "CHOICE", "template": "What must be given up to continue", "tension_target": 0.85, "priority": 0.9},
            {"type": "CONSEQUENCE", "template": "Someone pays the ultimate price", "tension_target": 0.90, "priority": 0.85},
            {"type": "CHARACTER_MOMENT", "template": "Question whether it's worth it", "tension_target": 0.80, "priority": 0.7},
        ],
        "confrontation": [
            {"type": "COMBAT", "template": "Strike at the heart of power", "tension_target": 0.95, "priority": 0.95},
            {"type": "REVELATION", "template": "The final truth is exposed", "tension_target": 0.95, "priority": 0.9},
            {"type": "CHOICE", "template": "Destroy the system or become it", "tension_target": 0.90, "priority": 0.85},
        ],
        "change": [
            {"type": "CONSEQUENCE", "template": "The world shifts in some way", "tension_target": 0.45, "priority": 0.9},
            {"type": "CHARACTER_MOMENT", "template": "Assess what was won and lost", "tension_target": 0.40, "priority": 0.8},
            {"type": "CLIFFHANGER", "template": "The fight continues in new form", "tension_target": 0.45, "priority": 0.7},
        ],
    },
}


# Valid phase transitions for each genre arc
GENRE_TRANSITIONS: Dict[GenreArcType, Dict[str, List[str]]] = {
    GenreArcType.HORROR: {
        "normalcy": ["intrusion"],
        "intrusion": ["investigation", "descent"],
        "investigation": ["descent", "intrusion"],  # Can loop back
        "descent": ["confrontation"],
        "confrontation": ["cost", "survival"],
        "cost": ["survival", "aftermath"],
        "survival": ["aftermath"],
        "aftermath": [],  # End state
    },
    GenreArcType.MYSTERY: {
        "crime": ["scene"],
        "scene": ["suspects"],
        "suspects": ["complications", "breakthrough"],
        "complications": ["suspects", "breakthrough"],  # Can loop back
        "breakthrough": ["confrontation"],
        "confrontation": ["resolution"],
        "resolution": [],  # End state
    },
    GenreArcType.HEIST: {
        "opportunity": ["assembly"],
        "assembly": ["planning"],
        "planning": ["preparation"],
        "preparation": ["execution"],
        "execution": ["complication", "escape"],
        "complication": ["escape"],
        "escape": ["aftermath"],
        "aftermath": [],  # End state
    },
    GenreArcType.ROMANCE: {
        "meeting": ["attraction"],
        "attraction": ["deepening", "crisis"],
        "deepening": ["crisis"],
        "crisis": ["separation"],
        "separation": ["reconciliation"],
        "reconciliation": ["union"],
        "union": [],  # End state
    },
    GenreArcType.SURVIVAL: {
        "collapse": ["scarcity"],
        "scarcity": ["conflict", "community"],
        "conflict": ["community", "scarcity"],  # Can loop
        "community": ["threat"],
        "threat": ["hope", "conflict"],  # Can loop back
        "hope": [],  # End state
    },
    GenreArcType.WESTERN: {
        "arrival": ["discovery"],
        "discovery": ["escalation"],
        "escalation": ["showdown"],
        "showdown": ["aftermath"],
        "aftermath": ["departure"],
        "departure": [],  # End state
    },
    GenreArcType.CYBERPUNK: {
        "awakening": ["contact"],
        "contact": ["mission"],
        "mission": ["escalation"],
        "escalation": ["sacrifice", "mission"],  # Can loop back
        "sacrifice": ["confrontation"],
        "confrontation": ["change"],
        "change": [],  # End state
    },
}


# Phase detection keywords for each genre arc
GENRE_PHASE_INDICATORS: Dict[GenreArcType, Dict[str, List[str]]] = {
    GenreArcType.HORROR: {
        "normalcy": ["routine", "ordinary", "normal day", "peaceful", "quiet life"],
        "intrusion": ["wrong", "strange", "impossible", "shouldn't be", "can't be real"],
        "investigation": ["research", "investigate", "library", "history", "forbidden"],
        "descent": ["madness", "losing grip", "no escape", "everywhere", "consumed"],
        "confrontation": ["face it", "final stand", "no choice", "must destroy"],
        "cost": ["sacrifice", "price", "lost forever", "gave up", "worth it"],
        "survival": ["escaped", "survived", "made it out", "still alive"],
        "aftermath": ["changed", "never the same", "haunted", "remember"],
    },
    GenreArcType.MYSTERY: {
        "crime": ["murder", "stolen", "missing", "crime scene", "victim"],
        "scene": ["evidence", "clue", "witness", "examine", "forensic"],
        "suspects": ["alibi", "motive", "suspect", "questioned", "theory"],
        "complications": ["wrong", "another", "deeper", "connected", "threatened"],
        "breakthrough": ["realized", "the key", "finally", "proof", "confession"],
        "confrontation": ["accuse", "caught", "admit", "guilty", "arrest"],
        "resolution": ["solved", "justice", "closure", "truth", "over"],
    },
    GenreArcType.HEIST: {
        "opportunity": ["score", "target", "job", "impossible", "worth millions"],
        "assembly": ["need", "specialist", "recruit", "team", "crew"],
        "planning": ["blueprint", "security", "timing", "entry point", "plan"],
        "preparation": ["equipment", "rehearse", "ready", "final check"],
        "execution": ["go time", "in position", "phase one", "moving"],
        "complication": ["wrong", "abort", "improvise", "caught", "alarm"],
        "escape": ["run", "getaway", "out", "clean", "disappeared"],
        "aftermath": ["split", "lay low", "consequences", "worth it"],
    },
    GenreArcType.ROMANCE: {
        "meeting": ["first saw", "met", "encounter", "noticed", "introduction"],
        "attraction": ["can't stop thinking", "drawn to", "chemistry", "resist"],
        "deepening": ["trust", "vulnerable", "opened up", "real", "connection"],
        "crisis": ["misunderstand", "secret", "lied", "betrayed", "over"],
        "separation": ["apart", "without", "miss", "empty", "wrong choice"],
        "reconciliation": ["sorry", "forgive", "truth", "realize", "love"],
        "union": ["together", "forever", "commitment", "future", "happy"],
    },
    GenreArcType.SURVIVAL: {
        "collapse": ["end", "fallen", "destroyed", "apocalypse", "gone"],
        "scarcity": ["running out", "ration", "hunger", "desperate", "need"],
        "conflict": ["raiders", "fight", "territory", "kill", "enemy"],
        "community": ["group", "survivors", "together", "trust", "build"],
        "threat": ["horde", "army", "coming", "defend", "last stand"],
        "hope": ["safe", "future", "rebuild", "sustainable", "new beginning"],
    },
    GenreArcType.WESTERN: {
        "arrival": ["rode into", "stranger", "new in town", "drifter"],
        "discovery": ["learned", "this town", "corruption", "who runs"],
        "escalation": ["pushing back", "won't stand", "challenge", "violence"],
        "showdown": ["high noon", "face", "draw", "final", "end this"],
        "aftermath": ["over", "done", "peace", "quiet", "buried"],
        "departure": ["moving on", "ride out", "goodbye", "horizon"],
    },
    GenreArcType.CYBERPUNK: {
        "awakening": ["truth", "lies", "system", "wake up", "see"],
        "contact": ["underground", "resistance", "rebels", "network", "trust"],
        "mission": ["job", "hack", "infiltrate", "data", "target"],
        "escalation": ["hunting", "everywhere", "corporation", "strike back"],
        "sacrifice": ["give up", "cost", "lose", "price", "worth"],
        "confrontation": ["core", "heart", "CEO", "AI", "mainframe"],
        "change": ["different", "shifted", "new world", "revolution", "aftermath"],
    },
}


def get_arc_type_for_genre(genre: str) -> GenreArcType:
    """
    Get the appropriate arc type for a world genre.

    Args:
        genre: The world's genre (e.g., "horror", "mystery", "fantasy")

    Returns:
        The appropriate GenreArcType, defaulting to HEROIC for unknown genres
    """
    return GENRE_TO_ARC.get(genre.lower(), GenreArcType.HEROIC)


def get_phases_for_arc(arc_type: GenreArcType) -> List[GenrePhase]:
    """
    Get the phase list for a genre arc type.

    Args:
        arc_type: The genre arc type

    Returns:
        List of GenrePhase objects for that arc
    """
    return GENRE_ARC_PHASES.get(arc_type, [])


def get_beat_templates_for_phase(
    arc_type: GenreArcType,
    phase_id: str,
) -> List[Dict[str, Any]]:
    """
    Get beat templates for a specific arc type and phase.

    Args:
        arc_type: The genre arc type
        phase_id: The phase ID (e.g., "normalcy", "crime")

    Returns:
        List of beat template dicts
    """
    arc_templates = GENRE_BEAT_TEMPLATES.get(arc_type, {})
    return arc_templates.get(phase_id, [])


def get_valid_transitions(arc_type: GenreArcType, phase_id: str) -> List[str]:
    """
    Get valid next phases for a given arc type and current phase.

    Args:
        arc_type: The genre arc type
        phase_id: The current phase ID

    Returns:
        List of valid next phase IDs
    """
    arc_transitions = GENRE_TRANSITIONS.get(arc_type, {})
    return arc_transitions.get(phase_id, [])


def get_phase_indicators(arc_type: GenreArcType, phase_id: str) -> List[str]:
    """
    Get keyword indicators for detecting a phase in narrative text.

    Args:
        arc_type: The genre arc type
        phase_id: The phase ID

    Returns:
        List of keywords that suggest this phase
    """
    arc_indicators = GENRE_PHASE_INDICATORS.get(arc_type, {})
    return arc_indicators.get(phase_id, [])
