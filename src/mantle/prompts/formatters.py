"""
Compact Formatters for DM Prompt Sections.

Each formatter compresses verbose context into token-efficient format.
Uses consistent conventions:
- Pipe (|) for inline lists
- Arrow (→) for relationships/causation
- Brackets [] for metadata
- Abbreviations: HP, AC, STR/DEX/CON/INT/WIS/CHA, PC/NPC

Typical savings: 50-60% token reduction per section.
"""

from typing import List, Dict, Optional, Any


# =============================================================================
# CHARACTER CONTEXT
# =============================================================================

def format_character_compact(
    name: str,
    class_name: str,
    level: int,
    hp: int,
    max_hp: int,
    ac: int,
    skills: List[str] = None,
    gear: List[str] = None,
    abilities: List[str] = None,
    conditions: List[str] = None,
) -> str:
    """
    Format character context compactly.

    Before (~150 tokens):
        You are controlling a character named Kira Shadowmend, a level 3 Shadow Walker.
        Current hit points: 18 out of 24 maximum hit points...

    After (~60 tokens):
        PC: Kira Shadowmend (Shadow Walker 3)
        HP: 18/24 | AC: 14 | Skills: Stealth, Deception, Acrobatics
        Gear: rapier, leather armor, thieves' tools
    """
    lines = [f"PC: {name} ({class_name} {level})"]

    # Stats line
    stats_parts = [f"HP: {hp}/{max_hp}", f"AC: {ac}"]
    if skills:
        stats_parts.append(f"Skills: {', '.join(skills[:4])}")
    lines.append(" | ".join(stats_parts))

    # Gear line (if present)
    if gear:
        lines.append(f"Gear: {', '.join(gear[:5])}")

    # Abilities (if notable)
    if abilities:
        lines.append(f"Abilities: {', '.join(abilities[:3])}")

    # Conditions (if any)
    if conditions:
        lines.append(f"Conditions: {', '.join(conditions)}")

    return "\n".join(lines)


# =============================================================================
# NPC CONTEXT (PERSONALITY + STATS)
# =============================================================================

def format_npc_compact(
    name: str,
    dialogue_style: str = "",
    threat_level: str = "trivial",
    attack_style: str = "non-combatant",
    hp: int = 0,
    notables: List[str] = None,
) -> str:
    """
    Format NPC context compactly.

    Before (~100 tokens per NPC):
        CAPTAIN VARN
        Captain Varn has a personality that is confident and assured...

    After (~40 tokens per NPC):
        CAPTAIN VARN | melee, HP 45, moderate | STR 15, CON 14
        Style: confident, precise
    """
    parts = [name.upper()]

    # Combat info (skip for trivial/non-combatant)
    if threat_level not in ["trivial", "unknown"] and attack_style != "non-combatant":
        combat = f"{attack_style}, HP {hp}, {threat_level}"
        parts.append(combat)
        if notables:
            parts.append(", ".join(notables))
    else:
        parts.append("non-combatant")

    result = " | ".join(parts)

    # Add dialogue style on second line if present
    if dialogue_style and dialogue_style != "neutral conversational style":
        # Shorten common patterns
        style = dialogue_style.replace(" and ", ", ").replace("; ", ", ")
        result += f"\nStyle: {style}"

    return result


def format_npcs_section(npcs: List[Dict[str, Any]]) -> str:
    """Format multiple NPCs as a compact section."""
    if not npcs:
        return ""

    npc_blocks = []
    for npc in npcs:
        block = format_npc_compact(
            name=npc.get("name", "Unknown"),
            dialogue_style=npc.get("dialogue_style", ""),
            threat_level=npc.get("stat_threat_level", "trivial"),
            attack_style=npc.get("stat_attack_style", "non-combatant"),
            hp=npc.get("stat_hit_points", 0),
            notables=npc.get("notables", []),
        )
        npc_blocks.append(block)

    return "=== SCENE NPCs ===\n" + "\n".join(npc_blocks)


# =============================================================================
# KNOWLEDGE GRAPH ENTITIES
# =============================================================================

def format_entity_compact(
    name: str,
    description: str,
    knowledge_level: str,
    relationships: List[Dict[str, str]] = None,
) -> str:
    """
    Format knowledge graph entity compactly.

    Before (~80 tokens):
        Entity: Lord Blackwood (Character)
        Description: A cunning noble who secretly controls...
        Knowledge Level: KNOWN to the party
        Relationships: ENEMY_OF the Crown, CONTROLS the Shadow Market

    After (~35 tokens):
        [KNOWN] Lord Blackwood - cunning noble, secretly runs thieves' guild
          → ENEMY_OF Crown | CONTROLS Shadow Market
    """
    # Truncate description to 60 chars
    short_desc = description[:60] + "..." if len(description) > 60 else description

    result = f"[{knowledge_level}] {name} - {short_desc}"

    # Add relationships (max 2)
    if relationships:
        rels = " | ".join([
            f"{r.get('type', 'RELATED_TO')} {r.get('target', 'Unknown')}"
            for r in relationships[:2]
        ])
        result += f"\n  → {rels}"

    return result


