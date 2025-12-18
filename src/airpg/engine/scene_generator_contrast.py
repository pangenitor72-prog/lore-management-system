# src/airpg/engine/scene_generator_contrast.py
"""
Generates a contrasting narrative scene that demonstrates a sharply different
NPC personality based on a hardcoded OCEAN profile, as per Phase 0 requirements.
"""

def generate_scene() -> str:
    """
    Generates a static scene with one NPC, one location, and one OCEAN profile
    that sharply contrasts with the 'scene_generator.py' example.

    The scene demonstrates the following OCEAN traits for the NPC, Commander Valerius:
    - Low Openness: Valerius focuses on concrete facts and dismisses abstract ideas.
    - High Conscientiousness: Shown by the meticulous order of his surroundings and his focus on procedure.
    - High Extraversion: Exhibited through his direct, assertive, and commanding presence.
    - Low Agreeableness: Comes across in his skepticism, bluntness, and focus on task over pleasantries.
    """

    # --- Hardcoded Data ---

    npc_name = "Commander Valerius"

    ocean_profile = {
        "openness": 0.2,        # Low: Concrete, traditional, dislikes abstraction
        "conscientiousness": 0.9, # High: Organized, dutiful, efficient
        "extraversion": 0.8,    # High: Assertive, energetic, enjoys leadership
        "agreeableness": 0.2,   # Low: Skeptical, challenging, blunt
        "neuroticism": 0.5,     # Moderate: Can be impatient or focused on potential problems
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
