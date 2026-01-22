# This file exists solely as a Phase 1 validation artifact and is not part of
# the runtime engine.

from typing import Dict

def generate_scene(ocean: Dict[str, float]) -> str:
    npc_name = "Elara"
    location_description = (
        "The small alchemist's lab is a chaotic symphony of bubbling beakers, "
        "glowing retorts, and shelves overflowing with exotic herbs and dusty tomes. "
        "The air hums with faint, earthy aromas and a tangible sense of potent possibility."
    )

    # --- Interpret OCEAN traits ---
    openness = ocean.get("openness", 0.5)
    conscientiousness = ocean.get("conscientiousness", 0.5)
    agreeableness = ocean.get("agreeableness", 0.5)

    # --- Scene construction based on traits ---
    scene = f"{location_description}\n\n"

    # NPC's initial state/action based on conscientiousness
    if conscientiousness > 0.7:
        scene += (
            f"{npc_name} meticulously labels a vial, her movements precise and unhurried. "
            "Her workspace is surprisingly tidy amidst the general clutter of the lab. "
            "She turns slowly as you enter, her expression composed."
        )
        initial_greeting = "Welcome. Please, don't disturb the reagents. Everything has its place."
    elif conscientiousness < 0.3:
        scene += (
            f"{npc_name} startles as you enter, nearly knocking over a stack of empty bottles. "
            "She's hunched over a bubbling concoction, surrounded by scattered notes and half-eaten apples. "
            "She blinks at you, a smudge of soot on her cheek."
        )
        initial_greeting = "Oh! Didn't hear you. Always lost in the flow, you know? What brings you into this delightful chaos?"
    else: # Moderate conscientiousness
        scene += (
            f"{npc_name} pauses from stirring a dark liquid, setting her spoon down carefully. "
            "Her gaze is even, taking in your presence. She gestures vaguely around the organized mess."
        )
        initial_greeting = "Ah, a visitor. I was just at a critical juncture. How may I assist you?"


    # Dialogue style based on openness
    if openness > 0.7:
        dialogue_part_one = (
            f"'{initial_greeting} Tell me, have you ever considered how the very concept of a 'key' "
            "is just a formalized wish? A desire for access, made manifest in metal. "
            "What lock do you wish to open today, traveler? Not just a door, but perhaps a secret within yourself?'"
        )
    elif openness < 0.3:
        dialogue_part_one = (
            f"'{initial_greeting} State your purpose. I'm busy with practical matters. "
            "No riddles, just facts. What do you need?'"
        )
    else: # Moderate openness
        dialogue_part_one = (
            f"'{initial_greeting} So, what can I do for you? "
            "I'm generally occupied with my work, but I can spare a moment.'"
        )

    scene += f"\n\n{npc_name} says, {dialogue_part_one}\n\n"

    # Response to a hypothetical interruption (or general cooperativeness) based on agreeableness
    if agreeableness > 0.7:
        scene += (
            "You begin to speak, and Elara nods attentively, allowing you to finish "
            "before responding. 'Of course. Your needs are paramount. Let's explore the possibilities together.' "
            "She gestures towards a comfortable, albeit dust-covered, armchair."
        )
    elif agreeableness < 0.3:
        scene += (
            "You attempt to speak, but Elara cuts you off with a raised hand. "
            "'Hold that thought. I already anticipate your primary concern. Let me outline the options. "
            "Now, if you'll simply listen.' She turns back to her work, expecting compliance."
        )
    else: # Moderate agreeableness
        scene += (
            "You start to explain, and Elara listens, occasionally interjecting with a precise question. "
            "'Understood. We can proceed. What steps do you propose?' She awaits your direct answer."
        )


    return scene
