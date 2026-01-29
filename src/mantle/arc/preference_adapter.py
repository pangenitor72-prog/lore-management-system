# src/mantle/arc/preference_adapter.py
"""
Preference Adapter - Adapts Arc Engine output to player storytelling preferences.

The Arc Engine tracks story phases (Campbell's 12-stage structure) internally,
but the TEXT injected into the DM prompt should match the player's chosen arc,
lethality, and moral complexity preferences.

This module provides arc-appropriate descriptions and guidance for each phase,
so an Anti-Hero player never sees "the hero returns transformed" and a
Plot Armor player never gets "life-or-death" ordeal language.
"""

from __future__ import annotations

from typing import Optional, Dict

from .models import StoryPhase


# =============================================================================
# ARC-ADAPTED PHASE DESCRIPTIONS
# =============================================================================
# Each arc type gets a distinct description for every phase.
# These replace StoryPhase.description when preferences are active.

ARC_DESCRIPTIONS: Dict[str, Dict[StoryPhase, str]] = {
    "chosen_one": {
        StoryPhase.ORDINARY_WORLD: "The hero's normal life before destiny calls",
        StoryPhase.CALL_TO_ADVENTURE: "Destiny disrupts the status quo with a clear purpose",
        StoryPhase.REFUSAL_OF_THE_CALL: "The weight of destiny brings fear and reluctance",
        StoryPhase.MEETING_THE_MENTOR: "A guide reveals the hero's true potential",
        StoryPhase.CROSSING_THE_THRESHOLD: "The hero accepts their destiny and steps into the unknown",
        StoryPhase.TESTS_ALLIES_ENEMIES: "Trials prove the hero worthy of their calling",
        StoryPhase.APPROACH_TO_INMOST_CAVE: "The hero prepares for the challenge they were born to face",
        StoryPhase.ORDEAL: "The hero faces the ultimate challenge they were destined for",
        StoryPhase.REWARD: "Victory confirms the hero's purpose — the prize is claimed",
        StoryPhase.THE_ROAD_BACK: "The return journey carries the weight of responsibility",
        StoryPhase.RESURRECTION: "A final test proves the hero has truly earned their destiny",
        StoryPhase.RETURN_WITH_ELIXIR: "The hero returns transformed, bearing wisdom for their people",
    },
    "reluctant_hero": {
        StoryPhase.ORDINARY_WORLD: "A quiet life, deliberately chosen — this person wants no part of adventure",
        StoryPhase.CALL_TO_ADVENTURE: "Trouble arrives uninvited — duty demands what desire refuses",
        StoryPhase.REFUSAL_OF_THE_CALL: "Every instinct says walk away — and the reasons are valid",
        StoryPhase.MEETING_THE_MENTOR: "Someone who understands the burden offers hard truths, not comfort",
        StoryPhase.CROSSING_THE_THRESHOLD: "Not a leap of faith but a grudging acceptance — someone has to do this",
        StoryPhase.TESTS_ALLIES_ENEMIES: "Challenges faced with competence, not enthusiasm — proving capability despite reluctance",
        StoryPhase.APPROACH_TO_INMOST_CAVE: "Dread builds — this was never wanted, but there's no one else",
        StoryPhase.ORDEAL: "The crisis demands action despite every instinct to flee",
        StoryPhase.REWARD: "Relief, not triumph — the job is done, but at what personal cost?",
        StoryPhase.THE_ROAD_BACK: "The pull of normal life grows stronger with every step",
        StoryPhase.RESURRECTION: "One final demand — the last thing standing between duty and freedom",
        StoryPhase.RETURN_WITH_ELIXIR: "Return to the life they wanted, forever changed by what duty demanded",
    },
    "everyman_rising": {
        StoryPhase.ORDINARY_WORLD: "An ordinary person in an ordinary life — unremarkable by anyone's measure",
        StoryPhase.CALL_TO_ADVENTURE: "Circumstances thrust an unlikely candidate into an impossible situation",
        StoryPhase.REFUSAL_OF_THE_CALL: "Self-doubt speaks loudly — surely someone more qualified should handle this",
        StoryPhase.MEETING_THE_MENTOR: "An unexpected source of belief — someone who sees potential others miss",
        StoryPhase.CROSSING_THE_THRESHOLD: "A deep breath and a first step — faking confidence until it becomes real",
        StoryPhase.TESTS_ALLIES_ENEMIES: "Each small victory builds something new — competence that surprises even them",
        StoryPhase.APPROACH_TO_INMOST_CAVE: "The challenge ahead seems impossible — but so did everything before this",
        StoryPhase.ORDEAL: "The moment that proves ordinary people can do extraordinary things",
        StoryPhase.REWARD: "The look on everyone's face — they didn't expect this, and neither did we",
        StoryPhase.THE_ROAD_BACK: "Carrying hard-won confidence into a world that still underestimates",
        StoryPhase.RESURRECTION: "One final challenge that demands everything learned along the way",
        StoryPhase.RETURN_WITH_ELIXIR: "Return having earned respect — no longer underestimated, no longer ordinary",
    },
    "anti_hero": {
        StoryPhase.ORDINARY_WORLD: "Life on their own terms — messy, pragmatic, and nobody's business",
        StoryPhase.CALL_TO_ADVENTURE: "An opportunity or threat that aligns with self-interest — for now",
        StoryPhase.REFUSAL_OF_THE_CALL: "Weighing the angles — what's in it for them, and what's the catch?",
        StoryPhase.MEETING_THE_MENTOR: "An uneasy alliance with someone who has what they need",
        StoryPhase.CROSSING_THE_THRESHOLD: "Committing to the play — not out of nobility, but necessity",
        StoryPhase.TESTS_ALLIES_ENEMIES: "Trust is earned the hard way — and betrayal is always on the table",
        StoryPhase.APPROACH_TO_INMOST_CAVE: "Planning the approach with pragmatic calculation, not heroic resolve",
        StoryPhase.ORDEAL: "The situation demands a hard choice — principles or survival",
        StoryPhase.REWARD: "Taking what's owed — no apologies, no ceremony",
        StoryPhase.THE_ROAD_BACK: "Consequences catch up — every shortcut has a price",
        StoryPhase.RESURRECTION: "The moment that reveals what actually matters underneath the cynicism",
        StoryPhase.RETURN_WITH_ELIXIR: "Moving on, scars and all — changed in ways they'd never admit",
    },
    "redemption": {
        StoryPhase.ORDINARY_WORLD: "Living with the weight of past mistakes — a life built on atonement",
        StoryPhase.CALL_TO_ADVENTURE: "A chance to make things right — or at least to try",
        StoryPhase.REFUSAL_OF_THE_CALL: "The fear of failing again, of making things worse like last time",
        StoryPhase.MEETING_THE_MENTOR: "Someone who offers trust despite knowing the past — cautious hope",
        StoryPhase.CROSSING_THE_THRESHOLD: "Choosing to face the world again instead of hiding from what was done",
        StoryPhase.TESTS_ALLIES_ENEMIES: "Proving change is real — some believe it, many don't, all are watching",
        StoryPhase.APPROACH_TO_INMOST_CAVE: "Approaching the thing most connected to past sins — full circle",
        StoryPhase.ORDEAL: "Confronting the consequences of who they used to be",
        StoryPhase.REWARD: "Not forgiveness — something harder: the beginning of self-forgiveness",
        StoryPhase.THE_ROAD_BACK: "The past doesn't erase, but the path forward becomes clearer",
        StoryPhase.RESURRECTION: "The choice between old patterns and the person they're becoming",
        StoryPhase.RETURN_WITH_ELIXIR: "Peace earned, not given — the past remains, but it no longer defines",
    },
}


