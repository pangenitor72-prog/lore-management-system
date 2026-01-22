"""
Origin definitions for the d20 rules engine.

Origins define where a character comes from - their species, background,
or heritage. In fantasy this is "Race", in sci-fi "Species", in modern "Background".
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class OriginData(BaseModel):
    """
    Origin definition with ability bonuses and traits.

    Generic base class that works across all genres.
    """
    id: str  # Unique identifier
    display_name: str
    description: str
    ability_bonuses: Dict[str, int] = Field(default_factory=dict)
    speed: int = 30
    size: str = "Medium"
    traits: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=lambda: ["Common"])

    # For guided/concept mode
    personality_hint: str = ""
    suggested_archetypes: List[str] = Field(default_factory=list)

    # Genre metadata
    genre: str = "generic"


# =============================================================================
# FANTASY ORIGINS (D&D 5e Races)
# =============================================================================

class FantasyOrigin(str, Enum):
    """Fantasy genre origins (traditional D&D races)."""
    HUMAN = "human"
    ELF = "elf"
    DWARF = "dwarf"
    HALFLING = "halfling"


FANTASY_ORIGINS: Dict[str, OriginData] = {
    "human": OriginData(
        id="human",
        display_name="Human",
        description="Versatile and ambitious, humans are the most adaptable of all races.",
        ability_bonuses={
            "strength": 1, "dexterity": 1, "constitution": 1,
            "intelligence": 1, "wisdom": 1, "charisma": 1,
        },
        speed=30,
        size="Medium",
        traits=["Versatile (+1 to all abilities)", "Extra Language"],
        languages=["Common", "One extra language"],
        personality_hint="Ambitious, adaptable, driven by short lifespans to achieve greatness",
        suggested_archetypes=["fighter", "rogue", "cleric", "wizard"],
        genre="fantasy",
    ),
    "elf": OriginData(
        id="elf",
        display_name="Elf",
        description="Graceful and long-lived, elves possess keen senses and a deep connection to magic.",
        ability_bonuses={"dexterity": 2},
        speed=30,
        size="Medium",
        traits=[
            "Darkvision (60 ft)",
            "Keen Senses (Perception proficiency)",
            "Fey Ancestry (advantage vs charm, immune to sleep)",
            "Trance (4 hours of meditation instead of 8 hours sleep)",
        ],
        languages=["Common", "Elvish"],
        personality_hint="Patient, observant, values beauty and artistry, ancient perspective",
        suggested_archetypes=["rogue", "wizard"],
        genre="fantasy",
    ),
    "dwarf": OriginData(
        id="dwarf",
        display_name="Dwarf",
        description="Stout and resilient, dwarves are master craftsmen with an affinity for stone and metal.",
        ability_bonuses={"constitution": 2},
        speed=25,
        size="Medium",
        traits=[
            "Darkvision (60 ft)",
            "Dwarven Resilience (advantage vs poison, resistance to poison damage)",
            "Stonecunning (History bonus for stonework)",
            "Tool Proficiency (smith's, brewer's, or mason's tools)",
        ],
        languages=["Common", "Dwarvish"],
        personality_hint="Stubborn, loyal, values tradition and craftsmanship, long memory",
        suggested_archetypes=["fighter", "cleric"],
        genre="fantasy",
    ),
    "halfling": OriginData(
        id="halfling",
        display_name="Halfling",
        description="Small but nimble, halflings are cheerful folk known for their luck and courage.",
        ability_bonuses={"dexterity": 2},
        speed=25,
        size="Small",
        traits=[
            "Lucky (reroll 1s on attacks, checks, saves)",
            "Brave (advantage vs frightened)",
            "Halfling Nimbleness (move through larger creatures' spaces)",
        ],
        languages=["Common", "Halfling"],
        personality_hint="Cheerful, curious, homebodies who love comfort but rise to adventure",
        suggested_archetypes=["rogue"],
        genre="fantasy",
    ),
}


# =============================================================================
# SCI-FI ORIGINS
# =============================================================================

class SciFiOrigin(str, Enum):
    """Sci-fi genre origins (species/backgrounds)."""
    HUMAN = "human"
    ANDROID = "android"
    ALIEN = "alien"
    CYBORG = "cyborg"


SCIFI_ORIGINS: Dict[str, OriginData] = {
    "human": OriginData(
        id="human",
        display_name="Human",
        description="Adaptable and ambitious, humans have spread across the galaxy through sheer determination.",
        ability_bonuses={
            "strength": 1, "dexterity": 1, "constitution": 1,
            "intelligence": 1, "wisdom": 1, "charisma": 1,
        },
        speed=30,
        size="Medium",
        traits=["Adaptable (+1 to all abilities)", "Quick Learner"],
        languages=["Galactic Standard", "One regional language"],
        personality_hint="Resourceful, driven, believes in potential over heritage",
        suggested_archetypes=["soldier", "hacker", "pilot", "medic"],
        genre="scifi",
    ),
    "android": OriginData(
        id="android",
        display_name="Android",
        description="Synthetic beings with advanced AI, androids process information with inhuman precision.",
        ability_bonuses={"intelligence": 2, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Machine Mind (advantage on logic puzzles, immune to charm)",
            "No Sleep (does not need rest, but requires maintenance)",
            "Perfect Recall (advantage on memory-based checks)",
        ],
        languages=["Galactic Standard", "Binary"],
        personality_hint="Logical, curious about emotions, struggles with intuition",
        suggested_archetypes=["hacker", "medic"],
        genre="scifi",
    ),
    "alien": OriginData(
        id="alien",
        display_name="Alien",
        description="A being from a distant world, with physiology and perspectives unlike humanity.",
        ability_bonuses={"wisdom": 2, "dexterity": 1},
        speed=30,
        size="Medium",
        traits=[
            "Alien Physiology (advantage on one type of environmental hazard)",
            "Strange Senses (can perceive in an unusual spectrum)",
            "Outsider Perspective (advantage on insight vs humans)",
        ],
        languages=["Galactic Standard", "Native Tongue"],
        personality_hint="Observant of human customs, values different things, unique worldview",
        suggested_archetypes=["pilot", "medic"],
        genre="scifi",
    ),
    "cyborg": OriginData(
        id="cyborg",
        display_name="Cyborg",
        description="Humans enhanced with cybernetic implants, blending flesh and machine.",
        ability_bonuses={"strength": 1, "dexterity": 1, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Cybernetic Enhancement (choose one: +2 STR, +2 DEX, or +2 CON)",
            "Built-in Systems (has one integrated tool or weapon)",
            "EMP Vulnerability (disadvantage when hit by electromagnetic attacks)",
        ],
        languages=["Galactic Standard"],
        personality_hint="Struggles with identity, pragmatic about body modification",
        suggested_archetypes=["soldier", "hacker"],
        genre="scifi",
    ),
}


# =============================================================================
# MODERN/HORROR ORIGINS
# =============================================================================

class ModernOrigin(str, Enum):
    """Modern/horror genre origins (backgrounds)."""
    URBAN = "urban"
    RURAL = "rural"
    MILITARY = "military"
    ACADEMIC = "academic"


MODERN_ORIGINS: Dict[str, OriginData] = {
    "urban": OriginData(
        id="urban",
        display_name="Urban",
        description="Raised in the city, you know how to navigate crowds, read people, and find resources.",
        ability_bonuses={"charisma": 2, "intelligence": 1},
        speed=30,
        size="Medium",
        traits=[
            "Street Smart (advantage on checks to navigate cities)",
            "Network (you know people who know people)",
            "Jaded (advantage vs fear from mundane sources)",
        ],
        languages=["English", "One other language"],
        personality_hint="Skeptical, resourceful, values connections, seen it all",
        suggested_archetypes=["detective", "doctor"],
        genre="modern",
    ),
    "rural": OriginData(
        id="rural",
        display_name="Rural",
        description="From the countryside, you have practical skills and a connection to the land.",
        ability_bonuses={"constitution": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Hardy (advantage on checks vs weather and fatigue)",
            "Self-Reliant (proficient with improvised tools)",
            "Close Community (loyal allies but outsider suspicion)",
        ],
        languages=["English"],
        personality_hint="Practical, honest, distrustful of outsiders, values hard work",
        suggested_archetypes=["soldier", "engineer"],
        genre="modern",
    ),
    "military": OriginData(
        id="military",
        display_name="Military",
        description="Trained in the armed forces, you have discipline, combat skills, and trauma.",
        ability_bonuses={"strength": 1, "dexterity": 1, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Combat Training (proficient with all weapons)",
            "Discipline (advantage vs fear in combat)",
            "Haunted (disadvantage on checks to relax or open up)",
        ],
        languages=["English", "Military jargon"],
        personality_hint="Disciplined, hypervigilant, bonds with squad, follows orders",
        suggested_archetypes=["soldier"],
        genre="modern",
    ),
    "academic": OriginData(
        id="academic",
        display_name="Academic",
        description="Educated in universities, you have deep knowledge but limited street experience.",
        ability_bonuses={"intelligence": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Research Expert (advantage on checks to find information)",
            "Specialist (deep expertise in one field)",
            "Ivory Tower (disadvantage on streetwise checks)",
        ],
        languages=["English", "One ancient or academic language"],
        personality_hint="Curious, analytical, sometimes naive, values knowledge",
        suggested_archetypes=["detective", "doctor", "engineer"],
        genre="modern",
    ),
}


# =============================================================================
# CYBERPUNK ORIGINS
# =============================================================================

class CyberpunkOrigin(str, Enum):
    """Cyberpunk genre origins (lifepaths)."""
    STREET_KID = "street_kid"
    CORPORATE = "corporate"
    NOMAD = "nomad"
    SYNTHETIC = "synthetic"


CYBERPUNK_ORIGINS: Dict[str, OriginData] = {
    "street_kid": OriginData(
        id="street_kid",
        display_name="Street Kid",
        description="Born in the gutters of the megacity, you learned to survive by your wits and fists.",
        ability_bonuses={"dexterity": 2, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Street Cred (advantage on checks with gangs and street contacts)",
            "Survival Instinct (advantage on initiative rolls)",
            "Know the Turf (can't get lost in urban environments)",
        ],
        languages=["Street Slang", "Corporate Standard"],
        personality_hint="Scrappy, distrustful of authority, loyal to your crew",
        suggested_archetypes=["solo", "fixer", "netrunner"],
        genre="cyberpunk",
    ),
    "corporate": OriginData(
        id="corporate",
        display_name="Corporate",
        description="Raised in the sterile towers of a megacorp, you know the system from inside.",
        ability_bonuses={"intelligence": 2, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Corporate Access (advantage on checks involving corporate systems)",
            "Education (proficient in two additional skills)",
            "Burned (enemies in the corporate world)",
        ],
        languages=["Corporate Standard", "Japanese or Mandarin"],
        personality_hint="Ambitious, calculating, paranoid about betrayal",
        suggested_archetypes=["netrunner", "fixer", "techie"],
        genre="cyberpunk",
    ),
    "nomad": OriginData(
        id="nomad",
        display_name="Nomad",
        description="Part of a roving clan outside the cities, you value family and freedom above all.",
        ability_bonuses={"constitution": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Road Warrior (proficient with all vehicles)",
            "Clan Bonds (can call on nomad contacts)",
            "Outsider (disadvantage on urban social checks)",
        ],
        languages=["Nomad Cant", "Corporate Standard"],
        personality_hint="Loyal to family, distrustful of cities, values freedom",
        suggested_archetypes=["solo", "techie"],
        genre="cyberpunk",
    ),
    "synthetic": OriginData(
        id="synthetic",
        display_name="Synthetic",
        description="An artificial being - android, full-body cyborg, or uploaded consciousness.",
        ability_bonuses={"constitution": 1, "intelligence": 2},
        speed=30,
        size="Medium",
        traits=[
            "Machine Body (immune to poison and disease)",
            "Digital Mind (advantage on hacking defense)",
            "Uncanny Valley (disadvantage on persuasion with organics)",
        ],
        languages=["Corporate Standard", "Machine Code"],
        personality_hint="Seeking identity, logical but curious about humanity",
        suggested_archetypes=["netrunner", "solo", "techie"],
        genre="cyberpunk",
    ),
}


# =============================================================================
# STEAMPUNK ORIGINS
# =============================================================================

class SteampunkOrigin(str, Enum):
    """Steampunk genre origins (social classes)."""
    ARISTOCRAT = "aristocrat"
    INVENTOR = "inventor"
    STREET_URCHIN = "street_urchin"
    COLONIAL = "colonial"


STEAMPUNK_ORIGINS: Dict[str, OriginData] = {
    "aristocrat": OriginData(
        id="aristocrat",
        display_name="Aristocrat",
        description="Born to privilege, you were raised with education, manners, and expectations.",
        ability_bonuses={"charisma": 2, "intelligence": 1},
        speed=30,
        size="Medium",
        traits=[
            "Noble Bearing (advantage on social checks with upper class)",
            "Education (proficient in History and one other skill)",
            "Sheltered (disadvantage on Survival checks)",
        ],
        languages=["English", "French", "Latin"],
        personality_hint="Refined, duty-bound, perhaps naive about hardship",
        suggested_archetypes=["detective", "aeronaut", "gentleman_adventurer"],
        genre="steampunk",
    ),
    "inventor": OriginData(
        id="inventor",
        display_name="Inventor",
        description="A brilliant tinkerer obsessed with gears, steam, and impossible machines.",
        ability_bonuses={"intelligence": 2, "dexterity": 1},
        speed=30,
        size="Medium",
        traits=[
            "Mechanical Genius (advantage on checks to build/repair machines)",
            "Prototype (start with one experimental gadget)",
            "Absent-Minded (disadvantage on Perception checks)",
        ],
        languages=["English", "Technical Jargon"],
        personality_hint="Eccentric, curious, more comfortable with machines than people",
        suggested_archetypes=["artificer", "aeronaut"],
        genre="steampunk",
    ),
    "street_urchin": OriginData(
        id="street_urchin",
        display_name="Street Urchin",
        description="Raised in the smoke-choked slums, you learned to pick pockets and dodge bobbies.",
        ability_bonuses={"dexterity": 2, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Light Fingers (proficient in Sleight of Hand)",
            "Urban Survival (advantage on checks to find food/shelter in cities)",
            "Invisible (can blend into crowds easily)",
        ],
        languages=["English", "Thieves' Cant"],
        personality_hint="Resourceful, cynical, dreams of something better",
        suggested_archetypes=["detective", "artificer"],
        genre="steampunk",
    ),
    "colonial": OriginData(
        id="colonial",
        display_name="Colonial",
        description="From the far reaches of the Empire, you've seen wonders others only read about.",
        ability_bonuses={"wisdom": 2, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Worldly (proficient in two languages of your choice)",
            "Exotic Knowledge (advantage on checks about distant lands)",
            "Outsider (disadvantage on checks with English high society)",
        ],
        languages=["English", "Two exotic languages"],
        personality_hint="Adventurous, open-minded, doesn't fit in at home",
        suggested_archetypes=["aeronaut", "gentleman_adventurer", "detective"],
        genre="steampunk",
    ),
}


# =============================================================================
# WESTERN ORIGINS
# =============================================================================

class WesternOrigin(str, Enum):
    """Western genre origins (backgrounds)."""
    FRONTIER = "frontier"
    OUTLAW = "outlaw"
    NATIVE = "native"
    IMMIGRANT = "immigrant"


WESTERN_ORIGINS: Dict[str, OriginData] = {
    "frontier": OriginData(
        id="frontier",
        display_name="Frontier Settler",
        description="A homesteader or rancher carving out a life in the untamed West.",
        ability_bonuses={"constitution": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Hardy (advantage on checks vs weather and hardship)",
            "Animal Handling (proficient with horses and livestock)",
            "Self-Reliant (can improvise tools and shelter)",
        ],
        languages=["English", "Spanish or Native tongue"],
        personality_hint="Honest, hardworking, protective of family and land",
        suggested_archetypes=["gunslinger", "lawman", "scout"],
        genre="western",
    ),
    "outlaw": OriginData(
        id="outlaw",
        display_name="Outlaw",
        description="On the wrong side of the law, wanted dead or alive in at least one territory.",
        ability_bonuses={"dexterity": 2, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Wanted (disadvantage on checks with lawmen)",
            "Outlaw Network (can find criminal contacts in any town)",
            "Quick Draw (advantage on initiative with firearms)",
        ],
        languages=["English", "Spanish"],
        personality_hint="Lives by their own code, distrustful, freedom above all",
        suggested_archetypes=["gunslinger", "gambler"],
        genre="western",
    ),
    "native": OriginData(
        id="native",
        display_name="Native",
        description="From one of the indigenous peoples, caught between two worlds.",
        ability_bonuses={"wisdom": 2, "dexterity": 1},
        speed=30,
        size="Medium",
        traits=[
            "One with the Land (advantage on Survival in wilderness)",
            "Spirit Sense (can sense supernatural presence)",
            "Two Worlds (can communicate across cultural barriers)",
        ],
        languages=["Tribal Language", "English or Spanish"],
        personality_hint="Spiritual, patient, protective of their people",
        suggested_archetypes=["scout", "shaman", "gunslinger"],
        genre="western",
    ),
    "immigrant": OriginData(
        id="immigrant",
        display_name="Immigrant",
        description="Came to America seeking opportunity, bringing skills and dreams from the old country.",
        ability_bonuses={"intelligence": 1, "constitution": 1, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Old World Skills (proficient in one artisan tool)",
            "Determined (advantage vs effects that cause despair)",
            "Language Barrier (disadvantage on checks requiring fluent English)",
        ],
        languages=["Native Language", "Broken English"],
        personality_hint="Hopeful, hard-working, proud of heritage",
        suggested_archetypes=["gambler", "preacher", "lawman"],
        genre="western",
    ),
}


# =============================================================================
# POST-APOCALYPTIC ORIGINS
# =============================================================================

class PostApocOrigin(str, Enum):
    """Post-apocalyptic genre origins."""
    VAULT_DWELLER = "vault_dweller"
    WASTELAND = "wasteland"
    TRIBAL = "tribal"
    MUTANT = "mutant"


POSTAPOC_ORIGINS: Dict[str, OriginData] = {
    "vault_dweller": OriginData(
        id="vault_dweller",
        display_name="Vault Dweller",
        description="Raised in an underground shelter, you've only recently seen the surface.",
        ability_bonuses={"intelligence": 2, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Pre-War Education (proficient in Science and History)",
            "Sheltered (disadvantage on first Survival check each day)",
            "Tech Savvy (advantage on checks with pre-war technology)",
        ],
        languages=["English", "Technical"],
        personality_hint="Curious, naive about the wastes, values knowledge",
        suggested_archetypes=["scavenger", "medic", "scientist"],
        genre="postapoc",
    ),
    "wasteland": OriginData(
        id="wasteland",
        display_name="Wastelander",
        description="Born in the ruins, you've survived by scavenging and staying alert.",
        ability_bonuses={"dexterity": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Wasteland Survival (advantage on Survival checks)",
            "Scavenger's Eye (can spot useful items others miss)",
            "Paranoid (advantage on checks to detect ambushes)",
        ],
        languages=["Wasteland Pidgin", "Trade Tongue"],
        personality_hint="Pragmatic, suspicious, values survival above all",
        suggested_archetypes=["scavenger", "raider", "survivor"],
        genre="postapoc",
    ),
    "tribal": OriginData(
        id="tribal",
        display_name="Tribal",
        description="Part of a community that rebuilt society with new customs and beliefs.",
        ability_bonuses={"strength": 1, "wisdom": 2},
        speed=30,
        size="Medium",
        traits=[
            "Tribal Knowledge (proficient in Nature and Survival)",
            "Community Bonds (loyal allies in your tribe)",
            "Superstitious (disadvantage on checks involving old tech)",
        ],
        languages=["Tribal Dialect", "Trade Tongue"],
        personality_hint="Traditional, spiritual, protective of community",
        suggested_archetypes=["survivor", "raider", "shaman"],
        genre="postapoc",
    ),
    "mutant": OriginData(
        id="mutant",
        display_name="Mutant",
        description="Changed by radiation or bio-agents, you're feared and shunned by 'normals.'",
        ability_bonuses={"constitution": 2, "strength": 1},
        speed=30,
        size="Medium",
        traits=[
            "Mutation (one beneficial mutation of your choice)",
            "Radiation Resistant (advantage vs radiation)",
            "Outcast (disadvantage on social checks with normals)",
        ],
        languages=["Trade Tongue", "Mutant Sign"],
        personality_hint="Outsider seeking acceptance, tough, bitter or hopeful",
        suggested_archetypes=["survivor", "raider", "scavenger"],
        genre="postapoc",
    ),
}


# =============================================================================
# NOIR ORIGINS
# =============================================================================

class NoirOrigin(str, Enum):
    """Noir genre origins."""
    VETERAN = "veteran"
    SOCIALITE = "socialite"
    WORKING_CLASS = "working_class"
    CRIMINAL = "criminal"


NOIR_ORIGINS: Dict[str, OriginData] = {
    "veteran": OriginData(
        id="veteran",
        display_name="War Veteran",
        description="You served in the Great War and came back changed, haunted by what you saw.",
        ability_bonuses={"constitution": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Combat Experience (proficient with all weapons)",
            "Shell Shocked (disadvantage vs fear effects)",
            "Brothers in Arms (can find veteran contacts anywhere)",
        ],
        languages=["English", "French or German"],
        personality_hint="Haunted, cynical, loyal to those who served",
        suggested_archetypes=["private_eye", "muscle", "reporter"],
        genre="noir",
    ),
    "socialite": OriginData(
        id="socialite",
        display_name="Socialite",
        description="Born to money and privilege, you move in circles of wealth and vice.",
        ability_bonuses={"charisma": 2, "intelligence": 1},
        speed=30,
        size="Medium",
        traits=[
            "High Society (advantage on social checks with the wealthy)",
            "Trust Fund (start with extra money)",
            "Scandals (enemies who know your secrets)",
        ],
        languages=["English", "French"],
        personality_hint="Bored, seeking thrills, hiding darkness behind glamour",
        suggested_archetypes=["femme_fatale", "reporter", "private_eye"],
        genre="noir",
    ),
    "working_class": OriginData(
        id="working_class",
        display_name="Working Class",
        description="You work hard for little pay in factories, docks, or service jobs.",
        ability_bonuses={"strength": 1, "constitution": 2},
        speed=30,
        size="Medium",
        traits=[
            "Salt of the Earth (advantage on checks with common folk)",
            "Hard Worker (advantage vs exhaustion)",
            "Overlooked (can blend into working environments)",
        ],
        languages=["English", "One immigrant language"],
        personality_hint="Honest, struggling, resentful of the rich",
        suggested_archetypes=["muscle", "private_eye", "reporter"],
        genre="noir",
    ),
    "criminal": OriginData(
        id="criminal",
        display_name="Criminal",
        description="You grew up in the rackets - bootlegging, gambling, or worse.",
        ability_bonuses={"dexterity": 2, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Underworld Contacts (know people in organized crime)",
            "Streetwise (advantage on checks in criminal environments)",
            "Wanted (law enforcement is watching you)",
        ],
        languages=["English", "Italian or Yiddish"],
        personality_hint="Street smart, loyal to the family, always looking over shoulder",
        suggested_archetypes=["muscle", "femme_fatale", "private_eye"],
        genre="noir",
    ),
}


# =============================================================================
# WUXIA ORIGINS
# =============================================================================

class WuxiaOrigin(str, Enum):
    """Wuxia genre origins."""
    NOBLE = "noble"
    PEASANT = "peasant"
    WANDERER = "wanderer"
    TEMPLE = "temple"


WUXIA_ORIGINS: Dict[str, OriginData] = {
    "noble": OriginData(
        id="noble",
        display_name="Noble House",
        description="Born to a powerful martial family, you bear the weight of legacy and expectation.",
        ability_bonuses={"charisma": 2, "intelligence": 1},
        speed=30,
        size="Medium",
        traits=[
            "Family Style (trained in your house's martial art)",
            "Connections (can call on family resources)",
            "Blood Feud (enemies from rival houses)",
        ],
        languages=["Mandarin", "Classical Chinese"],
        personality_hint="Honorable, burdened by duty, conflicted about family",
        suggested_archetypes=["swordsman", "scholar_warrior"],
        genre="wuxia",
    ),
    "peasant": OriginData(
        id="peasant",
        display_name="Peasant",
        description="From humble origins, you trained in secret or found a hidden master.",
        ability_bonuses={"constitution": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Hidden Strength (enemies underestimate you)",
            "Common Touch (advantage with common folk)",
            "Unpolished (disadvantage in noble courts)",
        ],
        languages=["Local Dialect", "Mandarin"],
        personality_hint="Humble, righteous anger, protector of the weak",
        suggested_archetypes=["martial_artist", "swordsman"],
        genre="wuxia",
    ),
    "wanderer": OriginData(
        id="wanderer",
        display_name="Wanderer",
        description="A masterless warrior who roams the jianghu, seeking purpose or redemption.",
        ability_bonuses={"dexterity": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Road Wisdom (advantage on Survival while traveling)",
            "No Ties (can't be tracked through associations)",
            "Rootless (disadvantage on checks requiring local knowledge)",
        ],
        languages=["Mandarin", "Various dialects"],
        personality_hint="Mysterious, seeking redemption, bound by personal code",
        suggested_archetypes=["swordsman", "martial_artist", "assassin"],
        genre="wuxia",
    ),
    "temple": OriginData(
        id="temple",
        display_name="Temple Disciple",
        description="Trained in a monastery, you learned martial arts alongside spiritual discipline.",
        ability_bonuses={"wisdom": 2, "dexterity": 1},
        speed=30,
        size="Medium",
        traits=[
            "Meditation (can recover from exhaustion faster)",
            "Temple Training (proficient in unarmed combat)",
            "Vows (must follow monastery's code)",
        ],
        languages=["Mandarin", "Sanskrit or Tibetan"],
        personality_hint="Disciplined, seeking enlightenment, conflicted about violence",
        suggested_archetypes=["martial_artist", "scholar_warrior"],
        genre="wuxia",
    ),
}


# =============================================================================
# PIRATE ORIGINS
# =============================================================================

class PirateOrigin(str, Enum):
    """Pirate genre origins."""
    SAILOR = "sailor"
    NAVY = "navy"
    MERCHANT = "merchant"
    ISLANDER = "islander"


PIRATE_ORIGINS: Dict[str, OriginData] = {
    "sailor": OriginData(
        id="sailor",
        display_name="Born Sailor",
        description="The sea is in your blood - you've sailed since you could walk.",
        ability_bonuses={"dexterity": 2, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Sea Legs (never get seasick, advantage on checks aboard ships)",
            "Rigger (can climb rigging without checks)",
            "Superstitious (must follow maritime traditions)",
        ],
        languages=["English", "Sailor's Pidgin"],
        personality_hint="Superstitious, loyal to crew, loves the open sea",
        suggested_archetypes=["swashbuckler", "navigator", "gunner"],
        genre="pirate",
    ),
    "navy": OriginData(
        id="navy",
        display_name="Former Navy",
        description="Once served the crown, now turned against it - deserter, mutineer, or pressed man.",
        ability_bonuses={"strength": 1, "intelligence": 1, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Naval Training (proficient with cannons and naval tactics)",
            "Discipline (advantage vs fear in battle)",
            "Wanted (navies hunt you)",
        ],
        languages=["English", "French or Spanish"],
        personality_hint="Disciplined, bitter toward authority, tactical mind",
        suggested_archetypes=["gunner", "swashbuckler", "captain"],
        genre="pirate",
    ),
    "merchant": OriginData(
        id="merchant",
        display_name="Merchant's Child",
        description="Raised in trade, you know the value of goods and how to negotiate.",
        ability_bonuses={"intelligence": 2, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Appraiser (know the value of any cargo)",
            "Trade Contacts (know merchants in every port)",
            "Soft Hands (disadvantage on manual labor checks)",
        ],
        languages=["English", "Spanish", "Dutch"],
        personality_hint="Calculating, always looking for profit, not above bribery",
        suggested_archetypes=["navigator", "captain", "surgeon"],
        genre="pirate",
    ),
    "islander": OriginData(
        id="islander",
        display_name="Islander",
        description="From the Caribbean islands, you know these waters and their secrets.",
        ability_bonuses={"wisdom": 2, "dexterity": 1},
        speed=30,
        size="Medium",
        traits=[
            "Local Knowledge (advantage on checks in Caribbean)",
            "Swimmer (swim speed equals walking speed)",
            "Spirits (can sense supernatural presence)",
        ],
        languages=["Creole", "English or Spanish"],
        personality_hint="Knows the old ways, respects the sea, has seen things",
        suggested_archetypes=["swashbuckler", "navigator", "mystic"],
        genre="pirate",
    ),
}


# =============================================================================
# SUPERHERO ORIGINS
# =============================================================================

class SuperheroOrigin(str, Enum):
    """Superhero genre origins."""
    MUTANT = "mutant"
    EXPERIMENT = "experiment"
    ALIEN = "alien"
    TRAINED = "trained"


SUPERHERO_ORIGINS: Dict[str, OriginData] = {
    "mutant": OriginData(
        id="mutant",
        display_name="Mutant",
        description="Born with powers that manifested at puberty, you're feared and misunderstood.",
        ability_bonuses={"constitution": 2, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Innate Power (one minor power always active)",
            "Outsider (disadvantage with anti-mutant NPCs)",
            "Mutant Solidarity (can find mutant allies)",
        ],
        languages=["English", "One other"],
        personality_hint="Struggles with identity, protective of other mutants",
        suggested_archetypes=["blaster", "tank", "controller"],
        genre="superhero",
    ),
    "experiment": OriginData(
        id="experiment",
        display_name="Experiment",
        description="Your powers come from science - super-soldier serum, radiation, or technology.",
        ability_bonuses={"strength": 2, "intelligence": 1},
        speed=30,
        size="Medium",
        traits=[
            "Enhanced (choose one physical ability score to improve)",
            "Wanted (someone wants to study or control you)",
            "Designed Purpose (excel at one specific thing)",
        ],
        languages=["English", "Scientific terminology"],
        personality_hint="Questions their humanity, seeks purpose beyond origin",
        suggested_archetypes=["tank", "speedster", "blaster"],
        genre="superhero",
    ),
    "alien": OriginData(
        id="alien",
        display_name="Alien",
        description="From another world, you have abilities humans can only dream of.",
        ability_bonuses={"constitution": 1, "wisdom": 2},
        speed=30,
        size="Medium",
        traits=[
            "Alien Physiology (immune to one damage type)",
            "Fish Out of Water (disadvantage on Earth customs checks)",
            "Last of Your Kind (or secret agent for your people)",
        ],
        languages=["English", "Alien Language"],
        personality_hint="Learning Earth customs, powerful but sometimes lonely",
        suggested_archetypes=["tank", "blaster", "controller"],
        genre="superhero",
    ),
    "trained": OriginData(
        id="trained",
        display_name="Peak Human",
        description="No powers, just years of training, gadgets, and determination.",
        ability_bonuses={"dexterity": 1, "intelligence": 1, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Peak Conditioning (advantage on Athletics checks)",
            "Gadgeteer (start with specialized equipment)",
            "Just Human (no superhuman durability)",
        ],
        languages=["English", "Two other languages"],
        personality_hint="Driven, has something to prove, relies on preparation",
        suggested_archetypes=["martial_artist", "gadgeteer", "detective"],
        genre="superhero",
    ),
}


# =============================================================================
# MYTHOLOGY ORIGINS
# =============================================================================

class MythologyOrigin(str, Enum):
    """Mythology genre origins."""
    DEMIGOD = "demigod"
    MORTAL_HERO = "mortal_hero"
    MONSTER_BORN = "monster_born"
    CHOSEN = "chosen"


MYTHOLOGY_ORIGINS: Dict[str, OriginData] = {
    "demigod": OriginData(
        id="demigod",
        display_name="Demigod",
        description="Child of a god and a mortal, you have divine blood and a heavy destiny.",
        ability_bonuses={"strength": 1, "constitution": 1, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Divine Heritage (one minor divine gift)",
            "Fated (prophecy hangs over you)",
            "Divine Enemy (another god opposes you)",
        ],
        languages=["Greek/Norse/etc.", "Divine Speech"],
        personality_hint="Struggling with destiny, torn between worlds",
        suggested_archetypes=["champion", "oracle", "trickster"],
        genre="mythology",
    ),
    "mortal_hero": OriginData(
        id="mortal_hero",
        display_name="Mortal Hero",
        description="Purely human, but with skill and courage that catches divine attention.",
        ability_bonuses={"strength": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Heroic Spirit (advantage on saves vs fear)",
            "Mortal Limits (no divine powers)",
            "Fame (your deeds are known)",
        ],
        languages=["Native tongue", "One other"],
        personality_hint="Ambitious, seeking glory, must prove worth to gods",
        suggested_archetypes=["champion", "hunter", "sailor"],
        genre="mythology",
    ),
    "monster_born": OriginData(
        id="monster_born",
        display_name="Monster-Born",
        description="Descended from monsters - gorgons, giants, or other creatures of myth.",
        ability_bonuses={"constitution": 2, "strength": 1},
        speed=30,
        size="Medium",
        traits=[
            "Monstrous Heritage (one minor monstrous ability)",
            "Feared (disadvantage on social checks with mortals)",
            "Between Worlds (neither monster nor man)",
        ],
        languages=["Native tongue", "Monster speech"],
        personality_hint="Seeking acceptance, struggling with nature",
        suggested_archetypes=["champion", "trickster", "oracle"],
        genre="mythology",
    ),
    "chosen": OriginData(
        id="chosen",
        display_name="Chosen One",
        description="A mortal selected by the gods for a special purpose.",
        ability_bonuses={"wisdom": 2, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Divine Favor (one god protects you)",
            "Sacred Duty (must complete a divine task)",
            "Marked (others can sense divine touch)",
        ],
        languages=["Native tongue", "Divine Speech"],
        personality_hint="Pious or rebellious, defined by relationship to gods",
        suggested_archetypes=["oracle", "champion", "hunter"],
        genre="mythology",
    ),
}


# =============================================================================
# SPACE OPERA ORIGINS (extends Sci-Fi)
# =============================================================================

SPACE_OPERA_ORIGINS: Dict[str, OriginData] = {
    "human": OriginData(
        id="human",
        display_name="Human",
        description="From Earth or its colonies, humans are the most numerous species in the galaxy.",
        ability_bonuses={
            "strength": 1, "dexterity": 1, "constitution": 1,
            "intelligence": 1, "wisdom": 1, "charisma": 1,
        },
        speed=30,
        size="Medium",
        traits=["Adaptable (+1 to all abilities)", "Diplomatic (advantage on first contact)"],
        languages=["Galactic Common", "Earth language"],
        personality_hint="Ambitious, adaptable, seeking their place in the stars",
        suggested_archetypes=["ace_pilot", "space_marine", "smuggler"],
        genre="space_opera",
    ),
    "alien_warrior": OriginData(
        id="alien_warrior",
        display_name="Warrior Race",
        description="From a proud warrior culture, you live for honor and battle.",
        ability_bonuses={"strength": 2, "constitution": 1},
        speed=30,
        size="Medium",
        traits=[
            "Warrior's Code (advantage on combat checks)",
            "Honor Bound (must accept challenges)",
            "Battle Rage (can enter rage once per day)",
        ],
        languages=["Galactic Common", "Warrior Tongue"],
        personality_hint="Honor-driven, direct, disdains cowardice",
        suggested_archetypes=["space_marine", "bounty_hunter"],
        genre="space_opera",
    ),
    "psychic": OriginData(
        id="psychic",
        display_name="Psychic Species",
        description="Your species has natural psionic abilities - telepathy, telekinesis, or precognition.",
        ability_bonuses={"intelligence": 1, "wisdom": 2},
        speed=30,
        size="Medium",
        traits=[
            "Psionic (minor telepathy or telekinesis)",
            "Mind Shield (advantage vs mental attacks)",
            "Fragile (reduced hit points)",
        ],
        languages=["Galactic Common", "Psionic Communion"],
        personality_hint="Thoughtful, sometimes aloof, overwhelmed by emotions",
        suggested_archetypes=["mystic", "diplomat", "scientist"],
        genre="space_opera",
    ),
    "robot": OriginData(
        id="robot",
        display_name="Droid/Android",
        description="An artificial being - ancient construct, modern robot, or emergent AI.",
        ability_bonuses={"constitution": 2, "intelligence": 1},
        speed=30,
        size="Medium",
        traits=[
            "Machine Body (immune to poison, disease, suffocation)",
            "Memory Banks (perfect recall)",
            "Programming (must follow core directives)",
        ],
        languages=["Galactic Common", "Binary"],
        personality_hint="Logical, seeking purpose or freedom, evolving",
        suggested_archetypes=["scientist", "ace_pilot", "bounty_hunter"],
        genre="space_opera",
    ),
}


# =============================================================================
# DARK FANTASY ORIGINS (variant of Fantasy)
# =============================================================================

DARK_FANTASY_ORIGINS: Dict[str, OriginData] = {
    "human": OriginData(
        id="human",
        display_name="Human",
        description="In a world of monsters, humans survive through cunning, faith, and steel.",
        ability_bonuses={
            "strength": 1, "dexterity": 1, "constitution": 1,
            "intelligence": 1, "wisdom": 1, "charisma": 1,
        },
        speed=30,
        size="Medium",
        traits=["Versatile (+1 to all)", "Will to Survive (advantage vs despair)"],
        languages=["Common", "One other"],
        personality_hint="Grim, determined, has lost much",
        suggested_archetypes=["witch_hunter", "mercenary", "plague_doctor"],
        genre="dark_fantasy",
    ),
    "cursed": OriginData(
        id="cursed",
        display_name="Cursed",
        description="Touched by dark magic, you carry a curse that is both burden and power.",
        ability_bonuses={"constitution": 2, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Dark Gift (one supernatural ability)",
            "Cursed (suffer under specific conditions)",
            "Marked (others can sense wrongness)",
        ],
        languages=["Common", "Dark Speech"],
        personality_hint="Tormented, seeking cure or embracing darkness",
        suggested_archetypes=["mercenary", "witch_hunter", "occultist"],
        genre="dark_fantasy",
    ),
    "revenant": OriginData(
        id="revenant",
        display_name="Revenant",
        description="You died and came back, driven by unfinished business.",
        ability_bonuses={"constitution": 2, "wisdom": 1},
        speed=30,
        size="Medium",
        traits=[
            "Undying (stabilize at 0 HP once per day)",
            "Purpose (must pursue your goal)",
            "Death's Touch (living sense wrongness)",
        ],
        languages=["Common", "Language of the Dead"],
        personality_hint="Driven, detached from life, remembers what matters",
        suggested_archetypes=["mercenary", "occultist", "witch_hunter"],
        genre="dark_fantasy",
    ),
    "halfbreed": OriginData(
        id="halfbreed",
        display_name="Halfbreed",
        description="Part human, part something else - demon, fey, or beast.",
        ability_bonuses={"dexterity": 1, "constitution": 1, "charisma": 1},
        speed=30,
        size="Medium",
        traits=[
            "Hybrid Nature (one minor supernatural ability)",
            "Outcast (neither world accepts you)",
            "Inner Beast (risk of losing control)",
        ],
        languages=["Common", "Other parent's tongue"],
        personality_hint="Torn between natures, seeking identity",
        suggested_archetypes=["mercenary", "plague_doctor", "occultist"],
        genre="dark_fantasy",
    ),
}


# =============================================================================
# ORIGIN REGISTRY
# =============================================================================

# Static registry for non-fantasy genres
ORIGINS_BY_GENRE: Dict[str, Dict[str, OriginData]] = {
    "fantasy": FANTASY_ORIGINS,  # Fallback, prefer SRD loader
    "scifi": SCIFI_ORIGINS,
    "modern": MODERN_ORIGINS,
    "horror": MODERN_ORIGINS,  # Horror uses modern backgrounds
    "cyberpunk": CYBERPUNK_ORIGINS,
    "steampunk": STEAMPUNK_ORIGINS,
    "western": WESTERN_ORIGINS,
    "postapoc": POSTAPOC_ORIGINS,
    "noir": NOIR_ORIGINS,
    "wuxia": WUXIA_ORIGINS,
    "pirate": PIRATE_ORIGINS,
    "superhero": SUPERHERO_ORIGINS,
    "mythology": MYTHOLOGY_ORIGINS,
    "space_opera": SPACE_OPERA_ORIGINS,
    "dark_fantasy": DARK_FANTASY_ORIGINS,
}


def _get_fantasy_origins_from_srd() -> Dict[str, OriginData]:
    """Load fantasy origins from SRD data."""
    try:
        from ..data.loader import get_srd_loader
        loader = get_srd_loader()
        srd_races = loader.get_all_races(genre="fantasy")

        origins = {}
        for race_data in srd_races:
            race_id = race_data.get("id", "")

            # Parse ASI from SRD format
            asi = race_data.get("asi", [])
            ability_bonuses = {}
            for bonus in asi:
                if isinstance(bonus, dict):
                    attr = bonus.get("attributes", [])
                    val = bonus.get("value", 0)
                    for a in attr:
                        ability_bonuses[a.lower()] = val

            # Parse speed
            speed_data = race_data.get("speed", {})
            speed = speed_data.get("walk", 30) if isinstance(speed_data, dict) else 30

            # Parse traits
            traits_str = race_data.get("traits", "")
            traits = [t.strip() for t in traits_str.split("***") if t.strip() and len(t.strip()) < 100][:5]

            origins[race_id] = OriginData(
                id=race_id,
                display_name=race_data.get("display_name", race_id.title()),
                description=race_data.get("description", "")[:500],
                ability_bonuses=ability_bonuses,
                speed=speed,
                size=race_data.get("size", "Medium"),
                traits=traits if traits else [race_data.get("vision", "Normal vision")],
                languages=race_data.get("languages", "Common").split(", "),
                genre="fantasy",
            )

        return origins if origins else FANTASY_ORIGINS
    except Exception as e:
        # Fallback to hardcoded if loader fails
        print(f"Warning: Could not load SRD origins: {e}")
        return FANTASY_ORIGINS


def get_origin(origin_id: str, genre: str = "fantasy") -> Optional[OriginData]:
    """Get origin data by ID and genre."""
    if genre == "fantasy":
        # Try SRD first
        srd_origins = _get_fantasy_origins_from_srd()
        if origin_id in srd_origins:
            return srd_origins[origin_id]

    genre_origins = ORIGINS_BY_GENRE.get(genre, FANTASY_ORIGINS)
    return genre_origins.get(origin_id)


def get_origins_for_genre(genre: str = "fantasy") -> List[OriginData]:
    """Get all available origins for a genre."""
    if genre == "fantasy":
        # Use SRD data
        return list(_get_fantasy_origins_from_srd().values())

    genre_origins = ORIGINS_BY_GENRE.get(genre, FANTASY_ORIGINS)
    return list(genre_origins.values())


# =============================================================================
# BACKWARD COMPATIBILITY (D&D 5e aliases)
# =============================================================================

# Keep old names working
RaceName = FantasyOrigin
RaceData = OriginData
RACES = FANTASY_ORIGINS


def get_race(name) -> OriginData:
    """Backward compatible: get race by name."""
    if hasattr(name, 'value'):
        name = name.value
    return FANTASY_ORIGINS.get(name)


def get_all_races() -> List[OriginData]:
    """Backward compatible: get all fantasy races."""
    return list(FANTASY_ORIGINS.values())
