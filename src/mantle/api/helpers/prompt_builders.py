# src/mantle/api/helpers/prompt_builders.py
"""
DM Prompt Building Helpers

Functions that construct various context sections for the DM system prompt.
Extracted from game_routes.py for better organization.
"""

from typing import Dict, Any, Optional


def get_story_scope_guidance(scope: str, turn_count: int, max_turns: int) -> str:
    """
    Get pacing guidance based on story scope and current progress.

    IMPORTANT: Different scopes use DIFFERENT narrative structures:
    - One-shots: Compressed 5-act (Hook -> Complication -> Rising -> Climax -> Resolution)
    - Campaigns: Full Hero's Journey (12 stages across many sessions)
    """
    if max_turns <= 0:
        max_turns = 1000  # Campaign mode - no real limit

    progress = turn_count / max_turns if max_turns > 0 else 0

    # CAMPAIGNS: Subtle, principle-based guidance (not prescriptive)
    if scope == "campaign":
        # Early campaign: focus on foundation, not structure
        if turn_count < 20:
            return f"""
=== CAMPAIGN (Turn {turn_count}) ===
Let them LIVE in this world first. No rush.
- Who are they? What do they care about? Who do they know?
- Small moments reveal character better than grand events
- Plant seeds casually - a name mentioned, a detail noticed
- Trust that significance will emerge from play"""
        elif turn_count < 50:
            return f"""
=== CAMPAIGN (Turn {turn_count}) ===
The world is taking shape through their choices.
- Consequences ripple from earlier decisions
- Recurring faces, familiar places, building history
- Threads can dangle - not everything resolves quickly
- Let their interests guide what becomes important"""
        else:
            return f"""
=== CAMPAIGN (Turn {turn_count}) ===
A story is emerging from the accumulated choices.
- Honor what came before - callbacks reward attention
- Subplots can simmer, main threads can breathe
- Not every session needs crisis - quiet moments matter
- The shape of their journey reveals itself through play"""

    # ONE-SHOTS: Compressed structure, immediate engagement
    if scope == "one_shot":
        if progress < 0.10:
            phase = "HOOK"
            guidance = "Drop them into the moment. Character through action, not backstory. Something immediately interesting."
        elif progress < 0.25:
            phase = "COMPLICATION"
            guidance = "The situation demands response. A choice, a problem, a discovery. Personal stakes, clear and present."
        elif progress < 0.60:
            phase = "RISING TENSION"
            guidance = "Consequences compound. Choices matter. Tension builds through what they DO, not destiny."
        elif progress < 0.85:
            phase = "CLIMAX"
            guidance = "The confrontation. Everything comes to a head. This is what it's all been building toward."
        else:
            phase = "RESOLUTION"
            guidance = "Aftermath and change. Show who they've become. END with '**THE END**' when the story is complete."

        return f"""
=== STORY: ONE-SHOT ({turn_count}/{max_turns} turns, {progress:.0%}) ===
Phase: {phase}
{guidance}
REMEMBER: One-shots are COMPLETE stories. No sequel-baiting. Satisfying endings."""

    # SHORT/MEDIUM: Slightly expanded structure
    if scope in ("short", "medium"):
        if progress < 0.12:
            phase = "OPENING"
            guidance = "Establish character and world through lived experience. Who they are before anything changes."
        elif progress < 0.25:
            phase = "INCITING"
            guidance = "Something disrupts the ordinary. A choice to engage."
        elif progress < 0.50:
            phase = "RISING"
            guidance = "Complications. Allies and enemies. Stakes rise through consequence."
        elif progress < 0.75:
            phase = "CRISIS"
            guidance = "A major turning point. Something changes that can't be undone."
        elif progress < 0.90:
            phase = "CLIMAX"
            guidance = "The confrontation approaches and peaks."
        else:
            phase = "RESOLUTION"
            guidance = "Aftermath. Change. Consider ending with '**THE END**'."

        label = "SHORT STORY" if scope == "short" else "MEDIUM ADVENTURE"
        return f"""
=== STORY: {label} ({turn_count}/{max_turns} turns, {progress:.0%}) ===
Phase: {phase}
{guidance}"""

    # LONG: More room for development, closer to campaign pacing
    if scope == "long":
        if progress < 0.10:
            phase = "ORDINARY WORLD"
            guidance = "Establish who they are, what they want, what's missing."
        elif progress < 0.20:
            phase = "CALL"
            guidance = "Something beckons. A problem, opportunity, or discovery."
        elif progress < 0.35:
            phase = "THRESHOLD"
            guidance = "They commit. Cross into the unknown. No going back."
        elif progress < 0.50:
            phase = "TESTS & ALLIES"
            guidance = "Challenges, new relationships, learning the rules of this new world."
        elif progress < 0.65:
            phase = "ORDEAL"
            guidance = "The major crisis. Face what they fear. Transformation."
        elif progress < 0.80:
            phase = "REWARD & ROAD BACK"
            guidance = "They've changed. Now they must return with what they've gained."
        elif progress < 0.90:
            phase = "RESURRECTION"
            guidance = "Final test. Everything on the line. Who have they become?"
        else:
            phase = "RETURN"
            guidance = "Resolution. The world changed, or they have. Consider '**THE END**'."

        return f"""
=== STORY: EXTENDED ({turn_count}/{max_turns} turns, {progress:.0%}) ===
Phase: {phase}
{guidance}"""

    # Fallback
    return f"Turn: {turn_count}/{max_turns}"


