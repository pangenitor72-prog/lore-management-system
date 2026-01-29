# src/mantle/creative/catalyst.py
"""
Creative Catalyst - Directed unpredictability for AI narrative generation.

Injects rotating creative constraints into the DM prompt to prevent
repetitive trope patterns. Each turn gets 1-2 directives from different
categories, with session-level tracking to prevent repeats.

Directives are "for this response only" — nothing is permanently banned.
The AI can still use taverns or mysterious strangers, just not every turn.
"""

from __future__ import annotations

import random
import logging
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class DirectiveCategory(str, Enum):
    ANTI_TROPE = "anti_trope"
    SENSORY = "sensory"
    STRUCTURAL = "structural"
    NPC_SEED = "npc_seed"
    EMOTIONAL = "emotional"


# =============================================================================
# UNIVERSAL DIRECTIVE POOLS
# =============================================================================

DIRECTIVE_POOLS: Dict[DirectiveCategory, List[str]] = {
    DirectiveCategory.ANTI_TROPE: [
        "Do NOT open with weather or landscape description — start with a person doing something",
        "No mysterious strangers — if a new character appears, make them mundane with a surprising detail",
        "Avoid prophecies, chosen-one hints, or destiny language in this response",
        "No taverns, inns, or drinking establishments as scene locations",
        "Skip the ominous warning — let danger arrive without announcement",
        "No mentors dispensing wisdom — any advice should come from an unlikely or reluctant source",
        "Avoid 'suddenly' — let transitions happen through character action, not narrative ambush",
        "No villains monologuing or explaining their plans — show threat through action",
        "Do not use a campfire scene or fireside conversation",
        "No convenient eavesdropping — if the player learns information, it should cost something",
        "Avoid the rescue-the-helpless-person hook — find a different motivation",
        "No glowing, pulsing, or humming magical objects — magic should manifest subtly",
    ],
    DirectiveCategory.SENSORY: [
        "Lead with SMELL in this scene — what does the air carry?",
        "Lead with SOUND — what does the player hear before they see anything?",
        "Lead with TOUCH/TEXTURE — ground the scene in physical sensation",
        "Lead with TASTE — something in the air, on their lips, or offered to them",
        "Describe TEMPERATURE as a character in this scene — how does heat or cold shape the moment?",
        "Include a specific bodily sensation — hunger, exhaustion, adrenaline, nausea, relief",
        "Describe the LIGHT specifically — not just 'dim' but how shadows fall, what's illuminated",
        "Ground the scene in one unexpected micro-detail only someone physically present would notice",
    ],
    DirectiveCategory.STRUCTURAL: [
        "Start this response in the MIDDLE of action — no preamble",
        "Use a single long sentence for the climactic moment, then short staccato sentences after",
        "End this response on an unresolved sensory detail, not a dramatic beat",
        "Begin with dialogue — someone is already talking when the scene opens",
        "Write the key moment of this scene from an unusual vantage point or angle",
        "Use silence or absence as the dramatic element — what ISN'T happening?",
        "Structure this response as contrast: juxtapose something beautiful with something ugly",
        "Let the scene breathe — include a beat of mundane normalcy amid the extraordinary",
    ],
    DirectiveCategory.NPC_SEED: [
        "Any NPC introduced should have a visible physical habit (fidgeting, limping, humming)",
        "Give any new NPC a goal that has nothing to do with the protagonist",
        "Any NPC encountered should be in the middle of their own problem when the player arrives",
        "New NPCs should initially be indifferent to the protagonist, not helpful or hostile",
        "Give any speaking NPC an unusual speech pattern: terse, formal, asks questions back, or trails off",
        "Any NPC should reveal one surprising personal detail that humanizes them",
        "If an NPC appears, they should want something tangible from the player",
        "An NPC's body language should contradict their words",
    ],
    DirectiveCategory.EMOTIONAL: [
        "Thread an undercurrent of HUMOR through this scene, even if the situation is serious",
        "Evoke NOSTALGIA — reference something the character has lost or left behind",
        "Build UNEASE through normalcy — everything seems fine, which is what makes it unsettling",
        "Create a moment of unexpected BEAUTY in an otherwise harsh or dark scene",
        "Let the protagonist feel DOUBT — not about the quest, but about themselves",
        "Include a moment of genuine WARMTH between characters, however brief",
        "Evoke LONELINESS even if the protagonist is surrounded by others",
        "Create a sense of TIME PRESSURE without explicitly stating a deadline",
    ],
}