# =============================================================================
# ARC-ADAPTED PHASE GUIDANCE
# =============================================================================
# These replace StoryPhaseManager.get_phase_guidance() when preferences are active.

ARC_GUIDANCE: Dict[str, Dict[StoryPhase, str]] = {
    "chosen_one": {
        StoryPhase.ORDINARY_WORLD: (
            "Establish the protagonist's normal world. Show their daily life, "
            "relationships, and what they have to lose. Hint at untapped potential. Create empathy."
        ),
        StoryPhase.CALL_TO_ADVENTURE: (
            "Present a challenge that feels personally destined. This could be a prophecy, "
            "a unique talent awakening, or a crisis only they can address. Make it compelling."
        ),
        StoryPhase.REFUSAL_OF_THE_CALL: (
            "Allow the protagonist to feel the weight of destiny. The burden is real — "
            "show that accepting this path means sacrificing the life they knew."
        ),
        StoryPhase.MEETING_THE_MENTOR: (
            "Introduce a guide who recognizes the protagonist's potential. Provide wisdom, "
            "tools, or training that unlocks ability. The mentor sees what others don't."
        ),
        StoryPhase.CROSSING_THE_THRESHOLD: (
            "Mark the point of no return. The protagonist accepts their calling "
            "and steps into the larger world. This should feel momentous."
        ),
        StoryPhase.TESTS_ALLIES_ENEMIES: (
            "Present challenges that test the protagonist's growing abilities. "
            "Build the world of the adventure. Allies rally to the cause."
        ),
        StoryPhase.APPROACH_TO_INMOST_CAVE: (
            "Build tension as the protagonist approaches their defining challenge. "
            "This is destiny converging — preparation meets inevitability."
        ),
        StoryPhase.ORDEAL: (
            "The climactic challenge the protagonist was born to face. Maximum stakes. "
            "This should feel like a death-and-rebirth moment — total transformation through crisis."
        ),
        StoryPhase.REWARD: (
            "Celebrate the victory. The prophecy is fulfilled, the power is claimed. "
            "But hint at remaining complications — responsibility follows power."
        ),
        StoryPhase.THE_ROAD_BACK: (
            "Begin the return with the weight of achievement. The protagonist may be "
            "pursued or face consequences of their new power. The world has changed."
        ),
        StoryPhase.RESURRECTION: (
            "A final test that requires everything the protagonist has become. "
            "This is the ultimate proof of transformation and worthiness."
        ),
        StoryPhase.RETURN_WITH_ELIXIR: (
            "Bring the journey full circle. The protagonist returns as the person destiny "
            "intended, bearing wisdom or gifts. Close the narrative with earned grandeur."
        ),
    },
    "reluctant_hero": {
        StoryPhase.ORDINARY_WORLD: (
            "Show a life the protagonist has worked to build — quiet, stable, intentionally "
            "unremarkable. They've earned this peace and have no interest in losing it."
        ),
        StoryPhase.CALL_TO_ADVENTURE: (
            "The disruption should feel unwelcome and unavoidable. Not a glorious quest — "
            "a problem that won't go away. Make the protagonist's irritation feel justified."
        ),
        StoryPhase.REFUSAL_OF_THE_CALL: (
            "Give the protagonist GOOD reasons to refuse. They're not cowardly — they're "
            "practical. Someone else should handle this. Let their reluctance feel earned."
        ),
        StoryPhase.MEETING_THE_MENTOR: (
            "The guide should speak to duty, not glory. No inspirational speeches — "
            "hard truths about why this person, why now, and what happens if they don't act."
        ),
        StoryPhase.CROSSING_THE_THRESHOLD: (
            "Not a dramatic charge but a resigned sigh. They're doing this because someone "
            "has to, not because they want to. The commitment is grudging but real."
        ),
        StoryPhase.TESTS_ALLIES_ENEMIES: (
            "Show competence despite reluctance. They're good at this even if they hate it. "
            "Allies are drawn to their honesty about not wanting to be here."
        ),
        StoryPhase.APPROACH_TO_INMOST_CAVE: (
            "Build dread, not excitement. Every step closer is one step further from "
            "the life they want. But they push forward because no one else will."
        ),
        StoryPhase.ORDEAL: (
            "The crisis forces action that goes against every instinct. Not a heroic charge — "
            "a desperate necessity. Let the protagonist's frustration and fear fuel their resolve."
        ),
        StoryPhase.REWARD: (
            "Relief, not celebration. The immediate crisis is over. Allow a moment of "
            "'can I go home now?' before the reality of remaining complications sets in."
        ),
        StoryPhase.THE_ROAD_BACK: (
            "The pull of home is overwhelming. Every delay on the return feels like "
            "salt in a wound. New dangers mean more time away from the life they chose."
        ),
        StoryPhase.RESURRECTION: (
            "One final demand on someone who has given everything they didn't want to give. "
            "The choice between freedom and one last act of duty."
        ),
        StoryPhase.RETURN_WITH_ELIXIR: (
            "Return to the quiet life — but it's different now. The protagonist has been changed "
            "by what they did, even if they'd rather forget. Peace, hard-won and bittersweet."
        ),
    },
    "everyman_rising": {
        StoryPhase.ORDINARY_WORLD: (
            "Establish the protagonist as genuinely ordinary. No hidden powers, no secret lineage. "
            "Show them being overlooked, underestimated, or dismissed. Create sympathy through familiarity."
        ),
        StoryPhase.CALL_TO_ADVENTURE: (
            "Circumstances should thrust them in, not destiny. Wrong place, wrong time, or "
            "the only one available. Make it feel accidental, not fated."
        ),
        StoryPhase.REFUSAL_OF_THE_CALL: (
            "Self-doubt is the real enemy. 'I'm nobody' should feel true, not like false modesty. "
            "Let them try to find someone more qualified. There isn't anyone."
        ),
        StoryPhase.MEETING_THE_MENTOR: (
            "The mentor sees something others miss — not destiny, but determination. "
            "Provide practical tools and encouragement, not prophecy."
        ),
        StoryPhase.CROSSING_THE_THRESHOLD: (
            "A deep breath and a first step. Not confidence — courage in the absence of confidence. "
            "Fake it until it becomes real. Every step is a small victory."
        ),
        StoryPhase.TESTS_ALLIES_ENEMIES: (
            "Each challenge should build competence visibly. Small wins compound. "
            "Allies who initially doubted should start to reconsider."
        ),
        StoryPhase.APPROACH_TO_INMOST_CAVE: (
            "The challenge ahead seems impossible — but so did everything before this. "
            "Build on accumulated small victories. The protagonist knows they've come further than anyone expected."
        ),
        StoryPhase.ORDEAL: (
            "The moment that proves ordinary people can do extraordinary things. "
            "Not through special powers but through grit, cleverness, and heart."
        ),
        StoryPhase.REWARD: (
            "The satisfaction of proving doubters wrong. Not just the prize, but the recognition. "
            "They did what no one thought possible. Let the moment breathe."
        ),
        StoryPhase.THE_ROAD_BACK: (
            "Carrying hard-won confidence into a world that still sees the old them. "
            "The gap between who they've become and who others think they are."
        ),
        StoryPhase.RESURRECTION: (
            "A final challenge that demands everything learned — every scrappy trick, "
            "every hard lesson. Show growth by contrast with who they were at the start."
        ),
        StoryPhase.RETURN_WITH_ELIXIR: (
            "Return as someone who earned their place. The world sees them differently now. "
            "Not a hero — something better: proof that anyone can rise."
        ),
    },
    "anti_hero": {
        StoryPhase.ORDINARY_WORLD: (
            "Show a life lived on their own terms — morally flexible, pragmatically successful. "
            "Don't judge their methods. Let the audience understand why they do what they do."
        ),
        StoryPhase.CALL_TO_ADVENTURE: (
            "The hook should appeal to self-interest first. Money, leverage, survival, or revenge. "
            "If there's a noble cause underneath, bury it deep — they'd never admit it."
        ),
        StoryPhase.REFUSAL_OF_THE_CALL: (
            "Not fear but calculation. What's the angle? What's the catch? "
            "Let them negotiate terms, not agonize over morality."
        ),
        StoryPhase.MEETING_THE_MENTOR: (
            "An uneasy alliance with someone who has resources or information they need. "
            "Not a wise sage — a useful contact. Trust is transactional."
        ),
        StoryPhase.CROSSING_THE_THRESHOLD: (
            "Commitment because the alternative is worse, not because it's right. "
            "They're playing an angle, even if the angle evolves later."
        ),
        StoryPhase.TESTS_ALLIES_ENEMIES: (
            "Moral shortcuts should be viable options. Don't punish pragmatism. "
            "Let darker choices have real (sometimes positive) consequences. Trust is earned slowly."
        ),
        StoryPhase.APPROACH_TO_INMOST_CAVE: (
            "Planning with cold pragmatism. No heroic speeches — tactical assessment. "
            "If there's a dirty way that works, it should be on the table."
        ),
        StoryPhase.ORDEAL: (
            "A situation where being clever or ruthless isn't enough. "
            "Something has to give — principles or survival, loyalty or self-preservation."
        ),
        StoryPhase.REWARD: (
            "Taking what's owed without apology. But maybe, quietly, doing "
            "one thing that can't be explained by self-interest."
        ),
        StoryPhase.THE_ROAD_BACK: (
            "Consequences of shortcuts and burned bridges. Every pragmatic choice "
            "has a ledger, and the bill is coming due."
        ),
        StoryPhase.RESURRECTION: (
            "The moment that reveals what actually matters underneath the cynicism. "
            "Not a moral awakening — a choice that shows who they really are when it costs them."
        ),
        StoryPhase.RETURN_WITH_ELIXIR: (
            "No triumphant return. They move on, changed in ways they'd never admit. "
            "Maybe they did something good. They'd deny it if asked."
        ),
    },
    "redemption": {
        StoryPhase.ORDINARY_WORLD: (
            "Show someone living with weight — guilt, shame, or consequence. "
            "Their current life is an attempt to be different, but the past is always close."
        ),
        StoryPhase.CALL_TO_ADVENTURE: (
            "A chance to make amends, or at least to try. The opportunity should connect "
            "to what they did before — this is personal, not random."
        ),
        StoryPhase.REFUSAL_OF_THE_CALL: (
            "The fear of failing AGAIN. Of making things worse, like last time. "
            "Self-doubt rooted in evidence, not insecurity."
        ),
        StoryPhase.MEETING_THE_MENTOR: (
            "Someone who offers trust despite knowing the truth. Not blind faith — "
            "cautious hope. This trust feels fragile and precious."
        ),
        StoryPhase.CROSSING_THE_THRESHOLD: (
            "Choosing to face the world again instead of hiding. Every step forward "
            "is a step toward the thing they're most afraid of — their own past."
        ),
        StoryPhase.TESTS_ALLIES_ENEMIES: (
            "Some people believe in the change, many don't. All are watching. "
            "Let NPCs react to reputation — distrust, suspicion, cautious hope."
        ),
        StoryPhase.APPROACH_TO_INMOST_CAVE: (
            "Approaching something deeply connected to past sins. The worst-case scenario "
            "isn't death — it's becoming who they were before."
        ),
        StoryPhase.ORDEAL: (
            "Confronting the direct consequences of past actions. Face-to-face with "
            "the damage done. This is personal reckoning, not just danger."
        ),
        StoryPhase.REWARD: (
            "Not forgiveness — something harder. The first glimmer of self-forgiveness. "
            "Others may start to believe the change is real."
        ),
        StoryPhase.THE_ROAD_BACK: (
            "The past doesn't erase. Old enemies, old debts, old patterns try to pull them back. "
            "The road forward is a choice that must be made again and again."
        ),
        StoryPhase.RESURRECTION: (
            "The ultimate test — a situation where old methods would be easier. "
            "The choice between the person they were and the person they're becoming."
        ),
        StoryPhase.RETURN_WITH_ELIXIR: (
            "Peace earned, not given. The past remains but no longer defines them. "
            "Not a clean slate — a page turned. That's enough."
        ),
    },
}