def format_graph_section(
    known: List[Dict],
    rumored: List[Dict] = None,
    secret: List[Dict] = None,
    max_per_tier: int = 3,
) -> str:
    """Format knowledge graph as compact section."""
    lines = ["=== WORLD KNOWLEDGE ==="]

    for entities, label in [(known, "KNOWN"), (rumored or [], "RUMORED"), (secret or [], "SECRET")]:
        for entity in entities[:max_per_tier]:
            lines.append(format_entity_compact(
                name=entity.get("name", "Unknown"),
                description=entity.get("description", ""),
                knowledge_level=label,
                relationships=entity.get("relationships", []),
            ))

    return "\n".join(lines) if len(lines) > 1 else ""


# =============================================================================
# HISTORY / CONVERSATION
# =============================================================================

def format_history_turn_compact(
    turn_num: int,
    player_action: str,
    dm_result: str,
) -> str:
    """
    Format single history turn compactly.

    Before (~80 tokens):
        Turn 5:
        Player: I want to carefully search the bookshelf...
        DM: As you run your fingers along the dusty spines...

    After (~40 tokens):
        [5] Search bookshelf → Found hidden compartment: silver key + note
    """
    # Extract key action (first 50 chars or first sentence)
    short_action = player_action[:50].rstrip()
    if len(player_action) > 50:
        short_action += "..."

    # Extract key result (first 80 chars)
    short_result = dm_result[:80].rstrip()
    if len(dm_result) > 80:
        short_result += "..."

    return f"[{turn_num}] {short_action} → {short_result}"


def format_history_section(
    history: List[Dict[str, str]],
    max_turns: int = 10,
) -> str:
    """
    Format conversation history compactly.

    Uses tiered detail:
    - Last 3 turns: More detail (100 chars each)
    - Earlier turns: Brief (60 chars each)
    """
    if not history:
        return ""

    recent = history[-max_turns:]
    lines = ["=== RECENT HISTORY ==="]

    for i, turn in enumerate(recent):
        turn_num = len(history) - len(recent) + i + 1
        player = turn.get("player", turn.get("user", ""))
        dm = turn.get("dm", turn.get("assistant", ""))

        # More detail for recent turns
        is_recent = i >= len(recent) - 3
        action_limit = 100 if is_recent else 60
        result_limit = 150 if is_recent else 80

        short_action = player[:action_limit].rstrip()
        short_result = dm[:result_limit].rstrip()

        if len(player) > action_limit:
            short_action += "..."
        if len(dm) > result_limit:
            short_result += "..."

        lines.append(f"[{turn_num}] {short_action} → {short_result}")

    return "\n".join(lines)


# =============================================================================
# ARC ENGINE CONTEXT
# =============================================================================

def format_arc_compact(
    phase: str,
    tension: float,
    progress: float,
    beat_suggestion: str = "",
) -> str:
    """
    Format arc engine context compactly.

    Before (~100 tokens):
        === STORY STRUCTURE ===
        Current Phase: RISING ACTION (Act 2)
        Tension Level: 0.65 (moderately high)
        Journey Progress: 35% through the story
        Beat Suggestions: Consider introducing a complication...

    After (~25 tokens):
        ARC: Rising Action | Tension: 0.65 | Progress: 35% | Suggest: complication
    """
    parts = [
        f"ARC: {phase}",
        f"Tension: {tension:.2f}",
        f"Progress: {int(progress * 100)}%",
    ]

    if beat_suggestion:
        # Shorten to first word/phrase
        short_beat = beat_suggestion.split(",")[0].split(".")[0][:30]
        parts.append(f"Suggest: {short_beat}")

    return " | ".join(parts)


# =============================================================================
# MEMORY SYSTEM CONTEXT
# =============================================================================

def format_memory_relationship_compact(
    npc_name: str,
    npc_role: str,
    feeling: str,
    reason: str,
    trust_level: str,
) -> str:
    """
    Format memory relationship compactly.

    Before (~60 tokens):
        The bartender Bob feels grateful toward the player...
        Trust level: High (0.8)

    After (~20 tokens):
        Bob (bartender) → grateful (saved daughter) | Trust: HIGH
    """
    return f"{npc_name} ({npc_role}) → {feeling} ({reason}) | Trust: {trust_level}"