# =============================================================================
# GENRE-SPECIFIC ANTI-TROPES
# =============================================================================

GENRE_ANTI_TROPES: Dict[str, List[str]] = {
    "fantasy": [
        "No ancient evil awakening from slumber — if there's a threat, make it recent and personal",
        "Skip the wise old wizard — magical knowledge should come from unexpected sources",
        "No throne rooms or royal audiences — power operates through less formal channels",
        "No dark lords — antagonists should have comprehensible, even sympathetic, motivations",
        "Avoid enchanted forests where trees whisper — if nature is important, make it specific and real",
    ],
    "horror": [
        "No creaky doors, flickering lights, or jump scares — build dread through wrongness in familiar things",
        "Do NOT explain the horror — leave it ambiguous whether the threat is real or imagined",
        "No abandoned asylums, haunted houses, or cursed dolls — find unexpected locations for unease",
        "The horror should come from something the player trusted, not something obviously threatening",
        "No gore for shock value — the most disturbing element should be psychological",
    ],
    "scifi": [
        "No rogue AI that wants to destroy humanity — if AI is present, give it alien but logical goals",
        "Skip the dystopian monologue — show societal problems through small, personal moments",
        "No convenient translator devices — communication barriers should be real obstacles",
        "Technology should have mundane failures and quirks, not just dramatic malfunctions",
        "No chosen-pilot or special-gene tropes — competence should come from training and grit",
    ],
    "mystery": [
        "No red herrings that feel like cheating — every clue should be fair and potentially relevant",
        "The investigator should miss something obvious the player might catch",
        "No convenient witnesses who saw everything — information should come in fragments",
        "Avoid the dramatic reveal in a drawing room — truth should emerge messily",
        "No perfect alibis to crack — suspects should have complicated, partially honest explanations",
    ],
    "gothic": [
        "No storms arriving to match the mood — weather should contrast with emotion",
        "The supernatural should intrude on the mundane, not the other way around",
        "No pure-evil vampires or werewolves — the monster's humanity is the interesting part",
        "No crumbling castle as primary setting — find unexpected spaces for gothic atmosphere",
        "Avoid blood-drenched excess — restraint is more unsettling than spectacle",
    ],
    "urban_fantasy": [
        "No hidden magical academies — magic should be woven into ordinary institutions",
        "The magical world should have bureaucracy, boredom, and petty politics",
        "No clear division between magical and mundane people — the lines should blur",
        "Avoid the 'normie stumbles into magic' opening — the player already lives in both worlds",
        "No magical artifacts in antique shops — if magic objects exist, they're in unexpected places",
    ],
    "adventure": [
        "No treasure maps with X marks the spot — if there's a goal, the path should be uncertain",
        "Skip the expedition-briefing scene — drop the player into the middle of the journey",
        "No exotic locals who exist only to provide exposition about their own culture",
        "The environment should be an active threat, not just scenic backdrop",
        "Avoid clear heroes-and-villains framing — rivals should have legitimate competing claims",
    ],
    "romance": [
        "No love at first sight — connection should build through specific shared experiences",
        "Avoid the miscommunication that could be resolved by one honest conversation",
        "No rival love interests who are obviously wrong for the protagonist",
        "The romantic interest should have a life and goals independent of the protagonist",
        "Skip the grand gesture — intimacy should come through small, specific moments",
    ],
    "drama": [
        "No deathbed confessions — if someone has a secret, they should struggle to keep it alive",
        "Avoid the confrontation scene where everyone says exactly what they mean",
        "No convenient crises that force characters together — let proximity feel natural",
        "Characters should want contradictory things simultaneously, not just face a binary choice",
        "Skip the heart-to-heart conversation — let emotional truth emerge through action",
    ],
}


# =============================================================================
# OPENING VARIETY SEEDS
# =============================================================================

OPENING_SEEDS: List[str] = [
    "Begin the story mid-conversation — the protagonist is already talking to someone",
    "Open with the protagonist doing something mundane that reveals character",
    "Start with a problem already in progress — something has gone wrong before the story begins",
    "Open from someone else's perspective briefly, then shift to the protagonist arriving",
    "Begin with the protagonist leaving somewhere — the story starts with departure, not arrival",
    "Start with the protagonist's hands — what are they holding, making, or doing?",
    "Open with a sound that doesn't belong — something out of place in the environment",
    "Begin at the END of a routine day — the last ordinary moment before everything changes",
    "Start with the protagonist observing someone else — they're watching, not being watched",
    "Open with the protagonist refusing something — an offer, a request, a temptation",
    "Begin with physical discomfort — the protagonist is cold, hungry, sore, or exhausted",
    "Start with a lie — the protagonist is pretending to be something they're not",
]


