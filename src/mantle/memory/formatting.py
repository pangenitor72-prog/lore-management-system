# src/mantle/memory/formatting.py
"""
Formatting utilities for memory display.

Separated from manager.py to avoid circular imports.
"""

from .models import Impression


def format_npc_relationship_context(impression: Impression, npc_name: str) -> str:
    """
    Format an NPC's relationship with the player for DM context injection.

    Returns a rich, readable summary the DM can use to inform NPC behavior.
    """
    # Determine disposition label
    if impression.trust > 0.7 and impression.affection > 0.6:
        disposition = "CLOSE ALLY"
    elif impression.trust > 0.6:
        disposition = "FRIENDLY"
    elif impression.trust > 0.4:
        disposition = "NEUTRAL"
    elif impression.trust > 0.2:
        disposition = "WARY"
    else:
        disposition = "HOSTILE"

    # Build context block
    lines = [
        f"**{npc_name}**",
        f"Disposition: {disposition} (trust: {int(impression.trust * 100)}%, respect: {int(impression.respect * 100)}%)",
    ]

    # Forms of address
    if impression.forms_of_address:
        lines.append(f'Calls player: "{impression.forms_of_address[0]}"')

    # Debt
    if impression.debt_to_player > 0.2:
        lines.append(f"OWES PLAYER: {impression.debt_reason or 'Unspecified favor'}")
    elif impression.debt_to_player < -0.2:
        lines.append(f"PLAYER OWES THEM: {impression.debt_reason or 'Unspecified debt'}")

    # Key memory
    if impression.summary:
        lines.append(f"Key memory: {impression.summary}")

    # Promises
    if impression.promises_made:
        lines.append(f"Has promised: {impression.promises_made[-1]}")
    if impression.promises_broken:
        lines.append(f"BROKEN PROMISE: {impression.promises_broken[-1]}")

    # Secrets
    if impression.shared_secrets:
        lines.append(f"Shared secret: {impression.shared_secrets[-1]}")

    # Behavioral guidance
    behaviors = []
    if impression.will_help:
        behaviors.append("willing to help")
    if impression.will_share_secrets:
        behaviors.append("may share secrets")
    if impression.will_betray:
        behaviors.append("may betray")
    if impression.fear > 0.5:
        behaviors.append("fearful")

    if behaviors:
        lines.append(f"Behavior: {', '.join(behaviors)}")

    return "\n".join(lines)