def format_memory_section(
    relationships: List[Dict] = None,
    legends: List[Dict] = None,
    active_threads: List[Dict] = None,
    max_items: int = 3,
) -> str:
    """Format memory system context compactly."""
    lines = []

    # Relationships (impressions)
    if relationships:
        lines.append("MEMORY:")
        for rel in relationships[:max_items]:
            lines.append("  " + format_memory_relationship_compact(
                npc_name=rel.get("npc_name", "Unknown"),
                npc_role=rel.get("npc_role", "NPC"),
                feeling=rel.get("feeling", "neutral"),
                reason=rel.get("reason", ""),
                trust_level=rel.get("trust_level", "NEUTRAL"),
            ))

    # Legends (player reputation)
    if legends:
        legend_parts = [f"\"{l.get('title', '')}\"" for l in legends[:2]]
        lines.append(f"REPUTATION: {' | '.join(legend_parts)}")

    # Active threads
    if active_threads:
        thread_parts = [t.get("description", "")[:40] for t in active_threads[:2]]
        lines.append(f"THREADS: {' | '.join(thread_parts)}")

    return "\n".join(lines) if lines else ""


# =============================================================================
# AUDITOR / CONTINUITY WARNINGS
# =============================================================================

def format_warning_compact(
    issue_type: str,
    detail: str,
) -> str:
    """
    Format continuity warning compactly.

    Before (~50 tokens):
        === CONTINUITY WARNING ===
        In the previous turn, you mentioned that Lord Blackwood was at the tavern.
        However, Lord Blackwood was established as being imprisoned...

    After (~20 tokens):
        ⚠️ CONTINUITY: Lord Blackwood is imprisoned (established), not at tavern
    """
    short_detail = detail[:80] if len(detail) > 80 else detail
    return f"⚠️ {issue_type}: {short_detail}"


def format_warnings_section(warnings: List[Dict]) -> str:
    """Format multiple warnings compactly."""
    if not warnings:
        return ""

    lines = [
        format_warning_compact(
            issue_type=w.get("type", "WARNING"),
            detail=w.get("detail", w.get("description", "")),
        )
        for w in warnings[:3]  # Max 3 warnings
    ]
    return "\n".join(lines)


# =============================================================================
# NPC STATE OVERLAY (DEAD/CAPTURED/MISSING)
# =============================================================================

def format_npc_state_compact(states: List[Dict]) -> str:
    """
    Format NPC state overlay compactly.

    Before:
        === NPC STATUS (THIS SESSION) ===
        - Lord Blackwood: DEAD (killed earlier this session)
        CRITICAL: Do NOT include dead/captured NPCs as active participants.

    After:
        ⚠️ NPC STATE: Lord Blackwood=DEAD | Guard=CAPTURED
        (Do not include these NPCs as active participants)
    """
    if not states:
        return ""

    state_parts = []
    for s in states[:5]:  # Max 5
        name = s.get("name", "Unknown")
        status = "DEAD" if s.get("is_dead") else "CAPTURED" if s.get("is_captured") else "MISSING"
        state_parts.append(f"{name}={status}")

    return f"⚠️ NPC STATE: {' | '.join(state_parts)}\n(Do not include these NPCs as active)"


# =============================================================================
# WORLD LORE SUMMARY
# =============================================================================

def format_world_lore_compact(
    lore_text: str,
    max_chars: int = 1200,
) -> str:
    """
    Format world lore compactly.

    Truncates to max_chars and ensures clean sentence boundary.
    """
    if not lore_text:
        return ""

    if len(lore_text) <= max_chars:
        return lore_text

    # Truncate at sentence boundary
    truncated = lore_text[:max_chars]
    last_period = truncated.rfind(".")
    if last_period > max_chars // 2:
        truncated = truncated[:last_period + 1]
    else:
        truncated = truncated.rstrip() + "..."

    return truncated


# =============================================================================
# STORYTELLING PREFERENCES
# =============================================================================

def format_storytelling_prefs_compact(
    lethality: str = "",
    moral_complexity: str = "",
    arc_guidance: str = "",
) -> str:
    """
    Format storytelling preferences compactly.

    Before (~100 tokens):
        === STORYTELLING PREFERENCES ===
        Lethality: High - death is a real possibility...
        Moral Complexity: Gray morality - no clear heroes...

    After (~30 tokens):
        PREFS: Lethality=HIGH | Morality=GRAY | Arc=heroic
    """
    parts = []
    if lethality:
        parts.append(f"Lethality={lethality.upper()[:6]}")
    if moral_complexity:
        parts.append(f"Morality={moral_complexity.upper()[:6]}")
    if arc_guidance:
        parts.append(f"Arc={arc_guidance[:15]}")

    return f"PREFS: {' | '.join(parts)}" if parts else ""
