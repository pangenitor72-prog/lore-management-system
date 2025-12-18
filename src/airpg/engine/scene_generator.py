# src/airpg/engine/scene_generator.py
"""
Generates a single, hardcoded narrative scene to demonstrate consistent NPC
personality based on a predefined OCEAN profile, as per Phase 0 requirements.
"""

def generate_scene() -> str:
    """

    # --- Hardcoded Data ---

    npc_name = "Kaelen"

    ocean_profile = {
        "openness": 0.9,
        "conscientiousness": 0.2,
        "extraversion": 0.3,
        "agreeableness": 0.8,
        "neuroticism": 0.1,
    }

    location_description = (
        "The air in the scriptorium is thick with the scent of old paper and beeswax. "
        "Sunlight, heavy with dust motes, cuts across towers of precariously stacked "
        "scrolls and leather-bound books that cover every available surface. A half-full "
        "cup of tea, long since gone cold, rests on a pile of star-charts."
    )

    # --- Scene Generation ---

    scene = (
        f"{location_description}\n\n"
        f"{npc_name} looks up from a massive, open tome, his finger still tracing a line of script. "
        "He doesn't seem surprised by the intrusion. A slow, gentle smile spreads across his face. "
        "'Ah, welcome,' he says, his voice a soft murmur. 'Come in, come in. Don't mind the... well, "
        "the delightful chaos. Each book is a universe, you see, and right now we're experiencing a "
        "rather beautiful cosmic collision.'\n\n"
        "He gestures vaguely toward a chair mostly buried under a heap of maps. 'I was just pondering "
        "the nature of echoes. Not of sound, but of intent. Do you think a forgotten promise leaves "
        "a... a residue? A faint vibration in the fabric of what-is? I'm sure I had a scroll on the "
        "subject somewhere.' He pushes a stack of parchments, which slide and threaten to collapse, "
        "before he pats the pile with a resigned sigh. 'No matter. What knowledge are you seeking to "
        "add to the beautiful mess?'"
    )

    return scene