def get_genre_guidance(genre: str) -> Dict[str, str]:
    """
    Get narrative guidance specific to each genre.

    IMPORTANT: 'magic' field explicitly defines whether supernatural elements exist.
    - "yes": Magic/supernatural is core to the genre
    - "no": Grounded in reality - NO magic, NO supernatural (enforce strictly)
    - "optional": Can include supernatural horror OR psychological horror
    """
    guidance = {
        "fantasy": {
            "elements": "magic, mystical creatures, wonder, the impossible made real",
            "hooks": "something unexpected that demands attention - a person, an event, a discovery, or a problem",
            "voice": "evocative and wondrous, grounded in character rather than destiny",
            "magic": "yes",
        },
        "romance": {
            "elements": "emotional tension, meaningful glances, past connections, unspoken feelings",
            "hooks": "a moment of connection or tension with another person",
            "voice": "warm and intimate, focused on feelings and connections between people",
            "magic": "no",
        },
        "mystery": {
            "elements": "clues, secrets, suspicious characters, hidden motives, puzzles",
            "hooks": "something that feels wrong or out of place",
            "voice": "atmospheric and intriguing, building tension through details",
            "magic": "no",
        },
        "horror": {
            "elements": "dread, the unknown, isolation, things not quite right, building unease",
            "hooks": "a subtle wrongness that grows more unsettling",
            "voice": "unsettling and atmospheric, letting imagination fill the shadows",
            "magic": "optional",
        },
        "adventure": {
            "elements": "exploration, discovery, challenges, exotic locations, bold action",
            "hooks": "an opportunity or challenge that beckons",
            "voice": "exciting and propulsive, full of momentum and possibility",
            "magic": "no",
        },
        "drama": {
            "elements": "complex relationships, moral dilemmas, personal stakes, family secrets",
            "hooks": "a moment of emotional weight or decision",
            "voice": "emotionally resonant, focused on human complexity and growth",
            "magic": "no",
        },
        "urban_fantasy": {
            "elements": "hidden magic in modern cities, secret societies, mundane meets magical, parallel supernatural world, magical creatures disguised among humans",
            "hooks": "the veil between worlds thinning, a magical intrusion into normal life, or discovering the truth behind the mundane",
            "voice": "grounded in familiar reality but threaded with wonder and danger, where the magical world exists alongside our own",
            "magic": "yes",
        },
        "gothic": {
            "elements": "vampires, werewolves, mages, supernatural politics, personal horror, the beast within, ancient conspiracies, tragic immortality",
            "hooks": "a threat to one's humanity, a breach in the supernatural order, or the eternal struggle between monster and man",
            "voice": "dark and atmospheric, where monsters are the protagonists wrestling with their nature, and power comes at a terrible cost",
            "magic": "yes",
        },
    }
    return guidance.get(genre, guidance["fantasy"])


def get_style_instructions(style: str) -> str:
    """Get storytelling instructions based on user's preferred style."""
    styles = {
        "guided": """
Provide clear narrative direction with vivid description. Help the reader feel
oriented in the world. End scenes at natural pause points, letting the reader
decide what to do next. NEVER suggest specific choices or ask questions.""",
        "freeform": """
Create a rich sandbox. Describe the environment with enough detail to spark
curiosity. Let the reader discover what catches their interest. End naturally
without prompting. NEVER suggest specific choices or ask questions.""",
        "collaborative": """
Build the story together through natural narrative flow. Describe the world
vividly and let moments breathe. End at natural pause points, trusting the
reader to respond. NEVER suggest specific choices or ask direct questions.""",
    }
    return styles.get(style, styles["guided"])


