# This file exists solely as a Phase 1 validation artifact and is not part of
# the runtime engine.

from typing import Dict

def generate_scene() -> str:
    # --- Hardcoded Data ---

    npc_name = "Commander Valerius"

    ocean_profile = {
        "openness": 0.2,
        "conscientiousness": 0.9,
        "extraversion": 0.8,
        "agreeableness": 0.2,
        "neuroticism": 0.5,
    }

    location_description = (
        "The briefing room is stark, metal-paneled, and immaculately organized. "
        "A large tactical map glows faintly on the central table, surrounded by "
        "neatly arranged data slates. There is no dust, no misplaced item. "
        "The air is cool and still, humming with the quiet efficiency of unseen machinery."
    )

    # --- Scene Generation ---

    scene = (
        f"{location_description}\n\n"
        f"Commander Valerius stands rigidly by the tactical map, his arms crossed. His gaze, "
        "sharp and unwavering, fixes on you as you enter. There is no warmth, only an assessment. "
        "He clears his throat, a curt, deliberate sound. 'You're precisely three minutes late. "
        "My schedule is not a suggestion.'\n\n"
        "He jabs a finger at a blinking icon on the map. 'This is the objective. Concrete. Achievable. "
        "We move at 0600. I require actionable intelligence, not philosophical musings on 'echoes of intent.' "
        "What is your status report? And ensure it is concise. I have no patience for conjecture or metaphor. "
        "Just the facts, soldier. Progress, obstacles, and what you intend to do about them. Is that clear?'"
    )

    return scene