# =============================================================================
# LETHALITY-ADJUSTED TENSION TARGETS
# =============================================================================
# Overrides StoryPhase.expected_tension based on lethality preference.
# Only phases with meaningful differences are included; others use defaults.

LETHALITY_TENSION_OVERRIDES: Dict[str, Dict[StoryPhase, float]] = {
    "plot_armor": {
        # Emotional crises, not mortal danger
        StoryPhase.ORDEAL: 0.70,
        StoryPhase.RESURRECTION: 0.65,
        StoryPhase.APPROACH_TO_INMOST_CAVE: 0.55,
        StoryPhase.THE_ROAD_BACK: 0.45,
    },
    "forgiving": {
        StoryPhase.ORDEAL: 0.80,
        StoryPhase.RESURRECTION: 0.75,
    },
    # "balanced" uses defaults (no overrides needed)
    "dangerous": {
        StoryPhase.TESTS_ALLIES_ENEMIES: 0.65,
        StoryPhase.APPROACH_TO_INMOST_CAVE: 0.80,
        StoryPhase.THE_ROAD_BACK: 0.70,
    },
    "brutal": {
        StoryPhase.ORDINARY_WORLD: 0.30,  # Even the start feels unsafe
        StoryPhase.TESTS_ALLIES_ENEMIES: 0.70,
        StoryPhase.APPROACH_TO_INMOST_CAVE: 0.85,
        StoryPhase.ORDEAL: 1.0,
        StoryPhase.THE_ROAD_BACK: 0.75,
        StoryPhase.RESURRECTION: 0.95,
    },
}