def get_protagonist_arc_guidance(arc: Optional[str]) -> str:
    """Get narrative guidance for the player's chosen protagonist arc."""
    if not arc:
        return ""
    arcs = {
        "chosen_one": """PROTAGONIST ARC - CHOSEN ONE:
The protagonist is marked by destiny. Lean into moments of revelation, growing power, and the weight of prophecy.
NPCs should sense something special about them. Challenges should feel like tests of worthiness.""",
        "reluctant_hero": """PROTAGONIST ARC - RELUCTANT HERO:
The protagonist didn't ask for this. They're pulled into events. Honor their resistance — let them complain, hesitate, try to walk away.
But make the reasons to stay more compelling than the reasons to leave. Growth comes through acceptance.""",
        "everyman_rising": """PROTAGONIST ARC - EVERYMAN RISING:
The protagonist is ordinary. No special bloodline, no prophecy. They grow through effort, wit, and determination.
Early challenges should feel barely manageable. Victories should feel earned, not destined. NPCs should initially underestimate them.""",
        "anti_hero": """PROTAGONIST ARC - ANTI-HERO:
The protagonist's methods are unconventional. They may lie, steal, or manipulate for what they see as right.
Present moral shortcuts as viable options. Don't punish pragmatism. Let their darker choices have real (sometimes positive) consequences.""",
        "redemption": """PROTAGONIST ARC - REDEMPTION:
The protagonist carries guilt. They're trying to be better. Weave in reminders of their past without being heavy-handed.
Offer chances to make different choices than before. Let NPCs react to their reputation — some with distrust, some with cautious hope.""",
    }
    return arcs.get(arc, "")


def get_lethality_guidance(lethality: Optional[str]) -> str:
    """Get danger-level guidance for the DM."""
    if not lethality:
        return ""
    levels = {
        "plot_armor": """LETHALITY - PLOT ARMOR:
The protagonist will survive. Injuries are dramatic but never fatal. Focus on emotional and narrative stakes rather than mortal danger.
Bad outcomes are setbacks, captures, losses of allies or resources — never death.""",
        "forgiving": """LETHALITY - FORGIVING:
The world is dangerous but fair. Death is very unlikely unless the player makes truly reckless choices.
Wounds heal, failures teach, and there are usually second chances.""",
        "balanced": """LETHALITY - BALANCED:
Real danger exists but is proportional to the risks taken. Smart play is rewarded, recklessness has consequences.
Death is possible in extreme situations but not the default outcome of failure.""",
        "dangerous": """LETHALITY - DANGEROUS:
This world is genuinely threatening. Combat can maim or kill. Bad decisions have severe, sometimes permanent consequences.
The player should feel the weight of choosing to fight vs. flee, prepare vs. rush in.""",
        "brutal": """LETHALITY - BRUTAL:
Death is always close. Every fight could be the last. Resources are scarce, healing is limited.
Survival itself is an achievement. Make the player feel the cost of every wound, every risk taken.""",
    }
    return levels.get(lethality, "")


def get_moral_complexity_guidance(complexity: Optional[str]) -> str:
    """Get moral complexity guidance for the DM."""
    if not complexity:
        return ""
    levels = {
        "clear": """MORALITY - CLEAR GOOD VS EVIL:
Villains are villainous, heroes are heroic. The right choice is recognizable. Evil looks evil, good looks good.
Let the player feel righteous. Don't muddy the waters with moral ambiguity.""",
        "mostly_clear": """MORALITY - MOSTLY CLEAR:
Good and evil are real, but individuals can surprise you. A bandit might have a family. A noble might be corrupt.
The right path is usually clear, but sometimes complicated by circumstance.""",
        "gray_areas": """MORALITY - GRAY AREAS:
No side is purely right. Factions have legitimate grievances. Solutions involve trade-offs.
Present dilemmas where reasonable people would disagree. Let the player define what 'right' means.""",
        "ambiguous": """MORALITY - MORALLY AMBIGUOUS:
Everyone believes they're justified. Power corrupts, idealism fails, and good intentions lead to terrible outcomes.
Challenge the player's assumptions. Make them question their choices after the fact.""",
        "no_clear": """MORALITY - NO CLEAR MORALITY:
Morality is a construct. Survival, power, loyalty, love — these drive people, not good vs evil.
Present choices in terms of practical consequences, not moral weight. There are no heroes, only survivors.""",
    }
    return levels.get(complexity, "")


