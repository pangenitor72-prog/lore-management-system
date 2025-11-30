"""Boundary Enforcement Prompts - Player agency education."""

class BoundaryPrompts:
    """Prompts for educating players about game boundaries."""
    
    DECLARATION_REMINDER = """⚠️ **Player Boundary**: You cannot declare what exists in the world.

Instead, try:
- "I search for..." (the DM will tell you what you find)
- "Is there a...?" (the DM will determine if it exists)
- "I look around for..." (the DM describes what's present)"""

    OUTCOME_FORCING_REMINDER = """⚠️ **Player Boundary**: You cannot declare the outcome of your actions.

Instead, try:
- "I attempt to..." (the DM determines if you succeed)
- "I try to..." (the DM will resolve the action)
- "Can I...?" (the DM will tell you if it's possible)"""

    META_CONTROL_REMINDER = """⚠️ **Player Boundary**: You cannot control NPCs or define their motivations.

The DM controls all NPCs, world events, and hidden information.
You control only your character's actions and attempts."""

    REFRAME_TEMPLATE = """The player said: "{player_input}"

This violates game boundaries (players cannot {violation_type}).

Reframe this as a valid player action or question, then respond as DM.

IMPORTANT - When responding:
1. Consider if the thing SHOULD exist based on narrative logic
2. Context matters: On your own ship/home, you'd know what's there
3. Don't just give players what they want - maintain world consistency
4. It's OK to say "You search but find nothing" or "You already know every inch of this place"

Examples:
- "There's a trapdoor" → Player searches, but DM decides if one exists (probably not if it's their own home)
- "I find a sword" → Player searches, DM determines what's actually there (maybe nothing)
- "The king is evil" → Player tries to read the king, DM reveals only what's observable

Reframed action and DM response:"""
    
    @staticmethod
    def get_reminder(violation_type: str) -> str:
        """Get appropriate reminder for violation type."""
        reminders = {
            "declaration": BoundaryPrompts.DECLARATION_REMINDER,
            "outcome_forcing": BoundaryPrompts.OUTCOME_FORCING_REMINDER,
            "meta_control": BoundaryPrompts.META_CONTROL_REMINDER
        }
        return reminders.get(violation_type, "")
    
    @staticmethod
    def build_reframe_prompt(player_input: str, violation_type: str) -> str:
        """Build prompt to reframe invalid player input."""
        return BoundaryPrompts.REFRAME_TEMPLATE.format(
            player_input=player_input,
            violation_type=violation_type
        )