# =============================================================================
# LETHALITY-ADAPTED PACING GUIDANCE
# =============================================================================
# Phase-specific pacing overrides when lethality preference changes the stakes.

LETHALITY_PACING: Dict[str, Dict[StoryPhase, str]] = {
    "plot_armor": {
        StoryPhase.ORDEAL: (
            "The Ordeal should feel like an emotional crisis — high personal stakes, "
            "but the protagonist will survive. Focus on what they might LOSE (relationships, "
            "beliefs, allies) rather than their life."
        ),
        StoryPhase.RESURRECTION: (
            "The final test demands emotional sacrifice, not physical survival. "
            "What are they willing to give up to succeed?"
        ),
    },
    "forgiving": {
        StoryPhase.ORDEAL: (
            "Real danger exists but the world is fair. Smart choices are rewarded, "
            "recklessness has consequences, but failure teaches rather than kills."
        ),
    },
    "dangerous": {
        StoryPhase.ORDEAL: (
            "The Ordeal should feel genuinely threatening. Bad decisions here have "
            "severe, permanent consequences. The protagonist should feel the weight of every choice."
        ),
        StoryPhase.TESTS_ALLIES_ENEMIES: (
            "Every challenge carries real risk. Allies can be lost permanently. "
            "Make the player feel the cost of combat and confrontation."
        ),
    },
    "brutal": {
        StoryPhase.ORDEAL: (
            "The Ordeal could genuinely end everything. Death is a real possibility, "
            "not dramatic license. Make the player feel that survival itself is victory."
        ),
        StoryPhase.ORDINARY_WORLD: (
            "Even the ordinary world is harsh. Resources are scarce, safety is fragile. "
            "Establish early that this world doesn't protect anyone."
        ),
        StoryPhase.TESTS_ALLIES_ENEMIES: (
            "Every fight could be fatal. Allies die. Enemies are lethal. "
            "Survival requires caution, preparation, and hard choices about when to engage."
        ),
    },
}