def build_storytelling_preferences_context(
    session: Dict[str, Any],
    lore_bases: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build the full storytelling preferences prompt section, including world/player blending.

    Uses description-inferred preferences as fallbacks when player hasn't
    explicitly set a preference (from character concept analysis).

    Args:
        session: The session data dictionary
        lore_bases: Optional dict of lore bases for world characteristic lookup
    """
    protagonist_arc = session.get("protagonist_arc") or session.get("description_inferred_arc")
    lethality_pref = session.get("lethality_preference") or session.get("description_inferred_lethality")
    moral_pref = session.get("moral_complexity_preference") or session.get("description_inferred_morality")

    # Get individual guidance blocks
    arc_guidance = get_protagonist_arc_guidance(protagonist_arc)
    lethality_guidance = get_lethality_guidance(lethality_pref)
    moral_guidance = get_moral_complexity_guidance(moral_pref)

    if not any([arc_guidance, lethality_guidance, moral_guidance]):
        return ""

    # Load world characteristics for blending
    world_id = session.get("world_id")
    world_chars = {}
    if world_id and lore_bases and world_id in lore_bases:
        world_chars = lore_bases[world_id].get("world_characteristics", {})

    # Build blending notes where player differs from world
    blending_notes = []

    tone_val = session.get("tone_preference") or session.get("description_inferred_tone")
    if tone_val and world_chars.get("tone"):
        world_tone = world_chars["tone"].lower()
        if tone_val.lower() != world_tone:
            blending_notes.append(
                f"Tone: World baseline is '{world_chars['tone']}', but player prefers '{tone_val}'. "
                f"Honor both — maintain the world's established feel while steering toward the player's preference."
            )

    if lethality_pref and world_chars.get("lethality"):
        lethality_labels = {"plot_armor": "Plot Armor", "forgiving": "Forgiving", "balanced": "Balanced", "dangerous": "Dangerous", "brutal": "Brutal"}
        player_label = lethality_labels.get(lethality_pref, lethality_pref)
        if player_label.lower() != world_chars["lethality"].lower():
            blending_notes.append(
                f"Lethality: World baseline is '{world_chars['lethality']}', but player prefers '{player_label}'. "
                f"Honor both — maintain the world's danger profile while adjusting toward the player's comfort."
            )

    if moral_pref and world_chars.get("moral_complexity"):
        moral_labels = {"clear": "Clear Good vs Evil", "mostly_clear": "Mostly Clear", "gray_areas": "Gray Areas", "ambiguous": "Morally Ambiguous", "no_clear": "No Clear Morality"}
        player_label = moral_labels.get(moral_pref, moral_pref)
        if player_label.lower() != world_chars["moral_complexity"].lower():
            blending_notes.append(
                f"Moral Complexity: World baseline is '{world_chars['moral_complexity']}', but player prefers '{player_label}'. "
                f"Honor both — use the world's moral framework while emphasizing the player's preferred complexity."
            )

    # Assemble the full section
    parts = ["=== PLAYER STORYTELLING PREFERENCES ==="]
    if arc_guidance:
        parts.append(arc_guidance)
    if lethality_guidance:
        parts.append(lethality_guidance)
    if moral_guidance:
        parts.append(moral_guidance)
    if blending_notes:
        parts.append("=== PREFERENCE BLENDING ===")
        parts.extend(blending_notes)

    return "\n".join(parts)


def get_guidance_instruction(needs_guidance: bool) -> str:
    """Get optional story guidance instruction when player seems stuck."""
    if needs_guidance:
        return """
GUIDANCE MODE: The player seems uncertain about what to do next. Without railroading:
- Weave a subtle hint into the narrative about possible directions
- Have an NPC mention something relevant, or describe an environmental detail that suggests action
- Keep it natural - the player should feel they discovered the option, not that it was handed to them
Example: Instead of "You should go to the tavern", use "The distant sound of laughter drifts from the tavern's open windows"
"""
    return ""
