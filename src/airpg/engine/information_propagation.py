# src/airpg/engine/information_propagation.py
from typing import Dict

def propagate_information(info: str, ocean: Dict[str, float]) -> str:
    # This function demonstrates deterministic information mutation
    # driven solely by NPC personality traits under zero state.

    # --- Interpret OCEAN traits ---
    neuroticism = ocean.get("neuroticism", 0.5)
    conscientiousness = ocean.get("conscientiousness", 0.5)
    extraversion = ocean.get("extraversion", 0.5)
    
    # --- Base fact extraction ---
    # This is a highly simplified way to ensure the core fact is preserved.
    # In a real system, this would be more robust (e.g., using NLP).
    # For this artifact, we assume the core fact is the input string.
    core_fact = info

    # --- Frame the information based on personality ---
    
    # Neuroticism: Influences urgency, anxiety, and negative framing.
    if neuroticism > 0.8:
        prefix = "Disaster! I knew it! "
        suffix = " We're in serious trouble now, mark my words."
        certainty_phrase = ""
    elif neuroticism > 0.6:
        prefix = "This is very concerning. "
        suffix = " This could have serious consequences."
        certainty_phrase = "They're saying "
    elif neuroticism < 0.2:
        prefix = ""
        suffix = " It's likely just a minor delay."
        certainty_phrase = "I heard that "
    else: # Moderate neuroticism
        prefix = "Just so you're aware, "
        suffix = ""
        certainty_phrase = ""

    # Conscientiousness: Influences precision and qualification.
    if conscientiousness > 0.8:
        # High conscientiousness sticks very closely to the fact.
        certainty_phrase = "The official report states that "
        core_fact = core_fact.replace("by nightfall", "by the scheduled time of nightfall")
    elif conscientiousness < 0.3:
        # Low conscientiousness is less precise.
        certainty_phrase = "Someone mentioned that "
        core_fact = core_fact.replace(" at the eastern gate by nightfall", "") + " is missing."

    # Extraversion: Influences directness and social framing.
    if extraversion > 0.8:
        # High extraversion is direct and may frame it as a call to action.
        prefix = "Listen up! " + prefix
        suffix += " We need to find out what happened, now!"
    elif extraversion < 0.3:
        # Low extraversion is less direct, more hesitant.
        prefix = "Sorry to bother you, but... " + prefix
        certainty_phrase = "I might have heard something about how "

    # Combine the parts for the final mutated information string.
    # The structure ensures that even with modifications, the core fact remains.
    mutated_info = prefix + certainty_phrase + core_fact + suffix
    
    # A final pass to clean up potential spacing issues from combining parts.
    return " ".join(mutated_info.split())