# =============================================================================
# CHARACTER GENERATION CREATIVE TWISTS
# =============================================================================

CHARACTER_GEN_DIRECTIVES: List[str] = [
    "Include at least one origin that is typically an antagonist race/group in this genre, reimagined as playable",
    "One archetype should combine two traditional roles in an unexpected way (e.g., healer-assassin, scholar-brawler)",
    "Include an origin based on a social class or occupation rather than species or heritage",
    "One archetype should be built around a non-combat specialty that becomes combat-relevant",
    "Include an origin that is normally considered mundane or low-status in the setting",
    "One archetype should subvert the genre's most common class trope",
]


# =============================================================================
# CREATIVE CATALYST CLASS
# =============================================================================

class CreativeCatalyst:
    """
    Session-scoped creative directive selector.

    Tracks recently used directives to avoid repetition and selects
    1-2 genre-appropriate creative constraints per AI generation call.
    """

    def __init__(self, genre: str = "fantasy"):
        self._genre = genre
        self._used_directives: List[str] = []
        self._used_opening_seeds: List[str] = []
        self._max_recent = 12
        self._turn_count = 0

    def get_directives(self, count: int = 2) -> str:
        """
        Select creative directives for this turn's DM prompt.

        Returns a formatted string ready for prompt injection (2-3 lines).
        Automatically avoids recently used directives.
        """
        self._turn_count += 1
        directives = []

        # 1. Select anti-trope (universal + genre-specific pool)
        anti_trope_pool = list(DIRECTIVE_POOLS[DirectiveCategory.ANTI_TROPE])
        genre_tropes = GENRE_ANTI_TROPES.get(self._genre, [])
        anti_trope_pool.extend(genre_tropes)

        selected = self._pick_from_pool(anti_trope_pool)
        if selected:
            directives.append(selected)

        # 2. Select from rotating secondary category
        categories_rotation = [
            DirectiveCategory.SENSORY,
            DirectiveCategory.STRUCTURAL,
            DirectiveCategory.NPC_SEED,
            DirectiveCategory.EMOTIONAL,
        ]
        secondary_cat = categories_rotation[self._turn_count % len(categories_rotation)]
        secondary_pool = list(DIRECTIVE_POOLS[secondary_cat])

        selected = self._pick_from_pool(secondary_pool)
        if selected:
            directives.append(selected)

        if not directives:
            return ""

        lines = ["CREATIVE DIRECTION (for this response only):"]
        for d in directives[:count]:
            lines.append(f"- {d}")

        logger.debug(f"[CATALYST] Turn {self._turn_count}: {len(directives)} directives selected")
        return "\n".join(lines)

    def get_opening_seed(self) -> str:
        """Select an opening variety seed for _generate_opening()."""
        available = [s for s in OPENING_SEEDS if s not in self._used_opening_seeds]
        if not available:
            self._used_opening_seeds.clear()
            available = OPENING_SEEDS

        selected = random.choice(available)
        self._used_opening_seeds.append(selected)
        return selected

    def get_character_gen_directive(self) -> str:
        """Return a creative constraint for character option generation."""
        return random.choice(CHARACTER_GEN_DIRECTIVES)

    def _pick_from_pool(self, pool: List[str]) -> Optional[str]:
        """Pick a directive from a pool, avoiding recently used ones."""
        available = [d for d in pool if d not in self._used_directives]
        if not available:
            # Clear only this pool's entries from recency window
            pool_set = set(pool)
            self._used_directives = [d for d in self._used_directives if d not in pool_set]
            available = pool

        if not available:
            return None

        selected = random.choice(available)
        self._used_directives.append(selected)

        # Trim rolling window
        while len(self._used_directives) > self._max_recent:
            self._used_directives.pop(0)

        return selected

    # === PERSISTENCE ===

    def to_dict(self) -> Dict[str, Any]:
        """Export state for persistence."""
        return {
            "genre": self._genre,
            "used_directives": self._used_directives,
            "used_opening_seeds": self._used_opening_seeds,
            "turn_count": self._turn_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CreativeCatalyst":
        """Restore from dictionary."""
        catalyst = cls(genre=data.get("genre", "fantasy"))
        catalyst._used_directives = data.get("used_directives", [])
        catalyst._used_opening_seeds = data.get("used_opening_seeds", [])
        catalyst._turn_count = data.get("turn_count", 0)
        return catalyst
