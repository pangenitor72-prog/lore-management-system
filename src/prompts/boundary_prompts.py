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

Examples:
- "There's a library here" → "You ask locals if there's a library. [DM generates response]"
- "I find a sword" → "You search for weapons. [DM determines what you find]"
- "The king is evil" → "You try to discern the king's true nature. [DM provides clues]"

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