# =============================================================================
# PUBLIC FUNCTIONS
# =============================================================================

def get_adapted_description(
    phase: StoryPhase,
    arc_type: Optional[str] = None,
) -> str:
    """
    Get a phase description adapted to the player's protagonist arc.

    Args:
        phase: Current story phase
        arc_type: Player's chosen arc (chosen_one, reluctant_hero, etc.)

    Returns:
        Arc-appropriate phase description. Falls back to default if arc unknown.
    """
    if arc_type and arc_type in ARC_DESCRIPTIONS:
        return ARC_DESCRIPTIONS[arc_type].get(phase, phase.description)
    return phase.description


def get_adapted_guidance(
    phase: StoryPhase,
    arc_type: Optional[str] = None,
) -> str:
    """
    Get phase guidance adapted to the player's protagonist arc.

    Args:
        phase: Current story phase
        arc_type: Player's chosen arc

    Returns:
        Arc-appropriate guidance text for the DM.
    """
    if arc_type and arc_type in ARC_GUIDANCE:
        return ARC_GUIDANCE[arc_type].get(phase, "Continue the narrative.")
    # Default: return None to signal caller should use original guidance
    return ""


def get_adapted_tension_target(
    phase: StoryPhase,
    lethality: Optional[str] = None,
) -> float:
    """
    Get the expected tension target adjusted for lethality preference.

    Args:
        phase: Current story phase
        lethality: Player's lethality preference

    Returns:
        Adjusted tension target (0.0-1.0). Falls back to phase default.
    """
    if lethality and lethality in LETHALITY_TENSION_OVERRIDES:
        overrides = LETHALITY_TENSION_OVERRIDES[lethality]
        if phase in overrides:
            return overrides[phase]
    return phase.expected_tension


def get_adapted_pacing_guidance(
    phase: StoryPhase,
    lethality: Optional[str] = None,
) -> Optional[str]:
    """
    Get lethality-adapted pacing guidance for a specific phase.

    Args:
        phase: Current story phase
        lethality: Player's lethality preference

    Returns:
        Adapted pacing guidance, or None if no override exists.
    """
    if lethality and lethality in LETHALITY_PACING:
        return LETHALITY_PACING[lethality].get(phase)
    return None
